import json
import errno
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import app


class EditTransactionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='gurumoji-edit-recovery-')
        self.root = Path(self.temporary.name)
        self.output = self.root / 'output'
        self.output.mkdir()
        self.original_database = app.DATABASE_FILE
        self.original_output = app.DEFAULT_OUTPUT_DIRECTORY
        app.DATABASE_FILE = self.root / 'library.sqlite3'
        app.DEFAULT_OUTPUT_DIRECTORY = self.output
        app.initialize_library()
        self.item_id = 'recovery-item'

    def tearDown(self):
        app.DATABASE_FILE = self.original_database
        app.DEFAULT_OUTPUT_DIRECTORY = self.original_output
        self.temporary.cleanup()

    def create_item(self, files):
        return app.upsert_library_item(
            item_id=self.item_id,
            source_name='meeting.wav',
            output_dir=self.output,
            media_path=None,
            language='ja',
            segments=[{
                'id': 's1', 'start': 0.0, 'end': 1.0,
                'speaker': 'S1', 'text': 'old',
            }],
            speaker_names={'S1': 'Speaker'},
            outline=None,
            emotion_analysis=None,
            files=files,
            write_srt=False,
            write_json=True,
        )

    def create_staging(self, contents):
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        staged_files = []
        for name, content in contents.items():
            staged = staging / name
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
            staged_files.append(staged)
        app.write_edit_transaction_manifest(
            staging,
            self.output,
            staged_files,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )
        return staging, staged_files

    @staticmethod
    def promote_one(staging, output, staged):
        relative = staged.relative_to(staging)
        target = output / relative
        if target.exists():
            backup = staging / '.previous' / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target)

    def test_uncommitted_promotion_restores_previous_file(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertEqual(target.read_bytes(), b'old')
        self.assertFalse(staging.exists())
        self.assertEqual(int(app.library_row(self.item_id)['revision_count']), 0)

    def test_committed_promotion_keeps_new_file_and_removes_backup(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        with app.database_connection() as connection:
            connection.execute(
                'UPDATE library_items SET revision_count = 1 WHERE id = ?',
                (self.item_id,),
            )

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertEqual(target.read_bytes(), b'new')
        self.assertFalse(staging.exists())

    def test_committed_database_with_unapplied_rename_finishes_promotion(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        with app.database_connection() as connection:
            connection.execute(
                'UPDATE library_items SET revision_count = 1 WHERE id = ?',
                (self.item_id,),
            )

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertEqual(target.read_bytes(), b'new')
        self.assertFalse(staging.exists())

    def test_target_tamper_is_rejected_before_first_promotion(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        target.write_bytes(b'external')

        with self.assertRaisesRegex(
            OSError,
            'changed (?:after manifest creation|ownership or content)',
        ):
            with app.promote_staged_files(staging, self.output, staged_files):
                self.fail('promotion must not start')

        self.assertEqual(target.read_bytes(), b'external')
        self.assertEqual(staged_files[0].read_bytes(), b'new')
        self.assertFalse((staging / '.previous').exists())
        self.assertTrue((staging / app.EDIT_TRANSACTION_MANIFEST_NAME).is_file())

    def test_staged_tamper_is_rejected_before_first_promotion(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        staged_files[0].write_bytes(b'tampered')

        with self.assertRaisesRegex(
            OSError,
            'changed (?:after manifest creation|ownership or content)',
        ):
            with app.promote_staged_files(staging, self.output, staged_files):
                self.fail('promotion must not start')

        self.assertEqual(target.read_bytes(), b'old')
        self.assertEqual(staged_files[0].read_bytes(), b'tampered')
        self.assertFalse((staging / '.previous').exists())
        self.assertTrue((staging / app.EDIT_TRANSACTION_MANIFEST_NAME).is_file())

    def test_tampered_backup_is_never_restored_over_new_target(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        backup = staging / '.previous' / target.name
        backup.write_bytes(b'tampered-backup')

        with self.assertRaisesRegex(RuntimeError, 'automatic import was stopped'):
            app.recover_edit_transactions()

        self.assertEqual(target.read_bytes(), b'new')
        self.assertEqual(backup.read_bytes(), b'tampered-backup')
        self.assertFalse((staging / '.discarded').exists())
        self.assertTrue((staging / app.EDIT_TRANSACTION_MANIFEST_NAME).is_file())

    def test_partial_multi_file_promotion_is_rolled_back(self):
        first = self.output / 'first.json'
        first.write_bytes(b'old-first')
        second = self.output / 'second.json'
        self.create_item([first])
        staging, staged_files = self.create_staging({
            'first.json': b'new-first',
            'second.json': b'new-second',
        })
        self.promote_one(staging, self.output, staged_files[0])

        app.recover_edit_transactions()

        self.assertEqual(first.read_bytes(), b'old-first')
        self.assertFalse(second.exists())
        self.assertFalse(staging.exists())

    def test_crash_after_backup_move_but_before_promotion_restores_old_file(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        backup = staging / '.previous' / target.name
        backup.parent.mkdir(parents=True)
        os.replace(target, backup)

        app.recover_edit_transactions()

        self.assertEqual(target.read_bytes(), b'old')
        self.assertFalse(staging.exists())

    def test_interrupted_recovery_is_idempotent_on_the_next_start(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        real_replace = os.replace
        failed = False

        def fail_first_backup_restore(source, destination):
            nonlocal failed
            if not failed and '.previous' in str(source):
                failed = True
                raise OSError('simulated recovery interruption')
            return real_replace(source, destination)

        with patch.object(app.os, 'replace', side_effect=fail_first_backup_restore):
            with self.assertRaisesRegex(RuntimeError, 'automatic import was stopped'):
                app.recover_edit_transactions()

        self.assertFalse(target.exists())
        self.assertTrue(staging.is_dir())
        self.assertEqual(app.recover_edit_transactions(), [])
        self.assertEqual(target.read_bytes(), b'old')
        self.assertFalse(staging.exists())

    def test_committed_cleanup_failure_is_retried_without_losing_manifest(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        with app.database_connection() as connection:
            connection.execute(
                'UPDATE library_items SET revision_count = 1 WHERE id = ?',
                (self.item_id,),
            )
        with patch.object(
            app,
            'remove_edit_directory_contents',
            side_effect=OSError('simulated locked backup'),
        ):
            warnings = app.recover_edit_transactions()

        self.assertTrue(warnings)
        self.assertEqual(
            len(list(staging.parent.glob('.edit-cleanup-*/.edit-transaction.json'))),
            1,
        )
        self.assertEqual(target.read_bytes(), b'new')
        self.assertEqual(app.recover_edit_transactions(), [])
        self.assertFalse(staging.exists())

    def test_delete_reconciles_committed_journal_before_removing_row(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        with app.database_connection() as connection:
            connection.execute(
                'UPDATE library_items SET revision_count = 1 WHERE id = ?',
                (self.item_id,),
            )

        response = app.app.test_client().delete(f'/api/library/{self.item_id}')

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(app.library_row(self.item_id))
        self.assertFalse(staging.exists())
        self.assertEqual(app.recover_edit_transactions(), [])

    def test_delete_is_blocked_until_committed_journal_cleanup_succeeds(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        with app.database_connection() as connection:
            connection.execute(
                'UPDATE library_items SET revision_count = 1 WHERE id = ?',
                (self.item_id,),
            )
        with patch.object(
            app,
            'remove_edit_directory_contents',
            side_effect=OSError('simulated locked backup'),
        ):
            blocked = app.app.test_client().delete(f'/api/library/{self.item_id}')

        self.assertEqual(blocked.status_code, 409)
        self.assertIsNotNone(app.library_row(self.item_id))
        self.assertEqual(
            len(list(staging.parent.glob('.edit-cleanup-*/.edit-transaction.json'))),
            1,
        )

        retried = app.app.test_client().delete(f'/api/library/{self.item_id}')
        self.assertEqual(retried.status_code, 200)
        self.assertIsNone(app.library_row(self.item_id))
        self.assertFalse(staging.exists())

    def test_new_source_name_cannot_bypass_pending_journal_in_old_output(self):
        self.create_item([])
        old_output = app.manual_output_directory('first.wav', self.item_id)
        old_output.mkdir(parents=True, exist_ok=True)
        staging = old_output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        staged = staging / 'old-result.json'
        staged.write_bytes(b'old-attempt')
        app.write_edit_transaction_manifest(
            staging,
            old_output,
            [staged],
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )
        self.promote_one(staging, old_output, staged)
        row = app.library_row(self.item_id)
        payload = {
            'revision_count': 0,
            'source_name': 'second.wav',
            'segments': app.row_segments(row),
            'speaker_names': {'S1': 'Speaker'},
        }
        with patch.object(
            app,
            'remove_edit_directory_contents',
            side_effect=OSError('simulated locked discard'),
        ):
            with self.assertRaisesRegex(OSError, 'pending edit transaction'):
                app.update_library_from_payload(self.item_id, payload)

        self.assertEqual(int(app.library_row(self.item_id)['revision_count']), 0)
        self.assertEqual(
            len(list(staging.parent.glob('.edit-cleanup-*/.edit-transaction.json'))),
            1,
        )

        result = app.update_library_from_payload(self.item_id, payload)

        self.assertEqual(result['revision_count'], 1)
        self.assertFalse(staging.exists())
        self.assertFalse((old_output / 'old-result.json').exists())
        self.assertEqual(app.recover_edit_transactions(), [])

    def test_commit_then_interrupt_keeps_database_and_new_outputs_consistent(self):
        self.create_item([])
        row = app.library_row(self.item_id)
        training_clip = self.root / 'committed-training-clip.wav'
        training_clip.write_bytes(b'clip')
        training_event = {
            'event_id': 'e' * 32,
            'created_at': '2026-07-31T00:00:00+00:00',
            'audio_clip': str(training_clip),
        }
        payload = {
            'revision_count': 0,
            'source_name': 'meeting.wav',
            'segments': app.row_segments(row),
            'speaker_names': {'S1': 'Speaker'},
        }
        raised_after_commit = False

        @contextmanager
        def ambiguous_connection():
            nonlocal raised_after_commit
            connection = sqlite3.connect(app.DATABASE_FILE, timeout=30)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
                connection.commit()
                current = connection.execute(
                    'SELECT revision_count FROM library_items WHERE id = ?',
                    (self.item_id,),
                ).fetchone()
                if (
                    current is not None
                    and int(current['revision_count'] or 0) == 1
                    and not raised_after_commit
                ):
                    raised_after_commit = True
                    raise KeyboardInterrupt('commit result became ambiguous')
            except BaseException:
                connection.rollback()
                raise
            finally:
                connection.close()

        with (
            patch.object(app, 'database_connection', ambiguous_connection),
            patch.object(
                app,
                'prepare_training_corrections',
                return_value=([training_event], [training_clip]),
            ),
        ):
            with self.assertRaises(KeyboardInterrupt):
                app.update_library_from_payload(self.item_id, payload)

        stored = app.library_row(self.item_id)
        self.assertEqual(int(stored['revision_count']), 1)
        final_files = [Path(value) for value in json.loads(stored['files_json'])]
        self.assertTrue(final_files)
        self.assertTrue(all(path.is_file() for path in final_files))
        self.assertTrue(training_clip.is_file())
        with app.database_connection() as connection:
            self.assertEqual(
                connection.execute(
                    'SELECT COUNT(*) FROM training_events WHERE event_id = ?',
                    (training_event['event_id'],),
                ).fetchone()[0],
                1,
            )
        self.assertEqual(app.recover_edit_transactions(), [])
        self.assertEqual(
            list(Path(stored['output_dir']).glob('.edit-staging-*')),
            [],
        )

    def test_failed_optional_video_assets_do_not_leave_unlisted_stage_files(self):
        media = self.root / 'source.mp4'
        media.write_bytes(b'video-placeholder')
        app.upsert_library_item(
            item_id=self.item_id,
            source_name='meeting.mp4',
            output_dir=self.output,
            media_path=media,
            language='ja',
            segments=[{
                'id': 's1', 'start': 0.0, 'end': 1.0,
                'speaker': 'S1', 'text': 'old',
            }],
            speaker_names={'S1': 'Speaker'},
            outline=None,
            emotion_analysis=None,
            files=[],
            write_srt=False,
            write_json=True,
            burn_subtitled_video=True,
        )
        row = app.library_row(self.item_id)
        payload = {
            'revision_count': 0,
            'source_name': 'meeting.mp4',
            'segments': app.row_segments(row),
            'speaker_names': {'S1': 'Speaker'},
        }

        def fail_after_partial_ass(*args, **kwargs):
            staging_dir = Path(args[2])
            (staging_dir / 'partial_話者カラー字幕.ass').write_text(
                'partial', encoding='utf-8'
            )
            raise RuntimeError('simulated video failure')

        with patch.object(
            app,
            'write_subtitled_video_assets',
            side_effect=fail_after_partial_ass,
        ):
            with self.assertRaisesRegex(OSError, 'unauthenticated files'):
                app.update_library_from_payload(self.item_id, payload)

        stages = list(self.output.rglob('.edit-staging-*'))
        self.assertEqual(len(stages), 1)
        self.assertTrue(list(stages[0].glob('partial_*ass')))
        self.assertTrue((stages[0] / app.EDIT_PREPARATION_MARKER_NAME).is_file())
        self.assertEqual(int(app.library_row(self.item_id)['revision_count']), 0)

    def test_later_revision_is_never_overwritten_by_stale_journal(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})
        self.promote_one(staging, self.output, staged_files[0])
        target.write_bytes(b'later revision')
        with app.database_connection() as connection:
            connection.execute(
                'UPDATE library_items SET revision_count = 2 WHERE id = ?',
                (self.item_id,),
            )

        app.recover_edit_transactions()

        self.assertEqual(target.read_bytes(), b'later revision')
        self.assertFalse(staging.exists())

    def test_modified_manifest_is_retained_and_blocks_recovery(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        unrelated = self.output / 'unrelated.json'
        unrelated.write_bytes(b'unrelated')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        manifest = staging / app.EDIT_TRANSACTION_MANIFEST_NAME
        payload = json.loads(manifest.read_text(encoding='utf-8'))
        payload['files'][0]['relative_path'] = 'unrelated.json'
        manifest.write_text(json.dumps(payload), encoding='utf-8')

        with self.assertRaisesRegex(RuntimeError, 'automatic import was stopped'):
            app.recover_edit_transactions()

        self.assertEqual(target.read_bytes(), b'old')
        self.assertEqual(unrelated.read_bytes(), b'unrelated')
        self.assertTrue(staging.is_dir())

    def test_manifestless_preparation_crash_is_cleaned(self):
        self.create_item([])
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        app.write_edit_preparation_marker(
            staging,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )
        staged = staging / 'not-promoted.json'
        staged.write_bytes(b'new')
        app.write_edit_preparation_marker(
            staging,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
            staged_files=[staged],
        )

        self.assertEqual(app.recover_edit_transactions(), [])
        self.assertFalse(staging.exists())

    def test_unsigned_partial_preparation_is_retained(self):
        self.create_item([])
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        app.write_edit_preparation_marker(
            staging,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )
        partial = staging / 'unsigned-partial.json'
        partial.write_bytes(b'not-in-marker')

        with self.assertRaisesRegex(RuntimeError, 'automatic import was stopped'):
            app.recover_edit_transactions()

        self.assertEqual(partial.read_bytes(), b'not-in-marker')
        self.assertTrue((staging / app.EDIT_PREPARATION_MARKER_NAME).is_file())

    def test_crash_with_both_authenticated_journals_is_recovered(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        staged = staging / target.name
        staged.write_bytes(b'new')
        marker = app.write_edit_preparation_marker(
            staging,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
            staged_files=[staged],
        )
        marker_content = marker.read_bytes()
        app.write_edit_transaction_manifest(
            staging,
            self.output,
            [staged],
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )
        marker.write_bytes(marker_content)

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertEqual(target.read_bytes(), b'old')
        self.assertFalse(staging.exists())

    def test_empty_preparing_crash_does_not_block_startup(self):
        self.create_item([])
        preparing = self.output / (
            f'.edit-preparing-{uuid.uuid4().hex}-{uuid.uuid4().hex}'
        )
        preparing.mkdir()

        self.assertEqual(app.recover_edit_transactions(), [])
        self.assertFalse(preparing.exists())

    def test_authenticated_preparing_crash_is_cleaned(self):
        self.create_item([])
        preparing = self.output / (
            f'.edit-preparing-{uuid.uuid4().hex}-{uuid.uuid4().hex}'
        )
        preparing.mkdir()
        app.write_edit_preparation_marker(
            preparing,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )

        self.assertEqual(app.recover_edit_transactions(), [])
        self.assertFalse(preparing.exists())

    def test_cleanup_quarantine_is_restored_and_recovered_on_startup(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        cleanup = staging.with_name(
            f'.edit-cleanup-{staging.name.lstrip(chr(46))}-{uuid.uuid4().hex}'
        )
        os.replace(staging, cleanup)

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertEqual(target.read_bytes(), b'old')
        self.assertFalse(staging.exists())
        self.assertFalse(cleanup.exists())

    def test_windows_unsafe_transaction_paths_are_rejected_on_all_platforms(self):
        unsafe = [
            'a//b.json',
            'a/',
            '../outside.json',
            'NUL.txt',
            'NUL .txt',
            'COM1 .json',
            'LPT9 .log',
            'file:stream.json',
            'trailing.',
            'trailing ',
            '.Previous/file.json',
            '.EDIT-TRANSACTION.JSON',
            'bad?.json',
            'a\\b.json',
            'bad' + chr(34) + '.json',
        ]
        for value in unsafe:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    app.safe_edit_relative_path(value)

    def test_discovery_rejects_reparse_ancestor_of_output_root(self):
        with patch.object(app, 'path_has_reparse_ancestor', return_value=True):
            with self.assertRaisesRegex(OSError, 'Unsafe default output directory'):
                app.discover_edit_transaction_staging_dirs(
                    include_database_outputs=False,
                )

    def test_discovery_does_not_descend_reparse_child(self):
        linked = self.output / 'linked-output'
        hidden = linked / f'.edit-staging-{uuid.uuid4().hex}'
        hidden.mkdir(parents=True)
        real_check = app.path_is_link_or_reparse

        def mark_linked(path):
            candidate = Path(path)
            if candidate == linked:
                return True
            return real_check(candidate)

        with patch.object(app, 'path_is_link_or_reparse', side_effect=mark_linked):
            found = app.discover_edit_transaction_staging_dirs(
                include_database_outputs=False,
            )

        self.assertNotIn(hidden, found)

    def test_discovery_rejects_stage_named_reparse_point(self):
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        real_check = app.path_is_link_or_reparse

        def mark_staging(path):
            candidate = Path(path)
            if candidate == staging:
                return True
            return real_check(candidate)

        with patch.object(app, 'path_is_link_or_reparse', side_effect=mark_staging):
            with self.assertRaisesRegex(OSError, 'reparse point'):
                app.discover_edit_transaction_staging_dirs(
                    include_database_outputs=False,
                )

    def test_manifest_rejects_ntfs_case_duplicate_targets(self):
        self.create_item([])
        staging, _ = self.create_staging({'Report.json': b'new'})
        manifest = staging / app.EDIT_TRANSACTION_MANIFEST_NAME
        payload = json.loads(manifest.read_text(encoding='utf-8'))
        duplicate = dict(payload['files'][0])
        duplicate['relative_path'] = 'report.JSON'
        payload['files'].append(duplicate)
        payload.pop('mac')
        with app.database_connection() as connection:
            secret = app.edit_journal_secret(connection)
            storage_id = app.edit_storage_id(connection)
        payload['mac'] = app.edit_journal_mac(payload, secret)
        manifest.write_text(json.dumps(payload), encoding='utf-8')

        with self.assertRaisesRegex(ValueError, 'duplicate targets'):
            app.load_edit_transaction_manifest(
                staging,
                expected_storage_id=storage_id,
                expected_secret=secret,
            )

    def test_unowned_manifestless_directory_is_retained_and_blocks_startup(self):
        self.create_item([])
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        (staging / 'user-file.json').write_bytes(b'do not delete')

        with self.assertRaisesRegex(RuntimeError, 'automatic import was stopped'):
            app.recover_edit_transactions()

        self.assertEqual((staging / 'user-file.json').read_bytes(), b'do not delete')

    def test_publish_collision_never_deletes_unowned_final_stage(self):
        self.create_item([])
        row = app.library_row(self.item_id)
        payload = {
            'revision_count': 0,
            'source_name': 'meeting.wav',
            'segments': app.row_segments(row),
            'speaker_names': {'S1': 'Speaker'},
        }
        real_move = app.durable_move
        collision_stage = None

        def collide_on_publish(source, destination, *, replace_existing=True):
            nonlocal collision_stage
            source = Path(source)
            destination = Path(destination)
            if (
                source.name.startswith('.edit-preparing-')
                and destination.name.startswith('.edit-staging-')
            ):
                collision_stage = destination
                destination.mkdir(parents=True, exist_ok=False)
                (destination / 'sentinel.txt').write_bytes(b'not-owned')
                raise FileExistsError('simulated publish collision')
            return real_move(
                source,
                destination,
                replace_existing=replace_existing,
            )

        with patch.object(app, 'durable_move', side_effect=collide_on_publish):
            with self.assertRaises(FileExistsError):
                app.update_library_from_payload(self.item_id, payload)

        self.assertIsNotNone(collision_stage)
        self.assertEqual(
            (collision_stage / 'sentinel.txt').read_bytes(),
            b'not-owned',
        )
        self.assertEqual(
            list(collision_stage.parent.glob('.edit-preparing-*')),
            [],
        )

    def test_update_reconciles_pending_preparation_before_mutation(self):
        self.create_item([])
        staging = self.output / f'.edit-staging-{uuid.uuid4().hex}'
        staging.mkdir()
        app.write_edit_preparation_marker(
            staging,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
        )
        staged = staging / 'partial.json'
        staged.write_bytes(b'partial')
        app.write_edit_preparation_marker(
            staging,
            self.output,
            item_id=self.item_id,
            expected_revision=0,
            previous_output_dir=self.output,
            staged_files=[staged],
        )
        row = app.library_row(self.item_id)

        result = app.update_library_from_payload(self.item_id, {
            'revision_count': 0,
            'source_name': 'meeting.wav',
            'segments': app.row_segments(row),
            'speaker_names': {'S1': 'Speaker'},
        })

        self.assertEqual(result['revision_count'], 1)
        self.assertFalse(staging.exists())
        self.assertEqual(app.recover_edit_transactions(), [])

    def test_cleanup_rejects_stage_replaced_after_authenticated_load(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        with app.database_connection() as connection:
            storage_id = app.edit_storage_id(connection)
            secret = app.edit_journal_secret(connection)
        loaded = app.load_edit_transaction_manifest(
            staging,
            expected_storage_id=storage_id,
            expected_secret=secret,
        )
        authentic = staging.with_name(staging.name + '-authentic')
        os.replace(staging, authentic)
        staging.mkdir()
        sentinel = staging / 'victim.txt'
        sentinel.write_bytes(b'do-not-delete')

        cleanup_errors = app.cleanup_edit_staging(
            staging,
            expected_identity=loaded['_staging_identity'],
            inventory=loaded['_cleanup_inventory'],
        )

        self.assertTrue(cleanup_errors)
        self.assertEqual(sentinel.read_bytes(), b'do-not-delete')
        self.assertTrue(authentic.is_dir())

    def test_cleanup_never_deletes_entries_injected_after_inventory(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        with app.database_connection() as connection:
            storage_id = app.edit_storage_id(connection)
            secret = app.edit_journal_secret(connection)
        loaded = app.load_edit_transaction_manifest(
            staging,
            expected_storage_id=storage_id,
            expected_secret=secret,
        )
        outside_file = self.root / 'user-owned.txt'
        outside_file.write_bytes(b'user-file')
        outside_directory = self.root / 'user-owned-directory'
        outside_directory.mkdir()
        (outside_directory / 'sentinel.txt').write_bytes(b'user-directory')
        injected_file = staging / 'injected-file.txt'
        injected_directory = staging / 'injected-directory'
        os.replace(outside_file, injected_file)
        os.replace(outside_directory, injected_directory)

        cleanup_errors = app.cleanup_edit_staging(
            staging,
            expected_identity=loaded['_staging_identity'],
            inventory=loaded['_cleanup_inventory'],
        )

        self.assertTrue(cleanup_errors)
        self.assertEqual(injected_file.read_bytes(), b'user-file')
        self.assertEqual(
            (injected_directory / 'sentinel.txt').read_bytes(),
            b'user-directory',
        )
        self.assertTrue((staging / app.EDIT_TRANSACTION_MANIFEST_NAME).is_file())

    def test_conflicting_recreated_journal_preserves_authenticated_snapshot(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, _ = self.create_staging({'transcript.json': b'new'})
        manifest = staging / app.EDIT_TRANSACTION_MANIFEST_NAME
        authenticated_content = manifest.read_bytes()
        with app.database_connection() as connection:
            storage_id = app.edit_storage_id(connection)
            secret = app.edit_journal_secret(connection)
        loaded = app.load_edit_transaction_manifest(
            staging,
            expected_storage_id=storage_id,
            expected_secret=secret,
        )
        def recreate_during_cleanup(directory, *args, **kwargs):
            quarantined_manifest = Path(directory) / app.EDIT_TRANSACTION_MANIFEST_NAME
            quarantined_manifest.unlink()
            quarantined_manifest.write_bytes(b'foreign-replacement')
            raise OSError('simulated final cleanup conflict')

        with patch.object(
            app,
            'remove_edit_directory_contents',
            side_effect=recreate_during_cleanup,
        ):
            cleanup_errors = app.cleanup_edit_staging(
                staging,
                expected_identity=loaded['_staging_identity'],
                inventory=loaded['_cleanup_inventory'],
            )

        self.assertTrue(cleanup_errors)
        quarantines = list(self.output.glob('.edit-cleanup-*'))
        self.assertEqual(len(quarantines), 1)
        quarantine = quarantines[0]
        self.assertEqual(
            (quarantine / app.EDIT_TRANSACTION_MANIFEST_NAME).read_bytes(),
            b'foreign-replacement',
        )
        recovery_snapshots = list(quarantine.glob('*.authenticated-*.recovery'))
        self.assertEqual(len(recovery_snapshots), 1)
        self.assertEqual(recovery_snapshots[0].read_bytes(), authenticated_content)
        self.assertEqual(
            app.discover_edit_transaction_staging_dirs(
                include_database_outputs=False,
            ),
            [],
        )
        self.assertTrue(quarantine.is_dir())

    def test_target_changed_during_commit_retains_old_and_new_recovery_files(self):
        target = self.output / 'transcript.json'
        target.write_bytes(b'old')
        self.create_item([target])
        staging, staged_files = self.create_staging({'transcript.json': b'new'})

        with self.assertRaisesRegex(OSError, 'state was uncertain'):
            with app.promote_staged_files(staging, self.output, staged_files):
                with app.database_connection() as connection:
                    connection.execute(
                        'UPDATE library_items SET revision_count = 1 WHERE id = ?',
                        (self.item_id,),
                    )
                target.write_bytes(b'external-during-commit')

        self.assertEqual(target.read_bytes(), b'external-during-commit')
        self.assertEqual(staged_files[0].read_bytes(), b'new')
        self.assertEqual(
            (staging / '.previous' / target.name).read_bytes(),
            b'old',
        )
        self.assertTrue((staging / app.EDIT_TRANSACTION_MANIFEST_NAME).is_file())
        self.assertEqual(int(app.library_row(self.item_id)['revision_count']), 1)
        with self.assertRaisesRegex(RuntimeError, 'automatic import was stopped'):
            app.recover_edit_transactions()

    def test_failed_write_cleanup_retains_authenticated_marker_when_locked(self):
        self.create_item([])
        row = app.library_row(self.item_id)
        payload = {
            'revision_count': 0,
            'source_name': 'meeting.wav',
            'segments': app.row_segments(row),
            'speaker_names': {'S1': 'Speaker'},
        }

        def fail_write_outputs(source_name, staging_dir, *args, **kwargs):
            (Path(staging_dir) / 'partial.json').write_bytes(b'partial')
            raise OSError('simulated output failure')

        with (
            patch.object(app, 'write_outputs', side_effect=fail_write_outputs),
            patch.object(
                app,
                'remove_edit_directory_contents',
                side_effect=OSError('simulated locked stage'),
            ),
        ):
            with self.assertRaisesRegex(OSError, 'cleanup was incomplete'):
                app.update_library_from_payload(self.item_id, payload)

        stages = list(self.output.rglob('.edit-staging-*'))
        self.assertEqual(len(stages), 1)
        self.assertTrue((stages[0] / app.EDIT_PREPARATION_MARKER_NAME).is_file())
        self.assertEqual((stages[0] / 'partial.json').read_bytes(), b'partial')

    def test_empty_cleanup_quarantine_is_removed_without_restore(self):
        cleanup = self.output / (
            f'.edit-cleanup-edit-staging-{uuid.uuid4().hex}-{uuid.uuid4().hex}'
        )
        cleanup.mkdir()

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertFalse(cleanup.exists())
        self.assertEqual(list(self.output.glob('.edit-staging-*')), [])

    def test_nonempty_journalless_cleanup_quarantine_is_retained(self):
        cleanup = self.output / (
            f'.edit-cleanup-edit-staging-{uuid.uuid4().hex}-{uuid.uuid4().hex}'
        )
        cleanup.mkdir()
        sentinel = cleanup / 'sentinel.txt'
        sentinel.write_bytes(b'keep')

        self.assertEqual(app.recover_edit_transactions(), [])

        self.assertEqual(sentinel.read_bytes(), b'keep')
        self.assertEqual(list(self.output.glob('.edit-staging-*')), [])

    def test_windows_device_namespaces_are_rejected(self):
        for value in (
            r'\\.\PhysicalDrive0',
            r'\\.\PIPE\gurumoji',
            r'\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1',
        ):
            with self.subTest(value=value):
                with self.assertRaises(OSError):
                    app.windows_extended_path(Path(value))

    def test_windows_path_key_matches_ntfs_without_unicode_expansion(self):
        self.assertEqual(
            app.edit_relative_path_key(Path('Report.JSON')),
            app.edit_relative_path_key(Path('report.json')),
        )
        self.assertNotEqual(
            app.edit_relative_path_key(Path('Straße.json')),
            app.edit_relative_path_key(Path('STRASSE.json')),
        )
        self.assertNotEqual(
            app.edit_relative_path_key(Path('İ.json')),
            app.edit_relative_path_key(Path('i\u0307.json')),
        )

    def test_required_directory_sync_propagates_io_errors(self):
        with (
            patch.object(app.os, 'name', 'posix'),
            patch.object(app.os, 'open', return_value=91),
            patch.object(
                app.os,
                'fsync',
                side_effect=OSError(errno.EIO, 'simulated directory I/O failure'),
            ),
            patch.object(app.os, 'close'),
        ):
            with self.assertRaises(OSError) as raised:
                app.sync_directory_metadata(self.output, required=True)
        self.assertEqual(raised.exception.errno, errno.EIO)

    def test_unsupported_directory_sync_is_tolerated(self):
        with (
            patch.object(app.os, 'name', 'posix'),
            patch.object(app.os, 'open', return_value=92),
            patch.object(
                app.os,
                'fsync',
                side_effect=OSError(errno.EINVAL, 'directory fsync unsupported'),
            ),
            patch.object(app.os, 'close'),
        ):
            app.sync_directory_metadata(self.output, required=True)

    def test_durable_move_reports_post_rename_sync_failure(self):
        source = self.root / 'durability-source.txt'
        destination = self.root / 'durability-destination.txt'
        source.write_bytes(b'value')
        real_replace = app.os.replace
        with (
            patch.object(app.os, 'name', 'posix'),
            patch.object(app.os, 'replace', wraps=real_replace),
            patch.object(
                app,
                'sync_rename_metadata',
                side_effect=OSError(errno.EIO, 'simulated directory I/O failure'),
            ),
        ):
            with self.assertRaises(OSError) as raised:
                app.durable_move(source, destination)
        self.assertEqual(raised.exception.errno, errno.EIO)
        self.assertEqual(destination.read_bytes(), b'value')

    def test_posix_link_fallback_never_deletes_replaced_destination(self):
        source = self.root / 'link-source.txt'
        destination = self.root / 'link-destination.txt'
        source.write_bytes(b'owned')
        real_unlink = Path.unlink

        def fail_source_unlink(path, *args, **kwargs):
            if path == source:
                real_unlink(destination)
                destination.write_bytes(b'unowned-replacement')
                raise OSError(errno.EIO, 'simulated source unlink failure')
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, 'unlink', new=fail_source_unlink):
            with self.assertRaises(OSError):
                app.posix_move_no_replace(source, destination)

        self.assertEqual(source.read_bytes(), b'owned')
        self.assertEqual(destination.read_bytes(), b'unowned-replacement')

    def test_real_child_process_exit_after_promotion_is_recovered(self):
        child_root = self.root / 'hard-crash'
        child_data = child_root / 'data'
        child_output = child_root / 'output'
        worker = r'''
import os
import sys
import uuid
from pathlib import Path

import app

output = app.DEFAULT_OUTPUT_DIRECTORY
output.mkdir(parents=True, exist_ok=True)
app.initialize_library()
item_id = 'hard-crash-item'
target = output / 'hard-crash.json'
target.write_bytes(b'old')
app.upsert_library_item(
    item_id=item_id,
    source_name='hard-crash.wav',
    output_dir=output,
    media_path=None,
    language='ja',
    segments=[{
        'id': 's1', 'start': 0.0, 'end': 1.0,
        'speaker': 'S1', 'text': 'old',
    }],
    speaker_names={'S1': 'Speaker'},
    outline=None,
    emotion_analysis=None,
    files=[target],
    write_srt=False,
    write_json=True,
)
staging = output / f'.edit-staging-{uuid.uuid4().hex}'
staging.mkdir()
staged = staging / target.name
staged.write_bytes(b'new')
app.write_edit_transaction_manifest(
    staging,
    output,
    [staged],
    item_id=item_id,
    expected_revision=0,
    previous_output_dir=output,
)
backup = staging / '.previous' / target.name
backup.parent.mkdir(parents=True)
os.replace(target, backup)
os.replace(staged, target)
os._exit(97)
'''
        environment = os.environ.copy()
        environment['MOJIOKOSI_DATA_DIR'] = str(child_data)
        environment['MOJIOKOSI_OUTPUT_DIR'] = str(child_output)
        completed = subprocess.run(
            [sys.executable, '-c', worker],
            cwd=Path(app.__file__).resolve().parent,
            env=environment,
            check=False,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 97)
        self.assertEqual((child_output / 'hard-crash.json').read_bytes(), b'new')

        fixture_database = app.DATABASE_FILE
        fixture_output = app.DEFAULT_OUTPUT_DIRECTORY
        try:
            app.DATABASE_FILE = child_data / 'library.sqlite3'
            app.DEFAULT_OUTPUT_DIRECTORY = child_output
            self.assertEqual(app.recover_edit_transactions(), [])
        finally:
            app.DATABASE_FILE = fixture_database
            app.DEFAULT_OUTPUT_DIRECTORY = fixture_output

        self.assertEqual((child_output / 'hard-crash.json').read_bytes(), b'old')
        self.assertEqual(list(child_output.glob('.edit-staging-*')), [])


if __name__ == '__main__':
    unittest.main()
