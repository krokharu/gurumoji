"""Synthetic ownership, delivery and durable-resume acceptance for E5-E8."""
import copy
import json
import unittest
from types import SimpleNamespace

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import ExecutionStopped
from gurumoji.services import analysis_intervals as intervals, model_context
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
from gurumoji.ai_finishing import create_outline
import test_analysis_orchestration as fixtures


def rows(count=12):
    return [{"utterance_id": f"u{i}", "evidence_id": f"ev{i}", "text": "架空の応答・否定・少数意見",
             "speaker": "A", "start": i * 60, "end": i * 60 + 50, "excluded": False} for i in range(count)]


def outline(first="u1", last="u3", title="議題"):
    return {"sections": [{"title": title, "start_segment_id": first, "end_segment_id": last,
                          "segment_ids": [first], "bullets": ["AIの要点"]}]}


class PartitionTests(unittest.TestCase):
    def build(self, data=None, candidate=None, **options):
        return intervals.build_partition(rows() if data is None else data, candidate,
            dataset_version="input-v1", row_limit=120, text_limit=60000, **options)

    def owners(self, partition):
        return [uid for i in partition["intervals"] for uid in i["owned_utterance_ids"]]

    def test_partial_outline_keeps_unquoted_responses_and_fills_both_gaps(self):
        p = self.build(candidate=outline())
        self.assertEqual(self.owners(p), [f"u{i}" for i in range(12)])
        topic = next(i for i in p["intervals"] if i["method"] == "existing")
        self.assertEqual(topic["owned_utterance_ids"], ["u1", "u2", "u3"])
        self.assertEqual(topic["boundary_evidence_ids"], ["ev0", "ev4"])

    def test_quotes_and_quote_times_are_never_used_as_complete_boundaries(self):
        p = self.build(candidate={"sections": [{"title": "引用のみ", "segment_ids": ["u1", "u8"], "start": 60, "end": 530}]})
        self.assertTrue(all(i["method"] == "time" for i in p["intervals"]))
        self.assertEqual(self.owners(p), [f"u{i}" for i in range(12)])

    def test_boundary_at_300_seconds_belongs_to_next_time_bucket(self):
        p = self.build()
        self.assertEqual(p["intervals"][0]["owned_utterance_ids"], ["u0", "u1", "u2", "u3", "u4"])
        self.assertEqual(p["intervals"][1]["owned_utterance_ids"][0], "u5")

    def test_reappearing_topic_has_distinct_intervals_and_same_parent(self):
        candidate = outline("u0", "u2")
        candidate["sections"] += outline("u8", "u10")["sections"]
        topics = [i for i in self.build(candidate=candidate)["intervals"] if i["method"] == "existing"]
        self.assertEqual(topics[0]["parent_topic_id"], topics[1]["parent_topic_id"])
        self.assertNotEqual(topics[0]["interval_id"], topics[1]["interval_id"])

    def test_overlapping_candidates_are_normalized_deterministically(self):
        candidate = outline("u0", "u4")
        candidate["sections"] += outline("u3", "u7", "別議題")["sections"]
        p = self.build(candidate=candidate)
        candidate["sections"].reverse()
        self.assertEqual(self.build(candidate=candidate)["intervals"], p["intervals"])
        self.assertEqual(len(self.owners(p)), len(set(self.owners(p))))

    def test_overlapping_speech_keeps_source_order_and_single_ownership(self):
        data = rows(4)
        data[1].update(start=0, end=70)
        self.assertEqual(self.owners(self.build(data)), ["u0", "u1", "u2", "u3"])

    def test_empty_or_invalid_candidate_is_time_fallback(self):
        for candidate in ({"sections": []}, outline("missing", "u4"), outline("u4", "u1")):
            with self.subTest(candidate=candidate):
                self.assertTrue(all(i["method"] == "time" for i in self.build(candidate=candidate)["intervals"]))

    def test_empty_input_does_not_invent_a_time_or_interval(self):
        self.assertEqual(self.build([])["intervals"], [])

    def test_invalid_time_is_explicitly_unprocessable_and_not_zero(self):
        for value in (None, float("nan"), float("inf"), -1, True, "60"):
            data = rows(3)
            data[1]["start"] = value
            p = self.build(data)
            bad = next(i for i in p["intervals"] if "u1" in i["owned_utterance_ids"])
            self.assertEqual(bad["status"], "unprocessable")
            self.assertEqual(bad["reason"], "invalid_time")
            self.assertIsNone(bad["start"])
            self.assertEqual(self.owners(p), ["u0", "u1", "u2"])

    def test_exclusion_does_not_enter_any_interval_or_boundary(self):
        data = rows(3)
        data[1]["excluded"] = True
        self.assertEqual(self.owners(self.build(data)), ["u0", "u2"])

    def test_row_and_text_budget_preserve_ownership(self):
        data = rows()
        p = intervals.build_partition(data, outline("u0", "u11"), dataset_version="input-v1",
                                      row_limit=4, text_limit=100)
        self.assertEqual(self.owners(p), [f"u{i}" for i in range(12)])
        self.assertGreater(len(p["intervals"]), 1)
        self.assertEqual(len({i["parent_topic_id"] for i in p["intervals"]}), 1)

    def test_single_long_utterance_is_unprocessed_with_full_text_preserved(self):
        data = rows(1)
        data[0]["text"] *= 100
        before = copy.deepcopy(data)
        p = intervals.build_partition(data, None, dataset_version="input-v1", text_limit=10)
        self.assertEqual(p["intervals"][0]["reason"], "single_utterance_budget_exceeded")
        self.assertEqual(data, before)

    def test_duplicate_identity_is_rejected(self):
        data = rows(2)
        data[1]["utterance_id"] = "u0"
        with self.assertRaises(AnalysisContractError):
            self.build(data)

    def test_partition_hash_input_and_settings_are_checked(self):
        p = self.build()
        config = {"analysis_interval_seconds": 300, "context_evidence_limit": 120, "context_text_limit": 60000}
        intervals.check_partition(p, config, "input-v1")
        for field, value in (("analysis_interval_seconds", 100), ("context_text_limit", 300)):
            with self.assertRaises(AnalysisContractError):
                intervals.check_partition(p, {**config, field: value}, "input-v1")
        with self.assertRaises(AnalysisContractError):
            intervals.check_partition(p, config, "changed-input")
        p["intervals"][0]["owned_evidence_ids"].pop()
        with self.assertRaises(AnalysisContractError):
            intervals.check_partition(p, config, "input-v1")

    def test_context_reduction_cannot_remove_interval_ownership(self):
        context = {"task": {"phase": "specialist_followup"}, "raw_evidence": rows(3),
                   "coverage": {"page": {"interval_id": "i", "owned_evidence_ids": ["ev1"]}}}
        self.assertIsNone(model_context.reduce_context(context))


