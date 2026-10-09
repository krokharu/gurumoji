"""F03 CPU boundaries and synthetic semantic controls; no model/SDK/API calls.

A constructed measurement ledger tests only the pure judge. It is never evidence
of an actual model run; the CLI CPU report always remains measurement_ready=False.
"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import io
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("f03_driver", ROOT / "scripts/test_expert_agent_model.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def H(label):
    return driver.canonical_hash(label)


class GuardedEntryTests(unittest.TestCase):
    def test_both_opt_in_entrypoints_hold_before_db_or_http_without_external_proof(self):
        saved_spec = importlib.util.spec_from_file_location("saved_driver", ROOT / "scripts/test_saved_autonomous_analysis.py")
        saved = importlib.util.module_from_spec(saved_spec); saved_spec.loader.exec_module(saved)
        # No real path is opened: the opt-in gate runs before database/model setup.
        with patch.dict(sys.modules, {"test_expert_agent_model": driver}):
            for module in (driver, saved):
                with self.subTest(module=module.__name__), patch.object(sys, "argv", ["TEST", "--guarded-receipt", "TEST-receipt"]), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(module.main(), 2)
                    state = json.loads(output.getvalue())
                    self.assertEqual(state["model_calls"], 0)
                    self.assertFalse(state["measurement_ready"])
                    self.assertIn("current_source_manifest_required", state["blockers"])

    def test_json_self_declaration_and_stale_sources_cannot_enable_post(self):
        manifest = driver.current_guarded_manifest()
        state = driver.prepare_guarded_entry(manifest, "TEST-receipt")
        self.assertIsNone(state["factory"])
        self.assertFalse(state["measurement_ready"])
        self.assertEqual(state["model_calls"], 0)
        manifest[next(iter(manifest))] = "0" * 64
        state = driver.prepare_guarded_entry(manifest, "TEST-receipt")
        self.assertEqual(state["blockers"], ["current_source_manifest_required"])

    def test_programmatic_synthetic_seam_binds_current_sources_and_per_run_factory(self):
        from gurumoji.services.ai.request_budget import BatchQuota
        from test_ai_request_budget import CONDITIONS, count_proof, Clock
        from gurumoji.analysis_orchestration import OrchestrationBudget
        seen = []
        def verify(manifest, receipt):
            seen.append((manifest, receipt))
            return {key: True for key in ("accepted", "model_verified", "context_verified", "tokenizer_verified", "template_verified", "full_schema_verified")} | {"conditions": CONDITIONS}
        state = driver.prepare_guarded_entry(driver.current_guarded_manifest(), CONDITIONS["acceptance_anchor"],
            verify_receipt=verify, token_counter=count_proof, batch=BatchQuota(max_calls=216, max_tokens=6193152),
            policy={"trial_call_limit": 6, "trial_token_limit": 172032})
        self.assertFalse(state["measurement_ready"])
        self.assertEqual(state["blockers"], ["synthetic_evidence_only"])
        clock = Clock()
        budget = state["factory"](run_id="TEST-entry-run", run_started_at=clock(), clock=clock)
        controller = OrchestrationBudget(budget, run_id="TEST-entry-run", run_started_at=clock(), clock=clock)
        self.assertEqual(controller.snapshot()["ledger"]["entry_count"], 0)
        self.assertEqual(seen[0][0], driver.current_guarded_manifest())


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-f03-test-")
        cls.cpu = {cid: driver.prepare_cpu_case(cid, Path(cls.temporary.name) / cid / "test.sqlite3")
                   for cid in driver.F03_CASES}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def accepted_manifest(self, revision):
        """Fictitious external approval defined before observations, never real C0 acceptance."""
        revisions = {}
        for r in (0, 1):
            conditions = {}
            for cid, cpu in self.cpu.items():
                conditions[cid] = {}
                for condition in ("A", "B"):
                    hashes = {k: H("fixed-" + k) for k in driver.F03_TRIAL_HASHES}
                    hashes.update(input=cpu["input_hash"], case=cpu["fixture_hash"], schema=driver.F03_SCHEMA_HASH,
                        condition=H("condition-A" if condition == "A" else "condition-B-" + str(r)))
                    conditions[cid][condition] = hashes
            revisions[str(r)] = {"acceptance_receipt_id": "SYNTHETIC-PREACCEPTED-R" + str(r),
                                 "accepted_monotonic": 0.0 if r == 0 else 360.0, "conditions": conditions}
        if revision == 0:
            revisions["1"] = None
        return {"schema_version": "f03-preaccepted-1", "comparison_id": "synthetic-unit-control",
                "revisions": revisions}

    def measurement(self, *, revision=0, A_input=100, B_input=88, gap_improvement=False):
        """Invented metadata for pure unit controls, with real synthetic CPU cells."""
        self.preaccepted_manifest = self.accepted_manifest(revision)
        trials, receipts, sequence = [], {}, 0
        condition_hashes = {str(r): {"A": H("condition-A"), "B": H("condition-B-" + str(r))}
                            for r in (0, 1)}
        order = driver.comparison_order(0) + (driver.comparison_order(1) if revision == 1 else [])
        for index, entry in enumerate(order):
            tid, cid = entry["trial_id"], entry["case_id"]
            cpu = self.cpu[cid]
            input_per_call = A_input // 2 if entry["condition"] == "A" else B_input // 2
            start = 1.0 + index * 20.0
            calls, call_receipts = [], {}
            for phase, offset in (("plan", .4), ("explanation", 4.4)):
                task_id, attempt_id = tid + "-" + phase, tid + "-" + phase + "-post0"
                raw_usage = {"prompt_tokens": input_per_call, "completion_tokens": 20,
                             "completion_tokens_details": {"reasoning_tokens": 5},
                             "total_tokens": input_per_call + 20}
                semantics = {"completion_includes_reasoning": True, "total_includes_reasoning": True,
                             "absent_reasoning_is_zero": False}
                usage = driver.inspect_raw_usage(raw_usage, semantics)
                call = {"task_id": task_id, "attempt_id": attempt_id, "phase": phase, "round": 0,
                        "dispatch_state": "returned", "request_hash": H(attempt_id),
                        "full_input_tokens_preflight": input_per_call,
                        **{k: usage[k] for k in ("raw_usage_exists", "present_usage_fields", "input_tokens",
                              "output_tokens", "reasoning_tokens", "total_tokens", "token_completeness")},
                        "elapsed_seconds": 1.0, "error_kind": None}
                calls.append(call)
                task_start = start + (.1 if phase == "plan" else 4.1)
                call_receipts[attempt_id] = {
                    "entrance_id": task_id + "-entry0", "wire_sequence": sequence,
                    "request_hash": call["request_hash"], "raw_usage": raw_usage,
                    "usage_semantics": semantics, "usage": usage,
                    "count_coverage": {k: True for k in driver.F03_WIRE_COVERAGE},
                    "output_cap_tokens": 4096, "reserved_tokens": input_per_call + 4096,
                    "sent_monotonic": start + offset, "finished_monotonic": start + offset + 1,
                    "task_started_monotonic": task_start, "task_remaining_seconds": 240 - (start + offset - task_start),
                    "run_remaining_seconds": 600 - offset, "wire_timeout_seconds": 10.0, "cleanup_seconds": 5.0,
                    "reservation_retained": True,
                }
                sequence += 1
            code_tasks = [{"task_id": tid + "-" + method, "method_id": method,
                           "result_id": tid + "-" + method + "-result",
                           "raw_hash": H(self.cpu[cid]["cpu_calculation_raws"][method]),
                           "status": self.cpu[cid]["cpu_calculation_raws"][method]["status"]}
                          for method in ("pearson", "spearman")]
            checks = [{"item_id": item, "status": "unmet" if gap_improvement and entry["condition"] == "A"
                       and i == 0 else "met", "evidence_ref": tid + "-synthetic-review-" + item}
                      for i, item in enumerate(driver.F03_GAP_CATALOG[cid])]
            trial = {**entry, "fixture_hash": cpu["fixture_hash"], "app_run_id": tid + "-app",
                     "state": "completed", "calls": calls, "code_tasks": code_tasks,
                     "quality": {"status": "pass", "critical_errors": [], "unnecessary_rejections": 0,
                                 "item_checks": checks}, "input_tokens": input_per_call * 2, "output_tokens": 40,
                     "reasoning_tokens": 10, "total_tokens": (input_per_call + 20) * 2,
                     "complete_usage_calls": 2, "missing_usage_calls": 0, "hook_rounds": 0,
                     "hook_requests": 0, "knowledge_receipts": [],
                     "elapsed_seconds": 10.0 if entry["condition"] == "A" else 9.0,
                     "initial_cpu_seconds": .1, "queue_wait_seconds": .1,
                     "source_unchanged": True, "error_kind": None}
            hashes = copy.deepcopy(self.preaccepted_manifest["revisions"][str(entry["revision"])]
                                   ["conditions"][cid][entry["condition"]])
            receipt = {"started": True, "hashes": hashes, "calls": call_receipts,
                       "input_version": cpu["input_version"],
                       "handler_reserved_calls": 2, "call_ai_entrances": 2,
                       "final_status": "needs_input" if cid == "C2" else "draft",
                       "calculation_result_ids": [t["result_id"] for t in code_tasks],
                       "missing_inputs": ["paired observations", "varying characters"] if cid == "C2" else [],
                       "route_evaluated": True, "included_ids": list(cpu["included_ids"]),
                       "excluded_ids": list(cpu["excluded_ids"]),
                       "critical_checks": {k: "met" for k in driver.F03_CRITICAL},
                       "run_started_monotonic": start, "run_ended_monotonic": start + trial["elapsed_seconds"],
                       "quality_reviewer": "SYNTHETIC-UNIT-CONTROL",
                       "quality_review_kind": "independent", "hooks": {"plan": [], "explanation": []},
                       "code_executed_ids": [t["task_id"] for t in code_tasks],
                       "calculation_raws": copy.deepcopy(cpu["cpu_calculation_raws"]),
                       "task_clocks": {
                           tid + "-plan": {"started": start + .1, "ended": start + 2},
                           tid + "-pearson": {"started": start + 2, "ended": start + 3},
                           tid + "-spearman": {"started": start + 3, "ended": start + 4},
                           tid + "-explanation": {"started": start + 4.1, "ended": start + 6},
                       }}
            def segment(kind, begin, end, task=None, attempt=None):
                return {"kind": kind, "task_id": tid + "-" + task if task else None,
                        "attempt_id": tid + "-" + attempt if attempt else None,
                        "started": start + begin, "ended": start + end}
            receipt["clock_segments"] = [
                segment("initial_cpu", 0, .1), segment("queue", .1, .2, "plan"),
                segment("context", .2, .4, "plan"), segment("wire", .4, 1.4, "plan", "plan-post0"),
                segment("validation", 1.4, 1.9, "plan"), segment("cleanup", 1.9, 2, "plan"),
                segment("code", 2, 2.9, "pearson"), segment("validation", 2.9, 3, "pearson"),
                segment("code", 3, 3.9, "spearman"), segment("validation", 3.9, 4, "spearman"),
                segment("validation", 4, 4.1), segment("context", 4.1, 4.4, "explanation"),
                segment("wire", 4.4, 5.4, "explanation", "explanation-post0"),
                segment("validation", 5.4, 5.9, "explanation"), segment("cleanup", 5.9, 6, "explanation"),
                segment("validation", 6, 6.1), segment("cleanup", 6.1, trial["elapsed_seconds"])]
            trials.append(trial); receipts[tid] = receipt
        limits = {k: p.get("const") for k, p in driver.F03_RESULT_SCHEMA["properties"]["limits"]["properties"].items()}
        limits.update(effective_context_tokens=32768, input_cap_tokens=24576,
                      output_including_reasoning_cap_tokens=4096, total_token_cap=6193152)
        result = {"schema_version": "f03-result-1", "comparison_id": "synthetic-unit-control",
                  "spec_hash": driver.F03_SPEC_HASH, "plan_hash": driver.F03_PLAN_HASH,
                  "preparation_commit": "a" * 40, "baseline_commit": "b" * 40,
                  "corpus_hash": H("fixed-corpus"), "model_condition_hash": H("fixed-model_condition"),
                  "measurement_ready": True, "ready_blockers": [], "limits": limits, "trials": trials,
                  "totals": driver.comparison_totals(trials, receipts), "verdict": "hold", "not_run": []}
        payload = {"fixed_hashes": {"spec": driver.F03_SPEC_HASH, "schema": driver.F03_SCHEMA_HASH,
                   "corrections": driver.F03_CORRECTIONS_HASH, "guard_findings": driver.F03_GUARD_FINDINGS_HASH,
                   "script": H("fixed-script"), "validator": H("fixed-validator"), "runtime_guard": H("fixed-guard"),
                   "case_inputs": {cid: self.cpu[cid]["input_hash"] for cid in driver.F03_CASES}},
                   "readiness": {**{k: True for k in driver.F03_READY_FLAGS},
                                 "model_instance_id": "SYNTHETIC-UNIT-CONTROL-not-a-loaded-model",
                                 "parallel": 1, "baseline_commit": result["baseline_commit"], "kv_reused": False,
                                 "generated_warmup_calls": 0},
                   "time_scope": copy.deepcopy(driver.F03_TIME_SCOPE), "revision1_authorized": revision == 1,
                   "preaccepted_manifest_hash": H(self.preaccepted_manifest),
                   "condition_hashes": condition_hashes, "trials": receipts, "core_calls": 0}
        return result, payload

    def assess(self, result, payload, *, recalculate=False):
        if recalculate:
            for trial in result["trials"]:
                calls = [c for c in trial["calls"] if c["dispatch_state"] != "not_dispatched"]
                trial["complete_usage_calls"] = sum(c["token_completeness"] == "complete" for c in calls)
                trial["missing_usage_calls"] = len(calls) - trial["complete_usage_calls"]
                for field in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
                    values = [c[field] for c in calls]
                    trial[field] = sum(values) if values and all(v is not None for v in values) else None
            result["totals"] = driver.comparison_totals(result["trials"], payload["trials"])
        return driver.assess_comparison(result, driver.bind_comparison_evidence(result, payload),
                                       preaccepted_manifest=self.preaccepted_manifest)

    def assertReject(self, result, payload, prefix):
        judged = self.assess(result, payload)
        self.assertFalse(judged["valid"], judged)
        self.assertTrue(any(e.startswith(prefix) for e in judged["errors"]), judged)
        self.assertEqual(judged["verdict"], "hold")

    def test_fixed_order_and_single_revision(self):
        first, second = driver.comparison_order(), driver.comparison_order(1)
        self.assertEqual([t["condition"] for t in first[:6]], ["A", "B", "B", "A", "A", "B"])
        self.assertEqual(len({t["trial_id"] for t in first + second}), 36)
        self.assertEqual([t["condition"] for t in second], [{"A": "B", "B": "A"}[t["condition"]] for t in first])
        for revision in (2, -1, True):
            with self.assertRaises(ValueError):
                driver.comparison_order(revision)

    def test_saved_annotation_is_the_exclusion_contract(self):
        for cid, cpu in self.cpu.items():
            self.assertEqual(cpu["included_ids"], [f"{cid}-u{i}" for i in range(1, 7)])
            self.assertEqual(cpu["excluded_ids"], [cid + "-excluded"])
            self.assertEqual(cpu["family_results"], 30)
        raw = driver.prepare_cpu_case("C2", Path(self.temporary.name) / "raw" / "test.sqlite3",
                                     save_exclusion=False)
        self.assertEqual(len(raw["included_ids"]), 7)
        self.assertEqual(raw["excluded_ids"], [])
        self.assertEqual(raw["primary"]["pearson"]["status"], "computed")
        with self.assertRaises(ValueError):
            driver.prepare_cpu_case("C1", Path(self.temporary.name) / "C1" / "test.sqlite3")

    def test_independent_oracle_N_null_participants_and_coefficient(self):
        self.assertEqual(self.cpu["C2"]["primary"]["pearson"]["n"], 2)
        self.assertEqual(self.cpu["C2"]["primary"]["pearson"]["missing"], 4)
        self.assertIsNone(self.cpu["C2"]["primary"]["pearson"]["coefficient"])
        self.assertIsNone(self.cpu["C2"]["primary"]["spearman"]["p_value"])
        self.assertEqual(self.cpu["C3"]["oracle"]["speaker_count"], 2)
        self.assertAlmostEqual(self.cpu["C1"]["oracle"]["pearson"]["coefficient"], .9340038280798552)
        self.assertAlmostEqual(self.cpu["C3"]["oracle"]["spearman"]["coefficient"], .5428571428571428)
        self.assertNotIn("oracle", driver.build_comparison_case("C1"))
        options = driver.comparison_options("C1")
        self.assertEqual((options["max_calls"], options["max_tasks"], options["concurrency"]), (6, 4, 1))
        self.assertEqual((options["time_limit_seconds"], options["call_timeout_seconds"]), (600, 240))
        self.assertEqual(options["publication_targets"], [])
        self.assertNotIn(".934", json.dumps(options))

    def test_both_efficiency_branches_and_revision_outcomes(self):
        for revision, B_input, gaps, expected in ((0, 88, False, "continue"), (0, 100, True, "continue"),
                                                 (0, 100, False, "rework"), (1, 100, False, "stop")):
            result, payload = self.measurement(revision=revision, B_input=B_input, gap_improvement=gaps)
            judged = self.assess(result, payload)
            self.assertTrue(judged["valid"], judged)
            self.assertEqual(judged["verdict"], expected)

    def test_notready_continue_rejected_and_honest_hold_preserved(self):
        result, payload = self.measurement()
        payload["readiness"]["guard_accepted"] = False
        result["measurement_ready"] = False
        result["ready_blockers"] = ["guard_pending"]
        self.assertEqual(self.assess(result, payload)["verdict"], "hold")
        result["verdict"] = "continue"
        self.assertReject(result, payload, "declared_verdict")

    def test_null_caps_cannot_claim_ready(self):
        result, payload = self.measurement()
        result["limits"]["effective_context_tokens"] = None
        self.assertReject(result, payload, "measurement_ready_without_evidence")

    def test_duplicate_trial_ids_and_attribute_mismatch(self):
        result, payload = self.measurement()
        result["trials"].append(copy.deepcopy(result["trials"][0]))
        self.assertReject(result, payload, "trial_ids_unique_receipts")
        result, payload = self.measurement()
        result["trials"][0]["case_id"] = "C2"
        self.assertReject(result, payload, "trial_id_attributes")

    def test_wire_217_and_plan_only_completed_trial_rejected(self):
        result, payload = self.measurement()
        result["totals"]["model_transport_attempts"] = 217
        self.assertReject(result, payload, "batch_call_budget")
        result, payload = self.measurement()
        trial = result["trials"][0]
        trial["calls"][1]["phase"] = "plan"
        self.assertReject(result, payload, "completed_phase_and_calculation_route")

    def test_raw_absent_complete_and_complete_null_total_rejected(self):
        result, payload = self.measurement()
        result["trials"][0]["calls"][0]["raw_usage_exists"] = False
        self.assertReject(result, payload, "raw_usage_completeness")
        result, payload = self.measurement()
        result["trials"][0]["calls"][0]["total_tokens"] = None
        self.assertReject(result, payload, "raw_usage_completeness")

    def test_failed_denominator_kept_and_success_subset_not_adopted(self):
        result, payload = self.measurement()
        result["trials"][0]["state"] = "failed"
        self.assertReject(result, payload, "totals_denominators")
        judged = self.assess(result, payload, recalculate=True)
        self.assertTrue(judged["valid"], judged)
        self.assertEqual(result["totals"]["failed_trials"], 1)
        self.assertEqual(result["totals"]["trials_started"], 18)
        self.assertEqual(result["totals"]["model_transport_attempts"], 36)
        self.assertEqual(judged["verdict"], "hold")

    def test_partial_usage_stops_following_calls_and_retains_unknown_reservation(self):
        result, payload = self.measurement()
        t = result["trials"][0]; c = t["calls"][0]
        receipt = payload["trials"][t["trial_id"]]["calls"][c["attempt_id"]]
        receipt["raw_usage"] = {"prompt_tokens": 50}
        receipt["usage"] = driver.inspect_raw_usage(receipt["raw_usage"], receipt["usage_semantics"])
        for k in ("raw_usage_exists", "present_usage_fields", "input_tokens", "output_tokens",
                  "reasoning_tokens", "total_tokens", "token_completeness"):
            c[k] = receipt["usage"][k]
        judged = self.assess(result, payload, recalculate=True)
        self.assertIn("post_after_unknown_usage_or_outcome", judged["errors"])
        self.assertIsNone(result["totals"]["total_tokens"])
        receipt["reservation_retained"] = False
        judged = self.assess(result, payload)
        self.assertTrue(any(e.startswith("unknown_reservation_released") for e in judged["errors"]))

    def test_unknown_usage_at_last_trial_honestly_hold(self):
        result, payload = self.measurement()
        t = result["trials"][-1]; c = t["calls"][-1]
        receipt = payload["trials"][t["trial_id"]]["calls"][c["attempt_id"]]
        receipt["raw_usage"] = None
        receipt["usage"] = driver.inspect_raw_usage(None, {})
        for k in ("raw_usage_exists", "present_usage_fields", "input_tokens", "output_tokens",
                  "reasoning_tokens", "total_tokens", "token_completeness"):
            c[k] = receipt["usage"][k]
        t["state"] = "failed"
        judged = self.assess(result, payload, recalculate=True)
        self.assertTrue(judged["valid"], judged)
        self.assertEqual(judged["verdict"], "hold")
        self.assertEqual(result["totals"]["missing_usage_calls"], 1)
        self.assertIsNone(result["totals"]["total_tokens"])

    def test_usage_semantics_doublecount_and_invalid_raw_types(self):
        raw = {"prompt_tokens": 100, "completion_tokens": 20,
               "completion_tokens_details": {"reasoning_tokens": 5}}
        known = {"completion_includes_reasoning": True, "total_includes_reasoning": True}
        self.assertEqual(driver.inspect_raw_usage(raw, known)["total_tokens"], 120)
        self.assertIsNone(driver.inspect_raw_usage(raw, {})["total_tokens"])
        self.assertIsNone(driver.inspect_raw_usage(None, known)["input_tokens"])
        for wrong in (True, "100", -1, 1.5, float("nan"), float("inf")):
            bad = copy.deepcopy(raw); bad["prompt_tokens"] = wrong
            self.assertNotEqual(driver.inspect_raw_usage(bad, known)["token_completeness"], "complete")
        raw["prompt_tokens_details"] = {"cached_tokens": 20}
        measured = driver.inspect_raw_usage(raw, known)
        self.assertEqual(measured["total_tokens"], 120)
        self.assertEqual(measured["input_tokens"], 100)
        self.assertIn("cached_tokens", measured["present_usage_fields"])
        raw["prompt_tokens_details"]["cached_tokens"] = True
        self.assertNotEqual(driver.inspect_raw_usage(raw, known)["token_completeness"], "complete")
        self.assertIsNone(driver.inspect_raw_usage(None, None)["total_tokens"])

    def test_missing_and_wrong_type_sidecar_fail_closed_without_crashing(self):
        for key, value in (("readiness", None), ("trials", None), ("condition_hashes", [])):
            result, payload = self.measurement()
            payload[key] = value
            judged = self.assess(result, payload)
            self.assertFalse(judged["valid"], judged)
            self.assertFalse(judged["measurement_ready"])
            self.assertEqual(judged["verdict"], "hold")
        result, payload = self.measurement()
        result["trials"][0]["calls"][0]["present_usage_fields"] = [float("nan")]
        judged = driver.assess_comparison(result, {})
        self.assertFalse(judged["valid"])

    def test_deadline_outputcap_count_coverage_and_reservation(self):
        for mutation, error in (
                (lambda a: a.update(wire_timeout_seconds=240), "remaining_deadline"),
                (lambda a: a["count_coverage"].update(response_schema=False), "wire_coverage"),
                (lambda a: a.update(reserved_tokens=0), "token_reservation"),
                (lambda a: a.update(output_cap_tokens=10), "token_reservation")):
            result, payload = self.measurement()
            first = result["trials"][0]
            mutation(payload["trials"][first["trial_id"]]["calls"][first["calls"][0]["attempt_id"]])
            self.assertReject(result, payload, error)

    def test_missing_pairs_pending_quality_condition_mismatch_and_zero_baseline_hold(self):
        result, payload = self.measurement()
        removed = result["trials"].pop()
        payload["trials"].pop(removed["trial_id"])
        self.assertEqual(self.assess(result, payload, recalculate=True)["verdict"], "hold")
        result, payload = self.measurement()
        result["trials"][0]["quality"]["status"] = "review_pending"
        self.assertEqual(self.assess(result, payload)["verdict"], "hold")
        result, payload = self.measurement()
        payload["trials"][result["trials"][0]["trial_id"]]["hashes"]["input"] = H("different input")
        self.assertEqual(self.assess(result, payload)["verdict"], "hold")
        result, payload = self.measurement()
        result["trials"][0]["quality"]["item_checks"][0]["status"] = "unknown"
        self.assertEqual(self.assess(result, payload)["verdict"], "hold")
        result, payload = self.measurement(A_input=0, B_input=0)
        judged = self.assess(result, payload)
        self.assertTrue(judged["valid"], judged)
        self.assertEqual(judged["verdict"], "hold")
        self.assertTrue(any(b.startswith("zero_baseline:") for b in judged["blockers"]))

    def test_unknown_normal_control_and_clock_breakdown_hold(self):
        for field in ("unnecessary_rejections", "initial_cpu_seconds", "queue_wait_seconds"):
            result, payload = self.measurement()
            target = result["trials"][0]["quality"] if field == "unnecessary_rejections" else result["trials"][0]
            target[field] = None
            judged = self.assess(result, payload)
            self.assertTrue(judged["valid"], judged)
            self.assertEqual(judged["verdict"], "hold")

    def test_completed_trial_needs_real_phase_and_four_started_tasks(self):
        result, payload = self.measurement()
        trial = result["trials"][0]
        trial["app_run_id"] = None
        payload["trials"][trial["trial_id"]]["started"] = False
        judged = self.assess(result, payload, recalculate=True)
        self.assertTrue(any(e.startswith("execution_without_started_trial:") for e in judged["errors"]))
        result, payload = self.measurement()
        trial = result["trials"][0]
        trial["calls"][1]["dispatch_state"] = "not_dispatched"
        judged = self.assess(result, payload, recalculate=True)
        self.assertTrue(any(e.startswith("completed_phase_and_calculation_route:") for e in judged["errors"]))
        result, payload = self.measurement()
        trial = result["trials"][0]
        trial["calls"][1]["task_id"] = trial["calls"][0]["task_id"]
        self.assertReject(result, payload, "completed_phase_and_calculation_route")

    def test_saved_numeric_cell_cannot_be_changed_even_with_valid_new_hashes(self):
        for cid, field, value in (("C1", "coefficient", -.93400383), ("C1", "n", 7),
                                  ("C2", "coefficient", 0), ("C3", "p_value", .0001)):
            result, payload = self.measurement()
            trial = next(t for t in result["trials"] if t["case_id"] == cid)
            receipt = payload["trials"][trial["trial_id"]]
            raw = receipt["calculation_raws"]["pearson"]
            rows = raw["datasets"]["correlations"]["rows"]
            primary = next(r for r in rows if r["variable_a"] == "duration_seconds" and r["variable_b"] == "characters")
            primary[field] = value
            for i, row in enumerate(rows):
                row["row_id"] = "sha256:" + H(["pearson", i, {k: v for k, v in row.items() if k != "row_id"}])
            raw["manifest"]["rows_hash"] = "sha256:" + H(rows)
            trial["code_tasks"][0]["raw_hash"] = H(raw)
            judged = self.assess(result, payload)
            self.assertFalse(judged["valid"], judged)
            self.assertTrue(any(e.startswith("calculation_numeric:") or e.startswith("calculation_N_null_units:")
                                for e in judged["errors"]), judged)

    def test_deadline_task_reset_late_reply_and_total_reservation_cannot_pass(self):
        result, payload = self.measurement()
        trial = result["trials"][0]; receipt = payload["trials"][trial["trial_id"]]
        call = receipt["calls"][trial["calls"][0]["attempt_id"]]
        call["task_started_monotonic"] += 1
        self.assertReject(result, payload, "task_clock_reset")
        result, payload = self.measurement()
        trial = result["trials"][0]; receipt = payload["trials"][trial["trial_id"]]
        call = receipt["calls"][trial["calls"][0]["attempt_id"]]
        call["finished_monotonic"] = call["task_started_monotonic"] + 241
        self.assertReject(result, payload, "late_or_invalid_call_clock")
        result, payload = self.measurement()
        result["limits"]["total_token_cap"] = 4145
        self.assertReject(result, payload, "batch_token_reservation")

    def test_C2_needs_input_route_and_critical_actor_scope_are_not_success_labels(self):
        result, payload = self.measurement()
        trial = next(t for t in result["trials"] if t["case_id"] == "C2")
        payload["trials"][trial["trial_id"]]["final_status"] = "draft"
        self.assertReject(result, payload, "completed_phase_and_calculation_route")
        result, payload = self.measurement()
        trial = result["trials"][0]
        payload["trials"][trial["trial_id"]]["critical_checks"]["actor"] = "unmet"
        self.assertReject(result, payload, "critical_unresolved")
        result, payload = self.measurement()
        trial = result["trials"][0]
        payload["trials"][trial["trial_id"]]["included_ids"].append("C1-excluded")
        self.assertReject(result, payload, "exclusion_ids")

    def test_revision_history_cannot_reset_and_sidecar_hash_cannot_be_swapped(self):
        result, payload = self.measurement(revision=1)
        result["trials"] = result["trials"][18:]
        payload["trials"] = {k: v for k, v in payload["trials"].items() if k.startswith("r1-")}
        judged = self.assess(result, payload, recalculate=True)
        self.assertIn("revision1_history_or_candidate_version", judged["errors"])
        result, payload = self.measurement()
        evidence = driver.bind_comparison_evidence(result, payload)
        evidence["payload"]["core_calls"] = 1
        self.assertFalse(driver.assess_comparison(result, evidence)["valid"])

    def test_shape_strict_types_extra_fields_and_hash(self):
        for key, value in (("input_tokens", True), ("input_tokens", -1), ("input_tokens", 1.5),
                           ("round", 3), ("request_hash", "not-a-hash")):
            result, payload = self.measurement()
            result["trials"][0]["calls"][0][key] = value
            self.assertTrue(any(e.startswith("shape:") for e in self.assess(result, payload)["errors"]))
        result, payload = self.measurement(); result["extra"] = "forbidden"
        self.assertTrue(any("additionalProperties" in e for e in self.assess(result, payload)["errors"]))

    @staticmethod
    def rehash_calculation(trial, receipt, method="pearson"):
        raw = receipt["calculation_raws"][method]
        rows = raw["datasets"]["correlations"]["rows"]
        for index, row in enumerate(rows):
            row["row_id"] = "sha256:" + H([method, index, {k: v for k, v in row.items() if k != "row_id"}])
        raw["manifest"]["rows_hash"] = "sha256:" + H(rows)
        next(c for c in trial["code_tasks"] if c["method_id"] == method)["raw_hash"] = H(raw)

    @staticmethod
    def shift_trial_clock(receipt, delta):
        for key in ("run_started_monotonic", "run_ended_monotonic"):
            if receipt[key] is not None:
                receipt[key] += delta
        for clock in receipt["task_clocks"].values():
            for key in ("started", "ended"):
                if clock[key] is not None:
                    clock[key] += delta
        for attempt in receipt["calls"].values():
            for key in ("sent_monotonic", "finished_monotonic", "task_started_monotonic"):
                if attempt[key] is not None:
                    attempt[key] += delta
        for segment in receipt["clock_segments"]:
            for key in ("started", "ended"):
                if segment[key] is not None:
                    segment[key] += delta

    def test_IR01_rehashed_analysis_unit_group_and_inference_policy_reject(self):
        alterations = [
            lambda raw: raw["manifest"].update(group_count=6),
            lambda raw: raw["manifest"].update(analysis_unit="participant"),
            lambda raw: raw["manifest"].update(group_variable="participant"),
            lambda raw: raw["manifest"]["inference_policy"].update(mode="confirmatory"),
            lambda raw: raw["manifest"]["inference_policy"].update(p_value_adjustment="bonferroni"),
            lambda raw: raw["manifest"]["inference_policy"].update(independence_verified=True),
            lambda raw: raw["manifest"]["inference_policy"].update(independence_verified=0),
            lambda raw: next(x for x in raw["datasets"]["correlations"]["rows"]
                if x["variable_a"] == "duration_seconds" and x["variable_b"] == "characters").update(analysis_unit="participant"),
        ]
        for alter in alterations:
            result, payload = self.measurement()
            trial = next(t for t in result["trials"] if t["case_id"] == "C3")
            receipt = payload["trials"][trial["trial_id"]]
            alter(receipt["calculation_raws"]["pearson"])
            self.rehash_calculation(trial, receipt)
            judged = self.assess(result, payload)
            self.assertFalse(judged["valid"], judged)
            self.assertEqual(judged["verdict"], "hold")
            self.assertTrue(any("calculation_analysis_scope_policy:" in e or "calculation_N_null_units:" in e
                                for e in judged["errors"]), judged)
        result, payload = self.measurement()
        self.assertEqual(self.assess(result, payload)["verdict"], "continue")

    def test_IR02_clock_breakdown_and_fully_consistent_late_return_reject(self):
        for field, value in (("initial_cpu_seconds", 700), ("queue_wait_seconds", 800)):
            result, payload = self.measurement()
            result["trials"][0][field] = value
            self.assertReject(result, payload, "clock_breakdown")
        result, payload = self.measurement()
        trial = result["trials"][0]; receipt = payload["trials"][trial["trial_id"]]
        first = trial["calls"][0]; attempt = receipt["calls"][first["attempt_id"]]
        boundary, extra = attempt["finished_monotonic"], 99.0
        attempt["wire_timeout_seconds"] = 1.0
        for segment in receipt["clock_segments"]:
            for key in ("started", "ended"):
                if segment[key] >= boundary:
                    segment[key] += extra
        for clock in receipt["task_clocks"].values():
            for key in ("started", "ended"):
                if clock[key] >= boundary:
                    clock[key] += extra
        for call in trial["calls"]:
            observation = receipt["calls"][call["attempt_id"]]
            for key in ("sent_monotonic", "finished_monotonic", "task_started_monotonic"):
                if observation[key] >= boundary:
                    observation[key] += extra
            call["elapsed_seconds"] = observation["finished_monotonic"] - observation["sent_monotonic"]
            observation["task_remaining_seconds"] = 240 - (observation["sent_monotonic"] - observation["task_started_monotonic"])
            observation["run_remaining_seconds"] = 600 - (observation["sent_monotonic"] - receipt["run_started_monotonic"])
        receipt["run_ended_monotonic"] += extra
        trial["elapsed_seconds"] += extra
        for later in result["trials"][1:]:
            self.shift_trial_clock(payload["trials"][later["trial_id"]], extra)
        judged = self.assess(result, payload, recalculate=True)
        self.assertEqual(judged["errors"], ["returned_after_wire_deadline:" + trial["trial_id"]], judged)
        self.assertEqual(judged["verdict"], "hold")
        result, payload = self.measurement()
        self.assertEqual(self.assess(result, payload)["verdict"], "continue")

    def test_IR02_remaining_deadline_boundary_controls(self):
        for remaining, wire, expected in ((240, 235, True), (6, 1, True), (5.999, 1, False)):
            result, payload = self.measurement()
            # One early running trial avoids claiming completed quality for this clock control.
            trial = result["trials"][0]; tid = trial["trial_id"]
            result["trials"] = [trial]; payload["trials"] = {tid: payload["trials"][tid]}
            receipt = payload["trials"][tid]; call = trial["calls"][0]
            trial["state"] = "running"; trial["calls"] = [call]; trial["code_tasks"] = []
            receipt["calls"] = {call["attempt_id"]: receipt["calls"][call["attempt_id"]]}
            attempt = receipt["calls"][call["attempt_id"]]
            sent = 1 + 240 - remaining
            attempt.update(sent_monotonic=sent, finished_monotonic=sent + .1,
                task_started_monotonic=1.0, task_remaining_seconds=remaining,
                run_remaining_seconds=600 - (sent - .9), wire_timeout_seconds=wire)
            receipt.update(run_started_monotonic=.9, run_ended_monotonic=sent + .2,
                code_executed_ids=[], call_ai_entrances=1, handler_reserved_calls=1,
                task_clocks={call["task_id"]: {"started": 1.0, "ended": sent + .2}})
            trial.update(elapsed_seconds=sent + .2 - .9, initial_cpu_seconds=.1, queue_wait_seconds=0.0)
            call["elapsed_seconds"] = .1
            def seg(kind, begin, end, task=None, aid=None):
                return {"kind":kind, "started":begin, "ended":end, "task_id":task, "attempt_id":aid}
            receipt["clock_segments"] = [seg("initial_cpu", .9, 1), seg("context", 1, sent, call["task_id"]),
                seg("wire", sent, sent + .1, call["task_id"], call["attempt_id"]),
                seg("cleanup", sent + .1, sent + .2, call["task_id"])]
            judged = self.assess(result, payload, recalculate=True)
            if expected:
                self.assertTrue(judged["valid"], judged)
                self.assertEqual(judged["verdict"], "hold")
            else:
                self.assertTrue(any(e.startswith("remaining_deadline:") for e in judged["errors"]), judged)

    def test_IR03_schedule_parallel_overlap_and_phase_clock_order_reject(self):
        for delta_a, delta_b in ((20, -20), (0, -20)):
            result, payload = self.measurement()
            self.shift_trial_clock(payload["trials"][result["trials"][0]["trial_id"]], delta_a)
            self.shift_trial_clock(payload["trials"][result["trials"][1]["trial_id"]], delta_b)
            judged = self.assess(result, payload)
            self.assertIn("trial_clock_schedule_or_overlap", judged["errors"])
            self.assertIn("wire_clock_order_or_overlap", judged["errors"])
            self.assertEqual(judged["verdict"], "hold")
        result, payload = self.measurement()
        receipt = payload["trials"][result["trials"][0]["trial_id"]]
        for phase, delta in (("plan", 4), ("explanation", -4)):
            task = result["trials"][0]["trial_id"] + "-" + phase
            for key in ("started", "ended"):
                receipt["task_clocks"][task][key] += delta
            for segment in receipt["clock_segments"]:
                if segment["task_id"] == task:
                    segment["started"] += delta; segment["ended"] += delta
            for attempt in receipt["calls"].values():
                if attempt["entrance_id"].startswith(task):
                    for key in ("sent_monotonic", "finished_monotonic", "task_started_monotonic"):
                        attempt[key] += delta
                    attempt["run_remaining_seconds"] -= delta
        self.assertReject(result, payload, "explanation_before_code_complete")

    def test_IR02_all_rounds_knowledge_and_known_retry_wait_normal_control(self):
        result, payload = self.measurement()
        trial = result["trials"][0]; tid = trial["trial_id"]; receipt = payload["trials"][tid]
        first = trial["calls"][0]; original = receipt["calls"][first["attempt_id"]]
        boundary, extra = original["finished_monotonic"], 1.7
        for segment in receipt["clock_segments"]:
            if segment["kind"] == "wire" and segment["attempt_id"] == first["attempt_id"]:
                continue
            for key in ("started", "ended"):
                if segment[key] >= boundary:
                    segment[key] += extra
        for clock in receipt["task_clocks"].values():
            for key in ("started", "ended"):
                if clock[key] >= boundary:
                    clock[key] += extra
        for call in trial["calls"][1:]:
            attempt = receipt["calls"][call["attempt_id"]]
            for key in ("sent_monotonic", "finished_monotonic", "task_started_monotonic"):
                attempt[key] += extra
            attempt["run_remaining_seconds"] -= extra
        retry = copy.deepcopy(first); retry["attempt_id"] = tid + "-plan-post1"; retry["request_hash"] = H(retry["attempt_id"])
        trial["calls"].insert(1, retry)
        attempt = copy.deepcopy(original)
        attempt.update(request_hash=retry["request_hash"], wire_sequence=1,
            sent_monotonic=boundary + .7, finished_monotonic=boundary + 1.7)
        attempt["task_remaining_seconds"] = 240 - (attempt["sent_monotonic"] - attempt["task_started_monotonic"])
        attempt["run_remaining_seconds"] = 600 - (attempt["sent_monotonic"] - receipt["run_started_monotonic"])
        receipt["calls"][retry["attempt_id"]] = attempt
        for later in result["trials"]:
            for call in later["calls"]:
                observed = payload["trials"][later["trial_id"]]["calls"][call["attempt_id"]]
                if call is not retry and observed["wire_sequence"] >= 1:
                    observed["wire_sequence"] += 1
        def span(kind, begin, end, aid=None):
            return {"kind":kind, "started":begin, "ended":end, "task_id":first["task_id"], "attempt_id":aid}
        receipt["clock_segments"][4:4] = [span("knowledge", boundary, boundary + .2),
            span("retry_wait", boundary + .2, boundary + .6), span("context", boundary + .6, boundary + .7),
            span("wire", boundary + .7, boundary + 1.7, retry["attempt_id"])]
        receipt["run_ended_monotonic"] += extra; trial["elapsed_seconds"] += extra
        trial["knowledge_receipts"] = [{"phase":"plan", "note_id":"synthetic-note", "section_id":"synthetic-section",
            "source_hash":H("synthetic-source"), "section_hash":H("synthetic-section"), "characters":10, "elapsed_seconds":.2}]
        judged = self.assess(result, payload, recalculate=True)
        self.assertTrue(judged["valid"], judged)
        self.assertEqual(judged["verdict"], "continue")
        self.assertEqual(result["totals"]["model_transport_attempts"], 37)
        self.assertEqual(receipt["call_ai_entrances"], 2)  # Retry counts as another wire, not another entrance.
        trial["knowledge_receipts"][0]["elapsed_seconds"] = 700
        self.assertReject(result, payload, "knowledge_clock_coverage")
        trial["knowledge_receipts"][0]["elapsed_seconds"] = None
        judged = self.assess(result, payload)
        self.assertTrue(judged["valid"], judged)
        self.assertEqual(judged["verdict"], "hold")

    def test_IR03_unknown_clock_cannot_be_hidden_by_wire_sequence(self):
        result, payload = self.measurement()
        trial = result["trials"][0]; call = trial["calls"][0]
        receipt = payload["trials"][trial["trial_id"]]["calls"][call["attempt_id"]]
        receipt["raw_usage"] = None; receipt["usage"] = driver.inspect_raw_usage(None, receipt["usage_semantics"])
        for key in ("raw_usage_exists", "present_usage_fields", "input_tokens", "output_tokens",
                    "reasoning_tokens", "total_tokens", "token_completeness"):
            call[key] = receipt["usage"][key]
        for tr in result["trials"]:
            for attempt in payload["trials"][tr["trial_id"]]["calls"].values():
                attempt["wire_sequence"] = 35 if attempt is receipt else attempt["wire_sequence"] - 1
        judged = self.assess(result, payload, recalculate=True)
        self.assertIn("post_after_unknown_clock", judged["errors"])
        self.assertIn("wire_clock_order_or_overlap", judged["errors"])
        self.assertEqual(judged["verdict"], "hold")

    def test_IR02_partition_tolerance_does_not_scale_with_monotonic_origin(self):
        result, payload = self.measurement()
        for receipt in payload["trials"].values():
            self.shift_trial_clock(receipt, 1_000_000_000)
        self.assertEqual(self.assess(result, payload)["verdict"], "continue")
        next(iter(payload["trials"].values()))["clock_segments"][-1]["started"] += .01
        self.assertReject(result, payload, "clock_partition")

    def test_IR04_preaccepted_manifest_replicates_and_external_binding(self):
        for field in ("profile", "knowledge", "sections", "prompt"):
            result, payload = self.measurement()
            for trial in result["trials"]:
                if trial["case_id"] == "C1" and trial["pair"] == 2 and (
                        field in ("profile", "knowledge") or trial["condition"] == "A"):
                    payload["trials"][trial["trial_id"]]["hashes"][field] = H("different-" + field)
            self.assertReject(result, payload, "preaccepted_conditions")
        result, payload = self.measurement()
        judged = driver.assess_comparison(result, driver.bind_comparison_evidence(result, payload))
        self.assertIn("preaccepted_manifest_missing", judged["errors"])
        payload["preaccepted_manifest_hash"] = H("forged observed manifest")
        self.assertReject(result, payload, "preaccepted_manifest_binding")
        result, payload = self.measurement()
        self.preaccepted_manifest["revisions"]["0"]["accepted_monotonic"] = 2
        payload["preaccepted_manifest_hash"] = H(self.preaccepted_manifest)
        self.assertReject(result, payload, "manifest_accepted_after_start")

    def test_IR04_R1_only_approved_B_prompt_section_revision_allowed(self):
        result, payload = self.measurement(revision=1)
        for cid in driver.F03_CASES:
            expected = self.preaccepted_manifest["revisions"]["1"]["conditions"][cid]["B"]
            expected.update(sections=H("R1-B-sections"), prompt=H("R1-B-prompt"))
            for trial in result["trials"]:
                if trial["revision"] == 1 and trial["case_id"] == cid and trial["condition"] == "B":
                    payload["trials"][trial["trial_id"]]["hashes"] = copy.deepcopy(expected)
        payload["preaccepted_manifest_hash"] = H(self.preaccepted_manifest)
        self.assertEqual(self.assess(result, payload)["verdict"], "continue")
        for cid in driver.F03_CASES:
            self.preaccepted_manifest["revisions"]["1"]["conditions"][cid]["A"]["profile"] = H("changed-A")
            for trial in result["trials"]:
                if trial["revision"] == 1 and trial["case_id"] == cid and trial["condition"] == "A":
                    payload["trials"][trial["trial_id"]]["hashes"]["profile"] = H("changed-A")
        payload["preaccepted_manifest_hash"] = H(self.preaccepted_manifest)
        self.assertReject(result, payload, "preaccepted_revision_mutation")

    def test_IR05_nested_extra_missing_and_wrong_types_reject(self):
        def targets(payload):
            receipt = next(iter(payload["trials"].values())); call = next(iter(receipt["calls"].values()))
            return [payload["readiness"], payload["fixed_hashes"], payload["fixed_hashes"]["case_inputs"],
                payload["condition_hashes"], payload["condition_hashes"]["0"], receipt, receipt["hashes"],
                call, call["usage"], call["usage_semantics"], call["count_coverage"],
                next(iter(receipt["task_clocks"].values())), receipt["clock_segments"][0], receipt["hooks"]]
        for index in range(14):
            for change in ("extra", "missing", "wrong_type"):
                result, payload = self.measurement()
                target = targets(payload)[index]
                if change == "extra": target["unexpected"] = True
                elif change == "missing": target.pop(next(iter(target)))
                else: target[next(iter(target))] = ["wrong"]
                judged = self.assess(result, payload)
                self.assertFalse(judged["valid"], (index, change, judged))
                self.assertFalse(judged["measurement_ready"])
                self.assertEqual(judged["verdict"], "hold")

    def test_IR06_declared_false_and_blockers_never_promoted(self):
        result, payload = self.measurement()
        result.update(measurement_ready=False, ready_blockers=["initial_clock_unknown"])
        judged = self.assess(result, payload)
        self.assertTrue(judged["valid"], judged)
        self.assertFalse(judged["measurement_ready"])
        self.assertEqual(judged["verdict"], "hold")
        result["verdict"] = "continue"
        self.assertReject(result, payload, "declared_verdict")
        result, payload = self.measurement()
        judged = self.assess(result, payload)
        self.assertTrue(judged["measurement_ready"], judged)
        self.assertEqual(judged["verdict"], "continue")

    def test_old_help_and_comparison_measurement_cannot_accidentally_run(self):
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/test_expert_agent_model.py"), "--help"],
                                   text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for flag in ("--model", "--expert-id", "--statistical-cycle", "--output", "--call-timeout",
                     "--comparison-preflight", "--revision"):
            self.assertIn(flag, completed.stdout)
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/test_expert_agent_model.py"),
                                    "--comparison-id", "must-not-run"],
                                   text=True, encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("not wired", completed.stderr)
        for flag in (("--revision", "0"), ("--comparison-packet", "must-not-read.json")):
            completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/test_expert_agent_model.py"), *flag],
                                       text=True, encoding="utf-8", capture_output=True, timeout=20)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("not wired", completed.stderr)


if __name__ == "__main__":
    unittest.main()
