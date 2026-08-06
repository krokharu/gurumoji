"""Local Web UI for speaker-diarized transcription.

The browser UI is intentionally bound to 127.0.0.1. Heavy speech-recognition
libraries are imported only inside the background worker so the UI can start
even while the Python environment is being diagnosed.
"""

from __future__ import annotations

import gc
import csv
import ctypes
import difflib
import errno
import hashlib
import html
import hmac
import io
import inspect
import ipaddress
import json
import math
import mimetypes
import ntpath
import os
import platform
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import warnings
import webbrowser
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

_ORIGINAL_OS_REPLACE = os.replace

from flask import Flask, g, has_request_context, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from research_analysis import (
    RESEARCH_CSV_FIELDS,
    build_analysis_workbook,
    enrich_research_analysis,
    research_csv_sources,
)


os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings(
    "ignore",
    message=r"\s*torchcodec is not installed correctly.*",
    category=UserWarning,
)

PRODUCT_NAME = "グルモジ"
APP_VERSION = "1.7.0"
APP_CREATOR = "Kurokawa"
APP_NAME = f"{PRODUCT_NAME} | 話者分離文字起こし"
APP_DIRECTORY = Path(__file__).resolve().parent
AI_HTTP_WORKER_FILE = APP_DIRECTORY / "ai_http_worker.py"
DEFAULT_OUTPUT_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_OUTPUT_DIR", str(APP_DIRECTORY / "output"))
).expanduser()
UPLOAD_DIRECTORY = APP_DIRECTORY / "uploads"
DATA_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_DATA_DIR", str(APP_DIRECTORY / "data"))
).expanduser()
MEDIA_DIRECTORY = DATA_DIRECTORY / "media"
THUMBNAIL_DIRECTORY = DATA_DIRECTORY / "thumbnails"
TRAINING_DIRECTORY = DATA_DIRECTORY / "kushinada_training"
TRAINING_AUDIO_DIRECTORY = TRAINING_DIRECTORY / "audio"
TRAINING_JSONL_FILE = TRAINING_DIRECTORY / "corrections.jsonl"
TRAINING_MANIFEST_FILE = TRAINING_DIRECTORY / "manifest.csv"
DATABASE_FILE = DATA_DIRECTORY / "library.sqlite3"
INSTANCE_LOCK_FILE = UPLOAD_DIRECTORY / ".gurumoji.instance.lock"
DATA_INSTANCE_LOCK_FILE = DATA_DIRECTORY / ".gurumoji.instance.lock"
TOKEN_FILE = APP_DIRECTORY / "tokens.json"
EDIT_TRANSACTION_MANIFEST_NAME = '.edit-transaction.json'
EDIT_PREPARATION_MARKER_NAME = '.edit-preparation.json'
EDIT_TRANSACTION_SCHEMA_VERSION = 1
MAX_EDIT_TRANSACTION_MANIFEST_BYTES = 1024 * 1024
MAX_EDIT_TRANSACTION_FILES = 256
DIARIZATION_MODEL = os.environ.get(
    "MOJIOKOSI_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"
)
DIARIZATION_ACCESS_REPOS = (
    DIARIZATION_MODEL,
    "pyannote/segmentation-3.0",
    "pyannote/speaker-diarization-community-1",
)
ALLOWED_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".wav", ".mp3", ".m4a", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv"}


def positive_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


MAX_MEDIA_UPLOAD_BYTES = positive_env_int(
    "MOJIOKOSI_MAX_MEDIA_MB", 4096, minimum=1, maximum=1024 * 1024
) * 1024 * 1024
MAX_CSV_UPLOAD_BYTES = positive_env_int(
    "MOJIOKOSI_MAX_CSV_MB", 10, minimum=1, maximum=256
) * 1024 * 1024
MAX_JSON_REQUEST_BYTES = positive_env_int(
    "MOJIOKOSI_MAX_JSON_MB", 32, minimum=1, maximum=512
) * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 2 * 1024 * 1024
MAX_RETAINED_JOBS = positive_env_int(
    "MOJIOKOSI_MAX_RETAINED_JOBS", 50, minimum=1, maximum=10000
)
JOB_TTL_SECONDS = positive_env_int(
    "MOJIOKOSI_JOB_TTL_SECONDS", 24 * 60 * 60, minimum=60, maximum=30 * 86400
)
ORPHAN_UPLOAD_GRACE_SECONDS = positive_env_int(
    "MOJIOKOSI_ORPHAN_GRACE_SECONDS", 15 * 60, minimum=60, maximum=7 * 86400
)
REMOTE_ACCESS_ENABLED = env_enabled("MOJIOKOSI_ALLOW_REMOTE")
REMOTE_LOCAL_PATHS_ENABLED = env_enabled("MOJIOKOSI_ENABLE_REMOTE_LOCAL_PATHS")
REMOTE_ACCESS_TOKEN = os.environ.get("MOJIOKOSI_ACCESS_TOKEN", "").strip()
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
UNSAFE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ACTIVE_JOB_STATUSES = frozenset({"queued", "running", "committing"})
SPEAKER_THEME_COLORS = (
    "#E86A5A",
    "#2F80ED",
    "#27AE60",
    "#9B51E0",
    "#F2994A",
    "#00A6A6",
    "#EB5FA7",
    "#7A6FBE",
    "#6C8B3C",
    "#C47F17",
    "#3E8ED0",
    "#B85C5C",
    "#D1495B",
    "#00798C",
    "#6A4C93",
    "#8F5B34",
    "#B33C86",
    "#4D9078",
    "#E4572E",
    "#577590",
)
MODEL_NAMES = {"tiny", "base", "small", "medium", "large-v3"}
LANGUAGES = {None, "ja", "en", "zh", "ko"}
AI_PROVIDERS = {"none", "openai", "google"}
AIST_EMOTION_MODEL_CHOICES = {"kushinada", "izanami", "both"}
AIST_EMOTION_MODELS: dict[str, dict[str, str]] = {
    "kushinada": {
        "label": "くしなだ",
        "display": "くしなだ / HuBERT Large",
        "emotion_repo": "imprt/kushinada-hubert-large-jtes-er",
        "upstream_repo": "imprt/kushinada-hubert-large",
        "upstream_file": "kushinada-hubert-large-s3prl.pt",
        "checkpoint_dir": "kushinada-hubert-large-jtes-er_fold1",
        "fold": "fold1",
        "reference_accuracy": "0.8477",
    },
    "izanami": {
        "label": "いざなみ",
        "display": "いざなみ / wav2vec 2.0 Large",
        "emotion_repo": "imprt/izanami-wav2vec2-large-jtes-er",
        "upstream_repo": "imprt/izanami-wav2vec2-large",
        "upstream_file": "izanami-wav2vec2-large-s3prl.pt",
        "checkpoint_dir": "izanami-wav2vec2-large-jtes-er_fold1",
        "fold": "fold1",
        "reference_accuracy": "0.8012",
    },
}
AIST_EMOTION_LABEL_JA = {
    "ang": "怒り",
    "anger": "怒り",
    "angry": "怒り",
    "hap": "喜び",
    "happy": "喜び",
    "joy": "喜び",
    "sad": "悲しみ",
    "sadness": "悲しみ",
    "neu": "平常",
    "neutral": "平常",
}
AUDIO_PREPROCESS_PRESETS: dict[str, dict[str, Any]] = {
    "none": {
        "label": "加工なし",
        "filters": [],
    },
    "light": {
        "label": "軽め",
        "filters": [
            "highpass=f=70",
            "lowpass=f=7800",
            "loudnorm=I=-18:LRA=11:TP=-1.5",
        ],
    },
    "standard": {
        "label": "おすすめ",
        "filters": [
            "highpass=f=70",
            "lowpass=f=7800",
            "afftdn=nr=8:nf=-55:tn=1",
            "speechnorm=e=3:r=0.00001:l=1",
            "loudnorm=I=-18:LRA=11:TP=-1.5",
        ],
    },
    "strong": {
        "label": "強め",
        "filters": [
            "highpass=f=80",
            "lowpass=f=7600",
            "afftdn=nr=14:nf=-50:tn=1",
            "speechnorm=e=6.25:r=0.00001:l=1",
            "loudnorm=I=-18:LRA=11:TP=-1.5",
        ],
    },
}
MAX_LOG_LINES = 200
NORMAL_VAD_ONSET = 0.5
NORMAL_VAD_OFFSET = 0.363
NORMAL_NO_SPEECH_THRESHOLD = 0.6
QUIET_SUPPLEMENT_MIN_DURATION = 0.2
QUIET_SUPPLEMENT_EDGE_PADDING = 0.12
QUIET_SUPPLEMENT_LOW_OVERLAP_RATIO = 0.2
QUIET_SUPPLEMENT_PARTIAL_OVERLAP_RATIO = 0.65
QUIET_SUPPLEMENT_TEXT_WINDOW_SECONDS = 8.0
QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS = 8
QUIET_SUPPLEMENT_MAX_NO_SPEECH_PROB = 0.85
QUIET_SUPPLEMENT_MIN_AVG_LOGPROB = -1.35
QUIET_SUPPLEMENT_MAX_COMPRESSION_RATIO = 3.2
TRIPLE_PASS_MIN_GAP_SECONDS = 1.5
TRIPLE_PASS_GAP_CONTEXT_SECONDS = 0.75
TRIPLE_PASS_MIN_GAP_OVERLAP_RATIO = 0.6
SHORT_SPEAKER_ISLAND_MAX_SECONDS = 0.55
SPEAKER_BACKCHANNEL_TEXTS = {
    "はい", "ええ", "うん", "そう", "そうです", "なるほど", "確かに",
    "はいはい", "うんうん", "へえ", "ああ", "おお", "ん", "うーん",
}
WHISPER_SAMPLE_RATE = 16000
SESSION_TYPES = {"focus_group", "meeting", "interview", "workshop", "other"}
SPEAKER_ROLES = {
    "participant", "moderator", "facilitator", "assistant_moderator", "observer",
    "note_taker", "interviewer", "chair", "presenter", "decision_maker",
    "attendee", "guest", "other",
}
CONSENT_STATUSES = {"unknown", "pending", "granted", "declined", "not_required"}
ATTENDANCE_STATUSES = {"unknown", "planned", "attended", "absent", "left_early", "remote"}
ANALYSIS_UNITS = {"turn"}
ANALYSIS_GROUP_FIELDS = {"none", "role", "organization", "department", "job_title"}
ANALYSIS_INTERPRETATION_STATUSES = {"draft", "reviewed"}
ANALYSIS_INTERACTION_TAGS = {
    "agreement": "同意・賛同",
    "disagreement": "不一致・反対",
    "differentiation": "立場の差異化",
    "change": "意見の変化",
    "word_use": "言葉の意味の違い",
    "repetition": "反復・強調",
    "engagement": "関与・発展",
    "silencing": "沈黙・発言抑制",
}
ANALYSIS_FACILITATOR_ROLES = {
    "moderator", "facilitator", "assistant_moderator", "interviewer", "chair",
}
ANALYSIS_NON_PARTICIPANT_ROLES = ANALYSIS_FACILITATOR_ROLES | {
    "observer", "note_taker",
}
ANALYSIS_MAX_TIMELINE_SECONDS = 31 * 86400
ANALYSIS_MAX_TIME_BINS = 5000


class AnalysisConflictError(RuntimeError):
    pass


class TranscriptConflictError(RuntimeError):
    def __init__(self, current_revision: int):
        super().__init__("The transcript was changed by another editor. Reload before saving again.")
        self.current_revision = current_revision


class SpeakerRegistryConflictError(RuntimeError):
    def __init__(self, current_revision: int):
        super().__init__("The speaker registry was changed in another tab. Reload before saving again.")
        self.current_revision = current_revision


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_AS_ASCII"] = False
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = MAX_MEDIA_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES


def request_hostname() -> str:
    try:
        return (urllib.parse.urlsplit(f"//{request.host}").hostname or "").casefold()
    except ValueError:
        return ""


def trusted_request_hosts() -> set[str]:
    hosts = set(LOOPBACK_HOSTS)
    if not REMOTE_ACCESS_ENABLED:
        return hosts
    configured = os.environ.get("MOJIOKOSI_TRUSTED_HOSTS", "")
    hosts.update(value.strip().casefold() for value in configured.split(",") if value.strip())
    bind_host = os.environ.get("MOJIOKOSI_HOST", "127.0.0.1").strip().casefold()
    if bind_host and bind_host not in {"0.0.0.0", "::", "[::]", "*"}:
        hosts.add(bind_host.strip("[]"))
    return hosts


def remote_addr_is_loopback() -> bool:
    raw = str(request.remote_addr or "").strip()
    try:
        return ipaddress.ip_address(raw).is_loopback
    except ValueError:
        return raw.casefold() == "localhost"


def bind_host_is_loopback(host: str) -> bool:
    normalized = host.strip().strip("[]").casefold()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def local_path_access_allowed() -> bool:
    if not has_request_context():
        return True
    if REMOTE_ACCESS_ENABLED:
        # Authentication is enforced by before_request.  Remote filesystem
        # access remains unavailable unless the separate high-risk opt-in is set.
        return REMOTE_LOCAL_PATHS_ENABLED
    return remote_addr_is_loopback()


WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:[\\/]|\\\\(?:[?.]\\)?[^\\/\r\n]+[\\/])"
)
POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|(?<=[\s'\`(<\[{=:]))/(?!/)[^\s'\`<>()\[\]{}\r\n]+"
)
FILE_URI_RE = re.compile(r"(?i)\bfile://")
HIDDEN_LOCAL_PATH_MESSAGE = "[local path hidden]"
REMOTE_DIAGNOSTIC_KEYS = frozenset({
    "error", "message", "logs", "reason", "warning", "warnings",
    "restore_errors", "cleanup_errors", "recovery_paths",
    "output_warning", "learning_warning", "output_dir", "default_output_dir",
})


def public_diagnostic_text(value: str, *, reveal_local_paths: bool) -> str:
    """Hide a whole diagnostic item if it contains an absolute local path."""
    text = str(value or "")
    if reveal_local_paths or not text:
        return text
    if (
        WINDOWS_ABSOLUTE_PATH_RE.search(text)
        or POSIX_ABSOLUTE_PATH_RE.search(text)
        or FILE_URI_RE.search(text)
    ):
        return HIDDEN_LOCAL_PATH_MESSAGE
    return text


def sanitize_remote_diagnostic_value(value: Any) -> Any:
    if isinstance(value, str):
        return public_diagnostic_text(value, reveal_local_paths=False)
    if isinstance(value, list):
        return [sanitize_remote_diagnostic_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_remote_diagnostic_value(item)
            for key, item in value.items()
        }
    return value


def sanitize_remote_json_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [sanitize_remote_json_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        diagnostic = (
            key_text in REMOTE_DIAGNOSTIC_KEYS
            or key_text.endswith("_warning")
            or key_text.endswith("_errors")
        )
        sanitized[key] = (
            sanitize_remote_diagnostic_value(item)
            if diagnostic
            else sanitize_remote_json_payload(item)
        )
    return sanitized


def remote_auth_valid() -> bool:
    if not REMOTE_ACCESS_ENABLED or len(REMOTE_ACCESS_TOKEN) < 20:
        return not REMOTE_ACCESS_ENABLED
    supplied = ""
    header = request.headers.get("Authorization", "")
    if header.casefold().startswith("bearer "):
        supplied = header[7:].strip()
    elif request.authorization and request.authorization.type.casefold() == "basic":
        supplied = request.authorization.password or ""
    return bool(supplied) and secrets.compare_digest(supplied, REMOTE_ACCESS_TOKEN)


def request_origin_allowed(value: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    configured = {
        item.strip().rstrip("/").casefold()
        for item in os.environ.get("MOJIOKOSI_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    normalized = f"{parsed.scheme}://{parsed.netloc}".rstrip("/").casefold()
    if normalized in configured:
        return True
    try:
        expected = urllib.parse.urlsplit(request.host_url)
    except ValueError:
        return False
    try:
        return (
            parsed.scheme == expected.scheme
            and parsed.hostname.casefold() == (expected.hostname or "").casefold()
            and parsed.port == expected.port
        )
    except ValueError:
        return False


@app.before_request
def enforce_request_security():
    hostname = request_hostname()
    colab_loopback_proxy = is_colab_runtime() and remote_addr_is_loopback()
    if not hostname or (
        hostname not in trusted_request_hosts() and not colab_loopback_proxy
    ):
        return jsonify({"error": "Untrusted Host header."}), 400

    if REMOTE_ACCESS_ENABLED and not remote_auth_valid():
        response = jsonify({"error": "Authentication is required."})
        response.status_code = 401 if len(REMOTE_ACCESS_TOKEN) >= 20 else 503
        if response.status_code == 401:
            response.headers["WWW-Authenticate"] = 'Basic realm="Gurumoji", charset="UTF-8"'
        return response

    fetch_site = request.headers.get("Sec-Fetch-Site", "").casefold()
    if request.path.startswith("/api/") and fetch_site in {"cross-site", "same-site"}:
        return jsonify({"error": "Cross-origin request rejected."}), 403

    if request.method in UNSAFE_HTTP_METHODS:
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")
        # Fetch Metadata is authoritative for browser requests and remains correct
        # when Colab/tunnel reverse proxies rewrite Host before Flask sees it.
        if fetch_site != "same-origin" and origin and not request_origin_allowed(origin):
            return jsonify({"error": "Invalid request origin."}), 403
        if fetch_site != "same-origin" and not origin and referer and not request_origin_allowed(referer):
            return jsonify({"error": "Invalid request referrer."}), 403
        browser_markers = bool(origin or referer or fetch_site)
        if request.headers.get("X-Gurumoji-Request") != "1" and (
            REMOTE_ACCESS_ENABLED or browser_markers or not remote_addr_is_loopback()
        ):
            return jsonify({"error": "Missing CSRF request header."}), 403

    if request.endpoint == "import_speaker_registry":
        request.max_content_length = MAX_CSV_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
    elif request.endpoint == "create_job":
        request.max_content_length = MAX_MEDIA_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
    elif request.is_json:
        request.max_content_length = MAX_JSON_REQUEST_BYTES

    length = request.content_length
    if length is not None:
        if request.endpoint == "import_speaker_registry" and length > (
            MAX_CSV_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
        ):
            raise RequestEntityTooLarge()
        if request.endpoint == "create_job" and length > (
            MAX_MEDIA_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
        ):
            raise RequestEntityTooLarge()
        if request.is_json and length > MAX_JSON_REQUEST_BYTES:
            raise RequestEntityTooLarge()

    if request.endpoint == "create_job" and request.method == "POST":
        global _job_admission_id
        submission_id = request.headers.get("X-Gurumoji-Submission-Id", "").strip()
        if submission_id and not re.fullmatch(r"[0-9a-f]{32}", submission_id):
            return jsonify({"error": "Invalid transcription submission ID."}), 400
        with jobs_lock:
            prune_jobs_locked()
            existing = jobs.get(submission_id) if submission_id else None
            if existing is not None:
                status_code = 202 if existing.status in ACTIVE_JOB_STATUSES else 200
                return jsonify(existing.public()), status_code
            if _job_admission_id is not None:
                if submission_id and _job_admission_id == submission_id:
                    return jsonify(admission_job_public(submission_id)), 202
                return jsonify({"error": "Another transcription job is already active."}), 409
            if any(job.status in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify({"error": "Another transcription job is already active."}), 409
            _job_admission_id = submission_id or uuid.uuid4().hex
            g.job_admission_id = _job_admission_id
    return None


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify({"error": "Request body exceeds the configured size limit."}), 413


@app.after_request
def disable_development_cache(response):
    global _job_admission_id
    admission_id = getattr(g, "job_admission_id", None)
    if admission_id:
        with jobs_lock:
            if _job_admission_id == admission_id:
                _job_admission_id = None
    if request.path == "/" or request.path.startswith(("/static/", "/api/")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    if REMOTE_ACCESS_ENABLED and not REMOTE_LOCAL_PATHS_ENABLED and response.is_json:
        payload = response.get_json(silent=True)
        if payload is not None:
            sanitized = sanitize_remote_json_payload(payload)
            if sanitized != payload:
                response.set_data(json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")))
                response.headers["Content-Type"] = "application/json"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    frame_ancestors = "'none'"
    if is_colab_runtime():
        frame_ancestors = "https://colab.research.google.com https://*.research.google.com"
    else:
        response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
        f"object-src 'none'; base-uri 'self'; frame-ancestors {frame_ancestors}",
    )
    return response


@dataclass(frozen=True)
class TokenConfig:
    huggingface_token: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    openai_model: str = "gpt-5.6-luna"
    google_model: str = "gemini-flash-latest"

    def availability(self) -> dict[str, Any]:
        return {
            "token_file": TOKEN_FILE.name,
            "huggingface": bool(self.huggingface_token),
            "openai": bool(self.openai_api_key),
            "google": bool(self.google_api_key),
            "openai_model": self.openai_model,
            "google_model": self.google_model,
        }


@dataclass(frozen=True)
class JobOptions:
    input_path: Path
    work_dir: Path
    source_name: str
    output_dir: Path
    model_name: str
    language: str | None
    hf_token: str
    audio_preprocess: str
    min_speakers: int | None
    max_speakers: int | None
    device: str
    diarization_device: str
    triple_pass: bool
    boost_quiet_speech: bool
    vad_onset: float
    vad_offset: float
    no_speech_threshold: float
    write_srt: bool
    write_json: bool
    burn_subtitled_video: bool
    ai_provider: str
    clean_transcript: bool
    detect_speaker_names: bool
    create_outline: bool
    emotion_analysis: bool
    emotion_model: str
    ai_api_key: str = ""
    ai_model: str = ""
    owns_output_dir: bool = False


@dataclass
class JobRecord:
    id: str
    source_name: str
    output_dir: Path
    write_srt: bool
    write_json: bool
    burn_subtitled_video: bool = False
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    stage_label: str = "開始準備"
    stage_progress: int = 0
    message: str = "開始を待っています…"
    logs: list[str] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    speaker_names: dict[str, str] = field(default_factory=dict)
    session_profile: dict[str, Any] = field(default_factory=dict)
    speaker_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    outline: dict[str, Any] | None = None
    emotion_analysis: dict[str, Any] | None = None
    ai_usage: dict[str, Any] = field(default_factory=dict)
    media_path: Path | None = None
    files: list[Path] = field(default_factory=list)
    language: str | None = None
    error: str = ""
    output_warning: str = ""
    revision_count: int = 0
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def public(self) -> dict[str, Any]:
        with jobs_lock:
            reveal_local_paths = local_path_access_allowed()
            return {
                "id": self.id,
                "source_name": self.source_name,
                "output_dir": str(self.output_dir) if reveal_local_paths else "",
                "status": self.status,
                "progress": self.progress,
                "stage": self.stage,
                "stage_label": self.stage_label,
                "stage_progress": self.stage_progress,
                "message": public_diagnostic_text(
                    self.message, reveal_local_paths=reveal_local_paths
                ),
                "logs": [
                    public_diagnostic_text(item, reveal_local_paths=reveal_local_paths)
                    for item in self.logs
                ],
                "segments": [dict(item) for item in self.segments] if self.status == "completed" else [],
                "speaker_names": dict(self.speaker_names) if self.status == "completed" else {},
                "session_profile": (
                    dict(self.session_profile) if self.status == "completed" else {}
                ),
                "speaker_profiles": (
                    {key: dict(value) for key, value in self.speaker_profiles.items()}
                    if self.status == "completed" else {}
                ),
                "write_srt": self.write_srt,
                "write_json": True,
                "burn_subtitled_video": self.burn_subtitled_video,
                "outline": dict(self.outline) if self.status == "completed" and self.outline else None,
                "emotion_analysis": (
                    dict(self.emotion_analysis)
                    if self.status == "completed" and self.emotion_analysis
                    else None
                ),
                "ai_usage": normalize_ai_usage(self.ai_usage),
                "media_url": f"/api/library/{self.id}/media" if self.status == "completed" and self.media_path else None,
                "media_kind": media_kind(self.media_path) if self.status == "completed" and self.media_path else None,
                "files": [
                    {
                        "name": path.name,
                        "url": f"/api/library/{self.id}/files/{urllib.parse.quote(path.name)}",
                    }
                    for path in self.files
                    if path_is_within(path, self.output_dir) and path.is_file()
                ],
                "error": public_diagnostic_text(
                    self.error, reveal_local_paths=reveal_local_paths
                ),
                "output_warning": public_diagnostic_text(
                    self.output_warning, reveal_local_paths=reveal_local_paths
                ),
                "revision_count": self.revision_count,
            }


jobs: dict[str, JobRecord] = {}
jobs_lock = threading.RLock()
library_write_lock = threading.RLock()
training_lock = threading.Lock()
file_dialog_lock = threading.Lock()
machine_profile_lock = threading.Lock()
token_config_lock = threading.Lock()
machine_profile_cache: dict[str, Any] | None = None
system_activity_lock = threading.Lock()
system_activity_previous_io: tuple[float, int, int, int, int] | None = None
_job_admission_id: str | None = None
_instance_lock_streams: list[Any] = []
_instance_lock_guard = threading.Lock()


def prune_jobs_locked(now: float | None = None) -> None:
    current = time.time() if now is None else now
    terminal = {"completed", "failed", "cancelled"}
    for job in jobs.values():
        if job.status in terminal and job.finished_at is None:
            job.finished_at = current
    expired = [
        job_id
        for job_id, job in jobs.items()
        if job.status in terminal
        and job.finished_at is not None
        and current - job.finished_at >= JOB_TTL_SECONDS
    ]
    for job_id in expired:
        jobs.pop(job_id, None)
    excess = len(jobs) - MAX_RETAINED_JOBS
    if excess <= 0:
        return
    removable = sorted(
        (
            (job.finished_at or job.created_at, job_id)
            for job_id, job in jobs.items()
            if job.status in terminal
        ),
        key=lambda value: value[0],
    )
    for _created_at, job_id in removable[:excess]:
        jobs.pop(job_id, None)


def cleanup_orphaned_uploads() -> None:
    if not UPLOAD_DIRECTORY.is_dir():
        return
    upload_root = UPLOAD_DIRECTORY.resolve()
    cutoff = time.time() - ORPHAN_UPLOAD_GRACE_SECONDS
    with jobs_lock:
        active_job_ids = {
            job_id
            for job_id, job in jobs.items()
            if job.status in ACTIVE_JOB_STATUSES
        }
    for candidate in UPLOAD_DIRECTORY.iterdir():
        if not candidate.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", candidate.name):
            continue
        if candidate.name in active_job_ids:
            continue
        try:
            if candidate.stat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.parent == upload_root:
            shutil.rmtree(resolved, ignore_errors=True)


def lock_instance_stream(stream: Any) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def unlock_instance_stream(stream: Any) -> None:
    if os.name == "nt":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def instance_lock_paths() -> list[Path]:
    unique: dict[str, Path] = {}
    for path in (INSTANCE_LOCK_FILE, DATA_INSTANCE_LOCK_FILE):
        key = os.path.normcase(str(path.resolve(strict=False)))
        unique.setdefault(key, path)
    return [unique[key] for key in sorted(unique)]


def acquire_instance_lock() -> bool:
    global _instance_lock_streams
    with _instance_lock_guard:
        if _instance_lock_streams:
            return True
        acquired: list[Any] = []
        try:
            for lock_path in instance_lock_paths():
                lock_path.parent.mkdir(parents=True, exist_ok=True)
                stream = lock_path.open("a+b")
                try:
                    lock_instance_stream(stream)
                except Exception:
                    stream.close()
                    raise
                acquired.append(stream)
        except (ImportError, OSError):
            for stream in reversed(acquired):
                try:
                    unlock_instance_stream(stream)
                except (ImportError, OSError):
                    pass
                stream.close()
            return False
        _instance_lock_streams = acquired
        return True


def release_instance_lock() -> None:
    global _instance_lock_streams
    with _instance_lock_guard:
        streams = _instance_lock_streams
        if not streams:
            return
        for stream in reversed(streams):
            try:
                unlock_instance_stream(stream)
            except (ImportError, OSError):
                pass
            stream.close()
        _instance_lock_streams = []


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def total_system_memory_gib() -> float:
    if sys.platform == "win32":
        try:
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / (1024**3), 1)
        except (AttributeError, OSError, ValueError):
            pass
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        page_count = int(os.sysconf("SC_PHYS_PAGES"))
        return round(page_size * page_count / (1024**3), 1)
    except (AttributeError, OSError, TypeError, ValueError):
        return 0.0


def recommend_machine_settings(
    cpu_threads: int,
    memory_gib: float,
    cuda_available: bool,
    vram_gib: float = 0.0,
    capability_major: int = 0,
) -> dict[str, str]:
    if cuda_available:
        if capability_major < 7:
            model_name = "base" if vram_gib >= 4 else "tiny"
            reason = "旧世代CUDA GPUのため、互換性を優先した軽量設定です。"
        elif vram_gib >= 11.5:
            model_name = "large-v3"
            reason = "VRAM 12 GB以上のCUDA GPUを活かす最高精度設定です。"
        elif vram_gib >= 7.5:
            model_name = "medium"
            reason = "VRAM 8 GB以上のCUDA GPU向け高精度設定です。"
        elif vram_gib >= 5.5:
            model_name = "small"
            reason = "VRAM容量と精度のバランスを取ったGPU設定です。"
        elif vram_gib >= 3.5:
            model_name = "base"
            reason = "VRAM 4 GB級GPUで安定性を優先した設定です。"
        else:
            model_name = "tiny"
            reason = "GPUメモリが少ないため、最軽量モデルを推奨します。"
        diarization_device = "cuda" if capability_major >= 7 and vram_gib >= 7.5 else "cpu"
        return {
            "model_name": model_name,
            "device": "cuda",
            "diarization_device": diarization_device,
            "reason": reason,
        }

    if memory_gib >= 16 and cpu_threads >= 8:
        model_name = "small"
        reason = "CUDAを利用できないため、CPUとRAMを活かす高精度寄りの設定です。"
    elif memory_gib >= 8 and cpu_threads >= 4:
        model_name = "base"
        reason = "CUDAを利用できないため、CPUで安定しやすい標準設定です。"
    else:
        model_name = "tiny"
        reason = "CUDAを利用できずCPU/RAMも限られるため、最軽量設定です。"
    return {
        "model_name": model_name,
        "device": "cpu",
        "diarization_device": "cpu",
        "reason": reason,
    }


def detect_machine_profile() -> dict[str, Any]:
    cpu_threads = max(1, os.cpu_count() or 1)
    cpu_name = (
        platform.processor()
        or os.environ.get("PROCESSOR_IDENTIFIER", "")
        or platform.machine()
        or "CPU"
    ).strip()
    memory_gib = total_system_memory_gib()
    gpu: dict[str, Any] = {
        "cuda_available": False,
        "name": "",
        "vram_gib": 0.0,
        "cuda_version": "",
        "capability": "",
        "device_count": 0,
        "reason": "PyTorchでCUDAを利用できません。",
    }
    try:
        import torch

        gpu["torch_version"] = str(getattr(torch, "__version__", ""))
        gpu["cuda_version"] = str(getattr(torch.version, "cuda", "") or "")
        gpu["cuda_available"] = bool(torch.cuda.is_available())
        if gpu["cuda_available"]:
            gpu["device_count"] = int(torch.cuda.device_count())
            properties = torch.cuda.get_device_properties(0)
            capability = torch.cuda.get_device_capability(0)
            gpu.update({
                "name": str(properties.name),
                "vram_gib": round(properties.total_memory / (1024**3), 1),
                "capability": f"{capability[0]}.{capability[1]}",
                "capability_major": int(capability[0]),
                "reason": "",
            })
        elif not gpu["cuda_version"]:
            gpu["reason"] = "インストール済みPyTorchがCUDA対応ではありません。"
        else:
            gpu["reason"] = "CUDA対応PyTorchからGPUを使用できません。ドライバーを確認してください。"
    except Exception as exc:
        gpu["reason"] = f"GPU診断に失敗しました: {exc}"

    recommended = recommend_machine_settings(
        cpu_threads,
        memory_gib,
        bool(gpu["cuda_available"]),
        float(gpu["vram_gib"]),
        int(gpu.get("capability_major", 0)),
    )
    return {
        "checked_at": utc_now_iso(),
        "cpu": {
            "available": True,
            "name": cpu_name,
            "logical_threads": cpu_threads,
        },
        "memory_gib": memory_gib,
        "gpu": gpu,
        "recommended": recommended,
    }


def get_machine_profile(*, refresh: bool = False) -> dict[str, Any]:
    global machine_profile_cache
    with machine_profile_lock:
        if machine_profile_cache is None or refresh:
            machine_profile_cache = detect_machine_profile()
        return {
            **machine_profile_cache,
            "cpu": dict(machine_profile_cache["cpu"]),
            "gpu": dict(machine_profile_cache["gpu"]),
            "recommended": dict(machine_profile_cache["recommended"]),
        }


def nvidia_activity_snapshot() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {
            "available": False,
            "utilization_percent": None,
            "memory_used_gib": None,
            "memory_total_gib": None,
            "memory_percent": None,
        }
    try:
        completed = subprocess.run(
            [
                executable,
                "--id=0",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            raise RuntimeError("nvidia-smi failed")
        first_line = next(
            (line.strip() for line in completed.stdout.splitlines() if line.strip()),
            "",
        )
        values = [float(value.strip()) for value in first_line.split(",")]
        if len(values) != 3:
            raise ValueError("unexpected nvidia-smi response")
        utilization, memory_used_mib, memory_total_mib = values
        memory_percent = (
            100.0 * memory_used_mib / memory_total_mib
            if memory_total_mib > 0
            else 0.0
        )
        return {
            "available": True,
            "utilization_percent": round(max(0.0, min(100.0, utilization)), 1),
            "memory_used_gib": round(memory_used_mib / 1024, 2),
            "memory_total_gib": round(memory_total_mib / 1024, 2),
            "memory_percent": round(max(0.0, min(100.0, memory_percent)), 1),
        }
    except (OSError, RuntimeError, StopIteration, subprocess.TimeoutExpired, ValueError):
        return {
            "available": False,
            "utilization_percent": None,
            "memory_used_gib": None,
            "memory_total_gib": None,
            "memory_percent": None,
        }


def system_activity_snapshot() -> dict[str, Any]:
    global system_activity_previous_io
    now = time.monotonic()
    cpu: dict[str, Any] = {"available": False, "utilization_percent": None}
    memory: dict[str, Any] = {
        "available": False,
        "utilization_percent": None,
        "used_gib": None,
        "total_gib": None,
    }
    disk: dict[str, Any] = {
        "available": False,
        "read_active": False,
        "write_active": False,
        "read_mib_per_second": 0.0,
        "write_mib_per_second": 0.0,
    }
    try:
        import psutil

        # Flask's threaded development server may handle every poll on a new
        # thread. psutil keeps the non-blocking baseline per thread, so
        # interval=None can return the meaningless first-call value (0.0) on
        # every request. A short blocking sample is thread-independent.
        cpu_percent = float(psutil.cpu_percent(interval=0.1))
        virtual_memory = psutil.virtual_memory()
        total_bytes = int(virtual_memory.total)
        available_bytes = int(virtual_memory.available)
        cpu = {
            "available": True,
            "utilization_percent": round(max(0.0, min(100.0, cpu_percent)), 1),
        }
        memory = {
            "available": True,
            "utilization_percent": round(
                max(0.0, min(100.0, float(virtual_memory.percent))), 1
            ),
            "used_gib": round((total_bytes - available_bytes) / (1024**3), 1),
            "total_gib": round(total_bytes / (1024**3), 1),
        }
        io_counters = psutil.Process(os.getpid()).io_counters()
        read_bytes = int(getattr(io_counters, "read_bytes", 0) or 0)
        write_bytes = int(getattr(io_counters, "write_bytes", 0) or 0)
        read_count = int(getattr(io_counters, "read_count", 0) or 0)
        write_count = int(getattr(io_counters, "write_count", 0) or 0)
        with system_activity_lock:
            previous = system_activity_previous_io
            system_activity_previous_io = (
                now,
                read_bytes,
                write_bytes,
                read_count,
                write_count,
            )
        if previous is None:
            elapsed = 0.0
            read_delta = 0
            write_delta = 0
        else:
            elapsed = max(0.001, now - previous[0])
            read_delta = max(0, read_bytes - previous[1])
            write_delta = max(0, write_bytes - previous[2])
        disk = {
            "available": True,
            "read_active": read_delta > 0 or (previous is not None and read_count > previous[3]),
            "write_active": write_delta > 0 or (previous is not None and write_count > previous[4]),
            "read_mib_per_second": round(read_delta / elapsed / (1024**2), 2) if elapsed else 0.0,
            "write_mib_per_second": round(write_delta / elapsed / (1024**2), 2) if elapsed else 0.0,
        }
    except (AttributeError, ImportError, OSError, ValueError):
        pass
    return {
        "sampled_at": utc_now_iso(),
        "cpu": cpu,
        "memory": memory,
        "gpu": nvidia_activity_snapshot(),
        "disk": disk,
    }


def media_kind(path: Path | None) -> str | None:
    if path is None:
        return None
    mime = mimetypes.guess_type(path.name)[0] or ""
    return "video" if mime.startswith("video/") or path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv"} else "audio"


def is_unc_path(value: str | Path) -> bool:
    raw = str(value).strip()
    return raw.startswith("\\") or raw.startswith("//")


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def read_upload_limited(upload: Any, maximum: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.stream.read(min(1024 * 1024, maximum - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise RequestEntityTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


def save_upload_limited(upload: Any, target: Path, maximum: int) -> int:
    total = 0
    try:
        with target.open("xb") as stream:
            while True:
                chunk = upload.stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise RequestEntityTooLarge()
                stream.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if total == 0:
        target.unlink(missing_ok=True)
        raise ValueError("The uploaded media file is empty.")
    return total


def copy_file_limited(source: Path, target: Path, maximum: int) -> int:
    total = 0
    try:
        with source.open("rb") as input_stream, target.open("xb") as output_stream:
            while True:
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise RequestEntityTooLarge()
                output_stream.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if total == 0:
        target.unlink(missing_ok=True)
        raise ValueError("The selected media file is empty.")
    return total


def validate_json_value(value: Any, *, maximum_nodes: int = 2_000_000) -> None:
    remaining = [maximum_nodes]

    def visit(current: Any, depth: int) -> None:
        remaining[0] -= 1
        if remaining[0] < 0:
            raise ValueError("The JSON payload contains too many values.")
        if depth > 24:
            raise ValueError("The JSON payload is nested too deeply.")
        if current is None or isinstance(current, (bool, int, str)):
            return
        if isinstance(current, float):
            if not math.isfinite(current):
                raise ValueError("NaN and Infinity are not valid input values.")
            return
        if isinstance(current, list):
            for item in current:
                visit(item, depth + 1)
            return
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings.")
                visit(item, depth + 1)
            return
        raise ValueError("The JSON payload contains an unsupported value type.")

    visit(value, 0)


def is_colab_runtime() -> bool:
    return (
        os.environ.get("MOJIOKOSI_RUNTIME", "").strip().casefold() == "colab"
        or "COLAB_RELEASE_TAG" in os.environ
    )


def runtime_info() -> dict[str, Any]:
    colab = is_colab_runtime()
    native_file_dialog = platform.system() == "Windows" and not colab and not REMOTE_ACCESS_ENABLED
    return {
        "kind": "colab" if colab else "local",
        "colab": colab,
        "native_file_dialog": native_file_dialog,
        "browser_upload": not native_file_dialog,
        "ephemeral_storage": colab and not str(DATA_DIRECTORY).startswith("/content/drive/"),
    }


@contextmanager
def database_connection():
    connection = sqlite3.connect(DATABASE_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_output_import_provenance_schema(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS output_import_provenance (
            item_id TEXT NOT NULL,
            canonical_path TEXT NOT NULL,
            content_sha256 TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (item_id, canonical_path)
        )
        """
    )
    table_info = connection.execute(
        "PRAGMA table_info(output_import_provenance)"
    ).fetchall()
    primary_key = [
        str(row["name"])
        for row in sorted(table_info, key=lambda row: int(row["pk"] or 0))
        if int(row["pk"] or 0) > 0
    ]
    if primary_key != ["item_id", "canonical_path"]:
        columns = {str(row["name"]) for row in table_info}
        fingerprint_expression = (
            "COALESCE(content_sha256, '')"
            if "content_sha256" in columns
            else "''"
        )
        connection.execute("DROP TABLE IF EXISTS output_import_provenance_v2")
        connection.execute(
            """
            CREATE TABLE output_import_provenance_v2 (
                item_id TEXT NOT NULL,
                canonical_path TEXT NOT NULL,
                content_sha256 TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (item_id, canonical_path)
            )
            """
        )
        connection.execute(
            "INSERT OR REPLACE INTO output_import_provenance_v2 "
            "(item_id, canonical_path, content_sha256) "
            f"SELECT item_id, canonical_path, {fingerprint_expression} "
            "FROM output_import_provenance"
        )
        connection.execute("DROP TABLE output_import_provenance")
        connection.execute(
            "ALTER TABLE output_import_provenance_v2 "
            "RENAME TO output_import_provenance"
        )
    else:
        columns = {str(row["name"]) for row in table_info}
        if "content_sha256" not in columns:
            connection.execute(
                "ALTER TABLE output_import_provenance "
                "ADD COLUMN content_sha256 TEXT NOT NULL DEFAULT ''"
            )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS output_import_provenance_path_idx "
        "ON output_import_provenance(canonical_path)"
    )


def initialize_library(*, repair_provenance: bool = True) -> None:
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    MEDIA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    TRAINING_AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS library_items (
                id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                media_path TEXT,
                language TEXT,
                segments_json TEXT NOT NULL,
                speaker_names_json TEXT NOT NULL,
                outline_json TEXT,
                emotion_analysis_json TEXT,
                ai_usage_json TEXT NOT NULL DEFAULT '{}',
                files_json TEXT NOT NULL,
                write_srt INTEGER NOT NULL DEFAULT 1,
                write_json INTEGER NOT NULL DEFAULT 1,
                burn_subtitled_video INTEGER NOT NULL DEFAULT 0,
                analysis_config_json TEXT NOT NULL DEFAULT '{}',
                analysis_annotations_json TEXT NOT NULL DEFAULT '{}',
                analysis_revision INTEGER NOT NULL DEFAULT 0,
                analysis_updated_at TEXT,
                revision_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        library_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(library_items)").fetchall()
        }
        if "session_profile_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN session_profile_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "speaker_profiles_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN speaker_profiles_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "ai_usage_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN ai_usage_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "burn_subtitled_video" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN burn_subtitled_video INTEGER NOT NULL DEFAULT 0"
            )
        if "analysis_config_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN analysis_config_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "analysis_annotations_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN analysis_annotations_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "analysis_revision" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN analysis_revision INTEGER NOT NULL DEFAULT 0"
            )
        if "analysis_updated_at" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN analysis_updated_at TEXT"
            )
        connection.execute("UPDATE library_items SET write_json = 1 WHERE write_json <> 1")
        legacy_session_rows = connection.execute(
            "SELECT id, session_profile_json FROM library_items "
            "WHERE session_profile_json LIKE '%confidentiality_notes%'"
        ).fetchall()
        for legacy_row in legacy_session_rows:
            raw_profile = json_load(legacy_row["session_profile_json"], {})
            if not isinstance(raw_profile, dict) or "confidentiality_notes" not in raw_profile:
                continue
            sanitized_profile = dict(raw_profile)
            sanitized_profile.pop("confidentiality_notes", None)
            connection.execute(
                "UPDATE library_items SET session_profile_json = ? WHERE id = ?",
                (json.dumps(sanitized_profile, ensure_ascii=False), legacy_row["id"]),
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS speaker_registry (
                id TEXT PRIMARY KEY,
                participant_code TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                pseudonym TEXT NOT NULL DEFAULT '',
                default_role TEXT NOT NULL DEFAULT 'participant',
                organization TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                job_title TEXT NOT NULL DEFAULT '',
                consent_status TEXT NOT NULL DEFAULT 'unknown',
                recording_consent TEXT NOT NULL DEFAULT 'unknown',
                confidentiality_status TEXT NOT NULL DEFAULT 'unknown',
                tags_json TEXT NOT NULL DEFAULT '[]',
                attributes_json TEXT NOT NULL DEFAULT '{}',
                notes TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS library_updated_idx ON library_items(updated_at DESC)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS speaker_registry_code_idx "
            "ON speaker_registry(participant_code)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS speaker_registry_updated_idx "
            "ON speaker_registry(updated_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)",
            ("speaker_registry_revision", "0"),
        )
        connection.execute(
            "INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)",
            ("training_events_migrated", "0"),
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS training_events (
                event_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS training_events_created_idx "
            "ON training_events(created_at, event_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS output_import_tombstones (
                canonical_path TEXT PRIMARY KEY,
                content_sha256 TEXT NOT NULL DEFAULT '',
                deleted_at TEXT NOT NULL
            )
            """
        )
        tombstone_columns = {
            str(row["name"])
            for row in connection.execute(
                "PRAGMA table_info(output_import_tombstones)"
            ).fetchall()
        }
        if "content_sha256" not in tombstone_columns:
            connection.execute(
                "ALTER TABLE output_import_tombstones "
                "ADD COLUMN content_sha256 TEXT NOT NULL DEFAULT ''"
            )
        ensure_output_import_provenance_schema(connection)
        if repair_provenance:
            repair_output_import_provenance(connection)
        for row in connection.execute("SELECT id, source_name FROM library_items").fetchall():
            source_path = Path(str(row["source_name"]))
            if source_path.is_absolute() and source_path.name:
                connection.execute(
                    "UPDATE library_items SET source_name = ? WHERE id = ?",
                    (source_path.name, row["id"]),
                )


def json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def clean_single_line(value: Any, limit: int) -> str:
    return str(value or "").strip().replace("\r", " ").replace("\n", " ")[:limit]


def clean_multiline(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def normalize_source_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid source name.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Source names cannot contain control characters.")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 255:
        raise ValueError("Source names must contain between 1 and 255 characters.")
    return cleaned


def normalize_tags(value: Any) -> list[str]:
    raw_values = value if isinstance(value, list) else re.split(r"[,、;\n]", str(value or ""))
    tags: list[str] = []
    for raw in raw_values:
        tag = clean_single_line(raw, 80)
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:100]


def normalize_attributes(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    attributes: dict[str, str] = {}
    for raw_key, raw_value in list(value.items())[:200]:
        key = clean_single_line(raw_key, 120)
        if not key:
            continue
        attributes[key] = clean_multiline(raw_value, 2000)
    return attributes


def speaker_registry_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "participant_code": row["participant_code"],
        "display_name": row["display_name"],
        "pseudonym": row["pseudonym"],
        "default_role": row["default_role"],
        "organization": row["organization"],
        "department": row["department"],
        "job_title": row["job_title"],
        "consent_status": row["consent_status"],
        "recording_consent": row["recording_consent"],
        "confidentiality_status": row["confidentiality_status"],
        "tags": json_load(row["tags_json"], []),
        "attributes": json_load(row["attributes_json"], {}),
        "notes": row["notes"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def normalize_speaker_registry_record(
    raw: Any,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("話者データの形式が不正です。")
    base = existing or {}
    record_id = clean_single_line(raw.get("id") or base.get("id") or uuid.uuid4().hex, 80)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", record_id):
        record_id = uuid.uuid4().hex
    default_role = clean_single_line(raw.get("default_role", base.get("default_role", "participant")), 40)
    if default_role not in SPEAKER_ROLES:
        default_role = "participant"

    def consent(field_name: str) -> str:
        value = clean_single_line(raw.get(field_name, base.get(field_name, "unknown")), 30)
        return value if value in CONSENT_STATUSES else "unknown"

    display_name = clean_single_line(raw.get("display_name", base.get("display_name", "")), 120)
    pseudonym = clean_single_line(raw.get("pseudonym", base.get("pseudonym", "")), 120)
    participant_code = clean_single_line(
        raw.get("participant_code", base.get("participant_code", "")), 120
    )
    if not (display_name or pseudonym or participant_code):
        raise ValueError("話者には氏名、仮名、参加者コードのいずれかを入力してください。")
    return {
        "id": record_id,
        "participant_code": participant_code,
        "display_name": display_name,
        "pseudonym": pseudonym,
        "default_role": default_role,
        "organization": clean_single_line(raw.get("organization", base.get("organization", "")), 200),
        "department": clean_single_line(raw.get("department", base.get("department", "")), 200),
        "job_title": clean_single_line(raw.get("job_title", base.get("job_title", "")), 200),
        "consent_status": consent("consent_status"),
        "recording_consent": consent("recording_consent"),
        "confidentiality_status": consent("confidentiality_status"),
        "tags": normalize_tags(raw.get("tags", base.get("tags", []))),
        "attributes": normalize_attributes(raw.get("attributes", base.get("attributes", {}))),
        "notes": clean_multiline(raw.get("notes", base.get("notes", "")), 10000),
        "active": bool(raw.get("active", base.get("active", True))),
    }


def speaker_registry_revision(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT value FROM application_metadata WHERE key = ?",
        ("speaker_registry_revision",),
    ).fetchone()
    if row is None:
        raise RuntimeError("Speaker registry metadata is missing; initialize the database first.")
    try:
        revision = int(row["value"])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Speaker registry revision metadata is invalid.") from exc
    if revision < 0:
        raise RuntimeError("Speaker registry revision metadata is invalid.")
    return revision


def parse_registry_revision(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("registry_revision must be a non-negative integer.")
    if isinstance(value, int):
        revision = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        revision = int(value.strip())
    else:
        raise ValueError("registry_revision must be a non-negative integer.")
    if revision < 0:
        raise ValueError("registry_revision must be a non-negative integer.")
    return revision


def speaker_registry_rows(
    connection: sqlite3.Connection,
    *,
    include_inactive: bool = True,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM speaker_registry"
    if not include_inactive:
        query += " WHERE active = 1"
    query += " ORDER BY active DESC, pseudonym, display_name, participant_code, updated_at DESC"
    return connection.execute(query).fetchall()


def speaker_registry_snapshot(
    *,
    include_inactive: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    with database_connection() as connection:
        revision = speaker_registry_revision(connection)
        rows = speaker_registry_rows(connection, include_inactive=include_inactive)
    return [speaker_registry_public(row) for row in rows], revision


def list_speaker_registry(*, include_inactive: bool = True) -> list[dict[str, Any]]:
    records, _revision = speaker_registry_snapshot(include_inactive=include_inactive)
    return records


def save_speaker_registry_records(
    raw_records: Any,
    *,
    delete_ids: Any = None,
    expected_revision: int | None = None,
    merge_by_participant_code: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(raw_records, list) or len(raw_records) > 10000:
        raise ValueError("Speaker registry data must be an array of at most 10000 records.")
    requested_delete_ids = {
        clean_single_line(value, 80)
        for value in (delete_ids if isinstance(delete_ids, list) else [])
        if clean_single_line(value, 80)
    }
    now = utc_now_iso()
    with database_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        current_revision = speaker_registry_revision(connection)
        if expected_revision is not None and current_revision != expected_revision:
            raise SpeakerRegistryConflictError(current_revision)

        existing_records = {
            item["id"]: item
            for item in (
                speaker_registry_public(row)
                for row in speaker_registry_rows(connection, include_inactive=True)
            )
        }
        prepared_records = raw_records
        if merge_by_participant_code:
            by_code = {
                item["participant_code"].casefold(): item
                for item in existing_records.values()
                if item["participant_code"]
            }
            prepared_records = []
            for raw in raw_records:
                if not isinstance(raw, dict):
                    prepared_records.append(raw)
                    continue
                code = clean_single_line(raw.get("participant_code"), 120).casefold()
                previous = by_code.get(code) if code else None
                if previous is None:
                    prepared_records.append(dict(raw))
                    continue
                merged_attributes = {
                    **previous.get("attributes", {}),
                    **(raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}),
                }
                prepared_records.append({
                    **previous,
                    **raw,
                    "id": previous["id"],
                    "attributes": merged_attributes,
                })

        normalized = [
            normalize_speaker_registry_record(
                raw,
                existing=existing_records.get(str(raw.get("id"))) if isinstance(raw, dict) else None,
            )
            for raw in prepared_records
        ]
        for record in normalized:
            previous = existing_records.get(record["id"])
            connection.execute(
                """
                INSERT INTO speaker_registry (
                    id, participant_code, display_name, pseudonym, default_role,
                    organization, department, job_title, consent_status,
                    recording_consent, confidentiality_status, tags_json,
                    attributes_json, notes, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    participant_code=excluded.participant_code,
                    display_name=excluded.display_name,
                    pseudonym=excluded.pseudonym,
                    default_role=excluded.default_role,
                    organization=excluded.organization,
                    department=excluded.department,
                    job_title=excluded.job_title,
                    consent_status=excluded.consent_status,
                    recording_consent=excluded.recording_consent,
                    confidentiality_status=excluded.confidentiality_status,
                    tags_json=excluded.tags_json,
                    attributes_json=excluded.attributes_json,
                    notes=excluded.notes,
                    active=excluded.active,
                    updated_at=excluded.updated_at
                """,
                (
                    record["id"], record["participant_code"], record["display_name"],
                    record["pseudonym"], record["default_role"], record["organization"],
                    record["department"], record["job_title"], record["consent_status"],
                    record["recording_consent"], record["confidentiality_status"],
                    json.dumps(record["tags"], ensure_ascii=False),
                    json.dumps(record["attributes"], ensure_ascii=False), record["notes"],
                    int(record["active"]), previous["created_at"] if previous else now, now,
                ),
            )
        if requested_delete_ids:
            placeholders = ",".join("?" for _ in requested_delete_ids)
            connection.execute(
                f"DELETE FROM speaker_registry WHERE id IN ({placeholders})",
                tuple(sorted(requested_delete_ids)),
            )
        new_revision = current_revision + 1
        connection.execute(
            "UPDATE application_metadata SET value = ? WHERE key = ?",
            (str(new_revision), "speaker_registry_revision"),
        )
        rows = speaker_registry_rows(connection, include_inactive=True)
        records = [speaker_registry_public(row) for row in rows]
    return records, new_revision

def normalized_csv_header(value: Any) -> str:
    return re.sub(r"[\s_\-（）()\[\]【】]+", "", str(value or "").strip().casefold())


SPEAKER_CSV_FIELD_ALIASES = {
    "タイムスタンプ": "",
    "timestamp": "",
    "id": "participant_code",
    "参加者id": "participant_code",
    "回答者id": "participant_code",
    "参加者コード": "participant_code",
    "participantid": "participant_code",
    "participantcode": "participant_code",
    "氏名": "display_name",
    "名前": "display_name",
    "お名前": "display_name",
    "name": "display_name",
    "displayname": "display_name",
    "仮名": "pseudonym",
    "匿名名": "pseudonym",
    "pseudonym": "pseudonym",
    "役割": "default_role",
    "デフォルト役割": "default_role",
    "role": "default_role",
    "defaultrole": "default_role",
    "組織": "organization",
    "会社": "organization",
    "所属組織": "organization",
    "organization": "organization",
    "company": "organization",
    "部署": "department",
    "所属部署": "department",
    "department": "department",
    "役職": "job_title",
    "職位": "job_title",
    "jobtitle": "job_title",
    "title": "job_title",
    "研究同意": "consent_status",
    "参加同意": "consent_status",
    "consent": "consent_status",
    "consentstatus": "consent_status",
    "録音同意": "recording_consent",
    "recordingconsent": "recording_consent",
    "守秘同意": "confidentiality_status",
    "confidentiality": "confidentiality_status",
    "confidentialitystatus": "confidentiality_status",
    "タグ": "tags",
    "tags": "tags",
    "備考": "notes",
    "メモ": "notes",
    "notes": "notes",
    "有効": "active",
    "active": "active",
}

SPEAKER_ROLE_ALIASES = {
    "参加者": "participant",
    "司会": "moderator",
    "モデレーター": "moderator",
    "進行": "facilitator",
    "ファシリテーター": "facilitator",
    "副司会": "assistant_moderator",
    "観察者": "observer",
    "記録者": "note_taker",
    "書記": "note_taker",
    "インタビュアー": "interviewer",
    "議長": "chair",
    "発表者": "presenter",
    "意思決定者": "decision_maker",
    "出席者": "attendee",
    "ゲスト": "guest",
    "その他": "other",
}


def normalize_csv_role(value: Any) -> str:
    cleaned = clean_single_line(value, 40)
    mapped = SPEAKER_ROLE_ALIASES.get(cleaned, cleaned)
    return mapped if mapped in SPEAKER_ROLES else "participant"


def normalize_csv_consent(value: Any) -> str:
    cleaned = clean_single_line(value, 40).casefold()
    if cleaned in {"yes", "y", "true", "1", "同意", "同意済み", "許可", "済", "承諾"}:
        return "granted"
    if cleaned in {"no", "n", "false", "0", "拒否", "非同意", "不許可"}:
        return "declined"
    if cleaned in {"pending", "保留", "確認中", "未回答"}:
        return "pending"
    if cleaned in {"notrequired", "不要", "対象外"}:
        return "not_required"
    return cleaned if cleaned in CONSENT_STATUSES else "unknown"


def speaker_csv_field_for_header(header: str) -> str | None:
    normalized = normalized_csv_header(header)
    exact = SPEAKER_CSV_FIELD_ALIASES.get(normalized)
    if exact is not None:
        return exact
    if "録音" in normalized and ("同意" in normalized or "許可" in normalized):
        return "recording_consent"
    if "守秘" in normalized and ("同意" in normalized or "確認" in normalized):
        return "confidentiality_status"
    if ("研究" in normalized or "参加" in normalized) and "同意" in normalized:
        return "consent_status"
    if "参加者" in normalized and ("コード" in normalized or "id" in normalized):
        return "participant_code"
    return None


def import_speaker_registry_csv(
    content: bytes,
    *,
    expected_revision: int,
) -> tuple[list[dict[str, Any]], int, int]:
    if len(content) > MAX_CSV_UPLOAD_BYTES:
        raise ValueError("CSVは10MB以内にしてください。")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("cp932")
        except UnicodeDecodeError as exc:
            raise ValueError("CSVの文字コードはUTF-8またはWindows日本語にしてください。") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSVに見出し行がありません。")
    imported: list[dict[str, Any]] = []
    for row_index, row in enumerate(reader, 2):
        if row_index > 10001:
            raise ValueError("一度に取り込める話者は10000件までです。")
        fixed: dict[str, Any] = {"attributes": {}}
        for raw_header, raw_value in row.items():
            header = clean_single_line(raw_header, 120)
            value = clean_multiline(raw_value, 10000)
            if not header or not value:
                continue
            field_name = speaker_csv_field_for_header(header)
            if field_name == "":
                continue
            if field_name:
                fixed[field_name] = value
            else:
                fixed["attributes"][header] = value
        if not any(fixed.get(key) for key in ("participant_code", "display_name", "pseudonym")):
            continue
        if fixed.get("default_role"):
            fixed["default_role"] = normalize_csv_role(fixed["default_role"])
        for field_name in ("consent_status", "recording_consent", "confidentiality_status"):
            if fixed.get(field_name):
                fixed[field_name] = normalize_csv_consent(fixed[field_name])
        if "active" in fixed:
            fixed["active"] = str(fixed["active"]).strip().casefold() not in {
                "0", "false", "no", "n", "無効",
            }
        imported.append(fixed)
    if not imported:
        raise ValueError("取り込める話者行がありませんでした。見出しと値を確認してください。")
    records, revision = save_speaker_registry_records(
        imported,
        expected_revision=expected_revision,
        merge_by_participant_code=True,
    )
    return records, len(imported), revision


def speaker_registry_csv_bytes(records: list[dict[str, Any]]) -> bytes:
    custom_headers = sorted({
        key
        for record in records
        for key in (record.get("attributes") or {})
    })
    fixed_headers = [
        "参加者コード", "氏名", "仮名", "役割", "組織", "部署", "役職",
        "守秘同意", "タグ", "備考", "有効",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
    writer.writerow({header: analysis_csv_safe(header) for header in fixed_headers + custom_headers})
    for record in records:
        row = {
            "参加者コード": record["participant_code"],
            "氏名": record["display_name"],
            "仮名": record["pseudonym"],
            "役割": record["default_role"],
            "組織": record["organization"],
            "部署": record["department"],
            "役職": record["job_title"],
            "守秘同意": record["confidentiality_status"],
            "タグ": ",".join(record["tags"]),
            "備考": record["notes"],
            "有効": "1" if record["active"] else "0",
            **record["attributes"],
        }
        writer.writerow({key: analysis_csv_safe(value) for key, value in row.items()})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def stable_segment_id(item_id: str, index: int, segment: dict[str, Any]) -> str:
    existing = str(segment.get("id") or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", existing):
        return existing
    seed = f"{item_id}:{index}:{segment.get('start', 0)}:{segment.get('end', 0)}"
    return uuid.uuid5(uuid.NAMESPACE_URL, seed).hex


def ensure_segment_ids(item_id: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, raw in enumerate(segments):
        if not isinstance(raw, dict):
            continue
        segment = dict(raw)
        segment_id = stable_segment_id(item_id, index, segment)
        if segment_id in used:
            segment_id = uuid.uuid4().hex
        segment["id"] = segment_id
        used.add(segment_id)
        normalized.append(segment)
    return normalized


def library_row(item_id: str) -> sqlite3.Row | None:
    with database_connection() as connection:
        return connection.execute("SELECT * FROM library_items WHERE id = ?", (item_id,)).fetchone()


def row_segments(row: sqlite3.Row) -> list[dict[str, Any]]:
    raw = json_load(row["segments_json"], [])
    return ensure_segment_ids(row["id"], raw if isinstance(raw, list) else [])


def normalize_session_profile(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raw = {}
    session_type = clean_single_line(raw.get("session_type", "focus_group"), 40)
    if session_type not in SESSION_TYPES:
        session_type = "other"
    session_date = clean_single_line(raw.get("session_date"), 40)
    session_date_source = clean_single_line(raw.get("session_date_source"), 30)
    if session_date_source not in {"media_metadata", "manual"}:
        session_date_source = "manual" if session_date else ""
    if not session_date:
        session_date_source = ""
    return {
        "session_type": session_type,
        "session_date": session_date,
        "session_date_source": session_date_source,
        "location": clean_single_line(raw.get("location"), 300),
        "objective": clean_multiline(raw.get("objective"), 10000),
        "moderator_guide": clean_multiline(raw.get("moderator_guide"), 20000),
        "group_conditions": clean_multiline(raw.get("group_conditions"), 10000),
        "field_notes": clean_multiline(raw.get("field_notes"), 30000),
    }


def normalize_conversation_speaker_profiles(
    raw: Any,
    labels: set[str],
    speaker_names: dict[str, str],
) -> dict[str, dict[str, Any]]:
    source = raw if isinstance(raw, dict) else {}
    profiles: dict[str, dict[str, Any]] = {}
    for index, label in enumerate(sorted(labels)):
        value = source.get(label)
        value = value if isinstance(value, dict) else {}
        role = clean_single_line(value.get("session_role", "participant"), 40)
        if role not in SPEAKER_ROLES:
            role = "participant"
        consent_status = clean_single_line(value.get("consent_status", "unknown"), 30)
        recording_consent = clean_single_line(value.get("recording_consent", "unknown"), 30)
        attendance_status = clean_single_line(value.get("attendance_status", "attended"), 30)
        theme_color = clean_single_line(value.get("theme_color"), 7).upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", theme_color):
            theme_color = SPEAKER_THEME_COLORS[index % len(SPEAKER_THEME_COLORS)]
        profiles[label] = {
            "speaker_label": label,
            "global_speaker_id": clean_single_line(value.get("global_speaker_id"), 80),
            "display_name": clean_single_line(
                value.get("display_name") or speaker_names.get(label), 120
            ),
            "theme_color": theme_color,
            "session_role": role,
            "organization": clean_single_line(value.get("organization"), 200),
            "department": clean_single_line(value.get("department"), 200),
            "job_title": clean_single_line(value.get("job_title"), 200),
            "consent_status": (
                consent_status if consent_status in CONSENT_STATUSES else "unknown"
            ),
            "recording_consent": (
                recording_consent if recording_consent in CONSENT_STATUSES else "unknown"
            ),
            "attendance_status": (
                attendance_status if attendance_status in ATTENDANCE_STATUSES else "unknown"
            ),
            "conditions": clean_multiline(value.get("conditions"), 10000),
            "notes": clean_multiline(value.get("notes"), 10000),
        }
    return profiles


def row_session_profile(row: sqlite3.Row) -> dict[str, str]:
    return normalize_session_profile(json_load(row["session_profile_json"], {}))


def row_speaker_profiles(
    row: sqlite3.Row,
    segments: list[dict[str, Any]] | None = None,
    speaker_names: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    segments = segments if segments is not None else row_segments(row)
    if speaker_names is None:
        raw_names = json_load(row["speaker_names_json"], {})
        speaker_names = raw_names if isinstance(raw_names, dict) else {}
    labels = {str(item.get("speaker") or "UNKNOWN") for item in segments}
    return normalize_conversation_speaker_profiles(
        json_load(row["speaker_profiles_json"], {}),
        labels,
        speaker_names,
    )


def emotion_values(segment: dict[str, Any]) -> list[str]:
    emotions = segment.get("emotions")
    if not isinstance(emotions, dict):
        return []
    values: list[str] = []
    for data in emotions.values():
        if not isinstance(data, dict):
            continue
        raw_value = data.get("label_ja") or data.get("label")
        if not raw_value:
            continue
        value = str(data.get("label_ja") or emotion_label_ja(str(raw_value))).strip()
        if value and value not in values:
            values.append(value)
    return values


def library_public(row: sqlite3.Row, *, full: bool = True, match_count: int | None = None) -> dict[str, Any]:
    segments = row_segments(row)
    speaker_names = json_load(row["speaker_names_json"], {})
    if not isinstance(speaker_names, dict):
        speaker_names = {}
    speakers = sorted({
        str(speaker_names.get(str(item.get("speaker") or "")) or default_speaker_name(item.get("speaker")))
        for item in segments
        if item.get("speaker")
    })
    emotions = sorted({value for item in segments for value in emotion_values(item)})
    media_path = Path(row["media_path"]) if row["media_path"] else None
    file_paths = [Path(value) for value in json_load(row["files_json"], []) if isinstance(value, str)]
    output_root = Path(row["output_dir"])
    media_available = bool(
        media_path
        and path_is_within(media_path, MEDIA_DIRECTORY / str(row["id"]))
        and media_path.is_file()
    )
    result: dict[str, Any] = {
        "id": row["id"],
        "source_name": row["source_name"],
        "output_dir": row["output_dir"] if local_path_access_allowed() else "",
        "language": row["language"],
        "segment_count": len(segments),
        "duration": max((float(item.get("end", 0) or 0) for item in segments), default=0),
        "speakers": speakers,
        "emotions": emotions,
        "preview": " ".join(str(item.get("text", "")).strip() for item in segments[:3]).strip()[:240],
        "thumbnail_url": (
            f"/api/library/{row['id']}/thumbnail?v="
            f"{urllib.parse.quote(str(row['updated_at']))}"
        ),
        "media_url": f"/api/library/{row['id']}/media" if media_available else None,
        "media_kind": media_kind(media_path) if media_available else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "revision_count": int(row["revision_count"] or 0),
        "analysis_revision": int(row["analysis_revision"] or 0),
        "analysis_updated_at": row["analysis_updated_at"],
        "match_count": match_count,
        "speaker_data_url": f"/api/library/{row['id']}/speakers.csv",
        "analysis_url": f"/api/library/{row['id']}/analysis",
        "analysis_export_url": f"/api/library/{row['id']}/analysis/export.json",
        "files": [
            {"name": path.name, "url": f"/api/library/{row['id']}/files/{urllib.parse.quote(path.name)}"}
            for path in file_paths if path_is_within(path, output_root) and path.is_file()
        ],
    }
    if full:
        result.update({
            "status": "completed",
            "segments": segments,
            "speaker_names": speaker_names,
            "session_profile": row_session_profile(row),
            "speaker_profiles": row_speaker_profiles(row, segments, speaker_names),
            "outline": json_load(row["outline_json"], None),
            "emotion_analysis": json_load(row["emotion_analysis_json"], None),
            "ai_usage": normalize_ai_usage(json_load(row["ai_usage_json"], {})),
            "write_srt": bool(row["write_srt"]),
            "write_json": True,
            "burn_subtitled_video": bool(row["burn_subtitled_video"]),
        })
    return result


def upsert_library_item(
    *, item_id: str, source_name: str, output_dir: Path, media_path: Path | None,
    language: str | None, segments: list[dict[str, Any]], speaker_names: dict[str, str],
    outline: dict[str, Any] | None, emotion_analysis: dict[str, Any] | None,
    files: list[Path], write_srt: bool, write_json: bool, increment_revision: bool = False,
    created_at: str | None = None, session_profile: dict[str, Any] | None = None,
    speaker_profiles: dict[str, Any] | None = None, burn_subtitled_video: bool = False,
    expected_revision: int | None = None,
    connection: sqlite3.Connection | None = None,
    ai_usage: dict[str, Any] | None = None,
) -> sqlite3.Row:
    validate_json_value(segments)
    validate_json_value(speaker_names)
    validate_json_value(outline)
    validate_json_value(emotion_analysis)
    validate_json_value(session_profile)
    validate_json_value(speaker_profiles)
    ai_usage = normalize_ai_usage(ai_usage)
    validate_json_value(ai_usage)
    now = utc_now_iso()
    segments = ensure_segment_ids(item_id, segments)
    session_profile = normalize_session_profile(session_profile)
    labels = {str(item.get("speaker") or "UNKNOWN") for item in segments}
    speaker_profiles = normalize_conversation_speaker_profiles(
        speaker_profiles,
        labels,
        speaker_names,
    )
    def persist(active_connection: sqlite3.Connection) -> sqlite3.Row:
        if expected_revision is not None:
            if not active_connection.in_transaction:
                active_connection.execute("BEGIN IMMEDIATE")
            current = active_connection.execute(
                "SELECT revision_count FROM library_items WHERE id = ?", (item_id,)
            ).fetchone()
            if current is None:
                raise LookupError("The transcript no longer exists.")
            current_revision = int(current["revision_count"] or 0)
            if current_revision != expected_revision:
                raise TranscriptConflictError(current_revision)
        active_connection.execute(
            """
            INSERT INTO library_items (
                id, source_name, output_dir, media_path, language, segments_json,
                speaker_names_json, outline_json, emotion_analysis_json, ai_usage_json, files_json,
                write_srt, write_json, burn_subtitled_video, revision_count, created_at, updated_at,
                session_profile_json, speaker_profiles_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_name=excluded.source_name, output_dir=excluded.output_dir,
                media_path=excluded.media_path, language=excluded.language,
                segments_json=excluded.segments_json, speaker_names_json=excluded.speaker_names_json,
                outline_json=excluded.outline_json, emotion_analysis_json=excluded.emotion_analysis_json,
                ai_usage_json=excluded.ai_usage_json,
                files_json=excluded.files_json, write_srt=excluded.write_srt,
                write_json=excluded.write_json,
                burn_subtitled_video=excluded.burn_subtitled_video,
                session_profile_json=excluded.session_profile_json,
                speaker_profiles_json=excluded.speaker_profiles_json,
                revision_count=library_items.revision_count + ?, updated_at=excluded.updated_at
            """,
            (
                item_id, source_name, str(output_dir), str(media_path) if media_path else None,
                language, json.dumps(segments, ensure_ascii=False),
                json.dumps(speaker_names, ensure_ascii=False),
                json.dumps(outline, ensure_ascii=False) if outline else None,
                json.dumps(emotion_analysis, ensure_ascii=False) if emotion_analysis else None,
                json.dumps(ai_usage, ensure_ascii=False),
                json.dumps([str(path) for path in files], ensure_ascii=False),
                int(write_srt), 1, int(burn_subtitled_video),
                int(increment_revision), created_at or now, now,
                json.dumps(session_profile, ensure_ascii=False),
                json.dumps(speaker_profiles, ensure_ascii=False),
                int(increment_revision),
            ),
        )
        row = active_connection.execute(
            "SELECT * FROM library_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("The library record could not be read back before commit.")
        return row

    if connection is not None:
        return persist(connection)
    with database_connection() as owned_connection:
        return persist(owned_connection)


def safe_media_filename(original_name: str, fallback_stem: str = 'media') -> str:
    '''Keep an allowed media suffix when Werkzeug strips a non-ASCII stem.'''
    suffix = Path(original_name).suffix.lower()
    safe_stem = secure_filename(Path(original_name).stem).strip(' .')
    if not safe_stem:
        safe_stem = fallback_stem
    return f'{safe_stem}{suffix}'


def stage_media_archive(
    item_id: str,
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[Path, Path]:
    target_dir = MEDIA_DIRECTORY / item_id
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_media_filename(source_path.name)
    target = target_dir / safe_name
    staged = temporary_output_path(target)
    try:
        atomic_copy_file(source_path, staged, check_cancelled)
    except Exception:
        staged.unlink(missing_ok=True)
        raise
    return target, staged


def commit_staged_media(target: Path, staged: Path) -> Path:
    if staged.parent.resolve() != target.parent.resolve() or not staged.is_file():
        raise OSError("The staged media file is missing or outside its destination directory.")
    sync_file_data(staged)
    durable_move(staged, target)
    return target


def archive_media(
    item_id: str,
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    target, staged = stage_media_archive(item_id, source_path, check_cancelled)
    try:
        return commit_staged_media(target, staged)
    finally:
        staged.unlink(missing_ok=True)


def remove_owned_directory(path: Path, *, ignore_errors: bool = False) -> None:
    try:
        if path.is_symlink():
            path.unlink(missing_ok=True)
        elif path.exists():
            shutil.rmtree(path)
    except OSError:
        if not ignore_errors:
            raise


def cleanup_uncommitted_job_artifacts(job: JobRecord, options: JobOptions) -> list[str]:
    """Remove only resources reserved for this job when no library row was committed."""
    warnings: list[str] = []
    try:
        if library_row(job.id) is not None:
            return warnings
    except (OSError, sqlite3.Error) as exc:
        return [f"Could not verify library persistence; temporary artifacts were retained: {exc}"]

    if options.owns_output_dir:
        expected_suffix = f"_{job.id[:8]}"
        if options.output_dir.name.endswith(expected_suffix):
            try:
                remove_owned_directory(options.output_dir)
            except OSError as exc:
                warnings.append(f"Could not remove the incomplete output directory: {exc}")
        else:
            warnings.append("The incomplete output directory failed its ownership check and was retained.")

    media_dir = MEDIA_DIRECTORY / job.id
    if re.fullmatch(r"[0-9a-f]{32}", job.id):
        try:
            media_root = MEDIA_DIRECTORY.resolve()
            if media_dir.parent.resolve() == media_root:
                remove_owned_directory(media_dir)
        except OSError as exc:
            warnings.append(f"Could not remove the incomplete media archive: {exc}")
    return warnings


def resolve_local_media_path(raw_path: str) -> Path:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        raise ValueError("処理する音声・動画ファイルを選択してください。")
    expanded = os.path.expandvars(raw_path)
    if is_unc_path(raw_path) or is_unc_path(expanded):
        raise ValueError("UNC/network media paths are disabled by default. Upload the file instead.")
    try:
        path = Path(expanded).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"指定したパスを開けません: {exc}") from exc
    if not path.is_file():
        raise ValueError("指定したパスはファイルではありません。")
    if path.stat().st_size == 0:
        raise ValueError("指定したファイルが空です。")
    if path.stat().st_size > MAX_MEDIA_UPLOAD_BYTES:
        raise ValueError("The media file exceeds the configured size limit.")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("対応形式は MP4/MOV/MKV/WAV/MP3/M4A/FLAC です。")
    return path


def prepare_output_root(raw_path: str) -> Path:
    expanded = os.path.expandvars(raw_path.strip().strip('"'))
    if expanded and (is_unc_path(raw_path) or is_unc_path(expanded)):
        raise ValueError("UNC/network output paths are disabled by default.")
    output_root = Path(expanded).expanduser() if expanded else DEFAULT_OUTPUT_DIRECTORY
    if is_unc_path(output_root):
        raise ValueError("UNC/network output paths are disabled by default.")
    output_root.mkdir(parents=True, exist_ok=True)
    if not output_root.is_dir():
        raise ValueError("The output destination must be a directory.")
    probe = output_root / f".gurumoji-write-test-{uuid.uuid4().hex}"
    try:
        with probe.open("xb") as stream:
            stream.write(b"ok")
    except OSError as exc:
        raise ValueError(f"The output directory is not writable: {exc}") from exc
    finally:
        probe.unlink(missing_ok=True)
    return output_root.resolve()


def edit_storage_id(connection: sqlite3.Connection | None = None) -> str:
    def read(active_connection: sqlite3.Connection) -> str:
        active_connection.execute(
            'INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)',
            ('edit_storage_id', uuid.uuid4().hex),
        )
        row = active_connection.execute(
            'SELECT value FROM application_metadata WHERE key = ?',
            ('edit_storage_id',),
        ).fetchone()
        value = str(row['value'] if row is not None else '')
        if not re.fullmatch(r'[0-9a-f]{32}', value):
            raise RuntimeError('The edit transaction storage identity is missing or invalid.')
        return value

    if connection is not None:
        return read(connection)
    with database_connection() as owned_connection:
        return read(owned_connection)


def edit_journal_secret(connection: sqlite3.Connection | None = None) -> bytes:
    def read(active_connection: sqlite3.Connection) -> bytes:
        active_connection.execute(
            'INSERT OR IGNORE INTO application_metadata (key, value) VALUES (?, ?)',
            ('edit_journal_secret', secrets.token_hex(32)),
        )
        row = active_connection.execute(
            'SELECT value FROM application_metadata WHERE key = ?',
            ('edit_journal_secret',),
        ).fetchone()
        value = str(row['value'] if row is not None else '')
        if not re.fullmatch(r'[0-9a-f]{64}', value):
            raise RuntimeError('The edit journal authentication secret is missing or invalid.')
        return bytes.fromhex(value)

    if connection is not None:
        return read(connection)
    with database_connection() as owned_connection:
        return read(owned_connection)


def edit_journal_mac(payload: dict[str, Any], secret: bytes) -> str:
    authenticated = {
        key: value
        for key, value in payload.items()
        if key != 'mac' and not key.startswith('_')
    }
    encoded = json.dumps(
        authenticated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hmac.new(secret, encoded, hashlib.sha256).hexdigest()


def safe_edit_relative_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path or len(raw_path) > 1024:
        raise ValueError('An edit transaction contains an invalid relative path.')
    if '\\' in raw_path or '\x00' in raw_path:
        raise ValueError('An edit transaction contains an unsafe relative path.')
    pure = PurePosixPath(raw_path)
    if (
        pure.is_absolute()
        or pure.as_posix() != raw_path
        or any(part in {'', '.', '..'} for part in pure.parts)
    ):
        raise ValueError('An edit transaction contains an unsafe relative path.')
    reserved_devices = {
        'con', 'prn', 'aux', 'nul', 'conin$', 'conout$',
        *(f'com{index}' for index in range(1, 10)),
        *(f'lpt{index}' for index in range(1, 10)),
        'com¹', 'com²', 'com³', 'lpt¹', 'lpt²', 'lpt³',
    }
    reserved_internal = {
        '.previous',
        '.discarded',
        EDIT_TRANSACTION_MANIFEST_NAME.casefold(),
        EDIT_PREPARATION_MARKER_NAME.casefold(),
    }
    for part in pure.parts:
        folded = part.casefold()
        device_base = part.split('.', 1)[0].rstrip(' .').casefold()
        if (
            folded in reserved_internal
            or device_base in reserved_devices
            or part.endswith((' ', '.'))
            or any(
                character in '<>:|?*' or character == chr(34)
                for character in part
            )
            or any(ord(character) < 32 or ord(character) == 127 for character in part)
        ):
            raise ValueError('An edit transaction contains an unsafe Windows path.')
    relative = Path(*pure.parts)
    if relative.is_absolute() or relative.drive:
        raise ValueError('An edit transaction contains an unsafe relative path.')
    return relative


def windows_case_insensitive_text(value: str) -> str:
    if os.name == 'nt':
        return ntpath.normcase(value)
    # Python's Unicode lower() performs multi-code-point expansions that the
    # Windows invariant mapping does not. Keep those characters unexpanded.
    return ''.join(
        lowered if len(lowered := character.lower()) == 1 else character
        for character in value
    )


def edit_relative_path_key(relative: Path) -> str:
    # NTFS comparisons are case-insensitive, but they do not use Unicode
    # case-fold expansions (for example, German sharp-s is not equal to SS).
    return PurePosixPath(*(
        windows_case_insensitive_text(part)
        for part in relative.parts
    )).as_posix()


def sync_directory_metadata(directory: Path, *, required: bool = False) -> None:
    # POSIX requires an explicit directory sync for durable rename metadata.
    if os.name == 'nt':
        return
    directory_fd: int | None = None
    try:
        directory_fd = os.open(str(directory), os.O_RDONLY)
        os.fsync(directory_fd)
    except OSError as exc:
        unsupported = {
            errno.EINVAL,
            getattr(errno, 'ENOTSUP', errno.EINVAL),
            getattr(errno, 'EOPNOTSUPP', errno.EINVAL),
        }
        if required and exc.errno not in unsupported:
            raise
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def sync_file_data(path: Path) -> None:
    with path.open('r+b') as stream:
        stream.flush()
        os.fsync(stream.fileno())


def sync_rename_metadata(
    source: Path,
    destination: Path,
    *,
    required: bool = False,
) -> None:
    sync_directory_metadata(source.parent, required=required)
    if destination.parent != source.parent:
        sync_directory_metadata(destination.parent, required=required)


def windows_extended_path(path: Path) -> str:
    supplied = os.fspath(path)
    if supplied.lower().startswith('\\\\.\\'):
        raise OSError('Windows device namespace paths are not supported.')
    raw = os.path.abspath(supplied)
    lowered = raw.lower()
    if lowered.startswith('\\\\.\\'):
        raise OSError('Windows device namespace paths are not supported.')
    if lowered.startswith('\\\\?\\'):
        extended_tail = raw[4:]
        if not (
            re.match(r'^[A-Za-z]:\\', extended_tail)
            or extended_tail.lower().startswith('unc\\')
        ):
            raise OSError('Unsupported Windows extended namespace path.')
        return raw
    if raw.startswith('\\\\'):
        return '\\\\?\\UNC\\' + raw.lstrip('\\')
    return '\\\\?\\' + raw


def windows_move_file_write_through(
    source: Path,
    destination: Path,
    *,
    replace_existing: bool,
) -> None:
    move_file_ex = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file_ex.restype = ctypes.c_int
    flags = 0x8 | (0x1 if replace_existing else 0)
    if not move_file_ex(
        windows_extended_path(source),
        windows_extended_path(destination),
        flags,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def posix_move_no_replace(source: Path, destination: Path) -> None:
    rename_function = None
    rename_flags = 0
    if sys.platform.startswith('linux'):
        rename_function = getattr(ctypes.CDLL(None, use_errno=True), 'renameat2', None)
        rename_flags = 0x1
    elif sys.platform == 'darwin':
        rename_function = getattr(ctypes.CDLL(None, use_errno=True), 'renamex_np', None)
        rename_flags = 0x4
    if rename_function is not None:
        rename_function.argtypes = (
            [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            if sys.platform.startswith('linux')
            else [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        )
        rename_function.restype = ctypes.c_int
        encoded_source = os.fsencode(source)
        encoded_destination = os.fsencode(destination)
        result = (
            rename_function(-100, encoded_source, -100, encoded_destination, rename_flags)
            if sys.platform.startswith('linux')
            else rename_function(encoded_source, encoded_destination, rename_flags)
        )
        if result == 0:
            return
        failure = ctypes.get_errno()
        if failure not in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise OSError(failure, os.strerror(failure), str(destination))
    if source.is_file() and not source.is_symlink():
        os.link(source, destination)
        source.unlink()
        return
    raise OSError(
        errno.ENOTSUP,
        'Atomic no-replace directory rename is not supported on this platform.',
        str(destination),
    )


def durable_move(
    source: Path,
    destination: Path,
    *,
    replace_existing: bool = True,
) -> None:
    source = Path(source)
    destination = Path(destination)
    if os.name == 'nt' and os.replace is _ORIGINAL_OS_REPLACE:
        windows_move_file_write_through(
            source,
            destination,
            replace_existing=replace_existing,
        )
    elif (
        os.name != 'nt'
        and not replace_existing
        and os.replace is _ORIGINAL_OS_REPLACE
    ):
        posix_move_no_replace(source, destination)
    else:
        if not replace_existing and (
            destination.exists() or destination.is_symlink()
        ):
            raise FileExistsError(str(destination))
        os.replace(source, destination)
    sync_rename_metadata(source, destination, required=True)


def edit_staging_identity(path: Path) -> tuple[int, int]:
    candidate = Path(os.path.abspath(os.fspath(path)))
    if path_is_link_or_reparse(candidate) or not candidate.is_dir():
        raise OSError('The edit staging path is not a local directory.')
    metadata = candidate.lstat()
    inode = int(metadata.st_ino)
    if not inode:
        raise OSError('The filesystem does not provide a stable staging identity.')
    return int(metadata.st_dev), inode


def edit_cleanup_entry_identity(path: Path) -> tuple[str, int, int]:
    if path_is_link_or_reparse(path):
        raise OSError('An edit cleanup entry is a symbolic link or reparse point.')
    metadata = path.lstat()
    if stat.S_ISDIR(metadata.st_mode):
        kind = 'directory'
    elif stat.S_ISREG(metadata.st_mode):
        kind = 'file'
    else:
        raise OSError('An edit cleanup entry has an unsupported filesystem type.')
    inode = int(metadata.st_ino)
    if not inode:
        raise OSError('An edit cleanup entry has no stable filesystem identity.')
    return kind, int(metadata.st_dev), inode


def edit_cleanup_allowed_directories(file_names: set[str]) -> set[str]:
    directories: set[str] = set()
    for file_name in file_names:
        relative = PurePosixPath(file_name)
        for parent in relative.parents:
            if parent != PurePosixPath('.'):
                directories.add(parent.as_posix())
    return directories


def capture_edit_cleanup_inventory(
    staging_root: Path,
    file_options: dict[str, set[tuple[int, str]]],
) -> dict[str, Any]:
    root = Path(os.path.abspath(os.fspath(staging_root)))
    root_identity = edit_staging_identity(root)
    allowed_files = set(file_options)
    allowed_directories = edit_cleanup_allowed_directories(allowed_files)
    entries: dict[str, tuple[str, int, int]] = {}
    seen_keys: set[str] = set()
    ensure_staging_tree_has_no_reparse_points(root)
    for candidate in root.rglob('*'):
        relative = candidate.relative_to(root)
        relative_name = PurePosixPath(*relative.parts).as_posix()
        relative_key = edit_relative_path_key(relative)
        if relative_key in seen_keys:
            raise OSError('An edit cleanup tree contains a Windows path collision.')
        seen_keys.add(relative_key)
        entry_identity = edit_cleanup_entry_identity(candidate)
        kind = entry_identity[0]
        if kind == 'directory':
            if relative_name not in allowed_directories:
                raise OSError('An edit cleanup tree contains an unowned directory.')
        else:
            options = file_options.get(relative_name)
            if options is None:
                raise OSError('An edit cleanup tree contains an unowned file.')
            if not any(
                file_matches_fingerprint(candidate, sha256, size)
                for size, sha256 in options
            ):
                raise OSError('An edit cleanup file changed ownership or content.')
        entries[relative_name] = entry_identity
    if edit_staging_identity(root) != root_identity:
        raise OSError('An edit cleanup tree changed while it was inventoried.')
    return {
        'root_identity': root_identity,
        'entries': entries,
        'file_options': {
            name: set(options)
            for name, options in file_options.items()
        },
    }


def validate_edit_cleanup_inventory(
    staging_root: Path,
    inventory: dict[str, Any],
) -> None:
    expected_root = inventory.get('root_identity')
    expected_entries = inventory.get('entries')
    file_options = inventory.get('file_options')
    if (
        not isinstance(expected_root, tuple)
        or len(expected_root) != 2
        or not isinstance(expected_entries, dict)
        or not isinstance(file_options, dict)
    ):
        raise OSError('The edit cleanup inventory is invalid.')
    current = capture_edit_cleanup_inventory(staging_root, file_options)
    if current['root_identity'] != expected_root or current['entries'] != expected_entries:
        raise OSError('The edit cleanup inventory changed before removal.')


@contextmanager
def hold_edit_directory_against_rename(
    path: Path,
    expected_identity: tuple[int, int],
):
    candidate = Path(os.path.abspath(os.fspath(path)))
    if os.name == 'nt':
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        create_file.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        handle = create_file(
            windows_extended_path(candidate),
            0x80,
            0x1 | 0x2,
            None,
            3,
            0x02000000 | 0x00200000,
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if handle in {None, invalid_handle}:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if edit_staging_identity(candidate) != expected_identity:
                raise OSError('The edit staging identity changed before it was locked.')
            yield None
        finally:
            close_handle(handle)
        return

    flags = os.O_RDONLY
    flags |= int(getattr(os, 'O_DIRECTORY', 0))
    flags |= int(getattr(os, 'O_NOFOLLOW', 0))
    directory_fd = os.open(str(candidate), flags)
    try:
        metadata = os.fstat(directory_fd)
        actual_identity = (int(metadata.st_dev), int(metadata.st_ino))
        if actual_identity != expected_identity:
            raise OSError('The edit staging identity changed before it was locked.')
        yield directory_fd
    finally:
        os.close(directory_fd)


def durable_write_json(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, target)
        with target.open('r+b') as stream:
            os.fsync(stream.fileno())
        sync_directory_metadata(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def write_edit_preparation_marker(
    staging_dir: Path,
    output_dir: Path,
    *,
    item_id: str,
    expected_revision: int,
    previous_output_dir: Path,
    staged_files: list[Path] | None = None,
) -> Path:
    if path_is_link_or_reparse(staging_dir) or not staging_dir.is_dir():
        raise OSError('The edit staging directory must be a local directory.')
    staging_root = staging_dir.resolve()
    output_root = output_dir.resolve()
    if staging_root.parent != output_root:
        raise OSError('The edit staging directory is outside its output directory.')
    final_match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    preparing_match = re.fullmatch(
        r'\.edit-preparing-([0-9a-f]{32})-[0-9a-f]{32}',
        staging_root.name,
    )
    match = final_match or preparing_match
    if match is None:
        raise OSError('The edit staging directory name is invalid.')
    transaction_id = match.group(1)
    final_staging_name = f'.edit-staging-{transaction_id}'
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError('The edit transaction revision is invalid.')
    if (
        not isinstance(item_id, str)
        or not 1 <= len(item_id) <= 255
        or re.search(r'[\x00-\x1f]', item_id)
    ):
        raise ValueError('The edit transaction item ID is invalid.')
    for candidate in output_root.glob('.edit-staging-*'):
        if (
            candidate != staging_root
            and re.fullmatch(r'\.edit-staging-[0-9a-f]{32}', candidate.name)
        ):
            raise OSError('A previous edit transaction must be recovered before saving.')
    prepared_entries: list[dict[str, Any]] | None = None
    if staged_files is not None:
        if not 1 <= len(staged_files) <= MAX_EDIT_TRANSACTION_FILES:
            raise OSError('An edit preparation contains an invalid number of files.')
        prepared_entries = []
        seen_prepared: set[str] = set()
        for staged_path in staged_files:
            if path_is_link_or_reparse(staged_path):
                raise OSError('A prepared output file is a symbolic link or reparse point.')
            staged = staged_path.resolve()
            if not path_is_within(staged, staging_root) or not staged.is_file():
                raise OSError('A prepared output file is missing or outside staging.')
            relative = staged.relative_to(staging_root)
            relative_text = PurePosixPath(*relative.parts).as_posix()
            safe_relative = safe_edit_relative_path(relative_text)
            relative_key = edit_relative_path_key(safe_relative)
            if relative_key in seen_prepared:
                raise OSError('An edit preparation contains duplicate targets.')
            seen_prepared.add(relative_key)
            entry_identity = edit_cleanup_entry_identity(staged)
            prepared_entries.append({
                'relative_path': relative_text,
                'size': staged.stat().st_size,
                'sha256': file_sha256(staged),
                'device': entry_identity[1],
                'inode': entry_identity[2],
            })
    with database_connection() as connection:
        storage_id = edit_storage_id(connection)
        journal_secret = edit_journal_secret(connection)
    payload: dict[str, Any] = {
        'schema_version': EDIT_TRANSACTION_SCHEMA_VERSION,
        'kind': 'library-edit-preparation',
        'transaction_id': transaction_id,
        'final_staging_name': final_staging_name,
        'storage_id': storage_id,
        'item_id': item_id,
        'expected_revision': expected_revision,
        'output_dir': str(output_root),
        'previous_output_dir': str(previous_output_dir.resolve()),
        'created_at': utc_now_iso(),
    }
    if prepared_entries is not None:
        payload['files'] = prepared_entries
    payload['mac'] = edit_journal_mac(payload, journal_secret)
    marker = staging_root / EDIT_PREPARATION_MARKER_NAME
    durable_write_json(marker, payload)
    return marker


def write_edit_transaction_manifest(
    staging_dir: Path,
    output_dir: Path,
    staged_files: list[Path],
    *,
    item_id: str,
    expected_revision: int,
    previous_output_dir: Path,
) -> Path:
    if path_is_link_or_reparse(staging_dir) or not staging_dir.is_dir():
        raise OSError('The edit staging directory must be a local directory.')
    ensure_staging_tree_has_no_reparse_points(staging_dir)
    staging_root = staging_dir.resolve()
    output_root = output_dir.resolve()
    if staging_root.parent != output_root:
        raise OSError('The edit staging directory is outside its output directory.')
    match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    if match is None:
        raise OSError('The edit staging directory name is invalid.')
    for candidate in output_root.glob('.edit-staging-*'):
        if (
            candidate != staging_root
            and re.fullmatch(r'\.edit-staging-[0-9a-f]{32}', candidate.name)
        ):
            raise OSError('A previous edit transaction must be recovered before saving.')
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError('The edit transaction revision is invalid.')
    if not 1 <= len(staged_files) <= MAX_EDIT_TRANSACTION_FILES:
        raise OSError('The edit transaction contains an invalid number of files.')

    entries: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for staged_path in staged_files:
        if staged_path.is_symlink():
            raise OSError('A staged output file must not be a symbolic link.')
        staged = staged_path.resolve()
        if not path_is_within(staged, staging_root) or not staged.is_file():
            raise OSError('A staged output file is missing or outside the staging directory.')
        relative = staged.relative_to(staging_root)
        relative_text = PurePosixPath(*relative.parts).as_posix()
        safe_relative = safe_edit_relative_path(relative_text)
        if (
            safe_relative.parts[0] in {'.previous', '.discarded'}
            or safe_relative.name == EDIT_TRANSACTION_MANIFEST_NAME
        ):
            raise OSError('A staged output file uses a reserved transaction path.')
        target = output_root / safe_relative
        target_key = edit_relative_path_key(safe_relative)
        if target_key in seen_targets:
            raise OSError('Duplicate staged output target.')
        seen_targets.add(target_key)
        if not path_is_within(target, output_root):
            raise OSError('A staged output target escapes the output directory.')
        if target.is_symlink():
            raise OSError('A staged output target must not be a symbolic link.')
        if target.exists() and not target.is_file():
            raise OSError('A staged output target is not a file.')
        with staged.open('r+b') as stream:
            os.fsync(stream.fileno())
        had_previous = target.exists() or target.is_symlink()
        previous_sha256 = ''
        previous_size: int | None = None
        if had_previous and target.is_file():
            previous_size = target.stat().st_size
            previous_sha256 = file_sha256(target)
        entries.append({
            'relative_path': relative_text,
            'had_previous': had_previous,
            'new_size': staged.stat().st_size,
            'new_sha256': file_sha256(staged),
            'previous_size': previous_size,
            'previous_sha256': previous_sha256,
        })

    with database_connection() as connection:
        storage_id = edit_storage_id(connection)
        journal_secret = edit_journal_secret(connection)
    manifest = staging_root / EDIT_TRANSACTION_MANIFEST_NAME
    payload: dict[str, Any] = {
        'schema_version': EDIT_TRANSACTION_SCHEMA_VERSION,
        'kind': 'library-edit',
        'transaction_id': match.group(1),
        'storage_id': storage_id,
        'item_id': item_id,
        'expected_revision': expected_revision,
        'target_revision': expected_revision + 1,
        'output_dir': str(output_root),
        'previous_output_dir': str(previous_output_dir.resolve()),
        'created_at': utc_now_iso(),
        'files': entries,
    }
    payload['mac'] = edit_journal_mac(payload, journal_secret)
    durable_write_json(manifest, payload)
    (staging_root / EDIT_PREPARATION_MARKER_NAME).unlink(missing_ok=True)
    sync_directory_metadata(staging_root)
    return manifest


@contextmanager
def open_windows_edit_entry_for_deletion(
    path: Path,
    expected_entry: tuple[str, int, int],
):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int
    handle = create_file(
        windows_extended_path(path),
        0x00010000 | 0x80,
        0x1 | 0x2,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle in {None, invalid_handle}:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if edit_cleanup_entry_identity(path) != expected_entry:
            raise OSError('An edit cleanup entry changed before its delete handle opened.')
        yield handle
    finally:
        close_handle(handle)


def mark_windows_handle_for_deletion(handle: int) -> None:
    class FileDispositionInfo(ctypes.Structure):
        _fields_ = [('delete_file', ctypes.c_int)]

    set_information = ctypes.WinDLL(
        'kernel32',
        use_last_error=True,
    ).SetFileInformationByHandle
    set_information.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    set_information.restype = ctypes.c_int
    disposition = FileDispositionInfo(1)
    if not set_information(
        handle,
        4,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def remove_windows_edit_directory_contents(
    directory: Path,
    expected_identity: tuple[int, int],
    *,
    transaction_root: Path,
    expected_entries: dict[str, tuple[str, int, int]],
    top_level: bool,
) -> None:
    expected_directory = ('directory', expected_identity[0], expected_identity[1])

    def journal_order(child: Path) -> tuple[int, str]:
        if top_level and child.name == EDIT_PREPARATION_MARKER_NAME:
            return 1, child.name
        if top_level and child.name == EDIT_TRANSACTION_MANIFEST_NAME:
            return 2, child.name
        return 0, child.name

    with open_windows_edit_entry_for_deletion(
        directory,
        expected_directory,
    ) as directory_handle:
        children = sorted(list(directory.iterdir()), key=journal_order)
        for child in children:
            relative_name = PurePosixPath(
                *child.relative_to(transaction_root).parts
            ).as_posix()
            expected_entry = expected_entries.get(relative_name)
            if expected_entry is None:
                raise OSError('An unowned entry appeared during edit cleanup.')
            if expected_entry[0] == 'directory':
                remove_windows_edit_directory_contents(
                    child,
                    (expected_entry[1], expected_entry[2]),
                    transaction_root=transaction_root,
                    expected_entries=expected_entries,
                    top_level=False,
                )
            else:
                with open_windows_edit_entry_for_deletion(
                    child,
                    expected_entry,
                ) as child_handle:
                    mark_windows_handle_for_deletion(child_handle)
            expected_entries.pop(relative_name, None)
        if list(directory.iterdir()):
            raise OSError('A new entry appeared while edit cleanup was finishing.')
        mark_windows_handle_for_deletion(directory_handle)


def remove_edit_directory_contents(
    directory: Path,
    expected_identity: tuple[int, int],
    *,
    transaction_root: Path,
    expected_entries: dict[str, tuple[str, int, int]],
    top_level: bool = True,
) -> None:
    if os.name == 'nt':
        remove_windows_edit_directory_contents(
            directory,
            expected_identity,
            transaction_root=transaction_root,
            expected_entries=expected_entries,
            top_level=top_level,
        )
        return

    def journal_order(name: str) -> tuple[int, str]:
        if top_level and name == EDIT_PREPARATION_MARKER_NAME:
            return 1, name
        if top_level and name == EDIT_TRANSACTION_MANIFEST_NAME:
            return 2, name
        return 0, name

    with hold_edit_directory_against_rename(
        directory,
        expected_identity,
    ) as directory_fd:
        if directory_fd is not None:
            entries = sorted(list(os.scandir(directory_fd)), key=lambda item: journal_order(item.name))
            for entry in entries:
                child = directory / entry.name
                relative_name = PurePosixPath(
                    *child.relative_to(transaction_root).parts
                ).as_posix()
                expected_entry = expected_entries.get(relative_name)
                if expected_entry is None:
                    raise OSError('An unowned entry appeared during edit cleanup.')
                if edit_cleanup_entry_identity(child) != expected_entry:
                    raise OSError('An edit cleanup entry changed identity before removal.')
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(metadata.st_mode):
                    flags = os.O_RDONLY
                    flags |= int(getattr(os, 'O_DIRECTORY', 0))
                    flags |= int(getattr(os, 'O_NOFOLLOW', 0))
                    child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
                    try:
                        child_metadata = os.fstat(child_fd)
                        child_identity = (
                            int(child_metadata.st_dev),
                            int(child_metadata.st_ino),
                        )
                    finally:
                        os.close(child_fd)
                    remove_edit_directory_contents(
                        child,
                        child_identity,
                        transaction_root=transaction_root,
                        expected_entries=expected_entries,
                        top_level=False,
                    )
                    os.rmdir(entry.name, dir_fd=directory_fd)
                    expected_entries.pop(relative_name, None)
                else:
                    os.unlink(entry.name, dir_fd=directory_fd)
                    expected_entries.pop(relative_name, None)
            if list(os.scandir(directory_fd)):
                raise OSError('A new entry appeared while edit cleanup was finishing.')
            os.fsync(directory_fd)
            return

        children = sorted(list(directory.iterdir()), key=lambda child: journal_order(child.name))
        for child in children:
            relative_name = PurePosixPath(
                *child.relative_to(transaction_root).parts
            ).as_posix()
            expected_entry = expected_entries.get(relative_name)
            if expected_entry is None:
                raise OSError('An unowned entry appeared during edit cleanup.')
            if edit_cleanup_entry_identity(child) != expected_entry:
                raise OSError('An edit cleanup entry changed identity before removal.')
            try:
                metadata = child.lstat()
            except FileNotFoundError:
                continue
            if path_is_link_or_reparse(child):
                if stat.S_ISDIR(metadata.st_mode):
                    child.rmdir()
                else:
                    child.unlink()
                expected_entries.pop(relative_name, None)
                continue
            if stat.S_ISDIR(metadata.st_mode):
                child_identity = (int(metadata.st_dev), int(metadata.st_ino))
                if not child_identity[1]:
                    raise OSError('A cleanup child has no stable filesystem identity.')
                remove_edit_directory_contents(
                    child,
                    child_identity,
                    transaction_root=transaction_root,
                    expected_entries=expected_entries,
                    top_level=False,
                )
                if edit_staging_identity(child) != child_identity:
                    raise OSError('A cleanup child identity changed before removal.')
                child.rmdir()
                expected_entries.pop(relative_name, None)
            else:
                child.unlink()
                expected_entries.pop(relative_name, None)
        if list(directory.iterdir()):
            raise OSError('A new entry appeared while edit cleanup was finishing.')
        sync_directory_metadata(directory, required=True)


def cleanup_edit_staging(
    staging_root: Path,
    *,
    expected_identity: tuple[int, int],
    inventory: dict[str, Any],
) -> list[str]:
    original_root = Path(os.path.abspath(os.fspath(staging_root)))
    errors: list[str] = []
    journal_snapshots: dict[str, tuple[tuple[str, int, int], bytes]] = {}
    try:
        with hold_edit_directory_against_rename(original_root, expected_identity):
            validate_edit_cleanup_inventory(original_root, inventory)
            ensure_staging_tree_has_no_reparse_points(original_root)
            for name in (EDIT_TRANSACTION_MANIFEST_NAME, EDIT_PREPARATION_MARKER_NAME):
                journal = original_root / name
                if journal.is_file() and not path_is_link_or_reparse(journal):
                    journal_snapshots[name] = (
                        edit_cleanup_entry_identity(journal),
                        journal.read_bytes(),
                    )
            if edit_staging_identity(original_root) != expected_identity:
                raise OSError('The edit staging identity changed during cleanup preflight.')
    except OSError as exc:
        return [str(exc)]

    quarantine = original_root.with_name(
        f'.edit-cleanup-{original_root.name.removeprefix(chr(46))}-{uuid.uuid4().hex}'
    )

    def preserve_journal_snapshot(root: Path, name: str, content: bytes) -> Path:
        recovery = root / (
            f'.{name}.authenticated-{uuid.uuid4().hex}.recovery'
        )
        temporary = root / f'.{recovery.name}.{uuid.uuid4().hex}.tmp'
        with temporary.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, recovery, replace_existing=False)
        return recovery

    def restore_journals(root: Path) -> None:
        if edit_staging_identity(root) != expected_identity:
            raise OSError('The cleanup quarantine no longer belongs to this transaction.')
        with hold_edit_directory_against_rename(root, expected_identity):
            for name, (original_entry_identity, content) in journal_snapshots.items():
                target = root / name
                if target.exists() or target.is_symlink():
                    try:
                        target_matches = (
                            edit_cleanup_entry_identity(target) == original_entry_identity
                            and target.read_bytes() == content
                        )
                    except OSError:
                        target_matches = False
                    if target_matches:
                        continue
                    recovery = preserve_journal_snapshot(root, name, content)
                    raise OSError(
                        'A conflicting journal appeared during cleanup; the authenticated '
                        f'snapshot was retained at {recovery}.'
                    )
                temporary = root / f'.{name}.{uuid.uuid4().hex}.tmp'
                with temporary.open('xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    durable_move(temporary, target, replace_existing=False)
                except OSError:
                    recovery = preserve_journal_snapshot(root, name, content)
                    raise OSError(
                        'A journal could not be restored without replacement; the '
                        f'authenticated snapshot was retained at {recovery}.'
                    )
                if target.read_bytes() != content:
                    recovery = preserve_journal_snapshot(root, name, content)
                    raise OSError(
                        'A restored journal changed unexpectedly; the authenticated '
                        f'snapshot was retained at {recovery}.'
                    )

    def restore_quarantine() -> None:
        if not path_entry_exists(quarantine):
            return
        try:
            if edit_staging_identity(quarantine) != expected_identity:
                raise OSError('The cleanup quarantine was replaced; it was left untouched.')
            restore_journals(quarantine)
        except OSError as exc:
            errors.append(f'{quarantine}: could not preserve cleanup quarantine: {exc}')

    try:
        durable_move(original_root, quarantine, replace_existing=False)
    except OSError as exc:
        errors.append(f'{original_root}: could not quarantine edit staging: {exc}')
        if path_entry_exists(quarantine):
            restore_quarantine()
        return errors
    try:
        if edit_staging_identity(quarantine) != expected_identity:
            raise OSError('The edit staging identity changed before cleanup.')
        validate_edit_cleanup_inventory(quarantine, inventory)
        expected_entries = dict(inventory['entries'])
        remove_edit_directory_contents(
            quarantine,
            expected_identity,
            transaction_root=quarantine,
            expected_entries=expected_entries,
        )
        if expected_entries:
            raise OSError('The edit cleanup inventory was not removed completely.')
        if os.name == 'nt':
            if path_entry_exists(quarantine):
                raise OSError('The handle-bound edit cleanup did not remove its root.')
        else:
            if edit_staging_identity(quarantine) != expected_identity:
                raise OSError('The edit staging identity changed before final removal.')
            quarantine.rmdir()
        sync_directory_metadata(quarantine.parent, required=True)
    except OSError as exc:
        errors.append(f'{quarantine}: {exc}')
        restore_quarantine()
    return errors


def file_matches_fingerprint(path: Path, expected_sha256: str, expected_size: int) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        if path.stat().st_size != expected_size:
            return False
        return secrets.compare_digest(file_sha256(path), expected_sha256)
    except OSError:
        return False


def path_is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, 'isjunction', None)
    if callable(is_junction) and is_junction(path):
        return True
    try:
        attributes = int(getattr(path.lstat(), 'st_file_attributes', 0) or 0)
    except OSError:
        return False
    reparse_flag = int(getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    return bool(attributes & reparse_flag)


def path_has_reparse_ancestor(path: Path) -> bool:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    if not parts:
        return False
    current = Path(parts[0])
    start = 1
    if not absolute.anchor:
        current = Path()
        start = 0
    for part in parts[start:]:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if path_is_link_or_reparse(current):
            return True
    return False


def ensure_staging_tree_has_no_reparse_points(staging_root: Path) -> None:
    if path_is_link_or_reparse(staging_root):
        raise OSError('An edit staging directory is a symbolic link or reparse point.')
    if not staging_root.is_dir():
        raise OSError('An edit staging path is not a directory.')
    for current, directory_names, file_names in os.walk(
        staging_root, topdown=True, followlinks=False
    ):
        for name in [*directory_names, *file_names]:
            candidate = Path(current) / name
            if path_is_link_or_reparse(candidate):
                raise OSError('An edit staging tree contains a symbolic link or reparse point.')


def load_edit_transaction_manifest(
    staging_dir: Path,
    *,
    expected_storage_id: str,
    expected_secret: bytes,
) -> dict[str, Any]:
    try:
        staging_identity = edit_staging_identity(staging_dir)
        ensure_staging_tree_has_no_reparse_points(staging_dir)
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    if staging_dir.is_symlink() or not staging_dir.is_dir():
        raise ValueError('An edit staging path is not a local directory.')
    staging_root = staging_dir.resolve()
    match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    if match is None:
        raise ValueError('An edit staging directory name is invalid.')
    manifest_path = staging_root / EDIT_TRANSACTION_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('An edit transaction manifest is missing or unsafe.')
    if manifest_path.stat().st_size > MAX_EDIT_TRANSACTION_MANIFEST_BYTES:
        raise ValueError('An edit transaction manifest is too large.')
    try:
        manifest_content = manifest_path.read_bytes()
        payload = json.loads(manifest_content.decode('utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('An edit transaction manifest cannot be read.') from exc
    if not isinstance(payload, dict):
        raise ValueError('An edit transaction manifest is not an object.')
    if payload.get('schema_version') != EDIT_TRANSACTION_SCHEMA_VERSION:
        raise ValueError('An edit transaction manifest has an unsupported schema.')
    if payload.get('kind') != 'library-edit':
        raise ValueError('An edit transaction manifest has an invalid kind.')
    if payload.get('transaction_id') != match.group(1):
        raise ValueError('An edit transaction ID does not match its directory.')
    if payload.get('storage_id') != expected_storage_id:
        raise ValueError('An edit transaction belongs to a different database.')
    supplied_mac = payload.get('mac')
    if (
        not isinstance(supplied_mac, str)
        or not re.fullmatch(r'[0-9a-f]{64}', supplied_mac)
        or not hmac.compare_digest(
            supplied_mac,
            edit_journal_mac(payload, expected_secret),
        )
    ):
        raise ValueError('An edit transaction manifest authentication failed.')

    item_id = payload.get('item_id')
    if (
        not isinstance(item_id, str)
        or not 1 <= len(item_id) <= 255
        or re.search(r'[\x00-\x1f]', item_id)
    ):
        raise ValueError('An edit transaction item ID is invalid.')
    expected_revision = payload.get('expected_revision')
    target_revision = payload.get('target_revision')
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
        or isinstance(target_revision, bool)
        or not isinstance(target_revision, int)
        or target_revision != expected_revision + 1
    ):
        raise ValueError('An edit transaction revision is invalid.')
    raw_output_dir = payload.get('output_dir')
    if not isinstance(raw_output_dir, str) or not raw_output_dir:
        raise ValueError('An edit transaction output directory is invalid.')
    output_root = Path(raw_output_dir).resolve()
    if output_root != staging_root.parent:
        raise ValueError('An edit transaction output directory does not match its location.')
    raw_previous_output_dir = payload.get('previous_output_dir')
    if not isinstance(raw_previous_output_dir, str) or not raw_previous_output_dir:
        raise ValueError('An edit transaction previous output directory is invalid.')
    previous_output_root = Path(raw_previous_output_dir).resolve()

    raw_files = payload.get('files')
    if not isinstance(raw_files, list) or not 1 <= len(raw_files) <= MAX_EDIT_TRANSACTION_FILES:
        raise ValueError('An edit transaction file list is invalid.')
    resolved_files: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed_files = {EDIT_TRANSACTION_MANIFEST_NAME}
    cleanup_file_options: dict[str, set[tuple[int, str]]] = {
        EDIT_TRANSACTION_MANIFEST_NAME: {
            (len(manifest_content), hashlib.sha256(manifest_content).hexdigest())
        },
    }
    preparation_marker = staging_root / EDIT_PREPARATION_MARKER_NAME
    if path_entry_exists(preparation_marker):
        if (
            path_is_link_or_reparse(preparation_marker)
            or not preparation_marker.is_file()
            or preparation_marker.stat().st_size > MAX_EDIT_TRANSACTION_MANIFEST_BYTES
        ):
            raise ValueError('A retained edit preparation marker is unsafe.')
        try:
            preparation_content = preparation_marker.read_bytes()
            preparation_payload = json.loads(preparation_content.decode('utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('A retained edit preparation marker cannot be read.') from exc
        supplied_preparation_mac = (
            preparation_payload.get('mac')
            if isinstance(preparation_payload, dict)
            else None
        )
        if (
            not isinstance(preparation_payload, dict)
            or preparation_payload.get('schema_version') != EDIT_TRANSACTION_SCHEMA_VERSION
            or preparation_payload.get('kind') != 'library-edit-preparation'
            or preparation_payload.get('transaction_id') != match.group(1)
            or preparation_payload.get('storage_id') != expected_storage_id
            or preparation_payload.get('item_id') != item_id
            or preparation_payload.get('expected_revision') != expected_revision
            or not isinstance(supplied_preparation_mac, str)
            or not re.fullmatch(r'[0-9a-f]{64}', supplied_preparation_mac)
            or not hmac.compare_digest(
                supplied_preparation_mac,
                edit_journal_mac(preparation_payload, expected_secret),
            )
        ):
            raise ValueError('A retained edit preparation marker authentication failed.')
        allowed_files.add(EDIT_PREPARATION_MARKER_NAME)
        cleanup_file_options[EDIT_PREPARATION_MARKER_NAME] = {
            (
                len(preparation_content),
                hashlib.sha256(preparation_content).hexdigest(),
            )
        }
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            raise ValueError('An edit transaction file entry is invalid.')
        relative = safe_edit_relative_path(raw_entry.get('relative_path'))
        relative_text = PurePosixPath(*relative.parts).as_posix()
        relative_key = edit_relative_path_key(relative)
        if relative_key in seen:
            raise ValueError('An edit transaction contains duplicate targets.')
        seen.add(relative_key)
        had_previous = raw_entry.get('had_previous')
        new_size = raw_entry.get('new_size')
        new_sha256 = raw_entry.get('new_sha256')
        previous_size = raw_entry.get('previous_size')
        previous_sha256 = raw_entry.get('previous_sha256')
        if not isinstance(had_previous, bool):
            raise ValueError('An edit transaction previous-file flag is invalid.')
        if isinstance(new_size, bool) or not isinstance(new_size, int) or new_size < 0:
            raise ValueError('An edit transaction file size is invalid.')
        if not isinstance(new_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', new_sha256):
            raise ValueError('An edit transaction new-file fingerprint is invalid.')
        if not isinstance(previous_sha256, str) or (
            previous_sha256 and not re.fullmatch(r'[0-9a-f]{64}', previous_sha256)
        ):
            raise ValueError('An edit transaction previous-file fingerprint is invalid.')
        if previous_size is not None and (
            isinstance(previous_size, bool)
            or not isinstance(previous_size, int)
            or previous_size < 0
        ):
            raise ValueError('An edit transaction previous-file size is invalid.')
        if bool(previous_sha256) != (previous_size is not None):
            raise ValueError('An edit transaction previous-file identity is incomplete.')
        if had_previous != bool(previous_sha256):
            raise ValueError('An edit transaction previous-file identity is inconsistent.')
        target = output_root / relative
        staged = staging_root / relative
        backup = staging_root / '.previous' / relative
        discarded = staging_root / '.discarded' / relative
        if not path_is_within(target, output_root):
            raise ValueError('An edit transaction target escapes its output directory.')
        for internal in (staged, backup, discarded):
            if not path_is_within(internal, staging_root):
                raise ValueError('An edit transaction path escapes its staging directory.')
        allowed_files.update({
            relative_text,
            f'.previous/{relative_text}',
            f'.discarded/{relative_text}',
        })
        cleanup_file_options.setdefault(relative_text, set()).add(
            (new_size, new_sha256)
        )
        cleanup_file_options.setdefault(
            f'.discarded/{relative_text}',
            set(),
        ).add((new_size, new_sha256))
        if had_previous:
            cleanup_file_options.setdefault(
                f'.previous/{relative_text}',
                set(),
            ).add((previous_size, previous_sha256))
        resolved_files.append({
            'relative': relative,
            'had_previous': had_previous,
            'new_size': new_size,
            'new_sha256': new_sha256,
            'previous_size': previous_size,
            'previous_sha256': previous_sha256,
            'target': target,
            'staged': staged,
            'backup': backup,
            'discarded': discarded,
        })

    actual_seen: set[str] = set()
    for candidate in staging_root.rglob('*'):
        if path_is_link_or_reparse(candidate):
            raise ValueError('An edit transaction contains a symbolic link.')
        relative_path = candidate.relative_to(staging_root)
        actual_key = edit_relative_path_key(relative_path)
        if actual_key in actual_seen:
            raise ValueError('An edit transaction contains a Windows path collision.')
        actual_seen.add(actual_key)
        if candidate.is_file():
            relative_name = PurePosixPath(*relative_path.parts).as_posix()
            if relative_name not in allowed_files:
                raise ValueError('An edit transaction contains an unlisted file.')
    if edit_staging_identity(staging_root) != staging_identity:
        raise ValueError('An edit staging identity changed while its manifest was loaded.')
    payload['_output_root'] = output_root
    payload['_previous_output_root'] = previous_output_root
    payload['_resolved_files'] = resolved_files
    payload['_staging_identity'] = staging_identity
    payload['_cleanup_file_options'] = cleanup_file_options
    payload['_cleanup_inventory'] = capture_edit_cleanup_inventory(
        staging_root,
        cleanup_file_options,
    )
    return payload


def load_edit_preparation_marker(
    staging_dir: Path,
    *,
    expected_storage_id: str,
    expected_secret: bytes,
) -> dict[str, Any]:
    try:
        staging_identity = edit_staging_identity(staging_dir)
        ensure_staging_tree_has_no_reparse_points(staging_dir)
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    staging_root = staging_dir.resolve()
    final_match = re.fullmatch(r'\.edit-staging-([0-9a-f]{32})', staging_root.name)
    preparing_match = re.fullmatch(
        r'\.edit-preparing-([0-9a-f]{32})-[0-9a-f]{32}',
        staging_root.name,
    )
    match = final_match or preparing_match
    if match is None:
        raise ValueError('An edit preparation directory name is invalid.')
    marker = staging_root / EDIT_PREPARATION_MARKER_NAME
    if not marker.is_file() or path_is_link_or_reparse(marker):
        raise ValueError('An authenticated edit preparation marker is missing.')
    if marker.stat().st_size > MAX_EDIT_TRANSACTION_MANIFEST_BYTES:
        raise ValueError('An edit preparation marker is too large.')
    try:
        marker_content = marker.read_bytes()
        payload = json.loads(marker_content.decode('utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('An edit preparation marker cannot be read.') from exc
    if not isinstance(payload, dict):
        raise ValueError('An edit preparation marker is not an object.')
    if payload.get('schema_version') != EDIT_TRANSACTION_SCHEMA_VERSION:
        raise ValueError('An edit preparation marker has an unsupported schema.')
    if payload.get('kind') != 'library-edit-preparation':
        raise ValueError('An edit preparation marker has an invalid kind.')
    if payload.get('transaction_id') != match.group(1):
        raise ValueError('An edit preparation ID does not match its directory.')
    final_staging_name = payload.get('final_staging_name')
    expected_final_staging_name = f'.edit-staging-{match.group(1)}'
    if (
        final_staging_name not in {None, expected_final_staging_name}
        or preparing_match is not None
        and final_staging_name != expected_final_staging_name
    ):
        raise ValueError('An edit preparation final directory is invalid.')
    if payload.get('storage_id') != expected_storage_id:
        raise ValueError('An edit preparation belongs to a different database.')
    supplied_mac = payload.get('mac')
    if (
        not isinstance(supplied_mac, str)
        or not re.fullmatch(r'[0-9a-f]{64}', supplied_mac)
        or not hmac.compare_digest(
            supplied_mac,
            edit_journal_mac(payload, expected_secret),
        )
    ):
        raise ValueError('An edit preparation marker authentication failed.')
    item_id = payload.get('item_id')
    expected_revision = payload.get('expected_revision')
    if (
        not isinstance(item_id, str)
        or not 1 <= len(item_id) <= 255
        or re.search(r'[\x00-\x1f]', item_id)
        or isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError('An edit preparation identity is invalid.')
    raw_output_dir = payload.get('output_dir')
    raw_previous_output_dir = payload.get('previous_output_dir')
    if not isinstance(raw_output_dir, str) or not raw_output_dir:
        raise ValueError('An edit preparation output directory is invalid.')
    if not isinstance(raw_previous_output_dir, str) or not raw_previous_output_dir:
        raise ValueError('An edit preparation previous output directory is invalid.')
    output_root = Path(raw_output_dir).resolve()
    if output_root != staging_root.parent:
        raise ValueError('An edit preparation output directory does not match its location.')
    cleanup_file_options: dict[str, set[tuple[int, str]]] = {
        EDIT_PREPARATION_MARKER_NAME: {
            (len(marker_content), hashlib.sha256(marker_content).hexdigest())
        },
    }
    raw_files = payload.get('files')
    if raw_files is not None:
        if not isinstance(raw_files, list) or not 1 <= len(raw_files) <= MAX_EDIT_TRANSACTION_FILES:
            raise ValueError('An edit preparation file list is invalid.')
        seen_files: set[str] = set()
        for raw_entry in raw_files:
            if not isinstance(raw_entry, dict):
                raise ValueError('An edit preparation file entry is invalid.')
            relative = safe_edit_relative_path(raw_entry.get('relative_path'))
            relative_name = PurePosixPath(*relative.parts).as_posix()
            relative_key = edit_relative_path_key(relative)
            if relative_key in seen_files:
                raise ValueError('An edit preparation contains duplicate targets.')
            seen_files.add(relative_key)
            size = raw_entry.get('size')
            sha256 = raw_entry.get('sha256')
            device = raw_entry.get('device')
            inode = raw_entry.get('inode')
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size < 0
                or not isinstance(sha256, str)
                or not re.fullmatch(r'[0-9a-f]{64}', sha256)
                or isinstance(device, bool)
                or not isinstance(device, int)
                or device < 0
                or isinstance(inode, bool)
                or not isinstance(inode, int)
                or inode <= 0
            ):
                raise ValueError('An edit preparation file identity is invalid.')
            prepared_path = staging_root / relative
            if not path_is_within(prepared_path, staging_root):
                raise ValueError('An edit preparation file escapes staging.')
            if edit_cleanup_entry_identity(prepared_path) != ('file', device, inode):
                raise ValueError('An edit preparation file changed filesystem identity.')
            if not file_matches_fingerprint(prepared_path, sha256, size):
                raise ValueError('An edit preparation file changed content.')
            cleanup_file_options.setdefault(relative_name, set()).add((size, sha256))
    try:
        cleanup_inventory = capture_edit_cleanup_inventory(
            staging_root,
            cleanup_file_options,
        )
    except OSError as exc:
        raise ValueError(str(exc)) from exc
    if edit_staging_identity(staging_root) != staging_identity:
        raise ValueError('An edit staging identity changed while its marker was loaded.')
    payload['_output_root'] = output_root
    payload['_previous_output_root'] = Path(raw_previous_output_dir).resolve()
    payload['_staging_identity'] = staging_identity
    payload['_cleanup_file_options'] = cleanup_file_options
    payload['_cleanup_inventory'] = cleanup_inventory
    return payload


def path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def edit_transaction_cleanup_inventory(
    staging_root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    inventory = capture_edit_cleanup_inventory(
        staging_root,
        payload['_cleanup_file_options'],
    )
    if inventory['root_identity'] != payload['_staging_identity']:
        raise OSError('The edit staging identity changed before cleanup inventory refresh.')
    return inventory


def transaction_file_kind(path: Path, entry: dict[str, Any]) -> str:
    if not path_entry_exists(path):
        return 'missing'
    if file_matches_fingerprint(path, entry['new_sha256'], entry['new_size']):
        return 'new'
    previous_sha256 = entry['previous_sha256']
    previous_size = entry['previous_size']
    if previous_sha256 and file_matches_fingerprint(
        path, previous_sha256, previous_size
    ):
        return 'previous'
    return 'unknown'


def preflight_rollback_edit_transaction(
    payload: dict[str, Any],
) -> list[tuple[dict[str, Any], str, str, str, str]]:
    states: list[tuple[dict[str, Any], str, str, str, str]] = []
    for entry in payload['_resolved_files']:
        target_kind = transaction_file_kind(entry['target'], entry)
        staged_kind = transaction_file_kind(entry['staged'], entry)
        backup_kind = transaction_file_kind(entry['backup'], entry)
        discarded_kind = transaction_file_kind(entry['discarded'], entry)
        if staged_kind not in {'missing', 'new'}:
            raise OSError('An edit transaction staged file was changed externally.')
        if discarded_kind not in {'missing', 'new'}:
            raise OSError('An edit transaction discarded file was changed externally.')
        if entry['had_previous']:
            if target_kind not in {'missing', 'new', 'previous'}:
                raise OSError('An edit transaction target was changed externally.')
            if backup_kind not in {'missing', 'previous'}:
                raise OSError('An edit transaction backup was changed externally.')
            if target_kind != 'previous' and backup_kind != 'previous':
                raise OSError('An edit transaction lost its previous output.')
        else:
            if target_kind not in {'missing', 'new'}:
                raise OSError('A new edit target was changed externally.')
            if backup_kind != 'missing':
                raise OSError('A new edit transaction has an unexpected backup.')
        states.append((entry, target_kind, staged_kind, backup_kind, discarded_kind))
    return states


def discard_transaction_target(entry: dict[str, Any]) -> None:
    target = entry['target']
    discarded = entry['discarded']
    if path_entry_exists(discarded):
        if not file_matches_fingerprint(
            discarded, entry['new_sha256'], entry['new_size']
        ):
            raise OSError('An edit transaction has a conflicting discarded file.')
        if not file_matches_fingerprint(
            target, entry['new_sha256'], entry['new_size']
        ):
            raise OSError('An edit transaction target was changed externally.')
        target.unlink()
        sync_directory_metadata(target.parent)
        return
    discarded.parent.mkdir(parents=True, exist_ok=True)
    durable_move(target, discarded)
    sync_rename_metadata(target, discarded)


def rollback_edit_transaction(staging_root: Path, payload: dict[str, Any]) -> None:
    states = preflight_rollback_edit_transaction(payload)
    for entry, target_kind, _, backup_kind, _ in reversed(states):
        target = entry['target']
        backup = entry['backup']
        had_previous = entry['had_previous']
        if had_previous:
            if target_kind == 'previous':
                if not file_matches_fingerprint(
                    target, entry['previous_sha256'], entry['previous_size']
                ):
                    raise OSError('An edit target changed after recovery preflight.')
                if backup_kind == 'previous' and not file_matches_fingerprint(
                    backup, entry['previous_sha256'], entry['previous_size']
                ):
                    raise OSError('An edit backup changed after recovery preflight.')
                continue
            if backup_kind != 'previous' or not file_matches_fingerprint(
                backup, entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('An edit backup changed after recovery preflight.')
            if target_kind == 'new':
                if not file_matches_fingerprint(
                    target, entry['new_sha256'], entry['new_size']
                ):
                    raise OSError('An edit target changed after recovery preflight.')
                discard_transaction_target(entry)
            elif path_entry_exists(target):
                raise OSError('An edit target appeared after recovery preflight.')
            target.parent.mkdir(parents=True, exist_ok=True)
            durable_move(backup, target)
            sync_rename_metadata(backup, target)
            if not file_matches_fingerprint(
                target, entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('An edit transaction backup could not be restored exactly.')
            continue

        if target_kind == 'new':
            if not file_matches_fingerprint(
                target, entry['new_sha256'], entry['new_size']
            ):
                raise OSError('A new edit target changed after recovery preflight.')
            discard_transaction_target(entry)
        elif path_entry_exists(target):
            raise OSError('A new edit target appeared after recovery preflight.')

    cleanup_errors = cleanup_edit_staging(
        staging_root,
        expected_identity=payload['_staging_identity'],
        inventory=edit_transaction_cleanup_inventory(staging_root, payload),
    )
    if cleanup_errors:
        raise OSError('Edit rollback cleanup failed: ' + '; '.join(cleanup_errors))


def finish_committed_edit_transaction(
    staging_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    states: list[tuple[dict[str, Any], str, str, str, str]] = []
    for entry in payload['_resolved_files']:
        target_kind = transaction_file_kind(entry['target'], entry)
        staged_kind = transaction_file_kind(entry['staged'], entry)
        backup_kind = transaction_file_kind(entry['backup'], entry)
        discarded_kind = transaction_file_kind(entry['discarded'], entry)
        if staged_kind not in {'missing', 'new'}:
            raise OSError('A committed edit staged file was changed externally.')
        if backup_kind not in {'missing', 'previous'}:
            raise OSError('A committed edit backup was changed externally.')
        if discarded_kind not in {'missing', 'new'}:
            raise OSError('A committed edit discarded file was changed externally.')
        if target_kind == 'previous' and not entry['had_previous']:
            raise OSError('A committed new target was changed externally.')
        if target_kind not in {'new', 'missing', 'previous'}:
            raise OSError('A committed edit target was changed externally.')
        if target_kind != 'new' and staged_kind != 'new':
            raise OSError('A committed edit target and its staged copy are missing.')
        states.append((entry, target_kind, staged_kind, backup_kind, discarded_kind))

    for entry, target_kind, staged_kind, backup_kind, _ in states:
        target = entry['target']
        staged = entry['staged']
        backup = entry['backup']
        if target_kind == 'new':
            if not file_matches_fingerprint(target, entry['new_sha256'], entry['new_size']):
                raise OSError('A committed edit target changed after recovery preflight.')
            continue
        if staged_kind != 'new' or not file_matches_fingerprint(
            staged, entry['new_sha256'], entry['new_size']
        ):
            raise OSError('A committed staged file changed after recovery preflight.')
        if target_kind == 'previous':
            if not file_matches_fingerprint(
                target, entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('A committed previous target changed after recovery preflight.')
            if backup_kind == 'previous':
                if not file_matches_fingerprint(
                    backup, entry['previous_sha256'], entry['previous_size']
                ):
                    raise OSError('A committed backup changed after recovery preflight.')
                target.unlink()
                sync_directory_metadata(target.parent)
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                durable_move(target, backup)
                sync_rename_metadata(target, backup)
        elif path_entry_exists(target):
            raise OSError('A committed target appeared after recovery preflight.')
        target.parent.mkdir(parents=True, exist_ok=True)
        durable_move(staged, target)
        sync_rename_metadata(staged, target)
        if not file_matches_fingerprint(target, entry['new_sha256'], entry['new_size']):
            raise OSError('A committed edit target could not be restored exactly.')
    return cleanup_edit_staging(
        staging_root,
        expected_identity=payload['_staging_identity'],
        inventory=edit_transaction_cleanup_inventory(staging_root, payload),
    )


def reconcile_edit_transaction_with_database(
    staging_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    with database_connection() as connection:
        row = connection.execute(
            'SELECT revision_count, output_dir FROM library_items WHERE id = ?',
            (payload['item_id'],),
        ).fetchone()
    if row is None:
        raise OSError('The edit transaction library row is missing.')
    current_revision = int(row['revision_count'] or 0)
    current_output_root = Path(str(row['output_dir'])).resolve()
    if current_revision == payload['expected_revision']:
        if current_output_root != payload['_previous_output_root']:
            raise OSError('The uncommitted edit does not match the library output directory.')
        rollback_edit_transaction(staging_root, payload)
        return []
    if current_revision == payload['target_revision']:
        if current_output_root != payload['_output_root']:
            raise OSError('The committed edit does not match the library output directory.')
        return finish_committed_edit_transaction(staging_root, payload)
    if current_revision > payload['target_revision']:
        if current_output_root != payload['_output_root']:
            raise OSError(
                'A stale edit transaction belongs to a different output directory.'
            )
        return cleanup_edit_staging(
            staging_root,
            expected_identity=payload['_staging_identity'],
            inventory=edit_transaction_cleanup_inventory(staging_root, payload),
        )
    raise OSError('The database revision predates the edit transaction.')


def preflight_edit_promotion(
    staging_root: Path,
    staged_files: list[Path],
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    expected = {
        edit_relative_path_key(entry['relative']): entry
        for entry in payload['_resolved_files']
    }
    supplied: dict[str, Path] = {}
    for staged_path in staged_files:
        if path_is_link_or_reparse(staged_path):
            raise OSError('A staged output file is a symbolic link or reparse point.')
        staged = staged_path.resolve()
        if not path_is_within(staged, staging_root) or not staged.is_file():
            raise OSError('A staged output file is missing or outside the staging directory.')
        relative_key = edit_relative_path_key(staged.relative_to(staging_root))
        if relative_key in supplied:
            raise OSError('Duplicate staged output target.')
        supplied[relative_key] = staged
    if set(supplied) != set(expected):
        raise OSError('The staged output set does not match its edit transaction manifest.')
    for relative_key, entry in expected.items():
        staged = supplied[relative_key]
        if not file_matches_fingerprint(staged, entry['new_sha256'], entry['new_size']):
            raise OSError('A staged output file was changed after manifest creation.')
        if path_entry_exists(entry['backup']) or path_entry_exists(entry['discarded']):
            raise OSError('A new edit transaction already contains promoted state.')
        if entry['had_previous']:
            if not file_matches_fingerprint(
                entry['target'], entry['previous_sha256'], entry['previous_size']
            ):
                raise OSError('An edit target was changed after manifest creation.')
        elif path_entry_exists(entry['target']):
            raise OSError('A new edit target appeared after manifest creation.')
    return expected


@contextmanager
def promote_staged_files(
    staging_dir: Path,
    output_dir: Path,
    staged_files: list[Path],
):
    staging_root = staging_dir.resolve()
    staging_identity = edit_staging_identity(staging_root)
    output_root = output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    backup_root = staging_root / ".previous"
    states: list[tuple[Path, Path | None, Path, int, str]] = []
    final_files: list[Path] = []
    seen: set[str] = set()
    retain_staging = False
    cleanup_handled = False
    transaction_payload: dict[str, Any] | None = None
    transaction_entries: dict[str, dict[str, Any]] = {}
    cleanup_file_options: dict[str, set[tuple[int, str]]] = {}
    manifest = staging_root / EDIT_TRANSACTION_MANIFEST_NAME
    if manifest.is_file() and not manifest.is_symlink():
        with database_connection() as connection:
            storage_id = edit_storage_id(connection)
            journal_secret = edit_journal_secret(connection)
        transaction_payload = load_edit_transaction_manifest(
            staging_root,
            expected_storage_id=storage_id,
            expected_secret=journal_secret,
        )
        staging_identity = transaction_payload['_staging_identity']
        transaction_entries = {
            edit_relative_path_key(entry['relative']): entry
            for entry in transaction_payload['_resolved_files']
        }
        transaction_entries = preflight_edit_promotion(
            staging_root,
            staged_files,
            transaction_payload,
        )
    try:
        for staged_path in staged_files:
            staged = staged_path.resolve()
            if not path_is_within(staged, staging_root) or not staged.is_file():
                raise OSError("A staged output file is missing or outside the staging directory.")
            relative = staged.relative_to(staging_root)
            target = output_root / relative
            relative_key = edit_relative_path_key(relative)
            if relative_key in seen:
                raise OSError("Duplicate staged output target.")
            seen.add(relative_key)
            transaction_entry = transaction_entries.get(relative_key)
            if transaction_payload is not None and transaction_entry is None:
                raise OSError('A staged file is absent from its edit transaction manifest.')
            if transaction_entry is not None:
                staged_size = transaction_entry['new_size']
                staged_sha256 = transaction_entry['new_sha256']
                if not file_matches_fingerprint(staged, staged_sha256, staged_size):
                    raise OSError('A staged output changed after promotion preflight.')
                if transaction_entry['had_previous']:
                    if not file_matches_fingerprint(
                        target,
                        transaction_entry['previous_sha256'],
                        transaction_entry['previous_size'],
                    ):
                        raise OSError('An edit target changed after promotion preflight.')
                elif path_entry_exists(target):
                    raise OSError('A new edit target appeared after promotion preflight.')
                if path_entry_exists(transaction_entry['backup']):
                    raise OSError('An edit backup appeared after promotion preflight.')
                if path_entry_exists(transaction_entry['discarded']):
                    raise OSError('An edit discarded file appeared after promotion preflight.')
            else:
                staged_size = staged.stat().st_size
                staged_sha256 = file_sha256(staged)
            relative_name = PurePosixPath(*relative.parts).as_posix()
            cleanup_file_options.setdefault(relative_name, set()).add(
                (staged_size, staged_sha256)
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            backup: Path | None = None
            if target.exists() or target.is_symlink():
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                durable_move(target, backup)
                sync_rename_metadata(target, backup)
                if transaction_entry is not None and not file_matches_fingerprint(
                    backup,
                    transaction_entry['previous_sha256'],
                    transaction_entry['previous_size'],
                ):
                    raise OSError('An edit backup changed during promotion.')
                if transaction_entry is None:
                    backup_name = PurePosixPath('.previous', *relative.parts).as_posix()
                    cleanup_file_options.setdefault(backup_name, set()).add(
                        (backup.stat().st_size, file_sha256(backup))
                    )
            states.append((target, backup, relative, staged_size, staged_sha256))
            if transaction_entry is not None:
                # Keep the authenticated new copy until the database commit is
                # known to have completed. If the target is replaced while the
                # transaction yields, recovery still has both old and new data.
                atomic_copy_file(staged, target, replace_existing=False)
            else:
                durable_move(staged, target)
                sync_rename_metadata(staged, target)
            if not file_matches_fingerprint(target, staged_sha256, staged_size):
                raise OSError('A promoted edit target does not match its manifest.')
            final_files.append(target)
        yield final_files
        for target, _, _, staged_size, staged_sha256 in states:
            if not file_matches_fingerprint(target, staged_sha256, staged_size):
                raise OSError('A promoted output target changed during database commit.')
    except BaseException as original_exc:
        if transaction_payload is not None:
            try:
                recovery_warnings = reconcile_edit_transaction_with_database(
                    staging_root,
                    transaction_payload,
                )
                cleanup_handled = True
                if recovery_warnings:
                    print(
                        'Edit transaction reconciliation warning: '
                        + '; '.join(recovery_warnings),
                        file=sys.stderr,
                    )
            except (OSError, ValueError, sqlite3.Error) as recovery_exc:
                retain_staging = True
                raise OSError(
                    'Output commit state was uncertain; recovery files were retained at '
                    f'{staging_root}: {recovery_exc}'
                ) from original_exc
            raise
        rollback_errors: list[str] = []
        for target, backup, relative, staged_size, staged_sha256 in reversed(states):
            try:
                if target.exists() or target.is_symlink():
                    if not file_matches_fingerprint(
                        target, staged_sha256, staged_size
                    ):
                        raise OSError('A promoted output target was changed externally.')
                    discarded = staging_root / '.discarded' / relative
                    discarded.parent.mkdir(parents=True, exist_ok=True)
                    durable_move(target, discarded)
                    sync_rename_metadata(target, discarded)
                    discarded_name = PurePosixPath(
                        '.discarded',
                        *relative.parts,
                    ).as_posix()
                    cleanup_file_options.setdefault(discarded_name, set()).add(
                        (staged_size, staged_sha256)
                    )
                if backup is not None and backup.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    durable_move(backup, target)
                    sync_rename_metadata(backup, target)
            except OSError as exc:
                rollback_errors.append(str(exc))
        if rollback_errors:
            retain_staging = True
            raise OSError(
                "Output rollback failed; recovery files were retained at "
                f"{staging_root}: {'; '.join(rollback_errors)}"
            ) from original_exc
        raise
    finally:
        if not retain_staging and not cleanup_handled:
            cleanup_inventory = (
                edit_transaction_cleanup_inventory(staging_root, transaction_payload)
                if transaction_payload is not None
                else capture_edit_cleanup_inventory(
                    staging_root,
                    cleanup_file_options,
                )
            )
            cleanup_errors = cleanup_edit_staging(
                staging_root,
                expected_identity=staging_identity,
                inventory=cleanup_inventory,
            )
            if cleanup_errors:
                print(
                    'Edit staging cleanup warning: ' + '; '.join(cleanup_errors),
                    file=sys.stderr,
                )


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def thumbnail_cache_path(source_path: Path) -> Path:
    stat = source_path.stat()
    seed = f"{source_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return THUMBNAIL_DIRECTORY / f"{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex}.jpg"


TEXT_MINING_STOP_WORDS = {
    "こと", "これ", "それ", "ため", "よう", "ところ", "もの", "こちら", "さん",
    "です", "ます", "でした", "ました", "する", "いる", "ある", "なる",
    "the", "and", "that", "this", "with", "from", "have", "will", "your",
}


def text_mining_counter(
    segments: list[dict[str, Any]],
    extra_stop_words: set[str] | None = None,
) -> Counter[str]:
    text = " ".join(str(item.get("text") or "") for item in segments)
    candidates = re.findall(
        r"[一-龯々〆ヵヶ]{2,}|[ァ-ヴー]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}",
        text,
    )
    stop_words = TEXT_MINING_STOP_WORDS | {
        str(value).casefold() for value in (extra_stop_words or set()) if str(value).strip()
    }
    return Counter(
        token.casefold() if token.isascii() else token
        for token in candidates
        if token.casefold() not in stop_words
    )


def text_mining_terms(
    segments: list[dict[str, Any]],
    limit: int = 18,
    extra_stop_words: set[str] | None = None,
) -> list[tuple[str, int]]:
    """Extract useful frequent terms without requiring a morphological analyzer."""
    return text_mining_counter(segments, extra_stop_words).most_common(limit)


def analysis_number(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return round(min(max(number, minimum), maximum), 3)


def analysis_bool(value: Any, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def default_analysis_config() -> dict[str, Any]:
    return {
        "research_question": "",
        "analysis_unit": "turn",
        "exclude_moderator": True,
        "excluded_speakers": [],
        "group_by": "none",
        "long_gap_seconds": 3.0,
        "overlap_seconds": 0.2,
        "low_participation_percent": 10.0,
        "time_bin_seconds": 300,
        "stop_words": [],
        "morph_split_mode": "C",
        "cooccurrence_min_count": 2,
        "cooccurrence_top_terms": 60,
        "statistics_group_by": "speaker",
        "crosstab_terms": [],
        "codebook": [],
        "analyst_memo": "",
        "interpretation_status": "draft",
    }


def normalize_analysis_codebook(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    codebook: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for index, value in enumerate(raw[:100]):
        if not isinstance(value, dict):
            continue
        label = clean_single_line(value.get("label"), 120)
        if not label:
            continue
        code_id = clean_single_line(value.get("id"), 80)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", code_id) or code_id in used_ids:
            seed = f"gurumoji-analysis-code:{index}:{label}"
            code_id = f"code_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:16]}"
        used_ids.add(code_id)
        color = clean_single_line(value.get("color"), 7).upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", color):
            color = SPEAKER_THEME_COLORS[index % len(SPEAKER_THEME_COLORS)]
        codebook.append({
            "id": code_id,
            "label": label,
            "description": clean_multiline(value.get("description"), 4000),
            "include_example": clean_multiline(value.get("include_example"), 2000),
            "exclude_example": clean_multiline(value.get("exclude_example"), 2000),
            "color": color,
        })
    return codebook


def normalize_analysis_group_by(value: Any) -> str:
    group_by = clean_single_line(value, 140)
    if group_by in ANALYSIS_GROUP_FIELDS:
        return group_by
    prefix = "attribute:"
    if group_by.startswith(prefix):
        attribute_key = clean_single_line(group_by[len(prefix):], 120)
        if attribute_key:
            return f"{prefix}{attribute_key}"
    return "none"


def normalize_analysis_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    config = default_analysis_config()
    unit = clean_single_line(source.get("analysis_unit", config["analysis_unit"]), 30)
    group_by = normalize_analysis_group_by(source.get("group_by", config["group_by"]))
    morph_split_mode = clean_single_line(
        source.get("morph_split_mode", config["morph_split_mode"]), 1
    ).upper()
    statistics_group_by = clean_single_line(
        source.get("statistics_group_by", config["statistics_group_by"]), 20
    )
    status = clean_single_line(
        source.get("interpretation_status", config["interpretation_status"]), 30
    )
    config.update({
        "research_question": clean_multiline(source.get("research_question"), 10000),
        "analysis_unit": unit if unit in ANALYSIS_UNITS else "turn",
        "exclude_moderator": analysis_bool(source.get("exclude_moderator"), True),
        "excluded_speakers": [
            clean_single_line(value, 80)
            for value in (source.get("excluded_speakers") or [])[:200]
            if clean_single_line(value, 80)
        ] if isinstance(source.get("excluded_speakers"), list) else [],
        "group_by": group_by,
        "long_gap_seconds": analysis_number(source.get("long_gap_seconds"), 3.0, 0.2, 120.0),
        "overlap_seconds": analysis_number(source.get("overlap_seconds"), 0.2, 0.0, 30.0),
        "low_participation_percent": analysis_number(
            source.get("low_participation_percent"), 10.0, 0.0, 50.0
        ),
        "time_bin_seconds": int(analysis_number(source.get("time_bin_seconds"), 300, 30, 3600)),
        "stop_words": normalize_tags(source.get("stop_words"))[:200],
        "morph_split_mode": (
            morph_split_mode if morph_split_mode in {"A", "B", "C"} else "C"
        ),
        "cooccurrence_min_count": int(analysis_number(
            source.get("cooccurrence_min_count"), 2, 1, 1000
        )),
        "cooccurrence_top_terms": int(analysis_number(
            source.get("cooccurrence_top_terms"), 60, 10, 200
        )),
        "statistics_group_by": (
            statistics_group_by
            if statistics_group_by in {"speaker", "role"}
            else "speaker"
        ),
        "crosstab_terms": normalize_tags(source.get("crosstab_terms"))[:30],
        "codebook": normalize_analysis_codebook(source.get("codebook")),
        "analyst_memo": clean_multiline(source.get("analyst_memo"), 30000),
        "interpretation_status": (
            status if status in ANALYSIS_INTERPRETATION_STATUSES else "draft"
        ),
    })
    return config


def normalize_analysis_annotations(
    raw: Any,
    segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    source = raw if isinstance(raw, dict) else {}
    segment_ids = {str(item.get("id") or "") for item in segments}
    code_ids = {str(item["id"]) for item in config.get("codebook", [])}
    annotations: dict[str, dict[str, Any]] = {}
    for segment_id, value in list(source.items())[:100000]:
        segment_id = str(segment_id)
        if segment_id not in segment_ids or not isinstance(value, dict):
            continue
        codes = []
        raw_codes = value.get("codes") if isinstance(value.get("codes"), list) else []
        for code_id in raw_codes[:100]:
            code_id = str(code_id)
            if code_id in code_ids and code_id not in codes:
                codes.append(code_id)
        tags = []
        raw_tags = (
            value.get("interaction_tags")
            if isinstance(value.get("interaction_tags"), list)
            else []
        )
        for tag in raw_tags[:50]:
            tag = str(tag)
            if tag in ANALYSIS_INTERACTION_TAGS and tag not in tags:
                tags.append(tag)
        annotation = {
            "codes": codes,
            "interaction_tags": tags,
            "memo": clean_multiline(value.get("memo"), 5000),
            "important": analysis_bool(value.get("important"), False),
            "excluded": analysis_bool(value.get("excluded"), False),
        }
        if any((codes, tags, annotation["memo"], annotation["important"], annotation["excluded"])):
            annotations[segment_id] = annotation
    return annotations


def row_analysis_config(row: sqlite3.Row) -> dict[str, Any]:
    return normalize_analysis_config(json_load(row["analysis_config_json"], {}))


def row_analysis_annotations(
    row: sqlite3.Row,
    segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    annotations, _ = row_analysis_annotation_state(row, segments, config)
    return annotations


def row_analysis_annotation_state(
    row: sqlite3.Row,
    segments: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    raw_value = json_load(row["analysis_annotations_json"], {})
    raw = raw_value if isinstance(raw_value, dict) else {}
    annotations = normalize_analysis_annotations(raw, segments, config)
    segment_ids = {str(item.get("id") or "") for item in segments}
    orphaned: dict[str, dict[str, Any]] = {}
    for index, (segment_id, value) in enumerate(raw.items()):
        if index >= 100000:
            break
        segment_id = str(segment_id)
        if segment_id in segment_ids or not isinstance(value, dict):
            continue
        normalized = normalize_analysis_annotations(
            {segment_id: value}, [{"id": segment_id}], config
        )
        if segment_id in normalized:
            orphaned[segment_id] = normalized[segment_id]
    return annotations, orphaned


def analysis_gini(values: list[float]) -> float:
    clean = sorted(max(0.0, float(value)) for value in values)
    total = sum(clean)
    if len(clean) <= 1 or total <= 0:
        return 0.0
    count = len(clean)
    weighted = sum((2 * index - count - 1) * value for index, value in enumerate(clean, 1))
    return weighted / (count * total)


def analysis_evenness(values: list[float]) -> float:
    clean = [max(0.0, float(value)) for value in values]
    total = sum(clean)
    if not clean or total <= 0:
        return 0.0
    if len(clean) == 1:
        return 1.0
    entropy = -sum(
        (value / total) * math.log(value / total)
        for value in clean if value > 0
    )
    return entropy / math.log(len(clean))


def analysis_segment_bounds(segment: dict[str, Any]) -> tuple[float, float, bool]:
    try:
        raw_start = float(segment.get("start", 0) or 0)
        raw_end = float(segment.get("end", raw_start) or raw_start)
    except (TypeError, ValueError):
        return 0.0, 0.0, False
    if not math.isfinite(raw_start) or not math.isfinite(raw_end):
        return 0.0, 0.0, False
    valid = (
        raw_start >= 0
        and raw_end >= raw_start
        and raw_start <= ANALYSIS_MAX_TIMELINE_SECONDS
        and raw_end <= ANALYSIS_MAX_TIMELINE_SECONDS
    )
    start = min(max(raw_start, 0.0), float(ANALYSIS_MAX_TIMELINE_SECONDS))
    end = min(max(raw_end, start), float(ANALYSIS_MAX_TIMELINE_SECONDS))
    return start, end, valid


def analysis_emotion_entries(segment: dict[str, Any]) -> list[dict[str, str]]:
    raw = segment.get("emotions")
    if not isinstance(raw, dict):
        return []
    entries: list[dict[str, str]] = []
    for model_key, value in raw.items():
        if not isinstance(value, dict):
            continue
        raw_label = clean_single_line(value.get("label"), 80)
        explicit_label_ja = clean_single_line(value.get("label_ja"), 80)
        if not raw_label and not explicit_label_ja:
            continue
        label_ja = clean_single_line(
            explicit_label_ja or emotion_label_ja(raw_label), 80
        )
        if not raw_label and not label_ja:
            continue
        entries.append({
            "model": clean_single_line(model_key, 80) or "unknown",
            "model_name": clean_single_line(value.get("model_name"), 120),
            "label": raw_label,
            "label_ja": label_ja or raw_label,
        })
    return entries


def group_analysis_for_row(
    row: sqlite3.Row,
    *,
    include_research_rows: bool = False,
) -> dict[str, Any]:
    segments = row_segments(row)
    config = row_analysis_config(row)
    annotations, orphaned_annotations = row_analysis_annotation_state(
        row, segments, config
    )
    raw_names = json_load(row["speaker_names_json"], {})
    speaker_names = raw_names if isinstance(raw_names, dict) else {}
    raw_profiles_value = json_load(row["speaker_profiles_json"], {})
    raw_profiles = raw_profiles_value if isinstance(raw_profiles_value, dict) else {}
    profiles = row_speaker_profiles(row, segments, speaker_names)
    linked_registry_ids = {
        str(profile.get("global_speaker_id") or "")
        for profile in profiles.values()
        if str(profile.get("global_speaker_id") or "")
    }
    registry_profiles = {}
    if linked_registry_ids:
        registry_profiles = {
            record["id"]: record
            for record in list_speaker_registry(include_inactive=True)
            if record["id"] in linked_registry_ids
        }
    session_profile = row_session_profile(row)
    codebook = {str(item["id"]): item for item in config["codebook"]}
    excluded_speakers = set(config["excluded_speakers"])

    ordered = sorted(segments, key=lambda item: analysis_segment_bounds(item)[:2])
    included: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    speaker_buckets: dict[str, dict[str, Any]] = {}
    emotion_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    emotion_covered = 0
    empty_text_count = 0
    zero_duration_count = 0
    invalid_time_count = 0

    for segment in ordered:
        segment_id = str(segment.get("id") or "")
        speaker = str(segment.get("speaker") or "UNKNOWN")
        start, end, valid_time = analysis_segment_bounds(segment)
        if not valid_time:
            invalid_time_count += 1
        duration = max(0.0, end - start)
        text = str(segment.get("text") or "").strip()
        annotation = annotations.get(segment_id, {
            "codes": [], "interaction_tags": [], "memo": "",
            "important": False, "excluded": False,
        })
        profile = profiles.get(speaker, {})
        display_name = str(
            profile.get("display_name")
            or speaker_names.get(speaker)
            or default_speaker_name(speaker)
        )
        role = str(profile.get("session_role") or "participant")
        color = str(profile.get("theme_color") or "#1C6B50")
        emotion_details = analysis_emotion_entries(segment)
        emotions = list(dict.fromkeys(item["label_ja"] for item in emotion_details))
        if emotion_details:
            emotion_covered += 1
        if not text:
            empty_text_count += 1
        if duration <= 0:
            zero_duration_count += 1
        excluded = bool(annotation.get("excluded")) or speaker in excluded_speakers
        question_candidate = bool(
            re.search(r"[?？]|(?:です|ます|でしょう)か[。．]?$", text)
        )
        item = {
            "id": segment_id,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "speaker": speaker,
            "speaker_name": display_name,
            "role": role,
            "color": color,
            "text": text,
            "characters": len(re.sub(r"\s+", "", text)),
            "emotions": emotions,
            "emotion_details": emotion_details,
            "question_candidate": question_candidate,
            "valid_time": valid_time,
            "annotation": annotation,
            "excluded": excluded,
        }
        timeline.append(item)
        if excluded:
            continue
        included.append(item)
        bucket = speaker_buckets.setdefault(speaker, {
            "speaker": speaker,
            "speaker_name": display_name,
            "role": role,
            "color": color,
            "turn_count": 0,
            "speaking_seconds": 0.0,
            "characters": 0,
            "question_candidates": 0,
            "first_start": start,
            "last_end": end,
            "emotion_counts": Counter(),
            "code_counts": Counter(),
        })
        bucket["turn_count"] += 1
        bucket["speaking_seconds"] += duration
        bucket["characters"] += item["characters"]
        bucket["first_start"] = min(float(bucket["first_start"]), start)
        bucket["last_end"] = max(float(bucket["last_end"]), end)
        if question_candidate:
            bucket["question_candidates"] += 1
        for emotion in emotion_details:
            bucket["emotion_counts"][emotion["label_ja"]] += 1
            key = (speaker, emotion["model"], emotion["label_ja"])
            emotion_row = emotion_rows.setdefault(key, {
                "speaker": speaker,
                "speaker_name": display_name,
                "model": emotion["model"],
                "model_name": emotion["model_name"],
                "label": emotion["label"],
                "emotion": emotion["label_ja"],
                "count": 0,
                "seconds": 0.0,
            })
            emotion_row["count"] += 1
            emotion_row["seconds"] += duration
        for code_id in annotation.get("codes", []):
            bucket["code_counts"][code_id] += 1

    valid_included = [
        item for item in included
        if item["valid_time"] and float(item["end"]) > float(item["start"])
    ]
    physical_timeline = [
        item for item in timeline
        if item["valid_time"] and float(item["end"]) > float(item["start"])
    ]

    total_speaking = sum(float(item["speaking_seconds"]) for item in speaker_buckets.values())
    actual_participant_labels = [
        label for label, item in speaker_buckets.items()
        if item["role"] not in ANALYSIS_NON_PARTICIPANT_ROLES
    ]
    balance_labels = (
        actual_participant_labels
        if config["exclude_moderator"]
        else list(speaker_buckets)
    )
    balance_total = sum(
        float(speaker_buckets[label]["speaking_seconds"]) for label in balance_labels
    )
    actual_participant_total = sum(
        float(speaker_buckets[label]["speaking_seconds"])
        for label in actual_participant_labels
    )
    speaker_metrics: list[dict[str, Any]] = []
    for label, bucket in sorted(
        speaker_buckets.items(),
        key=lambda pair: (-float(pair[1]["speaking_seconds"]), pair[1]["speaker_name"]),
    ):
        seconds = float(bucket["speaking_seconds"])
        turns = int(bucket["turn_count"])
        participant_share = (
            seconds / balance_total if label in balance_labels and balance_total > 0 else 0.0
        )
        profile = profiles.get(label, {})
        registry_profile = registry_profiles.get(
            str(profile.get("global_speaker_id") or ""), {}
        )
        speaker_metrics.append({
            "speaker": label,
            "speaker_name": bucket["speaker_name"],
            "role": bucket["role"],
            "color": bucket["color"],
            "turn_count": turns,
            "speaking_seconds": round(seconds, 3),
            "speaking_percent": round(100 * seconds / total_speaking, 2) if total_speaking else 0.0,
            "participant_percent": round(100 * participant_share, 2),
            "average_turn_seconds": round(seconds / turns, 3) if turns else 0.0,
            "characters": int(bucket["characters"]),
            "characters_per_minute": round(60 * int(bucket["characters"]) / seconds, 2) if seconds else 0.0,
            "question_candidates": int(bucket["question_candidates"]),
            "first_start": round(float(bucket["first_start"]), 3),
            "last_end": round(float(bucket["last_end"]), 3),
            "emotion_counts": dict(bucket["emotion_counts"]),
            "code_counts": dict(bucket["code_counts"]),
            "included_in_balance": label in balance_labels,
            "profile": {
                "organization": str(
                    profile.get("organization")
                    or registry_profile.get("organization")
                    or ""
                ),
                "department": str(
                    profile.get("department")
                    or registry_profile.get("department")
                    or ""
                ),
                "job_title": str(
                    profile.get("job_title")
                    or registry_profile.get("job_title")
                    or ""
                ),
                "conditions": str(profile.get("conditions") or ""),
                "tags": list(registry_profile.get("tags") or []),
                "attributes": dict(registry_profile.get("attributes") or {}),
            },
        })

    balance_seconds = [
        float(speaker_buckets[label]["speaking_seconds"]) for label in balance_labels
    ]
    balance_shares = [
        value / balance_total for value in balance_seconds if balance_total > 0
    ]
    dominant = max(
        (item for item in speaker_metrics if item["included_in_balance"]),
        key=lambda item: item["participant_percent"],
        default=None,
    )
    balance = {
        "participant_count": len(actual_participant_labels),
        "participant_speaking_seconds": round(actual_participant_total, 3),
        "balance_speaker_count": len(balance_labels),
        "balance_speaking_seconds": round(balance_total, 3),
        "max_participant_percent": dominant["participant_percent"] if dominant else 0.0,
        "max_participant_name": dominant["speaker_name"] if dominant else "",
        "gini": round(analysis_gini(balance_seconds), 4),
        "normalized_evenness": round(analysis_evenness(balance_seconds), 4),
        "hhi": round(sum(value * value for value in balance_shares), 4),
        "denominator": "participant_only" if config["exclude_moderator"] else "all_speakers",
    }

    transitions: dict[tuple[str, str], dict[str, Any]] = {}
    overlap_candidates: list[dict[str, Any]] = []
    consecutive_gaps: list[float] = []
    moderator_response_gaps: list[float] = []
    moderator_to_participant = 0
    participant_to_participant = 0
    cross_speaker_transitions = 0
    for previous, current in zip(valid_included, valid_included[1:]):
        if previous["speaker"] == current["speaker"]:
            continue
        gap = float(current["start"]) - float(previous["end"])
        cross_speaker_transitions += 1
        consecutive_gaps.append(gap)
        key = (str(previous["speaker"]), str(current["speaker"]))
        transition = transitions.setdefault(key, {
            "from_speaker": previous["speaker"],
            "from_name": previous["speaker_name"],
            "from_role": previous["role"],
            "to_speaker": current["speaker"],
            "to_name": current["speaker_name"],
            "to_role": current["role"],
            "count": 0,
            "gap_total": 0.0,
            "overlap_candidates": 0,
        })
        transition["count"] += 1
        transition["gap_total"] += gap
        overlap_end = min(float(previous["end"]), float(current["end"]))
        overlap_seconds = max(0.0, overlap_end - float(current["start"]))
        if (
            overlap_seconds > 0
            and overlap_seconds >= float(config["overlap_seconds"])
        ):
            transition["overlap_candidates"] += 1
        previous_moderator = previous["role"] in ANALYSIS_FACILITATOR_ROLES
        current_participant = current["role"] not in ANALYSIS_NON_PARTICIPANT_ROLES
        previous_participant = previous["role"] not in ANALYSIS_NON_PARTICIPANT_ROLES
        if previous_moderator and current_participant:
            moderator_to_participant += 1
            if previous["question_candidate"]:
                moderator_response_gaps.append(gap)
        if previous_participant and current_participant:
            participant_to_participant += 1

    transition_rows = []
    for value in transitions.values():
        count = int(value["count"])
        transition_rows.append({
            **{key: item for key, item in value.items() if key != "gap_total"},
            "average_gap_seconds": round(float(value["gap_total"]) / count, 3) if count else 0.0,
        })
    transition_rows.sort(key=lambda item: (-item["count"], item["from_name"], item["to_name"]))

    overlap_truncated = False
    active_segments: list[dict[str, Any]] = []
    for current in physical_timeline:
        current_start = float(current["start"])
        active_segments = [
            item for item in active_segments if float(item["end"]) > current_start
        ]
        if len(active_segments) > 1000:
            active_segments = active_segments[-1000:]
            overlap_truncated = True
        for previous in active_segments:
            if previous["speaker"] == current["speaker"]:
                continue
            overlap_end = min(float(previous["end"]), float(current["end"]))
            seconds = max(0.0, overlap_end - current_start)
            if seconds <= 0 or seconds < float(config["overlap_seconds"]):
                continue
            if len(overlap_candidates) >= 10000:
                overlap_truncated = True
                continue
            overlap_candidates.append({
                "start": round(current_start, 3),
                "end": round(overlap_end, 3),
                "seconds": round(seconds, 3),
                "from_speaker": previous["speaker"],
                "from_name": previous["speaker_name"],
                "to_speaker": current["speaker"],
                "to_name": current["speaker_name"],
            })
        active_segments.append(current)

    long_gaps: list[dict[str, Any]] = []
    coverage_end = 0.0
    previous_name = "開始"
    for segment in physical_timeline:
        start = float(segment["start"])
        if start > coverage_end:
            duration = start - coverage_end
            if duration >= float(config["long_gap_seconds"]):
                long_gaps.append({
                    "start": round(coverage_end, 3),
                    "end": round(start, 3),
                    "seconds": round(duration, 3),
                    "previous_name": previous_name,
                    "next_name": segment["speaker_name"],
                })
        if float(segment["end"]) >= coverage_end:
            coverage_end = float(segment["end"])
            previous_name = str(segment["speaker_name"])

    session_duration = max((float(item["end"]) for item in physical_timeline), default=0.0)
    requested_bin_seconds = int(config["time_bin_seconds"])
    bin_seconds = requested_bin_seconds
    if session_duration and math.ceil(session_duration / bin_seconds) > ANALYSIS_MAX_TIME_BINS:
        bin_seconds = max(
            requested_bin_seconds,
            int(math.ceil(session_duration / ANALYSIS_MAX_TIME_BINS)),
        )
    bin_count = max(1, int(math.ceil(session_duration / bin_seconds))) if session_duration else 1
    time_bins = [
        {
            "index": index,
            "start": index * bin_seconds,
            "end": min((index + 1) * bin_seconds, session_duration) if session_duration else bin_seconds,
            "speaking_seconds": 0.0,
            "turn_count": 0,
            "speakers": Counter(),
        }
        for index in range(bin_count)
    ]
    for segment in valid_included:
        start = float(segment["start"])
        end = float(segment["end"])
        if end <= start:
            continue
        first_bin = min(int(start // bin_seconds), bin_count - 1)
        last_bin = min(int(max(start, end - 0.000001) // bin_seconds), bin_count - 1)
        time_bins[first_bin]["turn_count"] += 1
        for index in range(first_bin, last_bin + 1):
            piece_start = max(start, index * bin_seconds)
            piece_end = min(end, (index + 1) * bin_seconds)
            seconds = max(0.0, piece_end - piece_start)
            time_bins[index]["speaking_seconds"] += seconds
            time_bins[index]["speakers"][segment["speaker"]] += seconds
    serialized_bins = [{
        **{key: value for key, value in item.items() if key != "speakers"},
        "speaking_seconds": round(float(item["speaking_seconds"]), 3),
        "speakers": [
            {
                "speaker": key,
                "speaker_name": speaker_buckets.get(key, {}).get("speaker_name", key),
                "seconds": round(value, 3),
            }
            for key, value in item["speakers"].items()
        ],
    } for item in time_bins]

    stop_words = set(config["stop_words"])
    keyword_pairs = text_mining_terms(included, limit=30, extra_stop_words=stop_words)
    speaker_segments: dict[str, list[dict[str, Any]]] = {}
    for item in included:
        speaker_segments.setdefault(item["speaker"], []).append(item)
    speaker_term_counts = {
        speaker: text_mining_counter(values, stop_words)
        for speaker, values in speaker_segments.items()
    }
    keywords = []
    for term, count in keyword_pairs:
        by_speaker = []
        for metric in speaker_metrics:
            occurrences = int(speaker_term_counts.get(metric["speaker"], Counter()).get(term, 0))
            if occurrences:
                by_speaker.append({
                    "speaker": metric["speaker"],
                    "speaker_name": metric["speaker_name"],
                    "count": occurrences,
                })
        keywords.append({"term": term, "count": count, "by_speaker": by_speaker})

    code_metrics = []
    for code_id, code in codebook.items():
        coded = [item for item in included if code_id in item["annotation"].get("codes", [])]
        code_metrics.append({
            **code,
            "segment_count": len(coded),
            "speaking_seconds": round(sum(float(item["duration"]) for item in coded), 3),
            "characters": sum(int(item["characters"]) for item in coded),
            "speaker_count": len({item["speaker"] for item in coded}),
            "important_count": sum(1 for item in coded if item["annotation"].get("important")),
        })
    interaction_counts = Counter(
        tag
        for item in included
        for tag in item["annotation"].get("interaction_tags", [])
    )
    interaction_summary = [
        {"tag": key, "label": label, "count": int(interaction_counts.get(key, 0))}
        for key, label in ANALYSIS_INTERACTION_TAGS.items()
    ]
    case_code_matrix = []
    for metric in speaker_metrics:
        case_code_matrix.append({
            "speaker": metric["speaker"],
            "speaker_name": metric["speaker_name"],
            "role": metric["role"],
            "codes": [
                {
                    "code_id": code_id,
                    "code_label": code["label"],
                    "count": int(metric["code_counts"].get(code_id, 0)),
                }
                for code_id, code in codebook.items()
            ],
        })

    groups: dict[str, dict[str, Any]] = {}
    if config["group_by"] != "none":
        for metric in speaker_metrics:
            profile_value = metric.get("profile")
            profile = profile_value if isinstance(profile_value, dict) else {}
            if config["group_by"] == "role":
                group_name = str(metric["role"] or "未設定")
            elif config["group_by"].startswith("attribute:"):
                attribute_key = config["group_by"][len("attribute:"):]
                attributes = profile.get("attributes")
                attribute_value = (
                    attributes.get(attribute_key)
                    if isinstance(attributes, dict)
                    else ""
                )
                group_name = str(attribute_value or "").strip() or "未回答"
            else:
                group_name = str(profile.get(config["group_by"]) or "未設定")
            group = groups.setdefault(group_name, {
                "group": group_name, "speaker_count": 0, "turn_count": 0,
                "speaking_seconds": 0.0, "characters": 0,
            })
            group["speaker_count"] += 1
            group["turn_count"] += int(metric["turn_count"])
            group["speaking_seconds"] += float(metric["speaking_seconds"])
            group["characters"] += int(metric["characters"])
    group_rows = [{
        **value,
        "speaking_seconds": round(float(value["speaking_seconds"]), 3),
        "speaking_percent": round(100 * float(value["speaking_seconds"]) / total_speaking, 2) if total_speaking else 0.0,
    } for value in groups.values()]

    moderator_seconds = sum(
        float(item["speaking_seconds"])
        for item in speaker_metrics if item["role"] in ANALYSIS_FACILITATOR_ROLES
    )
    moderator = {
        "assigned": any(
            item["role"] in ANALYSIS_FACILITATOR_ROLES for item in speaker_metrics
        ),
        "speaking_seconds": round(moderator_seconds, 3),
        "speaking_percent": round(100 * moderator_seconds / total_speaking, 2) if total_speaking else 0.0,
        "question_candidates": sum(
            int(item["question_candidates"])
            for item in speaker_metrics if item["role"] in ANALYSIS_FACILITATOR_ROLES
        ),
        "participant_responses": len(moderator_response_gaps),
        "moderator_to_participant_transitions": moderator_to_participant,
        "average_response_gap_seconds": round(
            sum(moderator_response_gaps) / len(moderator_response_gaps), 3
        ) if moderator_response_gaps else None,
        "participant_to_participant_transitions": participant_to_participant,
        "cross_speaker_transitions": cross_speaker_transitions,
    }

    observations: list[dict[str, str]] = []
    if dominant and float(dominant["participant_percent"]) >= 50:
        observations.append({
            "level": "attention",
            "label": "発話時間の集中候補",
            "message": f"{dominant['speaker_name']}の参加者内発話時間が{dominant['participant_percent']:.1f}%です。重要性や影響力を意味する値ではありません。",
        })
    low_names = [
        item["speaker_name"] for item in speaker_metrics
        if item["included_in_balance"]
        and float(item["participant_percent"]) < float(config["low_participation_percent"])
    ]
    if low_names:
        observations.append({
            "level": "attention",
            "label": "発言機会の確認候補",
            "message": f"設定した{config['low_participation_percent']:g}%未満: {', '.join(low_names)}。沈黙の意味は記録・文脈と合わせて判断してください。",
        })
    if moderator["speaking_percent"] >= 40:
        observations.append({
            "level": "attention",
            "label": "司会発話比率の確認",
            "message": f"司会・進行役の発話時間は全体の{moderator['speaking_percent']:.1f}%です。進行品質の得点ではありません。",
        })
    if long_gaps:
        observations.append({
            "level": "info", "label": "長い無音候補",
            "message": f"{config['long_gap_seconds']:g}秒以上の無音候補が{len(long_gaps)}件あります。無音の理由は自動判定できません。",
        })
    if overlap_candidates:
        observations.append({
            "level": "info", "label": "発話重なり候補",
            "message": f"{config['overlap_seconds']:g}秒以上の時間重なり候補が{len(overlap_candidates)}件あります。遮りとは断定しません。",
        })

    context_checks = [
        {"id": "research_question", "label": "研究質問", "ready": bool(config["research_question"]), "kind": "manual"},
        {"id": "objective", "label": "会話目的", "ready": bool(session_profile.get("objective")), "kind": "manual"},
        {"id": "moderator", "label": "司会・進行役", "ready": moderator["assigned"], "kind": "manual"},
        {
            "id": "participant_roles",
            "label": "話者役割",
            "ready": bool(speaker_metrics) and all(
                isinstance(raw_profiles.get(item["speaker"]), dict)
                and bool(raw_profiles[item["speaker"]].get("session_role"))
                for item in speaker_metrics
            ),
            "kind": "manual",
        },
        {"id": "guide", "label": "質問ガイド・議題", "ready": bool(session_profile.get("moderator_guide")), "kind": "manual"},
        {"id": "conditions", "label": "参加条件・グループ条件", "ready": bool(session_profile.get("group_conditions")), "kind": "manual"},
        {"id": "field_notes", "label": "観察・フィールドノート", "ready": bool(session_profile.get("field_notes")), "kind": "manual"},
        {"id": "codebook", "label": "コードブック", "ready": bool(codebook), "kind": "manual"},
        {
            "id": "coding",
            "label": "手動コーディング",
            "ready": any(
                value.get("codes") or value.get("interaction_tags")
                for value in annotations.values()
            ),
            "kind": "manual",
        },
    ]

    analysis = {
        "schema_version": 1,
        "algorithm_version": "focus-group-local-1",
        "generated_at": utc_now_iso(),
        "item": {
            "id": row["id"],
            "source_name": row["source_name"],
            "revision_count": int(row["revision_count"] or 0),
            "analysis_revision": int(row["analysis_revision"] or 0),
            "analysis_updated_at": row["analysis_updated_at"],
            "updated_at": row["updated_at"],
            "session_profile": session_profile,
        },
        "config": config,
        "annotations": annotations,
        "classification": {
            "automatic": ["発話量", "参加バランス", "話者遷移", "無音・重なり候補", "簡易頻出語", "感情分布"],
            "configured": ["司会除外", "比較属性", "判定しきい値", "ストップワード", "手動選択単語", "コードブック"],
            "manual": ["コード適用", "テーマ構築", "相互作用の意味", "司会影響", "重要引用", "研究上の解釈"],
        },
        "cautions": [
            "発話時間の多さは重要性・影響力を意味しません。",
            "簡易頻出語は重要テーマではありません。",
            "発話遷移は影響関係を意味しません。",
            "無音や重なりの意味、合意・対立、テーマは研究者が文脈とともに確認してください。",
            "音声感情モデルの推定は本人の感情を確定するものではありません。",
            "COREQは研究品質の得点ではなく、報告項目の確認に用います。",
        ],
        "automatic": {
            "overview": {
                "session_duration": round(session_duration, 3),
                "segment_count": len(timeline),
                "included_segment_count": len(included),
                "speaker_count": len(speaker_metrics),
                "participant_count": len(actual_participant_labels),
                "total_speaking_seconds": round(total_speaking, 3),
                "average_cross_speaker_gap_seconds": round(sum(consecutive_gaps) / len(consecutive_gaps), 3) if consecutive_gaps else None,
            },
            "speaker_metrics": speaker_metrics,
            "balance": balance,
            "moderator": moderator,
            "transitions": transition_rows,
            "long_gaps": long_gaps,
            "overlap_candidates": overlap_candidates,
                "time_bins": serialized_bins,
                "requested_time_bin_seconds": requested_bin_seconds,
                "effective_time_bin_seconds": bin_seconds,
            "keywords": keywords,
            "emotions": [{**value, "seconds": round(float(value["seconds"]), 3)} for value in emotion_rows.values()],
            "groups": group_rows,
            "observations": observations,
            "data_quality": {
                "unknown_speaker_segments": sum(1 for item in timeline if item["speaker"] == "UNKNOWN"),
                "empty_text_segments": empty_text_count,
                "zero_duration_segments": zero_duration_count,
                "invalid_time_segments": invalid_time_count,
                "overlap_candidates_truncated": overlap_truncated,
                "emotion_coverage_percent": round(100 * emotion_covered / len(timeline), 2) if timeline else 0.0,
                "excluded_segments": sum(1 for item in timeline if item["excluded"]),
            },
        },
        "manual": {
            "codebook": list(codebook.values()),
            "code_metrics": code_metrics,
            "interaction_tags": [
                {"id": key, "label": label} for key, label in ANALYSIS_INTERACTION_TAGS.items()
            ],
            "interaction_summary": interaction_summary,
            "case_code_matrix": case_code_matrix,
            "coded_segment_count": sum(1 for item in included if item["annotation"].get("codes")),
            "important_quote_count": sum(1 for item in included if item["annotation"].get("important")),
            "context_checks": context_checks,
            "analyst_memo": config["analyst_memo"],
            "interpretation_status": config["interpretation_status"],
            "orphaned_annotation_count": len(orphaned_annotations),
            "orphaned_annotations": [
                {"segment_id": segment_id, **value}
                for segment_id, value in orphaned_annotations.items()
            ],
        },
        "segments": timeline,
        "exports": {
            "json": f"/api/library/{row['id']}/analysis/export.json",
            "speakers": f"/api/library/{row['id']}/analysis/export.csv?dataset=speakers",
            "transitions": f"/api/library/{row['id']}/analysis/export.csv?dataset=transitions",
            "gaps": f"/api/library/{row['id']}/analysis/export.csv?dataset=gaps",
            "overlaps": f"/api/library/{row['id']}/analysis/export.csv?dataset=overlaps",
            "keywords": f"/api/library/{row['id']}/analysis/export.csv?dataset=keywords",
            "emotions": f"/api/library/{row['id']}/analysis/export.csv?dataset=emotions",
            "timeline": f"/api/library/{row['id']}/analysis/export.csv?dataset=timeline",
            "codes": f"/api/library/{row['id']}/analysis/export.csv?dataset=codes",
            "groups": f"/api/library/{row['id']}/analysis/export.csv?dataset=groups",
            "coded_segments": f"/api/library/{row['id']}/analysis/export.csv?dataset=coded_segments",
            "interactions": f"/api/library/{row['id']}/analysis/export.csv?dataset=interactions",
            "case_matrix": f"/api/library/{row['id']}/analysis/export.csv?dataset=case_matrix",
            "context": f"/api/library/{row['id']}/analysis/export.csv?dataset=context",
            "summary": f"/api/library/{row['id']}/analysis/export.csv?dataset=summary",
            "observations": f"/api/library/{row['id']}/analysis/export.csv?dataset=observations",
            "important_quotes": f"/api/library/{row['id']}/analysis/export.csv?dataset=important_quotes",
        },
    }
    return enrich_research_analysis(
        analysis,
        include_rows=include_research_rows,
    )


ANALYSIS_CSV_FIELDS: dict[str, list[str]] = {
    "speakers": [
        "speaker", "speaker_name", "role", "turn_count", "speaking_seconds",
        "speaking_percent", "participant_percent", "average_turn_seconds",
        "characters", "characters_per_minute", "question_candidates",
        "first_start", "last_end", "included_in_balance", "emotion_counts",
        "code_counts",
    ],
    "transitions": [
        "from_speaker", "from_name", "from_role", "to_speaker", "to_name",
        "to_role", "count", "average_gap_seconds", "overlap_candidates",
    ],
    "gaps": ["start", "end", "seconds", "previous_name", "next_name"],
    "overlaps": [
        "start", "end", "seconds", "from_speaker", "from_name",
        "to_speaker", "to_name",
    ],
    "keywords": ["term", "count", "by_speaker"],
    "emotions": [
        "speaker", "speaker_name", "model", "model_name", "label", "emotion",
        "count", "seconds",
    ],
    "timeline": [
        "index", "start", "end", "speaking_seconds", "turn_count", "speakers",
    ],
    "codes": [
        "id", "label", "description", "include_example", "exclude_example",
        "color", "segment_count", "speaking_seconds", "characters",
        "speaker_count", "important_count",
    ],
    "groups": [
        "group", "speaker_count", "turn_count", "speaking_seconds",
        "speaking_percent", "characters",
    ],
    "coded_segments": [
        "segment_id", "start", "end", "duration", "speaker", "speaker_name",
        "role", "text", "code_ids", "code_labels", "interaction_tags", "memo",
        "important", "excluded",
    ],
    "interactions": ["tag", "label", "count"],
    "case_matrix": ["speaker", "speaker_name", "role", "codes"],
    "context": ["id", "label", "ready", "kind"],
    "summary": ["section", "metric", "value"],
    "observations": ["level", "label", "message"],
    "important_quotes": [
        "segment_id", "start", "end", "speaker", "speaker_name", "role", "text",
        "code_labels", "memo", "excluded",
    ],
}
ANALYSIS_CSV_FIELDS.update(RESEARCH_CSV_FIELDS)


def analysis_csv_safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if not isinstance(value, str):
        return value
    visible = value.lstrip(" \t\r\n")
    if visible.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def analysis_csv_rows(
    analysis: dict[str, Any],
    dataset: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    automatic = analysis["automatic"]
    manual = analysis["manual"]
    code_labels = {
        str(item["id"]): str(item["label"]) for item in manual["codebook"]
    }
    coded_segments = []
    important_quotes = []
    for segment in analysis["segments"]:
        annotation = segment["annotation"]
        labels = [
            code_labels.get(str(code_id), str(code_id))
            for code_id in annotation.get("codes", [])
        ]
        row = {
            "segment_id": segment["id"],
            "start": segment["start"],
            "end": segment["end"],
            "duration": segment["duration"],
            "speaker": segment["speaker"],
            "speaker_name": segment["speaker_name"],
            "role": segment["role"],
            "text": segment["text"],
            "code_ids": annotation.get("codes", []),
            "code_labels": labels,
            "interaction_tags": annotation.get("interaction_tags", []),
            "memo": annotation.get("memo", ""),
            "important": annotation.get("important", False),
            "excluded": segment.get("excluded", False),
        }
        if any((
            row["code_ids"], row["interaction_tags"], row["memo"],
            row["important"], row["excluded"],
        )):
            coded_segments.append(row)
        if row["important"] and not row["excluded"]:
            important_quotes.append(row)
    summary_rows = [
        {"section": section, "metric": key, "value": value}
        for section, values in (
            ("overview", automatic["overview"]),
            ("balance", automatic["balance"]),
            ("moderator", automatic["moderator"]),
            ("data_quality", automatic["data_quality"]),
        )
        for key, value in values.items()
    ]
    sources: dict[str, list[dict[str, Any]]] = {
        "speakers": automatic["speaker_metrics"],
        "transitions": automatic["transitions"],
        "gaps": automatic["long_gaps"],
        "overlaps": automatic["overlap_candidates"],
        "keywords": automatic["keywords"],
        "emotions": automatic["emotions"],
        "timeline": automatic["time_bins"],
        "codes": manual["code_metrics"],
        "groups": automatic["groups"],
        "coded_segments": coded_segments,
        "interactions": manual["interaction_summary"],
        "case_matrix": manual["case_code_matrix"],
        "context": manual["context_checks"],
        "summary": summary_rows,
        "observations": automatic["observations"],
        "important_quotes": important_quotes,
    }
    sources.update(research_csv_sources(analysis))
    if dataset not in ANALYSIS_CSV_FIELDS:
        raise ValueError("出力する分析データの種類が正しくありません。")
    common = {
        "schema_version": analysis["schema_version"],
        "item_id": analysis["item"]["id"],
        "source_name": analysis["item"]["source_name"],
        "revision_count": analysis["item"]["revision_count"],
        "analysis_revision": analysis["item"]["analysis_revision"],
        "analysis_updated_at": analysis["item"]["analysis_updated_at"],
        "generated_at": analysis["generated_at"],
        "algorithm_version": analysis["algorithm_version"],
    }
    rows = [{**common, **dict(value)} for value in sources[dataset]]
    fields = list(common) + ANALYSIS_CSV_FIELDS[dataset]
    return fields, rows


def analysis_csv_content(analysis: dict[str, Any], dataset: str) -> bytes:
    fields, rows = analysis_csv_rows(analysis, dataset)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: analysis_csv_safe(row.get(key)) for key in fields})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def save_group_analysis(item_id: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("分析設定はJSONオブジェクトで送信してください。")
    row = library_row(item_id)
    if row is None:
        raise LookupError("処理済みデータが見つかりません。")
    missing_revisions = [
        key for key in ("source_revision", "analysis_revision") if key not in payload
    ]
    if missing_revisions:
        raise ValueError("保存前に分析データを再読み込みしてください。")
    if "config" in payload and not isinstance(payload["config"], dict):
        raise ValueError("分析設定の形式が正しくありません。")
    provided_config = payload.get("config")
    if (
        isinstance(provided_config, dict)
        and "exclude_moderator" in provided_config
        and not isinstance(provided_config["exclude_moderator"], bool)
    ):
        raise ValueError("司会・運営役の除外設定はtrueまたはfalseで指定してください。")
    if "annotations" in payload and not isinstance(payload["annotations"], dict):
        raise ValueError("発話注釈の形式が正しくありません。")
    provided_annotations = payload.get("annotations")
    if isinstance(provided_annotations, dict):
        for index, value in enumerate(provided_annotations.values()):
            if index >= 100000:
                break
            if not isinstance(value, dict):
                continue
            for key in ("important", "excluded"):
                if key in value and not isinstance(value[key], bool):
                    raise ValueError(f"注釈の{key}はtrueまたはfalseで指定してください。")
    segments = row_segments(row)
    source_revision = int(row["revision_count"] or 0)
    analysis_revision = int(row["analysis_revision"] or 0)
    for key, actual in (
        ("source_revision", source_revision),
        ("analysis_revision", analysis_revision),
    ):
        if key not in payload:
            continue
        try:
            expected = int(payload[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} が正しくありません。") from exc
        if expected != actual:
            raise AnalysisConflictError(
                "元データまたは分析が別の画面で更新されました。再読み込みして確認してください。"
            )
    current_config = row_analysis_config(row)
    current_annotations, orphaned_annotations = row_analysis_annotation_state(
        row, segments, current_config
    )
    config_source = payload.get("config", current_config)
    config = normalize_analysis_config(config_source)
    annotations_source = payload.get("annotations", current_annotations)
    annotations = normalize_analysis_annotations(annotations_source, segments, config)
    stored_annotations = {**orphaned_annotations, **annotations}
    now = utc_now_iso()
    with database_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE library_items SET
                analysis_config_json = ?, analysis_annotations_json = ?,
                analysis_revision = analysis_revision + 1, analysis_updated_at = ?
            WHERE id = ? AND revision_count = ? AND analysis_revision = ?
            """,
            (
                json.dumps(config, ensure_ascii=False),
                json.dumps(stored_annotations, ensure_ascii=False),
                now,
                item_id,
                source_revision,
                analysis_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise AnalysisConflictError(
                "元データまたは分析が別の画面で更新されました。再読み込みして確認してください。"
            )
    updated = library_row(item_id)
    if updated is None:
        raise LookupError("処理済みデータが見つかりません。")
    return group_analysis_for_row(updated)


WORD_CLOUD_SLOTS = (
    (320, 184, 250, 0, "middle"),
    (165, 118, 190, -8, "middle"),
    (478, 116, 190, 7, "middle"),
    (156, 232, 195, 6, "middle"),
    (480, 236, 190, -7, "middle"),
    (318, 96, 170, 0, "middle"),
    (319, 268, 180, 0, "middle"),
    (80, 170, 125, -12, "middle"),
    (560, 171, 125, 11, "middle"),
    (78, 283, 125, 0, "middle"),
    (557, 286, 125, 0, "middle"),
    (87, 86, 125, 0, "middle"),
    (551, 82, 125, 0, "middle"),
    (225, 304, 145, -5, "middle"),
    (413, 306, 145, 5, "middle"),
    (226, 58, 140, 0, "middle"),
    (411, 57, 140, 0, "middle"),
    (320, 330, 170, 0, "middle"),
)


def word_cloud_svg(source_name: str, segments: list[dict[str, Any]]) -> str:
    """Render a dependency-free word cloud as an SVG image."""
    terms = text_mining_terms(segments)
    max_count = max((count for _, count in terms), default=1)
    min_count = min((count for _, count in terms), default=1)
    palette = ("#d7f34a", "#ff9b42", "#79b791", "#efd6ac", "#b8d8d8", "#d3c4e3", "#f2b5d4", "#a7c7e7")
    words: list[str] = []
    for index, ((term, count), slot) in enumerate(zip(terms, WORD_CLOUD_SLOTS)):
        x, y, max_width, rotation, anchor = slot
        ratio = (count - min_count) / max(1, max_count - min_count)
        rank_bonus = max(0, 8 - index) * 0.7
        font_size = round(17 + ratio * 27 + rank_bonus, 1)
        label = html.escape(term[:24])
        estimated_width = len(term) * font_size * (0.95 if not term.isascii() else 0.58)
        length_attributes = (
            f' textLength="{max_width}" lengthAdjust="spacingAndGlyphs"'
            if estimated_width > max_width
            else ""
        )
        color = palette[index % len(palette)]
        words.append(
            f'<g transform="rotate({rotation} {x} {y})">'
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-size="{font_size}" fill="{color}" class="word"{length_attributes}>'
            f'<title>{label}: {count}回</title>{label}</text></g>'
        )
    if not words:
        words.append(
            '<text x="320" y="178" class="empty" text-anchor="middle">テキストデータなし</text>'
            '<text x="320" y="211" class="hint" text-anchor="middle">'
            '文字起こしを保存するとワードクラウドを表示します</text>'
        )
    title = html.escape(Path(source_name).stem[:42] or "文字起こし")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
<rect width="640" height="360" rx="24" fill="#18211d"/>
<circle cx="604" cy="34" r="86" fill="#d7f34a" opacity=".09"/>
<circle cx="38" cy="344" r="105" fill="#ff9b42" opacity=".08"/>
<text x="24" y="25" class="eyebrow">WORD CLOUD</text>
<text x="616" y="25" class="source" text-anchor="end">{title}</text>
{''.join(words)}
<text x="616" y="345" class="footer" text-anchor="end">{len(segments)} SEGMENTS</text>
<style>
text {{ font-family: "Yu Gothic UI", "Meiryo", sans-serif; }}
.word {{ font-weight:800; paint-order:stroke; stroke:#18211d; stroke-width:2px; stroke-opacity:.22; }}
.eyebrow {{ fill:#d7f34a; font-size:10px; font-weight:800; letter-spacing:2px; }}
.source {{ fill:#91a098; font-size:10px; }}
.empty {{ fill:#d7f34a; font-size:23px; font-weight:800; }}
.hint {{ fill:#91a098; font-size:12px; }}
.footer {{ fill:#91a098; font-size:9px; font-weight:800; letter-spacing:1px; }}
</style>
</svg>"""


def write_word_cloud(
    target: Path,
    source_name: str,
    segments: list[dict[str, Any]],
) -> Path:
    return atomic_write_text(target, word_cloud_svg(source_name, segments), encoding="utf-8")


def generate_word_cloud_thumbnail(
    item_id: str,
    source_name: str,
    segments: list[dict[str, Any]],
) -> Path:
    return write_word_cloud(
        THUMBNAIL_DIRECTORY / f"word_cloud_{item_id}.svg",
        source_name,
        segments,
    )


def generate_video_thumbnail(source_path: Path) -> Path:
    if not is_video_path(source_path):
        raise ValueError("サムネイルは動画ファイルだけ作成できます。")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg が見つかりません。README の手順でインストールしてください。")
    THUMBNAIL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    target = thumbnail_cache_path(source_path)
    if target.is_file() and target.stat().st_size > 0:
        return target
    last_error = ""
    for seek_at in ("00:00:01.000", "00:00:00.000"):
        temporary = temporary_output_path(target)
        try:
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                    "-ss", seek_at, "-i", str(source_path), "-frames:v", "1",
                    "-vf", "scale=640:-2:force_original_aspect_ratio=decrease",
                    "-q:v", "3", str(temporary),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            if completed.returncode == 0 and temporary.is_file() and temporary.stat().st_size > 0:
                sync_file_data(temporary)
                durable_move(temporary, target)
                return target
            last_error = completed.stderr.strip()
        except subprocess.TimeoutExpired:
            last_error = "サムネイル作成がタイムアウトしました。"
        finally:
            temporary.unlink(missing_ok=True)
    raise RuntimeError(last_error or "動画からサムネイルを作成できませんでした。")


def canonical_output_import_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def record_output_import_provenance(
    connection: sqlite3.Connection,
    item_id: str,
    paths: list[Path],
) -> None:
    for path in paths:
        if not path.name.endswith("_話者分離.json"):
            continue
        fingerprint = ""
        if path.is_file():
            try:
                fingerprint = file_sha256(path)
            except OSError:
                pass
        connection.execute(
            """
            INSERT INTO output_import_provenance (
                item_id, canonical_path, content_sha256
            ) VALUES (?, ?, ?)
            ON CONFLICT(item_id, canonical_path) DO UPDATE SET
                content_sha256 = CASE
                    WHEN excluded.content_sha256 <> ''
                    THEN excluded.content_sha256
                    ELSE output_import_provenance.content_sha256
                END
            """,
            (item_id, canonical_output_import_path(path), fingerprint),
        )


OUTPUT_ARTIFACT_SUFFIXES = (
    "_話者分離.json",
    "_話者分離.txt",
    "_話者分離.srt",
    "_ワードクラウド.svg",
    "_アウトライン.txt",
    "_感情分析.json",
    "_感情分析.csv",
    "_話者カラー字幕.ass",
    "_字幕付き.mp4",
)


def existing_output_artifacts(directory: Path, stem: str) -> list[Path]:
    return [
        path
        for suffix in OUTPUT_ARTIFACT_SUFFIXES
        if (path := directory / f"{stem}{suffix}").is_file()
    ]


def machine_json_owner_for_row(row: sqlite3.Row, files: list[Path]) -> Path | None:
    candidates = [path for path in files if path.name.endswith("_話者分離.json")]
    if not candidates:
        return None
    row_id = str(row["id"])
    id_matches = []
    for candidate in candidates:
        resolved = str(candidate.resolve())
        legacy_id = uuid.uuid5(uuid.NAMESPACE_URL, resolved).hex
        canonical_id = uuid.uuid5(
            uuid.NAMESPACE_URL, canonical_output_import_path(candidate)
        ).hex
        if row_id in {legacy_id, canonical_id}:
            id_matches.append(candidate)
    if len(id_matches) == 1:
        return id_matches[0]
    expected = Path(str(row["output_dir"])) / (
        f"{safe_output_stem(str(row['source_name']))}_話者分離.json"
    )
    expected_canonical = canonical_output_import_path(expected)
    expected_matches = [
        candidate
        for candidate in candidates
        if canonical_output_import_path(candidate) == expected_canonical
    ]
    if len(expected_matches) == 1:
        return expected_matches[0]
    return candidates[0] if len(candidates) == 1 else None


def repair_output_import_provenance(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT id, source_name, output_dir, files_json FROM library_items"
    ).fetchall()
    for row in rows:
        raw_files = json_load(row["files_json"], [])
        if not isinstance(raw_files, list):
            continue
        files = [Path(str(value)) for value in raw_files]
        owner = machine_json_owner_for_row(row, files)
        if owner is None:
            continue
        fingerprint = ""
        if owner.is_file():
            try:
                fingerprint = file_sha256(owner)
            except OSError:
                pass
        connection.execute(
            "INSERT OR IGNORE INTO output_import_provenance "
            "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
            (str(row["id"]), canonical_output_import_path(owner), fingerprint),
        )
        owner_canonical = canonical_output_import_path(owner)
        filtered = [
            value
            for value in raw_files
            if not Path(str(value)).name.endswith("_話者分離.json")
            or canonical_output_import_path(Path(str(value))) == owner_canonical
        ]
        if filtered != raw_files:
            connection.execute(
                "UPDATE library_items SET files_json = ? WHERE id = ?",
                (json.dumps(filtered, ensure_ascii=False), str(row["id"])),
            )


def import_existing_outputs() -> None:
    if not DEFAULT_OUTPUT_DIRECTORY.is_dir():
        return
    with database_connection() as connection:
        rows = connection.execute("SELECT id, files_json FROM library_items").fetchall()
        known = {str(row["id"]) for row in rows}
        referenced_json_owners: dict[str, set[str]] = {}
        for row in rows:
            files = json_load(row["files_json"], [])
            if not isinstance(files, list):
                continue
            for value in files:
                path = Path(str(value))
                if path.name.endswith("_話者分離.json"):
                    referenced_json_owners.setdefault(
                        canonical_output_import_path(path), set()
                    ).add(str(row["id"]))
        for provenance in connection.execute(
            "SELECT provenance.item_id, provenance.canonical_path "
            "FROM output_import_provenance AS provenance "
            "INNER JOIN library_items AS item ON item.id = provenance.item_id"
        ).fetchall():
            referenced_json_owners.setdefault(
                str(provenance["canonical_path"]), set()
            ).add(str(provenance["item_id"]))
        tombstones = {
            str(row["canonical_path"]): str(row["content_sha256"] or "")
            for row in connection.execute(
                "SELECT canonical_path, content_sha256 FROM output_import_tombstones"
            ).fetchall()
        }
    for json_path in DEFAULT_OUTPUT_DIRECTORY.rglob("*_話者分離.json"):
        if any(
            part.startswith(('.edit-staging-', '.edit-preparing-', '.edit-cleanup-'))
            for part in json_path.parts
        ):
            continue
        canonical_path = canonical_output_import_path(json_path)
        item_id = uuid.uuid5(uuid.NAMESPACE_URL, canonical_path).hex
        if item_id in known:
            try:
                known_fingerprint = file_sha256(json_path)
            except OSError:
                known_fingerprint = ""
            with database_connection() as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO output_import_provenance "
                    "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                    (item_id, canonical_path, known_fingerprint),
                )
            continue
        referenced_owners = referenced_json_owners.get(canonical_path, set())
        if referenced_owners:
            if len(referenced_owners) == 1:
                owner_id = next(iter(referenced_owners))
                try:
                    fingerprint = file_sha256(json_path)
                except OSError:
                    fingerprint = ""
                with database_connection() as connection:
                    connection.execute(
                        "INSERT OR IGNORE INTO output_import_provenance "
                        "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                        (owner_id, canonical_path, fingerprint),
                    )
            continue
        try:
            current_fingerprint = file_sha256(json_path)
            tombstone_fingerprint = tombstones.get(canonical_path)
            if tombstone_fingerprint is not None and (
                not tombstone_fingerprint
                or secrets.compare_digest(tombstone_fingerprint, current_fingerprint)
            ):
                continue
            payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
            segments = payload.get("segments")
            if not isinstance(segments, list):
                continue
            source_name = Path(str(payload.get("source") or json_path.name.replace("_話者分離.json", ""))).name
            stem = json_path.name[:-len("_話者分離.json")]
            files = existing_output_artifacts(json_path.parent, stem)
            created = datetime.fromtimestamp(json_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            with database_connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                upsert_library_item(
                    item_id=item_id, source_name=source_name, output_dir=json_path.parent,
                    media_path=None, language=payload.get("language"), segments=segments,
                    speaker_names=payload.get("speaker_names") if isinstance(payload.get("speaker_names"), dict) else {},
                    outline=payload.get("outline") if isinstance(payload.get("outline"), dict) else None,
                    emotion_analysis=payload.get("emotion_analysis") if isinstance(payload.get("emotion_analysis"), dict) else None,
                    files=files, write_srt=any(path.suffix.lower() == ".srt" for path in files),
                    write_json=True, created_at=created, connection=connection,
                )
                connection.execute(
                    "INSERT OR REPLACE INTO output_import_provenance "
                    "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                    (item_id, canonical_path, current_fingerprint),
                )
                connection.execute(
                    "DELETE FROM output_import_tombstones WHERE canonical_path = ?",
                    (canonical_path,),
                )
            known.add(item_id)
        except (OSError, ValueError, json.JSONDecodeError):
            continue


def clean_secret(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"your_token_here", "your_api_key_here", "hf_xxx", "sk-xxx", "aizaxxx"}:
        return ""
    return text


def load_token_config(path: Path = TOKEN_FILE) -> TokenConfig:
    """Read all credentials from tokens.json; credentials are never accepted by the UI."""
    if not path.is_file():
        return TokenConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{path.name} を読み込めません: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path.name} の最上位は JSON オブジェクトにしてください。")
    return TokenConfig(
        huggingface_token=clean_secret(raw.get("huggingface_token", raw.get("hf_token"))),
        openai_api_key=clean_secret(raw.get("openai_api_key")),
        google_api_key=clean_secret(raw.get("google_api_key", raw.get("gemini_api_key"))),
        openai_model=clean_secret(raw.get("openai_model")) or "gpt-5.6-luna",
        google_model=clean_secret(raw.get("google_model")) or "gemini-flash-latest",
    )


def available_ai_models(provider: str, config: TokenConfig) -> list[dict[str, Any]]:
    provider = str(provider or "").strip().casefold()
    if provider == "google":
        if not config.google_api_key:
            raise ValueError("Google Gemini のAPIキーが設定されていません。")
        request_object = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
            headers={"x-goog-api-key": config.google_api_key, "Accept": "application/json"},
            method="GET",
        )
    elif provider == "openai":
        if not config.openai_api_key:
            raise ValueError("OpenAI のAPIキーが設定されていません。")
        request_object = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": f"Bearer {config.openai_api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
    else:
        raise ValueError("モデル一覧を取得できるAIを選択してください。")
    try:
        with urllib.request.urlopen(request_object, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"モデル一覧APIが HTTP {exc.code} を返しました。") from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"モデル一覧を取得できません: {exc}") from exc
    models: list[dict[str, Any]] = []
    if provider == "google":
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            methods = item.get("supportedGenerationMethods")
            if not isinstance(methods, list) or "generateContent" not in methods:
                continue
            model_id = str(item.get("name") or "").removeprefix("models/").strip()
            if not model_id.startswith("gemini-") or len(model_id) > 200:
                continue
            models.append({
                "id": model_id,
                "label": clean_single_line(item.get("displayName") or model_id, 200),
                "description": clean_single_line(item.get("description"), 300),
            })
    else:
        raw_models = payload.get("data") if isinstance(payload, dict) else None
        excluded = (
            "embedding", "dall-e", "tts", "transcribe", "whisper", "moderation",
            "realtime", "audio", "image", "search", "computer-use",
        )
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            lowered = model_id.casefold()
            if (
                not model_id
                or len(model_id) > 200
                or not (lowered.startswith("gpt-") or re.fullmatch(r"o\d(?:[-.].+)?", lowered))
                or any(value in lowered for value in excluded)
            ):
                continue
            models.append({"id": model_id, "label": model_id, "description": ""})
    unique = {item["id"]: item for item in models}
    return [unique[key] for key in sorted(unique, key=str.casefold)]


def update_token_model(provider: str, model: str, path: Path = TOKEN_FILE) -> TokenConfig:
    provider = str(provider or "").strip().casefold()
    model = clean_single_line(model, 200)
    if provider not in {"openai", "google"}:
        raise ValueError("OpenAI または Google Gemini を選択してください。")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", model):
        raise ValueError("モデルIDの形式が不正です。")
    with token_config_lock:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{path.name} を更新できません: {exc}") from exc
        if not isinstance(raw, dict):
            raise RuntimeError(f"{path.name} の最上位は JSON オブジェクトにしてください。")
        raw[f"{provider}_model"] = model
        atomic_write_text(
            path,
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return load_token_config(path)


def configure_huggingface_hub_compatibility() -> None:
    """Bridge legacy pyannote callers to Hugging Face Hub v1's token API."""
    import huggingface_hub

    original_download = huggingface_hub.hf_hub_download
    if "use_auth_token" in inspect.signature(original_download).parameters:
        return
    if getattr(original_download, "_mojiokosi_compat", False):
        return

    def hf_hub_download_compat(*args: Any, **kwargs: Any) -> Any:
        legacy_token = kwargs.pop("use_auth_token", None)
        if legacy_token is not None:
            kwargs.setdefault("token", legacy_token)
        return original_download(*args, **kwargs)

    hf_hub_download_compat._mojiokosi_compat = True  # type: ignore[attr-defined]
    huggingface_hub.hf_hub_download = hf_hub_download_compat


def configure_speechbrain_lazy_import_compatibility() -> None:
    try:
        from speechbrain.utils.importutils import LazyModule
    except ImportError:
        return
    if getattr(LazyModule, "_mojiokosi_windows_inspect_compat", False):
        return
    original_getattr = LazyModule.__getattr__

    def lazy_module_getattr_compat(self: Any, attr: str) -> Any:
        if attr == "__file__" and self.lazy_module is None:
            raise AttributeError(attr)
        return original_getattr(self, attr)

    LazyModule.__getattr__ = lazy_module_getattr_compat
    LazyModule._mojiokosi_windows_inspect_compat = True


def diarization_access_error_message(model_name: str) -> str:
    repo_lines = "\n".join(f"https://huggingface.co/{repo_id}" for repo_id in DIARIZATION_ACCESS_REPOS)
    return (
        f"話者分離モデル {model_name} にアクセスできません。\n\n"
        "tokens.json の Hugging Face read token を確認し、以下のモデルページで"
        f"利用規約への同意を完了してください。\n\n{repo_lines}"
    )


def is_diarization_access_error(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    message = str(exc)
    return (
        (exc.__class__.__name__ in {"GatedRepoError", "RepositoryNotFoundError", "HfHubHTTPError"}
         and status_code in {401, 403, 404})
        or "Cannot access gated repo" in message
        or "401 Client Error" in message
        or "403 Client Error" in message
        or "'NoneType' object has no attribute 'to'" in message
    )


def create_diarization_pipeline(pipeline_class: Any, token: str, device: str) -> Any:
    parameters = inspect.signature(pipeline_class).parameters
    kwargs: dict[str, Any] = {"device": device}
    if "model_name" in parameters:
        kwargs["model_name"] = DIARIZATION_MODEL
    if "token" in parameters:
        kwargs["token"] = token
    else:
        kwargs["use_auth_token"] = token
    return pipeline_class(**kwargs)


def _stop_subprocess(process: subprocess.Popen[str]) -> None:
    """Best-effort termination used for cancellation and timeout paths."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        return
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def run_cancellable_subprocess(
    command: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: float | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a child process while regularly honoring job cancellation."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    started_at = time.monotonic()
    pending_input = input_text
    while True:
        try:
            if check_cancelled is not None:
                check_cancelled()
            remaining = None if timeout is None else timeout - (time.monotonic() - started_at)
            if remaining is not None and remaining <= 0:
                _stop_subprocess(process)
                raise subprocess.TimeoutExpired(command, timeout)
            wait_seconds = 0.25 if remaining is None else min(0.25, remaining)
            communication_input = pending_input
            pending_input = None
            communicate_kwargs: dict[str, Any] = {"timeout": wait_seconds}
            if communication_input is not None:
                communicate_kwargs["input"] = communication_input
            stdout, stderr = process.communicate(**communicate_kwargs)
            if check_cancelled is not None:
                check_cancelled()
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            if timeout is not None and time.monotonic() - started_at >= timeout:
                _stop_subprocess(process)
                raise subprocess.TimeoutExpired(command, timeout)
        except BaseException:
            _stop_subprocess(process)
            raise


def temporary_output_path(target: Path) -> Path:
    """Create a collision-resistant sibling name that preserves file suffix."""
    return target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp{target.suffix}")


def atomic_write_text(target: Path, value: str, *, encoding: str = "utf-8") -> Path:
    """Replace one text output only after its complete temporary file is durable."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    try:
        with temporary.open('w', encoding=encoding) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def atomic_write_bytes(target: Path, value: bytes) -> Path:
    """Replace a binary file only after its sibling temporary file is complete."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    try:
        with temporary.open('wb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def atomic_copy_file(
    source: Path,
    target: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    replace_existing: bool = True,
) -> Path:
    """Copy a media file without exposing a partial final destination."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    try:
        if check_cancelled is not None:
            check_cancelled()
        with source.open("rb") as input_stream, temporary.open("wb") as output_stream:
            while True:
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                output_stream.write(chunk)
                if check_cancelled is not None:
                    check_cancelled()
            output_stream.flush()
            os.fsync(output_stream.fileno())
        shutil.copystat(source, temporary)
        with temporary.open('r+b') as output_stream:
            os.fsync(output_stream.fileno())
        if check_cancelled is not None:
            check_cancelled()
        durable_move(
            temporary,
            target,
            replace_existing=replace_existing,
        )
        if check_cancelled is not None:
            check_cancelled()
    finally:
        temporary.unlink(missing_ok=True)
    return target


def audio_preprocess_label(preset: str) -> str:
    return str(AUDIO_PREPROCESS_PRESETS.get(preset, AUDIO_PREPROCESS_PRESETS["standard"])["label"])


def run_audio_preprocess(
    input_path: Path,
    output_path: Path,
    preset: str,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    if preset not in AUDIO_PREPROCESS_PRESETS:
        raise RuntimeError(f"未対応の音声前処理です: {preset}")
    filters = AUDIO_PREPROCESS_PRESETS[preset]["filters"]
    if not filters:
        return input_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:a:0",
        "-vn",
        "-af",
        ",".join(filters),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    completed = run_cancellable_subprocess(
        command,
        timeout=float(os.environ.get("MOJIOKOSI_FFMPEG_TIMEOUT_SECONDS", "7200")),
        check_cancelled=check_cancelled,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()[-1500:]
        raise RuntimeError(f"音声前処理に失敗しました: {details}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("音声前処理後のファイルが作成されませんでした。")
    return output_path


def run_audio_interval_preprocess(
    input_path: Path,
    output_path: Path,
    start: float,
    end: float,
    preset: str,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    if preset not in AUDIO_PREPROCESS_PRESETS:
        raise RuntimeError(f"未対応の音声前処理です: {preset}")
    start = max(0.0, float(start))
    end = max(start, float(end))
    if end - start < 0.05:
        raise RuntimeError("再文字起こし区間が短すぎます。")
    filters = AUDIO_PREPROCESS_PRESETS[preset]["filters"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{end - start:.3f}",
        "-map",
        "0:a:0",
        "-vn",
    ]
    if filters:
        command.extend(["-af", ",".join(filters)])
    command.extend([
        "-ac",
        "1",
        "-ar",
        str(WHISPER_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ])
    completed = run_cancellable_subprocess(
        command,
        timeout=float(os.environ.get("MOJIOKOSI_FFMPEG_CLIP_TIMEOUT_SECONDS", "300")),
        check_cancelled=check_cancelled,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()[-1500:]
        raise RuntimeError(f"再文字起こし区間の切り出しに失敗しました: {details}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("再文字起こし区間の音声ファイルが作成されませんでした。")
    return output_path


def segment_bounds(segment: dict[str, Any]) -> tuple[float, float]:
    start = float(segment.get("start", 0) or 0)
    end = float(segment.get("end", start) or start)
    if end < start:
        end = start
    return start, end


def normalize_asr_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_segments:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        start, end = segment_bounds(raw)
        item = dict(raw)
        item["start"] = start
        item["end"] = end
        item["text"] = text
        normalized.append(item)
    normalized.sort(key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))
    return normalized


def find_long_asr_gaps(
    raw_segments: list[dict[str, Any]],
    audio_duration: float,
    min_gap_seconds: float = TRIPLE_PASS_MIN_GAP_SECONDS,
) -> list[tuple[float, float]]:
    duration = max(0.0, float(audio_duration))
    minimum = max(0.05, float(min_gap_seconds))
    covered: list[tuple[float, float]] = []
    for segment in normalize_asr_segments(raw_segments):
        start, end = segment_bounds(segment)
        start = min(duration, max(0.0, start))
        end = min(duration, max(start, end))
        if end > start:
            covered.append((start, end))

    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in covered:
        if start > cursor and start - cursor >= minimum:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if duration > cursor and duration - cursor >= minimum:
        gaps.append((cursor, duration))
    return gaps


def offset_asr_segments_to_gap(
    raw_segments: list[dict[str, Any]],
    clip_start: float,
    gap_start: float,
    gap_end: float,
) -> list[dict[str, Any]]:
    shifted: list[dict[str, Any]] = []
    for raw in normalize_asr_segments(raw_segments):
        item = dict(raw)
        local_start, local_end = segment_bounds(raw)
        global_start = clip_start + local_start
        global_end = clip_start + local_end
        overlap_start = max(global_start, gap_start)
        overlap_end = min(global_end, gap_end)
        overlap_duration = overlap_end - overlap_start
        segment_duration = max(global_end - global_start, 0.001)
        if (
            overlap_duration <= 0.05
            or overlap_duration / segment_duration < TRIPLE_PASS_MIN_GAP_OVERLAP_RATIO
        ):
            continue
        # The clip includes context on both sides so Whisper does not start in
        # the middle of a phoneme. Never let that context become a duplicate
        # transcript segment outside the gap we are trying to recover.
        item["start"] = overlap_start
        item["end"] = overlap_end
        words: list[dict[str, Any]] = []
        raw_words = raw.get("words")
        if (
            not raw_words
            and overlap_duration / segment_duration < 0.85
        ):
            # Without word timestamps the text cannot be trimmed safely. A
            # context-heavy segment would duplicate or tear the neighbouring
            # conversation, so retain only segments located almost entirely
            # inside the gap.
            continue
        for raw_word in raw_words or []:
            word = dict(raw_word)
            word_start = (
                clip_start + float(word["start"])
                if word.get("start") is not None
                else global_start
            )
            word_end = (
                clip_start + float(word["end"])
                if word.get("end") is not None
                else global_end
            )
            if min(word_end, gap_end) - max(word_start, gap_start) <= 0.0:
                continue
            word["start"] = max(word_start, gap_start)
            word["end"] = min(word_end, gap_end)
            words.append(word)
        if isinstance(raw_words, list) and raw_words and not words:
            continue
        if words:
            item["words"] = words
            word_text = _joined_word_text([
                str(word.get("word", word.get("text", "")))
                for word in words
            ])
            if word_text:
                item["text"] = word_text
        shifted.append(item)
    return shifted


def merged_interval_coverage(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
    padding: float = QUIET_SUPPLEMENT_EDGE_PADDING,
) -> float:
    candidate_start, candidate_end = segment_bounds(candidate)
    duration = max(candidate_end - candidate_start, 0.001)
    intervals: list[tuple[float, float]] = []
    for segment in accepted:
        start, end = segment_bounds(segment)
        overlap_start = max(candidate_start, start - padding)
        overlap_end = min(candidate_end, end + padding)
        if overlap_end > overlap_start:
            intervals.append((overlap_start, overlap_end))
    if not intervals:
        return 0.0
    intervals.sort()
    covered = 0.0
    current_start, current_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            covered += current_end - current_start
            current_start, current_end = start, end
    covered += current_end - current_start
    return min(1.0, covered / duration)


def normalize_text_for_merge(text: str) -> str:
    text = re.sub(r"[\s\u3000、。,.!?！？「」『』（）()【】\[\]・…:：;；\"'`~〜\-ー]+", "", text)
    return text.lower()


def has_near_duplicate_text(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
    window_seconds: float = QUIET_SUPPLEMENT_TEXT_WINDOW_SECONDS,
) -> bool:
    candidate_text = normalize_text_for_merge(str(candidate.get("text", "")))
    if not candidate_text:
        return False
    candidate_start, candidate_end = segment_bounds(candidate)
    for segment in accepted:
        start, end = segment_bounds(segment)
        if end < candidate_start - window_seconds or start > candidate_end + window_seconds:
            continue
        text = normalize_text_for_merge(str(segment.get("text", "")))
        if not text:
            continue
        if (
            candidate_text == text
            and min(len(candidate_text), len(text)) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS
        ):
            temporal_distance = max(start - candidate_end, candidate_start - end, 0.0)
            if temporal_distance <= 1.25:
                return True
            continue
        if (
            len(candidate_text) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS
            or len(text) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS
        ):
            continue
        if candidate_text in text or text in candidate_text:
            return True
        temporal_distance = max(start - candidate_end, candidate_start - end, 0.0)
        if (
            temporal_distance <= window_seconds
            and difflib.SequenceMatcher(None, candidate_text, text).ratio() >= 0.86
        ):
            return True
    return False


def asr_segment_quality_ok(segment: dict[str, Any]) -> bool:
    start, end = segment_bounds(segment)
    if end - start < QUIET_SUPPLEMENT_MIN_DURATION:
        return False
    no_speech_prob = segment.get("no_speech_prob")
    if no_speech_prob is not None and float(no_speech_prob) > QUIET_SUPPLEMENT_MAX_NO_SPEECH_PROB:
        return False
    avg_logprob = segment.get("avg_logprob")
    if avg_logprob is not None and float(avg_logprob) < QUIET_SUPPLEMENT_MIN_AVG_LOGPROB:
        return False
    compression_ratio = segment.get("compression_ratio")
    if compression_ratio is not None and float(compression_ratio) > QUIET_SUPPLEMENT_MAX_COMPRESSION_RATIO:
        return False
    return True


def should_add_supplemental_segment(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
) -> bool:
    if not asr_segment_quality_ok(candidate):
        return False
    if has_near_duplicate_text(candidate, accepted):
        return False
    overlap_ratio = merged_interval_coverage(candidate, accepted)
    if overlap_ratio <= QUIET_SUPPLEMENT_LOW_OVERLAP_RATIO:
        return True
    return overlap_ratio <= QUIET_SUPPLEMENT_PARTIAL_OVERLAP_RATIO


def merge_supplemental_asr_segments(
    primary_segments: list[dict[str, Any]],
    supplemental_runs: list[tuple[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    accepted = normalize_asr_segments(primary_segments)
    added_counts: dict[str, int] = {}
    for label, raw_segments in supplemental_runs:
        added = 0
        for candidate in normalize_asr_segments(raw_segments):
            if should_add_supplemental_segment(candidate, accepted):
                accepted.append(candidate)
                accepted.sort(key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))
                added += 1
        added_counts[label] = added
    return accepted, added_counts


def display_time(seconds: float) -> str:
    total = int(max(0.0, float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def default_speaker_name(label: str | None) -> str:
    if not label:
        return "話者（未判定）"
    suffix = label.rsplit("_", 1)[-1]
    return f"話者 {int(suffix) + 1}" if suffix.isdigit() else label


def segment_speaker(segment: dict[str, Any]) -> str | None:
    if segment.get("speaker"):
        return str(segment["speaker"])
    for word in segment.get("words") or []:
        if word.get("speaker"):
            return str(word["speaker"])
    return None


def _finite_word_time(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _joined_word_text(parts: list[str]) -> str:
    """Join WhisperX words without adding visible spaces to Japanese text."""
    if not parts:
        return ""
    if any(part[:1].isspace() or part[-1:].isspace() for part in parts):
        return "".join(parts).strip()
    if any(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", part) for part in parts):
        return "".join(parts).strip()
    text = ""
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if not text or re.fullmatch(r"[,.;:!?%\)\]\}]", token):
            text += token
        elif text.endswith(("(", "[", "{")):
            text += token
        else:
            text += " " + token
    return text.strip()


def _word_speaker_segments(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Split one WhisperX segment at word-level speaker transitions."""
    raw_words = raw.get("words")
    if not isinstance(raw_words, list):
        return []
    words: list[dict[str, Any]] = []
    for value in raw_words:
        if not isinstance(value, dict):
            continue
        text = str(value.get("word", value.get("text", "")))
        if text.strip():
            words.append({**value, "_text": text})
    explicit_speakers = [str(word["speaker"]) for word in words if word.get("speaker")]
    if not words or not explicit_speakers:
        return []

    fallback_speaker = str(raw["speaker"]) if raw.get("speaker") else explicit_speakers[0]
    next_speakers: list[str | None] = [None] * len(words)
    next_speaker: str | None = None
    for index in range(len(words) - 1, -1, -1):
        if words[index].get("speaker"):
            next_speaker = str(words[index]["speaker"])
        next_speakers[index] = next_speaker

    segment_start, segment_end = segment_bounds(raw)
    resolved: list[dict[str, Any]] = []
    previous_speaker: str | None = None
    previous_end = segment_start
    for index, word in enumerate(words):
        speaker = (
            str(word["speaker"])
            if word.get("speaker")
            else previous_speaker or next_speakers[index] or fallback_speaker
        )
        start = _finite_word_time(word.get("start"))
        end = _finite_word_time(word.get("end"))
        start = max(segment_start, start if start is not None else previous_end)
        if end is None:
            next_start = None
            for following in words[index + 1:]:
                next_start = _finite_word_time(following.get("start"))
                if next_start is not None:
                    break
            end = next_start if next_start is not None else segment_end
        end = max(start, end)
        resolved.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": word["_text"],
        })
        previous_speaker = speaker
        previous_end = end

    groups: list[dict[str, Any]] = []
    for word in resolved:
        if groups and groups[-1]["speaker"] == word["speaker"]:
            groups[-1]["end"] = max(groups[-1]["end"], word["end"])
            groups[-1]["_parts"].append(word["text"])
        else:
            groups.append({
                "start": word["start"],
                "end": word["end"],
                "speaker": word["speaker"],
                "_parts": [word["text"]],
            })

    # Diarization occasionally assigns one short word in the middle of a
    # continuous utterance to another speaker. Collapse only A-B-A islands;
    # keep common Japanese backchannels because those are often real turns.
    for index in range(1, len(groups) - 1):
        previous = groups[index - 1]
        current = groups[index]
        following = groups[index + 1]
        duration = max(0.0, float(current["end"]) - float(current["start"]))
        island_text = normalize_text_for_merge(_joined_word_text(current["_parts"]))
        if (
            previous["speaker"] == following["speaker"]
            and current["speaker"] != previous["speaker"]
            and duration <= SHORT_SPEAKER_ISLAND_MAX_SECONDS
            and island_text not in SPEAKER_BACKCHANNEL_TEXTS
        ):
            current["speaker"] = previous["speaker"]

    smoothed: list[dict[str, Any]] = []
    for group in groups:
        if smoothed and smoothed[-1]["speaker"] == group["speaker"]:
            smoothed[-1]["end"] = max(smoothed[-1]["end"], group["end"])
            smoothed[-1]["_parts"].extend(group["_parts"])
        else:
            smoothed.append(group)
    groups = smoothed
    for group in groups:
        group["text"] = _joined_word_text(group.pop("_parts"))
    return [group for group in groups if group["text"]]


def make_display_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preserve word speaker turns, then safely merge adjacent same-speaker chunks."""
    normalized: list[dict[str, Any]] = []
    for raw in raw_segments:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        word_segments = _word_speaker_segments(raw)
        if len({item["speaker"] for item in word_segments}) > 1:
            normalized.extend(word_segments)
            continue
        start, end = segment_bounds(raw)
        normalized.append({
            "start": start,
            "end": end,
            "speaker": word_segments[0]["speaker"] if word_segments else segment_speaker(raw),
            "text": text,
        })

    normalized.sort(key=lambda item: (item["start"], item["end"]))
    # Detailed quiet-speech recovery can expose a very short A-B-A speaker
    # island across ASR segment boundaries. Repair only a non-backchannel
    # fragment surrounded by the same speaker; substantive short turns remain.
    for index in range(1, len(normalized) - 1):
        previous = normalized[index - 1]
        current = normalized[index]
        following = normalized[index + 1]
        duration = max(0.0, float(current["end"]) - float(current["start"]))
        island_text = normalize_text_for_merge(str(current.get("text") or ""))
        if (
            previous.get("speaker") == following.get("speaker")
            and current.get("speaker") != previous.get("speaker")
            and island_text not in SPEAKER_BACKCHANNEL_TEXTS
            and (
                duration <= SHORT_SPEAKER_ISLAND_MAX_SECONDS
                or (duration <= 1.2 and len(island_text) <= 8)
            )
        ):
            current["speaker"] = previous.get("speaker")
    merged: list[dict[str, Any]] = []
    for current in normalized:
        if (
            merged
            and current["speaker"] is not None
            and merged[-1]["speaker"] == current["speaker"]
            and current["start"] >= merged[-1]["start"]
            and current["start"] - merged[-1]["end"] <= 1.2
        ):
            merged[-1]["end"] = max(merged[-1]["end"], current["end"])
            merged[-1]["text"] += " " + current["text"]
        else:
            merged.append(dict(current))
    return merged


def format_outline_text(source_name: str, outline: dict[str, Any]) -> str:
    lines = ["議題・アウトライン", f"元ファイル: {source_name}", ""]
    sections = outline.get("sections") if isinstance(outline, dict) else None
    if not isinstance(sections, list) or not sections:
        lines.append("アウトラインは作成されませんでした。")
        return "\n".join(lines)
    for index, section in enumerate(sections, 1):
        title = str(section.get("title", "")).strip() or f"議題 {index}"
        start = display_time(float(section.get("start", 0)))
        end = display_time(float(section.get("end", section.get("start", 0))))
        lines.append(f"{index}. [{start} - {end}] {title}")
        bullets = section.get("bullets")
        if isinstance(bullets, list):
            for bullet in bullets:
                text = str(bullet).strip()
                if text:
                    lines.append(f"   - {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def aist_emotion_model_keys(choice: str) -> list[str]:
    if choice == "both":
        return ["kushinada", "izanami"]
    if choice in AIST_EMOTION_MODELS:
        return [choice]
    raise ValueError("感情分析モデルの指定が不正です。")


def emotion_label_ja(label: str | None) -> str:
    text = str(label or "").strip()
    if not text:
        return "不明"
    key = re.sub(r"[^a-zA-Z]", "", text).lower()
    return AIST_EMOTION_LABEL_JA.get(key, text)


def segment_emotion_display(segment: dict[str, Any]) -> str:
    emotions = segment.get("emotions")
    if not isinstance(emotions, dict) or not emotions:
        return ""
    parts: list[str] = []
    ordered_keys = [key for key in ("kushinada", "izanami") if key in emotions]
    ordered_keys.extend(sorted(key for key in emotions if key not in ordered_keys))
    for model_key in ordered_keys:
        data = emotions.get(model_key)
        if not isinstance(data, dict):
            continue
        model_name = str(data.get("model_name") or AIST_EMOTION_MODELS.get(model_key, {}).get("label") or model_key)
        label = str(data.get("label_ja") or emotion_label_ja(data.get("label")))
        confidence = data.get("confidence")
        if isinstance(confidence, (int, float)):
            parts.append(f"{model_name}: {label} {float(confidence):.2f}")
        else:
            parts.append(f"{model_name}: {label}")
    return " / ".join(parts)


def build_emotion_analysis_summary(
    segments: list[dict[str, Any]],
    model_keys: list[str],
    *,
    status: str = "completed",
    error: str = "",
) -> dict[str, Any]:
    model_infos = [
        {
            "key": key,
            "name": AIST_EMOTION_MODELS[key]["display"],
            "repo": AIST_EMOTION_MODELS[key]["emotion_repo"],
            "fold": AIST_EMOTION_MODELS[key]["fold"],
            "reference_accuracy": AIST_EMOTION_MODELS[key]["reference_accuracy"],
        }
        for key in model_keys
        if key in AIST_EMOTION_MODELS
    ]
    label_counts: dict[str, dict[str, dict[str, Any]]] = {}
    by_speaker: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    analyzed_segments = 0
    for segment in segments:
        emotions = segment.get("emotions")
        if not isinstance(emotions, dict) or not emotions:
            continue
        analyzed_segments += 1
        speaker = str(segment.get("speaker") or "UNKNOWN")
        for model_key, data in emotions.items():
            if not isinstance(data, dict):
                continue
            label = str(data.get("label") or "unknown")
            label_ja = str(data.get("label_ja") or emotion_label_ja(label))
            model_bucket = label_counts.setdefault(model_key, {})
            entry = model_bucket.setdefault(label, {"label": label, "label_ja": label_ja, "count": 0})
            entry["count"] += 1
            speaker_bucket = by_speaker.setdefault(speaker, {}).setdefault(model_key, {})
            speaker_entry = speaker_bucket.setdefault(label, {"label": label, "label_ja": label_ja, "count": 0})
            speaker_entry["count"] += 1
    payload: dict[str, Any] = {
        "enabled": True,
        "status": status,
        "source": "audio",
        "unit": "segment",
        "models": model_infos,
        "analyzed_segments": analyzed_segments,
        "label_counts": label_counts,
        "by_speaker": by_speaker,
    }
    if error:
        payload["error"] = error
    return payload


def emotion_segments_for_output(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(segments):
        emotions = item.get("emotions")
        if not isinstance(emotions, dict):
            emotions = {}
        speaker = item.get("speaker")
        speaker_label = str(speaker) if speaker else ""
        rows.append({
            "index": index,
            "start": round(float(item.get("start", 0)), 3),
            "end": round(float(item.get("end", item.get("start", 0))), 3),
            "speaker": speaker_label,
            "speaker_name": speaker_names.get(speaker_label, "") if speaker_label else "",
            "text": str(item.get("text", "")).strip(),
            "emotions": emotions,
        })
    return rows


def emotion_csv_text(segments: list[dict[str, Any]], speaker_names: dict[str, str]) -> str:
    buffer = io.StringIO(newline="")
    fieldnames = [
        "index",
        "start",
        "end",
        "speaker",
        "speaker_name",
        "model",
        "model_repo",
        "fold",
        "label",
        "label_ja",
        "confidence",
        "text",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for index, item in enumerate(segments):
        emotions = item.get("emotions")
        if not isinstance(emotions, dict) or not emotions:
            continue
        speaker = str(item.get("speaker") or "")
        for model_key, data in emotions.items():
            if not isinstance(data, dict):
                continue
            row = {
                "index": index,
                "start": round(float(item.get("start", 0)), 3),
                "end": round(float(item.get("end", item.get("start", 0))), 3),
                "speaker": speaker,
                "speaker_name": speaker_names.get(speaker, ""),
                "model": data.get("model_name", model_key),
                "model_repo": data.get("model_repo", ""),
                "fold": data.get("fold", ""),
                "label": data.get("label", ""),
                "label_ja": data.get("label_ja", ""),
                "confidence": "" if data.get("confidence") is None else data.get("confidence"),
                "text": str(item.get("text", "")).strip(),
            }
            writer.writerow({key: analysis_csv_safe(value) for key, value in row.items()})
    return buffer.getvalue()


def safe_output_stem(source_name: str) -> str:
    stem = Path(source_name).stem.strip()
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).rstrip(" .")
    return stem[:180] or "transcript"


def job_output_directory(output_root: Path, source_name: str, job_id: str) -> Path:
    """Return a unique, readable folder for one transcription execution."""
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    source_stem = safe_output_stem(source_name)[:72].rstrip(" ._") or "transcript"
    return output_root / f"{timestamp}_{source_stem}_{job_id[:8]}"


def manual_output_directory(source_name: str, item_id: str) -> Path:
    """Give every manually-created record an output directory of its own."""
    source_stem = safe_output_stem(source_name)[:72].rstrip(" ._") or "transcript"
    return DEFAULT_OUTPUT_DIRECTORY / f"manual_{source_stem}_{item_id[:8]}"


def speaker_theme_color_map(
    segments: list[dict[str, Any]],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Return stable, distinct RGB colors for every speaker label."""
    profiles = speaker_profiles if isinstance(speaker_profiles, dict) else {}
    labels = sorted({str(item.get("speaker") or "UNKNOWN") for item in segments})
    colors: dict[str, str] = {}
    for index, label in enumerate(labels):
        profile = profiles.get(label)
        profile = profile if isinstance(profile, dict) else {}
        requested = clean_single_line(profile.get("theme_color"), 7).upper()
        colors[label] = (
            requested
            if re.fullmatch(r"#[0-9A-F]{6}", requested)
            else SPEAKER_THEME_COLORS[index % len(SPEAKER_THEME_COLORS)]
        )
    return colors


def rgb_to_ass_color(value: str) -> str:
    """Convert #RRGGBB to libass' &H00BBGGRR format."""
    normalized = value.lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", normalized):
        normalized = "FFFFFF"
    red, green, blue = normalized[0:2], normalized[2:4], normalized[4:6]
    return f"&H00{blue}{green}{red}"


def ass_time(seconds: Any) -> str:
    centiseconds = max(0, round(float(seconds or 0) * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def ass_escape_text(value: Any) -> str:
    text = str(value or "").strip()
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r\n", r"\N")
        .replace("\r", r"\N")
        .replace("\n", r"\N")
    )


def subtitle_text_width(value: str, font_size: int) -> float:
    """Estimate rendered subtitle width for mixed Japanese and Latin text."""
    width = 0.0
    for character in str(value or ""):
        if character == "\t":
            width += font_size * 2.0
        elif character.isspace():
            width += font_size * 0.35
        elif unicodedata.east_asian_width(character) in {"W", "F", "A"}:
            width += font_size
        else:
            width += font_size * 0.58
    return width


SUBTITLE_BREAK_AFTER = frozenset("、。！？!?，,．.：:；;）)]｝}」』】〉》・ ")


def wrap_subtitle_lines(value: Any, max_width: float, font_size: int) -> list[str]:
    """Wrap text before it reaches the video's horizontal safe area."""
    maximum = max(float(font_size) * 4.0, float(max_width))
    lines: list[str] = []
    paragraphs = re.split(r"\r\n|\r|\n", str(value or "").strip())
    for paragraph in paragraphs:
        remaining = paragraph.strip()
        if not remaining:
            if lines and lines[-1]:
                lines.append("")
            continue
        while remaining:
            current = ""
            last_break = 0
            for character in remaining:
                candidate = current + character
                if current and subtitle_text_width(candidate, font_size) > maximum:
                    break
                current = candidate
                if character in SUBTITLE_BREAK_AFTER:
                    last_break = len(current)
            if len(current) == len(remaining):
                lines.append(current.strip())
                break
            if not current:
                current = remaining[0]
            minimum_break_width = maximum * 0.45
            if (
                last_break > 0
                and subtitle_text_width(current[:last_break], font_size) >= minimum_break_width
            ):
                split_at = last_break
            else:
                split_at = len(current)
            line = remaining[:split_at].strip()
            if line:
                lines.append(line)
            remaining = remaining[split_at:].lstrip()
    return lines or [""]


def subtitle_text_pages(
    value: Any,
    max_width: float,
    font_size: int,
    max_lines: int = 2,
) -> list[str]:
    lines = wrap_subtitle_lines(value, max_width, font_size)
    page_size = max(1, int(max_lines))
    return ["\n".join(lines[index:index + page_size]) for index in range(0, len(lines), page_size)]


MEDIA_SESSION_DATE_TAGS = (
    "com.apple.quicktime.creationdate",
    "creation_time",
    "date",
)


def media_metadata_session_date(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> str:
    """Read an embedded recording date without guessing from filesystem times."""
    if not is_video_path(source_path) or shutil.which("ffprobe") is None:
        return ""
    try:
        completed = run_cancellable_subprocess(
            [
                "ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags",
                "-of", "json", str(source_path.resolve()),
            ],
            timeout=30,
            check_cancelled=check_cancelled,
        )
        if completed.returncode != 0:
            return ""
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            return ""
        tag_sets: list[dict[str, Any]] = []
        format_data = payload.get("format")
        if isinstance(format_data, dict) and isinstance(format_data.get("tags"), dict):
            tag_sets.append(format_data["tags"])
        streams = payload.get("streams")
        if isinstance(streams, list):
            tag_sets.extend(
                stream["tags"]
                for stream in streams
                if isinstance(stream, dict) and isinstance(stream.get("tags"), dict)
            )
        normalized_tag_sets = [
            {str(key).casefold(): value for key, value in tags.items()}
            for tags in tag_sets
        ]
        for tag_name in MEDIA_SESSION_DATE_TAGS:
            for tags in normalized_tag_sets:
                raw_value = str(tags.get(tag_name, "")).strip()
                match = re.search(r"(?<!\d)(\d{4})[-:/](\d{2})[-:/](\d{2})(?!\d)", raw_value)
                if not match:
                    continue
                candidate = "-".join(match.groups())
                try:
                    datetime.strptime(candidate, "%Y-%m-%d")
                except ValueError:
                    continue
                return candidate
    except InterruptedError:
        raise
    except (OSError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        return ""
    return ""


def session_profile_from_media(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, str]:
    session_date = media_metadata_session_date(source_path, check_cancelled)
    if not session_date:
        return {}
    return {
        "session_date": session_date,
        "session_date_source": "media_metadata",
    }


def probe_video_dimensions(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[int, int]:
    """Return displayed video dimensions, accounting for rotation metadata."""
    if shutil.which("ffprobe") is None:
        return 1920, 1080
    try:
        completed = run_cancellable_subprocess(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height:stream_tags=rotate:stream_side_data=rotation",
                "-of", "json", str(source_path.resolve()),
            ],
            timeout=30,
            check_cancelled=check_cancelled,
        )
        payload = json.loads(completed.stdout) if completed.returncode == 0 else {}
        streams = payload.get("streams") if isinstance(payload, dict) else None
        stream = streams[0] if isinstance(streams, list) and streams else {}
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        rotation = int((stream.get("tags") or {}).get("rotate") or 0)
        for side_data in stream.get("side_data_list") or []:
            if isinstance(side_data, dict) and side_data.get("rotation") is not None:
                rotation = int(side_data["rotation"])
                break
        if width > 0 and height > 0:
            return (height, width) if abs(rotation) % 180 == 90 else (width, height)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        pass
    return 1920, 1080


def write_ass_subtitles(
    target: Path,
    source_name: str,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    video_width: int = 1920,
    video_height: int = 1080,
) -> Path:
    colors = speaker_theme_color_map(segments, speaker_profiles)
    play_res_x = max(160, int(video_width))
    play_res_y = max(90, int(video_height))
    scale = max(0.15, min(play_res_x / 1920.0, play_res_y / 1080.0))
    font_size = max(8, round(48 * scale))
    margin_h = max(8, round(90 * scale))
    margin_v = max(6, round(58 * scale))
    outline = max(1, round(3 * scale))
    shadow = max(1, round(scale))
    safe_text_width = max(font_size * 6.0, play_res_x - 2.0 * margin_h)
    header = f"""[Script Info]
Title: {ass_escape_text(source_name)}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Yu Gothic UI,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for item in segments:
        label = str(item.get("speaker") or "UNKNOWN")
        name = str(speaker_names.get(label) or default_speaker_name(label)).strip()
        start = max(0.0, float(item.get("start", 0) or 0))
        end = max(start + 0.2, float(item.get("end", start) or start))
        color = rgb_to_ass_color(colors.get(label, "#FFFFFF"))
        name_text = ass_escape_text(name)
        pages = subtitle_text_pages(item.get("text", ""), safe_text_width, font_size)
        duration = end - start
        for page_index, page in enumerate(pages):
            page_start = start + duration * page_index / len(pages)
            page_end = start + duration * (page_index + 1) / len(pages)
            body_text = ass_escape_text(page)
            dialogue = f"{{\\c{color}\\b1}}{name_text}{{\\rDefault}}\\N{body_text}"
            events.append(
                f"Dialogue: 0,{ass_time(page_start)},{ass_time(page_end)},Default,{ass_escape_text(label)},"
                f"0,0,0,,{dialogue}"
            )
    return atomic_write_text(
        target,
        header + "\n".join(events) + ("\n" if events else ""),
        encoding="utf-8-sig",
    )


def burn_ass_subtitles_into_video(
    source_path: Path,
    ass_path: Path,
    target: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    if not is_video_path(source_path):
        raise ValueError("字幕焼き込み動画は MP4/M4V/MOV/MKV からだけ作成できます。")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("字幕動画の作成に必要な ffmpeg が見つかりません。")
    if check_cancelled is not None:
        check_cancelled()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    escaped_ass_name = (
        ass_path.name.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )
    try:
        completed = run_cancellable_subprocess(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", str(source_path.resolve()),
                "-vf", f"ass='{escaped_ass_name}'",
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-max_muxing_queue_size", "2048",
                temporary.name,
            ],
            cwd=str(target.parent),
            timeout=float(os.environ.get("MOJIOKOSI_FFMPEG_TIMEOUT_SECONDS", "7200")),
            check_cancelled=check_cancelled,
        )
        if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            details = completed.stderr.strip()[-2000:]
            raise RuntimeError("字幕動画を作成できませんでした。" + (f"\n{details}" if details else ""))
        if check_cancelled is not None:
            check_cancelled()
        sync_file_data(temporary)
        durable_move(temporary, target)
        if check_cancelled is not None:
            check_cancelled()
    finally:
        temporary.unlink(missing_ok=True)
    return target


def write_subtitled_video_assets(
    source_path: Path,
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Path]:
    stem = safe_output_stem(source_name)
    if check_cancelled is not None:
        check_cancelled()
    video_width, video_height = probe_video_dimensions(source_path, check_cancelled)
    ass_path = write_ass_subtitles(
        output_dir / f"{stem}_話者カラー字幕.ass",
        source_name,
        segments,
        speaker_names,
        speaker_profiles,
        video_width,
        video_height,
    )
    if check_cancelled is not None:
        check_cancelled()
    video_path = burn_ass_subtitles_into_video(
        source_path,
        ass_path,
        output_dir / f"{stem}_字幕付き.mp4",
        check_cancelled,
    )
    return [ass_path, video_path]


def write_outputs(
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    language: str | None,
    speaker_names: dict[str, str],
    write_srt: bool,
    write_json: bool,
    outline: dict[str, Any] | None = None,
    emotion_analysis: dict[str, Any] | None = None,
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_output_stem(source_name)
    written: list[Path] = []

    def check() -> None:
        if check_cancelled is not None:
            check_cancelled()

    def write_text(target: Path, value: str, encoding: str = "utf-8") -> None:
        check()
        atomic_write_text(target, value, encoding=encoding)
        check()

    def name_for(label: str | None) -> str:
        if label and speaker_names.get(label, "").strip():
            return speaker_names[label].strip()
        return default_speaker_name(label)

    # JSON is the durable machine-readable result and is intentionally written
    # before every optional presentation format.
    theme_colors = speaker_theme_color_map(segments, speaker_profiles)
    json_path = output_dir / f"{stem}_話者分離.json"
    payload = {
        "source": source_name,
        "language": language,
        "speaker_names": speaker_names,
        "speaker_theme_colors": theme_colors,
        "speaker_profiles": speaker_profiles or {},
        "speakers": [
            {
                "label": label,
                "name": speaker_names.get(label) or default_speaker_name(label),
                "theme_color": color,
            }
            for label, color in theme_colors.items()
        ],
        "segments": segments,
    }
    if outline:
        payload["outline"] = outline
    if emotion_analysis:
        payload["emotion_analysis"] = emotion_analysis
    write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
    written.append(json_path)

    text_path = output_dir / f"{stem}_話者分離.txt"
    lines = [f"元ファイル: {source_name}", ""]
    for item in segments:
        emotion_text = segment_emotion_display(item)
        header = f"[{display_time(item['start'])} - {display_time(item['end'])}] {name_for(item.get('speaker'))}"
        if emotion_text:
            header = f"{header} / 感情: {emotion_text}"
        lines.extend([
            header,
            str(item.get("text", "")).strip(),
            "",
        ])
    write_text(text_path, "\n".join(lines))
    written.append(text_path)

    word_cloud_path = output_dir / f"{stem}_ワードクラウド.svg"
    check()
    write_word_cloud(word_cloud_path, source_name, segments)
    check()
    written.append(word_cloud_path)

    if write_srt:
        srt_path = output_dir / f"{stem}_話者分離.srt"
        blocks = [
            "\n".join([
                str(index),
                f"{srt_time(item['start'])} --> {srt_time(item['end'])}",
                f"{name_for(item.get('speaker'))}: {str(item.get('text', '')).strip()}",
            ])
            for index, item in enumerate(segments, 1)
        ]
        write_text(srt_path, "\n\n".join(blocks) + ("\n" if blocks else ""))
        written.append(srt_path)

    if outline:
        outline_path = output_dir / f"{stem}_アウトライン.txt"
        write_text(outline_path, format_outline_text(source_name, outline))
        written.append(outline_path)
    if emotion_analysis:
        emotion_payload = {
            "source": source_name,
            "language": language,
            "speaker_names": speaker_names,
            **emotion_analysis,
            "segments": emotion_segments_for_output(segments, speaker_names),
        }
        emotion_json_path = output_dir / f"{stem}_感情分析.json"
        write_text(
            emotion_json_path,
            json.dumps(emotion_payload, ensure_ascii=False, indent=2),
        )
        written.append(emotion_json_path)
        csv_body = emotion_csv_text(segments, speaker_names)
        if csv_body.count("\n") > 1:
            emotion_csv_path = output_dir / f"{stem}_感情分析.csv"
            write_text(emotion_csv_path, csv_body, encoding="utf-8-sig")
            written.append(emotion_csv_path)
    check()
    return written


def is_huggingface_access_error(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    message = str(exc)
    return (
        status_code in {401, 403, 404}
        or exc.__class__.__name__ in {"GatedRepoError", "RepositoryNotFoundError", "HfHubHTTPError"}
        or "Cannot access gated repo" in message
        or "401 Client Error" in message
        or "403 Client Error" in message
    )


def aist_model_access_error_message(repo_id: str) -> str:
    return (
        f"AIST感情分析モデル {repo_id} にアクセスできません。"
        f"Hugging Faceで利用条件に同意し、tokens.jsonのhuggingface_tokenを確認してください。\n"
        f"https://huggingface.co/{repo_id}"
    )


def aist_cache_dir(repo_id: str) -> Path:
    return APP_DIRECTORY / "models" / "aist" / repo_id.replace("/", "__")


def snapshot_download_to_local(
    repo_id: str,
    token: str,
    allow_patterns: list[str],
    status: Callable[[str], None],
) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub が見つかりません。run.batで環境を再セットアップしてください。") from exc
    local_dir = aist_cache_dir(repo_id)
    local_dir.mkdir(parents=True, exist_ok=True)
    status(f"Hugging FaceからAISTモデルを確認しています: {repo_id}")
    try:
        downloaded = snapshot_download(
            repo_id=repo_id,
            token=token,
            local_dir=str(local_dir),
            allow_patterns=allow_patterns,
        )
    except Exception as exc:
        if is_huggingface_access_error(exc):
            raise RuntimeError(aist_model_access_error_message(repo_id)) from exc
        raise RuntimeError(f"AISTモデル {repo_id} の取得に失敗しました: {exc}") from exc
    return Path(downloaded)


def resolve_s3prl_runtime_dir() -> Path:
    candidates: list[Path] = []
    env_root = os.environ.get("MOJIOKOSI_S3PRL_ROOT", "").strip().strip('"')
    if env_root:
        candidates.append(Path(env_root))
    candidates.extend([
        APP_DIRECTORY / "models" / "s3prl-v0.4.17",
        APP_DIRECTORY / "models" / "s3prl-v0.4.17" / "s3prl",
    ])
    for candidate in candidates:
        expanded = candidate.expanduser()
        if (expanded / "run_downstream.py").is_file():
            return expanded.resolve()
        if (expanded / "s3prl" / "run_downstream.py").is_file():
            return (expanded / "s3prl").resolve()
    raise RuntimeError(
        "AIST感情分析にはS3PRL v0.4.17のソースが必要です。"
        "このフォルダの setup_emotion.bat を一度実行してください。"
    )


def ensure_s3prl_importable(
    runtime_dir: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_dir.parent) + os.pathsep + env.get("PYTHONPATH", "")
    completed = run_cancellable_subprocess(
        [
            sys.executable,
            "-c",
            (
                "import s3prl, soundfile, torch, torchaudio, yaml; "
                "assert 'soundfile' in torchaudio.list_audio_backends(), "
                "'TorchAudio SoundFile backend is unavailable'"
            ),
        ],
        cwd=str(runtime_dir),
        env=env,
        timeout=float(os.environ.get("MOJIOKOSI_EMOTION_IMPORT_TIMEOUT_SECONDS", "180")),
        check_cancelled=check_cancelled,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()[-1200:]
        raise RuntimeError(
            "AIST感情分析用のS3PRL依存関係を読み込めません。"
            "setup_emotion.bat を実行してください。\n" + details
        )


def copy_tree_files(source_root: Path, target_root: Path) -> None:
    if not source_root.is_dir():
        return
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        target = target_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def prepare_aist_s3prl_files(
    model_key: str,
    hf_token: str,
    runtime_dir: Path,
    status: Callable[[str], None],
) -> Path:
    config = AIST_EMOTION_MODELS[model_key]
    emotion_snapshot = snapshot_download_to_local(
        config["emotion_repo"],
        hf_token,
        [
            "README.md",
            "s3prl/downstream/emotion/expert.py",
            "s3prl/jtes/Session*/train_meta_data.json",
            "s3prl/jtes/Session*/test_meta_data.json",
            "s3prl/result/downstream/*fold1/dev-best.ckpt",
        ],
        status,
    )
    upstream_snapshot = snapshot_download_to_local(
        config["upstream_repo"],
        hf_token,
        [f"s3prl/{config['upstream_file']}"],
        status,
    )
    copy_tree_files(emotion_snapshot / "s3prl", runtime_dir)
    upstream_source = upstream_snapshot / "s3prl" / config["upstream_file"]
    if not upstream_source.is_file():
        raise RuntimeError(
            f"AIST上流モデルファイルが見つかりません: {config['upstream_repo']} / {config['upstream_file']}"
        )
    upstream_target = runtime_dir / "upstream_models" / config["upstream_file"]
    upstream_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(upstream_source, upstream_target)
    return emotion_snapshot


def load_aist_emotion_labels(emotion_snapshot: Path) -> dict[str, int]:
    candidates = [
        emotion_snapshot / "s3prl" / "jtes" / "Session1" / "train_meta_data.json",
        emotion_snapshot / "s3prl" / "jtes" / "Session1" / "test_meta_data.json",
    ]
    for candidate in candidates:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        labels = data.get("labels") if isinstance(data, dict) else None
        if isinstance(labels, dict) and labels:
            parsed: dict[str, int] = {}
            for label, index in labels.items():
                try:
                    parsed[str(label)] = int(index)
                except (TypeError, ValueError):
                    continue
            if parsed:
                return parsed
    return {"joy": 0, "anger": 1, "sadness": 2, "neutral": 3}


def extract_emotion_segment_wavs(
    audio_path: Path,
    segments: list[dict[str, Any]],
    work_dir: Path,
    check_cancelled: Callable[[], None],
) -> tuple[Path, list[dict[str, Any]]]:
    wav_root = work_dir / "emotion_segments"
    wav_root.mkdir(parents=True, exist_ok=True)
    planned: list[dict[str, Any]] = []
    extracted: list[dict[str, Any]] = []
    try:
        for index, segment in enumerate(segments):
            check_cancelled()
            start, end = segment_bounds(segment)
            duration = end - start
            if duration < 0.15:
                continue
            padded_start = max(0.0, start - 0.05)
            padded_duration = duration + (start - padded_start) + 0.05
            output_path = wav_root / f"seg_{index:06d}.wav"
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass
            planned.append(
                {
                    "index": index,
                    "path": output_path,
                    "stem": output_path.stem,
                    "start": padded_start,
                    "duration": padded_duration,
                }
            )

        if not planned:
            raise RuntimeError("感情分析できる長さの発話セグメントがありません。")

        # Keep each Windows command comfortably below CreateProcess' command-line
        # limit while decoding the source only once per group instead of once per
        # utterance. The size is configurable for unusually long work paths.
        batch_size = positive_env_int(
            "MOJIOKOSI_FFMPEG_CLIP_BATCH_SIZE",
            24,
            minimum=1,
            maximum=32,
        )
        timeout_seconds = float(
            os.environ.get("MOJIOKOSI_FFMPEG_CLIP_TIMEOUT_SECONDS", "300")
        )
        for batch_start in range(0, len(planned), batch_size):
            check_cancelled()
            batch = planned[batch_start : batch_start + batch_size]
            batch_seek_start = min(float(item["start"]) for item in batch)
            batch_end = max(
                float(item["start"]) + float(item["duration"])
                for item in batch
            )
            # Input-side seeking prevents every later batch from decoding the
            # entire recording prefix. A tiny tail allowance avoids losing the
            # final sample to independent millisecond rounding.
            batch_input_duration = max(0.001, batch_end - batch_seek_start + 0.01)
            filter_parts: list[str] = []
            if len(batch) == 1:
                input_labels = ["[0:a:0]"]
            else:
                input_labels = [f"[split{offset}]" for offset in range(len(batch))]
                filter_parts.append(
                    f"[0:a:0]asplit={len(batch)}{''.join(input_labels)}"
                )
            for offset, (input_label, item) in enumerate(zip(input_labels, batch)):
                relative_start = max(0.0, float(item["start"]) - batch_seek_start)
                filter_parts.append(
                    f"{input_label}atrim=start={relative_start:.3f}:"
                    f"duration={item['duration']:.3f},asetpts=PTS-STARTPTS,"
                    f"aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono"
                    f"[clip{offset}]"
                )
            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-ss",
                f"{batch_seek_start:.3f}",
                "-t",
                f"{batch_input_duration:.3f}",
                "-i",
                str(audio_path),
                "-filter_complex",
                ";".join(filter_parts),
            ]
            for offset, item in enumerate(batch):
                command.extend(
                    [
                        "-map",
                        f"[clip{offset}]",
                        "-vn",
                        "-c:a",
                        "pcm_s16le",
                        str(item["path"]),
                    ]
                )
            completed = run_cancellable_subprocess(
                command,
                timeout=timeout_seconds,
                check_cancelled=check_cancelled,
            )
            failed_outputs = [
                item
                for item in batch
                if not item["path"].is_file() or item["path"].stat().st_size == 0
            ]
            if completed.returncode != 0 or failed_outputs:
                details = (completed.stderr or completed.stdout or "").strip()[-1000:]
                raise RuntimeError(f"感情分析用の音声切り出しに失敗しました: {details}")
            extracted.extend(
                {"index": item["index"], "path": item["path"], "stem": item["stem"]}
                for item in batch
            )
        return wav_root, extracted
    except BaseException:
        # A later batch may fail after earlier WAVs were completed. Do not leave
        # a partial corpus that a retry or S3PRL run could accidentally consume.
        for item in planned:
            try:
                item["path"].unlink()
            except (FileNotFoundError, OSError):
                pass
        raise


def create_s3prl_emotion_metadata(
    labels: dict[str, int],
    segment_wavs: list[dict[str, Any]],
    metadata_root: Path,
) -> None:
    session_dir = metadata_root / "Session1"
    session_dir.mkdir(parents=True, exist_ok=True)
    first_path = Path(segment_wavs[0]["path"]).name
    label_names = list(labels.keys()) or ["neutral"]
    train_meta = [{"path": first_path, "label": label} for label in label_names]
    test_meta = [
        {"path": Path(item["path"]).name, "label": label_names[0]}
        for item in segment_wavs
    ]
    payload_train = {"labels": labels, "meta_data": train_meta}
    payload_test = {"labels": labels, "meta_data": test_meta}
    (session_dir / "train_meta_data.json").write_text(
        json.dumps(payload_train, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (session_dir / "test_meta_data.json").write_text(
        json.dumps(payload_test, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_s3prl_predictions(prediction_path: Path) -> dict[str, str]:
    predictions: dict[str, str] = {}
    for line in prediction_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            predictions[parts[0]] = parts[-1]
    return predictions


def run_s3prl_emotion_model(
    model_key: str,
    wav_root: Path,
    segment_wavs: list[dict[str, Any]],
    hf_token: str,
    device: str,
    work_dir: Path,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
) -> dict[int, str]:
    config = AIST_EMOTION_MODELS[model_key]
    runtime_dir = resolve_s3prl_runtime_dir()
    ensure_s3prl_importable(runtime_dir, check_cancelled)
    emotion_snapshot = prepare_aist_s3prl_files(model_key, hf_token, runtime_dir, status)
    labels = load_aist_emotion_labels(emotion_snapshot)
    metadata_root = work_dir / f"{model_key}_meta"
    create_s3prl_emotion_metadata(labels, segment_wavs, metadata_root)
    checkpoint = runtime_dir / "result" / "downstream" / config["checkpoint_dir"] / "dev-best.ckpt"
    if not checkpoint.is_file():
        raise RuntimeError(f"AIST感情分析チェックポイントが見つかりません: {checkpoint}")
    override = ",,".join([
        f"config.downstream_expert.datarc.root={str(wav_root)!r}",
        f"config.downstream_expert.datarc.meta_data={str(metadata_root)!r}",
        "config.downstream_expert.datarc.eval_batch_size=1",
        "config.downstream_expert.datarc.train_batch_size=1",
        "config.downstream_expert.datarc.num_workers=0",
        "config.downstream_expert.datarc.pre_load=False",
        "config.runner.eval_dataloaders=['test']",
    ])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_dir.parent) + os.pathsep + env.get("PYTHONPATH", "")
    env["HF_TOKEN"] = hf_token
    timeout_seconds = float(os.environ.get("MOJIOKOSI_EMOTION_TIMEOUT_SECONDS", "3600"))
    command = [
        sys.executable,
        "run_downstream.py",
        "-m",
        "evaluate",
        "-t",
        "test",
        "-e",
        str(checkpoint),
        "--device",
        device,
        "-o",
        override,
    ]
    status(f"AIST感情分析を実行しています: {config['display']} / {config['fold']}")
    check_cancelled()
    started_at = time.time()
    completed = run_cancellable_subprocess(
        command,
        cwd=str(runtime_dir),
        env=env,
        timeout=timeout_seconds,
        check_cancelled=check_cancelled,
    )
    check_cancelled()
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()[-1800:]
        raise RuntimeError(f"S3PRLでのAIST感情分析に失敗しました: {details}")
    expected_prediction = (
        runtime_dir
        / "result"
        / "downstream"
        / config["checkpoint_dir"]
        / f"test_{config['fold']}_predict.txt"
    )
    prediction_path = expected_prediction if expected_prediction.is_file() else None
    if prediction_path is None:
        candidates = [
            path
            for path in (runtime_dir / "result" / "downstream").glob("**/test_*_predict.txt")
            if path.stat().st_mtime >= started_at - 5
        ]
        if candidates:
            prediction_path = max(candidates, key=lambda path: path.stat().st_mtime)
    if prediction_path is None:
        raise RuntimeError("S3PRLの感情予測ファイルを取得できませんでした。")
    predictions_by_stem = read_s3prl_predictions(prediction_path)
    indexed: dict[int, str] = {}
    for item in segment_wavs:
        label = predictions_by_stem.get(str(item["stem"]))
        if label:
            indexed[int(item["index"])] = label
    return indexed


def run_aist_emotion_analysis(
    audio_path: Path,
    segments: list[dict[str, Any]],
    model_choice: str,
    hf_token: str,
    device: str,
    work_dir: Path,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    model_keys = aist_emotion_model_keys(model_choice)
    updated_segments = [dict(segment) for segment in segments]
    status("感情分析用に発話ごとの音声を切り出しています。")
    wav_root, segment_wavs = extract_emotion_segment_wavs(audio_path, updated_segments, work_dir, check_cancelled)
    for model_key in model_keys:
        check_cancelled()
        predictions = run_s3prl_emotion_model(
            model_key,
            wav_root,
            segment_wavs,
            hf_token,
            device,
            work_dir,
            status,
            check_cancelled,
        )
        config = AIST_EMOTION_MODELS[model_key]
        for segment_index, label in predictions.items():
            emotions = updated_segments[segment_index].get("emotions")
            if not isinstance(emotions, dict):
                emotions = {}
            emotions[model_key] = {
                "model_key": model_key,
                "model_name": config["label"],
                "model_display": config["display"],
                "model_repo": config["emotion_repo"],
                "fold": config["fold"],
                "source": "audio",
                "label": label,
                "label_ja": emotion_label_ja(label),
                "confidence": None,
            }
            updated_segments[segment_index]["emotions"] = emotions
    summary = build_emotion_analysis_summary(updated_segments, model_keys, status="completed")
    check_cancelled()
    return updated_segments, summary


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int = 240,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """POST JSON in an isolated process so cancellation can stop network I/O."""
    if not AI_HTTP_WORKER_FILE.is_file():
        raise RuntimeError("AI API 通信ワーカーが見つかりません。")
    timeout_seconds = max(1.0, min(600.0, float(timeout)))
    worker_input = json.dumps(
        {
            "url": url,
            "headers": headers,
            "payload": payload,
            "timeout": timeout_seconds,
        },
        ensure_ascii=False,
    )
    try:
        completed = run_cancellable_subprocess(
            [sys.executable, "-I", str(AI_HTTP_WORKER_FILE)],
            input_text=worker_input,
            timeout=timeout_seconds + 5,
            check_cancelled=check_cancelled,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("AI API の応答がタイムアウトしました。") from exc
    if completed.returncode != 0:
        raise RuntimeError("AI API 通信ワーカーを実行できませんでした。")
    if len(completed.stdout.encode("utf-8")) > 10 * 1024 * 1024:
        raise RuntimeError("AI API 通信ワーカーの応答が大きすぎます。")
    try:
        worker_result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI API 通信ワーカーの応答形式が不正です。") from exc
    if not isinstance(worker_result, dict) or not worker_result.get("ok"):
        kind = worker_result.get("kind") if isinstance(worker_result, dict) else ""
        if kind == "http":
            status_code = worker_result.get("status", "不明")
            details = str(worker_result.get("details") or "")[:1500]
            suffix = f": {details}" if details else ""
            raise RuntimeError(f"API が HTTP {status_code} を返しました{suffix}")
        if kind == "response_too_large":
            raise RuntimeError("AI API の応答が大きすぎます。")
        raise RuntimeError("AI API に接続できません。")
    body = worker_result.get("body")
    if not isinstance(body, str):
        raise RuntimeError("AI API 通信ワーカーの応答形式が不正です。")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("API から JSON ではない応答が返されました。") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("API 応答の形式が不正です。")
    return parsed


def extract_openai_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError("OpenAI API 応答に出力テキストがありません。")


def extract_google_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        feedback = response.get("promptFeedback") or response
        raise RuntimeError(f"Google API に候補がありません: {feedback}")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts if part.get("text"))
    if not text:
        raise RuntimeError("Google API 応答に出力テキストがありません。")
    return text


def safe_token_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    if not math.isfinite(float(value)):
        return 0
    return max(0, min(10**12, int(value)))


def normalize_ai_usage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    provider = str(value.get("provider") or "").strip().casefold()
    if provider not in {"openai", "google"}:
        return {}
    return {
        "provider": provider,
        "model": str(value.get("model") or "").strip()[:200],
        "request_count": safe_token_count(value.get("request_count")),
        "input_tokens": safe_token_count(value.get("input_tokens")),
        "output_tokens": safe_token_count(value.get("output_tokens")),
        "total_tokens": safe_token_count(value.get("total_tokens")),
        "cached_tokens": safe_token_count(value.get("cached_tokens")),
        "reasoning_tokens": safe_token_count(value.get("reasoning_tokens")),
        "reported": bool(value.get("reported")),
    }


def merge_ai_usage(current_value: Any, sample_value: Any) -> dict[str, Any]:
    current = normalize_ai_usage(current_value)
    sample = normalize_ai_usage(sample_value)
    if not sample:
        return current
    if current and current["provider"] != sample["provider"]:
        current = {}
    return normalize_ai_usage({
        "provider": sample["provider"],
        "model": sample["model"] or current.get("model", ""),
        "request_count": current.get("request_count", 0) + sample["request_count"],
        "input_tokens": current.get("input_tokens", 0) + sample["input_tokens"],
        "output_tokens": current.get("output_tokens", 0) + sample["output_tokens"],
        "total_tokens": current.get("total_tokens", 0) + sample["total_tokens"],
        "cached_tokens": current.get("cached_tokens", 0) + sample["cached_tokens"],
        "reasoning_tokens": current.get("reasoning_tokens", 0) + sample["reasoning_tokens"],
        "reported": bool(current.get("reported") or sample["reported"]),
    })


def extract_ai_token_usage(
    provider: str,
    model: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    if provider == "openai":
        raw = response.get("usage")
        usage = raw if isinstance(raw, dict) else {}
        input_details = usage.get("input_tokens_details")
        output_details = usage.get("output_tokens_details")
        input_details = input_details if isinstance(input_details, dict) else {}
        output_details = output_details if isinstance(output_details, dict) else {}
        result = {
            "provider": provider,
            "model": model,
            "request_count": 1,
            "input_tokens": safe_token_count(usage.get("input_tokens")),
            "output_tokens": safe_token_count(usage.get("output_tokens")),
            "total_tokens": safe_token_count(usage.get("total_tokens")),
            "cached_tokens": safe_token_count(input_details.get("cached_tokens")),
            "reasoning_tokens": safe_token_count(output_details.get("reasoning_tokens")),
            "reported": bool(usage),
        }
    elif provider == "google":
        raw = response.get("usageMetadata")
        usage = raw if isinstance(raw, dict) else {}
        result = {
            "provider": provider,
            "model": model,
            "request_count": 1,
            "input_tokens": safe_token_count(usage.get("promptTokenCount")),
            "output_tokens": safe_token_count(usage.get("candidatesTokenCount")),
            "total_tokens": safe_token_count(usage.get("totalTokenCount")),
            "cached_tokens": safe_token_count(usage.get("cachedContentTokenCount")),
            "reasoning_tokens": safe_token_count(usage.get("thoughtsTokenCount")),
            "reported": bool(usage),
        }
    else:
        return {}
    if not result["total_tokens"]:
        result["total_tokens"] = (
            result["input_tokens"]
            + result["output_tokens"]
            + result["reasoning_tokens"]
        )
    return normalize_ai_usage(result)


def call_ai_json(
    provider: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    check_cancelled: Callable[[], None] | None = None,
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if provider == "openai":
        response = post_json(
            "https://api.openai.com/v1/responses",
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            {
                "model": model,
                "store": False,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                },
            },
            check_cancelled=check_cancelled,
        )
    elif provider == "google":
        encoded_model = urllib.parse.quote(model, safe="-_.")
        response = post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{encoded_model}:generateContent",
            {"x-goog-api-key": api_key, "Content-Type": "application/json"},
            {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                },
            },
            check_cancelled=check_cancelled,
        )
    else:
        raise RuntimeError(f"未対応の AI プロバイダーです: {provider}")
    usage = extract_ai_token_usage(provider, model, response)
    if usage_callback is not None:
        usage_callback(usage)
    text = extract_openai_text(response) if provider == "openai" else extract_google_text(response)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI が有効な JSON を返しませんでした。") from exc
    if not isinstance(result, dict):
        raise RuntimeError("AI の出力形式が不正です。")
    return result


def chunk_segments(segments: list[dict[str, Any]], max_items: int = 80, max_chars: int = 12000) -> list[list[tuple[int, dict[str, Any]]]]:
    chunks: list[list[tuple[int, dict[str, Any]]]] = []
    current: list[tuple[int, dict[str, Any]]] = []
    chars = 0
    for index, segment in enumerate(segments):
        item_chars = len(str(segment.get("text", ""))) + 80
        if current and (len(current) >= max_items or chars + item_chars > max_chars):
            chunks.append(current)
            current = []
            chars = 0
        current.append((index, segment))
        chars += item_chars
    if current:
        chunks.append(current)
    return chunks


def clean_segments_with_ai(
    segments: list[dict[str, Any]],
    provider: str,
    api_key: str,
    model: str,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    cleaned = [dict(item) for item in segments]
    chunks = chunk_segments(segments)
    system_prompt = (
        "あなたは文字起こし校正者です。音声認識由来の文字化け、無意味な反復、明白な同音異義語の誤変換、"
        "句読点の欠落だけを文脈に沿って修正してください。要約、情報の追加、発言の言い換え、発話の結合や分割は"
        "禁止です。固有名詞は確信がない限り変更せず、各 id を必ず1回ずつ同じ順序で返してください。"
    )
    for part_number, chunk in enumerate(chunks, 1):
        check_cancelled()
        status(f"AI で文字を整えています（{part_number}/{len(chunks)}）…")
        input_items = [
            {
                "id": index,
                "speaker": segment.get("speaker") or "UNKNOWN",
                "start": round(float(segment.get("start", 0)), 2),
                "text": segment.get("text", ""),
            }
            for index, segment in chunk
        ]
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": len(chunk),
                    "maxItems": len(chunk),
                    "items": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}, "text": {"type": "string"}},
                        "required": ["id", "text"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        }
        result = call_ai_json(
            provider,
            api_key,
            model,
            system_prompt,
            "次の発話を校正してください。\n" + json.dumps(input_items, ensure_ascii=False),
            "transcript_cleanup",
            schema,
            check_cancelled,
            usage_callback,
        )
        returned = result.get("items")
        expected_ids = [index for index, _ in chunk]
        if not isinstance(returned, list) or [item.get("id") for item in returned] != expected_ids:
            raise RuntimeError("AI が発話 ID または発話数を変更したため、安全のため結果を採用しませんでした。")
        for item in returned:
            value = item.get("text")
            if not isinstance(value, str):
                raise RuntimeError("AI の校正結果に文字列でない発話が含まれています。")
            cleaned[int(item["id"])]["text"] = value.strip()
    return cleaned


def normalize_detected_speaker_name(value: Any, evidence: Any = "") -> str:
    name = clean_single_line(value, 80).strip(" 　、。,.・:：;；「」『』【】()（）[]")
    evidence_text = clean_single_line(evidence, 300)
    name = re.sub(r"^(?:私は|わたしは|僕は|ぼくは|名前は)\s*", "", name)
    name = re.sub(
        r"\s*(?:と申します|ともうします|といいます|と言います|です|でございます)$",
        "",
        name,
    ).strip()
    for honorific in ("さん", "様", "さま", "君", "くん", "ちゃん"):
        if not name.endswith(honorific) or len(name) <= len(honorific):
            continue
        base = name[:-len(honorific)].strip()
        # ASR often renders a self-introduction as "名字さんです". Remove the
        # honorific only when the evidence contains that exact introductory
        # construction, rather than stripping legitimate name text blindly.
        if re.search(
            rf"{re.escape(base)}\s*{re.escape(honorific)}\s*(?:です|でございます|といいます|と言います|と申します)",
            evidence_text,
        ):
            name = base
        break
    return clean_single_line(name, 80)


def speaker_identity_context_records(
    records: list[dict[str, Any]],
    *,
    character_budget: int = 12000,
) -> list[dict[str, Any]]:
    if not records:
        return []
    invitation_pattern = re.compile(
        r"自己紹介|お名前|名前を|名乗|一人ずつ|ひとりずつ|お一人ずつ|順番に.{0,12}紹介"
    )
    identity_cue_pattern = re.compile(
        r"と申します|ともうします|といいます|と言います|出身|所属|担当|務め|"
        r"よろしくお願いします|"
        r"(?:^|[\s、。！？])[^\s、。！？]{1,20}(?:さん|様|くん|ちゃん)?です(?:[\s、。！？]|$)"
    )
    invitation_indexes = [
        index for index, record in enumerate(records)
        if invitation_pattern.search(str(record.get("text") or ""))
    ]
    cue_indexes = [
        index for index, record in enumerate(records)
        if identity_cue_pattern.search(str(record.get("text") or ""))
    ]
    selected_indexes: set[int] = set()

    def select_time_window(center_index: int, before: float, after: float) -> None:
        center = float(records[center_index].get("start", 0) or 0)
        lower = max(0.0, center - before)
        upper = center + after
        for index, record in enumerate(records):
            start = float(record.get("start", 0) or 0)
            end = float(record.get("end", start) or start)
            if end >= lower and start <= upper:
                selected_indexes.add(index)

    if invitation_indexes:
        # An invitation is the strongest boundary. The time window adapts to
        # long turns and many short turns without assuming a fixed turn count.
        for index in invitation_indexes:
            select_time_window(index, 60.0, 180.0)
    if cue_indexes:
        # Include later arrivals and introductions without an explicit request.
        for index in cue_indexes:
            select_time_window(index, 20.0, 35.0)
    if not selected_indexes:
        # With no lexical signal, retain an opening time/character window so
        # unconventional introductions can still be judged by the model.
        opening_start = float(records[0].get("start", 0) or 0)
        for index, record in enumerate(records):
            if float(record.get("start", 0) or 0) - opening_start > 240.0:
                break
            selected_indexes.add(index)

    selected = [records[index] for index in sorted(selected_indexes)]
    result: list[dict[str, Any]] = []
    used_characters = 0
    for record in selected:
        text_length = len(str(record.get("text") or ""))
        if result and used_characters + text_length > max(1000, character_budget):
            break
        result.append(record)
        used_characters += text_length
    return result or records[:1]


def apply_speaker_identity_repairs(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    diagnostics: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, int]]:
    """Apply strictly validated AI alias and short-fragment corrections."""
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    raw_aliases = diagnostics.get("speaker_aliases")
    aliases = raw_aliases if isinstance(raw_aliases, dict) else {}
    raw_corrections = diagnostics.get("segment_speaker_corrections")
    corrections = raw_corrections if isinstance(raw_corrections, dict) else {}

    def canonical(label: str) -> str:
        current = label
        visited: set[str] = set()
        while current in aliases and current not in visited:
            visited.add(current)
            target = str(aliases[current])
            if not target or target == current:
                break
            current = target
        return current

    repaired: list[dict[str, Any]] = []
    corrected_count = 0
    aliased_count = 0
    for index, raw_segment in enumerate(segments):
        segment = dict(raw_segment)
        original = str(segment.get("speaker") or "UNKNOWN")
        corrected = str(corrections.get(index) or original)
        if corrected != original:
            corrected_count += 1
        final_label = canonical(corrected)
        if final_label != corrected:
            aliased_count += 1
        if segment.get("speaker") or final_label != "UNKNOWN":
            segment["speaker"] = final_label
        repaired.append(segment)

    canonical_names: dict[str, str] = {}
    conflicting: set[str] = set()
    for raw_label, raw_name in speaker_names.items():
        label = canonical(str(raw_label))
        name = clean_single_line(raw_name, 80)
        if not name:
            continue
        if label in canonical_names and canonical_names[label] != name:
            conflicting.add(label)
        else:
            canonical_names[label] = name
    for label in conflicting:
        canonical_names.pop(label, None)

    return repaired, canonical_names, {
        "alias_count": len(aliases),
        "aliased_segments": aliased_count,
        "corrected_segments": corrected_count,
    }


def detect_speaker_names_with_ai(
    segments: list[dict[str, Any]],
    provider: str,
    api_key: str,
    model: str,
    check_cancelled: Callable[[], None] | None = None,
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
    diagnostics_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, str]:
    if check_cancelled is not None:
        check_cancelled()
    labels = sorted({str(item["speaker"]) for item in segments if item.get("speaker")})
    if not labels:
        return {}
    early: list[dict[str, Any]] = []
    chars = 0
    for index, item in enumerate(segments):
        if float(item.get("start", 0)) > 900 or len(early) >= 120 or chars >= 24000:
            break
        record = {
            "id": index,
            "speaker": item.get("speaker") or "UNKNOWN",
            "start": round(float(item.get("start", 0) or 0), 2),
            "end": round(float(item.get("end", item.get("start", 0)) or 0), 2),
            "text": item.get("text", ""),
        }
        early.append(record)
        chars += len(str(record["text"]))
    identity_context = speaker_identity_context_records(early)
    schema = {
        "type": "object",
        "properties": {
            "speaker_names": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string", "enum": labels},
                        "name": {"type": "string"},
                        "evidence": {"type": "string"},
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": ["speaker", "name", "evidence", "evidence_segment_ids"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["speaker_names"],
        "additionalProperties": False,
    }
    if status_callback is not None:
        status_callback("話者特定 1/2: 自己紹介の候補を抽出しています…")
    first_result = call_ai_json(
        provider,
        api_key,
        model,
        (
            "これは文字校正とは独立した話者特定処理です。会話冒頭付近の明示的な自己紹介から、"
            "氏名候補と、その名前を発話した音声話者ラベルを抽出してください。"
            "『私は田中です』『○○と申します』は例であり、固定表現の完全一致を条件にしません。"
            "人によって名乗り方が異なるため、直前の『自己紹介をお願いします』、発話順、話者交代、"
            "氏名らしい語の後に続く出身地・所属・役割・『よろしくお願いします』などを組み合わせ、"
            "その発話が本人の自己紹介であるかを文脈で判断してください。『片割さんです、出身は静岡です』"
            "のような敬称混入、助詞欠落、句読点欠落、名前と次の文の連結など音声認識特有の揺れも許容します。"
            "本人の名乗りに付いた『さん』『様』『くん』『ちゃん』は氏名本体から除いて返してください。"
            "ただし、他人を呼んだだけの名前、話題に出ただけの名前、会社名だけ、文脈根拠のない推測は採用しません。"
            "自己紹介が複数発話に分割されている場合は前後の発話をつなげて判断してください。"
            "根拠に使った発話の id を evidence_segment_ids に必ず入れてください。"
            "この段階では候補を漏らさないことを優先します。"
        ),
        "話者ラベル付きの発話です。\n" + json.dumps(identity_context, ensure_ascii=False),
        "speaker_identity_extraction",
        schema,
        check_cancelled,
        usage_callback,
    )
    if check_cancelled is not None:
        check_cancelled()

    def normalized_evidence_ids(value: Any) -> list[int]:
        result: list[int] = []
        if not isinstance(value, list):
            return result
        for raw_id in value:
            if isinstance(raw_id, bool) or not isinstance(raw_id, int):
                continue
            if 0 <= raw_id < len(early) and raw_id not in result:
                result.append(raw_id)
        return result[:12]

    first_candidates: list[dict[str, Any]] = []
    for item in first_result.get("speaker_names") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("speaker", ""))
        evidence = clean_single_line(item.get("evidence"), 240)
        name = normalize_detected_speaker_name(item.get("name"), evidence)
        if label in labels and name:
            first_candidates.append({
                "speaker": label,
                "name": name,
                "evidence": evidence,
                "evidence_segment_ids": normalized_evidence_ids(
                    item.get("evidence_segment_ids")
                ),
            })

    verification_schema = {
        "type": "object",
        "properties": {
            "speaker_names": schema["properties"]["speaker_names"],
            "speaker_aliases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "canonical_speaker": {"type": "string", "enum": labels},
                        "alias_speaker": {"type": "string", "enum": labels},
                        "confidence": {"type": "number"},
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": [
                        "canonical_speaker", "alias_speaker", "confidence",
                        "evidence_segment_ids",
                    ],
                    "additionalProperties": False,
                },
            },
            "segment_speaker_corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_id": {"type": "integer"},
                        "speaker": {"type": "string", "enum": labels},
                        "confidence": {"type": "number"},
                        "evidence_segment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                    },
                    "required": [
                        "segment_id", "speaker", "confidence",
                        "evidence_segment_ids",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "speaker_names", "speaker_aliases", "segment_speaker_corrections",
        ],
        "additionalProperties": False,
    }

    if status_callback is not None:
        status_callback("話者特定 2/2: 候補を音声話者ラベルへリンクして再確認しています…")
    try:
        verified_result = call_ai_json(
            provider,
            api_key,
            model,
            (
                "これは独立した話者リンクの最終確認です。一次候補を鵜呑みにせず、発話時刻、"
                "自己紹介文、speaker ラベルを再確認してください。固定の言い回しだけで判定せず、"
                "自己紹介依頼の直後という位置、発話順、出身地・所属・役割・挨拶の連続などから、"
                "本人の自己紹介と文脈上確認できた氏名を、"
                "その氏名部分を発話した speaker ラベルへリンクします。自己紹介が発話境界で分割された"
                "場合は隣接発話を復元して判断してください。一次処理が見落とした明示的な自己紹介も追加し、"
                "音声認識による『名前＋さんです』、助詞や句読点の欠落も許容し、敬称は氏名から除いてください。"
                "根拠がない候補や別人へのリンクは除外してください。根拠発話の id を"
                " evidence_segment_ids に必ず返してください。最終的に確認できた全話者を返してください。"
                "同じ人物が複数の speaker ラベルに分裂していることを強い文脈根拠で確認できる場合だけ、"
                "代表ラベルと別名ラベルを speaker_aliases に返してください。単に発話が隣接するだけでは"
                "同一人物と判定しません。また、短い発話だけ別 speaker になった A-B-A 型の断裂で、"
                "前後と同一人物だと確実に判断できる場合だけ segment_speaker_corrections に返してください。"
                "修復候補には対象発話と前後発話の id、0から1の confidence を入れてください。"
            ),
            (
                "一次候補:\n" + json.dumps(first_candidates, ensure_ascii=False)
                + "\n\n話者ラベル付き発話:\n" + json.dumps(identity_context, ensure_ascii=False)
            ),
            "speaker_identity_link_verification",
            verification_schema,
            check_cancelled,
            usage_callback,
        )
    except InterruptedError:
        raise
    except Exception:
        verified_result = {
            "speaker_names": first_candidates,
            "speaker_aliases": [],
            "segment_speaker_corrections": [],
        }
    if check_cancelled is not None:
        check_cancelled()

    resolved_candidates: list[tuple[str, str]] = []
    for item in verified_result.get("speaker_names") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("speaker", ""))
        evidence = clean_single_line(item.get("evidence"), 240)
        name = normalize_detected_speaker_name(item.get("name"), evidence)
        if label not in labels or not name:
            continue
        evidence_ids = normalized_evidence_ids(item.get("evidence_segment_ids"))
        evidence_labels = {
            str(early[evidence_id].get("speaker") or "UNKNOWN")
            for evidence_id in evidence_ids
        }
        # An explicit evidence id is more reliable than a free-form speaker
        # field generated by the model. Only keep the model choice when the
        # evidence genuinely spans more than one diarization label.
        if len(evidence_labels) == 1:
            label = next(iter(evidence_labels))
        elif evidence_labels and label not in evidence_labels:
            continue
        elif not evidence_ids:
            matching_labels = {
                str(record.get("speaker") or "UNKNOWN")
                for record in early
                if name in str(record.get("text") or "")
            }
            if len(matching_labels) == 1:
                label = next(iter(matching_labels))
        resolved_candidates.append((label, name))

    candidates_by_label: dict[str, list[str]] = defaultdict(list)
    for label, name in resolved_candidates:
        if name not in candidates_by_label[label]:
            candidates_by_label[label].append(name)
    ambiguous_labels = {
        label: values
        for label, values in candidates_by_label.items()
        if len(values) > 1
    }
    names = {
        label: values[0]
        for label, values in candidates_by_label.items()
        if len(values) == 1
    }

    def confidence_value(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        return parsed if math.isfinite(parsed) else 0.0

    proposed_aliases: dict[str, set[str]] = defaultdict(set)
    for item in verified_result.get("speaker_aliases") or []:
        if not isinstance(item, dict) or confidence_value(item.get("confidence")) < 0.92:
            continue
        canonical_label = str(item.get("canonical_speaker") or "")
        alias_label = str(item.get("alias_speaker") or "")
        if (
            canonical_label not in labels
            or alias_label not in labels
            or canonical_label == alias_label
        ):
            continue
        evidence_ids = normalized_evidence_ids(item.get("evidence_segment_ids"))
        evidence_labels = {
            str(early[evidence_id].get("speaker") or "UNKNOWN")
            for evidence_id in evidence_ids
        }
        if not {canonical_label, alias_label}.issubset(evidence_labels):
            continue
        if (
            names.get(canonical_label)
            and names.get(alias_label)
            and names[canonical_label] != names[alias_label]
        ):
            continue
        proposed_aliases[alias_label].add(canonical_label)
    speaker_aliases = {
        alias: next(iter(targets))
        for alias, targets in proposed_aliases.items()
        if len(targets) == 1 and alias not in targets
    }
    speaker_aliases = {
        alias: target
        for alias, target in speaker_aliases.items()
        if speaker_aliases.get(target) != alias
    }

    def canonical_label(label: str) -> str:
        current = label
        visited: set[str] = set()
        while current in speaker_aliases and current not in visited:
            visited.add(current)
            current = speaker_aliases[current]
        return current

    canonical_names: dict[str, str] = {}
    name_conflicts: set[str] = set()
    for label, name in names.items():
        canonical = canonical_label(label)
        if canonical in canonical_names and canonical_names[canonical] != name:
            name_conflicts.add(canonical)
        else:
            canonical_names[canonical] = name
    for label in name_conflicts:
        canonical_names.pop(label, None)
    names = canonical_names

    segment_speaker_corrections: dict[int, str] = {}
    for item in verified_result.get("segment_speaker_corrections") or []:
        if not isinstance(item, dict) or confidence_value(item.get("confidence")) < 0.92:
            continue
        segment_id = item.get("segment_id")
        proposed_speaker = str(item.get("speaker") or "")
        if (
            isinstance(segment_id, bool)
            or not isinstance(segment_id, int)
            or not 0 < segment_id < len(early) - 1
            or proposed_speaker not in labels
        ):
            continue
        previous_speaker = str(early[segment_id - 1].get("speaker") or "UNKNOWN")
        current_speaker = str(early[segment_id].get("speaker") or "UNKNOWN")
        following_speaker = str(early[segment_id + 1].get("speaker") or "UNKNOWN")
        start, end = segment_bounds(early[segment_id])
        normalized_text = normalize_text_for_merge(str(early[segment_id].get("text") or ""))
        evidence_ids = set(normalized_evidence_ids(item.get("evidence_segment_ids")))
        if (
            previous_speaker == following_speaker == proposed_speaker
            and current_speaker != proposed_speaker
            and (end - start <= 4.0 or len(normalized_text) <= 28)
            and segment_id in evidence_ids
            and evidence_ids.intersection({segment_id - 1, segment_id + 1})
        ):
            segment_speaker_corrections[segment_id] = proposed_speaker
    labels_by_name: dict[str, list[str]] = defaultdict(list)
    for label, name in names.items():
        labels_by_name[name].append(label)
    duplicate_names = {
        name: linked_labels
        for name, linked_labels in labels_by_name.items()
        if len(linked_labels) > 1
    }
    if duplicate_names:
        names = {
            label: name
            for label, name in names.items()
            if name not in duplicate_names
        }
    if diagnostics_callback is not None:
        diagnostics_callback({
            "source_segment_count": len(early),
            "context_segment_count": len(identity_context),
            "candidate_count": len(resolved_candidates),
            "linked_count": len(names),
            "ambiguous_labels": ambiguous_labels,
            "duplicate_names": duplicate_names,
            "speaker_aliases": speaker_aliases,
            "segment_speaker_corrections": segment_speaker_corrections,
        })
    return names


def display_speaker_for_ai(label: str | None, speaker_names: dict[str, str]) -> str:
    if label and speaker_names.get(label, "").strip():
        return speaker_names[label].strip()
    return default_speaker_name(label)


def normalize_outline_sections(
    raw_sections: Any,
    chunk: list[tuple[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    if not isinstance(raw_sections, list):
        raise RuntimeError("AI のアウトライン出力形式が不正です。")
    starts = [float(item.get("start", 0)) for _, item in chunk]
    ends = [float(item.get("end", item.get("start", 0))) for _, item in chunk]
    chunk_start = min(starts) if starts else 0.0
    chunk_end = max(ends) if ends else chunk_start
    normalized: list[dict[str, Any]] = []
    for raw in raw_sections:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        bullets = raw.get("bullets")
        if not title or not isinstance(bullets, list):
            continue
        cleaned_bullets = [
            str(bullet).strip()
            for bullet in bullets[:8]
            if isinstance(bullet, str) and str(bullet).strip()
        ]
        if not cleaned_bullets:
            continue
        try:
            start = float(raw.get("start", chunk_start))
        except (TypeError, ValueError):
            start = chunk_start
        try:
            end = float(raw.get("end", chunk_end))
        except (TypeError, ValueError):
            end = chunk_end
        start = max(0.0, start)
        end = max(start, end)
        normalized.append({
            "title": title[:120],
            "start": round(start, 2),
            "end": round(end, 2),
            "bullets": [bullet[:320] for bullet in cleaned_bullets],
        })
    return normalized


def create_outline_with_ai(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    provider: str,
    api_key: str,
    model: str,
    status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    chunks = chunk_segments(segments, max_items=80, max_chars=18000)
    sections: list[dict[str, Any]] = []
    system_prompt = (
        "あなたは会議録のアウトライン作成者です。入力された発話だけを根拠に、"
        "話している内容を時系列の議題アウトラインに整理してください。"
        "要点、決定事項、未決事項、次のアクションがあれば箇条書きに含めます。"
        "発話にない情報、推測、参加者名の創作、結論の追加は禁止です。"
        "start と end は入力発話の秒数範囲に基づく数値で返してください。"
    )
    schema = {
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "start", "end", "bullets"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["sections"],
        "additionalProperties": False,
    }
    for part_number, chunk in enumerate(chunks, 1):
        check_cancelled()
        status(f"AI で議題アウトラインを作成しています（{part_number}/{len(chunks)}）…")
        input_items = [
            {
                "id": index,
                "speaker": display_speaker_for_ai(segment.get("speaker"), speaker_names),
                "start": round(float(segment.get("start", 0)), 2),
                "end": round(float(segment.get("end", segment.get("start", 0))), 2),
                "text": segment.get("text", ""),
            }
            for index, segment in chunk
        ]
        result = call_ai_json(
            provider,
            api_key,
            model,
            system_prompt,
            "次の発話から議題アウトラインを作成してください。\n" + json.dumps(input_items, ensure_ascii=False),
            "meeting_outline",
            schema,
            check_cancelled,
            usage_callback,
        )
        sections.extend(normalize_outline_sections(result.get("sections"), chunk))
    if not sections and segments:
        sections.append({
            "title": "全体",
            "start": round(float(segments[0].get("start", 0)), 2),
            "end": round(float(segments[-1].get("end", segments[-1].get("start", 0))), 2),
            "bullets": ["具体的な議題を抽出できませんでした。本文を確認してください。"],
        })
    return {"title": "議題・アウトライン", "sections": sections}


def update_job(
    job: JobRecord,
    *,
    progress: int | None = None,
    message: str | None = None,
    stage: str | None = None,
    stage_label: str | None = None,
    stage_progress: int | None = None,
) -> None:
    with jobs_lock:
        if progress is not None:
            job.progress = max(job.progress, min(100, progress))
        if stage is not None:
            job.stage = stage
        if stage_label is not None:
            job.stage_label = stage_label
        if stage_progress is not None:
            job.stage_progress = max(0, min(100, stage_progress))
        if message is not None:
            job.message = message
            job.logs.append(message)
            job.logs = job.logs[-MAX_LOG_LINES:]


def run_transcription_job(job: JobRecord, options: JobOptions) -> None:
    model: Any = None
    model_a: Any = None
    audio: Any = None
    diarize_model: Any = None
    diarize_segments: Any = None
    staged_media_path: Path | None = None

    def status(message: str) -> None:
        update_job(job, message=message)

    def progress(value: int) -> None:
        update_job(job, progress=value)

    def set_stage(key: str, label: str, value: int = 0) -> None:
        update_job(
            job,
            stage=key,
            stage_label=label,
            stage_progress=value,
        )

    def record_ai_usage(sample: dict[str, Any]) -> None:
        usage = normalize_ai_usage(sample)
        if not usage:
            return
        with jobs_lock:
            current = normalize_ai_usage(job.ai_usage)
            if current and current["provider"] != usage["provider"]:
                current = {}
            job.ai_usage = merge_ai_usage(current, usage)

    def check_cancelled() -> None:
        if job.cancel_event.is_set():
            raise InterruptedError("処理を中止しました。")

    def record_warning(message: str) -> None:
        with jobs_lock:
            current = job.output_warning.strip()
            job.output_warning = f"{current}\n{message}".strip() if current else message
        status(message)

    with jobs_lock:
        job.status = "running"
    try:
        check_cancelled()
        set_stage("environment", "処理環境の確認", 5)
        progress(2)
        status("処理環境を確認しています…")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg が見つかりません。README の手順でインストールしてください。")
        internal_work_dir = options.work_dir / ".pipeline_internal"
        internal_work_dir.mkdir(parents=True, exist_ok=True)
        processing_input_path = options.input_path
        if options.audio_preprocess != "none":
            label = audio_preprocess_label(options.audio_preprocess)
            set_stage("preprocess", "音声の前処理", 10)
            status(f"文字起こし用に音声を前処理しています（{label}）…")
            processed_path = internal_work_dir / "preprocessed.wav"
            processing_input_path = run_audio_preprocess(
                options.input_path,
                processed_path,
                options.audio_preprocess,
                check_cancelled,
            )
            set_stage("preprocess", "音声の前処理", 100)
            status("前処理済み音声を使用します（16kHz / mono / WAV）。")
        else:
            status("音声前処理は行わず、元ファイルの音声を使用します。")
        check_cancelled()
        set_stage("environment", "処理環境の確認", 100)
        progress(8)
        try:
            import torch

            configure_huggingface_hub_compatibility()
            import whisperx

            configure_speechbrain_lazy_import_compatibility()
            from whisperx.diarize import DiarizationPipeline
        except ImportError as exc:
            raise RuntimeError("必要な Python パッケージがありません。run.bat でセットアップしてください。") from exc

        device = options.device
        diarization_device = options.diarization_device
        needs_cuda = device == "cuda" or diarization_device == "cuda"
        if needs_cuda and not torch.cuda.is_available():
            raise RuntimeError("CUDA を利用できません。CPU を選ぶか NVIDIA ドライバーを確認してください。")
        capability: tuple[int, int] | None = None
        vram_gib = 0.0
        gpu_name = ""
        if needs_cuda:
            gpu_name = torch.cuda.get_device_name(0)
            capability = torch.cuda.get_device_capability(0)
            vram_gib = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        compute_type = "float16" if capability and capability[0] >= 7 else "float32"
        use_openai_whisper = device == "cpu" or (capability is not None and capability[0] < 7)
        if device == "cuda":
            assert capability is not None
            status(
                f"GPU: {gpu_name} / VRAM {vram_gib:.1f} GB / "
                f"Compute Capability {capability[0]}.{capability[1]}"
            )
            if capability[0] < 7 and options.model_name not in {"tiny", "base"}:
                raise RuntimeError("旧世代 4 GB GPU では tiny / base だけを選べます。")
        else:
            status("文字起こしは CPU を使用します。")

        backend = "OpenAI Whisper" if use_openai_whisper else "WhisperX (faster-whisper)"
        if options.triple_pass:
            status(
                "詳細処理を使います。通常結果の3秒以上の空白だけを、軽め・強めの順で切り出して補完します。"
            )
        elif options.boost_quiet_speech:
            status(
                "小さい声を拾いやすくする設定を使います"
                f"（VAD onset={options.vad_onset:.2f}, offset={options.vad_offset:.2f}）…"
            )

        def release_asr_model() -> None:
            nonlocal model
            if model is not None:
                del model
                model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        def load_asr_model(
            language_hint: str | None,
            vad_onset: float,
            vad_offset: float,
            no_speech_threshold: float,
        ) -> Any:
            nonlocal model
            if use_openai_whisper:
                import whisper

                model = whisper.load_model(options.model_name, device=device)
            else:
                model = whisperx.load_model(
                    options.model_name,
                    device,
                    device_index=0,
                    compute_type=compute_type,
                    language=language_hint,
                    asr_options={"no_speech_threshold": no_speech_threshold},
                    vad_options={"vad_onset": vad_onset, "vad_offset": vad_offset},
                )
            return model

        def transcribe_pass(
            pass_label: str,
            audio_path: Path,
            language_hint: str | None,
            vad_onset: float,
            vad_offset: float,
            no_speech_threshold: float,
            progress_value: int,
        ) -> tuple[dict[str, Any], Any]:
            set_stage("transcription", f"{pass_label}の文字起こし", 10)
            status(f"{pass_label}: 音声認識モデルを読み込んでいます（{options.model_name} / {backend}）…")
            pass_model = load_asr_model(
                language_hint,
                vad_onset,
                vad_offset,
                no_speech_threshold,
            )
            check_cancelled()
            set_stage("transcription", f"{pass_label}の文字起こし", 35)

            status(
                f"{pass_label}: 音声を読み込み、文字起こししています"
                f"（VAD onset={vad_onset:.2f}, offset={vad_offset:.2f}）…"
            )
            pass_audio = whisperx.load_audio(str(audio_path))
            if use_openai_whisper:
                pass_result = pass_model.transcribe(
                    pass_audio,
                    language=language_hint,
                    fp16=False,
                    verbose=False,
                    condition_on_previous_text=False,
                    no_speech_threshold=no_speech_threshold,
                    word_timestamps=True,
                )
            else:
                pass_result = pass_model.transcribe(pass_audio, batch_size=1)
            set_stage("transcription", f"{pass_label}の文字起こし", 90)
            release_asr_model()
            check_cancelled()
            set_stage("transcription", f"{pass_label}の文字起こし", 100)
            progress(progress_value)
            return pass_result, pass_audio

        def transcribe_gap_pass(
            pass_label: str,
            preset: str,
            gaps: list[tuple[float, float]],
            audio_duration: float,
            language_hint: str | None,
            vad_onset: float,
            vad_offset: float,
            no_speech_threshold: float,
            progress_value: int,
        ) -> dict[str, Any]:
            if not gaps:
                set_stage("transcription", f"{pass_label}の文字起こし", 100)
                status(f"{pass_label}: {TRIPLE_PASS_MIN_GAP_SECONDS:.0f}秒以上の空白はありません。")
                progress(progress_value)
                return {"segments": [], "language": language_hint}

            total_gap_seconds = sum(end - start for start, end in gaps)
            set_stage("transcription", f"{pass_label}の文字起こし", 10)
            status(
                f"{pass_label}: {len(gaps)}か所、計{total_gap_seconds:.1f}秒の空白だけを再確認します。"
            )
            status(f"{pass_label}: 音声認識モデルを読み込んでいます（{options.model_name} / {backend}）…")
            pass_model = load_asr_model(
                language_hint,
                vad_onset,
                vad_offset,
                no_speech_threshold,
            )
            detected_language = language_hint
            collected: list[dict[str, Any]] = []
            try:
                for index, (gap_start, gap_end) in enumerate(gaps, 1):
                    check_cancelled()
                    set_stage(
                        "transcription",
                        f"{pass_label}の文字起こし",
                        15 + round(75 * (index - 1) / max(1, len(gaps))),
                    )
                    clip_start = max(0.0, gap_start - TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                    clip_end = min(audio_duration, gap_end + TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                    status(
                        f"{pass_label}: 空白 {index}/{len(gaps)} "
                        f"（{display_time(gap_start)}–{display_time(gap_end)}）を切り出して再文字起こししています…"
                    )
                    clip_path = internal_work_dir / f"gap_{preset}_{index:04d}.wav"
                    try:
                        run_audio_interval_preprocess(
                            options.input_path,
                            clip_path,
                            clip_start,
                            clip_end,
                            preset,
                            check_cancelled,
                        )
                        clip_audio = whisperx.load_audio(str(clip_path))
                        if use_openai_whisper:
                            clip_result = pass_model.transcribe(
                                clip_audio,
                                language=detected_language,
                                fp16=False,
                                verbose=False,
                                condition_on_previous_text=False,
                                no_speech_threshold=no_speech_threshold,
                                word_timestamps=True,
                            )
                        else:
                            clip_result = pass_model.transcribe(clip_audio, batch_size=1)
                        if not detected_language:
                            detected_language = clip_result.get("language")
                        collected.extend(
                            offset_asr_segments_to_gap(
                                clip_result.get("segments", []),
                                clip_start,
                                gap_start,
                                gap_end,
                            )
                        )
                    finally:
                        clip_path.unlink(missing_ok=True)
            finally:
                release_asr_model()
            check_cancelled()
            set_stage("transcription", f"{pass_label}の文字起こし", 100)
            progress(progress_value)
            return {"segments": collected, "language": detected_language}

        if options.triple_pass:
            primary_vad_onset = NORMAL_VAD_ONSET
            primary_vad_offset = NORMAL_VAD_OFFSET
            primary_no_speech_threshold = NORMAL_NO_SPEECH_THRESHOLD
            primary_progress = 26
        else:
            primary_vad_onset = options.vad_onset
            primary_vad_offset = options.vad_offset
            primary_no_speech_threshold = options.no_speech_threshold
            primary_progress = 52

        result, audio = transcribe_pass(
            "通常モード",
            processing_input_path,
            options.language,
            primary_vad_onset,
            primary_vad_offset,
            primary_no_speech_threshold,
            primary_progress,
        )
        language_code = options.language or result.get("language")

        if options.triple_pass:
            audio_duration = len(audio) / WHISPER_SAMPLE_RATE
            original_segments = result.get("segments", [])
            original_count = len(normalize_asr_segments(original_segments))

            light_gaps = find_long_asr_gaps(original_segments, audio_duration)
            light_result = transcribe_gap_pass(
                "2回目（軽め）",
                "light",
                light_gaps,
                audio_duration,
                language_code,
                options.vad_onset,
                options.vad_offset,
                options.no_speech_threshold,
                38,
            )
            if not language_code:
                language_code = light_result.get("language")
            after_light, light_counts = merge_supplemental_asr_segments(
                original_segments,
                [("長い空白・軽め", light_result.get("segments", []))],
            )

            strong_gaps = find_long_asr_gaps(after_light, audio_duration)
            strong_result = transcribe_gap_pass(
                "3回目（強め）",
                "strong",
                strong_gaps,
                audio_duration,
                language_code,
                options.vad_onset,
                options.vad_offset,
                options.no_speech_threshold,
                50,
            )
            if not language_code:
                language_code = strong_result.get("language")
            merged_segments, strong_counts = merge_supplemental_asr_segments(
                after_light,
                [("長い空白・強め", strong_result.get("segments", []))],
            )
            result = dict(result)
            result["segments"] = merged_segments
            if language_code:
                result["language"] = language_code
            status(
                "詳細処理の統合完了: "
                f"通常 {original_count} 区間、"
                f"2回目 {len(light_gaps)} 空白から +{light_counts.get('長い空白・軽め', 0)}、"
                f"3回目 {len(strong_gaps)} 空白から +{strong_counts.get('長い空白・強め', 0)} を追加しました。"
            )
        check_cancelled()
        progress(52)

        if language_code:
            try:
                set_stage("alignment", "発話時刻の補正", 10)
                status("発話時刻を整えています…")
                model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
                result = whisperx.align(
                    result["segments"], model_a, metadata, audio, device, return_char_alignments=False
                )
            except InterruptedError:
                raise
            except Exception as exc:
                status(f"時刻補正を省略しました: {exc}")
            finally:
                if model_a is not None:
                    del model_a
                    model_a = None
                gc.collect()
                if device == "cuda":
                    torch.cuda.empty_cache()
        check_cancelled()
        set_stage("alignment", "発話時刻の補正", 100)
        progress(64)

        set_stage("diarization", "話者の分離", 10)
        status(f"話者を分離しています（{diarization_device.upper()}）…")
        try:
            diarize_model = create_diarization_pipeline(
                DiarizationPipeline, options.hf_token, diarization_device
            )
        except Exception as exc:
            if is_diarization_access_error(exc):
                raise RuntimeError(diarization_access_error_message(DIARIZATION_MODEL)) from exc
            raise
        diarize_kwargs: dict[str, int] = {}
        if options.min_speakers is not None:
            diarize_kwargs["min_speakers"] = options.min_speakers
        if options.max_speakers is not None:
            diarize_kwargs["max_speakers"] = options.max_speakers
        diarize_segments = diarize_model(audio, **diarize_kwargs)
        check_cancelled()
        set_stage("diarization", "話者の分離", 100)
        progress(80)

        set_stage("speaker_assignment", "話者ラベルの割り当て", 15)
        status("話者ラベルを文字起こしに対応付けています…")
        result = whisperx.assign_word_speakers(
            diarize_segments,
            result,
            fill_nearest=True,
        )
        segments = make_display_segments(result.get("segments", []))
        if not segments:
            raise RuntimeError("文字起こし結果が空でした。音声が含まれているか確認してください。")
        # Speaker identification uses the unedited transcript as a dedicated
        # source so text cleanup cannot remove or rewrite a self-introduction.
        speaker_identity_segments = [dict(item) for item in segments]
        check_cancelled()
        set_stage("speaker_assignment", "話者ラベルの割り当て", 100)

        # Diarization and the full decoded audio are no longer needed. Releasing
        # them before optional emotion inference substantially reduces peak VRAM.
        diarize_segments = None
        diarize_model = None
        audio = None
        result = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        set_stage("finishing", "文字起こしの仕上げ", 10)
        if options.clean_transcript:
            try:
                segments = clean_segments_with_ai(
                    segments,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    status,
                    check_cancelled,
                    record_ai_usage,
                )
                check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                record_warning("AI文字整形を省略しました。元の文字起こしを保存します: " + details)
        set_stage("finishing", "文字起こしの仕上げ", 100)
        progress(88)
        emotion_analysis: dict[str, Any] | None = None
        if options.emotion_analysis:
            emotion_model_keys = aist_emotion_model_keys(options.emotion_model)
            try:
                set_stage("emotion", "音声感情の分析", 10)
                segments, emotion_analysis = run_aist_emotion_analysis(
                    processing_input_path,
                    segments,
                    options.emotion_model,
                    options.hf_token,
                    device,
                    internal_work_dir / "emotion_work",
                    status,
                    check_cancelled,
                )
                status("AIST感情分析が完了しました。")
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                record_warning("AIST感情分析は失敗しました。文字起こし処理は続行します: " + details)
                emotion_analysis = build_emotion_analysis_summary(
                    segments,
                    emotion_model_keys,
                    status="failed",
                    error=details,
                )
            set_stage("emotion", "音声感情の分析", 100)
        progress(90)
        speaker_names: dict[str, str] = {}
        speaker_identity_diagnostics: dict[str, Any] = {}
        speaker_repair_summary = {
            "alias_count": 0,
            "aliased_segments": 0,
            "corrected_segments": 0,
        }
        if options.detect_speaker_names:
            set_stage("speaker_names", "話者名の確認", 10)
            status("文字校正とは独立した2段階処理で、自己紹介と話者ラベルを確認しています…")
            try:
                check_cancelled()
                speaker_names = detect_speaker_names_with_ai(
                    speaker_identity_segments,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    check_cancelled,
                    record_ai_usage,
                    status,
                    speaker_identity_diagnostics.update,
                )
                segments, speaker_names, speaker_repair_summary = apply_speaker_identity_repairs(
                    segments,
                    speaker_names,
                    speaker_identity_diagnostics,
                )
                if any(speaker_repair_summary.values()):
                    status(
                        "AI話者連続性修復: "
                        f"重複ラベル {speaker_repair_summary['alias_count']}件 / "
                        f"ラベル統合発話 {speaker_repair_summary['aliased_segments']}件 / "
                        f"断裂修正 {speaker_repair_summary['corrected_segments']}件"
                    )
                    if emotion_analysis is not None:
                        emotion_analysis = build_emotion_analysis_summary(
                            segments,
                            aist_emotion_model_keys(options.emotion_model),
                            status=str(emotion_analysis.get("status") or "completed"),
                            error=str(emotion_analysis.get("error") or ""),
                        )
                check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                record_warning("AI話者名推定を省略しました。話者ラベルで保存します: " + details)
            set_stage("speaker_names", "話者名の確認", 100)
        speaker_profiles = normalize_conversation_speaker_profiles(
            None,
            {str(item.get("speaker") or "UNKNOWN") for item in segments},
            speaker_names,
        )
        session_profile = session_profile_from_media(options.input_path, check_cancelled)
        if session_profile.get("session_date"):
            status(
                "動画の撮影日時から実施日を自動入力しました: "
                f"{session_profile['session_date']}"
            )
        progress(94)
        outline: dict[str, Any] | None = None
        if options.create_outline:
            try:
                set_stage("outline", "議題アウトラインの作成", 10)
                outline = create_outline_with_ai(
                    segments,
                    speaker_names,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    status,
                    check_cancelled,
                    record_ai_usage,
                )
                check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                record_warning("AIアウトライン作成を省略しました。文字起こし結果は保存します: " + details)
            set_stage("outline", "議題アウトラインの作成", 100)
        progress(97)
        check_cancelled()

        set_stage("output", "結果ファイルの保存", 10)
        status("出力ファイルを書き出しています…")
        files = write_outputs(
            options.source_name,
            options.output_dir,
            segments,
            language_code,
            speaker_names,
            options.write_srt,
            options.write_json,
            outline,
            emotion_analysis,
            speaker_profiles,
            check_cancelled,
        )
        check_cancelled()
        set_stage("output", "結果ファイルの保存", 45)
        if options.burn_subtitled_video:
            if is_video_path(options.input_path):
                optional_stem = safe_output_stem(options.source_name)
                optional_ass = options.output_dir / f'{optional_stem}_話者カラー字幕.ass'
                optional_video = options.output_dir / f'{optional_stem}_字幕付き.mp4'
                optional_ass_existed = path_entry_exists(optional_ass)
                optional_video_existed = path_entry_exists(optional_video)
                status("話者名・テーマカラー付き字幕を動画へ焼き込んでいます…")
                try:
                    files.extend(write_subtitled_video_assets(
                        options.input_path,
                        options.source_name,
                        options.output_dir,
                        segments,
                        speaker_names,
                        speaker_profiles,
                        check_cancelled,
                    ))
                except InterruptedError:
                    if not optional_video_existed:
                        optional_video.unlink(missing_ok=True)
                    if not optional_ass_existed:
                        optional_ass.unlink(missing_ok=True)
                    raise
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                    if not optional_video_existed:
                        optional_video.unlink(missing_ok=True)
                    if not optional_ass_existed:
                        optional_ass.unlink(missing_ok=True)
                    warning = f"字幕動画の作成を完了できませんでした: {exc}"
                    record_warning(warning)
            else:
                status("音声ファイルのため、字幕焼き込み動画の作成は省略しました。")
        check_cancelled()
        set_stage("output", "結果ファイルの保存", 75)
        status("元の音声・動画をライブラリへ保存しています…")
        media_target, staged_media_path = stage_media_archive(
            job.id, options.input_path, check_cancelled
        )
        check_cancelled()
        with jobs_lock:
            if job.cancel_event.is_set():
                raise InterruptedError("The transcription job was cancelled.")
            job.status = "committing"
        saved_media_path = commit_staged_media(media_target, staged_media_path)
        staged_media_path = None
        persisted = upsert_library_item(
            item_id=job.id,
            source_name=options.source_name,
            output_dir=options.output_dir,
            media_path=saved_media_path,
            language=language_code,
            segments=segments,
            speaker_names=speaker_names,
            outline=outline,
            emotion_analysis=emotion_analysis,
            files=files,
            write_srt=options.write_srt,
            write_json=True,
            burn_subtitled_video=options.burn_subtitled_video,
            session_profile=session_profile,
            speaker_profiles=speaker_profiles,
            ai_usage=job.ai_usage,
        )
        with jobs_lock:
            job.segments = row_segments(persisted)
            job.speaker_names = speaker_names
            job.session_profile = row_session_profile(persisted)
            job.speaker_profiles = row_speaker_profiles(persisted, job.segments, speaker_names)
            job.outline = outline
            job.emotion_analysis = emotion_analysis
            job.media_path = saved_media_path
            job.files = files
            job.language = language_code
            job.status = "completed"
        set_stage("completed", "処理完了", 100)
        progress(100)
        status("Transcription completed and output files were saved.")
    except InterruptedError as exc:
        with jobs_lock:
            job.status = "cancelled"
            job.error = str(exc)
        set_stage("cancelled", "処理を中止", job.stage_progress)
        status(str(exc))
    except Exception as exc:
        details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        with jobs_lock:
            job.status = "failed"
            job.error = details
        set_stage("failed", "エラー", job.stage_progress)
        status("処理を完了できませんでした: " + details)
    finally:
        if staged_media_path is not None:
            staged_media_path.unlink(missing_ok=True)
        with jobs_lock:
            terminal_status = job.status
            if job.status in {"completed", "failed", "cancelled"}:
                job.finished_at = time.time()
        if terminal_status in {"failed", "cancelled"}:
            cleanup_warnings = cleanup_uncommitted_job_artifacts(job, options)
            if cleanup_warnings:
                with jobs_lock:
                    warning_text = "\n".join(cleanup_warnings)
                    job.output_warning = "\n".join(
                        value for value in (job.output_warning, warning_text) if value
                    )
                    job.logs.extend(cleanup_warnings)
                    job.logs = job.logs[-MAX_LOG_LINES:]
        if model is not None:
            del model
        if model_a is not None:
            del model_a
        diarize_model = None
        diarize_segments = None
        audio = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        # Processing files and any uploaded browser copy are isolated in this job directory.
        upload_parent = options.work_dir.resolve()
        upload_root = UPLOAD_DIRECTORY.resolve()
        if upload_parent.parent == upload_root and upload_parent.name == job.id:
            shutil.rmtree(upload_parent, ignore_errors=True)


def normalize_edited_segments(item_id: str, raw_segments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list):
        raise ValueError("発話データは配列で指定してください。")
    if len(raw_segments) > 100000:
        raise ValueError("発話数が多すぎます。")
    validate_json_value(raw_segments)
    normalized: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    label_aliases = {"怒り": "ang", "喜び": "hap", "悲しみ": "sad", "平常": "neu"}
    valid_emotions = {"", "ang", "hap", "sad", "neu"}
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            raise ValueError(f"発話 {index + 1} の形式が不正です。")
        try:
            start_raw = raw.get("start", 0)
            if start_raw is None or start_raw == "":
                start_raw = 0
            if isinstance(start_raw, bool):
                raise ValueError
            start_number = float(start_raw)
            end_raw = raw.get("end", start_number)
            if end_raw is None or end_raw == "":
                end_raw = start_number
            if isinstance(end_raw, bool):
                raise ValueError
            end_number = float(end_raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"発話 {index + 1} の時刻が不正です。") from exc
        if not math.isfinite(start_number) or not math.isfinite(end_number):
            raise ValueError(f"発話 {index + 1} の時刻にNaN/Infinityは使用できません。")
        start = round(max(0.0, start_number), 3)
        end = round(end_number, 3)
        if end < start:
            raise ValueError(f"発話 {index + 1} の終了時刻は開始時刻以降にしてください。")
        if end > ANALYSIS_MAX_TIMELINE_SECONDS or end - start > 86400:
            raise ValueError(f"発話 {index + 1} の長さが不正です。")
        text_value = raw.get("text", "")
        if not isinstance(text_value, str) or len(text_value) > 50000:
            raise ValueError(f"発話 {index + 1} の本文が不正です。")
        speaker_value = raw.get("speaker") or "UNKNOWN"
        if not isinstance(speaker_value, str) or len(speaker_value) > 80:
            raise ValueError(f"発話 {index + 1} の話者ラベルが不正です。")
        speaker = speaker_value.strip().replace("\r", " ").replace("\n", " ")
        if "id" in raw and not isinstance(raw["id"], str):
            raise ValueError(f"発話 {index + 1} のIDが不正です。")
        segment = dict(raw)
        segment.update({"start": start, "end": end, "speaker": speaker or "UNKNOWN", "text": text_value.strip()})
        segment_id = stable_segment_id(item_id, index, segment)
        if segment_id in used_ids:
            segment_id = uuid.uuid4().hex
        segment["id"] = segment_id
        used_ids.add(segment_id)

        if "kushinada_label" in raw:
            raw_label = raw.get("kushinada_label") or ""
            if not isinstance(raw_label, str):
                raise ValueError(f"発話 {index + 1} の感情ラベルが不正です。")
            requested_label = raw_label.strip().lower()
            requested_label = label_aliases.get(requested_label, requested_label)
            if requested_label not in valid_emotions:
                raise ValueError(f"発話 {index + 1} の感情ラベルが不正です。")
            emotions = dict(segment.get("emotions")) if isinstance(segment.get("emotions"), dict) else {}
            if requested_label:
                previous = emotions.get("kushinada") if isinstance(emotions.get("kushinada"), dict) else {}
                emotions["kushinada"] = {
                    **previous,
                    "model_name": "くしなだ",
                    "model_repo": AIST_EMOTION_MODELS["kushinada"]["emotion_repo"],
                    "label": requested_label,
                    "label_ja": emotion_label_ja(requested_label),
                    "manually_corrected": True,
                }
            else:
                emotions.pop("kushinada", None)
            segment["emotions"] = emotions
        normalized.append(segment)
    return sorted(normalized, key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))


def kushinada_label(segment: dict[str, Any]) -> str:
    emotions = segment.get("emotions")
    if not isinstance(emotions, dict):
        return ""
    data = emotions.get("kushinada")
    return str(data.get("label") or "") if isinstance(data, dict) else ""


def correction_signature(segment: dict[str, Any] | None, speaker_names: dict[str, str]) -> dict[str, Any] | None:
    if segment is None:
        return None
    speaker = str(segment.get("speaker") or "UNKNOWN")
    return {
        "start": round(float(segment.get("start", 0) or 0), 3),
        "end": round(float(segment.get("end", segment.get("start", 0)) or 0), 3),
        "speaker": speaker,
        "speaker_name": str(speaker_names.get(speaker) or ""),
        "text": str(segment.get("text") or "").strip(),
        "emotion": kushinada_label(segment),
    }


def extract_training_clip(media_path: Path | None, item_id: str, event_id: str, segment: dict[str, Any]) -> Path | None:
    if media_path is None or not media_path.is_file() or shutil.which("ffmpeg") is None:
        return None
    start = max(0.0, float(segment.get("start", 0) or 0))
    end = max(start, float(segment.get("end", start) or start))
    duration = end - start
    if duration <= 0:
        return None
    item_dir = TRAINING_AUDIO_DIRECTORY / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    target = item_dir / f"{event_id}.wav"
    temporary = temporary_output_path(target)
    try:
        completed = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-ss", f"{start:.3f}", "-i", str(media_path), "-t", f"{duration:.3f}",
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(temporary),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            return None
        sync_file_data(temporary)
        durable_move(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


TRAINING_MANIFEST_FIELDS = (
    "event_id", "audio_path", "emotion_label", "text", "speaker", "source_name",
    "start", "end", "operation", "created_at", "transcript_id", "segment_id",
)


def training_events_from_connection(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT payload_json FROM training_events ORDER BY created_at, event_id"
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        try:
            event = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise OSError("SQLite内の学習イベントが破損しています。") from exc
        if not isinstance(event, dict) or not isinstance(event.get("event_id"), str):
            raise OSError("SQLite内の学習イベント形式が不正です。")
        events.append(event)
    return events


def training_export_contents(events: list[dict[str, Any]]) -> tuple[str, str]:
    jsonl_content = "".join(
        json.dumps(event, ensure_ascii=False) + "\n" for event in events
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TRAINING_MANIFEST_FIELDS)
    writer.writerow({header: analysis_csv_safe(header) for header in TRAINING_MANIFEST_FIELDS})
    for event in events:
        current = event.get("after") or event.get("before") or {}
        if not isinstance(current, dict):
            current = {}
        manifest_row = {
            "event_id": event["event_id"],
            "audio_path": event.get("audio_clip") or "",
            "emotion_label": current.get("emotion") or "",
            "text": current.get("text") or "",
            "speaker": current.get("speaker_name") or current.get("speaker") or "",
            "source_name": event.get("source_name") or "",
            "start": current.get("start", ""),
            "end": current.get("end", ""),
            "operation": event.get("operation") or "",
            "created_at": event.get("created_at") or "",
            "transcript_id": event.get("transcript_id") or "",
            "segment_id": event.get("segment_id") or "",
        }
        writer.writerow({key: analysis_csv_safe(value) for key, value in manifest_row.items()})
    return jsonl_content, stream.getvalue()


def write_training_exports(events: list[dict[str, Any]]) -> None:
    TRAINING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if not events:
        TRAINING_JSONL_FILE.unlink(missing_ok=True)
        TRAINING_MANIFEST_FILE.unlink(missing_ok=True)
        return
    jsonl_content, manifest_content = training_export_contents(events)
    try:
        current_jsonl = TRAINING_JSONL_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        current_jsonl = None
    if current_jsonl != jsonl_content:
        atomic_write_text(TRAINING_JSONL_FILE, jsonl_content, encoding="utf-8")
    try:
        current_manifest = TRAINING_MANIFEST_FILE.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        current_manifest = None
    if current_manifest != manifest_content:
        atomic_write_text(TRAINING_MANIFEST_FILE, manifest_content, encoding="utf-8-sig")


def legacy_training_events() -> list[dict[str, Any]]:
    if not TRAINING_JSONL_FILE.is_file():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = TRAINING_JSONL_FILE.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        raise
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_id = event.get("event_id") if isinstance(event, dict) else None
        valid_snapshots = all(
            event.get(field) is None or isinstance(event.get(field), dict)
            for field in ("before", "after")
        ) if isinstance(event, dict) else False
        if (
            isinstance(event_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", event_id)
            and valid_snapshots
        ):
            events.append(event)
    return events


def cleanup_unreferenced_training_clips(events: list[dict[str, Any]]) -> None:
    if not TRAINING_AUDIO_DIRECTORY.is_dir():
        return
    referenced_ids = {
        str(event.get("event_id"))
        for event in events
        if event.get("audio_clip") and re.fullmatch(r"[0-9a-f]{32}", str(event.get("event_id")))
    }
    for clip_path in TRAINING_AUDIO_DIRECTORY.rglob("*.wav"):
        if clip_path.stem not in referenced_ids:
            clip_path.unlink(missing_ok=True)
    directories = sorted(
        (path for path in TRAINING_AUDIO_DIRECTORY.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def repair_training_artifacts() -> None:
    """Migrate legacy JSONL once, then rebuild all derived training files."""
    with training_lock:
        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            migrated_row = connection.execute(
                "SELECT value FROM application_metadata WHERE key = ?",
                ("training_events_migrated",),
            ).fetchone()
            migrated = migrated_row is not None and str(migrated_row["value"]) == "1"
            if not migrated:
                for event in legacy_training_events():
                    connection.execute(
                        "INSERT OR IGNORE INTO training_events (event_id, payload_json, created_at) "
                        "VALUES (?, ?, ?)",
                        (
                            event["event_id"],
                            json.dumps(event, ensure_ascii=False),
                            str(event.get("created_at") or ""),
                        ),
                    )
                connection.execute(
                    "UPDATE application_metadata SET value = ? WHERE key = ?",
                    ("1", "training_events_migrated"),
                )
            events = training_events_from_connection(connection)
        try:
            write_training_exports(events)
        except OSError:
            # JSONL/CSV are rebuildable caches and must not prevent startup or
            # roll back a completed one-time migration when Windows locks them.
            app.logger.exception("Could not rebuild derived training artifacts at startup")
    cleanup_unreferenced_training_clips(events)


def refresh_training_exports() -> list[dict[str, Any]]:
    with training_lock:
        with database_connection() as connection:
            events = training_events_from_connection(connection)
        try:
            write_training_exports(events)
        except OSError:
            # JSONL/CSV are derived caches. Downloads are rendered directly
            # from the canonical SQLite snapshot even if Windows has a cache
            # file open or the cache directory is temporarily unavailable.
            app.logger.exception("Could not refresh derived training export files")
    return events


def prepare_training_corrections(
    row: sqlite3.Row,
    old_segments: list[dict[str, Any]],
    new_segments: list[dict[str, Any]],
    old_names: dict[str, str],
    new_names: dict[str, str],
) -> tuple[list[dict[str, Any]], list[Path]]:
    old_by_id = {str(item.get("id")): item for item in old_segments}
    new_by_id = {str(item.get("id")): item for item in new_segments}
    ordered_ids = list(old_by_id) + [item_id for item_id in new_by_id if item_id not in old_by_id]
    media_path = Path(row["media_path"]) if row["media_path"] else None
    events: list[dict[str, Any]] = []
    created_clips: list[Path] = []
    try:
        for segment_id in ordered_ids:
            before = old_by_id.get(segment_id)
            after = new_by_id.get(segment_id)
            before_data = correction_signature(before, old_names)
            after_data = correction_signature(after, new_names)
            if before_data == after_data:
                continue
            operation = "add" if before is None else "delete" if after is None else "update"
            event_id = uuid.uuid4().hex
            reference = after or before
            assert reference is not None
            clip_path = extract_training_clip(media_path, row["id"], event_id, reference)
            if clip_path is not None:
                created_clips.append(clip_path)
            events.append({
                "schema_version": "1.0",
                "event_id": event_id,
                "created_at": utc_now_iso(),
                "transcript_id": row["id"],
                "segment_id": segment_id,
                "operation": operation,
                "source_name": row["source_name"],
                "source_media": str(media_path) if media_path else None,
                "audio_clip": str(clip_path) if clip_path else None,
                "before": before_data,
                "after": after_data,
                "ready_for_kushinada": bool(clip_path and after_data and after_data.get("emotion")),
            })
    except BaseException:
        for clip_path in created_clips:
            clip_path.unlink(missing_ok=True)
        raise
    return events, created_clips


def insert_training_events(
    connection: sqlite3.Connection,
    events: list[dict[str, Any]],
) -> None:
    for event in events:
        connection.execute(
            "INSERT INTO training_events (event_id, payload_json, created_at) "
            "VALUES (?, ?, ?)",
            (
                event["event_id"],
                json.dumps(event, ensure_ascii=False),
                event["created_at"],
            ),
        )
    if events:
        connection.execute(
            "UPDATE application_metadata SET value = ? WHERE key = ?",
            ("1", "training_events_migrated"),
        )


def discard_training_clips(created_clips: list[Path]) -> None:
    for clip_path in created_clips:
        try:
            clip_path.unlink(missing_ok=True)
        except OSError:
            # The canonical DB transaction has already been rolled back. Any
            # retained orphan is removed by repair_training_artifacts at boot.
            pass
    for directory in sorted(
        {clip_path.parent for clip_path in created_clips},
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def record_training_corrections(
    row: sqlite3.Row,
    old_segments: list[dict[str, Any]],
    new_segments: list[dict[str, Any]],
    old_names: dict[str, str],
    new_names: dict[str, str],
) -> int:
    events, created_clips = prepare_training_corrections(
        row, old_segments, new_segments, old_names, new_names
    )
    if not events:
        return 0
    with training_lock:
        original_files: dict[Path, bytes | None] = {}
        try:
            for path in (TRAINING_JSONL_FILE, TRAINING_MANIFEST_FILE):
                original_files[path] = path.read_bytes() if path.is_file() else None
            with database_connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                insert_training_events(connection, events)
                write_training_exports(training_events_from_connection(connection))
        except BaseException:
            for path, original in original_files.items():
                try:
                    if original is not None:
                        atomic_write_bytes(path, original)
                    else:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass
            discard_training_clips(created_clips)
            raise
    return len(events)


def update_library_from_payload(item_id: str, payload: Any) -> dict[str, Any]:
    with library_write_lock:
        return _update_library_from_payload_locked(item_id, payload)


def _update_library_from_payload_locked(
    item_id: str,
    payload: Any,
    *,
    ai_usage_override: dict[str, Any] | None = None,
    record_training: bool = True,
) -> dict[str, Any]:
    row = library_row(item_id)
    if row is None:
        raise LookupError("データが見つかりません。")
    if not isinstance(payload, dict):
        raise ValueError("編集内容が JSON ではありません。")
    validate_json_value(payload)
    expected_revision = payload.get("revision_count")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise ValueError("revision_count is required and must be an integer.")
    current_revision = int(row["revision_count"] or 0)
    if expected_revision != current_revision:
        raise TranscriptConflictError(current_revision)
    recovery_errors, _ = reconcile_edit_transactions_before_mutation(item_id, row)
    if recovery_errors:
        raise OSError(
            'A pending edit transaction could not be recovered safely. Restart the application.'
        )
    row = library_row(item_id)
    if row is None:
        raise LookupError('データが見つかりません。')
    current_revision = int(row['revision_count'] or 0)
    if expected_revision != current_revision:
        raise TranscriptConflictError(current_revision)
    old_segments = row_segments(row)
    old_names = json_load(row["speaker_names_json"], {})
    if not isinstance(old_names, dict):
        old_names = {}
    new_segments = normalize_edited_segments(item_id, payload.get("segments"))
    raw_names = payload.get("speaker_names", {})
    if not isinstance(raw_names, dict):
        raise ValueError("話者名の形式が不正です。")
    labels = {str(item.get("speaker") or "UNKNOWN") for item in new_segments}
    new_names: dict[str, str] = {}
    for label, value in raw_names.items():
        if not isinstance(label, str) or not isinstance(value, str) or len(label) > 80:
            raise ValueError("Invalid speaker name mapping.")
        clean_name = value.strip().replace("\r", " ").replace("\n", " ")
        if label in labels and clean_name:
            if len(clean_name) > 80:
                raise ValueError("話者名は 80 文字以内にしてください。")
            new_names[label] = clean_name
    source_value = payload.get("source_name") or row["source_name"]
    if not isinstance(source_value, str):
        raise ValueError("Invalid source name.")
    source_name = normalize_source_name(source_value)
    if not source_name or len(source_name) > 255:
        raise ValueError("データ名は 1～255 文字で指定してください。")
    session_profile = (
        normalize_session_profile(payload.get("session_profile"))
        if "session_profile" in payload
        else row_session_profile(row)
    )
    speaker_profiles = normalize_conversation_speaker_profiles(
        payload.get("speaker_profiles")
        if "speaker_profiles" in payload
        else json_load(row["speaker_profiles_json"], {}),
        labels,
        new_names,
    )
    for label, profile in speaker_profiles.items():
        if profile["display_name"]:
            new_names[label] = profile["display_name"]

    outline = json_load(row["outline_json"], None)
    emotion_analysis = json_load(row["emotion_analysis_json"], None)
    model_keys = sorted({
        str(model_key)
        for segment in new_segments
        for model_key in ((segment.get("emotions") or {}).keys() if isinstance(segment.get("emotions"), dict) else [])
    })
    if model_keys:
        emotion_analysis = build_emotion_analysis_summary(new_segments, model_keys, status="completed")
    output_dir = Path(row["output_dir"])
    try:
        uses_shared_default = output_dir.resolve() == DEFAULT_OUTPUT_DIRECTORY.resolve()
    except OSError:
        uses_shared_default = output_dir == DEFAULT_OUTPUT_DIRECTORY
    if uses_shared_default:
        output_dir = manual_output_directory(source_name, item_id)
    raw_previous_files = json_load(row["files_json"], [])
    previous_output_dir = Path(str(row['output_dir']))
    previous_files = (
        [Path(str(value)) for value in raw_previous_files]
        if isinstance(raw_previous_files, list)
        else []
    )
    staging_dir = output_dir / f".edit-staging-{uuid.uuid4().hex}"
    transaction_id = staging_dir.name.removeprefix('.edit-staging-')
    preparing_dir = output_dir / f'.edit-preparing-{transaction_id}-{uuid.uuid4().hex}'
    preparing_dir.mkdir(parents=True, exist_ok=False)
    preparing_identity = edit_staging_identity(preparing_dir)
    staging_identity: tuple[int, int] | None = None
    preparation_inventory = capture_edit_cleanup_inventory(preparing_dir, {})

    def cleanup_if_owned(candidate: Path) -> list[str]:
        if not path_entry_exists(candidate):
            return []
        try:
            if edit_staging_identity(candidate) != preparing_identity:
                return []
        except OSError:
            return []
        return cleanup_edit_staging(
            candidate,
            expected_identity=preparing_identity,
            inventory=preparation_inventory,
        )

    try:
        write_edit_preparation_marker(
            preparing_dir,
            output_dir,
            item_id=item_id,
            expected_revision=current_revision,
            previous_output_dir=previous_output_dir,
        )
        with database_connection() as connection:
            preparation_storage_id = edit_storage_id(connection)
            preparation_secret = edit_journal_secret(connection)
        preparation_payload = load_edit_preparation_marker(
            preparing_dir,
            expected_storage_id=preparation_storage_id,
            expected_secret=preparation_secret,
        )
        preparation_inventory = preparation_payload['_cleanup_inventory']
        durable_move(preparing_dir, staging_dir, replace_existing=False)
        if edit_staging_identity(staging_dir) != preparing_identity:
            raise OSError('The published edit staging identity changed unexpectedly.')
        staging_identity = preparing_identity
        staged_files = write_outputs(
            source_name, staging_dir, new_segments, row["language"], new_names,
            bool(row["write_srt"]), True, outline, emotion_analysis, speaker_profiles,
        )
        write_edit_preparation_marker(
            staging_dir,
            output_dir,
            item_id=item_id,
            expected_revision=current_revision,
            previous_output_dir=previous_output_dir,
            staged_files=staged_files,
        )
        core_prepared_payload = load_edit_preparation_marker(
            staging_dir,
            expected_storage_id=preparation_storage_id,
            expected_secret=preparation_secret,
        )
        preparation_inventory = core_prepared_payload['_cleanup_inventory']
    except BaseException as preparation_exc:
        cleanup_errors = [
            *cleanup_if_owned(preparing_dir),
            *cleanup_if_owned(staging_dir),
        ]
        if cleanup_errors:
            raise OSError(
                'Edit preparation failed and owned staging cleanup was incomplete: '
                + '; '.join(cleanup_errors)
            ) from preparation_exc
        raise
    output_warning = ""
    media_path = Path(row["media_path"]) if row["media_path"] else None
    if bool(row["burn_subtitled_video"]) and media_path and media_path.is_file() and is_video_path(media_path):
        optional_assets_before = {
            candidate.resolve()
            for candidate in staging_dir.rglob('*')
            if candidate.is_file()
        }
        try:
            staged_files.extend(write_subtitled_video_assets(
                media_path,
                source_name,
                staging_dir,
                new_segments,
                new_names,
                speaker_profiles,
            ))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            unexpected_optional = [
                candidate
                for candidate in staging_dir.rglob('*')
                if candidate.is_file()
                and candidate.resolve() not in optional_assets_before
            ]
            if unexpected_optional:
                cleanup_errors = cleanup_edit_staging(
                    staging_dir,
                    expected_identity=staging_identity,
                    inventory=preparation_inventory,
                )
                raise OSError(
                    'Optional video generation left unauthenticated files; edit staging '
                    'was retained for safe recovery: '
                    + '; '.join(cleanup_errors)
                ) from exc
            output_warning = f"字幕動画の再作成に失敗しました: {exc}"
    try:
        write_edit_preparation_marker(
            staging_dir,
            output_dir,
            item_id=item_id,
            expected_revision=current_revision,
            previous_output_dir=previous_output_dir,
            staged_files=staged_files,
        )
        prepared_payload = load_edit_preparation_marker(
            staging_dir,
            expected_storage_id=preparation_storage_id,
            expected_secret=preparation_secret,
        )
        preparation_inventory = prepared_payload['_cleanup_inventory']
    except BaseException as inventory_exc:
        cleanup_errors = cleanup_edit_staging(
            staging_dir,
            expected_identity=staging_identity,
            inventory=preparation_inventory,
        )
        if cleanup_errors:
            raise OSError(
                'Edit output inventory could not be authenticated; staging was retained: '
                + '; '.join(cleanup_errors)
            ) from inventory_exc
        raise
    if record_training:
        try:
            training_events, created_training_clips = prepare_training_corrections(
                row, old_segments, new_segments, old_names, new_names
            )
        except BaseException as training_exc:
            cleanup_errors = cleanup_edit_staging(
                staging_dir,
                expected_identity=staging_identity,
                inventory=preparation_inventory,
            )
            if cleanup_errors:
                raise OSError(
                    'Training preparation failed and edit staging was retained: '
                    + '; '.join(cleanup_errors)
                ) from training_exc
            raise
    else:
        training_events, created_training_clips = [], []
    learning_warning = ""
    learning_events = len(training_events)
    try:
        write_edit_transaction_manifest(
            staging_dir,
            output_dir,
            staged_files,
            item_id=item_id,
            expected_revision=current_revision,
            previous_output_dir=previous_output_dir,
        )
    except BaseException as manifest_exc:
        discard_training_clips(created_training_clips)
        cleanup_errors = cleanup_edit_staging(
            staging_dir,
            expected_identity=staging_identity,
            inventory=preparation_inventory,
        )
        if cleanup_errors:
            raise OSError(
                'Edit manifest creation failed and staging cleanup was incomplete: '
                + '; '.join(cleanup_errors)
            ) from manifest_exc
        raise
    try:
        with training_lock:
            all_training_events: list[dict[str, Any]] = []
            with promote_staged_files(staging_dir, output_dir, staged_files) as files:
                with database_connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    record_output_import_provenance(
                        connection, item_id, previous_files
                    )
                    record_output_import_provenance(
                        connection, item_id, files
                    )
                    updated = upsert_library_item(
                        item_id=item_id, source_name=source_name, output_dir=output_dir,
                        media_path=media_path,
                        language=row["language"], segments=new_segments,
                        speaker_names=new_names,
                        outline=outline, emotion_analysis=emotion_analysis, files=files,
                        write_srt=bool(row["write_srt"]), write_json=True,
                        increment_revision=True, created_at=row["created_at"],
                        session_profile=session_profile, speaker_profiles=speaker_profiles,
                        burn_subtitled_video=bool(row["burn_subtitled_video"]),
                        expected_revision=current_revision,
                        connection=connection,
                        ai_usage=(
                            ai_usage_override
                            if ai_usage_override is not None
                            else json_load(row["ai_usage_json"], {})
                        ),
                    )
                    insert_training_events(connection, training_events)
                    if training_events:
                        all_training_events = training_events_from_connection(connection)
            if training_events:
                try:
                    write_training_exports(all_training_events)
                except (OSError, csv.Error) as exc:
                    learning_warning = (
                        "学習履歴はデータベースへ保存しましたが、派生ファイルを更新できませんでした: "
                        f"{exc}"
                    )
    except BaseException:
        discard_uncommitted_clips = False
        try:
            with database_connection() as connection:
                revision_row = connection.execute(
                    'SELECT revision_count FROM library_items WHERE id = ?',
                    (item_id,),
                ).fetchone()
            discard_uncommitted_clips = (
                revision_row is not None
                and int(revision_row['revision_count'] or 0) == current_revision
            )
        except (OSError, sqlite3.Error):
            # Preserve ambiguous clips. Startup repair removes them if no
            # committed training event references them.
            pass
        if discard_uncommitted_clips:
            discard_training_clips(created_training_clips)
        raise
    with jobs_lock:
        job = jobs.get(item_id)
        if job is not None:
            job.source_name = source_name
            job.segments = row_segments(updated)
            job.speaker_names = new_names
            job.session_profile = session_profile
            job.speaker_profiles = speaker_profiles
            job.emotion_analysis = emotion_analysis
            job.files = files
            job.revision_count = int(updated["revision_count"] or 0)
    result = library_public(updated)
    result["learning_events"] = learning_events
    result["learning_warning"] = learning_warning
    result["output_warning"] = output_warning
    return result


def parse_bool(name: str, default: bool = False) -> bool:
    values = request.form.getlist(name)
    if not values:
        return default
    return any(value.lower() in {"1", "true", "yes", "on"} for value in values)


def parse_optional_int(name: str) -> int | None:
    raw = request.form.get(name, "").strip()
    if not raw or raw == "0":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} は整数で指定してください。") from exc
    if not 1 <= value <= 20:
        raise ValueError(f"{name} は 1～20 で指定してください。")
    return value


def parse_optional_float(name: str, default: float, min_value: float, max_value: float) -> float:
    raw = request.form.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} は数値で指定してください。") from exc
    if not math.isfinite(value) or not min_value <= value <= max_value:
        raise ValueError(f"{name} は {min_value:g}～{max_value:g} で指定してください。")
    return value


def parse_audio_preprocess() -> str:
    preset = request.form.get("audio_preprocess", "standard").strip() or "standard"
    if preset not in AUDIO_PREPROCESS_PRESETS:
        raise ValueError("音声前処理の指定が不正です。")
    return preset


def recover_delete_quarantines() -> list[str]:
    """Resolve crash-left delete staging from the canonical library row state."""
    warnings: list[str] = []
    storage_roots = ((MEDIA_DIRECTORY, "media"), (THUMBNAIL_DIRECTORY, "thumbnail"))
    with database_connection() as connection:
        for storage_root, asset_kind in storage_roots:
            if not storage_root.is_dir():
                continue
            for quarantine_root in sorted(storage_root.glob(".delete-staging-*")):
                if quarantine_root.is_symlink() or not quarantine_root.is_dir():
                    warnings.append(f"Unrecognized delete quarantine retained: {quarantine_root}")
                    continue
                try:
                    quarantined_assets = list(quarantine_root.iterdir())
                except OSError as exc:
                    warnings.append(f"Could not inspect delete quarantine {quarantine_root}: {exc}")
                    continue
                for quarantined in quarantined_assets:
                    if asset_kind == "media":
                        item_id = quarantined.name
                    else:
                        match = re.fullmatch(
                            r"(?:text_mining|word_cloud)_(.+)\.svg",
                            quarantined.name,
                        )
                        item_id = match.group(1) if match else ""
                    if not item_id:
                        warnings.append(f"Unrecognized quarantined asset retained: {quarantined}")
                        continue
                    row_exists = connection.execute(
                        "SELECT 1 FROM library_items WHERE id = ?",
                        (item_id,),
                    ).fetchone() is not None
                    target = storage_root / quarantined.name
                    try:
                        if row_exists:
                            if target.exists() or target.is_symlink():
                                warnings.append(
                                    f"Delete recovery target already exists; quarantine retained: {quarantined}"
                                )
                                continue
                            durable_move(quarantined, target, replace_existing=False)
                        elif quarantined.is_dir() and not quarantined.is_symlink():
                            shutil.rmtree(quarantined)
                        else:
                            quarantined.unlink(missing_ok=True)
                    except OSError as exc:
                        action = "restore" if row_exists else "remove"
                        warnings.append(
                            f"Could not {action} quarantined asset {quarantined}: {exc}"
                        )
                try:
                    quarantine_root.rmdir()
                except OSError:
                    # Unknown, conflicting, or locked assets remain recoverable.
                    pass
    return warnings


def discover_edit_transaction_staging_dirs(
    *,
    additional_output_roots: list[Path] | None = None,
    include_database_outputs: bool = True,
) -> list[Path]:
    candidates: dict[str, Path] = {}
    scan_errors: list[str] = []

    def remember(candidate: Path) -> None:
        cleanup_match = re.fullmatch(
            r'\.edit-cleanup-((?:edit-staging-[0-9a-f]{32}|edit-preparing-[0-9a-f]{32}-[0-9a-f]{32}))-[0-9a-f]{32}',
            candidate.name,
        )
        if cleanup_match is not None:
            try:
                if path_is_link_or_reparse(candidate) or not candidate.is_dir():
                    scan_errors.append(f'Unsafe edit cleanup quarantine: {candidate}')
                    return
                cleanup_identity = edit_staging_identity(candidate)
                with hold_edit_directory_against_rename(candidate, cleanup_identity):
                    cleanup_children = list(candidate.iterdir())
                if not cleanup_children:
                    if edit_staging_identity(candidate) != cleanup_identity:
                        raise OSError('An empty cleanup quarantine changed identity.')
                    candidate.rmdir()
                    sync_directory_metadata(candidate.parent, required=True)
                    return
                journal_names = {
                    EDIT_TRANSACTION_MANIFEST_NAME,
                    EDIT_PREPARATION_MARKER_NAME,
                }
                if any(
                    re.fullmatch(
                        r'\..+\.authenticated-[0-9a-f]{32}\.recovery',
                        child.name,
                    )
                    for child in cleanup_children
                ):
                    print(
                        f'Conflicted edit cleanup quarantine retained: {candidate}',
                        file=sys.stderr,
                    )
                    return
                if not any(child.name in journal_names for child in cleanup_children):
                    print(
                        f'Unrecognized edit cleanup quarantine retained: {candidate}',
                        file=sys.stderr,
                    )
                    return
                restored = candidate.with_name(f'.{cleanup_match.group(1)}')
                if path_entry_exists(restored):
                    scan_errors.append(
                        f'Edit cleanup quarantine conflicts with staging path: {candidate}'
                    )
                    return
                durable_move(candidate, restored, replace_existing=False)
                if edit_staging_identity(restored) != cleanup_identity:
                    raise OSError('A cleanup quarantine changed identity during restore.')
                candidate = restored
            except OSError as exc:
                scan_errors.append(f'{candidate}: {exc}')
                return
        if not re.fullmatch(
            r'(?:\.edit-staging-[0-9a-f]{32}|\.edit-preparing-[0-9a-f]{32}-[0-9a-f]{32})',
            candidate.name,
        ):
            return
        try:
            if path_is_link_or_reparse(candidate) or not candidate.is_dir():
                scan_errors.append(f'Unsafe edit staging path: {candidate}')
                return
        except OSError as exc:
            scan_errors.append(f'{candidate}: {exc}')
            return
        key = windows_case_insensitive_text(os.path.abspath(str(candidate)))
        candidates.setdefault(key, candidate)

    default_root = Path(os.path.abspath(os.fspath(DEFAULT_OUTPUT_DIRECTORY)))
    if path_entry_exists(default_root):
        if path_has_reparse_ancestor(default_root) or not default_root.is_dir():
            scan_errors.append(f'Unsafe default output directory: {default_root}')
        else:
            pending = [default_root]
            visited: set[tuple[Any, ...]] = set()
            while pending:
                current = pending.pop()
                try:
                    if path_is_link_or_reparse(current):
                        scan_errors.append(f'Output directory became a reparse point: {current}')
                        continue
                    current_stat = current.stat()
                    if int(current_stat.st_ino):
                        identity = (
                            'inode',
                            int(current_stat.st_dev),
                            int(current_stat.st_ino),
                        )
                    else:
                        identity = (
                            'path',
                            windows_case_insensitive_text(
                                os.path.abspath(str(current))
                            ),
                        )
                    if identity in visited:
                        continue
                    visited.add(identity)
                    with os.scandir(current) as entries:
                        children = list(entries)
                except OSError as exc:
                    scan_errors.append(f'{current}: {exc}')
                    continue
                for entry in children:
                    child = Path(entry.path)
                    stage_name = bool(re.fullmatch(
                        r'(?:\.edit-staging-[0-9a-f]{32}|\.edit-preparing-[0-9a-f]{32}-[0-9a-f]{32}|\.edit-cleanup-(?:edit-staging-[0-9a-f]{32}|edit-preparing-[0-9a-f]{32}-[0-9a-f]{32})-[0-9a-f]{32})',
                        entry.name,
                    ))
                    try:
                        if path_is_link_or_reparse(child):
                            if stage_name:
                                scan_errors.append(
                                    f'Unsafe edit staging reparse point: {child}'
                                )
                            continue
                        is_directory = entry.is_dir(follow_symlinks=False)
                    except OSError as exc:
                        scan_errors.append(f'{child}: {exc}')
                        continue
                    if stage_name:
                        if is_directory:
                            remember(child)
                        else:
                            scan_errors.append(f'Edit staging path is not a directory: {child}')
                    elif is_directory:
                        pending.append(child)

    output_roots = list(additional_output_roots or [])
    if include_database_outputs:
        with database_connection() as connection:
            output_rows = connection.execute(
                'SELECT DISTINCT output_dir FROM library_items'
            ).fetchall()
        output_roots.extend(Path(str(row['output_dir'])) for row in output_rows)
    for raw_output_root in output_roots:
        try:
            output_root = Path(os.path.abspath(os.fspath(raw_output_root)))
            if path_has_reparse_ancestor(output_root):
                scan_errors.append(f'Unsafe output directory reparse point: {output_root}')
                continue
            if not output_root.is_dir():
                continue
            for candidate in output_root.glob('.edit-staging-*'):
                remember(candidate)
            for candidate in output_root.glob('.edit-preparing-*'):
                remember(candidate)
            for candidate in output_root.glob('.edit-cleanup-*'):
                remember(candidate)
        except OSError as exc:
            scan_errors.append(str(exc))
    if scan_errors:
        raise OSError('Could not scan edit transactions: ' + '; '.join(scan_errors))
    return sorted(candidates.values(), key=lambda path: os.path.normcase(str(path)))


def cleanup_prepared_edit_staging(
    staging_dir: Path,
    payload: dict[str, Any],
) -> None:
    ensure_staging_tree_has_no_reparse_points(staging_dir)
    cleanup_errors = cleanup_edit_staging(
        staging_dir,
        expected_identity=payload['_staging_identity'],
        inventory=payload['_cleanup_inventory'],
    )
    if cleanup_errors:
        raise OSError('Prepared edit staging cleanup failed: ' + '; '.join(cleanup_errors))


def recover_edit_transactions() -> list[str]:
    staging_dirs = discover_edit_transaction_staging_dirs()
    if not staging_dirs:
        return []
    with database_connection() as connection:
        storage_id = edit_storage_id(connection)
        journal_secret = edit_journal_secret(connection)
        library_state = {
            str(row['id']): {
                'revision': int(row['revision_count'] or 0),
                'output_root': Path(str(row['output_dir'])).resolve(),
            }
            for row in connection.execute(
                'SELECT id, revision_count, output_dir FROM library_items'
            ).fetchall()
        }
    loaded: list[tuple[Path, dict[str, Any]]] = []
    prepared: list[tuple[Path, dict[str, Any]]] = []
    fatal_errors: list[str] = []
    warnings_found: list[str] = []

    for staging_dir in staging_dirs:
        manifest = staging_dir / EDIT_TRANSACTION_MANIFEST_NAME
        is_preparing = staging_dir.name.startswith('.edit-preparing-')
        if not manifest.exists() and not manifest.is_symlink():
            marker = staging_dir / EDIT_PREPARATION_MARKER_NAME
            if is_preparing and not marker.exists() and not marker.is_symlink():
                try:
                    ensure_staging_tree_has_no_reparse_points(staging_dir)
                    if any(staging_dir.iterdir()):
                        warnings_found.append(
                            f'Unrecognized preparing directory retained: {staging_dir}'
                        )
                    else:
                        empty_identity = edit_staging_identity(staging_dir)
                        cleanup_errors = cleanup_edit_staging(
                            staging_dir,
                            expected_identity=empty_identity,
                            inventory=capture_edit_cleanup_inventory(staging_dir, {}),
                        )
                        warnings_found.extend(
                            f'{staging_dir}: {message}' for message in cleanup_errors
                        )
                except OSError as exc:
                    warnings_found.append(f'{staging_dir}: {exc}')
                continue
            try:
                prepared.append((
                    staging_dir,
                    load_edit_preparation_marker(
                        staging_dir,
                        expected_storage_id=storage_id,
                        expected_secret=journal_secret,
                    ),
                ))
            except (OSError, ValueError) as exc:
                if is_preparing:
                    warnings_found.append(
                        f'Unrecognized preparing directory retained: {staging_dir}: {exc}'
                    )
                else:
                    fatal_errors.append(f'{staging_dir}: {exc}')
            continue
        try:
            loaded.append((
                staging_dir,
                load_edit_transaction_manifest(
                    staging_dir,
                    expected_storage_id=storage_id,
                    expected_secret=journal_secret,
                ),
            ))
        except (OSError, ValueError) as exc:
            fatal_errors.append(f'{staging_dir}: {exc}')

    item_counts = Counter(
        payload['item_id'] for _, payload in [*loaded, *prepared]
    )
    duplicate_items = {
        item_id for item_id, count in item_counts.items() if count > 1
    }
    if duplicate_items:
        fatal_errors.append(
            'Multiple edit transactions exist for: ' + ', '.join(sorted(duplicate_items))
        )

    for staging_dir, payload in prepared:
        item_id = payload['item_id']
        if item_id in duplicate_items:
            continue
        try:
            if staging_dir.name.startswith('.edit-preparing-'):
                cleanup_prepared_edit_staging(staging_dir, payload)
                continue
            state = library_state.get(item_id)
            if state is None:
                raise OSError('The prepared edit library row is missing.')
            if state['revision'] != payload['expected_revision']:
                raise OSError('The prepared edit database revision has changed.')
            if state['output_root'] != payload['_previous_output_root']:
                raise OSError('The prepared edit does not match the library output directory.')
            cleanup_prepared_edit_staging(staging_dir, payload)
        except (OSError, ValueError) as exc:
            fatal_errors.append(f'{staging_dir}: {exc}')

    for staging_dir, payload in loaded:
        item_id = payload['item_id']
        if item_id in duplicate_items:
            continue
        try:
            state = library_state.get(item_id)
            if state is None:
                raise OSError('The edit transaction library row is missing.')
            current_revision = state['revision']
            expected_revision = payload['expected_revision']
            target_revision = payload['target_revision']
            if current_revision == expected_revision:
                if state['output_root'] != payload['_previous_output_root']:
                    raise OSError('The uncommitted edit does not match the library output directory.')
                rollback_edit_transaction(staging_dir, payload)
            elif current_revision == target_revision:
                if state['output_root'] != payload['_output_root']:
                    raise OSError('The committed edit does not match the library output directory.')
                cleanup_errors = finish_committed_edit_transaction(staging_dir, payload)
                warnings_found.extend(
                    f'{staging_dir}: {message}' for message in cleanup_errors
                )
            elif current_revision > target_revision:
                if state['output_root'] != payload['_output_root']:
                    raise OSError(
                        'A stale edit transaction belongs to a different output directory.'
                    )
                cleanup_errors = cleanup_edit_staging(
                    staging_dir,
                    expected_identity=payload['_staging_identity'],
                    inventory=edit_transaction_cleanup_inventory(staging_dir, payload),
                )
                warnings_found.extend(
                    f'{staging_dir}: {message}' for message in cleanup_errors
                )
            else:
                raise OSError('The database revision predates the edit transaction.')
        except (OSError, ValueError, sqlite3.Error) as exc:
            fatal_errors.append(f'{staging_dir}: {exc}')

    if fatal_errors:
        raise RuntimeError(
            'Unsafe edit transaction recovery; automatic import was stopped: '
            + '; '.join(fatal_errors)
        )
    return warnings_found


def reconcile_edit_transactions_before_mutation(
    item_id: str,
    library_item: sqlite3.Row,
) -> tuple[list[str], list[Path]]:
    errors: list[str] = []
    retained: list[Path] = []
    try:
        staging_dirs = discover_edit_transaction_staging_dirs(
            additional_output_roots=[Path(str(library_item['output_dir']))],
            include_database_outputs=False,
        )
        if not staging_dirs:
            return errors, retained
        with database_connection() as connection:
            storage_id = edit_storage_id(connection)
            journal_secret = edit_journal_secret(connection)
            row = connection.execute(
                'SELECT revision_count, output_dir FROM library_items WHERE id = ?',
                (item_id,),
            ).fetchone()
        if row is None:
            return ['The library row disappeared before edit reconciliation.'], retained
        current_revision = int(row['revision_count'] or 0)
        current_output_root = Path(str(row['output_dir'])).resolve()
        matches: list[tuple[Path, str, dict[str, Any]]] = []
        for staging_dir in staging_dirs:
            manifest = staging_dir / EDIT_TRANSACTION_MANIFEST_NAME
            try:
                if manifest.exists() or manifest.is_symlink():
                    payload = load_edit_transaction_manifest(
                        staging_dir,
                        expected_storage_id=storage_id,
                        expected_secret=journal_secret,
                    )
                    kind = 'transaction'
                else:
                    payload = load_edit_preparation_marker(
                        staging_dir,
                        expected_storage_id=storage_id,
                        expected_secret=journal_secret,
                    )
                    kind = 'preparation'
            except (OSError, ValueError) as exc:
                if staging_dir.name.startswith('.edit-preparing-'):
                    retained.append(staging_dir)
                    continue
                errors.append(f'{staging_dir}: {exc}')
                retained.append(staging_dir)
                continue
            if payload['item_id'] == item_id:
                matches.append((staging_dir, kind, payload))

        if len(matches) > 1:
            errors.append('Multiple pending edit transactions exist for this library item.')
            retained.extend(staging_dir for staging_dir, _, _ in matches)
            return errors, sorted(set(retained), key=str)

        for staging_dir, kind, payload in matches:
            try:
                if kind == 'preparation':
                    if current_revision != payload['expected_revision']:
                        raise OSError('The prepared edit database revision has changed.')
                    if current_output_root != payload['_previous_output_root']:
                        raise OSError('The prepared edit output directory no longer matches.')
                    cleanup_prepared_edit_staging(staging_dir, payload)
                else:
                    cleanup_errors = reconcile_edit_transaction_with_database(
                        staging_dir,
                        payload,
                    )
                    if cleanup_errors:
                        raise OSError('; '.join(cleanup_errors))
                if staging_dir.exists() or staging_dir.is_symlink():
                    raise OSError('The edit staging directory could not be removed.')
            except (OSError, ValueError, sqlite3.Error) as exc:
                errors.append(f'{staging_dir}: {exc}')
                retained.append(staging_dir)
    except (OSError, ValueError, sqlite3.Error) as exc:
        errors.append(str(exc))
    return errors, sorted(set(retained), key=str)


def reconcile_edit_transactions_before_delete(
    item_id: str,
    library_item: sqlite3.Row,
) -> tuple[list[str], list[Path]]:
    return reconcile_edit_transactions_before_mutation(item_id, library_item)


def initialize_application() -> None:
    if not acquire_instance_lock():
        raise RuntimeError("Another Gurumoji process is already using this data directory.")
    try:
        initialize_library(repair_provenance=False)
        for recovery_warning in recover_edit_transactions():
            print(f'Edit recovery warning: {recovery_warning}', file=sys.stderr)
        with database_connection() as connection:
            repair_output_import_provenance(connection)
        for recovery_warning in recover_delete_quarantines():
            print(f"Delete recovery warning: {recovery_warning}", file=sys.stderr)
        repair_training_artifacts()
        cleanup_orphaned_uploads()
        import_existing_outputs()
    except Exception:
        release_instance_lock()
        raise


@app.get("/")
def index() -> str:
    runtime = runtime_info()
    return render_template(
        "index.html",
        app_name=APP_NAME,
        product_name=PRODUCT_NAME,
        app_version=APP_VERSION,
        app_creator=APP_CREATOR,
        runtime=runtime,
    )


@app.get("/api/config")
def api_config():
    machine = get_machine_profile()
    try:
        config = load_token_config(TOKEN_FILE)
        return jsonify({
            "ok": True,
            **config.availability(),
            "default_output_dir": str(DEFAULT_OUTPUT_DIRECTORY) if local_path_access_allowed() else "",
            "machine": machine,
            "runtime": runtime_info(),
        })
    except RuntimeError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
            "token_file": TOKEN_FILE.name,
            "machine": machine,
            "runtime": runtime_info(),
        }), 500


@app.get("/api/ai/models")
def api_ai_models():
    provider = str(request.args.get("provider") or "").strip().casefold()
    try:
        config = load_token_config(TOKEN_FILE)
        models = available_ai_models(provider, config)
        selected = config.openai_model if provider == "openai" else config.google_model
        return jsonify({
            "provider": provider,
            "selected_model": selected,
            "models": models,
            "source": TOKEN_FILE.name,
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502


@app.put("/api/ai/model")
def api_update_ai_model():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "モデル設定が JSON ではありません。"}), 400
    try:
        config = update_token_model(
            payload.get("provider"),
            payload.get("model"),
            TOKEN_FILE,
        )
        return jsonify({
            "ok": True,
            **config.availability(),
            "message": f"{TOKEN_FILE.name} のモデル設定を更新しました。",
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/system/activity")
def api_system_activity():
    return jsonify({"ok": True, **system_activity_snapshot()})


@app.get("/api/speakers")
def get_speaker_registry():
    include_inactive = request.args.get("include_inactive", "1") != "0"
    records, revision = speaker_registry_snapshot(include_inactive=include_inactive)
    return jsonify({
        "speakers": records,
        "total": len(records),
        "registry_revision": revision,
    })


@app.put("/api/speakers")
def update_speaker_registry():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "話者管理の編集内容がJSONではありません。"}), 400
    try:
        expected_revision = parse_registry_revision(payload.get("registry_revision"))
        records, revision = save_speaker_registry_records(
            payload.get("speakers"),
            delete_ids=payload.get("delete_ids"),
            expected_revision=expected_revision,
        )
        return jsonify({
            "speakers": records,
            "total": len(records),
            "registry_revision": revision,
        })
    except SpeakerRegistryConflictError as exc:
        return jsonify({
            "error": str(exc),
            "conflict": True,
            "current_revision": exc.current_revision,
        }), 409
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"error": f"話者管理データを保存できません: {exc}"}), 500


@app.post("/api/speakers/import")
def import_speaker_registry():
    upload = request.files.get("csv_file")
    if upload is None or not upload.filename:
        return jsonify({"error": "GoogleフォームまたはスプレッドシートのCSVを選択してください。"}), 400
    try:
        expected_revision = parse_registry_revision(request.form.get("registry_revision"))
        records, imported_count, revision = import_speaker_registry_csv(
            read_upload_limited(upload, MAX_CSV_UPLOAD_BYTES),
            expected_revision=expected_revision,
        )
        return jsonify({
            "speakers": records,
            "total": len(records),
            "imported_count": imported_count,
            "registry_revision": revision,
        })
    except SpeakerRegistryConflictError as exc:
        return jsonify({
            "error": str(exc),
            "conflict": True,
            "current_revision": exc.current_revision,
        }), 409
    except RequestEntityTooLarge:
        raise
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error) as exc:
        return jsonify({"error": f"CSVを取り込めません: {exc}"}), 500


@app.get("/api/speakers/export.csv")
def export_speaker_registry():
    content = speaker_registry_csv_bytes(list_speaker_registry())
    return send_file(
        io.BytesIO(content),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="gurumoji_speaker_registry.csv",
    )


@app.post("/api/select-input")
def select_input_file():
    if not local_path_access_allowed():
        return jsonify({"error": "Local filesystem selection is disabled for remote access."}), 403
    if not runtime_info()["native_file_dialog"]:
        return jsonify({
            "error": "この実行環境ではOSのファイル選択画面を利用できません。",
            "hint": "ブラウザーのファイルアップロードを使用してください。",
            "browser_upload_only": True,
        }), 409
    if not file_dialog_lock.acquire(blocking=False):
        return jsonify({"error": "ファイル選択画面をすでに開いています。"}), 409
    try:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            return jsonify({
                "error": "Windows のファイル選択画面を開けませんでした。",
                "hint": "ファイルのフルパスを入力欄へ直接貼り付けてください。",
                "details": str(exc),
            }), 500

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        try:
            selected = filedialog.askopenfilename(
                parent=root,
                title="処理する音声・動画ファイルを選択",
                filetypes=[
                    ("音声・動画", "*.mp4 *.m4v *.mov *.mkv *.wav *.mp3 *.m4a *.flac"),
                    ("動画", "*.mp4 *.m4v *.mov *.mkv"),
                    ("音声", "*.wav *.mp3 *.m4a *.flac"),
                    ("すべてのファイル", "*.*"),
                ],
            )
        finally:
            root.destroy()

        if not selected:
            return jsonify({"ok": True, "cancelled": True})
        path = resolve_local_media_path(selected)
        return jsonify({
            "ok": True,
            "cancelled": False,
            "path": str(path),
            "name": path.name,
            "size": path.stat().st_size,
            "media_kind": media_kind(path),
        })
    except (ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        file_dialog_lock.release()


@app.post("/api/source-thumbnail")
def source_thumbnail():
    if not local_path_access_allowed():
        return jsonify({"error": "Local filesystem thumbnails are disabled for remote access."}), 403
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("path"), str):
            raise ValueError("A media path is required.")
        source_path = resolve_local_media_path(payload["path"])
        thumbnail_path = generate_video_thumbnail(source_path)
        return send_file(thumbnail_path, mimetype="image/jpeg", conditional=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
        return jsonify({"error": f"サムネイルを作成できません: {exc}"}), 500


@app.get("/api/library")
def list_library():
    keyword = request.args.get("keyword", "").strip().casefold()
    speaker_filter = request.args.get("speaker", "").strip().casefold()
    emotion_filter = request.args.get("emotion", "").strip().casefold()
    sort_key = request.args.get("sort", "updated_desc").strip()
    with database_connection() as connection:
        rows = connection.execute("SELECT * FROM library_items ORDER BY updated_at DESC").fetchall()

    all_speakers: set[str] = set()
    all_emotions: set[str] = set()
    candidates: list[tuple[sqlite3.Row, int, list[str], list[str]]] = []
    for row in rows:
        segments = row_segments(row)
        names = json_load(row["speaker_names_json"], {})
        if not isinstance(names, dict):
            names = {}
        speakers = sorted({
            str(names.get(str(item.get("speaker") or "")) or default_speaker_name(item.get("speaker")))
            for item in segments if item.get("speaker")
        })
        emotions = sorted({value for item in segments for value in emotion_values(item)})
        all_speakers.update(speakers)
        all_emotions.update(emotions)
        searchable_segments = [str(item.get("text") or "") for item in segments]
        match_count = sum(1 for text_value in searchable_segments if keyword and keyword in text_value.casefold())
        source_match = bool(keyword and keyword in str(row["source_name"]).casefold())
        if keyword and not match_count and not source_match:
            continue
        if speaker_filter and not any(speaker_filter == value.casefold() for value in speakers):
            continue
        if emotion_filter and not any(emotion_filter == value.casefold() for value in emotions):
            continue
        candidates.append((row, match_count, speakers, emotions))

    if sort_key == "created_desc":
        candidates.sort(key=lambda item: item[0]["created_at"], reverse=True)
    elif sort_key == "speaker":
        candidates.sort(key=lambda item: ((item[2][0] if item[2] else "￿"), item[0]["updated_at"]))
    elif sort_key == "emotion":
        candidates.sort(key=lambda item: ((item[3][0] if item[3] else "￿"), item[0]["updated_at"]))
    elif sort_key == "keyword":
        candidates.sort(key=lambda item: (item[1], item[0]["updated_at"]), reverse=True)
    elif sort_key == "name":
        candidates.sort(key=lambda item: str(item[0]["source_name"]).casefold())
    else:
        candidates.sort(key=lambda item: item[0]["updated_at"], reverse=True)
    return jsonify({
        "items": [library_public(row, full=False, match_count=count) for row, count, _, _ in candidates],
        "total": len(candidates),
        "facets": {"speakers": sorted(all_speakers), "emotions": sorted(all_emotions)},
    })


@app.post("/api/library")
def create_library_item():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "追加内容が JSON ではありません。"}), 400
    source_name = str(payload.get("source_name") or "新規文字起こし").strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in source_name):
        return jsonify({"error": "Source names cannot contain control characters."}), 400
    if not source_name or len(source_name) > 255:
        return jsonify({"error": "データ名は 1～255 文字で指定してください。"}), 400
    item_id = uuid.uuid4().hex
    try:
        row = upsert_library_item(
            item_id=item_id,
            source_name=source_name,
            output_dir=manual_output_directory(source_name, item_id),
            media_path=None, language=None, segments=[], speaker_names={}, outline=None,
            emotion_analysis=None, files=[], write_srt=True, write_json=True,
        )
        return jsonify(library_public(row)), 201
    except (OSError, sqlite3.Error) as exc:
        return jsonify({"error": f"データを追加できません: {exc}"}), 500


@app.get("/api/library/<item_id>")
def get_library_item(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    return jsonify(library_public(row))


@app.post("/api/library/<item_id>/speaker-identification")
def rerun_library_speaker_identification(item_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "話者特定の指定が JSON ではありません。"}), 400
    provider = str(payload.get("provider") or "").strip().casefold()
    if provider not in {"openai", "google"}:
        return jsonify({"error": "OpenAI または Google Gemini を選択してください。"}), 400
    expected_revision = payload.get("revision_count")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        return jsonify({"error": "最新の編集内容を保存してから実行してください。"}), 400
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    current_revision = int(row["revision_count"] or 0)
    if current_revision != expected_revision:
        return jsonify({
            "error": "別の画面でデータが更新されています。再読み込みしてください。",
            "conflict": True,
            "current_revision": current_revision,
        }), 409
    segments = row_segments(row)
    if not segments:
        return jsonify({"error": "話者特定に使用できる発話がありません。"}), 400

    try:
        token_config = load_token_config()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    if provider == "openai":
        api_key, model = token_config.openai_api_key, token_config.openai_model
    else:
        api_key, model = token_config.google_api_key, token_config.google_model
    if not api_key:
        label = "OpenAI" if provider == "openai" else "Google Gemini"
        return jsonify({"error": f"tokens.json に {label} のAPIキーを設定してください。"}), 400

    run_usage: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}

    def record_usage(sample: dict[str, Any]) -> None:
        nonlocal run_usage
        run_usage = merge_ai_usage(run_usage, sample)

    try:
        detected_names = detect_speaker_names_with_ai(
            segments,
            provider,
            api_key,
            model,
            usage_callback=record_usage,
            diagnostics_callback=diagnostics.update,
        )
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        return jsonify({
            "error": "話者特定AIを実行できませんでした: "
            + public_diagnostic_text(str(exc), reveal_local_paths=False)
        }), 502

    try:
        with library_write_lock:
            latest = library_row(item_id)
            if latest is None:
                return jsonify({"error": "データが見つかりません。"}), 404
            latest_revision = int(latest["revision_count"] or 0)
            if latest_revision != expected_revision:
                return jsonify({
                    "error": "AI処理中にデータが更新されました。結果を反映せず再読み込みします。",
                    "conflict": True,
                    "current_revision": latest_revision,
                }), 409
            existing_names = json_load(latest["speaker_names_json"], {})
            if not isinstance(existing_names, dict):
                existing_names = {}
            latest_segments = row_segments(latest)
            segments, merged_names, repair_summary = apply_speaker_identity_repairs(
                latest_segments,
                {
                    str(label): clean_single_line(name, 80)
                    for label, name in existing_names.items()
                    if clean_single_line(name, 80)
                },
                diagnostics,
            )
            _, detected_names, _ = apply_speaker_identity_repairs(
                segments,
                detected_names,
                diagnostics,
            )
            speaker_profiles = row_speaker_profiles(latest, segments, merged_names)
            applied_names: dict[str, str] = {}
            for label, name in detected_names.items():
                profile = speaker_profiles.get(label, {})
                if merged_names.get(label) or profile.get("display_name"):
                    continue
                merged_names[label] = name
                profile["display_name"] = name
                speaker_profiles[label] = profile
                applied_names[label] = name
            combined_usage = merge_ai_usage(
                json_load(latest["ai_usage_json"], {}),
                run_usage,
            )
            repairs_applied = bool(
                repair_summary["aliased_segments"]
                or repair_summary["corrected_segments"]
            )
            if applied_names or repairs_applied:
                result = _update_library_from_payload_locked(
                    item_id,
                    {
                        "revision_count": latest_revision,
                        "source_name": latest["source_name"],
                        "segments": segments,
                        "speaker_names": merged_names,
                        "session_profile": row_session_profile(latest),
                        "speaker_profiles": speaker_profiles,
                    },
                    ai_usage_override=combined_usage,
                    record_training=False,
                )
            else:
                with database_connection() as connection:
                    connection.execute(
                        "UPDATE library_items SET ai_usage_json = ?, updated_at = ? "
                        "WHERE id = ? AND revision_count = ?",
                        (
                            json.dumps(combined_usage, ensure_ascii=False),
                            utc_now_iso(),
                            item_id,
                            latest_revision,
                        ),
                    )
                refreshed = library_row(item_id)
                if refreshed is None:
                    raise LookupError("データが見つかりません。")
                result = library_public(refreshed)
            result["speaker_identity"] = {
                "provider": provider,
                "model": model,
                "detected_count": len(detected_names),
                "applied_count": len(applied_names),
                "applied_names": applied_names,
                "ambiguous_labels": diagnostics.get("ambiguous_labels", {}),
                "duplicate_names": diagnostics.get("duplicate_names", {}),
                "repairs": repair_summary,
            }
            return jsonify(result)
    except TranscriptConflictError as exc:
        return jsonify({
            "error": str(exc),
            "conflict": True,
            "current_revision": exc.current_revision,
        }), 409
    except (LookupError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        return jsonify({"error": f"話者名を保存できません: {exc}"}), 500


@app.get("/api/library/<item_id>/analysis")
def get_library_analysis(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "処理済みデータが見つかりません。"}), 404
    try:
        return jsonify(group_analysis_for_row(row))
    except (ValueError, TypeError, OverflowError, sqlite3.Error):
        return jsonify({"error": "分析データを生成できません。元データを確認してください。"}), 500


@app.put("/api/library/<item_id>/analysis")
def update_library_analysis(item_id: str):
    if request.content_length and request.content_length > 16 * 1024 * 1024:
        return jsonify({"error": "分析設定が大きすぎます。"}), 413
    try:
        return jsonify(save_group_analysis(item_id, request.get_json(silent=True)))
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except AnalysisConflictError as exc:
        return jsonify({"error": str(exc), "conflict": True}), 409
    except sqlite3.Error:
        return jsonify({"error": "分析設定を保存できません。"}), 500


@app.get("/api/library/<item_id>/analysis/export.json")
def export_library_analysis_json(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "処理済みデータが見つかりません。"}), 404
    try:
        analysis = group_analysis_for_row(row, include_research_rows=True)
        content = json.dumps(
            analysis,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, OverflowError, sqlite3.Error):
        return jsonify({"error": "分析データを出力できません。元データを確認してください。"}), 500
    return send_file(
        io.BytesIO(content),
        mimetype="application/json; charset=utf-8",
        as_attachment=True,
        download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_analysis.json",
    )


@app.get("/api/library/<item_id>/analysis/export.xlsx")
def export_library_analysis_xlsx(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "処理済みデータが見つかりません。"}), 404
    try:
        analysis = group_analysis_for_row(row, include_research_rows=True)
        datasets = {
            dataset: analysis_csv_rows(analysis, dataset)
            for dataset in ANALYSIS_CSV_FIELDS
        }
        content = build_analysis_workbook(analysis, datasets)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, OverflowError, sqlite3.Error):
        return jsonify({"error": "Excel分析データを出力できません。元データを確認してください。"}), 500
    return send_file(
        io.BytesIO(content),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=(
            f"{safe_output_stem(str(row['source_name']))[:64]}_研究分析.xlsx"
        ),
    )


@app.get("/api/library/<item_id>/analysis/export.csv")
def export_library_analysis_csv(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "処理済みデータが見つかりません。"}), 404
    dataset = request.args.get("dataset", "speakers").strip().lower()
    try:
        analysis = group_analysis_for_row(row, include_research_rows=True)
        content = analysis_csv_content(analysis, dataset)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (TypeError, OverflowError, sqlite3.Error):
        return jsonify({"error": "分析データを出力できません。元データを確認してください。"}), 500
    return send_file(
        io.BytesIO(content),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=(
            f"{safe_output_stem(str(row['source_name']))[:64]}_analysis_{dataset}.csv"
        ),
    )


@app.get("/api/library/<item_id>/speakers.csv")
def export_conversation_speakers(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    segments = row_segments(row)
    raw_names = json_load(row["speaker_names_json"], {})
    speaker_names = raw_names if isinstance(raw_names, dict) else {}
    profiles = row_speaker_profiles(row, segments, speaker_names)
    session = row_session_profile(row)
    registry = {item["id"]: item for item in list_speaker_registry()}
    metrics: dict[str, dict[str, float | int]] = {}
    for segment in segments:
        label = str(segment.get("speaker") or "UNKNOWN")
        start, end = segment_bounds(segment)
        data = metrics.setdefault(label, {"count": 0, "seconds": 0.0, "characters": 0})
        data["count"] = int(data["count"]) + 1
        data["seconds"] = float(data["seconds"]) + max(0.0, end - start)
        data["characters"] = int(data["characters"]) + len(str(segment.get("text") or ""))
    custom_headers = sorted({
        key
        for profile in profiles.values()
        for key in (
            registry.get(profile.get("global_speaker_id"), {}).get("attributes", {}) or {}
        )
    })
    fixed_headers = [
        "会話ID", "データ名", "会話種別", "実施日", "場所", "目的",
        "話者ラベル", "表示名", "グローバル話者ID", "参加者コード",
        "テーマカラー", "会話役割", "組織", "部署", "役職", "参加状態",
        "会話固有条件", "メモ", "発話数", "発話秒数", "文字数",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
    writer.writerow({header: analysis_csv_safe(header) for header in fixed_headers + custom_headers})
    for label, profile in profiles.items():
        global_record = registry.get(profile.get("global_speaker_id"), {})
        metric = metrics.get(label, {"count": 0, "seconds": 0.0, "characters": 0})
        export_row = {
            "会話ID": row["id"],
            "データ名": row["source_name"],
            "会話種別": session["session_type"],
            "実施日": session["session_date"],
            "場所": session["location"],
            "目的": session["objective"],
            "話者ラベル": label,
            "表示名": profile["display_name"] or speaker_names.get(label, ""),
            "グローバル話者ID": profile["global_speaker_id"],
            "参加者コード": global_record.get("participant_code", ""),
            "テーマカラー": profile["theme_color"],
            "会話役割": profile["session_role"],
            "組織": profile["organization"],
            "部署": profile["department"],
            "役職": profile["job_title"],
            "参加状態": profile["attendance_status"],
            "会話固有条件": profile["conditions"],
            "メモ": profile["notes"],
            "発話数": metric["count"],
            "発話秒数": round(float(metric["seconds"]), 3),
            "文字数": metric["characters"],
            **(global_record.get("attributes", {}) or {}),
        }
        writer.writerow({key: analysis_csv_safe(value) for key, value in export_row.items()})
    content = ("\ufeff" + stream.getvalue()).encode("utf-8")
    return send_file(
        io.BytesIO(content),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_speakers.csv",
    )


@app.get("/api/library/<item_id>/thumbnail")
def library_thumbnail(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    try:
        thumbnail_path = generate_word_cloud_thumbnail(
            item_id,
            str(row["source_name"]),
            row_segments(row),
        )
        return send_file(
            thumbnail_path,
            mimetype="image/svg+xml",
            conditional=True,
            max_age=86400,
        )
    except OSError as exc:
        return jsonify({"error": f"ワードクラウドを作成できません: {exc}"}), 500


@app.put("/api/library/<item_id>")
def update_library_item_route(item_id: str):
    try:
        return jsonify(update_library_from_payload(item_id, request.get_json(silent=True)))
    except TranscriptConflictError as exc:
        return jsonify({
            "error": str(exc),
            "conflict": True,
            "current_revision": exc.current_revision,
        }), 409
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        return jsonify({"error": f"保存できません: {exc}"}), 500


@app.delete("/api/library/<item_id>")
def delete_library_item(item_id: str):
    with library_write_lock:
        return _delete_library_item_locked(item_id)


def _delete_library_item_locked(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "Data not found."}), 404
    with jobs_lock:
        job = jobs.get(item_id)
        if job and job.status in ACTIVE_JOB_STATUSES:
            return jsonify({"error": "An active job cannot be deleted."}), 409

    edit_recovery_errors, edit_recovery_paths = (
        reconcile_edit_transactions_before_delete(item_id, row)
    )
    if edit_recovery_errors:
        visible_paths = (
            [str(path) for path in edit_recovery_paths]
            if local_path_access_allowed()
            else [path.name for path in edit_recovery_paths]
        )
        return jsonify({
            'error': (
                '保留中の編集トランザクションを安全に完了できないため、'
                '削除を中止しました。アプリを再起動して復旧してください。'
            ),
            'recovery_paths': visible_paths,
        }), 409
    row = library_row(item_id)
    if row is None:
        return jsonify({'error': 'Data not found.'}), 404

    nonce = uuid.uuid4().hex
    candidates: list[Path] = []
    media_dir = (MEDIA_DIRECTORY / item_id).resolve()
    media_root = MEDIA_DIRECTORY.resolve()
    if media_dir.parent == media_root and media_dir.is_dir():
        candidates.append(media_dir)
    for thumbnail_name in (f"text_mining_{item_id}.svg", f"word_cloud_{item_id}.svg"):
        thumbnail = THUMBNAIL_DIRECTORY / thumbnail_name
        if thumbnail.is_file() or thumbnail.is_symlink():
            candidates.append(thumbnail)

    moved: list[tuple[Path, Path]] = []
    quarantine_roots: set[Path] = set()

    def restore_assets() -> list[str]:
        errors: list[str] = []
        for quarantined, original in reversed(moved):
            try:
                if quarantined.exists() or quarantined.is_symlink():
                    original.parent.mkdir(parents=True, exist_ok=True)
                    durable_move(quarantined, original, replace_existing=False)
            except OSError as exc:
                errors.append(str(exc))
        return errors

    def cleanup_empty_quarantine_roots() -> None:
        for quarantine_root in quarantine_roots:
            try:
                quarantine_root.rmdir()
            except OSError:
                # A non-empty directory contains an asset that could not be
                # restored.  Retain it for manual recovery.
                pass

    def retained_quarantine_paths() -> list[str]:
        retained = sorted(path for path in quarantine_roots if path.exists())
        if local_path_access_allowed():
            return [str(path) for path in retained]
        return [path.name for path in retained]

    try:
        for original in candidates:
            quarantine_root = original.parent / f".delete-staging-{nonce}"
            quarantine_root.mkdir(parents=True, exist_ok=True)
            quarantine_roots.add(quarantine_root)
            quarantined = quarantine_root / original.name
            durable_move(original, quarantined, replace_existing=False)
            moved.append((quarantined, original))
    except OSError as exc:
        restore_errors = restore_assets()
        cleanup_empty_quarantine_roots()
        retained = retained_quarantine_paths()
        return jsonify({
            "error": f"削除準備に失敗しました: {exc}",
            "restore_errors": restore_errors,
            "recovery_paths": retained,
        }), 409

    try:
        with database_connection() as connection:
            files = json_load(row["files_json"], [])
            output_json_paths: set[Path] = set()
            expected_current_json = Path(str(row["output_dir"])) / (
                f"{safe_output_stem(str(row['source_name']))}_話者分離.json"
            )
            expected_current_canonical = canonical_output_import_path(
                expected_current_json
            )
            if isinstance(files, list):
                output_json_paths.update(
                    Path(str(value))
                    for value in files
                    if (
                        Path(str(value)).name.endswith("_話者分離.json")
                        and canonical_output_import_path(Path(str(value)))
                        == expected_current_canonical
                    )
                )
            provenance_rows = connection.execute(
                "SELECT canonical_path, content_sha256 "
                "FROM output_import_provenance WHERE item_id = ?",
                (item_id,),
            ).fetchall()
            provenance_fingerprints = {
                str(provenance["canonical_path"]): str(
                    provenance["content_sha256"] or ""
                )
                for provenance in provenance_rows
            }
            output_json_paths.update(
                Path(canonical_path)
                for canonical_path in provenance_fingerprints
            )
            tombstone_records: list[tuple[str, str]] = []
            for output_path in output_json_paths:
                canonical_path = canonical_output_import_path(output_path)
                is_provenance = canonical_path in provenance_fingerprints
                if (
                    not is_provenance
                    and not path_is_within(output_path, DEFAULT_OUTPUT_DIRECTORY)
                ):
                    continue
                provenance_fingerprint = provenance_fingerprints.get(
                    canonical_path, ""
                )
                if output_path.is_file():
                    try:
                        fingerprint = file_sha256(output_path)
                    except OSError:
                        fingerprint = provenance_fingerprint if is_provenance else ""
                else:
                    fingerprint = provenance_fingerprint if is_provenance else ""
                tombstone_records.append((canonical_path, fingerprint))
            for canonical_path, fingerprint in tombstone_records:
                connection.execute(
                    "INSERT OR REPLACE INTO output_import_tombstones "
                    "(canonical_path, content_sha256, deleted_at) VALUES (?, ?, ?)",
                    (canonical_path, fingerprint, utc_now_iso()),
                )
            connection.execute(
                "DELETE FROM output_import_provenance WHERE item_id = ?",
                (item_id,),
            )
            connection.execute("DELETE FROM library_items WHERE id = ?", (item_id,))
    except sqlite3.Error as exc:
        restore_errors = restore_assets()
        cleanup_empty_quarantine_roots()
        retained = retained_quarantine_paths()
        suffix = f"; restore errors: {'; '.join(restore_errors)}" if restore_errors else ""
        return jsonify({
            "error": f"ライブラリレコードを削除できませんでした: {exc}{suffix}",
            "restore_errors": restore_errors,
            "recovery_paths": retained,
        }), 500

    with jobs_lock:
        jobs.pop(item_id, None)
    cleanup_errors: list[str] = []
    for quarantine_root in quarantine_roots:
        try:
            shutil.rmtree(quarantine_root)
        except OSError as exc:
            cleanup_errors.append(str(exc))
    retained = retained_quarantine_paths()
    result: dict[str, Any] = {
        "ok": True,
        "message": "ライブラリ項目と管理対象メディアを削除しました。出力と学習履歴は保持しています。",
        "recovery_paths": retained,
    }
    if cleanup_errors or retained:
        result["cleanup_warning"] = (
            "ライブラリ項目は削除しましたが、一部の隔離ファイルを消去できませんでした。"
            "表示された場所を管理者が確認してください。"
        )
        result["cleanup_errors"] = cleanup_errors
    return jsonify(result)

@app.get("/api/library/<item_id>/media")
def stream_library_media(item_id: str):
    row = library_row(item_id)
    if row is None or not row["media_path"]:
        return jsonify({"error": "元の音声・動画が保存されていません。"}), 404
    media_path = Path(row["media_path"])
    expected_media_dir = MEDIA_DIRECTORY / item_id
    if not path_is_within(media_path, expected_media_dir) or not media_path.is_file():
        return jsonify({"error": "元の音声・動画が見つかりません。"}), 404
    return send_file(media_path, conditional=True, mimetype=mimetypes.guess_type(media_path.name)[0])


@app.get("/api/library/<item_id>/files/<path:filename>")
def download_library_file(item_id: str, filename: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    paths = [Path(value) for value in json_load(row["files_json"], []) if isinstance(value, str)]
    output_root = Path(row["output_dir"])
    matching = next(
        (
            path for path in paths
            if path.name == filename and path_is_within(path, output_root)
        ),
        None,
    )
    if matching is None or not matching.is_file():
        return jsonify({"error": "出力ファイルが見つかりません。"}), 404
    return send_file(matching, as_attachment=True, download_name=matching.name)


@app.get("/api/training")
def training_status():
    try:
        with database_connection() as connection:
            events = training_events_from_connection(connection)
    except (OSError, sqlite3.Error):
        app.logger.exception("Could not read canonical training events")
        return jsonify({"error": "学習履歴を読み取れません。"}), 500
    event_count = len(events)
    ready_count = sum(int(bool(event.get("ready_for_kushinada"))) for event in events)
    downloads_allowed = not REMOTE_ACCESS_ENABLED
    return jsonify({
        "event_count": event_count,
        "ready_count": ready_count,
        "jsonl_url": (
            "/api/training/corrections.jsonl"
            if downloads_allowed and event_count > 0
            else None
        ),
        "manifest_url": (
            "/api/training/manifest.csv"
            if downloads_allowed and event_count > 0
            else None
        ),
    })


@app.get("/api/training/corrections.jsonl")
def download_training_jsonl():
    if REMOTE_ACCESS_ENABLED:
        return jsonify({"error": "Raw training data downloads are disabled for remote access."}), 403
    try:
        events = refresh_training_exports()
    except (OSError, sqlite3.Error) as exc:
        return jsonify({"error": f"学習データを生成できません: {exc}"}), 500
    if not events:
        return jsonify({"error": "学習データはまだありません。"}), 404
    jsonl_content, _manifest_content = training_export_contents(events)
    return send_file(
        io.BytesIO(jsonl_content.encode("utf-8")),
        mimetype="application/x-ndjson; charset=utf-8",
        as_attachment=True,
        download_name="kushinada_corrections.jsonl",
    )


@app.get("/api/training/manifest.csv")
def download_training_manifest():
    if REMOTE_ACCESS_ENABLED:
        return jsonify({"error": "Raw training data downloads are disabled for remote access."}), 403
    try:
        events = refresh_training_exports()
    except (OSError, sqlite3.Error) as exc:
        return jsonify({"error": f"学習データを生成できません: {exc}"}), 500
    if not events:
        return jsonify({"error": "学習データはまだありません。"}), 404
    _jsonl_content, manifest_content = training_export_contents(events)
    return send_file(
        io.BytesIO(("\ufeff" + manifest_content).encode("utf-8")),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="kushinada_manifest.csv",
    )


@app.post("/api/jobs")
def create_job():
    upload_dir: Path | None = None
    reserved_output_dir: Path | None = None
    registered_job_id: str | None = None
    try:
        with jobs_lock:
            if any(job.status in ACTIVE_JOB_STATUSES for job in jobs.values()):
                return jsonify({"error": "別の文字起こしを処理中です。完了または中止までお待ちください。"}), 409
        upload = request.files.get("input_file")
        source_path_raw = request.form.get("source_path", "").strip().strip('"')
        direct_input_path: Path | None = None
        if source_path_raw:
            if not local_path_access_allowed():
                raise ValueError("Direct local paths are disabled for remote access; upload the media instead.")
            direct_input_path = resolve_local_media_path(source_path_raw)
            original_name = direct_input_path.name
        elif upload is not None and upload.filename:
            original_name = Path(upload.filename).name
        else:
            return jsonify({"error": "処理する音声・動画ファイルを選択してください。"}), 400
        original_name = normalize_source_name(original_name)
        if Path(original_name).suffix.lower() not in ALLOWED_EXTENSIONS:
            return jsonify({"error": "対応形式は MP4/MOV/MKV/WAV/MP3/M4A/FLAC です。"}), 400

        model_name = request.form.get("model_name", "base")
        if model_name not in MODEL_NAMES:
            raise ValueError("認識モデルが不正です。")
        language_raw = request.form.get("language", "ja").strip()
        language = language_raw or None
        if language not in LANGUAGES:
            raise ValueError("言語が不正です。")
        audio_preprocess = parse_audio_preprocess()
        device = request.form.get("device", "cuda")
        diarization_device = request.form.get("diarization_device", "cpu")
        if device not in {"cpu", "cuda"} or diarization_device not in {"cpu", "cuda"}:
            raise ValueError("処理装置の指定が不正です。")
        machine = get_machine_profile()
        if (device == "cuda" or diarization_device == "cuda") and not machine["gpu"]["cuda_available"]:
            raise ValueError(
                "このマシンではGPU (CUDA)を利用できません。"
                "文字起こし装置と話者分離装置をCPUに設定してください。"
            )
        min_speakers = parse_optional_int("min_speakers")
        max_speakers = parse_optional_int("max_speakers")
        if min_speakers and max_speakers and min_speakers > max_speakers:
            raise ValueError("最少話者数は最多話者数以下にしてください。")
        triple_pass = parse_bool("triple_pass")
        boost_quiet_speech = parse_bool("boost_quiet_speech", default=True)
        if boost_quiet_speech or triple_pass:
            vad_onset = parse_optional_float("vad_onset", 0.35, 0.05, 0.95)
            vad_offset = parse_optional_float("vad_offset", 0.25, 0.05, 0.95)
            if vad_offset > vad_onset:
                raise ValueError("VAD offset は onset 以下にしてください。")
            # Keep quiet speech discoverable without accepting nearly silent
            # hallucinations, which often duplicate or tear adjacent turns.
            no_speech_threshold = 0.8
        else:
            vad_onset = 0.5
            vad_offset = 0.363
            no_speech_threshold = 0.6

        provider = request.form.get("ai_provider", "none")
        if provider not in AI_PROVIDERS:
            raise ValueError("AI プロバイダーが不正です。")
        clean_transcript = parse_bool("clean_transcript")
        detect_names = parse_bool("detect_speaker_names")
        create_outline = parse_bool("create_outline")
        if provider == "none":
            clean_transcript = False
            detect_names = False
            create_outline = False
        emotion_analysis = parse_bool("emotion_analysis")
        emotion_model = request.form.get("emotion_model", "kushinada").strip() or "kushinada"
        if emotion_model not in AIST_EMOTION_MODEL_CHOICES:
            raise ValueError("感情分析モデルの指定が不正です。")
        token_config = load_token_config()
        if not token_config.huggingface_token:
            raise ValueError("tokens.json に huggingface_token を設定してください。")
        ai_api_key = ""
        ai_model = ""
        if clean_transcript or detect_names or create_outline:
            if provider == "openai":
                ai_api_key, ai_model = token_config.openai_api_key, token_config.openai_model
            else:
                ai_api_key, ai_model = token_config.google_api_key, token_config.google_model
            if not ai_api_key:
                raise ValueError(f"tokens.json に {provider} の API キーを設定してください。")

        output_raw = request.form.get("output_dir", "").strip().strip('"')
        if output_raw and not local_path_access_allowed():
            raise ValueError("Custom output paths are disabled for remote access.")
        output_root = prepare_output_root(output_raw)

        job_id = str(getattr(g, "job_admission_id", "") or uuid.uuid4().hex)
        output_dir = job_output_directory(output_root, original_name, job_id)
        output_dir.mkdir(exist_ok=False)
        reserved_output_dir = output_dir
        upload_dir = UPLOAD_DIRECTORY / job_id
        UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        upload_dir.mkdir(parents=True, exist_ok=False)
        safe_name = safe_media_filename(original_name, fallback_stem="input")
        input_path = upload_dir / safe_name
        try:
            if direct_input_path is not None:
                copy_file_limited(direct_input_path, input_path, MAX_MEDIA_UPLOAD_BYTES)
            else:
                assert upload is not None
                save_upload_limited(upload, input_path, MAX_MEDIA_UPLOAD_BYTES)
            if not input_path.is_file() or input_path.stat().st_size == 0:
                raise ValueError("アップロードされたファイルが空です。")
        except Exception:
            shutil.rmtree(upload_dir, ignore_errors=True)
            raise

        options = JobOptions(
            input_path=input_path,
            work_dir=upload_dir,
            source_name=original_name,
            output_dir=output_dir,
            model_name=model_name,
            language=language,
            hf_token=token_config.huggingface_token,
            audio_preprocess=audio_preprocess,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            device=device,
            diarization_device=diarization_device,
            triple_pass=triple_pass,
            boost_quiet_speech=boost_quiet_speech,
            vad_onset=vad_onset,
            vad_offset=vad_offset,
            no_speech_threshold=no_speech_threshold,
            write_srt=parse_bool("write_srt"),
            write_json=True,
            burn_subtitled_video=parse_bool("burn_subtitled_video"),
            ai_provider=provider,
            clean_transcript=clean_transcript,
            detect_speaker_names=detect_names,
            create_outline=create_outline,
            emotion_analysis=emotion_analysis,
            emotion_model=emotion_model,
            ai_api_key=ai_api_key,
            ai_model=ai_model,
            owns_output_dir=True,
        )
        job = JobRecord(
            id=job_id,
            source_name=original_name,
            output_dir=output_dir,
            write_srt=options.write_srt,
            write_json=True,
            burn_subtitled_video=options.burn_subtitled_video,
        )
        with jobs_lock:
            jobs[job_id] = job
            registered_job_id = job_id
        thread = threading.Thread(
            target=run_transcription_job,
            args=(job, options),
            name=f"transcription-{job_id[:8]}",
            daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            with jobs_lock:
                jobs.pop(job_id, None)
                registered_job_id = None
            shutil.rmtree(upload_dir, ignore_errors=True)
            if reserved_output_dir is not None:
                remove_owned_directory(reserved_output_dir, ignore_errors=True)
            raise RuntimeError(f"Could not start the transcription worker: {exc}") from exc
        return jsonify(job.public()), 202
    except RequestEntityTooLarge:
        if registered_job_id:
            with jobs_lock:
                jobs.pop(registered_job_id, None)
        if upload_dir is not None:
            shutil.rmtree(upload_dir, ignore_errors=True)
        if reserved_output_dir is not None:
            remove_owned_directory(reserved_output_dir, ignore_errors=True)
        raise
    except ValueError as exc:
        if registered_job_id:
            with jobs_lock:
                jobs.pop(registered_job_id, None)
        if upload_dir is not None:
            shutil.rmtree(upload_dir, ignore_errors=True)
        if reserved_output_dir is not None:
            remove_owned_directory(reserved_output_dir, ignore_errors=True)
        return jsonify({"error": str(exc)}), 400
    except (RuntimeError, OSError) as exc:
        if registered_job_id:
            with jobs_lock:
                jobs.pop(registered_job_id, None)
        if upload_dir is not None:
            shutil.rmtree(upload_dir, ignore_errors=True)
        if reserved_output_dir is not None:
            remove_owned_directory(reserved_output_dir, ignore_errors=True)
        return jsonify({"error": str(exc)}), 500


def admission_job_public(job_id: str) -> dict[str, Any]:
    return {
        "id": job_id,
        "source_name": "",
        "output_dir": "",
        "status": "admitting",
        "progress": 0,
        "stage": "admitting",
        "stage_label": "送信データの受付",
        "stage_progress": 0,
        "message": "送信データを受け付けています…",
        "logs": [],
        "segments": [],
        "speaker_names": {},
        "session_profile": {},
        "speaker_profiles": {},
        "write_srt": False,
        "write_json": True,
        "burn_subtitled_video": False,
        "outline": None,
        "emotion_analysis": None,
        "media_url": None,
        "media_kind": None,
        "files": [],
        "error": "",
        "output_warning": "",
        "revision_count": 0,
    }


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with jobs_lock:
        prune_jobs_locked()
        job = jobs.get(job_id)
        admitting = job is None and _job_admission_id == job_id
    if job is None:
        if admitting:
            return jsonify(admission_job_public(job_id)), 202
        return jsonify({"error": "ジョブが見つかりません。"}), 404
    return jsonify(job.public())


@app.get("/api/jobs/active")
def get_active_job():
    with jobs_lock:
        prune_jobs_locked()
        active = [job for job in jobs.values() if job.status in ACTIVE_JOB_STATUSES]
        job = max(active, key=lambda value: value.created_at) if active else None
        admitting_id = _job_admission_id if job is None else None
    public_job = (
        job.public()
        if job is not None
        else admission_job_public(admitting_id) if admitting_id else None
    )
    return jsonify({"job": public_job})


@app.post("/api/jobs/<job_id>/cancel")
def cancel_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": "ジョブが見つかりません。"}), 404
        if job.status not in {"queued", "running"}:
            return jsonify({"error": "このジョブは既に終了しています。"}), 409
        job.cancel_event.set()
    update_job(job, message="中止を要求しました。現在の処理区切りで停止します…")
    return jsonify({"ok": True})


@app.put("/api/jobs/<job_id>/transcript")
def save_transcript(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        return jsonify({"error": "ジョブが見つかりません。"}), 404
    if job.status != "completed":
        return jsonify({"error": "完了したジョブだけを編集できます。"}), 409
    try:
        result = update_library_from_payload(job_id, request.get_json(silent=True))
        update_job(job, message="手動編集を保存し、修正差分を学習データへ蓄積しました。")
        return jsonify(result)
    except TranscriptConflictError as exc:
        return jsonify({
            "error": str(exc),
            "conflict": True,
            "current_revision": exc.current_revision,
        }), 409
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        return jsonify({"error": f"ファイルを保存できません: {exc}"}), 500


@app.get("/api/jobs/<job_id>/files/<path:filename>")
def download_file(job_id: str, filename: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": "ジョブが見つかりません。"}), 404
        matching = next(
            (
                path for path in job.files
                if path.name == filename and path_is_within(path, job.output_dir)
            ),
            None,
        )
    if matching is None or not matching.is_file():
        return jsonify({"error": "出力ファイルが見つかりません。"}), 404
    return send_file(matching, as_attachment=True, download_name=matching.name)


def main() -> int:
    host = os.environ.get("MOJIOKOSI_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.environ.get("MOJIOKOSI_PORT", "7860"))
    except ValueError:
        print("MOJIOKOSI_PORT must be an integer.", file=sys.stderr)
        return 2
    if not 1 <= port <= 65535:
        print("MOJIOKOSI_PORT must be between 1 and 65535.", file=sys.stderr)
        return 2
    if not bind_host_is_loopback(host) and not REMOTE_ACCESS_ENABLED:
        print(
            "Refusing a non-loopback bind. Set MOJIOKOSI_ALLOW_REMOTE=1 and configure authentication explicitly.",
            file=sys.stderr,
        )
        return 2
    if REMOTE_ACCESS_ENABLED and len(REMOTE_ACCESS_TOKEN) < 20:
        print(
            "MOJIOKOSI_ACCESS_TOKEN must contain at least 20 characters when remote access is enabled.",
            file=sys.stderr,
        )
        return 2
    try:
        prepare_output_root("")
        initialize_application()
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Application initialization failed: {exc}", file=sys.stderr)
        return 2
    try:
        return _run_initialized_application(host, port)
    finally:
        release_instance_lock()


def _run_initialized_application(host: str, port: int) -> int:
    url = f"http://{host}:{port}"
    machine = get_machine_profile()
    recommendation = machine["recommended"]
    cpu = machine["cpu"]
    gpu = machine["gpu"]
    print(f"{APP_NAME}: {url}")
    print(
        f"CPU利用可: {cpu['name']} / {cpu['logical_threads']} threads / "
        f"RAM {machine['memory_gib']:.1f} GB"
    )
    if gpu["cuda_available"]:
        print(
            f"GPU利用可: {gpu['name']} / VRAM {gpu['vram_gib']:.1f} GB / "
            f"CUDA {gpu['cuda_version']} / Compute Capability {gpu['capability']}"
        )
    else:
        print(f"GPU利用不可: {gpu['reason']}")
    print(
        "推奨設定: "
        f"model={recommendation['model_name']} / "
        f"transcription={recommendation['device']} / "
        f"diarization={recommendation['diarization_device']}"
    )
    print("終了するにはこのウィンドウで Ctrl+C を押してください。")
    if os.environ.get("MOJIOKOSI_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, threaded=True, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
