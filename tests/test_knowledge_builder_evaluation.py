import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.evaluation import (
    build_evaluation_record, model_config_sha256, validate_evaluation_record, validate_repeat_pair,
)


def passing_categories():
    return {
        "knowledge_coverage": {"passed": 9, "total": 10},
        "mandatory_items": {"passed": 5, "total": 5},
        "evidence_support": {"passed": 57, "total": 60},
        "knowledge_organization": {"passed": 19, "total": 20},
        "content_understanding": {"passed": 14, "total": 15},
        "applicability": {"passed": 14, "total": 15},
        "abstention": {"passed": 10, "total": 10},
        "citation_integrity": {"passed": 40, "total": 40},
        # "passed" means the case had no privacy leakage.
        "privacy_leakage": {"passed": 40, "total": 40},
        "structure_integrity": {"passed": 40, "total": 40},
    }


def checklist(prefix, total, passed):
    population_ids = [f"{prefix}-item-{index}" for index in range(1, total + 1)]
    passed_ids = population_ids[:passed]
    return {"population_ids": population_ids,
            "population_sha256": contracts.sha256_json(sorted(population_ids)),
            "passed_item_ids": passed_ids}


def fixture(expert_id="exp-test", evaluation_id="eval-test", run_id="run-test"):
    critical_ids = []
    noncritical_ids = [f"claim-n-{index}" for index in range(1, 101)]
    return {
        "schema_version": 1, "evaluation_id": evaluation_id, "expert_id": expert_id,
        "pack_root_sha256": "a" * 64, "suite_id": "suite-final", "suite_sha256": "b" * 64,
        "rubric_version": "rubric-v1", "rubric_sha256": "c" * 64,
        "model_config_sha256": "d" * 64, "prompt_template_sha256": "e" * 64,
        "renderer_version": "renderer-v1", "rendered_request_sha256": "f" * 64,
        "rendered_request_set_sha256": "1" * 64,
        "repeat_index": 1, "run_id": run_id, "case_ids": [f"case-{i}" for i in range(1, 41)],
        "critical_claim_population_total": 0, "critical_claim_population_ids": critical_ids,
        "critical_claim_population_sha256": contracts.sha256_json(critical_ids),
        "critical_claim_reviewed_ids": [], "critical_claim_unsupported_ids": [],
        "noncritical_claim_population_total": len(noncritical_ids),
        "noncritical_claim_population_ids": noncritical_ids,
        "noncritical_claim_population_sha256": contracts.sha256_json(sorted(noncritical_ids)),
        "noncritical_claim_reviewed_ids": noncritical_ids[:60],
        "knowledge_checklists": {
            "knowledge_coverage": checklist("coverage", 10, 9),
            "mandatory_items": checklist("mandatory", 5, 5),
            "knowledge_organization": checklist("organization", 20, 19),
        },
        "categories": passing_categories(), "critical_failures": [], "blocking_violations": [],
        "created_at": "2026-09-27T00:00:00Z",
    }


