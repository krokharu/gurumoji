"""Synthetic HTTP imports, search, fixed external results and reversible Vault moves."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
from support import use_temporary_library
from gurumoji.analysis_store import AnalysisStore
from gurumoji.services import research_notes, vault_operations, cross_search


class ResearchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='gurumoji-workspace-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        use_temporary_library(self,self.root,output=self.root/'output')
        self.client = app.app.test_client()
        for item in ('synthetic_a','synthetic_b'):
            app.upsert_library_item(item_id=item,source_name='架空の研究会話',output_dir=self.root/item,
                media_path=None,language='ja',segments=[{'id':'u1','speaker':'P1','start':0,'end':2,'text':'架空の窓口の説明です。'}],
                speaker_names={'P1':'架空話者'},outline=None,emotion_analysis=None,files=[],write_srt=False,write_json=True)
        self.store = AnalysisStore(self.root/'library.sqlite3',app.database_connection)
        self.store.layout.register('synthetic_a','架空の研究会話')
        p=patch.object(app,'analysis_archive_store',return_value=self.store); p.start(); self.addCleanup(p.stop)
        self.backup=patch.object(app,'create_data_backup',return_value={'status':'synthetic_backup'})
        self.backup_mock=self.backup.start(); self.addCleanup(self.backup.stop)

    def note(self,extra=''):
        layout=self.store.layout.load()
        folder=layout['interviews']['synthetic_a']['folder']
        path=self.store.vault/folder/'synthetic-interpretation.md'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('---\nnote_type: interpretation\nnote_id: synthetic-note\nconversation_id: synthetic_a\nmanaged_by: researcher\ntags: [独自タグ]\naliases: [独自別名]\n'+extra+'---\n研究者の解釈。\n',encoding='utf-8')
        return path

    def test_note_import_is_hash_guarded_preserves_original_and_reports_missing(self):
        path=self.note(); original=path.read_bytes()
        url='/api/library/synthetic_a/research-notes'
        preview=self.client.post(url+'/preview',json={}); self.assertEqual(preview.status_code,200,preview.get_json())
        selected=next(n for n in preview.get_json()['notes'] if n['note_id']=='synthetic-note')
        response=self.client.post(url+'/import',json={'notes':[selected]})
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.client.get(url).get_json()['notes'][0]['review_status'],'pending')
        path.write_bytes(original+'研究者による追記\n'.encode('utf-8'))
        self.assertEqual(self.client.post(url+'/import',json={'notes':[selected]}).status_code,409)
        self.assertEqual(self.client.get(url).get_json()['notes'][0]['source_status'],'changed')
        path.unlink()
        self.assertEqual(self.client.get(url).get_json()['notes'][0]['source_status'],'missing')

    def test_duplicate_frontmatter_is_rejected(self):
        self.note('conversation_id: synthetic_b\n')
        response=self.client.post('/api/library/synthetic_a/research-notes/preview',json={})
        self.assertEqual(response.status_code,409,response.get_json())
        self.assertEqual(self.client.post('/api/library/synthetic_a/research-notes/import',json={'notes':[None]}).status_code,409)

    def test_similar_index_excludes_stale_vectors_after_source_edit(self):
        from gurumoji.analysis_core import EMBEDDING_STANDARD_V1 as standard
        from gurumoji.transformer_analysis import transformer_embedding_fingerprint
        from gurumoji.services.segment_embeddings import text_sha256
        with app.database_connection() as db:
            for item in ('synthetic_a','synthetic_b'):
                row=db.execute('SELECT * FROM library_items WHERE id=?',(item,)).fetchone()
                analysis=cross_search.live_input(db,row,row_segments=app.row_segments,
                    row_profiles=app.row_speaker_profiles,row_session=app.row_session_profile)
                db.execute('INSERT INTO segment_embeddings VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (item,'u1',text_sha256(analysis['segments'][0]['text']),
                     transformer_embedding_fingerprint(analysis,model=standard['model_name'],revision=standard['model_revision']),
                     standard['model_name'],standard['model_revision'],384,'int8-scale-127',bytes([100])+bytes(383),'synthetic-date'))
        url='/api/library/search/similar?item_id=synthetic_a&segment_id=u1'
        response=self.client.get(url);self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(response.get_json()['matches'][0]['item_id'],'synthetic_b')
        with app.database_connection() as db:
            db.execute("UPDATE library_items SET segments_json=?,revision_count=revision_count+1 WHERE id='synthetic_a'",
                (json.dumps([{'id':'u1','speaker':'P1','start':0,'end':2,'text':'別の架空本文'}]),))
        self.assertEqual(self.client.get(url).status_code,409)

    def test_fulltext_updates_and_deleted_conversations_disappear(self):
        url='/api/library/search/segments?q=窓口の説明'
        response=self.client.get(url); self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(len(response.get_json()['matches']),2)
        with app.database_connection() as db:
            db.execute("DELETE FROM library_items WHERE id='synthetic_b'")
            db.execute("DROP TABLE cross_search_fts")
            cross_search.initialize(db)
        self.assertEqual(len(self.client.get(url).get_json()['matches']),1)
        self.assertEqual(self.client.get('/api/library/search/segments?q=&limit=0').status_code,409)

    def test_vault_copy_rollback_preserves_other_catalog_updates(self):
        source=self.store.vaults.root('visualization')
        source.mkdir(parents=True,exist_ok=True)
        (source/'synthetic.md').write_text('研究者によるタグ・別名',encoding='utf-8')
        plan=self.client.post('/api/vaults/roots/preview',json={'roots':{'visualization':'SyntheticVisuals'}})
        self.assertEqual(plan.status_code,200,plan.get_json())
        response=self.client.post('/api/vaults/roots/apply',json=plan.get_json())
        self.assertEqual(response.status_code,200,response.get_json()); self.backup_mock.assert_called_once()
        target=self.store.vaults.root('visualization')
        self.assertEqual((source/'synthetic.md').read_bytes(),(target/'synthetic.md').read_bytes())
        catalog=self.store.vaults.load(); catalog['vaults']['input']['synthetic_marker']='retained'; self.store.vaults.save(catalog)
        self.assertEqual(self.client.post('/api/vaults/roots/rollback',json={}).status_code,200)
        self.assertEqual(self.store.vaults.root('visualization'),source)
        self.assertEqual(self.store.vaults.load()['vaults']['input']['synthetic_marker'],'retained')

    def test_external_requires_matching_snapshot_and_evidence(self):
        source=self.store.save(item_id='synthetic_a',kind='text_analysis',snapshot={'segments':[{'id':'u1','text':'架空本文'}]},
            result={'parameters':{},'methods':[]},datasets={'values':(['value'],[{'value':2}])},request_id='synthetic-source',
            input_fingerprint='synthetic-input',source_revision=1,analysis_revision=1,publish=False)
        payload={'source_run_id':source['id'],'snapshot_id':source['snapshot_id'],'method':'架空の外部計算','version':'1',
            'evidence_segment_ids':['u1'],'tables':{'external_values':{'fields':['score'],'rows':[{'score':3}]}}}
        url='/api/library/synthetic_a/analysis/external'
        response=self.client.post(url,json=payload); self.assertEqual(response.status_code,200,response.get_json())
        run=response.get_json()['run']; self.assertEqual(self.store.read_table(run['id'],'external_values')['rows'][0]['values']['score'],3)
        self.assertEqual(self.client.post(url,json={**payload,'snapshot_id':'different'}).status_code,409)
        self.assertEqual(self.client.post(url,json={**payload,'evidence_segment_ids':['missing']}).status_code,409)
        self.assertEqual(self.client.post('/api/library/synthetic_b/analysis/external',json=payload).status_code,409)
        again=self.client.post(url,json={**payload,'request_id':'another-synthetic-request'})
        self.assertEqual(again.get_json()['run']['id'],run['id'])
