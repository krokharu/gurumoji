"""Private synthetic SQLite/store fixtures; no app/model/network/human consent."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gurumoji.analysis_store import (AnalysisStore, initialize_store, canonical, digest, StoreConflict,
    AssetBindingError, CONNECTION_TABLE_SCHEMA)
from gurumoji.analysis_method_registry import connection_method_descriptor
from gurumoji.services.analysis_orchestration_adapters import make_asset_binding_adapters
from gurumoji.services.expert_agents import ExpertAgentRegistry
from gurumoji.method_experts import ExpertCatalog

PROBES = []
ROOT = Path(__file__).resolve().parents[1]

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def h(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


class SyntheticStore:
    """All actors/body/IDs are test inventions; each connect opens a new SQLite handle."""
    def __init__(self, *, handler=False):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "TEST-library.sqlite3"
        self.connections = 0
        with self.connect() as db:
            columns = ["segments_json", "speaker_names_json", "speaker_profiles_json", "session_profile_json",
                       "analysis_config_json", "analysis_annotations_json", "revision_count", "analysis_revision",
                       "outline_json", "emotion_analysis_json"]
            db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY," + ",".join(c+" TEXT" for c in columns)+")")
            db.execute("CREATE TABLE speaker_registry(id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE application_metadata(key TEXT PRIMARY KEY,value TEXT)")
            db.execute("INSERT INTO application_metadata VALUES ('library_id','TEST-library')")
            db.execute("INSERT INTO library_items(id) VALUES ('TEST-conversation')")
            initialize_store(db)
            if not handler:
                db.executescript("""
                CREATE TABLE orchestration_runs(run_id TEXT PRIMARY KEY,state_json TEXT);
                CREATE TABLE orchestration_tasks(task_id TEXT PRIMARY KEY,run_id TEXT,state_json TEXT);
                CREATE TABLE orchestration_results(task_id TEXT,run_id TEXT,raw_json TEXT,state_json TEXT);
                """)
        self.store = AnalysisStore(self.path, self.connect)
        self.snapshot = {"TEST_fixture_only": True, "conversation_id": "TEST-conversation",
                         "input_hash": h({"TEST_input": 1}), "source_revision": 1, "analysis_revision": 1, "analysis": {},
                         "evidence": [{"evidence_id": "TEST-u1", "excluded": False, "text": "試験の発話",
                                       "valid_time": False, "start": None, "end": None}],
                         "segments": [{"id": "TEST-u1", "text": "試験の発話", "speaker": "TEST-A",
                                       "valid_time": False, "start": None, "end": None}]}
        self.sequence = 0

    def connect(self):
        self.connections += 1
        db = sqlite3.connect(self.path, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def close(self):
        with self.connect() as db:
            runs = db.execute("SELECT kind,status,COUNT(*) AS n FROM analysis_runs GROUP BY kind,status").fetchall()
        path = Path(self.temp.name)
        self.temp.cleanup()
        PROBES.append({"fixture_only": True, "connection_opens": self.connections,
                       "runs": [dict(row) for row in runs], "temporary_fixture_removed": not path.exists()})

    def run(self, suffix="1", *, legacy=False):
        return self.store.save(item_id="TEST-conversation", kind="ai_insights", snapshot=self.snapshot,
            result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True}, datasets={
                "correlations": (["n", "value_status"], [{"n": 0, "value_status": "observed"},
                    {"n": None, "value_status": "missing"}, {"value_status": "unprocessed"},
                    {"value_status": "excluded"}, {"value_status": "unknown"}])},
            request_id="TEST-analysis-"+suffix, input_fingerprint=digest(self.snapshot),
            source_revision=1, analysis_revision=1, publish=False, table_format_version=None if legacy else 1)

    def descriptors(self, run, *, original=False, parents=()):
        snapshot, _result, manifest, content = self.store.verified_package(run["id"])
        name = "input.json" if original else "tables/correlations.json"
        artifact = next(a for a in self.store.artifacts(run["id"]) if a["name"] == name)
        key = {"library_id": "TEST-library", "store_run_id": run["id"], "artifact_id": artifact["id"], "output_name": name}
        source = {"target_type": "snapshot", "target_id": manifest["input_snapshot_id"], "version": "1",
                  "content_hash": h(snapshot), "hash_domain": "canonical-json-v1", "library_id": "TEST-library"}
        scope = {"scope_id": "TEST-scope", "mode": "dataset", "input_refs": [source],
                 "conversation_ids": ["TEST-conversation"], "member_ids": ["TEST-u1"], "context_ids": []}
        scope["manifest_hash"] = h(scope)
        native = connection_method_descriptor("pearson")
        producer = {"kind": "system" if original else "code", "actor_id": "TEST-capture" if original else "TEST-code",
                    "step_ids": []}
        raw_hash = "sha256:" + hashlib.sha256(content[name]).hexdigest()
        common = {"asset_key": key, "raw_byte_hash": raw_hash, "scope": scope, "producer": producer,
                  "meaning": {"definition_refs": [], "description": "TEST observed values", "status": "declared", "unit": "utterance"},
                  "schema": native["native_input_schema"] if original else
                    {"schema_id": "gurumoji.analysis-table", "version": 1, "schema_hash": h(CONNECTION_TABLE_SCHEMA)},
                  "adapter": native["native_adapter"] if original else {"adapter_id": "analysis-store-table", "version": "1"}}
        if original:
            asset = {**common, "source_ref": source}
        else:
            definition = {"target_type": "definition", "target_id": "TEST-definition", "version": "1",
                          "content_hash": h({"TEST_definition": True}), "hash_domain": "canonical-json-v1"}
            variables = [{"variable_id": name, "version": 1, "definition_hash": definition["content_hash"],
                          "value_type": "integer" if name == "n" else "string", "scale": "ratio" if name == "n" else "nominal",
                          "unit": "utterance", "value_domain": "TEST-only", "generation": producer,
                          "validity": "structural_checked", "definition_ref": definition} for name in ("n", "value_status")]
            asset = {**common, "contract_id": "gurumoji.analysis-asset-connection", "contract_version": 1,
                     "content_hash": raw_hash, "content_domain": "raw-bytes-v1", "kind": "observation_table",
                     "source_refs": [source], "method_id": "pearson", "method_version": native["method_version"],
                     "variables": variables, "parent_refs": list(parents) if parents else [source]}
        state = {"asset_key": key, "target_content_hash": raw_hash, "target_domain": "raw-bytes-v1",
                 "state_revision": 1, "policy_revision": 1, "status": "adopted",
                 "allowed_purposes": ["exploratory", "descriptive"], "send_policy": "local_only", "destinations": [],
                 "revoked": False, "review_refs": [], "reason": "TEST structural fixture, not human adoption",
                 "updated_at": "2026-10-08T00:00:00Z"}
        return asset, state

    def register(self, assets=(), originals=(), states=(), links=()):
        self.sequence += 1
        originals, states = list(originals), list(states)
        # Explicit TEST-only source policies; production never infers them.
        existing_sources = list(self.store._connection_index()[1].values()) + originals
        for asset in assets:
            for ref in asset["parent_refs"]:
                if ref["target_type"] != "snapshot" or any(o["source_ref"] == ref for o in existing_sources):
                    continue
                original, source_state = self.descriptors(self.store.get(asset["asset_key"]["store_run_id"]), original=True)
                if original["source_ref"] == ref:
                    originals.append(original); states.append(source_state); existing_sources.append(original)
        metadata = {"version": 1, "assets": list(assets), "originals": list(originals),
                    "states": states, "producer_links": list(links)}
        return self.store.save_connection_metadata(request_id=f"TEST-metadata-{self.sequence}",
            item_id="TEST-conversation", snapshot=self.snapshot, metadata=metadata)

    def request(self, asset, *, original=False, role="data_input"):
        native = connection_method_descriptor("pearson")
        slot = {"slot_id": "TEST-slot", "required": True, "min_items": 1, "max_items": 1, "roles": [role],
                "accept_kinds": [] if original else ["observation_table"], "accept_schemas": [asset["schema"]],
                "accept_units": ["utterance"], "scope_modes": ["dataset"], "actors": [asset["producer"]["kind"]],
                "adapter": asset["adapter"], "purposes": ["exploratory", "descriptive"], "max_bytes": 10000}
        if original: slot["accept_source_types"] = ["snapshot"]
        context = {"plan_id": "TEST-plan", "plan_version": 1, "plan_hash": h({"TEST_plan": 1}), "generation": 1,
                   "consumer_task_id": "TEST-consumer", "purpose": "exploratory", "destination": "local",
                   "scope_id": asset["scope"]["scope_id"], "scope_manifest_hash": asset["scope"]["manifest_hash"], "cancelled": False}
        selector = {"row_ids": [], "column_ids": [], "range_ref": None}; selector["selection_hash"] = h(selector)
        source = {"type": "original", "source_ref": asset["source_ref"]} if original else {
                  "type": "frozen", "asset_key": asset["asset_key"], "content_hash": asset["content_hash"], "content_domain": asset["content_domain"]}
        ref = {k: context[k] for k in ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id")}
        ref.update(slot_id=slot["slot_id"], input_ref_id="TEST-ref", role=role, selection="selected",
                   omission_reason=None, source=source, selector=selector)
        return {"slot": slot, "inputs": [ref], "context": context, "method_id": "pearson"}

    def parent(self, asset, request, status="succeeded", valid=True):
        execution, task = "TEST-execution", "TEST-producer"
        asset.update(execution_run_id=execution, producer_task_id=task)
        identity = {k: request["context"][k] for k in ("plan_id", "plan_version", "plan_hash", "generation")}
        raw = {"TEST_fixture_only": True}
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO orchestration_runs VALUES (?,?)", (execution, canonical({"asset_plan_identity": identity}).decode()))
            db.execute("INSERT OR REPLACE INTO orchestration_tasks VALUES (?,?,?)", (task, execution, canonical({
                "task_id": task, "run_id": execution, "generation": 1, "status": status}).decode()))
            db.execute("DELETE FROM orchestration_results WHERE task_id=?", (task,))
            db.execute("INSERT INTO orchestration_results VALUES (?,?,?,?)", (task, execution, canonical(raw).decode(),
                canonical({"validation_status": "valid" if valid else "quarantined", "raw_hash": h(raw),
                           "task_id": task, "run_id": execution}).decode()))
        return {**identity, "execution_run_id": execution, "producer_task_id": task,
                "output_name": asset["asset_key"]["output_name"], "asset_key": asset["asset_key"]}


class AssetBindingTests(unittest.TestCase):
    def setUp(self):
        self.f = SyntheticStore(); self.addCleanup(self.f.close)
        self.run = self.f.run(); self.asset, self.state = self.f.descriptors(self.run)

    def bind(self, request=None):
        return self.f.store.bind_asset_inputs(**(request or self.f.request(self.asset)))

    def test_01_different_runs_same_output_remain_explicit_choices(self):
        a2, s2 = self.f.descriptors(self.f.run("2"))
        self.f.register([self.asset, a2], states=[self.state, s2])
        self.assertEqual(len(self.f.store.list_assets(output_name="tables/correlations.json")), 2)
        result = self.bind()
        self.assertEqual(result["decision"], "unsupported")
        self.assertTrue(result["content_resolution"]); self.assertFalse(result["execution_enabled"])
        bad = self.f.request(self.asset); bad["inputs"][0]["source"]["content_hash"] = h("wrong")
        self.assertEqual(self.bind(bad)["reason"], "content_target_mismatch")
        bad = self.f.request(self.asset); bad["inputs"][0]["source"]["asset_key"] = {
            **self.asset["asset_key"], "library_id": "TEST-foreign"}
        self.assertEqual(self.bind(bad)["reason"], "foreign_library")

    def test_02_duplicate_choice_identity_cannot_be_redefined(self):
        self.f.register([self.asset], states=[self.state])
        changed = copy.deepcopy(self.asset); changed["meaning"]["description"] = "changed meaning"
        with self.assertRaises(AssetBindingError): self.f.register([changed])
        self.assertEqual(self.f.store.list_assets()[0], self.asset)

    def test_03_all_four_roles_dependency_and_capability_are_distinct(self):
        self.f.register([self.asset], states=[self.state])
        for role in ("data_input", "selection_basis", "evidence_context", "parameter_source"):
            request = self.f.request(self.asset, role=role)
            with self.subTest(role=role):
                self.assertEqual(self.bind(request)["decision"], "unsupported")
                request["inputs"][0].pop("source")
                self.assertEqual(self.bind(request)["decision"], "needs_input")

    def test_04_selected_optional_waits_omitted_has_no_binding(self):
        self.f.register([self.asset], states=[self.state])
        request = self.f.request(self.asset); request["slot"].update(required=False, min_items=0)
        request["inputs"][0].pop("source")
        self.assertEqual(self.bind(request)["decision"], "needs_input")
        request["inputs"][0].update(selection="omitted", omission_reason="TEST-explicit")
        request["inputs"][0].pop("selector")
        result = self.bind(request); self.assertEqual(result["decision"], "needs_input"); self.assertEqual(result["bindings"], [])
        request["slot"]["required"] = True; request["slot"]["min_items"] = 1
        self.assertEqual(self.bind(request)["reason"], "illegal_omission")

    def test_05_original_snapshot_exact_version_and_domain(self):
        original, state = self.f.descriptors(self.run, original=True)
        self.f.register(originals=[original], states=[state])
        request = self.f.request(original, original=True)
        self.assertEqual(self.bind(request)["decision"], "eligible")
        for field, value in (("version", "2"), ("hash_domain", "raw-bytes-v1"), ("content_hash", h("changed"))):
            bad = copy.deepcopy(request); bad["inputs"][0]["source"]["source_ref"][field] = value
            with self.subTest(field=field): self.assertEqual(self.bind(bad)["decision"], "needs_input")
        bad = copy.deepcopy(request); bad["inputs"][0]["source"]["source_ref"]["target_type"] = "artifact"
        self.assertEqual(self.bind(bad)["decision"], "rejected")

    def test_06_from_step_requires_persisted_adopted_saved_parent(self):
        request = self.f.request(self.asset); link = self.f.parent(self.asset, request)
        self.f.register([self.asset], states=[self.state], links=[link])
        request["inputs"][0]["source"] = {"type": "from_step", "producer_task_id": "TEST-producer", "output_name": "tables/correlations.json"}
        self.assertEqual(self.bind(request)["decision"], "unsupported")
        identity = {k: request["context"][k] for k in ("plan_id", "plan_version", "plan_hash", "generation")}
        identity["plan_version"] = True
        with self.f.connect() as db:
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?",
                       (canonical({"asset_plan_identity": identity}).decode(), "TEST-execution"))
        self.assertEqual(self.bind(request)["reason"], "parent_plan_identity")
        self.f.parent(self.asset, request, status="queued")
        self.assertEqual(self.bind(request)["decision"], "needs_input")
        self.f.parent(self.asset, request, status="failed")
        self.assertEqual(self.bind(request)["decision"], "blocked")

    def test_07_parent_mapping_unknown_and_plan_generation_mismatch(self):
        self.f.register([self.asset], states=[self.state])
        request = self.f.request(self.asset)
        request["inputs"][0]["source"] = {"type": "from_step", "producer_task_id": "TEST-producer", "output_name": "tables/correlations.json"}
        self.assertEqual(self.bind(request)["reason"], "parent_mapping_unresolved")
        request["inputs"][0]["generation"] = True
        self.assertEqual(self.bind(request)["decision"], "rejected")

    def test_08_metadata_history_appends_keep_old_raw_payload(self):
        first = self.f.register([self.asset], states=[self.state])
        raw1 = self.f.store.verified_package(first["id"])[3]["result.json"]
        new = copy.deepcopy(self.state); new.update(state_revision=2, reason="TEST status receipt")
        second = self.f.register(states=[new])
        self.assertNotEqual(raw1, self.f.store.verified_package(second["id"])[3]["result.json"])
        self.assertEqual(raw1, self.f.store.verified_package(first["id"])[3]["result.json"])
        self.assertEqual(self.f.store.list_assets()[0]["content_hash"], self.asset["content_hash"])
        new["state_revision"] = 3; new["target_content_hash"] = h("changed content")
        with self.assertRaises(AssetBindingError): self.f.register(states=[new])
        body = {"id": "TEST-candidate", "definition": "テーマ", "input": h({"TEST":1}), "scope": "TEST-scope"}
        before = h({"domain": "ta-candidate-content-v1", "content": body})
        wrapper = {"content": body, "human_records": [], "receipts": [], "status": "draft"}
        old_raw = canonical(wrapper)
        wrapper.update(status="human_pending", human_records=[{"fixture_only": True, "TEST_HR": "not consent"}])
        self.assertEqual(before, h({"domain": "ta-candidate-content-v1", "content": wrapper["content"]}))
        self.assertNotEqual(old_raw, canonical(wrapper))
        changed = {**body, "definition": "new"}; self.assertNotEqual(before, h({"domain":"ta-candidate-content-v1","content":changed}))
        self.assertEqual(hashlib.sha256(canonical({"語":"テーマ"})).hexdigest(),
                         "6021cb228be0d308a9ae5e8c70d488cacb659f9f3fb2eea29e611b9c6cfe3980")
        self.assertNotEqual(h({"n":None}), h({}))
        self.assertNotEqual(h([1,2]), h([2,1]))

    def test_09_tamper_stops_without_recovery_or_publication(self):
        self.f.register([self.asset], states=[self.state])
        artifact = next(a for a in self.f.store.artifacts(self.run["id"]) if a["name"] == "tables/correlations.json")
        path = self.f.store.root / artifact["path"]; original_raw = path.read_bytes(); path.write_bytes(b"tampered")
        self.assertEqual(self.bind()["decision"], "rejected")
        self.assertEqual(path.read_bytes(), b"tampered")
        self.assertEqual(self.f.store.get(self.run["id"])["status"], "completed")
        path.write_bytes(original_raw)  # Isolate the next negative, not product recovery.
        manifest = next(a for a in self.f.store.artifacts(self.run["id"]) if a["name"] == "manifest.json")
        manifest_path = self.f.store.root / manifest["path"]; raw_manifest = manifest_path.read_bytes()
        manifest_path.write_bytes(raw_manifest + b" ")
        self.assertEqual(self.bind()["decision"], "rejected")
        self.assertEqual(manifest_path.read_bytes(), raw_manifest + b" ")
        manifest_path.write_bytes(raw_manifest)
        with self.f.connect() as db:
            db.execute("UPDATE analysis_artifacts SET bytes=bytes+1 WHERE id=?", (artifact["id"],))
        self.assertEqual(self.bind()["decision"], "rejected")
        self.assertEqual(path.read_bytes(), original_raw)

    def test_10_multi_parent_local_only_and_purpose_intersection(self):
        parent, parent_state = self.f.descriptors(self.f.run("parent"))
        parent_state["allowed_purposes"] = ["descriptive"]
        self.asset["parent_refs"] = [{"target_type": "artifact", "target_id": parent["asset_key"]["artifact_id"],
             "version": "1", "content_hash": parent["content_hash"], "hash_domain": parent["content_domain"], "library_id": "TEST-library"}]
        self.f.register([self.asset, parent], states=[self.state, parent_state])
        self.assertEqual(self.bind()["reason"], "purpose_intersection")
        request = self.f.request(self.asset); request["context"].update(purpose="descriptive", destination="TEST-cloud")
        self.assertEqual(self.bind(request)["reason"], "destination_intersection")

    def test_11_state_revoke_drop_permission_and_no_widening(self):
        self.f.register([self.asset], states=[self.state])
        update = copy.deepcopy(self.state); update.update(state_revision=2, policy_revision=2, revoked=True)
        self.f.register(states=[update]); self.assertEqual(self.bind()["decision"], "blocked")
        update.update(state_revision=3, policy_revision=3, revoked=False)
        with self.assertRaises(AssetBindingError): self.f.register(states=[update])
        for suffix, patch, reason in (("drop", {"allowed_purposes":[]}, "purpose_intersection"),
                                     ("prohibit", {"send_policy":"prohibited"}, "destination_intersection")):
            asset, state = self.f.descriptors(self.f.run("policy-"+suffix))
            self.f.register([asset], states=[state])
            narrowed = copy.deepcopy(state); narrowed.update(state_revision=2, policy_revision=2, **patch)
            self.f.register(states=[narrowed])
            with self.subTest(policy=suffix):
                self.assertEqual(self.bind(self.f.request(asset))["reason"], reason)

    def test_12_pre_adoption_rereads_state_and_old_receipt_stays_old(self):
        self.f.register([self.asset], states=[self.state]); request = self.f.request(self.asset)
        receipt = self.bind(request)
        self.assertEqual(self.f.store.revalidate_asset_inputs(receipt, **request)["decision"], "unsupported")
        malformed = copy.deepcopy(receipt); malformed["bindings"] = [{}]
        self.assertEqual(self.f.store.revalidate_asset_inputs(malformed, **request)["decision"], "blocked")
        update = copy.deepcopy(self.state); update.update(state_revision=2, reason="TEST new revision")
        self.f.register(states=[update])
        self.assertEqual(self.f.store.revalidate_asset_inputs(receipt, **request)["decision"], "blocked")
        self.assertEqual(receipt["bindings"][0]["checked_state_revision"], 1)
        changed_again = copy.deepcopy(update); changed_again.update(state_revision=3, reason="TEST during check")
        def late_assess(envelopes):
            self.f.register(states=[changed_again])
            return {"decision":"unsupported", "reason":"typed_consumer_unimplemented"}
        current = self.f.store.bind_asset_inputs(**request, assess=late_assess)
        self.assertEqual(current["decision"], "blocked")
        self.assertEqual(current["reason"], "state_changed_during_resolution")

    def test_13_unknown_human_record_is_pending_not_adoption(self):
        self.state["review_refs"] = [{"target_type": "artifact", "target_id": "TEST-HR-not-real-consent",
             "version": "1", "content_hash": h({"TEST_HR": True}), "hash_domain": "human-record-v1", "library_id": "TEST-library"}]
        self.f.register([self.asset], states=[self.state])
        self.assertEqual(self.bind()["decision"], "human_pending")
        self.assertEqual(self.bind()["payloads"], [])

    def test_14_schema_scope_unit_adapter_actor_and_bool_rejected_or_unsupported(self):
        for field, value in (("schema", {"schema_id": "unknown", "version": True, "schema_hash": h({})}),
                             ("content_domain", "ta-candidate-content-v1"), ("kind", "embedding_matrix"),
                             ("kind", []), ("content_domain", True),
                             ("adapter", {"adapter_id": "unknown", "version": "1"}),
                             ("contract_version", True)):
            bad = copy.deepcopy(self.asset); bad[field] = value
            with self.subTest(field=field):
                with self.assertRaises((AssetBindingError, ValueError)): self.f.register([bad])
        self.f.register([self.asset], states=[self.state])
        for field, value in (("scope_id", "foreign"), ("scope_manifest_hash", h("wrong"))):
            request = self.f.request(self.asset); request["context"][field] = value
            with self.subTest(field=field): self.assertEqual(self.bind(request)["decision"], "rejected")

    def test_15_selector_exact_ids_hash_and_payload_cap(self):
        self.f.register([self.asset], states=[self.state]); request = self.f.request(self.asset)
        selector = request["inputs"][0]["selector"]; selector["row_ids"] = ["correlations:1"]; selector["column_ids"] = ["n"]
        selector["selection_hash"] = h({k: v for k, v in selector.items() if k != "selection_hash"})
        result = self.bind(request); self.assertEqual(result["payloads"][0]["value"]["rows"][0]["values"], {"n": 0})
        self.assertEqual(result["payloads"][0]["value"]["columns"][0]["null_count"], 0)
        self.assertEqual(result["payloads"][0]["value"]["columns"][0]["absent_count"], 0)
        request["slot"]["max_bytes"] = 10
        self.assertEqual(self.bind(request)["decision"], "needs_input")
        request["slot"]["max_bytes"] = 10000; selector["row_ids"] = ["absent"]; selector["selection_hash"] = h({k: v for k, v in selector.items() if k != "selection_hash"})
        self.assertEqual(self.bind(request)["reason"], "selector_id")

    def test_16_null_missing_statuses_preserved_on_independent_reload(self):
        self.f.register([self.asset], states=[self.state])
        other = AnalysisStore(self.f.path, self.f.connect)
        result = other.bind_asset_inputs(**self.f.request(self.asset))
        rows = result["payloads"][0]["value"]["rows"]
        self.assertEqual(rows[0]["values"]["n"], 0); self.assertIsNone(rows[1]["values"]["n"])
        self.assertNotIn("n", rows[2]["values"])
        self.assertEqual([r["values"]["value_status"] for r in rows], ["observed", "missing", "unprocessed", "excluded", "unknown"])
        self.assertGreater(self.f.connections, 10)

    def test_17_legacy_read_table_does_not_infer_and_failed_projection_separate(self):
        run = self.f.run("legacy", legacy=True)
        self.f.store.verified_package(run["id"])
        with self.assertRaises(StoreConflict): self.f.store.read_table(run["id"], "correlations")
        with self.f.connect() as db: db.execute("UPDATE analysis_runs SET vault_status='failed' WHERE id=?", (self.run["id"],))
        self.f.register([self.asset], states=[self.state])
        self.assertEqual(self.bind()["decision"], "unsupported")

    def test_18_cycles_state_domain_and_versions_fail_closed(self):
        bad = copy.deepcopy(self.asset); bad["parent_refs"] = [{"target_type": "artifact",
            "target_id": self.asset["asset_key"]["artifact_id"], "version": "1", "content_hash": self.asset["content_hash"],
            "hash_domain": "raw-bytes-v1", "library_id": "TEST-library"}]
        with self.assertRaises(AssetBindingError): self.f.register([bad], states=[self.state])
        bad_state = copy.deepcopy(self.state); bad_state["target_domain"] = "ta-theme-content-v1"
        with self.assertRaises(AssetBindingError): self.f.register([self.asset], states=[bad_state])
        scope = copy.deepcopy(self.asset); scope["scope"]["member_ids"] = ["TEST-foreign-utterance"]
        scope["scope"]["manifest_hash"] = h({k:v for k,v in scope["scope"].items() if k != "manifest_hash"})
        with self.assertRaises(AssetBindingError): self.f.register([scope], states=[self.state])

    def test_19_actual_registry_adapter_seam_no_transport_or_adoption(self):
        original, state = self.f.descriptors(self.run, original=True)
        self.f.register(originals=[original], states=[state])
        catalog = ExpertCatalog(root=ROOT/"docs/program-vault", local_root=Path(self.f.temp.name)/"empty")
        resolve, revalidate = make_asset_binding_adapters(store=self.f.store, expert_registry=ExpertAgentRegistry(catalog))
        request = self.f.request(original, original=True); request.update(expert_id="exp-correlation", step_id="cor-p2",
            actor={"kind": "code", "actor_id": "TEST-code", "step_ids": ["cor-p2"]})
        result = resolve(**request)
        self.assertEqual(result["decision"], "eligible", result)
        self.assertFalse(result["execution_enabled"]); self.assertFalse(result["adoption_performed"])
        self.assertEqual(revalidate(result, **request)["decision"], "eligible")
        request["actor"]["kind"] = "researcher"
        rejected = resolve(**request)
        self.assertEqual(rejected["decision"], "rejected")
        self.assertEqual(rejected["payloads"], [])

    def test_20_cancellation_permissions_missing_and_duplicate_id(self):
        self.f.register([self.asset])
        self.assertEqual(self.bind()["decision"], "needs_input")
        request = self.f.request(self.asset); request["context"]["cancelled"] = True
        self.assertEqual(self.bind(request)["decision"], "blocked")
        self.f.register(states=[self.state])
        request = self.f.request(self.asset); request["inputs"].append(copy.deepcopy(request["inputs"][0]))
        self.assertEqual(self.bind(request)["decision"], "rejected")
        request["inputs"][-1]["input_ref_id"] = "TEST-ref-2"
        self.assertEqual(self.bind(request)["reason"], "slot_cardinality")
        request["inputs"].pop(); request["slot"].update(min_items=2, max_items=2)
        self.assertEqual(self.bind(request)["decision"], "needs_input")


class TablePilotHandlerTests(unittest.TestCase):
    """Preregistered T01-T18; real Handler/Store, private SQLite, network zero.

    Saved policies below are explicit TEST engineering states, never human consent.
    No agent is called; seams only mutate a result or trigger a real cancellation/policy.
    """
    def setUp(self):
        from gurumoji.analysis_orchestration import AnalysisOrchestrationService
        from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
        self.f = SyntheticStore(handler=True)
        self.addCleanup(self.f.close)
        self.item = {"id": "TEST-conversation"}
        statuses = ["observed", "observed", "missing", "unprocessed", "unknown", "excluded"]
        segments = [{"id": f"TEST-u{i}", "text": f"Invented utterance {i}",
                     "speaker": "TEST-A", "excluded": status == "excluded", "valid_time": False}
                    for i, status in enumerate(statuses)]
        self.f.snapshot.update(analysis={"segments": segments}, segments=segments)
        def no_agent(*args, **kwargs):
            raise AssertionError("No AI call is authorized")
        self.runner = run_orchestration_method
        self.service = AnalysisOrchestrationService(connect=self.f.connect,
            find_item=lambda _id: self.item, snapshot_builder=lambda _item: copy.deepcopy(self.f.snapshot),
            agent_runner=no_agent, method_runner=self.runner, schedule=False, table_store=self.f.store)
        self.run = self.service.start("TEST-conversation", {"model": "TEST-no-model", "max_tasks": 50})
        with self.f.connect() as db:
            self.f.snapshot = self.service._initial(db, self.run["initial_id"])
        self.fields = ["utterance_id", "conversation_id", "value_status", "n", "category"]
        self.values = [{"utterance_id": f"TEST-u{i}", "conversation_id": "TEST-conversation",
                        "value_status": status, "n": (0 if i == 0 else 2) if i in (0, 1, 5) else None,
                        "category": ("A" if i == 0 else "B") if i in (0, 1, 5) else None}
                       for i, status in enumerate(statuses)]
        saved = self.f.store.save(item_id="TEST-conversation", kind="ai_insights", snapshot=self.f.snapshot,
            result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True},
            datasets={"correlations": (self.fields, self.values)}, request_id="TEST-source",
            input_fingerprint=digest(self.f.snapshot), source_revision=1, analysis_revision=1, publish=False)
        self.asset, self.state = self.f.descriptors(saved)
        original, original_state = self.f.descriptors(saved, original=True)
        scope = self.asset["scope"]
        scope["member_ids"] = [e["evidence_id"] for e in self.f.snapshot["evidence"] if not e["excluded"]]
        scope["context_ids"] = [e["evidence_id"] for e in self.f.snapshot["evidence"] if e["excluded"]]
        scope["manifest_hash"] = h({k: v for k, v in scope.items() if k != "manifest_hash"})
        original["scope"] = copy.deepcopy(scope)
        template = self.asset["variables"][0]
        self.asset["variables"] = [{**copy.deepcopy(template), "variable_id": field,
            "value_type": "integer" if field == "n" else "string",
            "scale": "ratio" if field == "n" else "nominal"} for field in self.fields]
        self.f.register([self.asset], originals=[original], states=[self.state, original_state])
        self.source_table = self.f.store.read_table(saved["id"], "correlations")
        self.source_id = saved["id"]
        self.saved_tasks = []

    def request(self, method, assets=None, parameters=None):
        from gurumoji.analysis_method_registry import table_pilot_slot
        assets = assets or [self.asset]
        params = {"table_projection": {"columns": self.fields,
                    "row_ids": [r["row_id"] for r in self.source_table["rows"]]},
                  "table_aggregate": {"value_column": "n", "status_column": "value_status",
                    "operation": "count", "group_by": "utterance_id", "unit": "utterance"},
                  "table_join": {"key": "utterance_id"},
                  "table_frequency": {"value_column": "n", "status_column": "value_status"},
                  "table_crosstab": {"row_column": "n", "column_column": "category", "status_column": "value_status"}}
        context = {"plan_id": self.run["run_id"], "plan_version": 1,
            "plan_hash": h({"run_id": self.run["run_id"], "input_hash": self.run["input_hash"]}),
            "generation": 1, "consumer_task_id": "TEST-consumer", "purpose": "exploratory",
            "destination": "local", "scope_id": assets[0]["scope"]["scope_id"],
            "scope_manifest_hash": assets[0]["scope"]["manifest_hash"], "cancelled": False}
        inputs = []
        for index, asset in enumerate(assets):
            selector = {"row_ids": [], "column_ids": [], "range_ref": None}
            selector["selection_hash"] = h(selector)
            ref = {k: context[k] for k in ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id")}
            ref.update(slot_id="table", input_ref_id=f"TEST-ref-{index}", role="data_input", selection="selected",
                omission_reason=None, selector=selector, source={"type": "frozen", "asset_key": asset["asset_key"],
                "content_hash": asset["content_hash"], "content_domain": "raw-bytes-v1"})
            inputs.append(ref)
        return {"version": "table-pilot-1", "actor": "code", "parameters": copy.deepcopy(parameters or params[method]),
                "bindings": {"slot": table_pilot_slot(method), "inputs": inputs, "context": context}}

    def task(self, method, request=None):
        return self.service.register_table_pilot("TEST-conversation", self.run["run_id"], method,
                                                request or self.request(method))

    def state_of(self, task):
        with self.f.connect() as db:
            return json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",
                                         (task["task_id"],)).fetchone()[0])

    def raw_of(self, task):
        with self.f.connect() as db:
            row = db.execute("SELECT raw_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
            return json.loads(row[0]) if row else None

    def execute(self, method, request=None):
        task = self.task(method, request)
        self.service._execute(self.run["run_id"], task["task_id"])
        self.service._validate_received(self.run["run_id"], task["task_id"])
        state = self.state_of(task)
        self.assertEqual(state["status"], "succeeded", state)
        self.assertFalse(state["adoption_performed"])
        self.saved_tasks.append(state)
        return state, self.raw_of(task)

    def reusable(self, state):
        # A new Store instance and new connections resolve the immutable package.
        fresh = AnalysisStore(self.f.path, self.f.connect)
        asset = fresh.table_pilot_output_descriptor(state["table_store_run_id"])
        policy = {**copy.deepcopy(self.state), "asset_key": asset["asset_key"],
                  "target_content_hash": asset["content_hash"]}
        self.f.register([asset], states=[policy])
        return asset

    def reject_prepare(self, method, request):
        with self.assertRaises((ValueError, AssetBindingError)):
            self.f.store.prepare_table_pilot(method, request, expected_snapshot=self.f.snapshot)

    def padded_asset(self, padding):
        """Actual private Store metadata, not a mocked resolved wrapper."""
        saved = self.f.store.save(item_id="TEST-conversation", kind="ai_insights", snapshot=self.f.snapshot,
            result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True},
            datasets={"correlations": (self.fields, self.values)}, request_id=f"TEST-wide-{padding}",
            input_fingerprint=digest(self.f.snapshot), source_revision=1, analysis_revision=1, publish=False)
        asset, state = self.f.descriptors(saved)
        asset["scope"] = copy.deepcopy(self.asset["scope"])
        asset["variables"] = copy.deepcopy(self.asset["variables"])
        asset["variables"][0]["value_domain"] = "x" * padding
        self.f.register([asset], states=[state])
        return asset

    def test_T01_registered_five_step_saved_fresh_chain(self):
        projection = self.request("table_projection")
        projection["parameters"]["row_ids"] = [r["row_id"] for r in self.source_table["rows"]
                                                 if r["values"]["utterance_id"] != "TEST-u1"]
        p, p_raw = self.execute("table_projection", projection); pa = self.reusable(p)
        a, a_raw = self.execute("table_aggregate", self.request("table_aggregate", [pa])); aa = self.reusable(a)
        j, j_raw = self.execute("table_join", self.request("table_join", [pa, aa])); ja = self.reusable(j)
        for method in ("table_frequency", "table_crosstab"):
            end, raw = self.execute(method, self.request(method, [ja]))
            self.assertEqual(raw["population"]["excluded_ids"], ["TEST-u1", "TEST-u5"])
            self.assertEqual(raw["manifest"]["calculation_denominator"], 1)
            with self.assertRaises(ValueError):
                self.f.store.table_pilot_output_descriptor(end["table_store_run_id"])
        self.assertEqual(p_raw["population"]["observed_zero_ids"], ["TEST-u0"])
        self.assertEqual(a_raw["population"]["observed_zero_ids"], ["TEST-u0"])
        self.assertEqual(j_raw["population"]["observed_zero_ids"], ["TEST-u0"])
        self.assertEqual(j_raw["population"]["denominator"], 4)
        for state in (p, a, j):
            snap, result, _, _ = self.f.store.verified_package(state["table_store_run_id"])
            self.assertEqual(snap, {**self.f.snapshot, "library_id": "TEST-library"})
            self.assertEqual(result["parameters"]["adoption_state"], "unanswered")
            table = AnalysisStore(self.f.path, self.f.connect).read_table(state["table_store_run_id"], "table")
            self.assertEqual(len(table["rows"]), 6)
            self.assertEqual(next(r["values"] for r in table["rows"] if r["values"]["utterance_id"] == "TEST-u1")["value_status"], "excluded")

    def test_T02_projection_identity_and_invalid_selection(self):
        _, raw = self.execute("table_projection")
        self.assertEqual(raw["datasets"]["table"]["rows"][0]["conversation_id"], "TEST-conversation")
        for ids in ([], ["absent"], [self.source_table["rows"][0]["row_id"]] * 2):
            req = self.request("table_projection"); req["parameters"]["row_ids"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                if ids == ["absent"]:
                    self.f.store.prepare_table_pilot("table_projection", req, expected_snapshot=self.f.snapshot)
                    from gurumoji.research_analysis import run_table_pilot
                    prepared = self.f.store.prepare_table_pilot("table_projection", req, expected_snapshot=self.f.snapshot)
                    run_table_pilot("table_projection", prepared["tables"], req["parameters"])
                else: self.task("table_projection", req)

    def test_T03_indicator_not_measure_zero_and_duplicate_utterance(self):
        _, raw = self.execute("table_aggregate")
        by_id = {r["utterance_id"]: r for r in raw["datasets"]["table"]["rows"]}
        self.assertEqual(by_id["TEST-u0"]["count"], 1)
        for uid in ("TEST-u2", "TEST-u3", "TEST-u4", "TEST-u5"):
            self.assertIsNone(by_id[uid]["count"])
        from gurumoji.research_analysis import run_table_pilot
        prepared = self.f.store.prepare_table_pilot("table_aggregate", self.request("table_aggregate"), expected_snapshot=self.f.snapshot)
        prepared["tables"][0]["table"]["rows"][1]["values"]["utterance_id"] = "TEST-u0"
        with self.assertRaises(ValueError): run_table_pilot("table_aggregate", prepared["tables"], prepared["request"]["parameters"])

    def test_T04_join_fresh_parents_preserves_variable_zero(self):
        p, _ = self.execute("table_projection"); pa = self.reusable(p)
        a, _ = self.execute("table_aggregate"); aa = self.reusable(a)
        _, raw = self.execute("table_join", self.request("table_join", [pa, aa]))
        row = next(r for r in raw["datasets"]["table"]["rows"] if r["utterance_id"] == "TEST-u0")
        self.assertEqual((row["n"], row["count"]), (0, 1))
        self.assertEqual(raw["population"]["observed_zero_ids"], ["TEST-u0"])
        original = self.f.store.verified_package(a["table_store_run_id"])[1]
        self.assertEqual(original["population"]["observed_zero_ids"], ["TEST-u0"])

    def test_T05_join_rejects_nonunique_unmatched_status_and_collision(self):
        from gurumoji.research_analysis import run_table_pilot
        p, _ = self.execute("table_projection"); pa = self.reusable(p)
        a, _ = self.execute("table_aggregate"); aa = self.reusable(a)
        req = self.request("table_join", [pa, aa]); prepared = self.f.store.prepare_table_pilot("table_join", req, expected_snapshot=self.f.snapshot)
        for kind in ("duplicate", "empty", "nonstring", "unmatched", "status", "conversation", "collision"):
            tables = copy.deepcopy(prepared["tables"]); right = tables[1]["table"]
            if kind == "duplicate": right["rows"].append(copy.deepcopy(right["rows"][0])); right["row_count"] += 1
            elif kind in ("empty", "nonstring", "unmatched"):
                right["rows"][0]["values"]["utterance_id"] = {"empty": "", "nonstring": 7, "unmatched": "TEST-foreign"}[kind]
            elif kind == "status": right["rows"][0]["values"]["value_status"] = "missing"
            elif kind == "conversation": right["rows"][0]["values"]["conversation_id"] = "TEST-other"
            else: tables[1] = copy.deepcopy(tables[0])
            with self.subTest(kind=kind), self.assertRaises(ValueError): run_table_pilot("table_join", tables, req["parameters"])

    def test_T06_frequency_population_and_typed_zero(self):
        _, raw = self.execute("table_frequency")
        self.assertEqual(raw["population"], {"included_ids": [f"TEST-u{i}" for i in range(5)], "excluded_ids": ["TEST-u5"],
            "missing_ids": ["TEST-u2"], "unprocessed_ids": ["TEST-u3"], "unknown_ids": ["TEST-u4"],
            "observed_zero_ids": ["TEST-u0"], "denominator": 5})
        self.assertEqual([(r["category"], r["count"]) for r in raw["datasets"]["table"]["rows"]], [(0, 1), (2, 1)])
        from gurumoji.research_analysis import run_table_pilot
        prepared = self.f.store.prepare_table_pilot("table_frequency", self.request("table_frequency"), expected_snapshot=self.f.snapshot)
        table = prepared["tables"][0]
        variable = next(v for v in table["variables"] if v["variable_id"] == "n"); variable["value_type"] = "boolean"
        for row in table["table"]["rows"]:
            if row["values"]["n"] is not None: row["values"]["n"] = False
        next(c for c in table["table"]["columns"] if c["name"] == "n")["observed_types"] = ["boolean", "null"]
        pure = run_table_pilot("table_frequency", [table], prepared["request"]["parameters"])
        self.assertEqual(pure["population"]["observed_zero_ids"], [])
        self.assertIs(pure["rows"][0]["category"], False)

    def test_T07_crosstab_zero_cells_and_source_ids(self):
        _, raw = self.execute("table_crosstab")
        rows = raw["datasets"]["table"]["rows"]
        self.assertEqual(len(rows), 4); self.assertEqual(sum(r["count"] for r in rows), 2)
        self.assertEqual(sum(r["count"] == 0 for r in rows), 2)
        for row in rows:
            self.assertEqual(len(row["source_utterance_ids"]), row["count"])
        self.assertEqual(raw["manifest"]["included_denominator"], 5)
        self.assertEqual(raw["manifest"]["calculation_ids"], ["TEST-u0", "TEST-u1"])

    def crosstab_asset(self, *, row_values=(0, 2, 4), row_type="integer"):
        values = copy.deepcopy(self.values)
        values[2].update(value_status="observed", category="A")
        for index, value in enumerate(row_values):
            values[index]["n"] = value
        values[5]["n"] = row_values[1]
        saved = self.f.store.save(item_id="TEST-conversation", kind="ai_insights", snapshot=self.f.snapshot,
            result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True},
            datasets={"correlations": (self.fields, values)}, request_id="TEST-crosstab-source-" + row_type,
            input_fingerprint=digest(self.f.snapshot), source_revision=1, analysis_revision=1, publish=False)
        asset, state = self.f.descriptors(saved)
        asset["scope"] = copy.deepcopy(self.asset["scope"])
        asset["variables"] = copy.deepcopy(self.asset["variables"])
        next(v for v in asset["variables"] if v["variable_id"] == "n").update(value_type=row_type, scale="nominal")
        self.f.register([asset], states=[state])
        return asset

    def test_T07b_crosstab_rejects_omitted_zero_cells_with_recomputed_hash(self):
        from gurumoji.analysis_core import fingerprint
        asset = self.crosstab_asset()
        task = self.task("table_crosstab", self.request("table_crosstab", [asset]))
        def omit_zero_cells(method, snapshot):
            raw = self.runner(method, snapshot)
            rows = raw["datasets"]["table"]["rows"]
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(r["count"] == 0 for r in rows), 3)
            for _ in range(2):
                rows.remove(next(r for r in rows if r["count"] == 0))
            self.assertEqual(len(rows), 4)
            raw["manifest"]["rows_hash"] = fingerprint(rows)
            return raw
        self.service.method_runner = omit_zero_cells
        self.service._execute(self.run["run_id"], task["task_id"])
        state = self.state_of(task)
        self.assertEqual(state["status"], "quarantined", state["error"])
        self.assertEqual(state["error"], "table_output_cells")
        self.assertNotIn("table_store_run_id", state)

    def test_T07c_complete_crosstab_typed_categories_survive_fresh_store(self):
        from gurumoji.analysis_core import fingerprint
        for row_type, values in (("integer", (0, 2, 4)), ("boolean", (False, True, False)),
                                 ("string", ("0", "2", "4"))):
            with self.subTest(row_type=row_type):
                asset = self.crosstab_asset(row_values=values, row_type=row_type)
                state, raw = self.execute("table_crosstab", self.request("table_crosstab", [asset]))
                rows = raw["datasets"]["table"]["rows"]
                expected_cells = {(canonical(v), canonical(c)) for v in values for c in ("A", "B")}
                self.assertEqual({(canonical(r["row_value"]), canonical(r["column_value"])) for r in rows}, expected_cells)
                self.assertEqual(len(rows), len(expected_cells))
                self.assertEqual(sum(r["count"] for r in rows), 3)
                self.assertEqual(raw["population"]["unprocessed_ids"], ["TEST-u3"])
                self.assertEqual(raw["population"]["unknown_ids"], ["TEST-u4"])
                self.assertEqual(raw["population"]["excluded_ids"], ["TEST-u5"])
                self.assertEqual(raw["population"]["observed_zero_ids"], ["TEST-u0"] if row_type == "integer" else [])
                fresh = AnalysisStore(self.f.path, self.f.connect)
                saved = fresh.verified_package(state["table_store_run_id"])[1]
                self.assertEqual(saved["datasets"], raw["datasets"])
                self.assertEqual(saved["population"], raw["population"])
                self.assertEqual(saved["manifest"]["rows_hash"], fingerprint(rows))
                table = fresh.read_table(state["table_store_run_id"], "table")
                self.assertEqual(table["row_count"], len(expected_cells))
                self.assertEqual([r["values"]["row_value"] for r in table["rows"]], [r["row_value"] for r in rows])
                self.assertEqual([r["values"]["count"] for r in table["rows"]], [r["count"] for r in rows])

    def test_T07d_crosstab_rejects_cells_types_counts_and_source_ids(self):
        from gurumoji.analysis_core import fingerprint
        asset = self.crosstab_asset()
        kinds = ("duplicate_zero", "duplicate_nonzero", "extra_zero", "extra_nonzero",
                 "bool_category", "string_category", "float_category", "null_category", "column_type",
                 "wrong_count", "negative_count", "bool_count", "float_count", "wrong_source",
                 "duplicate_source", "missing_source", "zero_source", "unprocessed_source", "excluded_source")
        for kind in kinds:
            with self.subTest(kind=kind):
                req = self.request("table_crosstab", [asset])
                req["bindings"]["context"]["consumer_task_id"] += "-" + kind
                req["bindings"]["inputs"][0]["consumer_task_id"] = req["bindings"]["context"]["consumer_task_id"]
                task = self.task("table_crosstab", req)
                def altered(method, snapshot):
                    raw = self.runner(method, snapshot)
                    rows = raw["datasets"]["table"]["rows"]
                    zero = next(r for r in rows if r["row_value"] == 0 and r["count"] == 0)
                    nonzero = next(r for r in rows if r["source_utterance_ids"] == ["TEST-u0"])
                    if kind in {"duplicate_zero", "duplicate_nonzero"}:
                        rows.append(copy.deepcopy(zero if kind == "duplicate_zero" else nonzero))
                    elif kind.startswith("extra_"):
                        extra = copy.deepcopy(zero if kind == "extra_zero" else nonzero)
                        extra["row_value"] = 99
                        rows.append(extra)
                    elif kind.endswith("_category"):
                        zero["row_value"] = {"bool_category": False, "string_category": "0",
                                             "float_category": 0.0, "null_category": None}[kind]
                    elif kind == "column_type": zero["column_value"] = False
                    elif kind.endswith("_count"):
                        nonzero["count"] = {"wrong_count": 2, "negative_count": -1,
                                            "bool_count": True, "float_count": 1.0}[kind]
                    elif kind == "wrong_source": nonzero["source_utterance_ids"] = ["TEST-u1"]
                    elif kind == "duplicate_source": nonzero["source_utterance_ids"] *= 2
                    elif kind == "missing_source": nonzero.update(count=0, source_utterance_ids=[])
                    elif kind == "zero_source": zero.update(count=1, source_utterance_ids=["TEST-u0"])
                    elif kind == "unprocessed_source": nonzero["source_utterance_ids"] = ["TEST-u3"]
                    elif kind == "excluded_source": nonzero["source_utterance_ids"] = ["TEST-u5"]
                    raw["manifest"]["rows_hash"] = fingerprint(rows)
                    return raw
                self.service.method_runner = altered
                self.service._execute(self.run["run_id"], task["task_id"])
                state = self.state_of(task)
                self.assertEqual(state["status"], "quarantined", state["error"])
                self.assertNotIn("table_store_run_id", state)
                self.assertTrue(state["error"].startswith("table_output_"), state["error"])
                raw = self.raw_of(task)
                self.assertEqual(raw["manifest"]["rows_hash"], fingerprint(raw["datasets"]["table"]["rows"]))

    def test_T08_source_hash_schema_unit_descriptor_tamper(self):
        for field in ("content_hash", "asset_key", "content_domain"):
            req = self.request("table_frequency"); source = req["bindings"]["inputs"][0]["source"]
            if field == "asset_key": source[field] = {**source[field], "output_name": "absent"}
            else: source[field] = h("wrong") if field == "content_hash" else "canonical-json-v1"
            with self.subTest(field=field): self.reject_prepare("table_frequency", req)
        p, _ = self.execute("table_projection"); descriptor = self.f.store.table_pilot_output_descriptor(p["table_store_run_id"])
        descriptor["variables"][0]["unit"] = "speaker"
        policy = {**self.state, "asset_key": descriptor["asset_key"], "target_content_hash": descriptor["content_hash"]}
        self.f.register([descriptor], states=[policy])
        self.reject_prepare("table_frequency", self.request("table_frequency", [descriptor]))

    def test_T09_actor_purpose_scope_and_request_utf8_boundary(self):
        from gurumoji.analysis_core import validate_table_pilot_request
        for field, value in (("actor", "AI"), ("purpose", "confirmatory"), ("scope_manifest_hash", h("wrong"))):
            req = self.request("table_frequency")
            if field == "actor": req[field] = value
            else: req["bindings"]["context"][field] = value
            with self.subTest(field=field): self.reject_prepare("table_frequency", req)
        req = self.request("table_projection")
        # Unknown native IDs are structurally legal; this exercises the real request boundary only.
        pad = "\u3042" * 100
        req["parameters"]["row_ids"] = [pad]
        target = 131072
        n = target - len(canonical(req)); req["parameters"]["row_ids"][0] += "x" * n
        self.assertEqual(len(canonical(req)), target)
        validate_table_pilot_request("table_projection", req)
        req["parameters"]["row_ids"][0] += "x"
        with self.assertRaises(ValueError): validate_table_pilot_request("table_projection", req)
        # Native bytes remain small; the full resolved wrappers have their own limit.
        small = self.padded_asset(1)
        prepared = self.f.store.prepare_table_pilot("table_frequency", self.request("table_frequency", [small]),
                                                   expected_snapshot=self.f.snapshot)
        padding = 1 + target - len(canonical(prepared["tables"]))
        at_limit = self.padded_asset(padding)
        prepared = self.f.store.prepare_table_pilot("table_frequency", self.request("table_frequency", [at_limit]),
                                                   expected_snapshot=self.f.snapshot)
        self.assertEqual(len(canonical(prepared["tables"])), target)
        over_limit = self.padded_asset(padding + 1)
        self.reject_prepare("table_frequency", self.request("table_frequency", [over_limit]))

    def test_T10_trusted_plan_consumer_slot_and_frozen_identity(self):
        task = self.task("table_frequency")
        self.assertEqual(task["intent"]["table_pilot"]["bindings"]["context"]["consumer_task_id"], task["task_id"])
        for change in ("plan", "slot", "latest", "parameter"):
            req = self.request("table_frequency")
            if change == "plan":
                req["bindings"]["context"]["plan_hash"] = h("other")
                req["bindings"]["inputs"][0]["plan_hash"] = h("other")
            elif change == "slot": req["bindings"]["slot"]["max_bytes"] += 1
            elif change == "latest": req["bindings"]["inputs"][0]["source"] = {"type": "latest"}
            else: req["parameters"]["unexpected"] = True
            with self.subTest(change=change), self.assertRaises(ValueError): self.task("table_frequency", req)

    def test_T11_received_raw_validation_tamper_and_nonfinite(self):
        for kind in ("schema", "ids", "hash", "finite", "byte"):
            req = self.request("table_frequency")
            req["bindings"]["context"]["consumer_task_id"] += "-" + kind
            req["bindings"]["inputs"][0]["consumer_task_id"] = req["bindings"]["context"]["consumer_task_id"]
            task = self.task("table_frequency", req)
            def altered(method, snapshot):
                raw = self.runner(method, snapshot)
                if kind == "schema": raw["method_version"] = "wrong"
                elif kind == "ids": raw["datasets"]["table"]["rows"][0]["source_utterance_ids"] = ["foreign"]
                elif kind == "finite": raw["datasets"]["table"]["rows"][0]["count"] = float("inf")
                elif kind == "byte": raw["TEST_oversized"] = "x" * 131072
                return raw
            self.service.method_runner = altered
            if kind == "hash":
                original_validate = self.service._validate_received
                def corrupt_receipt(run_id, task_id):
                    with self.f.connect() as db:
                        row = db.execute("SELECT state_json FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()
                        meta = json.loads(row[0]); meta["raw_hash"] = h("wrong")
                        db.execute("UPDATE orchestration_results SET state_json=? WHERE task_id=?", (json.dumps(meta), task_id))
                    return original_validate(run_id, task_id)
                self.service._validate_received = corrupt_receipt
            self.service._execute(self.run["run_id"], task["task_id"])
            state = self.state_of(task)
            self.assertIn(state["status"], {"quarantined", "failed"}, kind)
            self.assertNotIn("table_store_run_id", state)
            if kind == "hash": self.service._validate_received = original_validate

    def test_T12_store_restart_immutable_saved_metadata(self):
        state, raw = self.execute("table_aggregate")
        fresh = AnalysisStore(self.f.path, self.f.connect)
        first = fresh.verified_package(state["table_store_run_id"])
        self.assertEqual(first[1]["population"], raw["population"])
        self.assertEqual(first[0], {**self.f.snapshot, "library_id": "TEST-library"})
        self.assertEqual(first[1]["parameters"]["table_pilot_provenance"]["method_id"], "table_aggregate")
        self.reusable(state)
        self.assertEqual(first[3], fresh.verified_package(state["table_store_run_id"])[3])

    def test_T13_new_draft_does_not_redirect_old_binding(self):
        before = self.f.store.verified_package(self.source_id)[3]
        state, _ = self.execute("table_projection"); self.reusable(state)
        prepared = self.f.store.prepare_table_pilot("table_frequency", self.request("table_frequency"), expected_snapshot=self.f.snapshot)
        self.assertEqual(prepared["receipt"]["bindings"][0]["source"]["store_run_id"], self.source_id)
        self.assertEqual(before, self.f.store.verified_package(self.source_id)[3])

    def test_T14_cancel_before_during_after_kernel_never_save(self):
        # Three independent private fixture runs; cancellation changes the real Handler.
        for moment in ("before", "during", "after"):
            if moment != "before":
                self.f.close(); self._cleanups.pop(); self.setUp()
            task = self.task("table_frequency")
            if moment == "before": self.service.cancel("TEST-conversation", self.run["run_id"])
            if moment in {"during", "after"}:
                def cancel_runner(method, snapshot):
                    if moment == "during": self.service.cancel("TEST-conversation", self.run["run_id"])
                    raw = self.runner(method, snapshot)
                    if moment == "after": self.service.cancel("TEST-conversation", self.run["run_id"])
                    return raw
                self.service.method_runner = cancel_runner
            self.service._execute(self.run["run_id"], task["task_id"])
            if self.raw_of(task): self.service._validate_received(self.run["run_id"], task["task_id"])
            state = self.state_of(task)
            self.assertNotEqual(state["status"], "succeeded", moment)
            self.assertNotIn("table_store_run_id", state)

    def revoke(self):
        policy = {**self.state, "state_revision": 2, "policy_revision": 2, "revoked": True}
        self.f.register(states=[policy])

    def test_T15_current_policy_change_before_save_blocks(self):
        original_save = self.f.store.save
        # Metadata saves use the same Store, so trigger only the table request.
        def conditional_revoke(**kwargs):
            if kwargs.get("request_id", "").startswith("table-pilot:"):
                self.f.store.save = original_save
                self.revoke()
            return original_save(**kwargs)
        self.f.store.save = conditional_revoke
        task = self.task("table_frequency"); self.service._execute(self.run["run_id"], task["task_id"])
        state = self.state_of(task)
        self.assertEqual(state["status"], "quarantined")
        self.assertNotIn("table_store_run_id", state)

    def test_T16_read_policy_denial_distinct_from_raw_package(self):
        state, _ = self.execute("table_projection"); asset = self.reusable(state)
        fresh = AnalysisStore(self.f.path, self.f.connect); raw = fresh.verified_package(state["table_store_run_id"])[3]
        policy = {**self.state, "asset_key": asset["asset_key"], "target_content_hash": asset["content_hash"],
                  "state_revision": 2, "policy_revision": 2, "revoked": True}
        self.f.register(states=[policy])
        with self.assertRaises(ValueError): fresh.prepare_table_pilot("table_frequency", self.request("table_frequency", [asset]), expected_snapshot=self.f.snapshot)
        self.assertEqual(raw, fresh.verified_package(state["table_store_run_id"])[3])

    def test_T17_default_statistics_and_legacy_reference_unchanged(self):
        from gurumoji.analysis_method_registry import connection_method_descriptor
        for method in ("participation", "descriptive_statistics", "correlation", "group_statistics"):
            self.assertNotEqual(connection_method_descriptor(method).get("method_version"), "table-pilot-1")
        req = self.request("table_frequency"); req["bindings"]["inputs"][0]["source"] = {
            "type": "original", "source_ref": self.asset["source_refs"][0]}
        self.reject_prepare("table_frequency", req)

    def test_T18_unsupported_units_methods_AI_and_human_adoption(self):
        from gurumoji.analysis_core import validate_table_pilot_request
        for method in ("correlation", "TA", "HC", "embedding"):
            with self.subTest(method=method), self.assertRaises(ValueError): validate_table_pilot_request(method, {})
        for field, value in (("unit", "participant"), ("operation", "mean")):
            req = self.request("table_aggregate"); req["parameters"][field] = value
            with self.assertRaises(ValueError): self.task("table_aggregate", req)
        req = self.request("table_frequency"); req["human_records"] = [{"decision": "adopt"}]
        with self.assertRaises(ValueError): self.task("table_frequency", req)


if __name__ == "__main__":
    unittest.main()
