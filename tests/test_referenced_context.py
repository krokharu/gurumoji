"""Synthetic Vault and provider boundaries for Handler-resolved reference input."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from gurumoji import method_experts
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import model_context
from gurumoji.services.ai import client
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters


def make_catalog(root):
    root = Path(root)
    selections = {
        "01-Evidence-and-Claims.md": ("記述の4区分", "2種類の根拠を分ける", "作らないもの", "人の確認が必要な箇所"),
        "04-AI-Assistance-Boundaries.md": ("AIに任せてよいこと・いけないこと",),
    }
    for name, headings in selections.items():
        path = root / method_experts.COMMON_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nnote_id: fixture-" + name[:2] + "\nnote_type: common-knowledge\nstatus: current\nupdated: 2026-10-06\n---\n"
            + "\n".join("## " + heading + "\nOnly a draft; unknown remains unknown. [[target|readable]]" for heading in headings)
            + "\n## unrelated\nNEVER_LOAD_OTHER_SECTION\n", encoding="utf-8")
    return method_experts.ExpertCatalog(root, local_root=root / "local")


class KnowledgeRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = make_catalog(self.temp.name)

    def test_named_sections_have_provenance_and_preserve_limits_without_whole_vault(self):
        packet = method_experts.orchestration_context(stage="initial_labels", catalog=self.catalog)
        rendered = json.dumps(packet)
        self.assertNotIn("NEVER_LOAD_OTHER_SECTION", rendered)
        self.assertNotIn("[[target", rendered)
        self.assertIn("unknown remains unknown", rendered)
        self.assertEqual(len(packet["sources"]), 2)
        self.assertEqual(len(self.catalog.read_log), 2)
        for row in packet["sources"]:
            self.assertEqual(len(row["source_sha256"]), 64)
            self.assertEqual(row["vault_kind"], "software")
            self.assertFalse(Path(row["path"]).is_absolute())

    def test_changed_bytes_are_rehashed_even_when_file_stamp_did_not_change(self):
        first = method_experts.orchestration_context(stage="core", catalog=self.catalog)
        path = self.catalog.root / first["sources"][0]["path"]
        stamp = path.stat()
        path.write_bytes(path.read_bytes().replace(b"unknown", b"missing"))
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        second = method_experts.orchestration_context(stage="core", catalog=self.catalog)
        self.assertNotEqual(first["sources"][0]["source_sha256"], second["sources"][0]["source_sha256"])

    def test_arbitrary_path_missing_section_and_noncurrent_note_are_rejected(self):
        with self.assertRaises(method_experts.ExpertDefinitionError):
            self.catalog.context_excerpt(Path("../../secrets.md"), ("section",))
        path = self.catalog.root / method_experts.COMMON_DIR / "01-Evidence-and-Claims.md"
        data = path.read_bytes()
        for updated in (data.replace(b"status: current", b"status: draft"), data.replace("## 作らないもの".encode(), b"## missing")):
            path.write_bytes(updated)
            with self.assertRaises(method_experts.ExpertDefinitionError):
                method_experts.orchestration_context(stage="core", catalog=self.catalog)

    def test_required_knowledge_is_held_instead_of_silently_truncated(self):
        with self.assertRaises(method_experts.ExpertDefinitionError):
            method_experts.orchestration_context(stage="interpretation", brief={"required_inputs": "x" * 9000}, catalog=self.catalog)


class ReferenceTransportTests(unittest.TestCase):
    def context(self):
        return {"task": {"phase": "initial_analysis", "role": "interpretation"}, "question": "fixture question", "data_version": "v",
                "resources_origin": {"initial_id": "initial_123", "run_id": "run_456"},
                "raw_evidence": [{"evidence_id": "e1", "utterance_id": "u1", "text": "PRIVATE_SOURCE_TEXT"}],
                "coverage": {"available_count": 1, "provided_count": 1},
                "expert_knowledge": {"sources": [{"note_id": "note-1", "path": "50-Analysis-Methods/rules.md", "source_sha256": "a" * 64,
                                                 "sections": {"scope": "RETRIEVED_SECTION_TEXT"}}]}}

    def test_instruction_contains_paths_but_data_and_excerpts_are_separate_and_hash_checked(self):
        context = self.context()
        before = copy.deepcopy(context)
        user, messages = model_context.reference_messages(context)
        self.assertNotIn("PRIVATE_SOURCE_TEXT", user)
        self.assertNotIn("RETRIEVED_SECTION_TEXT", user)
        self.assertIn("db://orchestration_initials/initial_123/raw_evidence", user)
        self.assertIn("50-Analysis-Methods/rules.md", user)
        rebuilt = model_context.restored_reference_context(user, messages)
        self.assertEqual(rebuilt["raw_evidence"], context["raw_evidence"])
        self.assertEqual(context, before)
        with self.assertRaises(ValueError):
            model_context.restored_reference_context(user, messages[:-1])
        with self.assertRaises(ValueError):
            model_context.restored_reference_context(user, [row.replace("PRIVATE_SOURCE_TEXT", "TAMPERED") for row in messages])

    def test_provider_requests_use_separate_messages_or_parts_and_one_dispatch(self):
        for provider in ("lmstudio", "openai", "google"):
            posted = []
            response = {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]}
            if provider == "openai": response = {"output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}]}
            if provider == "google": response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"ok":true}'}]}}]}
            def post(url, headers, payload, **kwargs):
                posted.append(payload)
                return response
            result = client.call_ai_json(provider, "fixture-key", "fixture-model", "system", "instruction", "fixture", {},
                post=post, lmstudio_base=lambda *_: "http://127.0.0.1:1234/v1", lmstudio_model_id=str,
                lmstudio_reasoning=lambda *_: {}, providers={"lmstudio", "openai", "google"}, data_messages=["data", "knowledge"])
            self.assertTrue(result["ok"])
            self.assertEqual(len(posted), 1)
            if provider == "google":
                texts = [part["text"] for part in posted[0]["contents"][0]["parts"]]
                self.assertEqual(texts, ["instruction", "data", "knowledge"])
            else:
                values = posted[0]["messages" if provider == "lmstudio" else "input"]
                self.assertEqual([row["content"] for row in values], ["system", "instruction", "data", "knowledge"])

    def test_preflight_receives_data_and_refuses_oversized_owned_page_without_dispatch(self):
        measured, sent, saved = [], [], []
        def meter(*args, **kwargs):
            measured.append(model_context.restored_reference_context(args[3], kwargs["data_messages"]))
            return {"fits": False}
        resolve, runner = make_orchestration_adapters(call_ai_json=lambda *a, **k: sent.append(a),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""), configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=meter)
        with self.assertRaises(AnalysisContractError) as caught:
            runner("interpretation", self.context(), resolve({"model_context_version": 1}), lambda: None, saved.append)
        self.assertEqual(caught.exception.code, "context_budget_exceeded")
        self.assertEqual(sent, [])
        self.assertEqual(measured[0]["raw_evidence"][0]["text"], "PRIVATE_SOURCE_TEXT")
        manifest = saved[0]["context_manifest"]
        self.assertEqual(manifest["provided_evidence_ids"], ["e1"])
        self.assertEqual(manifest["reference_version"], 1)
        self.assertEqual(len(manifest["data_messages_sha256"]), 64)

    def test_initial_routing_keeps_knowledge_and_real_origin_paths(self):
        context = self.context()
        context["task"]["phase"] = "initial_routing"
        packet = model_context.compact_context(context)
        self.assertNotIn("raw_evidence", packet)
        self.assertEqual(packet["expert_knowledge"], context["expert_knowledge"])
        self.assertEqual(packet["resources_origin"], context["resources_origin"])


if __name__ == "__main__": unittest.main()
