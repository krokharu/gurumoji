"""Synthetic map-stage planning and acceptance; no model, API, user DB or Vault."""
import copy
import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import full_text_pipeline as pipeline

def rows(lengths, prefix="ev"):
    return [{"evidence_id": f"{prefix}{i:03d}", "speaker": "A" if i % 2 else "B", "text": "あ" * n}
            for i, n in enumerate(lengths)]

def tags_for(evidence, sizes):
    tags, index = {}, 0
    for section, size in enumerate(sizes, 1):
        for row in evidence[index:index + size]:
            tags[row["evidence_id"]] = f"S{section:02d}"
        index += size
    return tags

class PlanTests(unittest.TestCase):
    def test_every_character_and_id_is_planned_once(self):
        evidence = rows([30, 0, 250, 12, 7, 90] * 20)
        plan = pipeline.plan_chunks(evidence, tags_for(evidence, [13, 40, 7, 60]), input_version="v1",
                                    body_chars=400, max_rows=25)
        pipeline.verify_plan(plan, evidence)
        self.assertEqual(sum(chunk["chars"] for chunk in plan["chunks"]), sum(len(r["text"]) for r in evidence))
        planned = [segment[0] for chunk in plan["chunks"] for segment in chunk["segments"]]
        self.assertEqual(list(dict.fromkeys(planned)), [r["evidence_id"] for r in evidence])
        self.assertTrue(all(chunk["chars"] <= 400 and len(chunk["segments"]) <= 25 for chunk in plan["chunks"]))

    def test_small_sections_stay_whole_and_large_sections_start_a_chunk(self):
        evidence = rows([10] * 30)
        plan = pipeline.plan_chunks(evidence, tags_for(evidence, [5, 5, 20]), input_version="v1", body_chars=120)
        self.assertEqual([chunk["sections"] for chunk in plan["chunks"]], [["S01", "S02"], ["S03"], ["S03"]])

    def test_long_utterance_is_split_by_offset(self):
        evidence = rows([5, 1000, 5])
        plan = pipeline.plan_chunks(evidence, None, input_version="v1", body_chars=300)
        long = [s for chunk in plan["chunks"] for s in chunk["segments"] if s[0] == "ev001"]
        self.assertEqual([(s[1], s[2]) for s in long], [(0, 300), (300, 600), (600, 900), (900, 1000)])
        pipeline.verify_plan(plan, evidence)

    def test_plan_is_deterministic_and_bound_to_input_version(self):
        evidence = rows([20] * 10)
        first = pipeline.plan_chunks(evidence, None, input_version="v1", body_chars=50)
        self.assertEqual(first, pipeline.plan_chunks(evidence, None, input_version="v1", body_chars=50))
        other = pipeline.plan_chunks(evidence, None, input_version="v2", body_chars=50)
        self.assertNotEqual(first["chunks"][0]["chunk_id"], other["chunks"][0]["chunk_id"])

    def test_tampered_or_stale_plan_is_rejected(self):
        evidence = rows([20] * 10)
        plan = pipeline.plan_chunks(evidence, None, input_version="v1", body_chars=50)
        tampered = copy.deepcopy(plan)
        tampered["chunks"][0]["segments"].pop()
        with self.assertRaises(AnalysisContractError) as caught:
            pipeline.verify_plan(tampered, evidence)
        self.assertEqual(caught.exception.code, "map_plan_mismatch")
        changed = copy.deepcopy(evidence)
        changed[3]["text"] += "追加"
        with self.assertRaises(AnalysisContractError):
            pipeline.verify_plan(plan, changed)

    def test_coverage_counts_only_accepted_chunks(self):
        evidence = rows([5, 1000, 5])
        plan = pipeline.plan_chunks(evidence, None, input_version="v1", body_chars=300)
        ids = [chunk["chunk_id"] for chunk in plan["chunks"]]
        partial = pipeline.coverage(plan, ids[:2])
        self.assertFalse(partial["complete"])
        self.assertEqual(partial["evidence_read_count"], 1)  # the split utterance is not read yet
        self.assertEqual(pipeline.coverage(plan, ids)["evidence_read_count"], 3)
        self.assertTrue(pipeline.coverage(plan, ids)["complete"])

