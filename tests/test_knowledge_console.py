import sys
import tempfile
import unittest
import json
import hashlib
import importlib.util
import time
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path
from devtools.knowledge_console.app import (
    _ask_local_llm,
    DriveApiQueue,
    _preferred_browser,
    _read_drive_session,
    FolderQueue,
    _check_colab_connection,
    _enqueue_drive_task,
    _signed_payload,
    _wait_for_drive_result,
    create_app,
)
from devtools.knowledge_console.store import KnowledgeConsoleStore, expert_projection


GROUND_CONTEXT = "Sources\n" + json.dumps({"evidence": [{"note_id": "note-test", "sha256": "a" * 64,
    "excerpt": "The source includes verified input for this test."}]})


def grounded_answer(findings):
    return json.dumps({"status": "completed", "findings": findings, "missing_inputs": [],
                       "citations": [{"note_id": "note-test", "quote": "verified input for this test"}]})


class FakeDriveRequest:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeDriveFiles:
    def __init__(self, service):
        self.service = service

    def list(self, *, q, **_kwargs):
        name = q.split("name = '", 1)[1].split("'", 1)[0]
        parent = q.split("' in parents", 1)[0].rsplit("'", 1)[1]
        found = [
            {
                "id": record["id"],
                "size": str(len(record["raw"])),
                "ownedByMe": record["ownedByMe"],
                "shared": record["shared"],
            }
            for record in self.service.records
            if record["name"] == name and parent in record["parents"]
        ]
        return FakeDriveRequest({"files": found})

    def get_media(self, *, fileId, **_kwargs):
        record = next(item for item in self.service.records if item["id"] == fileId)
        return FakeDriveRequest(record["raw"])

    def create(self, *, body, media_body, **_kwargs):
        record = self.service.add(
            body["name"], media_body.getbytes(0, media_body.size()), parents=body["parents"]
        )
        return FakeDriveRequest({"id": record["id"]})


class FakeDriveService:
    """Just enough of the Drive v3 client for the queue and session contracts."""

    def __init__(self):
        self.records = []

    @property
    def files_by_name(self):
        return {record["name"]: record for record in self.records}

    def files(self):
        return FakeDriveFiles(self)

    def add(self, name, raw, *, parents, owned_by_me=True, shared=False):
        record = {
            "id": f"id-{len(self.records)}",
            "name": name,
            "parents": parents,
            "raw": raw,
            "ownedByMe": owned_by_me,
            "shared": shared,
        }
        self.records.append(record)
        return record

    def put(self, name, payload, *, parents=("folder-id-for-tests",), **flags):
        return self.add(
            name, json.dumps(payload, ensure_ascii=False).encode("utf-8"), parents=list(parents), **flags
        )


class FakeDriveAuthorization:
    def __init__(self, service):
        self._service = service

    def has_credentials(self):
        return True

    def service(self, *, interactive=False):
        return self._service


class KnowledgeConsoleStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-knowledge-console-")
        self.data_dir = Path(self.temporary.name) / "data"
        self.store = KnowledgeConsoleStore(self.data_dir)

    def tearDown(self):
        self.temporary.cleanup()

    def test_real_task_lifecycle_and_revision(self):
        task = self.store.create_task(
            {
                "title": "テーマ分析の再評価",
                "expert_id": "thematic-analysis",
                "actor": "a100",
                "model_id": "qwen3-80b",
            }
        )
        running = self.store.execute_task(
            task["task_id"], expected_revision=task["revision"], simulation=False
        )
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["progress"], 5)
        self.assertEqual(running["phase"], "Colab A100への送信待ち")
        self.assertFalse(running["simulation"])
        progressed = self.store.update_real_task(
            task["task_id"], progress=45, phase="A100実モデルで推論中"
        )
        self.assertEqual(progressed["progress"], 45)
        completed = self.store.complete_real_task(
            task["task_id"],
            {"simulation": False, "provider": "test-a100", "content": "実応答"},
        )
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["progress"], 100)
        self.assertEqual(completed["phase"], "応答受信・未評価")
        self.assertEqual(completed["run_count"], 1)
        self.assertFalse(completed["simulation"])
        self.assertEqual(completed["result"]["content"], "実応答")
        with self.assertRaisesRegex(RuntimeError, "revision conflict"):
            self.store.execute_task(
                task["task_id"], expected_revision=task["revision"], simulation=False
            )

    def test_repeating_task_settings_are_validated(self):
        base = {"title": "反復", "expert_id": "thematic-analysis", "model_id": "qwen3-80b"}
        task = self.store.create_task({**base, "actor": "a100", "target_score": "80"})
        self.assertEqual((task["target_score"], task["max_iterations"]), (80, 5))
        plain = self.store.create_task({**base, "actor": "a100"})
        self.assertEqual((plain["target_score"], plain["max_iterations"]), (None, 1))
        with self.assertRaisesRegex(ValueError, "A100担当タスクだけ"):
            self.store.create_task(
                {**base, "actor": "local", "model_id": "local-default", "target_score": 80}
            )
        with self.assertRaisesRegex(ValueError, "1〜100"):
            self.store.create_task({**base, "actor": "a100", "target_score": 0})
        with self.assertRaisesRegex(ValueError, "最大回数"):
            self.store.create_task({**base, "actor": "a100", "target_score": 80, "max_iterations": 11})

    def test_default_backlog_creates_twenty_tasks_once(self):
        self.assertEqual(self.store.seed_default_tasks(), 20)
        self.assertEqual(self.store.seed_default_tasks(), 0)
        tasks = self.store.list_tasks()
        self.assertEqual(len(tasks), 20)
        self.assertEqual([task["position"] for task in tasks], list(range(1, 21)))
        self.assertTrue(all(task["progress"] == 0 for task in tasks))
        self.assertTrue(all(task["phase"] == "未実行" for task in tasks))
        self.assertTrue(all(task["decision_mode"] in {"program", "local_llm"} for task in tasks))
        a100_tasks = [task for task in tasks if task["actor"] == "a100"]
        self.assertEqual(len(a100_tasks), 11)
        self.assertEqual(
            [task["position"] for task in a100_tasks],
            sorted(task["position"] for task in a100_tasks),
        )

    def test_trace_uses_ordered_coarse_knowledge_blocks(self):
        trace = self.store.create_trace(
            {
                "question": "参加者間の発話量を分析してください。",
                "expert_id": "participation-balance",
                "model_id": "qwen3-80b",
            }
        )
        self.assertEqual(trace["status"], "completed")
        self.assertEqual(len(trace["events"]), 7)
        self.assertEqual(
            [event["payload"]["step"] for event in trace["events"]],
            list(range(1, 8)),
        )
        self.assertEqual(
            [event["payload"]["block_id"] for event in trace["events"]],
            [
                "input-layer",
                "obsidian-layer-1",
                "obsidian-layer-2",
                "obsidian-layer-3",
                "thought-buffer",
                "label-generation",
                "output-data",
            ],
        )
        self.assertTrue(trace["result"]["simulation"])

    def test_summary_reads_empty_worker_tables_without_faking_usage(self):
        summary = self.store.summary()
        self.assertEqual(summary["counts"]["experts"], 17)
        self.assertIsNone(summary["budget"]["usage"])
        self.assertEqual(summary["budget"]["state"], "unknown")
        self.assertTrue(all(row["sample"] for row in expert_projection()))


