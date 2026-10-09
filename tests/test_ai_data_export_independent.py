"""Independent Issue 29 acceptance, using only isolated synthetic records.

The fixture deliberately differs from implementation-owner fixtures.  Browser
acceptance is opt-in through the repository's existing browser_support helper.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote, urlsplit
import wave
import zipfile

import app
import browser_support
from gurumoji import transcript_preparation as preparation


class IndependentExportTests(unittest.TestCase):
    item_id = "independent_unicode"
    original_text = '  原文 e\u0301／猫🐈\n=1+2, "引用"  '
    current_text = '  訂正 é／猫🐈\n=2+3, "現在"  '
    split_text = "分割した続き\t終わり"
    saved_outline = {"title": "保存済み概要", "summary": "SAVED_ONLY_保存版", "topics": []}

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-issue29-independent-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for key, value in {
            "DATA_DIRECTORY": self.root / "data",
            "DATABASE_FILE": self.root / "data" / "library.sqlite3",
            "MEDIA_DIRECTORY": self.root / "data" / "media",
            "THUMBNAIL_DIRECTORY": self.root / "data" / "thumbnails",
            "TRAINING_AUDIO_DIRECTORY": self.root / "data" / "training" / "audio",
            "TRAINING_DIRECTORY": self.root / "data" / "training",
            "TRAINING_JSONL_FILE": self.root / "data" / "training" / "corrections.jsonl",
            "TRAINING_MANIFEST_FILE": self.root / "data" / "training" / "manifest.csv",
            "CUSTOM_VOCABULARY_FILE": self.root / "data" / "custom_vocabulary.json",
            "BACKUP_DIRECTORY": self.root / "backups",
            "TOKEN_FILE": self.root / "config" / "tokens.json",
            "DEFAULT_OUTPUT_DIRECTORY": self.root / "output",
        }.items():
            guard = patch.object(app, key, value)
            guard.start()
            self.addCleanup(guard.stop)
        for key in ("publish_input_vault", "refresh_archive_index"):
            guard = patch.object(app, key, side_effect=AssertionError("export must not publish or index"))
            guard.start()
            self.addCleanup(guard.stop)
        # Normal /api/config otherwise probes a real loopback model-list service.
        # Keep the unrelated connection-light dependency synthetic too.  Its
        # invalid scheme is rejected locally before any model HTTP request.
        guard = patch.object(app, "load_token_config", return_value=app.TokenConfig(
            lmstudio_base_url="invalid://independent-disabled"))
        guard.start()
        self.addCleanup(guard.stop)
        app.initialize_library(repair_provenance=False)
        self.client = app.app.test_client()
        self.source = self.root / "synthetic-original.txt"
        self.source.write_text(self.original_text, encoding="utf-8")
        self.names = {"S_A": "合成氏名A", "S_B": "合成氏名B"}
        self.profiles = {
            "S_A": {"display_name": "合成氏名A", "session_role": "participant", "organization": "合成組織A"},
            "S_B": {"display_name": "合成氏名B", "session_role": "observer", "organization": "合成組織B"},
        }
        self.originals = [
            {"id": "root", "start": 0, "end": 1, "speaker": "S_A", "text": self.original_text},
            {"id": "zero", "start": 0, "end": 0, "speaker": "S_B", "text": "観測した0"},
            {"id": "unknown", "text": "時刻と話者は欠測"},
            {"id": "retired", "start": 3, "end": 3.5, "speaker": "S_Z", "text": "旧版だけの話者"},
        ]
        self.persist(self.originals, originals=self.originals)
        self.current = [
            {**self.originals[0], "text": self.current_text},
            self.originals[1], self.originals[2],
            {"id": "split", "speaker": "S_A", "text": self.split_text},
        ]
        self.persist(self.current, increment=True)
        with app.database_connection() as connection:
            row = connection.execute("SELECT * FROM library_items WHERE id=?", (self.item_id,)).fetchone()
            # Ordinary persistence adds profiles such as UNKNOWN with a saved
            # empty name. Read that source before export, distinguishing empty,
            # absent and excluded names without consulting the projection.
            self.saved_profiles = json.loads(row["speaker_profiles_json"])
            self.saved_names = json.loads(row["speaker_names_json"])
            before = preparation.view(connection, row, app.row_segments(row))
            preparation.save(connection, row, app.row_segments(row), {
                "revision": before["revision"], "source_hash": before["source_hash"],
                "order_verified": True,
                "records": {
                    "root": {"text_status": "transcript_checked", "boundary_verified": True,
                             "source_segment_ids": ["root"], "source_locator": "synthetic page 1"},
                    "split": {"source_segment_ids": ["root"], "source_locator": "synthetic page 1 continuation"},
                },
            })
        self.expected_preparation = self.client.get(self.preparation_url).get_json()

    @property
    def preparation_url(self):
        return f"/api/library/{self.item_id}/preparation/export.json"

    @property
    def export_url(self):
        return f"/api/library/{self.item_id}/ai-export.zip"

    def persist(self, segments, *, originals=None, increment=False, media=None):
        return app.upsert_library_item(
            item_id=self.item_id, source_name="合成会話.mp4", output_dir=self.root / "output",
            media_path=media, language="ja", segments=segments, speaker_names=self.names,
            speaker_profiles=self.profiles, outline=self.saved_outline, emotion_analysis=None,
            files=[self.source], write_srt=False, write_json=True,
            session_profile={"objective": "DERIVED_DIFFERENT_派生計画"},
            original_segments=originals, increment_revision=increment,
        )

    def snapshot(self):
        with closing(sqlite3.connect(app.DATABASE_FILE)) as connection:
            logical = "\n".join(connection.iterdump()).encode("utf-8")
        return {"db": hashlib.sha256(logical).hexdigest(),
                "files": {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in self.root.rglob("*") if path.is_file()}}

    def parse_zip(self, content):
        archive = zipfile.ZipFile(io.BytesIO(content))
        names = archive.namelist()
        self.assertEqual(len(names), len(set(names)), "duplicate ZIP members")
        self.assertLessEqual(sum(info.file_size for info in archive.infolist()), 64 * 1024 * 1024)
        self.assertLessEqual(sum(info.file_size for info in archive.infolist()
                                 if not info.filename.endswith(".jpg")), 32 * 1024 * 1024)
        for name in names:
            path = PurePosixPath(name)
            self.assertFalse(path.is_absolute())
            self.assertNotIn("..", path.parts)
            self.assertNotIn("\\", name)
            self.assertNotIn(":", name)
        self.assertIsNone(archive.testzip())
        return archive

    def synthetic_video(self):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("FFmpeg unavailable: actual synthetic video decode NOTRUN")
        folder = app.MEDIA_DIRECTORY / self.item_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "synthetic.mp4"
        subprocess.run([ffmpeg, "-nostdin", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=160x96:rate=2:duration=4", "-c:v", "mpeg4", str(target)],
                       capture_output=True, check=True, timeout=15)
        return target

    def export(self, **selection):
        return self.client.post(self.export_url, json=selection)

    @contextmanager
    def http_server(self):
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def save_browser_evidence(self, page, name, network):
        raw = os.environ.get("GURUMOJI_AI_EXPORT_EVIDENCE_DIR")
        if raw:
            directory = Path(raw).resolve()
            repository = Path(__file__).resolve().parents[1]
            self.assertFalse(directory.is_relative_to(repository), "evidence must stay outside Git")
            directory.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(directory / f"{name}.png"))
            panel = page.locator('[data-ai-data-export]:visible')
            if panel.count():
                panel.screenshot(path=str(directory / f"{name}-panel.png"))
            (directory / f"{name}-network.json").write_text(
                json.dumps(network, ensure_ascii=False, indent=2), encoding="utf-8")
            (directory / f"{name}-browser.json").write_text(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(), "url": page.url,
                "browser_version": page.context.browser.version, "viewport": page.viewport_size,
                "user_agent": page.evaluate("navigator.userAgent"),
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_normal_export_panel(self, page, origin, width):
        page.set_viewport_size({"width": width, "height": 900 if width > 500 else 844})
        page.goto(f"{origin}/?view=analysis&item={self.item_id}")
        page.locator('#analysis-item-select').wait_for(state="visible")
        page.wait_for_function("id => document.querySelector('#analysis-item-select').value === id", arg=self.item_id)
        page.locator('[data-analysis-mode="manual"]:visible').click()
        panel = page.locator('[data-ai-data-export]:visible')
        panel.locator("summary").click()
        panel.locator('[data-ai-export-download]').wait_for(state="visible")
        return panel

    @browser_support.ui_browser_test
    def test_browser_normal_controls_and_real_missing_media_failure_desktop_mobile(self):
        before = self.snapshot()
        with self.http_server() as origin, browser_support.sandboxed_playwright_browser() as browser:
            for width in (1440, 390):
                with self.subTest(width=width):
                    context = browser.new_context(accept_downloads=True)
                    try:
                        page = context.new_page()
                        errors, downloads, external, network = [], [], [], []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.on("download", lambda download: downloads.append(download))
                        page.on("response", lambda response: network.append({
                            "method": response.request.method, "url": response.url, "status": response.status}))

                        def guard(route):
                            if urlsplit(route.request.url).hostname != "127.0.0.1":
                                external.append(route.request.url)
                                route.abort()
                            else:
                                route.continue_()

                        context.route("**/*", guard)
                        panel = self.open_normal_export_panel(page, origin, width)
                        self.assertFalse(panel.get_by_label("話者の氏名・表示名を含める", exact=True).is_checked())
                        self.assertFalse(panel.get_by_label("動画フレームを含める（初期値OFF）", exact=True).is_checked())
                        self.assertIsNotNone(panel.locator('[data-ai-export-frame-options]').get_attribute("disabled"))
                        self.assertTrue(panel.locator('[data-ai-export-frame="start"]').is_disabled())
                        self.assertTrue(all(not box.is_checked() for box in panel.locator('[data-ai-export-attribute]').all()))
                        self.assertIn("匿名化を保証する出力ではありません", panel.inner_text())
                        self.assertIn("外部AIへ自動送信しません", panel.inner_text())
                        panel.get_by_label("動画フレームを含める（初期値OFF）", exact=True).check()
                        panel.get_by_label("終了時刻（秒・開始から600秒以内）", exact=True).fill("24")
                        button = panel.get_by_role("button", name="AI向け生データZIPをダウンロード", exact=True)
                        button.focus()
                        page.keyboard.press("Enter")
                        self.assertIn("動画の条件を確認してください", panel.locator('[data-ai-export-status]').inner_text())
                        self.assertEqual(len([r for r in network if r["url"].endswith("ai-export.zip")]), 0)
                        panel.get_by_label("終了時刻（秒・開始から600秒以内）", exact=True).fill("0")
                        with page.expect_response(lambda response: response.url.endswith("ai-export.zip")) as reply:
                            button.click()
                        self.assertEqual(reply.value.status, 422)
                        page.wait_for_function("() => [...document.querySelectorAll('[data-ai-export-status]')].some(n => n.textContent.includes('ZIPはダウンロードされていません'))")
                        self.assertIn("動画フレームを利用できません", panel.locator('[data-ai-export-status]').inner_text())
                        self.assertFalse(button.is_disabled())
                        self.assertEqual(downloads, [])
                        self.assertEqual(external, [])
                        self.assertEqual(errors, [])
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"))
                        self.save_browser_evidence(page, f"controls-missing-media-{width}", network)
                    finally:
                        context.close()
        self.assertEqual(before, self.snapshot())

    @browser_support.ui_browser_test
    def test_browser_cancel_and_item_epoch_suppress_late_real_http_response(self):
        from gurumoji.web import export_routes

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        old_id = self.item_id
        self.item_id = "independent_other"
        self.persist(self.current)
        self.item_id = old_id
        original_extract = export_routes.extract_frames
        before = self.snapshot()
        with self.http_server() as origin, browser_support.sandboxed_playwright_browser() as browser:
            for action in ("cancel", "item_epoch"):
                with self.subTest(action=action):
                    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

                    def delayed(*args, **kwargs):
                        entered.set()
                        try:
                            if not release.wait(15):
                                raise AssertionError("independent HTTP service gate timed out")
                            return original_extract(*args, **kwargs)
                        finally:
                            finished.set()

                    context = browser.new_context(accept_downloads=True)
                    downloads = []
                    try:
                        page = context.new_page()
                        page.on("download", lambda download: downloads.append(download))
                        panel = self.open_normal_export_panel(page, origin, 1440)
                        panel.get_by_label("動画フレームを含める（初期値OFF）", exact=True).check()
                        panel.get_by_label("終了時刻（秒・開始から600秒以内）", exact=True).fill("0")
                        with patch.object(export_routes, "extract_frames", side_effect=delayed):
                            panel.locator('[data-ai-export-download]').click()
                            self.assertTrue(entered.wait(5), "real HTTP API did not reach extractor")
                            self.assertEqual(panel.get_attribute("aria-busy"), "true")
                            if action == "cancel":
                                panel.get_by_role("button", name="ダウンロードを取り消す", exact=True).click()
                                self.assertIn("サーバー側の処理停止は確認していません", panel.locator('[data-ai-export-status]').inner_text())
                                self.assertTrue(panel.locator('[data-ai-export-download]').evaluate("node => node === document.activeElement"))
                            else:
                                page.locator('#analysis-item-select').select_option("independent_other")
                                page.wait_for_function("() => document.querySelector('#analysis-item-select').value === 'independent_other'")
                            release.set()
                            self.assertTrue(finished.wait(5))
                            page.wait_for_timeout(250)
                            self.assertEqual(downloads, [])
                            self.save_browser_evidence(page, f"late-http-{action}", [])
                    finally:
                        release.set()
                        if entered.is_set():
                            finished.wait(5)
                        context.close()
        self.assertEqual(before, self.snapshot())

    def assert_bundle(self, content, *, names=False, attributes=(), frames=False):
        archive = self.parse_zip(content)
        manifest = json.loads(archive.read("manifest.json"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["item_id"], self.item_id)
        self.assertEqual(manifest["source_hash"], self.expected_preparation["source_hash"])
        self.assertEqual(manifest["input_version"], self.expected_preparation["input_version"])
        self.assertEqual(manifest["preparation_revision"], self.expected_preparation["revision"])
        self.assertEqual(manifest["hash_domains"], {
            "source_hash": "source_snapshot", "files": "exact_export_file_bytes"})
        entries = manifest["files"]
        self.assertEqual({entry["path"] for entry in entries}, set(archive.namelist()) - {"manifest.json"})
        self.assertEqual(len(entries), len(archive.namelist()) - 1)
        for entry in entries:
            exact = archive.read(entry["path"])
            self.assertEqual(entry["sha256"], hashlib.sha256(exact).hexdigest(), entry["path"])
            self.assertEqual(entry["size"], len(exact), entry["path"])
        fixed = {"README.md", "schema.json", "manifest.json", "conversation.json",
                 "speakers.json", "utterances.jsonl", "outline.json"}
        if not frames:
            self.assertEqual(set(archive.namelist()), fixed)
            self.assertEqual(manifest["frames"], {
                "status": "disabled", "reason": "not_requested", "media": None, "count": 0})
        conversation = json.loads(archive.read("conversation.json"))
        self.assertEqual(conversation["item"], {"id": self.item_id, "language": "ja"})
        exported = conversation["preparation"]
        rows = [json.loads(line) for line in archive.read("utterances.jsonl").decode("utf-8").splitlines()]
        self.assertEqual(exported["rows"], rows)
        original_rows = [{key: row[key] for key in preparation.FIELDS} for row in rows]
        row_bytes = json.dumps(original_rows, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
        self.assertEqual(exported["manifest"]["rows_sha256"], hashlib.sha256(row_bytes).hexdigest())
        saved_row = app.library_row(self.item_id)
        source_snapshot = {key: json.loads(saved_row[column] or default) for key, column, default in (
            ("segments", "segments_json", "[]"), ("speaker_profiles", "speaker_profiles_json", "{}"),
            ("speaker_names", "speaker_names_json", "{}"), ("session_profile", "session_profile_json", "{}"))}
        source_bytes = json.dumps(source_snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
        self.assertEqual(manifest["source_hash"], hashlib.sha256(source_bytes).hexdigest())
        speakers = json.loads(archive.read("speakers.json"))
        mapping = {speaker["raw_label"]: speaker["speaker_no"] for speaker in speakers}
        self.assertEqual(list(mapping), sorted(mapping))
        self.assertEqual(list(mapping.values()), list(range(1, len(mapping) + 1)))
        expected_labels = {"S_A", "S_B", "UNKNOWN"}
        if any(segment.get("speaker") == "S_Z" for segment in self.expected_preparation["original_segments"]) or any(
            segment.get("speaker") == "S_Z" for version in self.expected_preparation["versions"]
            for segment in version["source"]["segments"]):
            expected_labels.add("S_Z")
        self.assertEqual(set(mapping), expected_labels)
        for speaker in speakers:
            self.assertEqual(set(speaker), {"speaker_no", "raw_label", "display_name", "attributes"})
            label = speaker["raw_label"]
            profile = self.saved_profiles.get(label, {})
            expected_name = None
            if names:
                if "display_name" in profile and isinstance(profile["display_name"], str):
                    expected_name = profile["display_name"]
                elif label in self.saved_names and isinstance(self.saved_names[label], str):
                    expected_name = self.saved_names[label]
            self.assertEqual(speaker["display_name"], expected_name)
            self.assertEqual(speaker["attributes"], {
                key: profile[key] for key in attributes if key in profile})
        for expected, actual in zip(self.expected_preparation["rows"], rows, strict=True):
            self.assertEqual({key: actual[key] for key in preparation.FIELDS}, expected)
            self.assertEqual(actual["raw_speaker_label"], expected["speaker_id"])
            self.assertEqual(actual["speaker_no"], mapping.get(expected["speaker_id"]))
        for key, value in self.expected_preparation.items():
            if key not in {"rows", "versions", "original_segments"}:
                self.assertEqual(exported[key], value, key)
        for old, filtered in zip(self.expected_preparation["versions"], exported["versions"], strict=True):
            self.assertEqual(old["source_hash"], filtered["source_hash"])
            self.assertEqual(old["version"], filtered["version"])
            if names:
                self.assertEqual(filtered["source"]["speaker_names"], self.names)
            else:
                self.assertNotIn("speaker_names", filtered["source"])
            self.assertEqual(filtered["source"]["session_profile"], old["source"]["session_profile"])
            for label, profile in filtered["source"]["speaker_profiles"].items():
                self.assertTrue(set(profile).issubset(set(attributes) | {"speaker_label", "display_name"}))
                if not names:
                    self.assertNotIn("display_name", profile)
                self.assertNotIn("global_speaker_id", profile)
                self.assertNotIn("notes", profile)
        outline = json.loads(archive.read("outline.json"))
        self.assertEqual(outline["outline"], self.saved_outline)
        self.assertEqual(outline["provenance"], {
            "kind": "saved" if self.saved_outline is not None else "absent",
            "source_hash": self.expected_preparation["source_hash"],
            "input_version": self.expected_preparation["input_version"],
            "analysis_source_hash": self.expected_preparation["analysis_source_hash"],
        })
        self.assertEqual(json.loads(archive.read("schema.json"))["schema_version"], 1)
        all_text = b"\n".join(archive.read(name) for name in archive.namelist() if not name.endswith(".jpg")).decode("utf-8")
        documented_domains = archive.read("schema.json") + archive.read("README.md")
        self.assertIn(b"original_preparation_rows", documented_domains)
        self.assertNotIn(str(self.root), all_text)
        if not names:
            for name in self.names.values():
                self.assertNotIn(name, all_text)
        return archive, manifest

    def test_default_zip_preserves_saved_preparation_and_is_readonly(self):
        from gurumoji.web import export_routes

        before = self.snapshot()
        with patch.object(export_routes, "extract_frames", side_effect=AssertionError("disabled media read")), \
             patch.object(export_routes, "permitted_media", side_effect=AssertionError("disabled media stat")), \
             patch.object(export_routes, "media_identity", side_effect=AssertionError("disabled media identity")):
            response = self.export()
        self.assertEqual(response.status_code, 200, response.data[:1000])
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assert_bundle(response.data)
        self.assertEqual(before, self.snapshot())
        again = self.export()
        self.assertEqual(again.status_code, 200)
        self.assertEqual(response.data, again.data, "same saved input must have deterministic ZIP bytes")
        self.assertEqual(before, self.snapshot())

    def test_explicit_names_and_only_selected_raw_attribute(self):
        response = self.export(include_names=True, speaker_attributes=["organization"])
        self.assertEqual(response.status_code, 200, response.data[:1000])
        self.assert_bundle(response.data, names=True, attributes=["organization"])

    def test_absent_outline_and_migrated_original_status_remain_explicit(self):
        self.saved_outline = None
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET outline_json=NULL,original_segments_status=? WHERE id=?",
                               ("migrated_current_snapshot", self.item_id))
        self.expected_preparation = self.client.get(self.preparation_url).get_json()
        response = self.export()
        self.assertEqual(response.status_code, 200, response.data[:1000])
        archive, _ = self.assert_bundle(response.data)
        self.assertEqual(json.loads(archive.read("conversation.json"))["preparation"]["original_status"],
                         "migrated_current_snapshot")

    def test_legacy_missing_original_and_uncaptured_input_version_stay_null(self):
        with app.database_connection() as connection:
            connection.execute("DELETE FROM transcript_versions WHERE item_id=?", (self.item_id,))
            connection.execute("UPDATE library_items SET original_segments_json='[]',original_segments_status='unavailable' WHERE id=?",
                               (self.item_id,))
        self.expected_preparation = self.client.get(self.preparation_url).get_json()
        self.assertIsNone(self.expected_preparation["input_version"])
        self.assertEqual(self.expected_preparation["versions"], [])
        before = self.snapshot()
        response = self.export()
        self.assertEqual(response.status_code, 200, response.data[:1000])
        archive, manifest = self.assert_bundle(response.data)
        self.assertIsNone(manifest["input_version"])
        rows = [json.loads(line) for line in archive.read("utterances.jsonl").decode("utf-8").splitlines()]
        self.assertTrue(all(row["original_text"] is None for row in rows))
        self.assertTrue(all(row["original_status"] == "unavailable" for row in rows))
        self.assertEqual(before, self.snapshot())

    def test_malformed_options_and_attempted_path_url_injection_reject_readonly(self):
        before = self.snapshot()
        bad = [
            {"include_names": 1}, {"include_names": "false"},
            {"speaker_attributes": ["notes"]}, {"speaker_attributes": ["organization", "organization"]},
            {"expected_revision": True}, {"expected_revision": "1"},
            {"media_path": str(self.source)}, {"output_path": "../escape.zip"},
            {"url": "https://example.invalid/video"}, {"frames": {"enabled": False, "start": 0}},
            {"frames": {"enabled": True, "start": 0, "end": 601, "interval": 100}},
            {"frames": {"enabled": True, "start": 0, "end": 24, "interval": 1}},
            {"frames": {"enabled": True, "start": 0, "end": 1, "interval": 0.5}},
            {"frames": {"enabled": True, "start": True, "end": 1, "interval": 1}},
            {"frames": {"enabled": True, "start": 0, "end": 1, "interval": 1, "max_frames": 25}},
            {"frames": {"enabled": True, "start": 0, "end": 1, "interval": 1, "max_dimension": 1281}},
            {"frames": {"enabled": True, "start": 0, "end": 1, "interval": 1, "path": "../secret"}},
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                response = self.export(**payload)
                self.assertEqual(response.status_code, 400, response.data[:1000])
                self.assertTrue(response.get_json().get("error"))
        for content in ("null", "[]", "{", '{"frames":{"enabled":true,"start":NaN,"end":1,"interval":1}}'):
            with self.subTest(content=content):
                response = self.client.post(self.export_url, data=content, content_type="application/json")
                self.assertEqual(response.status_code, 400, response.data[:1000])
        self.assertEqual(before, self.snapshot())

    def test_missing_item_and_optimistic_revocation_do_not_download(self):
        self.assertEqual(self.client.post("/api/library/missing-item/ai-export.zip", json={}).status_code, 404)
        for payload in ({"expected_source_hash": "f" * 64}, {"expected_revision": 999}):
            response = self.export(**payload)
            self.assertEqual(response.status_code, 409, response.data[:1000])
            self.assertNotEqual(response.mimetype, "application/zip")
            self.assertTrue(response.get_json().get("error"))
        self.assertEqual(self.client.get(self.export_url).status_code, 405)

    def assert_video_bundle(self, content, *, names=False, attributes=()):
        from PIL import Image

        archive, manifest = self.assert_bundle(content, names=names, attributes=attributes, frames=True)
        index = [json.loads(line) for line in archive.read("frames/index.jsonl").decode("utf-8").splitlines()]
        self.assertEqual(manifest["frames"]["status"], "complete")
        self.assertIsNone(manifest["frames"]["reason"])
        self.assertEqual(manifest["frames"]["count"], 3)
        self.assertEqual(manifest["frames"]["media"]["kind"], "video")
        self.assertTrue(manifest["frames"]["media"]["identity_hash_domain"])
        self.assertEqual([frame["requested_time"] for frame in index], [0, 1, 2])
        self.assertEqual([frame["frame_id"] for frame in index], ["f0001", "f0002", "f0003"])
        self.assertEqual(len(index), 3)
        total = 0
        valid = [row for row in self.expected_preparation["rows"] if row["start"] is not None]
        for frame in index:
            self.assertNotIn("data", frame)
            path = frame["path"]
            self.assertEqual(path, f'frames/{frame["frame_id"]}.jpg')
            jpeg = archive.read(path)
            self.assertEqual(frame["sha256"], hashlib.sha256(jpeg).hexdigest())
            self.assertLessEqual(len(jpeg), 2 * 1024 * 1024)
            total += len(jpeg)
            with Image.open(io.BytesIO(jpeg)) as decoded:
                decoded.load()
                self.assertEqual(decoded.format, "JPEG")
                self.assertLessEqual(max(decoded.size), 64)
                self.assertGreater(min(decoded.size), 0)
            self.assertTrue(frame["method"])
            observed = frame["actual_time"]
            expected_refs = [] if observed is None else [
                row["segment_id"] for row in valid if row["start"] <= observed <= row["end"]]
            self.assertEqual(frame["utterance_ids"], expected_refs)
        self.assertLessEqual(total, 32 * 1024 * 1024)
        return archive, manifest

    def test_actual_synthetic_video_opt_in_decodes_and_leaves_sources_unchanged(self):
        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        before = self.snapshot()
        disabled = self.export()
        self.assertEqual(disabled.status_code, 200, disabled.data[:1000])
        self.assert_bundle(disabled.data)
        enabled = self.export(frames={"enabled": True, "start": 0, "end": 2,
                                      "interval": 1, "max_frames": 3, "max_dimension": 64})
        self.assertEqual(enabled.status_code, 200, enabled.data[:1000])
        self.assert_video_bundle(enabled.data)
        self.assertEqual(before, self.snapshot())

    @browser_support.ui_browser_test
    def test_browser_normal_local_download_real_api_zip_hashes_and_frames(self):
        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        before = self.snapshot()
        with self.http_server() as origin, browser_support.sandboxed_playwright_browser() as browser:
            for width in (1440, 390):
                with self.subTest(width=width):
                    context = browser.new_context(accept_downloads=True)
                    page = context.new_page()
                    errors, external, network, posted = [], [], [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("response", lambda response: network.append({
                        "method": response.request.method, "url": response.url, "status": response.status}))
                    page.on("request", lambda request: posted.append(request.post_data_json)
                            if request.url.endswith("ai-export.zip") else None)

                    def guard(route):
                        if urlsplit(route.request.url).hostname != "127.0.0.1":
                            external.append(route.request.url)
                            route.abort()
                        else:
                            route.continue_()

                    context.route("**/*", guard)
                    try:
                        panel = self.open_normal_export_panel(page, origin, width)
                        panel.locator("summary").focus()
                        page.keyboard.press("Tab")
                        self.assertTrue(panel.locator('[data-ai-export-names]').evaluate("node => node === document.activeElement"))
                        page.keyboard.press("Space")
                        self.assertTrue(panel.locator('[data-ai-export-names]').is_checked())
                        page.keyboard.press("Space")
                        button = panel.get_by_role("button", name="AI向け生データZIPをダウンロード", exact=True)
                        button.focus()
                        with page.expect_download() as text_download:
                            page.keyboard.press("Enter")
                        text_content = Path(text_download.value.path()).read_bytes()
                        self.assert_bundle(text_content)
                        self.assertEqual(posted[0]["frames"], {"enabled": False})
                        self.assertFalse(posted[0]["include_names"])
                        self.assertEqual(posted[0]["speaker_attributes"], [])
                        self.assertEqual(posted[0]["expected_source_hash"], self.expected_preparation["source_hash"])
                        self.assertEqual(posted[0]["expected_revision"], self.expected_preparation["revision"])
                        panel.get_by_label("話者の氏名・表示名を含める", exact=True).check()
                        panel.get_by_label("組織", exact=True).check()
                        panel.get_by_label("動画フレームを含める（初期値OFF）", exact=True).check()
                        for key, value in {"start": "0", "end": "2", "interval": "1", "max_frames": "3", "max_dimension": "64"}.items():
                            panel.locator(f'[data-ai-export-frame="{key}"]').fill(value)
                        with page.expect_download() as frame_download:
                            button.click()
                        frame_content = Path(frame_download.value.path()).read_bytes()
                        self.assert_video_bundle(frame_content, names=True, attributes=["organization"])
                        self.assertEqual(posted[1]["speaker_attributes"], ["organization"])
                        self.assertEqual(posted[1]["frames"], {"enabled": True, "start": 0, "end": 2,
                            "interval": 1, "max_frames": 3, "max_dimension": 64})
                        self.assertEqual([r["status"] for r in network if r["url"].endswith("ai-export.zip")], [200, 200])
                        self.assertIn("外部AIへ自動送信していません", panel.locator('[data-ai-export-status]').inner_text())
                        self.assertEqual(errors, [])
                        self.assertEqual(external, [])
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"))
                        self.save_browser_evidence(page, f"download-success-{width}", network)
                        evidence = os.environ.get("GURUMOJI_AI_EXPORT_EVIDENCE_DIR")
                        if evidence:
                            target = Path(evidence)
                            (target / f"browser-text-{width}.zip").write_bytes(text_content)
                            (target / f"browser-frames-{width}.zip").write_bytes(frame_content)
                    finally:
                        context.close()
        self.assertEqual(before, self.snapshot())

    def test_missing_media_and_external_saved_reference_fail_without_zip(self):
        options = {"enabled": True, "start": 0, "end": 1, "interval": 1}
        for reference in (None, str(self.root / "absent.mp4"), str(self.source),
                          "https://example.invalid/video.mp4", "../outside.mp4"):
            with self.subTest(reference=reference):
                with app.database_connection() as connection:
                    connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (reference, self.item_id))
                before = self.snapshot()
                response = self.export(frames=options)
                self.assertEqual(response.status_code, 422, response.data[:1000])
                self.assertNotEqual(response.mimetype, "application/zip")
                self.assertTrue(response.get_json().get("error"))
                self.assertEqual(before, self.snapshot())

    def test_audio_only_media_is_explicitly_unsupported(self):
        folder = app.MEDIA_DIRECTORY / self.item_id
        folder.mkdir(parents=True, exist_ok=True)
        audio = folder / "synthetic.wav"
        with wave.open(str(audio), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(8000)
            stream.writeframes(b"\0\0" * 8000)
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(audio), self.item_id))
        before = self.snapshot()
        response = self.export(frames={"enabled": True, "start": 0, "end": 0, "interval": 1})
        self.assertEqual(response.status_code, 422, response.data[:1000])
        self.assertNotEqual(response.mimetype, "application/zip")
        self.assertTrue(response.get_json().get("error"))
        self.assertEqual(before, self.snapshot())

    def test_adversarial_saved_item_id_cannot_widen_permitted_media_root(self):
        video = self.synthetic_video()
        current_id = self.item_id
        for unsafe_id in (".", "..", "C:\\outside", "nested\\child"):
            with self.subTest(item_id=unsafe_id):
                with app.database_connection() as connection:
                    connection.execute("UPDATE library_items SET id=?,media_path=? WHERE id=?",
                                       (unsafe_id, str(video), current_id))
                current_id = unsafe_id
                before = self.snapshot()
                response = self.client.post(f"/api/library/{quote(unsafe_id, safe='')}/ai-export.zip",
                    json={"frames": {"enabled": True, "start": 0, "end": 0, "interval": 1}})
                self.assertEqual(response.status_code, 422, response.data[:1000])
                self.assertNotEqual(response.mimetype, "application/zip")
                self.assertTrue(response.get_json().get("error"))
                self.assertEqual(before, self.snapshot())

    @unittest.skipUnless(os.name == "nt", "Windows Junction acceptance applies only on Windows")
    def test_actual_windows_junction_escape_rejects_before_decode(self):
        from gurumoji.web import export_routes
        from gurumoji.services import ai_data_export_frames as adapter

        video = self.synthetic_video()
        outside = self.root / "outside-item"
        outside.mkdir()
        shutil.copyfile(video, outside / "synthetic.mp4")
        junction = video.parent / "junction"
        script = self.root / "create-junction.ps1"
        script.write_text('param([string]$Link,[string]$Target)\n'
                          'New-Item -ItemType Junction -Path $Link -Target $Target -ErrorAction Stop | Out-Null\n',
                          encoding="utf-8")
        created = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-File", str(script),
                                  "-Link", str(junction), "-Target", str(outside)],
                                 capture_output=True, timeout=15)
        if created.returncode:
            self.skipTest("unprivileged synthetic Junction creation unavailable")

        def remove_junction_only():
            self.assertTrue(junction.is_junction())
            self.assertEqual(junction.resolve(), outside.resolve())
            self.assertTrue(outside.resolve().is_relative_to(self.root.resolve()))
            self.assertTrue(junction.parent.resolve().is_relative_to(self.root.resolve()))
            junction.rmdir()
            self.assertTrue((outside / "synthetic.mp4").is_file(), "junction removal must retain target")

        self.addCleanup(remove_junction_only)
        self.assertTrue(junction.is_junction())
        escaped = junction / "synthetic.mp4"
        self.assertEqual(escaped.resolve(), (outside / "synthetic.mp4").resolve())
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(escaped), self.item_id))
        before = self.snapshot()
        with patch.object(export_routes, "extract_frames", wraps=export_routes.extract_frames) as extraction, \
             patch.object(adapter, "_run_bounded", side_effect=AssertionError("junction must reject before decoder")) as decoder:
            response = self.export(frames={"enabled": True, "start": 0, "end": 0, "interval": 1})
        self.assertEqual(extraction.call_count, 1)
        decoder.assert_not_called()
        self.assertEqual(response.status_code, 422, response.data)
        self.assertEqual(response.get_json()["frames"], {"status": "unavailable", "reason": "media_not_permitted"})
        self.assertEqual(before, self.snapshot())

    def test_archive_validator_rejects_hash_schema_reference_and_path_tampering(self):
        from gurumoji.services.ai_data_export_bundle import validate_ai_bundle_zip

        response = self.export()
        self.assertEqual(response.status_code, 200, response.data[:1000])
        archive = self.parse_zip(response.data)
        original = {name: archive.read(name) for name in archive.namelist()}

        def rebuild(values, *, rehash=True, duplicate=False, symlink=False):
            values = dict(values)
            if rehash:
                manifest = json.loads(values["manifest.json"])
                for entry in manifest["files"]:
                    if entry["path"] in values:
                        data = values[entry["path"]]
                        entry.update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
                values["manifest.json"] = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for name, data in values.items():
                    info = zipfile.ZipInfo(name)
                    if symlink and name == "README.md":
                        info.create_system = 3
                        info.external_attr = 0o120777 << 16
                    out.writestr(info, data)
                if duplicate:
                    with self.assertWarns(UserWarning):
                        out.writestr("README.md", values["README.md"])
            return stream.getvalue()

        cases = {"bad_hash": rebuild({**original, "README.md": b"changed"}, rehash=False),
                 "duplicate": rebuild(original, duplicate=True), "symlink": rebuild(original, symlink=True)}
        self.assertEqual(validate_ai_bundle_zip(rebuild(original)), json.loads(original["manifest.json"]),
                         "the independent rewriter must preserve a valid benign archive")
        for path in ("../escape", "/absolute", "C:/absolute", "frames\\escape.jpg", "extra.json"):
            cases[path] = rebuild({**original, path: b"untrusted"})
        changed = dict(original)
        schema = json.loads(changed["schema.json"])
        schema["schema_version"] = 99
        changed["schema.json"] = json.dumps(schema).encode()
        cases["schema_version"] = rebuild(changed)
        conversation = json.loads(original["conversation.json"])
        conversation["preparation"]["rows"][0]["speaker_no"] = 999
        changed = {**original,
                   "conversation.json": json.dumps(conversation, ensure_ascii=False).encode("utf-8"),
                   "utterances.jsonl": ("\n".join(json.dumps(row, ensure_ascii=False)
                       for row in conversation["preparation"]["rows"]) + "\n").encode("utf-8")}
        cases["rehash_invalid_speaker_reference"] = rebuild(changed)
        for name, content in cases.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                validate_ai_bundle_zip(content)

    def test_large_frame_request_times_reject_invalid_grids_after_rehash(self):
        from gurumoji.services import ai_data_export_bundle as bundle

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        before = self.snapshot()
        with patch.object(bundle, "build_ai_bundle", wraps=bundle.build_ai_bundle) as builder:
            response = self.export(frames={"enabled": True, "start": 0, "end": 1,
                                          "interval": 1, "max_frames": 2, "max_dimension": 64})
        self.assertEqual(response.status_code, 200, response.data[:1000])
        payload = builder.call_args.args[0]
        archive = self.parse_zip(response.data)
        original = {name: archive.read(name) for name in archive.namelist()}
        self.assertEqual(bundle.validate_ai_bundle_zip(response.data), json.loads(original["manifest.json"]))
        decimal_payload = copy.deepcopy(payload)
        decimal_times = (1.3, 2.3)
        self.assertLess(decimal_times[1] - decimal_times[0], 1,
                        "exercise ordinary decimal subtraction rounding")
        for frame, requested in zip(decimal_payload["frames"]["items"], decimal_times, strict=True):
            frame["requested_time"] = requested
        decimal_zip = bundle.build_ai_bundle(decimal_payload)
        decimal_archive = self.parse_zip(decimal_zip)
        self.assertEqual(bundle.validate_ai_bundle_zip(decimal_zip),
                         json.loads(decimal_archive.read("manifest.json")))
        self.assertEqual([json.loads(line)["requested_time"] for line in
                          decimal_archive.read("frames/index.jsonl").decode().splitlines()], list(decimal_times))
        for label, times in (("duplicate", (1e16, 1e16)), ("descending", (1e16, 1e16 - 2)),
                             ("subsecond", (1e15, 1e15 + 0.75))):
            changed_payload = copy.deepcopy(payload)
            for frame, requested in zip(changed_payload["frames"]["items"], times, strict=True):
                frame["requested_time"] = requested
            values = dict(original)
            index = [json.loads(line) for line in values["frames/index.jsonl"].decode().splitlines()]
            for frame, requested in zip(index, times, strict=True):
                frame["requested_time"] = requested
            values["frames/index.jsonl"] = ("\n".join(json.dumps(frame) for frame in index) + "\n").encode()
            manifest = json.loads(values["manifest.json"])
            for entry in manifest["files"]:
                data = values[entry["path"]]
                entry.update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
            values["manifest.json"] = json.dumps(manifest).encode()
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as output:
                for path, data in values.items():
                    output.writestr(path, data)
            altered = stream.getvalue()
            self.parse_zip(altered)
            evidence = os.environ.get("GURUMOJI_AI_EXPORT_EVIDENCE_DIR")
            if evidence:
                (Path(evidence) / f"large-time-{label}.zip").write_bytes(altered)
            with self.subTest(case=label, boundary="payload"), self.assertRaises(ValueError):
                bundle.build_ai_bundle(changed_payload)
            with self.subTest(case=label, boundary="archive"), self.assertRaises(ValueError):
                bundle.validate_ai_bundle_zip(altered)
        self.assertEqual(before, self.snapshot())

    def test_archive_oversize_rejects_before_member_decompression(self):
        from gurumoji.services.ai_data_export_bundle import validate_ai_bundle_zip

        response = self.export()
        self.assertEqual(response.status_code, 200, response.data[:1000])
        original = self.parse_zip(response.data)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for name in original.namelist():
                out.writestr(name, b"x" * (64 * 1024 * 1024 + 1) if name == "README.md" else original.read(name))
        compressed = stream.getvalue()
        self.assertLess(len(compressed), 1024 * 1024)
        with patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("oversize must reject before decompression")):
            with self.assertRaises(ValueError):
                validate_ai_bundle_zip(compressed)

    def test_fixture_has_saved_revisions_lineage_and_null_distinct_from_zero(self):
        data = self.expected_preparation
        self.assertEqual(data["input_version"], 2)
        rows = {row["segment_id"]: row for row in data["rows"]}
        self.assertEqual(rows["root"]["original_text"], self.original_text)
        self.assertEqual(rows["root"]["text"], self.current_text)
        self.assertEqual(rows["zero"]["start"], 0)
        self.assertIsNone(rows["unknown"]["start"])
        self.assertIsNone(rows["unknown"]["speaker_id"])
        self.assertEqual(rows["split"]["source_segment_ids"], ["root"])
        self.assertIsNone(rows["split"]["original_text"])
        self.assertEqual(len(data["versions"]), 2)
        self.assertEqual(len(data["review_history"]), 1)
        before = self.snapshot()
        self.assertEqual(self.client.get(self.preparation_url).get_json(), data)
        self.assertEqual(before, self.snapshot())

    def test_readonly_projection_reuses_complete_saved_preparation(self):
        from gurumoji.services.ai_data_export import (
            ai_export_payload, preparation_export_snapshot, validate_export_request,
        )

        before = self.snapshot()
        with app.database_connection() as connection:
            connection.execute("PRAGMA query_only=ON")
            row = connection.execute("SELECT * FROM library_items WHERE id=?", (self.item_id,)).fetchone()
            segments = app.row_segments(row)
            saved = preparation_export_snapshot(connection, row, segments)
            self.assertEqual(saved, self.expected_preparation)
            payload = ai_export_payload(row, segments, copy.deepcopy(saved), validate_export_request({}))
        self.assertEqual(payload["outline"], self.saved_outline)
        self.assertEqual(payload["frames"]["status"], "disabled")
        self.assertEqual(payload["selection"], {"include_names": False, "speaker_attributes": []})
        for expected, actual in zip(saved["rows"], payload["preparation"]["rows"], strict=True):
            self.assertEqual({key: actual[key] for key in preparation.FIELDS}, expected)
        self.assertEqual([speaker["raw_label"] for speaker in payload["speakers"]],
                         ["S_A", "S_B", "S_Z", "UNKNOWN"])
        self.assertTrue(all(speaker["display_name"] is None for speaker in payload["speakers"]))
        self.assertTrue(all(speaker["attributes"] == {} for speaker in payload["speakers"]))
        for version in payload["preparation"]["versions"]:
            self.assertNotIn("speaker_names", version["source"])
            self.assertTrue(all(set(profile) == {"speaker_label"}
                                for profile in version["source"]["speaker_profiles"].values()))
        self.assertEqual(before, self.snapshot())

    def test_real_frame_adapter_observes_decoder_pts_instead_of_requested_time(self):
        from PIL import Image
        from gurumoji.services.ai_data_export import validate_export_request
        from gurumoji.services import ai_data_export_frames as adapter

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        row = app.library_row(self.item_id)
        options = validate_export_request({"frames": {"enabled": True, "start": 0.25, "end": 2.25,
            "interval": 1, "max_frames": 3, "max_dimension": 64}})["frames"]
        before = self.snapshot()
        deadlines = []
        original_run = adapter._run_bounded

        def record_deadline(args, deadline, cancelled):
            deadlines.append(deadline)
            return original_run(args, deadline, cancelled)

        started = time.monotonic()
        with patch.object(adapter, "_run_bounded", side_effect=record_deadline):
            result = adapter.extract_frames(row, self.expected_preparation["rows"], options,
                                    media_directory=lambda: app.MEDIA_DIRECTORY, path_is_within=app.path_is_within)
        self.assertEqual(len(deadlines), 3)
        self.assertEqual(len(set(deadlines)), 1, "all decoder processes must share one cumulative deadline")
        self.assertGreaterEqual(deadlines[0] - started, 29)
        self.assertLessEqual(deadlines[0] - started, 31)
        self.assertEqual(result["status"], "complete")
        domain = result["media"]["identity_hash_domain"]
        self.assertTrue(domain)
        if domain == "stat_identity":
            self.assertEqual(result["media"]["identity"]["size"], video.stat().st_size)
        else:
            self.assertIn(hashlib.sha256(video.read_bytes()).hexdigest(), json.dumps(result["media"]["identity"]),
                          "a content-identity domain must carry the actual synthetic media hash")
        self.assertEqual([item["requested_time"] for item in result["items"]], [0.25, 1.25, 2.25])
        self.assertEqual([item["actual_time"] for item in result["items"]], [0.5, 1.5, 2.5])
        for item in result["items"]:
            self.assertEqual(item["method"], "ffmpeg_showinfo_pts")
            self.assertNotEqual(item["actual_time"], item["requested_time"])
            self.assertLessEqual(len(item["data"]), 2 * 1024 * 1024)
            with Image.open(io.BytesIO(item["data"])) as image:
                image.load()
                self.assertLessEqual(max(image.size), 64)
            expected_refs = [row["segment_id"] for row in self.expected_preparation["rows"]
                if row["start"] is not None and row["start"] <= item["actual_time"] <= row["end"]]
            self.assertEqual(item["utterance_ids"], expected_refs)
        self.assertEqual(before, self.snapshot())

    def test_noffmpeg_timeout_partial_failure_are_explicit_http_errors(self):
        from gurumoji.services import ai_data_export_frames as adapter

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        options = {"enabled": True, "start": 0, "end": 5, "interval": 5, "max_frames": 2}
        before = self.snapshot()
        with patch.object(adapter.shutil, "which", return_value=None):
            missing = self.export(frames=options)
        self.assertEqual(missing.status_code, 422, missing.data)
        self.assertEqual(missing.get_json()["frames"], {"status": "unavailable", "reason": "ffmpeg_unavailable"})
        with patch.object(adapter, "BUDGET_SECONDS", -1):
            timeout = self.export(frames=options)
        self.assertEqual(timeout.status_code, 408, timeout.data)
        self.assertEqual(timeout.get_json()["frames"]["reason"], "frame_timeout")
        partial = self.export(frames=options)
        self.assertEqual(partial.status_code, 422, partial.data)
        self.assertEqual(partial.get_json()["frames"]["status"], "partial")
        self.assertNotEqual(partial.mimetype, "application/zip")
        self.assertEqual(before, self.snapshot())

    def test_subprocess_deadline_kills_actual_child_and_caps_output(self):
        from gurumoji.services.ai_data_export import ExportError
        from gurumoji.services.ai_data_export_frames import _run_bounded

        started = time.monotonic()
        with self.assertRaises(ExportError) as caught:
            _run_bounded([sys.executable, "-c", "import time;time.sleep(5)"], started + 0.1, None)
        self.assertEqual(caught.exception.status, 408)
        self.assertLess(time.monotonic() - started, 3)
        with self.assertRaises(ExportError) as caught:
            _run_bounded([sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'x'*(3*1024*1024))"],
                         time.monotonic() + 5, None)
        self.assertEqual(caught.exception.reason, "frame_output_limit")

    def test_frame_identity_substitution_during_real_decode_rejects_409(self):
        from gurumoji.services import ai_data_export_frames as adapter

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        original = video.read_bytes()
        before_db = self.snapshot()["db"]
        original_run = adapter._run_bounded
        calls = []

        def substitute(*args, **kwargs):
            result = original_run(*args, **kwargs)
            calls.append(1)
            if len(calls) == 1:
                video.write_bytes(original + b"INDEPENDENT_SYNTHETIC_SUBSTITUTION")
            return result

        with patch.object(adapter, "_run_bounded", side_effect=substitute):
            response = self.export(frames={"enabled": True, "start": 0, "end": 1, "interval": 1})
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.get_json()["frames"], {"status": "failed", "reason": "media_changed"})
        self.assertEqual(len(calls), 1, "decode must stop before reading substituted media")
        self.assertEqual(self.snapshot()["db"], before_db)
        self.assertEqual(video.read_bytes(), original + b"INDEPENDENT_SYNTHETIC_SUBSTITUTION")

    def test_source_change_after_real_zip_build_is_rejected_409(self):
        from gurumoji.services import ai_data_export_bundle as bundle

        actual_build = bundle.build_ai_bundle
        original = app.library_row(self.item_id)["original_segments_json"]

        def change_after_build(payload):
            data = actual_build(payload)
            segments = copy.deepcopy(self.current)
            segments[0]["text"] = "INDEPENDENT_SYNTHETIC_CONCURRENT_EDIT"
            with app.database_connection() as connection:
                connection.execute("UPDATE library_items SET segments_json=? WHERE id=?",
                                   (json.dumps(segments, ensure_ascii=False), self.item_id))
            return data

        with patch.object(bundle, "build_ai_bundle", side_effect=change_after_build):
            response = self.export()
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.get_json()["error"], "source_changed")
        self.assertNotEqual(response.mimetype, "application/zip")
        self.assertEqual(app.library_row(self.item_id)["original_segments_json"], original)

    def test_disappearing_media_stat_after_real_zip_build_rejects_409(self):
        from gurumoji.web import export_routes

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        before = self.snapshot()
        with patch.object(export_routes, "media_identity", side_effect=FileNotFoundError("synthetic post-build stat disappearance")):
            response = self.export(frames={"enabled": True, "start": 0, "end": 0, "interval": 1})
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.get_json()["frames"], {"status": "failed", "reason": "media_changed"})
        self.assertNotEqual(response.mimetype, "application/zip")
        self.assertEqual(before, self.snapshot())

    def test_media_resolution_failure_is_explicit_422(self):
        from gurumoji.services.ai_data_export import ExportError
        from gurumoji.services import ai_data_export_frames as adapter

        video = self.synthetic_video()
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET media_path=? WHERE id=?", (str(video), self.item_id))
        row = app.library_row(self.item_id)
        for error in (OSError("synthetic resolve failure"), RuntimeError("synthetic symlink loop")):
            with self.subTest(error=type(error).__name__), patch.object(adapter.Path, "resolve", side_effect=error):
                with self.assertRaises(ExportError) as caught:
                    adapter.permitted_media(row, lambda: app.MEDIA_DIRECTORY, app.path_is_within)
                self.assertEqual(caught.exception.status, 422)
                self.assertEqual(caught.exception.frame_status, "unavailable")


if __name__ == "__main__":
    unittest.main()
