"""Independent Task6e8 acceptance: invented data, production archive/Store only.

Preparation tests prove fixture integrity and the existing carrier boundary.
They do not certify a final pooled Handler or UI candidate. No author fixture
or author test module is imported, and no scheduler/model/Vault is executed.
"""
import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_method_registry import connected_slot
from gurumoji.analysis_store import AnalysisStore, canonical, digest, initialize_store, safe_path, CONNECTION_TABLE_SCHEMA
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.services.analysis_unit_groups import pool_unit_tables
from gurumoji.research_analysis import run_connected_table


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def independent_browser_app(fixture):
    """Production templates/scripts + real scoped APIs on synthetic loopback.

    Unrelated shell bootstrap GETs return invented empty application metadata.
    Analysis options/plans/records/status all use the actual production routes.
    No scheduler is started: the test driver explicitly executes registered tasks.
    """
    from flask import Flask, jsonify, render_template
    from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
    root = Path(__file__).resolve().parents[1] / "src" / "gurumoji"
    app = Flask(__name__, static_folder=str(root / "static"), template_folder=str(root / "templates"))
    register_orchestration_routes(app, lambda: fixture.service, fixture.forbidden,
                                  table_reader=fixture.readonly_reader)

    @app.get("/")
    def index():
        return render_template("index.html", app_name="Gurumoji independent synthetic acceptance",
            app_version="TEST", local_llm_label="TEST no model", local_llm_short_label="TEST",
            runtime={"label": "synthetic acceptance", "native_file_dialog": False, "colab": False,
                     "source_path_example": "TEST invented media", "qwen_setup_note": "TEST no model"})

    @app.get("/api/<path:unused>")
    def bootstrap(unused):
        if unused == "jobs/active":
            return jsonify(job=None)
        if unused == "config":
            return jsonify(ok=True, runtime={"browser_upload": True})
        return jsonify(items=[], speakers=[], terms=[], runs=[], event_count=0, ready_count=0)

    return app


