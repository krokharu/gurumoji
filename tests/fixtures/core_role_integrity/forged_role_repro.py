"""Public synthetic CPU repro; no private Git/data/approval, no model/network.

PYTHONPATH=<fixed snapshot>/src;<fixed snapshot>/tests
python -X utf8 -B forged_role_repro.py <new artifact output directory>
Exit1 means the required rejection failed. It is never converted to success.
"""
import copy,hashlib,json,os,socket,sqlite3,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(root);sys.dont_write_bytecode=True
os.environ.update(TEMP=str(root),TMP=str(root),MOJIOKOSI_DATA_DIR=str(root/'data'),MOJIOKOSI_OUTPUT_DIR=str(root/'output'),MOJIOKOSI_BACKUP_DIR=str(root/'backup'))
def deny(*a,**k):raise AssertionError('No socket/model/network in synthetic reproduction')
socket.socket.connect=deny;socket.socket.bind=deny;socket.create_connection=deny
from gurumoji.analysis_core import canonical,fingerprint,AnalysisContractError
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services import analysis_orchestration_adapters as adapters
from types import SimpleNamespace
import test_analysis_orchestration as support
results=[]
for mode in ['result_state_role_only','both_result_and_task_state_role','task_state_role_only']:
    dbfile=root/(mode+'.sqlite3');assert not dbfile.exists()
    snapshot={'input_hash':'synthetic-role-v1','source_revision':1,'analysis_revision':1,
      'analysis':{'segments':[{'id':'synthetic-u0','text':'Synthetic utterance only','speaker':'S0','valid_time':False,'excluded':False}]}}
    service=AnalysisOrchestrationService(connect=lambda:sqlite3.connect(dbfile),find_item=lambda _: {'id':'synthetic-item'},
      snapshot_builder=lambda _:copy.deepcopy(snapshot),source_fingerprint=lambda _:snapshot['input_hash'],
      agent_runner=lambda *args:support.core('Synthetic adopted Core; human review pending'),method_runner=deny,schedule=False)
    run=service.start('synthetic-item',{'model':'synthetic','question':'Synthetic role integrity inquiry','obsidian_management':False,'publication_targets':[]})
    with service._db() as db:
        current=service._read_run(db,run['run_id'])
        task=service._register(db,current,support.intent('core',question='Synthetic role integrity inquiry'),phase='core',automatic=True)
    service._execute(run['run_id'],task['task_id'])
    with service._db() as db:
        current=service._read_run(db,run['run_id'])
        task=json.loads(db.execute('SELECT state_json FROM orchestration_tasks WHERE task_id=?',(task['task_id'],)).fetchone()[0]);assert task['status']=='succeeded'
        row=db.execute('SELECT * FROM orchestration_results WHERE task_id=?',(task['task_id'],)).fetchone()
        service._apply_core(db,current,task,row);service._write_run(db,current)
        decision=db.execute('SELECT * FROM orchestration_decisions WHERE result_id=?',(row['result_id'],)).fetchone();assert decision
        raw=bytes(row['raw_json'],'utf8');decision_before=decision['payload_json'];meta=json.loads(row['state_json'])
        original={'SQL_result_id':row['result_id'],'SQL_result_run_id':row['run_id'],'SQL_result_task_id':row['task_id'],
          'task_role':task['role'],'result_role':meta['role'],'decision_role':json.loads(decision_before)['role'],'raw_sha256':hashlib.sha256(raw).hexdigest()}
        if mode!='task_state_role_only':
            meta['role']='critic';db.execute('UPDATE orchestration_results SET state_json=? WHERE result_id=?',(canonical(meta).decode(),row['result_id']))
        if mode!='result_state_role_only':
            changed=copy.deepcopy(task);changed['role']='critic';db.execute('UPDATE orchestration_tasks SET state_json=? WHERE task_id=?',(canonical(changed).decode(),task['task_id']))
        consumer=service._register(db,current,support.intent('critic',question='Synthetic role integrity inquiry',target_id='view',target_version=current['view_version']),phase='specialists',automatic=True)
    before=dbfile.read_bytes();calls=[]
    record={'case':mode,'changed_only':'state_json.role; SQL IDs/raw/hash/committed decision untouched','before':original,'expected':'reject before synthetic transport'}
    try:
        with service._db() as db:context=service._context(db,service._read_run(db,run['run_id']),consumer)
        resolve,runner=adapters.make_orchestration_adapters(call_ai_json=lambda *args:calls.append(json.loads(args[4])) or support.critic(context),
          load_token_config=lambda:SimpleNamespace(lmstudio_base_url='http://127.0.0.1:9/v1'),configured_ai_credentials=lambda *_:('','synthetic'))
        runner('critic',context,resolve({}),lambda:None,lambda _:None)
        delivered=next(x for x in calls[-1]['results'] if x.get('result_id')==row['result_id'])
        record.update(actual='NOERROR',FAIL=True,synthetic_transport_calls=len(calls),body_delivered='content' in delivered,body_not_delivered=delivered.get('body_not_delivered'),delivered_role=delivered.get('role'))
    except AnalysisContractError as error:record.update(actual='AnalysisContractError',error=error.code,PASS=True,synthetic_transport_calls=len(calls))
    assert dbfile.read_bytes()==before
    with service._db() as db:
        r=db.execute('SELECT * FROM orchestration_results WHERE result_id=?',(row['result_id'],)).fetchone()
        d=db.execute('SELECT * FROM orchestration_decisions WHERE result_id=?',(row['result_id'],)).fetchone()
        assert r['raw_json'].encode()==raw and d['payload_json']==decision_before
    record['readers_DB_bytes_unchanged']=True;results.append(record)
report={'python':sys.version,'loaded_source':{name:{'path':str(Path(sys.modules[name].__file__)),'sha256':hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()} for name in ['gurumoji.analysis_orchestration','gurumoji.services.analysis_orchestration_adapters']},
  'cases':results,'PASS':sum(bool(x.get('PASS')) for x in results),'FAIL':sum(bool(x.get('FAIL')) for x in results),'ERROR':0,'SKIP':0,
  'provenance':'synthetic real service execute/Handler committed adoption; only explicit state_json role corruption; no raw/hash/SQL-ID/decision edits; real adapter with in-memory transport'}
(root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));sys.exit(1 if report['FAIL'] else 0)
