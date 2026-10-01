import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.job_store import KnowledgeJobStore
from gurumoji.knowledge_builder.transport import (
    MAX_MEMBER_BYTES, TransportError, export_colab_job, import_colab_result,
)

EXCERPT_TEXT = "Synthetic source excerpt for transport tests."
EXCERPT_SHA256 = hashlib.sha256(EXCERPT_TEXT.encode("utf-8")).hexdigest()


def _source(*, private=False):
    return {
        "schema_version": 1, "source_id": "source-transport", "version": "v1", "sha256": "a" * 64,
        "title": "Synthetic transport source", "source_type": "paper",
        "locator": {"kind": "local_uri", "value": "file:///private/paper.pdf"} if private else
                   {"kind": "doi", "value": "10.1234/transport"},
        "access_scope": "local_private" if private else "full_text",
        "license": {"license_id": "fixture", "terms": "Synthetic test data"},
        "anchors": [{"anchor_id": "p1", "kind": "page", "start": "1", "end": "1",
                      "extracted_text_sha256": EXCERPT_SHA256}],
        "rights": {"classification": "private" if private else "licensed",
                   "allowed_routes": ["local"] if private else ["local", "colab"]},
    }


def _claim(source, *, status="candidate"):
    claim = {
        "schema_version": 1, "claim_id": "claim-transport", "expert_id": "exp-transport",
        "claim": "Synthetic claim for transport tests.", "applicability": ["fixture"], "exceptions": [],
        "claim_type": "literature",
        "evidence": [{"source_id": source["source_id"], "source_version": source["version"],
                      "source_sha256": source["sha256"], "anchor_id": "p1",
                      "span": {"kind": "page", "start": "1", "end": "1"},
                      "extracted_text_sha256": EXCERPT_SHA256, "transform_history": []}],
        "contradictions": [], "status": status, "provenance": {
            "method": "synthetic fixture", "created_at": "2026-09-27T00:00:00Z"},
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab"]},
    }
    claim["reviewer"] = {"identity": "fixture-reviewer", "reviewed_at": "2026-09-27T00:00:00Z",
                         "target_sha256": contracts.claim_review_target(claim)}
    return claim


