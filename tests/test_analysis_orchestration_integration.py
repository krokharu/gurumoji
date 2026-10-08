"""Full Flask/SQLite/real-adapter integration with synthetic provider responses."""
import json
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support


class OrchestrationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url + "/orchestration"
        self.config_patch = patch.object(app, "load_token_config", return_value=app.TokenConfig(lmstudio_model="synthetic-local"))
        self.config_patch.start(); self.addCleanup(self.config_patch.stop)
        self.service = app.analysis_orchestration_service()
        self.service.schedule = False
        # This legacy general-agent fixture supplies no expert_report. Typed
        # knowledge/outputs are exercised by test_analysis_typed_assets instead.
        self.service.expert_provider = None
        self.calls = []

    def payload(self, request_id="integration-run-request-0001"):
        value = self.client.get(self.fixture.url).get_json()
        return {"request_id": request_id, "source_revision": value["item"]["revision_count"],
                "analysis_revision": value["item"]["analysis_revision"],
                "question": "合成会話の発話内容と参加量を観察する", "provider": "lmstudio",
                "provider_policy": "local_only", "stop_mode": "auto", "max_iterations": None,
                "time_limit_seconds": None, "max_calls": 20, "max_tasks": 40}

    def response(self, provider, key, model, system, prompt, schema_name, schema, check, usage, base, timeout_seconds=240):
        check()
        context = json.loads(prompt)
        role = schema_name.removeprefix("analysis_orchestration_")
        self.calls.append((role, context, provider, model))
        usage({"provider": provider, "model": model, "request_count": 1,
               "reported": True, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        evidence_id = context["raw_evidence"][0]["evidence_id"]
        claim = {"claim_id": "observed-price", "text": "合成会話に価格の発話がある", "kind": "observation", "evidence_ids": [evidence_id]}
        if role == "core":
            intents = []
            if context["task"]["iteration"] == 1:
                intents = [{"role": target, "kind": "analysis", "result_id": "",
                            "question": "対象全体の原文か参加量を確認", "why_now": "問いの根拠を集める",
                            "success_criteria": "根拠IDまたは集計結果を提示",
                            "method_id": "participation" if target == "statistics" else "",
                            "evidence_ids": [], "importance": "high", "importance_reason": "中心となる証拠",
                            "dependencies": [], "label_dependent": False, "replicate_id": ""}
                           for target in ("interpretation", "statistics", "verification")]
            return {"summary": "発話の観察は支持されるが、人物属性を推定しない。", "claims": [claim],
                    "intents": intents, "stop": None if intents else {"reason": "question_satisfied", "summary": "対象範囲で回答", "unresolved": []},
                    "critique_responses": [], "label_decisions": []}
        result = {"summary": "合成会話の原文を確認", "claims": [claim], "analysis_requests": [], "label_patches": []}
        if role == "critic":
            result.update(review_status="no_issues", reviewed_scope="限定的な観察と終了案", limitations="合成会話のみ", issues=[])
        return result

    def start(self, payload=None):
        response = self.client.post(self.url, json=payload or self.payload())
        self.assertEqual(response.status_code, 202, response.get_json())
        return response.get_json()["run"]["run_id"]

    def test_real_adapter_loop_full_initial_export_and_no_poll_model_calls(self):
        with patch.object(app, "call_orchestration_ai_json", side_effect=self.response):
            rid = self.start()
            self.service.run(rid)
            value = self.client.get(self.url + "/" + rid).get_json()["run"]
            self.assertEqual(value["status"], "completed", value)
            self.assertEqual(value["review_status"], "reviewed")
            self.assertEqual(set(c[0] for c in self.calls), {"core", "interpretation", "verification", "critic"})
            self.assertTrue(all(e["utterance_id"] != "x1" for c in self.calls for e in c[1].get("raw_evidence", [])))
            self.assertTrue(any(t["role"] == "statistics" and t["status"] == "succeeded" for t in value["tasks"]))
            self.assertEqual(value["usage"]["total_tokens"], 15 * len(self.calls))
            before = len(self.calls)
            for _ in range(3):
                self.client.get(self.url + "/" + rid)
                self.client.get(self.url)
            exported = self.client.get(self.url + "/" + rid + "/export.json").get_json()
            self.assertIn("initial", exported)
            self.assertIn("label_versions", exported)
            note = self.client.get(self.url + "/" + rid + "/export.md")
            self.assertEqual(note.status_code, 200)
            self.assertIn("完全な保存履歴", note.get_data(as_text=True))
            self.assertEqual(len(self.calls), before)
            original = exported["initial"]
            rid2 = self.start(self.payload("integration-run-request-0002"))
            self.assertEqual(self.service.result("content", rid2)["initial"], original)

    def test_service_identity_and_pending_cancel_survive_http_requests(self):
        rid = self.start()
        self.assertIs(self.service, app.analysis_orchestration_service())
        response = self.client.post(self.url + "/" + rid + "/cancel", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["run"]["status"], "cancelled")
        with patch.object(app, "call_orchestration_ai_json") as model:
            self.service.run(rid)
        model.assert_not_called()

    def test_actual_transport_has_no_hidden_retry(self):
        with patch.object(app.ai_client, "post_json", side_effect=app.ai_client.RetryableApiError("synthetic transient")) as post:
            with self.assertRaises(app.ai_client.RetryableApiError):
                app.call_orchestration_ai_json("openai", "synthetic", "synthetic", "s", "p", "analysis_orchestration_core", {})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["retry_delays"], ())

    def test_configured_call_timeout_reaches_http_worker(self):
        with patch.object(app.ai_client, "post_json", side_effect=RuntimeError("synthetic stop")) as post:
            with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
                app.call_orchestration_ai_json("openai", "synthetic", "synthetic", "s", "p",
                                              "analysis_orchestration_core", {}, timeout_seconds=420)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["timeout"], 420)

    def test_label_adoption_recomputes_real_code_method_and_preserves_initial(self):
        initial = None
        def response(*args):
            nonlocal initial
            context = json.loads(args[4]); role = args[5].removeprefix("analysis_orchestration_")
            if role == "core" and initial is None:
                # The initial builder is now durable/asynchronous. Capture its
                # completed immutable output before the first Core decision.
                initial = self.service.result("content", rid)["initial"]
            result = self.response(*args)
            if role == "interpretation":
                source = context["raw_evidence"][0]
                result["label_patches"] = [{
                    "utterance_id": source["utterance_id"], "field": "theme",
                    "old_value": context["labels"].get(source["utterance_id"], {}).get("theme"),
                    "new_value": "price", "reason": "原文中の価格への言及", "evidence_ids": [source["evidence_id"]],
                    "base_annotation_version": context["annotation_version"],
                    "codebook_version": context["task"]["codebook_version"],
                }]
            if role == "core":
                task = {"role": "statistics", "question": "固定版テーマの頻度を確認",
                        "why_now": "ラベル版に対応する集計が必要", "success_criteria": "対象数と欠測を保持",
                        "method_id": "label_frequency", "label_field": "theme", "evidence_ids": [],
                        "importance": "high", "importance_reason": "解釈への影響", "label_dependent": True}
                if context["task"]["iteration"] == 1:
                    result["intents"] = [result["intents"][0], task]
                elif context["task"]["iteration"] == 2:
                    result["label_decisions"] = [{"proposal_id": value["proposal_id"], "disposition": "adopt", "reason": "原文根拠を確認"}
                                                 for value in context["label_proposals"]]
                    result["intents"] = [task]; result["stop"] = None
            return result
        with patch.object(app, "call_orchestration_ai_json", side_effect=response):
            rid = self.start()
            self.service.run(rid)
        exported = self.service.result("content", rid)
        self.assertEqual(exported["run"]["status"], "completed", exported["run"])
        self.assertIsNotNone(initial)
        self.assertEqual(exported["initial"], initial)
        results = [entry for entry in exported["raw_results"] if entry["raw"].get("method_id") == "label_frequency"]
        self.assertEqual(len(results), 2)
        self.assertEqual([r["raw"]["annotation_version"] for r in results], [0, 1])
        self.assertEqual(results[0]["raw"]["rows"], [])
        self.assertEqual(results[1]["raw"]["rows"][0]["label"], "price")
        self.assertEqual(results[1]["raw"]["rows"][0]["count"], 1)
        self.assertTrue(results[0]["stale"])
        self.assertFalse(results[1]["stale"])


if __name__ == "__main__":
    unittest.main()