class IntervalRuntimeTests(unittest.TestCase):
    connect = fixtures.RuntimeTests.connect
    build = fixtures.RuntimeTests.build
    run_agent = fixtures.RuntimeTests.run_agent
    method = fixtures.RuntimeTests.method
    make_service = fixtures.RuntimeTests.make_service
    drive = fixtures.RuntimeTests.drive

    def setUp(self):
        fixtures.RuntimeTests.setUp(self)
        self.snapshot["analysis"]["segments"] = [{"id": r["utterance_id"], **{k: r[k] for k in ("text", "speaker", "start", "end")}}
                                                   for r in rows()]
        self.generated = []
        self.agent = self.valid_agent

    def valid_agent(self, role, context, options, check, usage):
        usage({"context_manifest": model_context.context_manifest(context, {}, "", "{}", {"fits": True})})
        return fixtures.InitialSpecialistTests.valid_agent(self, role, context)

    def start(self, **options):
        return fixtures.RuntimeTests.start(self, core_progress_version=1, initial_label_definitions_version=1,
            initial_specialist_analysis_version=1, analysis_interval_version=1, context_evidence_limit=6,
            context_text_limit=6000, **options)

    def generate(self, segments, hint, options, check, before_call, usage):
        check()
        before_call()
        self.generated.append([s["id"] for s in segments])
        return outline(segments[0]["id"], segments[-1]["id"], "AI仮説の議題")

    def test_time_fallback_full_coverage_blind_packet_and_full_statistics(self):
        final = self.drive(self.start(max_calls=100, max_tasks=150))
        self.assertTrue(final.get("initial_analysis_report", {}).get("full_evidence_coverage"), final.get("error"))
        for role, ctx, _ in self.calls:
            if ctx.get("task", {}).get("phase") != "initial_analysis":
                continue
            scope = ctx["coverage"]["page"]
            self.assertEqual(set(scope["owned_evidence_ids"] + scope["boundary_evidence_ids"]),
                             {r["evidence_id"] for r in ctx["raw_evidence"]})
            if role == "verification":
                for field in ("title", "results", "current_view", "initial_analysis_report"):
                    self.assertNotIn(field, ctx if field != "title" else scope)
        self.assertEqual(len(self.methods), 3)
        self.assertTrue(all(len(s["analysis"]["segments"]) == 12 for _, s in self.methods))
        for role in final["interval_progress"]["roles"].values():
            self.assertEqual(len(role["processed_evidence_ids"]), 12)
            self.assertEqual(role["unprocessed_evidence_ids"], [])

    def test_generation_saved_as_run_draft_without_mutating_source(self):
        self.service = self.make_service(outline_builder=self.generate)
        before = copy.deepcopy(self.snapshot)
        run = self.start(max_calls=100, max_tasks=150)
        self.service._prepare_intervals(run["run_id"])
        self.service._prepare_intervals(run["run_id"])
        saved = self.service.status("conversation", run["run_id"])
        self.assertEqual(len(self.generated), 1)
        self.assertEqual(saved["interval_preparation"]["drafts"][0]["status"], "ai_draft")
        self.assertEqual(saved["interval_preparation"]["drafts"][0]["owner_run_id"], run["run_id"])
        self.assertEqual(self.snapshot, before)

    def test_existing_outline_reused_without_generation(self):
        self.snapshot["source_outline"] = {**outline("u0", "u3"), "dataset_version": "input-v1"}
        # Other ranges are time fallback if AI is unavailable; citations are not
        # the owners: u1/u2/u3 are included despite only u0 being quoted.
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        saved = self.service.status("conversation", run["run_id"])
        first = saved["analysis_partition"]["intervals"][0]
        self.assertEqual(first["method"], "existing")
        self.assertEqual(first["owned_utterance_ids"], ["u0", "u1", "u2", "u3"])

    def test_stale_outline_is_not_reused(self):
        self.snapshot["source_outline"] = {**outline("u0", "u3"), "dataset_version": "old-input"}
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        saved = self.service.status("conversation", run["run_id"])
        self.assertFalse(saved["interval_preparation"]["source_outline_matched"])
        self.assertTrue(all(i["method"] == "time" for i in saved["analysis_partition"]["intervals"]))

    def test_coarse_outline_refinement_keeps_parent_topic(self):
        self.snapshot["source_outline"] = {**outline("u0", "u11"), "dataset_version": "input-v1"}
        self.service = self.make_service(outline_builder=self.generate)
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        saved = self.service.status("conversation", run["run_id"])
        self.assertEqual(saved["interval_preparation"]["drafts"][0]["method"], "refined")
        self.assertEqual(len({i["parent_topic_id"] for i in saved["analysis_partition"]["intervals"]}), 1)

    def test_generation_failure_falls_back_but_cancel_does_not(self):
        def fail(*_):
            raise RuntimeError("synthetic failure")
        self.service = self.make_service(outline_builder=fail)
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        final = self.service.status("conversation", run["run_id"])
        self.assertTrue(all(i["method"] == "time" for i in final["analysis_partition"]["intervals"]))
        self.assertEqual(final["interval_preparation"]["drafts"][0]["status"], "failed")
        def cancel(*_):
            raise ExecutionStopped()
        self.service = self.make_service(outline_builder=cancel)
        run = self.start(request_id="cancel")
        with self.assertRaises(ExecutionStopped):
            self.service._prepare_intervals(run["run_id"])
        self.assertNotIn("analysis_partition", self.service.status("conversation", run["run_id"]))

    def test_bad_time_blocks_without_provider_dispatch(self):
        self.snapshot["analysis"]["segments"][3]["start"] = None
        final = self.drive(self.start())
        self.assertEqual(final["status"], "recovery_required")
        self.assertFalse(self.calls)
        self.assertEqual(len(final["interval_progress"]["roles"]["verification"]["unprocessed_evidence_ids"]), 12)

    def test_local_cloud_mix_uses_identical_owned_ranges(self):
        final = self.drive(self.start(max_calls=100, max_tasks=150, provider_policy="cloud_allowed", cloud_consent=True,
                                     roles={"critic": {"provider": "openai", "model": "synthetic-cloud"}}))
        sets = {role: [ctx["coverage"]["page"]["owned_evidence_ids"] for r, ctx, _ in self.calls
                      if r == role and ctx["task"].get("phase") == "initial_analysis"]
                for role in ("interpretation", "verification", "critic")}
        # Independent worker completion order is deliberately unspecified.
        normalize = lambda values: sorted(tuple(page) for page in values)
        self.assertEqual(normalize(sets["interpretation"]), normalize(sets["verification"]))
        self.assertEqual(normalize(sets["interpretation"]), normalize(sets["critic"]))
        self.assertTrue(final.get("initial_analysis_report", {}).get("full_evidence_coverage"))

    def test_missing_scope_followup_fans_out_all_intervals_and_citation_selects_owner(self):
        run = self.start(max_calls=100, max_tasks=150)
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            first = state["analysis_partition"]["intervals"][0]
            self.service._register(db, state, fixtures.intent("interpretation"), phase="specialist_followup")
            self.service._register(db, state, fixtures.intent("verification", evidence_ids=[first["owned_evidence_ids"][0]]), phase="specialist_followup")
            tasks = self.service._tasks(db, run["run_id"])
            self.assertEqual(sum(t["role"] == "interpretation" for t in tasks), len(state["analysis_partition"]["intervals"]))
            verify = next(t for t in tasks if t["role"] == "verification")
            self.assertEqual(verify["intent"]["scope"]["owned_evidence_ids"], first["owned_evidence_ids"])

    def test_restart_does_not_regenerate_or_repeat_completed_tasks(self):
        self.service = self.make_service(outline_builder=self.generate)
        original = self.service._apply_initial_routing
        def pause(db, run, task):
            run["status"] = "recovery_required"
            self.service._write_run(db, run)
        self.service._apply_initial_routing = pause
        final = self.drive(self.start(max_calls=100, max_tasks=150))
        self.assertEqual(final["status"], "recovery_required", final.get("error"))
        partition = final["analysis_partition"]
        calls = sum(c["task"].get("phase") == "initial_analysis" for _, c, _ in self.calls)
        self.service = self.make_service(outline_builder=self.generate)
        self.service.resume("conversation", final["run_id"])
        resumed = self.drive(final)
        self.assertEqual(resumed["analysis_partition"], partition)
        self.assertEqual(len(self.generated), 1)
        self.assertEqual(sum(c["task"].get("phase") == "initial_analysis" for _, c, _ in self.calls), calls)

    def test_model_budget_splits_pages_with_parent_lineage_without_losing_rows(self):
        self.snapshot["source_outline"] = {**outline("u0", "u11"), "dataset_version": "input-v1"}
        original = self.agent
        def bounded(role, ctx, *args):
            scope = ctx.get("coverage", {}).get("page", {})
            if scope.get("interval_id") and len(scope["owned_evidence_ids"]) > 2:
                raise AnalysisContractError("synthetic capacity", code="context_budget_exceeded")
            return original(role, ctx, *args)
        self.agent = bounded
        final = self.drive(self.start(max_calls=150, max_tasks=200))
        self.assertTrue(final.get("initial_analysis_report", {}).get("full_evidence_coverage"), final.get("error"))
        self.assertTrue(final.get("interval_refinements"))
        self.assertTrue(all(i["parent_interval_id"] for i in final["interval_refinements"]))
        for status in final["interval_progress"]["roles"].values():
            self.assertEqual(status["unprocessed_evidence_ids"], [])

    def test_budget_stop_keeps_all_unprocessed_rows_instead_of_success(self):
        final = self.drive(self.start(max_calls=1, max_tasks=150))
        self.assertEqual(final["status"], "stopped")
        self.assertFalse(final.get("initial_analysis_report", {}).get("full_evidence_coverage"))
        self.assertEqual(len(final["interval_progress"]["roles"]["verification"]["unprocessed_evidence_ids"]), 12)

    def test_unreadable_single_utterance_stops_before_inference(self):
        self.snapshot["analysis"]["segments"][2]["text"] *= 1000
        final = self.drive(self.start())
        self.assertEqual(final["status"], "recovery_required")
        self.assertFalse(self.calls)
        self.assertTrue(any(i["reason"] == "single_utterance_budget_exceeded" for i in final["analysis_partition"]["intervals"]))

    def test_generated_out_of_scope_boundary_is_failed_time_fallback(self):
        def bad(*_):
            return outline("u0", "foreign")
        self.service = self.make_service(outline_builder=bad)
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        saved = self.service.status("conversation", run["run_id"])
        self.assertEqual(saved["interval_preparation"]["drafts"][0]["reason"], "outline_invalid")
        self.assertTrue(all(i["method"] == "time" for i in saved["analysis_partition"]["intervals"]))

    def test_task_cannot_invent_ownership_for_a_real_interval_id(self):
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            scope = intervals.interval_scope(state["analysis_partition"]["intervals"][0])
            scope["owned_evidence_ids"] = []
            with self.assertRaises(AnalysisContractError) as caught:
                self.service._register(db, state, fixtures.intent("interpretation", scope=scope), phase="specialist_followup")
            self.assertEqual(caught.exception.code, "interval_scope_invalid")

    def test_delivery_manifest_cannot_silently_omit_owned_source(self):
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            task = self.service._register(db, state, fixtures.intent("verification"), phase="specialist_followup")
            ctx = self.service._context(db, state, task)
        ctx["raw_evidence"].pop()
        manifest = model_context.context_manifest(ctx, {}, "", "{}", {})
        with self.assertRaises(AnalysisContractError) as caught:
            self.service._record_usage(run["run_id"], task["task_id"], {"context_manifest": manifest})
        self.assertEqual(caught.exception.code, "context_manifest_invalid")

    def test_tampered_partition_is_rejected_on_execution(self):
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            state["analysis_partition"]["time_width"] = 10
            self.service._write_run(db, state)
        final = self.drive(run)
        self.assertEqual(final["error"], "interval_version_conflict")
        self.assertFalse(self.calls)

    def test_explicit_multi_interval_comparison_uses_only_requested_intervals(self):
        run = self.start(max_calls=100)
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            chosen = state["analysis_partition"]["intervals"][:2]
            self.service._register(db, state, fixtures.intent("interpretation", "区間を比較", interval_ids=[i["interval_id"] for i in chosen]), phase="specialist_followup")
            self.assertEqual({t["intent"]["scope"]["interval_id"] for t in self.service._tasks(db, run["run_id"])},
                             {i["interval_id"] for i in chosen})

    def test_unknown_interval_id_is_rejected_before_dispatch(self):
        run = self.start()
        self.service._prepare_intervals(run["run_id"])
        with self.service._db() as db:
            state = self.service._read_run(db, run["run_id"])
            with self.assertRaises(AnalysisContractError):
                self.service._register(db, state, fixtures.intent("verification", interval_ids=["foreign"]), phase="specialist_followup")
        self.assertFalse(self.calls)

    def test_validated_results_keep_interval_and_parent_lineage(self):
        final = self.drive(self.start(max_calls=100, max_tasks=150))
        report = final["initial_analysis_report"]
        sources = [r for r in report["reports"] if r["role"] != "statistics"]
        self.assertTrue(all(r.get("interval_id") and r.get("parent_topic_id") for r in sources))
        results = [r for r in final["results"] if "interval_lineage" in r]
        self.assertEqual(len(results), len(sources))
        self.assertTrue(all(r["interval_lineage"]["dataset_version"] == final["input_hash"] for r in results))

    def test_specialist_topic_sources_reach_core_integration(self):
        original = self.agent
        def delegated(role, ctx, options, check, usage):
            if role == "orchestrator":
                usage({"context_manifest": model_context.context_manifest(ctx, {}, "", "{}", {})})
                return fixtures.core("親議題の所見と限界", stop=None, result_assessments=fixtures.assess_pending_results(ctx))
            if role == "core" and ctx["task"]["phase"] == "core":
                usage({"context_manifest": model_context.context_manifest(ctx, {}, "", "{}", {})})
                return fixtures.stop()
            return original(role, ctx, options, check, usage)
        self.agent = delegated
        final = self.drive(self.start(max_calls=150, max_tasks=200, specialist_orchestration_version=1))
        self.assertEqual(final["status"], "completed", final.get("error"))
        integration = next(ctx for role, ctx, _ in self.calls if role == "core" and ctx["task"]["phase"] == "core")
        groups = [r["topic_sources"] for r in integration["domain_reports"] if r.get("topic_sources")]
        self.assertTrue(groups)
        self.assertTrue(all(source["interval_id"] and source["ownership_sha256"]
                            for group in groups for sources in group.values() for source in sources))