class IndependentPoolFixture:
    """Fresh private SQLite and immutable packages, never a real user database."""
    library = "TEST-independent-library"
    fields = ["utterance_id", "conversation_id", "value_status", "n"]

    def __init__(self, source_count=2, *, real_archive_stamp=False, silent_roster=False,
                 extra_observed=0, primary_observed_only=False, extra_other_observed=0):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-independent-pool-")
        self.path = Path(self.temp.name) / "TEST.sqlite3"
        self.snapshots, self.runs, self.assets, self.states = {}, {}, [], []
        self.sequence = 0
        with self.connect() as db:
            cols = ["source_name", "segments_json", "speaker_names_json", "speaker_profiles_json", "session_profile_json",
                    "analysis_config_json", "analysis_annotations_json", "revision_count", "analysis_revision",
                    "outline_json", "emotion_analysis_json"]
            db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY," + ",".join(c + (" INTEGER" if c in {"revision_count", "analysis_revision"} else " TEXT") for c in cols) + ")")
            db.execute("CREATE TABLE speaker_registry(id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE application_metadata(key TEXT PRIMARY KEY,value TEXT)")
            db.execute("INSERT INTO application_metadata VALUES ('library_id',?)", (self.library,))
            initialize_store(db)
            if real_archive_stamp:
                from gurumoji import transcript_preparation
                transcript_preparation.initialize(db)
        self.store = self.fresh()
        self.archive_source_stamp = None
        if real_archive_stamp:
            from gurumoji.services.analysis_archive import make_analysis_archive
            self.archive_source_stamp, self.archive_snapshot, *_ = make_analysis_archive(
                analysis_archive_store=lambda: self.store, database_connection=self.connect,
                row_segments=lambda row: json.loads(row["segments_json"] or "[]"),
                row_session_profile=lambda row: json.loads(row["session_profile_json"] or "{}"))
        self.service = AnalysisOrchestrationService(connect=self.connect,
            find_item=self.find_item,
            snapshot_builder=lambda item: copy.deepcopy(self.snapshots[item["id"]]),
            source_fingerprint=lambda item: self.archive_source_stamp(item) if self.archive_source_stamp else self.snapshots[item["id"]]["input_hash"],
            agent_runner=self.forbidden, method_runner=run_orchestration_method,
            schedule=False, table_store=self.store)
        for index in range(source_count):
            cid = "TEST-independent-C" + str(index)
            statuses = ["observed", "observed", "missing", "unknown", "unprocessed", "excluded"] if index == 0 else ["observed"]
            if index == 0:
                statuses = ["observed", "observed"] if primary_observed_only else statuses
                statuses += ["observed"] * extra_observed
            else:
                statuses += ["observed"] * extra_other_observed
            segments = [{"id": "TEST-u" + str(i), "text": "Invented acceptance utterance " + str(i),
                         "speaker": "TEST-S1", "excluded": status == "excluded", "valid_time": False,
                         "start": None, "end": None} for i, status in enumerate(statuses)]
            self.snapshots[cid] = {"TEST_fixture_only": True, "conversation_id": cid,
                "input_hash": fingerprint([cid, segments]), "source_revision": 1, "analysis_revision": 1,
                "analysis": {"segments": segments}, "segments": segments}
            with self.connect() as db:
                db.execute("INSERT INTO library_items(id,source_name,segments_json,speaker_names_json,speaker_profiles_json,"
                           "session_profile_json,analysis_config_json,analysis_annotations_json,revision_count,analysis_revision) "
                           "VALUES (?,?,?,'{}','{}','{}','{}','{}',1,1)", (cid, "TEST invented " + cid, canonical(segments).decode()))
                if silent_roster:
                    db.execute("UPDATE library_items SET speaker_names_json=? WHERE id=?",
                               (canonical({"TEST-S1": "TEST recorded", "TEST-SILENT": "TEST saved silent roster"}).decode(), cid))
            if self.archive_source_stamp:
                row = self.find_item(cid)
                from gurumoji.services.analysis_pipeline_adapters import make_staged_initial_builder
                # The snapshot serializer is real. Earlier checkpoints below are
                # explicitly invented and unmeasured; no NLP/model stage runs.
                analysis = {"TEST_fixture_only": True, "TEST_unmeasured_stages":
                    ["base", "linguistics", "statistics", "content"], "segments": segments,
                    "item": {"id": cid, "revision_count": 1, "analysis_revision": 1,
                             "session_profile": {}}, "config": {"codebook": []}}
                linguistics = {"engine": {"status": "TEST-unmeasured", "morphology":
                    "TEST-unmeasured", "syntax": "TEST-unmeasured"}, "coverage": {}}
                for name in ("pos_frequency", "term_frequency", "speaker_term_frequency",
                             "cooccurrence", "morphemes", "dependencies"):
                    linguistics[name] = []
                outputs = {"base": {"analysis": analysis, "experts": {"index": {}, "entries": {}}},
                    "linguistics": linguistics,
                    "statistics": {"statistics": {"engine": {"name": "TEST-unmeasured",
                        "version": "TEST", "status": "TEST-unmeasured"}}, "segments": []},
                    "content": {"local": {}, "TEST_unmeasured": True}}
                builder = make_staged_initial_builder(archive_snapshot=self.archive_snapshot,
                    archive_source_stamp=self.archive_source_stamp,
                    group_analysis_for_row=self.forbidden)
                self.snapshots[cid] = builder.run_stage("snapshot", row, outputs)
            run = self.service.start(cid, {"model": "TEST-no-model", "max_tasks": 50})
            with self.connect() as db:
                self.snapshots[cid] = self.service._initial(db, run["initial_id"])
            self.runs[cid] = run
            values = [{"utterance_id": s["id"], "conversation_id": cid, "value_status": status,
                       "n": (0 if i == 0 else 2) if index == 0 and status == "observed" else
                            4 if index == 1 and status == "observed" else
                            index if status == "observed" else None}
                      for i, (s, status) in enumerate(zip(segments, statuses))]
            saved = self.store.save(item_id=cid, kind="ai_insights", snapshot=self.snapshots[cid],
                result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True},
                datasets={"correlations": (self.fields, values)}, request_id="TEST-independent-source-" + str(index),
                input_fingerprint=digest(self.snapshots[cid]), source_revision=1, analysis_revision=1, publish=False)
            asset, original, state, original_state = self.descriptors(saved)
            self.metadata(cid, assets=[asset], originals=[original], states=[state, original_state])
            self.assets.append(asset)
            self.states.append(state)
        self.owner = next(iter(self.runs))
        self.run = self.runs[self.owner]

    @staticmethod
    def forbidden(*args, **kwargs):
        raise AssertionError("Model/AI execution is outside independent acceptance")

    def connect(self):
        db = sqlite3.connect(self.path, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def find_item(self, cid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM library_items WHERE id=?", (cid,)).fetchone()
            return dict(row) if row else None

    def fresh(self):
        return AnalysisStore(self.path, self.connect)

    @contextmanager
    def readonly_connect(self):
        db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        try:
            yield db
        finally:
            db.close()

    def readonly_reader(self):
        return AnalysisOrchestrationService(connect=self.readonly_connect, find_item=self.service.find_item,
            source_fingerprint=self.service.source_fingerprint, snapshot_builder=None, agent_runner=None,
            method_runner=None, schedule=False, table_store=AnalysisStore(self.path, self.readonly_connect))

    def close(self):
        self.temp.cleanup()

    def descriptors(self, saved):
        snapshot, _, manifest, content = self.store.verified_package(saved["id"])
        cid = snapshot.get("conversation_id") or snapshot["archive_snapshot"]["conversation_id"]
        ref = {"target_type": "snapshot", "target_id": manifest["input_snapshot_id"], "version": "1",
               "content_hash": fingerprint(snapshot), "hash_domain": "canonical-json-v1", "library_id": self.library}
        scope = {"scope_id": "TEST-source-scope:" + cid, "mode": "dataset",
                 "input_refs": [ref], "conversation_ids": [cid],
                 "member_ids": [e["evidence_id"] for e in snapshot["evidence"] if not e["excluded"]],
                 "context_ids": [e["evidence_id"] for e in snapshot["evidence"] if e["excluded"]]}
        scope["manifest_hash"] = fingerprint(scope)
        definition = {"target_type": "definition", "target_id": "TEST-exact-shared-definition", "version": "1",
                      "content_hash": fingerprint({"TEST_rule": "invented n; zero is observed"}), "hash_domain": "canonical-json-v1"}
        producer = {"kind": "code", "actor_id": "TEST-independent-producer", "step_ids": []}
        variables = [{"variable_id": f, "version": 1, "definition_hash": definition["content_hash"],
                      "definition_ref": definition, "value_type": "integer" if f == "n" else "string",
                      "scale": "ratio" if f == "n" else "nominal", "unit": "utterance", "value_domain": "TEST-only",
                      "generation": producer, "validity": "structural_checked"} for f in self.fields]
        from gurumoji.analysis_method_registry import connection_method_descriptor
        native = connection_method_descriptor("pearson")
        objects, states = [], []
        for name in ("tables/correlations.json", "input.json"):
            artifact = next(a for a in self.store.artifacts(saved["id"]) if a["name"] == name)
            key = {"library_id": self.library, "store_run_id": saved["id"], "artifact_id": artifact["id"], "output_name": name}
            raw_hash = "sha256:" + hashlib.sha256(content[name]).hexdigest()
            common = {"asset_key": key, "raw_byte_hash": raw_hash, "scope": copy.deepcopy(scope), "producer": producer,
                      "meaning": {"definition_refs": [], "description": "TEST complete invented population", "status": "declared", "unit": "utterance"}}
            obj = {**common, "schema": {"schema_id": "gurumoji.analysis-table", "version": 1,
                                       "schema_hash": fingerprint(CONNECTION_TABLE_SCHEMA)},
                   "adapter": {"adapter_id": "analysis-store-table", "version": "1"},
                   "contract_id": "gurumoji.analysis-asset-connection", "contract_version": 1,
                   "content_hash": raw_hash, "content_domain": "raw-bytes-v1", "kind": "observation_table",
                   "source_refs": [ref], "method_id": "pearson", "method_version": native["method_version"],
                   "variables": variables, "parent_refs": [ref]} if name != "input.json" else {
                       **common, "schema": native["native_input_schema"], "adapter": native["native_adapter"], "source_ref": ref}
            state = {"asset_key": key, "target_content_hash": raw_hash, "target_domain": "raw-bytes-v1",
                     "state_revision": 1, "policy_revision": 1, "status": "adopted", "allowed_purposes": ["exploratory"],
                     "send_policy": "local_only", "destinations": [], "revoked": False, "review_refs": [],
                     "reason": "TEST engineering fixture; no real researcher consent", "updated_at": "2026-10-09T00:00:00Z"}
            objects.append(obj)
            states.append(state)
        return objects[0], objects[1], states[0], states[1]

    def metadata(self, cid, *, assets=(), originals=(), states=()):
        self.sequence += 1
        return self.fresh().save_connection_metadata(request_id="TEST-independent-metadata-" + str(self.sequence),
            item_id=cid, snapshot=self.snapshots[cid], metadata={"version": 1, "assets": list(assets),
                "originals": list(originals), "states": list(states), "producer_links": []})

    def request(self, method, assets, parameters, scope=None):
        scope = scope or assets[0]["scope"]
        context = {"plan_id": self.run["run_id"], "plan_version": 1,
                   "plan_hash": fingerprint({"run_id": self.run["run_id"], "input_hash": self.run["input_hash"]}),
                   "generation": self.run["generation"], "consumer_task_id": "TEST-independent-consumer",
                   "purpose": "exploratory", "destination": "local", "scope_id": scope["scope_id"],
                   "scope_manifest_hash": scope["manifest_hash"], "cancelled": False}
        inputs = []
        for i, asset in enumerate(assets):
            selector = {"row_ids": [], "column_ids": [], "range_ref": None}
            selector["selection_hash"] = fingerprint(selector)
            ref = {k: context[k] for k in ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id")}
            inputs.append({**ref, "slot_id": "table", "input_ref_id": "TEST-independent-ref-" + str(i),
                "role": "data_input", "selection": "selected", "omission_reason": None, "selector": selector,
                "source": {"type": "frozen", "asset_key": asset["asset_key"], "content_hash": asset["content_hash"],
                           "content_domain": asset["content_domain"]}})
        return {"version": "connected-assets-2", "actor": "code", "parameters": parameters,
                "bindings": {"slot": connected_slot(method), "inputs": inputs, "context": context}}

    def carriers(self):
        parameters = {"value_column": "n", "operation": "count", "unit": "conversation", "participant_mapping": None}
        return [self.fresh().prepare_connected("unit_aggregate", self.request("unit_aggregate", [a], parameters))["tables"][0]
                for a in self.assets]

    def alternate_source(self, index, *, rows_transform=None, descriptor_transform=None, snapshot_transform=None):
        """Additional real archive, explicitly malformed candidate when requested."""
        cid = list(self.snapshots)[index]
        rows = [copy.deepcopy(r["values"]) for r in self.store.read_table(self.assets[index]["asset_key"]["store_run_id"], "correlations")["rows"]]
        if rows_transform:
            rows_transform(rows)
        snapshot = copy.deepcopy(self.snapshots[cid])
        if snapshot_transform:
            snapshot_transform(snapshot)
        self.sequence += 1
        saved = self.fresh().save(item_id=cid, kind="ai_insights", snapshot=snapshot,
            result={"schema_version": 1, "parameters": {}, "TEST_fixture_only": True},
            datasets={"correlations": (self.fields, rows)}, request_id="TEST-independent-alternate-" + str(self.sequence),
            input_fingerprint=digest(snapshot), source_revision=1, analysis_revision=1, publish=False)
        asset, original, state, original_state = self.descriptors(saved)
        if descriptor_transform:
            descriptor_transform(asset, original)
        self.metadata(cid, assets=[asset], originals=[original], states=[state, original_state])
        return asset

    @staticmethod
    def group_scope(tables):
        scope = {"scope_id": "TEST-independent-group", "mode": "dataset",
                 "input_refs": [r for t in tables for r in t["scope"]["input_refs"]],
                 "conversation_ids": [t["scope"]["conversation_ids"][0] for t in tables],
                 "member_ids": [r["unit_id"] for t in tables for r in t["rows"] if r["value_status"] != "excluded"],
                 "context_ids": [r["unit_id"] for t in tables for r in t["rows"] if r["value_status"] == "excluded"]}
        scope["manifest_hash"] = fingerprint(scope)
        return scope


class IndependentPreparationTests(unittest.TestCase):
    def setUp(self):
        self.f = IndependentPoolFixture()
        self.addCleanup(self.f.close)

    def test_saved_complete_sources_and_fresh_carriers(self):
        before = [self.f.fresh().verified_package(a["asset_key"]["store_run_id"])[3] for a in self.f.assets]
        tables = self.f.carriers()
        self.assertEqual([len(t["rows"]) for t in tables], [6, 1])
        rows = [r for t in tables for r in t["rows"]]
        self.assertEqual(sorted(r["n"] for r in rows if r["value_status"] == "observed"), [0, 2, 4])
        self.assertEqual({r["value_status"] for r in rows}, {"observed", "missing", "unknown", "unprocessed", "excluded"})
        pooled = pool_unit_tables(tables, group_scope=self.f.group_scope(tables))
        for operation, expected in (("count", [2, 1]), ("sum", [2, 4]), ("mean", [1, 4])):
            result = run_connected_table("unit_aggregate", [pooled], {"value_column": "n", "operation": operation,
                "unit": "conversation", "participant_mapping": None})
            self.assertEqual([r["value"] for r in result["rows"]], expected)
        self.assertEqual(sum(r["n"] for r in rows if r["value_status"] == "observed"), 6)
        self.assertEqual(sum(r["value_status"] == "observed" for r in rows), 3)
        self.assertEqual(before, [self.f.fresh().verified_package(a["asset_key"]["store_run_id"])[3] for a in self.f.assets])

    def test_source_policy_reread_and_immutable_archive(self):
        a = self.f.assets[1]
        before = self.f.fresh().verified_package(a["asset_key"]["store_run_id"])[3]
        state = {**self.f.states[1], "state_revision": 2, "policy_revision": 2, "revoked": True, "status": "retired"}
        self.f.metadata(a["scope"]["conversation_ids"][0], states=[state])
        with self.assertRaises(AnalysisContractError):
            self.f.carriers()
        self.assertEqual(before, self.f.fresh().verified_package(a["asset_key"]["store_run_id"])[3])

    def test_tampered_saved_bytes_fail_on_fresh_prepare(self):
        a = self.f.assets[1]
        artifact = next(x for x in self.f.fresh().artifacts(a["asset_key"]["store_run_id"]) if x["id"] == a["asset_key"]["artifact_id"])
        path = safe_path(self.f.store.root, artifact["path"])
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises((AnalysisContractError, ValueError)):
            self.f.carriers()

    def test_exact_definition_and_identity_boundaries_from_store_carriers(self):
        tables = self.f.carriers()
        for field, value in (("version", 2), ("value_type", "number"), ("scale", "interval"),
                             ("validity", "human_reviewed"), ("value_domain", "other definition")):
            changed = copy.deepcopy(tables)
            next(v for v in changed[1]["variables"] if v["variable_id"] == "n")[field] = value
            with self.subTest(field=field), self.assertRaises(AnalysisContractError):
                pool_unit_tables(changed, group_scope=self.f.group_scope(changed))
        for mutate in (lambda t: t["rows"].pop(),
                       lambda t: t["source_utterances"][t["rows"][0]["unit_id"]].update(input_hash=fingerprint("wrong input")),
                       lambda t: t["rows"][0].update(n=None),
                       lambda t: t["rows"][2].update(n=0)):
            changed = copy.deepcopy(tables)
            mutate(changed[0])
            with self.assertRaises(AnalysisContractError):
                pool_unit_tables(changed, group_scope=self.f.group_scope(changed))

    def test_current_projection_exclusion_preserves_original_denominator(self):
        source = self.f.carriers()[0]
        uid = next(r["unit_id"] for r in source["rows"] if r.get("n") == 2)
        keep = [r["unit_id"] for r in source["rows"] if r["unit_id"] != uid]
        projected = run_connected_table("unit_projection", [source], {"columns": source["fields"], "unit_ids": keep})
        projected_table = {**projected["unit_contract"], "fields": projected["fields"], "rows": projected["rows"]}
        tables = [projected_table, self.f.carriers()[1]]
        pooled = pool_unit_tables(tables, group_scope=self.f.group_scope(tables))
        self.assertEqual(next(r for r in pooled["rows"] if r["unit_id"] == uid)["value_status"], "excluded")
        self.assertEqual(pooled["denominators"][uid], source["denominators"][uid])
        self.assertEqual(pooled["denominators"][uid]["observed"], 1)
        result = run_connected_table("unit_aggregate", [pooled], {"value_column": "n", "operation": "mean",
                                   "unit": "conversation", "participant_mapping": None})
        self.assertEqual([r["value"] for r in result["rows"]], [0, 4])

    def test_saved_carriers_two_through_sixteen_and_cardinality_rejection(self):
        f = IndependentPoolFixture(source_count=16)
        self.addCleanup(f.close)
        tables = f.carriers()
        for count in range(2, 17):
            subset = tables[:count]
            with self.subTest(count=count):
                pooled = pool_unit_tables(subset, group_scope=f.group_scope(subset))
                self.assertEqual(len(pooled["scope"]["conversation_ids"]), count)
                self.assertEqual(len(pooled["rows"]), 6 + count - 1)
        for subset in ([], tables[:1], tables + [tables[0]], [tables[0], tables[0]]):
            with self.assertRaises(AnalysisContractError):
                pool_unit_tables(subset, group_scope=f.group_scope(subset))

    def test_native_single_source_HTTP_scaffold_saved_fresh(self):
        from flask import Flask
        from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
        app = Flask(__name__)
        register_orchestration_routes(app, lambda: self.f.service, self.f.forbidden, table_reader=lambda: self.f.service)
        client = app.test_client()
        base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
        options = client.get(base + "/asset-plans/options").get_json()
        choice = next(c for c in options["inputs"] if "unit_projection" in c["compatible_methods"])
        request = {**options["plan_template"], "steps": [{"step_id": "TEST-native-scaffold", "method_id": "unit_projection",
            "parameters": {"columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"], "unit_ids": choice["unit_ids"]},
            "inputs": [{"input_ref_id": choice["input_ref_id"], "role": "data_input", "selection": "selected",
                        "omission_reason": None, "source": choice["source"]}],
            "scope": {k: choice["scope"][k] for k in ("scope_id", "manifest_hash")}}]}
        response = client.post(base + "/asset-plans", data=canonical(request), content_type="application/json")
        self.assertEqual(response.status_code, 202, response.get_json())
        tid = next(iter(response.get_json()["tasks"].values()))
        self.f.service._execute(self.f.run["run_id"], tid)
        self.f.service._validate_received(self.f.run["run_id"], tid)
        with self.f.connect() as db:
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (tid,)).fetchone()[0])
        self.assertEqual(task["status"], "succeeded", task)
        self.assertEqual(self.f.fresh().connected_output_descriptor(task["table_store_run_id"])["meaning"]["unit"], "utterance")
        self.assertEqual(self.f.fresh().read_table(task["table_store_run_id"], "table")["row_count"], 6)

    def test_actual_archive_source_stamp_fixture_keeps_bare_hash(self):
        f = IndependentPoolFixture(real_archive_stamp=True)
        self.addCleanup(f.close)
        for cid, snapshot in f.snapshots.items():
            self.assertEqual(snapshot["input_hash"], f.archive_source_stamp(f.find_item(cid)))
            self.assertEqual(len(snapshot["input_hash"]), 64)
            self.assertFalse(snapshot["input_hash"].startswith("sha256:"))
            self.assertNotIn("conversation_id", snapshot)
            source = next(a for a in f.assets if a["scope"]["conversation_ids"] == [cid])
            saved = f.fresh().verified_package(source["asset_key"]["store_run_id"])[0]
            self.assertEqual(saved["input_hash"], snapshot["input_hash"])
            self.assertEqual(saved["archive_snapshot"]["original_source"]["segments"], json.loads(f.find_item(cid)["segments_json"]))


