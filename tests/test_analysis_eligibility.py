import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import CAPABILITIES, AnalysisContractError, eligibility_assessment
import test_analysis_definition_safety as support


class AnalysisEligibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gurumoji-eligibility-")
        self.addCleanup(temporary.cleanup)
        self.enterContext(patch.dict(os.environ, {
            "MOJIOKOSI_DATA_DIR": str(Path(temporary.name) / "data"),
            "MOJIOKOSI_OUTPUT_DIR": str(Path(temporary.name) / "output"),
            "MOJIOKOSI_BACKUP_DIR": str(Path(temporary.name) / "backup"),
        }))

    def test_hard_unknown_or_failure_blocks_but_warning_unknown_does_not(self):
        blocked = eligibility_assessment([], segment_count=0)
        self.assertEqual((blocked["execution"], blocked["inference_scope"]), ("blocked", "none"))

        allowed = eligibility_assessment([{"definition_id": "d1"}], segment_count=2)
        self.assertEqual(allowed["execution"], "allowed")
        self.assertEqual(allowed["status"], "eligible_with_warnings")
        precision = next(value for value in allowed["checks"] if value["dimension"] == "precision")
        self.assertEqual((precision["severity"], precision["outcome"]), ("warning", "unknown"))

    def test_each_supported_descriptive_method_passes_inference_validity(self):
        for method in ("frequency", "descriptive"):
            with self.subTest(method=method):
                result = eligibility_assessment([{"definition_id": "d1", "method": method}], segment_count=2)
                check = next(c for c in result["checks"] if c["dimension"] == "inference_validity")
                self.assertEqual((check["outcome"], check["reason_code"]), ("pass", "descriptive_scope_only"))
                self.assertEqual((result["execution"], result["inference_scope"]), ("allowed", "descriptive"))

    def test_non_descriptive_and_unknown_methods_stop_even_with_descriptive_definitions(self):
        for method in ("inferential_statistics", "interview_evaluation", "unknown_method", None, []):
            with self.subTest(method=method):
                result = eligibility_assessment([
                    {"definition_id": "descriptive", "method": "frequency"},
                    {"definition_id": "unsupported", "method": method},
                ], segment_count=2)
                check = next(c for c in result["checks"] if c.get("definition_id") == "unsupported"
                             and c["dimension"] == "inference_validity")
                self.assertEqual((check["severity"], check["outcome"]), ("hard", "unknown"))
                self.assertEqual((result["execution"], result["status"], result["inference_scope"]),
                                 ("blocked", "ineligible", "none"))

    def test_capability_scope_and_availability_determine_the_gate(self):
        capability = CAPABILITIES["methods"]["manual_measurement"]
        for scope in ("inferential", "unknown", None):
            with self.subTest(scope=scope), patch.dict(capability["definition_methods"]["descriptive"],
                                                     {"inference_scope": scope}):
                result = eligibility_assessment([{"definition_id": "d1", "method": "descriptive"}], segment_count=2)
                self.assertEqual(result["execution"], "blocked")
        with patch.dict(capability, {"status": "unavailable"}):
            result = eligibility_assessment([{"definition_id": "d1"}], segment_count=2)
            self.assertEqual(result["execution"], "blocked")
        with patch.dict(CAPABILITIES["methods"], {"manual_measurement": {}}):
            result = eligibility_assessment([{"definition_id": "d1"}], segment_count=2)
            self.assertEqual(result["execution"], "blocked")

    def fixture(self):
        case = support.DefinitionSafetyTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.save()
        return case

    def test_non_descriptive_request_is_rejected_before_pipeline_creation(self):
        case = self.fixture()
        with self.assertRaises(AnalysisContractError) as caught:
            case.service.save_definition("synthetic", "text_size", support.definition(method="inferential_statistics"))
        self.assertEqual(caught.exception.code, "method_unavailable")
        with case.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM analysis_pipeline_requests").fetchone()[0], 0)

    def test_non_descriptive_capability_stops_start_and_an_already_accepted_run_before_execution(self):
        case = self.fixture()
        pipeline_id = case.start()
        capability = CAPABILITIES["methods"]["manual_measurement"]["definition_methods"]["descriptive"]
        with patch.dict(capability, {"inference_scope": "inferential"}), \
                patch.object(case.service, "method_runner") as execute, \
                patch.object(case.service, "_schedule") as schedule:
            with self.assertRaises(AnalysisContractError) as caught:
                case.service.start("synthetic", case.payload(request_id="ineligible-new-request"),
                                   app_url="http://synthetic.invalid")
            self.assertEqual(caught.exception.code, "ineligible")
            with self.assertRaises(AnalysisContractError) as caught:
                case.service._run(pipeline_id, "http://synthetic.invalid")
            self.assertEqual(caught.exception.code, "ineligible")
            execute.assert_not_called()
            schedule.assert_not_called()
        self.assertEqual(case.saved, [])
        with case.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM analysis_pipeline_requests").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