class OutlineBoundaryTests(unittest.TestCase):
    def segments(self):
        return [{"id": r["utterance_id"], **{k: r[k] for k in ("text", "speaker", "start", "end")}} for r in rows(3)]

    def response(self):
        return {"sections": [{"title": "架空の議題", "start_segment_id": "u0", "end_segment_id": "u2",
                              "bullets": [{"text": "引用の要点", "segment_ids": ["u0"]}]}]}

    def test_outline_generation_records_bounds_separately_from_citations(self):
        result = create_outline(self.segments(), {}, lambda *_: self.response(), lambda _: None, lambda: None,
                                analysis_boundaries=True)
        section = result["sections"][0]
        self.assertEqual(section["segment_ids"], ["u0"])
        self.assertEqual(section["end_segment_id"], "u2")

    def test_unknown_or_reversed_bounds_fail_format_validation(self):
        for first, last in (("foreign", "u2"), ("u2", "u0")):
            reply = self.response()
            reply["sections"][0].update(start_segment_id=first, end_segment_id=last)
            with self.assertRaises(RuntimeError):
                create_outline(self.segments(), {}, lambda *_: reply, lambda _: None, lambda: None, analysis_boundaries=True)

    def test_outline_legacy_mode_retains_its_existing_response_contract(self):
        reply = self.response()
        reply["sections"][0].pop("start_segment_id")
        reply["sections"][0].pop("end_segment_id")
        result = create_outline(self.segments(), {}, lambda *_: reply, lambda _: None, lambda: None)
        self.assertNotIn("end_segment_id", result["sections"][0])

    def test_provider_preflight_failure_never_dispatches_outline(self):
        sent = []
        _, runner = make_orchestration_adapters(call_ai_json=lambda *a, **k: sent.append(a),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""), configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *_: {"fits": False})
        with self.assertRaises(AnalysisContractError):
            runner.prepare_outline(self.segments(), None, {"roles": {"interpretation": {"provider": "lmstudio", "model": "synthetic"}},
                                   "call_timeout_seconds": 20}, lambda: None, lambda: None, lambda _: None)
        self.assertEqual(sent, [])

    def test_outline_provider_policy_still_requires_cloud_consent(self):
        sent = []
        _, runner = make_orchestration_adapters(call_ai_json=lambda *a, **k: sent.append(a),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""), configured_ai_credentials=lambda *_: ("synthetic-key", "synthetic"))
        with self.assertRaises(AnalysisContractError):
            runner.prepare_outline(self.segments(), None, {"roles": {"interpretation": {"provider": "openai", "model": "synthetic"}},
                                   "provider_policy": "cloud_allowed", "cloud_consent": False}, lambda: None, lambda: None, lambda _: None)
        self.assertEqual(sent, [])