class FixedCandidateAcceptanceTests(unittest.TestCase):
    """Run explicitly only against C0-routed fixed backend+UI candidate.

    Deliberately no success stub or skip: absent wire is a failed acceptance.
    UI browser operation is reported separately, never inferred from Flask.
    """
    def setUp(self):
        from flask import Flask
        from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
        self.f = IndependentPoolFixture(real_archive_stamp=True)
        self.addCleanup(self.f.close)
        app = Flask(__name__)
        app.testing = True
        self.execution_factory_calls = 0
        def executor():
            self.execution_factory_calls += 1
            return self.f.service
        register_orchestration_routes(app, executor, self.f.forbidden,
                                      table_reader=lambda: self.f.readonly_reader())
        self.app = app
        self.client = app.test_client()
        self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]

    def ledger(self):
        with self.f.connect() as db:
            return {name: [tuple(r) for r in db.execute("SELECT * FROM " + name)] for name in
                    ("orchestration_runs", "orchestration_tasks", "orchestration_results", "analysis_runs", "analysis_artifacts")}

    def options(self):
        response = self.client.get(self.base + "/asset-plans/options")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def pool_request(self):
        pool = self.options()["unit_pool"]
        self.assertEqual((pool["min_sources"], pool["max_sources"]), (2, 16))
        by_key = {canonical(a["asset_key"]) for a in self.f.assets}
        selected = [s for s in pool["sources"] if canonical(s["source"]["asset_key"]) in by_key]
        self.assertEqual(len(selected), len(self.f.assets), pool)
        return {**pool["request_template"], "source_ids": [s["option_id"] for s in selected],
                "columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"]}

    def post_plan(self, request):
        response = self.client.post(self.base + "/asset-plans", data=canonical(request), content_type="application/json")
        self.assertIn(response.status_code, (200, 202), response.get_json())
        return response.get_json()

    def execute(self, registered):
        task_id = next(iter(registered["tasks"].values()))
        self.f.service._execute(self.f.run["run_id"], task_id)
        self.f.service._validate_received(self.f.run["run_id"], task_id)
        with self.f.connect() as db:
            state = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
        self.assertEqual(state["status"], "succeeded", state)
        self.assertEqual(state["validation_status"], "valid", state)
        self.assertTrue(state["table_store_run_id"])
        return state

    def task_state(self, task_id):
        with self.f.connect() as db:
            return json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])

    def execute_with_before_validation(self, registered, mutate):
        """Inject a change at the real execution/validation boundary, not a fake validator."""
        from unittest.mock import patch
        task_id = next(iter(registered["tasks"].values()))
        actual = self.f.service._validate_received
        called = []
        def boundary(run_id, current_id):
            self.assertEqual(self.task_state(current_id)["status"], "received")
            called.append(current_id)
            mutate()
            return actual(run_id, current_id)
        with patch.object(self.f.service, "_validate_received", boundary):
            self.f.service._execute(self.f.run["run_id"], task_id)
        self.assertEqual(called, [task_id])
        return self.task_state(task_id)

    def revoke_source(self, index=1):
        asset, state = self.f.assets[index], self.f.states[index]
        self.f.metadata(asset["scope"]["conversation_ids"][0], states=[{**state,
            "state_revision": 2, "policy_revision": 2, "status": "retired", "revoked": True}])

    def tamper_source_bytes(self, index=1):
        asset = self.f.assets[index]
        artifact = next(a for a in self.f.fresh().artifacts(asset["asset_key"]["store_run_id"])
                        if a["id"] == asset["asset_key"]["artifact_id"])
        path = safe_path(self.f.store.root, artifact["path"])
        path.write_bytes(path.read_bytes() + b" ")

    def assert_post_rejected_without_mutation(self, request):
        before = self.ledger()
        response = self.client.post(self.base + "/asset-plans", data=canonical(request), content_type="application/json")
        self.assertIn(response.status_code, (400, 409), response.get_json())
        self.assertEqual(self.ledger(), before)

    def pooled(self):
        request = self.pool_request()
        registered = self.post_plan(request)
        self.assertEqual(len(registered["tasks"]), 1, registered)
        state = self.execute(registered)
        saved = self.f.fresh().verified_package(state["table_store_run_id"])
        table = self.f.fresh().read_table(state["table_store_run_id"], "table")
        self.assertEqual(table["row_count"], 7)
        self.assertEqual(saved[1]["unit_contract"]["scope"]["conversation_ids"], list(self.f.snapshots))
        return state, saved

    def group_mapping(self, saved_id, conversations=None):
        response = self.client.get(self.base + "/human-records")
        self.assertEqual(response.status_code, 200, response.get_json())
        matches = [o for o in response.get_json()["options"] if o["target_kind"] == "participant_mapping"
                   and o["asset_key"]["store_run_id"] == saved_id]
        self.assertEqual(len(matches), 1, response.get_json())
        option = matches[0]
        self.assertTrue(option["enabled"], option)
        conversations = conversations or list(self.f.snapshots)
        self.assertEqual(set(option["scope"]["conversation_ids"]), set(conversations))
        speakers = option.get("speakers") or [{"conversation_id": cid, "speaker_id": "TEST-S1"} for cid in conversations]
        assignments = [{**s, "participant_id": "TEST-P-SILENT" if s["speaker_id"] == "TEST-SILENT" else "TEST-P1"}
                       for s in speakers]
        source = canonical({"participant_mapping": assignments}).decode()
        record_id = "TEST-independent-HC:" + saved_id
        record = {"record_id": record_id, "revision": 1, "supersedes_record_ref": None,
                  "actor": {"kind": "researcher", "actor_id": "TEST-independent-researcher"}, "decision": "adopt",
                  "target": option["target"], "allowed_step_ids": ["participant-mapping-review"],
                  "scope": option["scope"], "recorded_at": "2026-10-09T03:00:00Z",
                  "reason": "TEST synthetic cross-conversation mapping, not research consent",
                  "record_ref": {"target_type": "researcher_memo", "target_id": "human-source:" + record_id,
                      "version": "1", "content_hash": "sha256:" + hashlib.sha256(source.encode()).hexdigest(),
                      "hash_domain": "raw-bytes-v1", "library_id": self.f.library}}
        payload = {"asset_key": option["asset_key"], "record": record, "source_text": source,
                   "expected_state_revision": option["expected_state_revision"]}
        response = self.client.post(self.base + "/human-records", data=canonical(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201, response.get_json())
        return {"actor": record["actor"], "record_ref": response.get_json()["record_ref"], "assignments": assignments}

    def aggregate_request(self, saved_id, mapping, operation, *, require_compatible=True):
        options = self.options()
        choices = [o for o in options["inputs"] if o["source"].get("asset_key", {}).get("store_run_id") == saved_id
                   and (not require_compatible or "unit_aggregate" in o["compatible_methods"])]
        self.assertEqual(len(choices), 1, options)
        choice = choices[0]
        scope = {k: choice["scope"][k] for k in ("scope_id", "manifest_hash")}
        return {**options["plan_template"], "steps": [{"step_id": "TEST-independent-aggregate-" + operation,
                "method_id": "unit_aggregate", "parameters": {"value_column": "n", "operation": operation,
                "unit": "participant", "participant_mapping": mapping}, "scope": scope,
                "inputs": [{"input_ref_id": choice["input_ref_id"], "role": "data_input", "selection": "selected",
                "omission_reason": None, "source": choice["source"]}]}]}

    def test_API_get_is_read_only_and_post_pool_mapping_sum_mean_fresh(self):
        ledger = self.ledger()
        files = {str(p.relative_to(self.f.store.root)): p.read_bytes() for p in self.f.store.root.rglob("*") if p.is_file()}
        request = self.pool_request()
        self.pool_request()
        self.assertEqual(self.execution_factory_calls, 0)
        self.assertEqual(self.ledger(), ledger)
        self.assertEqual(files, {str(p.relative_to(self.f.store.root)): p.read_bytes() for p in self.f.store.root.rglob("*") if p.is_file()})
        state, saved = self.pooled()
        sid = state["table_store_run_id"]
        before = saved[3]
        mapping = self.group_mapping(sid)
        for operation, value in (("sum", 6), ("mean", 2), ("count", 3)):
            final_state = self.execute(self.post_plan(self.aggregate_request(sid, mapping, operation)))
            result = self.f.fresh().verified_package(final_state["table_store_run_id"])[1]
            rows = result["datasets"]["table"]["rows"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["participant_id"], "TEST-P1")
            self.assertEqual(rows[0]["value"], value)
            d = next(iter(result["unit_contract"]["denominators"].values()))
            self.assertEqual(d, {"included": 6, "observed": 3, "missing": 1, "unknown": 1, "unprocessed": 1, "excluded": 1})
            descriptor = self.f.fresh().connected_output_descriptor(final_state["table_store_run_id"])
            self.assertEqual(descriptor["meaning"]["unit"], "participant")
        self.assertEqual(before, self.f.fresh().verified_package(sid)[3])

    def test_API_invalid_selection_rejected_before_registration(self):
        request = self.pool_request()
        invalid = [dict(request, source_ids=request["source_ids"][:1]),
                   dict(request, source_ids=[request["source_ids"][0]] * 2),
                   dict(request, source_ids=request["source_ids"] + ["TEST-forged-option"]),
                   dict(request, source_ids=request["source_ids"] * 9),
                   dict(request, columns=["n"]), dict(request, columns=request["columns"] + ["TEST-absent"]),
                   dict(request, group_scope={"TEST-forged": True}), dict(request, plan_version=True)]
        for i, changed in enumerate(invalid):
            with self.subTest(case=i):
                self.assert_post_rejected_without_mutation(changed)

    def test_actual_group_projection_retains_original_denominator_and_current_exclusion(self):
        state, saved = self.pooled()
        sid = state["table_store_run_id"]
        mapping = self.group_mapping(sid)
        rows = saved[1]["datasets"]["table"]["rows"]
        omitted = next(row["unit_id"] for row in rows if row.get("n") == 2)
        options = self.options()
        choice = next(o for o in options["inputs"] if o["source"].get("asset_key", {}).get("store_run_id") == sid
                      and "unit_projection" in o["compatible_methods"])
        request = {**options["plan_template"], "steps": [{"step_id": "TEST-group-current-exclusion", "method_id": "unit_projection",
            "parameters": {"columns": choice["fields"], "unit_ids": [r["unit_id"] for r in rows if r["unit_id"] != omitted]},
            "scope": {k: choice["scope"][k] for k in ("scope_id", "manifest_hash")},
            "inputs": [{"input_ref_id": choice["input_ref_id"], "role": "data_input", "selection": "selected",
                        "omission_reason": None, "source": choice["source"]}]}]}
        projected = self.execute(self.post_plan(request))
        result = self.f.fresh().verified_package(projected["table_store_run_id"])[1]
        current = next(r for r in result["datasets"]["table"]["rows"] if r["unit_id"] == omitted)
        self.assertEqual((current["value_status"], current["n"]), ("excluded", 2))
        self.assertEqual(result["unit_contract"]["denominators"], saved[1]["unit_contract"]["denominators"])
        self.assertEqual(result["population"], {"denominator": 5, "calculation_denominator": 2})
        aggregate = self.execute(self.post_plan(self.aggregate_request(projected["table_store_run_id"], mapping, "sum")))
        final = self.f.fresh().verified_package(aggregate["table_store_run_id"])[1]
        self.assertEqual(final["datasets"]["table"]["rows"][0]["value"], 4)
        self.assertEqual(next(iter(final["unit_contract"]["denominators"].values())),
            {"included": 5, "observed": 2, "missing": 1, "unknown": 1, "unprocessed": 1, "excluded": 2})
        self.assertEqual(saved[3], self.f.fresh().verified_package(sid)[3])

    def test_identical_POST_replay_preserves_identity_tasks_full_scope_and_ledger(self):
        request = self.pool_request()
        first = self.post_plan(request)
        before = self.ledger()
        response = self.client.post(self.base + "/asset-plans", data=canonical(request), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.get_json())
        duplicate = response.get_json()
        self.assertTrue(duplicate["duplicate"])
        for field in ("identity", "tasks", "scope"):
            self.assertEqual(duplicate[field], first[field])
        self.assertEqual(self.ledger(), before)
        self.revoke_source()
        self.assert_post_rejected_without_mutation(request)

    def test_identical_POST_replay_after_cancel_is_rejected(self):
        request = self.pool_request()
        self.post_plan(request)
        response = self.client.post(self.base + "/cancel")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assert_post_rejected_without_mutation(request)

    def test_every_source_policy_checked_before_execution(self):
        registered = self.post_plan(self.pool_request())
        task_id = next(iter(registered["tasks"].values()))
        self.revoke_source()
        self.f.service._execute(self.f.run["run_id"], task_id)
        state = self.task_state(task_id)
        self.assertNotEqual(state["status"], "succeeded", state)
        self.assertFalse(state.get("table_store_run_id"), state)
        with self.f.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()[0], 0)

    def test_every_source_policy_checked_before_save(self):
        registered = self.post_plan(self.pool_request())
        state = self.execute_with_before_validation(registered, self.revoke_source)
        self.assertNotEqual(state["status"], "succeeded", state)
        self.assertFalse(state.get("table_store_run_id"), state)

    def test_secondary_bytes_change_after_prepare_before_execution(self):
        registered = self.post_plan(self.pool_request())
        task_id = next(iter(registered["tasks"].values()))
        self.tamper_source_bytes()
        self.f.service._execute(self.f.run["run_id"], task_id)
        state = self.task_state(task_id)
        self.assertNotEqual(state["status"], "succeeded", state)
        self.assertFalse(state.get("table_store_run_id"), state)

    def test_secondary_bytes_change_after_execution_before_save(self):
        registered = self.post_plan(self.pool_request())
        state = self.execute_with_before_validation(registered, self.tamper_source_bytes)
        self.assertNotEqual(state["status"], "succeeded", state)
        self.assertFalse(state.get("table_store_run_id"), state)

    def test_secondary_bytes_change_after_save_before_fresh_adoption(self):
        state, saved = self.pooled()
        mapping = self.group_mapping(state["table_store_run_id"])
        request = self.aggregate_request(state["table_store_run_id"], mapping, "mean")
        self.tamper_source_bytes()
        self.assert_post_rejected_without_mutation(request)
        self.assertEqual(saved[3], self.f.fresh().verified_package(state["table_store_run_id"])[3])

    def test_every_source_policy_checked_on_fresh_group_adoption(self):
        state, saved = self.pooled()
        sid = state["table_store_run_id"]
        mapping = self.group_mapping(sid)
        request = self.aggregate_request(sid, mapping, "mean")
        self.revoke_source()
        self.assert_post_rejected_without_mutation(request)
        self.assertEqual(saved[3], self.f.fresh().verified_package(sid)[3])

    def test_source_revoke_between_GET_and_POST_rejected(self):
        request = self.pool_request()
        self.revoke_source()
        self.assert_post_rejected_without_mutation(request)

    def test_incomplete_and_false_scope_population_not_offered(self):
        malformed = self.f.alternate_source(0, rows_transform=lambda rows: rows.pop())
        def replace_evidence(asset, original):
            for obj in (asset, original):
                scope = obj["scope"]
                scope["member_ids"][0] = "TEST-same-cardinality-foreign-evidence"
                scope["manifest_hash"] = fingerprint({k: v for k, v in scope.items() if k != "manifest_hash"})
        from gurumoji.analysis_store import AssetBindingError
        try:
            substituted = self.f.alternate_source(0, descriptor_transform=replace_evidence)
        except AssetBindingError as exc:
            self.assertEqual(exc.reason, "scope_population_mismatch")
            substituted = None
        offered = {canonical(s["source"]["asset_key"]) for s in self.options()["unit_pool"]["sources"]}
        self.assertNotIn(canonical(malformed["asset_key"]), offered)
        if substituted:
            self.assertNotIn(canonical(substituted["asset_key"]), offered)

    def test_wrong_variable_definition_pool_rejected(self):
        def change_definition(asset, original):
            next(v for v in asset["variables"] if v["variable_id"] == "n")["version"] = 2
        alternate = self.f.alternate_source(1, descriptor_transform=change_definition)
        options = self.options()["unit_pool"]
        required = {canonical(self.f.assets[0]["asset_key"]), canonical(alternate["asset_key"])}
        selected = [s["option_id"] for s in options["sources"] if canonical(s["source"]["asset_key"]) in required]
        if len(selected) == 2:
            self.assert_post_rejected_without_mutation({**options["request_template"], "source_ids": selected,
                "columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"]})
        else:
            self.assertNotIn(canonical(alternate["asset_key"]),
                {canonical(s["source"]["asset_key"]) for s in options["sources"]})

    def test_same_name_version_different_definition_hash_pool_rejected(self):
        def change_definition(asset, original):
            variable = next(v for v in asset["variables"] if v["variable_id"] == "n")
            variable["definition_ref"] = copy.deepcopy(variable["definition_ref"])
            variable["definition_hash"] = fingerprint({"TEST": "different n definition, same name and version"})
            variable["definition_ref"]["content_hash"] = variable["definition_hash"]
        alternate = self.f.alternate_source(1, descriptor_transform=change_definition)
        pool = self.options()["unit_pool"]
        keys = {canonical(self.f.assets[0]["asset_key"]), canonical(alternate["asset_key"])}
        selected = [s["option_id"] for s in pool["sources"] if canonical(s["source"]["asset_key"]) in keys]
        if len(selected) == 2:
            self.assert_post_rejected_without_mutation({**pool["request_template"], "source_ids": selected,
                "columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"]})
        else:
            self.assertNotIn(canonical(alternate["asset_key"]), {canonical(s["source"]["asset_key"]) for s in pool["sources"]})

    def test_oversized_actual_saved_source_cannot_be_selected_or_discarded_by_projection(self):
        valid_uid = self.f.carriers()[1]["rows"][0]["unit_id"]
        self.f.fields = [*self.f.fields, "TEST_large_declared_text"]
        def large_row(rows):
            for row in rows:
                row["TEST_large_declared_text"] = "TEST" * 40000
        alternate = self.f.alternate_source(1, rows_transform=large_row)
        request = self.f.request("unit_projection", [alternate],
            {"columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"], "unit_ids": [valid_uid]})
        receipt = self.f.fresh().bind_asset_inputs(method_id="unit_projection", **request["bindings"])
        self.assertNotEqual(receipt["decision"], "eligible", receipt)
        self.assertEqual(receipt["reason"], "payload_byte_limit", receipt)
        options = self.options()["unit_pool"]
        self.assertNotIn(canonical(alternate["asset_key"]), {canonical(s["source"]["asset_key"]) for s in options["sources"]})
        source = {"type": "frozen", "asset_key": alternate["asset_key"], "content_hash": alternate["content_hash"], "content_domain": alternate["content_domain"]}
        primary = next(s["option_id"] for s in options["sources"] if s["source"]["asset_key"] == self.f.assets[0]["asset_key"])
        self.assert_post_rejected_without_mutation({**options["request_template"],
            "source_ids": [primary, "saved:" + digest(source)],
            "columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"]})

    def test_top_nested_manifest_identity_conflicts_rejected(self):
        from gurumoji.analysis_store import AssetBindingError, StoreConflict
        cid = list(self.f.snapshots)[1]
        def keep_declared_owner(asset, original):
            for obj in (asset, original):
                obj["scope"]["conversation_ids"] = [cid]
                obj["scope"]["manifest_hash"] = fingerprint({k: v for k, v in obj["scope"].items() if k != "manifest_hash"})
        mutations = [lambda s: s.update(conversation_id="TEST-foreign-top"),
                     lambda s: s["archive_snapshot"].update(conversation_id="TEST-foreign-nested"),
                     lambda s: (s.update(conversation_id=cid), s["archive_snapshot"].update(conversation_id="TEST-foreign-nested"))]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                try:
                    asset = self.f.alternate_source(1, snapshot_transform=mutate, descriptor_transform=keep_declared_owner)
                except (AnalysisContractError, AssetBindingError, StoreConflict):
                    continue  # A production save/registration boundary refused it.
                offered = {canonical(s["source"]["asset_key"]) for s in self.options()["unit_pool"]["sources"]}
                self.assertNotIn(canonical(asset["asset_key"]), offered)

    def test_wrong_actual_input_version_is_not_offered(self):
        from gurumoji.analysis_store import AssetBindingError, StoreConflict
        try:
            asset = self.f.alternate_source(1, snapshot_transform=lambda s: s.update(input_hash="0" * 64))
        except (AnalysisContractError, AssetBindingError, StoreConflict):
            return
        offered = {canonical(s["source"]["asset_key"]) for s in self.options()["unit_pool"]["sources"]}
        self.assertNotIn(canonical(asset["asset_key"]), offered)

    def test_real_single_conversation_HC_cannot_adopt_group_mapping(self):
        options = self.options()
        choice = next(o for o in options["inputs"] if o["source"].get("asset_key") == self.f.assets[0]["asset_key"]
                      and "unit_projection" in o["compatible_methods"])
        request = {**options["plan_template"], "steps": [{"step_id": "TEST-single-HC-target", "method_id": "unit_projection",
            "parameters": {"columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"],
                           "unit_ids": choice["unit_ids"]},
            "scope": {k: choice["scope"][k] for k in ("scope_id", "manifest_hash")},
            "inputs": [{"input_ref_id": choice["input_ref_id"], "role": "data_input", "selection": "selected",
                        "omission_reason": None, "source": choice["source"]}]}]}
        single = self.execute(self.post_plan(request))
        mapping = self.group_mapping(single["table_store_run_id"], [self.f.owner])
        pooled, _ = self.pooled()
        self.assert_post_rejected_without_mutation(self.aggregate_request(pooled["table_store_run_id"], mapping, "mean", require_compatible=False))

    def test_deleted_nonowner_source_rejected(self):
        request = self.pool_request()
        cid = list(self.f.snapshots)[1]
        with self.f.connect() as db:
            db.execute("DELETE FROM library_items WHERE id=?", (cid,))
        self.assert_post_rejected_without_mutation(request)

    def test_stale_nonowner_source_rejected(self):
        request = self.pool_request()
        cid = list(self.f.snapshots)[1]
        with self.f.connect() as db:
            db.execute("UPDATE library_items SET analysis_revision=2 WHERE id=?", (cid,))
        self.assert_post_rejected_without_mutation(request)

    def test_sixteen_saved_sources_actual_POST_Handler_save_fresh(self):
        self.f.close()
        self.f = IndependentPoolFixture(source_count=16, real_archive_stamp=True)
        self.addCleanup(self.f.close)
        self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
        state = self.execute(self.post_plan(self.pool_request()))
        saved = self.f.fresh().verified_package(state["table_store_run_id"])
        self.assertEqual(len(saved[1]["unit_contract"]["scope"]["conversation_ids"]), 16)
        self.assertEqual(self.f.fresh().read_table(state["table_store_run_id"], "table")["row_count"], 21)
        provenance = saved[1]["parameters"]["table_pilot_provenance"]
        self.assertEqual(provenance["version"], "connected-provenance-3")
        self.assertNotIn("parents", provenance)
        self.assertEqual(provenance["receipt"], state["table_pilot_prepared"]["receipt"])
        self.assertEqual(provenance["parents_ref"], {"target": "receipt.bindings",
            "content_hash": fingerprint(provenance["receipt"]["bindings"]), "hash_domain": "canonical-json-v1"})

    def test_saved_pool_parent_ref_target_domain_hash_bindings_payload_version_missing_unknown_rejected(self):
        from unittest.mock import patch
        mutations = [lambda p: p["parents_ref"].update(target="receipt.payloads"),
            lambda p: p["parents_ref"].update(hash_domain="raw-bytes-v1"),
            lambda p: p["parents_ref"].update(content_hash="sha256:" + "0" * 64),
            lambda p: p["receipt"]["bindings"][0]["source"].update(output_name="TEST-foreign-alias"),
            lambda p: p["receipt"]["payloads"][0].update(bytes=p["receipt"]["payloads"][0]["bytes"] + 1),
            lambda p: p["receipt"]["payloads"][0]["value"].update(TEST_foreign_value="TEST altered immutable input payload"),
            lambda p: p.update(version="TEST-unknown-provenance-version"),
            lambda p: p.pop("parents_ref"),
            lambda p: p["parents_ref"].update(TEST_unknown_field=True),
            lambda p: p.update(parents=copy.deepcopy(p["receipt"]["bindings"]))]
        from gurumoji.analysis_store import AssetBindingError
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                self.f.close()
                self.f = IndependentPoolFixture(real_archive_stamp=True)
                self.addCleanup(self.f.close)
                self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
                registered = self.post_plan(self.pool_request())
                task_id = next(iter(registered["tasks"].values()))
                actual, injected = self.f.store.table_pilot_carrier, []
                def corrupt_once(raw, prepared):
                    carrier, provenance = actual(raw, prepared)
                    if not injected:
                        self.assertEqual(provenance["version"], "connected-provenance-3")
                        provenance = copy.deepcopy(provenance)
                        mutate(provenance)
                        injected.append(True)
                    return carrier, provenance
                # Real Store writes/checks/immutable hashes and real Handler run.
                # The fault injection touches only a synthetic saved proof; all
                # later verification uses the unchanged production serializer.
                with patch.object(self.f.store, "table_pilot_carrier", corrupt_once):
                    self.f.service._execute(self.f.run["run_id"], task_id)
                self.assertEqual(injected, [True])
                with self.f.connect() as db:
                    saved_ids = [r[0] for r in db.execute("SELECT id FROM analysis_runs WHERE request_id=?", ("table-pilot:" + task_id,))]
                if saved_ids:
                    for saved_id in saved_ids:
                        with self.assertRaises((AssetBindingError, AnalysisContractError, ValueError)):
                            self.f.fresh().connected_output_descriptor(saved_id)
                else:
                    state = self.task_state(task_id)
                    self.assertNotEqual(state["status"], "succeeded", state)

    def test_saved_pool_parent_ref_requires_actual_task_and_raw_ledger(self):
        from gurumoji.analysis_store import AssetBindingError
        for table in ("orchestration_tasks", "orchestration_results"):
            with self.subTest(missing=table):
                self.f.close()
                self.f = IndependentPoolFixture(real_archive_stamp=True)
                self.addCleanup(self.f.close)
                self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
                state, saved = self.pooled()
                sid = state["table_store_run_id"]
                with self.f.connect() as db:
                    db.execute("DELETE FROM " + table + " WHERE task_id=?", (state["task_id"],))
                with self.assertRaises((AssetBindingError, AnalysisContractError, ValueError)):
                    self.f.fresh().connected_output_descriptor(sid)
                self.assertEqual(saved[3], self.f.fresh().verified_package(sid)[3])

    def test_valid_larger_complete_pool_still_rejected_at_save_byte_gate(self):
        self.f.close()
        self.f = IndependentPoolFixture(source_count=16, real_archive_stamp=True,
                                        primary_observed_only=True, extra_other_observed=2)
        self.addCleanup(self.f.close)
        self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
        registered = self.post_plan(self.pool_request())
        task_id = next(iter(registered["tasks"].values()))
        self.f.service._execute(self.f.run["run_id"], task_id)
        state = self.task_state(task_id)
        self.assertEqual(state["status"], "quarantined", state)
        self.assertEqual(state["error"], "table_carrier_byte_limit", state)
        self.assertFalse(state.get("table_store_run_id"), state)
        with self.f.connect() as db:
            raw = json.loads(db.execute("SELECT raw_json FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()[0])
        carrier, provenance = self.f.store.table_pilot_carrier(raw, state["table_pilot_prepared"])
        self.assertEqual(len(carrier["rows"]), 47)
        self.assertEqual(len(raw["unit_contract"]["scope"]["conversation_ids"]), 16)
        self.assertGreater(len(canonical({"carrier": carrier, "provenance": provenance})), 131072)

    def test_saved_pool_actual_receipt_value_tamper_is_rejected(self):
        from unittest.mock import patch
        from gurumoji.analysis_store import AssetBindingError
        registered = self.post_plan(self.pool_request())
        task_id = next(iter(registered["tasks"].values()))
        actual, injected = self.f.store.table_pilot_carrier, []
        def corrupt_once(raw, prepared):
            carrier, provenance = actual(raw, prepared)
            if not injected:
                provenance = copy.deepcopy(provenance)
                row = provenance["receipt"]["payloads"][0]["value"]["rows"][0]["values"]
                row["n"] += 1
                injected.append(True)
            return carrier, provenance
        with patch.object(self.f.store, "table_pilot_carrier", corrupt_once):
            self.f.service._execute(self.f.run["run_id"], task_id)
        self.assertEqual(injected, [True])
        with self.f.connect() as db:
            saved_ids = [r[0] for r in db.execute("SELECT id FROM analysis_runs WHERE request_id=?", ("table-pilot:" + task_id,))]
        self.assertTrue(saved_ids)
        for saved_id in saved_ids:
            with self.assertRaises((AssetBindingError, AnalysisContractError, ValueError)):
                self.f.fresh().connected_output_descriptor(saved_id)

    def test_group_raw_hash_adapter_preserves_original_addresses_and_rejects_corruption(self):
        from gurumoji.analysis_store import AssetBindingError
        _state, saved = self.pooled()
        group = saved[1]["unit_contract"]["group_source_set"]
        for member in group["sources"]:
            cid = member["conversation_id"]
            raw = self.f.snapshots[cid]["input_hash"]
            self.assertEqual(member["current"]["input_hash"], raw)
            self.assertEqual(member["qualified_input_hash"], "sha256:" + raw)
            self.assertEqual(member["original_ref"]["content_hash"], member["snapshot_content_hash"])
            for uid, original in member["original_units"].items():
                self.assertEqual(original["input_hash"], raw)
                self.assertEqual(original["source_unit_id"], "utterance:" + fingerprint(
                    [self.f.library, cid, raw, original["utterance_id"]]).removeprefix("sha256:"))
                self.assertEqual(uid, "utterance:" + fingerprint(
                    [self.f.library, cid, "sha256:" + raw, original["utterance_id"]]).removeprefix("sha256:"))
        mutations = [lambda m: m.update(qualified_input_hash="sha256:" + "0" * 64),
                     lambda m: m.update(snapshot_content_hash="sha256:" + "0" * 64),
                     lambda m: next(iter(m["original_units"].values())).update(source_unit_id="TEST-forged-address")]
        for mutate in mutations:
            malformed = copy.deepcopy(group)
            mutate(malformed["sources"][1])
            with self.assertRaises(AssetBindingError):
                self.f.fresh()._verify_group(malformed)

    def test_pool_permit_metadata_requires_distinct_sources_and_primary_anchor(self):
        pool = self.options()["unit_pool"]
        self.assertTrue(pool["enabled"], pool)
        self.assertIsNone(pool["reason_code"])
        self.f.close()
        self.f = IndependentPoolFixture(source_count=3, real_archive_stamp=True)
        self.addCleanup(self.f.close)
        self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
        self.revoke_source(0)
        before = self.ledger()
        options = self.options()
        pool = options["unit_pool"]
        self.assertEqual(len(pool["sources"]), 2)
        self.assertFalse(pool["enabled"], pool)
        self.assertEqual(pool["reason_code"], "pool_anchor_unavailable")
        self.assertEqual(self.ledger(), before)
        self.assert_post_rejected_without_mutation({**pool["request_template"],
            "source_ids": [s["option_id"] for s in pool["sources"]],
            "columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"]})
        self.revoke_source(1)
        pool = self.options()["unit_pool"]
        self.assertEqual(len(pool["sources"]), 1)
        self.assertFalse(pool["enabled"])
        self.assertIn(pool["reason_code"], ("pool_sources_insufficient", "pool_anchor_unavailable"))

    def test_saved_silent_roster_options_validation_and_group_count_remain_observed_only(self):
        self.f.close()
        self.f = IndependentPoolFixture(real_archive_stamp=True, silent_roster=True)
        self.addCleanup(self.f.close)
        self.base = "/api/library/" + self.f.owner + "/analysis/orchestration/" + self.f.run["run_id"]
        options = self.options()
        choice = next(o for o in options["inputs"] if canonical(o["source"].get("asset_key")) == canonical(self.f.assets[0]["asset_key"]))
        single = self.execute(self.post_plan({**options["plan_template"], "steps": [{"step_id": "TEST-silent-single",
            "method_id": "unit_projection", "parameters": {"columns": ["unit_id", "conversation_id", "speaker_id", "value_status", "n"], "unit_ids": choice["unit_ids"]},
            "scope": {k: choice["scope"][k] for k in ("scope_id", "manifest_hash")},
            "inputs": [{"input_ref_id": choice["input_ref_id"], "role": "data_input", "selection": "selected", "omission_reason": None, "source": choice["source"]}]}]}))
        self.group_mapping(single["table_store_run_id"], [self.f.owner])
        contexts = self.options()["participant_context"]["contexts"]
        context = next(c for c in contexts if c["human_record_option"]["asset_key"]["store_run_id"] == single["table_store_run_id"])
        self.assertEqual({s["speaker_id"] for s in context["speakers"]}, {"TEST-S1", "TEST-SILENT"})
        pooled, _saved = self.pooled()
        mapping = self.group_mapping(pooled["table_store_run_id"])
        state = self.execute(self.post_plan(self.aggregate_request(pooled["table_store_run_id"], mapping, "count")))
        result = self.f.fresh().verified_package(state["table_store_run_id"])[1]
        rows = result["datasets"]["table"]["rows"]
        observed = next(r for r in rows if r["participant_id"] == "TEST-P1")
        self.assertEqual(observed["value"], 3)
        for row in rows:
            if row["participant_id"] == "TEST-P-SILENT":
                self.assertIsNone(row["value"])


class BrowserFixedCandidateAcceptanceTests(unittest.TestCase):
    """Explicit final-only Edge operation with real APIs and manual Handler driver."""
    def test_normal_screen_pool_without_primary_anchor_is_disabled(self):
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server, WSGIRequestHandler
        class Quiet(WSGIRequestHandler):
            def log(self, *args, **kwargs):
                pass
        helper = FixedCandidateAcceptanceTests()
        helper.setUp()
        helper.f.close()
        helper.f = IndependentPoolFixture(source_count=3, real_archive_stamp=True)
        f = helper.f
        helper.addCleanup(f.close)
        helper.revoke_source(0)
        server = make_server("127.0.0.1", 0, independent_browser_app(f), threaded=True, request_handler=Quiet)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = "http://127.0.0.1:" + str(server.server_port)
        evidence = Path(os.environ.get("GURUMOJI_INDEPENDENT_EVIDENCE_DIR") or tempfile.mkdtemp(prefix="gurumoji-independent-permit-"))
        evidence.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                try:
                    page = browser.new_page(viewport={"width": 390, "height": 844})
                    page.set_default_timeout(120000)
                    errors, posts = [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: posts.append(request.url) if request.method == "POST" else None)
                    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin + "/") else r.abort())
                    stored = json.dumps({"itemId": f.owner, "runId": f.run["run_id"]})
                    page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1');sessionStorage.setItem('gurumoji.orchestration.v1'," + json.dumps(stored) + ");")
                    page.goto(origin)
                    page.locator("#orchestration-chip").click()
                    with page.expect_response(lambda r: "/asset-plans/options" in r.url) as response:
                        page.locator("#orchestration-asset-load").click()
                    self.assertEqual(response.value.status, 200)
                    pool = response.value.json()["unit_pool"]
                    self.assertEqual(len(pool["sources"]), 2)
                    self.assertFalse(pool["enabled"])
                    self.assertEqual(pool["reason_code"], "pool_anchor_unavailable")
                    page.locator("#orchestration-asset-method").select_option("unit_pool")
                    choices = page.locator("#orchestration-asset-inputs input[data-choice]")
                    self.assertEqual(choices.count(), 2)
                    for index in range(2):
                        self.assertTrue(choices.nth(index).is_disabled())
                    self.assertTrue(page.locator("#orchestration-asset-add").is_disabled())
                    self.assertIn("この実行の会話", page.locator("#orchestration-asset-availability").inner_text())
                    self.assertEqual(posts, [])
                    self.assertEqual(errors, [])
                    page.screenshot(path=str(evidence / "pool-anchor-disabled-390.png"))
                    (evidence / "browser-permit-receipt.json").write_text(json.dumps(
                        {"status": "PASS", "width": 390, "sources": 2, "pool_enabled": False,
                         "reason_code": pool["reason_code"], "posts": posts, "errors": errors,
                         "browser": browser.version}, indent=2), encoding="utf-8")
                finally:
                    browser.close()
        finally:
            server.shutdown()
            helper.doCleanups()

    def test_normal_screen_pool_group_HC_mean_sum_save_fresh_1440_390(self):
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server, WSGIRequestHandler

        class Quiet(WSGIRequestHandler):
            def log(self, *args, **kwargs):
                pass

        evidence = Path(os.environ.get("GURUMOJI_INDEPENDENT_EVIDENCE_DIR") or
                        tempfile.mkdtemp(prefix="gurumoji-independent-browser-evidence-"))
        evidence.mkdir(parents=True, exist_ok=True)
        receipts = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            try:
                requested_width = os.environ.get("GURUMOJI_INDEPENDENT_BROWSER_WIDTH")
                widths = (int(requested_width),) if requested_width else (1440, 390)
                self.assertTrue(all(width in (1440, 390) for width in widths))
                for width in widths:
                    helper = FixedCandidateAcceptanceTests()
                    helper.setUp()
                    f = helper.f
                    server = make_server("127.0.0.1", 0, independent_browser_app(f), threaded=True, request_handler=Quiet)
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                    origin = "http://127.0.0.1:" + str(server.server_port)
                    context = browser.new_context(viewport={"width": width, "height": 900 if width == 1440 else 844})
                    page = context.new_page()
                    # Fixed group descendants are fully verified on every GET;
                    # allow that real work to finish instead of mocking it.
                    page.set_default_timeout(120000)
                    errors, blocked, posts = [], [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: posts.append(request.post_data_json) if request.method == "POST" and
                            request.url.endswith(("/asset-plans", "/human-records")) else None)
                    def route(request_route):
                        if request_route.request.url.startswith(origin + "/"):
                            request_route.continue_()
                        else:
                            blocked.append(request_route.request.url)
                            request_route.abort()
                    context.route("**/*", route)
                    receipt = {"phase": "fixed_candidate_browser", "browser": browser.version, "channel": "msedge",
                               "width": width, "origin": origin, "driver": "explicit _execute/_validate_received; scheduler disabled",
                               "shell": "production templates/scripts; invented empty unrelated bootstrap GETs",
                               "source_hashes": {name: hashlib.sha256((Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
                                   for name in ("src/gurumoji/static/analysis-orchestration.js",
                                                "src/gurumoji/templates/views/analysis-orchestration.html")}, "status": "FAIL"}
                    try:
                        # Standard persisted-run restoration, then only visible controls.
                        stored = json.dumps({"itemId": f.owner, "runId": f.run["run_id"]})
                        page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1');" +
                                             "sessionStorage.setItem('gurumoji.orchestration.v1'," + json.dumps(stored) + ");")
                        page.goto(origin)
                        page.locator("#orchestration-chip").wait_for(state="visible")
                        page.locator("#orchestration-chip").click()
                        with page.expect_response(lambda r: "/asset-plans/options" in r.url) as options_response:
                            page.locator("#orchestration-asset-load").click()
                        self.assertEqual(options_response.value.status, 200)
                        options = options_response.value.json()
                        page.locator("#orchestration-asset-form").wait_for(state="visible")
                        page.locator("#orchestration-asset-method").select_option("unit_pool")
                        choices = page.locator("#orchestration-asset-inputs input[data-choice]")
                        self.assertEqual(choices.count(), 2)
                        choices.nth(0).check()
                        page.locator("#orchestration-asset-add").click()
                        self.assertIn("2〜16", page.locator("#orchestration-asset-message").inner_text())
                        self.assertEqual(posts, [])
                        self.assertTrue(page.locator("#orchestration-asset-inputs").evaluate("n => n === document.activeElement"))
                        choices.nth(1).check()
                        page.locator("input[name='asset-columns'][value='n']").check()
                        page.locator("#orchestration-asset-add").click()
                        page.locator("#orchestration-asset-review").click()
                        self.assertTrue(page.locator("#orchestration-asset-execute").evaluate("n => n === document.activeElement"))
                        page.screenshot(path=str(evidence / ("pool-confirm-" + str(width) + ".png")))
                        with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/asset-plans")) as response:
                            page.keyboard.press("Enter")
                        self.assertEqual(response.value.status, 202)
                        pool_post = posts[-1]
                        self.assertEqual(set(pool_post), {"version", "plan_id", "plan_version", "source_ids", "columns"})
                        self.assertEqual(pool_post["version"], "unit-pool-request-1")
                        self.assertEqual(len(pool_post["source_ids"]), 2)
                        pooled = helper.execute(response.value.json())
                        sid = pooled["table_store_run_id"]
                        before = f.fresh().verified_package(sid)[3]
                        page.locator("#orchestration-asset-clear").click()
                        with page.expect_response(lambda r: "/asset-plans/options" in r.url) as response:
                            page.locator("#orchestration-asset-load").click()
                        options = response.value.json()
                        page.locator("#orchestration-participant > summary").click()
                        selector = page.locator("#orchestration-participant-context")
                        values = selector.locator("option").evaluate_all("nodes => nodes.map(n => n.value)")
                        selected = [v for v in values if v and json.loads(v)[2]["store_run_id"] == sid]
                        self.assertEqual(len(selected), 1)
                        selector.select_option(selected[0])
                        page.locator("#orchestration-participant-form").wait_for(state="visible")
                        page.locator("#orchestration-participant-target > summary").click()
                        target_text = page.locator("#orchestration-participant-target-meta").inner_text()
                        self.assertIn(sid, target_text)
                        for cid in f.snapshots:
                            self.assertIn(cid, target_text)
                        assignments = page.locator("#orchestration-participant-assignments input")
                        self.assertEqual(assignments.count(), 2)
                        for i in range(assignments.count()):
                            assignments.nth(i).fill("TEST-P1")
                        page.locator("#orchestration-participant-actor").fill("TEST-independent-browser-researcher")
                        page.locator("#orchestration-participant-decision").select_option("adopt")
                        page.locator("#orchestration-participant-reason").fill("TEST 合成の両会話・話者と固定対象を明示確認")
                        page.locator("#orchestration-participant-reason").focus()
                        page.keyboard.press("Tab")
                        self.assertTrue(page.locator("#orchestration-participant-review").evaluate("n => n === document.activeElement"))
                        page.keyboard.press("Enter")
                        page.locator("#orchestration-participant-confirmation").wait_for(state="visible")
                        page.locator("#orchestration-participant-save").scroll_into_view_if_needed()
                        page.screenshot(path=str(evidence / ("group-HC-confirm-" + str(width) + ".png")))
                        with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/human-records")) as response:
                            page.locator("#orchestration-participant-save").click()
                        self.assertEqual(response.value.status, 201)
                        self.assertEqual(posts[-1]["asset_key"]["store_run_id"], sid)
                        self.assertEqual(set(posts[-1]["record"]["scope"]["conversation_ids"]), set(f.snapshots))
                        self.assertEqual(len(f.fresh()._human_packages()[0]), 1)
                        outcomes = []
                        for operation, expected in (("mean", 2), ("sum", 6)):
                            with page.expect_response(lambda r: "/asset-plans/options" in r.url) as response:
                                page.locator("#orchestration-asset-load").click()
                            options = response.value.json()
                            page.locator("#orchestration-asset-method").select_option("unit_aggregate")
                            index = next(i for i, c in enumerate(options["inputs"]) if c["source"].get("asset_key", {}).get("store_run_id") == sid)
                            page.locator("#orchestration-asset-choice-" + str(index)).check()
                            page.locator("#orchestration-asset-param-operation").select_option(operation)
                            page.locator("#orchestration-asset-param-unit").select_option("participant")
                            page.locator("#orchestration-asset-param-value_column").select_option("n")
                            page.locator("#orchestration-asset-add").click()
                            page.locator("#orchestration-asset-review").click()
                            with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/asset-plans")) as response:
                                page.keyboard.press("Enter")
                            self.assertEqual(response.value.status, 202)
                            task = helper.execute(response.value.json())
                            result = f.fresh().verified_package(task["table_store_run_id"])[1]
                            self.assertEqual(result["datasets"]["table"]["rows"][0]["value"], expected)
                            self.assertEqual(next(iter(result["unit_contract"]["denominators"].values()))["observed"], 3)
                            f.fresh().connected_output_descriptor(task["table_store_run_id"])
                            outcomes.append({"operation": operation, "value": expected, "store_run_id": task["table_store_run_id"]})
                            page.locator("#orchestration-asset-clear").click()
                        self.assertEqual(before, f.fresh().verified_package(sid)[3])
                        self.assertEqual(errors, [])
                        self.assertEqual(blocked, [])
                        self.assertEqual(len(posts), 4)
                        page.screenshot(path=str(evidence / ("saved-fresh-" + str(width) + ".png")))
                        receipt.update(status="PASS", posts=posts, outcomes=outcomes, errors=errors, blocked=blocked,
                                       scope=f.fresh().verified_package(sid)[1]["unit_contract"]["scope"])
                    except Exception as exc:
                        receipt.update(error=str(exc), posts=posts, errors=errors, blocked=blocked)
                        page.screenshot(path=str(evidence / ("failure-" + str(width) + ".png")))
                        raise
                    finally:
                        (evidence / ("browser-receipt-" + str(width) + ".json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf8")
                        receipts.append(receipt)
                        context.close()
                        server.shutdown()
                        helper.doCleanups()
            finally:
                browser.close()
        print("Independent browser evidence:", evidence)


if __name__ == "__main__":
    unittest.main()
