"""Specialists receive real, frozen knowledge from an isolated Software Vault."""
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

import yaml

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.method_experts import ExpertCatalog, EXPERTS_DIR, COMMON_DIR, LITERATURE_DIR, KNOWLEDGE_NOTES
from gurumoji.services.expert_agents import (
    CONTRACT_NOTE, ExpertAgentRegistry, catalog_packet, expert_profile, validate_shape,
)
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
from gurumoji.services.obsidian_management import management_packet
import test_analysis_orchestration as fixtures

ROOT = Path(__file__).resolve().parents[1]
EXPERT = "exp-thematic-analysis"


class ExpertAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "SoftwareVault"
        self.local = self.root / "local_knowledge"
        source = ROOT / "docs/program-vault"
        base = ExpertCatalog(root=source, local_root=self.local)
        definition = base.definition(EXPERT)
        self.folder = EXPERTS_DIR / "thematic-analysis"
        names = [self.folder / name for name in (*KNOWLEDGE_NOTES, CONTRACT_NOTE)]
        names += [COMMON_DIR / f"{name}.md" for name in definition["common_notes"]]
        names += [LITERATURE_DIR / f"{name}.md" for name in definition["literature"]]
        for relative in names:
            target = self.vault / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)
        self.catalog = ExpertCatalog(root=self.vault, local_root=self.local)
        self.registry = ExpertAgentRegistry(self.catalog)
        self.calls = []
        self.transport_calls = []
        self.snap = {"input_hash": "v1", "source_revision": 1, "analysis_revision": 1,
                     "analysis": {"automatic": {"overview": {"included_segment_count": 2, "speaker_count": 2}}, "segments": [
                         {"id": "u1", "text": "Synthetic statement", "speaker": "A"},
                         {"id": "u2", "text": "Synthetic counterexample", "speaker": "B"}]}}
        self.item = {"id": "synthetic", "revision": "v1"}
        self.service = self.make_service()

    def connect(self):
        return sqlite3.connect(self.root / "library.sqlite3")

    def make_service(self, **extra):
        return AnalysisOrchestrationService(connect=self.connect, find_item=lambda _: self.item,
            snapshot_builder=lambda _: copy.deepcopy(self.snap), source_fingerprint=lambda _: "v1",
            method_runner=lambda *_: {}, agent_runner=self.agent, schedule=False,
            expert_provider=self.registry.freeze, **extra)

    def start(self, **extra):
        return self.service.start("synthetic", {"model": "fixture", "question": "Synthetic research question",
            "expert_ids": [EXPERT], "time_limit_seconds": None, "max_calls": 15, **extra})

    def report(self, context):
        profile = context["expert_request"]["knowledge"]
        evidence_id = context["raw_evidence"][0]["evidence_id"]
        return {"summary": "Synthetic expert draft", "claims": [], "analysis_requests": [], "label_patches": [],
                "expert_report": {"expert_id": EXPERT, "profile_hash": profile["profile_hash"],
                    "knowledge_hash": profile["knowledge_hash"], "status": "draft",
                    "outputs": {name: "Synthetic bounded draft" for name in profile["output_schema"]["properties"]},
                    "evidence_ids": [evidence_id], "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                    "performed_step_ids": [profile["allowed_steps"][0]["id"]], "missing_inputs": [],
                    "limitations": "Human interpretation and unread text remain unchecked."}}

    def agent(self, role, context, options, check, usage):
        self.calls.append((role, copy.deepcopy(context)))
        if role == "core":
            if context["budget"]["completed_core_iterations"] == 0:
                return fixtures.core(intents=[fixtures.intent("interpretation", expert_id=EXPERT)])
            return fixtures.stop()
        if role == "interpretation":
            return self.report(context)
        return fixtures.critic(context)

    def drive(self, run):
        self.service.run(run["run_id"])
        return self.service.status("synthetic", run["run_id"])

    def test_typed_opt_in_keeps_legacy_fields_and_binds_fixed_source(self):
        from gurumoji.services.expert_agents import thematic_source_packet, request_packet, validate_report, render_expert_context
        from test_analysis_typed_assets import candidate_fixture
        run = self.start(); self.drive(run)
        initial = self.service.result("synthetic", run["run_id"])["initial"]
        source = thematic_source_packet(initial, library_id="TEST-library", conversation_id="synthetic")
        profile = self.registry.freeze({"expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"typed_contract": "thematic_candidates_v1"}}})["profiles"][EXPERT]
        context = copy.deepcopy(next(c for r, c in self.calls if r == "interpretation"))
        packet = request_packet(profile, context, initial["snapshot"]["analysis"], thematic_source=source)
        self.assertEqual(profile["contract_version"], 2)
        self.assertEqual(len(profile["output_schema"]["properties"]), 7)
        self.assertEqual(packet["thematic_source"]["source_ref"], source["source_ref"])
        self.assertNotIn("text", packet["thematic_source"]["utterance_index"][0])
        context["expert_request"] = packet
        producer = {"kind": "ai", "actor_id": "TEST-model", "step_ids": [profile["allowed_steps"][0]["id"]],
                    "model_id": "TEST-model", "revision": "TEST-revision", "provider": "TEST-provider"}
        raw = self.report(context); raw["expert_report"]["thematic_candidates_v1"] = candidate_fixture(source, producer=producer)
        validate_report(profile, raw, raw["expert_report"]["evidence_ids"], thematic_source=source)
        rendered = render_expert_context(context)
        self.assertEqual(rendered["expert_request"]["typed_contract"], "thematic_candidates_v1")
        self.assertEqual(rendered["expert_request"]["thematic_source"], packet["thematic_source"])
        with self.assertRaises(AnalysisContractError): request_packet(profile, context, initial["snapshot"]["analysis"])

    def test_handler_loads_selected_knowledge_and_receipts_without_exposing_text_to_core(self):
        final = self.drive(self.start())
        self.assertEqual(final["status"], "completed", final.get("error"))
        core_context = self.calls[0][1]
        self.assertEqual(core_context["expert_catalog"]["experts"][0]["expert_id"], EXPERT)
        self.assertNotIn("knowledge", core_context["expert_catalog"]["experts"][0])
        packet = next(c["expert_request"] for r, c in self.calls if r == "interpretation")
        self.assertTrue(any("Braun" in n["excerpt"] for n in packet["knowledge"]["knowledge"]))
        self.assertTrue(packet["knowledge"]["prohibited_conclusions"])
        self.assertEqual(set(packet["knowledge"]["output_schema"]["properties"]), {
            "research_context", "analysis_form", "candidate_themes", "theme_evidence",
            "theme_relations", "quality_record", "limitations"})
        self.assertTrue(all(row["source_hash"].startswith("sha256:") for row in packet["knowledge"]["knowledge"]))
        self.assertTrue(any(event["type"] == "expert_knowledge_loaded" for event in final["events"]))
        with self.service._db() as db:
            exported = self.service.result_locked(db, "synthetic", final["run_id"])
        self.assertEqual(exported["expert_knowledge_snapshot"]["bundle_hash"], final["expert_agents"]["bundle_hash"])
        self.assertNotIn("profiles", final["expert_agents"])
        memory = management_packet(final, [])
        self.assertEqual(memory["expert_calls"][0]["expert_id"], EXPERT)
        self.assertNotIn("expert_request", json.dumps(memory))

    def test_profile_is_frozen_even_when_source_changes_before_execution(self):
        run = self.start()
        with self.service._db() as db:
            frozen = copy.deepcopy(self.service._read_run(db, run["run_id"])["expert_agents"])
        note = self.vault / self.folder / "02-Procedure.md"
        note.write_text(note.read_text(encoding="utf-8") + "\nChanged synthetic knowledge.\n", encoding="utf-8")
        updated = self.registry.freeze({"expert_ids": [EXPERT]})
        self.assertNotEqual(updated["bundle_hash"], frozen["bundle_hash"])
        self.drive(run)
        packet = next(c["expert_request"] for r, c in self.calls if r == "interpretation")
        self.assertEqual(packet["profile_hash"], frozen["profiles"][EXPERT]["profile_hash"])
        self.assertNotIn("Changed synthetic knowledge", json.dumps(packet))

    def test_missing_or_modified_knowledge_and_unknown_expert_are_not_adopted(self):
        bundle = self.registry.freeze({"expert_ids": [EXPERT]})
        bundle["profiles"][EXPERT]["knowledge"][0]["excerpt"] = "tampered"
        with self.assertRaises(AnalysisContractError):
            catalog_packet(bundle)
        for ids in (["exp-unknown"], [["invalid"]]):
            with self.subTest(ids=ids), self.assertRaises(AnalysisContractError):
                self.registry.freeze({"expert_ids": ids})
        (self.vault / self.folder / "03-Quality.md").unlink()
        with self.assertRaises(AnalysisContractError) as caught:
            self.start()
        self.assertEqual(caught.exception.code, "expert_knowledge_missing")
        self.assertEqual(self.calls, [])

    def test_local_contract_defines_typed_inputs_and_outputs_and_rejects_wrong_input(self):
        contract = {"schema_version": 1, "expert_id": EXPERT, "contract_version": 2,
                    "input_fields": [{"id": "research_premise", "title": "Synthetic premise", "type": "string", "required": True}],
                    "output_fields": [{"id": "candidate_count", "title": "Synthetic count", "type": "integer", "required": True}]}
        target = self.local / self.folder / CONTRACT_NOTE
        target.parent.mkdir(parents=True)
        target.write_text("---\nnote_id: local-contract\n---\n```yaml\n" + yaml.safe_dump(contract) + "```\n", encoding="utf-8")
        for value in ({}, {"research_premise": 2}, {"research_premise": "x", "extra": "x"}):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError):
                self.start(expert_inputs={EXPERT: value})
        bundle = self.registry.freeze({"expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"research_premise": "fixture"}}})
        profile = expert_profile(bundle, EXPERT)
        self.assertEqual(profile["contract_version"], 2)
        self.assertEqual(profile["inputs"], {"research_premise": "fixture"})
        validate_shape(profile["output_schema"], {"candidate_count": 3})
        with self.assertRaises(AnalysisContractError):
            validate_shape(profile["output_schema"], {"candidate_count": True})

    def test_handler_quarantines_unknown_output_field_hash_note_step_or_evidence(self):
        original = self.report
        mutations = [lambda r: r["outputs"].update(extra="invalid"),
                     lambda r: r.update(profile_hash="invented"),
                     lambda r: r.update(knowledge_note_ids=["invented"]),
                     lambda r: r.update(performed_step_ids=["ta-p6"]),
                     lambda r: r.update(evidence_ids=["invented"]),
                     lambda r: r.update(status="needs_input", missing_inputs=[])]
        for index, mutate in enumerate(mutations):
            def broken(context, mutate=mutate):
                raw = original(context)
                mutate(raw["expert_report"])
                return raw
            self.report = broken
            final = self.drive(self.start(request_id=f"invalid-{index}"))
            task = next(task for task in final["tasks"] if task["role"] == "interpretation")
            self.assertEqual(task["status"], "quarantined", task)
        self.report = original

    def test_core_must_select_a_known_expert_and_cannot_assign_it_to_verification(self):
        for role, eid in (("interpretation", ""), ("interpretation", "exp-unknown"), ("verification", EXPERT)):
            self.calls.clear()
            self.service.agent_runner = lambda *_: fixtures.core(intents=[fixtures.intent(role=role, expert_id=eid)])
            final = self.drive(self.start(request_id=f"intent-{role}-{eid}"))
            self.assertEqual(final["tasks"][0]["status"], "quarantined")
            self.assertEqual(final["tasks"][0]["error"], "expert_selection_invalid")

    def test_provider_receives_same_knowledge_and_schema_for_local_and_cloud(self):
        from types import SimpleNamespace
        calls = []
        resolve, runner = make_orchestration_adapters(call_ai_json=lambda *args: calls.append(args) or {},
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("synthetic", "synthetic"))
        self.drive(self.start())
        context = next(c for r, c in self.calls if r == "interpretation")
        for provider in ("lmstudio", "openai", "google"):
            runner("interpretation", context, resolve({"provider": provider, "provider_policy": "cloud_allowed", "cloud_consent": True}), lambda: None, lambda _: None)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][3:7], calls[1][3:7])
        self.assertEqual(calls[1][3:7], calls[2][3:7])
        self.assertIn("専門家として", calls[0][3])
        self.assertIn("expert_report", calls[0][6]["required"])
        self.assertIn("expert_request", json.loads(calls[0][4]))
        rendered = json.loads(calls[0][4])
        self.assertNotIn("input_schema", rendered["expert_request"]["knowledge"])
        self.assertNotIn("output_schema", rendered["expert_request"]["knowledge"])
        self.assertNotIn("excerpt", rendered["expert_request"]["rendered_omissions"])
        self.assertEqual(rendered["expert_request"]["knowledge"]["knowledge"][0]["excerpt"],
                         context["expert_request"]["knowledge"]["knowledge"][0]["excerpt"])
        self.assertLess(sum(len(row["excerpt"]) for row in rendered["expert_request"]["knowledge"]["knowledge"]), 8001)
        self.assertEqual(calls[0][6]["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"],
                         sorted(row["evidence_id"] for row in context["raw_evidence"]))

    def test_expert_ids_are_part_of_task_identity_and_old_runs_do_not_gain_knowledge(self):
        run = self.start()
        with self.service._db() as db:
            saved = self.service._read_run(db, run["run_id"])
            first = self.service._register(db, saved, fixtures.intent("interpretation", expert_id=EXPERT), phase="specialists")
            duplicate = self.service._register(db, saved, fixtures.intent("interpretation", expert_id=EXPERT), phase="specialists")
            self.assertIsNone(duplicate)
            self.assertEqual(first["expert_agent"]["expert_id"], EXPERT)
        old = AnalysisOrchestrationService(connect=self.connect, find_item=lambda _: self.item,
            snapshot_builder=lambda _: copy.deepcopy(self.snap), source_fingerprint=lambda _: "v1",
            method_runner=lambda *_: {}, agent_runner=self.agent, schedule=False)
        legacy = old.start("synthetic", {"model": "fixture", "request_id": "legacy"})
        self.assertNotIn("expert_agents", legacy)
        with old._db() as db:
            exported = old.result_locked(db, "synthetic", legacy["run_id"])
        self.assertNotIn("expert_knowledge_snapshot", exported)

    def test_codegen_only_expert_stays_unavailable_to_llm(self):
        base = ExpertCatalog(root=ROOT / "docs/program-vault", local_root=self.local)
        with self.assertRaises(AnalysisContractError) as caught:
            ExpertAgentRegistry(base).freeze({"expert_ids": ["exp-participation-balance"]})
        self.assertEqual(caught.exception.code, "expert_ai_unavailable")

    def test_note_edit_during_freeze_is_detected(self):
        original = self.catalog.knowledge
        def changed(*args):
            knowledge = original(*args)
            note = self.vault / self.folder / "03-Quality.md"
            note.write_text(note.read_text(encoding="utf-8") + "\nSynthetic concurrent edit.\n", encoding="utf-8")
            return knowledge
        self.catalog.knowledge = changed
        with self.assertRaises(AnalysisContractError) as caught:
            self.start()
        self.assertEqual(caught.exception.code, "expert_knowledge_hash_mismatch")
        self.assertEqual(self.calls, [])

    def test_independent_verification_stays_blind(self):
        run = self.start()
        with self.service._db() as db:
            saved = self.service._read_run(db, run["run_id"])
            task = self.service._register(db, saved, {"role": "verification", "question": "biased expected answer"}, phase="specialists", automatic=True)
            packet = self.service._context(db, saved, task)
        self.assertTrue(packet["blind_first"])
        self.assertNotIn("expert_agents", packet)
        self.assertNotIn("expert_request", packet)
        self.assertNotIn("biased expected answer", json.dumps(packet))

    def test_previous_bundle_is_readable_without_relabeling_or_mutating_it(self):
        bundle = self.registry.freeze({"expert_ids": [EXPERT]})
        bundle["version"] = "obsidian-expert-agents-1"
        profile = bundle["profiles"][EXPERT]
        profile["agent_version"] = bundle["version"]
        profile["profile_hash"] = fingerprint({key: value for key, value in profile.items() if key != "profile_hash"})
        bundle["bundle_hash"] = fingerprint({key: value for key, value in bundle.items() if key != "bundle_hash"})
        before = copy.deepcopy(bundle)
        catalog = catalog_packet(bundle)
        self.assertEqual(catalog["version"], "obsidian-expert-agents-1")
        self.assertEqual(expert_profile(bundle, EXPERT)["agent_version"], catalog["version"])
        self.assertEqual(bundle, before)

    def test_not_applicable_input_is_rejected_before_the_specialist_call(self):
        self.snap["analysis"]["segments"][1]["speaker"] = "A"
        self.snap["analysis"]["automatic"]["overview"]["speaker_count"] = 1
        # Add a real, deterministic prerequisite to the isolated definition.
        note = self.vault / self.folder / "01-Expert.md"
        text = note.read_text(encoding="utf-8")
        text = text.replace("check: min_included_segments", "check: min_speakers").replace("min: 1", "min: 2")
        note.write_text(text, encoding="utf-8")
        final = self.drive(self.start())
        task = next(t for t in final["tasks"] if t["role"] == "interpretation")
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error"], "expert_not_applicable")
        self.assertEqual([r for r, _ in self.calls], ["core"])
        self.assertEqual(final["usage"]["calls"], 1)


class StatisticalContractRegistryTests(unittest.TestCase):
    def setUp(self):
        import test_statistical_expert_agents as statistics
        self.h = statistics.StatisticalExpertTests(methodName="runTest")
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)

    def test_version_two_requires_exact_keys_valid_actor_ids_and_binding_policy(self):
        profile = self.h.registry.freeze({"expert_ids": ["exp-correlation"]})["profiles"]["exp-correlation"]
        contract = {"schema_version": 2, "expert_id": profile["expert_id"], "contract_version": 2,
                    **{key: copy.deepcopy(profile[key]) for key in ("input_fields", "output_fields", "phase_requirements", "numeric_binding")}}
        target = self.h.catalog.local_root / EXPERTS_DIR / "correlation" / CONTRACT_NOTE
        target.parent.mkdir(parents=True)
        mutations = (
            lambda c: c.update(schema_version=3), lambda c: c.update(extra="unknown"),
            lambda c: c.update(contract_version=1), lambda c: c.pop("phase_requirements"),
            lambda c: c["phase_requirements"].update(unknown={}),
            lambda c: c["phase_requirements"]["analysis_plan"].update(ai_draft=[]),
            lambda c: c["phase_requirements"]["analysis_plan"].update(ai_draft=["cor-ai-plan", "cor-ai-plan"]),
            lambda c: c["phase_requirements"]["analysis_plan"].update(ai_draft=["cor-p1"]),
            lambda c: c["phase_requirements"]["analysis_plan"].update(code=["cor-p2"]),
            lambda c: c["phase_requirements"]["result_explanation"].update(code=["cor-p3"]),
            lambda c: c["phase_requirements"]["result_explanation"].update(researcher=["invented"]),
            lambda c: c["phase_requirements"]["result_explanation"].update(code=["cor-p2", "cor-p2"]),
            lambda c: c["numeric_binding"].update(render_policy="arbitrary-precision"),
            lambda c: c["numeric_binding"]["required_fields"].append("value"),
            lambda c: c["numeric_binding"].update(extra=True))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(contract)
                mutate(changed)
                target.write_text("---\nnote_id: synthetic-contract\n---\n```yaml\n" + yaml.safe_dump(changed) + "```\n", encoding="utf-8")
                with self.assertRaises(AnalysisContractError):
                    self.h.registry.freeze({"expert_ids": ["exp-correlation"]})

    def test_each_domain_phase_requirements_match_existing_actor_definitions(self):
        from gurumoji.services.analysis_orchestration_methods import EXPERT_STATISTICAL_TOOLS
        for eid in EXPERT_STATISTICAL_TOOLS:
            with self.subTest(expert=eid):
                profile = self.h.registry.freeze({"expert_ids": [eid]})["profiles"][eid]
                actors = {step["id"]: step["actor"] for step in self.h.catalog.definition(eid)["procedure"]}
                self.assertEqual(profile["contract_schema_version"], 2)
                for phase, requirements in profile["phase_requirements"].items():
                    for actor, steps in requirements.items():
                        self.assertTrue(all(actors[step] == actor for step in steps))
                self.assertEqual(profile["numeric_binding"]["render_policy"], "statistical-cells-v1")

    def test_legacy_frozen_bundle_run_and_results_read_without_revalidation_or_upgrade(self):
        import test_statistical_expert_agents as statistics
        from gurumoji.analysis_orchestration import recover_orchestration_runs
        h = self.h
        for version in ("obsidian-expert-agents-1", "obsidian-expert-agents-2"):
            with self.subTest(version=version):
                run = h.start()
                task = h.dispatch(run, statistics.fixtures.intent("interpretation", expert_id="exp-correlation"))
                with h.service._db() as db:
                    saved = h.service._read_run(db, run["run_id"])
                    bundle = saved["expert_agents"]
                    bundle["version"] = version
                    profile = bundle["profiles"]["exp-correlation"]
                    for key in ("contract_schema_version", "phase_requirements", "numeric_binding"):
                        profile.pop(key)
                    profile.update(agent_version=version, contract_version=1)
                    profile["profile_hash"] = fingerprint({k: v for k, v in profile.items() if k != "profile_hash"})
                    bundle["bundle_hash"] = fingerprint({k: v for k, v in bundle.items() if k != "bundle_hash"})
                    saved["config"]["adapter_version"] = "legacy-adapter"
                    h.service._write_run(db, saved)
                    row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (task["result_id"],)).fetchone()
                    raw, meta = json.loads(row[0]), json.loads(row[1])
                    raw["expert_report"].pop("numeric_bindings")
                    raw["expert_report"]["profile_hash"] = profile["profile_hash"]
                    meta.pop("statistical_review")
                    meta["raw_hash"] = fingerprint(raw)
                    db.execute("UPDATE orchestration_results SET raw_json=?,state_json=? WHERE result_id=?", (json.dumps(raw), json.dumps(meta), task["result_id"]))
                    recover_orchestration_runs(db)
                    before = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (task["result_id"],)).fetchone()
                calls_before = len(h.calls)
                for _ in range(2):
                    state = h.service.status("synthetic", run["run_id"])
                    result = h.service.result("synthetic", run["run_id"], task["result_id"])
                    self.assertEqual(result["raw"], raw)
                    self.assertEqual(result["raw_hash"], meta["raw_hash"])
                    self.assertEqual(result["content_status"], "unreviewed")
                    self.assertNotIn("statistical_review", result)
                    self.assertEqual(state["expert_agents"]["bundle_hash"], bundle["bundle_hash"])
                with self.assertRaises(AnalysisContractError) as caught:
                    h.service.resume("synthetic", run["run_id"])
                self.assertEqual(caught.exception.code, "adapter_version_conflict")
                with h.service._db() as db:
                    after = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (task["result_id"],)).fetchone()
                    self.assertEqual(tuple(after), tuple(before))
                self.assertEqual(len(h.calls), calls_before)


