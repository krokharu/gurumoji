"""Focused tests for the Flask-free transcription job boundary."""

import tempfile
import threading
import unittest
from pathlib import Path

import app
from gurumoji.handlers.jobs import JobHandler, JobRequestError


class FakeJob:
    def __init__(self, job_id, *, status="queued", output_dir=None):
        self.id = job_id
        self.status = status
        self.created_at = 1.0
        self.cancel_event = threading.Event()
        self.output_dir = output_dir or Path("output") / job_id
        self.files = []

    def public(self):
        return {"id": self.id, "status": self.status}


class JobHandlerTests(unittest.TestCase):
    def setUp(self):
        self.jobs = {}
        self.admission = None
        self.messages = []
        self.saved = []
        self.handler = JobHandler(
            jobs=self.jobs,
            lock=threading.RLock(),
            active_statuses={"queued", "running", "committing"},
            prune=lambda: None,
            admission_id=lambda: self.admission,
            admission_public=lambda job_id: {"id": job_id, "status": "admitting"},
            start_job=lambda form, upload, **options: (
                {"form": dict(form), "upload": upload, **options}, 202
            ),
            update_job=lambda job, **values: self.messages.append((job.id, values)),
            update_transcript=lambda job_id, payload: self.saved.append(
                (job_id, payload)
            ) or {"id": job_id},
            path_is_within=lambda path, parent: path.parent == parent,
        )

    def test_admission_and_start_are_available_without_flask(self):
        self.admission = "a" * 32
        body, status = self.handler.get(self.admission)
        self.assertEqual((status, body["status"]), (202, "admitting"))
        started, status = self.handler.start(
            {"model_name": "tiny"}, object(), admission_id=self.admission
        )
        self.assertEqual((status, started["admission_id"]), (202, self.admission))

    def test_active_cancel_and_commit_boundary(self):
        job = FakeJob("job-1", status="running")
        self.jobs[job.id] = job
        self.assertEqual(self.handler.active()["job"]["id"], job.id)
        self.assertTrue(self.handler.cancel(job.id)["ok"])
        self.assertTrue(job.cancel_event.is_set())

        job.status = "committing"
        with self.assertRaises(JobRequestError) as raised:
            self.handler.cancel(job.id)
        self.assertEqual(raised.exception.status, 409)

    def test_completed_edit_and_owned_artifact(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-handler-") as temporary:
            output = Path(temporary)
            artifact = output / "result.json"
            artifact.write_text("{}", encoding="utf-8")
            job = FakeJob("job-1", status="completed", output_dir=output)
            job.files = [artifact]
            self.jobs[job.id] = job

            self.assertEqual(
                self.handler.save_transcript(job.id, {"revision_count": 1})["id"],
                job.id,
            )
            self.assertEqual(self.handler.artifact(job.id, artifact.name).path, artifact)

    def test_missing_job_is_not_found(self):
        with self.assertRaises(JobRequestError) as raised:
            self.handler.get("missing")
        self.assertEqual(raised.exception.status, 404)


class JobRouteStructureTests(unittest.TestCase):
    def test_job_routes_keep_unique_compatibility_endpoints(self):
        expected = {
            "create_job": ("/api/jobs", "POST"),
            "get_job": ("/api/jobs/<job_id>", "GET"),
            "get_active_job": ("/api/jobs/active", "GET"),
            "cancel_job": ("/api/jobs/<job_id>/cancel", "POST"),
            "save_transcript": ("/api/jobs/<job_id>/transcript", "PUT"),
            "download_file": ("/api/jobs/<job_id>/files/<path:filename>", "GET"),
        }
        for endpoint, (path, method) in expected.items():
            rules = [
                rule for rule in app.app.url_map.iter_rules()
                if rule.endpoint == endpoint and str(rule.rule) == path
            ]
            self.assertEqual(len(rules), 1)
            self.assertIn(method, rules[0].methods)

        speaker_import = [
            rule for rule in app.app.url_map.iter_rules()
            if rule.endpoint == "import_speaker_registry"
            and str(rule.rule) == "/api/speakers/import"
        ]
        self.assertEqual(len(speaker_import), 1)
        self.assertIn("POST", speaker_import[0].methods)


if __name__ == "__main__":
    unittest.main()
