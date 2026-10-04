"""Deterministic schedule-boundary test with original M0-M7 engine.
Temporary synthetic SQLite only. _schedule is paused to permit a definition edit
between acceptance and worker entry; _run then uses original orchestration.
Method/output adapters are synthetic stubs. No real runtime, Vault, model, or AI.
"""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]/'app'
sys.path.insert(0,str(ROOT/'src'))
from gurumoji.analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store
from gurumoji.analysis_core import fingerprint

with tempfile.TemporaryDirectory(prefix='synthetic-definition-',dir=Path(__file__).resolve().parent) as temp:
    db=Path(temp)/'synthetic.sqlite3'
    def connect():
        connection=sqlite3.connect(db,timeout=10)
        connection.row_factory=sqlite3.Row
        return connection
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        initialize_pipeline_store(c)
    segments=[{'id':'e1','text':'abc','speaker':'A','duration':60,'start':0,'end':60,'valid_time':True}]
    analysis={'segments':segments}
    snapshot={'analysis':analysis,'input_hash':fingerprint(analysis),'source_revision':1,'analysis_revision':1,'archive_snapshot':{'segments':segments}}
    captured=[]
    def save_result(**kwargs):
        captured.append(copy.deepcopy(kwargs))
        return {'id':'synthetic-result','status':'completed','fingerprint':fingerprint(kwargs['result'])}
    def method_runner(method,snapshot):
        return {'method':{'method_id':method,'summaries':[],'charts':[]},'datasets':{}}
    service=AnalysisPipelineService(connect=connect,find_item=lambda _: {'id':'synthetic-only','revision_count':1,'analysis_revision':1},
        source_fingerprint=lambda _:snapshot['input_hash'],snapshot_builder=lambda _:copy.deepcopy(snapshot),method_runner=method_runner,
        save_result=save_result,publish_result=lambda _: {},publication_outcomes=lambda _: {},public_run=lambda _: {},runtime_key='full-lifecycle-probe')
    service._schedule=lambda *_: None
    base={'definition_id':'synthetic_measure','name':'Synthetic measure','description':'Initial character count','unit_of_analysis':'segment',
          'source_columns':['text'],'output_column':'synthetic_value','data_type':'number','measurement_level':'ratio','measurement_rule':'text_length','method':'descriptive','status':'adopted'}
    service.save_definition('synthetic-only',base['definition_id'],base)
    started,status=service.start('synthetic-only',{'request_id':'synthetic-full-request-0001','source_revision':1,'analysis_revision':1,'mode':'manual',
        'definition_ids':[base['definition_id']],'publication_targets':[],'provider_policy':'local_only','research_protocol':{'classification':'exploratory','data_viewed':True}},app_url='http://synthetic.invalid/')
    assert status==202
    service.save_definition('synthetic-only',base['definition_id'],{**base,'source_columns':['duration'],'measurement_rule':'duration','description':'Changed to duration','expected_revision':1})
    service._run(started['pipeline_id'],'http://synthetic.invalid/')
    final=service.status('synthetic-only',started['pipeline_id'],ensure_running=False)
    assert final['status']=='completed',final
    package=captured[0]
    binding=package['result']['parameters']['binding']['resolved'][0]
    definition=package['result']['parameters']['definitions'][0]
    measured=package['datasets']['measurements'][1][0]['synthetic_value']
    assert binding['definition_version']==1 and definition['version']==2 and measured==60
    print(json.dumps({'method':'original M0-M7 engine with deterministic paused scheduling; synthetic adapters and temporary SQLite, not browser/real methods',
        'pipeline_status':final['status'],'milestones':[{'id':m['id'],'status':m['status']} for m in final['milestones']],
        'save_adapter_package_binding_definition_version':binding['definition_version'],'save_adapter_package_definition_version':definition['version'],
        'save_adapter_package_measurement_rule':definition['measurement_rule'],'original_expected_character_count':3,'actual_measurement_value':measured,
        'external_calls':0,'real_runtime_or_source_mutation':False},ensure_ascii=False,indent=2))
