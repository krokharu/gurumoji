"""Explicit TEST researcher HTTP fixtures only; no actual human adoption/data."""
import copy
import hashlib
import json
import unittest
from flask import Flask
from gurumoji.analysis_core import content_fingerprint, fingerprint
from gurumoji.analysis_store import AnalysisStore, AssetBindingError, StoreConflict, canonical, safe_path
from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes
import test_analysis_typed_assets as typed


class HumanRecordTests(unittest.TestCase):
    def setUp(self):
        self.helper = typed.TypedHandlerIntegrationTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.fixture = self.helper.fixture
        # Match the Handler's synthetic source versions before publishing. A
        # later library UPDATE correctly stales saved packages via the real
        # Store trigger and must never be used to prepare a readonly fixture.
        with self.fixture.connect() as db:
            db.execute("UPDATE library_items SET revision_count=1,analysis_revision=1 WHERE id='TEST-conversation'")
        self.service = self.helper.service()
        run = self.helper.start(self.service); self.run_id = run["run_id"]
        self.service.run(self.run_id)
        publisher = AnalysisOrchestrationPublicationService(connect=self.fixture.connect, store_factory=lambda: self.fixture.store,
            source_guard=lambda db, item, expected: {"id": item}, export_locked=self.service.result_locked)
        publication = publisher.finalize("TEST-conversation", self.run_id)
        self.saved_id = publication["result_run_id"]
        choices = self.fixture.store.thematic_asset_descriptors(self.saved_id)
        self.asset, self.original = choices["assets"][0], choices["original"]
        self.candidate, self.steps, *_ = self.fixture.store._human_contract(self.asset)
        self.binding_helper = typed.TypedAssetsTests(); self.binding_helper.fixture = self.fixture
        app = Flask(__name__)
        register_orchestration_routes(app, lambda: self.service, lambda _: self.fail("No AI preparation"),
                                      table_reader=lambda: self.service)
        self.client = app.test_client()
        self.url = f"/api/library/TEST-conversation/analysis/orchestration/{self.run_id}/human-records"

    def fresh(self): return AnalysisStore(self.fixture.path, self.fixture.connect)

    def payload(self, step, *, decision="adopt", revision=1, previous=None, theme=False):
        record_id = "TEST-researcher-" + step + ("-theme" if theme else "")
        source_text = f"TEST ONLY explicit synthetic researcher statement: {step}/{decision}/{revision}"
        record = {"record_id": record_id, "revision": revision, "supersedes_record_ref": None,
            "actor": {"kind": "researcher", "actor_id": "TEST-researcher"}, "decision": decision,
            "target": {"domain": "ta-candidate-content-v1", "candidate_set_id": self.candidate["content"]["candidate_set_id"],
                "version": self.candidate["content"]["version"], "content_hash": self.candidate["content_hash"]},
            "allowed_step_ids": [step], "scope": copy.deepcopy(self.asset["scope"]),
            "recorded_at": "2026-10-08T17:00:00Z", "reason": "TEST synthetic decision; not actual research",
            "record_ref": {"target_type": "researcher_memo", "target_id": "human-source:" + record_id,
                "version": str(revision), "content_hash": "sha256:" + hashlib.sha256(source_text.encode()).hexdigest(),
                "hash_domain": "raw-bytes-v1", "library_id": "TEST-library"}}
        if theme: record["target"] = copy.deepcopy(self.candidate["content"]["theme_refs"][0])
        if previous:
            record["supersedes_record_ref"] = {"domain": "human-record-v1", "record_id": record_id,
                "revision": previous["record"]["revision"], "content_hash": previous["record_ref"]["content_hash"]}
        states = self.fresh()._connection_index()[2].get(typed.digest(self.asset["asset_key"]), {})
        return {"asset_key": copy.deepcopy(self.asset["asset_key"]), "record": record, "source_text": source_text,
                "expected_state_revision": max(states) if states else 0}

    def post(self, payload):
        return self.client.post(self.url, data=canonical(payload), content_type="application/json")

    def bind(self): return self.fresh().bind_asset_inputs(**self.binding_helper.request(self.asset))

    def adopt(self):
        outcomes = []
        for step in self.steps:
            response = self.post(self.payload(step)); self.assertEqual(response.status_code, 201, response.get_json())
            outcomes.append(response.get_json())
        return outcomes

    def test_api_saved_body_fresh_binding_requires_all_frozen_researcher_steps(self):
        before = self.fresh().verified_package(self.saved_id)[3]
        self.assertEqual(len(self.steps), 4)
        self.assertEqual(self.bind()["decision"], "needs_input")
        for index, step in enumerate(self.steps):
            payload = self.payload(step); response = self.post(payload)
            self.assertEqual(response.status_code, 201, response.get_json())
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            outcome = response.get_json()
            self.assertEqual(outcome["record_ref"]["content_hash"], content_fingerprint("human-record-v1", payload["record"]))
            self.assertEqual(self.bind()["decision"], "eligible" if index == 3 else "human_pending")
        packages, _latest = self.fresh()._human_packages()
        for package in packages:
            _snapshot, result, _manifest, files = self.fresh().verified_package(package["run_id"])
            self.assertEqual(files["human/record.json"], canonical(package["record"]))
            self.assertEqual(json.loads(files["human/submission.json"])["record"], package["record"])
            self.assertEqual(files["human/source.txt"].decode(), result["human_submission"]["source_text"])
        receipt = self.bind()
        self.assertFalse(receipt["execution_enabled"])
        self.assertFalse(receipt["adoption_performed"])
        self.assertEqual(before, self.fresh().verified_package(self.saved_id)[3])
        request = self.binding_helper.request(self.asset); request["context"]["purpose"] = "confirmatory"
        request["slot"]["purposes"].append("confirmatory")
        self.assertEqual(self.fresh().bind_asset_inputs(**request)["reason"], "variable_review_unconfirmed")

    def test_defer_reject_absent_and_theme_only_do_not_adopt_dataset(self):
        for step, decision in zip(self.steps, ("adopt", "adopt", "defer", "reject")):
            response = self.post(self.payload(step, decision=decision)); self.assertEqual(response.status_code, 201, response.get_json())
            self.assertEqual(self.bind()["decision"], "human_pending")
        for step in self.steps:
            response = self.post(self.payload(step, theme=True)); self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(self.bind()["decision"], "human_pending")

    def test_closed_actor_target_revision_scope_step_source_and_state_negatives(self):
        mutations = [lambda p: p["record"]["actor"].update(kind="ai"),
            lambda p: p["record"]["actor"].update(model_id="TEST-AI"), lambda p: p["record"].update(revision=True),
            lambda p: p["record"].update(revision=2), lambda p: p["record"].update(allowed_step_ids=[]),
            lambda p: p["record"].update(allowed_step_ids=[self.steps[0], self.steps[1]]),
            lambda p: p["record"].update(allowed_step_ids=["ta-p2-ai-codes"]),
            lambda p: p["record"]["target"].update(content_hash=fingerprint("old")),
            lambda p: p["record"]["target"].update(version=0), lambda p: p["record"]["target"].update(domain="raw-bytes-v1"),
            lambda p: p["record"]["scope"].update(member_ids=[]), lambda p: p.update(source_text="different"),
            lambda p: p["record"]["record_ref"].update(target_id="self-wrapper"),
            lambda p: p.update(expected_state_revision=7), lambda p: p.update(extra="unknown"),
            lambda p: p.update(asset_key=None), lambda p: p["asset_key"].update(library_id="FOREIGN"),
            lambda p: p["record"].update(decision=[]), lambda p: p["record"].update(recorded_at="2026-10-08 17:00:00Z")]
        for mutate in mutations:
            value = self.payload(self.steps[0]); mutate(value)
            with self.subTest(mutate=mutate):
                self.assertIn(self.post(value).status_code, (400, 409))
        self.assertEqual(self.fresh()._human_packages()[0], [])

    def test_idempotency_revision_correction_and_retained_old_bytes(self):
        outcomes = self.adopt(); previous = outcomes[0]
        old_packages = {p["run_id"]: self.fresh().verified_package(p["run_id"])[3] for p in self.fresh()._human_packages()[0]}
        payload = self.payload(self.steps[0], decision="defer", revision=2, previous=previous)
        response = self.post(payload); self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["state"]["status"], "stale")
        self.assertEqual(self.bind()["decision"], "blocked")
        duplicate = self.post(payload); self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        for run_id, content in old_packages.items(): self.assertEqual(content, self.fresh().verified_package(run_id)[3])
        invalid = self.payload(self.steps[0], revision=3, previous=previous)
        record_count = len(self.fresh()._human_packages()[0])
        invalid_response = self.post(invalid)
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.get_json()["reason_code"], "human_record_revision")
        self.assertEqual(len(self.fresh()._human_packages()[0]), record_count)
        corrected = self.payload(self.steps[0], revision=3, previous=response.get_json())
        self.assertEqual(self.post(corrected).status_code, 201)
        self.assertEqual(self.bind()["decision"], "eligible")

    def test_counterfeit_generic_wrapper_and_tampered_saved_body_are_rejected(self):
        payload = self.payload(self.steps[0])
        with self.assertRaises(AssetBindingError):
            self.fixture.store.save(item_id="TEST-conversation", kind="analysis_human_record", snapshot={},
                result={"human_submission": payload}, datasets={}, request_id="TEST-counterfeit",
                input_fingerprint="TEST", source_revision=1, analysis_revision=1, publish=False)
        self.adopt()
        package = self.fresh()._human_packages()[0][0]
        artifact = next(a for a in self.fresh().artifacts(package["run_id"]) if a["name"] == "human/record.json")
        path = safe_path(self.fixture.store.root, artifact["path"]); path.write_bytes(path.read_bytes() + b" ")
        self.assertEqual(self.bind()["decision"], "rejected")

    def test_theme_target_alone_and_counterfeit_review_state_cannot_adopt_dataset(self):
        for step in self.steps:
            response = self.post(self.payload(step, theme=True)); self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(self.bind()["decision"], "human_pending")
        states = self.fresh()._connection_index()[2][typed.digest(self.asset["asset_key"])]
        forged = copy.deepcopy(states[max(states)])
        forged.update(status="adopted", state_revision=forged["state_revision"] + 1)
        forged["review_refs"] = [{"target_type": "artifact", "target_id": "TEST-forged-wrapper", "version": "1",
            "content_hash": fingerprint("TEST forged HumanRecord"), "hash_domain": "human-record-v1", "library_id": "TEST-library"}]
        self.fixture.register(states=[forged])
        receipt = self.bind(); self.assertEqual(receipt["decision"], "human_pending")
        self.assertEqual(receipt["reason"], "human_record_current")

    def test_policy_and_parent_state_rechecked_after_real_record_adoption(self):
        outcomes = self.adopt(); previous = outcomes[0]
        receipt = self.bind(); self.assertEqual(receipt["decision"], "eligible")
        state = copy.deepcopy(outcomes[-1]["state"])
        state.update(send_policy="prohibited", state_revision=state["state_revision"] + 1, policy_revision=2)
        self.fixture.register(states=[state])
        changed = self.post(self.payload(self.steps[0], revision=2, previous=previous))
        self.assertEqual(changed.status_code, 201, changed.get_json())
        self.assertEqual(changed.get_json()["state"]["policy_revision"], 2)
        self.assertEqual(changed.get_json()["state"]["send_policy"], "prohibited")
        self.assertEqual(self.bind()["reason"], "destination_intersection")
        original_states = self.fresh()._connection_index()[2][typed.digest(self.original["asset_key"])]
        source = copy.deepcopy(original_states[max(original_states)])
        source.update(revoked=True, state_revision=source["state_revision"] + 1, policy_revision=2)
        self.fixture.register(states=[source])
        self.assertEqual(self.bind()["reason"], "parent_state_unavailable")
        rejection = self.post(self.payload(self.steps[0], theme=True, decision="reject"))
        self.assertEqual(rejection.status_code, 201, rejection.get_json())
        forged = copy.deepcopy(rejection.get_json()["state"])
        forged.update(status="adopted", state_revision=forged["state_revision"] + 1)
        forged["review_refs"].remove(rejection.get_json()["record_ref"])
        self.fixture.register(states=[forged])
        self.assertEqual(self.bind()["reason"], "human_record_current")

    def test_changed_current_source_rejects_submission_before_saving_record(self):
        self.service.source_fingerprint = lambda _: fingerprint("TEST changed input")
        response = self.post(self.payload(self.steps[0]))
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["reason_code"], "revision_conflict")
        self.assertEqual(self.fresh()._human_packages()[0], [])

    def test_correction_cannot_retarget_same_record_id_from_candidate_to_theme(self):
        previous = self.post(self.payload(self.steps[0])).get_json()
        retarget = self.payload(self.steps[0], revision=2, previous=previous)
        retarget["record"]["target"] = copy.deepcopy(self.candidate["content"]["theme_refs"][0])
        old_bytes = {p["run_id"]: self.fresh().verified_package(p["run_id"])[3] for p in self.fresh()._human_packages()[0]}
        response = self.post(retarget)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["reason_code"], "human_record_supersedes")
        self.assertEqual(len(self.fresh()._human_packages()[0]), 1)
        for run_id, content in old_bytes.items(): self.assertEqual(content, self.fresh().verified_package(run_id)[3])

    def test_fresh_human_boundary_rechecks_historical_producer_against_actual_task(self):
        self.adopt()
        saved_bytes = self.fresh().verified_package(self.saved_id)[3]
        task_id = self.candidate["content"]["producer"]["actor_id"]
        with self.fixture.connect() as db:
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
            original_model = task["model"]
            task["model"] = "TEST-actual-model-mismatch"
            db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (canonical(task).decode(), task_id))
        receipt = self.bind(); self.assertEqual(receipt["decision"], "blocked")
        self.assertEqual(receipt["reason"], "typed_execution_provenance")
        response = self.post(self.payload(self.steps[0], theme=True))
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["reason_code"], "typed_execution_provenance")
        self.assertEqual(len(self.fresh()._human_packages()[0]), 4)
        self.assertEqual(self.fresh().verified_package(self.saved_id)[3], saved_bytes)
        with self.fixture.connect() as db:
            task.update(model=original_model, status="cancelled")
            db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (canonical(task).decode(), task_id))
        self.assertEqual(self.bind()["reason"], "typed_execution_provenance")
        self.assertEqual(self.post(self.payload(self.steps[0], theme=True)).status_code, 409)

    def test_current_cancel_and_exact_target_stale_block_records_and_binding(self):
        self.adopt()
        child_run = self.fixture.run("TEST-current-parent-check")
        parent_ref = {"target_type": "artifact", "target_id": self.asset["asset_key"]["artifact_id"],
            "version": str(self.asset["schema"]["version"]), "content_hash": self.asset["content_hash"],
            "hash_domain": self.asset["content_domain"], "library_id": "TEST-library"}
        child, state = self.fixture.descriptors(child_run, parents=[parent_ref])
        self.fixture.register(assets=[child], states=[state])
        with self.fixture.connect() as db:
            original_run = db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (self.run_id,)).fetchone()[0]
            current = json.loads(original_run); current["cancel_requested"] = True
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (canonical(current).decode(), self.run_id))
        self.assertEqual(self.bind()["reason"], "human_run_cancelled")
        self.assertEqual(self.fresh().bind_asset_inputs(**self.fixture.request(child))["reason"], "human_run_cancelled")
        response = self.post(self.payload(self.steps[0], theme=True))
        self.assertEqual(response.status_code, 409); self.assertEqual(response.get_json()["reason_code"], "human_run_cancelled")
        with self.fixture.connect() as db:
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (original_run, self.run_id))
            row = db.execute("SELECT result_id,state_json FROM orchestration_results WHERE run_id=? AND raw_json LIKE '%thematic_candidates_v1%'", (self.run_id,)).fetchone()
            metadata = json.loads(row["state_json"]); metadata["stale"] = True
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (canonical(metadata).decode(), row["result_id"]))
        self.assertEqual(self.bind()["reason"], "human_target_stale")
        self.assertEqual(self.fresh().bind_asset_inputs(**self.fixture.request(child))["reason"], "human_target_stale")
        response = self.post(self.payload(self.steps[0], theme=True))
        self.assertEqual(response.status_code, 409); self.assertEqual(response.get_json()["reason_code"], "human_target_stale")
        with self.fixture.connect() as db:
            metadata["stale"] = False
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (canonical(metadata).decode(), row["result_id"]))
            current = json.loads(original_run); current["stale"] = True
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (canonical(current).decode(), self.run_id))
        self.assertEqual(self.bind()["reason"], "human_target_stale")
        self.assertEqual(self.post(self.payload(self.steps[0], theme=True)).status_code, 409)
        with self.fixture.connect() as db:
            db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (original_run, self.run_id))
            db.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (self.saved_id,))
        self.assertEqual(self.bind()["reason"], "human_target_stale")
        self.assertEqual(self.post(self.payload(self.steps[0], theme=True)).status_code, 409)
        self.assertEqual(len(self.fresh()._human_packages()[0]), 4)

    def test_correction_stales_registered_descendant_and_keeps_raw_package_bytes(self):
        outcomes = self.adopt()
        child_run = self.fixture.run("TEST-dependent")
        parent_ref = {"target_type": "artifact", "target_id": self.asset["asset_key"]["artifact_id"],
            "version": str(self.asset["schema"]["version"]), "content_hash": self.asset["content_hash"],
            "hash_domain": self.asset["content_domain"], "library_id": "TEST-library"}
        child, child_state = self.fixture.descriptors(child_run, parents=[parent_ref])
        independent_run = self.fixture.run("TEST-independent")
        independent, independent_state = self.fixture.descriptors(independent_run)
        self.fixture.register(assets=[independent], states=[independent_state])
        independent_bytes = self.fresh().verified_package(independent_run["id"])[3]
        independent_decision = self.fresh().bind_asset_inputs(**self.fixture.request(independent))["decision"]
        # A retained TEST code producer ledger exercises Handler notification.
        # This does not assert a supported TA -> numerical measurement adapter.
        task_id, result_id = "TEST-retained-dependent-task", "TEST-retained-dependent-result"
        child.update(execution_run_id=self.run_id, producer_task_id=task_id)
        raw = self.fresh().verified_package(child_run["id"])[1]
        with self.fixture.connect() as db:
            task = {"task_id": task_id, "run_id": self.run_id, "idempotency_key": task_id,
                "kind": "code", "method_id": "pearson", "status": "succeeded"}
            meta = {"result_id": result_id, "task_id": task_id, "run_id": self.run_id,
                "validation_status": "valid", "raw_hash": fingerprint(raw), "stale": False}
            db.execute("INSERT INTO orchestration_tasks VALUES (?,?,?,?)", (task_id, self.run_id, task_id, canonical(task).decode()))
            db.execute("INSERT INTO orchestration_results VALUES (?,?,?,?,?)", (result_id, self.run_id, task_id, canonical(raw).decode(), canonical(meta).decode()))
        self.fixture.register(assets=[child], states=[child_state])
        old_bytes = self.fresh().verified_package(child_run["id"])[3]
        correction = self.payload(self.steps[0], decision="reject", revision=2, previous=outcomes[0])
        response = self.post(correction)
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertIn(child["asset_key"], response.get_json()["stale_assets"])
        self.assertNotIn(independent["asset_key"], response.get_json()["stale_assets"])
        self.assertEqual(self.fresh().bind_asset_inputs(**self.fixture.request(independent))["decision"], independent_decision)
        self.assertEqual(independent_bytes, self.fresh().verified_package(independent_run["id"])[3])
        self.assertEqual(self.fresh().get(independent_run["id"])["stale"], 0)
        current = self.fresh()._connection_index()[2][typed.digest(child["asset_key"])]
        self.assertEqual(current[max(current)]["status"], "stale")
        self.assertEqual(self.fresh().get(child_run["id"])["stale"], 1)
        self.assertEqual(old_bytes, self.fresh().verified_package(child_run["id"])[3])
        self.assertEqual(self.fresh().bind_asset_inputs(**self.fixture.request(child))["reason"], "state_unavailable")
        with self.fixture.connect() as db:
            result = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (result_id,)).fetchone()
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
            self.assertEqual(result["raw_json"].encode(), canonical(raw))
            self.assertTrue(json.loads(result["state_json"])["stale"])
            self.assertEqual(task["human_record_ref"], response.get_json()["record_ref"])
            events = db.execute("SELECT COUNT(*) FROM orchestration_events WHERE run_id=?", (self.run_id,)).fetchone()[0]
        duplicate = self.post(correction); self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["stale_assets"], response.get_json()["stale_assets"])
        with self.fixture.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_events WHERE run_id=?", (self.run_id,)).fetchone()[0], events)


if __name__ == "__main__": unittest.main()
