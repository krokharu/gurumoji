"""Run one pinned, bounded knowledge Claim job on a CLI-managed A100."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath

BUNDLE = Path("/content/gurumoji_batch_b20260927t201116-05.zip")
RESULT = Path("/content/gurumoji_batch_result_b20260927t201116-05.zip")
STATUS = Path("/content/gurumoji_batch_status_b20260927t201116-05.json")
EXPECTED_BUNDLE_SHA256 = "8db14248cc406036fdf9d6bc80a481dccd4c7c7a08c3d79d0bdd7b735612a33a"
EXPECTED_JOB_ID = "b20260927t201116-05"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_status(**fields: object) -> None:
    value = {
        "schema_version": 1,
        "job_id": EXPECTED_JOB_ID,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **fields,
    }
    STATUS.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def read_zip(data: bytes, expected: set[str]) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError("bundle member set is invalid")
        for item in archive.infolist():
            if item.is_dir() or item.file_size > 2_000_000:
                raise ValueError("bundle member size is invalid")
        return {name: archive.read(name) for name in names}


def install_model_dependencies(deadline: datetime) -> None:
    def install(*packages: str) -> None:
        left = (deadline - datetime.now(timezone.utc)).total_seconds()
        if left < 90:
            raise TimeoutError("job deadline too near for dependency installation")
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", *packages],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=min(600, max(1, int(left - 30))),
            check=False,
        )
        if completed.returncode:
            raise RuntimeError("dependency install failed: " + completed.stdout[-1200:])
        importlib.invalidate_caches()

    if importlib.util.find_spec("awq") is None:
        install("autoawq==0.2.9")
    try:
        transformers = importlib.import_module("transformers")
        version = tuple(int(p) for p in re.findall(r"\d+", transformers.__version__)[:3])
    except ImportError:
        version = (0,)
    if version < (4, 51, 0) or version >= (5, 0, 0):
        install("transformers>=4.51.0,<5")
        sys.modules.pop("transformers", None)
        importlib.import_module("transformers")


def main() -> None:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is unavailable")
    gpu = torch.cuda.get_device_name(0)
    if "A100" not in gpu.upper():
        raise RuntimeError("an A100 GPU is required")
    save_status(status="validating_bundle", gpu=gpu)

    bundle_bytes = BUNDLE.read_bytes()
    if digest(bundle_bytes) != EXPECTED_BUNDLE_SHA256:
        raise ValueError("bundle SHA-256 mismatch")
    bundle = read_zip(bundle_bytes, {
        "bundle_manifest.json", "request.zip", "approved_sources.json", "worker_sources.zip",
    })
    manifest = json.loads(bundle["bundle_manifest.json"])
    if (manifest["schema_version"] != 1 or manifest["kind"] != "gurumoji_colab_job_bundle"
            or manifest["job_id"] != EXPECTED_JOB_ID or manifest["generation"] != 1):
        raise ValueError("bundle manifest does not match the assigned job")
    if manifest["files"] != {name: digest(bundle[name]) for name in bundle if name != "bundle_manifest.json"}:
        raise ValueError("bundle member hashes are invalid")

    worker_data = bundle["worker_sources.zip"]
    with zipfile.ZipFile(BytesIO(worker_data)) as archive:
        worker_names = archive.namelist()
        if len(worker_names) != len(set(worker_names)) or "worker_sources_manifest.json" not in worker_names:
            raise ValueError("worker archive is invalid")
        worker_manifest = json.loads(archive.read("worker_sources_manifest.json"))
        worker_hashes = worker_manifest["files"]
        if set(worker_names) != set(worker_hashes) | {"worker_sources_manifest.json"}:
            raise ValueError("worker member set is invalid")
        worker_root = Path("/content/gurumoji_pilot_worker")
        for relative, expected_hash in worker_hashes.items():
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
                raise ValueError("unsafe worker path")
            content = archive.read(relative)
            if digest(content) != expected_hash:
                raise ValueError("worker source hash mismatch")
            target = worker_root.joinpath(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    sys.path.insert(0, str(worker_root / "src"))
    from gurumoji.knowledge_builder import colab_qwen3, colab_worker, transport

    with zipfile.ZipFile(BytesIO(bundle["request.zip"])) as archive:
        handoff = json.loads(archive.read("handoff.json"))
        request = json.loads(archive.read("request.json"))
    job = handoff["job"]
    if (job["job_id"] != EXPECTED_JOB_ID or job["generation"] != 1
            or job["model_id"] != colab_qwen3.MODEL_REFERENCE
            or manifest["model_reference"] != colab_qwen3.MODEL_REFERENCE
            or request["task"]["worker_source_hashes"] != worker_hashes):
        raise ValueError("job identity, model, or worker code differs from the pinned request")
    deadline = datetime.fromisoformat(job["deadline"].replace("Z", "+00:00"))
    registry = json.loads(bundle["approved_sources.json"])
    sources = {record["source_id"]: record for record in registry["sources"]}
    if len(sources) != 1 or registry["schema_version"] != 1:
        raise ValueError("approved Source registry is invalid")
    transport._validate_source_excerpt_request(job, request)
    if datetime.now(timezone.utc) >= deadline:
        raise TimeoutError("job deadline expired")
    save_status(status="installing_model_dependencies", gpu=gpu)
    install_model_dependencies(deadline)
    save_status(status="running_model", gpu=gpu, model_reference=job["model_id"])
    generate = colab_qwen3.create_generator(
        job=job, approved_sources=sources,
        expert_definition=request["task"]["expert_context"]["definition"],
    )
    def observed_generate(task, excerpts):
        try:
            generated = generate(task, excerpts)
        except Exception as exc:
            Path("/content/gurumoji_batch_generator_error_b20260927t201116-05.json").write_text(
                json.dumps({"error_type": type(exc).__name__, "error": str(exc)[:1000],
                            "cause": repr(exc.__cause__)[:1000]}, sort_keys=True),
                encoding="utf-8")
            raise
        Path("/content/gurumoji_batch_generated_b20260927t201116-05.json").write_text(
            json.dumps(generated, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return generated
    result = colab_worker.run_colab_worker(
        bundle["request.zip"], approved_sources=sources, generate=observed_generate,
    )
    RESULT.write_bytes(result)
    save_status(status="candidate_ready", gpu=gpu, result_sha256=digest(result),
                result_size_bytes=len(result), model_reference=job["model_id"])
    print(json.dumps({"status": "candidate_ready", "job_id": EXPECTED_JOB_ID,
                      "result_sha256": digest(result), "gpu": gpu}, sort_keys=True))


try:
    main()
except Exception as exc:
    save_status(status="failed", error_type=type(exc).__name__, error=str(exc)[:1000])
    traceback.print_exc()
    raise
