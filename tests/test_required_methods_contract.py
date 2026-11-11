import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.orchestration_required_methods import (
    method_catalog, required_intents, required_progress, validate_required_methods,
)


class RequiredMethodsContractTest(unittest.TestCase):
    def test_validation_and_intents(self):
        self.assertEqual(len(method_catalog()), 4)
        self.assertEqual(validate_required_methods([]), [])
        for invalid in (None, "participation", ["unknown"], ["participation", "participation"], [[]]):
            with self.assertRaises(AnalysisContractError):
                validate_required_methods(invalid)
        intent = required_intents(["label_frequency"], "問い")[0]
        self.assertEqual((intent["label_field"], intent["label_dependent"]), ("codes", True))

    def test_review_and_core_integration_and_staleness(self):
        task = {"role": "statistics", "method_id": "label_frequency", "task_id": "t", "result_id": "r",
                "status": "succeeded", "validation_status": "valid", "dataset_version": "v1", "annotation_version": 2,
                "codebook_version": 1}
        results = [{"result_id": "r", "validation_status": "valid"}]
        decisions = [{"role": "orchestrator", "result_id": "report", "result_assessments": [
            {"result_id": "r", "disposition": "reject", "reason": "限界が大きい"}]},
            {"role": "core", "domain_report_ids": ["report"]}]
        def progress(**kwargs):
            return required_progress(["label_frequency"], [task], results, decisions,
                                     dataset_version="v1", annotation_version=kwargs.get("version", 2),
                                     codebook_version=kwargs.get("codebook", 1),
                                     run_stale=kwargs.get("stale", False))[0]
        self.assertTrue(progress()["complete"])
        self.assertEqual(progress(version=3)["status"], "stale")
        self.assertEqual(progress(codebook=2)["status"], "stale")
        self.assertFalse(progress(stale=True)["complete"])
        decisions[0]["result_assessments"][0]["disposition"] = "defer"
        self.assertFalse(progress()["complete"])
        decisions[0]["result_assessments"][0]["disposition"] = "adopt"
        decisions[1]["domain_report_ids"] = []
        self.assertFalse(progress()["complete"])


if __name__ == "__main__":
    unittest.main()
