import unittest

from gurumoji.analysis_core import eligibility_assessment


class AnalysisEligibilityTests(unittest.TestCase):
    def test_hard_unknown_or_failure_blocks_but_warning_unknown_does_not(self):
        blocked = eligibility_assessment([], segment_count=0)
        self.assertEqual((blocked["execution"], blocked["inference_scope"]), ("blocked", "none"))

        allowed = eligibility_assessment([{"definition_id": "d1"}], segment_count=2)
        self.assertEqual(allowed["execution"], "allowed")
        self.assertEqual(allowed["status"], "eligible_with_warnings")
        precision = next(value for value in allowed["checks"] if value["dimension"] == "precision")
        self.assertEqual((precision["severity"], precision["outcome"]), ("warning", "unknown"))


if __name__ == "__main__":
    unittest.main()
