"""Synthetic unit contracts, actual Handler/Store and fresh immutable reads."""
import copy
import json
import unittest
from gurumoji.analysis_core import fingerprint
from gurumoji.analysis_method_registry import connected_slot
from gurumoji.analysis_store import AnalysisStore
from gurumoji.research_analysis import run_connected_table
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
import test_analysis_human_records as human
import test_analysis_asset_bindings as bindings


def request_for(run, asset, method, parameters):
    context={"plan_id":run["run_id"],"plan_version":1,"plan_hash":fingerprint({"run_id":run["run_id"],"input_hash":run["input_hash"]}),
        "generation":run["generation"],"consumer_task_id":"TEST-consumer","purpose":"exploratory","destination":"local",
        "scope_id":asset["scope"]["scope_id"],"scope_manifest_hash":asset["scope"]["manifest_hash"],"cancelled":False}
    selector={"row_ids":[],"column_ids":[],"range_ref":None}; selector["selection_hash"]=fingerprint(selector)
    ref={**{k:context[k] for k in ("plan_id","plan_version","plan_hash","generation","consumer_task_id")},
        "slot_id":"table","input_ref_id":"TEST-input","role":"data_input","selection":"selected","omission_reason":None,
        "source":{"type":"frozen","asset_key":asset["asset_key"],"content_hash":asset["content_hash"],"content_domain":asset["content_domain"]},"selector":selector}
    return {"version":"connected-assets-2","actor":"code","parameters":parameters,
        "bindings":{"slot":connected_slot(method),"inputs":[ref],"context":context}}


class ConnectedThemeTests(unittest.TestCase):
    def setUp(self):
        self.h=human.HumanRecordTests(); self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.h.adopt()
        self.service=self.h.helper.service(); self.service.method_runner=run_orchestration_method
        self.service.agent_runner=lambda *_:self.fail("No AI calls in deterministic steps")
        self.run=self.service.start("TEST-conversation",{"model":"TEST-no-model","max_tasks":50,"time_limit_seconds":None})
        self.store=AnalysisStore(self.h.fixture.path,self.h.fixture.connect)

    def execute(self,asset,method,parameters):
        task=self.service.register_table_pilot("TEST-conversation",self.run["run_id"],method,request_for(self.run,asset,method,parameters))
        self.service._execute(self.run["run_id"],task["task_id"])
        self.service._validate_received(self.run["run_id"],task["task_id"])
        with self.h.fixture.connect() as db:
            state=json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(task["task_id"],)).fetchone()[0])
        self.assertEqual(state["status"],"succeeded",state)
        return state,self.store.verified_package(state["table_store_run_id"])[1]

    def register(self,task):
        asset=self.store.connected_output_descriptor(task["table_store_run_id"])
        state=self.h.binding_helper.state(asset,"adopted")
        state["review_refs"]=[]
        self.h.fixture.register([asset],states=[state]); return asset

    def test_adopted_theme_real_handler_save_fresh_read_numeric_consumer(self):
        before=self.store.verified_package(self.h.saved_id)[3]
        task,raw=self.execute(self.h.asset,"theme_evidence_table",{"theme_id":"TEST-theme"})
        rows=raw["datasets"]["table"]["rows"]
        self.assertEqual(rows[0]["support_count"],1)
        self.assertEqual(rows[0]["counter_count"],0)
        self.assertTrue(raw["unit_contract"]["definition_adoption_refs"])
        self.assertEqual(raw["unit_contract"]["unit"],"utterance")
        asset=self.register(task)
        aggregate,result=self.execute(asset,"unit_aggregate",{"value_column":"support_count","operation":"sum","unit":"conversation_speaker","participant_mapping":None})
        self.assertEqual(result["datasets"]["table"]["rows"][0]["value"],1)
        self.assertEqual(self.store.read_asset(self.register(aggregate))["value"]["rows"][0]["values"]["value"],1)
        self.assertEqual(self.store.verified_package(self.h.saved_id)[3],before)


