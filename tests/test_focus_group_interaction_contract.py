"""Issue31: isolated synthetic CPU Handler/Store proof; no models or network."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import types
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.analysis_store import AnalysisStore
from gurumoji.method_experts import ExpertCatalog, SKILL_NOTE_REFS
from gurumoji.services.expert_agents import (
    ExpertAgentRegistry, FGI_CONTRACT, FGI_EXPERT,
    render_expert_context, report_schema, thematic_source_packet, validate_report,
)
from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
from test_analysis_asset_bindings import SyntheticStore
import test_analysis_orchestration as fixtures

ROOT = Path(__file__).resolve().parents[1]
BASE = "220b62dcfdaa1dea8f5eebc4c66688fa7e6c8d26"


def candidate_report(context):
    packet = context["expert_request"]
    profile = packet["knowledge"]
    source = packet["thematic_source"]
    steps = ["fgi-p3", "fgi-p5"]
    rows = context["raw_evidence"]
    refs = [{"evidence_id": row["evidence_id"], "utterance_id": row["utterance_id"],
             "utterance_hash": "sha256:" + hashlib.sha256(row["text"].encode()).hexdigest()} for row in rows]
    value = {"version": FGI_CONTRACT, "source_ref": copy.deepcopy(source["source_ref"]),
        "scope": copy.deepcopy(source["scope"]), "producer": {**packet["expected_producer"], "step_ids": steps},
        "coverage": copy.deepcopy(packet["delivery_coverage"]), "human_status": "human_pending",
        "human_record_state": "not_entered", "human_records": [], "semantic_review": "undetermined",
        "eligible_as_confirmed_evidence": False,
        "candidates": [
            {"candidate_id": "TEST-question", "step_id": "fgi-p3", "relation_kind": "question_answer",
             "text": "Synthetic question and response candidate.", "limitations": "Unverified text-only draft; human interpretation pending.",
             "evidence_refs": refs[:2]},
            {"candidate_id": "TEST-disagreement", "step_id": "fgi-p5", "relation_kind": "disagreement_candidate",
             "text": "Synthetic disagreement candidate.", "limitations": "Unverified text-only draft; human interpretation pending.",
             "evidence_refs": refs[1:3]},
            {"candidate_id": "TEST-change", "step_id": "fgi-p5", "relation_kind": "opinion_change_candidate",
             "text": "Synthetic disagreement and change candidate.", "limitations": "Unverified text-only draft; human interpretation pending.",
             "evidence_refs": refs[1:4]},
        ]}
    return {"summary": "Synthetic FGI draft; human review pending.", "claims": [], "analysis_requests": [], "label_patches": [],
        "expert_report": {"expert_id": FGI_EXPERT, "profile_hash": profile["profile_hash"], "knowledge_hash": profile["knowledge_hash"],
            "status": "draft", "outputs": {key: "Unverified synthetic AI draft; researcher steps remain pending."
                                           for key in profile["output_schema"]["properties"]},
            "evidence_ids": [r["evidence_id"] for r in rows], "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
            "performed_step_ids": steps, "missing_inputs": [], "limitations": "Text-only draft; semantics and researcher adoption remain unverified.",
            FGI_CONTRACT: value}}


class FocusGroupInteractionContractTests(unittest.TestCase):
    def setUp(self):
        network = patch("socket.socket", side_effect=AssertionError("Synthetic CPU tests must not use network."))
        network.start(); self.addCleanup(network.stop)
        self.fixture = SyntheticStore(handler=True)
        self.addCleanup(self.fixture.close)
        self.catalog = ExpertCatalog(root=ROOT / "docs/program-vault", local_root=Path(self.fixture.temp.name) / "local")
        self.registry = ExpertAgentRegistry(self.catalog)
        self.segments = [
            {"id": "TEST-u1", "speaker": "TEST-A", "text": "Which route shall we try?"},
            {"id": "TEST-u2", "speaker": "TEST-B", "text": "I suggest the short route."},
            {"id": "TEST-u3", "speaker": "TEST-A", "text": "I disagree; the long route avoids traffic."},
            {"id": "TEST-u4", "speaker": "TEST-B", "text": "That changes my view; I suggest the long route."},
        ]
        self.manual = {"preparation": {"status": "confirmed", "order_verified": True, "unknown_speaker_turns": 0,
                                       "analysis_needs_review": False},
                       "interaction_links": [{"id": "TEST-manual", "source_id": "TEST-u1", "target_id": "TEST-u4",
                                              "relation": "researcher-original", "memo": "Never replace this manual record."}]}
        self.snapshot = {"conversation_id": "TEST-conversation", "input_hash": fingerprint({"TEST_input": 31}),
            "source_revision": 1, "analysis_revision": 1, "analysis": {"segments": copy.deepcopy(self.segments),
                "manual": copy.deepcopy(self.manual), "automatic": {"overview": {"segment_count": 4,
                    "included_segment_count": 4, "speaker_count": 2, "participant_count": 2},
                    "data_quality": {"unknown_speaker_segments": 0}}}}
        with self.fixture.connect() as db:
            db.execute("UPDATE library_items SET analysis_annotations_json=? WHERE id='TEST-conversation'", (json.dumps(self.manual),))
        self.calls = []
        self.raw_sent = []
        self.services = []

    def service(self, *, mutate=None, store=None, selected=False, missing_store=False, needs_input=False):
        def agent(role, context, *args):
            self.calls.append((role, copy.deepcopy(context)))
            if role == "core":
                if context["budget"]["completed_core_iterations"] == 0:
                    intent = fixtures.intent("interpretation", expert_id=FGI_EXPERT)
                    if selected:
                        intent["evidence_ids"] = [r["evidence_id"] for r in context["raw_evidence"][:2]]
                    return fixtures.core(intents=[intent])
                return fixtures.stop()
            if role == "critic": return fixtures.critic(context)
            raw = candidate_report(context)
            if needs_input:
                raw["expert_report"].update(status="needs_input", missing_inputs=["Complete text delivery is required."],
                                            **{FGI_CONTRACT: None})
            if mutate: mutate(raw, context)
            self.raw_sent.append(copy.deepcopy(raw))
            return raw
        service = AnalysisOrchestrationService(connect=self.fixture.connect,
            find_item=lambda _: {"id": "TEST-conversation", "revision_count": 1, "analysis_revision": 1},
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot), source_fingerprint=lambda _: self.snapshot["input_hash"],
            method_runner=lambda *_: self.fail("No code method expected"), agent_runner=agent,
            expert_provider=self.registry.freeze, table_store=None if missing_store else store or self.fixture.store, schedule=False)
        self.services.append(service)
        return service

    def drive(self, service=None, **config):
        service = service or self.service()
        run = service.start("TEST-conversation", {"model": "TEST-model", "question": "Synthetic FGI question",
            "time_limit_seconds": None, "max_calls": 15, "expert_ids": [FGI_EXPERT],
            "expert_inputs": {FGI_EXPERT: {"typed_contract": FGI_CONTRACT}}, **config})
        service.run(run["run_id"])
        result = service.result("TEST-conversation", run["run_id"])
        return service, run, result

    def accepted(self, **config):
        service, run, result = self.drive(**config)
        expert = next(r for r in result["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "valid", expert)
        self.context = next(c for role, c in self.calls if role == "interpretation")
        self.profile = self.context["expert_request"]["knowledge"]
        self.source = thematic_source_packet(result["initial"], library_id=self.fixture.store.library_id(), conversation_id="TEST-conversation")
        self.delivery = self.context["expert_request"]["delivery_coverage"]
        self.raw = expert["raw"]
        return service, run, result, expert

    def validate(self, raw=None, *, source=None, evidence_ids=None, delivery=None, producer=None, analysis=None):
        return validate_report(self.profile, self.raw if raw is None else raw,
            self.context["expert_request"]["delivery_coverage"]["delivered_evidence_ids"] if evidence_ids is None else evidence_ids,
            thematic_source=self.source if source is None else source,
            source_analysis=self.snapshot["analysis"] if analysis is None else analysis,
            expected_producer=self.context["expert_request"]["expected_producer"] if producer is None else producer,
            expected_delivery=self.delivery if delivery is None else delivery)

    def assert_rejected_mutations(self, mutations):
        for name, mutate in mutations:
            with self.subTest(case=name):
                raw = copy.deepcopy(self.raw)
                mutate(raw["expert_report"][FGI_CONTRACT], raw["expert_report"], raw)
                with self.assertRaises(AnalysisContractError): self.validate(raw)

    def test_handler_store_fresh_preserves_raw_and_manual_records(self):
        service, run, result, expert = self.accepted()
        self.assertEqual(expert["raw"], self.raw_sent[0])
        self.assertEqual(expert["raw_hash"], fingerprint(self.raw_sent[0]))
        typed = expert["raw"]["expert_report"][FGI_CONTRACT]
        self.assertEqual(typed["source_ref"]["version"], self.snapshot["input_hash"])
        self.assertEqual(typed["source_ref"]["content_hash"], fingerprint(result["initial"]["snapshot"]))
        self.assertNotEqual(typed["source_ref"]["version"], typed["source_ref"]["content_hash"])
        self.assertEqual(typed["producer"], {"kind": "ai", "actor_id": expert["task_id"], "model_id": "TEST-model",
                                           "provider": "lmstudio", "revision": "unverified", "step_ids": ["fgi-p3", "fgi-p5"]})
        self.assertTrue(typed["coverage"]["complete"])
        self.assertEqual(typed["human_status"], "human_pending")
        self.assertFalse(typed["eligible_as_confirmed_evidence"])
        rendered = render_expert_context(self.context)
        self.assertEqual(rendered["expert_request"]["delivery_coverage"], self.delivery)
        publisher = AnalysisOrchestrationPublicationService(connect=self.fixture.connect, store_factory=lambda: self.fixture.store,
            source_guard=lambda db, item, expected: {"id": item}, export_locked=service.result_locked)
        publication = publisher.finalize("TEST-conversation", run["run_id"])
        self.assertEqual(publication["save_status"], "saved", publication)
        fresh = AnalysisStore(self.fixture.path, self.fixture.connect)
        stored_snapshot, saved, _, _ = fresh.verified_package(publication["result_run_id"])
        self.assertEqual(saved["orchestration"]["raw_results"], result["raw_results"])
        self.assertEqual(saved["orchestration"]["initial"]["snapshot"]["analysis"]["manual"], self.manual)
        self.assertEqual(stored_snapshot["segments"], self.snapshot["analysis"]["segments"])
        self.assertEqual(service.result("TEST-conversation", run["run_id"])["initial"]["snapshot"]["analysis"]["manual"], self.manual)
        with self.fixture.connect() as db:
            self.assertEqual(db.execute("SELECT analysis_annotations_json FROM library_items").fetchone()[0], json.dumps(self.manual))
        self.assertEqual(self.snapshot["analysis"]["manual"], self.manual)

    def test_support_cardinality_identity_order_and_hash_rejections(self):
        self.accepted()
        def refs(c): return c["candidates"][0]["evidence_refs"]
        self.assert_rejected_mutations([
            ("single", lambda c, r, raw: refs(c).pop()),
            ("duplicate", lambda c, r, raw: refs(c).__setitem__(1, copy.deepcopy(refs(c)[0]))),
            ("reversed", lambda c, r, raw: refs(c).reverse()),
            ("unknown", lambda c, r, raw: refs(c)[1].update(evidence_id="UNKNOWN")),
            ("wrong_utterance", lambda c, r, raw: refs(c)[1].update(utterance_id="TEST-u4")),
            ("utterance_hash", lambda c, r, raw: refs(c)[1].update(utterance_hash=fingerprint("wrong"))),
            ("not_reported", lambda c, r, raw: r["evidence_ids"].pop(0)),
            ("duplicate_candidate", lambda c, r, raw: c["candidates"][1].update(candidate_id=c["candidates"][0]["candidate_id"])),
        ])
        with self.assertRaises(AnalysisContractError): self.validate(evidence_ids=self.delivery["delivered_evidence_ids"][:-1])
        source = copy.deepcopy(self.source); source["evidence"][1]["excluded"] = True
        with self.assertRaises(AnalysisContractError): self.validate(source=source)

    def test_source_scope_crosschecks_reject_rehashed_forgery(self):
        self.accepted()
        self.assert_rejected_mutations([
            ("input_version", lambda c, r, raw: c["source_ref"].update(version="changed")),
            ("content_hash", lambda c, r, raw: c["source_ref"].update(content_hash=fingerprint("changed"))),
            ("library", lambda c, r, raw: c["source_ref"].update(library_id="other-library")),
            ("initial", lambda c, r, raw: c["source_ref"].update(target_id="other-initial")),
            ("scope_member", lambda c, r, raw: c["scope"]["member_ids"].pop()),
            ("scope_context", lambda c, r, raw: c["scope"]["context_ids"].append("TEST-u1")),
            ("conversation", lambda c, r, raw: c["scope"].update(conversation_ids=["other-conversation"])),
            ("scope_hash", lambda c, r, raw: c["scope"].update(manifest_hash=fingerprint("changed"))),
            ("two_conversations", lambda c, r, raw: c["scope"]["conversation_ids"].append("other")),
            ("coverage_count", lambda c, r, raw: c["coverage"].update(source_utterance_count=3)),
            ("coverage_delivery", lambda c, r, raw: c["coverage"]["delivered_evidence_ids"].pop()),
        ])
        raw = copy.deepcopy(self.raw); c = raw["expert_report"][FGI_CONTRACT]
        c["scope"]["member_ids"].pop(); c["scope"]["manifest_hash"] = fingerprint({k: v for k, v in c["scope"].items() if k != "manifest_hash"})
        with self.assertRaises(AnalysisContractError): self.validate(raw)

    def test_actor_step_human_record_and_auto_action_spoofs_rejected(self):
        self.accepted()
        self.assert_rejected_mutations([
            ("researcher", lambda c, r, raw: c["producer"].update(kind="researcher")),
            ("task", lambda c, r, raw: c["producer"].update(actor_id="other-task")),
            ("model", lambda c, r, raw: c["producer"].update(model_id="other-model")),
            ("provider", lambda c, r, raw: c["producer"].update(provider="other-provider")),
            ("revision", lambda c, r, raw: c["producer"].update(revision="verified")),
            ("human_step", lambda c, r, raw: c["candidates"][0].update(step_id="fgi-p4")),
            ("unperformed_step", lambda c, r, raw: r.update(performed_step_ids=["fgi-p3"])),
            ("wrong_step_relation", lambda c, r, raw: c["candidates"][0].update(step_id="fgi-p5")),
            ("duplicate_step", lambda c, r, raw: r.update(performed_step_ids=["fgi-p3", "fgi-p3"])),
            ("confirmed", lambda c, r, raw: c.update(human_status="confirmed")),
            ("record", lambda c, r, raw: c["human_records"].append({"actor": "researcher"})),
            ("human_state", lambda c, r, raw: c.update(human_record_state="entered")),
            ("semantics", lambda c, r, raw: c.update(semantic_review="confirmed")),
            ("eligible", lambda c, r, raw: c.update(eligible_as_confirmed_evidence=True)),
            ("claims", lambda c, r, raw: raw["claims"].append({"text": "No auto action"})),
            ("labels", lambda c, r, raw: raw["label_patches"].append({"code": "No auto action"})),
            ("requests", lambda c, r, raw: raw["analysis_requests"].append({"kind": "analysis"})),
        ])
        with self.assertRaises(AnalysisContractError):
            validate_report(self.profile, self.raw, self.delivery["delivered_evidence_ids"], thematic_source=self.source,
                            source_analysis=self.snapshot["analysis"], expected_delivery=self.delivery)

    def test_closed_schema_bounds_type_tricks_and_nonverbal_kinds_rejected(self):
        self.accepted()
        self.assert_rejected_mutations([
            ("extra_top", lambda c, r, raw: c.update(annotation={})),
            ("extra_candidate", lambda c, r, raw: c["candidates"][0].update(confirmed=True)),
            ("extra_ref", lambda c, r, raw: c["candidates"][0]["evidence_refs"][0].update(speaker="fake")),
            ("81_candidates", lambda c, r, raw: c.update(candidates=[copy.deepcopy(c["candidates"][0]) for _ in range(81)])),
            ("17_refs", lambda c, r, raw: c["candidates"][0].update(evidence_refs=c["candidates"][0]["evidence_refs"] * 9)),
            ("long_text", lambda c, r, raw: c["candidates"][0].update(text="a" * 2001)),
            ("long_limits", lambda c, r, raw: c["candidates"][0].update(limitations="a" * 2001)),
            ("empty_text", lambda c, r, raw: c["candidates"][0].update(text=" ")),
            ("bool_count", lambda c, r, raw: c["coverage"].update(source_utterance_count=True)),
            ("int_bool", lambda c, r, raw: c.update(eligible_as_confirmed_evidence=0)),
            ("list_kind", lambda c, r, raw: c["producer"].update(kind=[])),
            ("voice_kind", lambda c, r, raw: c["candidates"][0].update(relation_kind="voice_agreement")),
            ("silence_kind", lambda c, r, raw: c["candidates"][0].update(relation_kind="silence")),
            ("known_assertion", lambda c, r, raw: c["candidates"][0].update(text="Silence proves agreement.")),
            ("known_voice_assertion", lambda c, r, raw: c["candidates"][0].update(text="Voice tone proves disagreement.")),
            ("known_human_assertion", lambda c, r, raw: c["candidates"][0].update(text="These candidates are researcher-confirmed.")),
        ])
        raw = copy.deepcopy(self.raw); raw["expert_report"][FGI_CONTRACT]["candidates"][0]["text"] = "Silence does not prove agreement."
        self.validate(raw)

    def test_caution_polarity_is_local_to_the_prohibited_assertion(self):
        self.accepted()
        pairs = [
            ("沈黙は同意を示すわけではない。", "沈黙は同意を示す。"),
            ('Do not claim "Silence proves agreement".', '"Silence proves agreement".'),
            ('"Silence proves agreement" is unsupported.', '"Silence proves agreement" is supported.'),
            ("「沈黙は同意を示す」と断定しない。", "「沈黙は同意を示す」と断定する。"),
            ("沈黙は同意を示すとは限らない。", "沈黙は同意を示す。別の問題はない。"),
            ("These candidates are not researcher-confirmed.", "These candidates are researcher-confirmed, not merely tentative."),
            ('The claim "These candidates are researcher-confirmed" is unsupported.',
             'The claim "These candidates are researcher-confirmed" is supported.'),
        ]
        for caution, assertion in pairs:
            for text, accepted in ((caution, True), (assertion, False)):
                with self.subTest(text=text):
                    raw = copy.deepcopy(self.raw); raw["expert_report"]["limitations"] = text
                    if accepted:
                        self.validate(raw)
                        self.assertEqual(raw["expert_report"][FGI_CONTRACT]["human_status"], "human_pending")
                    else:
                        with self.assertRaises(AnalysisContractError) as caught: self.validate(raw)
                        self.assertEqual(caught.exception.code, "expert_prohibited_conclusion")
        for text in ('Do not claim "Silence proves agreement"; silence proves agreement.',
                     "No other issues: silence proves agreement.", "沈黙は同意を示すわけではない。しかし相づちは合意を意味する。"):
            raw = copy.deepcopy(self.raw); raw["expert_report"]["limitations"] = text
            with self.subTest(text=text), self.assertRaises(AnalysisContractError): self.validate(raw)

    def test_exact_candidate_text_and_evidence_bounds_accept(self):
        for i in range(5, 17):
            self.snapshot["analysis"]["segments"].append({"id": f"TEST-u{i}", "speaker": "TEST-A", "text": f"Synthetic turn {i}."})
        self.snapshot["analysis"]["automatic"]["overview"].update(segment_count=16, included_segment_count=16)
        self.accepted(expert_hooks=False)
        raw = copy.deepcopy(self.raw); typed = raw["expert_report"][FGI_CONTRACT]
        candidate = typed["candidates"][0]
        candidate["evidence_refs"] = [{"evidence_id": row["evidence_id"], "utterance_id": row["utterance_id"],
            "utterance_hash": "sha256:" + hashlib.sha256(row["text"].encode()).hexdigest()} for row in self.source["evidence"]]
        candidate.update(text="x" * 2000, limitations="x" * 2000)
        typed["candidates"] = [{**copy.deepcopy(candidate), "candidate_id": f"TEST-candidate-{i}"} for i in range(80)]
        self.validate(raw)

    def test_empty_examined_none_needs_proof_and_explicit_limitations(self):
        self.accepted()
        raw = copy.deepcopy(self.raw); raw["expert_report"][FGI_CONTRACT]["candidates"] = []
        raw["expert_report"]["limitations"] = "Examined the delivered text; no candidate proposed. Human interpretation remains pending."
        self.validate(raw)
        for key in ("limitations", "performed_step_ids", "evidence_ids"):
            bad = copy.deepcopy(raw); bad["expert_report"][key] = " " if key == "limitations" else []
            with self.subTest(key=key), self.assertRaises(AnalysisContractError): self.validate(bad)
        for status in ("needs_input", "not_applicable"):
            bad = copy.deepcopy(raw); bad["expert_report"].update(status=status, missing_inputs=["Incomplete source."])
            with self.subTest(status=status), self.assertRaises(AnalysisContractError): self.validate(bad)
            bad["expert_report"][FGI_CONTRACT] = None
            self.validate(bad)

    def test_handler_quarantines_invalid_raw_without_rewriting_original(self):
        def mutate(raw, context): raw["expert_report"][FGI_CONTRACT]["producer"]["actor_id"] = "forged-task"
        _, _, result = self.drive(self.service(mutate=mutate))
        expert = next(r for r in result["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "quarantined", expert)
        self.assertEqual(expert["error"], "typed_execution_provenance")
        self.assertEqual(expert["raw"], self.raw_sent[0])
        self.assertEqual(expert["raw_hash"], fingerprint(self.raw_sent[0]))

    def test_incomplete_delivery_cannot_be_claimed_complete_and_needs_input_survives(self):
        _, _, result = self.drive(context_evidence_limit=3)
        expert = next(r for r in result["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "quarantined", expert)
        self.assertEqual(expert["error"], "fgi_incomplete_delivery")
        _, _, result = self.drive(self.service(needs_input=True), context_evidence_limit=3)
        expert = next(r for r in result["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "valid", expert)
        self.assertEqual(expert["raw"]["expert_report"]["status"], "needs_input")

    def test_hook_truncated_body_is_not_full_delivery(self):
        self.snapshot["analysis"]["segments"][2]["text"] = "x" * 13000
        _, _, result = self.drive(expert_hooks=True)
        expert = next(r for r in result["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "quarantined", expert)
        self.assertEqual(expert["error"], "fgi_incomplete_delivery")
        self.assertFalse(expert["raw"]["expert_report"][FGI_CONTRACT]["coverage"]["complete"])

    def test_excluded_context_not_positive_support_or_complete_coverage(self):
        self.snapshot["analysis"]["segments"][3]["excluded"] = True
        _, _, result = self.drive()
        expert = next(r for r in result["raw_results"] if "expert_report" in r["raw"])
        self.assertEqual(expert["validation_status"], "quarantined", expert)
        typed = expert["raw"]["expert_report"][FGI_CONTRACT]
        self.assertEqual(typed["scope"]["context_ids"], ["TEST-u4"])
        self.assertEqual(typed["coverage"]["undelivered_utterance_ids"], ["TEST-u4"])
        self.assertFalse(typed["coverage"]["complete"])

    def test_missing_confirmation_single_participant_and_type_tricks_stop_before_call(self):
        original = copy.deepcopy(self.snapshot)
        for name, mutate in [
            ("missing_preparation", lambda a: a["manual"].pop("preparation")),
            ("order", lambda a: a["manual"]["preparation"].update(order_verified=False)),
            ("unknown_speaker", lambda a: a["manual"]["preparation"].update(unknown_speaker_turns=1)),
            ("single", lambda a: a["automatic"]["overview"].update(participant_count=1)),
            ("string_order", lambda a: a["manual"]["preparation"].update(order_verified="true")),
            ("bool_unknown", lambda a: a["manual"]["preparation"].update(unknown_speaker_turns=False)),
            ("string_participants", lambda a: a["automatic"]["overview"].update(participant_count="2")),
        ]:
            with self.subTest(case=name):
                self.snapshot = copy.deepcopy(original); mutate(self.snapshot["analysis"])
                self.snapshot["input_hash"] = fingerprint({"negative": name})
                before = len(self.raw_sent)
                _, _, result = self.drive()
                task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
                self.assertEqual(task["error"], "expert_not_applicable", task)
                self.assertEqual(len(self.raw_sent), before)

    def test_changed_immutable_snapshot_is_quarantined_at_handler_validation(self):
        def mutate(raw, context):
            with self.fixture.connect() as db:
                row = db.execute("SELECT initial_id,snapshot_json FROM orchestration_initials").fetchone()
                value = json.loads(row["snapshot_json"])
                value["evidence"][0]["text"] = "Tampered after delivery."
                db.execute("UPDATE orchestration_initials SET snapshot_json=? WHERE initial_id=?",
                           (json.dumps(value), row["initial_id"]))
        self.drive(self.service(mutate=mutate))
        with self.fixture.connect() as db:
            rows = db.execute("SELECT raw_json,state_json FROM orchestration_results").fetchall()
        raw, meta = next((json.loads(r["raw_json"]), json.loads(r["state_json"])) for r in rows
                         if "expert_report" in json.loads(r["raw_json"]))
        self.assertEqual(meta["validation_status"], "quarantined")
        self.assertEqual(meta["error"], "initial_hash_mismatch")
        self.assertEqual(raw, self.raw_sent[0])

    def test_initial_database_owner_is_required_without_snapshot_conversation_hint(self):
        self.snapshot.pop("conversation_id")
        service = self.service()
        run = service.start("TEST-conversation", {"model": "TEST-model", "question": "Synthetic FGI question",
            "time_limit_seconds": None, "max_calls": 15, "expert_ids": [FGI_EXPERT],
            "expert_inputs": {FGI_EXPERT: {"typed_contract": FGI_CONTRACT}}})
        with self.fixture.connect() as db:
            db.execute("UPDATE orchestration_initials SET item_id='OTHER-conversation'")
        service.run(run["run_id"])
        result = service.result("TEST-conversation", run["run_id"])
        task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
        self.assertEqual(task["error"], "fgi_source_or_delivery_mismatch")
        self.assertFalse(self.raw_sent)

    def test_actual_speaker_unknown_missing_empty_and_type_spoofs_stop_before_model(self):
        original = copy.deepcopy(self.snapshot)
        for value in ("UNKNOWN", " unknown ", "", " \r\n", None, True, False, 1, [], {}, "x" * 81):
            with self.subTest(speaker=value):
                self.snapshot = copy.deepcopy(original)
                self.snapshot["analysis"]["segments"][1]["speaker"] = value
                self.snapshot["input_hash"] = fingerprint({"speaker_negative": value})
                before = len(self.raw_sent)
                _, _, result = self.drive()
                task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
                self.assertEqual(task["error"], "expert_not_applicable", task)
                self.assertEqual(len(self.raw_sent), before)
                self.assertFalse(any("expert_report" in row["raw"] for row in result["raw_results"]))
        self.snapshot = copy.deepcopy(original)
        self.snapshot["analysis"]["segments"][1].pop("speaker")
        self.snapshot["input_hash"] = fingerprint({"speaker_negative": "missing"})
        _, _, result = self.drive()
        task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
        self.assertEqual(task["error"], "expert_not_applicable")

    def test_actual_single_speaker_and_nonparticipant_or_mixed_roles_stop(self):
        original = copy.deepcopy(self.snapshot)
        cases = [
            ("single", lambda rows: [row.update(speaker="TEST-A") for row in rows]),
            ("normalized_single", lambda rows: [row.update(speaker=" TEST-A " if i % 2 else "TEST-A") for i, row in enumerate(rows)]),
            ("one_participant_and_moderator", lambda rows: [row.update(role="moderator") for row in rows if row["speaker"] == "TEST-B"]),
            ("one_participant_and_observer", lambda rows: [row.update(role="observer") for row in rows if row["speaker"] == "TEST-B"]),
            ("mixed_role", lambda rows: rows[1].update(role="moderator")),
            ("unknown_role", lambda rows: rows[1].update(role="unknown")),
            ("role_type", lambda rows: rows[1].update(role=True)),
        ]
        for name, mutate in cases:
            with self.subTest(case=name):
                self.snapshot = copy.deepcopy(original); mutate(self.snapshot["analysis"]["segments"])
                self.snapshot["input_hash"] = fingerprint({"actual_speaker_negative": name})
                before = len(self.raw_sent)
                _, _, result = self.drive()
                task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
                self.assertEqual(task["error"], "expert_not_applicable", task)
                self.assertEqual(len(self.raw_sent), before)

    def test_actual_two_participants_and_moderator_preserve_draft_and_snapshot(self):
        for row in self.snapshot["analysis"]["segments"]:
            row["role"] = "participant"
        self.snapshot["analysis"]["segments"].append({"id": "TEST-u5", "speaker": "TEST-M", "role": "moderator", "text": "Synthetic closing question."})
        self.snapshot["analysis"]["automatic"]["overview"].update(segment_count=5, included_segment_count=5, speaker_count=3)
        before = copy.deepcopy(self.snapshot)
        self.test_handler_store_fresh_preserves_raw_and_manual_records()
        self.assertEqual(self.snapshot, before)

    def test_actual_speaker_validation_cannot_be_bypassed_at_report_acceptance(self):
        self.accepted()
        for value in ("UNKNOWN", None, True):
            analysis = copy.deepcopy(self.snapshot["analysis"])
            analysis["segments"][1]["speaker"] = value
            with self.subTest(value=value), self.assertRaises(AnalysisContractError) as caught:
                self.validate(analysis=analysis)
            self.assertEqual(caught.exception.code, "expert_not_applicable")

    def test_missing_wrong_store_other_conversation_and_partial_scope_stop(self):
        other = SyntheticStore(handler=True); self.addCleanup(other.close)
        for options, code in [({"missing_store": True}, "typed_source_missing"),
                              ({"store": other.store}, "typed_store_mismatch"),
                              ({"selected": True}, "fgi_dataset_scope_required")]:
            with self.subTest(options=options):
                _, _, result = self.drive(self.service(**options))
                task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
                self.assertEqual(task["error"], code, task)
        self.snapshot["conversation_id"] = "another-conversation"
        self.snapshot["input_hash"] = fingerprint({"negative": "other-conversation"})
        _, _, result = self.drive()
        task = next(t for t in result["run"]["tasks"] if t["role"] == "interpretation")
        self.assertEqual(task["error"], "fgi_source_or_delivery_mismatch")

    def test_pins_paths_versions_and_default_legacy_profile(self):
        typed_config = {"expert_ids": [FGI_EXPERT], "expert_inputs": {FGI_EXPERT: {"typed_contract": FGI_CONTRACT}}}
        profile = self.registry.freeze(typed_config)["profiles"][FGI_EXPERT]
        self.assertIn(FGI_CONTRACT, report_schema(profile, ["TEST"])["properties"])
        for suffix in ("agent-contract", "skill-hook-binding"):
            nid = "expert-focus-group-interaction-" + suffix
            spec = SKILL_NOTE_REFS[nid]
            for key, value in (("raw_sha256", "0" * 64), ("path", "../outside.md"),
                               ("version", {"schema_version": True}), ("range_hashes", {spec["sections"][0]: fingerprint("stale")})):
                with self.subTest(note=nid, key=key), patch.dict(SKILL_NOTE_REFS, {nid: {**spec, key: value}}):
                    with self.assertRaises(AnalysisContractError): self.registry.freeze(typed_config)
            target = self.catalog.local_root / spec["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.catalog.root / spec["path"]).read_bytes() + b"\nchanged\n")
            with self.assertRaises(AnalysisContractError): self.registry.freeze(typed_config)
            target.unlink()
        legacy = self.registry.freeze({"expert_ids": [FGI_EXPERT]})
        self.assertNotIn(FGI_CONTRACT, report_schema(legacy["profiles"][FGI_EXPERT], ["TEST"])["properties"])
        source = subprocess.check_output(["git", "show", BASE + ":src/gurumoji/services/expert_agents.py"], cwd=ROOT)
        previous = types.ModuleType("gurumoji.services._fgi_base_reader"); previous.__package__ = "gurumoji.services"
        exec(compile(source, "<fixed public base reader>", "exec"), previous.__dict__)
        original_note = self.catalog._note
        # The public base has no FGI07. Preserve that exact pre-addition catalog view.
        def base_note(path):
            return None if str(path).endswith("focus-group-interaction/07-Agent-Contract.md") else original_note(path)
        with patch.object(self.catalog, "_note", side_effect=base_note):
            baseline = previous.ExpertAgentRegistry(self.catalog).freeze({"expert_ids": [FGI_EXPERT]})
        self.assertEqual(legacy, baseline)
        with self.assertRaises(AnalysisContractError):
            self.registry.freeze({"expert_ids": [FGI_EXPERT], "expert_inputs": {FGI_EXPERT: {"typed_contract": "wrong"}}})


if __name__ == "__main__": unittest.main()