def _commit(job, source, claim):
    records = [("source.json", "Source", source), ("claim.json", "Claim", claim)]
    artifacts = []
    data_by_path = {}
    for path, kind, record in records:
        data = contracts.canonical_json(record)
        data_by_path[path] = data
        artifacts.append({"path": path, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                          "record_type": kind, "schema_version": 1})
    commit = {"schema_version": 1, "job_id": job["job_id"], "generation": job["generation"],
              "attempt_id": job["attempt_id"], "directive_sha256": job["directive_sha256"],
              "complete": True, "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "artifacts": artifacts}
    commit["manifest_sha256"] = contracts.sha256_json(commit)
    return commit, data_by_path


def _result_zip(job, commit, artifact_data, request_payload, *, job_overrides=None, extra_files=None):
    remote_job = {field: job[field] for field in ("job_id", "generation", "attempt_id", "directive_sha256",
                                                   "input_manifest_sha256", "model_route", "deadline")}
    remote_job.update(job_overrides or {})
    files = {"request.json": contracts.canonical_json(request_payload),
             "result.json": contracts.canonical_json({"schema_version": 1, "kind": "colab_result",
                                                       "job": remote_job, "commit": commit})}
    files.update({f"artifacts/{path}": data for path, data in artifact_data.items()})
    files.update(extra_files or {})
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()


class ColabTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = KnowledgeJobStore(Path(self.temp.name) / "data")
        self.source = _source()
        self.claim = _claim(self.source)
        self.payload = {
            "schema_version": 1, "kind": "colab_source_excerpt_request",
            "task": {"expert_id": "exp-transport", "task_kind": "knowledge_claim_generation",
                     "prompt_version": "prompt-v1", "prompt_template_sha256": "c" * 64},
            "sources": [self.source],
            "excerpts": [{"source_id": self.source["source_id"], "source_version": self.source["version"],
                          "source_sha256": self.source["sha256"], "anchor_id": "p1",
                          "extracted_text_sha256": EXCERPT_SHA256, "text": EXCERPT_TEXT}],
        }
        self.job = self.store.create_job(self.payload, job_id="job-transport", model_route="colab",
                                         model_id="fixture-model", prompt_version="prompt-v1",
                                         compiler_version="compiler-v1", retry_limit=1)
        self.commit, self.artifact_data = _commit(self.job, self.source, self.claim)
        self.approved_sources = {self.source["source_id"]: self.source}

    def _export(self, payload=None, *, job_id=None, approved_sources=None):
        return export_colab_job(self.store, job_id or self.job["job_id"],
                                self.payload if payload is None else payload,
                                approved_sources=self.approved_sources if approved_sources is None else approved_sources)

    def _import(self, data):
        return import_colab_result(self.store, data, approved_sources=self.approved_sources)

    def test_deterministic_export_and_valid_result_roundtrip(self):
        bundle = self._export()
        self.assertEqual(bundle, self._export())
        with zipfile.ZipFile(BytesIO(bundle)) as archive:
            self.assertEqual(set(archive.namelist()), {"handoff.json", "request.json"})
            handoff = json.loads(archive.read("handoff.json"))
            self.assertEqual(handoff["job"]["model_route"], "colab")
            self.assertEqual(hashlib.sha256(archive.read("request.json")).hexdigest(),
                             self.job["input_manifest_sha256"])
        result = _result_zip(self.job, self.commit, self.artifact_data, self.payload)
        accepted = self._import(result)
        self.assertEqual(accepted["manifest_sha256"], self.commit["manifest_sha256"])
        self.assertEqual(self.store.accepted_commit(self.job["job_id"]), self.commit)
        replay = self._import(result)
        self.assertEqual(replay["manifest_sha256"], self.commit["manifest_sha256"])
        altered = dict(self.artifact_data)
        changed_source = dict(self.source, title="Untrusted replacement title")
        altered["source.json"] = contracts.canonical_json(changed_source)
        altered_commit, altered = _commit(self.job, changed_source, self.claim)
        with self.assertRaises(TransportError):
            self._import(_result_zip(self.job, altered_commit, altered, self.payload))

    def test_approved_source_registry_is_required_and_exact(self):
        with self.assertRaises(TransportError):
            export_colab_job(self.store, self.job["job_id"], self.payload)
        changed = dict(self.source, title="Unreviewed title")
        with self.assertRaises(TransportError):
            self._export(approved_sources={self.source["source_id"]: changed})

    def test_import_requires_trusted_sources_and_rejects_remote_approved_claim(self):
        result = _result_zip(self.job, self.commit, self.artifact_data, self.payload)
        with self.assertRaises(TransportError):
            import_colab_result(self.store, result)
        changed = dict(self.source, title="Untrusted title")
        with self.assertRaises(TransportError):
            import_colab_result(self.store, result, approved_sources={self.source["source_id"]: changed})
        approved_claim = _claim(self.source, status="approved")
        approved_commit, approved_data = _commit(self.job, self.source, approved_claim)
        with self.assertRaises(TransportError):
            import_colab_result(self.store, _result_zip(self.job, approved_commit, approved_data, self.payload),
                                approved_sources=self.approved_sources)

    def test_imports_new_generation_after_prior_acceptance(self):
        first = _result_zip(self.job, self.commit, self.artifact_data, self.payload)
        self._import(first)
        next_job = self.store.begin_generation(self.job["job_id"], self.payload)
        self.assertEqual(next_job["generation"], 2)
        exported = self._export(job_id=next_job["job_id"])
        self.assertTrue(exported)

    def test_payload_hash_route_and_private_sources_fail_closed(self):
        with self.assertRaises(TransportError):
            self._export({"task": "changed"})
        local_job = self.store.create_job({"task": "local"}, job_id="job-local", model_route="local",
                                          model_id="m", prompt_version="p", compiler_version="c", retry_limit=0)
        with self.assertRaises(TransportError):
            self._export({"task": "local"}, job_id=local_job["job_id"])
        private_source = _source(private=True)
        private_payload = dict(self.payload)
        private_payload["sources"] = [private_source]
        private_payload["excerpts"] = [{"source_id": private_source["source_id"],
            "source_version": private_source["version"], "source_sha256": private_source["sha256"],
            "anchor_id": "p1", "extracted_text_sha256": EXCERPT_SHA256, "text": EXCERPT_TEXT}]
        private_payload["task"] = dict(self.payload["task"], prompt_version="p")
        private_job = self.store.create_job(private_payload, job_id="job-private", model_route="colab",
                                            model_id="m", prompt_version="p", compiler_version="c", retry_limit=0)
        with self.assertRaises(TransportError):
            self._export(private_payload, job_id=private_job["job_id"])
        secret_payload = dict(self.payload, answer_key="never send")
        secret_job = self.store.create_job(secret_payload, job_id="job-secret", model_route="colab",
                                           model_id="m", prompt_version="p", compiler_version="c", retry_limit=0)
        with self.assertRaises(TransportError):
            self._export(secret_payload, job_id=secret_job["job_id"])
        bare = {"task": "bare text"}
        bare_job = self.store.create_job(bare, job_id="job-bare", model_route="colab", model_id="m",
                                         prompt_version="p", compiler_version="c", retry_limit=0)
        with self.assertRaises(TransportError):
            self._export(bare, job_id=bare_job["job_id"])

    def test_tampered_artifacts_and_stale_directive_are_rejected(self):
        tampered = dict(self.artifact_data)
        tampered["claim.json"] += b" "
        with self.assertRaises(TransportError):
            self._import(_result_zip(self.job, self.commit, tampered, self.payload))
        stale = _result_zip(self.job, self.commit, self.artifact_data, self.payload,
                            job_overrides={"directive_sha256": "0" * 64})
        with self.assertRaises(TransportError):
            self._import(stale)

    def test_excerpt_hash_and_result_source_authority_are_bound(self):
        bad_payload = json.loads(json.dumps(self.payload))
        bad_payload["excerpts"][0]["text"] = "different text"
        bad_job = self.store.create_job(bad_payload, job_id="job-bad-excerpt", model_route="colab",
                                        model_id="m", prompt_version="prompt-v1",
                                        compiler_version="c", retry_limit=0)
        with self.assertRaises(TransportError):
            self._export(bad_payload, job_id=bad_job["job_id"])
        altered_request = json.loads(json.dumps(self.payload))
        altered_request["task"]["prompt_template_sha256"] = "d" * 64
        with self.assertRaises(TransportError):
            self._import(_result_zip(self.job, self.commit, self.artifact_data, altered_request))

    def test_expired_job_is_rejected_on_export_and_import(self):
        result = _result_zip(self.job, self.commit, self.artifact_data, self.payload)
        with self.store._transaction() as connection:
            connection.execute("UPDATE knowledge_jobs SET deadline=? WHERE job_id=?",
                               ("2000-01-01T00:00:00Z", self.job["job_id"]))
        with self.assertRaises(TransportError):
            self._export()
        with self.assertRaises(TransportError):
            self._import(result)

    def test_zip_traversal_malformed_and_oversize_archives_are_rejected(self):
        traversal = BytesIO()
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../escape", b"x")
        with self.assertRaises(TransportError):
            self._import(traversal.getvalue())
        with self.assertRaises(TransportError):
            self._import(b"not a ZIP")
        oversized = BytesIO()
        with zipfile.ZipFile(oversized, "w") as archive:
            archive.writestr("huge", b"x" * (MAX_MEMBER_BYTES + 1))
        with self.assertRaises(TransportError):
            self._import(oversized.getvalue())
        special = BytesIO()
        info = zipfile.ZipInfo("special")
        info.external_attr = (0o010600) << 16  # FIFO, not a regular file.
        with zipfile.ZipFile(special, "w") as archive:
            archive.writestr(info, b"x")
        with self.assertRaises(TransportError):
            self._import(special.getvalue())
        encrypted = bytearray(_result_zip(self.job, self.commit, self.artifact_data, self.payload))
        # Set the encryption bit in both local and central ZIP headers.
        offset = 0
        while offset + 6 < len(encrypted):
            signature = encrypted[offset:offset + 4]
            flag_offset = offset + (6 if signature == b"PK\x03\x04" else 8)
            if signature in (b"PK\x03\x04", b"PK\x01\x02"):
                flags = int.from_bytes(encrypted[flag_offset:flag_offset + 2], "little") | 1
                encrypted[flag_offset:flag_offset + 2] = flags.to_bytes(2, "little")
            offset += 1
        with self.assertRaises(TransportError):
            self._import(bytes(encrypted))

    def test_import_refuses_preexisting_staging_data(self):
        stage = self.store.staging_dir(self.job["job_id"], self.job["generation"])
        (stage / "source.json").write_bytes(b"partial")
        with self.assertRaises(TransportError):
            self._import(_result_zip(self.job, self.commit, self.artifact_data, self.payload))
        self.assertEqual((stage / "source.json").read_bytes(), b"partial")

    def test_concurrent_exact_import_and_crash_recovery(self):
        result = _result_zip(self.job, self.commit, self.artifact_data, self.payload)
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: self._import(result), range(2)))
        self.assertEqual([item["manifest_sha256"] for item in outcomes],
                         [self.commit["manifest_sha256"]] * 2)

        # A fresh generation with fully adopted bytes simulates a crash before the DB CAS.
        recovery_job = self.store.begin_generation(self.job["job_id"], self.payload)
        recovery_commit, recovery_data = _commit(recovery_job, self.source, self.claim)
        stage = self.store.staging_dir(recovery_job["job_id"], recovery_job["generation"])
        for relative, data in recovery_data.items():
            (stage / relative).write_bytes(data)
        recovery_result = _result_zip(recovery_job, recovery_commit, recovery_data, self.payload)
        accepted = self._import(recovery_result)
        self.assertEqual(accepted["manifest_sha256"], recovery_commit["manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
