"""I3b acceptance using only fictional records and temporary database/files."""

import io
import json
import unittest
from unittest.mock import patch

import app
import test_data_catalog as fixtures
import test_analysis_definition_safety as definition_fixtures
from gurumoji.analysis_pipeline import AnalysisPipelineService
from gurumoji.services import change_log as history, data_catalog as catalog, library_trash as trash


class ResearcherChangesTests(unittest.TestCase):
    def setUp(self):
        fixtures.DataCatalogTests.setUp(self)

    def replay(self, entity, identity):
        with app.database_connection() as db:
            rows = history.rows(db, entity, identity)
            self.assertTrue(rows, (entity, identity))
            self.assertEqual(history.reconstruct(rows), history.current(db, entity, identity))
            self.assertEqual(rows[0]["origin"], "rule")
            self.assertEqual(json.loads(rows[0]["ops_json"])["past_origin"], "unknown")
            return rows

    def dump(self):
        with app.database_connection() as db:
            return list(db.iterdump())

    def pipeline(self):
        return AnalysisPipelineService(connect=app.database_connection, find_item=app.library_row,
            source_fingerprint=lambda _: "fictional-input",
            snapshot_builder=lambda _: {"input_hash": "fictional-input", "source_revision": 0,
                "analysis_revision": 0, "analysis": {"segments": [{"id": "u1", "text": "abc"}]},
                "archive_snapshot": {"segments": [{"id": "u1", "text": "abc"}]}},
            method_runner=lambda *_: {}, save_result=lambda **_: {}, publish_result=lambda *_: {},
            publication_outcomes=lambda *_: {}, public_run=lambda *_: {}, runtime_key=str(self.root))

    def annotate(self, **extra):
        row = app.library_row("a")
        return app.save_group_analysis("a", {"source_revision": row["revision_count"],
            "analysis_revision": row["analysis_revision"], **extra})

    def seed_catalog(self):
        with app.database_connection() as db:
            catalog.save_definition(db, {"key": "region", "scope": "conversation"})
            catalog.save_attributes(db, "a", {"region": "east"})
            tag = catalog.save_tag(db, {"name": "fictional tag"})
            group = catalog.save_group(db, {"name": "fictional group"})
            catalog.assign(db, "tags", tag["tag_id"], ["a", "b"])
            catalog.assign(db, "groups", group["group_id"], ["a", "b"])
        return tag["tag_id"], group["group_id"]

    def test_explicit_legacy_switch_is_readonly_idempotent_and_preserves_exact_values(self):
        tag, group = self.seed_catalog()
        app.save_speaker_registry_records([{"id": "speaker01", "display_name": "fictional",
            "attributes": {"question": None}}], expected_revision=0)
        self.pipeline().save_definition("a", "text_size", definition_fixtures.definition())
        with app.database_connection() as db:
            # Synthetic old installation: no I3b records exist yet.
            db.execute("DELETE FROM change_log")
            db.execute("UPDATE library_items SET analysis_config_json=?,analysis_annotations_json=? WHERE id='a'",
                ('{ "unknown": {"keep": 1} }', '{"removed_id":{"memo":"fictional legacy"}}'))
            history.capture(db, "vocabulary_terms", "global", {}, ["fictional"])
            before_vocabulary = history.rows(db, "vocabulary_terms", "global")
        before = self.dump()
        with app.database_connection() as db:
            report = history.fix_initial_states(db)
        self.assertGreater(report["unrecorded"], 0)
        self.assertEqual(self.dump(), before)
        with app.database_connection() as db:
            history.fix_initial_states(db, dry_run=False)
            self.assertEqual(history.rows(db, "vocabulary_terms", "global"), before_vocabulary)
        fixed = self.dump()
        with app.database_connection() as db:
            self.assertEqual(history.fix_initial_states(db, dry_run=False)["unrecorded"], 0)
            targets = list(db.execute("SELECT DISTINCT entity,entity_id FROM change_log WHERE entity!='vocabulary_terms'"))
        self.assertEqual(self.dump(), fixed)
        for target in targets:
            self.replay(*target)
        self.assertEqual(len(self.replay("analysis_config", "a")), 1)
        self.assertEqual(history.reconstruct(self.replay("analysis_config", "a")),
            {"analysis_config_json": '{ "unknown": {"keep": 1} }'})
        self.annotate(config={"research_question": "changed fictional"},
            annotations={"u1": {"memo": "changed fictional"}})
        app.save_speaker_registry_records([{"id": "speaker01", "display_name": "changed fictional"}], expected_revision=1)
        self.pipeline().save_definition("a", "text_size", definition_fixtures.definition(
            expected_revision=1, description="changed fictional"))
        with app.database_connection() as db:
            catalog.save_definition(db, {"scope": "conversation", "key": "region", "version": 1,
                "description": "changed fictional"})
            catalog.save_attributes(db, "a", {"region": "west"})
            catalog.save_tag(db, {"name": "changed fictional"}, tag)
            current_group = history.current(db, "data_groups", group)
            catalog.save_group(db, {"name": "changed fictional", "version": current_group["version"]}, group)
            catalog.assign(db, "tags", tag, ["a"], True)
            catalog.assign(db, "groups", group, ["a"], True)
        for target in targets:
            self.replay(*target)

    def test_annotation_codebook_config_and_orphans_replay_after_each_save(self):
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET analysis_annotations_json=? WHERE id='a'",
                ('{"old_id":{"memo":"fictional old"}}',))
        self.annotate(config={"research_question": "fictional question", "codebook": [
            {"id": "c1", "label": "fictional code"}], "codebook_change_reason": "fictional reason"},
            annotations={"u1": {"codes": ["c1"], "memo": "fictional annotation", "important": True}})
        for entity in ("analysis_annotations", "analysis_config"):
            self.replay(entity, "a")
        original = self.replay("analysis_annotations", "a")
        self.assertIn("old_id", json.loads(history.reconstruct(original)["analysis_annotations_json"]))
        self.annotate(config={"codebook": [{"id": "c1", "label": "changed code"}],
            "codebook_change_reason": "changed reason"}, annotations={})
        self.assertEqual(self.replay("analysis_annotations", "a")[:len(original)], original)
        config = json.loads(history.reconstruct(self.replay("analysis_config", "a"))["analysis_config_json"])
        self.assertEqual(config["codebook_version"], 2)

    def test_annotation_cas_and_history_failure_leave_every_row_unchanged(self):
        before = self.dump()
        with self.assertRaises(app.AnalysisConflictError):
            app.save_group_analysis("a", {"source_revision": 999, "analysis_revision": 0})
        self.assertEqual(self.dump(), before)
        append = history._append
        def fail(*args):
            append(*args)
            raise RuntimeError("fictional history failure after append")
        with patch.object(history, "_append", side_effect=fail), self.assertRaises(RuntimeError):
            self.annotate(annotations={"u1": {"memo": "fictional"}})
        self.assertEqual(self.dump(), before)

    def test_registry_csv_edit_delete_and_discovered_definitions_replay(self):
        app.save_speaker_registry_records([{"id": "speaker01", "display_name": "fictional",
            "attributes": {"known": "x"}}], expected_revision=0)
        original = self.replay("speaker_registry", "speaker01")
        response = self.client.post('/api/speakers/import', data={"registry_revision": "1", "csv_file": (
            io.BytesIO(b'participant_code,display_name,new_question\np2,fictional2,\n'), 'fictional.csv')})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.replay("attribute_definitions", "global")
        app.save_speaker_registry_records([{"id": "speaker01", "display_name": "changed fictional",
            "attributes": {"known": None, "new": False}}], expected_revision=2)
        self.assertEqual(self.replay("speaker_registry", "speaker01")[:len(original)], original)
        app.save_speaker_registry_records([], delete_ids=["speaker01"], expected_revision=3)
        self.assertEqual(history.reconstruct(self.replay("speaker_registry", "speaker01")), {})
        self.replay("attribute_definitions", "global")

    def test_definitions_create_trial_adopt_edit_retire_and_legacy_initial_state(self):
        service = self.pipeline()
        saved = service.save_definition("a", "text_size", definition_fixtures.definition(status="draft"))
        # Preserve a synthetic legacy row with no inferred past author.
        with app.database_connection() as db:
            db.execute("DELETE FROM change_log WHERE entity='analysis_definitions'")
            legacy = history.current(db, "analysis_definitions", "a")
        trial = service.trial_definition("a", "text_size")
        rows = self.replay("analysis_definitions", "a")
        self.assertEqual(history.reconstruct(rows[:1]), legacy)
        self.assertEqual(rows[-1]["origin"], "rule")
        adopted = service.save_definition("a", "text_size", definition_fixtures.definition(
            expected_revision=saved["revision"], expected_trial=trial))
        service.save_definition("a", "text_size", definition_fixtures.definition(
            expected_revision=adopted["revision"], status="retired", description="changed fictional"))
        self.replay("analysis_definitions", "a")

    def test_catalog_all_mutations_and_cascade_deletes_replay(self):
        tag, group = self.seed_catalog()
        with app.database_connection() as db:
            catalog.save_attributes(db, "a", {"region": None})
            catalog.save_attributes(db, "a", {})
            catalog.save_definition(db, {"key": "region", "scope": "conversation", "version": 1,
                "description": "changed fictional"})
            catalog.save_tag(db, {"name": "changed fictional tag"}, tag)
            old = history.current(db, "data_groups", group)
            catalog.save_group(db, {"name": "changed fictional group", "version": old["version"]}, group)
            catalog.assign(db, "tags", tag, ["a"], True)
            catalog.assign(db, "groups", group, ["a"], True)
        for entity, identity in [("attribute_definitions", "global"), ("conversation_attributes", "a"),
                ("tags", tag), ("data_groups", group), ("conversation_tags", "a"),
                ("data_group_members", "a"), ("data_group_members", "b")]:
            self.replay(entity, identity)
        self.assertEqual(self.client.delete('/api/library/tags/' + tag).status_code, 200)
        self.assertEqual(self.client.delete('/api/library/data-groups/' + group).status_code, 200)
        for entity, identity in [("tags", tag), ("data_groups", group), ("conversation_tags", "b"),
                ("data_group_members", "b")]:
            self.assertEqual(history.reconstruct(self.replay(entity, identity)), {})

    def test_bulk_history_failure_rolls_back_members_versions_and_stale_triggers(self):
        with app.database_connection() as db:
            group = catalog.save_group(db, {"name": "fictional"})["group_id"]
            before = list(db.iterdump())
            capture = history.capture
            def fail(connection, entity, identity, *args, **kwargs):
                if entity == "data_group_members" and identity == "b":
                    raise RuntimeError("fictional second-member history failure")
                return capture(connection, entity, identity, *args, **kwargs)
            with patch.object(history, "capture", side_effect=fail), self.assertRaises(RuntimeError):
                catalog.assign(db, "groups", group, ["a", "b"])
            self.assertEqual(list(db.iterdump()), before)

    def test_rule_group_definition_and_auto_registry_have_explicit_rule_origin(self):
        with app.database_connection() as db:
            group = catalog.save_group(db, {"name": "fictional rule", "kind": "rule",
                "rule": {"conditions": [{"scope": "segment", "key": "char_count", "op": "gte", "value": 1}]}})
            catalog.save_group(db, {"name": "changed rule", "kind": "rule", "version": group["version"],
                "rule": {"conditions": [{"scope": "segment", "key": "char_count", "op": "gte", "value": 999}]}}, group["group_id"])
            self.assertFalse(history.rows(db, "data_group_members", "a"))
        self.replay("data_groups", group["group_id"])
        profiles = app.normalize_conversation_speaker_profiles(None, {"P1"}, {"P1": "fictional automatic name"})
        _profiles, summary = app.register_detected_speakers(profiles, {"P1": "fictional automatic name"})
        identity = summary["created"]["P1"]
        self.assertEqual(self.replay("speaker_registry", identity)[-1]["origin"], "rule")
        app.save_speaker_registry_records([{"id": identity, "attributes": {"new": "fictional"}}], expected_revision=1)
        self.assertEqual(self.replay("attribute_definitions", "global")[-1]["origin"], "rule")

    def test_initial_switch_failure_and_outer_transaction_rollback_leave_no_history(self):
        with app.database_connection() as db:
            before = list(db.iterdump())
            append = history._append
            calls = []
            def fail(*args):
                calls.append(args)
                append(*args)
                if len(calls) == 3:
                    raise RuntimeError("fictional initial-state failure")
            with patch.object(history, "_append", side_effect=fail), self.assertRaises(RuntimeError):
                history.fix_initial_states(db, dry_run=False)
            self.assertEqual(list(db.iterdump()), before)
        before = self.dump()
        with self.assertRaises(RuntimeError), app.database_connection() as db:
            catalog.save_tag(db, {"name": "outer rollback"})
            raise RuntimeError("fictional outer transaction failure")
        self.assertEqual(self.dump(), before)

    def test_delete_api_history_conflict_restores_quarantined_media_and_database(self):
        _tag, group = self.seed_catalog()
        media = self.root / 'media' / 'a'
        media.mkdir(parents=True, exist_ok=True)
        asset = media / 'fictional.wav'
        asset.write_bytes(b'fictional media fixture')
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET media_path=? WHERE id='a'", (str(asset),))
            db.execute("UPDATE data_groups SET description='unrecorded fictional' WHERE group_id=?", (group,))
        before = self.dump()
        with patch.object(app, 'retire_input_vault') as retire:
            response = self.client.delete('/api/library/a')
        self.assertEqual(response.status_code, 500, response.get_json())
        self.assertEqual(asset.read_bytes(), b'fictional media fixture')
        self.assertEqual(self.dump(), before)
        retire.assert_not_called()

    def test_delete_restore_api_preserves_i3b_records(self):
        _tag, group = self.seed_catalog()
        self.annotate(annotations={"u1": {"memo": "fictional"}})
        self.pipeline().save_definition("a", "text_size", definition_fixtures.definition())
        with app.database_connection() as db:
            original = trash.snapshot_rows(db, 'a')
        with patch.object(app, 'retire_input_vault'):
            response = self.client.delete('/api/library/a')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.replay('data_groups', group)
        with patch.object(app, 'publish_input_vault'):
            self.assertEqual(app.restore_library_trash(response.get_json()['trash_entry']), 'a')
        with app.database_connection() as db:
            self.assertEqual(trash.snapshot_rows(db, 'a'), original)
        self.replay('data_groups', group)
        self.annotate(annotations={"u1": {"memo": "after fictional restore"}})
        self.replay('analysis_annotations', 'a')

    def test_mismatch_and_corrupt_log_block_save_and_switch_without_rebaselining(self):
        tag, _group = self.seed_catalog()
        with app.database_connection() as db:
            db.execute("UPDATE tags SET description='fictional unrecorded edit' WHERE tag_id=?", (tag,))
            before = list(db.iterdump())
            with self.assertRaises(ValueError):
                catalog.save_tag(db, {"name": "rejected"}, tag)
            self.assertEqual(list(db.iterdump()), before)
            for dry in (True, False):
                with self.assertRaises(ValueError):
                    history.fix_initial_states(db, dry_run=dry)
                self.assertEqual(list(db.iterdump()), before)
        with app.database_connection() as db:
            db.execute("UPDATE change_log SET after_hash='broken' WHERE entity='conversation_attributes'")
            before = list(db.iterdump())
            with self.assertRaises(ValueError):
                catalog.save_attributes(db, "a", {})
            self.assertEqual(list(db.iterdump()), before)

    def test_get_catalog_definition_and_analysis_do_not_create_baselines(self):
        self.pipeline().save_definition("a", "text_size", definition_fixtures.definition())
        with app.database_connection() as db:
            db.execute("DELETE FROM change_log")
        before = self.dump()
        self.assertEqual(self.client.get('/api/library/catalog').status_code, 200)
        self.pipeline().get_definition("a", "text_size")
        app.group_analysis_for_row(app.library_row("a"))
        self.assertEqual(self.dump(), before)

    def test_trash_restores_scoped_definitions_and_logs_preserving_global_and_other_history(self):
        _tag, group = self.seed_catalog()
        self.annotate(annotations={"u1": {"memo": "fictional"}})
        app.save_speaker_registry_records([{"id": "speaker01", "display_name": "fictional"}], expected_revision=0)
        self.pipeline().save_definition("a", "text_size", definition_fixtures.definition())
        with app.database_connection() as db:
            history.capture(db, "notation_variants", "global", {}, {"fictional": "Fictional"})
            history.capture(db, "speaker_registry", "a", {}, {})
            original = trash.snapshot_rows(db, "a")
            other = {target: history.rows(db, *target) for target in [
                ("speaker_registry", "a"), ("notation_variants", "global"), ("data_group_members", "b")]}
            entry = trash.begin(self.root / "trash", item_id="a", source_name="fictional",
                rows=original, tombstones_added=[], tombstones_replaced=[], assets=[])
            for table in ("transcript_versions", "transcript_preparations", "transcript_preparation_events",
                    "transcript_changes", "transcript_change_bases"):
                db.execute(f"DELETE FROM {table} WHERE item_id='a'")
            trash.delete_disposable_rows(db, "a")
            db.execute("DELETE FROM library_items WHERE id='a'")
            self.assertFalse(history.rows(db, "analysis_definitions", "a"))
            self.assertFalse(db.execute("SELECT 1 FROM analysis_definitions WHERE item_id='a'").fetchone())
        self.replay("data_groups", group)
        trash.finish(entry, lambda *_: None)
        trash.restore(self.root / "trash", entry.name, connect=app.database_connection, targets={}, move=lambda *_: None)
        with app.database_connection() as db:
            restored = trash.snapshot_rows(db, "a")
            self.assertEqual(restored, original)
            for target, rows in other.items():
                self.assertEqual(history.rows(db, *target), rows)
            targets = list(db.execute("SELECT DISTINCT entity,entity_id FROM change_log WHERE entity NOT IN ('notation_variants')"))
        for target in targets:
            self.replay(*target)


if __name__ == "__main__":
    unittest.main()
