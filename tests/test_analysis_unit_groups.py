"""Synthetic pure pooling tests; no real Store authority, files, DB or AI.

The fixture invokes the real prepare_connected conversion with its upstream
resolution methods replaced by in-memory fixtures. It does NOT exercise or
claim HumanRecord adoption, policy checks, Handler execution, save or fresh.
"""

import copy
import unittest

from gurumoji.analysis_core import AnalysisContractError, TABLE_PILOT_MAX_BYTES, canonical, fingerprint
from gurumoji.analysis_method_registry import connected_slot
from gurumoji.analysis_store import AnalysisStore, digest
from gurumoji.research_analysis import run_connected_table
from gurumoji.services.analysis_unit_groups import pool_unit_tables


def seal(scope):
    scope["manifest_hash"] = fingerprint({k: v for k, v in scope.items() if k != "manifest_hash"})
    return scope


def reference(kind="definition", identifier="TEST-shared-definition", domain="canonical-json-v1"):
    return {"target_type": kind, "target_id": identifier, "version": "1",
            "content_hash": fingerprint(["TEST-only", identifier]), "hash_domain": domain,
            "library_id": "TEST-library"}


def request(asset, method, parameters):
    context = {"plan_id": "TEST-plan", "plan_version": 1, "plan_hash": fingerprint("TEST-plan"),
               "generation": 1, "consumer_task_id": "TEST-consumer", "purpose": "exploratory",
               "destination": "local", "scope_id": asset["scope"]["scope_id"],
               "scope_manifest_hash": asset["scope"]["manifest_hash"], "cancelled": False}
    selector = {"row_ids": [], "column_ids": [], "range_ref": None}
    selector["selection_hash"] = fingerprint(selector)
    ref = {k: context[k] for k in ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id")}
    ref.update(slot_id="table", input_ref_id="TEST-input", role="data_input", selection="selected",
               omission_reason=None, selector=selector,
               source={"type": "frozen", "asset_key": asset["asset_key"],
                       "content_hash": fingerprint("TEST-saved-table"), "content_domain": "raw-bytes-v1"})
    return {"version": "connected-assets-2", "actor": "code", "parameters": parameters,
            "bindings": {"slot": connected_slot(method), "inputs": [ref], "context": context}}


def prepared_carrier(cid, states=("observed", "observed", "missing", "unprocessed", "unknown", "excluded"),
                     values=(0, 2, None, None, None, 5), *, theme=False, projected=False):
    """Use actual Store conversion rather than a hand-invented carrier shape."""
    input_hash = fingerprint(["TEST-input", cid])
    raw_ids = ["TEST-u" + str(i) for i in range(len(states))]
    evidence = [{"evidence_id": "ev_" + fingerprint({"dataset": input_hash, "utterance": uid,
                 "text": "TEST invented " + uid})[7:31], "utterance_id": uid, "excluded": state == "excluded"}
                for uid, state in zip(raw_ids, states)]
    snapshot = {"conversation_id": cid, "input_hash": input_hash, "source_revision": 1,
                "analysis_revision": 1, "evidence": evidence,
                "segments": [{"id": uid, "speaker": "TEST-S1"} for uid in raw_ids]}
    source = {**reference("snapshot", "TEST-snapshot-" + cid), "content_hash": fingerprint(snapshot)}
    scope = seal({"scope_id": "TEST-scope-" + cid, "mode": "dataset", "input_refs": [source],
                  "conversation_ids": [cid], "member_ids": [e["evidence_id"] for e in evidence if not e["excluded"]],
                  "context_ids": [e["evidence_id"] for e in evidence if e["excluded"]]})
    fields = ["utterance_id", "conversation_id", "value_status", "n", "category"]
    definition = reference()
    variables = [{"variable_id": name, "version": 1, "definition_hash": definition["content_hash"],
                  "definition_ref": copy.deepcopy(definition), "value_type": "integer" if name == "n" else "string",
                  "scale": "ratio" if name == "n" else "nominal", "unit": "utterance", "value_domain": "TEST-only",
                  "generation": {"kind": "code", "actor_id": "TEST-code", "step_ids": []},
                  "validity": "structural_checked"} for name in fields]
    key = {"library_id": "TEST-library", "store_run_id": "TEST-run-" + cid,
           "artifact_id": "TEST-artifact-" + cid, "output_name": "tables/correlations.json"}
    asset = {"asset_key": key, "scope": scope, "variables": variables, "meaning": {"unit": "utterance"}}
    table = {"fields": fields, "rows": [{"row_id": str(i), "values": {
        "utterance_id": uid, "conversation_id": cid, "value_status": state,
        "n": value, "category": "TEST-category" if value is not None else None}}
        for i, (uid, state, value) in enumerate(zip(raw_ids, states, values))]}
    adoption = reference("artifact", "TEST-human-record", "human-record-v1")
    states_index = {digest(key): {1: {"review_refs": [adoption]}}}
    if theme:
        table = {"content": {}, "themes": [{"content": {"theme_id": "TEST-theme",
                 "support": [{"utterance_id": raw_ids[0]}], "counterexamples": [{"utterance_id": raw_ids[1]}]}}],
                 "coverage": {"unread_sets": {"processing": {"status": "measured",
                              "ids": [uid for uid, state in zip(raw_ids, states) if state == "unprocessed"]}}}}
    receipt = {"decision": "eligible", "bindings": [{"source": key, "checked_state_revision": 1}],
               "payloads": [{"value": table}]}
    store = object.__new__(AnalysisStore)
    store.bind_asset_inputs = lambda **_: receipt
    store._connection_index = lambda: ({digest(key): asset}, {}, states_index, {})
    store._connection_content = lambda _: ({}, snapshot)
    store.verified_package = lambda _: ({}, {}, {}, {})
    store.library_id = lambda: "TEST-library"
    method = "theme_evidence_table" if theme else "unit_aggregate"
    parameters = {"theme_id": "TEST-theme"} if theme else {
        "value_column": "n", "operation": "mean", "unit": "conversation", "participant_mapping": None}
    result = store.prepare_connected(method, request(asset, method, parameters), expected_snapshot=snapshot)["tables"][0]
    if projected:
        output = run_connected_table("unit_projection", [result],
                                     {"columns": result["fields"], "unit_ids": [result["rows"][0]["unit_id"]]})
        receipt["payloads"] = [{"value": {"fields": output["fields"],
                                         "rows": [{"values": r} for r in output["rows"]]}}]
        store.verified_package = lambda _: ({}, {"unit_contract": output["unit_contract"]}, {}, {})
        result = store.prepare_connected(method, request(asset, method, parameters))["tables"][0]
    return result


def group_scope(tables):
    refs = {canonical(ref): ref for table in tables for ref in table["scope"]["input_refs"]}
    return seal({"scope_id": "TEST-group", "mode": "dataset",
                 "input_refs": [copy.deepcopy(refs[k]) for k in sorted(refs)],
                 "conversation_ids": sorted({r["conversation_id"] for t in tables for r in t["rows"]}),
                 "member_ids": sorted(r["unit_id"] for t in tables for r in t["rows"] if r["value_status"] != "excluded"),
                 "context_ids": sorted(r["unit_id"] for t in tables for r in t["rows"] if r["value_status"] == "excluded")})


class UnitPoolTests(unittest.TestCase):
    def setUp(self):
        self.tables = [prepared_carrier("TEST-C1"),
                       prepared_carrier("TEST-C2", ("observed", "unknown"), (10, None))]
        self.scope = group_scope(self.tables)

    def pooled(self, tables=None, scope=None):
        return pool_unit_tables(self.tables if tables is None else tables,
                                group_scope=self.scope if scope is None else scope)

    def rejected(self, tables=None, scope=None, code=None):
        with self.assertRaises(AnalysisContractError) as raised:
            self.pooled(tables, scope)
        self.assertTrue(raised.exception.code.startswith("unit_pool_"), raised.exception.code)
        if code:
            self.assertEqual(raised.exception.code, "unit_pool_" + code)

    def test_actual_native_carriers_count_sum_mean_and_all_states(self):
        pooled = self.pooled()
        self.assertEqual(len(pooled["rows"]), 8)
        self.assertEqual({r["value_status"] for r in pooled["rows"]},
                         {"observed", "missing", "unknown", "unprocessed", "excluded"})
        self.assertEqual(sum(r.get("n") == 0 for r in pooled["rows"]), 1)
        for operation, values in (("count", [2, 1]), ("sum", [2, 10]), ("mean", [1, 10])):
            with self.subTest(operation=operation):
                output = run_connected_table("unit_aggregate", [pooled], {"value_column": "n", "operation": operation,
                    "unit": "conversation_speaker", "participant_mapping": None})
                self.assertEqual([r["value"] for r in output["rows"]], values)
                ds = list(output["unit_contract"]["denominators"].values())
                self.assertEqual([d["included"] for d in ds], [5, 2])
                self.assertEqual([d["observed"] for d in ds], [2, 1])
                self.assertEqual(ds[0], {"included": 5, "observed": 2, "missing": 1,
                                        "unknown": 1, "unprocessed": 1, "excluded": 1})
                self.assertEqual(output["unit_contract"]["source_utterances"], pooled["source_utterances"])

    def test_explicit_participant_mapping_weighted_mean_and_silent_roster(self):
        adopted = reference("artifact", "TEST-participant-map", "human-record-v1")
        other = reference("artifact", "TEST-other-record", "human-record-v1")
        self.tables[0]["definition_adoption_refs"] = [adopted, other]
        self.tables[1]["definition_adoption_refs"] = [adopted]
        pooled = self.pooled()
        self.assertEqual(len(pooled["definition_adoption_refs"]), 2)
        mapping = {"actor": {"kind": "researcher", "actor_id": "TEST-person"}, "record_ref": adopted,
                   "assignments": [{"conversation_id": cid, "speaker_id": "TEST-S1", "participant_id": "TEST-P1"}
                                   for cid in ("TEST-C1", "TEST-C2")] + [
                       {"conversation_id": "TEST-C1", "speaker_id": "TEST-silent", "participant_id": "TEST-P2"}]}
        params = {"value_column": "n", "operation": "mean", "unit": "participant", "participant_mapping": mapping}
        output = run_connected_table("unit_aggregate", [pooled], params)
        self.assertEqual(len(output["rows"]), 1)
        self.assertEqual(output["rows"][0]["participant_id"], "TEST-P1")
        self.assertEqual(output["rows"][0]["value"], 4)  # (0 + 2 + 10) / 3, not mean([1, 10]).
        self.assertFalse(any(r["speaker_id"] == "TEST-silent" for r in pooled["rows"]))
        for bad in (None, {**mapping, "assignments": mapping["assignments"][:1]},
                    {**mapping, "assignments": mapping["assignments"] + [mapping["assignments"][0]]},
                    {**mapping, "record_ref": reference("artifact", "TEST-unadopted")}):
            with self.subTest(mapping=bad), self.assertRaises(AnalysisContractError):
                run_connected_table("unit_aggregate", [pooled], {**params, "participant_mapping": bad})

    def test_deep_copy_provenance_and_permutation_determinism(self):
        before, scope_before = copy.deepcopy(self.tables), copy.deepcopy(self.scope)
        pooled = self.pooled()
        for key in ("sources", "source_utterances", "denominators"):
            self.assertEqual(pooled[key], {uid: value for table in self.tables for uid, value in table[key].items()})
        self.assertEqual(pooled["input_hashes"], sorted(t["input_hashes"][0] for t in self.tables))
        # The same local utterance IDs in different conversations stay distinct.
        self.assertEqual(sum(s["utterance_id"] == "TEST-u0" for s in pooled["source_utterances"].values()), 2)
        permuted = copy.deepcopy(self.tables[::-1])
        for table in permuted:
            table["fields"].reverse()
            table["rows"].reverse()
            table["variables"].reverse()
        self.assertEqual(canonical(self.pooled(permuted)), canonical(pooled))
        pooled["rows"][0]["n"] = 99
        pooled["variables"][0]["generation"]["step_ids"].append("TEST-change")
        pooled["scope"]["input_refs"][0]["target_id"] = "TEST-change"
        pooled["sources"][pooled["rows"][0]["unit_id"]].append("TEST-change")
        self.assertEqual(self.tables, before)
        self.assertEqual(self.scope, scope_before)

    def test_null_and_absent_values_remain_distinct(self):
        del self.tables[0]["rows"][2]["n"]
        pooled = self.pooled()
        row = next(r for r in pooled["rows"] if r["unit_id"] == self.tables[0]["rows"][2]["unit_id"])
        self.assertNotIn("n", row)
        self.assertIsNone(self.tables[0]["rows"][3]["n"])

    def test_actual_theme_and_saved_projected_carriers(self):
        themes = [prepared_carrier(cid, theme=True) for cid in ("TEST-C1", "TEST-C2")]
        pooled = self.pooled(themes, group_scope(themes))
        self.assertEqual(pooled["theme_id"], "TEST-theme")
        self.assertTrue(pooled["definition_adoption_refs"])
        output = run_connected_table("theme_evidence_table", [pooled], {"theme_id": "TEST-theme"})
        self.assertEqual(len(output["rows"]), 12)
        projected = [prepared_carrier(cid, projected=True) for cid in ("TEST-C1", "TEST-C2")]
        pooled = self.pooled(projected, group_scope(projected))
        self.assertEqual(sum(r["value_status"] == "excluded" for r in pooled["rows"]), 10)
        self.assertEqual(sum(d["included"] for d in pooled["denominators"].values()), 10)
        self.assertEqual(len(pooled["scope"]["member_ids"]), 2)

    def test_two_through_sixteen_carriers(self):
        tables = [prepared_carrier("TEST-C" + str(i), ("observed",), (i,)) for i in range(16)]
        self.assertEqual(len(self.pooled(tables, group_scope(tables))["rows"]), 16)
        for bad in ([], tables[:1], tables + [prepared_carrier("TEST-C16", ("observed",), (16,))],
                    tuple(self.tables), None):
            with self.subTest(size=len(bad) if bad is not None else None):
                if bad is None:
                    with self.assertRaises(AnalysisContractError):
                        pool_unit_tables(None, group_scope=self.scope)
                else:
                    self.rejected(bad, code="cardinality")

    def test_table_shapes_and_row_population_boundaries(self):
        mutations = [lambda t: t.update(extra=True), lambda t: t.pop("sources"),
                     lambda t: t.update(unit="conversation"), lambda t: t.update(version="unit-table-1"),
                     lambda t: t.update(rows=[]), lambda t: t["rows"].pop(),
                     lambda t: t["rows"].append(copy.deepcopy(t["rows"][0])),
                     lambda t: t["rows"][0].update(conversation_id="TEST-foreign"),
                     lambda t: t["rows"][0].update(value_status="pending"),
                     lambda t: t["rows"][0].update(extra=0),
                     lambda t: t["fields"].append("n"),
                     lambda t: t["variables"].pop(),
                     lambda t: t["variables"].append(copy.deepcopy(t["variables"][0])),
                     lambda t: t["variables"][0].update(extra=True),
                     lambda t: t["rows"][0].update(n=None),
                     lambda t: t["rows"][2].update(n=0),
                     lambda t: t["rows"][0].update(n=True),
                     lambda t: t.update(theme_id="TEST-one-sided")]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                tables = copy.deepcopy(self.tables)
                mutation(tables[0])
                self.rejected(tables)
        self.rejected([self.tables[0], copy.deepcopy(self.tables[0])], code="duplicate_conversation")

    def test_source_hash_qualified_identity_and_denominator_boundaries(self):
        mutations = [lambda t, uid: t["sources"].pop(uid),
                     lambda t, uid: t["sources"].update({"TEST-extra": [uid]}),
                     lambda t, uid: t["sources"].update({uid: ["TEST-u0"]}),
                     lambda t, uid: t["sources"][uid].append(uid),
                     lambda t, uid: t["source_utterances"].pop(uid),
                     lambda t, uid: t["source_utterances"][uid].update(input_hash=fingerprint("TEST-foreign")),
                     lambda t, uid: t["source_utterances"][uid].update(conversation_id="TEST-C2"),
                     lambda t, uid: t["source_utterances"][uid].update(utterance_id="TEST-u1"),
                     lambda t, uid: t["source_utterances"][uid].update(extra=True),
                     lambda t, uid: t["input_hashes"].append(fingerprint("TEST-extra")),
                     lambda t, uid: t.update(input_hashes=["not-a-hash"]),
                     lambda t, uid: t["denominators"].pop(uid),
                     lambda t, uid: t["denominators"][uid].update(included=True),
                     lambda t, uid: t["denominators"][uid].update(observed=2),
                     lambda t, uid: t["denominators"][uid].update(extra=0),
                     lambda t, uid: t["scope"]["input_refs"][0].update(library_id="TEST-foreign")]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                tables = copy.deepcopy(self.tables)
                mutation(tables[0], tables[0]["rows"][0]["unit_id"])
                seal(tables[0]["scope"])
                self.rejected(tables)
        tables = copy.deepcopy(self.tables)
        # Keep all maps consistent but substitute a raw/unqualified ID.
        old = tables[0]["rows"][0]["unit_id"]
        tables[0]["rows"][0]["unit_id"] = "TEST-u0"
        for key in ("sources", "source_utterances", "denominators"):
            tables[0][key]["TEST-u0"] = tables[0][key].pop(old)
        tables[0]["sources"]["TEST-u0"] = ["TEST-u0"]
        self.rejected(tables, code="qualified_id")

    def test_semantically_exact_variable_definitions(self):
        mutations = [lambda v: v.update(version=2), lambda v: v.update(version=True),
                     lambda v: v.update(value_type="number"), lambda v: v.update(scale="interval"),
                     lambda v: v.update(unit="conversation"), lambda v: v.update(value_domain="different"),
                     lambda v: v.update(validity="human_reviewed"),
                     lambda v: v["generation"].update(actor_id="different"),
                     lambda v: v["generation"]["step_ids"].append("different"),
                     lambda v: v["definition_ref"].update(target_id="different"),
                     lambda v: v["definition_ref"].update(version="2"),
                     lambda v: v["definition_ref"].update(hash_domain="raw-bytes-v1"),
                     lambda v: v.update(definition_hash=fingerprint("different")),
                     lambda v: (v.update(definition_hash=fingerprint("different")),
                                v["definition_ref"].update(content_hash=fingerprint("different"))),
                     lambda v: v["generation"].update(kind="unregistered")]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                tables = copy.deepcopy(self.tables)
                mutation(next(v for v in tables[1]["variables"] if v["variable_id"] == "n"))
                self.rejected(tables)

    def test_denominator_internal_counts_without_rewriting_projection_provenance(self):
        for update in ({"missing": 1}, {"excluded": 1},
                       {"included": 1, "observed": 0, "missing": 0, "unknown": 0, "unprocessed": 0},
                       {"included": 0, "observed": 0, "excluded": 0}):
            tables = copy.deepcopy(self.tables)
            uid = tables[0]["rows"][0]["unit_id"]
            tables[0]["denominators"][uid].update(update)
            with self.subTest(update=update):
                self.rejected(tables, code="denominator")
        tables = copy.deepcopy(self.tables)
        uid = tables[0]["rows"][0]["unit_id"]
        original = {"included": 1, "observed": 1, "missing": 0, "unknown": 0, "unprocessed": 0, "excluded": 0}
        tables[0]["denominators"][uid] = original
        tables[0]["rows"][0]["value_status"] = "excluded"
        pooled = self.pooled(tables, group_scope(tables))
        self.assertEqual(pooled["denominators"][uid], original)

    def test_scope_closed_shape_hash_membership_and_source_union(self):
        mutations = [lambda s: s.update(extra=True), lambda s: s.pop("scope_id"),
                     lambda s: s.update(mode="selection"), lambda s: s["conversation_ids"].pop(),
                     lambda s: s["conversation_ids"].append("TEST-extra"),
                     lambda s: s["conversation_ids"].append(s["conversation_ids"][0]),
                     lambda s: s["member_ids"].pop(), lambda s: s["member_ids"].append("TEST-extra"),
                     lambda s: s["member_ids"].append(s["member_ids"][0]),
                     lambda s: s["context_ids"].append(s["member_ids"][0]),
                     lambda s: s["input_refs"].pop(),
                     lambda s: s["input_refs"].append(reference("snapshot", "TEST-extra")),
                     lambda s: s["input_refs"].append(copy.deepcopy(s["input_refs"][0])),
                     lambda s: s["input_refs"][0].update(extra=True),
                     lambda s: s["input_refs"][0].update(content_hash="invalid")]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                scope = copy.deepcopy(self.scope)
                mutation(scope)
                seal(scope)
                self.rejected(scope=scope)
        self.rejected(scope={**self.scope, "manifest_hash": fingerprint("wrong")}, code="scope_hash")
        scope = copy.deepcopy(self.scope)
        scope["member_ids"][0], scope["context_ids"][0] = scope["context_ids"][0], scope["member_ids"][0]
        self.rejected(scope=seal(scope), code="group_population")
        raw = copy.deepcopy(self.scope)
        raw["member_ids"] = [uid for t in self.tables for uid in t["scope"]["member_ids"]]
        raw["context_ids"] = [uid for t in self.tables for uid in t["scope"]["context_ids"]]
        self.rejected(scope=seal(raw), code="group_population")

    def test_source_scope_structural_checks_do_not_claim_evidence_identity(self):
        for key in ("member_ids", "context_ids"):
            tables = copy.deepcopy(self.tables)
            tables[0]["scope"][key].pop()
            seal(tables[0]["scope"])
            self.rejected(tables, code="population")
        # Raw evidence IDs are opaque here. Only Store has the evidence/text
        # needed to reject this same-cardinality substitution against a source.
        tables = copy.deepcopy(self.tables)
        tables[0]["scope"]["member_ids"][0] = "TEST-opaque-evidence-id"
        seal(tables[0]["scope"])
        self.assertEqual(len(self.pooled(tables)["rows"]), 8)
        self.assertNotEqual(tables[0]["scope"]["input_refs"][0]["content_hash"], tables[0]["input_hashes"][0])

    def test_bounded_rows_fields_sources_and_original_scopes(self):
        for key, value in (("rows", [{}] * 2001),
                           ("fields", ["TEST-field-" + str(i) for i in range(257)]),
                           ("sources", {str(i): [] for i in range(2001)}),
                           ("source_utterances", {str(i): {} for i in range(2001)}),
                           ("denominators", {str(i): {} for i in range(2001)})):
            tables = copy.deepcopy(self.tables)
            tables[0][key] = value
            with self.subTest(key=key):
                self.rejected(tables)
        mutations = [lambda s: s.update(extra=True), lambda s: s.pop("scope_id"),
                     lambda s: s.update(mode="selection"),
                     lambda s: s["conversation_ids"].append("TEST-C2"),
                     lambda s: s["context_ids"].append(s["member_ids"][0]),
                     lambda s: s.update(input_refs=[]),
                     lambda s: s["input_refs"][0].update(target_type="raw_text")]
        for mutation in mutations:
            tables = copy.deepcopy(self.tables)
            mutation(tables[0]["scope"])
            seal(tables[0]["scope"])
            with self.subTest(mutation=mutations.index(mutation)):
                self.rejected(tables)
        tables = copy.deepcopy(self.tables)
        tables[0]["scope"]["manifest_hash"] = fingerprint("TEST-wrong")
        self.rejected(tables, code="scope_hash")

    def test_json_nonfinite_depth_cycle_and_total_byte_limits(self):
        for bad in (float("nan"), float("inf"), float("-inf"), {1}, (1,), b"TEST", object()):
            tables = copy.deepcopy(self.tables)
            tables[0]["rows"][0]["n"] = bad
            with self.subTest(type=type(bad).__name__):
                self.rejected(tables)
        for bad in ("\ud800", "TEST" * TABLE_PILOT_MAX_BYTES, 10 ** 5000):
            tables = copy.deepcopy(self.tables)
            tables[0]["variables"][0]["value_domain"] = bad
            self.rejected(tables)
        tables = copy.deepcopy(self.tables)
        tables[0]["rows"][0][1] = "invalid-key"
        self.rejected(tables, code="json_key")
        nested = []
        for _ in range(20):
            nested = [nested]
        for bad in (nested, []):
            if not bad:
                bad.append(bad)
            tables = copy.deepcopy(self.tables)
            tables[0]["rows"][0]["n"] = bad
            self.rejected(tables, code="depth")
        # Each table fits; the aggregate payload must also fit, without truncation.
        tables = copy.deepcopy(self.tables)
        for table in tables:
            for variable in table["variables"]:
                variable["value_domain"] = "x" * 11500
            self.assertLess(len(canonical(table)), TABLE_PILOT_MAX_BYTES)
        self.rejected(tables, code="byte_limit")


if __name__ == "__main__":
    unittest.main()
