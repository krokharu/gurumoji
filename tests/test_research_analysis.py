import importlib.util
import io
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
