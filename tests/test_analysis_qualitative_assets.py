"""Invented fixtures only: saved researcher requests and connected qualitative reuse."""
import copy
import hashlib
import json
import unittest
from flask import Flask
from gurumoji.analysis_core import canonical,fingerprint
from gurumoji.analysis_method_registry import connected_slot
from gurumoji.analysis_store import AnalysisStore
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_typed_assets as typed
import test_analysis_human_records as human
import test_analysis_table_units as units


class QualitativeAssetTests(unittest.TestCase):
    def setUp(self):
        self.t=typed.TypedHandlerIntegrationTests();self.t.setUp();self.addCleanup(self.t.doCleanups)
        segments=self.t.snapshot["segments"]
        segments.append({"id":"TEST-u2","text":"Invented minority retraction; not agreement","speaker":"TEST-B","excluded":False,"valid_time":False})
        segments.append({"id":"TEST-u3","text":"Invented moderator context","speaker":"TEST-M","excluded":True,"valid_time":False})
        self.t.snapshot["analysis"]["segments"]=copy.deepcopy(segments)
        self.t.snapshot["input_hash"]=fingerprint(segments)
        ta_service=self.t.service();ta_run=self.t.start(ta_service);ta_service.run(ta_run["run_id"])
        publisher=AnalysisOrchestrationPublicationService(connect=self.t.fixture.connect,store_factory=lambda:self.t.fixture.store,
            source_guard=lambda db,item,expected:{"id":item},export_locked=ta_service.result_locked)
        saved=publisher.finalize("TEST-conversation",ta_run["run_id"])
        self.store=AnalysisStore(self.t.fixture.path,self.t.fixture.connect)
        self.ta=self.store.thematic_asset_descriptors(saved["result_run_id"])["assets"][0]
        self.original=self.store.thematic_asset_descriptors(saved["result_run_id"])["original"]
        self.service=self.t.service();self.service.method_runner=run_orchestration_method
        self.service.agent_runner=lambda *_:self.fail("No model call in deterministic reuse")
        self.run=self.service.start("TEST-conversation",{"model":"TEST-no-model","max_tasks":50,"time_limit_seconds":None})
        app=Flask(__name__);register_orchestration_routes(app,lambda:self.service,lambda _:self.fail("No AI prepare"));self.client=app.test_client()
        h=human.HumanRecordTests();h.fixture=self.t.fixture;h.helper=self.t;h.asset=self.ta;h.original=self.original;h.service=self.service
        h.run_id=ta_run["run_id"];h.saved_id=saved["result_run_id"];h.candidate,h.steps,*_=self.store._human_contract(self.ta)
        h.client=self.client;h.url=f'/api/library/TEST-conversation/analysis/orchestration/{ta_run["run_id"]}/human-records'
        h.adopt();self.h=h
        with self.t.fixture.connect() as db:self.initial=self.service._initial(db,self.run["initial_id"])
        evidence={e["utterance_id"]:e for e in self.initial["evidence"]}
        graph_row={"relation":"retract","source_segment_id":"TEST-u2","target_segment_id":"TEST-u1",
            "context_segment_ids":["TEST-u3"],"source_text":evidence["TEST-u2"]["text"],"target_text":evidence["TEST-u1"]["text"],
            "status":"recorded","evidence_memo":"TEST minority and retraction; no semantic agreement","valid_time":False,"start":None,"end":None}
        graph_saved=self.store.save(item_id="TEST-conversation",kind="ai_insights",snapshot=self.initial,
            result={"parameters":{},"TEST_fixture_only":True},datasets={"interaction_links":(list(graph_row),[graph_row])},
            request_id="TEST-manual-graph",input_fingerprint=fingerprint(self.initial),source_revision=1,analysis_revision=1,publish=False)
        self.graph=self.store.manual_relation_descriptors(graph_saved["id"])["assets"][0]
        response=self.post_record(self.graph,"manual-interaction-review");self.assertEqual(response.status_code,201,response.get_json())

    def post_record(self,asset,step,decision="adopt",revision=1,previous=None):
        source=f"TEST ONLY explicit researcher {step}/{decision}/{revision}"
        candidate,*_=self.store._human_contract(asset,execution_run_id=self.run["run_id"])
        record_id="TEST-human-"+asset["asset_key"]["artifact_id"]+"-"+step
        record={"record_id":record_id,"revision":revision,"supersedes_record_ref":None,
            "actor":{"kind":"researcher","actor_id":"TEST-human"},"decision":decision,"target":candidate["_human_target"],
            "allowed_step_ids":[step],"scope":asset["scope"],"recorded_at":"2026-10-08T19:00:00Z","reason":"TEST explicit judgment; not actual adoption",
            "record_ref":{"target_type":"researcher_memo","target_id":"human-source:"+record_id,"version":str(revision),
                "content_hash":"sha256:"+hashlib.sha256(source.encode()).hexdigest(),"hash_domain":"raw-bytes-v1","library_id":"TEST-library"}}
        if previous:record["supersedes_record_ref"]={"domain":"human-record-v1","record_id":record_id,"revision":revision-1,"content_hash":previous["record_ref"]["content_hash"]}
        histories=self.store._connection_index()[2].get(typed.digest(asset["asset_key"]),{})
        payload={"asset_key":asset["asset_key"],"record":record,"source_text":source,"expected_state_revision":max(histories) if histories else 0}
        return self.client.post(f'/api/library/TEST-conversation/analysis/orchestration/{self.run["run_id"]}/human-records',data=canonical(payload),content_type="application/json")

    def ref(self,name,asset=None,*,step=None,role="data_input",original=False,omitted=False):
        ref={"input_ref_id":name,"role":role,"selection":"omitted" if omitted else "selected","omission_reason":"Explicit TEST omission" if omitted else None}
        if omitted:return ref
        if step:ref["source"]={"type":"from_step","step_id":step,"output_name":"tables/table.json"}
        elif original:ref["source"]={"type":"original","source_ref":asset["source_ref"]}
        else:ref["source"]={"type":"frozen","asset_key":asset["asset_key"],"content_hash":asset["content_hash"],"content_domain":asset["content_domain"]}
        return ref

    def test_A1_F1_X1_Q1_I1_B1_A2_then_consumer_real_scheduler_saved_bytes(self):
        scope={k:self.ta["scope"][k] for k in ("scope_id","manifest_hash")}
        graph_scope={k:self.graph["scope"][k] for k in ("scope_id","manifest_hash")}
        def step(sid,method,params,refs,own_scope=None):return {"step_id":sid,"method_id":method,"parameters":params,"inputs":refs,"scope":own_scope or scope}
        plan={"version":"asset-plan-1","plan_id":"TEST-qual-plan","plan_version":1,"steps":[
            step("A1","theme_evidence_table",{"theme_id":"TEST-theme"},[self.ref("claim",self.ta)]),
            step("F1","unit_aggregate",{"value_column":"support_count","operation":"count","unit":"conversation","participant_mapping":None},[self.ref("a1",step="A1")]),
            step("X1","unit_aggregate",{"value_column":"support_count","operation":"sum","unit":"conversation","participant_mapping":None},[self.ref("a1",step="A1")]),
            step("Q1","qualitative_compare",{"proposals":[]},[self.ref("claim",self.ta),self.ref("original",self.original,role="evidence_context",original=True)]),
            step("I1","qualitative_compare",{"proposals":[]},[self.ref("graph",self.graph),self.ref("original",self.original,role="evidence_context",original=True)],graph_scope),
            step("B1","qualitative_compare",{"proposals":[]},[self.ref("f1",step="F1"),self.ref("x1",step="X1"),self.ref("q1",step="Q1",role="evidence_context"),
                self.ref("i1",step="I1"),self.ref("T1",omitted=True,role="evidence_context")]),
            step("A2","qualitative_reuse",{"relation_ids":["comparison-0001"]},[self.ref("b1",step="B1",role="selection_basis"),
                self.ref("q1",step="Q1",role="evidence_context"),self.ref("original",self.original,role="evidence_context",original=True)]),
            step("C2","qualitative_compare",{"proposals":[]},[self.ref("a2",step="A2"),self.ref("original",self.original,role="evidence_context",original=True)])]}
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],plan)
        self.service._drain_tasks(self.run["run_id"])
        with self.t.fixture.connect() as db:tasks={t["asset_step_id"]:t for t in self.service._tasks(db,self.run["run_id"])}
        self.assertTrue(all(t["status"]=="succeeded" for t in tasks.values()),[(s,t["status"],t.get("error"),t.get("asset_delivery_error")) for s,t in tasks.items()])
        fresh=AnalysisStore(self.t.fixture.path,self.t.fixture.connect)
        a2=fresh.connected_output_descriptor(tasks["A2"]["table_store_run_id"])
        bundle=json.loads(fresh.read_asset(a2)["value"]["rows"][0]["values"]["bundle_json"])
        self.assertEqual(bundle["stage"],"A2_rereading");self.assertFalse(bundle["independent_validation"])
        self.assertEqual(bundle["human_status"],"human_pending")
        self.assertEqual(len(bundle["relations"]),1)
        self.assertTrue(any(p["kind"]=="relation_graph" for p in bundle["evidence_packets"].values()))
        self.assertTrue(any(p["kind"]=="claim_set" and "coverage" in p["payload"] for p in bundle["evidence_packets"].values()))
        b1=fresh.connected_output_descriptor(tasks["B1"]["table_store_run_id"])
        before=fresh.verified_package(a2["asset_key"]["store_run_id"])[3]
        first=self.post_record(b1,"qualitative-interpretation-review");self.assertEqual(first.status_code,201,first.get_json())
        corrected=self.post_record(b1,"qualitative-interpretation-review","defer",2,first.get_json());self.assertEqual(corrected.status_code,201,corrected.get_json())
        self.assertIn(a2["asset_key"],corrected.get_json()["stale_assets"])
        independent=fresh.connected_output_descriptor(tasks["I1"]["table_store_run_id"])
        self.assertNotIn(independent["asset_key"],corrected.get_json()["stale_assets"])
        self.assertEqual(fresh.verified_package(a2["asset_key"]["store_run_id"])[3],before)

    def test_fixed_manual_proposals_support_counter_complement_conflict_incomparable(self):
        request=units.request_for(self.run,self.ta,"qualitative_compare",{"proposals":[]})
        context=request["bindings"]["context"]
        base=request["bindings"]["inputs"][0]
        request["bindings"]["inputs"].append({**copy.deepcopy(base),"input_ref_id":"graph","source":self.ref("graph",self.graph)["source"]})
        prepared=self.store.prepare_connected("qualitative_compare",request,expected_snapshot=self.initial)
        left=prepared["tables"][0]["inputs"][0]["targets"][1]
        right=prepared["tables"][0]["inputs"][1]["targets"][1]
        actor={"kind":"ai","actor_id":"TEST-proposal","step_ids":[],"model_id":"TEST-none","revision":"unverified","provider":"TEST-no-call"}
        request["parameters"]["proposals"]=[{"relation_id":r,"left":left,"right":right,"relation":r,"reason":"TEST explicit alternative reasoning "+r,"actor":actor}
            for r in ("support","counter","complement","conflict","incomparable")]
        task=self.service.register_table_pilot("TEST-conversation",self.run["run_id"],"qualitative_compare",request)
        self.service._execute(self.run["run_id"],task["task_id"])
        with self.t.fixture.connect() as db:state=json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(task["task_id"],)).fetchone()[0])
        self.assertEqual(state["status"],"succeeded",state.get("error"))
        fresh=AnalysisStore(self.t.fixture.path,self.t.fixture.connect);asset=fresh.connected_output_descriptor(state["table_store_run_id"])
        value=json.loads(fresh.read_asset(asset)["value"]["rows"][0]["values"]["bundle_json"])
        self.assertEqual([r["relation"] for r in value["relations"]],["support","counter","complement","conflict","incomparable"])
        self.assertTrue(all(r["semantic_status"]=="human_pending" for r in value["relations"]))
        graph=value["evidence_packets"][value["inputs"][1]["payload"]["evidence_packet_id"]]["payload"]["rows"][0]["values"]
        self.assertEqual(graph["relation"],"retract");self.assertEqual(graph["context_segment_ids"],["TEST-u3"])
        self.assertIsNone(graph["start"]);self.assertFalse(graph["valid_time"])
        request["parameters"]["proposals"][0]["left"]["content_hash"]=fingerprint("wrong")
        bad=self.store.prepare_connected("qualitative_compare",request,expected_snapshot=self.initial)
        with self.assertRaises(ValueError):
            from gurumoji.services.group_analysis import run_qualitative_asset_method
            run_qualitative_asset_method("qualitative_compare",bad["tables"][0],request["parameters"],{"task_id":"TEST-invalid"})
        rejected=self.service.register_table_pilot("TEST-conversation",self.run["run_id"],"qualitative_compare",request)
        self.service._execute(self.run["run_id"],rejected["task_id"])
        with self.t.fixture.connect() as db:
            state=json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(rejected["task_id"],)).fetchone()[0])
        self.assertEqual(state["status"],"failed");self.assertEqual(state["error"],"qualitative_target")
        unmapped=copy.deepcopy(request);unmapped["bindings"]["context"]["scope_manifest_hash"]=fingerprint("unmapped scope")
        with self.assertRaises(ValueError):self.store.prepare_connected("qualitative_compare",unmapped,expected_snapshot=self.initial)


if __name__=="__main__":unittest.main()
