import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

from gurumoji.obsidian_layout import ObsidianLayout, unpack, pack, GLOBAL_QUERY, interview_query
from gurumoji.obsidian_finishing import ObsidianWorkbench, read_text, parse_transcript
from gurumoji.obsidian_migration import migrate, rewrite_links


class ObsidianLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'library.sqlite3'
        self.layout = ObsidianLayout(self.database)
        self.workbench = ObsidianWorkbench(self.database)

    def test_three_interviews_share_only_explicit_theme_and_no_per_utterance_files(self):
        records = []
        for i in range(3):
            segments = [{'id': f's{x}', 'speaker': 'A', 'start': x, 'end': x+1, 'text': '話した本文'} for x in range(20)]
            state = self.workbench.prepare(str(i), f'会議{i}.wav', segments, revision=0)
            self.assertEqual(parse_transcript(read_text(self.workbench.note_path(state['work'])), segments), segments)
            record = self.layout.register(str(i), f'会議{i}.wav')
            records.append(record)
            self.assertEqual(len(list((self.layout.vault / record['folder']).glob('*-全文.md'))), 1)
        theme = self.layout.vault / '20-テーマ/働き方.md'
        theme.write_text('# 働き方\n\n研究者の解釈を保持する。\n', encoding='utf-8')
        original_theme = theme.read_bytes()
        for i in (0, 1):
            memo = self.layout.vault / self.layout.note_path(str(i), '', '研究メモ')
            with memo.open('a', encoding='utf-8') as handle: handle.write('\n[[20-テーマ/働き方]]\n')
        self.layout.sync_themes()
        self.assertEqual(theme.read_bytes(), original_theme)
        relation = next((self.layout.vault / '40-研究/テーマ関連').glob('*.md'))
        props, body = unpack(relation.read_text(encoding='utf-8'))
        self.assertIn('interview/i001', props['tags'])
        self.assertIn('interview/i002', props['tags'])
        self.assertNotIn('interview/i003', props['tags'])
        self.assertIn('[[20-テーマ/働き方', body)
        self.assertIn(records[0]['hub'][:-3], body)
        self.assertNotIn(records[2]['hub'][:-3], body)
        before = theme.read_bytes()
        self.layout.sync_themes()
        self.assertEqual(theme.read_bytes(), before)
        bookmarks = json.loads((self.layout.vault / '.obsidian/bookmarks.json').read_text(encoding='utf-8'))
        navigation = bookmarks['items'][0]['items']
        searches = next(item for item in navigation if item.get('title') == '分析を検索')['items']
        self.assertEqual({item['title'] for item in searches}, {'相づち・応答率', '話者別リザルト', '相づち統計'})
        self.assertTrue(all(item['type'] == 'search' for item in searches))
        self.assertTrue(all('path:"10-インタビュー"' in item['query'] for item in searches))
        graphs = navigation[-1]['items']
        self.assertEqual(len(graphs), 3)
        self.assertEqual(graphs[0]['options']['search'], interview_query(records[0]))
        self.assertIn('-tag:#graph/support', GLOBAL_QUERY)
        core = json.loads((self.layout.vault / '.obsidian/core-plugins.json').read_text(encoding='utf-8'))
        self.assertTrue(core['search'])
        self.assertTrue(core['global-search'])
        self.assertFalse((self.layout.vault / '15-Finishing').exists())

    def test_theme_sync_keeps_all_human_bytes_and_tracks_removed_links(self):
        self.layout.update('a', '会議', {})
        theme = self.layout.vault / '20-テーマ/働き方.md'
        original = ('---\r\n# comment\r\ntags: [graph/custom, interview/custom]\r\n'
                    'extra: &value [one, two]\r\naliases: *value\r\n---\r\n'
                    '> [!note] Human\r\n![[image.png]]\r\nText ^block\r\n').encode('utf-8')
        theme.write_bytes(original)
        unrelated = self.layout.vault / '20-テーマ/unrelated.md'
        unrelated.write_bytes(b'---\ninvalid: [\n---\nHuman note')
        memo = self.layout.vault / self.layout.note_path('a', '', '研究メモ')
        with memo.open('a', encoding='utf-8') as handle:
            handle.write('\n[[20-テーマ/働き方]]\n')
        self.layout.sync_themes()
        relation = next((self.layout.vault / '40-研究/テーマ関連').glob('*.md'))
        before_relation = relation.read_bytes()
        self.layout.sync_themes()
        self.assertEqual(relation.read_bytes(), before_relation)
        self.assertEqual(theme.read_bytes(), original)
        self.assertEqual(unrelated.read_bytes(), b'---\ninvalid: [\n---\nHuman note')
        memo.write_text(memo.read_text(encoding='utf-8').replace('[[20-テーマ/働き方]]', ''), encoding='utf-8')
        self.layout.sync_themes()
        self.assertIn('graph/history', unpack(relation.read_text(encoding='utf-8'))[0]['tags'])
        self.assertEqual(theme.read_bytes(), original)

    def test_finishing_sync_does_not_read_or_write_researcher_notes(self):
        state = self.workbench.prepare('a', '会議', [], revision=0)
        paths = [self.workbench.note_path(state[key]) for key in ('work', 'outline', 'control')]
        for path in paths:
            path.write_bytes(b'---\r\ninvalid: [\r\n---\r\nHuman edit ^block')
        with patch('gurumoji.obsidian_layout.write_atomic', wraps=__import__(
                'gurumoji.obsidian_layout', fromlist=['write_atomic']).write_atomic) as write:
            self.layout.sync_finishing(state)
        self.assertTrue(all(path.read_bytes().endswith(b'Human edit ^block') for path in paths))
        self.assertFalse(any(call.args[0] in paths for call in write.call_args_list))

    def test_user_bookmarks_memos_and_workspace_edits_survive_regeneration(self):
        self.layout.update('a', '会議', {})
        root = self.layout.vault
        bookmark = root / '.obsidian/bookmarks.json'
        data = json.loads(bookmark.read_text(encoding='utf-8'))
        data['items'].append({'type': 'group', 'title': '自分用', 'items': []})
        bookmark.write_text(json.dumps(data), encoding='utf-8')
        memo = root / self.layout.note_path('a', '会議', '研究メモ')
        with memo.open('a', encoding='utf-8') as handle: handle.write('\n手書きのメモ\n')
        before = memo.read_bytes()
        self.layout.update('a', '会議', {}, '完了')
        self.assertEqual(memo.read_bytes(), before)
        self.assertEqual(json.loads(bookmark.read_text(encoding='utf-8'))['items'][-1]['title'], '自分用')

    def test_existing_vault_settings_are_never_rewritten(self):
        settings = self.layout.vault / '.obsidian'
        settings.mkdir(parents=True)
        files = {
            'core-plugins.json': '{"graph": false, "file-explorer": true}',
            'appearance.json': '{"enabledCssSnippets": []}',
            'bookmarks.json': '{"items": [{"type": "file", "path": "mine.md"}]}',
            'workspaces.json': '{"workspaces": {}, "active": ""}',
        }
        for name, text in files.items():
            (settings / name).write_text(text, encoding='utf-8')
        for i in range(2):
            self.layout.update('existing', '既存.wav', {}, '保存済み')
        for name, text in files.items():
            self.assertEqual((settings / name).read_text(encoding='utf-8'), text, name)
        self.assertFalse((settings / 'graph.json').exists())
        self.assertFalse((settings / 'workspace.json').exists())
        self.assertEqual(self.layout.load()['obsidian_settings']['mode'], 'existing')

    def test_new_vault_is_configured_once_and_user_changes_stay(self):
        self.layout.update('new', '新規.wav', {}, '保存済み')
        settings = self.layout.vault / '.obsidian'
        self.assertEqual(self.layout.load()['obsidian_settings']['mode'], 'initialized')
        self.assertTrue(json.loads((settings / 'core-plugins.json').read_text(encoding='utf-8'))['graph'])
        # The user turns the graph off and removes the Gurumoji bookmarks.
        (settings / 'core-plugins.json').write_text('{"graph": false}', encoding='utf-8')
        (settings / 'bookmarks.json').write_text('{"items": []}', encoding='utf-8')
        (settings / 'graph.json').unlink()
        self.layout.update('second', '二件目.wav', {}, '保存済み')
        self.assertEqual((settings / 'core-plugins.json').read_text(encoding='utf-8'), '{"graph": false}')
        self.assertEqual((settings / 'bookmarks.json').read_text(encoding='utf-8'), '{"items": []}')
        self.assertFalse((settings / 'graph.json').exists())

    def test_interview_folder_name_leaves_room_under_the_path_limit(self):
        from gurumoji import analysis_store
        title = '非常に長い会議の録音ファイル名' * 6 + '.wav'
        limit = len(str(self.layout.vault)) + 170
        with patch.object(analysis_store, 'PATH_LIMIT', limit):
            record = self.layout.register('long', title)
        # Room for history and graph notes stays below the interview folder.
        self.assertLessEqual(len(str(self.layout.vault / record['folder'])) + 130, limit)
        self.assertLess(len(record['folder']), len('10-インタビュー/I001-') + len(title))
        self.assertEqual(record['title'], title)  # the full title is kept in the note
        self.assertEqual(len(self.layout.register('plain', '短い.wav')['folder'].split('-', 2)[-1]), 2)

    def test_idle_theme_sync_reads_only_changed_memos(self):
        # OBS-08: the 10-second theme sync stat()s unchanged notes instead of reading them.
        for index in range(3):
            self.layout.update(str(index), f'会議{index}.wav', {}, '保存済み')
        (self.layout.vault / '20-テーマ').mkdir(exist_ok=True)
        (self.layout.vault / '20-テーマ/働き方.md').write_text('# 働き方\n', encoding='utf-8')
        self.layout.sync_themes()
        memo = self.layout.vault / self.layout.note_path('1', '', '研究メモ')
        real = Path.read_text
        reads = []
        def counting(path, *args, **kwargs):
            reads.append(path)
            return real(path, *args, **kwargs)
        with patch.object(Path, 'read_text', counting):
            self.layout.sync_themes()
        self.assertFalse([p for p in reads if p.name.endswith('研究メモ.md')])
        with memo.open('a', encoding='utf-8') as handle:
            handle.write('\n[[20-テーマ/働き方]]\n')
        self.layout.sync_themes()
        relation = next((self.layout.vault / '40-研究/テーマ関連').glob('*.md')).read_text(encoding='utf-8')
        self.assertIn('interview/i002', relation)  # the edit is picked up on the next sync

    def test_deleted_conversation_is_marked_and_notes_are_kept(self):
        record = self.layout.register('gone', '削除する会議.wav')
        self.layout.update('gone', '削除する会議.wav', {}, '保存済み')
        memo = self.layout.vault / self.layout.note_path('gone', '', '研究メモ')
        memo.write_text(memo.read_text(encoding='utf-8') + '\n研究者の記録\n', encoding='utf-8')
        memo_bytes = memo.read_bytes()
        self.assertTrue(self.layout.mark_deleted('gone'))
        self.assertFalse(self.layout.mark_deleted('gone'))
        self.assertFalse(self.layout.mark_deleted('never-registered'))
        hub = (self.layout.vault / record['hub']).read_text(encoding='utf-8')
        self.assertEqual(unpack(hub)[0]['status'], 'アプリから削除済み')
        self.assertIn('この会話はアプリから削除されています', hub)
        index = (self.layout.vault / '10-インタビュー/インタビュー一覧.md').read_text(encoding='utf-8')
        self.assertIn('（アプリから削除済み）', index)
        analysis_index = (self.layout.vault / '01-分析結果.md').read_text(encoding='utf-8')
        self.assertNotIn('：未保存', analysis_index)
        self.assertEqual(memo.read_bytes(), memo_bytes)
        # Later finishing syncs do not quietly undo the deletion status.
        self.layout.update('gone', '削除する会議.wav', {}, '完了')
        self.assertEqual(self.layout.load()['interviews']['gone']['status'], 'アプリから削除済み')
        # Imported again under the same ID: the previous status comes back.
        self.assertTrue(self.layout.clear_deleted('gone'))
        restored = self.layout.load()['interviews']['gone']
        self.assertEqual(restored['status'], '保存済み')
        self.assertNotIn('deleted_at', restored)
        self.assertNotIn('削除されています', (self.layout.vault / record['hub']).read_text(encoding='utf-8'))

    def test_deleting_a_conversation_never_creates_a_vault_overview(self):
        self.assertFalse(self.layout.mark_deleted('never-published'))
        self.assertFalse(self.layout.registry.exists())
        self.assertFalse(self.layout.vault.exists())

    def test_method_tables_escape_link_alias_separator(self):
        from gurumoji.obsidian_layout import method_table
        row = method_table([{'path': 'a/method-x.md', 'title': '手法', 'status': 'completed',
                             'stale': False, 'created_at': ''}]).splitlines()[-1]
        self.assertIn('[[a/method-x\\|手法]]', row)
        self.assertEqual(row.replace('\\|', '').count('|'), 4)

    def test_shortest_path_theme_links_resolve_only_when_unique(self):
        self.layout.update('a', '会議', {})
        (self.layout.vault / '20-テーマ/働き方.md').write_text('# 働き方\n', encoding='utf-8')
        memo = self.layout.vault / self.layout.note_path('a', '会議', '研究メモ')
        with memo.open('a', encoding='utf-8') as handle: handle.write('\n[[働き方|働き方の話]]\n')
        self.layout.sync_themes()
        relation = next((self.layout.vault / '40-研究/テーマ関連').glob('*.md'))
        self.assertIn('interview/i001', unpack(relation.read_text(encoding='utf-8'))[0]['tags'])
        (self.layout.vault / '40-研究/働き方.md').write_text('# 別の働き方\n', encoding='utf-8')
        self.layout.sync_themes()
        self.assertIn('graph/history', unpack(relation.read_text(encoding='utf-8'))[0]['tags'])

    def test_idle_theme_sync_writes_nothing(self):
        self.layout.update('a', '会議', {})
        (self.layout.vault / '20-テーマ/働き方.md').write_text('# 働き方\n', encoding='utf-8')
        memo = self.layout.vault / self.layout.note_path('a', '会議', '研究メモ')
        with memo.open('a', encoding='utf-8') as handle: handle.write('\n[[20-テーマ/働き方]]\n')
        self.layout.sync_themes()
        with patch('gurumoji.obsidian_layout.write_atomic') as write:
            self.layout.sync_themes()
        write.assert_not_called()

    def test_renamed_interview_folder_is_followed_instead_of_recreated(self):
        self.layout.update('a', '会議', {})
        record = self.layout.register('a', '会議')
        old = self.layout.vault / record['folder']
        memo = old / f"{record['code']}-研究メモ.md"
        with memo.open('a', encoding='utf-8') as handle: handle.write('\n手書き\n')
        new = old.with_name(old.name + '-移動後')
        old.rename(new)
        self.layout.update('a', '会議', {}, '完了')
        moved = self.layout.register('a', '会議')
        self.assertFalse(old.exists())
        self.assertEqual(moved['folder'], record['folder'] + '-移動後')
        self.assertIn('手書き', (new / memo.name).read_text(encoding='utf-8'))
        self.assertIn('状態：完了', (self.layout.vault / moved['hub']).read_text(encoding='utf-8'))

    def test_unreadable_obsidian_settings_are_left_untouched(self):
        self.layout.update('a', '会議', {})
        bookmark = self.layout.vault / '.obsidian/bookmarks.json'
        bookmark.write_bytes(b'{"items": [')
        self.layout.update('a', '会議', {}, '完了')
        self.assertEqual(bookmark.read_bytes(), b'{"items": [')

    def test_bookmark_group_without_marker_is_replaced_not_duplicated(self):
        self.layout.update('a', '会議', {})
        bookmark = self.layout.vault / '.obsidian/bookmarks.json'
        data = json.loads(bookmark.read_text(encoding='utf-8'))
        data['items'][0].pop('gurumoji')
        bookmark.write_text(json.dumps(data), encoding='utf-8')
        self.layout.update('a', '会議', {}, '完了')
        items = json.loads(bookmark.read_text(encoding='utf-8'))['items']
        self.assertEqual([item['title'] for item in items], ['Gurumoji'])

    def seed_legacy(self):
        old = '25-Sources/snapshot/part-0001.md'
        text = pack({'note_id': 'source-1', 'note_type': 'source-snapshot', 'title': '会議',
                     'conversation_id': 'a', 'input_snapshot_id': 'snapshot'},
                    '# 原文\n\n> [[25-Sources/snapshot/part-0001]] は発言の文字列\n\n^s-61\n')
        path = self.layout.vault / old
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding='utf-8')
        home = self.layout.vault / '00-Home.md'
        home.write_text('# 私のホーム\n\n[[25-Sources/snapshot/part-0001#^s-61|根拠]]\n', encoding='utf-8')
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute('CREATE TABLE obsidian_notes(path TEXT PRIMARY KEY,note_id TEXT,sha256 TEXT)')
            conn.execute('INSERT INTO obsidian_notes VALUES (?,?,?)', (old, 'source-1', hashlib.sha256(path.read_bytes()).hexdigest()))
            conn.execute('CREATE TABLE analysis_runs(note_path TEXT)')
            conn.execute('INSERT INTO analysis_runs VALUES (?)', (old,))
        return old, text

    def test_migration_updates_catalog_links_and_preserves_literal_quotes_and_backup(self):
        old, text = self.seed_legacy()
        report = migrate(self.database)
        target = report['mapping'][old]
        self.assertFalse((self.layout.vault / old).exists())
        migrated = (self.layout.vault / target).read_text(encoding='utf-8')
        self.assertIn('> [[25-Sources/snapshot/part-0001]] は発言の文字列', migrated)
        self.assertIn(target[:-3] + '#^s-61|根拠', (self.layout.vault / '90-運用/以前のホーム.md').read_text(encoding='utf-8'))
        self.assertEqual((Path(report['backup']) / 'vault' / old).read_text(encoding='utf-8'), text)
        with closing(sqlite3.connect(self.database)) as conn, conn:
            row = conn.execute('SELECT path,sha256 FROM obsidian_notes').fetchone()
            self.assertEqual(row, (target, hashlib.sha256((self.layout.vault / target).read_bytes()).hexdigest()))
            self.assertEqual(conn.execute('SELECT note_path FROM analysis_runs').fetchone()[0], target)
        self.assertEqual(migrate(self.database), report)

    def test_migration_removes_only_folders_it_emptied(self):
        old, _ = self.seed_legacy()
        own_empty = self.layout.vault / '99-個人' / '空のフォルダー'
        own_empty.mkdir(parents=True)
        report = migrate(self.database)
        self.assertTrue(own_empty.is_dir())  # OBS-13: the user's empty folder survives
        source_folder = (self.layout.vault / old).parent
        if report['mapping'][old].rsplit('/', 1)[0] != old.rsplit('/', 1)[0]:
            self.assertFalse(source_folder.exists())

    def test_interrupted_migration_resumes_from_same_backup(self):
        self.seed_legacy()
        from gurumoji import obsidian_migration
        original = obsidian_migration.write_atomic
        def fail(path, data):
            if path.name == 'part-0001.md': raise OSError('disk unavailable')
            return original(path, data)
        with patch.object(obsidian_migration, 'write_atomic', side_effect=fail):
            with self.assertRaises(OSError): migrate(self.database)
        pending = self.database.parent / 'obsidian_layout/migration-pending.json'
        before = json.loads(pending.read_text(encoding='utf-8'))
        report = migrate(self.database)
        self.assertEqual(report['backup'], before['backup'])
        self.assertFalse(pending.exists())

    def test_legacy_fences_and_quote_literals_are_never_rewritten(self):
        original = '~~~text\n[[old]]\n~~~\n> [[old]]\n\n[[old#^s-61|引用]]\n'
        self.assertEqual(rewrite_links(original, {'old.md': 'new.md'}),
                         '~~~text\n[[old]]\n~~~\n> [[old]]\n\n[[new#^s-61|引用]]\n')


if __name__ == '__main__':
    unittest.main()
