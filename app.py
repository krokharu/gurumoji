"""Local Web UI for speaker-diarized transcription.

The browser UI is intentionally bound to 127.0.0.1. Heavy speech-recognition
libraries are imported only inside the background worker so the UI can start
even while the Python environment is being diagnosed.
"""

from __future__ import annotations

import gc
import csv
import html
import io
import inspect
import json
import mimetypes
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
import warnings
import webbrowser
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename


os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings(
    "ignore",
    message=r"\s*torchcodec is not installed correctly.*",
    category=UserWarning,
)

PRODUCT_NAME = "グルモジ"
APP_VERSION = "1.3.0"
APP_CREATOR = "クロカワ"
APP_NAME = f"{PRODUCT_NAME} | 話者分離文字起こし"
APP_DIRECTORY = Path(__file__).resolve().parent
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
TOKEN_FILE = APP_DIRECTORY / "tokens.json"
DIARIZATION_MODEL = os.environ.get(
    "MOJIOKOSI_DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1"
)
DIARIZATION_ACCESS_REPOS = (
    DIARIZATION_MODEL,
    "pyannote/segmentation-3.0",
    "pyannote/speaker-diarization-community-1",
)
ALLOWED_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".wav", ".mp3", ".m4a", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv"}
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
QUIET_SUPPLEMENT_MAX_NO_SPEECH_PROB = 0.95
QUIET_SUPPLEMENT_MIN_AVG_LOGPROB = -1.35
QUIET_SUPPLEMENT_MAX_COMPRESSION_RATIO = 3.2
TRIPLE_PASS_MIN_GAP_SECONDS = 3.0
TRIPLE_PASS_GAP_CONTEXT_SECONDS = 0.75
WHISPER_SAMPLE_RATE = 16000
SESSION_TYPES = {"focus_group", "meeting", "interview", "workshop", "other"}
SPEAKER_ROLES = {
    "participant", "moderator", "facilitator", "assistant_moderator", "observer",
    "note_taker", "interviewer", "chair", "presenter", "decision_maker",
    "attendee", "guest", "other",
}
CONSENT_STATUSES = {"unknown", "pending", "granted", "declined", "not_required"}
ATTENDANCE_STATUSES = {"unknown", "planned", "attended", "absent", "left_early", "remote"}

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_AS_ASCII"] = False
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def disable_development_cache(response):
    if request.path == "/" or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@dataclass(frozen=True)
class TokenConfig:
    huggingface_token: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    openai_model: str = "gpt-5.6-luna"
    google_model: str = "gemini-3.5-flash"

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
    message: str = "開始を待っています…"
    logs: list[str] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    speaker_names: dict[str, str] = field(default_factory=dict)
    session_profile: dict[str, Any] = field(default_factory=dict)
    speaker_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    outline: dict[str, Any] | None = None
    emotion_analysis: dict[str, Any] | None = None
    media_path: Path | None = None
    files: list[Path] = field(default_factory=list)
    language: str | None = None
    error: str = ""
    output_warning: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        with jobs_lock:
            return {
                "id": self.id,
                "source_name": self.source_name,
                "output_dir": str(self.output_dir),
                "status": self.status,
                "progress": self.progress,
                "message": self.message,
                "logs": list(self.logs),
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
                "media_url": f"/api/library/{self.id}/media" if self.status == "completed" and self.media_path else None,
                "media_kind": media_kind(self.media_path) if self.status == "completed" and self.media_path else None,
                "files": [
                    {
                        "name": path.name,
                        "url": f"/api/jobs/{self.id}/files/{urllib.parse.quote(path.name)}",
                    }
                    for path in self.files
                ],
                "error": self.error,
                "output_warning": self.output_warning,
            }


jobs: dict[str, JobRecord] = {}
jobs_lock = threading.RLock()
training_lock = threading.Lock()
file_dialog_lock = threading.Lock()
machine_profile_lock = threading.Lock()
machine_profile_cache: dict[str, Any] | None = None


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


def media_kind(path: Path | None) -> str | None:
    if path is None:
        return None
    mime = mimetypes.guess_type(path.name)[0] or ""
    return "video" if mime.startswith("video/") or path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv"} else "audio"


def is_colab_runtime() -> bool:
    return (
        os.environ.get("MOJIOKOSI_RUNTIME", "").strip().casefold() == "colab"
        or "COLAB_RELEASE_TAG" in os.environ
    )


def runtime_info() -> dict[str, Any]:
    colab = is_colab_runtime()
    native_file_dialog = platform.system() == "Windows" and not colab
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
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_library() -> None:
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
                files_json TEXT NOT NULL,
                write_srt INTEGER NOT NULL DEFAULT 1,
                write_json INTEGER NOT NULL DEFAULT 1,
                burn_subtitled_video INTEGER NOT NULL DEFAULT 0,
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
        if "burn_subtitled_video" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN burn_subtitled_video INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute("UPDATE library_items SET write_json = 1 WHERE write_json <> 1")
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


def list_speaker_registry(*, include_inactive: bool = True) -> list[dict[str, Any]]:
    query = "SELECT * FROM speaker_registry"
    if not include_inactive:
        query += " WHERE active = 1"
    query += " ORDER BY active DESC, pseudonym, display_name, participant_code, updated_at DESC"
    with database_connection() as connection:
        rows = connection.execute(query).fetchall()
    return [speaker_registry_public(row) for row in rows]


