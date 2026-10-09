"""Reviewed selection keeps whole claims and never guesses mandatory knowledge."""
import copy
import unittest

from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.expert_knowledge_context import (
    ExpertKnowledgeContext, ExpertPackError, validate_packet, render_agent_request)
import test_expert_knowledge_context as fixtures


class SelectedExpertTests(unittest.TestCase):
    def setUp(self):
        source, claim = fixtures._record_pair()
        claims = {}
        for index in range(4):
            row = copy.deepcopy(claim)
            row["claim_id"] = f"claim-{index}"
            row["exceptions"] = [f"Exception {index}"]
            row["contradictions"] = [f"Conflicting finding {index}"]
            row["reviewer"]["target_sha256"] = contracts.claim_review_target(row)
            claims[row["claim_id"]] = row
        self.context = ExpertKnowledgeContext({"root_sha256": "f" * 64}, {source["source_id"]: source}, claims)
        self.policy = {"schema_version": 1, "pack_root_sha256": "f" * 64, "expert_id": "exp-00",
            "stage": "interpretation", "claim_hashes": {key: contracts.sha256_json(row) for key, row in claims.items()},
            "required_claim_ids": ["claim-0"], "task_claim_ids": ["claim-1"],
            "dependencies": {"claim-0": [], "claim-1": ["claim-2"], "claim-2": [], "claim-3": []}}
        self.review(self.policy)

    def review(self, policy):
        policy["reviewer"] = {"identity": "fixture-human-reviewer", "reviewed_at": "2026-01-01T00:00:00Z",
            "target_sha256": contracts.sha256_json({key: value for key, value in policy.items() if key != "reviewer"})}

    def packet(self, policy=None):
        return self.context.build_selected_expert_packet("exp-00", "question", "local", policy=policy or self.policy)

    def test_selection_keeps_mandatory_dependency_exception_conflict_and_v1(self):
        full = self.context.build_expert_packet("exp-00", "question", "local")
        packet = self.packet()
        self.assertEqual(packet["schema_version"], 2)
        self.assertEqual([row["claim"]["claim_id"] for row in packet["claims"]], ["claim-0", "claim-1", "claim-2"])
        self.assertEqual(packet["selection"]["omitted_claim_ids"], ["claim-3"])
        for row in packet["claims"]:
            self.assertEqual(row["claim"], self.context.claims[row["claim"]["claim_id"]])
        self.assertIn("Exception 0", render_agent_request(packet))
        self.assertIn("Conflicting finding 2", render_agent_request(packet))
        self.assertEqual(len(full["claims"]), 4)
        self.assertEqual(full["schema_version"], 1)
        self.assertLess(len(render_agent_request(packet)), len(render_agent_request(full)))

    def test_unreviewed_changed_unknown_or_stale_policy_is_rejected(self):
        variants = []
        value = copy.deepcopy(self.policy); value.pop("reviewer"); variants.append(value)
        value = copy.deepcopy(self.policy); value["required_claim_ids"] = []; variants.append(value)
        value = copy.deepcopy(self.policy); value["claim_hashes"]["claim-0"] = "a" * 64; self.review(value); variants.append(value)
        value = copy.deepcopy(self.policy); value["dependencies"]["claim-1"] = ["unknown"]; self.review(value); variants.append(value)
        value = copy.deepcopy(self.policy); value["claim_hashes"].pop("claim-3"); self.review(value); variants.append(value)
        value = copy.deepcopy(self.policy); value["pack_root_sha256"] = "a" * 64; self.review(value); variants.append(value)
        for value in variants:
            with self.subTest(value=value):
                with self.assertRaises(ExpertPackError): self.packet(value)

    def test_rehashed_packet_cannot_remove_required_claim_or_exception(self):
        packet = self.packet()
        packet["claims"] = packet["claims"][1:]
        packet["packet_sha256"] = contracts.sha256_json({key: value for key, value in packet.items() if key != "packet_sha256"})
        with self.assertRaises(ExpertPackError): validate_packet(packet)
        packet = self.packet()
        packet["claims"][0]["claim"]["exceptions"] = []
        packet["packet_sha256"] = contracts.sha256_json({key: value for key, value in packet.items() if key != "packet_sha256"})
        with self.assertRaises(ExpertPackError): validate_packet(packet)


if __name__ == "__main__": unittest.main()
