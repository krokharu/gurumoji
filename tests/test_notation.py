import copy
import json
import unittest
from unittest.mock import Mock

from gurumoji.services import notation as n
from gurumoji.services.ai.transcript_finishing import run_full_cleanup


def segments(text):
    return [{"id": "s1", "speaker": "S1", "start": 0, "end": 3, "text": text}]


def analyze(source):
    words = ["AI", "ＡＩ", "サーバ", "サーバー", "打合せ", "打ち合わせ", "グルモジ", "ぐるもじ", "機会", "機械"]
    identities = {"打合せ": ("ウチアワセ", "打ち合わせ"), "打ち合わせ": ("ウチアワセ", "打ち合わせ"),
                  "グルモジ": ("グルモジ", "グルモジ"), "ぐるもじ": ("グルモジ", "グルモジ"),
                  "機会": ("キカイ", "機会"), "機械": ("キカイ", "機械")}
    return ([{"surface": w, "segment_id": s["id"], "reading": identities.get(w, (w, w))[0],
              "lemma": identities.get(w, (w, w))[1], "upos": "NOUN", "pos_detail": "名詞"}
             for s in source for w in words if w in s["text"]], {"status": "mock"})


class NotationTests(unittest.TestCase):
    def plan(self, text, **kwargs):
        return n.detect(segments(text), analyze=analyze, **kwargs)

    def test_rules_candidates_homonyms_and_protected_segments(self):
        text = "AI ＡＩ サーバ サーバー 打合せ 打ち合わせ グルモジ ぐるもじ 機会 機械"
        plan = self.plan(text)
        self.assertEqual(sorted(g["kind"] for g in plan["groups"]), ["candidate", "candidate", "rule", "rule"])
        self.assertFalse(any("機会" in g["allowed"] or "機械" in g["allowed"] for g in plan["groups"]))
        self.assertEqual(self.plan(text, protected=["s1"])["groups"], [])

    def test_dictionary_vocabulary_registry_then_history_priority(self):
        options = {"dictionary": {"ＡＩ": "AI"}, "terms": ["ＡＩ"], "registry": ["AI"], "confirmed": ["ＡＩ"]}
        for key, expected in [("dictionary", "dictionary"), ("terms", "vocabulary"), ("registry", "speaker_registry"), ("confirmed", "researcher_history")]:
            plan = self.plan("AI ＡＩ", **options)
            self.assertEqual(plan["groups"][0]["source"], expected)
            options.pop(key)

    def test_one_explicit_alias_and_multiword_source(self):
        source = segments("山 田さん、AI system と AI・system")
        plan = n.detect(source, dictionary={"山 田": "山田", "AI・system": "AI system"}, analyze=analyze)
        result = n.resolve(source, plan)
        self.assertEqual(result["segments"][0]["text"], "山田さん、AI system と AI system")

    def test_ambiguous_dictionary_stops_and_does_not_call_llm(self):
        plan = self.plan("AI ＡＩ", dictionary={"AI": "人工知能", "ＡＩ": "別表記"})
        call = Mock()
        self.assertEqual(n.resolve(segments("AI ＡＩ"), plan, call=call)["segments"], segments("AI ＡＩ"))
        call.assert_not_called()

    def test_llm_bounded_context_allowed_only_and_no_mutation(self):
        text = "冒頭の秘密" + "前" * 120 + " AI ＡＩ " + "後" * 120 + "末尾の秘密"
        source = segments(text)
        before = copy.deepcopy(source)
        seen = []
        def call(system, prompt, name, schema):
            seen.append(json.loads(prompt))
            self.assertNotIn("冒頭の秘密", prompt)
            self.assertNotIn("末尾の秘密", prompt)
            self.assertLess(max(map(len, seen[-1]["contexts"])), 70)
            self.assertEqual(name, "transcript_notation")
            return {"canonical": "AI"}
        result = n.resolve(source, self.plan(text), call=call)
        self.assertEqual(source, before)
        self.assertIn(" AI AI ", result["segments"][0]["text"])
        self.assertTrue(result["notation"]["groups"][0]["needs_review"])
        for invalid in ["人工知能", ["AI"], None]:
            invalid_result = n.resolve(source, self.plan(text), call=lambda *a: {"canonical": invalid})
            self.assertEqual(invalid_result["segments"], before)

    def test_ascii_substrings_and_overlaps_do_not_corrupt_text(self):
        source = segments("RAIL AI ＡＩ")
        result = n.resolve(source, self.plan(source[0]["text"], terms=["AI"]))
        self.assertEqual(result["segments"][0]["text"], "RAIL AI AI")

    def test_fallback_never_guesses_homonyms_or_readings(self):
        plan = n.detect(segments("機会 機械 AI ＡＩ サーバ サーバー"), analyze=lambda _: ([], {"status": "fallback"}))
        self.assertEqual(len(plan["groups"]), 2)
        self.assertEqual(plan["engine"]["status"], "fallback")

    def test_source_not_present_matches_lexical_identity_and_conflicting_pos_does_not_group(self):
        def lexical(source):
            rows = []
            for s in source:
                for word in ("表記甲", "表記乙", "確定表記"):
                    if word in s["text"]:
                        rows.append({"surface": word, "reading": "ヨミ", "lemma": "語彙素", "upos": "NOUN"})
            return rows, {"status": "mock"}
        plan = n.detect(segments("表記甲 表記乙"), registry=["確定表記"], analyze=lexical)
        self.assertEqual(plan["groups"][0]["canonical"], "確定表記")
        self.assertIn("確定表記", plan["groups"][0]["allowed"])
        rows = [{"surface": "生", "reading": "セイ", "lemma": "生", "upos": "NOUN"},
                {"surface": "せい", "reading": "セイ", "lemma": "生", "upos": "VERB"}]
        self.assertEqual(n.detect(segments("生 せい"), analyze=lambda _: (rows, {}))["groups"], [])

    def test_same_shared_stage_both_routes_and_strict_off(self):
        source = segments("AI ＡＩ")
        events = []
        def unify(s):
            events.append("notation")
            return n.resolve(s, n.detect(s, terms=["AI"], analyze=analyze))
        def cleanup(s, outline):
            events.append("cleanup")
            return s
        def run(**kwargs):
            return run_full_cleanup(source, check_cancelled=lambda: None,
                create_context_outline=lambda _: {"sections": ["mock"]},
                clean_with_outline=cleanup, unify_notation=unify, **kwargs)
        first = run(ai_efforts={"notation": "medium"})
        second = run(ai_efforts={"notation": "medium"})
        self.assertEqual(first, second)
        self.assertEqual(events, ["cleanup", "notation", "cleanup", "notation"])
        events.clear()
        off = run(ai_efforts={"notation": "off"})
        self.assertEqual(off["stages"]["notation"], "off")
        self.assertEqual(events, ["cleanup"])

    def test_cancel_and_failure_leave_input_untouched(self):
        source = segments("AI ＡＩ")
        before = copy.deepcopy(source)
        with self.assertRaises(InterruptedError):
            n.resolve(source, self.plan(source[0]["text"]), check=Mock(side_effect=InterruptedError))
        result = run_full_cleanup(source, check_cancelled=lambda: None, create_context_outline=lambda _: {},
            clean_with_outline=None, unify_notation=Mock(side_effect=ValueError("injected")),
            ai_efforts={"notation": "medium"}, on_failure=lambda *a: None)
        self.assertEqual(result["stages"]["notation"], "failed")
        self.assertEqual(result["segments"], before)
        self.assertEqual(source, before)


if __name__ == "__main__":
    unittest.main()
