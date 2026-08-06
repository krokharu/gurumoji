import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server

import app


def browser_executable() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


class BrowserJobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-browser-")
        self.root = Path(self.temporary.name)
        self.original_database = app.DATABASE_FILE
        app.DATABASE_FILE = self.root / "library.sqlite3"
        app.initialize_library()
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None

    def tearDown(self):
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None
        app.DATABASE_FILE = self.original_database
        self.temporary.cleanup()

    def test_real_browser_restores_the_active_job(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest("Chrome, Edge, or Chromium is required for the browser smoke test")

        marker = "E2E_ACTIVE_JOB_RESTORED"
        job = app.JobRecord(
            id="browser-active-job",
            source_name="browser-test.wav",
            output_dir=self.root / "output",
            write_srt=False,
            write_json=True,
            status="running",
            progress=37,
            message=marker,
            logs=[marker],
            ai_usage={
                "provider": "openai", "model": "gpt-browser-test", "request_count": 2,
                "input_tokens": 1234, "output_tokens": 321, "total_tokens": 1555,
                "cached_tokens": 100, "reasoning_tokens": 25, "reported": True,
            },
        )
        with app.jobs_lock:
            app.jobs[job.id] = job

        machine = {
            "cpu": {"available": True, "name": "Test CPU", "logical_threads": 4},
            "gpu": {"cuda_available": False, "reason": "test", "vram_gib": 0},
            "memory_gib": 8,
            "recommended": {
                "model_name": "tiny",
                "device": "cpu",
                "diarization_device": "cpu",
            },
        }
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        profile = self.root / "browser-profile"
        url = f"http://127.0.0.1:{server.server_port}/"
        try:
            with (
                patch.object(app, "get_machine_profile", return_value=machine),
                patch.object(app, "load_token_config", return_value=app.TokenConfig()),
                patch.object(
                    app,
                    "system_activity_snapshot",
                    return_value={
                        "sampled_at": "2026-07-31T00:00:00+00:00",
                        "cpu": {"available": True, "utilization_percent": 42},
                        "memory": {
                            "available": True,
                            "utilization_percent": 55,
                            "used_gib": 8.8,
                            "total_gib": 16.0,
                        },
                        "gpu": {
                            "available": True,
                            "utilization_percent": 64,
                            "memory_used_gib": 4.0,
                            "memory_total_gib": 12.0,
                            "memory_percent": 33,
                        },
                        "disk": {
                            "available": True,
                            "read_active": True,
                            "write_active": True,
                            "read_mib_per_second": 1.5,
                            "write_mib_per_second": 0.5,
                        },
                    },
                ),
            ):
                completed = subprocess.run(
                    [
                        browser,
                        "--headless=new",
                        "--disable-gpu",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--no-sandbox",
                        f"--user-data-dir={profile}",
                        "--virtual-time-budget=5000",
                        "--dump-dom",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        self.assertIn(marker, completed.stdout)
        self.assertIn("37%", completed.stdout)
        self.assertIn('id="progress-stage-label">文字起こし</strong>', completed.stdout)
        self.assertIn('id="progress-activity-label">RUNNING</small>', completed.stdout)
        self.assertIn('id="monitor-cpu-value">42.0%</strong>', completed.stdout)
        self.assertIn('id="monitor-gpu-value">64%</strong>', completed.stdout)
        self.assertIn('id="monitor-memory-value">55%</strong>', completed.stdout)
        self.assertRegex(completed.stdout, r'id="monitor-read-light" class="[^"]*is-active')
        self.assertRegex(completed.stdout, r'id="monitor-write-light" class="[^"]*is-active')
        self.assertIn('id="progress-ai-usage"', completed.stdout)
        self.assertIn('data-ai-total="">1,555</strong>', completed.stdout)
        self.assertIn('data-ai-provider="">OpenAI</strong>', completed.stdout)
        progress_tag = re.search(
            r'<section\b[^>]*\bid="progress-card"[^>]*>', completed.stdout
        )
        self.assertIsNotNone(progress_tag)
        self.assertNotRegex(progress_tag.group(0), r'\shidden(?:\s|=|>)')

    def test_real_browser_renders_pre_survey_dashboard(self):
        browser = browser_executable()
        if browser is None:
            self.skipTest("Chrome, Edge, or Chromium is required for the browser smoke test")

        app.save_speaker_registry_records(
            [
                {
                    "id": "survey_a",
                    "participant_code": "P-01",
                    "pseudonym": "参加者A",
                    "attributes": {"満足度": "5", "年齢層": "30代", "利用歴": "3年以上"},
                    "active": True,
                },
                {
                    "id": "survey_b",
                    "participant_code": "P-02",
                    "pseudonym": "参加者B",
                    "attributes": {"満足度": "3", "年齢層": "40代", "利用歴": "1年未満"},
                    "active": True,
                },
                {
                    "id": "survey_c",
                    "participant_code": "P-03",
                    "pseudonym": "参加者C",
                    "attributes": {"満足度": "4", "年齢層": "30代", "利用歴": "1年未満"},
                    "active": True,
                },
            ],
            expected_revision=0,
        )
        machine = {
            "cpu": {"available": True, "name": "Test CPU", "logical_threads": 4},
            "gpu": {"cuda_available": False, "reason": "test", "vram_gib": 0},
            "memory_gib": 8,
            "recommended": {
                "model_name": "tiny",
                "device": "cpu",
                "diarization_device": "cpu",
            },
        }
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        profile = self.root / "survey-browser-profile"
        url = f"http://127.0.0.1:{server.server_port}/?view=speakers"
        try:
            with (
                patch.object(app, "get_machine_profile", return_value=machine),
                patch.object(app, "load_token_config", return_value=app.TokenConfig()),
            ):
                completed = subprocess.run(
                    [
                        browser,
                        "--headless=new",
                        "--disable-gpu",
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--no-sandbox",
                        f"--user-data-dir={profile}",
                        "--virtual-time-budget=7000",
                        "--dump-dom",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        self.assertIn('id="registry-survey-metric">3</strong>', completed.stdout)
        self.assertIn('class="speaker-survey-overview"', completed.stdout)
        self.assertIn('class="speaker-survey-bars"', completed.stdout)
        self.assertIn(
            'class="speaker-survey-panel speaker-survey-crosstab"',
            completed.stdout,
        )
        self.assertIn('class="speaker-survey-table participant"', completed.stdout)
        self.assertIn("満足度", completed.stdout)
        self.assertIn("年齢層", completed.stdout)


if __name__ == "__main__":
    unittest.main()
