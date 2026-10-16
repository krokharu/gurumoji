"""Synthetic tests for content preservation, relocation and bounded retrieval."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import restructure_program_vault as migration
from build_program_vault_catalog import build_catalog

spec=importlib.util.spec_from_file_location('vault_retrieval',ROOT/'.agents/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py')
retrieval=importlib.util.module_from_spec(spec);sys.modules[spec.name]=retrieval;spec.loader.exec_module(retrieval)

class SplitTests(unittest.TestCase):
    def test_fenced_headings_are_not_boundaries_and_all_text_survives(self):
        body='# Title\n\n## One\n'+('説明。\n'*60)+'```markdown\n## Example only\n```\n## Two\n'+('詳細。\n'*60)
        parts=migration.split_body(body,180)
        self.assertEqual(''.join(p for _,_,p in parts),body)
        self.assertFalse(any(p.startswith('## Example') for _,_,p in parts))
        self.assertTrue(any('```markdown\n## Example only\n```' in p for _,_,p in parts))

    def test_table_rows_split_without_losing_rows_and_repeat_header_for_display(self):
        body='# Results\n\n| ID | Result |\n| --- | --- |\n'+''.join(f'| {i} | '+('x'*80)+' |\n' for i in range(40))
        parts=migration.split_body(body,1000)
        self.assertGreater(len(parts),1)
        self.assertEqual(''.join(p for _,_,p in parts),body)
        self.assertEqual(migration.table_header(body,parts[1][0],parts[1][2]),'| ID | Result |\n| --- | --- |\n')

    def test_prose_links_move_and_code_examples_stay_literal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();files={'a.md':b'', 'b.md':b'', 'asset.png':b''}
            text='[[b#Contract|details]] [image](asset.png)\n`[[b]]`\n```\n[[b]]\n```\n'
            actual=migration.rewrite_links(text,'a.md','deep/a.md',root,files,{'b.md':'new/b.md'},{('b.md','Contract'):'new/contract.md'})
            self.assertIn('[[new/contract#Contract|details]]',actual)
            self.assertIn('[image](../asset.png)',actual)
            self.assertIn('`[[b]]`\n```\n[[b]]\n```',actual)

class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.vault=self.base/'vault';self.vault.mkdir()
        self.work=self.base/'plan';self.work.mkdir()
        (self.work/'staged').mkdir();(self.vault/'old.md').write_bytes(b'local uncommitted text\r\n')
        import zipfile
        with zipfile.ZipFile(self.work/'before.zip','w') as z:z.writestr('old.md',(self.vault/'old.md').read_bytes())
        (self.work/'staged/old.md').write_bytes(b'redirect\n');(self.work/'staged/new.md').write_bytes(b'body\n')
        self.plan={'vault':str(self.vault),'before':{'old.md':migration.sha((self.vault/'old.md').read_bytes())},
                   'writes':{'old.md':migration.sha(b'redirect\n'),'new.md':migration.sha(b'body\n')}}
        self.path=self.work/'plan.json';self.path.write_text(json.dumps(self.plan),encoding='utf-8')

    def test_apply_restore_preserve_original_bytes_and_unrelated_settings(self):
        (self.vault/'.obsidian').mkdir();(self.vault/'.obsidian/app.json').write_bytes(b'{"user":true}')
        migration.execute(self.path);self.assertTrue((self.vault/'new.md').exists())
        migration.execute(self.path,restore=True)
        self.assertEqual((self.vault/'old.md').read_bytes(),b'local uncommitted text\r\n')
        self.assertFalse((self.vault/'new.md').exists())
        self.assertEqual((self.vault/'.obsidian/app.json').read_bytes(),b'{"user":true}')

    def test_concurrent_edits_block_apply_and_restore(self):
        (self.vault/'old.md').write_bytes(b'changed after plan')
        with self.assertRaisesRegex(ValueError,'changed since plan'):migration.execute(self.path)
        self.assertFalse((self.vault/'new.md').exists())
        (self.vault/'old.md').write_bytes(b'local uncommitted text\r\n');migration.execute(self.path)
        (self.vault/'new.md').write_bytes(b'user edits')
        with self.assertRaisesRegex(ValueError,'subsequent edits'):migration.execute(self.path,restore=True)
        self.assertEqual((self.vault/'new.md').read_bytes(),b'user edits')

class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.vault=Path(self.temp.name)
        for path,meta,body in [
            ('deep/contract.md',{'note_id':'contract','note_type':'reference-section','title':'保存契約','summary':'契約の要約','status':'current','tags':['test']},'# 保存契約\n\n## 保存先\nTARGET CONTENT\n\n## 外部送信\nOTHER CONTENT\n'),
            ('legacy.md',{'note_id':'legacy','note_type':'path-redirect','title':'保存契約','status':'deprecated'},'LEGACY DUPLICATE\n'),
            ('unrelated.md',{'note_id':'unrelated','title':'保存契約','status':'current'},'UNRELATED BODY\n')]:
            p=self.vault/path;p.parent.mkdir(exist_ok=True);p.write_bytes(migration.pack(meta,body))
        (self.vault/'00-Catalog.json').write_text(json.dumps(build_catalog(self.vault),ensure_ascii=False),encoding='utf-8')

    def test_exact_id_and_section_exclude_other_sections_and_include_content_hash(self):
        result=retrieval.packet(self.vault,'保存先',4,1200,False,False,note_id='contract',section='保存先')
        self.assertIn('TARGET CONTENT',result);self.assertNotIn('OTHER CONTENT',result)
        self.assertNotIn('UNRELATED BODY',result);self.assertIn('sha256 ',result);self.assertLessEqual(len(result),1200)

    def test_scope_summary_layer_and_redirect_exclusion(self):
        result=retrieval.packet(self.vault,'保存契約',4,1500,False,False,scope='deep',metadata_only=True)
        self.assertIn('契約の要約',result);self.assertNotIn('TARGET CONTENT',result)
        all_notes=retrieval.packet(self.vault,'保存契約',4,2000,False,False)
        self.assertNotIn('LEGACY DUPLICATE',all_notes)

    def test_stale_catalogue_and_scope_escape_fail_closed(self):
        with (self.vault/'deep/contract.md').open('a',encoding='utf-8') as f:f.write('new edit')
        with self.assertRaisesRegex(ValueError,'stale'):retrieval.packet(self.vault,'',1,1000,False,False,note_id='contract')
        with self.assertRaisesRegex(ValueError,'inside'):retrieval.packet(self.vault,'',1,1000,False,False,scope='..')

if __name__=='__main__':unittest.main()
