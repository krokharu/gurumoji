"""Synthetic, in-memory definition lifecycle checks. No app import or external IO.
The scheduled worker is paused; definition-loading prefix is extracted from the
original _run method, then the original manual-measurement step is run in isolation.
This is not a full pipeline/browser test.
"""
import ast
import copy
import inspect
import json
from pathlib import Path
import sqlite3
import sys
import textwrap
ROOT=Path(__file__).resolve().parents[2]/'app'
sys.path.insert(0,str(ROOT/'src'))
import gurumoji.analysis_pipeline as p
from gurumoji.analysis_core import AnalysisContractError, fingerprint

def fixture():
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
    p.initialize_pipeline_store(c); c.commit()
    analysis={'segments':[{'id':'e1','text':'abc','speaker':'A','duration':60,'start':0,'end':60,'valid_time':True}]}
    snapshot={'analysis':analysis,'input_hash':fingerprint(analysis),'source_revision':1,'analysis_revision':1,'archive_snapshot':{'segments':analysis['segments']}}
    service=p.AnalysisPipelineService(connect=lambda:c,find_item=lambda _: {'id':'synthetic-only','revision_count':1,'analysis_revision':1},
        source_fingerprint=lambda _:snapshot['input_hash'],snapshot_builder=lambda _:copy.deepcopy(snapshot),
        method_runner=lambda *_:{},save_result=lambda **_:{},publish_result=lambda _: {},publication_outcomes=lambda _: {},public_run=lambda _: {},runtime_key='lifecycle-probe')
    service._schedule=lambda *_: None
    return c,service,snapshot

base={'definition_id':'synthetic_measure','name':'Synthetic measure','description':'Initial character count','unit_of_analysis':'segment',
      'source_columns':['text'],'output_column':'synthetic_value','data_type':'number','measurement_level':'ratio','measurement_rule':'text_length','method':'descriptive','status':'adopted'}
c,s,snapshot=fixture()
first=s.save_definition('synthetic-only',base['definition_id'],base)
draft=s.save_definition('synthetic-only',base['definition_id'],{**base,'status':'draft','expected_revision':1,'description':'Unadopted edit'})
try: s._definitions('synthetic-only',[base['definition_id']]); raise AssertionError('Old adopted definition unexpectedly retained')
except AnalysisContractError as e: cancel_state_error=e.code
row=dict(c.execute('SELECT revision,status,payload_json FROM analysis_definitions').fetchone())
assert row['revision']==2 and row['status']=='draft'
first_result={'before_status':first['status'],'after_trial_preparation_status':row['status'],'row_count':c.execute('SELECT COUNT(*) FROM analysis_definitions').fetchone()[0],
 'adopted_lookup_error':cancel_state_error,'previous_payload_preserved_as_versioned_row':False}
c.close()

c,s,snapshot=fixture()
s.save_definition('synthetic-only',base['definition_id'],base)
started,status=s.start('synthetic-only',{'request_id':'synthetic-lifecycle-request-0001','source_revision':1,'analysis_revision':1,'mode':'manual',
 'definition_ids':[base['definition_id']],'publication_targets':[],'provider_policy':'local_only','research_protocol':{'classification':'exploratory','data_viewed':True}},app_url='http://synthetic.invalid/')
assert status==202
pipeline_id=started['pipeline_id']
pipeline=s._pipeline_row(pipeline_id)
binding=json.loads(pipeline['binding_json'])
assert binding['resolved'][0]['definition_version']==1
s.save_definition('synthetic-only',base['definition_id'],{**base,'source_columns':['duration'],'measurement_rule':'duration','description':'Changed to duration','expected_revision':1})
# Extract original worker statements up to and including definitions=... .
func=ast.parse(textwrap.dedent(inspect.getsource(p.AnalysisPipelineService._run))).body[0]
body=[]
for statement in func.body:
    body.append(statement)
    if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='definitions' for t in statement.targets):
        break
else: raise AssertionError('Original definitions assignment missing')
func.body=body+[ast.Return(value=ast.Name(id='definitions',ctx=ast.Load()))]
func.name='worker_definition_prefix'
module=ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[]))
namespace=dict(p.__dict__); exec(compile(module,str(ROOT/'src/gurumoji/analysis_pipeline.py'),'exec'),namespace)
definitions=namespace['worker_definition_prefix'](s,pipeline_id,'http://synthetic.invalid/')
assert definitions[0]['version']==2
step=dict(c.execute("SELECT * FROM analysis_step_attempts WHERE pipeline_id=? AND step_id='manual_measurement'",(pipeline_id,)).fetchone())
result=s._execute_step(pipeline,step,snapshot,definitions,'http://synthetic.invalid/')
value=result['artifact']['datasets']['measurements']['rows'][0]['synthetic_value']
assert value==60
second_result={'binding_definition_version':binding['resolved'][0]['definition_version'],'worker_loaded_definition_version':definitions[0]['version'],
 'binding_expected_measurement':'text_length','worker_measurement':definitions[0]['measurement_rule'],'expected_original_value':3,'actual_isolated_manual_step_value':value,
 'step_status':result['status'],'full_pipeline_executed':False}
c.close()
print(json.dumps({'method':'source-isolated worker prefix + original service/step methods with synthetic in-memory SQLite; scheduled worker disabled',
 'existing_adoption_after_draft_save':first_result,'definition_version_race':second_result,'external_calls':0,'real_runtime_or_source_mutation':False},ensure_ascii=False,indent=2))
