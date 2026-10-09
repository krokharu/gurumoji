"""Independent FGI acceptance against public Registry/Handler entry points.

Only temporary synthetic SQLite/Store data and an in-process agent stub are
used. These tests intentionally require the new opt-in contract; collection
does not turn an unavailable implementation into a skipped or passing test.
"""
import copy
import hashlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.analysis_store import AnalysisStore
from gurumoji.method_experts import ExpertCatalog, SKILL_CONTEXT_VERSION
from gurumoji.services.expert_agents import ExpertAgentRegistry, thematic_source_packet
from test_analysis_asset_bindings import SyntheticStore
import test_analysis_orchestration as protocol


ROOT = Path(__file__).resolve().parents[1]
EXPERT = "exp-focus-group-interaction"
CONTRACT = "focus_group_interaction_candidates_v1"


def utterance_ref(row):
    """Invent a response field from the supplied synthetic utterance bytes."""
    return {"evidence_id": row["evidence_id"], "utterance_id": row["utterance_id"],
            "utterance_hash": "sha256:" + hashlib.sha256(row["text"].encode("utf-8")).hexdigest()}


class FocusGroupInteractionIndependentTests(unittest.TestCase):
    def setUp(self):
        network = patch("socket.socket", side_effect=AssertionError("Independent synthetic QA must not use network"))
        network.start(); self.addCleanup(network.stop)
        self.fixture = SyntheticStore(handler=True)
        self.addCleanup(self.fixture.close)
        self.local = Path(self.fixture.temp.name) / "local"
        self.catalog = ExpertCatalog(root=ROOT / "docs/program-vault", local_root=self.local)
        self.registry = ExpertAgentRegistry(self.catalog)
        self.calls = []
        self.responses = []
        self.mutation = None
        self.typed = True
        self.snapshot = copy.deepcopy(self.fixture.snapshot)
        segments = [
            {"id": "QA-u1", "speaker": "QA-A", "text": "Could we meet earlier?"},
            {"id": "QA-u2", "speaker": "QA-B", "text": "Yes, earlier would help me."},
            {"id": "QA-u3", "speaker": "QA-A", "text": "I propose a morning meeting."},
            {"id": "QA-u4", "speaker": "QA-B", "text": "I disagree; afternoons work better."},
        ]
        segments[0]["annotation"] = {"interaction_links": [{"target_segment_id": "QA-u2",
            "relation": "response", "evidence_memo": "Existing synthetic manual record"}]}
        self.snapshot["analysis"] = {
            "segments": segments,
            "automatic": {"overview": {"included_segment_count": 4, "segment_count": 4,
                "speaker_count": 2, "participant_count": 2},
                "data_quality": {"unknown_speaker_segments": 0}},
            "manual": {"preparation": {"status": "confirmed", "order_verified": True,
                "unknown_speaker_turns": 0, "analysis_needs_review": False},
                "interaction_links": [{"source_segment_id": "QA-u1", "target_segment_id": "QA-u2",
                    "relation": "response", "status": "recorded"}]},
        }

    def service(self, *, store=True):
        service = AnalysisOrchestrationService(connect=self.fixture.connect,
            find_item=lambda _: {"id": "TEST-conversation", "revision_count": 1, "analysis_revision": 1},
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot),
            source_fingerprint=lambda _: self.snapshot["input_hash"],
            method_runner=lambda *_: self.fail("FGI draft must not schedule a method"),
            agent_runner=self.agent, expert_provider=self.registry.freeze,
            table_store=self.fixture.store if store else None, schedule=False)
        self.active_service = service
        return service

    def agent(self, role, context, *_):
        if role == "core":
            if context["budget"]["completed_core_iterations"] == 0:
                return protocol.core(intents=[protocol.intent("interpretation", expert_id=EXPERT)])
            return protocol.stop()
        if role == "critic":
            return protocol.critic(context)
        self.calls.append(copy.deepcopy(context))
        packet = context["expert_request"]
        profile = packet["knowledge"]
        raw = {"summary": "Synthetic FGI draft; interpretation remains pending", "claims": [],
            "analysis_requests": [], "label_patches": [], "expert_report": {
                "expert_id": EXPERT, "profile_hash": profile["profile_hash"],
                "knowledge_hash": profile["knowledge_hash"], "status": "draft",
                "outputs": {k: "Synthetic text-supported candidate; human review pending"
                            for k in profile["output_schema"]["properties"]},
                "evidence_ids": [r["evidence_id"] for r in context["raw_evidence"]],
                "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                "performed_step_ids": ["fgi-p3", "fgi-p5"], "missing_inputs": [],
                "limitations": "Only supplied utterance text examined; no human reading or semantic approval claimed."}}
        if self.typed:
            initial = self.active_service.result("TEST-conversation", context["task"]["run_id"])["initial"]
            source = thematic_source_packet(initial, library_id=self.fixture.store.library_id(),
                                            conversation_id="TEST-conversation")
            rows = source["evidence"]
            raw["expert_report"][CONTRACT] = {
                "version": CONTRACT, "source_ref": copy.deepcopy(source["source_ref"]),
                "scope": copy.deepcopy(source["scope"]),
                "producer": {**packet["expected_producer"], "step_ids": ["fgi-p3", "fgi-p5"]},
                "coverage": copy.deepcopy(packet["delivery_coverage"]),
                "human_status": "human_pending", "human_record_state": "not_entered", "human_records": [],
                "semantic_review": "undetermined", "eligible_as_confirmed_evidence": False,
                "candidates": [
                    {"candidate_id": "QA-reply", "step_id": "fgi-p3", "relation_kind": "question_answer",
                     "text": "A question and a response candidate.", "limitations": "Human interpretation pending.",
                     "evidence_refs": [utterance_ref(rows[0]), utterance_ref(rows[1])]},
                    {"candidate_id": "QA-dissent", "step_id": "fgi-p5", "relation_kind": "disagreement_candidate",
                     "text": "A proposal and a disagreement candidate.", "limitations": "Human interpretation pending.",
                     "evidence_refs": [utterance_ref(rows[2]), utterance_ref(rows[3])]},
                ]}
        if self.mutation:
            self.mutation(raw, context)
        self.responses.append(copy.deepcopy(raw))
        return raw

    def execute(self, *, store=True, **config):
        self.calls.clear()
        self.responses.clear()
        service = self.service(store=store)
        payload = {"model": "QA-stub-model", "question": "How do participants respond to proposals?",
            "time_limit_seconds": None, "max_calls": 15, "expert_ids": [EXPERT], **config}
        if self.typed:
            payload["expert_inputs"] = {EXPERT: {"typed_contract": CONTRACT}}
        run = service.start("TEST-conversation", payload)
        service.run(run["run_id"])
        return service, run, service.result("TEST-conversation", run["run_id"])

    @staticmethod
    def reports(result):
        return [r for r in result["raw_results"] if "expert_report" in r["raw"]]

    def assert_no_valid_draft(self, **config):
        # An unavailable opt-in is a test error, never a negative-case PASS.
        self.registry.freeze({"expert_ids": [EXPERT],
            "expert_inputs": {EXPERT: {"typed_contract": CONTRACT}}})
        service, run, result = self.execute(**config)
        if not self.responses:
            tasks = service.status("TEST-conversation", run["run_id"])["tasks"]
            self.assertTrue(any(t.get("error") in {"expert_not_applicable", "typed_source_missing",
                "typed_store_mismatch"} for t in tasks), tasks)
        self.assertFalse(any(r["validation_status"] == "valid" and
            r["raw"]["expert_report"]["status"] == "draft" for r in self.reports(result)), result)

    def test_handler_raw_report_persists_fresh_without_manual_adoption(self):
        before = copy.deepcopy(self.snapshot)
        service, run, result = self.execute()
        final = service.status("TEST-conversation", run["run_id"])
        self.assertEqual(final["status"], "completed", final)
        reports = self.reports(result)
        self.assertEqual(len(reports), 1, result)
        self.assertEqual(reports[0]["validation_status"], "valid", reports)
        self.assertEqual(reports[0]["raw"], self.responses[0])
        self.assertEqual(self.service().result("TEST-conversation", run["run_id"]), result)
        self.assertEqual(self.snapshot, before)
        self.assertEqual(result["initial"]["snapshot"]["analysis"]["manual"], before["analysis"]["manual"])
        typed = reports[0]["raw"]["expert_report"][CONTRACT]
        self.assertEqual(typed["source_ref"]["version"], before["input_hash"])
        self.assertEqual(typed["source_ref"]["content_hash"], fingerprint(result["initial"]["snapshot"]))
        self.assertEqual(typed["scope"]["conversation_ids"], ["TEST-conversation"])
        self.assertEqual(typed["scope"]["member_ids"], ["QA-u1", "QA-u2", "QA-u3", "QA-u4"])
        self.assertEqual(typed["scope"]["context_ids"], [])
        self.assertIs(typed["coverage"]["complete"], True)
        self.assertEqual(typed["coverage"]["undelivered_utterance_ids"], [])
        self.assertEqual(typed["producer"]["actor_id"], reports[0]["task_id"])
        self.assertEqual(typed["producer"]["revision"], "unverified")
        self.assertEqual(typed["human_status"], "human_pending")
        self.assertEqual(typed["human_records"], [])
        self.assertIs(typed["eligible_as_confirmed_evidence"], False)

    def test_legacy_default_report_remains_readable(self):
        self.typed = False
        _service, _run, result = self.execute()
        reports = self.reports(result)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["validation_status"], "valid", reports)
        self.assertNotIn(CONTRACT, reports[0]["raw"]["expert_report"])

    def test_real_store_save_fresh_package_preserves_raw_report_and_manual_links(self):
        from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
        before = copy.deepcopy(self.snapshot)
        service, run, exported = self.execute(publication_targets=[])
        reports = self.reports(exported)
        self.assertEqual(len(reports), 1, exported)
        self.assertEqual(reports[0]["validation_status"], "valid", reports)
        self.assertEqual(reports[0]["raw"], self.responses[0])
        publisher = AnalysisOrchestrationPublicationService(connect=self.fixture.connect,
            store_factory=lambda: self.fixture.store,
            source_guard=lambda _db, item_id, _expected: {"id": item_id},
            export_locked=service.result_locked)
        # Even a mistaken publication call must fail before any Vault write.
        with patch.object(self.fixture.store, "publish", side_effect=AssertionError("No targets authorized")), \
                patch.object(AnalysisStore, "source_notes", side_effect=AssertionError("No researcher Vault authorized")):
            publication = publisher.finalize("TEST-conversation", run["run_id"])
        self.assertEqual(publication["save_status"], "saved", publication)
        self.assertEqual(publication["publication_status"], "not_selected", publication)
        fresh = AnalysisStore(self.fixture.path, self.fixture.connect)
        saved_snapshot, saved_result, _manifest, _content = fresh.verified_package(publication["result_run_id"])
        self.assertEqual(saved_result["parameters"]["publication_targets"], [])
        self.assertEqual(saved_result["orchestration"]["raw_results"], exported["raw_results"])
        self.assertEqual(saved_result["orchestration"]["initial"], exported["initial"])
        self.assertEqual(self.reports(saved_result["orchestration"])[0]["raw"], self.responses[0])
        self.assertEqual(saved_snapshot["segments"], before["analysis"]["segments"])
        self.assertEqual(self.snapshot, before)
        if self.typed:
            self.assertEqual(self.reports(saved_result["orchestration"])[0]["raw"]["expert_report"][CONTRACT],
                             self.responses[0]["expert_report"][CONTRACT])

    def test_single_duplicate_reverse_unknown_and_mismapped_evidence_reject(self):
        def single(t): t["candidates"][0]["evidence_refs"].pop()
        def duplicate(t): t["candidates"][0]["evidence_refs"][1] = copy.deepcopy(t["candidates"][0]["evidence_refs"][0])
        def reverse(t): t["candidates"][0]["evidence_refs"].reverse()
        def unknown(t): t["candidates"][0]["evidence_refs"][1]["utterance_id"] = "QA-absent"
        def mismapped(t): t["candidates"][0]["evidence_refs"][1]["evidence_id"] = t["candidates"][1]["evidence_refs"][0]["evidence_id"]
        for mutate in (single, duplicate, reverse, unknown, mismapped):
            with self.subTest(mutation=mutate.__name__):
                self.mutation = lambda raw, _ctx, m=mutate: m(raw["expert_report"][CONTRACT])
                self.assert_no_valid_draft()

    def test_source_version_content_and_utterance_hash_tampering_reject(self):
        for target in ("version", "content_hash", "utterance_hash"):
            with self.subTest(target=target):
                def mutate(raw, _ctx):
                    typed = raw["expert_report"][CONTRACT]
                    if target == "utterance_hash":
                        typed["candidates"][0]["evidence_refs"][0][target] = "sha256:" + "0" * 64
                    else:
                        typed["source_ref"][target] = "old-input" if target == "version" else "sha256:" + "0" * 64
                        typed["scope"]["input_refs"] = [copy.deepcopy(typed["source_ref"])]
                        scope = typed["scope"]; scope.pop("manifest_hash"); scope["manifest_hash"] = fingerprint(scope)
                self.mutation = mutate
                self.assert_no_valid_draft()

    def test_rehashed_partial_other_conversation_and_scope_reject(self):
        for field, value in (("member_ids", ["QA-u1", "QA-u2"]),
                             ("conversation_ids", ["QA-other"]), ("mode", "section")):
            with self.subTest(field=field):
                def mutate(raw, _ctx):
                    scope = raw["expert_report"][CONTRACT]["scope"]
                    scope[field] = value; scope.pop("manifest_hash"); scope["manifest_hash"] = fingerprint(scope)
                self.mutation = mutate
                self.assert_no_valid_draft()

    def test_actor_human_record_and_researcher_step_spoofing_reject(self):
        def actor(t): t["producer"]["actor_id"] = "QA-forged-task"
        def kind(t): t["producer"]["kind"] = "researcher"
        def step(t): t["candidates"][0]["step_id"] = "fgi-p4"
        def confirmed(t): t["human_status"] = "confirmed"
        def record(t): t["human_records"] = [{"actor_id": "QA-fake-consent"}]
        def semantic(t): t["semantic_review"] = "approved"
        def eligible(t): t["eligible_as_confirmed_evidence"] = True
        for mutate in (actor, kind, step, confirmed, record, semantic, eligible):
            with self.subTest(mutation=mutate.__name__):
                self.mutation = lambda raw, _ctx, m=mutate: m(raw["expert_report"][CONTRACT])
                self.assert_no_valid_draft()

    def test_excluded_evidence_cannot_be_positive_support(self):
        self.snapshot["analysis"]["segments"].append({"id": "QA-excluded", "speaker": "QA-B",
            "text": "Excluded synthetic context.", "excluded": True})
        self.snapshot["analysis"]["automatic"]["overview"]["segment_count"] = 5
        def mutate(raw, context):
            initial = self.active_service.result("TEST-conversation", context["task"]["run_id"])["initial"]
            excluded = next(r for r in initial["snapshot"]["evidence"] if r["excluded"])
            raw["expert_report"][CONTRACT]["candidates"][0]["evidence_refs"][1] = utterance_ref(excluded)
        self.mutation = mutate
        self.assert_no_valid_draft()

    def test_partial_delivery_does_not_certify_full_coverage(self):
        self.assert_no_valid_draft(context_evidence_limit=2)

    def test_truncated_text_does_not_certify_full_coverage(self):
        self.snapshot["analysis"]["segments"][0]["text"] = "Synthetic repeated text. " * 600
        self.assert_no_valid_draft(context_text_limit=1000)

    def test_unconfirmed_speakers_order_and_min_participants_block(self):
        for field, value in (("order_verified", False), ("unknown_speaker_turns", 1)):
            with self.subTest(field=field):
                self.snapshot["analysis"]["manual"]["preparation"][field] = value
                self.assert_no_valid_draft()
                self.snapshot["analysis"]["manual"]["preparation"][field] = True if field == "order_verified" else 0
        self.snapshot["analysis"]["automatic"]["overview"]["participant_count"] = 1
        self.assert_no_valid_draft()

    def test_closed_relation_enum_extra_keys_and_boolean_types_reject(self):
        def relation(t): t["candidates"][0]["relation_kind"] = "facial_expression_agreement"
        def extra(t): t["adopt_manual_links"] = True
        def number(t): t["eligible_as_confirmed_evidence"] = 0
        def duplicate_id(t): t["candidates"][1]["candidate_id"] = t["candidates"][0]["candidate_id"]
        for mutate in (relation, extra, number, duplicate_id):
            with self.subTest(mutation=mutate.__name__):
                self.mutation = lambda raw, _ctx, m=mutate: m(raw["expert_report"][CONTRACT])
                self.assert_no_valid_draft()

    def test_missing_store_does_not_create_valid_draft(self):
        self.assert_no_valid_draft(store=False)

    def test_unknown_actual_speaker_cannot_hide_behind_confirmed_counts(self):
        self.snapshot["analysis"]["segments"][1]["speaker"] = "UNKNOWN"
        self.assert_no_valid_draft()

    def test_single_actual_speaker_cannot_hide_behind_two_participant_count(self):
        for row in self.snapshot["analysis"]["segments"]:
            row["speaker"] = "QA-A"
        self.assert_no_valid_draft()

    def test_same_input_hash_different_text_rejects_old_snapshot_reference(self):
        _service, _run, first = self.execute()
        first_report = self.reports(first)[0]
        self.assertEqual(first_report["validation_status"], "valid", first_report)
        old = copy.deepcopy(first_report["raw"]["expert_report"][CONTRACT])
        old_input_hash = self.snapshot["input_hash"]
        self.snapshot["analysis"]["segments"][1]["text"] = "Changed synthetic reply with unchanged declared input hash."
        # A new isolated library forces a new immutable capture. Reusing the
        # first library would intentionally reuse its initial for this version.
        self.fixture = SyntheticStore(handler=True)
        self.addCleanup(self.fixture.close)
        def mutate(raw, _ctx):
            typed = raw["expert_report"][CONTRACT]
            self.assertEqual(typed["source_ref"]["version"], old["source_ref"]["version"])
            self.assertNotEqual(typed["source_ref"]["content_hash"], old["source_ref"]["content_hash"])
            typed["source_ref"]["content_hash"] = old["source_ref"]["content_hash"]
            scope = typed["scope"]
            scope["input_refs"] = [copy.deepcopy(typed["source_ref"])]
            scope.pop("manifest_hash"); scope["manifest_hash"] = fingerprint(scope)
        self.mutation = mutate
        self.assertEqual(self.snapshot["input_hash"], old_input_hash)
        self.assert_no_valid_draft()

    def test_needs_input_keeps_nullable_candidates_and_does_not_adopt(self):
        def mutate(raw, _ctx):
            report = raw["expert_report"]
            report.update(status="needs_input", missing_inputs=["Researcher confirmation pending"])
            report[CONTRACT] = None
        self.mutation = mutate
        _service, _run, result = self.execute()
        reports = self.reports(result)
        self.assertEqual(len(reports), 1, result)
        self.assertEqual(reports[0]["validation_status"], "valid", reports)
        self.assertIsNone(reports[0]["raw"]["expert_report"][CONTRACT])

    def test_empty_examined_none_remains_unconfirmed(self):
        def mutate(raw, _ctx):
            report = raw["expert_report"]
            report[CONTRACT]["candidates"] = []
            report["limitations"] = "Supplied text examined; no candidate found; human review and meaning remain unverified."
        self.mutation = mutate
        _service, _run, result = self.execute()
        reports = self.reports(result)
        self.assertEqual(len(reports), 1, result)
        self.assertEqual(reports[0]["validation_status"], "valid", reports)
        typed = reports[0]["raw"]["expert_report"][CONTRACT]
        self.assertEqual(typed["candidates"], [])
        self.assertEqual(typed["semantic_review"], "undetermined")
        self.assertIs(typed["eligible_as_confirmed_evidence"], False)

    def test_fixed_skill_note_mismatch_is_not_silently_repaired(self):
        relative = Path("50-Analysis-Methods/10-Experts/focus-group-interaction/07-Agent-Contract.md")
        self.assertTrue((ROOT / "docs/program-vault" / relative).is_file())
        target = self.local / relative; target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / "docs/program-vault" / relative).read_bytes()
        for explicit in (False, True):
            with self.subTest(explicit_skill_context=explicit):
                target.write_bytes(raw + b"\nQA changed pin\n")
                config = {"expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"typed_contract": CONTRACT}}}
                if explicit:
                    config["skill_context"] = {"version": SKILL_CONTEXT_VERSION, "workflow": False}
                with self.assertRaises(AnalysisContractError) as caught:
                    self.registry.freeze(config)
                self.assertIn("hash", caught.exception.code)

    def test_same_size_same_mtime_pin_change_without_skill_selection_rejects(self):
        relative = Path("50-Analysis-Methods/10-Experts/focus-group-interaction/07-Agent-Contract.md")
        raw = (ROOT / "docs/program-vault" / relative).read_bytes()
        self.assertIn(b"human_pending", raw, "Contract must state the human-pending boundary")
        target = self.local / relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        config = {"expert_ids": [EXPERT], "expert_inputs": {EXPERT: {"typed_contract": CONTRACT}}}
        frozen = self.registry.freeze(config)
        stamp = target.stat()
        changed = raw.replace(b"human_pending", b"human_pendinG", 1)
        self.assertEqual(len(changed), len(raw)); self.assertNotEqual(changed, raw)
        target.write_bytes(changed)
        os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(target.stat().st_size, stamp.st_size)
        self.assertEqual(target.stat().st_mtime_ns, stamp.st_mtime_ns)
        with self.assertRaises(AnalysisContractError) as caught:
            self.registry.freeze(config)
        self.assertIn("hash", caught.exception.code)
        self.assertEqual(frozen["profiles"][EXPERT]["typed_contract"], CONTRACT)


if __name__ == "__main__":
    unittest.main()
