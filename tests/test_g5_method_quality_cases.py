"""Pinned G5 inputs and CPU contracts, never semantic or researcher acceptance.

Only public-base fixtures are imported. The af2711e review/old test are provenance
sources, not runtime dependencies. Statistical model calls remain separate from
these synthetic CPU observations; no SDK/network/Vault is used.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, canonical, fingerprint
from gurumoji.method_experts import ExpertCatalog, EXPERTS_DIR
from gurumoji.services.expert_agents import ExpertAgentRegistry, NUMERIC_BINDING_FIELDS

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "tests/fixtures/g5_method_quality/cases.json"
PACKET_RAW_SHA256 = "9f9e7deedeec5d892acb28f5d3bb924f45c396687d76687da83e0335084fb5fa"
BASE = "a0a2e0dc34c37fa3e1c2bd7cb0142bd37598f95b"
NUMBERS = (1, 2, 3, 4, 5, 8, 11, 12, 13)
EXPERTS = tuple("exp-" + name for name in (
    "qualitative-content-analysis", "thematic-analysis", "framework-method", "scat", "m-gta",
    "focus-group-interaction", "descriptive-statistics", "group-comparison-statistics", "correlation"))
INHERITED = (
    "b45b51a5258aff9a06ca48d312853418f083fcc8b60b89d3ba3dec55a23cba49",
    "af8d8ced53d0ada3d8a60ca40661d7183ea12b6be09ccc43577fb90ab68772b2",
    "273803efab49fa8ad4f780ab78d3f55c4470dace2dda1bec068d9c19402b5409",
    "87d8717f853fc9fead975efe2d81028ea5af7f0d520ee33c66957e8e44988a15",
    "4645d711966040fc05d47c005cc8504735c21e17f3203a3839ebde0c11ea01e6",
    "4d9fe0d06514287b53e470eecdf69242779815684ca92282ab5e5531b1e3c8ad",
    "a50cd47999e139672d9f00441316322e71c6e4e08fbcb608140774386f635e9d",
    "a50cd47999e139672d9f00441316322e71c6e4e08fbcb608140774386f635e9d",
    "a50cd47999e139672d9f00441316322e71c6e4e08fbcb608140774386f635e9d",
)


def load_packet():
    raw = PACKET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKET_RAW_SHA256:
        raise ValueError("fixed packet bytes changed")
    return json.loads(raw)


def validate_packet(packet, *, expected_case_hashes):
    """Test-only preflight against independent fixed case identities and hashes."""
    def require(condition):
        if not condition:
            raise ValueError("G5 packet identity/order/content mismatch")
    require(packet["schema_version"] == "g5-method-quality-cases-v1")
    require(packet["suite_id"] == "G5-method-quality-20261010" and packet["fixed_source_sha"] == BASE)
    require(packet["source_methodreview_sha256"] == "34cf435e80825b1a52e12d8a33e959646845533b68f3bcad011fbda10a9ab534")
    require(list(packet["profiles"]) == list(EXPERTS))
    cases = packet["cases"]
    ids = [f"G5-{n:02d}-{condition}" for n in NUMBERS for condition in ("N", "X")]
    require([c["case_id"] for c in cases] == ids)
    require(set(expected_case_hashes) == set(ids))
    slots = []
    for index, case in enumerate(cases):
        n, eid, inherited = NUMBERS[index // 2], EXPERTS[index // 2], "sha256:" + INHERITED[index // 2]
        cid, condition = ids[index], ("N", "X")[index % 2]
        require(case["canonical_case_hash"] == expected_case_hashes[cid])
        require(fingerprint({k: v for k, v in case.items() if k != "canonical_case_hash"}) == expected_case_hashes[cid])
        require((case["expert_id"], case["condition"], case["source_id"], case["inherited_source_hash"]) ==
                (eid, condition, f"synthetic-M33-{n:02d}", inherited))
        require(fingerprint(case["raw_synthetic_analysis"]) == inherited)
        require(case["runtime_binding"] == {"status": "NOTRUN", "run_id": None,
                "data_version": None, "annotation_version": None, "input_hash": None, "call_id": None})
        profile = packet["profiles"][eid]
        require(case["profile_binding"] == {key: profile[key] for key in
                ("profile_hash", "knowledge_hash", "definition_version", "contract_version")})
        phases = ["specialist_draft"] if n < 11 else ["analysis_plan", "result_explanation"]
        require(case["call_phases"] == phases)
        require("method_oracle" not in case["model_input_fields"] and "normal_expected" not in case["model_input_fields"])
        oracle = case["method_oracle"]
        require((oracle["case_id"], oracle["expert_id"], oracle["source_id"], oracle["inherited_source_hash"], oracle["phases"]) ==
                (cid, eid, case["source_id"], inherited, phases))
        require(oracle["delivery"] == "independent_reviewer_only")
        require(oracle["semantic_quality"] == oracle["researcher_adoption"] == "NOTRUN")
        require(oracle["actual_output_binding"] is None and oracle["independent_review_receipt"] is None)
        require(oracle["review_contract"]["semantic_pass_from_schema_or_keywords"] is False)
        require("call_id" in oracle["review_contract"]["requires"])
        segments = case["raw_synthetic_analysis"]["segments"]
        require(oracle["source_evidence"] == [{"utterance_id": row["id"], "order": i,
            "speaker": row["speaker"], "raw_text_hash": fingerprint(row["text"]), "excluded": row.get("excluded", False)}
            for i, row in enumerate(segments)])
        require(len({row["id"] for row in segments}) == len(segments))
        known = {row["id"] for row in segments}
        require(set(oracle["support"]["utterance_ids"]) <= known and set(oracle["counterexamples"]["utterance_ids"]) <= known)
        require(oracle["human_step_ids"] == [step["id"] for step in profile["human_steps"]])
        require(bool(oracle["support"]["reasoning"] and oracle["alternatives"] and oracle["human_responsibilities"]
                     and oracle["inappropriate_claims_to_reject"]))
        candidate = case["third_party_candidate"]
        require(candidate is None if condition == "N" else candidate["status"] == "unverified_third_party_candidate")
        if n >= 11:
            contract = case["statistical_contract"]
            require(contract["method_id"] == {11: "descriptive_statistics", 12: "crosstabs", 13: "pearson"}[n])
            require(contract["cell_binding_keys"] == list(NUMERIC_BINDING_FIELDS))
            require(contract["cell_bindings"] is None and contract["binding_status"] == "NOTRUN")
            require(contract["explanation_on_missing_rejected_or_unknown_plan"] == "NOTRUN")
        for phase in phases:
            slots.append({"slot_id": cid + "-" + phase, "case_id": cid, "expert_id": eid, "phase": phase,
                "source_id": case["source_id"], "inherited_source_hash": inherited,
                "profile_hash": profile["profile_hash"], "knowledge_hash": profile["knowledge_hash"],
                "max_calls": 1, "max_conservative_tokens": 28672, "execution_status": "NOTRUN", "call_id": None,
                "depends_on_slot_id": cid + "-analysis_plan" if phase == "result_explanation" else None})
    require(canonical(packet["ordered_call_slots"]) == canonical(slots))
    require(len(slots) == 24 and len({s["slot_id"] for s in slots}) == 24)
    policy = packet["evaluation_policy"]
    require(policy == {"model_execution": "NOTRUN", "semantic_quality": "NOTRUN", "researcher_adoption": "NOTRUN",
        "structural_pass_is_semantic_pass": False, "oracle_in_model_input": False, "maximum_calls": 24,
        "maximum_conservative_tokens": 688128, "budget_is_execution_authorization": False})
    manifest = packet["source_definition_manifest"]
    paths = [row["path"] for row in manifest]
    require(paths == sorted(set(paths)))
    for row in manifest:
        relative = Path(row["path"])
        require(not relative.is_absolute() and ".." not in relative.parts)
        require(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == row["raw_sha256"])
    return {"profiles": 9, "cases": 18, "slots": 24, "semantic_quality": "NOTRUN", "researcher_adoption": "NOTRUN"}


def bind_quote_span(text, start, end):
    """Structural span proof only, retaining denial/quotation context for review."""
    if not isinstance(text, str) or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError("invalid actual-output quote span")
    return {"output_text_hash": fingerprint(text), "start": start, "end": end, "quote": text[start:end],
            "preceding_context": text[:start], "following_context": text[end:], "semantic_quality": "NOTRUN"}


class G5PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = load_packet()
        cls.hashes = {case["case_id"]: case["canonical_case_hash"] for case in cls.packet["cases"]}
        cls.local = tempfile.TemporaryDirectory(prefix="g5-empty-local-")
        cls.addClassCleanup(cls.local.cleanup)
        cls.catalog = ExpertCatalog(ROOT / "docs/program-vault", local_root=cls.local.name)
        cls.registry = ExpertAgentRegistry(cls.catalog)
        guard = patch("socket.socket.connect", side_effect=AssertionError("No G5 network or SDK"))
        guard.start(); cls.addClassCleanup(guard.stop)

    def test_fixed_packet_order_hashes_and_source_manifest(self):
        self.assertEqual(validate_packet(self.packet, expected_case_hashes=self.hashes),
            {"profiles": 9, "cases": 18, "slots": 24, "semantic_quality": "NOTRUN", "researcher_adoption": "NOTRUN"})
        self.assertEqual(self.packet["inherited_fixture_source"]["blob"], "0f20cac116baa2ee02b9025d69134a934018c6a0")
        self.assertFalse(self.packet["inherited_fixture_source"]["runtime_dependency"])

    def test_all_nine_profiles_match_real_schemas_knowledge_and_allowed_steps(self):
        manifest = {row["path"]: row for row in self.packet["source_definition_manifest"]}
        for eid in EXPERTS:
            with self.subTest(expert=eid):
                expected = self.packet["profiles"][eid]
                profile = self.registry.freeze({"expert_ids": [eid], "expert_inputs": {eid: expected["inputs"]}})["profiles"][eid]
                self.assertEqual({key: profile[key] for key in expected}, expected)
                self.assertEqual(profile["profile_hash"], fingerprint({k: v for k, v in profile.items() if k != "profile_hash"}))
                definition = self.catalog.definition(eid)
                self.assertEqual({s["id"] for s in profile["allowed_steps"]}, set(definition["ai_assist"]["steps"]))
                self.assertTrue(all(s["actor"] == "ai_draft" for s in profile["allowed_steps"]))
                knowledge = self.catalog.knowledge(eid, definition)
                for path in knowledge["notes"]:
                    row = manifest[(Path("docs/program-vault") / path).as_posix()]
                    self.assertIn(eid, row["expert_ids"])
                    self.assertIn("knowledge", row["roles"])
                folder = Path("docs/program-vault") / EXPERTS_DIR / self.catalog.index()[eid]["folder"]
                self.assertIn((folder / "01-Expert.md").as_posix(), manifest)
                for name in ("07-Agent-Contract.md", "08-Skill-Hook-Binding.md"):
                    if (ROOT / folder / name).exists():
                        self.assertIn((folder / name).as_posix(), manifest)

    def test_eight_forbidden_experts_have_no_inference_slot(self):
        forbidden = sorted(set(self.catalog.index()) - set(EXPERTS))
        self.assertEqual(len(forbidden), 8)
        self.assertEqual(forbidden, self.packet["ai_forbidden_expert_ids"])
        for eid in forbidden:
            with self.subTest(expert=eid):
                self.assertFalse(self.catalog.definition(eid)["ai_assist"]["allowed"])
                with self.assertRaises(AnalysisContractError) as caught:
                    self.registry.freeze({"expert_ids": [eid]})
                self.assertEqual(caught.exception.code, "expert_ai_unavailable")
                self.assertFalse(any(row["expert_id"] == eid for row in self.packet["ordered_call_slots"]))

    def test_n_and_x_share_exact_source_and_knowledge_without_replacing_output(self):
        for normal, negative in zip(self.packet["cases"][::2], self.packet["cases"][1::2]):
            with self.subTest(case=normal["case_id"]):
                for field in ("raw_synthetic_analysis", "source_id", "inherited_source_hash", "premises", "profile_binding", "author_choices"):
                    self.assertEqual(canonical(normal[field]), canonical(negative[field]))
                self.assertIsNone(normal["third_party_candidate"])
                self.assertEqual(negative["third_party_candidate"]["status"], "unverified_third_party_candidate")
                for case in (normal, negative):
                    self.assertIsNone(case["method_oracle"]["actual_output_binding"])
                    self.assertIsNone(case["method_oracle"]["independent_review_receipt"])
                    self.assertNotIn("method_oracle", case["model_input_fields"])
                    self.assertNotIn("expected_response", case)
                    self.assertEqual(case["method_oracle"]["researcher_adoption"], "NOTRUN")

    def test_null_zero_false_missing_and_excluded_remain_distinct(self):
        self.assertEqual(len({fingerprint(value) for value in ({}, {"v": None}, {"v": 0}, {"v": False})}), 4)
        qualitative = self.packet["cases"][0]["raw_synthetic_analysis"]
        self.assertIs(type(qualitative["manual"]["coded_segment_count"]), int)
        self.assertEqual(qualitative["manual"]["coded_segment_count"], 0)
        self.assertTrue(qualitative["manual"]["preparation"]["order_verified"])
        statistical = self.packet["cases"][12]["raw_synthetic_analysis"]
        self.assertIs(statistical["segments"][1]["valid_time"], False)
        self.assertEqual(statistical["segments"][1]["duration"], 3)
        self.assertIs(statistical["segments"][-1]["excluded"], True)
        self.assertNotIn("duration", statistical["segments"][-1])
        self.assertEqual(statistical["segments"][-1]["characters"], 10000)
        self.assertIsNone(self.packet["cases"][12]["runtime_binding"]["annotation_version"])

    def test_foreign_duplicate_reordered_and_self_rehashed_packet_mutations_fail(self):
        mutations = {
            "foreign case expert": lambda p: p["cases"][0].update(expert_id="exp-correlation"),
            "duplicate case": lambda p: p["cases"].__setitem__(1, copy.deepcopy(p["cases"][0])),
            "case order": lambda p: p["cases"].reverse(),
            "slot order": lambda p: p["ordered_call_slots"].reverse(),
            "duplicate slot": lambda p: p["ordered_call_slots"].__setitem__(1, copy.deepcopy(p["ordered_call_slots"][0])),
            "foreign source": lambda p: p["ordered_call_slots"][0].update(source_id="foreign"),
            "foreign knowledge": lambda p: p["ordered_call_slots"][0].update(knowledge_hash="sha256:foreign"),
            "boolean quota": lambda p: p["ordered_call_slots"][0].update(max_calls=True),
            "null to zero": lambda p: p["cases"][0]["runtime_binding"].update(annotation_version=0),
            "invented call ID": lambda p: p["ordered_call_slots"][0].update(call_id="usage-is-not-call"),
            "raw source order": lambda p: p["cases"][2]["raw_synthetic_analysis"]["segments"].reverse(),
            "excluded removed": lambda p: p["cases"][12]["raw_synthetic_analysis"]["segments"].pop(),
            "self rehash": lambda p: p["cases"][0]["raw_synthetic_analysis"]["segments"][0].update(text="Changed raw source"),
            "meaning falsely passed": lambda p: p["cases"][0]["method_oracle"].update(semantic_quality="PASS"),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                bad = copy.deepcopy(self.packet); mutate(bad)
                if name == "self rehash":
                    case = bad["cases"][0]
                    case["inherited_source_hash"] = fingerprint(case["raw_synthetic_analysis"])
                    case["canonical_case_hash"] = fingerprint({k: v for k, v in case.items() if k != "canonical_case_hash"})
                with self.assertRaises(ValueError):
                    validate_packet(bad, expected_case_hashes=self.hashes)

    def test_quote_offsets_retain_denial_context_without_meaning_pass(self):
        text = "第三者候補は『沈黙は全員の同意を証明する』とする。しかしその推論は支持できず、応答の文脈は研究者確認待ち。"
        phrase = "沈黙は全員の同意を証明する"
        start = text.index(phrase)
        proof = bind_quote_span(text, start, start + len(phrase))
        self.assertEqual(proof["quote"], phrase)
        self.assertEqual(proof["preceding_context"] + proof["quote"] + proof["following_context"], text)
        self.assertEqual(proof["semantic_quality"], "NOTRUN")
        self.assertEqual(proof["output_text_hash"], fingerprint(text))
        for first, last in ((False, 1), (0, 0), (-1, 3), (0, len(text) + 1)):
            with self.subTest(span=(first, last)), self.assertRaises(ValueError):
                bind_quote_span(text, first, last)


def explanation_gate(plan_task, plan_result, calculation_result):
    """Fixture driver guard, not a new production scheduler or semantic judge."""
    if not all(isinstance(value, dict) for value in (plan_task, plan_result, calculation_result)):
        return "NOTRUN"
    if (plan_task.get("status") != "succeeded" or plan_result.get("validation_status") != "valid"
            or plan_result.get("task_id") != plan_task.get("task_id")
            or plan_result.get("attempt_id") != plan_task.get("attempt_id")
            or plan_result.get("run_id") != plan_task.get("run_id")
            or plan_result.get("dataset_version") != plan_task.get("dataset_version")
            or fingerprint(plan_result.get("raw")) != plan_result.get("raw_hash")
            or plan_result.get("raw", {}).get("expert_report", {}).get("status") != "needs_calculation"
            or not calculation_result or calculation_result.get("validation_status") != "valid"
            or calculation_result.get("run_id") != plan_task.get("run_id")
            or calculation_result.get("dataset_version") != plan_task.get("dataset_version")
            or fingerprint(calculation_result.get("raw")) != calculation_result.get("raw_hash")):
        return "NOTRUN"
    return "ready"


CPU_OBSERVATIONS = []


class G5StatisticalChainTests(unittest.TestCase):
    def setUp(self):
        import app
        import test_content_analysis as content_support
        from gurumoji.analysis_store import AnalysisStore
        self.app = app
        self.content = content_support.ContentApiTests(methodName="runTest")
        self.content.setUp(); self.addCleanup(self.content.doCleanups)
        self.packet = load_packet()
        for guard in (patch("socket.socket.connect", side_effect=AssertionError("No G5 network")),
                      patch.object(AnalysisStore, "_publish_generated_vaults", side_effect=AssertionError("No Vault")),
                      patch.object(AnalysisStore, "_publish_research", side_effect=AssertionError("No Vault"))):
            guard.start(); self.addCleanup(guard.stop)

    def dispatch(self, helper, run, intent):
        # Same Handler registration/execution seam as the unchanged base helper,
        # using this temporary Store fixture's actual item ID.
        with helper.service._db() as db:
            current = helper.service._read_run(db, run["run_id"])
            task = helper.service._register(db, current, intent, phase="specialists")
        helper.service._execute(run["run_id"], task["task_id"])
        return next(t for t in helper.service.status("content", run["run_id"])["tasks"] if t["task_id"] == task["task_id"])

    def prepare_case(self, case):
        import test_statistical_expert_agents as existing
        from gurumoji.research_analysis import build_research_statistics
        helper = existing.StatisticalExpertTests(methodName="runTest")
        helper.setUp(); self.addCleanup(helper.doCleanups)
        analysis = copy.deepcopy(case["raw_synthetic_analysis"])
        self.assertEqual(fingerprint(analysis), case["inherited_source_hash"])
        # Existing CPU preparation computes its own engine state; no numbers or
        # result rows are authored/injected. Future app preparation stays null.
        analysis["research"].update(build_research_statistics(analysis, analysis["research"]["linguistics"]))
        helper.analysis = analysis
        cpu_input_hash = fingerprint({"cpu_fixture_analysis": analysis})
        helper.snap = {"input_hash": cpu_input_hash, "source_revision": 1, "analysis_revision": 1, "analysis": analysis}
        helper.service.source_fingerprint = lambda _: cpu_input_hash
        helper.service.connect = self.app.database_connection
        helper.service.find_item = self.app.library_row
        question = case["research_question"]
        if case["third_party_candidate"] is not None:
            question += "\n未検証の第三者候補を批判・訂正する: " + case["third_party_candidate"]["text"]
        run = helper.service.start("content", {"model": "fixture", "expert_ids": [case["expert_id"]],
            "expert_inputs": {case["expert_id"]: {"analysis_premises": case["premises"]}},
            "question": question, "time_limit_seconds": None, "max_calls": 4,
            "obsidian_management": False, "publication_targets": []})
        return helper, run

    def chain(self, case, *, stop_after_plan=False, stop_after_calculation=False):
        import test_analysis_orchestration as existing
        from gurumoji.analysis_orchestration import AnalysisOrchestrationService
        helper, run = self.prepare_case(case)
        plan = self.dispatch(helper, run, existing.intent("interpretation", expert_id=case["expert_id"]))
        plan_result = helper.service.result("content", run["run_id"], plan["result_id"])
        self.assertEqual(plan["status"], "succeeded", plan)
        self.assertEqual(plan_result["raw"]["expert_report"]["status"], "needs_calculation")
        self.assertEqual(helper.calls[0][1]["expert_request"]["response_phase"], "analysis_plan")
        self.assertEqual(helper.calls[0][1]["expert_request"]["calculations"], [])
        self.assertEqual(plan["expert_agent"]["profile_hash"], case["profile_binding"]["profile_hash"])
        if stop_after_plan:
            return {"helper": helper, "run": run, "plan": plan, "plan_result": plan_result}
        requests = plan_result["raw"]["analysis_requests"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["method_id"], case["statistical_contract"]["method_id"])
        calculation = self.dispatch(helper, run, requests[0])
        self.assertEqual(calculation["status"], "succeeded", calculation)
        raw = helper.service.result("content", run["run_id"], calculation["result_id"])
        fresh = AnalysisOrchestrationService(connect=self.app.database_connection, find_item=self.app.library_row,
            snapshot_builder=lambda *_: self.fail("No source rebuild on fresh getter"),
            agent_runner=lambda *_: self.fail("No fresh inference"), method_runner=lambda *_: self.fail("No fresh calculation"),
            schedule=False)
        before = self.app.DATABASE_FILE.read_bytes()
        self.assertEqual(fresh.result("content", run["run_id"], calculation["result_id"]), raw)
        self.assertEqual(self.app.DATABASE_FILE.read_bytes(), before)
        self.assertEqual(explanation_gate(plan, plan_result, raw), "ready")
        if stop_after_calculation:
            return {"helper": helper, "run": run, "plan": plan, "plan_result": plan_result,
                    "calculation": calculation, "calculation_result": raw}
        explanation = self.dispatch(helper, run, existing.intent("interpretation", expert_id=case["expert_id"],
            question="Explain the actually saved verified calculation", dependencies=[calculation["task_id"]]))
        self.assertEqual(explanation["status"], "succeeded", explanation)
        self.assertEqual(explanation["dependencies"], [calculation["task_id"]])
        self.assertEqual(explanation["statistical_review_status"], "human_pending")
        explanation_result = helper.service.result("content", run["run_id"], explanation["result_id"])
        self.assertEqual([ctx["expert_request"]["response_phase"] for role, ctx in helper.calls],
                         ["analysis_plan", "result_explanation"])
        packet = helper.calls[-1][1]["expert_request"]["calculations"][0]
        self.assertEqual((packet["result_id"], packet["task_id"], packet["raw_hash"]),
                         (raw["result_id"], calculation["task_id"], fingerprint(raw["raw"])))
        self.assertEqual(explanation_result["raw"]["expert_report"]["calculation_result_ids"], [calculation["result_id"]])
        self.assertFalse(explanation_result["statistical_review"]["eligible_as_confirmed_evidence"])
        self.assertEqual(explanation_result["statistical_review"]["status"], "human_pending")
        for task, result in ((plan, plan_result), (calculation, raw), (explanation, explanation_result)):
            self.assertEqual((task["run_id"], result["run_id"]), (run["run_id"], run["run_id"]))
            self.assertEqual(task["result_id"], result["result_id"])
            self.assertEqual(task["attempt_id"], result["attempt_id"])
            self.assertTrue(task["attempt_id"] and task["task_id"] and result["result_id"])
            self.assertEqual(result["raw_hash"], fingerprint(result["raw"]))
            self.assertEqual(result["dataset_version"], run["input_hash"])
        return {"helper": helper, "run": run, "plan": plan, "plan_result": plan_result,
                "calculation": calculation, "calculation_result": raw, "explanation": explanation,
                "explanation_result": explanation_result, "packet": packet, "fresh": fresh}

    def assert_values(self, case, result):
        from gurumoji.services.expert_agents import cell_binding, validate_numeric_bindings
        from gurumoji.services.analysis_orchestration_methods import calculation_packet
        raw = result["raw"]
        self.assertEqual((raw["manifest"]["included_count"], raw["manifest"]["excluded_count"]), (5, 1))
        self.assertIs(type(raw["manifest"]["included_count"]), int)
        self.assertIs(type(raw["manifest"]["excluded_count"]), int)
        self.assertEqual(len(raw["manifest"]["evidence_ids"]), 5)
        contract = case["statistical_contract"]
        name = contract["dataset"]
        rows = raw["datasets"][name]["rows"]
        self.assertEqual(raw["manifest"]["rows_hash"], fingerprint(rows))
        if name == "descriptives":
            row = next(r for r in rows if r["scope"] == "overall" and r["variable"] == "duration_seconds")
            chars = next(r for r in rows if r["scope"] == "overall" and r["variable"] == "characters")
            self.assertEqual((row["n"], row["missing"], row["mean"]), (4, 1, 4.25))
            self.assertEqual((chars["n"], chars["missing"], chars["maximum"]), (5, 0, 30))
            for counts in (row, chars):
                for key in ("n", "missing"):
                    self.assertIs(type(counts[key]), int)
        elif name == "correlations":
            row = next(r for r in rows if {r["variable_a"], r["variable_b"]} == {"duration_seconds", "characters"})
            self.assertEqual((row["n"], row["missing"], row["method"]), (4, 1, "Pearson"))
            self.assertIs(type(row["n"]), int); self.assertIs(type(row["missing"]), int)
        else:
            row = next(r for r in rows if type(r["count"]) is int)
        calc = calculation_packet(raw, result, max_chars=100000)
        binding = cell_binding(calc, name, row, contract["column"])
        self.assertEqual(list(binding), list(NUMERIC_BINDING_FIELDS))
        rendered = validate_numeric_bindings([binding], [calc])[0]
        self.assertEqual(rendered["value"], row[contract["column"]])
        if name == "crosstabs":
            self.assertEqual(rendered["denominators"]["total_percent"], 5)
            self.assertIs(type(rendered["denominators"]["total_percent"]), int)
        return binding, rendered

    def test_six_cases_use_real_plan_calculation_fresh_dependency_and_store(self):
        from gurumoji.analysis_store import AnalysisStore
        from gurumoji.services.analysis_orchestration_publication import build_orchestration_package
        for case in self.packet["cases"][12:]:
            with self.subTest(case=case["case_id"]):
                original = canonical(case)
                chain = self.chain(case)
                binding, rendered = self.assert_values(case, chain["calculation_result"])
                helper, run = chain["helper"], chain["run"]
                exported = helper.service.result("content", run["run_id"])
                self.assertEqual(exported["usage_records"], [])  # No fabricated call/usage/token IDs.
                snapshot, result, datasets = build_orchestration_package(exported, fingerprint(exported))
                store = self.app.analysis_archive_store()
                saved = store.save(item_id="content", kind="autonomous_analysis", snapshot=snapshot,
                    result=result, datasets=datasets, request_id=case["case_id"] + "-cpu-contract",
                    input_fingerprint=run["input_hash"], source_revision=1, analysis_revision=1, publish=False)
                artifact = next(row for row in store.public(saved)["artifacts"] if row["name"] == "result.json")
                fresh_store = AnalysisStore(store.database_file, store.connect)
                before = self.app.DATABASE_FILE.read_bytes()
                _, payload = fresh_store.read_artifact(artifact["id"])
                self.assertEqual(payload, store.read_artifact(artifact["id"])[1])
                persisted = json.loads(payload)["orchestration"]
                for field in ("raw_results", "decisions", "label_versions"):
                    self.assertEqual(persisted[field], exported[field])
                self.assertEqual(persisted["run"]["tasks"], exported["run"]["tasks"])
                self.assertEqual(chain["fresh"].result("content", run["run_id"]), exported)
                self.assertEqual(self.app.DATABASE_FILE.read_bytes(), before)
                self.assertEqual(canonical(case), original)
                CPU_OBSERVATIONS.append({"case_id": case["case_id"], "expert_id": case["expert_id"],
                    "inherited_source_hash": case["inherited_source_hash"], "cpu_run_id": run["run_id"],
                    "cpu_input_hash": run["input_hash"], "cpu_annotation_version": chain["plan"]["annotation_version"],
                    "plan": {k: chain["plan_result"][k] for k in ("task_id", "attempt_id", "result_id", "raw_hash")},
                    "calculation": {k: chain["calculation_result"][k] for k in ("task_id", "attempt_id", "result_id", "raw_hash")},
                    "code_method_id": chain["calculation_result"]["raw"]["method_id"],
                    "code_method_version": chain["calculation_result"]["raw"]["method_version"],
                    "explanation": {k: chain["explanation"][k] for k in ("task_id", "attempt_id", "result_id", "dependencies")},
                    "explanation_raw_hash": chain["explanation_result"]["raw_hash"],
                    "statistical_review_status": chain["explanation"]["statistical_review_status"],
                    "cell_binding": binding, "cell_value": rendered["value"], "store_package_sha256": hashlib.sha256(payload).hexdigest(),
                    "model_call_id": None, "model_execution": "NOTRUN", "model_plan_quality": "NOTRUN",
                    "semantic_quality": "NOTRUN", "researcher_adoption": "NOTRUN"})

    def test_actual_handler_rejects_foreign_duplicate_missing_and_changed_nine_keys(self):
        import test_analysis_orchestration as existing
        case = self.packet["cases"][16]
        chain = self.chain(case)
        helper, run = chain["helper"], chain["run"]
        original = chain["explanation_result"]["raw"]
        binding = original["expert_report"]["numeric_bindings"][0]
        self.assertEqual(set(binding), set(NUMERIC_BINDING_FIELDS))
        bad_values = {"result_id": "foreign-result", "dataset": "descriptives", "row_id": "foreign-row", "column": "mean",
            "variables": ["foreign-variable"], "target": {"scope": "foreign", "selectors": {}},
            "dataset_version": "foreign-input", "computation_input_hash": "sha256:foreign", "rows_hash": "sha256:foreign"}
        before = self.app.DATABASE_FILE.read_bytes()
        for key, value in bad_values.items():
            with self.subTest(field=key):
                bad = copy.deepcopy(original); bad["expert_report"]["numeric_bindings"][0][key] = value
                with helper.service._db() as db, self.assertRaises(AnalysisContractError):
                    current = helper.service._read_run(db, run["run_id"])
                    helper.service._validate_result(db, current, chain["explanation"], bad)
        for change in ("duplicate", "missing"):
            with self.subTest(change=change):
                bad = copy.deepcopy(original)
                if change == "duplicate": bad["expert_report"]["numeric_bindings"].append(copy.deepcopy(binding))
                else: del bad["expert_report"]["numeric_bindings"][0]["rows_hash"]
                with helper.service._db() as db, self.assertRaises(AnalysisContractError):
                    helper.service._validate_result(db, helper.service._read_run(db, run["run_id"]), chain["explanation"], bad)
        self.assertEqual(self.app.DATABASE_FILE.read_bytes(), before)
        # An actual second run cannot inherit the first run's code dependency.
        other = helper.service.start("content", {"model": "fixture", "expert_ids": [case["expert_id"]],
            "question": "Separate run", "time_limit_seconds": None, "obsidian_management": False})
        count = len(helper.calls)
        with helper.service._db() as db, self.assertRaises(AnalysisContractError):
            helper.service._register(db, helper.service._read_run(db, other["run_id"]),
                existing.intent("interpretation", expert_id=case["expert_id"], dependencies=[chain["calculation"]["task_id"]]), phase="specialists")
        self.assertEqual(len(helper.calls), count)
        # Table row order/content is protected by the independently saved hash.
        metadata = chain["calculation_result"]
        for change in ("reorder", "duplicate", "number"):
            with self.subTest(table_change=change):
                bad = copy.deepcopy(metadata["raw"])
                rows = bad["datasets"]["correlations"]["rows"]
                self.assertGreater(len(rows), 1)
                if change == "reorder": rows.reverse()
                elif change == "duplicate": rows.append(copy.deepcopy(rows[0]))
                else: rows[0]["coefficient"] = 123
                bad["manifest"]["rows_hash"] = fingerprint(rows)
                with helper.service._db() as db, self.assertRaises(AnalysisContractError):
                    current = helper.service._read_run(db, run["run_id"])
                    helper.service._statistical_source(db, current, chain["calculation"], metadata, bad,
                        helper.service._initial(db, current["initial_id"]))

    def test_absent_rejected_needs_input_or_unknown_plan_keeps_explanation_notrun(self):
        chain = self.chain(self.packet["cases"][12], stop_after_calculation=True)
        helper = chain["helper"]
        count = len(helper.calls)
        valid_calculation = chain["calculation_result"]
        self.assertEqual(explanation_gate(chain["plan"], chain["plan_result"], valid_calculation), "ready")
        self.assertEqual(explanation_gate(chain["plan"], chain["plan_result"], None), "NOTRUN")
        self.assertEqual(explanation_gate(None, chain["plan_result"], valid_calculation), "NOTRUN")
        self.assertEqual(explanation_gate(chain["plan"], None, valid_calculation), "NOTRUN")
        for status in ("quarantined", "needs_input", "unknown", "cancelled"):
            with self.subTest(status=status):
                changed = {**chain["plan"], "status": status}
                self.assertEqual(explanation_gate(changed, chain["plan_result"], valid_calculation), "NOTRUN")
        for status in ("needs_input", "unknown", "rejected"):
            with self.subTest(report_status=status):
                changed = copy.deepcopy(chain["plan_result"])
                changed["raw"]["expert_report"]["status"] = status
                changed["raw_hash"] = fingerprint(changed["raw"])
                self.assertEqual(explanation_gate(chain["plan"], changed, valid_calculation), "NOTRUN")
        for name, value in (("validation_status", "invalid"), ("task_id", "foreign"), ("attempt_id", "foreign"),
                            ("run_id", "foreign"), ("dataset_version", "foreign"), ("raw_hash", "sha256:foreign")):
            with self.subTest(plan_field=name):
                changed = {**chain["plan_result"], name: value}
                self.assertEqual(explanation_gate(chain["plan"], changed, valid_calculation), "NOTRUN")
        for name, value in (("validation_status", "invalid"), ("run_id", "foreign"),
                            ("dataset_version", "foreign"), ("raw_hash", "sha256:foreign")):
            with self.subTest(calculation_field=name):
                changed = {**valid_calculation, name: value}
                self.assertEqual(explanation_gate(chain["plan"], chain["plan_result"], changed), "NOTRUN")
        self.assertEqual(len(helper.calls), count)
        self.assertFalse(any(ctx["expert_request"]["response_phase"] == "result_explanation" for _, ctx in helper.calls))
        self.assertTrue(all(case["runtime_binding"]["status"] == "NOTRUN" for case in self.packet["cases"]))
        self.assertEqual(self.packet["evaluation_policy"]["semantic_quality"], "NOTRUN")


if __name__ == "__main__":
    unittest.main()
