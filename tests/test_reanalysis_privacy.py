"""再分析時の役割別配送と除外範囲を合成データで検証する。"""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
from gurumoji.services.model_context import restored_reference_context


class ReanalysisPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(AnalysisOrchestrationService)
        self.excluded = {"utterance_id": "excluded-u", "evidence_id": "excluded-e",
                         "text": "SECRET-EXCLUDED-TEXT", "excluded": True}
        self.source = {"source_analysis_id": "result_prior", "source_run_id": "run_prior",
                       "source_result_id": "result_prior", "input_hash": "input-v1", "raw_hash": "hash",
                       "human_prompt": "Examine differences", "original_question": "Question",
                       "content": {"summary": "public summary", "claims": [
                           {"text": "SECRET-EXCLUDED-TEXT", "evidence_ids": ["excluded-e"]},
                           {"text": "public finding", "evidence_ids": ["public-e"]},
                           {"text": "hidden id", "evidence_ids": ["excluded-e"]},
                           {"text": "hidden utterance", "utterance_id": "excluded-u"}]}}
        self.run = {"initial_id": "initial", "config": {"reanalysis": copy.deepcopy(self.source)}}

    def context(self, role, finding=False):
        task = {"role": role, "intent": {"kind": "finding_review" if finding else "analysis"}}
        base = {"task": {"role": role, "phase": "specialists"}, "question": "Question",
                "data_version": "input-v1", "raw_evidence": [{"evidence_id": "public-e",
                "utterance_id": "public-u", "text": "public text"}], "coverage": {}}
        with patch.object(self.service, "_base_context", return_value=base), \
             patch.object(self.service, "_initial", return_value={"evidence": [self.excluded]}), \
             patch.object(self.service, "_recheck_review_binding"), \
             patch.object(self.service, "build_review_resources", side_effect=lambda db, run, task, ctx: dict(ctx)):
            return self.service._context(None, self.run, task)

    def sent(self, role, context):
        packets = []
        def reply(*args, **kwargs):
            packets.append((args, kwargs))
            return {"summary": "synthetic", "claims": []}
        resolve, runner = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a, **k: {"fits": True, "output_reserve": 1600})
        options = resolve({"model_context_version": 1, "context_reference_version": 1,
                           "specialist_orchestration_version": 0})
        options["_reference_evidence"] = [{"evidence_id": "public-e", "utterance_id": "public-u"}]
        runner(role, context, options, lambda: None, lambda _: None)
        args, kwargs = packets[0]
        return restored_reference_context(args[4], kwargs.get("data_messages")), (args, kwargs)

    def test_verification_receives_instruction_but_no_old_claims(self):
        context = self.context("verification")
        sent, packet = self.sent("verification", context)
        self.assertEqual(sent["human_prompt"], self.source["human_prompt"])
        self.assertNotIn("reanalysis", sent)
        self.assertEqual(sent["reanalysis_origin"]["source_result_id"], "result_prior")
        self.assertNotIn("public finding", str(packet))
        self.assertNotIn("SECRET-EXCLUDED-TEXT", str(packet))

    def test_core_source_is_sanitized_in_provider_packet(self):
        context = self.context("core")
        sent, packet = self.sent("core", context)
        self.assertEqual(sent["human_prompt"], self.source["human_prompt"])
        self.assertTrue(sent["reanalysis"]["excluded_content_omitted"])
        self.assertEqual(sent["reanalysis"]["content"]["claims"][0]["text"], "public finding")
        self.assertEqual(len(sent["reanalysis"]["content"]["claims"]), 1)
        for secret in ("SECRET-EXCLUDED-TEXT", "excluded-u", "excluded-e"):
            self.assertNotIn(secret, str(packet))
        self.assertEqual(self.run["config"]["reanalysis"], self.source)

    def test_finding_review_receives_prompt_without_prior_reanalysis(self):
        context = self.context("critic", finding=True)
        self.assertEqual(context["human_prompt"], self.source["human_prompt"])
        self.assertNotIn("reanalysis", context)
        self.assertEqual(context["reanalysis_origin"]["source_result_id"], "result_prior")


if __name__ == "__main__":
    unittest.main()
