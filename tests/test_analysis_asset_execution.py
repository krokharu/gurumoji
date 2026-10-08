"""No network: real persisted Handler DAG, immutable Store and restart delivery."""
import copy
import json
import threading
import unittest
from flask import Flask
from gurumoji.analysis_core import fingerprint,validate_asset_plan
from gurumoji.analysis_orchestration import AnalysisOrchestrationService,recover_orchestration_runs
from gurumoji.analysis_store import AnalysisStore
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_asset_bindings as bindings


class AssetExecutionTests(unittest.TestCase):
    def setUp(self):
        self.h=bindings.TablePilotHandlerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.service=self.h.service;self.run=self.h.run;self.fixture=self.h.f
        self.calls=[]
        def runner(method,snapshot):
            self.calls.append(snapshot["orchestration_task"]["task_id"])
            return run_orchestration_method(method,snapshot)
        self.service.method_runner=runner
        self.runner=runner
        app=Flask(__name__);register_orchestration_routes(app,lambda:self.service,lambda _:self.fail("No AI preparation"))
        self.client=app.test_client();self.url=f'/api/library/TEST-conversation/analysis/orchestration/{self.run["run_id"]}/asset-plans'

    def plan(self):
        asset=self.h.asset
        frozen={"type":"frozen","asset_key":asset["asset_key"],"content_hash":asset["content_hash"],"content_domain":asset["content_domain"]}
        scope={k:asset["scope"][k] for k in ("scope_id","manifest_hash")}
        ids=["utterance:"+fingerprint(["TEST-library","TEST-conversation",self.run["input_hash"],f"TEST-u{i}"]).removeprefix("sha256:") for i in range(6)]
        def ref(source):return {"input_ref_id":"TEST-ref","role":"data_input","selection":"selected","omission_reason":None,"source":source}
        projection={"columns":["unit_id","conversation_id","speaker_id","value_status","n"],"unit_ids":ids}
        return {"version":"asset-plan-1","plan_id":"TEST-plan","plan_version":1,"steps":[
            {"step_id":"A1","method_id":"unit_projection","parameters":projection,"scope":scope,"inputs":[ref(frozen)]},
            {"step_id":"F1","method_id":"unit_aggregate","parameters":{"value_column":"n","operation":"sum","unit":"conversation","participant_mapping":None},"scope":scope,
                "inputs":[ref({"type":"from_step","step_id":"A1","output_name":"tables/table.json"})]},
            {"step_id":"Q1","method_id":"unit_projection","parameters":projection,"scope":scope,"inputs":[ref(frozen)]}]}

    def tasks(self):
        with self.fixture.connect() as db:return self.service._tasks(db,self.run["run_id"])

    def statuses(self):return [(t.get("asset_step_id"),t["status"],t.get("error"),t.get("asset_delivery_error")) for t in self.tasks()]

    def fresh_service(self):
        return AnalysisOrchestrationService(connect=self.fixture.connect,find_item=lambda _:self.h.item,
            snapshot_builder=lambda _:copy.deepcopy(self.fixture.snapshot),method_runner=self.runner,
            agent_runner=lambda *_:self.fail("No AI calls"),schedule=False,table_store=AnalysisStore(self.fixture.path,self.fixture.connect))

    def test_api_dag_fresh_bind_duplicate_receipts_and_once_execution(self):
        response=self.client.post(self.url,json=self.plan());self.assertEqual(response.status_code,202,response.get_json())
        outcome=response.get_json();ids=outcome["tasks"]
        self.service._execute(self.run["run_id"],ids["F1"])
        self.assertEqual(self.calls,[])
        self.service._drain_tasks(self.run["run_id"])
        self.assertTrue(all(t["status"]=="succeeded" for t in self.tasks()),self.statuses())
        self.assertEqual(len(self.calls),3);self.assertEqual(len(set(self.calls)),3)
        fresh=self.fresh_service();fresh.reconcile_asset_plan(self.run["run_id"])
        duplicate=fresh.notify_asset_output("TEST-conversation",self.run["run_id"],ids["A1"])
        self.assertTrue(duplicate["duplicate"]);self.assertEqual(len(self.calls),3)
        child=next(t for t in self.tasks() if t["task_id"]==ids["F1"])
        self.assertEqual(len(child["asset_receipts"]),1)
        self.assertEqual(child["dependencies"],[ids["A1"]])
        receipt=next(iter(child["asset_receipts"].values()))["identity"]
        self.assertEqual((receipt["slot_id"],receipt["input_ref_id"]),("table","TEST-ref"))
        self.assertEqual(self.client.post(self.url,json=self.plan()).status_code,200)
        self.assertEqual(len(self.tasks()),3)

    def test_lost_notification_reconciles_from_fresh_persisted_packages(self):
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan());ids=outcome["tasks"]
        original=self.service.notify_asset_output
        self.service.notify_asset_output=lambda *_:{"receipts":[]}
        self.service._execute(self.run["run_id"],ids["A1"])
        child=next(t for t in self.tasks() if t["task_id"]==ids["F1"]);self.assertNotIn("asset_receipts",child)
        self.service._execute(self.run["run_id"],ids["F1"])
        self.assertEqual(next(t for t in self.tasks() if t["task_id"]==ids["F1"])["status"],"queued")
        self.assertEqual(len(self.calls),1)
        self.service.notify_asset_output=original
        fresh=self.fresh_service();fresh.reconcile_asset_plan(self.run["run_id"]);fresh._drain_tasks(self.run["run_id"])
        self.assertEqual(len(self.calls),3);self.assertEqual(len(set(self.calls)),3)
        self.assertTrue(all(t["status"]=="succeeded" for t in self.tasks()),self.statuses())

    def test_startup_recovery_keeps_verified_code_children_and_receipts(self):
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan());ids=outcome["tasks"]
        self.service._execute(self.run["run_id"],ids["A1"])
        with self.fixture.connect() as db:recover_orchestration_runs(db)
        fresh=self.fresh_service();resumed=fresh.resume("TEST-conversation",self.run["run_id"])
        self.assertEqual(resumed["generation"],self.run["generation"])
        fresh._drain_tasks(self.run["run_id"])
        self.assertEqual(len(self.tasks()),3);self.assertEqual(len(self.calls),3)
        self.assertEqual(len(set(self.calls)),3);self.assertTrue(all(t["status"]=="succeeded" for t in self.tasks()),self.statuses())

    def test_mixed_ai_resume_generation_blocks_old_plan_before_code_or_save(self):
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan())
        with self.service._db() as db:
            run=self.service._read_run(db,self.run["run_id"])
            self.service._register(db,run,{"role":"core","question":"TEST synthetic queued Core; no call"},phase="core",automatic=True)
        resumed=self.service.resume("TEST-conversation",self.run["run_id"])
        self.assertEqual(resumed["generation"],2)
        self.service._execute(self.run["run_id"],outcome["tasks"]["A1"])
        task=next(t for t in self.tasks() if t["task_id"]==outcome["tasks"]["A1"])
        self.assertEqual(task["status"],"blocked");self.assertEqual(task["generation"],1)
        self.assertEqual(task["error"],"asset_plan_changed");self.assertEqual(self.calls,[])
        self.assertNotIn("table_store_run_id",task)

    def test_natural_completed_scheduler_output_reused_by_fresh_new_run(self):
        import test_analysis_orchestration as ai
        from test_analysis_table_units import request_for
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan())
        self.service.agent_runner=lambda role,context,*args:ai.stop() if role=="core" else ai.critic(context)
        self.service.run(self.run["run_id"])
        completed=self.service.status("TEST-conversation",self.run["run_id"])
        self.assertEqual(completed["status"],"completed",completed["stop_reason"])
        self.assertEqual(completed["generation"],self.run["generation"])
        producer=next(t for t in self.tasks() if t["task_id"]==outcome["tasks"]["A1"])
        fresh=self.fresh_service();asset=fresh.table_store.connected_output_descriptor(producer["table_store_run_id"])
        before=fresh.table_store.verified_package(producer["table_store_run_id"])[3]
        new=fresh.start("TEST-conversation",{"model":"TEST-no-model","time_limit_seconds":None,"max_tasks":50})
        request=request_for(new,asset,"unit_aggregate",{"value_column":"n","operation":"mean","unit":"conversation","participant_mapping":None})
        child=fresh.register_table_pilot("TEST-conversation",new["run_id"],"unit_aggregate",request)
        fresh._execute(new["run_id"],child["task_id"])
        with self.fixture.connect() as db:
            state=json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(child["task_id"],)).fetchone()[0])
        self.assertEqual(state["status"],"succeeded",state.get("error"))
        value=AnalysisStore(self.fixture.path,self.fixture.connect).verified_package(state["table_store_run_id"])[1]
        self.assertEqual(value["datasets"]["table"]["rows"][0]["value"],1)
        self.assertEqual(fresh.table_store.verified_package(producer["table_store_run_id"])[3],before)

    def test_branch_failure_preserves_independent_branch_and_raw(self):
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan());ids=outcome["tasks"]
        def runner(method,snapshot):
            if snapshot["orchestration_task"]["asset_step_id"]=="A1":raise ValueError("TEST branch failure")
            return self.runner(method,snapshot)
        self.service.method_runner=runner;self.service._drain_tasks(self.run["run_id"])
        tasks={t["asset_step_id"]:t for t in self.tasks()}
        self.assertEqual(tasks["A1"]["status"],"failed");self.assertEqual(tasks["F1"]["status"],"blocked")
        self.assertEqual(tasks["Q1"]["status"],"succeeded")

    def test_selected_delayed_T1_waits_while_other_branch_finishes_once(self):
        plan=self.plan();later=copy.deepcopy(plan["steps"][2]);later["step_id"]="T1";plan["steps"].append(later)
        refs=[{"input_ref_id":sid,"role":"data_input","selection":"selected","omission_reason":None,
            "source":{"type":"from_step","step_id":sid,"output_name":"tables/table.json"}} for sid in ("Q1","T1")]
        plan["steps"].append({"step_id":"B1","method_id":"qualitative_compare","parameters":{"proposals":[]},
            "scope":plan["steps"][0]["scope"],"inputs":refs})
        outcome=self.service.register_asset_plan("TEST-conversation",self.run["run_id"],plan)
        entered=threading.Event();release=threading.Event();errors=[]
        def runner(method,snapshot):
            if snapshot["orchestration_task"]["asset_step_id"]=="T1":
                entered.set();self.assertTrue(release.wait(15),"Synthetic T1 gate timed out")
            return self.runner(method,snapshot)
        self.service.method_runner=runner
        def drain():
            try:self.service._drain_tasks(self.run["run_id"])
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=drain);worker.start()
        try:
            self.assertTrue(entered.wait(15))
            self.assertEqual(next(t for t in self.tasks() if t["asset_step_id"]=="B1")["status"],"queued")
        finally:release.set();worker.join(60)
        self.assertFalse(worker.is_alive());self.assertEqual(errors,[])
        self.assertTrue(all(t["status"]=="succeeded" for t in self.tasks()),self.statuses())
        self.assertEqual(len(self.calls),5);self.assertEqual(len(set(self.calls)),5)

    def test_cycle_wrong_output_and_plan_hash_conflict_rejected_before_tasks(self):
        plan=self.plan();plan["steps"][0]["inputs"][0]["source"]={"type":"from_step","step_id":"F1","output_name":"tables/table.json"}
        with self.assertRaises(ValueError):validate_asset_plan(plan)
        self.assertEqual(self.tasks(),[])
        bad=self.plan();bad["steps"][1]["inputs"][0]["source"]["output_name"]="arbitrary.py"
        self.assertEqual(self.client.post(self.url,json=bad).status_code,400)
        self.assertEqual(self.tasks(),[])
        self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan())
        changed=self.plan();changed["steps"][1]["parameters"]["operation"]="mean"
        self.assertEqual(self.client.post(self.url,json=changed).status_code,409)

    def test_revoke_only_lineage_stale_old_packages_unchanged(self):
        self.service.register_asset_plan("TEST-conversation",self.run["run_id"],self.plan());self.service._drain_tasks(self.run["run_id"])
        tasks={t["asset_step_id"]:t for t in self.tasks()};store=AnalysisStore(self.fixture.path,self.fixture.connect)
        before={s:store.verified_package(t["table_store_run_id"])[3] for s,t in tasks.items()}
        asset=store.connected_output_descriptor(tasks["A1"]["table_store_run_id"])
        states=store._connection_index()[2][fingerprint(asset["asset_key"]).removeprefix("sha256:")];prior=states[max(states)]
        revoked={**copy.deepcopy(prior),"state_revision":prior["state_revision"]+1,"policy_revision":prior["policy_revision"]+1,"revoked":True,"reason":"TEST revoked"}
        store.save_connection_metadata(item_id="TEST-conversation",snapshot={},request_id="TEST-revoked",metadata={"version":1,"assets":[],"originals":[],"states":[revoked],"producer_links":[]})
        self.service.reconcile_asset_plan(self.run["run_id"])
        actual={t["asset_step_id"]:t for t in self.tasks()}
        self.assertTrue(actual["A1"]["stale"]);self.assertTrue(actual["F1"]["stale"]);self.assertFalse(actual["Q1"]["stale"])
        for sid,task in tasks.items():self.assertEqual(store.verified_package(task["table_store_run_id"])[3],before[sid])
        self.assertEqual(len(self.calls),3)


if __name__=="__main__":unittest.main()
