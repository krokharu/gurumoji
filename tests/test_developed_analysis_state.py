"""Synthetic append-only analysis state and bounded Core view; temporary SQLite only."""
import json
import sqlite3
import unittest
from pathlib import Path

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import analysis_state as state_module

def observations(chunk, count, *, theme="辛さ", kind="pattern"):
    accepted = {"observations": [{"evidence_ids": [f"ev{chunk}{i}"], "statement": f"観察{chunk}-{i}",
                                  "kind": kind, "theme": theme} for i in range(count)]}
    return state_module.observations_event(f"chk_{chunk}", f"res_{chunk}", accepted)

class StateTests(unittest.TestCase):
    def test_claims_link_and_change_status(self):
        state = state_module.replay([observations("a", 3), observations("b", 1, kind="exception")])
        ids = list(state["observations"])
        state = state_module.apply(state, {"op": "claim_added", "claim_id": "clm_1", "text": "辛さが選択を決める",
                                           "support": ids[:2], "counter": []})
        state = state_module.apply(state, {"op": "claim_linked", "claim_id": "clm_1", "counter": [ids[3]]})
        state = state_module.apply(state, {"op": "claim_status", "claim_id": "clm_1", "status": "contested",
                                           "reason": "例外の発話がある"})
        self.assertEqual(state["claims"]["clm_1"]["counter"], [ids[3]])
        self.assertEqual(state["claims"]["clm_1"]["status"], "contested")

    def test_invalid_events_leave_state_unchanged(self):
        state = state_module.replay([observations("a", 2)])
        ids = list(state["observations"])
        before = json.dumps(state, sort_keys=True)
        bad = [
            {"op": "claim_added", "claim_id": "clm_1", "text": "x", "support": ["obs_unknown"]},
            {"op": "claim_added", "claim_id": "clm_1", "text": "x", "support": ids, "counter": ids[:1]},
            {"op": "claim_added", "claim_id": "clm_1", "text": "x", "support": []},
            {"op": "claim_status", "claim_id": "clm_missing", "status": "open", "reason": "r"},
            {"op": "question_closed", "question_id": "qst_missing", "reason": "r"},
            {"op": "unknown"},
            observations("a", 1),  # the same chunk twice
        ]
        for event in bad:
            with self.subTest(event=event), self.assertRaises(AnalysisContractError):
                state_module.apply(state, event)
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_empty_map_result_still_occupies_its_chunk(self):
        state = state_module.replay([observations("a", 0)])
        with self.assertRaises(AnalysisContractError):
            state_module.apply(state, observations("a", 0))

    def test_view_size_does_not_grow_with_observations(self):
        def size(chunks):
            events = [observations(f"{c:03d}", 8, theme=f"テーマ{c % 40}") for c in range(chunks)]
            return len(json.dumps(state_module.view(state_module.replay(events)), ensure_ascii=False))
        small, large = size(20), size(400)
        self.assertLess(abs(large - small), 200)  # only counts and IDs differ

    def test_examples_include_the_majority_and_the_minority(self):
        events = [observations("a", 5), observations("b", 1, kind="exception")]
        row = next(r for r in state_module.view(state_module.replay(events), max_examples=1)["themes"] if r["theme"] == "辛さ")
        self.assertEqual([kind for kind, _ in row["examples"]], ["pattern", "exception"])

    def test_claim_text_can_be_revised_and_changes_its_digest(self):
        state = state_module.replay([observations("a", 2)])
        ids = list(state["observations"])
        state = state_module.apply(state, {"op": "claim_added", "claim_id": "clm_1", "text": "旧", "support": ids, "counter": []})
        before = state_module.claim_digest(state["claims"]["clm_1"])
        state = state_module.apply(state, {"op": "claim_revised", "claim_id": "clm_1", "text": "新"})
        self.assertEqual(state["claims"]["clm_1"]["text"], "新")
        self.assertNotEqual(state_module.claim_digest(state["claims"]["clm_1"]), before)
        with self.assertRaises(AnalysisContractError):
            state_module.apply(state, {"op": "claim_revised", "claim_id": "clm_none", "text": "x"})

    def test_view_keeps_exceptions_and_reports_omissions(self):
        events = [observations("a", 5)] + [observations(f"x{i}", 1, theme=f"別{i}") for i in range(20)]
        events.append(observations("z", 1, theme="辛さ", kind="exception"))
        view = state_module.view(state_module.replay(events), max_themes=3)
        spicy = next(row for row in view["themes"] if row["theme"] == "辛さ")
        self.assertIn("exception", [kind for kind, _ in spicy["examples"]])  # kept beside the majority
        self.assertEqual(view["omitted"]["themes"], view["totals"]["themes"] - 3)
        self.assertFalse(view["omitted"]["omitted_is_read"])

