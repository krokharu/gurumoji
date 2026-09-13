import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class CustomVocabularyTests(unittest.TestCase):
    def test_normalizes_deduplicates_and_builds_a_compact_whisper_prompt(self):
        terms = app.normalize_custom_vocabulary(
            " グルモジ \nWhisperX\nグルモジ\n\n黒川研究室 "
        )

        self.assertEqual(terms, ("グルモジ", "WhisperX", "黒川研究室"))
        self.assertEqual(
            app.whisper_vocabulary_prompt(terms),
            "用語・固有名詞: グルモジ、WhisperX、黒川研究室。",
        )

    def test_rejects_an_overlong_registered_term(self):
        with self.assertRaisesRegex(ValueError, "80文字以内"):
            app.normalize_custom_vocabulary(["あ" * 81])

    def test_vocabulary_api_persists_terms_locally(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-vocabulary-") as temporary:
            target = Path(temporary) / "custom_vocabulary.json"
            with patch.object(app, "CUSTOM_VOCABULARY_FILE", target):
                client = app.app.test_client()
                saved = client.put(
                    "/api/custom-vocabulary",
                    json={"terms": ["グルモジ", "WhisperX", "グルモジ"]},
                )
                loaded = client.get("/api/custom-vocabulary")

            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.get_json()["terms"], ["グルモジ", "WhisperX"])
            self.assertEqual(loaded.status_code, 200)
            self.assertEqual(loaded.get_json()["terms"], ["グルモジ", "WhisperX"])
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
