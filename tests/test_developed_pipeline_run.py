"""Synthetic end-to-end Core pipeline runs; temporary SQLite, scripted agent, no provider."""
import copy
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.core_pipeline_service import AnalysisOrchestrationService, validate_orchestration_payload
from gurumoji.services import analysis_state, pipeline_context, pipeline_run

def utterances(count):
    return [{"id": f"u{i:03d}", "speaker": "A" if i % 2 else "B",
             "text": ("辛いのが好き" if i % 3 else "辛さは苦手で値段を見る") + "。" * (i % 7)} for i in range(count)]

class PipelineRunTests(unittest.TestCase):
    def setUp(self):
        chunk_size = patch.object(pipeline_run, "MAP_BODY_CHARS", 600)
        chunk_size.start()
        self.addCleanup(chunk_size.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "runtime.sqlite"
        self.item = {"id": "conversation", "revision": "input-v1"}
        self.snapshot = {"input_hash": "input-v1", "source_revision": 1, "analysis_revision": 1,
                         "analysis": {"segments": utterances(90)}}
        self.calls = []
        self.core_script = []
        self.bad_extract_once = False
        self.verify_unclear = False
        self.verify_invalid = False
        self.service = AnalysisOrchestrationService(
            connect=self.connect, find_item=lambda item: self.item if item == self.item["id"] else None,
            snapshot_builder=lambda item: copy.deepcopy(self.snapshot), source_fingerprint=lambda item: item["revision"],
            agent_runner=self.agent, method_runner=lambda *a: None, schedule=False)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def start(self, **extra):
        payload = {"model": "synthetic-model", "stop_mode": "auto", "max_iterations": None,
                   "time_limit_seconds": None, "concurrency": 1, **extra}
        return self.service.start("conversation", payload)

    def agent(self, role, request, options, check, usage):
        self.calls.append((role, request["role"], copy.deepcopy(request)))
        self.assertLessEqual(request["planned_characters"], pipeline_context.LIMITS[request["role"]])
        packet = request["packet"]
        if request["role"] == "extract":
            ids = [row[0] for row in packet["utterances"]["rows"]]
            if self.bad_extract_once and packet["chunk"]["index"] == 1:
                self.bad_extract_once = False
                ids = ["u999"]
            return {"chunk_id": packet["chunk"]["chunk_id"], "uncovered_notes": "", "observations": [
                {"evidence_ids": ids[:2], "statement": "辛さを好む発言", "kind": "pattern", **self.heading(packet, "辛さの好み")},
                {"evidence_ids": ids[-1:], "statement": "値段を気にする例外", "kind": "exception",
                 **self.heading(packet, "辛さの好み")}]}
        if request["role"] == "verify":
            if self.verify_invalid:  # a verification that skips every utterance breaks the schema
                return {"claim_id": packet["claim"]["claim_id"], "judgements": {}}
            rows = packet["utterances"]["rows"]
            if self.verify_unclear:  # the evidence mostly does not say what the claim says
                judgements = {row[0]: {"judgement": "unclear", "note": "別の内容"} for row in rows}
                judgements[rows[0][0]] = {"judgement": "supports", "note": "好みを述べる"}
            else:
                judgements = {row[0]: {"judgement": "supports", "note": "好みを述べる"} for row in rows}
            if len(rows) > 1:
                judgements[rows[-1][0]] = {"judgement": "contradicts", "note": "苦手と述べる"}
            return {"claim_id": packet["claim"]["claim_id"], "judgements": judgements}
        if request["role"] == "critic":
            return {"claim_id": packet["claim"]["claim_id"], "no_issue_reason": "",
                    "issues": [{"text": "値段を重視する層の扱いが不明", "refs": []}]}
        step = self.core_script.pop(0)
        return step(packet)

    @staticmethod
    def heading(packet, name):
        """Reuse the heading when it was offered, otherwise name it: the two fields are exclusive."""
        if name in packet.get("known_themes", []):
            return {"reuse_theme": name, "new_theme": ""}
        return {"reuse_theme": "", "new_theme": name}

    def drive(self, run):
        self.service.run(run["run_id"])
        return self.service.status("conversation", run["run_id"])

    def events(self, run):
        db = self.connect()
        try:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT payload_json FROM orchestration_events WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        finally:
            db.close()

    def state(self, run):
        db = self.connect()
        try:
            return analysis_state.load_state(db, run["run_id"])
        finally:
            db.close()

    @staticmethod
    def core(state_ops=(), action=None, summary="整理"):
        return {"summary": summary, "state_ops": list(state_ops), "action": action or {"op": "none"}, "reason": "根拠に沿って進める"}

    def test_full_run_reads_everything_reviews_and_completes(self):
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好みが選択を分ける"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core([{"op": "claim_status", "claim_id": p["state"]["questions"][0]["claim_id"],
                                  "status": "contested", "reason": "批判を限界として残す"},
                                 {"op": "question_closed", "question_id": p["state"]["questions"][0]["question_id"],
                                  "resolution": "accepted_limit",
                                  "reason": "例外として主張の反例に残した"}],
                                action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
        ]
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("completed", "question_satisfied"))
        state = self.state(run)
        plan = run["pipeline"]["plan"]
        self.assertEqual(set(state["sources"].values()) & {c["chunk_id"] for c in plan["chunks"]},
                         {c["chunk_id"] for c in plan["chunks"]})
        self.assertEqual(plan["evidence_count"], 90)
        [(claim_id, claim_row)] = state["claims"].items()
        self.assertTrue(claim_row["counter"])  # the exception and the contradicting verification stay attached
        self.assertEqual(run["pipeline"]["critiqued"], {claim_id: pipeline_run._claim_hash(claim_row)})
        closed = [q for q in state["questions"].values() if q["text"].startswith(pipeline_run.CRITIC_PREFIX)]
        self.assertEqual([q["status"] for q in closed], ["closed"])
        roles = [call[1] for call in self.calls]
        self.assertEqual(roles.count("extract"), len(plan["chunks"]))
        self.assertEqual(roles.count("core"), 5)
        self.assertEqual(roles.count("verify"), 1)
        self.assertEqual(roles.count("critic"), 1)
        core_sizes = [call[2]["planned_characters"] for call in self.calls if call[1] == "core"]
        self.assertLess(max(core_sizes), pipeline_context.LIMITS["core"])

    def test_claim_merges_themes_and_later_chunks_see_known_headings(self):
        seen = []
        original = self.agent
        def spy(role, request, options, check, usage):
            if request["role"] == "extract":
                seen.append(request["packet"].get("known_themes"))
            return original(role, request, options, check, usage)
        self.service.agent_runner = spy
        def merge(p):
            themes = [row["theme"] for row in p["state"]["themes"]][:2]
            return self.core([{"op": "claim_from_themes", "themes": themes, "text": "二つの見出しをまとめた主張"}])
        self.core_script = [merge, lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})]
        run = self.drive(self.start())
        self.assertIsNone(seen[0])  # the first chunk has nothing to reuse
        self.assertTrue(all(isinstance(known, list) and known for known in seen[1:]))
        state = self.state(run)
        [claim] = state["claims"].values()
        self.assertEqual(claim["text"], "二つの見出しをまとめた主張")
        self.assertGreaterEqual(len(claim["support"]) + len(claim["counter"]), 2)

    def test_claimed_themes_are_not_offered_again(self):
        offers = []
        def first(p):
            theme = p["state"]["themes"][0]["theme"]
            return self.core([{"op": "claim_from_themes", "themes": [theme], "text": "最初の主張"}])
        def second(p):
            unclaimed = [row["theme"] for row in p["state"]["themes"] if row["unclaimed"] > 0]
            claimed = [row["theme"] for row in p["state"]["themes"] if row["unclaimed"] == 0]
            offers.append((unclaimed, claimed))
            # Choosing an already claimed heading is outside the offer and must stop the run.
            return self.core([{"op": "claim_from_themes", "themes": [claimed[0]], "text": "同じ見出しをもう一度"}])
        self.core_script = [first] + [second] * (1 + pipeline_run.MAX_REASK)
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "execution_failure"))
        self.assertEqual(len(self.state(run)["claims"]), 1)
        self.assertTrue(offers and offers[0][1])  # a claimed heading existed and was withheld from the offer

    def test_verification_counts_supports_and_adds_only_counter_evidence(self):
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"}),
        ]
        run = self.drive(self.start())
        state = self.state(run)
        [(claim_id, claim)] = state["claims"].items()
        before_support = len(claim["support"])
        self.assertEqual(claim["verification"]["digest"], analysis_state.claim_digest(claim))
        shown = claim["verification"]["supports"] + claim["verification"]["contradicts"] + claim["verification"]["unclear"]
        self.assertEqual(claim["verification"]["contradicts"], 1)
        self.assertGreater(shown, 1)  # every shown utterance has a judgement
        verified_rows = [o for o in state["observations"].values() if o.get("origin") == "verify"]
        self.assertEqual(len(verified_rows), 1)  # the contradiction only; the support was counted, not stored
        self.assertTrue(set(o["observation_id"] for o in verified_rows) <= set(claim["counter"]))
        self.assertGreaterEqual(before_support, 1)
        self.assertFalse([g for g in analysis_state.themes(state).values() if g["theme"].startswith("辛さの好み") and g["theme"] != "辛さの好み"])

    def test_stop_review_verifies_before_it_critiques(self):
        order = []
        original = self.agent
        def spy(role, request, options, check, usage):
            order.append(request["role"])
            return original(role, request, options, check, usage)
        self.service.agent_runner = spy
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core([{"op": "claim_status", "claim_id": p["state"]["questions"][0]["claim_id"],
                                  "status": "contested", "reason": "批判を限界として残す"},
                                 {"op": "question_closed", "question_id": p["state"]["questions"][0]["question_id"],
                                  "resolution": "accepted_limit",
                                  "reason": "例外として扱った"}],
                                action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
        ]
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("completed", "question_satisfied"))
        self.assertLess(order.index("verify"), order.index("critic"))
        state = self.state(run)
        [(claim_id, claim)] = state["claims"].items()
        self.assertEqual(run["pipeline"]["critiqued"][claim_id], analysis_state.claim_digest(claim))

    def test_core_sees_both_a_pattern_and_an_exception_example(self):
        seen = []
        def look(p):
            row = p["state"]["themes"][0]
            seen.append({kind for kind, _ in row["examples"]})
            return self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})
        self.core_script = [look]
        self.drive(self.start())
        self.assertEqual(seen, [{"pattern", "exception"}])

    def test_revised_claim_text_voids_its_verification_and_review(self):
        self.verify_unclear = True
        def claim(p):
            return self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}])
        def revise(p):
            row = p["state"]["claims"][0]
            self.assertIsNotNone(row["verification"])  # verified by the Handler during the stop review
            self.assertGreaterEqual(row["verification"]["contradicts"], 1)
            return self.core([{"op": "claim_revise", "claim_id": row["claim_id"], "text": "辛さの好みは選択を分けない"}])
        def verify_again(p):
            row = p["state"]["claims"][0]
            self.assertEqual(row["text"], "辛さの好みは選択を分けない")
            self.assertIsNone(row["verification"])  # the old verification was of the old wording
            return self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})
        self.core_script = [
            claim, lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            revise, verify_again]
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "human_review_required")
        self.assertEqual(run["error"], "")

    def test_core_cannot_order_verification_or_critique(self):
        def claim(p):
            return self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}])
        for action in ({"op": "verify_claim", "claim_id": "clm_x"}, {"op": "critique_claim", "claim_id": "clm_x"}):
            with self.subTest(action=action["op"]):
                self.setUp()
                self.core_script = [claim] + [lambda p, a=action: self.core(action=a)] * (1 + pipeline_run.MAX_REASK)
                run = self.drive(self.start())
                self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "execution_failure"))
                self.assertEqual([c[1] for c in self.calls].count("verify"), 0)

    def test_revision_is_offered_only_for_a_claim_its_verification_does_not_support(self):
        self.verify_unclear = True
        offered = []
        def watch(p):
            offered.append(p["state"]["claims"][0]["verification"])
            return self.core()
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            watch,
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core([{"op": "claim_revise", "claim_id": p["state"]["claims"][0]["claim_id"], "text": "別の本文"}],
                                action={"op": "propose_stop", "stop_reason": "human_review_required"}),
        ]
        run = self.drive(self.start())
        self.assertIsNone(offered[0])  # not verified yet: nothing to revise on
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "human_review_required"))
        [claim] = self.state(run)["claims"].values()
        self.assertEqual(claim["text"], "別の本文")

    def test_a_supported_claim_cannot_be_revised(self):
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
        ] + [lambda p: self.core([{"op": "claim_revise", "claim_id": p["state"]["claims"][0]["claim_id"], "text": "別の本文"}])] \
            * (1 + pipeline_run.MAX_REASK)
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "execution_failure"))
        [claim] = self.state(run)["claims"].values()
        self.assertEqual(claim["text"], "辛さの好み")

    def test_identical_claim_text_is_merged_not_duplicated(self):
        def second(p):
            themes = [row["theme"] for row in p["state"]["themes"]]
            return self.core([{"op": "claim_from_themes", "themes": themes[:1], "text": "辛さの好み"},
                              {"op": "claim_from_themes", "themes": themes[:2], "text": "辛さの好み"}])
        self.core_script = [second, lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})]
        run = self.drive(self.start())
        self.assertEqual(len(self.state(run)["claims"]), 1)

    def test_an_op_that_changes_nothing_does_not_count_as_progress(self):
        def claim(p):
            return self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}])
        def same_status(p):
            row = p["state"]["claims"][0]
            return self.core([{"op": "claim_status", "claim_id": row["claim_id"], "status": row["status"], "reason": "変えない"}])
        self.core_script = [claim] + [same_status] * 6
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "human_review_required"))
        # the claim decision is progress; only the unchanged ones count toward the idle limit
        self.assertEqual([c[1] for c in self.calls].count("core"), 1 + pipeline_run.IDLE_ROUNDS_LIMIT)

    def test_repeated_idle_decisions_stop_for_human_review(self):
        self.core_script = [lambda p: self.core()] * 6
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "human_review_required"))
        self.assertEqual([c[1] for c in self.calls].count("core"), pipeline_run.IDLE_ROUNDS_LIMIT)

    def test_rejected_chunk_is_offered_for_reread_and_stop_waits_for_coverage(self):
        self.bad_extract_once = True
        def reread(p):
            self.assertEqual(len(p["coverage"]["remaining_chunk_ids"]), 1)
            self.assertFalse(p["coverage"]["complete"])
            return self.core(action={"op": "reread_chunk", "chunk_id": p["coverage"]["remaining_chunk_ids"][0]})
        def done(p):
            self.assertTrue(p["coverage"]["complete"])
            return self.core(action={"op": "propose_stop", "stop_reason": "no_more_evidence"})
        self.core_script = [reread, lambda p: self.core(), done]
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("completed", "no_more_evidence"))

    def test_incomplete_coverage_never_completes(self):
        self.bad_extract_once = True
        self.core_script = [lambda p: self.core()] * 2 + [lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"})]
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "full_text_incomplete"))

    def test_unknown_reference_from_core_stops_without_state_change(self):
        self.core_script = [lambda p: self.core([{"op": "claim_from_themes", "themes": ["提示していない"], "text": "x"}])] \
            * (1 + pipeline_run.MAX_REASK)
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "execution_failure"))
        self.assertEqual(self.state(run)["claims"], {})
        self.assertEqual([c[1] for c in self.calls].count("core"), 1 + pipeline_run.MAX_REASK)  # bounded, then stop

    def test_a_rejected_core_answer_is_asked_again_with_the_reason(self):
        notices = []
        def invalid(p):
            notices.append(p.get("notice"))
            return self.core([{"op": "claim_from_themes", "themes": ["提示していない"], "text": "x"}])
        def corrected(p):
            notices.append(p.get("notice"))
            return self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}])
        self.core_script = [invalid, corrected, lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})]
        run = self.drive(self.start())
        self.assertIsNone(notices[0])
        self.assertIn("採用されませんでした", notices[1])  # the rejection and its code are told to Core
        self.assertRegex(notices[1], r"expert_format_mismatch|pipeline_")
        self.assertEqual(run["stop_reason"], "human_review_required")
        self.assertEqual(len(self.state(run)["claims"]), 1)
        self.assertEqual(run["pipeline"]["reask_count"], 0)  # reset by the adopted decision

    def test_core_is_told_to_close_open_critic_questions_itself(self):
        hints = []
        def watch(p):
            hints.append((p["progress"]["open_critic_questions"], p["progress"]["next_step"]))
            return self.core([{"op": "claim_status", "claim_id": p["state"]["questions"][0]["claim_id"],
                               "status": "contested", "reason": "批判を限界として残す"},
                              {"op": "question_closed", "question_id": p["state"]["questions"][0]["question_id"],
                               "resolution": "accepted_limit",
                               "reason": "限界として受け入れた"}], action={"op": "propose_stop", "stop_reason": "question_satisfied"})
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            watch,
        ]
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("completed", "question_satisfied"))
        self.assertEqual(hints[0][0], 1)
        self.assertIn("question_closed", hints[0][1])

    def test_new_claims_beyond_the_remaining_slots_are_rejected_and_asked_again(self):
        from unittest import mock
        def too_many(p):
            themes = [row["theme"] for row in p["state"]["themes"]]
            return self.core([{"op": "claim_from_themes", "themes": [themes[0]], "text": "主張一"},
                              {"op": "claim_from_themes", "themes": [themes[-1]], "text": "主張二"}])
        def within(p):
            return self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "主張一"}])
        self.core_script = [too_many, within, lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})]
        with mock.patch.object(pipeline_context, "MAX_LIVE_CLAIMS", 1):
            run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "human_review_required")
        self.assertEqual(len(self.state(run)["claims"]), 1)
        rejected = [e for e in self.events(run) if e["type"] == "core_response_rejected"]
        self.assertEqual([e["code"] for e in rejected], ["pipeline_claim_limit"])

    def test_resolution_mismatch_is_reasked_with_the_missing_condition(self):
        for resolution, required in (("revised", "本文または根拠"), ("accepted_limit", "contestedかrejected"),
                                     ("withdrawn", "空でない撤回理由")):
            with self.subTest(resolution=resolution):
                notices = []
                def invalid(p):
                    return self.core([{"op": "question_closed", "question_id": p["state"]["questions"][0]["question_id"],
                                       "resolution": resolution, "reason": ""}])
                def corrected(p):
                    notices.append(p["notice"])
                    q = p["state"]["questions"][0]
                    return self.core([{"op": "claim_status", "claim_id": q["claim_id"], "status": "contested", "reason": "限界"},
                                      {"op": "question_closed", "question_id": q["question_id"],
                                       "resolution": "accepted_limit", "reason": "限界を保持"}],
                                     action={"op": "propose_stop", "stop_reason": "question_satisfied"})
                self.core_script = [
                    lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
                    lambda p: self.core(),
                    lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
                    lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
                    invalid, corrected]
                run = self.drive(self.start())
                self.assertEqual(run["status"], "completed")
                self.assertIn("state_resolution_mismatch", notices[0])
                self.assertIn(required, notices[0])
                rejected = [e for e in self.events(run) if e["type"] == "core_response_rejected"]
                self.assertEqual([e["code"] for e in rejected], ["state_resolution_mismatch"])
                state = self.state(run)
                self.assertEqual(len(state["questions"]), 1)
                question = next(iter(state["questions"].values()))
                self.assertIn(question["claim_id"], state["claims"])
                self.assertEqual(question["resolution"], "accepted_limit")

    def test_resolution_mismatch_reask_limit_is_preserved(self):
        def invalid(p):
            return self.core([{"op": "question_closed", "question_id": p["state"]["questions"][0]["question_id"],
                               "resolution": "revised", "reason": "修正した"}])
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
        ] + [invalid] * (pipeline_run.MAX_REASK + 1)
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "execution_failure"))
        rejected = [e for e in self.events(run) if e["type"] == "core_response_rejected"]
        self.assertEqual(len(rejected), pipeline_run.MAX_REASK)
        self.assertEqual(next(iter(self.state(run)["questions"].values()))["status"], "open")

    def test_multiple_critic_questions_keep_the_target_and_distinct_opening_sequences(self):
        original = self.agent
        def critic_many(role, request, options, check, usage):
            if request["role"] == "critic":
                return {"claim_id": request["packet"]["claim"]["claim_id"], "no_issue_reason": "",
                        "issues": [{"text": f"根拠の問い{i}", "refs": []} for i in range(3)]}
            return original(role, request, options, check, usage)
        self.service.agent_runner = critic_many
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})]
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "human_review_required")
        state = self.state(run)
        claim_id = next(iter(state["claims"]))
        questions = list(state["questions"].values())
        self.assertEqual(len(questions), 3)
        seqs = [q["opened_at_event"] for q in questions]
        self.assertEqual(seqs, list(range(seqs[0], seqs[0] + 3)))
        for question in questions:
            self.assertEqual(question["claim_id"], claim_id)
            self.assertEqual(question["claim_digest"], analysis_state.claim_digest(state["claims"][claim_id]))

    def test_a_heading_named_twice_is_the_same_set(self):
        def twice(p):
            theme = p["state"]["themes"][0]["theme"]
            return self.core([{"op": "claim_from_themes", "themes": [theme, theme], "text": "辛さの好み"}])
        self.core_script = [twice, lambda p: self.core(action={"op": "propose_stop", "stop_reason": "human_review_required"})]
        run = self.drive(self.start())
        self.assertEqual(run["stop_reason"], "human_review_required")
        [claim] = self.state(run)["claims"].values()
        self.assertEqual(len(claim["support"]) + len(claim["counter"]),
                         len(set(claim["support"]) | set(claim["counter"])))  # no observation counted twice

    def test_a_rejected_review_result_stops_for_a_person_instead_of_looping(self):
        self.verify_invalid = True
        self.core_script = [
            lambda p: self.core([{"op": "claim_from_themes", "themes": [p["state"]["themes"][0]["theme"]], "text": "辛さの好み"}]),
            lambda p: self.core(),
            lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"}),
        ] + [lambda p: self.core(action={"op": "propose_stop", "stop_reason": "question_satisfied"})] * 5
        run = self.drive(self.start())
        self.assertEqual((run["status"], run["stop_reason"]), ("stopped", "human_review_required"))
        self.assertEqual([c[1] for c in self.calls].count("verify"), 1)  # the same input is not asked again

    def test_minimum_iterations_hold_an_early_stop(self):
        self.core_script = [lambda p: self.core(action={"op": "propose_stop", "stop_reason": "no_more_evidence"})] * 3
        run = self.drive(self.start())
        self.assertEqual(run["status"], "completed")
        self.assertEqual([c[1] for c in self.calls].count("core"), 3)

