"""Focused tests for deterministic Base Pack construction from accepted Commits."""
import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.job_store import KnowledgeJobStore
from gurumoji.knowledge_builder.pack_builder import (
    PackBuildError, _build_base_pack_from_inputs, _load_base_catalog_data,
    build_base_pack, compute_base_root_sha256,
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def source(*, private=False, source_id="src-1"):
    return {
        "schema_version": 1, "source_id": source_id, "version": "v1", "sha256": "a" * 64,
        "title": "Fixture source", "source_type": "paper",
        "authors": ["Fixture Author"], "publication_year": 2024,
        "adaptation_notice": "Claim paraphrased; no source text is reproduced.",
        "license_url": {"kind": "https", "value": "https://example.org/license"},
        "locator": {"kind": "local_uri", "value": "file:///fixture/paper.pdf"} if private else
                   {"kind": "doi", "value": "10.1234/fixture"},
        "access_scope": "local_private" if private else "abstract",
        "license": {"license_id": "fixture-license", "terms": "Test fixture only."},
        "anchors": [{"anchor_id": "p1", "kind": "page", "start": "p. 1", "end": "p. 1",
                      "extracted_text_sha256": "b" * 64}],
        "rights": {"classification": "private" if private else "licensed",
                   "allowed_routes": ["local"] if private else ["local", "export"]},
    }


def claim(src, expert_id="exp-example", claim_id="claim-1"):
    value = {
        "schema_version": 1, "claim_id": claim_id, "expert_id": expert_id,
        "claim": "Fixture-only checked statement.", "applicability": ["fixture"], "exceptions": [],
        "claim_type": "literature",
        "evidence": [{"source_id": src["source_id"], "source_version": src["version"],
                      "source_sha256": src["sha256"], "anchor_id": "p1",
                      "span": {"kind": "page", "start": "p. 1", "end": "p. 1"},
                      "extracted_text_sha256": "b" * 64, "transform_history": []}],
        "contradictions": [], "status": "approved",
        "provenance": {"method": "fixture", "created_at": now()},
        "rights": {"classification": "private" if src["rights"]["classification"] == "private" else "licensed",
                   "allowed_routes": list(src["rights"]["allowed_routes"])},
    }
    value["reviewer"] = {"identity": "fixture-reviewer", "reviewed_at": now(),
                          "target_sha256": contracts.claim_review_target(value)}
    return value


class BasePackBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = KnowledgeJobStore(Path(self.temp.name) / "data")
        self.experts = {"exp-example": {"expert_id": "exp-example", "name": "Fixture"}}
        self.experts.update({f"exp-extra-{index:02d}": {"expert_id": f"exp-extra-{index:02d}", "name": "Fixture"}
                             for index in range(1, 17)})
        self.definition_hashes = {expert_id: hashlib.sha256(contracts.canonical_json(definition)).hexdigest()
                                  for expert_id, definition in self.experts.items()}
        self.source_note_hashes = {expert_id: hashlib.sha256(("source note " + expert_id).encode()).hexdigest()
                                   for expert_id in self.experts}
        self.base_root = compute_base_root_sha256(self.definition_hashes, self.source_note_hashes)

    def _accepted_job(self, src=None, claim_value=None, job_id="job-base"):
        src = src or source()
        claim_value = claim_value or claim(src)
        job = self.store.create_job({}, job_id=job_id, model_route="local", model_id="fixture-model",
                                    prompt_version="p1", compiler_version="c1", retry_limit=0)
        stage = self.store.staging_dir(job_id, 1)
        artifacts = []
        for filename, kind, record in (("source.json", "Source", src), ("claim.json", "Claim", claim_value)):
            data = contracts.canonical_json(record)
            (stage / filename).write_bytes(data)
            artifacts.append({"path": filename, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                              "record_type": kind, "schema_version": 1})
        commit = {"schema_version": 1, "job_id": job_id, "generation": 1, "attempt_id": job["attempt_id"],
                  "directive_sha256": job["directive_sha256"], "complete": True, "created_at": now(),
                  "artifacts": artifacts}
        commit["manifest_sha256"] = contracts.sha256_json(commit)
        self.store.accept_commit(job_id, 1, commit)
        return job

    def _build_fixture(self, *, job_ids=("job-base",), route="export", pack_id="pack-base",
                       expected_base_root_sha256=None, store=None):
        return _build_base_pack_from_inputs(
            store or self.store, pack_id=pack_id, accepted_job_ids=job_ids,
            expert_definitions=self.experts, source_note_hashes=self.source_note_hashes,
            expected_base_root_sha256=expected_base_root_sha256 or self.base_root,
            distribution_route=route, compiler_version="fixture-compiler",
        )

    def test_builds_registerable_pack_from_accepted_commits(self):
        self._accepted_job()
        manifest = self._build_fixture()
        self.assertEqual(manifest["base_root_sha256"], self.base_root)
        self.assertEqual(manifest["stage"], "internal_candidate")
        self.assertEqual(len(manifest["experts"]), 17)
        self.assertEqual(manifest["claim_ids"], ["claim-1"])
        self.assertEqual(manifest["source_ids"], ["src-1"])
        self.assertEqual(len(manifest["files"]), 19)
        source_file = self.store.pack_staging_dir("pack-base") / "knowledge" / "sources.jsonl"
        packed_source = json.loads(source_file.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(packed_source["authors"], ["Fixture Author"])
        self.assertEqual(packed_source["publication_year"], 2024)
        self.assertEqual(packed_source["adaptation_notice"], "Claim paraphrased; no source text is reproduced.")
        registration = self.store.register_pack(manifest)
        self.assertEqual(registration["stage"], "internal_candidate")
        self.assertEqual(self.store.get_pack("pack-base"), manifest)

    def test_commit_reference_order_is_canonical(self):
        source_a = source(source_id="src-a")
        source_z = source(source_id="src-z")
        self._accepted_job(source_a, claim(source_a, claim_id="claim-a"), "job-z")
        self._accepted_job(source_z, claim(source_z, claim_id="claim-z"), "job-a")
        manifest = self._build_fixture(job_ids=("job-z", "job-a"), pack_id="pack-order")
        self.assertEqual([reference["job_id"] for reference in manifest["commits"]], ["job-a", "job-z"])
        self.assertEqual(manifest["source_ids"], ["src-a", "src-z"])

        class AlternateStaging:
            def __init__(self, base_store):
                self.base_store = base_store
                self.calls = 0
                self.staging_root = base_store.staging_root / "proxy-root"

            def __getattr__(self, name):
                return getattr(self.base_store, name)

            def pack_staging_dir(self, _pack_id):
                self.calls += 1
                path = self.base_store.staging_root / "packs" / f"determinism-{self.calls}"
                path.mkdir(parents=True)
                return path

        alternate_store = AlternateStaging(self.store)
        reversed_manifest = self._build_fixture(job_ids=("job-a", "job-z"), pack_id="pack-order",
                                                store=alternate_store)
        self.assertEqual(reversed_manifest, manifest)

    def test_rejects_unaccepted_commit_and_pin_mismatch(self):
        with self.assertRaises(LookupError):
            self._build_fixture()
        self._accepted_job()
        with self.assertRaisesRegex(PackBuildError, "pinned Base root"):
            self._build_fixture(expected_base_root_sha256="f" * 64, pack_id="pack-bad-pin")

    def test_rejects_route_denial_and_private_local_source(self):
        self._accepted_job(job_id="job-route")
        with self.assertRaisesRegex(PackBuildError, "route is not authorized"):
            self._build_fixture(job_ids=("job-route",), route="colab", pack_id="pack-route")

        private_source = source(private=True)
        self._accepted_job(private_source, claim(private_source), job_id="job-private")
        with self.assertRaisesRegex(PackBuildError, "private or local paper"):
            self._build_fixture(job_ids=("job-private",), route="local", pack_id="pack-private")

    def test_rejects_claim_with_expert_outside_pinned_base(self):
        src = source()
        self._accepted_job(src, claim(src, "exp-unknown"), job_id="job-unknown-expert")
        with self.assertRaisesRegex(PackBuildError, "expert missing"):
            self._build_fixture(job_ids=("job-unknown-expert",), pack_id="pack-unknown-expert")

    def test_public_builder_reads_base_software_catalog_and_accepts_only_root_pin(self):
        definitions, source_hashes, root_hash = _load_base_catalog_data()
        expert_id = "exp-thematic-analysis"
        src = source()
        self._accepted_job(src, claim(src, expert_id), job_id="job-public")
        manifest = build_base_pack(
            self.store, pack_id="pack-public", accepted_job_ids=("job-public",),
            expected_base_root_sha256=root_hash, distribution_route="export", compiler_version="real-base-test",
        )
        self.assertEqual(len(definitions), 17)
        self.assertEqual(len(source_hashes), 17)
        self.assertEqual(manifest["base_root_sha256"], root_hash)
        self.assertEqual(manifest["stage"], "internal_candidate")
        self.assertEqual(manifest["experts"][0]["source_note_sha256"], source_hashes[manifest["experts"][0]["expert_id"]])
        self.assertNotIn("expert_definitions", inspect.signature(build_base_pack).parameters)

    def test_existing_pack_directory_fails_closed_and_write_failure_rolls_back(self):
        self._accepted_job()
        self.store.pack_staging_dir("pack-existing")
        with self.assertRaisesRegex(PackBuildError, "already exists"):
            self._build_fixture(pack_id="pack-existing")

        class FailingWriteStore:
            def __init__(self, base_store):
                self.base_store = base_store
                self.calls = 0

            def __getattr__(self, name):
                return getattr(self.base_store, name)

            def pack_staging_dir(self, pack_id):
                path = self.base_store.staging_root / "packs" / "rollback-fixture"
                path.mkdir(parents=True, exist_ok=False)
                return path

            def _artifact_path(self, stage, relative):
                self.calls += 1
                if self.calls == 3:
                    raise OSError("fixture write failure")
                return self.base_store._artifact_path(stage, relative)

        failing_store = FailingWriteStore(self.store)
        with self.assertRaisesRegex(OSError, "fixture write failure"):
            self._build_fixture(pack_id="pack-rollback", store=failing_store)
        self.assertFalse((self.store.staging_root / "packs" / "rollback-fixture").exists())


if __name__ == "__main__":
    unittest.main()
