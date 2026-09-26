import unittest

import app


class AiScalingTests(unittest.TestCase):
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
