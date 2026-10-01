"""Add a bounded Drive-backed scheduler to the P0 Colab notebook.

The monitor polls for immutable one-excerpt jobs every five minutes, processes
them on an assigned A100, checks runtime status hourly, and verifies pinned
Drive artifacts every 80 minutes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "output" / "knowledge-p0-colab-roundtrip"
MONITOR_MARKER = "# Gurumoji A100 runtime scheduler"
PINNED_WORKER_PATHS = (
    "src/gurumoji/__init__.py",
    "src/gurumoji/knowledge_builder/__init__.py",
    "src/gurumoji/knowledge_builder/contracts.py",
    "src/gurumoji/knowledge_builder/job_store.py",
    "src/gurumoji/knowledge_builder/transport.py",
    "src/gurumoji/knowledge_builder/colab_worker.py",
    "src/gurumoji/knowledge_builder/colab_qwen3.py",
)
MAX_JOB_ATTEMPTS = 3
MAX_JOB_ATTEMPT_SECONDS = 55 * 60


MONITOR_SOURCE = r'''# Gurumoji A100 runtime scheduler
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
import types
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath

import google.auth
from google.colab import auth as colab_auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

DRIVE_FOLDER_ID = @DRIVE_FOLDER_ID_JSON@
EXPECTED_BUNDLE_FILE_ID = @BUNDLE_FILE_ID_JSON@
EXPECTED_BUNDLE_NAME = @BUNDLE_NAME_JSON@
EXPECTED_BUNDLE_SHA256 = @BUNDLE_SHA256_JSON@
EXPECTED_BUNDLE_SIZE = @BUNDLE_SIZE@
EXPECTED_JOB_ID = @JOB_ID_JSON@
EXPECTED_GENERATION = @GENERATION@
EXPECTED_WORKER_SOURCE_HASHES = @WORKER_SOURCE_HASHES_JSON@
STATUS_INTERVAL_SECONDS = 60 * 60
QUEUE_POLL_INTERVAL_SECONDS = 5 * 60
DRIVE_AUDIT_INTERVAL_SECONDS = 80 * 60
MAX_MONITOR_HOURS = 24
MONITOR_FILE_NAME = f"Gurumoji_A100_Runtime_Monitor_{EXPECTED_JOB_ID}_g{EXPECTED_GENERATION}.json"
RESULT_FILE_NAME = f"Gurumoji_P0_Result_{EXPECTED_JOB_ID}_g{EXPECTED_GENERATION}.zip"
MAX_QUEUE_FILES_PER_POLL = 100
MAX_JOB_ATTEMPTS = 3
MAX_TRACKED_ARTIFACTS = 1000
MAX_JOB_ATTEMPT_SECONDS = 55 * 60

colab_auth.authenticate_user()
credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
drive_api = build("drive", "v3", credentials=credentials, cache_discovery=False)
monitor_credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
monitor_drive_api = build("drive", "v3", credentials=monitor_credentials, cache_discovery=False)
runtime_user = drive_api.about().get(fields="user(emailAddress)").execute(num_retries=3).get("user", {})
runtime_user_email = runtime_user.get("emailAddress")
if not isinstance(runtime_user_email, str) or "@" not in runtime_user_email:
    raise RuntimeError("Could not identify the Drive account authorized for Colab Job uploads")

def drive_list_folder(api=None):
    api = api or drive_api
    files = []
    page_token = None
    while True:
        response = api.files().list(
            q=f"'{DRIVE_FOLDER_ID}' in parents and trashed = false",
            pageSize=1000,
            pageToken=page_token,
            fields="nextPageToken,files(id,name,size,md5Checksum,mimeType,parents,modifiedTime,headRevisionId,owners(emailAddress),createdByMeTime,lastModifyingUser(emailAddress))",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute(num_retries=3)
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files

def drive_read(file_id, api=None):
    api = api or drive_api
    return api.files().get_media(fileId=file_id, supportsAllDrives=True).execute(num_retries=3)

def drive_file_metadata(file_id, api=None):
    api = api or drive_api
    return api.files().get(
        fileId=file_id,
        fields="id,name,size,modifiedTime,headRevisionId,owners(emailAddress),createdByMeTime,lastModifyingUser(emailAddress)",
        supportsAllDrives=True,
    ).execute(num_retries=3)

def _job_file_revision(metadata):
    owners = metadata.get("owners", [])
    owner_emails = tuple(sorted(
        item.get("emailAddress", "").casefold() for item in owners
        if isinstance(item, dict) and isinstance(item.get("emailAddress"), str)
    )) if isinstance(owners, list) else ()
    modifier = (metadata.get("lastModifyingUser") or {}).get("emailAddress")
    return (metadata.get("id"), metadata.get("name"), metadata.get("size"),
            metadata.get("modifiedTime"), metadata.get("headRevisionId"),
            owner_emails, metadata.get("createdByMeTime"), modifier)

def _read_stable_job_bundle(file_value):
    before = drive_file_metadata(file_value["id"])
    if (_job_file_revision(before) != _job_file_revision(file_value) or
            not _uploaded_by_runtime_user(before)):
        raise RuntimeError("Drive Job bundle changed or failed the uploader gate before download")
    content = drive_read(file_value["id"])
    after = drive_file_metadata(file_value["id"])
    if (_job_file_revision(before) != _job_file_revision(after) or
            not _uploaded_by_runtime_user(after)):
        raise RuntimeError("Drive Job bundle changed or failed the uploader gate during download")
    if len(content) != int(after.get("size", -1)):
        raise RuntimeError("Drive Job bundle size does not match its stable Drive revision")
    return content

def drive_upload_or_reuse(name, content, mime_type):
    digest = hashlib.sha256(content).hexdigest()
    matches = [item for item in drive_list_folder() if item["name"] == name]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple Drive files have the reserved name {name!r}")
    if matches:
        existing = matches[0]
        existing_bytes = drive_read(existing["id"])
        if name == RESULT_FILE_NAME:
            archive, members = transport._read_safe_zip(existing_bytes)
            try:
                remote = transport._parse_canonical_json(
                    transport._zip_read(archive, members, transport._RESULT_MANIFEST))
                result_job = remote["job"]
                commit = remote["commit"]
                if (remote.get("kind") != "colab_result" or
                        result_job.get("job_id") != EXPECTED_JOB_ID or
                        result_job.get("generation") != EXPECTED_GENERATION or
                        result_job.get("input_manifest_sha256") != job["input_manifest_sha256"] or
                        commit.get("job_id") != EXPECTED_JOB_ID or
                        commit.get("generation") != EXPECTED_GENERATION):
                    raise RuntimeError("Existing Drive result belongs to a different job generation")
            finally:
                archive.close()
        existing_sha256 = hashlib.sha256(existing_bytes).hexdigest()
        if name == RESULT_FILE_NAME and existing_sha256 != digest:
            prior_monitors = [item for item in drive_list_folder()
                              if item["name"] == MONITOR_FILE_NAME]
            if len(prior_monitors) != 1:
                raise RuntimeError("Existing Drive result differs from this run and has no unique integrity pin")
            prior_monitor = json.loads(drive_read(prior_monitors[0]["id"]).decode("utf-8"))
            if (prior_monitor.get("schema_version") != 1 or
                    prior_monitor.get("job_id") != EXPECTED_JOB_ID or
                    prior_monitor.get("generation") != EXPECTED_GENERATION):
                raise RuntimeError("Existing Drive result integrity pin belongs to another job generation")
            prior_result_pins = [item for item in prior_monitor.get("tracked_artifacts", [])
                                 if item.get("id") == existing["id"] and
                                 item.get("name") == RESULT_FILE_NAME]
            if (len(prior_result_pins) != 1 or
                    prior_result_pins[0].get("sha256") != existing_sha256 or
                    prior_result_pins[0].get("size_bytes") != len(existing_bytes)):
                raise RuntimeError("Existing Drive result differs from its persisted integrity pin")
            return existing, existing_bytes
        if existing_sha256 != digest:
            raise RuntimeError(f"Refusing to overwrite a different existing artifact: {name}")
        return existing, existing_bytes
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type, resumable=True)
    created = drive_api.files().create(
        body={"name": name, "mimeType": mime_type, "parents": [DRIVE_FOLDER_ID]},
        media_body=media,
        fields="id,name,size,md5Checksum,mimeType,parents,modifiedTime",
        supportsAllDrives=True,
    ).execute(num_retries=3)
    return created, content

def _job_result_binding(result_bytes, expected_job, request_payload, request_data):
    archive, members = transport._read_safe_zip(result_bytes)
    try:
        if transport._RESULT_MANIFEST not in members or transport._REQUEST_FILE not in members:
            raise RuntimeError("Colab result ZIP is incomplete")
        result = transport._parse_canonical_json(
            transport._zip_read(archive, members, transport._RESULT_MANIFEST))
        result = transport.contracts._object(
            result, {"schema_version", "kind", "job", "commit"}, name="Colab result envelope")
        if result["schema_version"] != 1 or result["kind"] != "colab_result":
            raise RuntimeError("Colab result envelope version or kind is invalid")
        embedded_request = transport._zip_read(archive, members, transport._REQUEST_FILE)
        if embedded_request != request_data:
            raise RuntimeError("Colab result does not contain the exact Job request")
        remote_job = transport.contracts._object(result["job"], {
            "job_id", "generation", "attempt_id", "directive_sha256", "input_manifest_sha256",
            "model_route", "deadline",
        }, name="Colab result Job binding")
        binding_fields = ("job_id", "generation", "attempt_id", "directive_sha256",
                          "input_manifest_sha256", "model_route", "deadline")
        if any(remote_job[field] != expected_job[field] for field in binding_fields):
            raise RuntimeError("Colab result does not match the pinned Job generation and directive")
        if hashlib.sha256(request_data).hexdigest() != expected_job["input_manifest_sha256"]:
            raise RuntimeError("Job request does not match its pinned input hash")
        commit = transport.contracts.validate_commit(result["commit"])
        if any(commit[field] != expected_job[local_field] for field, local_field in (
                ("job_id", "job_id"), ("generation", "generation"),
                ("attempt_id", "attempt_id"), ("directive_sha256", "directive_sha256"))):
            raise RuntimeError("Colab Commit does not match the pinned Job directive")
        commit_created = datetime.fromisoformat(commit["created_at"].replace("Z", "+00:00"))
        job_created = datetime.fromisoformat(expected_job["created_at"].replace("Z", "+00:00"))
        job_deadline = datetime.fromisoformat(expected_job["deadline"].replace("Z", "+00:00"))
        if not job_created <= commit_created <= job_deadline:
            raise RuntimeError("Colab Commit was not created within the Job deadline")
        expected_members = {transport._RESULT_MANIFEST, transport._REQUEST_FILE,
                            *(transport._RESULT_PREFIX + item["path"] for item in commit["artifacts"])}
        if set(members) != expected_members:
            raise RuntimeError("Colab result ZIP member set does not match the Commit")
        artifacts = {}
        for item in commit["artifacts"]:
            path = item["path"]
            artifacts[path] = transport._zip_read(archive, members, transport._RESULT_PREFIX + path)
        sources, permitted = transport._validate_source_excerpt_request(expected_job, request_payload)
        transport._validate_artifact_bytes(expected_job, commit, artifacts, sources,
                                           permitted, request_payload["task"]["expert_id"])
        return result
    finally:
        archive.close()

def _job_bundle_content(bundle_bytes, expected_name):
    if not isinstance(bundle_bytes, bytes) or len(bundle_bytes) > transport.MAX_TOTAL_BYTES:
        raise RuntimeError("Job bundle is missing or exceeds the transfer limit")
    archive, members = transport._read_safe_zip(bundle_bytes)
    try:
        required = {"request.zip", "approved_sources.json", "worker_sources.zip", "bundle_manifest.json"}
        if set(members) != required:
            raise RuntimeError("Job bundle member set is invalid")
        manifest = transport._parse_canonical_json(
            transport._zip_read(archive, members, "bundle_manifest.json"))
        if (set(manifest) != {"schema_version", "kind", "job_id", "generation", "model_reference", "files"} or
                manifest["schema_version"] != 1 or manifest["kind"] != "gurumoji_colab_job_bundle" or
                not isinstance(manifest["files"], dict)):
            raise RuntimeError("Job bundle manifest is invalid")
        job_id = manifest["job_id"]
        generation = manifest["generation"]
        expected_pattern = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", job_id or "")
        if (expected_pattern is None or type(generation) is not int or generation < 1 or
                expected_name != f"Gurumoji_Job_{job_id}_g{generation}.zip"):
            raise RuntimeError("Drive filename does not match the pinned Job ID and generation")
        file_bytes = {name: transport._zip_read(archive, members, name)
                      for name in ("request.zip", "approved_sources.json", "worker_sources.zip")}
        if set(manifest["files"]) != set(file_bytes):
            raise RuntimeError("Job bundle file manifest is invalid")
        for name, content in file_bytes.items():
            if hashlib.sha256(content).hexdigest() != manifest["files"][name]:
                raise RuntimeError("Job bundle SHA-256 mismatch")
        if manifest["model_reference"] != "Qwen/Qwen3-32B-AWQ@0499c3ac83fdef8810b907a23894ba91e95eddd8":
            raise RuntimeError("Job bundle model revision is not the pinned A100 model")
        return manifest, file_bytes
    finally:
        archive.close()

def _import_pinned_worker(worker_zip_bytes, expected_hashes):
    if expected_hashes != EXPECTED_WORKER_SOURCE_HASHES:
        raise RuntimeError("Job requests worker source hashes not pinned by this notebook")
    archive, members = transport._read_safe_zip(worker_zip_bytes)
    try:
        if "worker_sources_manifest.json" not in members:
            raise RuntimeError("Pinned worker source manifest is missing")
        manifest = transport._parse_canonical_json(
            transport._zip_read(archive, members, "worker_sources_manifest.json"))
        expected_paths = set(EXPECTED_WORKER_SOURCE_HASHES)
        if (set(manifest) != {"schema_version", "files"} or manifest["schema_version"] != 1 or
                set(manifest["files"]) != expected_paths or set(members) != expected_paths | {"worker_sources_manifest.json"} or
                manifest["files"] != EXPECTED_WORKER_SOURCE_HASHES):
            raise RuntimeError("worker source files do not match the immutable Job task hashes")
        files = {name: transport._zip_read(archive, members, name) for name in sorted(expected_paths)}
    finally:
        archive.close()
    digest = hashlib.sha256(transport.contracts.canonical_json(expected_hashes)).hexdigest()
    worker_root = Path("/content") / ("gurumoji_colab_worker_" + digest)
    for relative, content in files.items():
        member = PurePosixPath(relative)
        if member.is_absolute() or ".." in member.parts or "\\" in relative:
            raise RuntimeError("worker source path is unsafe")
        destination = worker_root.joinpath(*member.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.is_symlink() or hashlib.sha256(destination.read_bytes()).hexdigest() != expected_hashes[relative]:
                raise RuntimeError("cached worker source differs from its pinned hash")
        else:
            destination.write_bytes(content)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != expected_hashes[relative]:
            raise RuntimeError("worker source failed its pinned hash check")

    alias = "gurumoji_worker_" + digest[:20]
    if alias not in sys.modules:
        root_package = types.ModuleType(alias)
        root_package.__path__ = [str(worker_root / "src" / "gurumoji")]
        root_package.__package__ = alias
        root_package.__file__ = str(worker_root / "src" / "gurumoji" / "__init__.py")
        sys.modules[alias] = root_package
        builder_name = alias + ".knowledge_builder"
        builder_package = types.ModuleType(builder_name)
        builder_package.__path__ = [str(worker_root / "src" / "gurumoji" / "knowledge_builder")]
        builder_package.__package__ = builder_name
        builder_package.__file__ = str(worker_root / "src" / "gurumoji" / "knowledge_builder" / "__init__.py")
        sys.modules[builder_name] = builder_package
        importlib.import_module(builder_name + ".contracts")
        importlib.import_module(builder_name + ".transport")
        importlib.import_module(builder_name + ".colab_worker")
        importlib.import_module(builder_name + ".colab_qwen3")
    builder_name = alias + ".knowledge_builder"
    return (sys.modules[builder_name + ".transport"],
            sys.modules[builder_name + ".colab_worker"],
            sys.modules[builder_name + ".colab_qwen3"])

def _upload_job_result(name, result_bytes, job, request_payload, request_data):
    matches = [item for item in drive_list_folder() if item["name"] == name]
    if len(matches) > 1:
        raise RuntimeError("Multiple Drive result files have the reserved Job name")
    if matches:
        existing = matches[0]
        existing_bytes = drive_read(existing["id"])
        _job_result_binding(existing_bytes, job, request_payload, request_data)
        if hashlib.sha256(existing_bytes).hexdigest() != hashlib.sha256(result_bytes).hexdigest():
            raise RuntimeError("A different result already exists for this Job generation")
        return existing, existing_bytes
    media = MediaIoBaseUpload(BytesIO(result_bytes), mimetype="application/zip", resumable=True)
    created = drive_api.files().create(
        body={"name": name, "mimeType": "application/zip", "parents": [DRIVE_FOLDER_ID]},
        media_body=media,
        fields="id,name,size,md5Checksum,mimeType,parents,modifiedTime",
        supportsAllDrives=True,
    ).execute(num_retries=3)
    return created, result_bytes

def _ensure_qwen_transformers(job):
    deadline = datetime.fromisoformat(job["deadline"].replace("Z", "+00:00"))
    seconds_left = (deadline - datetime.now(timezone.utc)).total_seconds()
    if seconds_left <= 0:
        raise RuntimeError("Job deadline expired before model dependency setup")
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(max(5, min(90, int(seconds_left))))
    os.environ["HF_HUB_ETAG_TIMEOUT"] = str(max(5, min(20, int(seconds_left))))
    def install_with_deadline(arguments):
        seconds_left = (deadline - datetime.now(timezone.utc)).total_seconds()
        if seconds_left <= 0:
            raise RuntimeError("Job deadline expired during model dependency setup")
        subprocess.run(arguments, check=True, timeout=max(1, min(600, int(seconds_left))))

    try:
        awq_installed = importlib.util.find_spec("awq") is not None
    except (ImportError, ValueError):
        awq_installed = False
    if not awq_installed:
        install_with_deadline([
            sys.executable, "-m", "pip", "install", "autoawq==0.2.9",
        ])
        importlib.invalidate_caches()
    try:
        transformers = importlib.import_module("transformers")
    except ImportError:
        transformers = None
    version = getattr(transformers, "__version__", "0") if transformers is not None else "0"
    version_parts = tuple(int(part) for part in re.findall(r"\d+", version)[:3])
    if version_parts < (4, 51, 0) or version_parts >= (5, 0, 0):
        install_with_deadline([
            sys.executable, "-m", "pip", "install", "transformers>=4.51.0,<5",
        ])
        importlib.invalidate_caches()
        sys.modules.pop("transformers", None)
        transformers = importlib.import_module("transformers")
        version = getattr(transformers, "__version__", "0")
        version_parts = tuple(int(part) for part in re.findall(r"\d+", version)[:3])
    if version_parts < (4, 51, 0) or version_parts >= (5, 0, 0):
        raise RuntimeError("Transformers >=4.51 and <5 is required for the pinned Qwen3 worker")

def _pin_tracked_artifact(file_value, content):
    pin = {"id": file_value["id"], "name": file_value["name"],
           "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    with tracked_artifacts_lock:
        existing = [item for item in tracked_artifacts if item["id"] == pin["id"]]
        if existing and existing[0] != pin:
            raise RuntimeError("A tracked Drive artifact changed after it was pinned")
        if not existing:
            if len(tracked_artifacts) >= MAX_TRACKED_ARTIFACTS:
                raise RuntimeError("Tracked Drive artifact limit reached")
            tracked_artifacts.append(pin)

def process_job_bundle(file_value):
    bundle_bytes = _read_stable_job_bundle(file_value)
    manifest, bundle = _job_bundle_content(bundle_bytes, file_value["name"])
    job_archive, job_members = transport._read_safe_zip(bundle["request.zip"])
    try:
        handoff = transport._parse_canonical_json(
            transport._zip_read(job_archive, job_members, transport._HANDOFF_MANIFEST))
        request_data = transport._zip_read(job_archive, job_members, transport._REQUEST_FILE)
        request_payload = transport._parse_canonical_json(request_data, max_bytes=transport.MAX_REQUEST_BYTES)
    finally:
        job_archive.close()
    job = handoff["job"]
    if (job["job_id"] != manifest["job_id"] or job["generation"] != manifest["generation"] or
            hashlib.sha256(request_data).hexdigest() != job["input_manifest_sha256"]):
        raise RuntimeError("request does not match the pinned Job bundle manifest")
    result_name = f"Gurumoji_Result_{job['job_id']}_g{job['generation']}.zip"
    existing_results = [item for item in drive_list_folder() if item["name"] == result_name]
    if len(existing_results) > 1:
        raise RuntimeError("Multiple Drive results exist for this Job generation")
    if existing_results:
        saved_result = drive_read(existing_results[0]["id"])
        _job_result_binding(saved_result, job, request_payload, request_data)
        _pin_tracked_artifact(file_value, bundle_bytes)
        _pin_tracked_artifact(existing_results[0], saved_result)
        return {"job_id": job["job_id"], "generation": job["generation"],
                "result_file_id": existing_results[0]["id"],
                "result_sha256": hashlib.sha256(saved_result).hexdigest(),
                "status": "result_already_saved_to_drive"}
    if not transport._deadline_active(job):
        return {"job_id": job["job_id"], "generation": job["generation"], "status": "expired_before_start"}
    task = request_payload["task"]
    if "worker_source_hashes" not in task or "expert_context" not in task:
        raise RuntimeError("production Job lacks pinned expert and worker context")
    if task["worker_source_hashes"] != EXPECTED_WORKER_SOURCE_HASHES:
        raise RuntimeError("production Job does not use this Notebook's pinned worker source")
    registry_value = transport._parse_canonical_json(bundle["approved_sources.json"])
    if (set(registry_value) != {"schema_version", "sources"} or registry_value["schema_version"] != 1 or
            not isinstance(registry_value["sources"], list)):
        raise RuntimeError("Job approved Source registry is invalid")
    approved_sources = {source["source_id"]: source for source in registry_value["sources"]}
    if len(approved_sources) != len(registry_value["sources"]):
        raise RuntimeError("Job approved Source registry has duplicate IDs")
    job_transport, job_worker, qwen3 = _import_pinned_worker(bundle["worker_sources.zip"],
                                                             task["worker_source_hashes"])
    if (job["model_id"] != qwen3.MODEL_REFERENCE or job["prompt_version"] != qwen3.PROMPT_VERSION or
            job["compiler_version"] != qwen3.COMPILER_VERSION):
        raise RuntimeError("Job directive differs from the pinned Colab Qwen3 adapter")
    if not job_transport._deadline_active(job):
        return {"job_id": job["job_id"], "generation": job["generation"],
                "status": "expired_before_model_setup"}
    _ensure_qwen_transformers(job)
    if not job_transport._deadline_active(job):
        return {"job_id": job["job_id"], "generation": job["generation"],
                "status": "expired_before_model_load"}
    expected_task = qwen3.build_task_descriptor(task["expert_context"]["definition"])
    if expected_task != task:
        raise RuntimeError("Job task differs from the hash-pinned expert definition or worker code")
    generate = qwen3.create_generator(job=job, approved_sources=approved_sources,
                                      expert_definition=task["expert_context"]["definition"])
    result_bytes = job_worker.run_colab_worker(
        bundle["request.zip"], approved_sources=approved_sources, generate=generate)
    _job_result_binding(result_bytes, job, request_payload, request_data)
    result_drive_file, saved_result = _upload_job_result(result_name, result_bytes, job,
                                                         request_payload, request_data)
    _pin_tracked_artifact(file_value, bundle_bytes)
    _pin_tracked_artifact(result_drive_file, saved_result)
    return {"job_id": job["job_id"], "generation": job["generation"],
            "result_file_id": result_drive_file["id"],
            "result_sha256": hashlib.sha256(saved_result).hexdigest(),
            "status": "untrusted_result_saved_to_drive"}

# The synthetic P0 result is written to Drive once. It remains untrusted until
# the local acceptance script validates it and advances the local generation.
result_drive_file, saved_result_zip = drive_upload_or_reuse(
    RESULT_FILE_NAME, result_zip, "application/zip")
result_zip = saved_result_zip
result_sha256 = sha256(result_zip)
tracked_artifacts = [
    {
        "id": EXPECTED_BUNDLE_FILE_ID,
        "name": EXPECTED_BUNDLE_NAME,
        "size_bytes": EXPECTED_BUNDLE_SIZE,
        "sha256": EXPECTED_BUNDLE_SHA256,
    },
    {
        "id": result_drive_file["id"],
        "name": RESULT_FILE_NAME,
        "size_bytes": len(result_zip),
        "sha256": result_sha256,
    },
]
tracked_artifacts_lock = threading.RLock()
processed_jobs = {}

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def a100_health_probe(gpu):
    if not torch.cuda.is_available() or "A100" not in gpu.upper():
        return {"status": "skipped", "reason": "a100_not_available"}
    try:
        left = torch.ones((256, 256), device="cuda", dtype=torch.float16)
        right = torch.ones((256, 256), device="cuda", dtype=torch.float16)
        product = left @ right
        torch.cuda.synchronize()
        result = float(product[0, 0].item())
        del left, right, product
    except Exception as exc:
        return {"status": "failed", "error_type": type(exc).__name__}
    if result != 256.0:
        return {"status": "failed", "operation": "256x256_fp16_matmul", "result": result}
    return {"status": "passed", "operation": "256x256_fp16_matmul", "result": result}

def runtime_status(files, *, model_job_running=False):
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
    if torch.cuda.is_available():
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        gpu_memory = {"free_mib": round(free_bytes / (1024 * 1024)),
                      "total_mib": round(total_bytes / (1024 * 1024))}
    else:
        gpu_memory = None
    queued = sorted(
        item["name"] for item in files
        if item["name"].startswith("Gurumoji_Job_") and item["name"].endswith(".zip")
    )
    gpu_health_probe = ({"status": "skipped", "reason": "model_job_running"}
                        if model_job_running else a100_health_probe(gpu))
    return {
        "checked_at": utc_now(),
        "event": "hourly_runtime_and_queue_check",
        "gpu": gpu,
        "is_a100": "A100" in gpu.upper(),
        "gpu_memory": gpu_memory,
        "queued_job_bundles": queued,
        "queue_action": "no_job_waiting" if not queued else "five_minute_worker_poll_on_a100",
        "gpu_health_probe": gpu_health_probe,
        "gpu_work": ("pinned_qwen3_model_job_running" if model_job_running else
                     "a100_health_probe_when_no_job_is_running" if gpu_health_probe["status"] != "skipped" else
                     "none_no_a100_assignment"),
    }

def _uploaded_by_runtime_user(file_value):
    owners = file_value.get("owners", [])
    owned_by_runtime_user = (isinstance(owners, list) and any(
        isinstance(owner, dict) and isinstance(owner.get("emailAddress"), str) and
        owner["emailAddress"].casefold() == runtime_user_email.casefold()
        for owner in owners))
    created_by_runtime_user = bool(file_value.get("createdByMeTime"))
    modifier = (file_value.get("lastModifyingUser") or {}).get("emailAddress")
    return ((owned_by_runtime_user or created_by_runtime_user) and
            isinstance(modifier, str) and modifier.casefold() == runtime_user_email.casefold())

def audit_drive_artifacts():
    audit_credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive"])
    audit_drive_api = build("drive", "v3", credentials=audit_credentials, cache_discovery=False)
    files_by_id = {item["id"]: item for item in drive_list_folder(api=audit_drive_api)}
    checked = []
    with tracked_artifacts_lock:
        pins = list(tracked_artifacts)
    for expected in pins:
        item = files_by_id.get(expected["id"])
        if item is None:
            raise RuntimeError(f"Expected Drive artifact is missing: {expected['name']}")
        if item["name"] != expected["name"]:
            raise RuntimeError(f"Drive artifact name changed: {expected['id']}")
        if DRIVE_FOLDER_ID not in item.get("parents", []):
            raise RuntimeError(f"Drive artifact moved out of the configured folder: {expected['name']}")
        content = drive_read(expected["id"], api=audit_drive_api)
        actual_size = len(content)
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_size != expected["size_bytes"] or actual_sha256 != expected["sha256"]:
            raise RuntimeError(f"Drive artifact verification failed: {expected['name']}")
        checked.append({"id": expected["id"], "name": expected["name"],
                        "size_bytes": actual_size, "sha256": actual_sha256})
    return {"checked_at": utc_now(), "event": "80_minute_drive_artifact_audit",
            "status": "verified", "artifacts": checked}

def save_monitor_state(events):
    global monitor_drive_file_id
    with tracked_artifacts_lock:
        artifact_snapshot = list(tracked_artifacts)
    payload = json.dumps({
        "schema_version": 1,
        "job_id": EXPECTED_JOB_ID,
        "generation": EXPECTED_GENERATION,
        "session_started_at": monitor_started_at,
        "monitor_interval_minutes": 60,
        "drive_audit_interval_minutes": 80,
        "queue_poll_interval_minutes": 5,
        "max_monitor_hours": MAX_MONITOR_HOURS,
        "tracked_artifacts": artifact_snapshot,
        "processed_jobs": processed_jobs,
        "events": events[-100:],
    }, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(BytesIO(payload), mimetype="application/json", resumable=True)
    if monitor_drive_file_id is None:
        response = monitor_drive_api.files().create(
            body={"name": MONITOR_FILE_NAME, "mimeType": "application/json",
                  "parents": [DRIVE_FOLDER_ID]},
            media_body=media,
            fields="id,name,size,parents,modifiedTime",
            supportsAllDrives=True,
        ).execute(num_retries=3)
        monitor_drive_file_id = response["id"]
    else:
        response = monitor_drive_api.files().update(
            fileId=monitor_drive_file_id,
            media_body=media,
            fields="id,name,size,parents,modifiedTime",
            supportsAllDrives=True,
        ).execute(num_retries=3)
    if DRIVE_FOLDER_ID not in response.get("parents", [DRIVE_FOLDER_ID]):
        raise RuntimeError("Runtime monitor file was not saved in the configured Drive folder")

monitor_drive_file_id = None
events = []
existing_monitors = [item for item in drive_list_folder(api=monitor_drive_api) if item["name"] == MONITOR_FILE_NAME]
if len(existing_monitors) > 1:
    raise RuntimeError("Multiple runtime monitor files exist in the configured Drive folder")
if existing_monitors:
    previous = json.loads(drive_read(existing_monitors[0]["id"], api=monitor_drive_api).decode("utf-8"))
    if (previous.get("schema_version") != 1 or
            previous.get("job_id") != EXPECTED_JOB_ID or
            previous.get("generation") != EXPECTED_GENERATION):
        raise RuntimeError("Refusing to resume an unrelated Drive monitor file")
    prior_events = previous.get("events", [])
    if not isinstance(prior_events, list) or any(not isinstance(item, dict) for item in prior_events):
        raise RuntimeError("Existing Drive monitor history has an invalid shape")
    events.extend(prior_events[-100:])
    prior_pins = previous.get("tracked_artifacts", [])
    if not isinstance(prior_pins, list) or len(prior_pins) > MAX_TRACKED_ARTIFACTS:
        raise RuntimeError("Existing Drive artifact pins have an invalid shape")
    for pin in prior_pins:
        if (not isinstance(pin, dict) or set(pin) != {"id", "name", "size_bytes", "sha256"} or
                not isinstance(pin["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", pin["id"]) or
                not isinstance(pin["name"], str) or len(pin["name"]) > 500 or
                type(pin["size_bytes"]) is not int or pin["size_bytes"] < 0 or
                not isinstance(pin["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])):
            raise RuntimeError("Existing Drive artifact pin is invalid")
        known = [item for item in tracked_artifacts if item["id"] == pin["id"]]
        if known and known[0] != pin:
            raise RuntimeError("Existing Drive artifact pin conflicts with the current P0 pins")
        if not known:
            tracked_artifacts.append(pin)
    prior_jobs = previous.get("processed_jobs", {})
    if not isinstance(prior_jobs, dict) or len(prior_jobs) > MAX_TRACKED_ARTIFACTS:
        raise RuntimeError("Existing processed Job state has an invalid shape")
    for key, state in prior_jobs.items():
        if (not isinstance(key, str) or len(key) > 256 or not isinstance(state, dict) or
                set(state) != {"status", "attempts", "bundle_id", "updated_at"} or
                state["status"] not in {"saved", "expired", "failed", "running", "rejected"} or
                type(state["attempts"]) is not int or not 0 <= state["attempts"] <= 3 or
                not isinstance(state["bundle_id"], str) or len(state["bundle_id"]) > 256 or
                not isinstance(state["updated_at"], str) or len(state["updated_at"]) > 64):
            raise RuntimeError("Existing processed Job state is invalid")
        processed_jobs[key] = state
    monitor_drive_file_id = existing_monitors[0]["id"]
monitor_started_at = utc_now()
monitor_started = time.monotonic()
stop_at = monitor_started + MAX_MONITOR_HOURS * 60 * 60
next_status = monitor_started
next_drive_audit = monitor_started
next_queue_poll = monitor_started
print(f"Monitor started at {monitor_started_at}; 60-minute status checks, "
      f"5-minute Job polling, 80-minute Drive hash audits, "
      f"maximum {MAX_MONITOR_HOURS} hours. Existing monitor history: {len(events)} events.")
print(f"P0 result saved to Drive: {result_drive_file['id']} ({result_sha256})")

worker_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gurumoji-a100-job")
audit_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gurumoji-drive-audit")
active_future = None
active_job = None
audit_future = None
try:
    while time.monotonic() < stop_at:
        now = time.monotonic()
        files = None
        if now >= min(next_status, next_queue_poll):
            files = drive_list_folder(api=monitor_drive_api)

        if active_future is not None and active_future.done():
            job_key = active_job["job_key"]
            try:
                outcome = active_future.result()
                state_status = ("saved" if outcome["status"] in
                                {"untrusted_result_saved_to_drive", "result_already_saved_to_drive"}
                                else "expired" if outcome["status"] in {
                                    "expired_before_start", "expired_before_model_setup",
                                    "expired_before_model_load",
                                } else "failed")
                attempts = active_job["attempts"] + (0 if state_status in {"saved", "expired"} else 1)
                processed_jobs[job_key] = {"status": state_status, "attempts": attempts,
                                           "bundle_id": active_job["bundle_id"], "updated_at": utc_now()}
                events.append({"checked_at": utc_now(), "event": "job_finished", **outcome})
                print("JOB_FINISHED=" + json.dumps(outcome, ensure_ascii=False, sort_keys=True))
            except Exception as exc:
                attempts = active_job["attempts"] + 1
                processed_jobs[job_key] = {"status": "failed", "attempts": attempts,
                                           "bundle_id": active_job["bundle_id"], "updated_at": utc_now()}
                error = {"job_id": active_job["job_id"], "generation": active_job["generation"],
                         "attempt": attempts, "status": "failed", "error_type": type(exc).__name__}
                events.append({"checked_at": utc_now(), "event": "job_failed", **error})
                print("JOB_ERROR=" + json.dumps(error, ensure_ascii=False, sort_keys=True))
            active_future = None
            active_job = None
            save_monitor_state(events)

        if audit_future is not None and audit_future.done():
            try:
                audit = audit_future.result()
                events.append(audit)
                print("DRIVE_AUDIT=" + json.dumps(audit, ensure_ascii=False, sort_keys=True))
            except Exception as exc:
                audit_error = {"checked_at": utc_now(), "event": "80_minute_drive_artifact_audit",
                               "status": "failed", "error_type": type(exc).__name__}
                events.append(audit_error)
                print("DRIVE_AUDIT_ERROR=" + json.dumps(audit_error, ensure_ascii=False, sort_keys=True))
            audit_future = None
            save_monitor_state(events)

        if now >= next_status:
            if files is None:
                files = drive_list_folder(api=monitor_drive_api)
            event = runtime_status(files, model_job_running=active_future is not None)
            events.append(event)
            print("RUNTIME_STATUS=" + json.dumps(event, ensure_ascii=False, sort_keys=True))
            while next_status <= now:
                next_status += STATUS_INTERVAL_SECONDS
        if now >= next_drive_audit:
            if audit_future is None:
                audit_future = audit_pool.submit(audit_drive_artifacts)
            else:
                events.append({"checked_at": utc_now(), "event": "80_minute_drive_artifact_audit",
                               "status": "delayed", "reason": "previous_audit_still_running"})
            while next_drive_audit <= now:
                next_drive_audit += DRIVE_AUDIT_INTERVAL_SECONDS
        if now >= next_queue_poll:
            if files is None:
                files = drive_list_folder(api=monitor_drive_api)
            gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
            is_a100 = "A100" in gpu.upper()
            queued_all = sorted(
                [item for item in files
                 if item["name"].startswith("Gurumoji_Job_") and item["name"].endswith(".zip")],
                key=lambda item: (item.get("modifiedTime", ""), item["name"], item["id"]),
            )
            queued = queued_all[:MAX_QUEUE_FILES_PER_POLL]
            name_counts = {}
            for item in queued_all:
                name_counts[item["name"]] = name_counts.get(item["name"], 0) + 1
            outcomes = []
            if active_future is not None:
                outcomes.append({"job_id": active_job["job_id"], "generation": active_job["generation"],
                                 "status": "model_job_running"})
            elif not is_a100:
                outcomes.extend({"file_id": item["id"], "status": "waiting_for_a100"} for item in queued)
            elif stop_at - now < MAX_JOB_ATTEMPT_SECONDS:
                outcomes.append({"status": "deferred_to_next_monitor_session",
                                 "reason": "24_hour_monitor_limit_near"})
            else:
                for bundle_file in queued:
                    identity = re.fullmatch(r"Gurumoji_Job_(.+)_g([1-9][0-9]*)\.zip", bundle_file["name"])
                    if (identity is None or
                            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", identity.group(1)) is None):
                        outcomes.append({"file_id": bundle_file["id"], "status": "invalid_reserved_filename"})
                        continue
                    if name_counts[bundle_file["name"]] > 1:
                        outcomes.append({"job_id": identity.group(1), "generation": int(identity.group(2)),
                                         "status": "duplicate_job_bundle_name"})
                        continue
                    job_key = identity.group(1) + ":g" + identity.group(2)
                    prior = processed_jobs.get(job_key)
                    if prior and prior["bundle_id"] != bundle_file["id"]:
                        prior = None
                        processed_jobs.pop(job_key, None)
                    if prior and prior["status"] in {"saved", "expired", "rejected"}:
                        continue
                    if prior and prior["status"] == "failed" and prior["attempts"] >= MAX_JOB_ATTEMPTS:
                        continue
                    if not _uploaded_by_runtime_user(bundle_file):
                        processed_jobs[job_key] = {"status": "rejected", "attempts": prior["attempts"] if prior else 0,
                                                   "bundle_id": bundle_file["id"], "updated_at": utc_now()}
                        outcomes.append({"job_id": identity.group(1), "generation": int(identity.group(2)),
                                         "status": "rejected_untrusted_uploader"})
                        continue
                    attempts = prior["attempts"] if prior else 0
                    processed_jobs[job_key] = {"status": "running", "attempts": attempts,
                                               "bundle_id": bundle_file["id"], "updated_at": utc_now()}
                    active_job = {"job_key": job_key, "job_id": identity.group(1),
                                  "generation": int(identity.group(2)), "attempts": attempts,
                                  "bundle_id": bundle_file["id"]}
                    active_future = worker_pool.submit(process_job_bundle, bundle_file)
                    outcomes.append({"job_id": identity.group(1), "generation": int(identity.group(2)),
                                     "status": "started_on_a100"})
                    break
            queue_event = {"checked_at": utc_now(), "event": "five_minute_job_queue_poll",
                           "gpu": gpu, "is_a100": is_a100,
                           "queued_job_count": len(queued_all),
                           "queue_scan_limited": len(queued_all) > MAX_QUEUE_FILES_PER_POLL,
                           "outcomes": outcomes}
            events.append(queue_event)
            print("JOB_QUEUE=" + json.dumps(queue_event, ensure_ascii=False, sort_keys=True))
            while next_queue_poll <= now:
                next_queue_poll += QUEUE_POLL_INTERVAL_SECONDS
        if events:
            save_monitor_state(events)
        next_check = min(next_status, next_drive_audit, next_queue_poll, stop_at)
        wait_seconds = max(1, next_check - time.monotonic())
        if active_future is not None:
            wait_seconds = min(wait_seconds, 30)
        time.sleep(wait_seconds)
except KeyboardInterrupt:
    print("Monitor stopped by user; active Job may continue in the worker thread. Latest queue state was saved to Drive.")
finally:
    save_monitor_state(events)
    worker_pool.shutdown(wait=False, cancel_futures=True)
    audit_pool.shutdown(wait=False, cancel_futures=True)
print("Monitor window ended. Colab may also stop a runtime earlier under its service limits.")
'''


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_monitor(root: Path, drive_folder_id: str, *, bundle_file_id: str | None = None,
                notebook_file_id: str | None = None) -> dict[str, object]:
    root = root.resolve()
    notebook_path = root / "Gurumoji_P0_A100_Roundtrip.ipynb"
    metadata_path = root / "p0_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    if not isinstance(drive_folder_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", drive_folder_id):
        raise ValueError("Drive folder ID has an invalid format")
    job_id = metadata.get("job_id")
    if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", job_id):
        raise ValueError("P0 job ID has an invalid format")

    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    if not code_cells:
        raise ValueError("Notebook has no P0 worker code cell")
    source_cell = code_cells[0]
    source = "".join(source_cell["source"])
    source = source.replace(
        'print("P0_RESULT_ZIP_BASE64=" + base64.b64encode(result_zip).decode("ascii"))\n',
        "",
    )
    source_cell["source"] = source.splitlines(keepends=True)
    for cell in notebook["cells"]:
        markdown_source = "".join(cell.get("source", [])) if cell.get("cell_type") == "markdown" else ""
        if "# Gurumoji P0 A100 transport smoke" not in markdown_source and "# Gurumoji A100 worker and transport smoke" not in markdown_source:
            continue
        cell["source"] = [
            "# Gurumoji A100 worker and transport smoke\n", "\n",
            "This notebook includes a synthetic transport smoke and a hash-pinned worker. The synthetic job contains no user documents, article content, credentials, or evaluation answers. Production jobs contain one approved source excerpt and one Base Expert definition.\n", "\n",
            "Run all cells in order on an A100 runtime. The notebook saves the synthetic P0 result, asks for Drive authorization, then checks for production Job ZIPs every 5 minutes. Add a locally prepared bundle to this shared Drive folder with the exact name `Gurumoji_Job_<job_id>_g<generation>.zip`, using the same Google account authorized by Colab. Only bundles created and last edited by that account are eligible. Only an assigned A100 runs a job; the worker pins the Qwen3-32B-AWQ revision and installs Transformers >=4.51 and AutoAWQ when needed. It writes `Gurumoji_Result_<job_id>_g<generation>.zip` to Drive.\n", "\n",
            "The model job runs in a background worker while the monitor schedules a 5-minute queue poll, hourly Runtime/GPU check, and 80-minute Drive integrity audit. With no active model job, an assigned A100 runs one lightweight 256x256 FP16 health operation each hour. Audits check pinned Drive file IDs, folder placement, sizes, and SHA-256, including production bundles and results. Monitor history and job state are saved to one JSON file and resumed after runtime restarts. The monitor loop runs for at most 24 hours and does not start a 55-minute Job window near its end. Drive calls and large model setup can make the schedule best-effort; the Python worker thread cannot be forcibly terminated, although dependency installs and Hub requests have timeouts and generation checks the Job deadline.\n", "\n",
            "A production result remains an untrusted candidate and is not accepted into the local JobStore. Keep the separately generated `.local-approved-sources.json` file locally, download the result ZIP, and pass both to `scripts/accept_colab_claim_job.py` for local validation. Colab may disconnect earlier under service limits; scheduled operations cannot guarantee a continuous connection.\n",
        ]
        break

    bundle_record = next(
        (item for item in metadata.get("drive_uploads", [])
         if item.get("name") == "Gurumoji_P0_Colab_Roundtrip_Bundle.zip"),
        None,
    )
    if not bundle_record:
        if bundle_file_id is None:
            raise ValueError("Uploaded P0 bundle metadata or --bundle-file-id is required")
        local_bundle = root / "p0_colab_roundtrip_bundle.zip"
        if not local_bundle.is_file():
            raise ValueError("Local P0 bundle is required to calculate its Drive pin")
        bundle_bytes = local_bundle.read_bytes()
        bundle_record = {
            "id": bundle_file_id,
            "name": "Gurumoji_P0_Colab_Roundtrip_Bundle.zip",
            "sha256": _sha256(bundle_bytes),
            "size_bytes": len(bundle_bytes),
        }
    local_bundle = root / "p0_colab_roundtrip_bundle.zip"
    actual_bundle_bytes = local_bundle.read_bytes()
    if (_sha256(actual_bundle_bytes) != metadata.get("bundle_sha256") or
            len(actual_bundle_bytes) != metadata.get("bundle_size_bytes")):
        raise ValueError("Local P0 bundle differs from its prepared metadata hash")
    elif bundle_file_id is not None and bundle_record.get("id") != bundle_file_id:
        raise ValueError("--bundle-file-id differs from the pinned Drive bundle ID")
    for key in ("id", "name", "sha256"):
        if not isinstance(bundle_record.get(key), str) or not bundle_record[key]:
            raise ValueError(f"Uploaded P0 bundle metadata field {key!r} is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", bundle_record["id"]):
        raise ValueError("Uploaded P0 bundle ID has an invalid format")
    if bundle_record["name"] != "Gurumoji_P0_Colab_Roundtrip_Bundle.zip":
        raise ValueError("Uploaded P0 bundle name is unexpected")
    if not re.fullmatch(r"[0-9a-f]{64}", bundle_record["sha256"]):
        raise ValueError("Uploaded P0 bundle hash is invalid")
    if type(bundle_record.get("size_bytes")) is not int or bundle_record["size_bytes"] <= 0:
        raise ValueError("Uploaded P0 bundle size is invalid")
    worker_hashes = metadata.get("worker_source_file_hashes")
    if (not isinstance(worker_hashes, dict) or set(worker_hashes) != set(PINNED_WORKER_PATHS) or
            any(not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                for digest in worker_hashes.values())):
        raise ValueError("P0 metadata does not contain a valid pinned worker source hash map")
    if notebook_file_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", notebook_file_id):
        raise ValueError("Drive notebook ID has an invalid format")
    generation = metadata.get("generation")
    if type(generation) is not int or generation < 1:
        raise ValueError("P0 job generation is invalid")
    values = {
        "@DRIVE_FOLDER_ID_JSON@": json.dumps(drive_folder_id, ensure_ascii=True),
        "@BUNDLE_FILE_ID_JSON@": json.dumps(bundle_record["id"], ensure_ascii=True),
        "@BUNDLE_NAME_JSON@": json.dumps(bundle_record["name"], ensure_ascii=True),
        "@BUNDLE_SHA256_JSON@": json.dumps(bundle_record["sha256"], ensure_ascii=True),
        "@BUNDLE_SIZE@": str(bundle_record["size_bytes"]),
        "@JOB_ID_JSON@": json.dumps(job_id, ensure_ascii=True),
        "@GENERATION@": str(metadata["generation"]),
        "@WORKER_SOURCE_HASHES_JSON@": json.dumps(worker_hashes, ensure_ascii=True, sort_keys=True),
    }
    monitor_source = MONITOR_SOURCE
    for placeholder, value in values.items():
        monitor_source = monitor_source.replace(placeholder, value)
    compile(monitor_source, "<colab-runtime-monitor>", "exec")

    monitor_cell = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": (monitor_source.splitlines(keepends=True)),
    }
    old_monitor = next(
        (index for index, cell in enumerate(notebook["cells"])
         if cell.get("cell_type") == "code" and MONITOR_MARKER in "".join(cell.get("source", []))),
        None,
    )
    if old_monitor is None:
        notebook["cells"].append(monitor_cell)
    else:
        notebook["cells"][old_monitor] = monitor_cell
    scheduler_markdown = {
        "cell_type": "markdown", "metadata": {},
        "source": [
            "## A100 Job queue, hourly runtime check, and Drive audit\n", "\n",
            "Run all cells in order. The monitor schedules a shared Drive folder poll for immutable production Job ZIPs every 5 minutes and processes one at a time only while an A100 is assigned. The model worker runs in the background so hourly runtime checks and 80-minute Drive integrity audits continue during inference. It records runtime/GPU and queue state hourly. When no model job is running, it performs one small A100 health operation each hour. Each completed audit verifies pinned file IDs, folder placement, sizes, and SHA-256 for the P0 bundle/result and processed production bundles/results. If an audit or Drive call takes longer than its interval, later work is delayed and recorded.\n", "\n",
            "A production result is an untrusted candidate. Keep its separate local approved Source registry and use `scripts/accept_colab_claim_job.py` locally to validate it before acceptance. Queue state and Drive hash pins resume from the monitor JSON after runtime restarts. The monitor loop runs for at most 24 hours; this is not a hard cancellation of an active background model thread. Colab may stop the runtime earlier under service limits.\n",
        ],
    }
    old_scheduler_markdown = next(
        (index for index, cell in enumerate(notebook["cells"])
         if cell.get("cell_type") == "markdown" and
         ("One monitor JSON file is updated in place" in "".join(cell.get("source", [])) or
          "## A100 Job queue, hourly runtime check, and Drive audit" in "".join(cell.get("source", [])))),
        None,
    )
    if old_scheduler_markdown is None:
        notebook["cells"].append(scheduler_markdown)
    else:
        notebook["cells"][old_scheduler_markdown] = scheduler_markdown

    notebook_bytes = (json.dumps(notebook, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    backup_path = notebook_path.with_name("Gurumoji_P0_A100_Roundtrip.before-scheduler.ipynb")
    if not backup_path.exists():
        backup_path.write_bytes(notebook_path.read_bytes())
    notebook_path.write_bytes(notebook_bytes)

    metadata["drive_folder_id"] = drive_folder_id
    metadata["runtime_schedule"] = {
        "status_check_minutes": 60,
        "queue_poll_minutes": 5,
        "drive_integrity_check_minutes": 80,
        "maximum_monitor_hours": 24,
        "monitor_loop_limit_hours": 24,
        "worker_cancellation": "soft_job_deadline_no_forced_thread_termination",
        "drive_audit_execution": "background_best_effort_delayed_if_previous_audit_is_running",
        "maximum_job_window_minutes": 55,
        "hourly_gpu_work_when_queue_empty": "256x256_fp16_a100_health_probe_when_assigned",
        "hourly_operation_when_queue_empty": "runtime_queue_check_plus_a100_health_probe_if_assigned",
        "resume_monitor_history": True,
        "production_job_adapter": "pinned_qwen3_32b_awq_a100",
        "maximum_job_bundle_files_per_poll": 100,
        "maximum_job_attempts_per_bundle": MAX_JOB_ATTEMPTS,
        "job_uploader_policy": "created_and_last_modified_by_authenticated_colab_account",
    }
    metadata["notebook_size_bytes"] = len(notebook_bytes)
    metadata["notebook_sha256"] = _sha256(notebook_bytes)
    drive_uploads = metadata.get("drive_uploads", [])
    if not isinstance(drive_uploads, list) or any(not isinstance(item, dict) for item in drive_uploads):
        raise ValueError("Drive upload metadata has an invalid shape")
    metadata["drive_uploads"] = drive_uploads
    bundle_record.update({
        "sha256": metadata["bundle_sha256"],
        "size_bytes": metadata["bundle_size_bytes"],
        "scheduler_update_pending_drive_sync": True,
    })
    notebook_record = next(
        (item for item in drive_uploads if item.get("name") == "Gurumoji_P0_A100_Roundtrip.ipynb"),
        None,
    )
    if notebook_record is None and notebook_file_id is not None:
        notebook_record = {"id": notebook_file_id, "name": "Gurumoji_P0_A100_Roundtrip.ipynb"}
        drive_uploads.append(notebook_record)
    if notebook_record is not None:
        if notebook_file_id is not None and notebook_record.get("id") != notebook_file_id:
            raise ValueError("--notebook-file-id differs from the pinned Drive notebook ID")
        notebook_record.update({
            "sha256": metadata["notebook_sha256"],
            "size_bytes": len(notebook_bytes),
            "scheduler_update_pending_drive_sync": True,
        })
    if not any(item is bundle_record or item.get("name") == bundle_record["name"] for item in drive_uploads):
        drive_uploads.append(bundle_record)
    elif not any(item is bundle_record for item in drive_uploads):
        index = next(i for i, item in enumerate(drive_uploads) if item.get("name") == bundle_record["name"])
        drive_uploads[index] = bundle_record
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                             encoding="utf-8")
    return {
        "notebook": str(notebook_path),
        "notebook_size_bytes": len(notebook_bytes),
        "notebook_sha256": metadata["notebook_sha256"],
        "drive_folder_id": drive_folder_id,
        "status_check_minutes": 60,
        "queue_poll_minutes": 5,
        "drive_audit_minutes": 80,
        "production_job_adapter": "pinned_qwen3_32b_awq_a100",
        "job_window_minutes": 55,
        "hourly_gpu_work_when_queue_empty": "256x256_fp16_a100_health_probe_when_assigned",
        "max_monitor_hours": 24,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--drive-folder-id", required=True)
    parser.add_argument("--bundle-file-id", help="Existing Drive bundle file ID to pin for an updated worker archive")
    parser.add_argument("--notebook-file-id", help="Existing Drive notebook file ID to update in place")
    args = parser.parse_args()
    print(json.dumps(add_monitor(args.artifact_root, args.drive_folder_id,
                                 bundle_file_id=args.bundle_file_id,
                                 notebook_file_id=args.notebook_file_id),
                           ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
