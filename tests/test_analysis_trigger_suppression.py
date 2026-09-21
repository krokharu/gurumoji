"""Tests to ensure GET /api/library/<id>/analysis does not trigger research analysis unless execute=1."""

import unittest
from unittest.mock import MagicMock, patch

import app


class AnalysisTriggerSuppressionTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    @patch("app.is_research_analysis_cached", return_value=False)
    @patch("app.enrich_research_analysis")
    @patch("app.library_row")
    def test_get_analysis_without_execute_does_not_call_enrich_research_analysis(
        self, mock_library_row, mock_enrich, mock_cached
    ):
        mock_row = MagicMock()
        mock_row.keys.return_value = ["id", "source_name", "revision_count", "analysis_revision", "updated_at", "analysis_updated_at"]
        mock_row.__getitem__.side_effect = lambda k: {
            "id": "item-123",
            "source_name": "test.mp4",
            "revision_count": 0,
            "analysis_revision": 0,
            "updated_at": "2026-09-22T00:00:00Z",
            "analysis_updated_at": None,
            "segments_json": "[]",
            "original_segments_json": "[]",
            "speaker_names_json": "{}",
            "speaker_profiles_json": "{}",
            "session_profile_json": "{}",
            "analysis_config_json": "{}",
            "analysis_annotations_json": "{}",
        }.get(k, "")
        mock_library_row.return_value = mock_row

        response = self.client.get("/api/library/item-123/analysis")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data.get("executed"))
        self.assertIsNone(data.get("research"))
        mock_enrich.assert_not_called()

    @patch("app.is_research_analysis_cached", return_value=False)
    @patch("app.enrich_research_analysis")
    @patch("app.library_row")
    def test_get_analysis_with_execute_triggers_enrich_research_analysis(
        self, mock_library_row, mock_enrich, mock_cached
    ):
        mock_row = MagicMock()
        mock_row.keys.return_value = ["id", "source_name", "revision_count", "analysis_revision", "updated_at", "analysis_updated_at"]
        mock_row.__getitem__.side_effect = lambda k: {
            "id": "item-123",
            "source_name": "test.mp4",
            "revision_count": 0,
            "analysis_revision": 0,
            "updated_at": "2026-09-22T00:00:00Z",
            "analysis_updated_at": None,
            "segments_json": "[]",
            "original_segments_json": "[]",
            "speaker_names_json": "{}",
            "speaker_profiles_json": "{}",
            "session_profile_json": "{}",
            "analysis_config_json": "{}",
            "analysis_annotations_json": "{}",
        }.get(k, "")
        mock_library_row.return_value = mock_row
        mock_enrich.side_effect = lambda a, **kw: {**a, "research": {"linguistics": {}, "statistics": {}}}

        response = self.client.get("/api/library/item-123/analysis?execute=1")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("executed"))
        self.assertIsNotNone(data.get("research"))
        mock_enrich.assert_called_once()


if __name__ == "__main__":
    unittest.main()
