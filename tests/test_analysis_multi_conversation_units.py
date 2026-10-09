"""Invented source metadata; real native Store writer, policies, Handler and HC.

No forged Handler producer/results or adoption flags. Native observations are
imported synthetic measurements through save/save_connection_metadata; all
derived producers and participant adoption come from the production APIs.
"""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from gurumoji.analysis_core import AnalysisContractError, fingerprint, web_asset_plan_template, TABLE_PILOT_MAX_BYTES
from gurumoji.analysis_method_registry import connection_method_descriptor, connection_output_contract
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.analysis_store import AnalysisStore, AssetBindingError, canonical, initialize_store, safe_path
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
from gurumoji import transcript_preparation
from gurumoji.services.analysis_archive import make_analysis_archive
from gurumoji.services.analysis_pipeline_adapters import make_analysis_pipeline_adapters
from gurumoji.services.group_analysis import group_analysis_for_row
from gurumoji.services import library_rows


class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()


class MultiConversationUnitsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"native.sqlite3"
        cases={"C1":[(0,"observed"),(2,"observed")],"C2":[(4,"observed")]}
        if self._testMethodName=="test_real_missing_unknown_unprocessed_excluded_denominators":
            cases={"C1":[(0,"observed"),(None,"missing"),(2,"excluded"),(None,"unknown")],
                "C2":[(None,"unprocessed"),(4,"observed")]}
        if self._testMethodName=="test_sixteen_saved_sources_actual_get_post_handler_save_fresh":
            cases={"C"+str(i):[(i,"observed")] for i in range(1,17)}
        if self._testMethodName=="test_pool_parent_reference_true_carrier_limit_rejects_save":
            cases={"C"+str(i):[(i+j,"observed") for j in range(3)] for i in range(1,17)}
            cases["C1"]=[(0,"observed"),(2,"observed")]
        with self.connect() as db:
            db.execute("CREATE TABLE application_metadata(key TEXT PRIMARY KEY,value TEXT)")
            db.execute("INSERT INTO application_metadata VALUES ('library_id','TEST-multi-library')")
            db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY, revision_count INTEGER, analysis_revision INTEGER, source_name TEXT, segments_json TEXT, speaker_names_json TEXT, speaker_profiles_json TEXT, session_profile_json TEXT, analysis_config_json TEXT, analysis_annotations_json TEXT, outline_json TEXT, emotion_analysis_json TEXT, original_segments_json TEXT, original_segments_status TEXT, media_path TEXT, analysis_updated_at TEXT, updated_at TEXT)")
            db.execute("CREATE TABLE speaker_registry(id TEXT PRIMARY KEY)")
            initialize_store(db)
            transcript_preparation.initialize(db)
            for cid,values in cases.items():
                segments=[{"id":str(i),"text":"TEST synthetic utterance "+str(v),"speaker":"S1","excluded":status=="excluded",
                    "valid_time":True,"start":i*2,"end":i*2+1} for i,(v,status) in enumerate(values)]
                if self._testMethodName=="test_real_missing_unknown_unprocessed_excluded_denominators" and cid=="C2":
                    segments[0]["speaker"]="S-null"
                db.execute("INSERT INTO library_items VALUES (?,?,?, ?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid,1,1,cid,json.dumps(segments),json.dumps({"S1":"same display name","silent":"known silent"}),"{}","{}","{}",
                     json.dumps({str(i):{"excluded":True} for i,(_v,status) in enumerate(values) if status=="excluded"}),
                     "null","null",json.dumps(segments),"imported","","2026-10-09","2026-10-09"))
        self.store=AnalysisStore(self.path,self.connect)
        archive=make_analysis_archive(analysis_archive_store=lambda:self.store,database_connection=self.connect,
            row_segments=library_rows.row_segments,row_session_profile=library_rows.row_session_profile)
        self.archive_stamp,self.archive_snapshot=archive[:2]
        def group(row,**kwargs):
            return group_analysis_for_row(row,include_research_rows=False,execute=False,defer_research=True,connect=self.connect,
                row_segments=library_rows.row_segments,row_original_segments=library_rows.row_original_segments,
                row_speaker_profiles=library_rows.row_speaker_profiles,row_session_profile=library_rows.row_session_profile,
                list_speaker_registry=lambda **_kwargs:[])
        def no_model(*_args,**_kwargs):raise AssertionError("No research/model execution")
        self.production_snapshot=make_analysis_pipeline_adapters(archive_snapshot=self.archive_snapshot,archive_source_stamp=self.archive_stamp,
            group_analysis_for_row=group,call_ai_json=no_model,configured_ai_credentials=no_model,
            encode_transformer_texts=no_model,load_token_config=no_model)[0]
        self.service=self.fresh_service(self.store)
        self.runs={cid:self.service.start(cid,{"model":"TEST-no-model","max_tasks":50}) for cid in cases}
        self.run=self.runs["C1"]
        self.native=[]
        for cid,values in cases.items():
            with self.connect() as db: initial=self.service._initial(db,self.runs[cid]["initial_id"])
            fields=["utterance_id","conversation_id","value_status","n"]
            rows=[{"utterance_id":str(i),"conversation_id":cid,"value_status":status,"n":v} for i,(v,status) in enumerate(values)]
            saved=self.store.save(item_id=cid,kind="ai_insights",snapshot=initial,
                result={"parameters":{},"synthetic_import":True},datasets={"correlations":(fields,rows)},
                request_id="native-import:"+cid,input_fingerprint=initial["input_hash"],source_revision=1,analysis_revision=1,publish=False)
            self.native.append(self.register_native(saved))
        self.app=Flask(__name__)
        register_orchestration_routes(self.app,lambda:self.service,lambda _:self.fail("No model preparation"),table_reader=self.reader_service)
        self.client=self.app.test_client()
        self.base=f'/api/library/C1/analysis/orchestration/{self.run["run_id"]}'

    def connect(self):
        db=sqlite3.connect(self.path,factory=ClosingConnection); db.row_factory=sqlite3.Row; return db

    def find_item(self,cid):
        with self.connect() as db: return db.execute("SELECT * FROM library_items WHERE id=?",(cid,)).fetchone()

    def readonly_connect(self):
        db=sqlite3.connect(self.path.resolve().as_uri()+"?mode=ro",uri=True,factory=ClosingConnection)
        db.row_factory=sqlite3.Row;db.execute("PRAGMA query_only=ON");return db

    def reader_service(self):
        def find(cid):
            with self.readonly_connect() as db:return db.execute("SELECT * FROM library_items WHERE id=?",(cid,)).fetchone()
        def stamp(row):
            with self.readonly_connect() as db:return self.archive_stamp(row,connection=db)
        return AnalysisOrchestrationService(connect=self.readonly_connect,find_item=find,source_fingerprint=stamp,
            snapshot_builder=None,agent_runner=None,method_runner=None,table_store=AnalysisStore(self.path,self.readonly_connect),schedule=False)

    def source_stamp(self,item):
        return self.archive_stamp(item)

    def snapshot(self,item):
        return self.production_snapshot(item)

    def fresh_service(self,store=None):
        def no_agent(*_): raise AssertionError("No model calls")
        return AnalysisOrchestrationService(connect=self.connect,find_item=self.find_item,snapshot_builder=self.snapshot,
            source_fingerprint=self.source_stamp,method_runner=run_orchestration_method,agent_runner=no_agent,
            table_store=store or AnalysisStore(self.path,self.connect),schedule=False)

    def register_native(self,saved,*,include_original=True):
        fixed,result,manifest,content=self.store.verified_package(saved["id"])
        source={"target_type":"snapshot","target_id":manifest["input_snapshot_id"],"version":str(manifest["source_revision"]),
            "content_hash":fingerprint(fixed),"hash_domain":"canonical-json-v1","library_id":manifest["library_id"]}
        scope={"scope_id":"native:"+manifest["conversation_id"],"mode":"dataset","input_refs":[source],
            "conversation_ids":[manifest["conversation_id"]],"member_ids":[e["evidence_id"] for e in fixed["evidence"] if not e["excluded"]],
            "context_ids":[e["evidence_id"] for e in fixed["evidence"] if e["excluded"]]}
        scope["manifest_hash"]=fingerprint(scope)
        producer={"kind":"system","actor_id":"TEST-native-observation-import","step_ids":[]}
        def key(name):
            return {"library_id":manifest["library_id"],"store_run_id":saved["id"],"artifact_id":next(a["id"] for a in manifest["artifacts"] if a["name"]==name),"output_name":name}
        def raw_hash(name): return "sha256:"+hashlib.sha256(content[name]).hexdigest()
        native=connection_method_descriptor("pearson");output=connection_output_contract("correlation","tables/correlations.json")
        meaning={"unit":"utterance","description":"Imported TEST synthetic native observations","status":"declared","definition_refs":[]}
        original={"asset_key":key("input.json"),"raw_byte_hash":raw_hash("input.json"),"schema":native["native_input_schema"],
            "scope":scope,"producer":producer,"adapter":native["native_adapter"],"meaning":meaning,"source_ref":source}
        fields=self.store.read_table(saved["id"],"correlations")["fields"]
        definition={"target_type":"definition","target_id":"TEST-fixed-native-definition","version":"1",
            "content_hash":fingerprint({"definition":"synthetic observed measure"}),"hash_domain":"canonical-json-v1"}
        variables=[{"variable_id":f,"version":1,"definition_hash":definition["content_hash"],"definition_ref":definition,
            "value_type":"integer" if f=="n" else "string","scale":"ratio" if f=="n" else "nominal","unit":"utterance",
            "value_domain":"TEST-explicit-measure" if f=="n" else "native-identity","generation":producer,"validity":"structural_checked"} for f in fields]
        asset={"asset_key":key("tables/correlations.json"),"raw_byte_hash":raw_hash("tables/correlations.json"),"schema":output["schema"],
            "scope":scope,"producer":producer,"adapter":output["adapter"],"meaning":meaning,"contract_id":"gurumoji.analysis-asset-connection","contract_version":1,
            "content_hash":raw_hash("tables/correlations.json"),"content_domain":"raw-bytes-v1","kind":"observation_table","source_refs":[source],
            "method_id":"correlation","method_version":connection_method_descriptor("correlation")["registry_version"],"variables":variables,"parent_refs":[source]}
        def state(a):
            return {"asset_key":a["asset_key"],"target_content_hash":a["raw_byte_hash"],"target_domain":"raw-bytes-v1","state_revision":1,"policy_revision":1,
                "status":"adopted","allowed_purposes":["exploratory"],"send_policy":"local_only","destinations":[],"revoked":False,
                "review_refs":[],"reason":"TEST explicit local structural reuse policy; no human adoption claim","updated_at":"2026-10-09T00:00:00Z"}
        self.store.save_connection_metadata(item_id=manifest["conversation_id"],snapshot={},request_id="native-policy:"+saved["id"],
            metadata={"version":1,"assets":[asset],"originals":[original] if include_original else [],
                "states":[state(asset),state(original)] if include_original else [state(asset)],"producer_links":[]})
        return asset

    def options(self):
        response=self.client.get(self.base+"/asset-plans/options")
        self.assertEqual(response.status_code,200,response.get_json()); return response.get_json()

    def pool(self):
        opts=self.options()["unit_pool"]
        self.assertTrue(opts["enabled"]);self.assertIsNone(opts["reason_code"])
        request={**opts["request_template"],"source_ids":[s["option_id"] for s in opts["sources"] if s["source"]["asset_key"] in [a["asset_key"] for a in self.native]],
            "columns":opts["required_columns"]+["n"]}
        response=self.client.post(self.base+"/asset-plans",json=request)
        self.assertEqual(response.status_code,202,response.get_json())
        with self.connect() as db:counts=tuple(db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ("analysis_runs","orchestration_tasks"))
        duplicate=self.client.post(self.base+"/asset-plans",json=request)
        self.assertEqual(duplicate.status_code,200,duplicate.get_json())
        for key in ("identity","tasks","scope"):self.assertEqual(response.get_json()[key],duplicate.get_json()[key])
        with self.connect() as db:self.assertEqual(counts,tuple(db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ("analysis_runs","orchestration_tasks")))
        self.service._drain_tasks(self.run["run_id"])
        task=self.task(response.get_json()["tasks"]["P1"])
        self.assertEqual(task["status"],"succeeded",task)
        self.assertEqual(set(response.get_json()["scope"]),{"scope_id","manifest_hash","mode","conversation_ids","member_ids","context_ids","input_refs"})
        return task,self.store.connected_output_descriptor(task["table_store_run_id"])

    def task(self,tid):
        with self.connect() as db:return json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(tid,)).fetchone()[0])

    def human_options(self):
        response=self.client.get(self.base+"/human-records")
        self.assertEqual(response.status_code,200,response.get_json()); return response.get_json()["options"]

    def mapping_payload(self,option,assignments=None):
        step=option["human_steps"][0]
        text=json.dumps({"participant_mapping":assignments or [{**s,"participant_id":"P-silent" if s["speaker_id"]=="silent" else "P-null" if s["speaker_id"]=="S-null" else "P1"} for s in option["speakers"]]})
        old=step["latest_record"];rid=old["record"]["record_id"] if old else "TEST-group-mapping"
        revision=step["next_revision"]
        record={"record_id":rid,"revision":revision,"supersedes_record_ref":step["next_supersedes_record_ref"],
            "actor":{"kind":"researcher","actor_id":"TEST-explicit-human"},"decision":"adopt","target":option["target"],
            "allowed_step_ids":[step["step_id"]],"scope":option["scope"],"recorded_at":"2026-10-09T00:00:00Z","reason":"TEST explicit two-conversation identity",
            "record_ref":{"target_type":"researcher_memo","target_id":"human-source:"+rid,"version":str(revision),"content_hash":"sha256:"+hashlib.sha256(text.encode()).hexdigest(),
                "hash_domain":"raw-bytes-v1","library_id":option["library_id"]}}
        return {"asset_key":option["asset_key"],"record":record,"source_text":text,"expected_state_revision":option["expected_state_revision"]}

    def adopt(self,asset):
        option=next(o for o in self.human_options() if o["asset_key"]==asset["asset_key"])
        self.assertEqual(option["scope"]["conversation_ids"],["C1","C2"])
        self.assertEqual(len(option["speakers"]),sum(len(self.store.participant_speakers(self.store._connection_content(a)[1])) for a in self.native))
        response=self.client.post(self.base+"/human-records",data=canonical(self.mapping_payload(option)),content_type="application/json")
        self.assertEqual(response.status_code,201,response.get_json()); return response.get_json()

    def aggregate(self,asset,operation="mean",service=None):
        service=service or self.service
        options=service.asset_plan_options("C1",self.run["run_id"])
        choice=next(c for c in options["inputs"] if c["source"].get("asset_key")==asset["asset_key"])
        self.assertIsNotNone(choice["confirmed_participant_mapping"])
        plan={**options["plan_template"],"steps":[{"step_id":"F1","method_id":"unit_aggregate",
            "parameters":{"value_column":"n","operation":operation,"unit":"participant","participant_mapping":choice["confirmed_participant_mapping"]},
            "scope":{k:choice["scope"][k] for k in ("scope_id","manifest_hash")},
            "inputs":[{"input_ref_id":choice["input_ref_id"],"role":"data_input","selection":"selected","omission_reason":None,"source":choice["source"]}]}]}
        outcome=service.register_asset_plan("C1",self.run["run_id"],plan);service._drain_tasks(self.run["run_id"])
        task=self.task(outcome["tasks"]["F1"]);self.assertEqual(task["status"],"succeeded",task)
        return task,service.table_store.verified_package(task["table_store_run_id"])[1]

    def projection(self):
        options=self.options();choice=next(c for c in options["inputs"] if c["source"].get("asset_key")==self.native[0]["asset_key"])
        fixed=self.store.verified_package(self.native[0]["asset_key"]["store_run_id"])[0]
        ids=["utterance:"+fingerprint([self.store.library_id(),"C1",fixed["input_hash"],e["utterance_id"]])[7:] for e in fixed["evidence"]]
        plan={**options["plan_template"],"steps":[{"step_id":"I1","method_id":"unit_projection",
            "parameters":{"columns":["unit_id","conversation_id","speaker_id","value_status","n"],"unit_ids":ids},
            "scope":{k:choice["scope"][k] for k in ("scope_id","manifest_hash")},
            "inputs":[{"input_ref_id":choice["input_ref_id"],"role":"data_input","selection":"selected","omission_reason":None,"source":choice["source"]}]}]}
        response=self.client.post(self.base+"/asset-plans",json=plan);self.assertEqual(response.status_code,202,response.get_json())
        self.service._drain_tasks(self.run["run_id"]);task=self.task(response.get_json()["tasks"]["I1"])
        self.assertEqual(task["status"],"succeeded",task)
        return task,self.store.connected_output_descriptor(task["table_store_run_id"])

    def test_single_projection_exact_silent_roster_human_post(self):
        task,asset=self.projection()
        option=next(o for o in self.human_options() if o["asset_key"]==asset["asset_key"])
        self.assertEqual(option["speakers"],[{"conversation_id":"C1","speaker_id":"S1"},{"conversation_id":"C1","speaker_id":"silent"}])
        self.assertEqual(self.options()["participant_context"]["speakers"],option["speakers"])
        response=self.client.post(self.base+"/human-records",data=canonical(self.mapping_payload(option)),content_type="application/json")
        self.assertEqual(response.status_code,201,response.get_json())
        self.assertEqual(len(self.store.verified_package(task["table_store_run_id"])[1]["datasets"]["table"]["rows"]),2)

    def test_sixteen_saved_sources_actual_get_post_handler_save_fresh(self):
        options=self.options();self.assertTrue(options["enabled"]);self.assertEqual(len(options["unit_pool"]["sources"]),16)
        self.assertLessEqual(len(json.dumps(options,ensure_ascii=True).encode()),65536)
        task,asset=self.pool();fresh=self.fresh_service().table_store
        delivered=fresh.read_asset(asset)
        self.assertEqual(len(delivered["value"]["rows"]),16)
        group=fresh.verified_package(task["table_store_run_id"])[1]["unit_contract"]["group_source_set"]
        self.assertEqual(len(group["sources"]),16);self.assertEqual(len(group["scope"]["conversation_ids"]),16)
        self.assertEqual({m["current"]["input_hash"] for m in group["sources"]},{self.archive_stamp(self.find_item(cid)) for cid in self.runs})

    def test_pool_parent_reference_closed_scope_and_real_task_ledger_fence(self):
        task,asset=self.pool();saved=self.store.verified_package(task["table_store_run_id"])
        provenance=saved[1]["parameters"]["table_pilot_provenance"]
        self.assertEqual(provenance["version"],"connected-provenance-3")
        self.assertNotIn("parents",provenance);self.assertNotIn("payload_refs",provenance["receipt"])
        self.assertEqual(provenance["receipt"],task["table_pilot_prepared"]["receipt"])
        self.assertEqual(provenance["unit_contract"],saved[1]["unit_contract"])
        self.assertEqual(self.store._pool_provenance_parents(provenance),provenance["receipt"]["bindings"])
        for mutation in ("version","target","hash","domain","unknown","duplicate"):
            bad=copy.deepcopy(provenance)
            if mutation=="version":bad["version"]="connected-provenance-unknown"
            elif mutation=="target":bad["parents_ref"]["target"]="external.caller"
            elif mutation=="hash":bad["parents_ref"]["content_hash"]=fingerprint("foreign")
            elif mutation=="domain":bad["parents_ref"]["hash_domain"]="raw-bytes-v1"
            elif mutation=="unknown":bad["parents_ref"]["alias"]="receipt.bindings"
            else:
                bad["receipt"]["bindings"][1]=copy.deepcopy(bad["receipt"]["bindings"][0])
                bad["parents_ref"]["content_hash"]=fingerprint(bad["receipt"]["bindings"])
            with self.subTest(mutation=mutation),self.assertRaises((AssetBindingError,AnalysisContractError)):
                self.store._pool_provenance_parents(bad)
        self.fresh_service().table_store.read_asset(asset)
        original=copy.deepcopy(task);changed=copy.deepcopy(task)
        changed["table_pilot_prepared"]["receipt"]["bindings"][1]["checked_policy_revision"]+=1
        with self.connect() as db:
            count=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
            db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?",(canonical(changed).decode(),task["task_id"]))
        with self.assertRaises(AnalysisContractError) as failure:self.fresh_service().table_store.read_asset(asset)
        self.assertEqual(failure.exception.code,"connected_provenance_refs")
        original.pop("table_pilot_prepared")
        with self.connect() as db:db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?",(canonical(original).decode(),task["task_id"]))
        with self.assertRaises(AnalysisContractError):self.fresh_service().table_store.read_asset(asset)
        self.assertEqual(self.store.verified_package(task["table_store_run_id"])[3],saved[3])
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],count)

    def test_pool_parent_reference_true_carrier_limit_rejects_save(self):
        opts=self.options()["unit_pool"]
        request={**opts["request_template"],"source_ids":[s["option_id"] for s in opts["sources"]],"columns":opts["required_columns"]+["n"]}
        response=self.client.post(self.base+"/asset-plans",json=request);self.assertEqual(response.status_code,202,response.get_json())
        measured=[];actual=self.store.table_pilot_carrier
        def inspect(raw,prepared):
            carrier,provenance=actual(raw,prepared)
            measured.append(len(canonical({"carrier":carrier,"provenance":provenance})))
            self.assertEqual(provenance["version"],"connected-provenance-3")
            return carrier,provenance
        self.store.table_pilot_carrier=inspect
        with self.connect() as db:before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        self.service._drain_tasks(self.run["run_id"]);task=self.task(response.get_json()["tasks"]["P1"])
        self.assertTrue(measured);self.assertGreater(measured[0],TABLE_PILOT_MAX_BYTES)
        print("valid pool carrier+provenance bytes:",measured[0],"limit:",TABLE_PILOT_MAX_BYTES)
        self.assertEqual(task["status"],"quarantined",task);self.assertEqual(task["error"],"table_carrier_byte_limit")
        self.assertNotIn("table_store_run_id",task)
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)
            raw,meta=db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=?",(task["task_id"],)).fetchone()
        self.assertEqual(fingerprint(json.loads(raw)),json.loads(meta)["raw_hash"])
        self.assertEqual(len(json.loads(raw)["unit_contract"]["source_utterances"]),47)

    def test_real_missing_unknown_unprocessed_excluded_denominators(self):
        pool,asset=self.pool();self.adopt(asset)
        pooled=self.store.verified_package(pool["table_store_run_id"])[1]
        self.assertEqual(sorted(r["value_status"] for r in pooled["datasets"]["table"]["rows"]),
            ["excluded","missing","observed","observed","unknown","unprocessed"])
        task,result=self.aggregate(asset,"mean",service=self.fresh_service())
        rows={r["participant_id"]:r for r in result["datasets"]["table"]["rows"]}
        self.assertEqual(set(rows),{"P1","P-null"});self.assertEqual(rows["P1"]["value"],2)
        self.assertIsNone(rows["P-null"]["value"]);self.assertEqual(rows["P-null"]["value_status"],"unprocessed")
        denominators=result["unit_contract"]["denominators"]
        self.assertEqual(denominators[rows["P1"]["unit_id"]],{"included":4,"observed":2,"missing":1,"unknown":1,"unprocessed":0,"excluded":1})
        self.assertEqual(denominators[rows["P-null"]["unit_id"]],{"included":1,"observed":0,"missing":0,"unknown":0,"unprocessed":1,"excluded":0})
        self.assertEqual(len(result["unit_contract"]["source_utterances"]),6)

    def test_mapping_correction_invalidates_only_descendant_and_keeps_raw_bytes(self):
        independent,branch=self.projection();pool,asset=self.pool();self.adopt(asset)
        descendant,_result=self.aggregate(asset,"sum");old=self.store.connected_output_descriptor(descendant["table_store_run_id"])
        runs=[a["asset_key"]["store_run_id"] for a in self.native]+[independent["table_store_run_id"],pool["table_store_run_id"],descendant["table_store_run_id"]]
        before={rid:self.store.verified_package(rid)[3] for rid in runs}
        key=hashlib.sha256(canonical(branch["asset_key"])).hexdigest()
        histories=self.store._connection_index()[2]
        # Compare actual immutable branch policy history, independent of pool HC.
        branch_history=copy.deepcopy(histories[key])
        option=next(o for o in self.human_options() if o["asset_key"]==asset["asset_key"])
        assignments=[{**s,"participant_id":("P-silent" if s["speaker_id"]=="silent" else "P1" if s["conversation_id"]=="C1" else "P2")} for s in option["speakers"]]
        response=self.client.post(self.base+"/human-records",data=canonical(self.mapping_payload(option,assignments)),content_type="application/json")
        self.assertEqual(response.status_code,201,response.get_json());self.assertEqual(response.get_json()["record"]["revision"],2)
        with self.assertRaises(AssetBindingError):self.fresh_service().table_store.read_asset(old)
        self.assertEqual(self.store._connection_index()[2][key],branch_history)
        for rid,content in before.items():self.assertEqual(self.store.verified_package(rid)[3],content)

    def test_real_get_post_handler_human_save_and_fresh_numeric_consumer(self):
        before={a["asset_key"]["store_run_id"]:self.store.verified_package(a["asset_key"]["store_run_id"])[3] for a in self.native}
        with self.connect() as db: counts=tuple(db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ("analysis_runs","orchestration_tasks"))
        self.options();self.options()
        with self.connect() as db:self.assertEqual(counts,tuple(db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in ("analysis_runs","orchestration_tasks")))
        pool,asset=self.pool();adopted=self.adopt(asset)
        contract=self.store.verified_package(pool["table_store_run_id"])[1]["unit_contract"]
        for member in contract["group_source_set"]["sources"]:
            self.assertEqual(member["current"]["input_hash"],self.archive_stamp(self.find_item(member["conversation_id"])))
            self.assertEqual(member["qualified_input_hash"],"sha256:"+member["current"]["input_hash"])
            self.assertEqual(member["snapshot_content_hash"],member["original_ref"]["content_hash"])
            self.assertNotEqual(member["snapshot_content_hash"],member["qualified_input_hash"])
            self.assertEqual(len({v["source_unit_id"] for v in member["original_units"].values()}),len(member["original_units"]))
        fresh=self.fresh_service()
        for operation,expected in (("sum",6),("mean",2),("count",3)):
            task,result=self.aggregate(asset,operation,service=fresh)
            rows=result["datasets"]["table"]["rows"];self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["value"],expected);self.assertEqual(rows[0]["participant_id"],"P1")
            self.assertEqual(next(iter(result["unit_contract"]["denominators"].values()))["observed"],3)
            self.assertEqual(len(result["unit_contract"]["source_utterances"]),3)
            self.assertIn(adopted["record_ref"],result["unit_contract"]["definition_adoption_refs"])
            self.assertEqual(result["unit_contract"]["group_source_set"]["scope"]["conversation_ids"],["C1","C2"])
        for rid,content in before.items():self.assertEqual(self.store.verified_package(rid)[3],content)

    def test_nonprimary_deleted_source_blocks_reuse_without_saves(self):
        pool,asset=self.pool();self.adopt(asset)
        with self.connect() as db:
            count=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
            db.execute("DELETE FROM library_items WHERE id='C2'")
        fresh=self.fresh_service()
        with self.assertRaises(AssetBindingError):fresh.table_store.read_asset(asset)
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],count)

    def test_nonprimary_original_policy_revoked_blocks_fresh_no_payload_or_save(self):
        task,asset=self.pool();bindings=task["table_pilot_prepared"]["request"]["bindings"]
        _assets,originals,states,_links=self.store._connection_index()
        original=next(o for o in originals.values() if o["scope"]["conversation_ids"]==["C2"])
        key=hashlib.sha256(canonical(original["asset_key"])).hexdigest();state=copy.deepcopy(states[key][max(states[key])])
        state.update(state_revision=state["state_revision"]+1,policy_revision=state["policy_revision"]+1,revoked=True)
        self.store.save_connection_metadata(item_id="C2",snapshot={},request_id="TEST-revoke-nonprimary-parent",
            metadata={"version":1,"assets":[],"originals":[],"states":[state],"producer_links":[]})
        with self.connect() as db:before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        fresh=self.fresh_service().table_store
        receipt=fresh.bind_asset_inputs(method_id="unit_pool",**bindings)
        self.assertNotEqual(receipt["decision"],"eligible");self.assertEqual(receipt["payloads"],[])
        with self.assertRaises(AssetBindingError):fresh.read_asset(asset)
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)

    def test_duplicate_source_and_untrusted_group_scope_rejected(self):
        opts=self.options()["unit_pool"];sid=opts["sources"][0]["option_id"]
        request={**opts["request_template"],"source_ids":[sid,sid],"columns":opts["required_columns"]+["n"]}
        self.assertEqual(self.client.post(self.base+"/asset-plans",json=request).status_code,409)
        request["source_ids"]=[s["option_id"] for s in opts["sources"]];request["scope"]={"caller":"not authoritative"}
        self.assertEqual(self.client.post(self.base+"/asset-plans",json=request).status_code,409)
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_tasks").fetchone()[0],0)

    def test_nonprimary_revision_changed_between_run_and_save_keeps_raw_and_no_save(self):
        opts=self.options()["unit_pool"]
        request={**opts["request_template"],"source_ids":[s["option_id"] for s in opts["sources"]],"columns":opts["required_columns"]+["n"]}
        response=self.client.post(self.base+"/asset-plans",json=request);self.assertEqual(response.status_code,202,response.get_json())
        tid=response.get_json()["tasks"]["P1"]
        with self.connect() as db:before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        def changed(method,snapshot):
            result=run_orchestration_method(method,snapshot)
            with self.connect() as db:db.execute("UPDATE library_items SET analysis_revision=2 WHERE id='C2'")
            return result
        self.service.method_runner=changed;self.service._drain_tasks(self.run["run_id"])
        task=self.task(tid);self.assertEqual(task["status"],"quarantined",task)
        self.assertNotIn("table_store_run_id",task)
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)
            raw,meta=db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=?",(tid,)).fetchone()
        self.assertEqual(fingerprint(json.loads(raw)),json.loads(meta)["raw_hash"])

    def test_nonprimary_changed_before_execute_never_delivers_or_calls_method(self):
        opts=self.options()["unit_pool"]
        request={**opts["request_template"],"source_ids":[s["option_id"] for s in opts["sources"]],"columns":opts["required_columns"]+["n"]}
        response=self.client.post(self.base+"/asset-plans",json=request);self.assertEqual(response.status_code,202,response.get_json())
        with self.connect() as db:
            before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
            db.execute("UPDATE library_items SET analysis_revision=2 WHERE id='C2'")
        def forbidden(*_args):raise AssertionError("Stale nonprimary source reached calculation")
        self.service.method_runner=forbidden;self.service._drain_tasks(self.run["run_id"])
        task=self.task(response.get_json()["tasks"]["P1"])
        self.assertEqual(task["status"],"failed",task);self.assertNotIn("table_pilot_prepared",task)
        self.assertNotIn("table_store_run_id",task)
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_results").fetchone()[0],0)

    def test_nonprimary_original_bytes_tampered_rejected_without_payload_or_save(self):
        task,_asset=self.pool();bindings=task["table_pilot_prepared"]["request"]["bindings"]
        source=next(a for a in self.native if a["scope"]["conversation_ids"]==["C2"])
        _fixed,_result,manifest,_content=self.store.verified_package(source["asset_key"]["store_run_id"])
        artifact=next(a for a in manifest["artifacts"] if a["name"]=="input.json")
        path=safe_path(self.store.root,artifact["path"]);path.write_bytes(path.read_bytes()+b" ")
        with self.connect() as db:before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        receipt=self.fresh_service().table_store.bind_asset_inputs(method_id="unit_pool",**bindings)
        self.assertNotEqual(receipt["decision"],"eligible");self.assertEqual(receipt["payloads"],[])
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)

    def test_partial_saved_source_is_not_offered_and_join_post_is_rejected(self):
        fixed=self.store.verified_package(self.native[0]["asset_key"]["store_run_id"])[0]
        saved=self.store.save(item_id="C1",kind="ai_insights",snapshot=fixed,result={"synthetic_import":True},
            datasets={"correlations":(["utterance_id","conversation_id","value_status","n"],
                [{"utterance_id":"0","conversation_id":"C1","value_status":"observed","n":0}])},
            request_id="TEST-partial-native",input_fingerprint=fixed["input_hash"],source_revision=1,analysis_revision=1,publish=False)
        partial=self.register_native(saved,include_original=False);options=self.options()
        self.assertFalse(any(o["source"]["asset_key"]==partial["asset_key"] for o in options["unit_pool"]["sources"]))
        source={"type":"frozen","asset_key":partial["asset_key"],"content_hash":partial["content_hash"],"content_domain":partial["content_domain"]}
        complete=next(o for o in options["inputs"] if o["source"].get("asset_key")==self.native[0]["asset_key"])
        plan={**options["plan_template"],"steps":[{"step_id":"J1","method_id":"unit_join","parameters":{"keys":["unit_id","conversation_id"]},
            "scope":{k:complete["scope"][k] for k in ("scope_id","manifest_hash")},"inputs":[
                {"input_ref_id":"TEST-complete","role":"data_input","selection":"selected","omission_reason":None,"source":complete["source"]},
                {"input_ref_id":"TEST-partial","role":"data_input","selection":"selected","omission_reason":None,"source":source}]}]}
        with self.connect() as db:before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        response=self.client.post(self.base+"/asset-plans",json=plan);self.assertEqual(response.status_code,400,response.get_json())
        self.assertEqual(response.get_json()["reason_code"],"asset_plan_input_unavailable")
        with self.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_tasks").fetchone()[0],0)

    def test_wrong_content_foreign_scope_and_tampered_adapter_block_without_payload(self):
        task,asset=self.pool()
        request=task["table_pilot_prepared"]["request"];self.assertEqual(request["version"],"connected-assets-2")
        with self.connect() as db:before=db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
        for mutation in ("hash","foreign","scope","duplicate"):
            bad=copy.deepcopy(request["bindings"])
            if mutation=="hash":bad["inputs"][0]["source"]["content_hash"]=fingerprint("wrong bytes")
            elif mutation=="foreign":bad["inputs"][0]["source"]["asset_key"]["library_id"]="foreign-library"
            elif mutation=="scope":bad["context"]["scope_manifest_hash"]=fingerprint("caller hash")
            else:bad["inputs"][1]["source"]=copy.deepcopy(bad["inputs"][0]["source"])
            with self.subTest(mutation=mutation):
                result=self.store.bind_asset_inputs(method_id="unit_pool",**bad)
                self.assertNotEqual(result["decision"],"eligible");self.assertEqual(result["payloads"],[])
        group=self.store.verified_package(task["table_store_run_id"])[1]["unit_contract"]["group_source_set"]
        for mutation in ("utterance","revision","input_hash","source_scope","original_version"):
            forged=copy.deepcopy(group);first=forged["sources"][0]
            if mutation=="utterance":first["original_units"][next(iter(first["original_units"]))]["utterance_id"]="foreign"
            elif mutation=="revision":first["current"]["source_revision"]+=1
            elif mutation=="input_hash":first["current"]["input_hash"]="0"*64
            elif mutation=="source_scope":first["source_scope"]["conversation_ids"]=["foreign"]
            else:first["original_ref"]["version"]="2"
            with self.subTest(group_mutation=mutation),self.assertRaises(AssetBindingError):self.store._verify_group(forged)
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0],before)

    def test_mapping_missing_duplicate_many_to_many_and_single_scope_rejected(self):
        task,asset=self.pool();option=next(o for o in self.human_options() if o["asset_key"]==asset["asset_key"])
        good=[{**s,"participant_id":"P-silent" if s["speaker_id"]=="silent" else "P1"} for s in option["speakers"]]
        for rows in (good[:1],good+good[:1],[{**s,"participant_id":"P1"} for s in good]):
            response=self.client.post(self.base+"/human-records",data=canonical(self.mapping_payload(option,rows)),content_type="application/json")
            self.assertEqual(response.status_code,409,response.get_json())
        bad=self.mapping_payload(option);bad["record"]["scope"]=copy.deepcopy(self.native[0]["scope"])
        self.assertEqual(self.client.post(self.base+"/human-records",data=canonical(bad),content_type="application/json").status_code,400)
        with self.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analysis_runs WHERE kind='human_record'").fetchone()[0],0)


if __name__=="__main__":unittest.main()
