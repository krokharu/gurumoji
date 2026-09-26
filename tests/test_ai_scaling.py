import json
import unittest

import app


class AiScalingTests(unittest.TestCase):
    def test_cleanup_chunking_uses_character_budget_without_small_fixed_batches(self):
        from gurumoji.ai_finishing import cleanup_batches, fragments

        segments = [
            {"id": f"s{index}", "speaker": f"SPEAKER_{index % 8:02d}", "text": "発話" * 20}
            for index in range(435)
        ]
        records = [{key: row[key] for key in ("id", "speaker", "text")} for row in fragments(segments)]

        batches = cleanup_batches(records)

        self.assertEqual(sum(len(batch) for batch in batches), 435)
        # The character budget, not a small item count, closes every batch but the last.
        self.assertTrue(all(len(batch) > 80 for batch in batches[:-1]))
        self.assertTrue(all(len(json.dumps(batch, ensure_ascii=False)) <= 10000 + 2 * len(batch)
                            for batch in batches))

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
