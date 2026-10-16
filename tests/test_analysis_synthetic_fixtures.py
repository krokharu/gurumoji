import json
from pathlib import Path
import unittest

from gurumoji.analysis_core import fingerprint, validate_definition
from gurumoji.analysis_pipeline import measure_segments


class AnalysisSyntheticFixtureTests(unittest.TestCase):
    def test_three_conversations_cover_shared_speakers_definitions_edits_and_codes(self):
        data = json.loads((Path(__file__).parent / "fixtures" / "analysis_three_conversations.json").read_text(encoding="utf-8"))
        self.assertTrue(data["synthetic"])
        conversations = data["conversations"]
        self.assertEqual(len(conversations), 3)
        self.assertEqual(len({value["analysis"]["item"]["id"] for value in conversations}), 3)
        definitions = {key: validate_definition(value, require_version=True)
                       for key, value in data["definitions"].items()}
        self.assertEqual(conversations[0]["definition_refs"], conversations[1]["definition_refs"])
        self.assertNotEqual(fingerprint(definitions["text_size_v1"]), fingerprint(definitions["duration_size_v2"]))
        self.assertEqual(definitions["text_size_v1"]["definition_id"], definitions["duration_size_v2"]["definition_id"])
        self.assertEqual(conversations[0]["speaker_person_ids"]["A"], conversations[1]["speaker_person_ids"]["B"])
        self.assertNotEqual(conversations[0]["speaker_person_ids"]["A"], conversations[1]["speaker_person_ids"]["A"])
        for conversation in conversations:
            analysis = conversation["analysis"]
            codes = {value["id"] for value in analysis["manual"]["codebook"]}
            self.assertTrue(any(value["annotation"]["codes"] for value in analysis["segments"]))
            self.assertTrue(all(set(value["annotation"]["codes"]) <= codes for value in analysis["segments"]))
            for edit in conversation["edits"]:
                segment = next(value for value in analysis["segments"] if value["id"] == edit["segment_id"])
                self.assertEqual(segment["text"], edit["text_after"])
                self.assertNotEqual(edit["text_before"], edit["text_after"])
                self.assertEqual(analysis["item"]["revision_count"], edit["source_revision_after"])
            rows = measure_segments(analysis, [definitions[key] for key in conversation["definition_refs"]])
            self.assertEqual(len(rows), len(analysis["segments"]))
            if conversation is conversations[2]:
                self.assertEqual([row["utterance_size"] for row in rows], [6, None])
            else:
                self.assertEqual([row["utterance_size"] for row in rows], [len(value["text"]) for value in analysis["segments"]])
        self.assertEqual(sum(len(value["edits"]) for value in conversations), 1)


if __name__ == "__main__":
    unittest.main()
