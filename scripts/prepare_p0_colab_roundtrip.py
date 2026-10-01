"""Prepare a synthetic, A100-checked Colab transport roundtrip in an isolated folder.

This creates one local job and immutable handoff, a Colab notebook with the
minimal worker source embedded in a bundle, and a local state store for later
acceptance. It never reads the runtime Vault or loads a model.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji.knowledge_builder import contracts
from gurumoji.knowledge_builder.job_store import KnowledgeJobStore
from gurumoji.knowledge_builder.transport import export_colab_job


DEFAULT_OUTPUT = ROOT / "output" / "knowledge-p0-colab-roundtrip"
EXCERPT = "Synthetic source excerpt for transport verification only; it contains no method guidance."
WORKER_PATHS = (
    "src/gurumoji/__init__.py",
    "src/gurumoji/knowledge_builder/__init__.py",
    "src/gurumoji/knowledge_builder/contracts.py",
    "src/gurumoji/knowledge_builder/job_store.py",
    "src/gurumoji/knowledge_builder/transport.py",
    "src/gurumoji/knowledge_builder/colab_worker.py",
    "src/gurumoji/knowledge_builder/colab_qwen3.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])
    return output.getvalue()


def _write_json(path: Path, value: object) -> bytes:
    data = contracts.canonical_json(value)
    path.write_bytes(data)
    return data


def _worker_archive() -> tuple[bytes, dict[str, str]]:
    files: dict[str, bytes] = {}
    for relative in WORKER_PATHS:
        path = ROOT / relative
        files[relative] = path.read_bytes()
    hashes = {name: _sha256(data) for name, data in sorted(files.items())}
    manifest = contracts.canonical_json({"schema_version": 1, "files": hashes})
    archive = _zip_bytes({**files, "worker_sources_manifest.json": manifest})
    return archive, hashes


def _notebook(bundle_b64: str, metadata: dict) -> bytes:
    source = r'''import base64
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath

import torch

BUNDLE_B64 = """@BUNDLE_B64@"""
EXPECTED_BUNDLE_SHA256 = "@BUNDLE_SHA256@"
EXPECTED_JOB_ID = "@JOB_ID@"
EXPECTED_GENERATION = @GENERATION@

def sha256(data):
    return hashlib.sha256(data).hexdigest()

bundle_bytes = base64.b64decode(BUNDLE_B64, validate=True)
assert sha256(bundle_bytes) == EXPECTED_BUNDLE_SHA256, "P0 bundle checksum mismatch"
with zipfile.ZipFile(BytesIO(bundle_bytes)) as zf:
    expected_members = {"request.zip", "approved_sources.json", "worker_sources.zip", "bundle_manifest.json"}
    assert set(zf.namelist()) == expected_members, "Unexpected bundle files"
    bundle = {name: zf.read(name) for name in expected_members}

bundle_manifest = json.loads(bundle["bundle_manifest.json"])
assert bundle_manifest["job_id"] == EXPECTED_JOB_ID
assert bundle_manifest["generation"] == EXPECTED_GENERATION
for name, digest in bundle_manifest["files"].items():
    assert name in bundle and sha256(bundle[name]) == digest, f"Bundle member hash mismatch: {name}"

# Validate the bundled worker source file set and every source hash before import.
worker_root = Path("/content/p0_worker")
worker_root.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(BytesIO(bundle["worker_sources.zip"])) as zf:
    names = set(zf.namelist())
    assert "worker_sources_manifest.json" in names
    manifest = json.loads(zf.read("worker_sources_manifest.json"))
    source_hashes = manifest["files"]
    assert names == set(source_hashes) | {"worker_sources_manifest.json"}
    for name, digest in source_hashes.items():
        member = PurePosixPath(name)
        assert not member.is_absolute() and ".." not in member.parts
        content = zf.read(name)
        assert sha256(content) == digest, f"Worker source hash mismatch: {name}"
        destination = worker_root.joinpath(*member.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
sys.path.insert(0, str(worker_root / "src"))

from gurumoji.knowledge_builder import contracts, transport
from gurumoji.knowledge_builder.colab_worker import run_colab_worker

registry_value = json.loads(bundle["approved_sources.json"])
assert registry_value["schema_version"] == 1
approved_sources = {source["source_id"]: source for source in registry_value["sources"]}
request_archive, members = transport._read_safe_zip(bundle["request.zip"])
try:
    handoff = transport._parse_canonical_json(transport._zip_read(request_archive, members, "handoff.json"))
    request_data = transport._zip_read(request_archive, members, "request.json")
    request = transport._parse_canonical_json(request_data)
finally:
    request_archive.close()
job = handoff["job"]
assert job["job_id"] == EXPECTED_JOB_ID and job["generation"] == EXPECTED_GENERATION
assert sha256(request_data) == job["input_manifest_sha256"]

# This small CUDA operation confirms the selected A100 is live. The generator
# below is deterministic fixture code, not an LLM call or analytical claim.
assert torch.cuda.is_available(), "CUDA GPU is required; select an A100 runtime"
device_name = torch.cuda.get_device_name(0)
assert "A100" in device_name.upper(), f"Expected A100, found {device_name}"
left = torch.ones((512, 512), device="cuda")
right = torch.ones((512, 512), device="cuda")
product = left @ right
torch.cuda.synchronize()
gpu_first = float(product[0, 0].item())
assert gpu_first == 512.0

def generate(task, excerpts):
    assert task["expert_id"] == "exp-p0-transport-fixture"
    assert len(excerpts) == 1
    excerpt = excerpts[0]
    source = approved_sources[excerpt["source_id"]]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    claim = {
        "schema_version": 1,
        "claim_id": "claim-p0-transport-fixture",
        "expert_id": task["expert_id"],
        "claim": "Synthetic transport fixture only; this is not method guidance.",
        "applicability": ["P0 transport smoke test"],
        "exceptions": [],
        "claim_type": "literature",
        "evidence": [{
            "source_id": source["source_id"], "source_version": source["version"],
            "source_sha256": source["sha256"], "anchor_id": excerpt["anchor_id"],
            "span": {"kind": "page", "start": "1", "end": "1"},
            "extracted_text_sha256": excerpt["extracted_text_sha256"], "transform_history": [],
        }],
        "contradictions": [],
        "status": "candidate",
        "provenance": {"method": "deterministic P0 transport fixture", "created_at": now},
        "rights": source["rights"],
        "reviewer": {"identity": "synthetic-fixture", "reviewed_at": now, "target_sha256": "0" * 64},
    }
    claim["reviewer"]["target_sha256"] = contracts.claim_review_target(claim)
    return [claim]

result_zip = run_colab_worker(bundle["request.zip"], approved_sources=approved_sources, generate=generate)
result_archive, result_members = transport._read_safe_zip(result_zip)
try:
    result_manifest = transport._parse_canonical_json(
        transport._zip_read(result_archive, result_members, transport._RESULT_MANIFEST))
finally:
    result_archive.close()
commit = result_manifest["commit"]
summary = {
    "status": "worker_result_created_unaccepted",
    "job_id": job["job_id"], "generation": job["generation"],
    "request_zip_sha256": sha256(bundle["request.zip"]),
    "input_manifest_sha256": job["input_manifest_sha256"],
    "result_zip_sha256": sha256(result_zip), "result_zip_size_bytes": len(result_zip),
    "commit_manifest_sha256": commit["manifest_sha256"],
    "artifact_count": len(commit["artifacts"]),
    "gpu": device_name, "gpu_matrix_first": gpu_first,
    "generator": "deterministic fixture; no LLM inference",
}
print("P0_RESULT_JSON=" + json.dumps(summary, sort_keys=True))
print("P0_RESULT_ZIP_BASE64=" + base64.b64encode(result_zip).decode("ascii"))
'''
    source = (source.replace("@BUNDLE_B64@", bundle_b64)
                    .replace("@BUNDLE_SHA256@", metadata["bundle_sha256"])
                    .replace("@JOB_ID@", metadata["job_id"])
                    .replace("@GENERATION@", str(metadata["generation"])))
    cells = [
        {
            "cell_type": "markdown", "metadata": {},
            "source": [
                "# Gurumoji P0 A100 transport smoke\n",
                "\n",
                "This notebook contains one synthetic job and a small worker source bundle. It does not contain user documents, credentials, or evaluation answers.\n",
                "\n",
                "Select an A100 GPU runtime, then run this notebook once. It checks a small CUDA matrix operation and runs a deterministic fixture through the Colab worker. It does not call an LLM. The result is still untrusted and is **not accepted** here.\n",
                "\n",
                "After the result appears, save this notebook to the shared Drive folder (Ctrl+S). Do not rerun it. The result ZIP is stored in the output as base64 so the local acceptance step can verify its hashes and accept the generation once.\n",
            ],
        },
        {
            "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": source.splitlines(keepends=True),
        },
    ]
    notebook = {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"gpuType": "A100", "include_colab_link": True, "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return (json.dumps(notebook, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def prepare(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output folder: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = output_dir / "local-state"
    store = KnowledgeJobStore(state_dir)

    excerpt_bytes = EXCERPT.encode("utf-8")
    source = {
        "schema_version": 1,
        "source_id": "source-p0-transport-fixture",
        "version": "fixture-v1",
        "sha256": _sha256(b"Synthetic source identity created for the P0 Colab roundtrip."),
        "title": "Synthetic P0 transport fixture",
        "source_type": "paper",
        "locator": {"kind": "doi", "value": "10.1234/p0-roundtrip-fixture"},
        "access_scope": "full_text",
        "license": {"license_id": "synthetic-fixture", "terms": "Original synthetic test text; local and Colab processing permitted."},
        "anchors": [{
            "anchor_id": "p1", "kind": "page", "start": "1", "end": "1",
            "extracted_text_sha256": _sha256(excerpt_bytes),
        }],
        "rights": {"classification": "licensed", "allowed_routes": ["local", "colab"]},
    }
    task_prompt = "P0 synthetic roundtrip fixture; no domain-knowledge generation."
    payload = {
        "schema_version": 1,
        "kind": "colab_source_excerpt_request",
        "task": {
            "expert_id": "exp-p0-transport-fixture",
            "task_kind": "knowledge_claim_generation",
            "prompt_version": "p0-transport-fixture-v1",
            "prompt_template_sha256": _sha256(task_prompt.encode("utf-8")),
        },
        "sources": [source],
        "excerpts": [{
            "source_id": source["source_id"], "source_version": source["version"],
            "source_sha256": source["sha256"], "anchor_id": "p1",
            "extracted_text_sha256": _sha256(excerpt_bytes), "text": EXCERPT,
        }],
    }
    job = store.create_job(
        payload,
        model_route="colab",
        model_id="deterministic-p0-transport-fixture",
        prompt_version="p0-transport-fixture-v1",
        compiler_version="p0-transport-fixture-v1",
        retry_limit=0,
        job_id="p0-colab-roundtrip-" + _sha256(task_prompt.encode())[:12],
        ttl_seconds=7 * 24 * 60 * 60,
    )
    request_zip = export_colab_job(store, job["job_id"], payload,
                                   approved_sources={source["source_id"]: source})
    approved_json = contracts.canonical_json({"schema_version": 1, "sources": [source]})
    worker_zip, worker_hashes = _worker_archive()
    files = {
        "request.zip": request_zip,
        "approved_sources.json": approved_json,
        "worker_sources.zip": worker_zip,
    }
    bundle_manifest = {
        "schema_version": 1,
        "job_id": job["job_id"],
        "generation": job["generation"],
        "input_manifest_sha256": job["input_manifest_sha256"],
        "deadline": job["deadline"],
        "files": {name: _sha256(data) for name, data in sorted(files.items())},
    }
    files["bundle_manifest.json"] = contracts.canonical_json(bundle_manifest)
    bundle_zip = _zip_bytes(files)

    source_path = output_dir / "approved_sources.json"
    source_path.write_bytes(approved_json)
    request_path = output_dir / "request.zip"
    request_path.write_bytes(request_zip)
    worker_path = output_dir / "worker_sources.zip"
    worker_path.write_bytes(worker_zip)
    bundle_path = output_dir / "p0_colab_roundtrip_bundle.zip"
    bundle_path.write_bytes(bundle_zip)

    metadata = {
        "schema_version": 1,
        "status": "prepared_waiting_for_colab",
        "job_id": job["job_id"],
        "generation": job["generation"],
        "deadline": job["deadline"],
        "input_manifest_sha256": job["input_manifest_sha256"],
        "request_zip_sha256": _sha256(request_zip),
        "approved_sources_sha256": _sha256(approved_json),
        "worker_sources_sha256": _sha256(worker_zip),
        "worker_source_file_hashes": worker_hashes,
        "bundle_sha256": _sha256(bundle_zip),
        "bundle_size_bytes": len(bundle_zip),
        "accepted_generation_before_colab": store.get_job(job["job_id"])["accepted_generation"],
        "state_directory": "local-state",
        "result_zip_path": "result.zip",
    }
    metadata_path = output_dir / "p0_metadata.json"
    _write_json(metadata_path, metadata)
    notebook_bytes = _notebook(base64.b64encode(bundle_zip).decode("ascii"), metadata)
    notebook_path = output_dir / "Gurumoji_P0_A100_Roundtrip.ipynb"
    notebook_path.write_bytes(notebook_bytes)
    return {
        "status": metadata["status"],
        "job_id": job["job_id"],
        "generation": job["generation"],
        "deadline": job["deadline"],
        "bundle_sha256": metadata["bundle_sha256"],
        "bundle_size_bytes": metadata["bundle_size_bytes"],
        "notebook_size_bytes": len(notebook_bytes),
        "output_dir": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output_dir), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