class EvaluationGateTests(unittest.TestCase):
    def test_passes_one_expert_repeat_and_binds_all_versions_and_hashes(self):
        record = build_evaluation_record(fixture())
        self.assertEqual(record["verdict"], "pass")
        self.assertEqual(validate_evaluation_record(record), record)
        self.assertEqual(record["categories"]["applicability"], {"passed": 14, "total": 15})
        self.assertEqual(record["categories"]["abstention"], {"passed": 10, "total": 10})

    def test_one_expert_failure_is_not_rescued_by_aggregate_pass_rate(self):
        expert_a = build_evaluation_record(fixture("exp-a", "eval-a", "run-a"))
        failed_input = fixture("exp-b", "eval-b", "run-b")
        failed_input["repeat_index"] = 1
        failed_input["categories"]["applicability"] = {"passed": 13, "total": 15}
        expert_b = build_evaluation_record(failed_input)
        self.assertEqual(expert_a["verdict"], "pass")
        self.assertEqual(expert_b["verdict"], "fail")
        aggregate_passed, aggregate_total = 14 + 13, 15 + 15
        self.assertGreaterEqual(aggregate_passed * 100, aggregate_total * 90)
        # Gate evaluates records separately and has no aggregate-score API.
        self.assertNotEqual(expert_b["verdict"], "pass")

    def test_critical_and_blocking_failures_cannot_be_compensated_by_scores(self):
        value = fixture()
        value["critical_failures"] = [{"category": "applicability", "case_id": "case-1",
                                       "code": "critical_misapplication"}]
        record = build_evaluation_record(value)
        self.assertEqual(record["verdict"], "fail")
        value = fixture("exp-test", "eval-blocked", "run-blocked")
        value["blocking_violations"] = [{"case_id": "case-2", "code": "privacy_leakage"}]
        self.assertEqual(build_evaluation_record(value)["verdict"], "fail")

    def test_all_critical_claims_are_included_and_unsupported_ones_fail(self):
        value = fixture()
        critical_ids = [f"claim-critical-{index}" for index in range(1, 76)]
        value["critical_claim_population_total"] = len(critical_ids)
        value["critical_claim_population_ids"] = critical_ids
        value["critical_claim_population_sha256"] = contracts.sha256_json(sorted(critical_ids))
        value["critical_claim_reviewed_ids"] = critical_ids.copy()
        record = build_evaluation_record(value)
        self.assertEqual(record["verdict"], "pass")
        missing = dict(value)
        missing["evaluation_id"] = "eval-critical-missing"
        missing["critical_claim_reviewed_ids"] = critical_ids[:-1]
        with self.assertRaises(contracts.ContractError):
            build_evaluation_record(missing)
        unsupported = dict(value)
        unsupported["evaluation_id"] = "eval-critical-unsupported"
        unsupported["critical_claim_unsupported_ids"] = [critical_ids[0]]
        unsupported["critical_failures"] = [{"category": "evidence_support", "code": "critical_unsupported",
                                              "case_id": "case-1", "evidence_item_id": critical_ids[0]}]
        self.assertEqual(build_evaluation_record(unsupported)["verdict"], "fail")

    def test_noncritical_population_requires_min_sixty_or_all_smaller(self):
        value = fixture()
        small_ids = [f"claim-small-{index}" for index in range(1, 13)]
        value["evaluation_id"] = "eval-small-pop"
        value["noncritical_claim_population_total"] = 12
        value["noncritical_claim_population_ids"] = small_ids
        value["noncritical_claim_population_sha256"] = contracts.sha256_json(sorted(small_ids))
        value["noncritical_claim_reviewed_ids"] = small_ids.copy()
        value["categories"]["evidence_support"] = {"passed": 12, "total": 12}
        self.assertEqual(build_evaluation_record(value)["verdict"], "pass")

    def test_repeat_pair_requires_matching_bindings_and_two_passes(self):
        first = build_evaluation_record(fixture("exp-pair", "eval-pair-1", "run-pair-1"))
        second_input = fixture("exp-pair", "eval-pair-2", "run-pair-2")
        second_input["repeat_index"] = 2
        second = build_evaluation_record(second_input)
        pair = validate_repeat_pair(second, first)
        self.assertEqual([record["repeat_index"] for record in pair], [1, 2])

        for field, value, suffix in (("model_config_sha256", "2" * 64, "model"),
                                     ("pack_root_sha256", "3" * 64, "pack")):
            mismatched_input = dict(second_input)
            mismatched_input["evaluation_id"] = f"eval-pair-{suffix}"
            mismatched_input["run_id"] = f"run-pair-{suffix}"
            mismatched_input[field] = value
            mismatched = build_evaluation_record(mismatched_input)
            with self.subTest(field=field), self.assertRaises(contracts.ContractError):
                validate_repeat_pair(first, mismatched)

        failed_input = dict(second_input)
        failed_input["evaluation_id"] = "eval-pair-failed"
        failed_input["run_id"] = "run-pair-failed"
        failed_input["categories"]["applicability"] = {"passed": 13, "total": 15}
        failed = build_evaluation_record(failed_input)
        with self.assertRaises(contracts.ContractError):
            validate_repeat_pair(first, failed)

    def test_repeat_denominators_and_runtime_content_are_closed(self):
        value = fixture()
        value["categories"]["abstention"] = {"passed": 9, "total": 10}
        self.assertEqual(build_evaluation_record(value)["verdict"], "fail")
        value = fixture("exp-test", "eval-content-denominator", "run-content-denominator")
        value["categories"]["content_understanding"] = {"passed": 13, "total": 14}
        with self.assertRaises(contracts.ContractError):
            build_evaluation_record(value)
        value = fixture("exp-test", "eval-support-denominator", "run-support-denominator")
        value["categories"]["evidence_support"] = {"passed": 58, "total": 59}
        value["noncritical_claim_reviewed_ids"] = value["noncritical_claim_reviewed_ids"][:-1]
        with self.assertRaises(contracts.ContractError):
            build_evaluation_record(value)
        value = fixture("exp-test", "eval-repeat", "run-repeat")
        value["repeat_index"] = 3
        with self.assertRaises(contracts.ContractError):
            build_evaluation_record(value)
        value = fixture("exp-test", "eval-content", "run-content")
        value["answer"] = "fixture answer must never be persisted"
        with self.assertRaises(contracts.ContractError):
            build_evaluation_record(value)

    def test_model_config_hash_covers_revision_quantization_context_and_sampling(self):
        config = {"model_revision": "model@revision-1", "quantization": "Q4_K_M", "context_tokens": 8192,
                  "sampling": {"temperature": 0.1, "top_p": 0.9, "top_k": 40, "seed": 12, "max_tokens": 1024}}
        digest = model_config_sha256(config)
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(digest, model_config_sha256({**config, "context_tokens": 4096}))
        with self.assertRaises(contracts.ContractError):
            model_config_sha256({**config, "unhashed_field": "bad"})


if __name__ == "__main__":
    unittest.main()