class UnitKernelTests(unittest.TestCase):
    def table(self):
        statuses=["observed","observed","missing","unprocessed","observed","unknown"]
        rows=[{"unit_id":f"TEST-u{i}","conversation_id":"C1" if i<4 else "C2","speaker_id":"S1",
            "value_status":s,"x":0 if i==0 else 2 if i==1 else 10 if i==4 else None} for i,s in enumerate(statuses)]
        return {"fields":list(rows[0]),"rows":rows,"unit":"utterance","input_hashes":[fingerprint("C1"),fingerprint("C2")],
            "sources":{r["unit_id"]:[r["unit_id"]] for r in rows},"definition_adoption_refs":[],"denominators":{},"scope":{"id":"TEST-scope"},
            "variables":[{"variable_id":k,"value_type":"integer" if k=="x" else "string","scale":"ratio" if k=="x" else "nominal","unit":"utterance"} for k in rows[0]]}

    def test_unequal_counts_null_zero_and_unprocessed_denominators(self):
        for operation,expected in (("count",[2,1]),("sum",[2,10]),("mean",[1,10])):
            result=run_connected_table("unit_aggregate",[self.table()],{"value_column":"x","operation":operation,"unit":"conversation_speaker","participant_mapping":None})
            self.assertEqual([r["value"] for r in result["rows"]],expected)
            self.assertEqual([d["included"] for d in result["unit_contract"]["denominators"].values()],[4,2])
            self.assertEqual([d["observed"] for d in result["unit_contract"]["denominators"].values()],[2,1])
        missing=self.table(); missing["rows"]=missing["rows"][2:4]
        result=run_connected_table("unit_aggregate",[missing],{"value_column":"x","operation":"count","unit":"conversation","participant_mapping":None})
        self.assertIsNone(result["rows"][0]["value"]); self.assertEqual(result["rows"][0]["value_status"],"unprocessed")

    def test_participant_mapping_and_known_roster_do_not_invent_speech(self):
        table=self.table(); reference={"TEST":"saved-human-ref"}; table["definition_adoption_refs"]=[reference]
        mapping={"actor":{"kind":"researcher","actor_id":"TEST-human"},"record_ref":reference,"assignments":[
            {"conversation_id":"C1","speaker_id":"S1","participant_id":"P1"},
            {"conversation_id":"C2","speaker_id":"S1","participant_id":"P1"},
            {"conversation_id":"C1","speaker_id":"silent","participant_id":"P2"}]}
        result=run_connected_table("unit_aggregate",[table],{"value_column":"x","operation":"mean","unit":"participant","participant_mapping":mapping})
        self.assertEqual(len(result["rows"]),1); self.assertEqual(result["rows"][0]["value"],4)
        self.assertEqual(result["rows"][0]["participant_id"],"P1")
        for bad in (None,{**mapping,"assignments":mapping["assignments"][:1]}, {**mapping,"assignments":mapping["assignments"]*2}):
            with self.assertRaises(ValueError): run_connected_table("unit_aggregate",[table],{"value_column":"x","operation":"sum","unit":"participant","participant_mapping":bad})

    def test_complete_join_rejects_null_partial_and_ambiguous_keys(self):
        left=self.table(); right=copy.deepcopy(left)
        right["fields"]=["y" if k=="x" else k for k in right["fields"]]
        for row in right["rows"]: row["y"]=row.pop("x")
        for var in right["variables"]:
            if var["variable_id"]=="x":var["variable_id"]="y"
        result=run_connected_table("unit_join",[left,right],{"keys":["unit_id","conversation_id"]})
        self.assertEqual(result["rows"][0]["x"],0);self.assertEqual(result["rows"][0]["y"],0)
        for mutate in (lambda t:t["rows"].pop(), lambda t:t["rows"].append(t["rows"][0]),lambda t:t["rows"][0].update(unit_id=None)):
            bad=copy.deepcopy(right);mutate(bad)
            with self.assertRaises((ValueError,TypeError)):run_connected_table("unit_join",[left,bad],{"keys":["unit_id","conversation_id"]})

    def test_explicit_numeric_pair_exploratory_correlation_and_scale(self):
        table=self.table(); table["rows"]=[r for r in table["rows"] if r["value_status"]=="observed"]
        table["fields"].append("y"); table["variables"].append({**table["variables"][-1],"variable_id":"y"})
        for row in table["rows"]:row["y"]=2*row["x"]+1
        for statistic in ("pearson","spearman"):
            result=run_connected_table("unit_correlation",[table],{"x_column":"x","y_column":"y","statistic":statistic})
            row=result["rows"][0]
            if row["status"]=="unavailable":self.skipTest("Existing optional SciPy kernel unavailable")
            self.assertAlmostEqual(row["coefficient"],1);self.assertEqual(row["n"],3);self.assertNotIn("p_value",row)
        table["variables"][-1]["scale"]="nominal"
        with self.assertRaises(ValueError):run_connected_table("unit_correlation",[table],{"x_column":"x","y_column":"y","statistic":"pearson"})


