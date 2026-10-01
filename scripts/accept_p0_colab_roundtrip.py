"""Validate and accept the result of the synthetic P0 Colab roundtrip once."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.job_store import KnowledgeJobStore
from gurumoji.knowledge_builder.transport import import_colab_result


DEFAULT_ROOT = ROOT / "output" / "knowledge-p0-colab-roundtrip"


def accept_result(artifact_root: Path, result_path: Path, expected_result_sha256: str) -> dict:
    metadata = json.loads((artifact_root / "p0_metadata.json").read_text(encoding="utf-8"))
    registry_value = json.loads((artifact_root / "approved_sources.json").read_text(encoding="utf-8"))
    result_bytes = result_path.read_bytes()
    if metadata.get("status") not in {"prepared_waiting_for_colab", "uploaded_waiting_for_colab"}:
        raise ValueError("P0 roundtrip is not waiting for its Colab result")
    expected_job_id = metadata["job_id"]
    expected_generation = metadata["generation"]
    if hashlib.sha256((artifact_root / "request.zip").read_bytes()).hexdigest() != metadata["request_zip_sha256"]:
        raise ValueError("Local request ZIP no longer matches its prepared checksum")
    if hashlib.sha256(result_bytes).hexdigest() != expected_result_sha256:
        raise ValueError("Result checksum does not match the observed Colab output")

    store = KnowledgeJobStore(artifact_root / metadata["state_directory"])
    job = store.get_job(expected_job_id)
    if not job or job["generation"] != expected_generation:
        raise ValueError("The local P0 Job is missing or has a different generation")
    approved_sources = {row["source_id"]: row for row in registry_value["sources"]}

    first_accept = import_colab_result(store, result_bytes, approved_sources=approved_sources)
    after_first = store.get_job(expected_job_id)
    if after_first["accepted_generation"] != expected_generation:
        raise ValueError("Colab result did not advance the accepted generation exactly once")
    accepted_manifest = store.accepted_commit(expected_job_id, expected_generation)
    if accepted_manifest["manifest_sha256"] != first_accept["manifest_sha256"]:
        raise ValueError("Accepted manifest differs from the imported completion record")

    replay = import_colab_result(store, result_bytes, approved_sources=approved_sources)
    after_replay = store.get_job(expected_job_id)
    if (after_replay["accepted_generation"] != expected_generation or
            replay["manifest_sha256"] != first_accept["manifest_sha256"]):
        raise ValueError("Idempotent replay changed the single accepted generation")

    metadata["status"] = "accepted_once"
    metadata["result_zip_sha256"] = hashlib.sha256(result_bytes).hexdigest()
    metadata["commit_manifest_sha256"] = first_accept["manifest_sha256"]
    metadata["accepted_generation"] = after_replay["accepted_generation"]
    metadata["idempotent_replay_verified"] = True
    (artifact_root / "p0_metadata.json").write_bytes(contracts.canonical_json(metadata))
    return {
        "status": metadata["status"],
        "job_id": expected_job_id,
        "generation": after_replay["accepted_generation"],
        "commit_manifest_sha256": first_accept["manifest_sha256"],
        "artifact_count": len(accepted_manifest["artifacts"]),
        "idempotent_replay_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_zip", type=Path)
    parser.add_argument("--expected-result-sha256", required=True,
                        help="SHA-256 printed in the saved Colab notebook output")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(accept_result(args.artifact_root, args.result_zip, args.expected_result_sha256),
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
