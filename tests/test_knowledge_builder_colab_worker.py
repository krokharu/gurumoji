import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.job_store import KnowledgeJobStore
from gurumoji.knowledge_builder import transport
from gurumoji.knowledge_builder.colab_worker import run_colab_worker

EXCERPT = "Synthetic licensed excerpt for worker tests."
EXCERPT_HASH = hashlib.sha256(EXCERPT.encode()).hexdigest()


def _source(*, allowed_routes=("local", "colab"), source_id="source-worker"):
    return {
        "schema_version": 1, "source_id": source_id, "version": "v1", "sha256": "a" * 64,
        "title": "Synthetic worker source", "source_type": "paper",
        "locator": {"kind": "doi", "value": "10.1234/worker"}, "access_scope": "full_text",
        "license": {"license_id": "fixture", "terms": "Synthetic test data"},
        "anchors": [{"anchor_id": "p1", "kind": "page", "start": "1", "end": "1",
                      "extracted_text_sha256": EXCERPT_HASH}],
        "rights": {"classification": "licensed", "allowed_routes": list(allowed_routes)},
    }


def _claim(source, *, status="candidate", claim_id="claim-worker"):
    claim = {
        "schema_version": 1, "claim_id": claim_id, "expert_id": "exp-worker",
        "claim": "A synthetic method claim.", "applicability": ["fixture"], "exceptions": [],
        "claim_type": "literature", "evidence": [{"source_id": source["source_id"],
            "source_version": source["version"], "source_sha256": source["sha256"], "anchor_id": "p1",
            "span": {"kind": "page", "start": "1", "end": "1"},
            "extracted_text_sha256": EXCERPT_HASH, "transform_history": []}],
        "contradictions": [], "status": status,
        "provenance": {"method": "synthetic fixture", "created_at": "2026-09-27T00:00:00Z"},
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab"]},
        "reviewer": {"identity": "fixture-reviewer", "reviewed_at": "2026-09-27T00:00:00Z",
                     "target_sha256": "0" * 64},
    }
    claim["reviewer"]["target_sha256"] = contracts.claim_review_target(claim)
    return claim


class ColabWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = KnowledgeJobStore(Path(self.temp.name) / "data")
        self.source = _source()
        self.approved = {self.source["source_id"]: self.source}
        self.payload = {"schema_version": 1, "kind": "colab_source_excerpt_request",
            "task": {"expert_id": "exp-worker", "task_kind": "knowledge_claim_generation",
                     "prompt_version": "prompt-v1", "prompt_template_sha256": "b" * 64},
            "sources": [self.source], "excerpts": [{"source_id": self.source["source_id"],
                "source_version": self.source["version"], "source_sha256": self.source["sha256"],
                "anchor_id": "p1", "extracted_text_sha256": EXCERPT_HASH, "text": EXCERPT}]}
        self.job = self.store.create_job(self.payload, job_id="job-worker", model_route="colab",
            model_id="synthetic", prompt_version="prompt-v1", compiler_version="compiler-v1", retry_limit=1)
        self.bundle = transport.export_colab_job(self.store, self.job["job_id"], self.payload,
                                                  approved_sources=self.approved)

    def _generate(self, task, excerpts):
        self.assertEqual(task["expert_id"], "exp-worker")
        self.assertEqual(excerpts[0]["text"], EXCERPT)
        return [_claim(self.source)]

    def _custom_bundle(self, payload, job=None):
        job = job or self.job
        request = contracts.canonical_json(payload)
        changed_job = dict(job, input_manifest_sha256=hashlib.sha256(request).hexdigest())
        # Recompute the immutable directive for this standalone malformed/security fixture.
        changed_job["directive_sha256"] = contracts.job_directive_hash(changed_job)
        handoff = {"schema_version": 1, "kind": "colab_request", "job": changed_job,
                   "request": {"path": "request.json", "size_bytes": len(request),
                               "sha256": hashlib.sha256(request).hexdigest()}}
        return transport._deterministic_zip({"handoff.json": contracts.canonical_json(handoff),
                                             "request.json": request})

    def test_mock_generation_returns_candidate_commit_and_imports_locally(self):
        result = run_colab_worker(self.bundle, approved_sources=self.approved, generate=self._generate)
        imported = transport.import_colab_result(self.store, result, approved_sources=self.approved)
        self.assertEqual(imported["job_id"], self.job["job_id"])
        accepted = self.store.accepted_commit(self.job["job_id"])
        self.assertEqual(len(accepted["artifacts"]), 2)
        self.assertEqual({item["record_type"] for item in accepted["artifacts"]}, {"Source", "Claim"})

    def test_malformed_unauthorized_and_expired_requests_fail(self):
        with self.assertRaises(transport.TransportError):
            run_colab_worker(b"not a zip", approved_sources=self.approved, generate=self._generate)
        restricted = _source(allowed_routes=("local",))
        restricted_payload = json.loads(json.dumps(self.payload))
        restricted_payload["sources"] = [restricted]
        restricted_payload["excerpts"][0]["source_sha256"] = restricted["sha256"]
        restricted_approved = {restricted["source_id"]: restricted}
        with self.assertRaises(transport.TransportError):
            run_colab_worker(self._custom_bundle(restricted_payload), approved_sources=restricted_approved,
                              generate=self._generate)
        expired = dict(self.job, deadline="2000-01-01T00:00:00Z")
        expired["directive_sha256"] = contracts.job_directive_hash(expired)
        with self.assertRaises(transport.TransportError):
            run_colab_worker(self._custom_bundle(self.payload, expired), approved_sources=self.approved,
                              generate=self._generate)

    def test_secret_input_and_non_candidate_output_fail(self):
        secret = dict(self.payload, metadata={"answer_key": "sealed"})
        with self.assertRaises(transport.TransportError):
            run_colab_worker(self._custom_bundle(secret), approved_sources=self.approved, generate=self._generate)
        with self.assertRaises(transport.TransportError):
            run_colab_worker(self.bundle, approved_sources=self.approved,
                             generate=lambda _task, _excerpts: [_claim(self.source, status="approved")])

    def test_source_authority_mismatch_and_untrusted_claim_evidence_fail(self):
        changed = dict(self.source, title="Different title")
        with self.assertRaises(transport.TransportError):
            run_colab_worker(self.bundle, approved_sources={changed["source_id"]: changed},
                             generate=self._generate)
        forged = _claim(self.source)
        forged["evidence"][0]["anchor_id"] = "not-requested"
        forged["reviewer"]["target_sha256"] = contracts.claim_review_target(forged)
        with self.assertRaises(transport.TransportError):
            run_colab_worker(self.bundle, approved_sources=self.approved,
                             generate=lambda _task, _excerpts: [forged])

    def test_colon_ids_roundtrip_with_safe_artifact_filenames(self):
        source = _source(source_id="source:worker")
        approved = {source["source_id"]: source}
        payload = json.loads(json.dumps(self.payload))
        payload["sources"] = [source]
        payload["excerpts"][0]["source_id"] = source["source_id"]
        store = KnowledgeJobStore(Path(self.temp.name) / "colon-data")
        job = store.create_job(payload, job_id="job-colon", model_route="colab", model_id="synthetic",
                               prompt_version="prompt-v1", compiler_version="compiler-v1", retry_limit=1)
        request_zip = transport.export_colab_job(store, job["job_id"], payload, approved_sources=approved)
        result_zip = run_colab_worker(request_zip, approved_sources=approved,
                                      generate=lambda _task, _excerpts: [_claim(source, claim_id="claim:worker")])
        accepted = transport.import_colab_result(store, result_zip, approved_sources=approved)
        self.assertEqual(accepted["job_id"], job["job_id"])
        commit = store.accepted_commit(job["job_id"])
        self.assertEqual({item["record_type"] for item in commit["artifacts"]}, {"Source", "Claim"})
        self.assertTrue(all(":" not in item["path"] for item in commit["artifacts"]))


if __name__ == "__main__":
    unittest.main()
