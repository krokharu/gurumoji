"""Synthetic S1 typed TA roundtrips. No model, real library or researcher record."""
import copy
import hashlib
import unittest
from pathlib import Path

from gurumoji.analysis_core import (AnalysisContractError, fingerprint, content_fingerprint,
    validate_thematic_candidates, assess_connection_inputs)
from gurumoji.analysis_method_registry import connection_method_descriptor, connection_kind_contract
from gurumoji.analysis_store import AnalysisStore, AssetBindingError, StoreConflict, canonical, digest, safe_path
from gurumoji.method_experts import ExpertCatalog
from gurumoji.services.expert_agents import ExpertAgentRegistry, thematic_source_packet, validate_report, report_schema
from test_analysis_asset_bindings import SyntheticStore

ROOT = Path(__file__).resolve().parents[1]
EXPERT = "exp-thematic-analysis"


def candidate_fixture(source, *, producer=None):
    """Explicit invention of machine fields, never parsing the legacy prose."""
    producer = producer or {"kind": "ai", "actor_id": "TEST-model", "step_ids": ["ta-p2-ai-codes"],
        "model_id": "TEST-model", "revision": "TEST-revision", "provider": "TEST-provider"}
    def ref(uid, relation):
        row = next(e for e in source["evidence"] if e["utterance_id"] == uid)
        return {"library_id": source["source_ref"]["library_id"], "snapshot_ref": copy.deepcopy(source["source_ref"]),
            "input_version": source["source_ref"]["version"], "input_hash": source["source_ref"]["content_hash"],
            "utterance_id": uid, "utterance_hash": "sha256:" + hashlib.sha256(row["text"].encode()).hexdigest(),
            "context_ids": [], "relation": relation}
    tc = {"candidate_set_id": "TEST-candidates", "theme_id": "TEST-theme", "version": 1, "claim_id": "TEST-claim",
        "input_refs": [copy.deepcopy(source["source_ref"])], "scope": copy.deepcopy(source["scope"]), "producer": producer,
        "name": "試験候補", "definition": None, "code_refs": [], "support": [ref(source["scope"]["member_ids"][0], "support")],
        "counterexamples": [], "alternatives": []}
    theme = {"content": tc, "content_hash": content_fingerprint("ta-theme-content-v1", tc), "status": "draft",
        "meaning_review": "human_pending", "search_state": {k: "not_searched" for k in ("support", "counterexamples", "alternatives")},
        "memo_refs": [], "receipt_bindings": []}
    target = {"domain": "ta-theme-content-v1", "candidate_set_id": tc["candidate_set_id"], "theme_id": tc["theme_id"],
              "version": 1, "content_hash": theme["content_hash"]}
    content = {"candidate_set_id": tc["candidate_set_id"], "version": 1, "input_refs": copy.deepcopy(tc["input_refs"]),
               "scope": copy.deepcopy(tc["scope"]), "producer": copy.deepcopy(producer), "theme_refs": [target]}
    coverage = {"dataset_ids": source["scope"]["member_ids"] + source["scope"]["context_ids"],
        "required_ids": copy.deepcopy(source["scope"]["member_ids"]), "excluded_ids": copy.deepcopy(source["scope"]["context_ids"]),
        "read_receipts": [], "delivery_receipts": [], "processing_receipts": [], "human_read_record_refs": [],
        "unread_sets": {k: {"status": "unknown", "ids": None} for k in ("retrieval", "delivery", "processing", "human")}}
    return {"schema_id": "gurumoji.thematic-candidate", "schema_version": 1, "content": content,
        "content_hash": content_fingerprint("ta-candidate-content-v1", content), "themes": [theme], "coverage": coverage,
        "human_status": "human_pending", "human_record_state": "not_entered", "human_records": [],
        "history": [{"change_id": "TEST-create", "operation": "create", "from_themes": [], "to_themes": [target],
            "reason": "Synthetic draft only", "actor": copy.deepcopy(producer), "recorded_at": "2026-10-08T00:00:00Z", "affected_code_refs": []}]}


def rehash(value):
    for theme, target in zip(value["themes"], value["content"]["theme_refs"]):
        theme["content_hash"] = content_fingerprint("ta-theme-content-v1", theme["content"])
        target.update(theme_id=theme["content"]["theme_id"], version=theme["content"]["version"], content_hash=theme["content_hash"])
    value["content_hash"] = content_fingerprint("ta-candidate-content-v1", value["content"])


class TypedAssetsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SyntheticStore(handler=True)
        self.addCleanup(self.fixture.close)
        from gurumoji.analysis_orchestration import initialize_orchestration_store
        with self.fixture.connect() as db: initialize_orchestration_store(db)
        snapshot = copy.deepcopy(self.fixture.snapshot)
        snapshot["evidence"][0].update(utterance_id="TEST-u1")
        self.initial = {"initial_id": "TEST-initial", "snapshot": snapshot, "hash": fingerprint(snapshot)}
        self.source = thematic_source_packet(self.initial, library_id="TEST-library", conversation_id="TEST-conversation")
        self.registry = ExpertAgentRegistry(ExpertCatalog(root=ROOT / "docs/program-vault", local_root=Path(self.fixture.temp.name) / "local"))
        self.profile = self.registry.freeze({"expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"typed_contract": "thematic_candidates_v1"}}})["profiles"][EXPERT]
        producer = {"kind": "ai", "actor_id": "TEST-model", "step_ids": [self.profile["allowed_steps"][0]["id"]],
            "model_id": "TEST-model", "revision": "unverified", "provider": "TEST-provider"}
        self.candidate = candidate_fixture(self.source, producer=producer)
        self.raw = {"expert_report": {"expert_id": EXPERT, "profile_hash": self.profile["profile_hash"],
            "knowledge_hash": self.profile["knowledge_hash"], "status": "draft",
            "outputs": {k: "Synthetic prose, not parsed" for k in self.profile["output_schema"]["properties"]},
            "evidence_ids": ["TEST-u1"], "knowledge_note_ids": [self.profile["knowledge"][0]["note_id"]],
            "performed_step_ids": producer["step_ids"], "missing_inputs": [], "limitations": "Human pending",
            "thematic_candidates_v1": self.candidate}}

    def save(self, value=None, suffix="1"):
        value = copy.deepcopy(value if value is not None else self.candidate)
        raw = copy.deepcopy(self.raw); raw["expert_report"]["thematic_candidates_v1"] = value
        # Explicit TEST producer ledger, never a provenance fallback in Store.
        execution_run = "TEST-typed-execution-" + suffix
        task_id = value["content"]["producer"]["actor_id"]
        task = {"task_id": task_id, "run_id": execution_run, "kind": "ai", "status": "succeeded",
            "model": "TEST-model", "provider": "TEST-provider"}
        meta = {"result_id": "TEST-result", "task_id": task_id, "run_id": execution_run,
            "validation_status": "valid", "raw_hash": fingerprint(raw), "stale": False}
        with self.fixture.connect() as db:
            db.execute("DELETE FROM orchestration_results WHERE task_id=?", (task_id,))
            db.execute("INSERT OR REPLACE INTO orchestration_tasks VALUES (?,?,?,?)", (task_id, execution_run, task_id, canonical(task).decode()))
            db.execute("INSERT OR REPLACE INTO orchestration_results VALUES (?,?,?,?,?)", ("TEST-result", execution_run, task_id, canonical(raw).decode(), canonical(meta).decode()))
        result = {"schema_version": 1, "parameters": {}, "orchestration": {"initial": self.initial,
            "expert_knowledge_snapshot": {"profiles": {EXPERT: self.profile}},
            "run": {"run_id": execution_run, "item_id": "TEST-conversation", "expert_agents": {"profiles": {EXPERT: self.profile}}},
            "raw_results": [{"result_id": "TEST-result", "task_id": task_id, "validation_status": "valid", "raw": raw}],
            "thematic_candidates_v1": [{"result_id": "TEST-result", "task_id": task_id, "candidate": value}]}}
        return self.fixture.store.save(item_id="TEST-conversation", kind="autonomous_analysis", snapshot={"title": "Synthetic"},
            result=result, datasets={}, request_id="TEST-typed-" + suffix, input_fingerprint=digest(self.initial),
            source_revision=1, analysis_revision=1, publish=False)

    def state(self, descriptor, status):
        return {"asset_key": descriptor["asset_key"], "target_content_hash": descriptor.get("content_hash", descriptor["raw_byte_hash"]),
            "target_domain": descriptor.get("content_domain", "raw-bytes-v1"), "state_revision": 1, "policy_revision": 1,
            "status": status, "allowed_purposes": ["exploratory", "qualitative_compare"], "send_policy": "local_only",
            "destinations": [], "revoked": False, "review_refs": [], "reason": "TEST explicit synthetic policy, no human adoption",
            "updated_at": "2026-10-08T00:00:00Z"}

    def request(self, asset, original=False):
        request = self.fixture.request(asset, original=original, role="evidence_context")
        request["method_id"] = "thematic"
        request["slot"].update(accept_kinds=[] if original else [asset["kind"]], accept_units=[asset["meaning"]["unit"]],
            purposes=["exploratory", "qualitative_compare"], max_bytes=100000)
        return request

    def test_validate_save_fresh_read_bind_keeps_human_pending_and_raw(self):
        validate_report(self.profile, self.raw, ["TEST-u1"], thematic_source=self.source)
        original_raw = canonical(self.raw)
        run = self.save()
        fresh = AnalysisStore(self.fixture.path, self.fixture.connect)
        choices = fresh.thematic_asset_descriptors(run["id"])
        asset, original = choices["assets"][0], choices["original"]
        self.assertNotEqual(asset["content_hash"], asset["raw_byte_hash"])
        review = fresh.read_asset(asset)
        self.assertEqual(review["value"], self.candidate)
        self.assertEqual(review["human_status"], "human_pending")
        self.assertFalse(review["execution_enabled"])
        saved = fresh.verified_package(run["id"])[1]
        self.assertEqual(canonical(saved["orchestration"]["raw_results"][0]["raw"]), original_raw)
        self.fixture.register(assets=[asset], originals=[original], states=[self.state(asset, "candidate"), self.state(original, "adopted")])
        bound = fresh.bind_asset_inputs(**self.request(asset))
        self.assertEqual(bound["decision"], "human_pending", bound)
        self.assertEqual(bound["payloads"], [])
        source_binding = fresh.bind_asset_inputs(**self.request(original, True))
        self.assertEqual(source_binding["decision"], "eligible", source_binding)
        self.assertEqual(source_binding["payloads"][0]["value"], self.initial["snapshot"])

    def test_legacy_default_and_explicit_contract(self):
        legacy = self.registry.freeze({"expert_ids": [EXPERT]})["profiles"][EXPERT]
        self.assertEqual(legacy["contract_version"], 1)
        self.assertEqual(len(legacy["output_schema"]["properties"]), 7)
        self.assertNotIn("thematic_candidates_v1", report_schema(legacy, ["TEST-u1"])["properties"])
        self.assertEqual(self.profile["contract_version"], 2)
        with self.assertRaises(AnalysisContractError): validate_report(legacy, self.raw, ["TEST-u1"])
        with self.assertRaises(AnalysisContractError): validate_report(self.profile, self.raw, ["TEST-u1"])
        with self.assertRaises(AnalysisContractError): self.registry.freeze({"expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"typed_contract": True}}})

    def test_saved_typed_output_requires_actual_producer_ledger_without_export_task_fallback(self):
        run = self.save()
        snapshot, result, _manifest, _files = self.fixture.store.verified_package(run["id"])
        result["orchestration"]["run"]["tasks"] = []
        result["orchestration"]["run"]["run_id"] = "TEST-missing-execution"
        result["parameters"] = {"TEST-provenance-negative": True}
        with self.assertRaises(AssetBindingError) as caught:
            self.fixture.store.save(item_id="TEST-conversation", kind="autonomous_analysis", snapshot=snapshot,
                result=result, datasets={}, request_id="TEST-no-producer", input_fingerprint=digest(snapshot),
                source_revision=1, analysis_revision=1, publish=False)
        self.assertEqual(caught.exception.reason, "typed_execution_provenance")
        self.assertEqual(self.fixture.store.by_request("TEST-no-producer")["status"], "failed")

    def test_closed_source_content_domain_actor_and_human_negatives(self):
        mutations = [lambda c: c.update(extra=True), lambda c: c.update(content_hash=fingerprint("bad")),
            lambda c: c["content"].update(version=True), lambda c: c["themes"][0]["content"].update(extra=1),
            lambda c: c["content"]["theme_refs"][0].update(domain="raw-bytes-v1"),
            lambda c: c["themes"][0]["content"]["support"][0].update(utterance_hash=fingerprint("wrong")),
            lambda c: c["themes"][0]["content"]["support"][0].update(input_version="wrong"),
            lambda c: c["themes"][0]["content"]["support"][0].update(library_id="foreign"),
            lambda c: c["content"]["producer"].update(kind="researcher"),
            lambda c: c.update(human_record_state="entered", human_records=[{"invented": True}]),
            lambda c: c["coverage"]["unread_sets"]["human"].update(status="measured", ids=[]),
            lambda c: c["coverage"]["unread_sets"]["delivery"].update(status="unknown", ids=[]),
            lambda c: c["coverage"]["unread_sets"]["processing"].update(status="measured", ids=[])]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index), self.assertRaises(AnalysisContractError):
                candidate = copy.deepcopy(self.candidate); mutate(candidate)
                validate_thematic_candidates(candidate, source=self.source)

    def test_content_changes_new_immutable_version_state_does_not_change_hc(self):
        first = self.save()
        choices = self.fixture.store.thematic_asset_descriptors(first["id"])
        raw_before = self.fixture.store.verified_package(first["id"])[3]
        revised = copy.deepcopy(self.candidate)
        revised["content"]["version"] = 2
        revised["themes"][0]["content"].update(version=2, definition="Synthetic changed interpretation")
        old = copy.deepcopy(revised["content"]["theme_refs"][0]); rehash(revised)
        revised["history"] = [{"change_id": "TEST-update", "operation": "update", "from_themes": [old],
            "to_themes": copy.deepcopy(revised["content"]["theme_refs"]), "reason": "New content, retained old bytes",
            "actor": revised["content"]["producer"], "recorded_at": "2026-10-08T00:00:01Z", "affected_code_refs": []}]
        validate_thematic_candidates(revised, source=self.source)
        second = self.save(revised, "2")
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(self.candidate["content_hash"], revised["content_hash"])
        state_only = copy.deepcopy(self.candidate); state_only["themes"][0]["search_state"]["support"] = "partial"
        validate_thematic_candidates(state_only, source=self.source)
        third = self.save(state_only, "3")
        self.assertNotEqual(first["id"], third["id"])
        self.assertEqual(self.candidate["content_hash"], state_only["content_hash"])
        self.assertEqual(raw_before, self.fixture.store.verified_package(first["id"])[3])
        asset = choices["assets"][0]
        self.fixture.register(assets=[asset], originals=[choices["original"]], states=[self.state(asset, "candidate")])
        next_state = self.state(asset, "stale"); next_state["state_revision"] = 2
        self.fixture.register(states=[next_state])
        self.assertEqual(raw_before, self.fixture.store.verified_package(first["id"])[3])

    def test_schema_output_library_and_byte_tamper_fail_closed(self):
        run = self.save(); asset = self.fixture.store.thematic_asset_descriptors(run["id"])["assets"][0]
        for mutate in (lambda a: a.update(content_domain="raw-bytes-v1"),
            lambda a: a["schema"].update(schema_hash=fingerprint("wrong")),
            lambda a: a["asset_key"].update(output_name="assets/../../arbitrary.json"),
            lambda a: a["asset_key"].update(library_id="foreign")):
            with self.subTest(mutate=mutate), self.assertRaises((AssetBindingError, AnalysisContractError)):
                bad = copy.deepcopy(asset); mutate(bad); self.fixture.store.read_asset(bad)
        artifact = next(a for a in self.fixture.store.artifacts(run["id"]) if a["name"] == asset["asset_key"]["output_name"])
        path = safe_path(self.fixture.store.root, artifact["path"])
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(StoreConflict): self.fixture.store.read_asset(asset)

    def test_all_five_kinds_share_capability_gates_no_fake_adapter(self):
        descriptor = connection_method_descriptor("thematic")
        for kind in ("claim_set", "relation_graph", "event_sequence", "embedding_matrix"):
            contract = connection_kind_contract(kind)
            candidate = {"source_type": "artifact", "kind": kind, "schema": contract["schema"], "unit": contract["unit"],
                "scope_mode": "dataset", "scope_policy": "all_included_initial", "actor": {"kind": contract["actor_kinds"][-1], "actor_id": "TEST-actor", "step_ids": []},
                "adapter": contract["adapter"], "purpose": "exploratory", "meaning_status": "declared", "human_review_state": "structural_checked",
                "content_hash": fingerprint("TEST"), "content_domain": "ta-candidate-content-v1" if kind == "claim_set" else "raw-bytes-v1"}
            slot = {"slot_id": "TEST", "required": True, "min_items": 1, "max_items": 1, "roles": ["evidence_context"],
                "accept_kinds": [kind], "accept_schemas": [contract["schema"]], "accept_units": [contract["unit"]], "scope_modes": ["dataset"],
                "actors": contract["actor_kinds"], "adapter": contract["adapter"], "purposes": ["exploratory"], "max_bytes": 10000}
            inputs = [{"input_ref_id": "TEST-ref", "selection": "selected", "role": "evidence_context", "omission_reason": None, "candidate": candidate}]
            with self.subTest(kind=kind):
                self.assertEqual(assess_connection_inputs(slot, inputs, descriptor)["decision"], "eligible" if contract["supported"] else "unsupported")
                for key, bad in (("unit", "conversation"), ("scope_mode", "section"), ("purpose", "confirmatory")):
                    wrong = copy.deepcopy(inputs); wrong[0]["candidate"][key] = bad
                    self.assertEqual(assess_connection_inputs(slot, wrong, descriptor)["decision"], "rejected")
        table = connection_method_descriptor("table_frequency")
        self.assertTrue(table["typed_asset_adapter_supported"])

    def test_receipts_require_real_bytes_and_unread_difference(self):
        value = copy.deepcopy(self.candidate)
        raw = b"TEST delivered bytes"
        payload_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        ref = {"target_type": "artifact", "target_id": "TEST-receipt-payload", "version": "1",
               "content_hash": payload_hash, "hash_domain": "raw-bytes-v1"}
        receipt = {"receipt_id": "TEST-receipt", "receipt_type": "delivery", "task_id": "TEST-task",
            "actor": {"kind": "system", "actor_id": "TEST-transport", "step_ids": []}, "input_hash": self.source["source_ref"]["content_hash"],
            "ids": ["TEST-u1"], "status": "recorded", "payload_ref": ref, "payload_hash": payload_hash}
        value["coverage"]["delivery_receipts"] = [receipt]
        value["coverage"]["unread_sets"]["delivery"] = {"status": "measured", "ids": []}
        with self.assertRaises(AnalysisContractError): validate_thematic_candidates(value, source=self.source)
        validate_thematic_candidates(value, source=self.source, receipt_resolver=lambda _: raw)
        with self.assertRaises(AnalysisContractError): validate_thematic_candidates(value, source=self.source, receipt_resolver=lambda _: b"wrong")
        value["coverage"]["delivery_receipts"].append({**receipt, "ids": []})
        with self.assertRaises(AnalysisContractError): validate_thematic_candidates(value, source=self.source, receipt_resolver=lambda _: raw)

    def test_manual_relation_graph_reuses_fixed_interaction_links(self):
        snapshot = copy.deepcopy(self.initial["snapshot"])
        snapshot["evidence"].append({"evidence_id": "TEST-u2", "utterance_id": "TEST-u2", "excluded": False, "text": "Synthetic response"})
        fields = ["relation", "source_segment_id", "target_segment_id", "context_segment_ids", "source_text", "target_text", "status"]
        row = {"relation": "response", "source_segment_id": "TEST-u2", "target_segment_id": "TEST-u1", "context_segment_ids": [],
               "source_text": "Synthetic response", "target_text": snapshot["evidence"][0]["text"], "status": "observed"}
        run = self.fixture.store.save(item_id="TEST-conversation", kind="qualitative_coding", snapshot=snapshot,
            result={"schema_version": 1, "parameters": {}}, datasets={"interaction_links": (fields, [row])},
            request_id="TEST-manual", input_fingerprint=digest(snapshot), source_revision=1, analysis_revision=1, publish=False)
        fixed, _, manifest, content = self.fixture.store.verified_package(run["id"])
        name = "tables/interaction_links.json"; artifact = next(a for a in self.fixture.store.artifacts(run["id"]) if a["name"] == name)
        source_ref = {"target_type": "snapshot", "target_id": manifest["input_snapshot_id"], "version": "1",
            "content_hash": fingerprint(fixed), "hash_domain": "canonical-json-v1", "library_id": "TEST-library"}
        scope = {"scope_id": "TEST-manual-scope", "mode": "dataset", "input_refs": [source_ref], "conversation_ids": ["TEST-conversation"],
                 "member_ids": ["TEST-u1", "TEST-u2"], "context_ids": []}; scope["manifest_hash"] = fingerprint(scope)
        contract = connection_kind_contract("relation_graph")
        asset = {"asset_key": {"library_id": "TEST-library", "store_run_id": run["id"], "artifact_id": artifact["id"], "output_name": name},
            "raw_byte_hash": "sha256:" + hashlib.sha256(content[name]).hexdigest(), "schema": contract["schema"], "scope": scope,
            "producer": {"kind": "researcher", "actor_id": "TEST-manual-annotation", "step_ids": []}, "adapter": contract["adapter"],
            "meaning": {"definition_refs": [], "description": "TEST manual direction target to source, not inferred agreement", "status": "declared", "unit": "utterance"},
            "contract_id": "gurumoji.analysis-asset-connection", "contract_version": 1, "kind": "relation_graph", "content_domain": "raw-bytes-v1",
            "source_refs": [source_ref], "method_id": "qualitative_coding", "method_version": connection_method_descriptor("qualitative_coding")["registry_version"],
            "variables": [], "parent_refs": [source_ref]}
        asset["content_hash"] = asset["raw_byte_hash"]
        review = AnalysisStore(self.fixture.path, self.fixture.connect).read_asset(asset)
        self.assertEqual(review["value"]["rows"][0]["values"], row)
        self.assertEqual(review["human_status"], "human_pending")
        for bad in ({**asset, "producer": {"kind": "code", "actor_id": "TEST", "step_ids": []}},
                    {**asset, "meaning": {**asset["meaning"], "unit": "dataset_claim"}}):
            with self.assertRaises(AssetBindingError): self.fixture.store.read_asset(bad)

    def test_same_version_content_conflict_and_missing_old_target_rejected(self):
        self.save()
        conflict = copy.deepcopy(self.candidate); conflict["themes"][0]["content"]["definition"] = "Changed without new version"
        rehash(conflict); conflict["history"][0]["to_themes"] = copy.deepcopy(conflict["content"]["theme_refs"])
        with self.assertRaises(AssetBindingError): self.save(conflict, "bad-version")
        unresolved = copy.deepcopy(self.candidate)
        unresolved["content"]["version"] = 2; unresolved["themes"][0]["content"]["version"] = 2; rehash(unresolved)
        old = {**unresolved["content"]["theme_refs"][0], "version": 1, "content_hash": fingerprint("unknown old content")}
        unresolved["history"] = [{**self.candidate["history"][0], "operation": "update", "from_themes": [old],
                                  "to_themes": copy.deepcopy(unresolved["content"]["theme_refs"])}]
        with self.assertRaises(AssetBindingError) as caught: self.save(unresolved, "missing-old")
        self.assertEqual(caught.exception.decision, "needs_input")

    def test_support_counter_alternative_code_memo_and_merge_split_history(self):
        value = copy.deepcopy(self.candidate)
        theme = value["themes"][0]; tc = theme["content"]
        counter = {**tc["support"][0], "relation": "counterexample"}; tc["counterexamples"] = [counter]
        tc["alternatives"] = [{"alternative_id": "TEST-alt", "description": "A different synthetic reading", "reason": "Same evidence can support ambiguity",
            "evidence_refs": [{**counter, "relation": "alternative"}]}]
        definition = {"target_type": "definition", "target_id": "TEST-code-definition", "version": "1",
            "content_hash": fingerprint("TEST-code-definition"), "hash_domain": "canonical-json-v1"}
        tc["code_refs"] = [{"code_id": "TEST-code", "version": 1, "definition_hash": definition["content_hash"], "source_ref": definition}]
        theme["memo_refs"] = [{**definition, "target_type": "researcher_memo", "target_id": "TEST-memo-ref"}]
        other = copy.deepcopy(theme); other["content"].update(theme_id="TEST-theme-2", claim_id="TEST-claim-2")
        value["themes"].append(other); value["content"]["theme_refs"].append(copy.deepcopy(value["content"]["theme_refs"][0]))
        rehash(value); value["history"][0]["to_themes"] = copy.deepcopy(value["content"]["theme_refs"])
        validate_thematic_candidates(value, source=self.source)
        original = self.save(value, "two-themes")
        merged = copy.deepcopy(value); merged["content"]["version"] = 2
        merged["themes"] = [merged["themes"][0]]; merged["content"]["theme_refs"] = [merged["content"]["theme_refs"][0]]
        merged["themes"][0]["content"].update(theme_id="TEST-merged", claim_id="TEST-merged-claim", version=1)
        rehash(merged)
        merged["history"] = [{**value["history"][0], "change_id": "TEST-merge", "operation": "merged",
            "from_themes": copy.deepcopy(value["content"]["theme_refs"]), "to_themes": copy.deepcopy(merged["content"]["theme_refs"]),
            "reason": "Explicit synthetic merge rationale, not a human decision"}]
        self.save(merged, "merged")
        split = copy.deepcopy(value); split["content"]["version"] = 3
        for index, theme in enumerate(split["themes"]):
            theme["content"].update(theme_id=f"TEST-split-{index}", claim_id=f"TEST-split-claim-{index}")
        rehash(split)
        split["history"] = [{**value["history"][0], "change_id": "TEST-split", "operation": "split",
            "from_themes": copy.deepcopy(merged["content"]["theme_refs"]), "to_themes": copy.deepcopy(split["content"]["theme_refs"]),
            "reason": "Explicit synthetic split rationale"}]
        saved = self.save(split, "split")
        self.assertNotEqual(original["id"], saved["id"])
        self.assertEqual(self.fixture.store.read_asset(self.fixture.store.thematic_asset_descriptors(original["id"])["assets"][0])["value"], value)
        missing_reason = copy.deepcopy(split); missing_reason["history"][0]["reason"] = ""
        with self.assertRaises(AnalysisContractError): validate_thematic_candidates(missing_reason, source=self.source)
        actor_fake = copy.deepcopy(split); actor_fake["history"][0]["actor"] = {"kind": "researcher", "actor_id": "TEST-fake", "step_ids": []}
        with self.assertRaises(AnalysisContractError): validate_thematic_candidates(actor_fake, source=self.source)


class TypedHandlerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SyntheticStore(handler=True)
        self.addCleanup(self.fixture.close)
        self.registry = ExpertAgentRegistry(ExpertCatalog(root=ROOT / "docs/program-vault", local_root=Path(self.fixture.temp.name) / "local"))
        self.snapshot = copy.deepcopy(self.fixture.snapshot)
        self.snapshot["analysis"] = {"segments": copy.deepcopy(self.snapshot["segments"]),
            "automatic": {"overview": {"included_segment_count": 1, "speaker_count": 1}}}
        self.interpretations = []

    def service(self, store=True, tamper=False, forged_producer=False):
        from gurumoji.analysis_orchestration import AnalysisOrchestrationService
        import test_analysis_orchestration as fixtures
        def agent(role, context, *args):
            if role == "core":
                if context["budget"]["completed_core_iterations"] == 0:
                    return fixtures.core(intents=[fixtures.intent("interpretation", expert_id=EXPERT)])
                return fixtures.stop()
            if role == "critic": return fixtures.critic(context)
            self.interpretations.append(copy.deepcopy(context))
            packet = context["expert_request"]; profile = packet["knowledge"]
            source = {"source_ref": packet["thematic_source"]["source_ref"], "scope": packet["thematic_source"]["scope"],
                      "evidence": [{**row, "excluded": False} for row in context["raw_evidence"]]}
            producer = {**packet["expected_producer"], "step_ids": [profile["allowed_steps"][0]["id"]]}
            if forged_producer:
                producer.update(actor_id="FORGED", model_id="FORGED", provider="FORGED", revision="FORGED")
            candidate = candidate_fixture(source, producer=producer)
            if tamper: candidate["themes"][0]["content"]["support"][0]["utterance_hash"] = fingerprint("wrong text")
            return {"summary": "Synthetic typed AI draft", "claims": [], "analysis_requests": [], "label_patches": [],
                "expert_report": {"expert_id": EXPERT, "profile_hash": profile["profile_hash"], "knowledge_hash": profile["knowledge_hash"],
                    "status": "draft", "outputs": {k: "Synthetic prose unchanged" for k in profile["output_schema"]["properties"]},
                    "evidence_ids": [context["raw_evidence"][0]["evidence_id"]], "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                    "performed_step_ids": producer["step_ids"], "missing_inputs": [], "limitations": "Human pending",
                    "thematic_candidates_v1": candidate}}
        return AnalysisOrchestrationService(connect=self.fixture.connect, find_item=lambda _: {"id": "TEST-conversation", "revision_count": 1, "analysis_revision": 1},
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot), source_fingerprint=lambda _: self.snapshot["input_hash"],
            method_runner=lambda *_: self.fail("No calculation expected"), agent_runner=agent,
            expert_provider=self.registry.freeze, table_store=self.fixture.store if store else None, schedule=False)

    def start(self, service):
        return service.start("TEST-conversation", {"model": "TEST-model", "question": "Synthetic typed question", "time_limit_seconds": None,
            "max_calls": 15, "expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"typed_contract": "thematic_candidates_v1"}}})

    def test_real_handler_validation_publication_save_fresh_read_binding(self):
        from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
        service = self.service(); run = self.start(service); service.run(run["run_id"])
        final = service.status("TEST-conversation", run["run_id"])
        self.assertEqual(final["status"], "completed", final)
        original = service.result("TEST-conversation", run["run_id"])
        expert = next(r for r in original["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "valid", expert)
        self.assertEqual(self.interpretations[0]["expert_request"]["thematic_source"]["source_ref"]["library_id"], "TEST-library")
        publisher = AnalysisOrchestrationPublicationService(connect=self.fixture.connect, store_factory=lambda: self.fixture.store,
            source_guard=lambda db, item, expected: {"id": item}, export_locked=service.result_locked)
        publication = publisher.finalize("TEST-conversation", run["run_id"])
        self.assertEqual(publication["save_status"], "saved", publication)
        fresh = AnalysisStore(self.fixture.path, self.fixture.connect)
        choices = fresh.thematic_asset_descriptors(publication["result_run_id"])
        candidate = fresh.read_asset(choices["assets"][0])["value"]
        self.assertEqual(candidate, expert["raw"]["expert_report"]["thematic_candidates_v1"])
        self.assertEqual(candidate["content"]["producer"]["actor_id"], expert["task_id"])
        self.assertEqual(candidate["content"]["producer"]["model_id"], "TEST-model")
        self.assertEqual(candidate["content"]["producer"]["provider"], "lmstudio")
        self.assertEqual(candidate["content"]["producer"]["revision"], "unverified")
        saved = fresh.verified_package(publication["result_run_id"])[1]
        self.assertEqual(saved["orchestration"]["raw_results"], original["raw_results"])
        # Existing unified resolver is used, never a parallel review permission.
        helper = TypedAssetsTests()
        helper.fixture = self.fixture
        asset, source = choices["assets"][0], choices["original"]
        self.fixture.register(assets=[asset], originals=[source], states=[helper.state(asset, "candidate"), helper.state(source, "adopted")])
        receipt = fresh.bind_asset_inputs(**helper.request(asset))
        self.assertEqual(receipt["decision"], "human_pending", receipt)
        self.assertEqual(receipt["payloads"], [])

    def test_missing_store_and_wrong_fixed_text_fail_before_valid_candidate(self):
        for store, tamper in ((False, False), (True, True)):
            with self.subTest(store=store, tamper=tamper):
                service = self.service(store=store, tamper=tamper)
                run = self.start(service); service.run(run["run_id"])
                results = service.result("TEST-conversation", run["run_id"])["raw_results"]
                self.assertFalse(any(r["validation_status"] == "valid" and "expert_report" in r["raw"] for r in results))

    def test_execution_producer_is_server_owned_even_with_rehashed_forged_claim(self):
        service = self.service(forged_producer=True)
        run = self.start(service); service.run(run["run_id"])
        results = service.result("TEST-conversation", run["run_id"])["raw_results"]
        result = next(r for r in results if "expert_report" in r["raw"])
        self.assertEqual(result["validation_status"], "quarantined", result)
        self.assertIn("typed_execution_provenance", str(result))


if __name__ == "__main__": unittest.main()
