"""Synthetic payload capture and publication-contract probes; no Flask/runtime/Vault/AI.
Uses original insight builder, pipeline orchestration and AnalysisStore.publish;
method/output/Vault adapters are controlled synthetic stubs, SQLite is temporary.
"""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]/'app'
sys.path.insert(0,str(ROOT/'src'))
from gurumoji.analysis_insights import create_ai_insights
from gurumoji.analysis_core import fingerprint
from gurumoji.analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store
from gurumoji.analysis_store import AnalysisStore, StoreConflict

analysis={'config':{'research_question':'Synthetic question','codebook':[{'id':'C1','label':'Synthetic code'}]},
 'item':{'session_profile':{'objective':'unused fallback'}},
 'segments':[{'id':'private-source-id','speaker':'speaker-A','speaker_name':'Synthetic A','role':'moderator','text':'Synthetic statement',
 'annotation':{'codes':['C1'],'important':True}},
 {'id':'excluded-id','speaker':'speaker-B','text':'EXCLUDED_TEXT','excluded':True}]}
expert={'expert_id':'synthetic-expert','definition_version':3,'brief':'SYNTHETIC_BRIEF',
 'steps':[{'id':'step1','title':'SYNTHETIC_STEP','basis':['R1']}], 'notes':'DO_NOT_SEND_NOTE','literature':'DO_NOT_SEND_FULL_LITERATURE'}
captured=[]
def call(system,prompt,schema):
 captured.append({'system':system,'prompt':prompt,'schema':schema}); return {'findings':[]}
create_ai_insights(analysis,call,lambda *_:None,lambda:None,expert)
record=json.loads(captured[0]['prompt'].split('発話記録:\n',1)[1])[0]
assert record['id']=='E0001' and record['role']=='moderator' and record['codes']==[{'id':'C1','label':'Synthetic code'}] and record['important']
assert 'SYNTHETIC_BRIEF' in captured[0]['system'] and 'SYNTHETIC_STEP' in captured[0]['system']
assert all(token not in json.dumps(captured) for token in ['DO_NOT_SEND_NOTE','DO_NOT_SEND_FULL_LITERATURE','EXCLUDED_TEXT','private-source-id'])
ai_result={'record_keys':list(record),'record':record,'research_question_sent':'Synthetic question' in captured[0]['prompt'],
 'expert_brief_and_allowed_step_title_sent':True,'excluded_text_not_sent':True,'raw_source_id_replaced_with_invocation_alias':True,
 'expert_note_and_full_literature_not_sent':True,'actual_external_calls':0}

cases=[]
for targets in [['input','orchestrator','visualization'],['input'],[]]:
 with tempfile.TemporaryDirectory(prefix='synthetic-publish-',dir=Path(__file__).resolve().parent) as temp:
  db=Path(temp)/'test.sqlite3'
  def connect():
   c=sqlite3.connect(db,timeout=10); c.row_factory=sqlite3.Row; return c
  with connect() as c:
   c.execute('PRAGMA journal_mode=WAL'); initialize_pipeline_store(c)
   c.execute('CREATE TABLE analysis_runs(id TEXT PRIMARY KEY,status TEXT,vault_status TEXT,error TEXT,item_id TEXT,app_url TEXT,kind TEXT)')
  store=AnalysisStore.__new__(AnalysisStore); store.connect=connect; store._last_publication_outcomes={}; trace=[]
  store._read_package=lambda _: ({'title':'Synthetic','segments':[]},{'methods':[]})
  store.layout=SimpleNamespace(analysis_dir=lambda *_:'synthetic')
  def source_notes(*_):
   trace.append('ResearchVault_attempt'); raise StoreConflict('Synthetic ResearchVault conflict')
  store.source_notes=source_notes
  def publish_generated(run_id):
   trace.extend(['InputVault_attempt','OrchestratorVault_attempt','VisualizationVault_attempt'])
   store._last_publication_outcomes[run_id]={k:{'status':'published','error':''} for k in ('input','orchestrator','visualization')}
   return {k:'published' for k in ('input','orchestrator','visualization')}
  store.publish_vaults=publish_generated
  def save_result(**kwargs):
   with connect() as c:
    c.execute('INSERT INTO analysis_runs VALUES(?,?,?,?,?,?,?)',('synthetic-result','completed','pending','','synthetic-only','http://synthetic.invalid','milestone_analysis'))
   return {'id':'synthetic-result','status':'completed','fingerprint':'synthetic-package'}
  a={'segments':[{'id':'e1','text':'synthetic','speaker':'A','start':0,'end':1,'duration':1,'valid_time':True}]}
  snap={'analysis':a,'input_hash':fingerprint(a),'source_revision':1,'analysis_revision':1,'archive_snapshot':{'segments':a['segments']}}
  service=AnalysisPipelineService(connect=connect,find_item=lambda _:{'id':'synthetic-only','revision_count':1,'analysis_revision':1},
   source_fingerprint=lambda _:snap['input_hash'],snapshot_builder=lambda _:copy.deepcopy(snap),
   method_runner=lambda method,_:{'method':{'method_id':method,'summaries':[],'charts':[]},'datasets':{}},
   save_result=save_result,publish_result=store.publish,publication_outcomes=store.publication_outcomes,public_run=lambda _:store.get('synthetic-result'),runtime_key='synthetic-publication')
  service._schedule=lambda *_:None
  started,status=service.start('synthetic-only',{'request_id':'synthetic-publish-request-0001','source_revision':1,'analysis_revision':1,
   'mode':'automatic','definition_ids':[],'publication_targets':targets,'provider_policy':'local_only'},app_url='http://synthetic.invalid')
  service._run(started['pipeline_id'],'http://synthetic.invalid')
  final=service.status('synthetic-only',started['pipeline_id'],ensure_running=False)
  assert final['status']=='completed',final
  research=store.get('synthetic-result')['vault_status']
  assert research==('conflict' if targets else 'pending')
  assert len(trace)==(4 if targets else 0)
  cases.append({'selected_targets':targets,'pipeline_status':final['status'],'ResearchVault_vault_status':research,
   'publication_records':{p['target_role']:p['status'] for p in final['publications']},'publisher_attempt_trace':trace,
   'real_files_or_vaults_written':False})
print(json.dumps({'ai_payload_capture':ai_result,'publication_cases':cases,'evidence_scope':'Original contract methods with synthetic adapters. No real AI, runtime, Vault, or GUI.'},ensure_ascii=False,indent=2))
