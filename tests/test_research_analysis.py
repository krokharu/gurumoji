import copy
import importlib.util
import io
import json
import unittest
from unittest.mock import patch

import research_analysis


def fixture_analysis(item_id="research_fixture"):
    segments = [
        {
            "id": "s1",
            "start": 0.0,
            "end": 2.0,
            "duration": 2.0,
            "speaker": "A",
            "speaker_name": "参加者A",
            "role": "participant",
            "text": "改善案に賛成です。",
            "characters": 9,
            "question_candidate": False,
            "annotation": {
                "codes": ["improvement"],
                "interaction_tags": ["agreement"],
                "important": False,
                "excluded": False,
            },
            "excluded": False,
        },
        {
            "id": "s2",
            "start": 2.5,
            "end": 6.5,
            "duration": 4.0,
            "speaker": "B",
            "speaker_name": "参加者B",
            "role": "participant",
            "text": "操作方法を改善したいです。",
            "characters": 12,
            "question_candidate": False,
            "annotation": {
                "codes": ["improvement"],
                "interaction_tags": [],
                "important": True,
                "excluded": False,
            },
            "excluded": False,
        },
        {
            "id": "s3",
            "start": 7.0,
            "end": 8.0,
            "duration": 1.0,
            "speaker": "A",
            "speaker_name": "参加者A",
            "role": "participant",
            "text": "質問ですか？",
            "characters": 6,
            "question_candidate": True,
            "annotation": {
                "codes": [],
                "interaction_tags": [],
                "important": False,
                "excluded": False,
            },
            "excluded": False,
        },
    ]
    return {
        "schema_version": 1,
        "algorithm_version": "fixture",
        "generated_at": "2026-07-31T00:00:00+00:00",
        "item": {
            "id": item_id,
            "source_name": '=unsafe".wav',
            "revision_count": 1,
            "analysis_revision": 2,
            "analysis_updated_at": "2026-07-31T00:00:00+00:00",
        },
        "config": {
            "stop_words": [],
            "morph_split_mode": "C",
            "cooccurrence_min_count": 1,
            "cooccurrence_top_terms": 60,
            "statistics_group_by": "speaker",
        },
        "classification": {"automatic": [], "configured": [], "manual": []},
        "cautions": [],
        "automatic": {},
        "manual": {
            "codebook": [{"id": "improvement", "label": "改善"}],
        },
        "segments": segments,
        "exports": {
            "json": f"/api/library/{item_id}/analysis/export.json",
        },
    }


def statistical_note_fixture(durations, characters, speakers):
    analysis = fixture_analysis("statistical_notes")
    source = analysis["segments"][0]
    analysis["segments"] = [
        {**source, "id": f"s{index}", "duration": duration, "end": duration,
         "valid_time": duration is not None, "characters": count,
         "speaker": speaker, "speaker_name": speaker}
        for index, (duration, count, speaker) in enumerate(zip(durations, characters, speakers))
    ]
    return analysis


