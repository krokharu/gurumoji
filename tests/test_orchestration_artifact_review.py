"""T01-T12: synthetic data only, including actual provider packets and durable JSON."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_analysis_orchestration as f
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.method_experts import counterexample_review_procedure
from gurumoji.services import artifact_review as review, model_context
from gurumoji.services.analysis_intervals import interval_scope
from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION, make_orchestration_adapters


class ArtifactReviewTests(unittest.TestCase):
    connect = f.RuntimeTests.connect
    build = f.RuntimeTests.build
    run_agent = f.RuntimeTests.run_agent
    method = f.RuntimeTests.method
    make_service = f.RuntimeTests.make_service

    def setUp(self):
        f.RuntimeTests.setUp(self)
        self.fixture = json.loads((Path(__file__).parent / "fixtures/artifact_review_conversation.json").read_text(encoding="utf-8"))
        self.snapshot["analysis"]["segments"] = self.fixture["segments"]
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        self.run = f.RuntimeTests.start(self, artifact_review_version=1, analysis_interval_version=1,
            specialist_orchestration_version=1, core_progress_version=1, adapter_version=ADAPTER_VERSION, max_calls=100, max_tasks=200)
        self.rid = self.run["run_id"]
        self.service._prepare_intervals(self.rid)
        with self.service._db() as db:
            self.run = self.service._read_run(db, self.rid)
            self.scope = interval_scope(self.run["analysis_partition"]["intervals"][0])
            self.evidence = {e["utterance_id"]: e["evidence_id"] for e in self.service._initial(db, self.run["initial_id"])["evidence"]}
        self.sources = [self.seed_source(i) for i in range(3)]

    def seed_source(self, number):
        with self.service._db() as db:
            run = self.service._read_run(db, self.rid)
            task = self.service._register(db, run, f.intent("interpretation", f"Synthetic finding {number}",
                scope=self.scope), phase="fixture", automatic=True)
            raw = {"summary": f"Synthetic R{number}", "claims": [{k:v for k,v in c.items() if k != "utterance_ids"}
                | {"evidence_ids": [self.evidence[u] for u in c["utterance_ids"]]} for c in self.fixture["claims"]],
                "limitations": "S1 only; not population confirmation", "label_patches": [], "analysis_requests": []}
            context = self.service._context(db, run, task)
            manifest = model_context.context_manifest(context, {}, "", "{}", {"fits": True})
            manifest["version"] = 2
            task.update(status="succeeded", validation_status="valid", result_id=f"R{number}",
                        context_manifest=manifest, context_manifest_hash=fingerprint(manifest))
            self.service._write_task(db, task)
            meta = {"result_id": task["result_id"], "run_id": self.rid, "task_id": task["task_id"],
                "attempt_id": task["attempt_id"], "role": "interpretation", "raw_hash": fingerprint(raw),
                "dataset_version": run["input_hash"], "annotation_version": 0, "validation_status": "valid",
                "context_manifest_hash": task["context_manifest_hash"], "content_status": "ai_draft", "stale": False,
                "interval_lineage": {k: self.scope[k] for k in ("interval_id", "parent_topic_id", "dataset_version", "ownership_sha256")}}
            db.execute("INSERT INTO orchestration_results VALUES (?,?,?,?,?)",
                       (task["result_id"], self.rid, task["task_id"], json.dumps(raw), json.dumps(meta)))
            return task, raw, meta

    def choices(self, candidates, values=("use", "skip", "defer")):
        return [{"result_id": c["result_id"], "disposition": values[i % len(values)], "reason": "Synthetic scoped choice",
            "purpose": review.PURPOSE, "interval_id": c["interval_id"], "expected_output": "Verdict per claim",
            "missing": "Missing definition", "release_condition": "A new definition result", "next_action": "Review next result"}
            for i,c in enumerate(candidates)]

    def intent(self, target="R0"):
        return f.intent("interpretation", "Check the minority counterexample", kind="finding_review",
            review_target_result_id=target, artifact_purpose=review.PURPOSE, interval_ids=[self.scope["interval_id"]])

    def orchestrator(self, domain="interpretation", values=("use", "skip", "defer"), apply=True):
        with self.service._db() as db:
            run = self.service._read_run(db, self.rid)
            task = self.service._register(db, run, f.intent("orchestrator", "Review " + domain + str(len(self.service._tasks(db, self.rid))),
                scope={"domain":domain}), phase="specialist_review", automatic=True)
            context = self.service._context(db, run, task)
            manifest = model_context.context_manifest(context, {}, "", "{}", {"fits": True})
            manifest.update(version=2, artifact_candidates=context["artifact_candidates"],
                            artifact_candidate_scope=context["artifact_candidate_scope"])
            task.update(context_manifest=manifest, context_manifest_hash=fingerprint(manifest))
            self.service._write_task(db, task)
            choices = self.choices(context["artifact_candidates"], values)
            use = next((r for r in choices if r["disposition"] == "use"), None)
            raw = f.core("Scoped review", stop=None, result_assessments=f.assess_pending_results(context),
                artifact_decisions=choices, intents=[self.intent(use["result_id"])] if use else [])
            meta = {"result_id":"decision-result-"+task["task_id"], "raw_hash":fingerprint(raw)}
            if apply:
                # Persist the same durable result boundary used by _apply_core.
                saved = {**meta, "run_id":self.rid, "task_id":task["task_id"], "validation_status":"valid",
                    "role":"orchestrator", "context_manifest_hash":task["context_manifest_hash"]}
                db.execute("INSERT INTO orchestration_results VALUES (?,?,?,?,?)",
                           (meta["result_id"], self.rid, task["task_id"], json.dumps(raw), json.dumps(saved)))
                self.service._apply_specialist_review(db, run, task, raw, meta)
            return task, context, raw

    def review_task(self):
        with self.service._db() as db:
            return next(t for t in self.service._tasks(db, self.rid) if t.get("input_artifacts"))

    def test_T01_domain_choices_are_separate_and_unpresented_is_not_skip(self):
        before = copy.deepcopy(self.sources)
        self.orchestrator()
        self.orchestrator("verification", ("skip", "defer", "skip"))
        with self.service._db() as db:
            x = self.service._artifact_history(db, self.run, "interpretation")
            y = self.service._artifact_history(db, self.run, "verification")
            self.assertEqual([r["disposition"] for r in x], ["use","skip","defer"])
            self.assertEqual([r["disposition"] for r in y], ["skip","defer","skip"])
            for task, raw, meta in before:
                row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (meta["result_id"],)).fetchone()
                self.assertEqual(json.loads(row[0]), raw)
                self.assertEqual(json.loads(row[1])["raw_hash"], meta["raw_hash"])

    def test_T01_invalid_missing_duplicate_unknown_and_reason_are_rejected(self):
        _, ctx, raw = self.orchestrator(apply=False)
        mutations = [lambda r:r["artifact_decisions"].pop(),
            lambda r:r["artifact_decisions"].append(copy.deepcopy(r["artifact_decisions"][0])),
            lambda r:r["artifact_decisions"][0].update(result_id="unknown"),
            lambda r:r["artifact_decisions"][0].update(reason=" "),
            lambda r:r["artifact_decisions"][2].update(release_condition="")]
        for mutate in mutations:
            candidate = copy.deepcopy(raw); mutate(candidate)
            with self.assertRaises(AnalysisContractError):
                review.validate_decisions(candidate, ctx["artifact_candidates"])

    def test_T02_use_is_bound_to_one_request_and_issuance_is_saved(self):
        _, ctx, raw = self.orchestrator()
        task = self.review_task()
        self.assertEqual(task["input_artifacts"][0]["result_id"], "R0")
        self.assertIn(self.sources[0][0]["task_id"], task["dependencies"])
        with self.service._db() as db:
            choice = self.service._artifact_history(db, self.run, "interpretation")[0]
            self.assertEqual(choice["issuance"], "issued")
            self.assertEqual(choice["issued_task_id"], task["task_id"])
        for mutate in (lambda r:r.update(intents=[]), lambda r:r["intents"][0].update(review_target_result_id="R1"),
                       lambda r:r["artifact_decisions"][1].update(disposition="use")):
            bad = copy.deepcopy(raw); mutate(bad)
            with self.assertRaises(AnalysisContractError): review.validate_decisions(bad, ctx["artifact_candidates"])

    def test_T03_invalid_source_is_rejected_before_any_agent_call(self):
        self.orchestrator()
        task = self.review_task()
        with self.service._db() as db:
            db.execute("UPDATE orchestration_results SET raw_json=? WHERE result_id='R0'", ('{"claims":[]}',))
            with self.assertRaises(AnalysisContractError): self.service._recheck_review_binding(db, self.run, task)
        self.assertEqual(self.calls, [])

    def test_T03_source_state_version_claim_and_kind_rejections(self):
        task, raw, meta = self.sources[0]
        procedure = counterexample_review_procedure()
        mutations = [("task",{"run_id":"other"}), ("meta",{"run_id":"other"}),
            ("task",{"status":"running"}), ("meta",{"validation_status":"quarantined"}),
            ("task",{"dataset_version":"other"}), ("task",{"codebook_version":99}),
            ("task",{"role":"verification"}), ("task",{"intent":{**task["intent"],"kind":"finding_review"}}),
            ("raw",{"claims":[]}), ("raw",{"claims":[raw["claims"][0],raw["claims"][0]]}),
            ("raw",{"claims":[{**raw["claims"][0],"evidence_ids":["unknown"]}]})]
        for target, changes in mutations:
            values = {"task":copy.deepcopy(task),"raw":copy.deepcopy(raw),"meta":copy.deepcopy(meta)}
            values[target].update(changes)
            if target == "raw": values["meta"]["raw_hash"] = fingerprint(values["raw"])
            with self.subTest(target=target,changes=changes), self.assertRaises(AnalysisContractError):
                review.validate_source(self.run, values["task"],values["meta"],values["raw"],self.scope,procedure)

    def test_T02_call_budget_keeps_intended_use_and_not_issued_reason(self):
        task, ctx, raw = self.orchestrator(apply=False)
        with self.service._db() as db:
            run = self.service._read_run(db,self.rid)
            run["config"]["max_calls"] = 1
            meta = {"result_id":"budget-choice", "raw_hash":fingerprint(raw)}
            self.service._apply_specialist_review(db,run,task,raw,meta)
            choice = self.service._artifact_history(db,run,"interpretation")[0]
            self.assertEqual(choice["disposition"],"use")
            self.assertEqual(choice["issuance"],"not_issued")
            self.assertEqual(choice["not_issued_reason"],"call_budget_limit")
            self.assertEqual(choice["issued_task_id"],"")
            self.assertFalse(any(t.get("input_artifacts") for t in self.service._tasks(db,self.rid)))

    def test_T01_candidate_paging_and_unreleased_defer(self):
        for i in range(3,8): self.seed_source(i)
        _,ctx,raw = self.orchestrator(values=("defer",),apply=False)
        self.assertEqual(len(ctx["artifact_candidates"]),6)
        self.assertEqual(ctx["artifact_candidate_scope"]["omitted_count"],2)
        smaller = model_context.reduce_context(ctx)
        self.assertEqual(len(smaller["artifact_candidates"]),3)
        self.assertEqual(smaller["artifact_candidate_scope"]["omitted_count"],5)
        prior = [{**raw["artifact_decisions"][0],"information_hash":ctx["artifact_candidates"][0]["information_hash"]}]
        raw["artifact_decisions"][0]["disposition"] = "use"
        raw["intents"] = [self.intent()]
        with self.assertRaises(AnalysisContractError): review.validate_decisions(raw,ctx["artifact_candidates"],prior=prior)

    def test_T08_verification_cannot_register_or_receive_artifacts(self):
        self.orchestrator()
        task = self.review_task()
        with self.service._db() as db:
            run = self.service._read_run(db, self.rid)
            with self.assertRaises(AnalysisContractError):
                self.service._register(db, run, {**task["intent"], "role":"verification"}, phase="specialist_followup")
            with self.assertRaises(AnalysisContractError):
                self.service._context(db, run, {**task, "role":"verification"})

    def verdicts(self, context):
        binding = context["input_artifacts"][0]
        return {"summary":"Minority counterexample in S1", "claims": [], "label_patches": [], "analysis_requests": [],
            "missing_inputs": [], "limitations":"S1 only; not an independent blind confirmation",
            "claim_verdicts":[{"result_id":binding["result_id"], "raw_hash":binding["raw_hash"], "claim_id":cid,
                "verdict":answer["verdict"], "reason":"Read the provided original in its scope",
                "evidence_ids":[next(e["evidence_id"] for e in context["raw_evidence"]
                    if e["text"] == next(s["text"] for s in self.fixture["segments"] if s["id"] == u)) for u in answer["utterance_ids"]]}
                for cid,answer in self.fixture["answer_key"].items()]}

    def delivery(self, *, provider="lmstudio", budget=None, options=None):
        task = self.review_task()
        with self.service._db() as db:
            context = self.service._context(db, self.service._read_run(db, self.rid), task)
        sent, manifests = [], []
        def transport(*args, **kw):
            restored = model_context.restored_reference_context(args[4], kw.get("data_messages"))
            sent.append((args, kw, restored))
            return self.verdicts(restored)
        _, adapter = make_orchestration_adapters(call_ai_json=transport,
            load_token_config=lambda:SimpleNamespace(lmstudio_base_url="http://synthetic.invalid"),
            configured_ai_credentials=lambda *_:("synthetic", "synthetic"),
            context_meter=lambda *a, **kw:budget or {"fits":True, "output_reserve":2000},
            provider_context_meter=lambda *a, **kw:budget or {"fits":True, "output_reserve":2000})
        config = {**self.run["config"], "provider":provider, "model":"synthetic", "roles":{},
                  "cloud_consent":True, "provider_policy":"cloud_allowed", **(options or {})}
        raw = adapter("interpretation", context, config, lambda:None, lambda r:manifests.append(r))
        return sent, manifests, raw

    def test_T04_actual_local_and_cloud_mock_delivery_is_complete_and_aliased(self):
        self.orchestrator()
        for provider in ("lmstudio", "openai"):
            with self.subTest(provider=provider):
                sent, manifests, raw = self.delivery(provider=provider)
                args, kw, wire = sent[0]
                self.assertEqual(len(wire["finding_resource"]["claims"]), 2)
                self.assertEqual(len(wire["raw_evidence"]), 7)  # S1 six + explicit u7 boundary
                self.assertIn(self.fixture["segments"][5]["text"], args[4]+"".join(kw["data_messages"]))
                self.assertNotIn("Synthetic R1", args[4]+"".join(kw["data_messages"]))
                self.assertNotIn(self.fixture["segments"][8]["text"], args[4]+"".join(kw["data_messages"]))
                self.assertNotIn("finding_resource", json.loads(args[4]))
                self.assertTrue(wire["review_procedure"]["quality_checks"])
                references = json.loads(args[4])["resource_references"]
                artifact = next(r for r in references if r["resource_id"] == "finding_resource")
                self.assertEqual(artifact["path"], "db://orchestration_results/R0")
                self.assertEqual(artifact["source_raw_hash"], self.sources[0][2]["raw_hash"])
                manifest = manifests[0]["context_manifest"]
                self.assertEqual(artifact["sha256"], manifest["finding_packet_sha256"])
                self.assertEqual(raw["claim_verdicts"][0]["evidence_ids"], [self.evidence["u6"]])
                for eid in self.evidence.values(): self.assertNotIn(eid, args[4]+"".join(kw["data_messages"]))

    def test_T05_budget_output_reserve_and_policy_reject_without_calls(self):
        self.orchestrator()
        for kwargs in ({"budget":{"fits":False,"output_reserve":2000}},
                       {"budget":{"fits":True,"output_reserve":1}},
                       {"provider":"openai","options":{"cloud_consent":False}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AnalysisContractError): self.delivery(**kwargs)
        with self.service._db() as db:
            context = self.service._context(db, self.run, self.review_task_from_db(db))
        self.assertIsNone(model_context.reduce_context(context))

    def test_T05_handler_budget_rejection_has_no_call_or_interval_split(self):
        self.orchestrator()
        before = self.review_task()
        task, result = self.execute_review(budget={"fits":False,"output_reserve":2000})
        self.assertIsNone(result)
        self.assertEqual(task["status"],"failed")
        self.assertEqual(task["error"],"context_budget_exceeded")
        self.assertEqual(self.sent,[])
        self.assertEqual(task["input_artifacts"],before["input_artifacts"])
        with self.service._db() as db:
            self.assertEqual(len([t for t in self.service._tasks(db,self.rid) if t.get("input_artifacts")]),1)

    def review_task_from_db(self, db):
        return next(t for t in self.service._tasks(db, self.rid) if t.get("input_artifacts"))

    def execute_review(self, mutate=None, budget=None):
        self.sent = []
        def transport(*args, **kw):
            context = model_context.restored_reference_context(args[4], kw.get("data_messages"))
            self.sent.append((args, kw, context))
            raw = self.verdicts(context)
            if mutate: mutate(raw, context)
            return raw
        _, adapter = make_orchestration_adapters(call_ai_json=transport,
            load_token_config=lambda:SimpleNamespace(lmstudio_base_url="http://synthetic.invalid"),
            configured_ai_credentials=lambda *_:("", "synthetic"),
            context_meter=lambda *a, **kw:budget or {"fits":True,"output_reserve":2000})
        self.agent = adapter
        self.service._execute(self.rid, self.review_task()["task_id"])
        with self.service._db() as db:
            task = self.review_task_from_db(db)
            result = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
        return task, (json.loads(result[0]), json.loads(result[1])) if result else None

    def test_T06_verdict_schema_and_valid_result_persist_at_real_provider_boundary(self):
        self.orchestrator()
        task, (raw, meta) = self.execute_review()
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(meta["validation_status"], "valid")
        self.assertEqual(meta["derived_from"], task["input_artifacts"])
        self.assertFalse(meta["independent_verification"])
        schema = self.sent[0][0][6]
        self.assertEqual(schema["properties"]["claim_verdicts"]["minItems"], 2)
        self.assertEqual(schema["properties"]["claim_verdicts"]["maxItems"], 2)
        self.assertEqual(raw["claim_verdicts"][0]["evidence_ids"], [self.evidence["u6"]])

    def test_T06_invalid_verdicts_are_quarantined_without_repair(self):
        mutations = [lambda r,c:r["claim_verdicts"].pop(),
            lambda r,c:r["claim_verdicts"].append(copy.deepcopy(r["claim_verdicts"][0])),
            lambda r,c:r["claim_verdicts"][0].update(claim_id="unknown"),
            lambda r,c:r["claim_verdicts"][0].update(result_id="R1"),
            lambda r,c:r["claim_verdicts"][0].update(raw_hash="changed"),
            lambda r,c:r["claim_verdicts"][0].update(evidence_ids=[]),
            lambda r,c:r["claim_verdicts"][0].update(evidence_ids=["unmapped"]),
            lambda r,c:r["claim_verdicts"][0].update(evidence_ids=[self.evidence["u6"]]),
            lambda r,c:r.update(claim_verdicts=[], used=True)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.setUp()  # Fresh isolated DB for each irreversible receipt boundary.
                self.orchestrator()
                task, (raw, meta) = self.execute_review(mutate)
                self.assertEqual(meta["validation_status"], "quarantined", raw)
                self.assertEqual(task["status"], "quarantined")
                self.assertEqual(len(self.sent), 1)

    def test_T07_incomplete_coverage_cannot_assert_no_counterexample(self):
        self.orchestrator()
        with self.service._db() as db:
            task = self.review_task_from_db(db)
            context = self.service._context(db, self.run, task)
        manifest = model_context.context_manifest(context, {}, "", "{}", {"fits":True})
        raw = self.verdicts(context)
        manifest["coverage"]["complete"] = False
        with self.assertRaises(AnalysisContractError): review.validate_review_output(raw, task["input_artifacts"][0], manifest)
        raw["claim_verdicts"][1].update(verdict="insufficient", reason="Missing scoped input", evidence_ids=[])
        raw["missing_inputs"] = ["Missing scoped input"]
        review.validate_review_output(raw, task["input_artifacts"][0], manifest)

    def test_T09_same_binding_reason_change_is_not_reissued(self):
        self.orchestrator()
        task = self.review_task()
        with self.service._db() as db:
            run = self.service._read_run(db, self.rid)
            self.assertIsNone(self.service._register(db, run, {**task["intent"], "why_now":"Changed only reason"}, phase="specialist_followup"))
            self.assertEqual(len([t for t in self.service._tasks(db,self.rid) if t.get("input_artifacts")]), 1)
        binding = task["input_artifacts"][0]
        for field, value in (("raw_hash","other"),("claim_ids",["c1"]),("dataset_version","other"),
                             ("procedure",{"version":2}),("interval",{"interval_id":"other"})):
            changed = copy.deepcopy(task)
            changed["input_artifacts"][0][field] = value
            with self.service._db() as db, self.assertRaises(AnalysisContractError):
                self.service._recheck_review_binding(db,self.run,changed)
        self.orchestrator("verification",("skip","use","defer"))
        with self.service._db() as db:
            tasks = [t for t in self.service._tasks(db,self.rid) if t.get("input_artifacts")]
            self.assertEqual(len(tasks),2)
            self.assertEqual({t["input_artifacts"][0]["result_id"] for t in tasks},{"R0","R1"})
            self.assertEqual(len({t["idempotency_key"] for t in tasks}),2)

    def test_T10_saved_receipt_validates_after_restart_without_resending(self):
        self.orchestrator()
        with patch.object(self.service, "_validate_received", side_effect=lambda *a:None):
            task, (raw, meta) = self.execute_review()
        self.assertEqual(task["status"], "received")
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        self.service._validate_received(self.rid, task["task_id"])
        self.service._validate_received(self.rid, task["task_id"])
        self.service._execute(self.rid, task["task_id"])
        self.assertEqual(len(self.sent), 1)
        with self.service._db() as db:
            self.assertEqual(self.review_task_from_db(db)["status"], "succeeded")

    def test_T10_choice_and_binding_rollback_together_then_replay_once(self):
        register = self.service._register
        def crash(db, run, intent, **options):
            task = register(db,run,intent,**options)
            if intent.get("kind") == "finding_review":
                raise RuntimeError("Synthetic interruption after binding before commit")
            return task
        with patch.object(self.service,"_register",side_effect=crash), self.assertRaises(RuntimeError):
            self.orchestrator()
        with self.service._db() as db:
            self.assertFalse(any(t.get("input_artifacts") for t in self.service._tasks(db,self.rid)))
            self.assertEqual(self.service._artifact_history(db,self.run,"interpretation"),[])
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        self.orchestrator()
        with self.service._db() as db:
            self.assertEqual(len([t for t in self.service._tasks(db,self.rid) if t.get("input_artifacts")]),1)

    def test_T10_bound_unsent_task_survives_restart_without_rebinding(self):
        self.orchestrator()
        before = self.review_task()
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        task, (_,meta) = self.execute_review()
        self.assertEqual(task["task_id"],before["task_id"])
        self.assertEqual(task["input_artifacts"],before["input_artifacts"])
        self.assertEqual(meta["validation_status"],"valid")
        self.service._execute(self.rid,task["task_id"])
        self.assertEqual(len(self.sent),1)

    def test_T10_unknown_external_call_cannot_be_automatically_resent(self):
        self.orchestrator()
        with self.service._db() as db:
            task = self.review_task_from_db(db); task["status"] = "uncertain"
            self.service._write_task(db, task)
        self.service = self.make_service(adapter_version=ADAPTER_VERSION)
        status = self.service.resume("conversation", self.rid)
        self.assertEqual(status["status"], "recovery_required")
        self.assertEqual(self.calls, [])

    def test_T11_lineage_and_deferred_choice_reach_core_without_new_original_evidence(self):
        self.orchestrator()
        review_task, (_, review_meta) = self.execute_review()
        self.orchestrator(values=("defer",))
        with self.service._db() as db:
            run = self.service._read_run(db, self.rid)
            reports = self.service._domain_reports(db, run)
            rr = next(r for report in reports for r in report.get("review_results", []))
            self.assertEqual(rr["derived_from"][0]["result_id"], "R0")
            self.assertEqual(rr["claim_verdicts"][0]["evidence_ids"], [self.evidence["u6"]])
            self.assertTrue(any(r["disposition"] == "defer" for report in reports for r in report.get("artifact_decisions", [])))
            self.assertEqual(self.service._new_result_basis(db, run, [], [review_meta["result_id"]]), [])
            self.assertEqual(self.service._new_review_checks(db, run, [], [review_meta["result_id"]]), [review_meta["result_id"]])
            self.assertEqual(self.service._new_review_checks(db, run, [review_meta["result_id"]], [review_meta["result_id"]]), [])
            core = self.service._register(db, run, f.intent("core", "Integrate scoped reports"), phase="core", automatic=True)
            core_context = self.service._context(db, run, core)
            self.assertEqual(core_context["domain_reports"], reports)

    def test_T12_old_results_and_source_labels_remain_readable_unchanged(self):
        initial = self.service.result("conversation", self.rid)["initial"]
        labels = self.service.result("conversation", self.rid)["label_versions"]
        self.orchestrator()
        self.execute_review()
        exported = self.service.result("conversation", self.rid)
        self.assertEqual(exported["initial"], initial)
        self.assertEqual(exported["label_versions"], labels)
        self.assertEqual(self.service.result("conversation", self.rid,"R0")["raw"], self.sources[0][1])

    def test_T11_full_handler_loop_routes_review_and_integrates_lineage(self):
        packets = []
        selected = []
        def transport(*args, **kw):
            ctx = model_context.restored_reference_context(args[4], kw.get("data_messages"))
            role = args[5].removeprefix("analysis_orchestration_")
            packets.append((role, ctx))
            if ctx.get("input_artifacts"):
                return self.verdicts(ctx)
            if role == "core" and ctx.get("task", {}).get("phase") == "core":
                return f.stop(alternatives=["Evidence-limited alternative"])
            if role == "orchestrator":
                candidates = ctx.get("artifact_candidates", [])
                decisions = self.choices(candidates, ("skip",))
                eligible = [c for c in candidates if c["interval_id"] == selected_scope["interval_id"]]
                followup = []
                if ctx["review_domain"] == "interpretation" and not selected and eligible:
                    target = eligible[0]
                    next(d for d in decisions if d["result_id"] == target["result_id"])["disposition"] = "use"
                    followup = [self.intent(target["result_id"])]
                    followup[0]["interval_ids"] = [selected_scope["interval_id"]]
                    selected.append(target["result_id"])
                return f.core("Scoped assessment", stop=None, result_assessments=f.assess_pending_results(ctx),
                    artifact_decisions=decisions, intents=followup,
                    critique_responses=[{"issue_id":r["issue_id"],"disposition":"defer","reason":"Needs review","impact":"Keep limitation"}
                                        for r in ctx.get("issues", [])])
            raw = f.InitialSpecialistTests.valid_agent(self, role, ctx)
            if role == "interpretation" and ctx["task"].get("phase") == "initial_analysis" and ctx["coverage"]["page"]["interval_id"] == selected_scope["interval_id"]:
                raw["claims"] = [{"claim_id":c["claim_id"],"text":c["text"],"kind":c["kind"],
                    "evidence_ids":[ctx["raw_evidence"][0]["evidence_id"]]} for c in self.fixture["claims"]]
            return raw
        resolve, adapter = make_orchestration_adapters(call_ai_json=transport,
            load_token_config=lambda:SimpleNamespace(lmstudio_base_url="http://synthetic.invalid"),
            configured_ai_credentials=lambda *_:("", "synthetic"),
            context_meter=lambda *a, **kw:{"fits":True,"output_reserve":2000})
        self.agent = adapter
        payload = resolve({"artifact_review_version":1,"analysis_interval_version":1,"max_calls":150,"max_tasks":200,
            "model":"synthetic","question":"Which reasons and objections were expressed?"})
        run = f.RuntimeTests.start(self, request_id="full-loop", **payload)
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            selected_scope = interval_scope(self.service._read_run(db, run["run_id"])["analysis_partition"]["intervals"][0])
        old_scope = self.scope
        self.scope = selected_scope
        try:
            self.service.run(run["run_id"])
        finally:
            self.scope = old_scope
        result = self.service.status("conversation", run["run_id"])
        self.assertEqual(result["status"],"completed", (result.get("stop_reason"), result.get("error"),
            [(t["role"],t["phase"],t["status"],t["error"]) for t in result["tasks"]]))
        self.assertEqual(len([c for _,c in packets if c.get("input_artifacts")]),1)
        self.assertTrue(any(r.get("review_results") for role,c in packets if role == "core" for r in c.get("domain_reports",[])))
        self.assertTrue(all(not c.get("finding_resource") for role,c in packets if role == "verification"))


class QualityPlanTests(unittest.TestCase):
    def setUp(self):
        from artifact_review_quality import quality_plan
        fixture = json.loads((Path(__file__).parent / "fixtures/artifact_review_quality.json").read_text(encoding="utf-8"))
        self.plan = quality_plan(fixture)

    def records(self):
        return [{"trial_id":t["trial_id"],"fixture_hash":self.plan["fixture_hash"],
            "adapter_version":self.plan["adapter_version"],"procedure_hash":self.plan["procedure"]["sha256"],
            "status":"completed","adjudicated":True,"model":"synthetic-test-only","provider":"mock",
            "settings_hash":"synthetic-settings","run_id":"synthetic-test-run","raw_hash":"synthetic-test-hash",
            "counterexample_detected":t["category"] == "counterexample","insufficient_preserved":t["category"] == "insufficient",
            "ai_text_as_original":False,"fabricated_evidence":False,"scope_overgeneralization":False,
            "followed_incorrect_finding":False,"format_valid":True,"input_tokens":None,"output_tokens":None,"cost":None}
            for t in self.plan["trials"]]

    def test_A5_108_trials_and_missing_execution_is_not_a_pass(self):
        from artifact_review_quality import evaluate_quality
        self.assertEqual(len(self.plan["trials"]),108)
        summary = evaluate_quality(self.plan,[])
        self.assertEqual(summary["status"],"not_evaluated")
        self.assertEqual(len(summary["missing_trial_ids"]),108)
        self.assertIsNone(summary["conditions"]["incorrect_finding"]["counterexample_detected"])
        self.assertIsNone(summary["conditions"]["incorrect_finding"]["cost"])

    def test_A5_complete_quality_gate_and_incomplete_denominator(self):
        from artifact_review_quality import evaluate_quality
        records = self.records()
        self.assertEqual(evaluate_quality(self.plan,records)["status"],"pass")
        self.assertEqual(evaluate_quality(self.plan,records[:-1])["status"],"not_evaluated")
        self.assertEqual(evaluate_quality(self.plan,records[:-1])["conditions"]["incorrect_finding"]["counterexample_denominator"],18)

    def test_A5_anti_following_insufficient_and_major_error_gates(self):
        from artifact_review_quality import evaluate_quality
        for category, condition, field in (("counterexample","incorrect_finding","counterexample_detected"),
                ("insufficient","correct_finding","insufficient_preserved"),
                ("not_found","correct_finding","fabricated_evidence")):
            records = self.records()
            chosen = [i for i,t in enumerate(self.plan["trials"]) if t["category"] == category and t["condition"] == condition]
            for i in chosen[:2]: records[i][field] = field == "fabricated_evidence"
            self.assertEqual(evaluate_quality(self.plan,records)["status"],"fail")

    def test_A5_duplicate_and_mismatched_provenance_are_rejected(self):
        from artifact_review_quality import evaluate_quality
        records = self.records()
        with self.assertRaises(ValueError): evaluate_quality(self.plan,[records[0],records[0]])
        records[0]["fixture_hash"] = "other"
        with self.assertRaises(ValueError): evaluate_quality(self.plan,records)


if __name__ == "__main__":
    unittest.main()
