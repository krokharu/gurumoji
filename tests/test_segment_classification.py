import unittest

from gurumoji.segment_classification import (
    build_result,
    classification_rows,
    classify_with_jev,
    crosstab_rows,
    template_proposals,
)


class SegmentClassificationTests(unittest.TestCase):
    def test_template_proposes_dialogue_act_and_screening_scores(self):
        rows = template_proposals([
            {"id": "q", "text": "この問題はなぜ重要ですか？"},
            {"id": "a", "text": "年収と通院情報が必要だからです。"},
        ])
        self.assertEqual(rows["q"]["dialogue_act"], "question")
        self.assertEqual(rows["a"]["dialogue_act"], "answer")
        self.assertGreaterEqual(rows["q"]["importance_score"], 65)
        self.assertGreaterEqual(rows["a"]["sensitivity_score"], 70)

    def test_jev_keeps_sources_and_expected_scores(self):
        segments = [{"id": "s1", "speaker": "A", "text": "改善を提案します。"}]
        topics = [{"id": "topic_a", "label": "改善", "description": "改善案"}]

        def answer(choice, criteria, confidence=0.8):
            probabilities = {key: 0.0 for key in criteria}
            probabilities[choice] = 1.0
            return {"type": "choice", "choice": choice,
                    "probabilities": probabilities, "confidence": confidence}

        def call(_state, questions):
            return {"model": "jev-test", "answers": {
                "act_0": answer("proposal", questions["act_0"]["criteria"]),
                "importance_0": answer("high", questions["importance_0"]["criteria"]),
                "review_0": answer("medium", questions["review_0"]["criteria"]),
                "sensitivity_0": answer("low", questions["sensitivity_0"]["criteria"]),
                "topic_0": answer("topic_0", questions["topic_0"]["criteria"]),
            }, "usage": {"input_tokens": 10, "output_tokens": 5}}

        proposals, usage = classify_with_jev(
            segments, topics, call, lambda _message: None, lambda: None,
            model="jev-test",
        )
        self.assertEqual(proposals["s1"]["dialogue_act"], "proposal")
        self.assertEqual(proposals["s1"]["topic_id"], "topic_a")
        self.assertEqual(proposals["s1"]["importance_score"], 100)
        self.assertEqual(proposals["s1"]["review_score"], 50)
        self.assertEqual(proposals["s1"]["sensitivity_score"], 0)
        self.assertEqual(usage["request_count"], 1)

    def test_invalid_jev_distribution_is_rejected(self):
        def call(_state, questions):
            answers = {}
            for key, question in questions.items():
                criteria = question["criteria"]
                choice = next(iter(criteria))
                answers[key] = {"type": "choice", "choice": choice,
                                "probabilities": {name: 0.9 for name in criteria},
                                "confidence": 0.5}
            return {"answers": answers}

        with self.assertRaises(RuntimeError):
            classify_with_jev(
                [{"id": "s1", "text": "本文"}], [], call,
                lambda _message: None, lambda: None, model="jev-test",
            )

    def test_result_preserves_manual_template_llm_and_transformer_layers(self):
        segments = [{"id": "s1", "speaker": "A", "speaker_name": "参加者A",
                     "start": 0, "end": 1, "text": "賛成です。"}]
        annotations = {"s1": {"dialogue_act": "agreement", "importance_score": 80,
                              "classification_status": "reviewed", "codes": ["c1"]}}
        codebook = [{"id": "c1", "label": "賛同"}]
        transformer = {"algorithm_version": "t1", "fingerprint": "fp", "engine": {"name": "e5"},
                       "assignments": [{"segment_id": "s1", "topic_id": "t1",
                                        "topic_label": "評価", "similarity": 0.8}]}
        llm = {"s1": {"dialogue_act": "agreement", "dialogue_act_label": "同意・賛同",
                       "importance_score": 75, "review_score": 25,
                       "sensitivity_score": 0, "model": "jev-test"}}
        result = build_result(
            segments, annotations, codebook, transformer, llm,
            source_revision=1, analysis_revision=2,
        )
        row = classification_rows(result)[0]
        self.assertEqual(row["manual_dialogue_act"], "agreement")
        self.assertEqual(row["llm_dialogue_act"], "agreement")
        self.assertEqual(row["transformer_topic_label"], "評価")
        self.assertTrue(row["manual_llm_act_agreement"])
        table_ids = {row["table_id"] for row in crosstab_rows(result)}
        self.assertIn("manual_code_llm_act", table_ids)
        self.assertIn("transformer_topic_llm_act", table_ids)


if __name__ == "__main__":
    unittest.main()