def save_speaker_registry_records(
    raw_records: Any,
    *,
    delete_ids: Any = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw_records, list) or len(raw_records) > 10000:
        raise ValueError("話者台帳は配列で指定してください。")
    existing_records = {item["id"]: item for item in list_speaker_registry()}
    normalized = [
        normalize_speaker_registry_record(
            raw,
            existing=existing_records.get(str(raw.get("id"))) if isinstance(raw, dict) else None,
        )
        for raw in raw_records
    ]
    requested_delete_ids = {
        clean_single_line(value, 80)
        for value in (delete_ids if isinstance(delete_ids, list) else [])
        if clean_single_line(value, 80)
    }
    now = utc_now_iso()
    with database_connection() as connection:
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
    return list_speaker_registry()


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


def import_speaker_registry_csv(content: bytes) -> tuple[list[dict[str, Any]], int]:
    if len(content) > 10 * 1024 * 1024:
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
    existing = list_speaker_registry()
    by_code = {
        item["participant_code"].casefold(): item
        for item in existing
        if item["participant_code"]
    }
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
        code = clean_single_line(fixed.get("participant_code"), 120).casefold()
        if code and code in by_code:
            fixed["id"] = by_code[code]["id"]
            merged_attributes = {
                **by_code[code].get("attributes", {}),
                **fixed.get("attributes", {}),
            }
            fixed = {**by_code[code], **fixed, "attributes": merged_attributes}
        imported.append(fixed)
    if not imported:
        raise ValueError("取り込める話者行がありませんでした。見出しと値を確認してください。")
    return save_speaker_registry_records(imported), len(imported)


