import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.job_store import (
    DuplicateAcceptanceError, ExpiredJobError, JobStoreError, KnowledgeJobStore,
    StaleGenerationError, UnacceptedCommitError,
)


def stamp(delta=timedelta()):
    return (datetime.now(timezone.utc) + delta).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_source(routes=None):
    return {"schema_version": 1, "source_id": "src-paper-1", "version": "rev-1",
            "sha256": "a" * 64, "title": "Example source", "source_type": "paper",
            "authors": ["Example Author"], "publication_year": 2024,
            "adaptation_notice": "Claims are paraphrased; no source text is reproduced.",
            "locator": {"kind": "doi", "value": "10.1234/example"}, "access_scope": "full_text",
            "license": {"license_id": "license-x", "terms": "Local use permitted."},
            "license_url": {"kind": "https", "value": "https://example.org/license"},
            "anchors": [{"anchor_id": "p4", "kind": "page", "start": "p. 4", "end": "p. 4",
                         "extracted_text_sha256": "b" * 64}],
            "rights": {"classification": "licensed", "allowed_routes": routes or ["local"]}}


def make_claim(source=None, routes=None):
    source = source or make_source()
    claim = {
        "schema_version": 1, "claim_id": "claim-1", "expert_id": "exp-example",
        "claim": "A checked methodological statement.", "applicability": ["when condition A holds"],
        "exceptions": ["when condition B holds"], "claim_type": "literature",
        "evidence": [{"source_id": source["source_id"], "source_version": source["version"],
                      "source_sha256": source["sha256"],
                      "anchor_id": "p4", "span": {"kind": "page", "start": "p. 4", "end": "p. 4"},
                      "extracted_text_sha256": "b" * 64,
                      "transform_history": [{"operation": "OCR", "tool": "ExampleOCR",
                                              "version": "1.0", "output_sha256": "c" * 64}]}],
        "contradictions": [], "status": "approved",
        "provenance": {"method": "manual extraction", "created_at": stamp()},
        "rights": {"classification": "licensed", "allowed_routes": routes or ["local"]},
    }
    claim["reviewer"] = {"identity": "reviewer@example", "reviewed_at": stamp(),
                         "target_sha256": contracts.claim_review_target(claim)}
    return claim


def make_commit(job, artifacts):
    job_id, generation = job["job_id"], job["generation"]
    commit = {"schema_version": 1, "job_id": job_id, "generation": generation, "complete": True,
              "attempt_id": job["attempt_id"], "directive_sha256": job["directive_sha256"],
              "created_at": stamp(), "artifacts": artifacts}
    commit["manifest_sha256"] = contracts.sha256_json(commit)
    return commit


def make_pack(commit, source, claim, pack_id="pack-example"):
    experts = [{"expert_id": "exp-example", "source_note_sha256": "d" * 64, "definition_sha256": "e" * 64}]
    experts.extend({"expert_id": f"exp-extra-{index:02d}", "source_note_sha256": "d" * 64,
                    "definition_sha256": "e" * 64}
                   for index in range(1, 17))
    manifest = {"schema_version": 1, "pack_id": pack_id, "flavor": "base", "distribution_route": "export",
                "stage": "internal_candidate", "compiler_version": "1.0", "experts": experts,
                "commits": [{"job_id": commit["job_id"], "generation": commit["generation"],
                             "manifest_sha256": commit["manifest_sha256"]}],
                "claim_ids": [claim["claim_id"]], "source_ids": [source["source_id"]],
                "files": [], "base_root_sha256": "b" * 64, "overlay_root_sha256": None}
    manifest["root_sha256"] = contracts.sha256_json(manifest)
    return manifest