class VerificationTests(unittest.TestCase):
    def claim_state(self):
        state = state_module.replay([observations("a", 3), observations("b", 1, kind="exception")])
        ids = list(state["observations"])
        return state_module.apply(state, {"op": "claim_added", "claim_id": "clm_1", "text": "主張",
                                          "support": ids[:2], "counter": []}), ids

    def test_verification_is_bound_to_the_claim_content(self):
        state, ids = self.claim_state()
        digest = state_module.claim_digest(state["claims"]["clm_1"])
        state = state_module.apply(state, {"op": "claim_verified", "claim_id": "clm_1", "claim_digest": digest,
                                           "supports": 2, "contradicts": 0, "unclear": 0})
        self.assertEqual(state_module.view(state)["claims"][0]["verification"],
                         {"supports": 2, "contradicts": 0, "unclear": 0, "omitted": 0})
        linked = state_module.apply(state, {"op": "claim_linked", "claim_id": "clm_1", "counter": [ids[3]]})
        self.assertIsNone(state_module.view(linked)["claims"][0]["verification"])  # evidence changed: stale
        with self.assertRaises(AnalysisContractError) as caught:
            state_module.apply(linked, {"op": "claim_verified", "claim_id": "clm_1", "claim_digest": digest,
                                        "supports": 2, "contradicts": 0, "unclear": 0})
        self.assertEqual(caught.exception.code, "state_claim_changed")

    def test_verification_records_how_much_evidence_was_not_shown(self):
        state, ids = self.claim_state()
        digest = state_module.claim_digest(state["claims"]["clm_1"])
        state = state_module.apply(state, {"op": "claim_verified", "claim_id": "clm_1", "claim_digest": digest,
                                           "supports": 2, "contradicts": 0, "unclear": 0, "omitted": 3})
        self.assertEqual(state_module.view(state)["claims"][0]["verification"]["omitted"], 3)
        with self.assertRaises(AnalysisContractError):
            state_module.apply(state, {"op": "claim_verified", "claim_id": "clm_1", "claim_digest": digest,
                                       "supports": 1, "contradicts": 0, "unclear": 0, "omitted": -1})

    def test_status_change_keeps_the_digest_and_rejection_releases_observations(self):
        state, ids = self.claim_state()
        before = state_module.claim_digest(state["claims"]["clm_1"])
        rejected = state_module.apply(state, {"op": "claim_status", "claim_id": "clm_1", "status": "rejected",
                                              "reason": "重複"})
        self.assertEqual(state_module.claim_digest(rejected["claims"]["clm_1"]), before)
        unclaimed = lambda s: sum(g["unclaimed"] for g in state_module.themes(s).values())
        self.assertEqual(unclaimed(state), 2)
        self.assertEqual(unclaimed(rejected), 4)

    def test_verification_observations_do_not_become_headings(self):
        state, ids = self.claim_state()
        row = {"observation_id": "obs_v1", "evidence_ids": ["evx"], "statement": "反する発話", "kind": "exception",
               "theme": "検証用の見出し", "origin": "verify"}
        state = state_module.apply(state, {"op": "observations_added", "chunk_id": "vrf_1", "result_id": "rv",
                                           "observations": [row]})
        self.assertNotIn("検証用の見出し", [g["theme"] for g in state_module.themes(state).values()])
        self.assertIn("obs_v1", state["observations"])

