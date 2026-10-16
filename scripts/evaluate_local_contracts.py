"""Opt-in real LM Studio contract probes using synthetic fixtures only.

Contract success is not scientific quality approval. No user DB or credentials
are read. Full preregistered 108-trial review and human adjudication stay separate.
"""
import argparse
import atexit
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'src'),str(ROOT)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--load',action='store_true',help='Explicitly load this installed model for the probe (16k context, TTL 10 minutes)')
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'output/validation').resolve()): parser.error('output must be under output/validation')
    output.mkdir(parents=True,exist_ok=True)
    if args.load:
        import lmstudio as lms
        client=lms.Client(api_host='127.0.0.1:1234')
        loaded=[handle for handle in client.llm.list_loaded() if handle.identifier==args.model]
        if not loaded:
            handle=client.llm.model(args.model,config={'contextLength':16384},ttl=600)
            atexit.register(handle.unload)
            print('Loaded installed model for synthetic probes:',handle.identifier,flush=True)
    from runtime_isolation import configure_environment,protect_runtime,application_paths
    records=[]
    with tempfile.TemporaryDirectory(prefix='gurumoji-real-model-') as temporary:
        configure_environment(temporary);protect_runtime()
        import app
        for key,value in application_paths(temporary).items():
            if hasattr(app,key): setattr(app,key,value)
        from gurumoji.analysis_core import fingerprint
        from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters,ADAPTER_VERSION
        from gurumoji.services import model_context,notation
        from test_analysis_orchestration import RuntimeTests
        from test_orchestration_artifact_review import ArtifactReviewTests
        def call(provider,key,model,system,user,name,schema,check=lambda:None,usage=lambda _:None,base='',timeout=90,**kwargs):
            return app.ai_client.call_ai_json(provider,'',model,system,user,name,schema,
                post=lambda url,headers,payload,**kw:app.post_json(url,headers,payload,timeout=90,**{k:v for k,v in kw.items() if k!='timeout'}),
                lmstudio_base=app.lmstudio_base_url,lmstudio_model_id=app.lmstudio_model_id,
                lmstudio_reasoning=app.lmstudio_reasoning_settings,providers={'lmstudio'},
                check_cancelled=check,usage_callback=usage,base_url='http://127.0.0.1:1234',
                ai_efforts={'outline':'off','cleanup':'off','notation':'off','name_extract':'off','name_verify':'off'},
                max_output_tokens=min(kwargs.get('max_output_tokens',2048),2048),data_messages=kwargs.get('data_messages'))
        resolve,runner=make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda:SimpleNamespace(lmstudio_base_url='http://127.0.0.1:1234'),
            configured_ai_credentials=lambda *_:('',args.model))
        options=resolve({'provider':'lmstudio','model':args.model,'analysis_interval_version':1,
            'model_context_version':1,'artifact_review_version':1,'timeout_seconds':90,'adapter_version':ADAPTER_VERSION})
        def probe(name,context,work,validate=lambda *_:None):
            started=time.monotonic();usage=[]
            record={'name':name,'model':args.model,'provider':'lmstudio','input_hash':fingerprint(context),'usage':usage}
            try:
                raw=work(usage.append); record.update(raw=raw,raw_hash=fingerprint(raw));validate(raw,usage)
                record['contract_status']='passed'
            except Exception as exc:
                record.update(contract_status='failed',error_code=getattr(exc,'code',type(exc).__name__),error_type=type(exc).__name__)
            record['elapsed_seconds']=round(time.monotonic()-started,3);records.append(record)
            (output/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
            print(name,record['contract_status'],record.get('error_code',''),flush=True)
        fixture=RuntimeTests();fixture.setUp()
        try:
            fixture.snapshot['analysis']['segments']=[{'id':'u1','speaker':'A','text':'架空の提案に賛成です。費用を抑えられます。','start':0,'end':3,'annotation':{'codes':[]}},
                {'id':'u2','speaker':'B','text':'私は反対です。保守の負担が大きくなります。','start':3,'end':7,'annotation':{'codes':[]}}]
            fixture.service=fixture.make_service(adapter_version=ADAPTER_VERSION)
            run=fixture.start(analysis_interval_version=1,model_context_version=1,specialist_orchestration_version=1)
            fixture.service._prepare_intervals(run['run_id'])
            with fixture.service._db() as db:
                run=fixture.service._read_run(db,run['run_id'])
                tasks=[fixture.service._register(db,run,intent,phase='initial_analysis',automatic=True)
                    for intent in fixture.service._initial_specialist_intents(db,run) if intent['role']!='statistics']
            for task in tasks:
                with fixture.service._db() as db: context=fixture.service._context(db,run,task)
                def validate(raw,usage,task=task,context=context):
                    manifest=next(value['context_manifest'] for value in usage if 'context_manifest' in value)
                    task=copy.deepcopy(task);task.update(context_manifest=manifest,context_manifest_hash=fingerprint(manifest))
                    with fixture.service._db() as db: fixture.service._validate_result(db,{**run,'config':{**run['config'],**options,'artifact_review_version':0}},task,raw)
                probe('interval_'+task['role'],context,lambda usage,task=task,context=context:runner(task['role'],context,{**options,'artifact_review_version':0},lambda:None,usage),validate)
        finally: fixture.doCleanups()
        review=ArtifactReviewTests();review.setUp()
        try:
            review.orchestrator();task=review.review_task()
            with review.service._db() as db:
                run=review.service._read_run(db,review.rid);context=review.service._context(db,run,task)
            def validate_review(raw,usage):
                manifest=next(value['context_manifest'] for value in usage if 'context_manifest' in value)
                checked=copy.deepcopy(task);checked.update(context_manifest=manifest,context_manifest_hash=fingerprint(manifest))
                with review.service._db() as db: review.service._validate_result(db,{**run,'config':{**run['config'],**options}},checked,raw)
            probe('finding_review',context,lambda usage:runner('interpretation',context,options,lambda:None,usage),validate_review)
        finally: review.doCleanups()
        group={'id':'synthetic-notation','allowed':['サーバー','サーバ'],'canonical':None,'source':'unresolved',
            'variants':[{'term':'サーバー'},{'term':'サーバ'}],
            'occurrences':[{'segment_id':'u1','start':0,'end':4,'variant':'サーバー','context':'サーバーを保守します。'}], 'reason':'架空候補'}
        segments=[{'id':'u1','text':'サーバーを保守します。'}]
        probe('notation',{'segments':segments,'group':group},lambda usage:notation.resolve(segments,{'groups':[group]},
            call=lambda system,user,name,schema:call('lmstudio','',args.model,system,user,name,schema,usage=usage)))
        summary={'model':args.model,'provider':'lmstudio','records':len(records),'contract_passed':sum(r['contract_status']=='passed' for r in records),
            'scientific_quality':'not_adjudicated','adoption':'not_approved','real_user_data_accessed':False,
            'code_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False))
    return int(any(row['contract_status']!='passed' for row in records))


if __name__=='__main__': raise SystemExit(main())