class IntervalAdapterTests(unittest.TestCase):
    def test_local_budget_is_measured_even_when_cloud_mix_disables_global_metering(self):
        sent, measured = [], []
        def meter(*args, **kwargs):
            measured.append(args)
            return {"fits": False, "output_reserve": 1600}
        resolve, runner = make_orchestration_adapters(call_ai_json=lambda *a, **k: sent.append(a),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("synthetic-key", "synthetic-model"), context_meter=meter)
        data = rows(4)
        page = intervals.interval_scope(intervals.make_interval(data, 1, 3, dataset_version="input-v1",
            parent_topic_id="topic-neutral", method="time"), blind=True)
        ctx = {"data_version": "input-v1", "task": {"phase": "initial_analysis", "role": "verification"},
               "raw_evidence": data, "coverage": {"page": page}}
        options = resolve({"provider_policy": "cloud_allowed", "cloud_consent": True, "analysis_interval_version": 1,
                           "model_context_version": 0, "roles": {"critic": {"provider": "openai", "model": "synthetic-cloud"}}})
        with self.assertRaises(AnalysisContractError) as caught:
            runner("verification", ctx, options, lambda: None, lambda _: None)
        self.assertEqual(caught.exception.code, "context_budget_exceeded")
        self.assertEqual(len(measured), 1)
        self.assertEqual(sent, [])

    def test_scoped_cloud_delivery_uses_all_rows_and_neutral_manifest(self):
        sent, recorded = [], []
        def reply(*args, **kwargs):
            sent.append(model_context.restored_reference_context(args[4], kwargs.get("data_messages")))
            return {"summary": "架空の確認", "claims": [{"evidence_ids": ["e1"]}]}
        resolve, runner = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("synthetic-key", "synthetic-model"))
        data = rows(4)
        page = intervals.interval_scope(intervals.make_interval(data, 1, 3, dataset_version="input-v1",
            parent_topic_id="topic-neutral", method="time"), blind=True)
        context = {"data_version": "input-v1", "question": "独立に確認", "task": {"phase": "initial_analysis", "role": "verification"},
                   "raw_evidence": data, "coverage": {"page": page}}
        response = runner("verification", context, resolve({"provider": "openai", "provider_policy": "cloud_allowed",
            "cloud_consent": True, "analysis_interval_version": 1}), lambda: None, recorded.append)
        self.assertEqual(len(sent[0]["raw_evidence"]), 4)
        self.assertEqual(response["claims"][0]["evidence_ids"], ["ev0"])
        self.assertEqual(recorded[-1]["context_manifest"]["analysis_interval"], page)
        self.assertNotIn("title", sent[0]["coverage"]["page"])

    def test_interval_selection_is_available_in_the_model_request_schema(self):
        schemas = []
        def reply(*args, **_):
            schemas.append(args[6])
            return {"summary": "架空の統合", "claims": []}
        resolve, runner = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("synthetic-key", "synthetic-model"))
        context = {"data_version": "input-v1", "task": {"role": "core", "phase": "core"}, "raw_evidence": rows(1),
                   "analysis_interval_index": [{"interval_id": "interval-neutral"}], "coverage": {}}
        runner("core", context, resolve({"provider": "openai", "provider_policy": "cloud_allowed", "cloud_consent": True,
                                       "analysis_interval_version": 1}), lambda: None, lambda _: None)
        branches = schemas[0]["properties"]["intents"]["items"]["anyOf"]
        branch = next(b for b in branches if "interpretation" in b["properties"]["role"]["enum"])
        self.assertEqual(branch["properties"]["interval_ids"]["items"]["enum"], ["interval-neutral"])


if __name__ == "__main__":
    unittest.main()