class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.evidence = rows([40] * 6)
        self.plan = pipeline.plan_chunks(self.evidence, None, input_version="v1", body_chars=120)
        self.chunk = self.plan["chunks"][0]
        self.good = {"chunk_id": self.chunk["chunk_id"], "uncovered_notes": "",
                     "observations": [{"evidence_ids": ["u1", "u2"], "statement": "辛さの好みが分かれる",
                                       "kind": "pattern", "reuse_theme": "", "new_theme": "辛さ"}]}

    def test_packet_contains_only_this_chunk(self):
        packet = pipeline.chunk_packet(self.plan, self.chunk, self.evidence, research_question="問い")
        self.assertEqual([row[0] for row in packet["utterances"]["rows"]], ["u1", "u2", "u3"])
        self.assertNotIn("ev000", str(packet))  # long stable IDs stay with the Handler
        self.assertEqual(pipeline.chunk_refs(self.chunk), {"u1": "ev000", "u2": "ev001", "u3": "ev002"})
        self.assertEqual(packet["chunk"]["of"], len(self.plan["chunks"]))

    def test_schema_limits_ids_to_the_chunk(self):
        schema = pipeline.map_schema(self.chunk)
        items = schema["properties"]["observations"]["items"]["properties"]["evidence_ids"]["items"]
        self.assertEqual(items["enum"], ["u1", "u2", "u3"])
        self.assertEqual(schema["properties"]["chunk_id"]["enum"], [self.chunk["chunk_id"]])

    def test_valid_and_empty_results_are_accepted(self):
        accepted = pipeline.accept_extract(self.chunk, self.good)
        self.assertEqual(accepted["observations"][0]["evidence_ids"], ["ev000", "ev001"])  # mapped back
        empty = {**self.good, "observations": []}
        self.assertEqual(pipeline.accept_extract(self.chunk, empty)["observations"], [])

    def test_heading_is_reused_or_new_and_never_both_or_neither(self):
        known = ("辛さ", "価格")
        def with_heading(reuse, new):
            raw = copy.deepcopy(self.good)
            raw["observations"][0].update(reuse_theme=reuse, new_theme=new)
            return raw
        accepted = pipeline.accept_extract(self.chunk, with_heading("辛さ", ""), known)
        self.assertEqual(accepted["observations"][0]["theme"], "辛さ")
        self.assertEqual(pipeline.accept_extract(self.chunk, with_heading("", " 新しい見出し "), known)
                         ["observations"][0]["theme"], "新しい見出し")
        for raw in (with_heading("辛さ", "別の見出し"), with_heading("", ""), with_heading("", "  "),
                    with_heading("示していない", "")):
            with self.subTest(raw=raw["observations"][0]["reuse_theme"] + "/" + raw["observations"][0]["new_theme"]), \
                    self.assertRaises(AnalysisContractError) as caught:
                pipeline.accept_extract(self.chunk, raw, known)
            self.assertEqual(caught.exception.code, "map_theme_invalid")
        schema = pipeline.map_schema(self.chunk, known)
        reuse = schema["properties"]["observations"]["items"]["properties"]["reuse_theme"]
        self.assertEqual(reuse["enum"], ["", "辛さ", "価格"])

    def test_invalid_results_are_rejected_without_repair(self):
        cases = {
            "map_chunk_mismatch": lambda r: r.update(chunk_id="chk_other"),
            "map_evidence_out_of_chunk": lambda r: r["observations"][0].update(evidence_ids=["u4"]),
            "map_text_invalid": lambda r: r["observations"][0].update(statement="   "),
            "map_shape_invalid": lambda r: r["observations"][0].update(kind="supports"),
        }
        for code, change in cases.items():
            raw = copy.deepcopy(self.good)
            change(raw)
            with self.subTest(code=code), self.assertRaises(AnalysisContractError) as caught:
                pipeline.accept_extract(self.chunk, raw)
            self.assertEqual(caught.exception.code, code)
        too_many = copy.deepcopy(self.good)
        too_many["observations"] *= pipeline.MAX_OBSERVATIONS + 1
        with self.assertRaises(AnalysisContractError):
            pipeline.accept_extract(self.chunk, too_many)
        extra = {**copy.deepcopy(self.good), "hook_requests": []}
        with self.assertRaises(AnalysisContractError):
            pipeline.accept_extract(self.chunk, extra)

if __name__ == "__main__":
    unittest.main()