class IntentionTests(unittest.TestCase):
    def setUp(self):
        self.events = [observations("a", 3)]
        state = state_module.replay(self.events)
        self.ids = list(state["observations"])
        self.events.append({"op": "claim_added", "claim_id": "clm_1", "text": "主張の本文に対象の説明が残る",
                            "support": self.ids[:1], "counter": []})
        state = state_module.replay(self.events)
        self.events.append(state_module.question_event(state, "qst_1", "説明の根拠は十分か", claim_id="clm_1"))
        self.state = state_module.replay(self.events)

    def close(self, resolution, reason="", state=None):
        return state_module.apply(state if state is not None else self.state, {
            "op": "question_closed", "question_id": "qst_1", "resolution": resolution, "reason": reason})

    def test_revised_requires_a_content_change_not_a_status_change(self):
        status = state_module.apply(self.state, {"op": "claim_status", "claim_id": "clm_1",
                                                "status": "contested", "reason": "限界"})
        with self.assertRaises(AnalysisContractError) as caught:
            self.close("revised", "修正した", status)
        self.assertEqual(caught.exception.code, "state_resolution_mismatch")
        revised = state_module.apply(self.state, {"op": "claim_revised", "claim_id": "clm_1", "text": "限定した主張"})
        self.assertEqual(self.close("revised", state=revised)["questions"]["qst_1"]["resolution"], "revised")

    def test_revised_accepts_new_evidence_and_rejects_reverted_text(self):
        linked = state_module.apply(self.state, {"op": "claim_linked", "claim_id": "clm_1", "counter": self.ids[1:]})
        self.assertEqual(self.close("revised", state=linked)["questions"]["qst_1"]["status"], "closed")
        revised = state_module.apply(self.state, {"op": "claim_revised", "claim_id": "clm_1", "text": "変更"})
        reverted = state_module.apply(revised, {"op": "claim_revised", "claim_id": "clm_1",
                                               "text": self.state["claims"]["clm_1"]["text"]})
        with self.assertRaises(AnalysisContractError):
            self.close("revised", state=reverted)

    def test_accepted_limit_requires_contested_or_rejected(self):
        for status in state_module.CLAIM_STATUSES:
            with self.subTest(status=status):
                state = state_module.apply(self.state, {"op": "claim_status", "claim_id": "clm_1",
                                                       "status": status, "reason": "判定"})
                if status in ("contested", "rejected"):
                    self.assertEqual(self.close("accepted_limit", state=state)["questions"]["qst_1"]["status"], "closed")
                else:
                    with self.assertRaises(AnalysisContractError) as caught:
                        self.close("accepted_limit", state=state)
                    self.assertEqual(caught.exception.code, "state_resolution_mismatch")

    def test_withdrawn_requires_a_reason_and_allows_a_rejected_claim(self):
        for reason in ("", "   ", None):
            with self.subTest(reason=reason), self.assertRaises(AnalysisContractError) as caught:
                self.close("withdrawn", reason)
            self.assertEqual(caught.exception.code, "state_resolution_mismatch")
        rejected = state_module.apply(self.state, {"op": "claim_status", "claim_id": "clm_1",
                                                  "status": "rejected", "reason": "不要"})
        self.assertEqual(self.close("withdrawn", "問いの前提が誤り", rejected)["questions"]["qst_1"]["resolution"], "withdrawn")

    def test_null_target_can_only_be_withdrawn(self):
        state = state_module.apply(self.state, state_module.question_event(self.state, "qst_general", "対象のない問い"))
        for resolution in state_module.RESOLUTIONS:
            event = {"op": "question_closed", "question_id": "qst_general", "resolution": resolution, "reason": "前提なし"}
            if resolution == "withdrawn":
                closed = state_module.apply(state, event)
                provenance = state_module.intention_provenance(closed, "qst_general")
                self.assertIsNone(provenance["claim_id"])
                self.assertIsNone(provenance["claim_digest"])
                self.assertEqual(provenance["observation_ids"], [])
                self.assertEqual(provenance["evidence_ids"], [])
            else:
                with self.subTest(resolution=resolution), self.assertRaises(AnalysisContractError):
                    state_module.apply(state, event)

    def test_provenance_keeps_the_opening_evidence_and_returns_a_copy(self):
        original = state_module.intention_provenance(self.state, "qst_1")
        linked = state_module.apply(self.state, {"op": "claim_linked", "claim_id": "clm_1", "counter": self.ids[1:]})
        closed = self.close("revised", state=linked)
        provenance = state_module.intention_provenance(closed, "qst_1")
        self.assertEqual(set(provenance), {"question_id", "claim_id", "claim_digest", "observation_ids", "evidence_ids",
                                           "opened_at_event", "closed_at_event", "resolution"})
        self.assertEqual(provenance["observation_ids"], self.ids[:1])
        self.assertEqual(provenance["evidence_ids"], ["eva0"])
        self.assertEqual(provenance["claim_digest"], original["claim_digest"])
        self.assertEqual((provenance["opened_at_event"], provenance["closed_at_event"]), (3, 5))
        self.assertEqual(closed["questions"]["qst_1"]["text"], self.state["questions"]["qst_1"]["text"])
        provenance["observation_ids"].clear()
        self.assertEqual(state_module.intention_provenance(closed, "qst_1")["observation_ids"], self.ids[:1])
        with self.assertRaises(AnalysisContractError):
            state_module.intention_provenance(closed, "qst_unknown")

    def test_old_missing_or_unknown_resolution_and_unsupported_op_are_rejected(self):
        for event in ({"op": "question_closed", "question_id": "qst_1", "reason": "修正した"},
                      {"op": "question_closed", "question_id": "qst_1", "resolution": "other", "reason": "r"},
                      {"op": "unknown"},
                      {"op": "question_added", "question_id": "qst_old", "text": "旧形式"}):
            with self.subTest(event=event), self.assertRaises(AnalysisContractError):
                state_module.apply(self.state, event)

    def test_sol_full_4_mismatch_fixtures_are_rejected_without_mutation(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/prospective_intentions/sol_full_4_mismatches.json").read_bytes())
        before = state_module.state_hash(self.state)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]), self.assertRaises(AnalysisContractError) as caught:
                self.close(case["resolution"], case["reason"])
            self.assertEqual(caught.exception.code, "state_resolution_mismatch")
            self.assertEqual(self.state["claims"]["clm_1"]["text"], case["text"])
            self.assertEqual(self.state["claims"]["clm_1"]["status"], case["status"])
        self.assertEqual(state_module.state_hash(self.state), before)

    def test_replay_store_hash_and_payload_are_deterministic(self):
        events = self.events + [{"op": "claim_revised", "claim_id": "clm_1", "text": "限定"},
                                {"op": "question_closed", "question_id": "qst_1", "resolution": "revised", "reason": ""}]
        with sqlite3.connect(":memory:") as db:
            state_module.initialize_state_store(db)
            for event in events:
                saved = state_module.append_event(db, "run", event, created_at="t")
            loaded = state_module.load_state(db, "run")
            replayed = state_module.replay(events)
            self.assertEqual(saved, loaded)
            self.assertEqual(loaded, replayed)
            self.assertEqual(state_module.state_hash(loaded), state_module.state_hash(state_module.replay(events)))
            payload = json.loads(db.execute("SELECT payload_json FROM orchestration_state_events WHERE seq=3").fetchone()[0])
            self.assertEqual(payload["claim_digest"], self.state["questions"]["qst_1"]["claim_digest"])
            self.assertEqual(payload["opened_at_event"], 3)
            self.assertEqual(payload["claim_id"], "clm_1")
            with self.assertRaises(AnalysisContractError):
                state_module.append_event(db, "run", events[-1], created_at="t")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_state_events").fetchone()[0], len(events))
        same = state_module.apply(loaded, {"op": "claim_revised", "claim_id": "clm_1", "text": "限定"})
        self.assertEqual(state_module.state_hash(same), state_module.state_hash(loaded))

    def test_opening_metadata_is_checked_and_view_is_compact(self):
        before = state_module.replay(self.events[:-1])
        for changes in ({"claim_id": "clm_missing"}, {"claim_id": []}, {"claim_digest": "fake"}, {"opened_at_event": 0}):
            with self.subTest(changes=changes), self.assertRaises(AnalysisContractError):
                state_module.apply(before, {**self.events[-1], **changes})
        row = state_module.view(self.state)["questions"][0]
        self.assertEqual(row["claim_id"], "clm_1")
        self.assertIsNone(row["resolution"])
        self.assertNotIn("claim_digest", row)
        self.assertNotIn("evidence_ids", row)

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        state_module.initialize_state_store(self.db)

    def test_append_and_replay(self):
        first = state_module.append_event(self.db, "run_1", observations("a", 2), created_at="t1")
        ids = list(first["observations"])
        state_module.append_event(self.db, "run_1", state_module.question_event(
            first, "qst_1", "例外は誰か"), created_at="t2")
        loaded = state_module.load_state(self.db, "run_1")
        self.assertEqual(list(loaded["observations"]), ids)
        self.assertEqual(state_module.load_state(self.db, "run_2"), state_module.empty())

    def test_rejected_event_is_not_stored(self):
        state_module.append_event(self.db, "run_1", observations("a", 1), created_at="t1")
        with self.assertRaises(AnalysisContractError):
            state_module.append_event(self.db, "run_1", {"op": "claim_added", "claim_id": "clm_1", "text": "x",
                                                         "support": ["obs_unknown"]}, created_at="t2")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM orchestration_state_events").fetchone()[0], 1)

    def test_tampered_event_is_detected(self):
        state_module.append_event(self.db, "run_1", observations("a", 1), created_at="t1")
        payload = json.loads(self.db.execute("SELECT payload_json FROM orchestration_state_events").fetchone()[0])
        payload["observations"][0]["statement"] = "書換え"
        self.db.execute("UPDATE orchestration_state_events SET payload_json=?", (json.dumps(payload),))
        with self.assertRaises(AnalysisContractError) as caught:
            state_module.load_state(self.db, "run_1")
        self.assertEqual(caught.exception.code, "state_integrity_mismatch")

if __name__ == "__main__":
    unittest.main()
