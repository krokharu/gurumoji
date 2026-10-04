"""Label-version-aware deterministic statistics. Entirely synthetic."""
import copy
import unittest
from unittest.mock import patch

from gurumoji.services.analysis_orchestration_methods import run_orchestration_method


class OrchestrationMethodTests(unittest.TestCase):
    def fixture(self):
        return {"evidence": [{"evidence_id": "e1", "utterance_id": "u1", "excluded": False},
                             {"evidence_id": "e2", "utterance_id": "u2", "excluded": False},
                             {"evidence_id": "e3", "utterance_id": "u3", "excluded": False},
                             {"evidence_id": "e4", "utterance_id": "u4", "excluded": True}],
                "orchestration_task": {"intent": {"label_field": "codes", "evidence_ids": []},
                                       "dataset_version": "synthetic", "annotation_version": 1, "codebook_version": 1},
                "orchestration_labels": {"u1": {"codes": ["price", "price", "usability"]},
                                         "u2": {"codes": ["price"]}, "u3": {}, "u4": {"codes": ["excluded-secret"]}}}

    def test_counts_deduplicate_each_utterance_and_keep_missing_denominator(self):
        snapshot = self.fixture(); original = copy.deepcopy(snapshot)
        result = run_orchestration_method("label_frequency", snapshot)
        self.assertEqual(result["denominator"], 3)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["rows"][0], {"label": "price", "count": 2, "denominator": 3,
                                            "proportion": 2/3, "evidence_ids": ["e1", "e2"]})
        self.assertNotIn("excluded-secret", str(result))
        self.assertEqual(snapshot, original)

    def test_new_annotation_version_is_recomputed_not_cached(self):
        snapshot = self.fixture()
        old = run_orchestration_method("label_frequency", snapshot)
        snapshot["orchestration_task"]["annotation_version"] = 2
        snapshot["orchestration_labels"]["u2"]["codes"] = ["usability"]
        new = run_orchestration_method("label_frequency", snapshot)
        self.assertEqual(new["rows"][0]["label"], "usability")
        self.assertEqual(new["annotation_version"], 2)
        self.assertEqual(old["rows"][0]["label"], "price")
        self.assertEqual(old["annotation_version"], 1)

    def test_subset_recomputes_scope_and_denominator(self):
        snapshot = self.fixture()
        snapshot["orchestration_task"]["intent"]["evidence_ids"] = ["e2"]
        result = run_orchestration_method("label_frequency", snapshot)
        self.assertEqual((result["denominator"], result["rows"][0]["count"]), (1, 1))
        self.assertEqual(result["manifest"]["scope"], "selected")
        self.assertEqual(result["manifest"]["evidence_ids"], ["e2"])

    def test_unknown_excluded_ids_and_unsupported_fields_are_rejected(self):
        for ids in (["e4"], ["unavailable"]):
            snapshot = self.fixture(); snapshot["orchestration_task"]["intent"]["evidence_ids"] = ids
            with self.assertRaises(ValueError):
                run_orchestration_method("label_frequency", snapshot)
        snapshot = self.fixture(); snapshot["orchestration_task"]["intent"]["label_field"] = "memo"
        with self.assertRaises(ValueError):
            run_orchestration_method("label_frequency", snapshot)

    def test_unexpected_label_type_never_becomes_invented_category(self):
        snapshot = self.fixture(); snapshot["orchestration_labels"]["u1"]["codes"] = {"bad": "shape"}
        with self.assertRaises(ValueError):
            run_orchestration_method("label_frequency", snapshot)

    def test_existing_fixed_methods_use_the_original_adapter(self):
        snapshot = self.fixture()
        with patch("gurumoji.services.analysis_orchestration_methods.run_analysis_pipeline_method", return_value={"original": True}) as original:
            self.assertEqual(run_orchestration_method("participation", snapshot), {"original": True})
        original.assert_called_once_with("participation", snapshot)


if __name__ == "__main__":
    unittest.main()
