import unittest
from unittest.mock import patch

import app
from gurumoji.jev_review import attach_comparison, comparison_rows, review_transcript


class JevReviewTests(unittest.TestCase):
    def test_app_calls_official_system_one_endpoint_with_bearer_key(self):
        response = {"model": "jev-test", "answers": {"decision_0": {
            "type": "choice", "choice": "no_correction_needed",
            "probabilities": {"correction_needed": 0.1, "no_correction_needed": 0.9},
            "confidence": 0.8,
        }}, "usage": {"input_tokens": 5, "output_tokens": 1}}
        with patch.object(app, "post_json", return_value=response) as post:
            reviews, _ = app.review_segments_with_jev(
                [{"id": "s1", "speaker": "A", "text": "本文"}],
                "secret", "jev-test", lambda _message: None, lambda: None,
            )
        self.assertFalse(reviews["s1"]["flagged"])
        self.assertEqual(post.call_args.args[0], "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(post.call_args.args[1]["Authorization"], "Bearer secret")
        self.assertEqual(post.call_args.args[2]["model"], "jev-test")

    def test_review_uses_binary_choice_and_preserves_probabilities(self):
        segments = [
            {"id": "s1", "speaker": "A", "text": "東京に行きました。", "start": 0, "end": 2},
            {"id": "s2", "speaker": "B", "text": "投擲に行きました。", "start": 2, "end": 4},
        ]
        captured = {}

        def call(state, questions):
            captured.update(state=state, questions=questions)
            return {
                "model": "jev-1.13.0",
                "answers": {
                    "decision_0": {
                        "type": "choice", "choice": "no_correction_needed",
                        "probabilities": {"correction_needed": 0.08, "no_correction_needed": 0.92},
                        "confidence": 0.84,
                    },
                    "decision_1": {
                        "type": "choice", "choice": "correction_needed",
                        "probabilities": {"correction_needed": 0.91, "no_correction_needed": 0.09},
                        "confidence": 0.82,
                    },
                },
                "usage": {"input_tokens": 42, "output_tokens": 8},
            }

        reviews, usage = review_transcript(
            segments, {"sections": []}, call, lambda _message: None, lambda: None,
        )

        self.assertEqual(set(captured["questions"]["decision_0"]["criteria"]), {
            "correction_needed", "no_correction_needed",
        })
        self.assertIn(
            "audio noise rendered as words",
            captured["questions"]["decision_0"]["instructions"]["correction_needed_when"],
        )
        self.assertEqual(reviews["s1"]["decision"], "no_correction_needed")
        self.assertFalse(reviews["s1"]["flagged"])
        self.assertEqual(reviews["s2"]["decision"], "correction_needed")
        self.assertAlmostEqual(reviews["s2"]["correction_needed_probability"], 0.91)
        self.assertEqual(usage["input_tokens"], 42)
        self.assertEqual(usage["model"], "jev-1.13.0")

    def test_any_flagged_fragment_flags_a_long_segment(self):
        segment = {"id": "long", "speaker": "A", "text": "あ" * 1600}

        def call(_state, questions):
            answers = {}
            for index in range(len(questions)):
                flagged = index == 1
                answers[f"decision_{index}"] = {
                    "type": "choice",
                    "choice": "correction_needed" if flagged else "no_correction_needed",
                    "probabilities": {
                        "correction_needed": 0.8 if flagged else 0.1,
                        "no_correction_needed": 0.2 if flagged else 0.9,
                    },
                    "confidence": 0.6,
                }
            return {"answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}}

        reviews, _ = review_transcript([segment], None, call, lambda _message: None, lambda: None)
        self.assertEqual(len(reviews["long"]["fragments"]), 2)
        self.assertTrue(reviews["long"]["flagged"])

    def test_invalid_probability_distribution_is_rejected(self):
        def call(_state, _questions):
            return {"answers": {"decision_0": {
                "type": "choice", "choice": "correction_needed",
                "probabilities": {"correction_needed": 0.9, "no_correction_needed": 0.9},
                "confidence": 0.5,
            }}}

        with self.assertRaises(RuntimeError):
            review_transcript(
                [{"id": "s1", "text": "本文"}], None, call,
                lambda _message: None, lambda: None,
            )

    def test_comparison_attaches_all_four_agreement_groups(self):
        revised = [
            {"id": "both", "text": "修正文", "ai_review": {"original_text": "原文"}},
            {"id": "current", "text": "修正文", "ai_review": {"original_text": "原文"}},
            {"id": "jev", "text": "原文"},
            {"id": "clear", "text": "原文"},
        ]
        reviews = {
            key: {
                "decision": "correction_needed" if flagged else "no_correction_needed",
                "flagged": flagged, "original_text": "原文", "model": "jev-latest",
                "correction_needed_probability": 0.8 if flagged else 0.1,
                "confidence": 0.7, "fragments": [],
            }
            for key, flagged in (("both", True), ("current", False), ("jev", True), ("clear", False))
        }

        attached = attach_comparison(revised, reviews)
        self.assertEqual(
            [row["jev_review"]["comparison"]["agreement"] for row in attached],
            ["both_flagged", "current_only", "jev_only", "both_clear"],
        )
        rows = comparison_rows(attached)
        self.assertEqual([row["agreement"] for row in rows], [
            "both_flagged", "current_only", "jev_only", "both_clear",
        ])


if __name__ == "__main__":
    unittest.main()
