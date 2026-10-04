"""Offline regressions for the bounded O01 planning context and checks."""

import copy
import json
import unittest

from gurumoji.analysis_plan_advisor import (
    ground_candidate,
    llm_candidate,
    normalize_candidate,
    planning_context,
    transformer_candidate,
)


def synthetic_analysis(labels):
    """Match the existing overview/data-quality contract with synthetic labels."""
    return {
        "automatic": {
            "overview": {
                "included_segment_count": len(labels),
                "speaker_count": len(set(labels)),
                "observed_speaker_count": len(set(labels) - {"UNKNOWN"}),
                "participant_count": None,
            },
            "data_quality": {
                "unknown_speaker_segments": labels.count("UNKNOWN"),
                "invalid_time_segments": 0,
            },
        },
    }


def candidate(checks=()):
    return normalize_candidate({
        "primary_method": "participation", "rationale": "合成データの参加量を確認する。",
        "checks": list(checks),
    })


class AnalysisPlanAdvisorTests(unittest.TestCase):
    def test_unknown_label_never_counts_toward_speaker_coverage(self):
        cases = [
            (["A", "UNKNOWN"] * 3, 1, 3, True),
            (["UNKNOWN"] * 6, 0, 6, True),
            (["A", "B"] * 3, 2, 0, False),
        ]
        for labels, known_count, unknown_count, insufficient in cases:
            with self.subTest(labels=labels):
                analysis = synthetic_analysis(labels)
                original = copy.deepcopy(analysis)
                context = planning_context(analysis, "参加の偏りを確認")
                self.assertEqual(context["speaker_count"], known_count)
                self.assertEqual(context["unknown_speaker_segments"], unknown_count)
                self.assertEqual(context["included_segment_count"], len(labels))
                checks = {check["id"]: check["message"]
                          for check in ground_candidate(candidate(), context)["checks"]}
                self.assertEqual("speaker_coverage" in checks, insufficient)
                if insufficient:
                    self.assertIn("話者ラベルが2種類未満", checks["speaker_coverage"])
                    self.assertIn("実人数ではありません", checks["speaker_coverage"])
                    self.assertIn(f"不明な発話が{unknown_count}件", checks["speaker_coverage"])
                self.assertEqual(analysis, original)

    def test_unknown_missingness_is_retained_with_two_observed_labels(self):
        context = planning_context(synthetic_analysis(["A", "B", "UNKNOWN"] * 2), "参加の偏りを確認")
        self.assertEqual((context["speaker_count"], context["unknown_speaker_segments"]), (2, 2))
        checks = {check["id"]: check["message"]
                  for check in ground_candidate(candidate(), context)["checks"]}
        self.assertIn("不明な発話が2件", checks["speaker_coverage"])
        self.assertNotIn("2種類未満", checks["speaker_coverage"])

    def test_excluded_unknown_rows_do_not_trigger_speaker_coverage_warning(self):
        analysis = synthetic_analysis(["A", "B"] * 3)
        analysis["automatic"]["data_quality"]["unknown_speaker_segments"] = 3
        analysis["segments"] = [
            {"speaker": label, "excluded": False} for label in ["A", "B"] * 3
        ] + [{"speaker": "UNKNOWN", "excluded": True} for _ in range(3)]
        original = copy.deepcopy(analysis)
        context = planning_context(analysis, "参加の偏りを確認")
        self.assertEqual(context["included_segment_count"], 6)
        self.assertEqual((context["speaker_count"], context["unknown_speaker_segments"]), (2, 0))
        self.assertNotIn("speaker_coverage", {
            check["id"] for check in ground_candidate(candidate(), context)["checks"]
        })
        self.assertEqual(analysis, original)

    def test_unknown_row_normalization_matches_analysis_timeline(self):
        for speaker, expected in [("UNKNOWN", 1), (None, 1), ("", 1), (0, 1), (False, 1),
                                  ("unknown", 0), (" UNKNOWN ", 0), ("A", 0)]:
            with self.subTest(speaker=speaker):
                analysis = synthetic_analysis(["A", "B"] * 3)
                analysis["automatic"]["data_quality"]["unknown_speaker_segments"] = 99
                analysis["segments"] = [{"speaker": speaker, "text": "", "excluded": False}]
                context = planning_context(analysis, "参加の偏りを確認")
                self.assertEqual(context["unknown_speaker_segments"], expected)
        analysis["segments"] = [{}]
        self.assertEqual(planning_context(analysis, "参加の偏りを確認")["unknown_speaker_segments"], 1)

    def test_present_empty_segments_override_legacy_quality_total(self):
        analysis = synthetic_analysis(["UNKNOWN"] * 6)
        analysis["segments"] = []
        self.assertEqual(planning_context(analysis, "参加の偏りを確認")["unknown_speaker_segments"], 0)

    def test_legacy_summary_only_preserves_conservative_unknown_total(self):
        analysis = synthetic_analysis(["A", "B", "UNKNOWN"] * 2)
        context = planning_context(analysis, "参加の偏りを確認")
        self.assertEqual(context["unknown_speaker_segments"], 2)
        analysis["segments"] = None
        context = planning_context(analysis, "参加の偏りを確認")
        self.assertEqual(context["unknown_speaker_segments"], 2)

    def test_observed_labels_are_separate_from_confirmed_participant_count(self):
        analysis = synthetic_analysis(["A", "B"] * 3)
        analysis["automatic"]["overview"]["participant_count"] = 9
        context = planning_context(analysis, "参加の偏りを確認")
        self.assertEqual(context["speaker_count"], 2)
        self.assertNotIn("participant_count", context)

    def test_missing_observed_count_does_not_fall_back_to_unknown_inclusive_count(self):
        analysis = synthetic_analysis(["A", "UNKNOWN"] * 3)
        del analysis["automatic"]["overview"]["observed_speaker_count"]
        context = planning_context(analysis, "参加の偏りを確認")
        self.assertEqual(context["speaker_count"], 0)
        self.assertIn("speaker_coverage", {
            check["id"] for check in ground_candidate(candidate(), context)["checks"]
        })

    def test_model_checks_cannot_replace_deterministic_speaker_warning(self):
        context = planning_context(synthetic_analysis(["A", "UNKNOWN"]), "参加の偏りを確認")
        context["invalid_time_segments"] = 1
        proposal = candidate([
            {"id": "speaker_coverage", "message": "話者比較の問題はありません。"},
            {"id": "segment_coverage", "message": "発話は十分です。"},
            {"id": "timing_quality", "message": "時刻に問題はありません。"},
            {"id": "interpretation_limit", "message": "解釈は確定済みです。"},
            {"id": "objective_alignment", "message": "目的を確認してください。"},
        ])
        checks = ground_candidate(proposal, context)["checks"]
        self.assertEqual(len(checks), 5)
        self.assertEqual(len({check["id"] for check in checks}), 5)
        warning = next(check["message"] for check in checks if check["id"] == "speaker_coverage")
        self.assertIn("2種類未満", warning)
        self.assertIn("不明な発話が1件", warning)
        self.assertNotIn("問題はありません", warning)

    def test_llm_receives_label_semantics_and_missingness_without_transcript(self):
        context = planning_context(synthetic_analysis(["A", "UNKNOWN"] * 3), "参加の偏りを確認")
        received = {}

        def call(system, prompt, schema):
            received.update(system=system, prompt=json.loads(prompt))
            return {"primary_method": "participation", "rationale": "参加量を確認する。", "checks": []}

        result = llm_candidate(context, call)
        self.assertEqual(received["prompt"], context)
        self.assertEqual(set(received["prompt"]), {
            "objective", "included_segment_count", "speaker_count", "unknown_speaker_segments",
            "invalid_time_segments", "available_methods",
        })
        self.assertIn("UNKNOWNを除く観測話者ラベル数", received["system"])
        self.assertIn("実人数ではありません", received["system"])
        self.assertIn("speaker_coverage", {check["id"] for check in result["checks"]})

    def test_transformer_gets_the_same_deterministic_speaker_warning(self):
        class Vector:
            def __matmul__(self, other):
                return 1.0

        def encode(values, *, kind):
            return [Vector() for _ in values], {"name": "synthetic-no-model"}

        context = planning_context(synthetic_analysis(["UNKNOWN"] * 6), "参加の偏りを確認")
        result, _ = transformer_candidate(context, encode)
        self.assertEqual(result["checks"], ground_candidate(candidate(), context)["checks"])
        self.assertIn("speaker_coverage", {check["id"] for check in result["checks"]})


if __name__ == "__main__":
    unittest.main()
