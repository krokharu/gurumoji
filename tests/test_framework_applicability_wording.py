"""Framework wording explains the existing product gate, not method adoption.

Case assignments below are synthetic researcher descriptions kept outside the
analysis payload: the product has no case-count input for fw-a3.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from gurumoji import method_experts as experts
from gurumoji.obsidian_layout import unpack


EXPERT_ID = "exp-framework-method"
ROOT = Path(__file__).resolve().parents[1] / "docs" / "program-vault"
NOTE = ROOT / experts.EXPERTS_DIR / "framework-method" / "01-Expert.md"
# Public base 2793c91d844331f01c25b1e7fd917a1b47f4175a, with only the
# fw-a3/a4/a5 messages removed. This checks every other definition field without
# requiring historical Git objects (including actors, AI brief/rights and steps).
BASE_CONTRACT_SHA256 = "7ee6f4b05fc8439503b0cb5cfd5a185379225ac45fdd23aaf00cfd7e18efca9c"


def synthetic(speaker_ids, *, participants=None):
    """Only values the real Catalog reads; no DB, models or researcher data."""
    return {
        "config": {"analysis_method": "framework", "research_question": "架空の比較の問い",
                   "group_by": "none"},
        "item": {"session_profile": {"moderator_guide": "架空の共通トピック"}},
        "automatic": {"overview": {"speaker_count": len(set(speaker_ids)),
                                   "participant_count": participants}},
        "manual": {"preparation": {"status": "confirmed", "order_verified": True},
                   "codebook": [], "coded_segment_count": 0,
                   "focus_group_plan": {"methods": [{"method_id": "framework", "role": "主"}]}},
    }


class FrameworkApplicabilityWordingTests(unittest.TestCase):
    def setUp(self):
        empty_local = tempfile.TemporaryDirectory(prefix="framework-no-overrides-")
        self.addCleanup(empty_local.cleanup)
        self.catalog = experts.ExpertCatalog(ROOT, local_root=empty_local.name)
        self.definition = self.catalog.definition(EXPERT_ID)

    def review(self, analysis):
        block = experts.review_for_analysis(analysis, self.catalog)
        self.assertEqual([row["expert_id"] for row in block["experts"]], [EXPERT_ID])
        review = block["experts"][0]
        checks = {row["id"]: row for row in review["checks"]}
        self.assertEqual(checks["fw-a6"]["result"], "human")
        return block, review, checks

    def test_two_speakers_one_researcher_case_passes_only_the_product_gate(self):
        case_speakers = {"case-one": ("speaker-a", "speaker-b")}
        self.assertEqual(len(case_speakers), 1)
        block, review, checks = self.review(synthetic(case_speakers["case-one"]))
        self.assertEqual(checks["fw-a3"]["result"], "pass")
        self.assertEqual(checks["fw-a3"]["observed"], {"speaker_count": 2.0, "min": 2})
        self.assertNotEqual(review["status"], "blocked")
        self.assertEqual(block["ai"]["mode"], "expert")
        self.assertEqual(block["ai"]["steps"], ["fw-p3", "fw-p6"])

    def test_one_speaker_two_researcher_cases_still_blocks_the_product_gate(self):
        case_speakers = {"case-one": ("speaker-a",), "case-two": ("speaker-a",)}
        self.assertEqual(len(case_speakers), 2)
        speakers = [speaker for group in case_speakers.values() for speaker in group]
        block, review, checks = self.review(synthetic(speakers))
        self.assertEqual(checks["fw-a3"]["result"], "fail")
        self.assertEqual(checks["fw-a3"]["observed"], {"speaker_count": 1.0, "min": 2})
        self.assertEqual(review["status"], "blocked")
        self.assertEqual(block["ai"]["mode"], "blocked")
        self.assertIn(checks["fw-a3"]["message"], block["ai"]["reason"])

    def test_moderator_and_participant_do_not_confirm_independent_cases(self):
        block, _, checks = self.review(synthetic(("moderator", "participant"), participants=1))
        self.assertEqual(checks["fw-a3"]["result"], "pass")
        self.assertEqual(checks["fw-a6"]["result"], "human")
        self.assertEqual(block["ai"]["mode"], "expert")
        body = NOTE.read_text(encoding="utf-8")
        self.assertIn("司会と参加者が各1人いても、独立した2ケースとはみなさない", body)
        self.assertIn("ケースの定義と方法の採否は研究者による確認が必要", body)
        self.assertIn("`fw-a3` の通過だけで確認済みにはならない", body)

    def test_zero_and_missing_speaker_count_keep_existing_results(self):
        for count, expected in ((0, "fail"), (None, "not_evaluable")):
            with self.subTest(speaker_count=count):
                analysis = synthetic(())
                analysis["automatic"]["overview"]["speaker_count"] = count
                _, _, checks = self.review(analysis)
                self.assertEqual(checks["fw-a3"]["result"], expected)
                self.assertEqual(checks["fw-a3"]["severity"], "block")

    def test_messages_name_the_product_boundary_without_equating_cases_and_speakers(self):
        checks = {row["id"]: row for row in self.definition["applicability_checks"]}
        message = checks["fw-a3"]["message"]
        self.assertIn("現製品の話者×コード比較には2話者以上が必要", message)
        self.assertIn("研究者が定義したケース数やフレームワーク法一般の適否を検査するものではありません", message)
        for check_id in ("fw-a3", "fw-a4", "fw-a5"):
            with self.subTest(check_id=check_id):
                self.assertIn("現製品の話者×コード比較", checks[check_id]["message"])
                self.assertNotIn("ケース（話者）", checks[check_id]["message"])
        self.assertIn("話者ラベルを用います", checks["fw-a4"]["message"])

    def test_all_definition_fields_except_three_messages_match_public_base(self):
        unchanged = deepcopy(self.definition)
        for check in unchanged["applicability_checks"]:
            if check["id"] in {"fw-a3", "fw-a4", "fw-a5"}:
                del check["message"]
        digest = hashlib.sha256(json.dumps(
            unchanged, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            default=str,
        ).encode("utf-8")).hexdigest()
        self.assertEqual(digest, BASE_CONTRACT_SHA256)
        gate = next(row for row in unchanged["applicability_checks"] if row["id"] == "fw-a3")
        self.assertEqual((gate["check"], gate["params"], gate["severity"]),
                         ("min_speakers", {"min": 2}, "block"))

    def test_explanation_only_revision_retains_version_and_needs_no_skill_pin(self):
        # method-rules.md, 専門家定義の登録 item 5 requires a version bump
        # for changed procedure, decisions or prohibitions; these are unchanged.
        props, _ = unpack(NOTE.read_text(encoding="utf-8"))
        self.assertEqual((props["definition_version"], self.definition["definition_version"]), (1, 1))
        self.assertFalse(any("framework" in note_id or "framework" in ref["path"]
                             for note_id, ref in experts.SKILL_NOTE_REFS.items()))


if __name__ == "__main__":
    unittest.main()
