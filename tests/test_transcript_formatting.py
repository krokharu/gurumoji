import app
import unittest


def segment(segment_id, start, end, speaker, text):
    return {
        "id": segment_id,
        "start": start,
        "end": end,
        "speaker": speaker,
        "text": text,
    }


class TranscriptFormattingTests(unittest.TestCase):
    def test_recommended_mode_formats_safe_punctuation_and_reports_candidates(self):
        original = [
            segment("s1", 0, 2, "SPEAKER_00", "これは　文です 、"),
            segment("s2", 3, 4, "SPEAKER_00", "（雑音） 次です。。"),
        ]

        formatted, result = app.transcript_formatting_result(
            original,
            original,
            mode="recommended",
            audio_preprocess="standard",
        )

        self.assertEqual(formatted[0]["text"], "これは 文です、")
        self.assertEqual(formatted[1]["text"], "（雑音） 次です。")
        self.assertEqual(result["summary"]["text_change_count"], 2)
        self.assertEqual(result["summary"]["boundary_warning_count"], 1)
        self.assertEqual(result["summary"]["noise_candidate_count"], 1)


    def test_off_mode_keeps_text_but_still_creates_review_result(self):
        original = [segment("s1", 0, 1, "SPEAKER_00", "文です 。。")]

        formatted, result = app.transcript_formatting_result(
            original,
            original,
            mode="off",
        )

        self.assertEqual(formatted[0]["text"], "文です 。。")
        self.assertEqual(result["mode"], "off")
        self.assertEqual(result["summary"]["text_change_count"], 0)
        self.assertEqual(result["summary"]["punctuation_warning_count"], 1)


    def test_result_exposes_verified_speaker_merge_and_self_introduction(self):
        original = [segment("s1", 0, 1, "SPEAKER_01", "田中です。")]
        repaired = [segment("s1", 0, 1, "SPEAKER_00", "田中です。")]

        _formatted, result = app.transcript_formatting_result(
            original,
            repaired,
            mode="advanced",
            speaker_names={"SPEAKER_00": "田中"},
            speaker_diagnostics={"speaker_aliases": {"SPEAKER_01": "SPEAKER_00"}},
            speaker_repair_summary={"alias_count": 1},
            finishing_stages={"speaker_identity": "completed", "cleanup": "completed"},
            ai_usage={
                "provider": "openai",
                "model": "test",
                "request_count": 3,
            },
            jev_usage={"request_count": 1},
        )

        self.assertEqual(result["speaker_aliases"], {"SPEAKER_01": "SPEAKER_00"})
        self.assertEqual(result["speaker_changes"], [
            {"segment_id": "s1", "from": "SPEAKER_01", "to": "SPEAKER_00"}
        ])
        self.assertEqual(result["self_introductions"], [
            {"speaker": "SPEAKER_00", "name": "田中", "status": "verified"}
        ])
        self.assertEqual(result["summary"]["llm_request_count"], 4)

    def test_recommended_mode_extracts_explicit_local_introduction_without_llm(self):
        original = [segment("s1", 0, 2, "SPEAKER_00", "私は田中と申します。")]

        _formatted, result = app.transcript_formatting_result(
            original,
            original,
            mode="recommended",
        )

        self.assertEqual(result["self_introductions"], [{
            "speaker": "SPEAKER_00",
            "name": "田中",
            "status": "local_candidate",
            "segment_id": "s1",
        }])

    def test_recommended_confirmation_and_replacement_are_reported(self):
        original = [segment("s1", 0, 2, "SPEAKER_00", "来週の予定は火曜")]
        repaired = [{
            **original[0],
            "text": "来週の予定は火曜日です。",
            "recommended_review": {
                "jev": {
                    "flagged": True,
                    "original_text": "来週の予定は火曜",
                    "correction_needed_probability": 0.88,
                },
                "llm": {
                    "confirmed_problem": True,
                    "replacement_applied": True,
                    "issue_type": "cutoff",
                    "original_text": "来週の予定は火曜",
                    "replacement_text": "来週の予定は火曜日です。",
                    "reason": "語尾の断裂を補正",
                    "effort": "high",
                    "context_before_count": 2,
                },
            },
        }]

        formatted, result = app.transcript_formatting_result(
            original,
            repaired,
            mode="recommended",
            finishing_stages={"recommended_cleanup": "completed"},
        )

        self.assertEqual(formatted[0]["text"], "来週の予定は火曜日です。")
        self.assertEqual(result["summary"]["recommended_candidate_count"], 1)
        self.assertEqual(result["summary"]["recommended_confirmed_count"], 1)
        self.assertEqual(result["summary"]["recommended_replacement_count"], 1)
        self.assertEqual(result["recommended_reviews"][0]["reason"], "語尾の断裂を補正")