def speaker_registry_csv_bytes(records: list[dict[str, Any]]) -> bytes:
    custom_headers = sorted({
        key
        for record in records
        for key in (record.get("attributes") or {})
    })
    fixed_headers = [
        "参加者コード", "氏名", "仮名", "役割", "組織", "部署", "役職",
        "研究同意", "録音同意", "守秘同意", "タグ", "備考", "有効",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
    writer.writeheader()
    for record in records:
        row = {
            "参加者コード": record["participant_code"],
            "氏名": record["display_name"],
            "仮名": record["pseudonym"],
            "役割": record["default_role"],
            "組織": record["organization"],
            "部署": record["department"],
            "役職": record["job_title"],
            "研究同意": record["consent_status"],
            "録音同意": record["recording_consent"],
            "守秘同意": record["confidentiality_status"],
            "タグ": ",".join(record["tags"]),
            "備考": record["notes"],
            "有効": "1" if record["active"] else "0",
            **record["attributes"],
        }
        writer.writerow(row)
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
    return {
        "session_type": session_type,
        "session_date": clean_single_line(raw.get("session_date"), 40),
        "location": clean_single_line(raw.get("location"), 300),
        "objective": clean_multiline(raw.get("objective"), 10000),
        "moderator_guide": clean_multiline(raw.get("moderator_guide"), 20000),
        "group_conditions": clean_multiline(raw.get("group_conditions"), 10000),
        "confidentiality_notes": clean_multiline(raw.get("confidentiality_notes"), 10000),
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
    result: dict[str, Any] = {
        "id": row["id"],
        "source_name": row["source_name"],
        "output_dir": row["output_dir"],
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
        "media_url": f"/api/library/{row['id']}/media" if media_path and media_path.is_file() else None,
        "media_kind": media_kind(media_path) if media_path and media_path.is_file() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "revision_count": int(row["revision_count"] or 0),
        "match_count": match_count,
        "speaker_data_url": f"/api/library/{row['id']}/speakers.csv",
        "files": [
            {"name": path.name, "url": f"/api/library/{row['id']}/files/{urllib.parse.quote(path.name)}"}
            for path in file_paths if path.is_file()
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
) -> sqlite3.Row:
    now = utc_now_iso()
    segments = ensure_segment_ids(item_id, segments)
    session_profile = normalize_session_profile(session_profile)
    labels = {str(item.get("speaker") or "UNKNOWN") for item in segments}
    speaker_profiles = normalize_conversation_speaker_profiles(
        speaker_profiles,
        labels,
        speaker_names,
    )
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO library_items (
                id, source_name, output_dir, media_path, language, segments_json,
                speaker_names_json, outline_json, emotion_analysis_json, files_json,
                write_srt, write_json, burn_subtitled_video, revision_count, created_at, updated_at,
                session_profile_json, speaker_profiles_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_name=excluded.source_name, output_dir=excluded.output_dir,
                media_path=excluded.media_path, language=excluded.language,
                segments_json=excluded.segments_json, speaker_names_json=excluded.speaker_names_json,
                outline_json=excluded.outline_json, emotion_analysis_json=excluded.emotion_analysis_json,
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
                json.dumps([str(path) for path in files], ensure_ascii=False),
                int(write_srt), 1, int(burn_subtitled_video),
                int(increment_revision), created_at or now, now,
                json.dumps(session_profile, ensure_ascii=False),
                json.dumps(speaker_profiles, ensure_ascii=False),
                int(increment_revision),
            ),
        )
    row = library_row(item_id)
    if row is None:
        raise RuntimeError("ライブラリへ保存できませんでした。")
    return row


def archive_media(item_id: str, source_path: Path) -> Path:
    target_dir = MEDIA_DIRECTORY / item_id
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(source_path.name) or f"media{source_path.suffix.lower()}"
    target = target_dir / safe_name
    shutil.copy2(source_path, target)
    return target


def resolve_local_media_path(raw_path: str) -> Path:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        raise ValueError("処理する音声・動画ファイルを選択してください。")
    try:
        path = Path(os.path.expandvars(raw_path)).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"指定したパスを開けません: {exc}") from exc
    if not path.is_file():
        raise ValueError("指定したパスはファイルではありません。")
    if path.stat().st_size == 0:
        raise ValueError("指定したファイルが空です。")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("対応形式は MP4/MOV/MKV/WAV/MP3/M4A/FLAC です。")
    return path


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


def text_mining_terms(segments: list[dict[str, Any]], limit: int = 18) -> list[tuple[str, int]]:
    """Extract useful frequent terms without requiring a morphological analyzer."""
    text = " ".join(str(item.get("text") or "") for item in segments)
    candidates = re.findall(
        r"[一-龯々〆ヵヶ]{2,}|[ァ-ヴー]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}",
        text,
    )
    counts = Counter(
        token.casefold() if token.isascii() else token
        for token in candidates
        if token.casefold() not in TEXT_MINING_STOP_WORDS
    )
    return counts.most_common(limit)


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
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(word_cloud_svg(source_name, segments), encoding="utf-8")
    return target


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
        target.unlink(missing_ok=True)
        completed = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-ss", seek_at, "-i", str(source_path), "-frames:v", "1",
                "-vf", "scale=640:-2:force_original_aspect_ratio=decrease",
                "-q:v", "3", str(target),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if completed.returncode == 0 and target.is_file() and target.stat().st_size > 0:
            return target
        last_error = completed.stderr.strip()
    target.unlink(missing_ok=True)
    raise RuntimeError(last_error or "動画からサムネイルを作成できませんでした。")


def import_existing_outputs() -> None:
    if not DEFAULT_OUTPUT_DIRECTORY.is_dir():
        return
    with database_connection() as connection:
        known = {row[0] for row in connection.execute("SELECT id FROM library_items")}
    for json_path in DEFAULT_OUTPUT_DIRECTORY.rglob("*_話者分離.json"):
        item_id = uuid.uuid5(uuid.NAMESPACE_URL, str(json_path.resolve())).hex
        if item_id in known:
            continue
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
            segments = payload.get("segments")
            if not isinstance(segments, list):
                continue
            source_name = Path(str(payload.get("source") or json_path.name.replace("_話者分離.json", ""))).name
            stem = json_path.name[:-len("_話者分離.json")]
            files = [path for path in json_path.parent.glob(f"{stem}_*") if path.is_file()]
            created = datetime.fromtimestamp(json_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            upsert_library_item(
                item_id=item_id, source_name=source_name, output_dir=json_path.parent,
                media_path=None, language=payload.get("language"), segments=segments,
                speaker_names=payload.get("speaker_names") if isinstance(payload.get("speaker_names"), dict) else {},
                outline=payload.get("outline") if isinstance(payload.get("outline"), dict) else None,
                emotion_analysis=payload.get("emotion_analysis") if isinstance(payload.get("emotion_analysis"), dict) else None,
                files=files, write_srt=any(path.suffix.lower() == ".srt" for path in files),
                write_json=True, created_at=created,
            )
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
        google_model=clean_secret(raw.get("google_model")) or "gemini-3.5-flash",
    )


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


def audio_preprocess_label(preset: str) -> str:
    return str(AUDIO_PREPROCESS_PRESETS.get(preset, AUDIO_PREPROCESS_PRESETS["standard"])["label"])


def run_audio_preprocess(input_path: Path, output_path: Path, preset: str) -> Path:
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
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
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
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
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
        if min(global_end, gap_end) - max(global_start, gap_start) <= 0.05:
            continue
        item["start"] = global_start
        item["end"] = global_end
        words: list[dict[str, Any]] = []
        for raw_word in raw.get("words") or []:
            word = dict(raw_word)
            if word.get("start") is not None:
                word["start"] = clip_start + float(word["start"])
            if word.get("end") is not None:
                word["end"] = clip_start + float(word["end"])
            words.append(word)
        if words:
            item["words"] = words
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
    if len(candidate_text) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS:
        return False
    candidate_start, candidate_end = segment_bounds(candidate)
    for segment in accepted:
        start, end = segment_bounds(segment)
        if end < candidate_start - window_seconds or start > candidate_end + window_seconds:
            continue
        text = normalize_text_for_merge(str(segment.get("text", "")))
        if len(text) < QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS:
            continue
        if candidate_text in text or text in candidate_text:
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


def make_display_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize and merge adjacent speech chunks from the same speaker."""
    merged: list[dict[str, Any]] = []
    for raw in raw_segments:
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        current = {
            "start": float(raw.get("start", 0)),
            "end": float(raw.get("end", raw.get("start", 0))),
            "speaker": segment_speaker(raw),
            "text": text,
        }
        if (
            merged
            and merged[-1]["speaker"] == current["speaker"]
            and current["start"] - merged[-1]["end"] <= 1.2
        ):
            merged[-1]["end"] = current["end"]
            merged[-1]["text"] += " " + current["text"]
        else:
            merged.append(current)
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
            writer.writerow({
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
            })
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


def write_ass_subtitles(
    target: Path,
    source_name: str,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
) -> Path:
    colors = speaker_theme_color_map(segments, speaker_profiles)
    header = f"""[Script Info]
Title: {ass_escape_text(source_name)}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Yu Gothic UI,48,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,3,1,2,90,90,58,1

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
        body_text = ass_escape_text(item.get("text", ""))
        dialogue = f"{{\\c{color}\\b1}}{name_text}{{\\rDefault}}\\N{body_text}"
        events.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,{ass_escape_text(label)},"
            f"0,0,0,,{dialogue}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(header + "\n".join(events) + ("\n" if events else ""), encoding="utf-8-sig")
    return target


def burn_ass_subtitles_into_video(source_path: Path, ass_path: Path, target: Path) -> Path:
    if not is_video_path(source_path):
        raise ValueError("字幕焼き込み動画は MP4/M4V/MOV/MKV からだけ作成できます。")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("字幕動画の作成に必要な ffmpeg が見つかりません。")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    escaped_ass_name = (
        ass_path.name.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )
    completed = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", str(source_path.resolve()),
            "-vf", f"ass='{escaped_ass_name}'",
            "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-max_muxing_queue_size", "2048",
            target.name,
        ],
        cwd=str(target.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        details = completed.stderr.strip()[-2000:]
        raise RuntimeError("字幕動画を作成できませんでした。" + (f"\n{details}" if details else ""))
    return target


def write_subtitled_video_assets(
    source_path: Path,
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
) -> list[Path]:
    stem = safe_output_stem(source_name)
    ass_path = write_ass_subtitles(
        output_dir / f"{stem}_話者カラー字幕.ass",
        source_name,
        segments,
        speaker_names,
        speaker_profiles,
    )
    video_path = burn_ass_subtitles_into_video(
        source_path,
        ass_path,
        output_dir / f"{stem}_字幕付き.mp4",
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
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_output_stem(source_name)
    written: list[Path] = []

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
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
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
    text_path.write_text("\n".join(lines), encoding="utf-8")
    written.append(text_path)

    word_cloud_path = output_dir / f"{stem}_ワードクラウド.svg"
    write_word_cloud(word_cloud_path, source_name, segments)
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
        srt_path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
        written.append(srt_path)

    if outline:
        outline_path = output_dir / f"{stem}_アウトライン.txt"
        outline_path.write_text(format_outline_text(source_name, outline), encoding="utf-8")
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
        emotion_json_path.write_text(
            json.dumps(emotion_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written.append(emotion_json_path)
        csv_body = emotion_csv_text(segments, speaker_names)
        if csv_body.count("\n") > 1:
            emotion_csv_path = output_dir / f"{stem}_感情分析.csv"
            emotion_csv_path.write_text(csv_body, encoding="utf-8-sig")
            written.append(emotion_csv_path)
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


def ensure_s3prl_importable(runtime_dir: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(runtime_dir.parent) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-c", "import s3prl, torch, torchaudio, yaml"],
        cwd=str(runtime_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
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
    extracted: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        check_cancelled()
        start, end = segment_bounds(segment)
        duration = end - start
        if duration < 0.15:
            continue
        padded_start = max(0.0, start - 0.05)
        padded_duration = duration + (start - padded_start) + 0.05
        output_path = wav_root / f"seg_{index:06d}.wav"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-ss",
            f"{padded_start:.3f}",
            "-t",
            f"{padded_duration:.3f}",
            "-i",
            str(audio_path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
            details = (completed.stderr or completed.stdout or "").strip()[-1000:]
            raise RuntimeError(f"感情分析用の音声切り出しに失敗しました: {details}")
        extracted.append({"index": index, "path": output_path, "stem": output_path.stem})
    if not extracted:
        raise RuntimeError("感情分析できる長さの発話セグメントがありません。")
    return wav_root, extracted


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
    ensure_s3prl_importable(runtime_dir)
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
    timeout_seconds = int(os.environ.get("MOJIOKOSI_EMOTION_TIMEOUT_SECONDS", "3600"))
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
    completed = subprocess.run(
        command,
        cwd=str(runtime_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
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
    return updated_segments, summary


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 240) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:1500]
        raise RuntimeError(f"API が HTTP {exc.code} を返しました: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API に接続できません: {exc.reason}") from exc
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


def call_ai_json(
    provider: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
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
        )
        text = extract_openai_text(response)
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
        )
        text = extract_google_text(response)
    else:
        raise RuntimeError(f"未対応の AI プロバイダーです: {provider}")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI が有効な JSON を返しませんでした。") from exc
    if not isinstance(result, dict):
        raise RuntimeError("AI の出力形式が不正です。")
    return result


def chunk_segments(segments: list[dict[str, Any]], max_items: int = 35, max_chars: int = 12000) -> list[list[tuple[int, dict[str, Any]]]]:
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


def detect_speaker_names_with_ai(
    segments: list[dict[str, Any]], provider: str, api_key: str, model: str
) -> dict[str, str]:
    labels = sorted({str(item["speaker"]) for item in segments if item.get("speaker")})
    if not labels:
        return {}
    early: list[dict[str, Any]] = []
    chars = 0
    for index, item in enumerate(segments):
        if float(item.get("start", 0)) > 300 or len(early) >= 45 or chars >= 10000:
            break
        record = {
            "id": index,
            "speaker": item.get("speaker") or "UNKNOWN",
            "text": item.get("text", ""),
        }
        early.append(record)
        chars += len(str(record["text"]))
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
                    },
                    "required": ["speaker", "name", "evidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["speaker_names"],
        "additionalProperties": False,
    }
    result = call_ai_json(
        provider,
        api_key,
        model,
        (
            "会話冒頭の明示的な自己紹介だけから話者名を抽出してください。"
            "『私は田中です』『○○と申します』のように本人が自分を名乗った場合だけ採用します。"
            "他人から呼ばれた名前、話題に出ただけの名前、会社名、推測は採用しません。"
            "確実な自己紹介がない話者は配列に含めないでください。"
        ),
        "会話冒頭の発話です。\n" + json.dumps(early, ensure_ascii=False),
        "speaker_name_detection",
        schema,
    )
    names: dict[str, str] = {}
    for item in result.get("speaker_names") or []:
        label = str(item.get("speaker", ""))
        name = str(item.get("name", "")).strip().replace("\r", " ").replace("\n", " ")
        if label in labels and name and len(name) <= 80:
            names[label] = name
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


def update_job(job: JobRecord, *, progress: int | None = None, message: str | None = None) -> None:
    with jobs_lock:
        if progress is not None:
            job.progress = max(job.progress, min(100, progress))
        if message is not None:
            job.message = message
            job.logs.append(message)
            job.logs = job.logs[-MAX_LOG_LINES:]


def run_transcription_job(job: JobRecord, options: JobOptions) -> None:
    model: Any = None
    model_a: Any = None

    def status(message: str) -> None:
        update_job(job, message=message)

    def progress(value: int) -> None:
        update_job(job, progress=value)

    def check_cancelled() -> None:
        if job.cancel_event.is_set():
            raise InterruptedError("処理を中止しました。")

    with jobs_lock:
        job.status = "running"
    try:
        progress(2)
        status("処理環境を確認しています…")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg が見つかりません。README の手順でインストールしてください。")
        processing_input_path = options.input_path
        if options.audio_preprocess != "none":
            label = audio_preprocess_label(options.audio_preprocess)
            status(f"文字起こし用に音声を前処理しています（{label}）…")
            processed_path = options.work_dir / "preprocessed.wav"
            processing_input_path = run_audio_preprocess(
                options.input_path,
                processed_path,
                options.audio_preprocess,
            )
            status("前処理済み音声を使用します（16kHz / mono / WAV）。")
        else:
            status("音声前処理は行わず、元ファイルの音声を使用します。")
        check_cancelled()
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
            status(f"{pass_label}: 音声認識モデルを読み込んでいます（{options.model_name} / {backend}）…")
            pass_model = load_asr_model(
                language_hint,
                vad_onset,
                vad_offset,
                no_speech_threshold,
            )
            check_cancelled()

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
                )
            else:
                pass_result = pass_model.transcribe(pass_audio, batch_size=1)
            release_asr_model()
            check_cancelled()
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
                status(f"{pass_label}: {TRIPLE_PASS_MIN_GAP_SECONDS:.0f}秒以上の空白はありません。")
                progress(progress_value)
                return {"segments": [], "language": language_hint}

            total_gap_seconds = sum(end - start for start, end in gaps)
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
                    clip_start = max(0.0, gap_start - TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                    clip_end = min(audio_duration, gap_end + TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                    status(
                        f"{pass_label}: 空白 {index}/{len(gaps)} "
                        f"（{display_time(gap_start)}–{display_time(gap_end)}）を切り出して再文字起こししています…"
                    )
                    clip_path = options.work_dir / f"gap_{preset}_{index:04d}.wav"
                    try:
                        run_audio_interval_preprocess(
                            options.input_path,
                            clip_path,
                            clip_start,
                            clip_end,
                            preset,
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
                status("発話時刻を整えています…")
                model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
                result = whisperx.align(
                    result["segments"], model_a, metadata, audio, device, return_char_alignments=False
                )
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
        progress(64)

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
        progress(80)

        status("話者ラベルを文字起こしに対応付けています…")
        result = whisperx.assign_word_speakers(diarize_segments, result)
        segments = make_display_segments(result.get("segments", []))
        if not segments:
            raise RuntimeError("文字起こし結果が空でした。音声が含まれているか確認してください。")
        check_cancelled()

        if options.clean_transcript:
            segments = clean_segments_with_ai(
                segments,
                options.ai_provider,
                options.ai_api_key,
                options.ai_model,
                status,
                check_cancelled,
            )
        progress(88)
        emotion_analysis: dict[str, Any] | None = None
        if options.emotion_analysis:
            emotion_model_keys = aist_emotion_model_keys(options.emotion_model)
            try:
                segments, emotion_analysis = run_aist_emotion_analysis(
                    processing_input_path,
                    segments,
                    options.emotion_model,
                    options.hf_token,
                    device,
                    options.work_dir / "emotion_work",
                    status,
                    check_cancelled,
                )
                status("AIST感情分析が完了しました。")
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                status("AIST感情分析は失敗しました。文字起こし処理は続行します: " + details)
                emotion_analysis = build_emotion_analysis_summary(
                    segments,
                    emotion_model_keys,
                    status="failed",
                    error=details,
                )
        progress(90)
        speaker_names: dict[str, str] = {}
        if options.detect_speaker_names:
            status("冒頭の自己紹介から話者名を確認しています…")
            speaker_names = detect_speaker_names_with_ai(
                segments, options.ai_provider, options.ai_api_key, options.ai_model
            )
        speaker_profiles = normalize_conversation_speaker_profiles(
            None,
            {str(item.get("speaker") or "UNKNOWN") for item in segments},
            speaker_names,
        )
        progress(94)
        outline: dict[str, Any] | None = None
        if options.create_outline:
            outline = create_outline_with_ai(
                segments,
                speaker_names,
                options.ai_provider,
                options.ai_api_key,
                options.ai_model,
                status,
                check_cancelled,
            )
        progress(97)
        check_cancelled()

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
        )
        if options.burn_subtitled_video:
            if is_video_path(options.input_path):
                status("話者名・テーマカラー付き字幕を動画へ焼き込んでいます…")
                try:
                    files.extend(write_subtitled_video_assets(
                        options.input_path,
                        options.source_name,
                        options.output_dir,
                        segments,
                        speaker_names,
                        speaker_profiles,
                    ))
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                    warning = f"字幕動画の作成を完了できませんでした: {exc}"
                    with jobs_lock:
                        job.output_warning = warning
                    status(warning)
            else:
                status("音声ファイルのため、字幕焼き込み動画の作成は省略しました。")
        status("元の音声・動画をライブラリへ保存しています…")
        saved_media_path = archive_media(job.id, options.input_path)
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
            speaker_profiles=speaker_profiles,
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
        progress(100)
        status(f"完了しました。出力を実行フォルダーへ保存しました: {options.output_dir}")
    except InterruptedError as exc:
        with jobs_lock:
            job.status = "cancelled"
            job.error = str(exc)
        status(str(exc))
    except Exception as exc:
        details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        with jobs_lock:
            job.status = "failed"
            job.error = details
        status("処理を完了できませんでした: " + details)
    finally:
        if model is not None:
            del model
        if model_a is not None:
            del model_a
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
    normalized: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    label_aliases = {"怒り": "ang", "喜び": "hap", "悲しみ": "sad", "平常": "neu"}
    valid_emotions = {"", "ang", "hap", "sad", "neu"}
    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            raise ValueError(f"発話 {index + 1} の形式が不正です。")
        try:
            start = round(max(0.0, float(raw.get("start", 0) or 0)), 3)
            end = round(float(raw.get("end", start) or start), 3)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"発話 {index + 1} の時刻が不正です。") from exc
        if end < start:
            raise ValueError(f"発話 {index + 1} の終了時刻は開始時刻以降にしてください。")
        if end - start > 86400:
            raise ValueError(f"発話 {index + 1} の長さが不正です。")
        text_value = raw.get("text", "")
        if not isinstance(text_value, str) or len(text_value) > 50000:
            raise ValueError(f"発話 {index + 1} の本文が不正です。")
        speaker = str(raw.get("speaker") or "UNKNOWN").strip().replace("\r", " ").replace("\n", " ")[:80]
        segment = dict(raw)
        segment.update({"start": start, "end": end, "speaker": speaker or "UNKNOWN", "text": text_value.strip()})
        segment_id = stable_segment_id(item_id, index, segment)
        if segment_id in used_ids:
            segment_id = uuid.uuid4().hex
        segment["id"] = segment_id
        used_ids.add(segment_id)

        if "kushinada_label" in raw:
            requested_label = str(raw.get("kushinada_label") or "").strip().lower()
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
    completed = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-i", str(media_path), "-t", f"{duration:.3f}",
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        return None
    return target


def record_training_corrections(
    row: sqlite3.Row,
    old_segments: list[dict[str, Any]],
    new_segments: list[dict[str, Any]],
    old_names: dict[str, str],
    new_names: dict[str, str],
) -> int:
    old_by_id = {str(item.get("id")): item for item in old_segments}
    new_by_id = {str(item.get("id")): item for item in new_segments}
    ordered_ids = list(old_by_id) + [item_id for item_id in new_by_id if item_id not in old_by_id]
    media_path = Path(row["media_path"]) if row["media_path"] else None
    events: list[dict[str, Any]] = []
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
    if not events:
        return 0
    TRAINING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    manifest_fields = [
        "event_id", "audio_path", "emotion_label", "text", "speaker", "source_name",
        "start", "end", "operation", "created_at", "transcript_id", "segment_id",
    ]
    with training_lock:
        with TRAINING_JSONL_FILE.open("a", encoding="utf-8", newline="\n") as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        manifest_exists = TRAINING_MANIFEST_FILE.is_file() and TRAINING_MANIFEST_FILE.stat().st_size > 0
        with TRAINING_MANIFEST_FILE.open("a", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=manifest_fields)
            if not manifest_exists:
                writer.writeheader()
            for event in events:
                current = event.get("after") or event.get("before") or {}
                writer.writerow({
                    "event_id": event["event_id"],
                    "audio_path": event.get("audio_clip") or "",
                    "emotion_label": current.get("emotion") or "",
                    "text": current.get("text") or "",
                    "speaker": current.get("speaker_name") or current.get("speaker") or "",
                    "source_name": event["source_name"],
                    "start": current.get("start", ""),
                    "end": current.get("end", ""),
                    "operation": event["operation"],
                    "created_at": event["created_at"],
                    "transcript_id": event["transcript_id"],
                    "segment_id": event["segment_id"],
                })
    return len(events)


def update_library_from_payload(item_id: str, payload: Any) -> dict[str, Any]:
    row = library_row(item_id)
    if row is None:
        raise LookupError("データが見つかりません。")
    if not isinstance(payload, dict):
        raise ValueError("編集内容が JSON ではありません。")
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
        clean_name = str(value).strip().replace("\r", " ").replace("\n", " ")
        if str(label) in labels and clean_name:
            if len(clean_name) > 80:
                raise ValueError("話者名は 80 文字以内にしてください。")
            new_names[str(label)] = clean_name
    source_name = str(payload.get("source_name") or row["source_name"]).strip()
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
    files = write_outputs(
        source_name, output_dir, new_segments, row["language"], new_names,
        bool(row["write_srt"]), True, outline, emotion_analysis, speaker_profiles,
    )
    output_warning = ""
    media_path = Path(row["media_path"]) if row["media_path"] else None
    if bool(row["burn_subtitled_video"]) and media_path and media_path.is_file() and is_video_path(media_path):
        try:
            files.extend(write_subtitled_video_assets(
                media_path,
                source_name,
                output_dir,
                new_segments,
                new_names,
                speaker_profiles,
            ))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            output_warning = f"字幕動画の再作成に失敗しました: {exc}"
    learning_warning = ""
    try:
        learning_events = record_training_corrections(row, old_segments, new_segments, old_names, new_names)
    except (OSError, subprocess.SubprocessError) as exc:
        learning_events = 0
        learning_warning = f"学習データの記録に失敗しました: {exc}"
    updated = upsert_library_item(
        item_id=item_id, source_name=source_name, output_dir=output_dir,
        media_path=media_path,
        language=row["language"], segments=new_segments, speaker_names=new_names,
        outline=outline, emotion_analysis=emotion_analysis, files=files,
        write_srt=bool(row["write_srt"]), write_json=True,
        increment_revision=True, created_at=row["created_at"],
        session_profile=session_profile, speaker_profiles=speaker_profiles,
        burn_subtitled_video=bool(row["burn_subtitled_video"]),
    )
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
    if not min_value <= value <= max_value:
        raise ValueError(f"{name} は {min_value:g}～{max_value:g} で指定してください。")
    return value


def parse_audio_preprocess() -> str:
    preset = request.form.get("audio_preprocess", "standard").strip() or "standard"
    if preset not in AUDIO_PREPROCESS_PRESETS:
        raise ValueError("音声前処理の指定が不正です。")
    return preset


initialize_library()
import_existing_outputs()


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
        config = load_token_config()
        return jsonify({
            "ok": True,
            **config.availability(),
            "default_output_dir": str(DEFAULT_OUTPUT_DIRECTORY),
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


@app.get("/api/speakers")
def get_speaker_registry():
    include_inactive = request.args.get("include_inactive", "1") != "0"
    records = list_speaker_registry(include_inactive=include_inactive)
    return jsonify({"speakers": records, "total": len(records)})


@app.put("/api/speakers")
def update_speaker_registry():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "話者台帳の編集内容がJSONではありません。"}), 400
    try:
        records = save_speaker_registry_records(
            payload.get("speakers"),
            delete_ids=payload.get("delete_ids"),
        )
        return jsonify({"speakers": records, "total": len(records)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except sqlite3.Error as exc:
        return jsonify({"error": f"話者台帳を保存できません: {exc}"}), 500


@app.post("/api/speakers/import")
def import_speaker_registry():
    upload = request.files.get("csv_file")
    if upload is None or not upload.filename:
        return jsonify({"error": "GoogleフォームまたはスプレッドシートのCSVを選択してください。"}), 400
    try:
        records, imported_count = import_speaker_registry_csv(upload.read())
        return jsonify({
            "speakers": records,
            "total": len(records),
            "imported_count": imported_count,
        })
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
        thumbnail_url = (
            f"/api/source-thumbnail?path={urllib.parse.quote(str(path))}"
            if is_video_path(path)
            else None
        )
        return jsonify({
            "ok": True,
            "cancelled": False,
            "path": str(path),
            "name": path.name,
            "size": path.stat().st_size,
            "media_kind": media_kind(path),
            "thumbnail_url": thumbnail_url,
        })
    except (ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        file_dialog_lock.release()


@app.get("/api/source-thumbnail")
def source_thumbnail():
    try:
        source_path = resolve_local_media_path(request.args.get("path", ""))
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
    if not source_name or len(source_name) > 255:
        return jsonify({"error": "データ名は 1～255 文字で指定してください。"}), 400
    item_id = uuid.uuid4().hex
    try:
        row = upsert_library_item(
            item_id=item_id, source_name=source_name, output_dir=DEFAULT_OUTPUT_DIRECTORY,
            media_path=None, language=None, segments=[], speaker_names={}, outline=None,
            emotion_analysis=None, files=[], write_srt=True, write_json=True,
        )
        return jsonify(library_public(row)), 201
    except OSError as exc:
        return jsonify({"error": f"データを追加できません: {exc}"}), 500


@app.get("/api/library/<item_id>")
def get_library_item(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    return jsonify(library_public(row))


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
        "テーマカラー", "会話役割", "組織", "部署", "役職", "参加状態", "研究同意",
        "録音同意", "会話固有条件", "メモ", "発話数", "発話秒数", "文字数",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
    writer.writeheader()
    for label, profile in profiles.items():
        global_record = registry.get(profile.get("global_speaker_id"), {})
        metric = metrics.get(label, {"count": 0, "seconds": 0.0, "characters": 0})
        writer.writerow({
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
            "研究同意": profile["consent_status"],
            "録音同意": profile["recording_consent"],
            "会話固有条件": profile["conditions"],
            "メモ": profile["notes"],
            "発話数": metric["count"],
            "発話秒数": round(float(metric["seconds"]), 3),
            "文字数": metric["characters"],
            **(global_record.get("attributes", {}) or {}),
        })
    content = ("\ufeff" + stream.getvalue()).encode("utf-8")
    return send_file(
        io.BytesIO(content),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=f"{Path(row['source_name']).stem}_speakers.csv",
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
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        return jsonify({"error": f"保存できません: {exc}"}), 500


@app.delete("/api/library/<item_id>")
def delete_library_item(item_id: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    with jobs_lock:
        job = jobs.get(item_id)
        if job and job.status in {"queued", "running"}:
            return jsonify({"error": "処理中のデータは削除できません。"}), 409
    media_dir = (MEDIA_DIRECTORY / item_id).resolve()
    media_root = MEDIA_DIRECTORY.resolve()
    if media_dir.parent == media_root and media_dir.is_dir():
        try:
            shutil.rmtree(media_dir)
        except OSError as exc:
            return jsonify({"error": f"メディアを使用中のため削除できません。再生を停止してからお試しください: {exc}"}), 409
    for thumbnail_name in (f"text_mining_{item_id}.svg", f"word_cloud_{item_id}.svg"):
        (THUMBNAIL_DIRECTORY / thumbnail_name).unlink(missing_ok=True)
    with database_connection() as connection:
        connection.execute("DELETE FROM library_items WHERE id = ?", (item_id,))
    with jobs_lock:
        jobs.pop(item_id, None)
    return jsonify({
        "ok": True,
        "message": "ライブラリのデータと保存メディアを削除しました。出力ファイルと学習履歴は保持しています。",
    })


@app.get("/api/library/<item_id>/media")
def stream_library_media(item_id: str):
    row = library_row(item_id)
    if row is None or not row["media_path"]:
        return jsonify({"error": "元の音声・動画が保存されていません。"}), 404
    media_path = Path(row["media_path"])
    if not media_path.is_file():
        return jsonify({"error": "元の音声・動画が見つかりません。"}), 404
    return send_file(media_path, conditional=True, mimetype=mimetypes.guess_type(media_path.name)[0])


@app.get("/api/library/<item_id>/files/<path:filename>")
def download_library_file(item_id: str, filename: str):
    row = library_row(item_id)
    if row is None:
        return jsonify({"error": "データが見つかりません。"}), 404
    paths = [Path(value) for value in json_load(row["files_json"], []) if isinstance(value, str)]
    matching = next((path for path in paths if path.name == filename), None)
    if matching is None or not matching.is_file():
        return jsonify({"error": "出力ファイルが見つかりません。"}), 404
    return send_file(matching, as_attachment=True, download_name=matching.name)


@app.get("/api/training")
def training_status():
    event_count = 0
    ready_count = 0
    if TRAINING_JSONL_FILE.is_file():
        try:
            for line in TRAINING_JSONL_FILE.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event_count += 1
                data = json.loads(line)
                ready_count += int(bool(data.get("ready_for_kushinada")))
        except (OSError, json.JSONDecodeError):
            pass
    return jsonify({
        "event_count": event_count,
        "ready_count": ready_count,
        "jsonl_url": "/api/training/corrections.jsonl" if TRAINING_JSONL_FILE.is_file() else None,
        "manifest_url": "/api/training/manifest.csv" if TRAINING_MANIFEST_FILE.is_file() else None,
    })


@app.get("/api/training/corrections.jsonl")
def download_training_jsonl():
    if not TRAINING_JSONL_FILE.is_file():
        return jsonify({"error": "学習データはまだありません。"}), 404
    return send_file(TRAINING_JSONL_FILE, as_attachment=True, download_name="kushinada_corrections.jsonl")


@app.get("/api/training/manifest.csv")
def download_training_manifest():
    if not TRAINING_MANIFEST_FILE.is_file():
        return jsonify({"error": "学習データはまだありません。"}), 404
    return send_file(TRAINING_MANIFEST_FILE, as_attachment=True, download_name="kushinada_manifest.csv")


@app.post("/api/jobs")
def create_job():
    try:
        with jobs_lock:
            if any(job.status in {"queued", "running"} for job in jobs.values()):
                return jsonify({"error": "別の文字起こしを処理中です。完了または中止までお待ちください。"}), 409
        upload = request.files.get("input_file")
        source_path_raw = request.form.get("source_path", "").strip().strip('"')
        direct_input_path: Path | None = None
        if source_path_raw:
            direct_input_path = resolve_local_media_path(source_path_raw)
            original_name = direct_input_path.name
        elif upload is not None and upload.filename:
            original_name = Path(upload.filename).name
        else:
            return jsonify({"error": "処理する音声・動画ファイルを選択してください。"}), 400
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
            no_speech_threshold = 0.9
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
        output_root = Path(output_raw).expanduser() if output_raw else DEFAULT_OUTPUT_DIRECTORY
        if output_root.exists() and not output_root.is_dir():
            raise ValueError("保存先にはフォルダーを指定してください。")

        job_id = uuid.uuid4().hex
        output_dir = job_output_directory(output_root, original_name, job_id)
        upload_dir = UPLOAD_DIRECTORY / job_id
        upload_dir.mkdir(parents=True, exist_ok=False)
        if direct_input_path is not None:
            input_path = direct_input_path
        else:
            assert upload is not None
            safe_name = secure_filename(original_name) or f"input{Path(original_name).suffix.lower()}"
            input_path = upload_dir / safe_name
            upload.save(input_path)
            if not input_path.is_file() or input_path.stat().st_size == 0:
                shutil.rmtree(upload_dir, ignore_errors=True)
                raise ValueError("アップロードされたファイルが空です。")

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
        thread = threading.Thread(
            target=run_transcription_job,
            args=(job, options),
            name=f"transcription-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return jsonify(job.public()), 202
    except (ValueError, RuntimeError, OSError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        return jsonify({"error": "ジョブが見つかりません。"}), 404
    return jsonify(job.public())


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
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        return jsonify({"error": f"ファイルを保存できません: {exc}"}), 500


@app.get("/api/jobs/<job_id>/files/<path:filename>")
def download_file(job_id: str, filename: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": "ジョブが見つかりません。"}), 404
        matching = next((path for path in job.files if path.name == filename), None)
    if matching is None or not matching.is_file():
        return jsonify({"error": "出力ファイルが見つかりません。"}), 404
    return send_file(matching, as_attachment=True, download_name=matching.name)


def main() -> int:
    host = os.environ.get("MOJIOKOSI_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("MOJIOKOSI_PORT", "7860"))
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
