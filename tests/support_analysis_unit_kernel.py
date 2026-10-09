"""Pure synthetic unit kernel contracts; no Flask, Handler or Store imports."""
import copy
import unittest
from gurumoji.analysis_core import fingerprint
from gurumoji.research_analysis import run_connected_table

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