class SkillContextAgentTests(unittest.TestCase):
    def catalog(self):
        from gurumoji.method_experts import SKILL_CONTEXT_VERSION
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        return ExpertCatalog(root=ROOT / "docs/program-vault", local_root=Path(self.temp.name) / "local"), SKILL_CONTEXT_VERSION

    def test_opt_in_preserves_TA_seven_strings_and_current_statistics_phases(self):
        catalog, version = self.catalog(); registry = ExpertAgentRegistry(catalog)
        for eid in ("exp-thematic-analysis", "exp-correlation", "exp-group-comparison-statistics"):
            profile = expert_profile(registry.freeze({"expert_ids": [eid], "skill_context": {"version": version, "workflow": False}}), eid)
            if eid == "exp-thematic-analysis":
                self.assertEqual(len(profile["output_fields"]), 7)
                self.assertTrue(all(field["type"] == "string" for field in profile["output_fields"]))
                self.assertNotIn("contract_schema_version", profile)
            else:
                self.assertEqual(profile["contract_schema_version"], 2)
                self.assertEqual(set(profile["phase_requirements"]), {"analysis_plan", "result_explanation"})
            self.assertFalse(profile["skill_binding_context"]["production_default_enabled"])
            self.assertEqual(profile["skill_binding_context"]["human_adoption"], "unanswered")

    def test_default_currentPack_matches_fixed_previous_reader(self):
        import subprocess
        import types
        catalog, _ = self.catalog(); config = {"expert_ids": [EXPERT]}
        source = subprocess.check_output(["git", "show", "6f1d532c5a0ce995b03e3dca191f358eeed6d42f:src/gurumoji/services/expert_agents.py"])
        previous = types.ModuleType("gurumoji.services._fixed_expert_reader"); previous.__package__ = "gurumoji.services"
        exec(compile(source, "<fixed B expert reader>", "exec"), previous.__dict__)
        old = previous.ExpertAgentRegistry(catalog).freeze(config)
        new = ExpertAgentRegistry(catalog).freeze(config)
        self.assertEqual(new, old)
        self.assertNotIn("skill_binding_context", expert_profile(new, EXPERT))

    def test_render_path_keeps_complete_registered_skill_body(self):
        from gurumoji.services.expert_agents import render_expert_context
        catalog, version = self.catalog(); registry = ExpertAgentRegistry(catalog)
        profile = expert_profile(registry.freeze({"expert_ids": [EXPERT], "skill_context": {"version": version, "workflow": True}}), EXPERT)
        context = {"expert_request": {"knowledge": profile, "evidence": [], "coverage": {}}, "coverage": {},
                   "task": {"task_id": "TEST", "role": "interpretation", "title": "TEST", "codebook_version": 1},
                   "raw_evidence": [], "labels": {}}
        rendered = render_expert_context(context)
        self.assertEqual(rendered["expert_request"]["knowledge"]["skill_binding_context"], profile["skill_binding_context"])
        self.assertIn("HumanRecord", json.dumps(rendered, ensure_ascii=False))
        self.assertIn("giew-procedure-guards", json.dumps(rendered, ensure_ascii=False))

    def test_connection_catalog_uses_authoritative_07_and_native_slots(self):
        from gurumoji.analysis_core import validate_connection_slot
        catalog, _ = self.catalog(); registry = ExpertAgentRegistry(catalog)
        data = registry.connection_catalog("exp-correlation")
        self.assertEqual(set(data["methods"]), {"correlation", "pearson", "spearman"})
        self.assertEqual(data["methods"]["correlation"]["input_slots"], [])
        for method in ("pearson", "spearman"):
            slot = validate_connection_slot(data["methods"][method]["input_slots"][0])
            self.assertEqual(slot["accept_kinds"], [])
            self.assertEqual(slot["accept_source_types"], ["snapshot"])
        self.assertFalse(data["typed_candidate_parser_implemented"])
        self.assertFalse(data["production_default_enabled"])
        self.assertEqual(data["callback_state"], "planned")


if __name__ == "__main__":
    unittest.main()
