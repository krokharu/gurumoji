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
        for i in (0, 1):
            memo = self.layout.vault / self.layout.note_path(str(i), '', '研究メモ')
            with memo.open('a', encoding='utf-8') as handle: handle.write('\n[[20-テーマ/働き方]]\n')
        self.layout.sync_themes()
        props, body = unpack(theme.read_text(encoding='utf-8'))
        self.assertIn('interview/i001', props['tags'])
        self.assertIn('interview/i002', props['tags'])
        self.assertNotIn('interview/i003', props['tags'])
        self.assertIn('研究者の解釈を保持する', body)
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
