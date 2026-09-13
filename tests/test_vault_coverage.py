"""Every Whisper and analysis entry point reaches the four Vaults.

Meeting minutes and group-interview comparisons are saved as their own runs.
"""
import json
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import test_content_analysis as support
import test_meeting_minutes as meeting
from gurumoji.obsidian_layout import unpack
from gurumoji.vault_registry import entity_key


def read_notes(root: Path) -> dict[str, tuple[dict, str]]:
    return {path.relative_to(root).as_posix(): unpack(path.read_text(encoding="utf-8"))
            for path in root.rglob("*.md") if ".obsidian" not in path.parts}


class LibraryVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-vault-coverage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        database = patch.object(app, "DATABASE_FILE", self.root / "library.sqlite3")
        database.start()
        self.addCleanup(database.stop)
        app.initialize_library()
        self.client = app.app.test_client()
        self.registry = app.vault_registry()
        self.store = app.analysis_archive_store()

    def add(self, item_id, name="面談.wav", texts=("価格を比べる", "機能を重視する"), *,
            names=None, profile=None, minutes=None):
        segments = [{"id": f"{item_id}_{index}", "speaker": "P1", "start": index * 2.0,
                     "end": index * 2.0 + 1, "text": text} for index, text in enumerate(texts)]
        app.upsert_library_item(
            item_id=item_id, source_name=name, output_dir=self.root / "out" / item_id, media_path=None,
            language="ja", segments=segments, speaker_names=names if names is not None else {"P1": "参加者"},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True,
            session_profile=profile, meeting_minutes=minutes)
        return app.library_row(item_id)

    def input_note(self, item_id):
        return read_notes(self.registry.root("input"))[f"10-Inputs/input-{entity_key(item_id)}.md"]

    def test_whisper_settings_record_vocabulary_and_diarization_without_terms_or_tokens(self):
        options = types.SimpleNamespace(
            model_name="large-v3", device="cpu", diarization_device="cpu", audio_preprocess="none",
            triple_pass=False, boost_quiet_speech=False, vad_onset=0.5, vad_offset=0.36,
            no_speech_threshold=0.6, min_speakers=None, max_speakers=None, emotion_analysis=False,
            emotion_model="model", conversation_mode="interview", custom_vocabulary=("山田商事", "Gurumoji"),
            hf_token="hf_secret")
        settings = app.whisper_vault_settings(options, "ja")
        self.assertEqual(settings["custom_vocabulary_terms"], 2)
        self.assertEqual(len(settings["custom_vocabulary_sha256"]), 64)
        self.assertEqual(settings["diarization_model"], app.DIARIZATION_MODEL)
        app.publish_input_vault(self.add("whisper"), settings)
        body = self.input_note("whisper")[1]
        self.assertIn("custom_vocabulary_terms", body)
        self.assertIn(app.DIARIZATION_MODEL, body)
        self.assertNotIn("山田商事", body)
        self.assertNotIn("hf_secret", body)

    def test_speaker_identification_updates_the_input_ledger(self):
        app.publish_input_vault(self.add("speakers", names={}), {"model": "large-v3"})
        with patch.object(app, "load_token_config", return_value=app.TokenConfig(openai_api_key="test-key")), \
                patch.object(app, "configured_ai_credentials", return_value=("test-key", "test-model")), \
                patch.object(app, "detect_speaker_names_with_ai", return_value={"P1": "山田"}):
            response = self.client.post("/api/library/speakers/speaker-identification",
                                        json={"provider": "openai", "revision_count": 0})
        self.assertEqual(response.status_code, 200, response.get_json())
        props, body = self.input_note("speakers")
        self.assertEqual(props["revision"], 1)
        self.assertIn("large-v3", body)

    def test_obsidian_apply_updates_the_input_ledger(self):
        row = self.add("finish")
        app.publish_input_vault(row)
        before = app.row_segments(row)
        revised = [{**segment, "text": segment["text"] + "。"} for segment in before]
        context = {"revision": 0, "names": {}, "before": before, "stages": {"cleanup": "completed"},
                   "provider": "openai", "model": "test-model", "usage": {}, "context_outline": None,
                   "run_id": "apply-test-0001"}
        app.run_obsidian_finishing("apply", {"item_id": "finish", "revision": 0}, revised, context,
                                   "openai", lambda: None)
        self.assertEqual(self.input_note("finish")[0]["revision"], 1)

    def test_output_json_import_creates_a_ledger_without_text(self):
        output = self.root / "outputs"
        output.mkdir()
        (output / "取込_話者分離.json").write_text(json.dumps({
            "source": "取込.wav", "language": "ja",
            "segments": [{"id": "x1", "speaker": "A", "start": 0, "end": 1, "text": "取り込んだ発言"}],
        }, ensure_ascii=False), encoding="utf-8")
        with patch.object(app, "DEFAULT_OUTPUT_DIRECTORY", output):
            app.import_existing_outputs()
        with app.database_connection() as connection:
            item_id = connection.execute("SELECT id FROM library_items WHERE source_name='取込.wav'").fetchone()[0]
        body = self.input_note(item_id)[1]
        self.assertIn("出力JSONの取り込み", body)
        self.assertNotIn("取り込んだ発言", body)

    def test_deleted_conversation_keeps_a_marked_ledger(self):
        app.publish_input_vault(self.add("gone"))
        response = self.client.delete("/api/library/gone")
        self.assertEqual(response.status_code, 200, response.get_json())
        props, body = self.input_note("gone")
        self.assertEqual(props["status"], "deleted")
        self.assertIn("アプリから削除された会話", body)

    def test_meeting_minutes_are_saved_as_their_own_run(self):
        profile = {"session_type": "meeting", "session_date": "2026-09-14"}
        minutes = app.build_meeting_minutes(meeting.MEETING_SEGMENTS, meeting.SPEAKER_NAMES, profile)
        app.upsert_library_item(
            item_id="meeting-1", source_name="定例会議.wav", output_dir=self.root / "meeting", media_path=None,
            language="ja", segments=meeting.MEETING_SEGMENTS, speaker_names=meeting.SPEAKER_NAMES, files=[],
            outline=None, emotion_analysis=None, write_srt=False, write_json=True,
            session_profile=profile, meeting_minutes=minutes)
        for _ in range(2):
            response = self.client.post("/api/library/meeting-1/meeting-obsidian")
            self.assertEqual(response.status_code, 200, response.get_json())
        runs = self.store.list("meeting-1")
        self.assertEqual([run["kind"] for run in runs], ["meeting_minutes"])
        run = runs[0]
        orchestrator = read_notes(self.registry.root("orchestrator"))
        props, body = orchestrator[f"20-Runs/run-{run['id']}.md"]
        self.assertEqual(props["conversation_id"], "meeting-1")
        self.assertIn("[[10-Methods/meeting_minutes", body)
        self.assertNotIn("[[10-Methods/morphology", body)
        visuals = read_notes(self.registry.root("visualization"))
        self.assertIn(f"10-Visuals/run-{run['id']}/meeting_minutes.md", visuals)
        result = json.loads(self.store.read_artifact(
            next(a["id"] for a in self.store.artifacts(run["id"]) if a["name"] == "result.json"))[1])
        self.assertEqual([method["method_id"] for method in result["methods"]], ["meeting_minutes"])

    def test_group_interview_comparison_is_saved_apart_from_each_interview(self):
        profile = {"session_type": "focus_group", "comparison_group": "製品評価",
                   "objective": "比較テスト", "moderator_guide": "質問ガイド"}
        self.add("same_a", "同内容 A", ("使いやすい製品", "価格を改善してほしい"), profile=profile)
        self.add("same_b", "同内容 B", ("製品は使いやすい", "価格より機能を重視する"), profile=profile)
        payload = {"item_ids": ["same_a", "same_b"], "allow_different_content": False,
                   "request_id": "comparison-request-0001"}
        payload["input_fingerprints"] = self.client.post(
            "/api/library/interview-comparison", json=payload).get_json()["input_fingerprints"]
        response = self.client.post("/api/library/interview-comparison/runs", json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        run = response.get_json()["run"]
        self.assertEqual(run["kind"], "interview_comparison")
        self.assertEqual(run["vault_status"], "completed", run)
        again = self.client.post("/api/library/interview-comparison/runs",
                                 json={**payload, "request_id": "comparison-request-0002"}).get_json()["run"]
        self.assertEqual(again["id"], run["id"])
        # Each interview's own run history stays untouched.
        self.assertEqual(self.store.list("same_a"), [])
        self.assertEqual(self.store.members(run["id"]), ["same_a", "same_b"])
        listed = self.client.get("/api/library/interview-comparison/runs").get_json()["runs"]
        self.assertEqual([(item["id"], item["member_ids"]) for item in listed], [(run["id"], ["same_a", "same_b"])])
        self.assertTrue((self.store.vault / f"40-研究/インタビュー比較/comparison-{run['id']}.md").is_file())
        self.assertFalse(any(key.startswith("comparison-") for key in self.store.layout.load()["interviews"]))
        props = read_notes(self.registry.root("orchestrator"))[f"20-Runs/run-{run['id']}.md"][0]
        self.assertEqual(props["conversation_ids"], ["same_a", "same_b"])
        snapshots = [note for path, note in read_notes(self.registry.root("input")).items()
                     if path.startswith("20-Snapshots/")]
        self.assertEqual([note[0]["note_type"] for note in snapshots], ["comparison-snapshot"])

        data = self.client.get("/api/library/same_a/analysis").get_json()
        config = data["config"]
        config["research_question"] = "別の問い"
        updated = self.client.put("/api/library/same_a/analysis", json={
            "source_revision": 0, "analysis_revision": data["item"]["analysis_revision"], "config": config})
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertTrue(self.store.get(run["id"])["stale"])
        self.assertEqual(self.registry.run_status(run["id"]), "stale")

        blocked = self.client.post("/api/library/interview-comparison/runs", json={
            **payload, "item_ids": ["same_a", "missing"], "request_id": "comparison-request-0003"})
        self.assertEqual(blocked.status_code, 404)


    def test_preparation_save_invalidates_single_and_comparison_runs_atomically(self):
        profile = {'session_type': 'focus_group', 'comparison_group': 'example'}
        for item_id in ('a', 'b'):
            self.add(item_id, profile=profile)
        selection = {'item_ids': ['a', 'b'], 'allow_different_content': False}
        compared = self.client.post('/api/library/interview-comparison', json=selection).get_json()
        comparison = self.client.post('/api/library/interview-comparison/runs', json={
            **selection, 'request_id': 'preparation-comparison-0001',
            'input_fingerprints': compared['input_fingerprints']}).get_json()['run']
        single = self.store.save(item_id='a', kind='text_analysis', snapshot={'title': 'a', 'segments': []},
            result={'methods': []}, datasets={}, request_id='preparation-single-0001',
            input_fingerprint=app.archive_source_stamp(app.library_row('a')), source_revision=0, analysis_revision=0)
        self.assertFalse(self.store.get(single['id'])['stale'])
        # An aborted preparation transaction must not leave runs invalidated.
        with app.database_connection() as connection:
            connection.execute('BEGIN')
            app.preparation.write_state(connection, 'a', 1, {'source_hash': 'rollback-test'})
            self.assertTrue(connection.execute('SELECT stale FROM analysis_runs WHERE id=?', (single['id'],)).fetchone()[0])
            connection.rollback()
        self.assertFalse(self.store.get(single['id'])['stale'])
        with app.database_connection() as connection:
            row = app.library_row('a')
            prepared = app.preparation.view(connection, row, app.row_segments(row))
        response = self.client.put('/api/library/a/preparation', json={
            'revision': prepared['revision'], 'source_hash': prepared['source_hash'], 'records': {}})
        self.assertEqual(response.status_code, 200, response.get_json())
        for run in (single, comparison):
            self.assertTrue(self.store.get(run['id'])['stale'])
            self.assertEqual(self.registry.run_status(run['id']), 'stale')
        listed = self.client.get('/api/library/interview-comparison/runs').get_json()['runs']
        self.assertTrue(listed[0]['stale'])


class LegacyRunVaultTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_resaving_a_run_from_before_the_four_vaults_mirrors_it(self):
        row = app.library_row("content")
        run = app.archive_group_analysis(row, app.group_analysis_for_row(row, include_research_rows=True),
                                         "legacy-request-000001")
        registry = app.vault_registry()
        # Simulate a run that was saved before the four Vaults existed.
        registry.catalog_file.unlink()
        shutil.rmtree(registry.root("orchestrator"))
        self.assertIsNone(registry.run_status(run["id"]))
        again = app.archive_group_analysis(row, app.group_analysis_for_row(row, include_research_rows=True),
                                           "legacy-request-000002")
        self.assertEqual(again["id"], run["id"])
        self.assertEqual(registry.run_status(run["id"]), "current")


if __name__ == "__main__":
    unittest.main()
