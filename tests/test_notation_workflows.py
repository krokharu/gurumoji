import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from gurumoji import transcript_preparation as h
from gurumoji.services import notation, notation_workflows as w, vocabulary_store as v, change_log
from test_notation import analyze, segments


class NotationWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="gurumoji-notation-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name, value in [("DATABASE_FILE", self.root / "library.sqlite3"), ("DATA_DIRECTORY", self.root / "data"),
                            ("CUSTOM_VOCABULARY_FILE", self.root / "vocabulary.json"),
                            ("MEDIA_DIRECTORY", self.root / "media"), ("DEFAULT_OUTPUT_DIRECTORY", self.root / "output")]:
            p = patch.object(app, name, value); p.start(); self.addCleanup(p.stop)
        app.initialize_library()
        app.reconcile_custom_vocabulary()
        original_prepare = w.prepare
        p = patch.object(w, "prepare", side_effect=lambda *a, **kw: original_prepare(*a, **kw, analyze=analyze))
        p.start(); self.addCleanup(p.stop)
        self.service = app.notation_workflows()
        self.raw = segments("AI ＡＩ サーバー サーバ")
        self.save(self.raw)
        self.client = app.app.test_client()

    def save(self, source, **kw):
        return app.upsert_library_item(item_id="c", source_name="架空.wav", output_dir=self.root / "output/c",
            media_path=None, language="ja", segments=source, speaker_names={"S1": "架空話者"}, outline=None,
            emotion_analysis=None, files=[], write_srt=False, write_json=True, original_segments=self.raw, **kw)

    def execute(self):
        preview = self.service.preview("c", "none")
        return self.service.execute("c", {"provider": "none", "preview_hash": preview["preview_hash"]})

    def test_preview_is_read_only_no_llm_and_stale_preview_rejected(self):
        with app.database_connection() as db:
            before = list(db.iterdump())
        with patch.object(app, "call_ai_json") as call:
            preview = self.service.preview("c", "none")
            self.assertEqual(preview["estimated_input_tokens"], 0)
            call.assert_not_called()
        with app.database_connection() as db:
            self.assertEqual(list(db.iterdump()), before)
        app.save_custom_vocabulary(["AI"])
        with self.assertRaises(ValueError):
            self.service.execute("c", {"provider": "none", "preview_hash": preview["preview_hash"]})

    def test_notation_raw_replay_ai_export_and_researcher_cancel(self):
        app.save_custom_vocabulary(["AI", "サーバー"])
        applied = self.execute()
        self.assertNotIn("notation_archive_warning", applied)
        with app.database_connection() as db:
            row = app.library_row("c")
            self.assertEqual(json.loads(row["original_segments_json"]), self.raw)
            self.assertEqual(h.read_version(db, "c", 2)["source"], h.source(row))
            ai = h.ai_change_rows(db, "c")
            self.assertEqual(ai[-1]["change_type"], "notation")
            self.assertEqual(ai[-1]["process_version"], "notation-1")
            self.assertTrue(ai[-1]["metadata"]["notation"]["groups"][0]["source_refs"])
            self.assertEqual(json.loads(row["speaker_names_json"]), {"S1": "架空話者"})
        review = self.service.review("c")
        group = next(g for g in review["groups"] if "AI" in g["allowed"])
        result = self.service.change("c", {**review, "group_id": group["id"], "action": "cancel"})
        self.assertIn("AI ＡＩ", result["segments"][0]["text"])
        self.assertIn("サーバー サーバー", result["segments"][0]["text"])
        with app.database_connection() as db:
            self.assertEqual(next(c for c in reversed(h._changes(db, "c")) if c["process"] == "notation_review")["origin"], "researcher")
            self.assertEqual(h.current_version(db, app.library_row("c")), 3)
            self.assertEqual(h.read_version(db, "c", 3)["source"], h.source(app.library_row("c")))

    def test_sequential_group_changes_dictionary_registration_and_delete(self):
        app.save_custom_vocabulary(["AI", "サーバー"])
        self.execute()
        for group in self.service.review("c")["groups"]:
            review = self.service.review("c")
            self.service.change("c", {**review, "group_id": group["id"], "action": "change", "canonical": "研究者表記"})
        self.assertEqual(app.row_segments(app.library_row("c"))[0]["text"], "研究者表記 研究者表記 研究者表記 研究者表記")
        review = self.service.review("c")
        group = review["groups"][0]
        self.service.change("c", {**review, "group_id": group["id"], "action": "register", "canonical": "確定"})
        with app.database_connection() as db:
            self.assertEqual(v.terms(db), ("AI", "サーバー"))
            self.assertEqual(change_log.reconstruct(change_log.rows(db, "notation_variants", "global")), v.variants(db))
        self.service.change("c", {**review, "group_id": group["id"], "action": "delete_dictionary"})
        with app.database_connection() as db:
            self.assertEqual(v.variants(db), {})

    def test_manual_edit_protection_and_conflicting_review(self):
        app.save_custom_vocabulary(["AI", "サーバー"])
        self.execute()
        review = self.service.review("c")
        manual = copy.deepcopy(app.row_segments(app.library_row("c")))
        manual[0]["text"] += " 研究者が確定。"
        self.save(manual, increment_revision=True)
        with self.assertRaises(ValueError):
            self.service.change("c", {**review, "group_id": review["groups"][0]["id"], "action": "cancel"})
        self.assertEqual(self.service.preview("c", "none")["plan"]["groups"], [])
        review["revision_count"] = app.library_row("c")["revision_count"]
        with self.assertRaises(ValueError):
            self.service.change("c", {**review, "group_id": review["groups"][0]["id"], "action": "cancel"})

    def test_flask_preview_apply_review_dictionary_and_missing(self):
        app.save_custom_vocabulary(["AI"])
        preview = self.client.get("/api/library/c/notation/preview").get_json()
        response = self.client.post("/api/library/c/notation", json={"provider": "none", "preview_hash": preview["preview_hash"]})
        self.assertEqual(response.status_code, 200, response.get_json())
        review = self.client.get("/api/library/c/notation").get_json()
        result = self.client.post("/api/library/c/notation/review", json={**review, "group_id": review["groups"][0]["id"], "action": "register", "canonical": "AI"})
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(self.client.get("/api/library/missing/notation").status_code, 404)

    def test_dictionary_history_failure_atomic_and_v1_copy(self):
        app.save_custom_vocabulary(["AI"])
        self.execute()
        review = self.service.review("c")
        with app.database_connection() as db:
            db.execute("CREATE TRIGGER fail_dictionary BEFORE INSERT ON change_log BEGIN SELECT RAISE(ABORT, 'injected'); END")
        with self.assertRaises(Exception):
            self.service.change("c", {**review, "group_id": review["groups"][0]["id"], "action": "register", "canonical": "AI"})
        with app.database_connection() as db:
            self.assertEqual(v.variants(db), {})
        self.assertEqual(json.loads(app.CUSTOM_VOCABULARY_FILE.read_text(encoding="utf-8")), {"version": 1, "terms": ["AI"]})

    def test_llm_flask_path_bounded_mock_usage_and_invalid_choice_keeps_raw(self):
        with patch.object(app, "load_token_config", return_value=app.TokenConfig(openai_api_key="mock")), \
                patch.object(app, "configured_ai_credentials", return_value=("mock", "mock-model")), \
                patch.object(app, "call_ai_json", return_value={"canonical": "invented"}) as call:
            preview = self.client.get("/api/library/c/notation/preview?provider=openai").get_json()
            self.assertGreater(preview["estimated_input_tokens"], 0)
            self.assertEqual(preview["destination"], "OpenAI")
            call.assert_not_called()
            result = self.client.post("/api/library/c/notation", json={"provider": "openai", "preview_hash": preview["preview_hash"]})
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertEqual(result.get_json()["segments"][0]["text"], self.raw[0]["text"])
            self.assertEqual(call.call_count, 2)
            for args in call.call_args_list:
                payload = json.loads(args.args[4])
                self.assertEqual(set(payload), {"variants", "allowed", "contexts"})
                self.assertTrue(all(len(c) <= 70 for c in payload["contexts"]))

    def test_other_conversation_evidence_is_current_researcher_text_with_provenance(self):
        other = [{**s, "id": "other-s1"} for s in self.raw]
        def save(source, history_steps=None):
            app.upsert_library_item(item_id="other", source_name="架空の別会話.wav", output_dir=self.root / "output/other",
                media_path=None, language="ja", segments=source, speaker_names={}, outline=None,
                emotion_analysis=None, files=[], write_srt=False, write_json=True,
                original_segments=other, increment_revision=history_steps is not None, finishing_history=history_steps)
        save(other)
        confirmed = [{**s, "text": "AIの研究者確定"} for s in other]
        save(confirmed)
        plan = self.service.preview("c", "none")["plan"]
        group = next(g for g in plan["groups"] if "AI" in g["allowed"])
        self.assertEqual(group["source"], "researcher_history")
        self.assertEqual(group["source_refs"][0]["item_id"], "other")
        self.assertEqual(group["source_refs"][0]["segment_id"], "other-s1")
        ai = [{**s, "text": "AI AI サーバー サーバー"} for s in confirmed]
        save(ai, [{"segments": ai, "origin": "ai", "process": "ai_finishing"}])
        self.assertTrue(all(g["source"] == "unresolved" for g in self.service.preview("c", "none")["plan"]["groups"]))


if __name__ == "__main__":
    unittest.main()
