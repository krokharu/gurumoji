import unittest

import app


class AiScalingTests(unittest.TestCase):
    def test_cleanup_chunking_uses_character_budget_without_small_fixed_batches(self):
        segments = [
            {"speaker": f"SPEAKER_{index % 8:02d}", "text": "発話" * 20}
            for index in range(435)
        ]

        chunks = app.chunk_segments(segments)

        self.assertEqual([len(chunk) for chunk in chunks], [80, 80, 80, 80, 80, 35])

    def test_community_diarization_is_the_default(self):
        self.assertEqual(
            app.DIARIZATION_MODEL,
            "pyannote/speaker-diarization-community-1",
        )

    def test_api_request_label_is_explicitly_cumulative(self):
        page = app.app.test_client().get("/").data.decode("utf-8")
        self.assertEqual(page.count("累計API呼び出し"), 2)


if __name__ == "__main__":
    unittest.main()