class CoreIntentionOrderTests(unittest.TestCase):
    def setUp(self):
        from test_developed_analysis_state import observations
        self.state = analysis_state.replay([observations("a", 1), observations("b", 1, theme="別の根拠")])
        ids = list(self.state["observations"])
        self.state = analysis_state.apply(self.state, {"op": "claim_added", "claim_id": "clm_1", "text": "主張", "support": ids[:1]})
        self.state = analysis_state.apply(self.state, analysis_state.question_event(
            self.state, "qst_1", "critic: 根拠は十分か", claim_id="clm_1"))
        self.close = {"op": "question_closed", "question_id": "qst_1", "resolution": "revised", "reason": "修正"}

    def test_revision_or_link_must_precede_closure_in_the_same_response(self):
        changes = [{"op": "claim_revise", "claim_id": "clm_1", "text": "限定した主張"},
                   {"op": "claim_from_themes", "themes": ["別の根拠"], "text": "主張"}]
        for change in changes:
            with self.subTest(change=change):
                events = pipeline_run._core_events(self.state, {"state_ops": [change, self.close]}, {"task_id": "task"})
                self.assertIn(events[0]["op"], ("claim_revised", "claim_linked"))
                following = self.state
                for event in events:
                    following = analysis_state.apply(following, event)
                self.assertEqual(following["questions"]["qst_1"]["status"], "closed")
                with self.assertRaises(AnalysisContractError) as caught:
                    pipeline_run._core_events(self.state, {"state_ops": [self.close, change]}, {"task_id": "task"})
                self.assertEqual(caught.exception.code, "state_resolution_mismatch")

    def test_noop_revision_does_not_satisfy_closure(self):
        with self.assertRaises(AnalysisContractError) as caught:
            pipeline_run._core_events(self.state, {"state_ops": [
                {"op": "claim_revise", "claim_id": "clm_1", "text": "主張"}, self.close]}, {"task_id": "task"})
        self.assertEqual(caught.exception.code, "state_resolution_mismatch")

    def test_general_questions_keep_null_and_targeted_questions_use_working_state(self):
        ops = [{"op": "claim_revise", "claim_id": "clm_1", "text": "変更後"},
               {"op": "question_added", "claim_id": "clm_1", "text": "対象の問い"},
               {"op": "question_added", "claim_id": None, "text": "一般の問い"}]
        events = pipeline_run._core_events(self.state, {"state_ops": ops}, {"task_id": "task"})
        following = self.state
        for event in events:
            following = analysis_state.apply(following, event)
        targeted = following["questions"][events[1]["question_id"]]
        self.assertEqual(targeted["claim_digest"], analysis_state.claim_digest(following["claims"]["clm_1"]))
        self.assertIsNone(events[2]["claim_id"])
        self.assertEqual(events[2]["opened_at_event"], following["event_count"])

    def test_schema_requires_resolution_and_respects_the_existing_budget(self):
        from gurumoji.services.expert_agents import validate_shape
        state = self.state
        for index in range(30):
            state = analysis_state.apply(state, analysis_state.question_event(
                state, f"qst_extra{index}", "根拠の問い" * 30, claim_id="clm_1"))
        coverage = {"chunk_count": 1, "accepted_chunk_count": 1, "evidence_count": 2,
                    "evidence_read_count": 2, "remaining_chunk_ids": [], "complete": True}
        request, offer = pipeline_context.fitted_core_request(state, coverage, experts=[],
            research_question="研究質問", instructions="分析", progress={"next_step": pipeline_run._next_step(state)})
        self.assertLessEqual(request["planned_characters"], pipeline_context.LIMITS["core"])
        self.assertLessEqual(len(request["packet"]["state"]["questions"]), 8)
        self.assertGreater(request["packet"]["state"]["omitted"]["questions"], 0)
        for key, value in (("resolution", None), ("resolution", "other"), ("op", "unsupported")):
            op = {**self.close, key: value}
            if value is None:
                del op[key]
            with self.subTest(op=op), self.assertRaises(AnalysisContractError):
                validate_shape(request["schema"], PipelineRunTests.core([op]))
        for claim_id in (None, "clm_1"):
            raw = PipelineRunTests.core([{"op": "question_added", "text": "問い", "claim_id": claim_id}])
            validate_shape(request["schema"], raw)
            pipeline_context.check_core(raw, offer)

class PipelinePayloadTests(unittest.TestCase):
    def test_pipeline_runs_without_fixed_caps_and_runner_can_limit_them(self):
        config = validate_orchestration_payload({"model": "m"})
        self.assertIsNone(config["max_calls"])
        self.assertEqual(config["adapter_version"], "core-pipeline-1")
        capped = validate_orchestration_payload({"model": "m",
                                                 "max_calls": 30, "max_tasks": 40})
        self.assertEqual((capped["max_calls"], capped["max_tasks"]), (30, 40))
        self.assertIsNone(validate_orchestration_payload({"model": "m", "max_calls": None})["max_calls"])

    def test_legacy_full_text_options_cannot_be_combined(self):
        with self.assertRaises(AnalysisContractError) as caught:
            validate_orchestration_payload({"model": "m",
                                            "context_index_limit": 10})
        self.assertEqual(caught.exception.code, "invalid_request")

if __name__ == "__main__":
    unittest.main()
