from pathlib import Path
import copy,threading,unittest
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import contextmanager
from flask import Flask
from gurumoji.services.developed_features import register_developed_features
from gurumoji.analysis_store import initialize_store
from gurumoji.analysis_orchestration import AnalysisOrchestrationService as LegacyService
from test_developed_analysis_asset_bindings import SyntheticStore
from pipeline_fixtures import reply
class CorePipelineBridgeTests(unittest.TestCase):
 def test_registered_factory_executes_and_seals_v2_without_legacy_history_mix(self):
  fixture=SyntheticStore(handler=True);self.addCleanup(fixture.close)
  snapshot=copy.deepcopy(fixture.snapshot);snapshot['analysis']={'segments':snapshot['segments']}
  @contextmanager
  def readonly():
   import sqlite3
   db=sqlite3.connect(fixture.path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
   try:db.execute('PRAGMA query_only=ON');yield db
   finally:db.close()
  runtime=SimpleNamespace(DATABASE_FILE=fixture.path, DATA_DIRECTORY=fixture.path.parent,
    call_orchestration_ai_json=Mock(side_effect=AssertionError('実モデルの呼出しは禁止')),
    load_token_config=lambda:{},configured_ai_credentials=lambda *_:('','TEST-synthetic-model'),
    database_connection=fixture.connect,analysis_archive_store=lambda:fixture.store,
    orchestration_source_guard=lambda db,item,stamp:{'id':item},library_write_lock=threading.RLock(),
    library_row=lambda item:{'id':item},archive_source_stamp=lambda *args,**kwargs:snapshot['input_hash'],
    build_analysis_orchestration_snapshot=lambda _:copy.deepcopy(snapshot),make_staged_initial_builder=lambda **kwargs:None,
    vault_registry=Mock(side_effect=AssertionError('実Vaultの呼出しは禁止')),
    analysis_history_connection=readonly,analysis_history_item=lambda item:{'id':item})
  app=Flask(__name__);register_developed_features(app,runtime);extension=app.extensions['core_pipeline']
  service=extension['service']();service.schedule=False;service.expert_provider=None;service.memory_manager=None
  service.agent_runner=lambda role,context,*args:reply(context)
  client=app.test_client();path='/api/library/TEST-conversation/analysis/core-pipeline'
  response=client.post(path,json={'model':'TEST-synthetic-model','obsidian_management':False,'time_limit_seconds':None,'max_calls':40})
  self.assertEqual(response.status_code,202,response.get_json());run=response.get_json()['run'];service.run(run['run_id'])
  status=client.get(path+'/'+run['run_id']).get_json()['run'];self.assertEqual(status['status'],'completed',status)
  saved=extension['publication']().status('TEST-conversation',run['run_id'])
  self.assertEqual(saved['save_status'],'saved',saved)
  self.assertEqual(fixture.store.verified_package(saved['result_run_id'])[2]['schema_version'],2)
  legacy=LegacyService(connect=fixture.connect,find_item=lambda _:{'id':'TEST-conversation'},snapshot_builder=lambda _:copy.deepcopy(snapshot),agent_runner=None,method_runner=None,schedule=False)
  self.assertEqual(legacy.history('TEST-conversation'),[])
  self.assertEqual([r['run_id'] for r in service.history('TEST-conversation')],[run['run_id']])
  self.assertIs(extension['table_reader']()._run_budgets,service._run_budgets)
  runtime.call_orchestration_ai_json.assert_not_called();runtime.vault_registry.assert_not_called()
 def test_core_usage_keeps_unknown_and_rejects_conflicting_delivery(self):
  from test_developed_analysis_orchestration import RuntimeTests
  from gurumoji.analysis_core import AnalysisContractError
  fixture=RuntimeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
  run=fixture.start();service=fixture.service
  usage={'usage_id':'TEST-call','input_tokens':0,'output_tokens':None,'total_tokens':None,'reported':True}
  service._record_usage(run['run_id'],'TEST-task',usage)
  service._record_usage(run['run_id'],'TEST-task',usage)
  with self.assertRaises(AnalysisContractError) as caught:
   service._record_usage(run['run_id'],'TEST-task',{**usage,'output_tokens':1})
  self.assertEqual(caught.exception.code,'usage_conflict')
  with service._db() as db:measured=service._usage(db,service._read_run(db,run['run_id']))
  self.assertEqual(measured['input_tokens'],0);self.assertIsNone(measured['output_tokens'])
  self.assertEqual(measured['measurement_status'],'partial');self.assertEqual(measured['measured_calls'],1)

 def test_staged_ready_cache_requires_same_builder_without_rebuilding(self):
  from test_developed_analysis_orchestration import RuntimeTests
  from test_orchestration_initial_recovery import SyntheticBuilder
  from gurumoji.analysis_core import AnalysisContractError
  fixture=RuntimeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
  fixture.item.update(revision_count=1,analysis_revision=2)
  builder=SyntheticBuilder(fixture);fixture.service=fixture.make_service(initial_builder=builder)
  run=fixture.start(request_id='TEST-staged');fixture.service._build_initial(run['run_id'])
  with fixture.service._db() as db:original=db.execute('SELECT snapshot_json FROM orchestration_initials WHERE initial_id=?',(run['initial_id'],)).fetchone()[0]
  builder.version='TEST-updated-builder'
  with self.assertRaises(AnalysisContractError) as caught:fixture.start(request_id='TEST-next')
  self.assertEqual(caught.exception.code,'initial_revalidation_required')
  status=fixture.service.status('conversation',run['run_id'])
  self.assertEqual(status['initial']['status'],'revalidation_required');self.assertNotIn('resume',status['allowed_actions'])
  fixture.service._run_analysis(run['run_id'])
  self.assertEqual(fixture.service.status('conversation',run['run_id'])['status'],'recovery_required')
  with fixture.service._db() as db:self.assertEqual(db.execute('SELECT snapshot_json FROM orchestration_initials WHERE initial_id=?',(run['initial_id'],)).fetchone()[0],original)
  self.assertEqual(builder.freeze_count,1);self.assertFalse(fixture.calls)

 def test_local_placement_is_explicit_opt_in_and_keeps_current_outline(self):
  import ast,os,typing
  from unittest.mock import patch
  from gurumoji.services.ai import transcript_finishing
  source=Path(__file__).resolve().parents[1]/'src/gurumoji/app.py'
  tree=ast.parse(source.read_text(encoding='utf-8'))
  function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_outline_with_ai')
  manager=Mock();manager.ensure.return_value={'action':'TEST-kept'}
  create=Mock(return_value={'provenance':{}})
  namespace={'__package__':'gurumoji','Any':typing.Any,'Callable':typing.Callable,'os':os,
    'lmstudio_placement':Mock(return_value=manager),'ai_transcript_finishing':transcript_finishing,
    'finish_create_outline':create,'call_ai_json':Mock(side_effect=AssertionError('実モデル禁止')),
    'utc_now_iso':lambda:'TEST-fixed-time'}
  exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
  args=([{'id':'TEST-u1','text':'合成の本文','speaker':'TEST-A'}],{},'lmstudio','','TEST-model',lambda *_:None,lambda:None)
  with patch.dict(os.environ,{'GURUMOJI_LMSTUDIO_AUTO_PLACEMENT':'0'}):namespace['create_outline_with_ai'](*args)
  namespace['lmstudio_placement'].assert_not_called()
  with patch.dict(os.environ,{'GURUMOJI_LMSTUDIO_AUTO_PLACEMENT':'1'}):result=namespace['create_outline_with_ai'](*args)
  manager.ensure.assert_called_once();self.assertEqual(result['provenance']['local_placement'],{'action':'TEST-kept'})
  self.assertEqual(create.call_count,2);namespace['call_ai_json'].assert_not_called()

if __name__=='__main__':unittest.main()