class ResearchAnalysisTests(unittest.TestCase):
    def setUp(self):
        research_analysis._RESEARCH_CACHE.clear()

    def test_same_display_name_keeps_statistics_separate_by_speaker_id(self):
        analysis = fixture_analysis("same_names")
        source = analysis["segments"][0]
        analysis["segments"] = [
            {**source, "id": str(index), "speaker": speaker, "speaker_name": "同名",
             "duration": duration, "end": duration, "question_candidate": speaker == "B"}
            for index, (speaker, duration) in enumerate((("A", 1), ("A", 2), ("B", 5), ("B", 6)))
        ]
        rows = research_analysis._segment_dataset(analysis, [])
        result = research_analysis._statistics_analysis(analysis, rows)
        self.assertEqual(result["group_count"], 2)
        groups = [row for row in result["descriptives"]
                  if row["scope"] == "group" and row["variable"] == "duration_seconds"]
        self.assertEqual({row["group_id"]: row["mean"] for row in groups}, {"A": 1.5, "B": 5.5})
        self.assertEqual({row["group"] for row in groups}, {"同名 [A]", "同名 [B]"})
        frequencies = [row for row in result["frequencies"] if row["variable"] == "speaker"]
        self.assertEqual({row["value_id"]: row["count"] for row in frequencies}, {"A": 2, "B": 2})
        question_rows = [row for row in result["crosstabs"] if row["column_variable"] == "question_candidate"]
        self.assertEqual({row["row_value"] for row in question_rows}, {"同名 [A]", "同名 [B]"})
        self.assertEqual({row["row_id"] for row in question_rows}, {"A", "B"})
        anova = next(row for row in result["tests"]
                     if row["outcome"] == "duration_seconds" and row["effect_name"] == "eta_squared")
        self.assertEqual(anova["groups"], 2)
        if result["engine"]["status"] == "ready":
            self.assertEqual(anova["status"], "computed")

    def test_speaker_label_that_matches_generated_label_stays_distinct(self):
        rows = [{"speaker": "A", "speaker_name": "同名"},
                {"speaker": "B", "speaker_name": "同名"},
                {"speaker": "C", "speaker_name": "同名 [A]"}]
        labels = research_analysis._speaker_labels(rows)
        self.assertEqual(len(set(labels.values())), 3)

    def test_unknown_time_is_missing_not_zero_in_research_statistics(self):
        analysis = fixture_analysis("unknown_times")
        source = analysis["segments"][0]
        analysis["segments"] = [
            {**source, "id": "known", "duration": 10, "end": 10, "valid_time": True},
            {**source, "id": "unknown", "duration": 0, "end": 0, "valid_time": False},
            {**source, "id": "placeholder", "duration": 100, "end": 100, "valid_time": False},
        ]
        rows = research_analysis._segment_dataset(analysis, [])
        self.assertEqual([row["duration_seconds"] for row in rows], [10, None, None])
        self.assertEqual([row["characters_per_minute"] for row in rows], [54, None, None])
        result = research_analysis._statistics_analysis(analysis, rows)
        duration = next(row for row in result["descriptives"]
                        if row["scope"] == "overall" and row["variable"] == "duration_seconds")
        self.assertEqual((duration["n"], duration["missing"], duration["mean"]), (1, 2, 10))
        # Text-only measures still include every turn.
        chars = next(row for row in result["descriptives"]
                     if row["scope"] == "overall" and row["variable"] == "characters")
        self.assertEqual(chars["n"], 3)

    def test_kruskal_note_identifies_current_formula_without_renaming_effect(self):
        analysis = statistical_note_fixture(range(1, 21), range(3, 23), "A" * 7 + "B" * 7 + "C" * 6)
        with patch("scipy.stats.kruskal", return_value=(8.0, 0.125)):
            result = research_analysis.build_research_statistics(analysis, {"morphemes": []})
        row = next(row for row in result["statistics"]["tests"]
                   if row["test"] == "Kruskal–Wallis検定" and row["outcome"] == "duration_seconds")
        self.assertEqual((row["statistic"], row["n"], row["groups"], row["p_value"], row["status"]),
                         (8.0, 20, 3, 0.125, "computed"))
        self.assertEqual(row["effect_size"], round(6 / 17, 8))
        self.assertNotEqual(row["effect_size"], round(8 / 19, 8))
        self.assertEqual(row["effect_name"], "epsilon_squared")
        note = row["assumption_note"]
        for text in ("max(0,(H-k+1)/(N-k))", "H: 検定統計量", "N: 有効観測数", "k: 群数",
                     "effect_name=epsilon_squared", "互換", "方法論的", "未確定",
                     "観測の独立性は必要", "探索的", research_analysis.INFERENTIAL_NOTE):
            self.assertIn(text, note)

    def test_statistical_notes_preserve_synthetic_boundary_results(self):
        from scipy import stats

        cases = (
            ("normal", tuple(range(1, 21)), tuple((i * 7) % 23 + 3 for i in range(20)),
             "A" * 7 + "B" * 7 + "C" * 6, "computed", "computed"),
            ("small", (1, 2, 4), (3, 5, 4), "AAB", "not_computable", "computed"),
            ("ties", (1, 1, 2, 2, 3, 3), (4, 5, 5, 6, 6, 7), "AAABBB", "computed", "computed"),
            ("constant", (2,) * 6, (4,) * 6, "AAABBB", "not_computable", "not_computable"),
            ("missing", (1, None, 3, 5, None, 9), (3, 7, 5, 6, 10, 13), "AAABBB", "computed", "computed"),
            ("uncomputed", (1, 2), (3, 4), "AB", "not_computable", "not_computable"),
        )
        for name, durations, characters, speakers, kruskal_status, correlation_status in cases:
            with self.subTest(case=name):
                analysis = statistical_note_fixture(durations, characters, speakers)
                before = copy.deepcopy(analysis)
                result = research_analysis.build_research_statistics(analysis, {"morphemes": []})["statistics"]
                self.assertEqual(analysis, before)
                kruskal = next(row for row in result["tests"]
                               if row["test"] == "Kruskal–Wallis検定" and row["outcome"] == "duration_seconds")
                pairs = [(x, y) for x, y in zip(durations, characters) if x is not None]
                self.assertEqual((kruskal["n"], kruskal["missing"], kruskal["status"]),
                                 (len(pairs), len(durations) - len(pairs), kruskal_status))
                self.assertEqual(kruskal["effect_name"], "epsilon_squared")
                self.assertIn("max(0,(H-k+1)/(N-k))", kruskal["assumption_note"])
                if kruskal_status == "computed":
                    samples = [[x for x, group in zip(durations, speakers) if x is not None and group == key]
                               for key in sorted(set(speakers))]
                    statistic, p_value = stats.kruskal(*samples)
                    self.assertEqual(kruskal["statistic"], round(float(statistic), 8))
                    self.assertEqual(kruskal["p_value"], float(p_value))
                    self.assertEqual(kruskal["effect_size"],
                                     round(max(0, (float(statistic) - len(samples) + 1) / (len(pairs) - len(samples))), 8))
                else:
                    for key in ("statistic", "p_value", "effect_size"):
                        self.assertIsNone(kruskal[key])
                for row in result["correlations"]:
                    if (row["variable_a"], row["variable_b"]) != ("duration_seconds", "characters"):
                        continue
                    self.assertEqual((row["n"], row["missing"], row["status"]),
                                     (len(pairs), len(durations) - len(pairs), correlation_status))
                    self.assertEqual(row["p_value_adjustment"], "none")
                    self.assertTrue(row["exploratory"])
                    old_note = research_analysis.INFERENTIAL_NOTE + " 定義上関連する指標を含み、因果関係は示しません。"
                    if row["method"] == "Spearman":
                        self.assertTrue(row["assumption_note"].startswith(old_note))
                        self.assertIn("小標本では漸近p値の精度に注意が必要", row["assumption_note"])
                    else:
                        self.assertEqual(row["assumption_note"], old_note)
                    if correlation_status == "computed":
                        function = stats.spearmanr if row["method"] == "Spearman" else stats.pearsonr
                        coefficient, p_value = function(*zip(*pairs))
                        self.assertEqual(row["coefficient"], round(float(coefficient), 8))
                        self.assertEqual(row["p_value"], float(p_value))
                    else:
                        self.assertIsNone(row["coefficient"])
                        self.assertIsNone(row["p_value"])
                self.assertFalse(result["inference_policy"]["independence_verified"])

    def test_statistical_note_hashes_cover_new_rows_and_preserve_legacy_receipts(self):
        from gurumoji.analysis_core import fingerprint
        from gurumoji.services.analysis_orchestration_methods import (
            calculation_packet, run_statistical_tool, validate_statistical_result,
        )

        analysis = statistical_note_fixture((1, 2, 4, 5, 7, 9), (3, 7, 5, 6, 10, 13), "AAABBB")
        analysis["research"] = {"linguistics": {"morphemes": []}}
        evidence = [{"evidence_id": row["id"], "excluded": False} for row in analysis["segments"]]
        for method, dataset, new_text in (("kruskal_wallis", "tests", "max(0,(H-k+1)/(N-k))"),
                                          ("spearman", "correlations", "小標本では漸近p値の精度に注意が必要")):
            with self.subTest(method=method):
                task = {"method_id": method, "dataset_version": "synthetic-v1"}
                snapshot = {"analysis": analysis, "evidence": evidence, "orchestration_task": task}
                before = copy.deepcopy(snapshot)
                current = run_statistical_tool(method, snapshot)
                rows = current["datasets"][dataset]["rows"]
                self.assertTrue(all(new_text in row["assumption_note"] for row in rows))
                self.assertEqual(current["manifest"]["rows_hash"], fingerprint(rows))
                validate_statistical_result(current, task, evidence)
                legacy = copy.deepcopy(current)
                for index, row in enumerate(legacy["datasets"][dataset]["rows"]):
                    row["assumption_note"] = (
                        "順位に基づく比較ですが、観測の独立性は必要です。発話の反復・"
                        "話者内相関があるため探索的に扱ってください。 " + research_analysis.INFERENTIAL_NOTE
                        if method == "kruskal_wallis" else research_analysis.INFERENTIAL_NOTE
                        + " 定義上関連する指標を含み、因果関係は示しません。")
                    del row["row_id"]
                    row["row_id"] = fingerprint([method, index, row])
                legacy["manifest"]["rows_hash"] = fingerprint(legacy["datasets"][dataset]["rows"])
                saved_bytes = json.dumps(legacy, ensure_ascii=False, sort_keys=True)
                metadata = {"result_id": "legacy-result", "task_id": "legacy-task", "raw_hash": fingerprint(legacy)}
                validate_statistical_result(legacy, task, evidence)
                packet = calculation_packet(legacy, metadata)
                self.assertEqual(packet["manifest"]["rows_hash"], legacy["manifest"]["rows_hash"])
                self.assertEqual(packet["raw_hash"], metadata["raw_hash"])
                self.assertNotEqual(current["manifest"]["rows_hash"], legacy["manifest"]["rows_hash"])
                self.assertEqual(run_statistical_tool(method, snapshot), current)
                self.assertEqual(json.dumps(legacy, ensure_ascii=False, sort_keys=True), saved_bytes)
                self.assertEqual(snapshot, before)

    def test_fallback_keeps_analysis_available_and_labels_limit(self):
        analysis = fixture_analysis("fallback_fixture")
        with (
            patch.object(research_analysis, "_load_ginza", return_value=(None, "not installed")),
            patch.object(research_analysis, "_load_sudachi", return_value=(None, "not installed")),
        ):
            result = research_analysis.enrich_research_analysis(analysis)

        research = result["research"]
        self.assertEqual(research["linguistics"]["engine"]["status"], "fallback")
        self.assertGreater(research["linguistics"]["coverage"]["token_count"], 0)
        self.assertTrue(research["linguistics"]["morpheme_preview"])
        self.assertNotIn("morphemes", research["linguistics"])
        self.assertEqual(research["segments"], [])
        self.assertIn("xlsx", result["exports"])
        self.assertIn("morphemes", result["exports"])
        self.assertTrue(
            any("研究データとして使用できません" in value
                for value in [research["linguistics"]["engine"]["message"]])
        )

    def test_complete_rows_contain_spreadsheet_and_spss_style_datasets(self):
        analysis = fixture_analysis("complete_fixture")
        with (
            patch.object(research_analysis, "_load_ginza", return_value=(None, "not installed")),
            patch.object(research_analysis, "_load_sudachi", return_value=(None, "not installed")),
        ):
            result = research_analysis.enrich_research_analysis(
                analysis,
                include_rows=True,
            )

        sources = research_analysis.research_csv_sources(result)
        self.assertEqual(len(sources["segments_all"]), 3)
        self.assertTrue(sources["morphemes"])
        self.assertTrue(sources["term_frequency"])
        speaker_terms = result["research"]["linguistics"]["speaker_term_frequency"]
        self.assertEqual({row["speaker"] for row in speaker_terms}, {"A", "B"})
        self.assertTrue(all(row["terms"] for row in speaker_terms))
        self.assertTrue(sources["descriptives"])
        self.assertTrue(sources["frequencies"])
        self.assertTrue(sources["crosstabs"])
        self.assertTrue(sources["statistical_tests"])
        self.assertTrue(sources["correlations"])
        self.assertTrue(sources["analysis_methods"])
        duration = next(
            row for row in sources["descriptives"]
            if row["scope"] == "overall" and row["variable"] == "duration_seconds"
        )
        self.assertEqual(duration["n"], 3)
        self.assertAlmostEqual(duration["mean"], 7 / 3)

    def test_manually_selected_term_builds_crosstab_and_chi_square(self):
        analysis = fixture_analysis("selected_term_fixture")
        analysis["config"]["crosstab_terms"] = ["改善"]
        with (
            patch.object(research_analysis, "_load_ginza", return_value=(None, "not installed")),
            patch.object(research_analysis, "_load_sudachi", return_value=(None, "not installed")),
        ):
            result = research_analysis.enrich_research_analysis(analysis, include_rows=True)

        statistics = result["research"]["statistics"]
        self.assertEqual(statistics["selected_terms"], ["改善"])
        table_rows = [
            row for row in statistics["crosstabs"]
            if row["column_variable"] == "selected_term:改善"
        ]
        self.assertEqual(len(table_rows), 4)
        self.assertEqual({row["row_value"] for row in table_rows}, {"参加者A", "参加者B"})
        self.assertEqual({row["column_value"] for row in table_rows}, {"あり", "なし"})
        test = next(
            row for row in statistics["tests"]
            if row["outcome_label"] == "正規化語・完全一致「改善」"
        )
        self.assertEqual(test["test"], "Pearsonのカイ二乗検定")
        self.assertEqual(test["effect_name"], "cramers_v")
        self.assertEqual(test["n"], 3)
        self.assertEqual(test["status"], "computed")

    def test_excel_cells_are_formula_safe(self):
        self.assertEqual(research_analysis._excel_value("=1+1"), "'=1+1")
        self.assertEqual(research_analysis._excel_value(" @SUM(A1)"), "' @SUM(A1)")
        self.assertEqual(research_analysis._excel_value(-2.5), -2.5)

    @unittest.skipUnless(
        importlib.util.find_spec("openpyxl"),
        "openpyxl is installed by requirements.txt",
    )
    def test_workbook_has_standard_research_sheets(self):
        from openpyxl import load_workbook

        analysis = fixture_analysis("workbook_fixture")
        with (
            patch.object(research_analysis, "_load_ginza", return_value=(None, "not installed")),
            patch.object(research_analysis, "_load_sudachi", return_value=(None, "not installed")),
        ):
            analysis = research_analysis.enrich_research_analysis(
                analysis,
                include_rows=True,
            )
        sources = research_analysis.research_csv_sources(analysis)
        datasets = {
            name: (research_analysis.RESEARCH_CSV_FIELDS[name], rows)
            for name, rows in sources.items()
        }
        content = research_analysis.build_analysis_workbook(analysis, datasets)
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        self.assertIn("README", workbook.sheetnames)
        self.assertIn("発話データ", workbook.sheetnames)
        self.assertIn("形態素", workbook.sheetnames)
        self.assertIn("構文・係り受け", workbook.sheetnames)
        self.assertIn("統計検定", workbook.sheetnames)
        source_value = workbook["README"]["B4"].value
        self.assertTrue(str(source_value).startswith("'="))


if __name__ == "__main__":
    unittest.main()