class ContractTests(unittest.TestCase):
    def test_source_citation_metadata_is_optional_but_validated(self):
        source = make_source()
        self.assertEqual(contracts.validate_source(source)["publication_year"], 2024)
        legacy = {key: value for key, value in source.items()
                  if key not in {"authors", "publication_year", "adaptation_notice", "license_url"}}
        self.assertIs(contracts.validate_source(legacy), legacy)
        with self.assertRaises(contracts.ContractError):
            contracts.validate_source({**source, "publication_year": "2013"})
        with self.assertRaises(contracts.ContractError):
            contracts.validate_source({**source, "authors": ["Author", "Author"]})

    def test_export_requires_complete_attribution(self):
        source = make_source(["local", "export"])
        contracts.authorize_route([source], "export")
        claim = make_claim(source, ["local", "export"])
        contracts.authorize_route([claim], "export", sources={source["source_id"]: source})
        for missing_field in ("authors", "publication_year", "license_url", "adaptation_notice"):
            incomplete = {key: value for key, value in source.items() if key != missing_field}
            with self.subTest(field=missing_field), self.assertRaises(PermissionError):
                contracts.authorize_route([incomplete], "export")
            with self.subTest(claim_source_field=missing_field), self.assertRaises(PermissionError):
                contracts.authorize_route([claim], "export", sources={source["source_id"]: incomplete})
        with self.assertRaises(contracts.ContractError):
            contracts.validate_source({**source, "license_url": {"kind": "https", "value": "http://example.org/license"}})

    def test_claim_requires_review_hash_and_source_rights_intersection(self):
        source = make_source(["local"])
        claim = make_claim(source, ["local"])
        self.assertIs(contracts.validate_claim(claim, {source["source_id"]: source}), claim)
        with self.assertRaises(contracts.ContractError):
            contracts.validate_claim({**claim, "claim": "tampered"}, {source["source_id"]: source})
        overbroad = make_claim(source, ["local", "export"])
        with self.assertRaises(contracts.ContractError):
            contracts.validate_claim(overbroad, {source["source_id"]: source})

    def test_route_authorization_fails_closed_for_claim_and_source(self):
        source = make_source(["local", "export"])
        claim = make_claim(source, ["local", "export"])
        with self.assertRaises(PermissionError):
            contracts.authorize_route([claim], "remote_llm", sources={source["source_id"]: source})
        with self.assertRaises(contracts.ContractError):
            contracts.authorize_route([claim], "remote_llm")

    def test_job_route_authorization_uses_immutable_job_directive(self):
        store = KnowledgeJobStore(Path(tempfile.mkdtemp()) / "job-route")
        self.addCleanup(lambda: __import__("shutil").rmtree(store.root.parent, ignore_errors=True))
        job = store.create_job({}, job_id="job-route", model_route="local", model_id="m1",
                               prompt_version="p1", compiler_version="c1", retry_limit=0)
        source = make_source(["local"])
        claim = make_claim(source, ["local"])
        contracts.authorize_job_route(job, [source, claim], sources={source["source_id"]: source}, route="local")
        with self.assertRaises(contracts.ContractError):
            contracts.authorize_job_route(job, [source, claim], sources={source["source_id"]: source}, route="export")

    def test_evaluation_rejects_legacy_unbound_record(self):
        legacy = {"schema_version": 1, "evaluation_id": "eval-1", "pack_root_sha256": "a" * 64,
                  "model_id": "local-model-v1", "prompt_version": "p1", "suite_id": "suite-1",
                  "case_ids": ["case-1"], "metrics": {"grounded": 1.0}, "created_at": stamp()}
        with self.assertRaises(contracts.ContractError):
            contracts.validate_evaluation(legacy)

    def test_pack_manifest_rejects_arbitrary_runtime_role(self):
        expert = {"expert_id": "exp-1", "source_note_sha256": "e" * 64, "definition_sha256": "a" * 64}
        pack = {"schema_version": 1, "pack_id": "pack-1", "flavor": "base", "stage": "internal_candidate",
                "distribution_route": "local", "compiler_version": "c1", "experts": [expert],
                "commits": [{"job_id": "job-1", "generation": 1, "manifest_sha256": "b" * 64}],
                "claim_ids": ["claim-1"], "source_ids": ["source-1"],
                "files": [{"path": "runtime.json", "size_bytes": 2, "sha256": "c" * 64, "role": "runtime"}],
                "base_root_sha256": contracts.sha256_json([expert]), "overlay_root_sha256": None}
        pack["root_sha256"] = contracts.sha256_json(pack)
        with self.assertRaises(contracts.ContractError):
            contracts.validate_pack_manifest(pack)
        pack["files"][0]["role"] = "documentation"
        pack["root_sha256"] = contracts.sha256_json({k: v for k, v in pack.items() if k != "root_sha256"})
        with self.assertRaises(contracts.ContractError):
            contracts.validate_pack_manifest(pack)


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = KnowledgeJobStore(Path(self.temp.name) / "data")

    def _job(self, request=None, *, job_id):
        return self.store.create_job(request or {}, job_id=job_id, model_route="local", model_id="model-v1",
                                     prompt_version="p1", compiler_version="c1", retry_limit=2)

    def _write_commit(self, job, records=None):
        records = records or [("source.json", "Source", make_source())]
        stage = self.store.staging_dir(job["job_id"], job["generation"])
        artifacts = []
        for relative, kind, record in records:
            data = contracts.canonical_json(record)
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            artifacts.append({"path": relative, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                              "record_type": kind, "schema_version": 1})
        return make_commit(job, artifacts)

    def _write_pack(self, manifest, source, claim, payload=b'{}'):
        directory = self.store.pack_staging_dir(manifest["pack_id"])
        source_data = contracts.canonical_json(source) + b"\n"
        claim_data = contracts.canonical_json(claim) + b"\n"
        files = [("source.jsonl", source_data, "knowledge_source", None),
                 ("claim.jsonl", claim_data, "knowledge_claim", None)]
        for expert in manifest["experts"]:
            expert_id = expert["expert_id"]
            definition = contracts.canonical_json({"expert_id": expert_id, "name": expert_id})
            expert["definition_sha256"] = hashlib.sha256(definition).hexdigest()
            expert["source_note_sha256"] = "d" * 64
            files.append((f"{expert_id}.json", definition, "expert_definition", expert_id))
        manifest["files"] = []
        for name, data, role, expert_id in files:
            (directory / name).write_bytes(data)
            item = {"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "role": role}
            if expert_id:
                item["expert_id"] = expert_id
            manifest["files"].append(item)
        manifest["root_sha256"] = contracts.sha256_json({k: v for k, v in manifest.items() if k != "root_sha256"})
        manifest["base_root_sha256"] = contracts.sha256_json([
            {"expert_id": expert["expert_id"], "source_note_sha256": expert["source_note_sha256"],
             "definition_sha256": expert["definition_sha256"]}
            for expert in sorted(manifest["experts"], key=lambda entry: entry["expert_id"])
        ])
        manifest["root_sha256"] = contracts.sha256_json({k: v for k, v in manifest.items() if k != "root_sha256"})
        (directory / "pack-manifest.json").write_bytes(contracts.canonical_json(manifest))
        return manifest

    def _rewrite_pack_sidecar(self, manifest):
        (self.store.pack_staging_dir(manifest["pack_id"]) / "pack-manifest.json").write_bytes(
            contracts.canonical_json(manifest))

    def test_explicit_data_dir_is_required(self):
        with self.assertRaises(ValueError):
            KnowledgeJobStore(None)

    def test_accepts_only_exact_artifacts_and_pack_only_accepted_commit(self):
        job = self._job({"expert_id": "exp-example"}, job_id="job-1")
        source = make_source(["local", "export"])
        claim = make_claim(source, ["local", "export"])
        commit = self._write_commit(job, [("source.json", "Source", source), ("claim.json", "Claim", claim)])
        pack = self._write_pack(make_pack(commit, source, claim), source, claim)
        with self.assertRaises(UnacceptedCommitError):
            self.store.register_pack(pack)
        accepted = self.store.accept_commit(job["job_id"], job["generation"], commit)
        self.assertEqual(accepted["manifest_sha256"], commit["manifest_sha256"])
        self.assertEqual(self.store.get_job("job-1")["accepted_generation"], 1)
        self.assertEqual(self.store.accepted_commit("job-1"), commit)
        self.assertEqual(self.store.accept_commit(job["job_id"], job["generation"], commit), accepted)
        self.assertEqual(self.store.register_pack(pack)["root_sha256"], pack["root_sha256"])
        self.assertEqual(self.store.get_pack(pack["pack_id"], expected_root_sha256=pack["root_sha256"]), pack)
        with self.assertRaisesRegex(JobStoreError, "frozen"):
            self.store.begin_generation("job-1", {"retry": 1})
        self.assertEqual(self.store.get_pack(pack["pack_id"]), pack)
        self.assertEqual(self.store.accept_commit("job-1", 1, commit), accepted)
        altered = {**commit, "created_at": stamp(timedelta(seconds=1))}
        altered["manifest_sha256"] = contracts.sha256_json({k: v for k, v in altered.items()
                                                           if k != "manifest_sha256"})
        with self.assertRaises(DuplicateAcceptanceError):
            self.store.accept_commit("job-1", 1, altered)

    def test_size_hash_and_schema_are_checked_before_acceptance(self):
        job = self._job({}, job_id="job-tamper")
        commit = self._write_commit(job)
        artifact = self.store.staging_dir("job-tamper", 1) / "source.json"
        artifact.write_bytes(artifact.read_bytes() + b" ")
        with self.assertRaisesRegex(JobStoreError, "byte size|SHA-256"):
            self.store.accept_commit("job-tamper", 1, commit)
        self.assertEqual(self.store.get_job("job-tamper")["accepted_generation"], 0)

    def test_exact_commit_retry_revalidates_artifact_bytes(self):
        job = self._job({}, job_id="job-replay")
        commit = self._write_commit(job)
        self.store.accept_commit("job-replay", 1, commit)
        artifact = self.store.staging_dir("job-replay", 1) / "source.json"
        artifact.write_bytes(artifact.read_bytes() + b" ")
        with self.assertRaisesRegex(JobStoreError, "byte size|SHA-256"):
            self.store.accept_commit("job-replay", 1, commit)

    def test_path_escape_and_symlink_are_rejected(self):
        job = self._job({}, job_id="job-path")
        commit = self._write_commit(job)
        commit["artifacts"][0]["path"] = "../outside.json"
        commit["manifest_sha256"] = contracts.sha256_json({k: v for k, v in commit.items() if k != "manifest_sha256"})
        with self.assertRaises(contracts.ContractError):
            self.store.accept_commit("job-path", 1, commit)

    def test_stale_generation_expiry_and_monotonic_acceptance(self):
        first = self._job({}, job_id="job-cas")
        first_commit = self._write_commit(first)
        second = self.store.begin_generation("job-cas", {"retry": 1})
        with self.assertRaises(StaleGenerationError):
            self.store.accept_commit("job-cas", 1, first_commit)
        second_commit = self._write_commit(second)
        self.store.accept_commit("job-cas", 2, second_commit)
        self.assertEqual(self.store.get_job("job-cas")["accepted_generation"], 2)
        with self.assertRaises(StaleGenerationError):
            self.store.accept_commit("job-cas", 1, first_commit)
        self.assertEqual(self.store.accept_commit("job-cas", 2, second_commit)["manifest_sha256"],
                         second_commit["manifest_sha256"])
        with self.assertRaises(UnacceptedCommitError):
            self.store.accepted_commit("job-cas", 1)

        expiring = self._job({}, job_id="job-expire")
        with self.store._transaction() as connection:
            connection.execute("UPDATE knowledge_jobs SET deadline=? WHERE job_id=?", ("2000-01-01T00:00:00Z", "job-expire"))
        commit = self._write_commit(expiring)
        with self.assertRaises(ExpiredJobError):
            self.store.accept_commit("job-expire", 1, commit)
        self.assertEqual(self.store.get_job("job-expire")["status"], "expired")

    def test_pack_rejects_unaccepted_or_modified_commit_reference(self):
        job = self._job({}, job_id="job-pack")
        source = make_source(["local", "export"])
        claim = make_claim(source, ["local", "export"])
        commit = self._write_commit(job, [("source.json", "Source", source), ("claim.json", "Claim", claim)])
        pack = self._write_pack(make_pack(commit, source, claim), source, claim)
        with self.assertRaises(UnacceptedCommitError):
            self.store.register_pack(pack)
        self.store.accept_commit("job-pack", 1, commit)
        pack["commits"][0]["manifest_sha256"] = "f" * 64
        pack["root_sha256"] = contracts.sha256_json({k: v for k, v in pack.items() if k != "root_sha256"})
        self._rewrite_pack_sidecar(pack)
        with self.assertRaises(UnacceptedCommitError):
            self.store.register_pack(pack)

    def test_pack_reader_rechecks_file_hash_and_rejects_answer_keys(self):
        job = self._job({}, job_id="job-reader")
        source = make_source(["local", "export"])
        claim = make_claim(source, ["local", "export"])
        commit = self._write_commit(job, [("source.json", "Source", source), ("claim.json", "Claim", claim)])
        self.store.accept_commit("job-reader", 1, commit)
        pack = self._write_pack(make_pack(commit, source, claim), source, claim)
        self.store.register_pack(pack)
        runtime_file = self.store.pack_staging_dir(pack["pack_id"]) / "claim.jsonl"
        runtime_file.write_text('{"changed":true}', encoding="utf-8")
        with self.assertRaisesRegex(JobStoreError, "size or SHA-256"):
            self.store.get_pack(pack["pack_id"])


    def test_pack_rejects_claim_for_missing_expert(self):
        job = self._job({}, job_id="job-expert-ref")
        source = make_source(["local", "export"])
        claim = make_claim(source, ["local", "export"])
        claim["expert_id"] = "exp-unknown"
        claim["reviewer"]["target_sha256"] = contracts.claim_review_target(claim)
        commit = self._write_commit(job, [("source.json", "Source", source), ("claim.json", "Claim", claim)])
        self.store.accept_commit(job["job_id"], 1, commit)
        pack = self._write_pack(make_pack(commit, source, claim, "pack-missing-expert"), source, claim)
        with self.assertRaisesRegex(JobStoreError, "expert absent"):
            self.store.register_pack(pack)

    def test_pack_jsonl_must_parse_and_match_accepted_records(self):
        job = self._job({}, job_id="job-pack-binding")
        source = make_source(["local", "export"])
        claim = make_claim(source, ["local", "export"])
        commit = self._write_commit(job, [("source.json", "Source", source), ("claim.json", "Claim", claim)])
        self.store.accept_commit(job["job_id"], 1, commit)

        malformed = self._write_pack(make_pack(commit, source, claim, "pack-bad-jsonl"), source, claim)
        claims_path = self.store.pack_staging_dir("pack-bad-jsonl") / "claim.jsonl"
        claims_path.write_text('{"claim_id":\n', encoding="utf-8")
        malformed["files"][1]["size_bytes"] = claims_path.stat().st_size
        malformed["files"][1]["sha256"] = hashlib.sha256(claims_path.read_bytes()).hexdigest()
        malformed["root_sha256"] = contracts.sha256_json({k: v for k, v in malformed.items() if k != "root_sha256"})
        self._rewrite_pack_sidecar(malformed)
        with self.assertRaisesRegex(JobStoreError, "JSONL could not be parsed"):
            self.store.register_pack(malformed)

        changed_claim = {**claim, "claim": "Different but valid reviewed claim."}
        changed_claim["reviewer"] = {**claim["reviewer"],
                                      "target_sha256": contracts.claim_review_target(changed_claim)}
        mismatch = self._write_pack(make_pack(commit, source, claim, "pack-content-mismatch"), source, changed_claim)
        with self.assertRaisesRegex(JobStoreError, "do not match accepted Commit"):
            self.store.register_pack(mismatch)


if __name__ == "__main__":
    unittest.main()
