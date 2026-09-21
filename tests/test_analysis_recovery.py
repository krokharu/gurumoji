import unittest

from gurumoji.analysis_core import AnalysisContractError, validate_transition


class AnalysisRecoveryRulesTests(unittest.TestCase):
    def test_late_terminal_attempt_cannot_return_to_running(self):
        for state in ("committed", "reused", "failed", "cancelled", "not_applicable"):
            with self.subTest(state=state), self.assertRaises(AnalysisContractError):
                validate_transition("step", state, "running", "late.report")

    def test_publication_retry_is_the_only_terminal_like_retry_transition(self):
        validate_transition("publication", "failed", "publishing", "publication.retry")
        with self.assertRaises(AnalysisContractError):
            validate_transition("publication", "published", "publishing", "duplicate.publish")


if __name__ == "__main__":
    unittest.main()
