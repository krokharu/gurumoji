"""Outline section tags: one rule for creation, display and analysis; no model or storage."""
import unittest

from gurumoji.services.outline_tags import (
    VERSION, assign, creation_assignment, ids_for_tags, outline_assignment, outline_sections, outline_tags,
)

def section(title, start, end, ids=()):
    return {"title": title, "start": start, "end": end, "segment_ids": list(ids)}

SECTIONS = [section("Intro", 1, 20, ids=["a"]), section("Overlap", 10, 20, ids=["c", "a"]), section("Later", 21, 30)]
SEGMENTS = [{"id": "i", "start": 0.5}, {"id": "a", "start": 1}, {"id": "b", "start": 12}, {"id": "c", "start": 15},
            {"id": "g", "start": None}, {"id": "d", "start": 20.5}, {"id": "e", "start": 25}, {"id": "f", "start": 40}]

class OutlineTagTests(unittest.TestCase):
    def test_every_utterance_gets_one_section_cited_or_inferred(self):
        self.assertEqual(assign(outline_sections(SECTIONS), SEGMENTS), {
            "i": {"tag": "S01", "basis": "inferred"},  # before the first section
            "a": {"tag": "S01", "basis": "listed"},    # cited twice: the earliest section
            "b": {"tag": "S02", "basis": "inferred"},  # the latest section started by 12s
            "c": {"tag": "S02", "basis": "listed"},
            "g": {"tag": "S02", "basis": "inferred"},  # no time: the previous utterance's section
            "d": {"tag": "S02", "basis": "inferred"},  # S03 starts at 21s
            "e": {"tag": "S03", "basis": "inferred"},
            "f": {"tag": "S03", "basis": "inferred"},  # after the last section's span
        })

    def test_creation_saves_the_map_and_display_reuses_it_until_utterances_change(self):
        outline = {"sections": SECTIONS}
        outline["section_assignment"] = creation_assignment(outline, SEGMENTS)
        shown = outline_assignment(outline, SEGMENTS)
        self.assertFalse(shown["derived"])
        self.assertEqual(shown["version"], VERSION)
        self.assertEqual([(s["tag"], s["count"], s["listed"], s["inferred"]) for s in shown["sections"]],
                         [("S01", 2, 1, 1), ("S02", 4, 1, 3), ("S03", 2, 0, 2)])
        changed = SEGMENTS + [{"id": "new", "start": 26}]
        recomputed = outline_assignment(outline, changed)
        self.assertTrue(recomputed["derived"])
        self.assertEqual(recomputed["segments"]["new"], {"tag": "S03", "basis": "inferred"})
        self.assertIsNone(outline_assignment({"sections": []}, SEGMENTS))
        self.assertIsNone(outline_assignment(None, SEGMENTS))

    def test_legacy_outline_without_saved_map_is_derived_by_the_same_rule(self):
        shown = outline_assignment({"sections": SECTIONS}, SEGMENTS)
        self.assertTrue(shown["derived"])
        self.assertEqual(shown["segments"], assign(outline_sections(SECTIONS), SEGMENTS))

    def test_analysis_snapshot_tags_use_the_same_rule(self):
        rows = [{**value, "title_source": "outline"} for value in SECTIONS]
        rows.append({"title": "Topic model span", "start": 30, "end": 50, "segment_ids": [], "title_source": "timeline"})
        evidence = [{"evidence_id": "ev_" + s["id"], "utterance_id": s["id"], "start": s["start"], "excluded": False}
                    for s in SEGMENTS]
        evidence.append({"evidence_id": "ev_x", "utterance_id": "x", "start": 5, "excluded": True})
        result = outline_tags({"analysis": {"session_outline": {"result": {"rows": rows}}}, "evidence": evidence})
        expected = assign(outline_sections(SECTIONS), SEGMENTS)
        self.assertEqual(result["tags"], {"ev_" + key: value["tag"] for key, value in expected.items()})
        self.assertEqual([(g["tag"], g["count"]) for g in result["sections"]], [("S01", 2), ("S02", 4), ("S03", 2)])
        self.assertIsNone(outline_tags({"analysis": {}, "evidence": []}))

    def test_ids_for_tags_keep_index_order_once(self):
        index = [("e1", "S02"), ("e2", "S01"), ("e3", "S02")]
        self.assertEqual(ids_for_tags(index, ["S02"]), ["e1", "e3"])

if __name__ == "__main__":
    unittest.main()