class NativeUnitIntegrationTests(unittest.TestCase):
    def test_resolution_phase_cache_rechecks_saved_bytes_before_delivery(self):
        from gurumoji.analysis_core import assess_connection_inputs
        from gurumoji.analysis_method_registry import connection_method_descriptor
        h=bindings.TablePilotHandlerTests();h.setUp();self.addCleanup(h.doCleanups)
        ids=["utterance:"+fingerprint(["TEST-library","TEST-conversation",h.run["input_hash"],f"TEST-u{i}"]).removeprefix("sha256:") for i in range(6)]
        request=request_for(h.run,h.asset,"unit_projection",{"columns":["unit_id","conversation_id","value_status","n"],"unit_ids":ids})
        artifact=next(a for a in h.f.store.artifacts(h.source_id) if a["name"]=="tables/correlations.json")
        path=h.f.store.root/artifact["path"]
        def tamper(envelopes):
            path.write_bytes(b"TEST ONLY external corruption")
            return assess_connection_inputs(request["bindings"]["slot"],envelopes,connection_method_descriptor("unit_projection"))
        result=h.f.store.bind_asset_inputs(method_id="unit_projection",**request["bindings"],assess=tamper)
        self.assertEqual(result["decision"],"rejected");self.assertEqual(result["payloads"],[])
        self.assertEqual(path.read_bytes(),b"TEST ONLY external corruption")

    def test_real_explicit_correlation_save_fresh_registered_qualitative_consumer(self):
        h=bindings.TablePilotHandlerTests();h.setUp();self.addCleanup(h.doCleanups)
        values=copy.deepcopy(h.values);values[2].update(value_status="observed",n=1)
        for row in values:row["y"]=2*row["n"]+1 if row["n"] is not None else None
        saved=h.f.store.save(item_id="TEST-conversation",kind="ai_insights",snapshot=h.f.snapshot,
            result={"parameters":{},"TEST_fixture_only":True},datasets={"correlations":(h.fields+["y"],values)},
            request_id="TEST-explicit-pair",input_fingerprint=fingerprint(h.f.snapshot),source_revision=1,analysis_revision=1,publish=False)
        asset,state=h.f.descriptors(saved);asset["scope"]=copy.deepcopy(h.asset["scope"])
        asset["variables"]=[{**copy.deepcopy(h.asset["variables"][-2]),"variable_id":field,
            "value_type":"integer" if field in {"n","y"} else "string","scale":"ratio" if field in {"n","y"} else "nominal"} for field in h.fields+["y"]]
        h.f.register([asset],states=[state])
        request=request_for(h.run,asset,"unit_correlation",{"x_column":"n","y_column":"y","statistic":"pearson"})
        task=h.task("unit_correlation",request);h.service._execute(h.run["run_id"],task["task_id"])
        state=h.state_of(task);self.assertEqual(state["status"],"succeeded",state.get("error"))
        fresh=AnalysisStore(h.f.path,h.f.connect);report=fresh.connected_output_descriptor(state["table_store_run_id"])
        self.assertEqual(report["meaning"]["unit"],"report_claim")
        record=fresh.read_asset(report)["value"]["rows"][0]["values"]
        if record["status"]=="unavailable":self.skipTest("Existing SciPy unavailable")
        self.assertAlmostEqual(record["coefficient"],1);self.assertEqual(record["n"],3);self.assertNotIn("p_value",record)
        permission={**copy.deepcopy(h.state),"asset_key":report["asset_key"],"target_content_hash":report["content_hash"],"target_domain":report["content_domain"]}
        h.f.register([report],states=[permission])
        original=next(iter(fresh._connection_index()[1].values()))
        comparison=request_for(h.run,report,"qualitative_compare",{"proposals":[]})
        base=comparison["bindings"]["inputs"][0]
        comparison["bindings"]["inputs"].append({**copy.deepcopy(base),"input_ref_id":"original","role":"evidence_context",
            "source":{"type":"original","source_ref":original["source_ref"]}})
        child=h.task("qualitative_compare",comparison);h.service._execute(h.run["run_id"],child["task_id"])
        self.assertEqual(h.state_of(child)["status"],"succeeded",h.state_of(child).get("error"))

    def test_complete_native_fixed_table_to_conversation_aggregate(self):
        h=bindings.TablePilotHandlerTests();h.setUp();self.addCleanup(h.doCleanups)
        request=request_for(h.run,h.asset,"unit_aggregate",{"value_column":"n","operation":"mean","unit":"conversation","participant_mapping":None})
        task=h.task("unit_aggregate",request)
        h.service._execute(h.run["run_id"],task["task_id"]);h.service._validate_received(h.run["run_id"],task["task_id"])
        state=h.state_of(task);self.assertEqual(state["status"],"succeeded",state)
        fresh=AnalysisStore(h.f.path,h.f.connect); result=fresh.verified_package(state["table_store_run_id"])[1]
        self.assertEqual(result["datasets"]["table"]["rows"][0]["value"],1)
        d=next(iter(result["unit_contract"]["denominators"].values()))
        self.assertEqual(d,{"included":5,"observed":2,"missing":1,"unprocessed":1,"unknown":1,"excluded":1})
        self.assertEqual(len(result["unit_contract"]["source_utterances"]),6)
        self.assertEqual(fresh.connected_output_descriptor(state["table_store_run_id"])["meaning"]["unit"],"conversation")


if __name__=="__main__":unittest.main()