class KnowledgeConsoleA100AdapterTests(unittest.TestCase):
    def test_local_llm_uses_configured_timeout_and_reports_it(self):
        tasks = [
            {
                "task_id": "task-1",
                "title": "テーマ分析",
                "expert_id": "thematic-analysis",
                "actor": "a100",
                "status": "queued",
                "decision_mode": "local_llm",
            }
        ]
        with mock.patch(
            "devtools.knowledge_console.app.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ) as urlopen:
            result = _ask_local_llm(
                base_url="http://127.0.0.1:1234/v1",
                model="local-model",
                tasks=tasks,
                timeout_seconds=45,
            )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 45)
        request_body = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(request_body["reasoning_effort"], "low")
        self.assertEqual(result["state"], "timeout")
        self.assertIn("45秒", result["message"])

    def test_drive_api_queue_roundtrips_through_the_drive_client(self):
        secret = "api-secret-value-that-is-long-enough"
        drive = FakeDriveService()
        queue = DriveApiQueue(drive, "folder-id-for-tests")
        task = {
            "task_id": "task-api",
            "title": "A100実推論",
            "expert_id": "thematic-analysis",
            "model_id": "qwen3-80b",
        }
        job = _enqueue_drive_task(queue=queue, secret=secret, task=task, focus="")
        self.assertEqual(drive.files_by_name[job["request_file"]]["parents"], ["folder-id-for-tests"])

        heartbeat = _signed_payload(
            {
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "is_a100": True,
                "model_ready": True,
                "active_job": job["job_id"],
            },
            secret,
        )
        drive.put("KCC_Heartbeat.json", heartbeat)
        connection = _check_colab_connection(queue=queue, secret=secret)
        self.assertTrue(connection["connected"])
        self.assertEqual(connection["target"], "google-drive-api")
        self.assertEqual(connection["active_job"], job["job_id"])

        drive.put(
            f"KCC_Result_{job['job_id']}.json",
            _signed_payload(
                {
                    "job_id": job["job_id"],
                    "request_sha256": job["request_sha256"],
                    "status": "succeeded",
                    "content": "api result",
                },
                secret,
            ),
        )
        result = _wait_for_drive_result(queue=queue, secret=secret, job=job, timeout_seconds=30)
        self.assertEqual(result["content"], "api result")

    def test_browser_override_is_registered_for_opening_pages(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-browser-") as temporary:
            browser = Path(temporary) / "browser.exe"
            browser.write_bytes(b"")
            with mock.patch.dict("os.environ", {"KNOWLEDGE_CONSOLE_BROWSER": str(browser)}):
                name = _preferred_browser()
            import webbrowser

            self.assertEqual(webbrowser.get(name).name, str(browser))

    def test_connection_reports_worker_startup_phases(self):
        secret = "phase-secret-value-long-enough"
        drive = FakeDriveService()
        queue = DriveApiQueue(drive, "folder-id-for-tests")
        waiting = _check_colab_connection(queue=queue, secret=secret)
        self.assertEqual(waiting["state"], "starting")

        def heartbeat(**fields):
            drive.records.clear()
            drive.put(
                "KCC_Heartbeat.json",
                _signed_payload(
                    {
                        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "is_a100": True,
                        **fields,
                    },
                    secret,
                ),
            )
            return _check_colab_connection(queue=queue, secret=secret)

        downloading = heartbeat(
            phase="downloading", model_ready=False, download_percent=35, model_source="drive"
        )
        self.assertEqual(downloading["state"], "starting")
        self.assertIn("ダウンロード中", downloading["message"])
        self.assertIn("35%", downloading["message"])
        self.assertIn("Driveキャッシュ", downloading["message"])
        self.assertFalse(downloading["connected"])

        failed = heartbeat(phase="failed", model_ready=False, detail="an A100 runtime is required")
        self.assertEqual(failed["state"], "worker_failed")
        self.assertIn("an A100 runtime is required", failed["message"])

        ready = heartbeat(
            phase="ready", model_ready=True, pending_count=2, completed_count=5, failed_count=1,
            jobs=[{"job_id": "job-1", "task_id": "t1", "title": "テーマ分析", "running_seconds": 42}],
            last_completed={"title": "前の分析", "ok": True, "seconds": 61.5, "tokens_per_second": 18.2},
            gpu_memory={"used_mib": 60000, "total_mib": 81920},
        )
        self.assertTrue(ready["connected"])
        # What the A100 is doing is passed through for the Web UI's activity panel.
        self.assertEqual(ready["jobs"][0]["title"], "テーマ分析")
        self.assertEqual((ready["pending_count"], ready["completed_count"], ready["failed_count"]), (2, 5, 1))
        self.assertEqual(ready["last_completed"]["tokens_per_second"], 18.2)
        self.assertEqual(ready["gpu_memory"]["used_mib"], 60000)

    def test_a100_plan_runs_tasks_that_were_only_completed_in_simulation(self):
        from devtools.knowledge_console.app import _build_a100_plan

        def task(task_id, *, simulation):
            return {
                "task_id": task_id, "position": 1 if task_id == "sim" else 2, "title": task_id,
                "actor": "a100", "model_id": "qwen3-80b", "status": "succeeded",
                "decision_mode": "program", "simulation": simulation,
            }

        plan = {item["task_id"]: item for item in _build_a100_plan(
            [task("sim", simulation=True), task("real", simulation=False)], {"decisions": {}}
        )}
        self.assertEqual(plan["sim"]["action"], "execute")
        self.assertTrue(plan["sim"]["program_gate"]["approved"])
        self.assertEqual(plan["real"]["action"], "hold")
        self.assertIn("応答は受信済み", plan["real"]["reason"])

    def test_drive_session_trusts_only_an_own_unshared_file(self):
        drive = FakeDriveService()
        planted = {
            "kind": "knowledge_console_a100_session",
            "drive_folder_id": "planted-folder-id",
            "queue_secret": "planted-secret-value-long-enough",
        }
        drive.put("KCC_Session.json", planted, parents=["root"], owned_by_me=False)
        drive.put("KCC_Session.json", planted, parents=["root"], shared=True)
        with self.assertRaises(LookupError):
            _read_drive_session(drive)
        drive.put(
            "KCC_Session.json",
            {
                "kind": "knowledge_console_a100_session",
                "session_id": "own-session",
                "drive_folder_id": "folder-id-for-tests",
                "queue_secret": "own-secret-value-long-enough",
            },
            parents=["root"],
        )
        session = _read_drive_session(drive)
        self.assertEqual(session["drive_folder_id"], "folder-id-for-tests")
        self.assertEqual(session["queue_secret"], "own-secret-value-long-enough")

    def test_drive_api_queue_uses_the_worker_subfolders(self):
        secret = "folder-secret-value-long-enough"
        drive = FakeDriveService()
        queue = DriveApiQueue(
            drive, "shared-folder-id-001",
            folders={"output": "output-folder-id-01", "temp": "temp-folder-id-0001"},
        )
        task = {"task_id": "task-folders", "title": "t", "expert_id": "e", "model_id": "qwen3-80b"}
        job = _enqueue_drive_task(queue=queue, secret=secret, task=task, focus="")
        self.assertEqual(drive.files_by_name[job["request_file"]]["parents"], ["temp-folder-id-0001"])
        drive.put(
            f"KCC_Result_{job['job_id']}.json",
            _signed_payload(
                {"job_id": job["job_id"], "request_sha256": job["request_sha256"],
                 "status": "succeeded", "content": "from output folder"},
                secret,
            ),
            parents=["output-folder-id-01"],
        )
        result = _wait_for_drive_result(queue=queue, secret=secret, job=job, timeout_seconds=30)
        self.assertEqual(result["content"], "from output folder")

        drive.put(
            "KCC_Session.json",
            {
                "kind": "knowledge_console_a100_session",
                "drive_folder_id": "shared-folder-id-001",
                "queue_secret": secret,
                "folders": {"output": "output-folder-id-01", "temp": "temp-folder-id-0001",
                            "bogus": "x", "models": "bad/id"},
            },
            parents=["root"],
        )
        self.assertEqual(
            _read_drive_session(drive)["folders"],
            {"output": "output-folder-id-01", "temp": "temp-folder-id-0001"},
        )

    def test_drive_api_queue_rejects_names_outside_the_queue_contract(self):
        queue = DriveApiQueue(FakeDriveService(), "folder-id-for-tests")
        with self.assertRaises(ValueError):
            queue.read_json("x' or name contains '", maximum=1024)

    def test_real_adapter_roundtrips_signed_drive_queue_files(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-drive-") as temporary:
            sync_dir = Path(temporary)
            secret = "queue-secret-value-that-is-long-enough"
            task = {
                "task_id": "task-real",
                "title": "A100実推論",
                "expert_id": "thematic-analysis",
                "model_id": "qwen3-80b",
            }
            queue = FolderQueue(str(sync_dir))
            job = _enqueue_drive_task(
                queue=queue, secret=secret, task=task, focus="意味関係を分析"
            )
            request_path = sync_dir / job["request_file"]
            self.assertTrue(request_path.is_file())
            self.assertIn("A100実推論", request_path.read_text(encoding="utf-8"))

            heartbeat = _signed_payload(
                {
                    "schema_version": 1,
                    "kind": "knowledge_console_a100_heartbeat",
                    "session_id": "session-test",
                    "updated_at": "2026-09-29T00:00:00Z",
                    "gpu": "NVIDIA A100",
                    "is_a100": True,
                    "model_ready": True,
                    "model": "qwen-real",
                    "active_job": None,
                },
                secret,
            )
            # Use a current timestamp so heartbeat freshness is part of the check.
            heartbeat["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            heartbeat = _signed_payload(
                {key: value for key, value in heartbeat.items() if key != "signature"}, secret
            )
            (sync_dir / "KCC_Heartbeat.json").write_text(
                json.dumps(heartbeat, ensure_ascii=False), encoding="utf-8"
            )
            self.assertTrue(
                _check_colab_connection(queue=queue, secret=secret)["connected"]
            )

            response = _signed_payload(
                {
                    "schema_version": 1,
                    "kind": "knowledge_console_a100_result",
                    "job_id": job["job_id"],
                    "request_sha256": job["request_sha256"],
                    "status": "succeeded",
                    "model": "qwen-real",
                    "content": "real result",
                    "usage": {"total_tokens": 12},
                    "completed_at": "2026-09-29T00:00:00Z",
                },
                secret,
            )
            (sync_dir / f"KCC_Result_{job['job_id']}.json").write_text(
                json.dumps(response, ensure_ascii=False), encoding="utf-8"
            )
            result = _wait_for_drive_result(
                queue=queue,
                secret=secret,
                job=job,
                timeout_seconds=30,
            )
            self.assertFalse(result["simulation"])
            self.assertEqual(result["content"], "real result")


class KnowledgeConsoleRouteTests(unittest.TestCase):
    def test_real_route_queues_and_imports_a_signed_drive_result(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-real-route-") as temporary:
            root = Path(temporary)
            sync_dir = root / "drive-sync"
            sync_dir.mkdir()
            secret = "route-secret-value-that-is-long-enough"
            heartbeat = _signed_payload(
                {
                    "schema_version": 1,
                    "kind": "knowledge_console_a100_heartbeat",
                    "session_id": "route-session",
                    "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "gpu": "NVIDIA A100",
                    "is_a100": True,
                    "model_ready": True,
                    "model": "qwen-real",
                    "active_job": None,
                },
                secret,
            )
            (sync_dir / "KCC_Heartbeat.json").write_text(
                json.dumps(heartbeat, ensure_ascii=False), encoding="utf-8"
            )
            flask_app = create_app(data_directory=root / "data")
            flask_app.config["KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR"] = str(sync_dir)
            flask_app.config["KNOWLEDGE_CONSOLE_QUEUE_SECRET"] = secret
            flask_app.config["KNOWLEDGE_CONSOLE_A100_RESULT_TIMEOUT"] = 30
            client = flask_app.test_client()
            task = next(
                item
                for item in client.get("/api/knowledge-console/tasks").get_json()["tasks"]
                if item["actor"] == "a100"
            )
            started = self._execute_grounded(client,
                f"/api/knowledge-console/tasks/{task['task_id']}/execute",
                json={"revision": task["revision"], "simulation": False, "focus": "実送信"},
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(started.status_code, 200)
            deadline = time.monotonic() + 5
            request_files = []
            while time.monotonic() < deadline and not request_files:
                request_files = list(sync_dir.glob("KCC_Task_*.json"))
                time.sleep(0.02)
            self.assertEqual(len(request_files), 1)
            request_raw = request_files[0].read_bytes()
            request_payload = json.loads(request_raw.decode("utf-8"))
            job_id = request_payload["job_id"]
            result = _signed_payload(
                {
                    "schema_version": 1,
                    "kind": "knowledge_console_a100_result",
                    "job_id": job_id,
                    "request_sha256": hashlib.sha256(request_raw).hexdigest(),
                    "status": "succeeded",
                    "model": "qwen-real",
                    "content": grounded_answer("route real result"),
                    "usage": {"total_tokens": 9},
                    "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
                secret,
            )
            (sync_dir / f"KCC_Result_{job_id}.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            completed = None
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                completed = next(
                    item
                    for item in client.get("/api/knowledge-console/tasks").get_json()["tasks"]
                    if item["task_id"] == task["task_id"]
                )
                if completed["status"] == "succeeded":
                    break
                time.sleep(0.05)
            self.assertEqual(completed["status"], "succeeded")
            self.assertFalse(completed["simulation"])
            self.assertEqual(completed["result"]["quality"]["findings"], "route real result")


    @staticmethod
    def _execute_grounded(client, *args, **kwargs):
        # Transport fixture; real goal provenance/staleness has separate coverage.
        with mock.patch("devtools.knowledge_console.goals.GoalWorkspace.task_context", return_value=GROUND_CONTEXT):
            return client.post(*args, **kwargs)

    def _repeating_route(self, root: Path, *, target: int, limit: int):
        """Start a repeat-until-score task against a folder queue; return (client, sync_dir, secret, task_id)."""
        sync_dir = root / "drive-sync"
        sync_dir.mkdir()
        secret = "route-secret-value-that-is-long-enough"
        heartbeat = _signed_payload(
            {
                "schema_version": 1,
                "kind": "knowledge_console_a100_heartbeat",
                "session_id": "route-session",
                "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "gpu": "NVIDIA A100",
                "is_a100": True,
                "model_ready": True,
                "model": "qwen-real",
                "active_job": None,
            },
            secret,
        )
        (sync_dir / "KCC_Heartbeat.json").write_text(json.dumps(heartbeat), encoding="utf-8")
        flask_app = create_app(data_directory=root / "data")
        flask_app.config["KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR"] = str(sync_dir)
        flask_app.config["KNOWLEDGE_CONSOLE_QUEUE_SECRET"] = secret
        flask_app.config["KNOWLEDGE_CONSOLE_A100_RESULT_TIMEOUT"] = 30
        client = flask_app.test_client()
        headers = {"X-Knowledge-Console-Request": "1"}
        task = client.post(
            "/api/knowledge-console/tasks",
            json={
                "title": "反復タスク",
                "expert_id": "thematic-analysis",
                "actor": "a100",
                "model_id": "qwen3-80b",
                "target_score": target,
                "max_iterations": limit,
            },
            headers=headers,
        ).get_json()["task"]
        started = self._execute_grounded(client,
            f"/api/knowledge-console/tasks/{task['task_id']}/execute",
            json={"revision": task["revision"], "simulation": False, "focus": "基本方針"},
            headers=headers,
        )
        self.assertEqual(started.status_code, 200)
        return client, sync_dir, secret, task["task_id"]

    @staticmethod
    def _answer_queue(sync_dir: Path, secret: str, answer, answered: set) -> list[dict]:
        """Act as the Colab worker for every new request file; return the new requests."""
        handled = []
        for request_file in sorted(sync_dir.glob("KCC_Task_*.json")):
            if request_file.name in answered:
                continue
            answered.add(request_file.name)
            raw = request_file.read_bytes()
            request = json.loads(raw.decode("utf-8"))
            result = _signed_payload(
                {
                    "schema_version": 1,
                    "kind": "knowledge_console_a100_result",
                    "job_id": request["job_id"],
                    "request_sha256": hashlib.sha256(raw).hexdigest(),
                    "status": "succeeded",
                    "model": "qwen-real",
                    "content": (answer(request) if request["kind"] == "knowledge_console_a100_score"
                                else grounded_answer(answer(request))),
                    "usage": {},
                    "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
                secret,
            )
            (sync_dir / f"KCC_Result_{request['job_id']}.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            handled.append(request)
        return handled

    def _drive_until_done(self, client, sync_dir, secret, task_id, answer) -> tuple[dict, list[dict]]:
        answered: set = set()
        requests_seen: list[dict] = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            requests_seen += self._answer_queue(sync_dir, secret, answer, answered)
            task = next(
                item
                for item in client.get("/api/knowledge-console/tasks").get_json()["tasks"]
                if item["task_id"] == task_id
            )
            if task["status"] in {"succeeded", "failed"}:
                return task, requests_seen
            time.sleep(0.05)
        self.fail("repeating task did not finish")

    def test_repeating_task_reruns_with_feedback_until_the_target_score(self):
        scores = iter([{"score": 55, "feedback": "根拠を追加"}, {"score": 85, "feedback": "十分"}])
        with tempfile.TemporaryDirectory(prefix="knowledge-console-repeat-") as temporary, mock.patch(
            "devtools.knowledge_console.app._score_with_local_llm", side_effect=lambda **_: next(scores)
        ):
            client, sync_dir, secret, task_id = self._repeating_route(Path(temporary), target=80, limit=5)
            task, requests_seen = self._drive_until_done(
                client, sync_dir, secret, task_id, lambda request: f"回答{request['analysis_focus']}"
            )
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual((task["score"], task["iteration"]), (85, 2))
        self.assertTrue(task["result"]["target_met"])
        self.assertEqual([item["score"] for item in task["result"]["attempts"]], [55, 85])
        # The UI reads each attempt of the latest run while the task is still running.
        self.assertEqual(
            [(item["iteration"], item["score"]) for item in task["score_history"]], [(1, 55), (2, 85)]
        )
        self.assertEqual(len(requests_seen), 2)
        self.assertIn("実行方針: 基本方針", requests_seen[0]["analysis_focus"])
        self.assertIn("前回の結果は55点", requests_seen[1]["analysis_focus"])
        self.assertIn("根拠を追加", requests_seen[1]["analysis_focus"])

    def test_repeating_task_fails_but_keeps_the_best_attempt_below_the_target(self):
        scores = iter([{"score": 60, "feedback": "a"}, {"score": 40, "feedback": "b"}])
        with tempfile.TemporaryDirectory(prefix="knowledge-console-repeat-") as temporary, mock.patch(
            "devtools.knowledge_console.app._score_with_local_llm", side_effect=lambda **_: next(scores)
        ):
            client, sync_dir, secret, task_id = self._repeating_route(Path(temporary), target=90, limit=2)
            answers = iter(["一回目", "二回目"])
            task, _ = self._drive_until_done(client, sync_dir, secret, task_id, lambda _request: next(answers))
        self.assertEqual(task["status"], "failed")
        self.assertIn("最高60点", task["error_message"])
        self.assertEqual(task["result"]["quality"]["findings"], "一回目")
        self.assertFalse(task["result"]["target_met"])

    def test_repeating_task_scores_on_a100_when_the_local_llm_is_unavailable(self):
        def answer(request):
            if request["kind"] == "knowledge_console_a100_score":
                self.assertEqual(json.loads(request["candidate"])["findings"], "分析結果")
                return '{"score": 92, "feedback": "良い"}'
            return "分析結果"

        with tempfile.TemporaryDirectory(prefix="knowledge-console-repeat-") as temporary, mock.patch(
            "devtools.knowledge_console.app._score_with_local_llm", return_value=None
        ):
            client, sync_dir, secret, task_id = self._repeating_route(Path(temporary), target=80, limit=3)
            task, requests_seen = self._drive_until_done(client, sync_dir, secret, task_id, answer)
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(task["score"], 92)
        self.assertEqual(task["result"]["attempts"][0]["scorer"], "a100")
        self.assertEqual(
            [item["kind"] for item in requests_seen],
            ["knowledge_console_a100_task", "knowledge_console_a100_score"],
        )

    @unittest.skipUnless(
        importlib.util.find_spec("google_auth_oauthlib"), "Google OAuth client is not installed"
    )
    def test_configure_with_folder_id_reports_missing_drive_authorization(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-configure-") as temporary:
            flask_app = create_app(data_directory=Path(temporary) / "data")
            response = flask_app.test_client().post(
                "/api/knowledge-console/runtime/configure",
                json={
                    "drive_folder_id": "1wd69nc_9Xaw80Id54Nt7WW_9x3ztm9j5",
                    "queue_secret": "configure-secret-value-long-enough",
                },
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(response.status_code, 200)
            connection = response.get_json()["connection"]
            self.assertFalse(connection["connected"])
            self.assertEqual(connection["state"], "drive_not_authorized")
            self.assertIn("google_oauth_client.json", connection["message"])

    def test_real_route_keeps_several_a100_jobs_in_flight(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-parallel-") as temporary:
            root = Path(temporary)
            sync_dir = root / "drive-sync"
            sync_dir.mkdir()
            secret = "parallel-secret-value-long-enough"
            heartbeat = _signed_payload(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "is_a100": True,
                    "model_ready": True,
                },
                secret,
            )
            (sync_dir / "KCC_Heartbeat.json").write_text(json.dumps(heartbeat), encoding="utf-8")
            flask_app = create_app(data_directory=root / "data")
            flask_app.config["KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR"] = str(sync_dir)
            flask_app.config["KNOWLEDGE_CONSOLE_QUEUE_SECRET"] = secret
            flask_app.config["KNOWLEDGE_CONSOLE_A100_RESULT_TIMEOUT"] = 30
            client = flask_app.test_client()
            a100_tasks = [
                item
                for item in client.get("/api/knowledge-console/tasks").get_json()["tasks"]
                if item["actor"] == "a100"
            ][:3]
            for task in a100_tasks:
                started = self._execute_grounded(client,
                    f"/api/knowledge-console/tasks/{task['task_id']}/execute",
                    json={"revision": task["revision"], "simulation": False},
                    headers={"X-Knowledge-Console-Request": "1"},
                )
                self.assertEqual(started.status_code, 200)
            # No result exists yet, so every request file proves a job is in flight.
            deadline = time.monotonic() + 5
            request_files = []
            while time.monotonic() < deadline and len(request_files) < 3:
                request_files = list(sync_dir.glob("KCC_Task_*.json"))
                time.sleep(0.02)
            self.assertEqual(len(request_files), 3)
            for request_file in request_files:
                request_raw = request_file.read_bytes()
                job_id = json.loads(request_raw.decode("utf-8"))["job_id"]
                (sync_dir / f"KCC_Result_{job_id}.json").write_text(
                    json.dumps(
                        _signed_payload(
                            {
                                "job_id": job_id,
                                "request_sha256": hashlib.sha256(request_raw).hexdigest(),
                                "status": "succeeded",
                                "content": grounded_answer("parallel result"),
                            },
                            secret,
                        )
                    ),
                    encoding="utf-8",
                )
            deadline = time.monotonic() + 10
            statuses = []
            while time.monotonic() < deadline:
                current = {
                    item["task_id"]: item["status"]
                    for item in client.get("/api/knowledge-console/tasks").get_json()["tasks"]
                }
                statuses = [current[task["task_id"]] for task in a100_tasks]
                if all(status == "succeeded" for status in statuses):
                    break
                time.sleep(0.05)
            self.assertEqual(statuses, ["succeeded"] * 3)

    def test_connection_check_discovers_the_colab_session_automatically(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-auto-") as temporary:
            flask_app = create_app(data_directory=Path(temporary) / "data")
            drive = FakeDriveService()
            flask_app.extensions["knowledge_console_drive_authorization"] = FakeDriveAuthorization(drive)
            client = flask_app.test_client()
            headers = {"X-Knowledge-Console-Request": "1"}

            waiting = client.post("/api/knowledge-console/runtime/check", json={}, headers=headers)
            self.assertEqual(waiting.get_json()["connection"]["state"], "waiting_for_worker")

            secret = "auto-secret-value-long-enough"
            drive.put(
                "KCC_Session.json",
                {
                    "kind": "knowledge_console_a100_session",
                    "session_id": "auto-session",
                    "drive_folder_id": "folder-id-for-tests",
                    "queue_secret": secret,
                },
                parents=["root"],
            )
            drive.put(
                "KCC_Heartbeat.json",
                _signed_payload(
                    {
                        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "is_a100": True,
                        "model_ready": True,
                        "session_id": "auto-session",
                    },
                    secret,
                ),
            )
            connected = client.post("/api/knowledge-console/runtime/check", json={}, headers=headers)
            connection = connected.get_json()["connection"]
            self.assertTrue(connection["connected"])
            self.assertEqual(connection["target"], "google-drive-api")
            status = client.get("/api/knowledge-console/setup/status").get_json()["setup"]
            self.assertEqual(status["queue_mode"], "auto")
            self.assertTrue(status["drive_authorized"])

    @unittest.skipUnless(
        importlib.util.find_spec("googleapiclient"), "Google API client is not installed"
    )
    def test_notebook_publish_reports_a_disabled_drive_api_without_creating_a_copy(self):
        from googleapiclient.errors import HttpError
        from httplib2 import Response

        link = "https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=421684302391"
        body = json.dumps(
            {
                "error": {
                    "code": 403,
                    "message": f"Google Drive API has not been used in project 421684302391 before or it is disabled. Enable it by visiting {link} then retry.",
                    "errors": [{"reason": "accessNotConfigured", "domain": "usageLimits"}],
                    "details": [{"reason": "accessNotConfigured"}],
                }
            }
        ).encode("utf-8")
        disabled = HttpError(Response({"status": 403}), body)

        class DisabledDrive:
            created = False

            def files(self):
                return self

            def get(self, **_kwargs):
                raise disabled

            def create(self, **_kwargs):
                DisabledDrive.created = True
                raise AssertionError("must not create a copy when the API is disabled")

        with tempfile.TemporaryDirectory(prefix="knowledge-console-notebook-") as temporary:
            flask_app = create_app(data_directory=Path(temporary) / "data")
            flask_app.extensions["knowledge_console_drive_authorization"] = FakeDriveAuthorization(DisabledDrive())
            response = flask_app.test_client().post(
                "/api/knowledge-console/setup/notebook",
                json={},
                headers={"X-Knowledge-Console-Request": "1"},
            )
        self.assertEqual(response.status_code, 502)
        self.assertFalse(DisabledDrive.created)
        self.assertIn("Google Drive API が有効になっていません", response.get_json()["error"])
        self.assertIn(link, response.get_json()["error"])

    def test_setup_stores_only_a_desktop_oauth_client(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-oauth-") as temporary:
            data_dir = Path(temporary) / "data"
            client = create_app(data_directory=data_dir).test_client()
            headers = {"X-Knowledge-Console-Request": "1"}
            status = client.get("/api/knowledge-console/setup/status").get_json()["setup"]
            self.assertFalse(status["oauth_client"])

            web_client = {"web": {"client_id": "x.apps.googleusercontent.com"}}
            rejected = client.post(
                "/api/knowledge-console/setup/oauth-client",
                json={"client_json": web_client},
                headers=headers,
            )
            self.assertEqual(rejected.status_code, 400)
            self.assertIn("デスクトップアプリ", rejected.get_json()["error"])

            desktop_client = {
                "installed": {
                    "client_id": "123-abc.apps.googleusercontent.com",
                    "client_secret": "client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            saved = client.post(
                "/api/knowledge-console/setup/oauth-client",
                json={"client_json": desktop_client},
                headers=headers,
            )
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.get_json()["setup"]["oauth_client"])
            stored = json.loads((data_dir / "google_oauth_client.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["installed"]["client_id"], "123-abc.apps.googleusercontent.com")

    def test_page_task_and_trace_flow(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-knowledge-console-http-") as temporary:
            flask_app = create_app(data_directory=Path(temporary) / "data")
            client = flask_app.test_client()
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            page_html = page.get_data(as_text=True)
            self.assertIn("Knowledge Control Center", page_html)
            self.assertIn('data-view="a100"', page_html)
            self.assertIn('id="kc-a100-task-board"', page_html)
            self.assertIn('id="kc-run-a100-batch"', page_html)
            # Connection checks are available without starting a batch run.
            self.assertEqual(page_html.count("kc-check-connection"), 3)
            # The setup lives in a dialog opened from the top bar and the A100 view.
            self.assertIn('id="kc-setup-dialog"', page_html)
            self.assertEqual(page_html.count("kc-open-setup"), 2)
            self.assertIn('id="kc-setup-colab-link"', page_html)
            self.assertIn('id="kc-activity-jobs"', page_html)
            self.assertIn('id="kc-setup-authorize"', page_html)
            self.assertIn("https://colab.research.google.com/drive/", page_html)
            self.assertIn("固定する判断", page_html)
            self.assertIn("A100 タスク可視化", page_html)
            self.assertEqual(page_html.count('class="kc-pipeline-stage"'), 7)
            self.assertEqual(page_html.count('class="kc-pipeline-link"'), 6)
            self.assertLess(page_html.index("入力層"), page_html.index("Obsidian 第1層"))
            self.assertLess(page_html.index("Obsidian 第3層"), page_html.index("思考一時保存"))
            self.assertLess(page_html.index("ラベル生成"), page_html.index("出力データ"))

            initial_tasks = client.get("/api/knowledge-console/tasks").get_json()["tasks"]
            self.assertEqual(len(initial_tasks), 20)
            self.assertEqual(
                [task["position"] for task in initial_tasks], list(range(1, 21))
            )

            flask_app.config["KNOWLEDGE_CONSOLE_DRIVE_SYNC_DIR"] = ""
            flask_app.config["KNOWLEDGE_CONSOLE_QUEUE_SECRET"] = ""
            flask_app.config["KNOWLEDGE_CONSOLE_LOCAL_LLM_URL"] = ""
            flask_app.config["KNOWLEDGE_CONSOLE_LOCAL_LLM_MODEL"] = ""
            connection = client.post(
                "/api/knowledge-console/runtime/check",
                json={"simulation": True},
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(connection.status_code, 200)
            self.assertFalse(connection.get_json()["connection"]["connected"])
            # Without a pasted secret the app auto-discovers, which first needs Drive consent.
            self.assertEqual(
                connection.get_json()["connection"]["state"], "drive_not_authorized"
            )

            a100_task = next(task for task in initial_tasks if task["actor"] == "a100")
            refused_real_run = client.post(
                f"/api/knowledge-console/tasks/{a100_task['task_id']}/execute",
                json={"revision": a100_task["revision"], "simulation": False},
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(refused_real_run.status_code, 400)
            self.assertIn("根拠ノート", refused_real_run.get_json()["error"])

            plan_response = client.post(
                "/api/knowledge-console/a100/plan",
                json={"simulation": True},
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(plan_response.status_code, 200)
            plan_payload = plan_response.get_json()
            self.assertEqual(plan_payload["local_llm"]["state"], "not_needed")
            self.assertEqual(len(plan_payload["plan"]), 11)
            self.assertEqual(
                [item["position"] for item in plan_payload["plan"]],
                sorted(item["position"] for item in plan_payload["plan"]),
            )
            self.assertTrue(
                all(not item["program_gate"]["approved"] and item["action"] == "hold" for item in plan_payload["plan"])
            )
            self.assertEqual(
                {item["decision_source"] for item in plan_payload["plan"]},
                {"program", "program_fallback"},
            )

            created = client.post(
                "/api/knowledge-console/tasks",
                json={
                    "title": "KJ法の知識確認",
                    "expert_id": "kj-method",
                    "actor": "local",
                    "model_id": "local-default",
                },
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(created.status_code, 201)
            task = created.get_json()["task"]
            self.assertEqual(task["position"], 21)

            executed = client.post(
                f"/api/knowledge-console/tasks/{task['task_id']}/execute",
                json={"revision": task["revision"], "simulation": True},
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(executed.status_code, 200)
            progressed_task = executed.get_json()["task"]
            self.assertEqual(progressed_task["status"], "running")
            while progressed_task["status"] == "running":
                advanced = client.post(
                    f"/api/knowledge-console/tasks/{task['task_id']}/advance",
                    json={"revision": progressed_task["revision"]},
                    headers={"X-Knowledge-Console-Request": "1"},
                )
                self.assertEqual(advanced.status_code, 200)
                progressed_task = advanced.get_json()["task"]
            self.assertEqual(progressed_task["progress"], 100)

            traced = client.post(
                "/api/knowledge-console/traces",
                json={
                    "question": "テスト質問",
                    "expert_id": "thematic-analysis",
                    "model_id": "qwen3-80b",
                },
                headers={"X-Knowledge-Console-Request": "1"},
            )
            self.assertEqual(traced.status_code, 201)
            self.assertEqual(len(traced.get_json()["trace"]["events"]), 7)

    def test_mutations_require_the_standalone_request_header(self):
        with tempfile.TemporaryDirectory(prefix="knowledge-console-security-") as temporary:
            client = create_app(data_directory=Path(temporary) / "data").test_client()
            response = client.post(
                "/api/knowledge-console/tasks",
                json={"title": "blocked"},
            )
            self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()


class DriveWorkerNotebookTests(unittest.TestCase):
    def test_generated_worker_runs_parallel_slots_and_reuses_only_own_build_cache(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from prepare_knowledge_console_a100_drive_worker import build_worker_notebook

        notebook = build_worker_notebook("folder-id-for-tests")
        code_cells = ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]
        code = "\n".join(code_cells)
        # Stage cells: setup, llama.cpp, model, server, worker loop, and an optional status cell.
        self.assertEqual(len(code_cells), 6)
        for stage in code_cells[1:5]:
            self.assertTrue(stage.startswith("try:\n"))
            self.assertIn("report_failure(exc)", stage)
        self.assertIn("except KeyboardInterrupt:\n    finish_worker()", code_cells[4])
        self.assertIn("else:\n    finish_worker()", code_cells[4])
        self.assertNotIn("finally:\n    finish_worker()", code)
        # Each stage cell refreshes one live panel about once per second.
        for stage in code_cells[1:5]:
            self.assertIn("begin_live_status(", stage)
        self.assertIn("process.communicate(timeout=1)", code)
        self.assertIn("display(Pretty(", code)
        self.assertIn("RETRY download_pinned_q4_gguf", code_cells[2])
        self.assertIn("'-np', str(PARALLEL_SLOTS)", code)
        self.assertIn("'-c', str(4096 * PARALLEL_SLOTS)", code)
        self.assertIn("'-DCMAKE_CUDA_ARCHITECTURES=80'", code)
        self.assertIn("item.get('ownedByMe') and (item.get('lastModifyingUser') or {}).get('me')", code)
        self.assertIn("'drive_folder_id': FOLDER_ID", code)
        # The session secret goes to a private My Drive file, never to notebook output.
        self.assertIn("'parents': ['root']", code)
        self.assertNotIn("clipboard", code)
        self.assertNotIn("KNOWLEDGE_CONSOLE_DRIVE_QUEUE_JSON", code)
        # The model download starts before the llama.cpp build and is awaited after it.
        self.assertLess(code.index("model_download = subprocess.Popen"), code.index("'build_llama_server'"))
        self.assertLess(code.index("'build_llama_server'"), code.index("model_download.wait("))
        # The session and first heartbeat are published before the long build starts.
        self.assertLess(code.index("KCC_Session.json"), code.index("'build_llama_server'"))
        self.assertLess(code.index("heartbeat_thread.start()"), code.index("'build_llama_server'"))
        self.assertIn("worker_status['phase'] = 'failed' if", code)
        # The model comes from this account's verified Drive copy, else Hugging Face.
        self.assertIn("HF_XET_FIXED_DOWNLOAD_CONCURRENCY='4'", code)
        self.assertIn("item.get('sha256Checksum') in (None, MODEL_SHA256)", code)
        self.assertLess(code.index("model_cache = find_own_model_cache()"), code.index("'build_llama_server'"))
        self.assertIn("result['model_sha256_source'] = 'drive_checksum'", code)
        self.assertIn("threading.Thread(target=save_model_cache", code)
        self.assertNotIn("drive.mount(", code)
        # Outputs, model data, and temporary queue files are kept in separate subfolders.
        for title in ("KCC_出力データ", "KCC_モデルデータ", "KCC_一時データ"):
            self.assertIn(title, code)
        self.assertIn("'folders': KCC_FOLDERS", code)
        self.assertIn("migrate_flat_queue_files()", code)
        self.assertIn("**activity_snapshot()", code)
        self.assertIn("job_activity['pending'] = len(waiting)", code)
