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
from types import SimpleNamespace
from typing import Any, Callable

from flask import Flask, g, has_request_context, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from .research_analysis import (
    is_research_analysis_cached,
    RESEARCH_CSV_FIELDS,
    build_analysis_workbook,
    build_research_analysis,
    enrich_research_analysis,
    research_csv_sources,
)
from .analysis_insights import (
    INSIGHT_VERSION, KWIC_FIELDS, build_session_outline, create_ai_insights,
    included_segments, input_fingerprint, plan_items, search_kwic,
)
from . import analysis_plan_advisor
from .transformer_analysis import (
    DEFAULT_MANUAL_MIN_SIMILARITY,
    DEFAULT_MODEL as DEFAULT_TRANSFORMER_MODEL,
    MAX_MANUAL_TOPICS,
    TOPIC_MODES,
    TRANSFORMER_ANALYSIS_VERSION,
    TRANSFORMER_CSV_FIELDS,
    analyze_transformer_topics,
    encode_texts as encode_transformer_texts,
    saved_embeddings as saved_transformer_embeddings,
    semantic_search as transformer_semantic_search,
    transformer_csv_sources,
    transformer_input_fingerprint,
)
from .ai_finishing import (
    FINISHING_VERSION, clean_transcript as finish_clean_transcript,
    create_outline as finish_create_outline, finishing_changes,
    repair_recommended_segments as finish_repair_recommended_segments,
)
from .jev_review import (
    JEV_DEFAULT_MODEL, JEV_REVIEW_VERSION,
    attach_comparison as attach_jev_comparison,
    comparison_rows as jev_comparison_rows,
    review_transcript as review_transcript_with_jev,
)
from .segment_classification import (
    CLASSIFICATION_FIELDS,
    CROSSTAB_FIELDS as SEGMENT_CLASSIFICATION_CROSSTAB_FIELDS,
    DIALOGUE_ACTS,
    SEGMENT_CLASSIFICATION_VERSION,
    build_result as build_segment_classification_result,
    classification_fingerprint,
    classification_rows,
    classify_with_jev,
    crosstab_rows as segment_classification_crosstab_rows,
    summary as segment_classification_summary,
    topic_candidates as segment_classification_topic_candidates,
)
from .obsidian_finishing import ObsidianWorkbench
from .ai_effort import normalize_efforts, effort_payload, local_effort_payload, SCHEMA_STAGES
from .analysis_method_registry import METHOD_GROUPS, SEPARATE_RUN_METHODS, method_results
from .analysis_store import AnalysisStore, StoreConflict, digest as archive_digest, initialize_store
from .analysis_core import AnalysisContractError
from .analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store
from .handlers.analysis_commands import (
    AnalysisCommandRequestError,
    AnalysisCommands,
    ComparisonRequestError,
    TranscriptConflictError,
)
from .handlers.analysis_queries import AnalysisQueries
from .handlers.application_lifecycle import ApplicationLifecycle
from .handlers.jobs import JobHandler, JobRequestError
from .handlers.library_groups import LibraryGroups
from .handlers.speaker_registry import (
    SpeakerIdentificationHandler,
    SpeakerIdentificationRequestError,
    SpeakerRegistryConflictError,
    SpeakerRegistryHandler,
)
from .web.analysis_routes import register_analysis_routes
from .web.job_routes import register_job_routes
from .web.obsidian_routes import register_obsidian_routes
from .web.speaker_routes import register_speaker_routes
from .web.system_routes import register_system_routes
from .services.obsidian_watcher import ObsidianWatcher
from .services.obsidian_workflows import ObsidianWorkflowService
from .services.transcription_reporting import TranscriptionReporter
from .services.vault_publication import VaultPublicationService, whisper_settings
from .services.ai import client as ai_client
from .services.ai import transcript_finishing as ai_transcript_finishing
from .services import durable_files
from .services import edit_transactions
from .services.edit_transactions import (
    EDIT_PREPARATION_MARKER_NAME,
    EDIT_TRANSACTION_MANIFEST_NAME,
    EDIT_TRANSACTION_SCHEMA_VERSION,
    MAX_EDIT_TRANSACTION_FILES,
    MAX_EDIT_TRANSACTION_MANIFEST_BYTES,
    capture_edit_cleanup_inventory,
    cleanup_edit_staging,
    cleanup_prepared_edit_staging,
    discard_transaction_target,
    edit_cleanup_allowed_directories,
    edit_cleanup_entry_identity,
    edit_journal_mac,
    edit_relative_path_key,
    edit_staging_identity,
    edit_transaction_cleanup_inventory,
    finish_committed_edit_transaction,
    hold_edit_directory_against_rename,
    load_edit_preparation_marker,
    load_edit_transaction_manifest,
    mark_windows_handle_for_deletion,
    open_windows_edit_entry_for_deletion,
    preflight_edit_promotion,
    preflight_rollback_edit_transaction,
    remove_edit_directory_contents,
    remove_windows_edit_directory_contents,
    rollback_edit_transaction,
    safe_edit_relative_path,
    transaction_file_kind,
    validate_edit_cleanup_inventory,
)
from .services import outputs
from .services import group_analysis
from .services import speaker_registry as speaker_registry_store
from .services import training_corpus
from .services import interview_comparison
from .services.transcription import formatting as transcript_formatting
from .services.transcription import job_runner as transcription_job_runner
from .services.training_corpus import (
    TRAINING_MANIFEST_FIELDS,
    correction_signature,
    discard_training_clips,
    insert_training_events,
    kushinada_label,
    training_events_from_connection,
    training_export_contents,
)
from .services.speaker_registry import (
    ATTENDANCE_STATUSES,
    CONSENT_STATUSES,
    SPEAKER_CSV_FIELD_ALIASES,
    SPEAKER_REGISTRATION_STATUSES,
    SPEAKER_ROLE_ALIASES,
    SPEAKER_ROLES,
    normalize_csv_consent,
    normalize_csv_role,
    normalize_speaker_registry_record,
    normalized_csv_header,
    speaker_csv_field_for_header,
    speaker_registry_csv_bytes,
    speaker_registry_public,
    speaker_registry_revision,
    speaker_registry_rows,
)
from .services.group_analysis import (
    ANALYSIS_CSV_FIELDS,
    ANALYSIS_ELICITATION_TYPES,
    ANALYSIS_FACILITATOR_ROLES,
    ANALYSIS_GROUP_FIELDS,
    ANALYSIS_INTERACTION_RELATIONS,
    ANALYSIS_INTERACTION_TAGS,
    ANALYSIS_INTERPRETATION_STATUSES,
    ANALYSIS_MAX_TIMELINE_SECONDS,
    ANALYSIS_MAX_TIME_BINS,
    ANALYSIS_METHODS,
    ANALYSIS_NON_PARTICIPANT_ROLES,
    ANALYSIS_UNITS,
    FOCUS_GROUP_METHOD_REFERENCES,
    TEXT_MINING_STOP_WORDS,
    analysis_bool,
    analysis_csv_content,
    analysis_csv_rows,
    analysis_csv_safe,
    analysis_emotion_entries,
    analysis_evenness,
    analysis_gini,
    analysis_number,
    analysis_optional_score,
    analysis_segment_bounds,
    build_focus_group_analysis_plan,
    default_analysis_config,
    focus_group_analysis_report_markdown,
    focus_group_data_inventory,
    normalize_analysis_annotations,
    normalize_analysis_codebook,
    normalize_analysis_config,
    normalize_analysis_group_by,
    normalize_codebook_history,
    normalize_transformer_topics,
    row_analysis_annotation_state,
    row_analysis_annotations,
    row_analysis_config,
    text_mining_counter,
    text_mining_terms,
)
from .services.outputs import (
    MEDIA_SESSION_DATE_TAGS,
    SPEAKER_THEME_COLORS,
    SUBTITLE_BREAK_AFTER,
    ass_escape_text,
    ass_time,
    job_output_directory,
    rgb_to_ass_color,
    safe_output_stem,
    speaker_theme_color_map,
    subtitle_text_pages,
    subtitle_text_width,
    wrap_subtitle_lines,
    write_ass_subtitles,
)
from .services.durable_files import (
    atomic_copy_file,
    atomic_write_bytes,
    atomic_write_text,
    durable_move,
    durable_write_json,
    ensure_staging_tree_has_no_reparse_points,
    file_matches_fingerprint,
    file_sha256,
    path_entry_exists,
    path_has_reparse_ancestor,
    path_is_link_or_reparse,
    path_is_within,
    sync_directory_metadata,
    sync_file_data,
    sync_rename_metadata,
    temporary_output_path,
    windows_case_insensitive_text,
    windows_extended_path,
    windows_move_file_write_through,
    posix_move_no_replace,
)
from .services import emotion as emotion_analysis
from .services.meeting_minutes import (
    MEETING_MINUTES_VERSION,
    MEETING_TASK_PRIORITIES,
    MEETING_TASK_PRIORITY_LABELS,
    build_meeting_minutes,
    format_meeting_minutes_markdown,
    format_outline_text,
    meeting_decision_candidate,
    meeting_due_details,
    meeting_external_payload,
    meeting_safe_number,
    meeting_task_candidate,
    meeting_task_priority,
    meeting_task_title,
    meeting_tasks_csv_text,
    normalize_meeting_minutes,
)
from .services.transcription import audio as transcription_audio
from .services.emotion import (
    AIST_EMOTION_LABEL_JA,
    AIST_EMOTION_MODELS,
    aist_emotion_model_keys,
    build_emotion_analysis_summary,
    emotion_label_ja,
    emotion_segments_for_output,
    segment_emotion_display,
)
from .services.transcription.segments import (
    SHORT_SPEAKER_ISLAND_MAX_SECONDS,
    SPEAKER_BACKCHANNEL_TEXTS,
    QUIET_SUPPLEMENT_EDGE_PADDING,
    QUIET_SUPPLEMENT_LOW_OVERLAP_RATIO,
    QUIET_SUPPLEMENT_MAX_COMPRESSION_RATIO,
    QUIET_SUPPLEMENT_MAX_NO_SPEECH_PROB,
    QUIET_SUPPLEMENT_MIN_AVG_LOGPROB,
    QUIET_SUPPLEMENT_MIN_DEDUPE_CHARS,
    QUIET_SUPPLEMENT_MIN_DURATION,
    QUIET_SUPPLEMENT_PARTIAL_OVERLAP_RATIO,
    QUIET_SUPPLEMENT_TEXT_WINDOW_SECONDS,
    TRIPLE_PASS_GAP_CONTEXT_SECONDS,
    TRIPLE_PASS_MIN_GAP_OVERLAP_RATIO,
    TRIPLE_PASS_MIN_GAP_SECONDS,
    asr_segment_quality_ok,
    default_speaker_name,
    display_time,
    find_long_asr_gaps,
    has_near_duplicate_text,
    make_display_segments,
    merge_supplemental_asr_segments,
    merged_interval_coverage,
    normalize_asr_segments,
    normalize_text_for_merge,
    offset_asr_segments_to_gap,
    segment_bounds,
    segment_speaker,
    should_add_supplemental_segment,
    srt_time,
)
from .env_settings import env_enabled, positive_env_int
from .media_formats import ALLOWED_EXTENSIONS, VIDEO_EXTENSIONS
from .text_utils import (
    clean_multiline,
    clean_single_line,
    json_load,
    normalize_attributes,
    normalize_tags,
    utc_now_iso,
)
from . import transcript_preparation as preparation
from . import method_experts
from .services.library_rows import (
    emotion_values,
    ensure_segment_ids,
    interview_comparison_identity,
    normalize_conversation_speaker_profiles,
    normalize_session_profile,
    normalize_source_name,
    row_meeting_minutes,
    row_original_segments,
    row_segments,
    row_session_outline,
    row_session_profile,
    row_speaker_profiles,
    stable_segment_id,
)
from .services.transcription.audio import (
    AUDIO_PREPROCESS_PRESETS,
)
from .text_utils import (
    validate_json_value,
)
from .web.request_parsing import (
    parse_audio_preprocess,
    parse_bool,
    parse_optional_float,
    parse_optional_int,
)
from .services.word_cloud import (
    write_word_cloud,
)
from .web.library_group_routes import register_library_group_routes
from .web.training_routes import register_training_routes
from .web.export_routes import register_export_routes
from .web.analysis_view_routes import register_analysis_view_routes
from .web.ai_routes import register_ai_routes
from .services.machine_profile import (
    detect_machine_profile,
    get_machine_profile,
    recommend_machine_settings,
    system_activity_snapshot,
)


os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
warnings.filterwarnings(
    "ignore",
    message=r"\s*torchcodec is not installed correctly.*",
    category=UserWarning,
)

PRODUCT_NAME = "グルモジ"
APP_VERSION = "1.8.0"
APP_CREATOR = "Kurokawa"
APP_NAME = f"{PRODUCT_NAME} | 話者分離文字起こし"
APP_DIRECTORY = Path(__file__).resolve().parent
PROJECT_DIRECTORY = APP_DIRECTORY.parents[1]
RUNTIME_DIRECTORY = PROJECT_DIRECTORY / "runtime"
AI_HTTP_WORKER_FILE = APP_DIRECTORY / "ai_http_worker.py"
DEFAULT_OUTPUT_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_OUTPUT_DIR", str(RUNTIME_DIRECTORY / "output"))
).expanduser()
UPLOAD_DIRECTORY = RUNTIME_DIRECTORY / "uploads"
DATA_DIRECTORY = Path(
    os.environ.get("MOJIOKOSI_DATA_DIR", str(RUNTIME_DIRECTORY / "data"))
).expanduser()
MEDIA_DIRECTORY = DATA_DIRECTORY / "media"
THUMBNAIL_DIRECTORY = DATA_DIRECTORY / "thumbnails"
TRAINING_DIRECTORY = DATA_DIRECTORY / "kushinada_training"
TRAINING_AUDIO_DIRECTORY = TRAINING_DIRECTORY / "audio"
TRAINING_JSONL_FILE = TRAINING_DIRECTORY / "corrections.jsonl"
TRAINING_MANIFEST_FILE = TRAINING_DIRECTORY / "manifest.csv"
CUSTOM_VOCABULARY_FILE = DATA_DIRECTORY / "custom_vocabulary.json"
DATABASE_FILE = DATA_DIRECTORY / "library.sqlite3"
INSTANCE_LOCK_FILE = UPLOAD_DIRECTORY / ".gurumoji.instance.lock"
DATA_INSTANCE_LOCK_FILE = DATA_DIRECTORY / ".gurumoji.instance.lock"
TOKEN_FILE = PROJECT_DIRECTORY / "config" / "tokens.json"
DIARIZATION_MODEL = os.environ.get(
    "MOJIOKOSI_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"
)
DIARIZATION_ACCESS_REPOS = (
    DIARIZATION_MODEL,
    "pyannote/segmentation-3.0",
    "pyannote/speaker-diarization-community-1",
)


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
MODEL_NAMES = {"tiny", "base", "small", "medium", "large-v3"}
LANGUAGES = {None, "ja", "en", "zh", "ko"}
AI_PROVIDERS = {"none", "openai", "google", "lmstudio"}
AI_MODEL_PROVIDERS = frozenset(AI_PROVIDERS - {"none"})
LMSTUDIO_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
LMSTUDIO_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
AI_PROVIDER_LABELS = {
    "openai": "OpenAI",
    "google": "Google Gemini",
    "lmstudio": "LM Studio（ローカル）",
}
AIST_EMOTION_MODEL_CHOICES = {"kushinada", "izanami", "both"}
MAX_LOG_LINES = 200
NORMAL_VAD_ONSET = 0.5
NORMAL_VAD_OFFSET = 0.363
NORMAL_NO_SPEECH_THRESHOLD = 0.6
CUSTOM_VOCABULARY_MAX_TERMS = 100
CUSTOM_VOCABULARY_MAX_TERM_LENGTH = 80
# Whisper's initial prompt shares a short context window with the beginning of
# the audio.  Keeping this compact makes registered terms useful without
# crowding out the first utterance, especially for Japanese where one token can
# be close to one visible character.
WHISPER_VOCABULARY_PROMPT_MAX_CHARACTERS = 220
WHISPER_SAMPLE_RATE = 16000
CONVERSATION_MODES = {
    "meeting": "meeting",
    "group_interview": "focus_group",
    "chat": "chat",
}


class AnalysisConflictError(RuntimeError):
    pass


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
    lmstudio_api_key: str = ""
    lmstudio_base_url: str = LMSTUDIO_DEFAULT_BASE_URL
    lmstudio_model: str = ""
    typesafe_api_key: str = ""
    typesafe_model: str = JEV_DEFAULT_MODEL

    def availability(self) -> dict[str, Any]:
        return {
            "token_file": TOKEN_FILE.name,
            "huggingface": bool(self.huggingface_token),
            "openai": bool(self.openai_api_key),
            "google": bool(self.google_api_key),
            "openai_model": self.openai_model,
            "google_model": self.google_model,
            "lmstudio_base_url": self.lmstudio_base_url,
            "lmstudio_model": self.lmstudio_model,
            "lmstudio_has_api_key": bool(self.lmstudio_api_key),
            "typesafe": bool(self.typesafe_api_key),
            "typesafe_model": self.typesafe_model,
            # Keep the lmstudio_* keys for backwards compatibility. The same
            # loopback-only OpenAI-compatible provider is backed by Ollama in
            # the Colab notebook.
            "local_llm_label": local_llm_label(),
            "local_llm_short_label": local_llm_short_label(),
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
    ai_base_url: str = ""
    owns_output_dir: bool = False
    finish_in_obsidian: bool = True
    ai_efforts: dict = field(default_factory=normalize_efforts)
    num_speakers: int | None = None
    conversation_mode: str = "meeting"
    custom_vocabulary: tuple[str, ...] = ()
    recommended_cleanup: bool = False
    jev_compare: bool = False
    jev_api_key: str = ""
    jev_model: str = JEV_DEFAULT_MODEL
    transcript_finishing_mode: str = "custom"
    write_word_cloud: bool = False
    generate_meeting_minutes: bool = False


@dataclass
class JobRecord:
    id: str
    source_name: str
    output_dir: Path
    write_srt: bool
    write_json: bool
    conversation_mode: str = "meeting"
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
    speaker_registration: dict[str, Any] = field(default_factory=dict)
    outline: dict[str, Any] | None = None
    meeting_minutes: dict[str, Any] | None = None
    emotion_analysis: dict[str, Any] | None = None
    formatting_result: dict[str, Any] = field(default_factory=dict)
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
                "conversation_mode": self.conversation_mode,
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
                "speaker_registration": (
                    dict(self.speaker_registration) if self.status == "completed" else {}
                ),
                "write_srt": self.write_srt,
                "write_json": True,
                "burn_subtitled_video": self.burn_subtitled_video,
                "outline": dict(self.outline) if self.status == "completed" and self.outline else None,
                "meeting_minutes": (
                    dict(self.meeting_minutes)
                    if self.status == "completed" and self.meeting_minutes
                    else None
                ),
                "emotion_analysis": (
                    dict(self.emotion_analysis)
                    if self.status == "completed" and self.emotion_analysis
                    else None
                ),
                "formatting_result": (
                    dict(self.formatting_result) if self.status == "completed" else {}
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
insight_jobs_lock = threading.RLock()
insight_cancel_events: dict[str, threading.Event] = {}
transformer_jobs_lock = threading.RLock()
transformer_cancel_events: dict[str, threading.Event] = {}
training_lock = threading.Lock()
file_dialog_lock = threading.Lock()
token_config_lock = threading.Lock()
custom_vocabulary_lock = threading.Lock()
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


def media_kind(path: Path | None) -> str | None:
    if path is None:
        return None
    mime = mimetypes.guess_type(path.name)[0] or ""
    return "video" if mime.startswith("video/") or path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv"} else "audio"


def is_unc_path(value: str | Path) -> bool:
    raw = str(value).strip()
    return raw.startswith("\\") or raw.startswith("//")


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
                group_id TEXT NOT NULL DEFAULT '',
                output_dir TEXT NOT NULL,
                media_path TEXT,
                language TEXT,
                segments_json TEXT NOT NULL,
                original_segments_json TEXT NOT NULL DEFAULT '',
                original_segments_status TEXT NOT NULL DEFAULT '',
                speaker_names_json TEXT NOT NULL,
                outline_json TEXT,
                meeting_minutes_json TEXT NOT NULL DEFAULT '{}',
                emotion_analysis_json TEXT,
                formatting_result_json TEXT NOT NULL DEFAULT '{}',
                ai_usage_json TEXT NOT NULL DEFAULT '{}',
                files_json TEXT NOT NULL,
                write_srt INTEGER NOT NULL DEFAULT 1,
                write_json INTEGER NOT NULL DEFAULT 1,
                burn_subtitled_video INTEGER NOT NULL DEFAULT 0,
                analysis_config_json TEXT NOT NULL DEFAULT '{}',
                analysis_annotations_json TEXT NOT NULL DEFAULT '{}',
                segment_classification_json TEXT NOT NULL DEFAULT '{}',
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
        if "group_id" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN group_id TEXT NOT NULL DEFAULT ''"
            )
        if "original_segments_json" not in library_columns:
            # A transcript that existed before this schema revision cannot be
            # reconstructed.  Keep the then-current text in a separate column
            # and disclose that provenance instead of calling it a pristine
            # ASR/field transcript.
            connection.execute(
                "ALTER TABLE library_items "
                "ADD COLUMN original_segments_json TEXT NOT NULL DEFAULT ''"
            )
            connection.execute(
                "ALTER TABLE library_items "
                "ADD COLUMN original_segments_status TEXT NOT NULL DEFAULT ''"
            )
            connection.execute(
                "UPDATE library_items SET original_segments_json = segments_json, "
                "original_segments_status = 'migrated_current_snapshot' "
                "WHERE original_segments_json = ''"
            )
        elif "original_segments_status" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items "
                "ADD COLUMN original_segments_status TEXT NOT NULL DEFAULT ''"
            )
            connection.execute(
                "UPDATE library_items SET original_segments_status = "
                "CASE WHEN original_segments_json <> '' THEN 'migrated_current_snapshot' ELSE '' END"
            )
        if "speaker_profiles_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN speaker_profiles_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "meeting_minutes_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN meeting_minutes_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "ai_usage_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN ai_usage_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "formatting_result_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN formatting_result_json TEXT NOT NULL DEFAULT '{}'"
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
        if "analysis_insights_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN analysis_insights_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "transformer_analysis_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN transformer_analysis_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "segment_classification_json" not in library_columns:
            connection.execute(
                "ALTER TABLE library_items ADD COLUMN segment_classification_json TEXT NOT NULL DEFAULT '{}'"
            )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS analysis_insight_requests (
                request_id TEXT PRIMARY KEY, item_id TEXT NOT NULL,
                source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
                fingerprint TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
                status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '', usage_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS insight_requests_item ON analysis_insight_requests(item_id, created_at)")
        connection.execute("""
            UPDATE analysis_insight_requests SET status = 'interrupted',
                message = 'アプリが再起動されました。必要な場合は再生成してください。'
            WHERE status IN ('queued', 'running', 'cancelling')
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS transformer_analysis_requests (
                request_id TEXT PRIMARY KEY, item_id TEXT NOT NULL,
                source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
                fingerprint TEXT NOT NULL, model TEXT NOT NULL,
                max_topics INTEGER NOT NULL, min_topic_size INTEGER NOT NULL,
                topic_count INTEGER NOT NULL DEFAULT 0,
                mode TEXT NOT NULL DEFAULT 'auto',
                min_similarity REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        transformer_request_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(transformer_analysis_requests)").fetchall()
        }
        if "topic_count" not in transformer_request_columns:
            connection.execute(
                "ALTER TABLE transformer_analysis_requests "
                "ADD COLUMN topic_count INTEGER NOT NULL DEFAULT 0"
            )
        if "mode" not in transformer_request_columns:
            connection.execute(
                "ALTER TABLE transformer_analysis_requests "
                "ADD COLUMN mode TEXT NOT NULL DEFAULT 'auto'"
            )
        if "min_similarity" not in transformer_request_columns:
            connection.execute(
                "ALTER TABLE transformer_analysis_requests "
                "ADD COLUMN min_similarity REAL NOT NULL DEFAULT 0"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS transformer_requests_item "
            "ON transformer_analysis_requests(item_id, created_at)"
        )
        connection.execute("""
            UPDATE transformer_analysis_requests SET status = 'interrupted',
                message = 'アプリが再起動されました。必要な場合は再実行してください。'
            WHERE status IN ('queued', 'running', 'cancelling')
        """)
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
            """
            CREATE TABLE IF NOT EXISTS library_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS library_group_name_idx ON library_groups(name COLLATE NOCASE)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS library_items_group_idx ON library_items(group_id)"
        )
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
        initialize_store(connection)
        initialize_pipeline_store(connection)
        preparation.initialize(connection)
        if repair_provenance:
            repair_output_import_provenance(connection)
        for row in connection.execute("SELECT id, source_name FROM library_items").fetchall():
            source_path = Path(str(row["source_name"]))
            if source_path.is_absolute() and source_path.name:
                connection.execute(
                    "UPDATE library_items SET source_name = ? WHERE id = ?",
                    (source_path.name, row["id"]),
                )


def speaker_registry_snapshot(
    *,
    include_inactive: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    return speaker_registry_store.speaker_registry_snapshot(
        include_inactive=include_inactive, connect=database_connection
    )


def list_speaker_registry(*, include_inactive: bool = True) -> list[dict[str, Any]]:
    return speaker_registry_store.list_speaker_registry(
        include_inactive=include_inactive, connect=database_connection
    )

def save_speaker_registry_records(
    raw_records: Any,
    *,
    delete_ids: Any = None,
    expected_revision: int | None = None,
    merge_by_participant_code: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    return speaker_registry_handler().save(
        raw_records,
        delete_ids=delete_ids,
        expected_revision=expected_revision,
        merge_by_participant_code=merge_by_participant_code,
    )


# Speaker registry composition boundary.
def persist_speaker_registry_record(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    previous: dict[str, Any] | None,
    now: str,
) -> None:
    speaker_registry_store.persist_speaker_registry_record(
        connection, record, previous, now
    )


def _save_speaker_registry_records_locked(*args: Any, **kwargs: Any):
    kwargs.setdefault("connect", database_connection)
    return speaker_registry_store._save_speaker_registry_records_locked(*args, **kwargs)


def import_speaker_registry_csv(
    content: bytes,
    *,
    expected_revision: int,
) -> tuple[list[dict[str, Any]], int, int]:
    return speaker_registry_store.import_speaker_registry_csv(
        content,
        expected_revision=expected_revision,
        max_upload_bytes=MAX_CSV_UPLOAD_BYTES,
        save_records=save_speaker_registry_records,
    )


def library_row(item_id: str) -> sqlite3.Row | None:
    with database_connection() as connection:
        return connection.execute("SELECT * FROM library_items WHERE id = ?", (item_id,)).fetchone()


def library_group_name(group_id: str) -> str:
    if not group_id:
        return ""
    with database_connection() as connection:
        row = connection.execute(
            "SELECT name FROM library_groups WHERE id = ?", (group_id,)
        ).fetchone()
    return str(row["name"]) if row is not None else ""


def library_public(
    row: sqlite3.Row, *, full: bool = True, match_count: int | None = None,
    group_name: str | None = None,
) -> dict[str, Any]:
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
    session_profile = row_session_profile(row)
    comparison_key, comparison_label, comparison_source = interview_comparison_identity(
        session_profile
    )
    group_id = str(row["group_id"] or "") if "group_id" in row.keys() else ""
    resolved_group_name = library_group_name(group_id) if group_name is None else group_name
    media_available = bool(
        media_path
        and path_is_within(media_path, MEDIA_DIRECTORY / str(row["id"]))
        and media_path.is_file()
    )
    result: dict[str, Any] = {
        "id": row["id"],
        "source_name": row["source_name"],
        "group_id": group_id,
        "group_name": resolved_group_name,
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
        # The key is only a matching token.  A guide-derived key never exposes
        # the guide text to the list API.
        "comparison_key": comparison_key,
        "comparison_label": comparison_label,
        "comparison_source": comparison_source,
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
            "session_profile": session_profile,
            "speaker_profiles": row_speaker_profiles(row, segments, speaker_names),
            "outline": json_load(row["outline_json"], None),
            "session_outline": row_session_outline(row, session_profile),
            "meeting_minutes": row_meeting_minutes(row),
            "emotion_analysis": json_load(row["emotion_analysis_json"], None),
            "formatting_result": json_load(row["formatting_result_json"], {}),
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
    meeting_minutes: dict[str, Any] | None = None,
    original_segments: list[dict[str, Any]] | None = None,
    formatting_result: dict[str, Any] | None = None,
) -> sqlite3.Row:
    validate_json_value(segments)
    validate_json_value(original_segments)
    validate_json_value(speaker_names)
    validate_json_value(outline)
    validate_json_value(emotion_analysis)
    validate_json_value(session_profile)
    validate_json_value(speaker_profiles)
    validate_json_value(meeting_minutes)
    validate_json_value(formatting_result)
    ai_usage = normalize_ai_usage(ai_usage)
    validate_json_value(ai_usage)
    now = utc_now_iso()
    segments = ensure_segment_ids(item_id, segments)
    import_segments = ensure_segment_ids(item_id, original_segments) if original_segments is not None else segments
    session_profile = normalize_session_profile(session_profile)
    meeting_minutes = normalize_meeting_minutes(meeting_minutes)
    labels = {str(item.get("speaker") or "UNKNOWN") for item in segments}
    speaker_profiles = normalize_conversation_speaker_profiles(
        speaker_profiles,
        labels,
        speaker_names,
    )
    def persist(active_connection: sqlite3.Connection) -> sqlite3.Row:
        if not active_connection.in_transaction:
            active_connection.execute("BEGIN IMMEDIATE")
        previous = active_connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
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
        if previous is not None:
            preparation.capture(active_connection, previous, "legacy_current_baseline")
        persisted_formatting_result = formatting_result
        if persisted_formatting_result is None and previous is not None:
            persisted_formatting_result = json_load(previous["formatting_result_json"], {})
        active_connection.execute(
            """
            INSERT INTO library_items (
                id, source_name, output_dir, media_path, language, segments_json,
                original_segments_json, original_segments_status,
                speaker_names_json, outline_json, meeting_minutes_json, emotion_analysis_json,
                formatting_result_json, ai_usage_json, files_json,
                write_srt, write_json, burn_subtitled_video, revision_count, created_at, updated_at,
                session_profile_json, speaker_profiles_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_name=excluded.source_name, output_dir=excluded.output_dir,
                media_path=excluded.media_path, language=excluded.language,
                segments_json=excluded.segments_json, speaker_names_json=excluded.speaker_names_json,
                outline_json=excluded.outline_json, meeting_minutes_json=excluded.meeting_minutes_json,
                emotion_analysis_json=excluded.emotion_analysis_json,
                formatting_result_json=excluded.formatting_result_json,
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
                json.dumps(import_segments, ensure_ascii=False), "initial_import",
                json.dumps(speaker_names, ensure_ascii=False),
                json.dumps(outline, ensure_ascii=False) if outline else None,
                json.dumps(meeting_minutes, ensure_ascii=False),
                json.dumps(emotion_analysis, ensure_ascii=False) if emotion_analysis else None,
                json.dumps(persisted_formatting_result or {}, ensure_ascii=False),
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
        preparation.capture(active_connection, row, "saved" if previous is not None else "initial_import")
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


# Edit transaction composition boundary: the module owns the crash-safe swap,
# this layer binds it to the application database.
def edit_storage_id(connection: sqlite3.Connection | None = None) -> str:
    return edit_transactions.edit_storage_id(connection, connect=database_connection)


def edit_journal_secret(connection: sqlite3.Connection | None = None) -> bytes:
    return edit_transactions.edit_journal_secret(connection, connect=database_connection)


def write_edit_preparation_marker(*args: Any, **kwargs: Any) -> Path:
    kwargs.setdefault("connect", database_connection)
    return edit_transactions.write_edit_preparation_marker(*args, **kwargs)


def write_edit_transaction_manifest(*args: Any, **kwargs: Any) -> Path:
    kwargs.setdefault("connect", database_connection)
    return edit_transactions.write_edit_transaction_manifest(*args, **kwargs)


def reconcile_edit_transaction_with_database(
    staging_root: Path,
    payload: dict[str, Any],
) -> list[str]:
    return edit_transactions.reconcile_edit_transaction_with_database(
        staging_root, payload, connect=database_connection
    )


def promote_staged_files(staging_dir: Path, output_dir: Path, staged_files: list[Path]):
    return edit_transactions.promote_staged_files(
        staging_dir, output_dir, staged_files, connect=database_connection
    )

def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def thumbnail_cache_path(source_path: Path) -> Path:
    stat = source_path.stat()
    seed = f"{source_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return THUMBNAIL_DIRECTORY / f"{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex}.jpg"


# Group analysis composition boundary: the module computes, this layer supplies
# the library row accessors and the database connection.
def group_analysis_for_row(
    row: sqlite3.Row,
    *,
    include_research_rows: bool = False,
    execute: bool = True,
) -> dict[str, Any]:
    return group_analysis.group_analysis_for_row(
        row,
        include_research_rows=include_research_rows,
        execute=execute,
        connect=database_connection,
        row_segments=row_segments,
        row_original_segments=row_original_segments,
        row_speaker_profiles=row_speaker_profiles,
        row_session_profile=row_session_profile,
        list_speaker_registry=list_speaker_registry,
    )


def summarize_codebook_change(before: list[dict[str, str]], after: list[dict[str, str]]) -> str:
    previous = {str(item.get("id") or ""): item for item in before}
    current = {str(item.get("id") or ""): item for item in after}
    added = [item.get("label") or item_id for item_id, item in current.items() if item_id not in previous]
    removed = [item.get("label") or item_id for item_id, item in previous.items() if item_id not in current]
    changed = [
        current[item_id].get("label") or item_id for item_id in current.keys() & previous.keys()
        if current[item_id] != previous[item_id]
    ]
    parts = []
    if added:
        parts.append("追加: " + "、".join(str(value) for value in added))
    if removed:
        parts.append("削除: " + "、".join(str(value) for value in removed))
    if changed:
        parts.append("変更: " + "、".join(str(value) for value in changed))
    return " / ".join(parts) or "コードブックの順序または定義を変更"


def save_group_analysis(item_id: str, payload: Any) -> dict[str, Any]:
    with library_write_lock:
        result = _save_group_analysis_locked(item_id, payload)
        refresh_archive_index(item_id)
        return result


def _save_group_analysis_locked(item_id: str, payload: Any) -> dict[str, Any]:
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
    # The client is allowed to submit an older configuration, but only the
    # server-held history is authoritative.  Record the reason even when it
    # was omitted so that a later reviewer can see the gap rather than assume
    # that no change occurred.
    config["codebook_history"] = list(current_config.get("codebook_history", []))
    config["codebook_version"] = int(current_config.get("codebook_version", 0))
    if config["codebook"] != current_config.get("codebook", []):
        version = config["codebook_version"] + 1
        config["codebook_version"] = version
        config["codebook_history"] = (
            config["codebook_history"] + [{
                "version": version,
                "changed_at": utc_now_iso(),
                "reason": config["codebook_change_reason"] or "変更理由未記入（要確認）",
                "summary": summarize_codebook_change(
                    current_config.get("codebook", []), config["codebook"]
                ),
            }]
        )[-20:]
        config["codebook_change_reason"] = ""
    annotations_source = payload.get("annotations", current_annotations)
    annotations = normalize_analysis_annotations(annotations_source, segments, config)
    existing_links = {(sid, link.get("target_segment_id"), link.get("relation"))
        for sid, annotation in {**orphaned_annotations, **current_annotations}.items()
        for link in annotation.get("interaction_links", [])}
    current_ids = {s["id"] for s in segments}
    for sid, annotation in annotations.items():
        for link in annotation.get("interaction_links", []):
            if link["target_segment_id"] not in current_ids and (sid, link["target_segment_id"], link["relation"]) not in existing_links:
                raise ValueError("相互作用リンクの対象発言が存在しません。削除済みの既存リンクのみ履歴として保持できます。")
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
        if stored_annotations and not current_annotations and not orphaned_annotations:
            preparation.capture(connection, row, "analysis_baseline")
            preparation.bind_analysis(connection, row)
    updated = library_row(item_id)
    if updated is None:
        raise LookupError("処理済みデータが見つかりません。")
    return group_analysis_for_row(updated)


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
                    formatting_result=(
                        payload.get("formatting_result")
                        if isinstance(payload.get("formatting_result"), dict) else None
                    ),
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
            publish_input_vault(library_row(item_id), source_kind="imported")
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
        lmstudio_api_key=clean_secret(raw.get("lmstudio_api_key")),
        lmstudio_base_url=clean_single_line(
            raw.get("lmstudio_base_url"), 300
        ) or LMSTUDIO_DEFAULT_BASE_URL,
        lmstudio_model=clean_single_line(raw.get("lmstudio_model"), 200),
        typesafe_api_key=clean_secret(raw.get("typesafe_api_key")),
        typesafe_model=clean_single_line(raw.get("typesafe_model"), 200) or JEV_DEFAULT_MODEL,
    )


def lmstudio_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def lmstudio_model_id(value: Any) -> str:
    model = clean_single_line(value, 200)
    if not model or any(ord(character) < 33 or ord(character) == 127 for character in model):
        raise ValueError("モデルIDの形式が不正です。")
    return model


def configured_ai_credentials(config: TokenConfig, provider: str) -> tuple[str, str]:
    if provider == "openai":
        return config.openai_api_key, config.openai_model
    if provider == "google":
        return config.google_api_key, config.google_model
    if provider == "lmstudio":
        lmstudio_base_url(config.lmstudio_base_url)
        return config.lmstudio_api_key, config.lmstudio_model
    raise ValueError("AI プロバイダーが不正です。")


def local_llm_short_label() -> str:
    return "Ollama" if is_colab_runtime() else "LM Studio"


def local_llm_label() -> str:
    return "Ollama（ColabローカルLLM）" if is_colab_runtime() else "LM Studio（ローカル）"


def local_llm_model_required_message() -> str:
    return (
        f"{local_llm_short_label()} のモデルが未選択です。"
        "上部のローカルLLMライトをクリックして選択してください。"
    )


def ai_provider_label(provider: str) -> str:
    if provider == "lmstudio":
        return local_llm_label()
    return AI_PROVIDER_LABELS.get(provider, "AI")


def available_ai_models(
    provider: str,
    config: TokenConfig,
    *,
    timeout: float = 30,
) -> list[dict[str, Any]]:
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
    elif provider == "lmstudio":
        base_url = lmstudio_base_url(config.lmstudio_base_url)
        request_object = urllib.request.Request(
            f"{base_url}/models",
            headers={**lmstudio_headers(config.lmstudio_api_key), "Accept": "application/json"},
            method="GET",
        )
    else:
        raise ValueError("モデル一覧を取得できるAIを選択してください。")
    try:
        with urllib.request.urlopen(request_object, timeout=max(0.2, min(30.0, float(timeout)))) as response:
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
    elif provider == "openai":
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
    else:
        raw_models = payload.get("data") if isinstance(payload, dict) else None
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                model_id = lmstudio_model_id(item.get("id"))
            except ValueError:
                continue
            model_type = clean_single_line(item.get("type") or item.get("object"), 80)
            models.append({
                "id": model_id,
                "label": model_id,
                "description": model_type,
            })
    unique = {item["id"]: item for item in models}
    return [unique[key] for key in sorted(unique, key=str.casefold)]


def lmstudio_connection_status(config: TokenConfig) -> dict[str, Any]:
    """Probe only the local model-list endpoint for the UI connection light."""
    try:
        base_url = lmstudio_base_url(config.lmstudio_base_url)
        models = available_ai_models("lmstudio", config, timeout=0.75)
    except (ValueError, RuntimeError):
        if is_colab_runtime():
            message = "起動待ちです。ノートブックの「ColabローカルLLM」セルを実行してください。"
        else:
            message = "起動待ちです。LM Studio の Developer で Start server を有効にしてください。"
        return {
            "reachable": False,
            "model_count": 0,
            "message": message,
        }
    empty_message = (
        "接続済みです。ノートブックでモデルを選択・取得してから、ライトをクリックしてください。"
        if is_colab_runtime()
        else "接続済みです。LM Studio でモデルを読み込み、ライトをクリックして選択してください。"
    )
    return {
        "reachable": True,
        "model_count": len(models),
        "base_url": base_url,
        "message": (
            f"接続済み（{len(models)} モデル）。ライトをクリックして使用モデルを選択してください。"
            if models else empty_message
        ),
    }


def update_token_model(provider: str, model: str, path: Path = TOKEN_FILE) -> TokenConfig:
    provider = str(provider or "").strip().casefold()
    if provider not in AI_MODEL_PROVIDERS:
        raise ValueError("OpenAI、Google Gemini、またはローカルLLMを選択してください。")
    model = lmstudio_model_id(model)
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


def normalize_custom_vocabulary(values: Any) -> tuple[str, ...]:
    """Validate and deduplicate user terms while preserving their display form."""
    if values is None:
        return ()
    if isinstance(values, str):
        candidates: list[Any] = values.splitlines()
    elif isinstance(values, (list, tuple)):
        candidates = list(values)
    else:
        raise ValueError("登録語は1行ごとの文字列または配列で指定してください。")

    terms: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not isinstance(value, str):
            raise ValueError("登録語には文字列だけを指定してください。")
        # NFC preserves the user's intended visible notation while avoiding
        # duplicates created solely by composed/decomposed Unicode forms.
        term = unicodedata.normalize("NFC", value).strip()
        term = re.sub(r"[\t\r\n]+", " ", term)
        if not term:
            continue
        if len(term) > CUSTOM_VOCABULARY_MAX_TERM_LENGTH:
            raise ValueError(
                f"登録語は1語あたり{CUSTOM_VOCABULARY_MAX_TERM_LENGTH}文字以内にしてください。"
            )
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) > CUSTOM_VOCABULARY_MAX_TERMS:
            raise ValueError(
                f"登録語は{CUSTOM_VOCABULARY_MAX_TERMS}語までにしてください。"
            )
    return tuple(terms)


def load_custom_vocabulary() -> tuple[str, ...]:
    """Read the local, application-wide recognition vocabulary safely."""
    with custom_vocabulary_lock:
        try:
            payload = json.loads(CUSTOM_VOCABULARY_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ()
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            # A damaged settings file must never prevent transcription. The UI
            # will show an empty list, which users can save again if desired.
            return ()
    if not isinstance(payload, dict):
        return ()
    try:
        return normalize_custom_vocabulary(payload.get("terms", []))
    except ValueError:
        return ()


def save_custom_vocabulary(values: Any) -> tuple[str, ...]:
    """Persist the recognition vocabulary as non-secret local settings."""
    terms = normalize_custom_vocabulary(values)
    payload = {"version": 1, "terms": list(terms)}
    with custom_vocabulary_lock:
        atomic_write_text(
            CUSTOM_VOCABULARY_FILE,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return terms


def whisper_vocabulary_prompt(values: Any) -> str:
    """Build a compact initial prompt accepted by Whisper and WhisperX."""
    terms = normalize_custom_vocabulary(values)
    if not terms:
        return ""
    prefix = "用語・固有名詞: "
    suffix = "。"
    available = WHISPER_VOCABULARY_PROMPT_MAX_CHARACTERS - len(prefix) - len(suffix)
    selected: list[str] = []
    used = 0
    for term in terms:
        addition = len(term) + (1 if selected else 0)
        if used + addition > available:
            break
        selected.append(term)
        used += addition
    return f"{prefix}{'、'.join(selected)}{suffix}" if selected else ""


_audio_processor = transcription_audio.AudioProcessor(
    AUDIO_PREPROCESS_PRESETS, WHISPER_SAMPLE_RATE, run_cancellable_subprocess
)
audio_preprocess_label = _audio_processor.label
audio_preprocess_filters = _audio_processor.filters
run_audio_preprocess = _audio_processor.preprocess
run_audio_interval_preprocess = _audio_processor.preprocess_interval


TRANSCRIPT_FINISHING_MODES = transcript_formatting.TRANSCRIPT_FINISHING_MODES
TRANSCRIPT_FORMATTING_VERSION = transcript_formatting.TRANSCRIPT_FORMATTING_VERSION
normalize_transcript_punctuation = transcript_formatting.normalize_transcript_punctuation


def transcript_formatting_result(
    original_segments: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    *,
    mode: str,
    audio_preprocess: str = "none",
    speaker_names: dict[str, str] | None = None,
    speaker_diagnostics: dict[str, Any] | None = None,
    speaker_repair_summary: dict[str, int] | None = None,
    finishing_stages: dict[str, str] | None = None,
    ai_usage: dict[str, Any] | None = None,
    jev_usage: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return transcript_formatting.transcript_formatting_result(
        original_segments, segments, mode=mode, audio_preprocess=audio_preprocess,
        speaker_names=speaker_names, speaker_diagnostics=speaker_diagnostics,
        speaker_repair_summary=speaker_repair_summary, finishing_stages=finishing_stages,
        ai_usage=ai_usage, jev_usage=jev_usage,
        normalize_ai_usage=normalize_ai_usage, safe_token_count=safe_token_count,
        normalize_detected_speaker_name=normalize_detected_speaker_name,
    )


# Transcript output composition boundary.
def manual_output_directory(source_name: str, item_id: str) -> Path:
    return outputs.manual_output_directory(
        source_name, item_id, output_root=DEFAULT_OUTPUT_DIRECTORY
    )


def media_metadata_session_date(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> str:
    return outputs.media_metadata_session_date(
        source_path, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def session_profile_from_media(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, str]:
    return outputs.session_profile_from_media(
        source_path, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def probe_video_dimensions(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[int, int]:
    return outputs.probe_video_dimensions(
        source_path, check_cancelled, run_subprocess=run_cancellable_subprocess
    )


def burn_ass_subtitles_into_video(
    source_path: Path,
    ass_path: Path,
    target: Path,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    return outputs.burn_ass_subtitles_into_video(
        source_path, ass_path, target, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def write_subtitled_video_assets(
    source_path: Path,
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> list[Path]:
    return outputs.write_subtitled_video_assets(
        source_path, source_name, output_dir, segments, speaker_names,
        speaker_profiles, check_cancelled,
        run_subprocess=run_cancellable_subprocess, is_video_path=is_video_path,
    )


def write_outputs(*args: Any, **kwargs: Any) -> list[Path]:
    kwargs.setdefault("write_word_cloud", write_word_cloud)
    kwargs.setdefault("emotion_csv_text", emotion_csv_text)
    return outputs.write_outputs(*args, **kwargs)


# AIST emotion analysis composition boundary.
def emotion_csv_text(segments: list[dict[str, Any]], speaker_names: dict[str, str]) -> str:
    return emotion_analysis.emotion_csv_text(
        segments, speaker_names, csv_safe=analysis_csv_safe
    )


def extract_emotion_segment_wavs(
    audio_path: Path,
    segments: list[dict[str, Any]],
    work_dir: Path,
    check_cancelled: Callable[[], None],
) -> tuple[Path, list[dict[str, Any]]]:
    return emotion_analysis.extract_emotion_segment_wavs(
        audio_path, segments, work_dir, check_cancelled,
        run_subprocess=run_cancellable_subprocess,
    )


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
    return emotion_analysis.run_aist_emotion_analysis(
        audio_path, segments, model_choice, hf_token, device, work_dir, status,
        check_cancelled,
        runtime_directory=RUNTIME_DIRECTORY,
        run_subprocess=run_cancellable_subprocess,
    )


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


def extract_lmstudio_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LM Studio API 応答に候補がありません。")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    text = message.get("content")
    if isinstance(text, str) and text.strip():
        return text
    raise RuntimeError("LM Studio API 応答に出力テキストがありません。")


def safe_token_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    if not math.isfinite(float(value)):
        return 0
    return max(0, min(10**12, int(value)))


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
    elif provider == "lmstudio":
        raw = response.get("usage")
        usage = raw if isinstance(raw, dict) else {}
        prompt_details = usage.get("prompt_tokens_details")
        completion_details = usage.get("completion_tokens_details")
        prompt_details = prompt_details if isinstance(prompt_details, dict) else {}
        completion_details = completion_details if isinstance(completion_details, dict) else {}
        result = {
            "provider": provider,
            "model": model,
            "request_count": 1,
            "input_tokens": safe_token_count(usage.get("prompt_tokens")),
            "output_tokens": safe_token_count(usage.get("completion_tokens")),
            "total_tokens": safe_token_count(usage.get("total_tokens")),
            "cached_tokens": safe_token_count(
                prompt_details.get("cached_tokens") or prompt_details.get("cached_tokens_count")
            ),
            "reasoning_tokens": safe_token_count(completion_details.get("reasoning_tokens")),
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


def lmstudio_reasoning_settings(base_url: str, api_key: str, model: str) -> dict:
    endpoint = lmstudio_base_url(base_url).removesuffix('/v1') + '/api/v1/models'
    request_object = urllib.request.Request(endpoint, headers=lmstudio_headers(api_key))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect()).open(request_object, timeout=3) as response:
            payload = json.loads(response.read(2 * 1024 * 1024).decode('utf-8'))
        for row in payload.get('models', []):
            identifiers = [row.get('key')] + [r.get('id') for r in row.get('loaded_instances', [])]
            if model in identifiers:
                return row.get('capabilities', {}).get('reasoning', {})
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return {}


# AI transport composition boundary.
def lmstudio_base_url(value: str) -> str:
    return ai_client.lmstudio_base_url(
        value, LMSTUDIO_DEFAULT_BASE_URL, LMSTUDIO_LOOPBACK_HOSTS
    )


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int = 240,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    return ai_client.post_json(
        url, headers, payload, worker_file=AI_HTTP_WORKER_FILE,
        run_subprocess=run_cancellable_subprocess, timeout=timeout,
        check_cancelled=check_cancelled,
    )


def normalize_ai_usage(value: Any) -> dict[str, Any]:
    return ai_client.normalize_ai_usage(value, AI_MODEL_PROVIDERS)


def merge_ai_usage(current_value: Any, sample_value: Any) -> dict[str, Any]:
    return ai_client.merge_ai_usage(current_value, sample_value, AI_MODEL_PROVIDERS)


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
    base_url: str = "",
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    return ai_client.call_ai_json(
        provider, api_key, model, system_prompt, user_prompt, schema_name, schema,
        post=post_json, lmstudio_base=lmstudio_base_url,
        lmstudio_model_id=lmstudio_model_id,
        lmstudio_reasoning=lmstudio_reasoning_settings,
        extract_openai=extract_openai_text, extract_google=extract_google_text,
        extract_lmstudio=extract_lmstudio_text,
        providers=AI_MODEL_PROVIDERS, check_cancelled=check_cancelled,
        usage_callback=usage_callback, base_url=base_url, ai_efforts=ai_efforts,
    )


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


def speaker_registry_identity_key(value: Any) -> str:
    """Return a conservative comparison key for a person name.

    This deliberately supports only harmless formatting differences.  It must
    not turn a partial or similar-looking name into a global-person match.
    """
    normalized = unicodedata.normalize("NFKC", clean_single_line(value, 120)).casefold()
    return re.sub(r"[\s\u3000・.．,，、。]", "", normalized)


def link_detected_speakers_to_registry(
    speaker_profiles: dict[str, dict[str, Any]],
    speaker_names: dict[str, str],
    registry_records: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Link verified self-introductions to one registered person when safe.

    A name with no unique active registry match remains scoped to this
    conversation as a temporary single-group speaker.  We intentionally do
    not create a global registry record or guess from a partial-name match.
    """
    if not speaker_names:
        return speaker_profiles, {
            "linked": {}, "temporary": {}, "ambiguous": {}, "changed": False,
        }
    records = registry_records if registry_records is not None else list_speaker_registry(
        include_inactive=False
    )
    matches_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict) or record.get("active") is False:
            continue
        keys = {
            speaker_registry_identity_key(record.get(field))
            for field in ("display_name", "pseudonym")
        }
        for key in keys - {""}:
            matches_by_name[key].append(record)

    linked: dict[str, str] = {}
    temporary: dict[str, str] = {}
    ambiguous: dict[str, list[str]] = {}
    changed = False
    for label, raw_name in speaker_names.items():
        name = clean_single_line(raw_name, 120)
        profile = speaker_profiles.get(str(label))
        if not name or not isinstance(profile, dict):
            continue
        # A user-selected link is authoritative; auto-identification must not
        # replace it based on a name collision.
        if clean_single_line(profile.get("global_speaker_id"), 80):
            if profile.get("registration_status") != "registered":
                profile["registration_status"] = "registered"
                changed = True
            continue
        candidates = matches_by_name.get(speaker_registry_identity_key(name), [])
        unique = {str(item.get("id") or ""): item for item in candidates if item.get("id")}
        if len(unique) == 1:
            record = next(iter(unique.values()))
            profile["global_speaker_id"] = str(record["id"])
            profile["registration_status"] = "registered"
            profile["display_name"] = (
                clean_single_line(record.get("pseudonym"), 120)
                or clean_single_line(record.get("display_name"), 120)
                or name
            )
            profile["session_role"] = clean_single_line(
                record.get("default_role"), 40
            ) if clean_single_line(record.get("default_role"), 40) in SPEAKER_ROLES else "participant"
            for field in ("organization", "department", "job_title"):
                profile[field] = clean_single_line(record.get(field), 200)
            attributes = record.get("attributes")
            profile["conditions"] = "; ".join(
                f"{clean_single_line(key, 120)}={clean_multiline(value, 2000)}"
                for key, value in attributes.items()
                if clean_single_line(key, 120)
            ) if isinstance(attributes, dict) else ""
            linked[str(label)] = str(record["id"])
            changed = True
        else:
            if profile.get("global_speaker_id") or profile.get("registration_status") != "temporary_single_group":
                profile["global_speaker_id"] = ""
                profile["registration_status"] = "temporary_single_group"
                changed = True
            profile["display_name"] = name
            temporary[str(label)] = name
            if len(unique) > 1:
                ambiguous[str(label)] = sorted(unique)
    return speaker_profiles, {
        "linked": linked,
        "temporary": temporary,
        "ambiguous": ambiguous,
        "changed": changed,
    }


def register_detected_speakers(
    speaker_profiles: dict[str, dict[str, Any]],
    speaker_names: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Link verified introductions and register unambiguous new speakers.

    This is deliberately called only from the AI self-introduction workflow,
    never from a manually edited display name.  Existing duplicate or inactive
    records remain for a person to resolve rather than creating another global
    speaker with the same name.
    """
    if not speaker_names:
        profiles, summary = link_detected_speakers_to_registry(
            speaker_profiles, speaker_names, []
        )
        return profiles, {
            **summary,
            "created": {},
            "inactive": {},
            "duplicate_identifications": {},
        }

    # The registry's ordinary editor uses the same lock, so a transcription
    # cannot create a duplicate while someone is saving speaker management.
    with library_write_lock:
        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            revision = speaker_registry_revision(connection)
            all_records = [
                speaker_registry_public(row)
                for row in speaker_registry_rows(connection, include_inactive=True)
            ]
            active_records = [
                record for record in all_records if record.get("active") is not False
            ]
            profiles, summary = link_detected_speakers_to_registry(
                speaker_profiles, speaker_names, active_records
            )

            inactive_matches: dict[str, list[str]] = defaultdict(list)
            for record in all_records:
                if record.get("active") is not False:
                    continue
                for field in ("display_name", "pseudonym"):
                    key = speaker_registry_identity_key(record.get(field))
                    if key and record.get("id"):
                        inactive_matches[key].append(str(record["id"]))

            labels_by_name: dict[str, list[str]] = defaultdict(list)
            for label, name in summary["temporary"].items():
                key = speaker_registry_identity_key(name)
                if key:
                    labels_by_name[key].append(label)

            inactive: dict[str, list[str]] = {}
            duplicate_identifications: dict[str, list[str]] = {}
            new_records: list[tuple[str, str, dict[str, Any]]] = []
            for label, name in summary["temporary"].items():
                key = speaker_registry_identity_key(name)
                if not key:
                    continue
                if label in summary["ambiguous"]:
                    continue
                if inactive_matches.get(key):
                    inactive[label] = sorted(set(inactive_matches[key]))
                    continue
                duplicate_labels = sorted(labels_by_name[key])
                if len(duplicate_labels) > 1:
                    duplicate_identifications[label] = duplicate_labels
                    continue
                record = normalize_speaker_registry_record({
                    "id": f"speaker_auto_{uuid.uuid4().hex}",
                    "display_name": name,
                    "default_role": "participant",
                    "active": True,
                })
                new_records.append((label, name, record))

            created: dict[str, str] = {}
            if new_records:
                now = utc_now_iso()
                for label, _name, record in new_records:
                    persist_speaker_registry_record(connection, record, None, now)
                    created[label] = record["id"]
                connection.execute(
                    "UPDATE application_metadata SET value = ? WHERE key = ?",
                    (str(revision + 1), "speaker_registry_revision"),
                )
                all_records.extend(record for _label, _name, record in new_records)

        if created:
            # Reuse the normal profile mapping so newly registered names get
            # the same display and role semantics as pre-existing speakers.
            profiles, refreshed = link_detected_speakers_to_registry(
                profiles, speaker_names, all_records
            )
            summary = {
                **refreshed,
                "changed": bool(summary["changed"] or refreshed["changed"]),
            }

    return profiles, {
        **summary,
        "created": created,
        "inactive": inactive,
        "duplicate_identifications": duplicate_identifications,
    }


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
    base_url: str = "",
    ai_efforts: dict | None = None,
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
        base_url,
        **({"ai_efforts": ai_efforts} if ai_efforts else {}),
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
            base_url,
        **({"ai_efforts": ai_efforts} if ai_efforts else {}),
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


# The composition boundary passes dependencies into the Flask-free service.
def clean_segments_with_ai(
    segments: list[dict[str, Any]], provider: str, api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    outline: dict[str, Any] | None = None, ai_efforts: dict | None = None,
) -> list[dict[str, Any]]:
    return ai_transcript_finishing.clean(
        segments, provider, api_key, model, status, check_cancelled,
        call_json=call_ai_json, finish=finish_clean_transcript,
        usage_callback=usage_callback, base_url=base_url, outline=outline,
        ai_efforts=ai_efforts,
    )


def review_segments_with_jev(
    segments: list[dict[str, Any]], api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None],
    outline: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return ai_transcript_finishing.review_with_jev(
        segments, api_key, model, status, check_cancelled,
        clean_single_line=clean_single_line, default_model=JEV_DEFAULT_MODEL,
        post=post_json, review=review_transcript_with_jev, outline=outline,
    )


def clean_recommended_segments_with_ai(
    segments: list[dict[str, Any]], reviews: dict[str, dict[str, Any]],
    provider: str, api_key: str, model: str, status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None,
    base_url: str = "", ai_efforts: dict | None = None, effort: str = "medium",
    outline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return ai_transcript_finishing.repair_recommended(
        segments, reviews, provider, api_key, model, status, check_cancelled,
        call_json=call_ai_json, repair=finish_repair_recommended_segments,
        usage_callback=usage_callback, base_url=base_url, ai_efforts=ai_efforts,
        effort=effort, outline=outline,
    )


def classify_segments_with_jev(
    segments: list[dict[str, Any]], topics: list[dict[str, str]], api_key: str,
    model: str, status: Callable[[str], None] = lambda _message: None,
    check_cancelled: Callable[[], None] = lambda: None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return ai_transcript_finishing.classify_with_jev(
        segments, topics, api_key, model, clean_single_line=clean_single_line,
        default_model=JEV_DEFAULT_MODEL, post=post_json, classify=classify_with_jev,
        status=status, check_cancelled=check_cancelled,
    )


def create_outline_with_ai(
    segments: list[dict[str, Any]], speaker_names: dict[str, str],
    provider: str, api_key: str, model: str, status: Callable[[str], None],
    check_cancelled: Callable[[], None],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    return ai_transcript_finishing.create_outline(
        segments, speaker_names, provider, api_key, model, status, check_cancelled,
        call_json=call_ai_json, create=finish_create_outline, now_iso=utc_now_iso,
        usage_callback=usage_callback, base_url=base_url, ai_efforts=ai_efforts,
    )


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
    dependencies = {
        "CONVERSATION_MODES": CONVERSATION_MODES,
        "DIARIZATION_MODEL": DIARIZATION_MODEL,
        "MAX_LOG_LINES": MAX_LOG_LINES,
        "NORMAL_NO_SPEECH_THRESHOLD": NORMAL_NO_SPEECH_THRESHOLD,
        "NORMAL_VAD_OFFSET": NORMAL_VAD_OFFSET,
        "NORMAL_VAD_ONSET": NORMAL_VAD_ONSET,
        "TRIPLE_PASS_GAP_CONTEXT_SECONDS": TRIPLE_PASS_GAP_CONTEXT_SECONDS,
        "TRIPLE_PASS_MIN_GAP_SECONDS": TRIPLE_PASS_MIN_GAP_SECONDS,
        "TranscriptionReporter": TranscriptionReporter,
        "UPLOAD_DIRECTORY": UPLOAD_DIRECTORY,
        "WHISPER_SAMPLE_RATE": WHISPER_SAMPLE_RATE,
        "aist_emotion_model_keys": aist_emotion_model_keys,
        "apply_speaker_identity_repairs": apply_speaker_identity_repairs,
        "attach_jev_comparison": attach_jev_comparison,
        "audio_preprocess_label": audio_preprocess_label,
        "build_emotion_analysis_summary": build_emotion_analysis_summary,
        "build_meeting_minutes": build_meeting_minutes,
        "clean_recommended_segments_with_ai": clean_recommended_segments_with_ai,
        "clean_segments_with_ai": clean_segments_with_ai,
        "cleanup_uncommitted_job_artifacts": cleanup_uncommitted_job_artifacts,
        "commit_staged_media": commit_staged_media,
        "configure_huggingface_hub_compatibility": configure_huggingface_hub_compatibility,
        "configure_speechbrain_lazy_import_compatibility": configure_speechbrain_lazy_import_compatibility,
        "create_diarization_pipeline": create_diarization_pipeline,
        "create_outline_with_ai": create_outline_with_ai,
        "detect_speaker_names_with_ai": detect_speaker_names_with_ai,
        "diarization_access_error_message": diarization_access_error_message,
        "display_time": display_time,
        "ensure_segment_ids": ensure_segment_ids,
        "find_long_asr_gaps": find_long_asr_gaps,
        "is_diarization_access_error": is_diarization_access_error,
        "is_video_path": is_video_path,
        "jobs_lock": jobs_lock,
        "json_load": json_load,
        "make_display_segments": make_display_segments,
        "merge_ai_usage": merge_ai_usage,
        "merge_supplemental_asr_segments": merge_supplemental_asr_segments,
        "normalize_ai_usage": normalize_ai_usage,
        "normalize_asr_segments": normalize_asr_segments,
        "normalize_conversation_speaker_profiles": normalize_conversation_speaker_profiles,
        "normalize_meeting_minutes": normalize_meeting_minutes,
        "obsidian_workbench": obsidian_workbench,
        "offset_asr_segments_to_gap": offset_asr_segments_to_gap,
        "path_entry_exists": path_entry_exists,
        "publish_input_vault": publish_input_vault,
        "publish_meeting_minutes_to_obsidian": publish_meeting_minutes_to_obsidian,
        "register_detected_speakers": register_detected_speakers,
        "review_segments_with_jev": review_segments_with_jev,
        "row_segments": row_segments,
        "row_session_profile": row_session_profile,
        "row_speaker_profiles": row_speaker_profiles,
        "run_aist_emotion_analysis": run_aist_emotion_analysis,
        "run_audio_interval_preprocess": run_audio_interval_preprocess,
        "run_audio_preprocess": run_audio_preprocess,
        "safe_output_stem": safe_output_stem,
        "safe_token_count": safe_token_count,
        "session_profile_from_media": session_profile_from_media,
        "stage_media_archive": stage_media_archive,
        "transcript_formatting_result": transcript_formatting_result,
        "update_job": update_job,
        "upsert_library_item": upsert_library_item,
        "whisper_vault_settings": whisper_vault_settings,
        "whisper_vocabulary_prompt": whisper_vocabulary_prompt,
        "write_outputs": write_outputs,
        "write_subtitled_video_assets": write_subtitled_video_assets,
    }
    transcription_job_runner.run_transcription_job(job, options, dependencies)


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
        segment["text"] = text_value
        if raw.get("time_unknown") or any(raw.get(key) in (None, "") for key in ("start", "end")):
            segment["time_unknown"] = True
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
    return sorted(normalized, key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0)))) if all(
        preparation.valid_time(item) for item in normalized
    ) else normalized


# Kushinada training corpus composition boundary.
def _training_store() -> training_corpus.TrainingStore:
    # Built per call: the corpus paths are module-level configuration that
    # tests and alternate data directories rebind after import.
    return training_corpus.TrainingStore(
        directory=TRAINING_DIRECTORY,
        audio_directory=TRAINING_AUDIO_DIRECTORY,
        jsonl_file=TRAINING_JSONL_FILE,
        manifest_file=TRAINING_MANIFEST_FILE,
        lock=training_lock,
        connect=lambda: database_connection(),
        logger=app.logger,
    )


def extract_training_clip(
    media_path: Path | None, item_id: str, event_id: str, segment: dict[str, Any]
) -> Path | None:
    return training_corpus.extract_training_clip(
        media_path, item_id, event_id, segment, store=_training_store()
    )


def write_training_exports(events: list[dict[str, Any]]) -> None:
    training_corpus.write_training_exports(events, store=_training_store())


def legacy_training_events() -> list[dict[str, Any]]:
    return training_corpus.legacy_training_events(store=_training_store())


def cleanup_unreferenced_training_clips(events: list[dict[str, Any]]) -> None:
    training_corpus.cleanup_unreferenced_training_clips(events, store=_training_store())


def repair_training_artifacts() -> None:
    training_corpus.repair_training_artifacts(store=_training_store())


def refresh_training_exports() -> list[dict[str, Any]]:
    return training_corpus.refresh_training_exports(store=_training_store())


def prepare_training_corrections(*args: Any, **kwargs: Any):
    kwargs.setdefault("store", _training_store())
    return training_corpus.prepare_training_corrections(*args, **kwargs)


def record_training_corrections(*args: Any, **kwargs: Any) -> int:
    kwargs.setdefault("store", _training_store())
    return training_corpus.record_training_corrections(*args, **kwargs)

def update_library_from_payload(item_id: str, payload: Any) -> dict[str, Any]:
    return analysis_commands().update_item(item_id, payload)


def vault_registry():
    from .vault_registry import VaultRegistry
    return VaultRegistry(DATABASE_FILE, PROJECT_DIRECTORY / "docs" / "program-vault")


def vault_publications() -> VaultPublicationService:
    return VaultPublicationService(
        registry=vault_registry,
        database_connection=database_connection,
        preparation_view=preparation.view,
        row_segments=row_segments,
        row_session_profile=row_session_profile,
        database_error=sqlite3.Error,
        warn=lambda message, exc: app.logger.warning("%s: %s", message, exc),
    )


def publish_input_vault(row, whisper: dict[str, Any] | None = None, *, source_kind: str | None = None) -> None:
    vault_publications().publish_input(row, whisper, source_kind=source_kind)


def retire_input_vault(item_id: str) -> None:
    vault_publications().retire_input(item_id)


def whisper_vault_settings(options: JobOptions, language: str | None) -> dict[str, Any]:
    return whisper_settings(options, language, diarization_model=DIARIZATION_MODEL)


def _update_library_from_payload_locked(
    item_id: str,
    payload: Any,
    *,
    ai_usage_override: dict[str, Any] | None = None,
    record_training: bool = True,
    outline_override: dict[str, Any] | None = None,
    check_cancelled: Callable[[], None] | None = None,
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

    outline = outline_override if outline_override is not None else json_load(row["outline_json"], None)
    meeting_minutes = (
        build_meeting_minutes(new_segments, new_names, session_profile, outline)
        if session_profile.get("session_type") == "meeting"
        else {}
    )
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
        formatting_result = json_load(row["formatting_result_json"], {})
        if isinstance(formatting_result, dict) and formatting_result:
            formatting_result = dict(formatting_result)
            formatting_result["manual_edit_status"] = "edited_after_formatting"
        else:
            formatting_result = {}
        staged_files = write_outputs(
            source_name, staging_dir, new_segments, row["language"], new_names,
            bool(row["write_srt"]), True, outline, emotion_analysis, speaker_profiles,
            meeting_minutes, check_cancelled,
            formatting_result=formatting_result,
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
            if check_cancelled is not None:
                check_cancelled()
            with promote_staged_files(staging_dir, output_dir, staged_files) as files:
                with database_connection() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if check_cancelled is not None:
                        check_cancelled()
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
                        meeting_minutes=meeting_minutes,
                        formatting_result=formatting_result,
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
            job.outline = outline
            job.revision_count = int(updated["revision_count"] or 0)
            job.ai_usage = json_load(updated["ai_usage_json"], {})
    result = library_public(updated)
    result["learning_events"] = learning_events
    result["learning_warning"] = learning_warning
    result["output_warning"] = output_warning
    return result


def recover_delete_quarantines() -> list[str]:
    return edit_transactions.recover_delete_quarantines(
        connect=database_connection,
        media_directory=MEDIA_DIRECTORY,
        thumbnail_directory=THUMBNAIL_DIRECTORY,
    )


def discover_edit_transaction_staging_dirs(
    *,
    additional_output_roots: list[Path] | None = None,
    include_database_outputs: bool = True,
) -> list[Path]:
    return edit_transactions.discover_edit_transaction_staging_dirs(
        additional_output_roots=additional_output_roots,
        include_database_outputs=include_database_outputs,
        connect=database_connection,
        output_root=DEFAULT_OUTPUT_DIRECTORY,
    )


def recover_edit_transactions() -> list[str]:
    return edit_transactions.recover_edit_transactions(
        connect=database_connection, output_root=DEFAULT_OUTPUT_DIRECTORY
    )


def reconcile_edit_transactions_before_mutation(
    item_id: str,
    library_item: sqlite3.Row,
) -> tuple[list[str], list[Path]]:
    return edit_transactions.reconcile_edit_transactions_before_mutation(
        item_id, library_item,
        connect=database_connection, output_root=DEFAULT_OUTPUT_DIRECTORY,
    )


def reconcile_edit_transactions_before_delete(
    item_id: str,
    library_item: sqlite3.Row,
) -> tuple[list[str], list[Path]]:
    return edit_transactions.reconcile_edit_transactions_before_delete(
        item_id, library_item,
        connect=database_connection, output_root=DEFAULT_OUTPUT_DIRECTORY,
    )

def initialize_application() -> None:
    application_lifecycle().initialize()


register_system_routes(
    app,
    app_name=APP_NAME,
    product_name=PRODUCT_NAME,
    app_version=APP_VERSION,
    app_creator=APP_CREATOR,
    token_file=lambda: TOKEN_FILE,
    default_output_directory=lambda: DEFAULT_OUTPUT_DIRECTORY,
    runtime_info=runtime_info,
    local_llm_label=local_llm_label,
    local_llm_short_label=local_llm_short_label,
    get_machine_profile=lambda: get_machine_profile(),
    load_token_config=lambda path: load_token_config(path),
    lmstudio_connection_status=lmstudio_connection_status,
    local_path_access_allowed=local_path_access_allowed,
    load_custom_vocabulary=load_custom_vocabulary,
    save_custom_vocabulary=save_custom_vocabulary,
    available_ai_models=lambda provider, config: available_ai_models(provider, config),
    update_token_model=lambda provider, model, path: update_token_model(provider, model, path),
    system_activity_snapshot=lambda: system_activity_snapshot(),
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
    group_filter = request.args.get("group", "").strip()
    sort_key = request.args.get("sort", "updated_desc").strip()
    with database_connection() as connection:
        rows = connection.execute("SELECT * FROM library_items ORDER BY updated_at DESC").fetchall()
        group_rows = connection.execute(
            """
            SELECT g.id, g.name, g.created_at, g.updated_at,
                   COUNT(items.id) AS item_count
            FROM library_groups AS g
            LEFT JOIN library_items AS items ON items.group_id = g.id
            GROUP BY g.id, g.name, g.created_at, g.updated_at
            ORDER BY g.name COLLATE NOCASE, g.created_at
            """
        ).fetchall()

    groups = [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "item_count": int(row["item_count"] or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in group_rows
    ]
    group_names = {group["id"]: group["name"] for group in groups}

    all_speakers: set[str] = set()
    all_emotions: set[str] = set()
    candidates: list[tuple[sqlite3.Row, int, list[str], list[str], str]] = []
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
        row_group_id = str(row["group_id"] or "")
        if group_filter == "__ungrouped__" and row_group_id:
            continue
        if group_filter and group_filter != "__ungrouped__" and row_group_id != group_filter:
            continue
        candidates.append((row, match_count, speakers, emotions, group_names.get(row_group_id, "")))

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
    elif sort_key == "group":
        candidates.sort(key=lambda item: (
            not bool(item[4]), item[4].casefold(), str(item[0]["source_name"]).casefold()
        ))
    else:
        candidates.sort(key=lambda item: item[0]["updated_at"], reverse=True)
    return jsonify({
        "items": [
            library_public(row, full=False, match_count=count, group_name=group_name)
            for row, count, _, _, group_name in candidates
        ],
        "total": len(candidates),
        "groups": groups,
        "facets": {
            "speakers": sorted(all_speakers),
            "emotions": sorted(all_emotions),
            "groups": groups,
        },
    })


comparison_rate = interview_comparison.comparison_rate


def build_interview_comparison(
    rows: list[sqlite3.Row], *, allow_different_content: bool,
) -> dict[str, Any]:
    return interview_comparison.build_interview_comparison(
        rows, allow_different_content=allow_different_content,
        row_session_profile=row_session_profile,
        interview_comparison_identity=interview_comparison_identity,
        group_analysis_for_row=group_analysis_for_row,
        text_mining_counter=text_mining_counter,
    )


def interview_comparison_request(payload: Any) -> tuple[list[sqlite3.Row], bool]:
    """Validate a 2-8 interview selection and read the rows in the selected order."""
    if not isinstance(payload, dict) or not isinstance(payload.get("item_ids"), list):
        raise ComparisonRequestError("比較するインタビューを指定してください。")
    item_ids: list[str] = []
    for value in payload["item_ids"]:
        item_id = str(value or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item_id):
            raise ComparisonRequestError("比較対象のIDが正しくありません。")
        if item_id not in item_ids:
            item_ids.append(item_id)
    if not 2 <= len(item_ids) <= 8:
        raise ComparisonRequestError("比較するインタビューは2〜8件選択してください。")
    allow_different = payload.get("allow_different_content", False)
    if not isinstance(allow_different, bool):
        raise ComparisonRequestError("内容が異なる比較の指定が正しくありません。")
    with database_connection() as connection:
        placeholders = ",".join("?" for _ in item_ids)
        fetched = connection.execute(
            f"SELECT * FROM library_items WHERE id IN ({placeholders})", item_ids
        ).fetchall()
    by_id = {str(row["id"]): row for row in fetched}
    if any(item_id not in by_id for item_id in item_ids):
        raise ComparisonRequestError("比較対象のデータが見つかりません。", 404)
    return [by_id[item_id] for item_id in item_ids], allow_different


@app.post("/api/library/interview-comparison")
def compare_group_interviews():
    if request.content_length and request.content_length > 64 * 1024:
        return jsonify({"error": "比較対象の指定が大きすぎます。"}), 413
    try:
        with library_write_lock:
            rows, allow_different = interview_comparison_request(request.get_json(silent=True))
            result = build_interview_comparison(rows, allow_different_content=allow_different)
            result["input_fingerprints"] = {str(row["id"]): archive_source_stamp(row) for row in rows}
    except ComparisonRequestError as exc:
        return jsonify({"error": str(exc)}), exc.status
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 409
    except (OverflowError, sqlite3.Error):
        return jsonify({"error": "インタビュー比較を生成できません。"}), 500
    return jsonify(result)


@app.get("/api/library/interview-comparison/runs")
def list_interview_comparison_runs():
    store = analysis_archive_store()
    local = local_path_access_allowed()
    return jsonify({"runs": [{**store.public(run, local=local), "member_ids": store.members(run["id"])}
                             for run in store.list_comparisons()]})


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


def identify_library_speakers(
    item_id: str, *, provider: str, expected_revision: int
) -> dict[str, Any]:
    row = library_row(item_id)
    if row is None:
        raise SpeakerIdentificationRequestError("データが見つかりません。", 404)
    current_revision = int(row["revision_count"] or 0)
    if current_revision != expected_revision:
        raise SpeakerIdentificationRequestError(
            "別の画面でデータが更新されています。再読み込みしてください。",
            409,
            current_revision=current_revision,
        )
    segments = row_segments(row)
    if not segments:
        raise SpeakerIdentificationRequestError(
            "話者特定に使用できる発話がありません。", 400
        )

    try:
        token_config = load_token_config()
    except RuntimeError as exc:
        raise SpeakerIdentificationRequestError(str(exc), 503) from exc
    try:
        api_key, model = configured_ai_credentials(token_config, provider)
    except ValueError as exc:
        raise SpeakerIdentificationRequestError(str(exc), 400) from exc
    base_url = token_config.lmstudio_base_url if provider == "lmstudio" else ""
    if provider != "lmstudio" and not api_key:
        raise SpeakerIdentificationRequestError(
            f"tokens.json に {ai_provider_label(provider)} のAPIキーを設定してください。",
            400,
        )
    if not model:
        raise SpeakerIdentificationRequestError(
            local_llm_model_required_message(), 400
        )

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
            base_url=base_url,
        )
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise SpeakerIdentificationRequestError(
            "話者特定AIを実行できませんでした: "
            + public_diagnostic_text(str(exc), reveal_local_paths=False),
            502,
        ) from exc

    try:
        with library_write_lock:
            latest = library_row(item_id)
            if latest is None:
                raise SpeakerIdentificationRequestError(
                    "データが見つかりません。", 404
                )
            latest_revision = int(latest["revision_count"] or 0)
            if latest_revision != expected_revision:
                raise SpeakerIdentificationRequestError(
                    "AI処理中にデータが更新されました。結果を反映せず再読み込みします。",
                    409,
                    current_revision=latest_revision,
                )
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
            speaker_profiles, registration_summary = register_detected_speakers(
                speaker_profiles,
                applied_names,
            )
            combined_usage = merge_ai_usage(
                json_load(latest["ai_usage_json"], {}),
                run_usage,
            )
            repairs_applied = bool(
                repair_summary["aliased_segments"]
                or repair_summary["corrected_segments"]
            )
            if applied_names or repairs_applied or registration_summary["changed"]:
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
                # Same follow-up as an ordinary edit: stale analyses and the Input ledger.
                refresh_archive_index(item_id)
                publish_input_vault(library_row(item_id))
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
                "registration": registration_summary,
            }
            return result
    except TranscriptConflictError as exc:
        raise SpeakerIdentificationRequestError(
            str(exc), 409, current_revision=exc.current_revision
        ) from exc


def obsidian_workbench() -> ObsidianWorkbench:
    return ObsidianWorkbench(DATABASE_FILE)


def obsidian_workflows() -> ObsidianWorkflowService:
    """Build explicit dependencies for researcher-owned workbench operations."""
    return ObsidianWorkflowService(SimpleNamespace(
        sqlite_error=sqlite3.Error,
        workbench=obsidian_workbench,
        library_row=library_row,
        row_session_profile=row_session_profile,
        row_meeting_minutes=row_meeting_minutes,
        row_segments=row_segments,
        meeting_external_payload=meeting_external_payload,
        meeting_tasks_csv_text=meeting_tasks_csv_text,
        normalize_meeting_minutes=normalize_meeting_minutes,
        library_write_lock=library_write_lock,
        row_speaker_profiles=row_speaker_profiles,
        update_library_item_locked=_update_library_from_payload_locked,
        merge_ai_usage=merge_ai_usage,
        json_load=json_load,
        publish_input_vault=publish_input_vault,
        archive_ai_finishing=archive_ai_finishing,
        load_token_config=load_token_config,
        configured_ai_credentials=configured_ai_credentials,
        create_outline_with_ai=create_outline_with_ai,
        clean_segments_with_ai=clean_segments_with_ai,
        review_segments_with_jev=review_segments_with_jev,
        attach_jev_comparison=attach_jev_comparison,
        detect_speaker_names_with_ai=detect_speaker_names_with_ai,
        apply_speaker_identity_repairs=apply_speaker_identity_repairs,
    ))


def meeting_minutes_fingerprint(minutes: dict[str, Any]) -> str:
    return obsidian_workflows().meeting_minutes_fingerprint(minutes)


def publish_meeting_minutes_to_obsidian(row: sqlite3.Row) -> dict[str, Any]:
    return obsidian_workflows().publish_meeting_minutes(row)


def run_obsidian_finishing(action: str, state: dict, segments: list[dict],
                           context: dict, provider: str, check: Callable) -> dict:
    return obsidian_workflows().run_finishing(action, state, segments, context, provider, check)


def _spawn_obsidian_watcher() -> tuple[threading.Event, threading.Thread]:
    from .obsidian_migration import migrate
    return ObsidianWatcher(
        workbench=obsidian_workbench,
        engine=run_obsidian_finishing,
        migrate=migrate,
        log_exception=app.logger.exception,
    ).start()


_application_lifecycle: ApplicationLifecycle | None = None


def application_lifecycle() -> ApplicationLifecycle:
    global _application_lifecycle
    if _application_lifecycle is None:
        def repair_provenance() -> None:
            with database_connection() as connection:
                repair_output_import_provenance(connection)

        _application_lifecycle = ApplicationLifecycle(
            acquire_instance_lock=lambda: acquire_instance_lock(),
            release_instance_lock=lambda: release_instance_lock(),
            initialize_library=lambda: initialize_library(repair_provenance=False),
            recover_edits=lambda: recover_edit_transactions(),
            repair_provenance=repair_provenance,
            recover_deletes=lambda: recover_delete_quarantines(),
            repair_training=lambda: repair_training_artifacts(),
            cleanup_uploads=lambda: cleanup_orphaned_uploads(),
            import_outputs=lambda: import_existing_outputs(),
            report_edit_warning=lambda warning: print(
                f"Edit recovery warning: {warning}", file=sys.stderr
            ),
            report_delete_warning=lambda warning: print(
                f"Delete recovery warning: {warning}", file=sys.stderr
            ),
            spawn_watcher=lambda: _spawn_obsidian_watcher(),
        )
    return _application_lifecycle


def start_obsidian_watcher() -> tuple[threading.Event, threading.Thread]:
    return application_lifecycle().start_watcher()


def analysis_archive_store() -> AnalysisStore:
    return AnalysisStore(DATABASE_FILE, database_connection)


def archive_source_stamp(row) -> str:
    with database_connection() as connection:
        registry = connection.execute("SELECT value FROM application_metadata WHERE key='speaker_registry_revision'").fetchone()
        prep_revision, _ = preparation.load_state(connection, row["id"])
    keys = ("id", "source_name", "segments_json", "speaker_names_json", "speaker_profiles_json",
            "session_profile_json", "outline_json", "emotion_analysis_json", "revision_count",
            "analysis_revision", "analysis_config_json", "analysis_annotations_json")
    return archive_digest({"source": {key: row[key] for key in keys},
                           "preparation_revision": prep_revision,
                           "registry_revision": registry[0] if registry else "0"})


def archive_snapshot(row, analysis: dict) -> dict:
    return {"title": str(row["source_name"]), "conversation_id": str(row["id"]),
            "source_revision": int(row["revision_count"]), "analysis_revision": int(row["analysis_revision"]),
            "segments": analysis["segments"], "config": analysis.get("config", {}),
            "annotations": analysis.get("annotations", {}),
            "preparation": analysis.get("manual", {}).get("preparation", {}),
            "speakers": analysis.get("automatic", {}).get("speaker_metrics", []),
            "original_source": {"segments": row_segments(row),
                                "speaker_names": json_load(row["speaker_names_json"], {}),
                                "speaker_profiles": json_load(row["speaker_profiles_json"], {}),
                                "session_profile": row_session_profile(row)}}


def archive_group_analysis(row, analysis: dict, request_id: str, *, kind: str = "text_analysis",
                           kwic: dict | None = None, app_url: str = "http://127.0.0.1:7860",
                           check_cancelled: Callable[[], None] = lambda: None,
                           store: AnalysisStore | None = None) -> dict:
    datasets = {name: analysis_csv_rows(analysis, name) for name in ANALYSIS_CSV_FIELDS}
    if kwic is not None:
        datasets = {"kwic": (KWIC_FIELDS, kwic["hits"])}
    outline = json_load(row["outline_json"], None)
    ai = analysis.get("insights", {}).get("ai") or {}
    methods = method_results(analysis, datasets, outline=outline, kwic=kwic)
    if kwic is not None: methods = [m for m in methods if m["method_id"] == "kwic"]
    expert_hashes = method_experts.attach_method_reviews(methods, analysis)
    expert_hashes.update(method_experts.knowledge_hashes(analysis.get("experts")))
    parameters: dict[str, Any] = ({key: kwic[key] for key in ("query", "mode", "speaker")}
                                  if kwic is not None else analysis["config"])
    algorithms = {"automatic": analysis.get("algorithm_version"),
                  "insights": INSIGHT_VERSION, "finishing": FINISHING_VERSION,
                  "research": analysis.get("research", {}).get("algorithm_version"),
                  "engine": analysis.get("research", {}).get("linguistics", {}).get("engine", {}),
                  "experts": dict(sorted(expert_hashes.items()))}
    if kind == "transformer_topics":
        transformer_result = analysis.get("transformer", {}).get("result") or {}
        parameters = {"analysis": analysis["config"],
                      "transformer": transformer_result.get("parameters", {})}
        algorithms["transformer"] = transformer_result.get("algorithm_version", "")
    result = {"schema_version": 1, "parameters": parameters,
              "algorithms": algorithms,
              "ai_request_id": ai.get("request_id", ""), "methods": methods,
              "analysis": analysis if kwic is None else {"kwic": kwic}}
    return (store or analysis_archive_store()).save(item_id=str(row["id"]), kind=kind,
        snapshot=archive_snapshot(row, analysis), result=result, datasets=datasets,
        request_id=request_id, input_fingerprint=archive_source_stamp(row),
        source_revision=int(row["revision_count"]), analysis_revision=int(row["analysis_revision"]),
        app_url=app_url, provider=ai.get("provider", "") if kind == "ai_insights" else "",
        model=ai.get("model", "") if kind == "ai_insights" else "", check_cancelled=check_cancelled)


def archive_segment_classification(
    row: sqlite3.Row, analysis: dict[str, Any], classification: dict[str, Any],
    request_id: str, *, app_url: str = "http://127.0.0.1:7860",
) -> dict[str, Any]:
    """Persist one immutable proposal run without changing manual annotations."""
    analysis_with_result = dict(analysis)
    analysis_with_result["segment_classification"] = {
        "result": classification,
        "stale": False,
        "summary": segment_classification_summary(classification),
        "dialogue_acts": DIALOGUE_ACTS,
    }
    datasets = {
        name: analysis_csv_rows(analysis_with_result, name)
        for name in ("segment_classifications", "segment_classification_crosstabs")
    }
    classification_state = analysis_with_result["segment_classification"]
    methods = method_results(
        analysis_with_result, datasets, classification=classification_state
    )
    methods = [value for value in methods if value["method_id"] == "segment_classification"]
    llm_source = (classification.get("sources") or {}).get("llm") or {}
    usage = llm_source.get("usage") or {}
    result = {
        "schema_version": 1,
        "parameters": {
            "use_jev": bool(llm_source.get("available")),
            "topic_candidate_count": len(segment_classification_topic_candidates(
                analysis.get("config", {}).get("codebook", [])
            )),
            "classification_fingerprint": str(classification.get("fingerprint") or ""),
        },
        "algorithms": {
            "segment_classification": SEGMENT_CLASSIFICATION_VERSION,
            "template": SEGMENT_CLASSIFICATION_VERSION,
            "transformer": ((classification.get("sources") or {}).get("transformer") or {}).get("algorithm_version", ""),
        },
        "methods": methods,
        "classification": classification,
        "usage": usage,
    }
    return analysis_archive_store().save(
        item_id=str(row["id"]), kind="segment_classification",
        snapshot=archive_snapshot(row, analysis_with_result), result=result,
        datasets=datasets, request_id=request_id,
        input_fingerprint=archive_source_stamp(row),
        source_revision=int(row["revision_count"]),
        analysis_revision=int(row["analysis_revision"]), app_url=app_url,
        provider="typesafe" if llm_source.get("available") else "",
        model=str(usage.get("model") or ""),
    )


def archive_ai_finishing(row, original_segments: list[dict], stages: dict, provider: str,
                         model: str, usage: dict, context_outline: dict | None = None,
                         jev_usage: dict | None = None,
                         request_id: str | None = None) -> dict:
    segments = row_segments(row)
    names = json_load(row["speaker_names_json"], {})
    display = [{**s, "speaker_name": names.get(s.get("speaker"), s.get("speaker", "UNKNOWN"))} for s in segments]
    jev_rows = jev_comparison_rows(segments)
    agreement_counts = Counter(str(row.get("agreement") or "") for row in jev_rows)
    jev_details = ({
        "review_version": JEV_REVIEW_VERSION,
        "model": str(jev_rows[0].get("jev_model") or JEV_DEFAULT_MODEL),
        "usage": jev_usage or {},
        "decision_labels": ["correction_needed", "no_correction_needed"],
        "reviewed_segment_count": len(jev_rows),
        "agreement_counts": dict(agreement_counts),
    } if jev_rows else {})
    details = {"prompt_version": FINISHING_VERSION, "provider": provider, "model": model,
               "usage": usage, "stages": stages, "original_segments": original_segments,
               "changes": finishing_changes(original_segments, segments),
               "context_outline": context_outline, "jev_comparison": jev_details}
    datasets = {"ai_changes": (["segment_id", "start", "end", "before_text", "after_text",
                                 "before_speaker", "after_speaker", "noise_candidate", "review_reason"], details["changes"])}
    if jev_rows:
        datasets["ai_jev_comparison"] = ([
            "segment_id", "start", "end", "speaker", "original_text", "current_text",
            "current_ai_flagged", "jev_flagged", "agreement", "jev_decision",
            "correction_needed_probability", "jev_confidence", "jev_model",
        ], jev_rows)
    cautions = ["AI仕上げは自動処理です。修正前の原文と比較して確認してください。"]
    if jev_rows:
        cautions.append(
            "Jevは音声ではなく文字起こしと会話文脈だけで修正要否を二択判定します。候補は原音で確認してください。"
        )
    analysis = {"segments": display, "config": row_analysis_config(row),
                "annotations": row_analysis_annotations(row, segments, row_analysis_config(row)),
                "cautions": cautions}
    outline = json_load(row["outline_json"], None)
    methods = [m for m in method_results(analysis, datasets, outline=outline, finishing=details)
               if m["method_id"] in {"ai_finishing", "outline"}]
    algorithms = {"finishing": FINISHING_VERSION}
    if jev_rows:
        algorithms["jev_review"] = JEV_REVIEW_VERSION
    result = {"schema_version": 1, "methods": methods, "parameters": {"stages": stages},
              "algorithms": algorithms, "finishing": details, "outline": outline}
    port = os.environ.get("MOJIOKOSI_PORT", "7860")
    if not port.isdigit() or not 1 <= int(port) <= 65535: port = "7860"
    return analysis_archive_store().save(item_id=str(row["id"]), kind="ai_finishing",
        snapshot=archive_snapshot(row, analysis), result=result, datasets=datasets,
        request_id=request_id or "finishing-" + str(row["id"]), input_fingerprint=archive_source_stamp(row),
        source_revision=int(row["revision_count"]), analysis_revision=int(row["analysis_revision"]),
        provider=provider, model=model, app_url=f"http://127.0.0.1:{port}")


def archive_app_url() -> str:
    port = os.environ.get("MOJIOKOSI_PORT", "7860")
    return f"http://127.0.0.1:{port if port.isdigit() and 1 <= int(port) <= 65535 else '7860'}"


def archive_meeting_minutes(row) -> dict | None:
    """Save meeting minutes as their own run, never inside the conversation's text analysis."""
    minutes = row_meeting_minutes(row)
    if row_session_profile(row).get("session_type") != "meeting" or not (
            minutes["tasks"] or minutes["decisions"] or minutes["summary"]
            or minutes["analysis"]["speaker_activity"]):
        return None
    segments = row_segments(row)
    names = json_load(row["speaker_names_json"], {})
    config = row_analysis_config(row)
    analysis = {"segments": [{**s, "speaker_name": names.get(s.get("speaker"), s.get("speaker", "UNKNOWN"))}
                             for s in segments],
                "config": config, "annotations": row_analysis_annotations(row, segments, config)}
    datasets = {
        "meeting_tasks": (["task_id", "title", "owner", "priority", "due_date", "due_text", "status", "confidence",
                           "evidence_segment_id", "evidence_start", "evidence_end", "source_text"], minutes["tasks"]),
        "meeting_decisions": (["decision_id", "text", "speaker", "evidence_segment_id", "evidence_start",
                               "evidence_end"], minutes["decisions"]),
        "meeting_speaker_activity": (["speaker", "turns", "seconds"], minutes["analysis"]["speaker_activity"]),
    }
    methods = [m for m in method_results(analysis, datasets, meeting=minutes) if m["method_id"] == "meeting_minutes"]
    result = {"schema_version": 1, "methods": methods,
              "parameters": {"method": minutes.get("method", ""), "version": minutes.get("version", "")},
              "algorithms": {"meeting_minutes": MEETING_MINUTES_VERSION}, "meeting_minutes": minutes}
    stamp = archive_source_stamp(row)
    return analysis_archive_store().save(item_id=str(row["id"]), kind="meeting_minutes",
        snapshot=archive_snapshot(row, analysis), result=result, datasets=datasets,
        request_id="meeting-" + archive_digest({"source": stamp, "minutes": minutes})[:40],
        input_fingerprint=stamp, source_revision=int(row["revision_count"]),
        analysis_revision=int(row["analysis_revision"]), app_url=archive_app_url())


def interview_comparison_datasets(comparison: dict[str, Any]) -> dict[str, tuple[list[str], list[dict]]]:
    """Long-format tables: one row per interview, so every value keeps its conversation ID."""
    def spread(rows: list[dict], label: str, summary: str) -> list[dict]:
        return [{label: row.get(label), summary: row.get(summary), **value}
                for row in rows for value in row.get("interviews", [])]
    return {
        "comparison_interviews": (["item_id", "source_name", "comparison_label", "comparison_source", "session_type",
                                   "session_date", "objective", "included_segment_count", "speaker_count",
                                   "participant_count", "session_duration", "total_speaking_seconds", "term_count",
                                   "excluded_segment_count"], comparison.get("interviews", [])),
        "comparison_common_terms": (["term", "minimum_count", "item_id", "count", "rate_per_1000_terms"],
                                    spread(comparison.get("common_terms", []), "term", "minimum_count")),
        "comparison_characteristic_terms": (["item_id", "source_name", "term", "count", "rate_per_1000_terms",
                                             "other_count", "other_rate_per_1000_terms", "difference_per_1000_terms"],
                                            comparison.get("characteristic_terms", [])),
        "comparison_codes": (["code", "max_count", "item_id", "count", "rate_per_100_segments"],
                             spread(comparison.get("code_comparison", []), "code", "max_count")),
        "comparison_emotions": (["emotion", "max_count", "item_id", "count", "rate_per_100_segments"],
                                spread(comparison.get("emotion_comparison", []), "emotion", "max_count")),
    }


def archive_interview_comparison(rows: list, comparison: dict[str, Any], request_id: str, *,
                                 app_url: str, store: AnalysisStore | None = None) -> dict:
    """Save a group-interview comparison as one multi-conversation run, apart from each interview's runs."""
    item_ids = [str(row["id"]) for row in rows]
    group_id = "comparison-" + hashlib.sha256("\n".join(sorted(item_ids)).encode("utf-8")).hexdigest()[:24]
    members = [{"conversation_id": str(row["id"]), "title": str(row["source_name"]),
                "source_revision": int(row["revision_count"] or 0),
                "analysis_revision": int(row["analysis_revision"] or 0),
                "input_fingerprint": archive_source_stamp(row)} for row in rows]
    datasets = interview_comparison_datasets(comparison)
    methods = [m for m in method_results({"segments": [], "config": {}}, datasets, comparison=comparison)
               if m["method_id"] == "interview_comparison"]
    expert_hashes = method_experts.attach_method_reviews(
        methods, {"segments": [], "config": {}}, context={"session_count": len(comparison.get("interviews", []))})
    allow_different = bool(comparison.get("allow_different_content"))
    snapshot = {"title": "グループインタビュー比較：" + " / ".join(member["title"] for member in members),
                "conversation_id": group_id, "kind": "interview_comparison", "members": members,
                "allow_different_content": allow_different,
                "comparison_key": comparison.get("comparison_key", ""), "segments": []}
    result = {"schema_version": 1, "methods": methods,
              "parameters": {"item_ids": item_ids, "allow_different_content": allow_different},
              "algorithms": {"interview_comparison": comparison.get("schema_version", 1), "experts": expert_hashes},
              "comparison": comparison}
    return (store or analysis_archive_store()).save(item_id=group_id, kind="interview_comparison", snapshot=snapshot,
        result=result, datasets=datasets, request_id=request_id,
        input_fingerprint=archive_digest([member["input_fingerprint"] for member in members]),
        source_revision=0, analysis_revision=0, app_url=app_url, member_ids=item_ids)


def refresh_archive_index(item_id: str) -> None:
    # Vault failure must not undo a successful transcript/configuration edit.
    try:
        analysis_archive_store().publish_index(item_id)
    except (OSError, ValueError, LookupError, sqlite3.Error):
        with database_connection() as connection:
            connection.execute("UPDATE analysis_runs SET vault_status='conflict',error='原文は保存済みですが、Vaultの更新確認が必要です。' WHERE item_id=? AND status='completed'", (item_id,))


def analysis_queries() -> AnalysisQueries:
    """Build request-time query dependencies so patched settings stay effective."""
    return AnalysisQueries(
        store=analysis_archive_store(),
        find_item=library_row,
        source_fingerprint=archive_source_stamp,
        database_connection=database_connection,
        build_analysis=group_analysis_for_row,
        public_insight_request=public_insight_request,
        public_transformer_request=public_transformer_request,
        expose_local_paths=local_path_access_allowed(),
    )


PIPELINE_METHOD_DATASETS = {
    "participation": ("speakers", "groups", "summary", "observations"),
    "conversation_dynamics": ("transitions", "gaps", "overlaps", "timeline"),
}


def build_analysis_pipeline_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    """Capture one immutable input and its existing-analysis adapter view."""
    analysis = group_analysis_for_row(row, include_research_rows=True)
    return {
        "schema_version": 1,
        "input_hash": archive_source_stamp(row),
        "source_revision": int(row["revision_count"] or 0),
        "analysis_revision": int(row["analysis_revision"] or 0),
        "analysis": analysis,
        "archive_snapshot": archive_snapshot(row, analysis),
    }


def advise_analysis_plan(snapshot: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Run the selected O01 adviser on a small, nonverbatim context packet."""
    context = analysis_plan_advisor.planning_context(
        snapshot["analysis"], payload.get("objective", "")
    )
    if context["included_segment_count"] < 1:
        raise AnalysisContractError("分析できる発話がありません。", code="no_valid_input")
    engine = payload.get("engine", "transformer")
    policy = payload.get("provider_policy", "local_only")
    if not isinstance(policy, str) or policy not in {"local_only", "cloud_allowed"}:
        raise AnalysisContractError("送信方針が正しくありません。", code="provider_unavailable")
    if engine == "transformer":
        if policy != "local_only":
            raise AnalysisContractError("Transformer計画候補はlocal_onlyで生成してください。", code="provider_unavailable")
        candidate, model_info = analysis_plan_advisor.transformer_candidate(
            context, encode_transformer_texts
        )
        provider, model = "local_transformer", model_info["name"]
    elif engine == "llm":
        provider = payload.get("provider", "lmstudio")
        if not isinstance(provider, str) or provider not in {"lmstudio", "openai", "google"}:
            raise AnalysisContractError("計画担当のLLMを選択してください。", code="provider_unavailable")
        if provider == "lmstudio" and policy != "local_only":
            raise AnalysisContractError("ローカルLLMはlocal_onlyで生成してください。", code="provider_unavailable")
        if provider != "lmstudio" and policy != "cloud_allowed":
            raise AnalysisContractError("クラウドLLMにはcloud_allowedが必要です。", code="provider_unavailable")
        config = load_token_config()
        api_key, configured_model = configured_ai_credentials(config, provider)
        model = payload.get("model") or configured_model
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\n" in model or "\r" in model:
            raise AnalysisContractError("計画担当のモデルを指定してください。", code="provider_unavailable")
        model = model.strip()
        if provider != "lmstudio" and not api_key:
            raise AnalysisContractError("選択したLLMのAPIキーが未設定です。", code="provider_unavailable")
        base_url = config.lmstudio_base_url if provider == "lmstudio" else ""
        candidate = analysis_plan_advisor.llm_candidate(
            context,
            lambda system, prompt, schema: call_ai_json(
                provider, api_key, model, system, prompt, "analysis_plan_o01", schema,
                base_url=base_url,
            ),
        )
    else:
        raise AnalysisContractError("計画担当のエンジンが正しくありません。", code="method_unavailable")
    return {
        "version": analysis_plan_advisor.ADVISOR_VERSION,
        "source_revision": snapshot["source_revision"],
        "analysis_revision": snapshot["analysis_revision"],
        "input_hash": snapshot["input_hash"],
        "objective": context["objective"],
        "engine": engine, "provider": provider, "model": model,
        **candidate,
    }


def run_analysis_pipeline_method(step_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Adapt one existing method to the fixed pipeline snapshot."""
    if step_id not in PIPELINE_METHOD_DATASETS:
        raise ValueError("未対応の分析stepです。")
    analysis = snapshot["analysis"]
    datasets = {
        name: analysis_csv_rows(analysis, name)
        for name in PIPELINE_METHOD_DATASETS[step_id]
    }
    methods = method_results(analysis, datasets)
    method = next((value for value in methods if value["method_id"] == step_id), None)
    if method is None:
        raise ValueError(f"{step_id}の既存分析結果を構築できません。")
    return {
        "method": method,
        "datasets": {
            name: {"fields": fields, "rows": rows}
            for name, (fields, rows) in datasets.items()
        },
    }


def analysis_pipeline_service() -> AnalysisPipelineService:
    store = analysis_archive_store()

    def public_run(value: dict[str, Any]) -> dict[str, Any]:
        row = store.get(str(value.get("id") or ""))
        if row is None:
            raise LookupError("保存結果が見つかりません。")
        return store.public(row, local=local_path_access_allowed())

    return AnalysisPipelineService(
        connect=database_connection,
        find_item=library_row,
        source_fingerprint=archive_source_stamp,
        snapshot_builder=build_analysis_pipeline_snapshot,
        method_runner=run_analysis_pipeline_method,
        save_result=store.save,
        publish_result=store.publish,
        publication_outcomes=store.publication_outcomes,
        public_run=public_run,
        runtime_key=str(DATABASE_FILE.resolve()),
        plan_advisor=advise_analysis_plan,
    )


def mark_analysis_run_stale(run_id: str) -> None:
    with database_connection() as connection:
        connection.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (run_id,))


def analysis_commands() -> AnalysisCommands:
    """Build save dependencies at request time so patched settings stay effective."""
    return AnalysisCommands(
        store=analysis_archive_store(),
        find_item=library_row,
        build_analysis=lambda row: group_analysis_for_row(
            row, include_research_rows=True
        ),
        search_kwic=search_kwic,
        archive_analysis=archive_group_analysis,
        source_fingerprint=archive_source_stamp,
        mark_stale=mark_analysis_run_stale,
        load_comparison_items=interview_comparison_request,
        build_comparison=build_interview_comparison,
        archive_comparison=archive_interview_comparison,
        database_connection=database_connection,
        save_preparation_state=preparation.save,
        segments_for_item=row_segments,
        refresh_archive_index=refresh_archive_index,
        publish_input_vault=publish_input_vault,
        update_library_item_locked=_update_library_from_payload_locked,
        start_insights=start_analysis_insights_command,
        cancel_insights=cancel_analysis_insights_command,
        start_transformer=start_transformer_analysis_command,
        cancel_transformer=cancel_transformer_analysis_command,
        run_classification=run_segment_classifications_command,
        write_lock=library_write_lock,
        expose_local_paths=local_path_access_allowed(),
        pipeline_service=analysis_pipeline_service(),
    )


def speaker_registry_handler() -> SpeakerRegistryHandler:
    """Build request-time speaker dependencies so patched settings stay effective."""
    return SpeakerRegistryHandler(
        snapshot=speaker_registry_snapshot,
        save_records_locked=_save_speaker_registry_records_locked,
        database_connection=database_connection,
        refresh_archive_index=refresh_archive_index,
        write_lock=library_write_lock,
    )


def speaker_identification_handler() -> SpeakerIdentificationHandler:
    return SpeakerIdentificationHandler(identify_library_speakers)


def job_handler() -> JobHandler:
    return JobHandler(
        jobs=jobs,
        lock=jobs_lock,
        active_statuses=ACTIVE_JOB_STATUSES,
        prune=prune_jobs_locked,
        admission_id=lambda: _job_admission_id,
        admission_public=admission_job_public,
        start_job=start_transcription_job_command,
        update_job=update_job,
        update_transcript=update_library_from_payload,
        path_is_within=path_is_within,
    )


register_analysis_routes(
    app, analysis_queries, analysis_commands, AI_MODEL_PROVIDERS
)
register_speaker_routes(
    app,
    speaker_registry_handler,
    speaker_identification_handler,
    AI_MODEL_PROVIDERS,
    import_speaker_registry_csv,
    read_upload_limited,
    lambda: MAX_CSV_UPLOAD_BYTES,
)
register_job_routes(app, job_handler)


def public_insight_request(row) -> dict[str, Any] | None:
    if row is None:
        return None
    return {**{key: row[key] for key in (
        "request_id", "item_id", "provider", "model", "status", "progress", "message",
        "created_at", "updated_at", "source_revision", "analysis_revision",
    )}, "usage": json_load(row["usage_json"], {})}


def update_insight_request(request_id: str, status: str, progress: int, message: str,
                           usage: dict[str, Any]) -> None:
    with database_connection() as connection:
        connection.execute("""
            UPDATE analysis_insight_requests SET status=?, progress=?, message=?, usage_json=?, updated_at=?
            WHERE request_id=?
        """, (status, progress, message, json.dumps(usage, ensure_ascii=False), utc_now_iso(), request_id))


class InsightCancelled(RuntimeError):
    pass


def run_analysis_insight_job(request_id: str, analysis: dict, provider: str, api_key: str,
                             model: str, cancel_event: threading.Event, base_url: str = "",
                             app_url: str = "http://127.0.0.1:7860",
                             ai_efforts: dict | None = None) -> None:
    usage: dict[str, Any] = {}
    progress_value = 0
    message = "発話の確認を準備しています。"

    def cancelled():
        if cancel_event.is_set():
            raise InsightCancelled("AI見解の生成を中止しました。")

    def progress(value, text):
        nonlocal progress_value, message
        with insight_jobs_lock:
            cancelled()
            progress_value, message = value, text
            update_insight_request(request_id, "running", value, text, usage)

    def record_usage(sample):
        nonlocal usage
        usage = merge_ai_usage(usage, sample)
        progress(progress_value, message)

    def call(system, prompt, schema):
        return call_ai_json(provider, api_key, model, system, prompt, "conversation_insights",
                            schema, cancelled, record_usage, base_url, ai_efforts=ai_efforts)

    try:
        expert = method_experts.ai_context(analysis.get("experts"))
        findings = create_ai_insights(analysis, call, progress, cancelled, expert=expert)
        with insight_jobs_lock, library_write_lock:
            cancelled()
            latest = library_row(analysis["item"]["id"])
            if latest is None:
                raise AnalysisConflictError("対象の会話が削除されたため見解を保存しませんでした。")
            current = group_analysis_for_row(latest)
            fingerprint = input_fingerprint(analysis)
            if current["insights"]["fingerprint"] != fingerprint:
                raise AnalysisConflictError("生成中に元データまたは分析条件が更新されました。再生成してください。")
            saved = {"findings": findings, "provider": provider, "model": model,
                     "generated_at": utc_now_iso(), "fingerprint": fingerprint,
                     "algorithm_version": INSIGHT_VERSION, "request_id": request_id,
                     "source_revision": analysis["item"]["revision_count"],
                     "analysis_revision": analysis["item"]["analysis_revision"], "usage": usage,
                     **({"expert": {key: expert[key] for key in
                                    ("expert_id", "definition_version", "knowledge_hash", "fingerprint")}}
                        if expert else {}),
                     "evidence": {s["id"]: {k: s.get(k) for k in
                                  ("id", "speaker", "speaker_name", "start", "end", "text")}
                                  for s in included_segments(analysis)
                                  if any(s["id"] in f["segment_ids"] for f in findings)}}
            full_analysis = group_analysis_for_row(latest, include_research_rows=True)
            full_analysis["insights"].update({"ai": saved, "stale": False})
            archived = archive_group_analysis(latest, full_analysis, "insights-" + request_id,
                                               kind="ai_insights", app_url=app_url, check_cancelled=cancelled)
            saved["archive_id"] = archived["id"]
            saved["vault_status"] = archived["vault_status"]
            with database_connection() as connection:
                cursor = connection.execute("""
                    UPDATE library_items SET analysis_insights_json=?
                    WHERE id=? AND revision_count=? AND analysis_revision=?
                """, (json.dumps(saved, ensure_ascii=False), latest["id"],
                      analysis["item"]["revision_count"], analysis["item"]["analysis_revision"]))
                if cursor.rowcount != 1:
                    raise AnalysisConflictError("保存直前にデータが更新されました。再生成してください。")
                connection.execute("""
                    UPDATE analysis_insight_requests SET status='completed', progress=100,
                        message='AI見解を保存しました。', usage_json=?, updated_at=? WHERE request_id=?
                """, (json.dumps(usage, ensure_ascii=False), utc_now_iso(), request_id))
    except InsightCancelled as exc:
        update_insight_request(request_id, "cancelled", progress_value, str(exc), usage)
    except AnalysisConflictError as exc:
        update_insight_request(request_id, "stale", progress_value, str(exc), usage)
    except Exception as exc:
        update_insight_request(request_id, "failed", progress_value,
                               "AI見解を生成できませんでした: "
                               + public_diagnostic_text(str(exc), reveal_local_paths=False)[:700], usage)
    finally:
        with insight_jobs_lock:
            insight_cancel_events.pop(request_id, None)


def start_analysis_insights_command(
    item_id: str, payload: dict[str, Any], *, app_url: str
) -> tuple[dict[str, Any], int]:
    provider, request_id = payload.get("provider"), payload.get("request_id")
    with insight_jobs_lock:
        row = library_row(item_id)
        if row is None:
            raise AnalysisCommandRequestError(
                "処理済みデータが見つかりません。", 404
            )
        with database_connection() as connection:
            previous = connection.execute("SELECT * FROM analysis_insight_requests WHERE request_id=?",
                                          (request_id,)).fetchone()
            if previous:
                if any(previous[k] != v for k, v in {
                    "item_id": item_id, "provider": provider,
                    "source_revision": payload["source_revision"],
                    "analysis_revision": payload["analysis_revision"],
                }.items()):
                    raise AnalysisCommandRequestError(
                        "リクエストIDが別の指定に使われています。", 409
                    )
                return {"run": public_insight_request(previous)}, 200
            active = connection.execute("""
                SELECT * FROM analysis_insight_requests WHERE item_id=?
                    AND status IN ('queued','running','cancelling') LIMIT 1
            """, (item_id,)).fetchone()
            if active:
                raise AnalysisCommandRequestError(
                    "この会話のAI見解は生成中です。",
                    409,
                    details={"run": public_insight_request(active)},
                )
        if payload["source_revision"] != int(row["revision_count"]) or payload["analysis_revision"] != int(row["analysis_revision"]):
            raise AnalysisCommandRequestError(
                "データが更新されています。分析を再読み込みしてください。",
                409,
                details={"conflict": True},
            )
        analysis = group_analysis_for_row(row)
        blocked = method_experts.ai_block_reason(analysis.get("experts"))
        if blocked:
            raise AnalysisCommandRequestError(
                blocked, 409, details={"expert_blocked": True}
            )
        if not included_segments(analysis):
            raise AnalysisCommandRequestError(
                "見解の生成に利用できる発話がありません。", 400
            )
        try:
            ai_efforts = normalize_efforts(payload.get("ai_efforts"))
            config = load_token_config()
            api_key, model = configured_ai_credentials(config, provider)
            base_url = config.lmstudio_base_url if provider == "lmstudio" else ""
            if provider != "lmstudio" and not api_key:
                raise ValueError("tokens.jsonに選択したプロバイダーのAPIキーを設定してください。")
            if not model:
                raise ValueError(local_llm_model_required_message())
        except (ValueError, RuntimeError) as exc:
            raise AnalysisCommandRequestError(str(exc), 400) from exc
        now = utc_now_iso()
        with database_connection() as connection:
            connection.execute("""
                INSERT INTO analysis_insight_requests
                (request_id,item_id,source_revision,analysis_revision,fingerprint,provider,model,status,message,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,'queued','生成を準備しています。',?,?)
            """, (request_id, item_id, payload["source_revision"], payload["analysis_revision"],
                  analysis["insights"]["fingerprint"], provider, model, now, now))
            run = connection.execute("SELECT * FROM analysis_insight_requests WHERE request_id=?", (request_id,)).fetchone()
        event = threading.Event()
        insight_cancel_events[request_id] = event
        try:
            threading.Thread(target=run_analysis_insight_job,
                             args=(request_id, analysis, provider, api_key, model, event, base_url,
                                   app_url, ai_efforts),
                             name=f"insights-{item_id}", daemon=True).start()
        except RuntimeError:
            insight_cancel_events.pop(request_id, None)
            update_insight_request(request_id, "failed", 0, "生成処理を開始できませんでした。", {})
            raise AnalysisCommandRequestError(
                "生成処理を開始できませんでした。", 503
            )
        return {"run": public_insight_request(run)}, 202


def cancel_analysis_insights_command(
    item_id: str, request_id: str
) -> dict[str, Any]:
    with insight_jobs_lock, database_connection() as connection:
        row = connection.execute("SELECT * FROM analysis_insight_requests WHERE item_id=? AND request_id=?",
                                 (item_id, request_id)).fetchone()
        if row is None:
            raise AnalysisCommandRequestError("生成処理が見つかりません。", 404)
        if row["status"] in {"queued", "running", "cancelling"}:
            event = insight_cancel_events.get(row["request_id"])
            if event:
                event.set()
            connection.execute("UPDATE analysis_insight_requests SET status='cancelling', message='中止しています。' WHERE request_id=?",
                               (row["request_id"],))
        return {"ok": True}


def public_transformer_request(row) -> dict[str, Any] | None:
    if row is None:
        return None
    keys = row.keys()
    return {
        **{key: row[key] for key in (
            "request_id", "item_id", "model", "max_topics", "min_topic_size", "topic_count",
            "status", "progress", "message", "created_at", "updated_at",
            "source_revision", "analysis_revision",
        )},
        "mode": str(row["mode"]) if "mode" in keys else "auto",
        "min_similarity": float(row["min_similarity"]) if "min_similarity" in keys else 0.0,
    }


def update_transformer_request(request_id: str, status: str, progress: int, message: str) -> None:
    with database_connection() as connection:
        connection.execute("""
            UPDATE transformer_analysis_requests
            SET status=?, progress=?, message=?, updated_at=? WHERE request_id=?
        """, (status, progress, message, utc_now_iso(), request_id))


class TransformerAnalysisCancelled(RuntimeError):
    pass


def run_transformer_analysis_job(
    request_id: str, analysis: dict, model: str, max_topics: int,
    min_topic_size: int, topic_count: int, cancel_event: threading.Event,
    app_url: str = "http://127.0.0.1:7860", mode: str = "auto",
    manual_topics: list[dict] | None = None,
    min_similarity: float = DEFAULT_MANUAL_MIN_SIMILARITY,
    saved_result: dict | None = None,
) -> None:
    progress_value = 0

    def cancelled() -> None:
        if cancel_event.is_set():
            raise TransformerAnalysisCancelled("Transformer分析を中止しました。")

    def progress(value: int, message: str) -> None:
        nonlocal progress_value
        with transformer_jobs_lock:
            cancelled()
            progress_value = max(0, min(99, int(value)))
            update_transformer_request(request_id, "running", progress_value, message)

    try:
        progress(2, "日本語の解析結果を準備しています。")
        research = build_research_analysis(analysis)
        reuse = (saved_transformer_embeddings(saved_result, analysis, model=model)
                 if mode in {"candidate", "manual"} else None)
        embeddings, embedding_segment_ids, engine = reuse if reuse else (None, None, None)
        saved_quality = (saved_result or {}).get("quality")
        previous_candidates = (saved_quality.get("cluster_candidates")
                               if isinstance(saved_quality, dict) else None)
        if reuse:
            progress(60, "保存済みの意味ベクトルを再利用します。")
        elif mode != "auto":
            progress(5, "保存済みの意味ベクトルがないため、発話を意味ベクトル化します。")
        result = analyze_transformer_topics(
            analysis, research["linguistics"]["morphemes"], model_name=model,
            max_topics=max_topics, min_topic_size=min_topic_size,
            topic_count=topic_count or None, mode=mode,
            manual_topics=manual_topics or [], manual_min_similarity=min_similarity,
            embeddings=embeddings, embedding_segment_ids=embedding_segment_ids, engine=engine,
            previous_candidates=previous_candidates,
            progress=progress, check_cancelled=cancelled,
        )
        result.update({
            "generated_at": utc_now_iso(), "request_id": request_id,
            "source_revision": analysis["item"]["revision_count"],
            "analysis_revision": analysis["item"]["analysis_revision"],
        })
        with transformer_jobs_lock, library_write_lock:
            cancelled()
            latest = library_row(analysis["item"]["id"])
            if latest is None:
                raise AnalysisConflictError("対象の会話が削除されたため結果を保存しませんでした。")
            current = group_analysis_for_row(latest)
            expected = transformer_input_fingerprint(analysis, model=model)
            actual = transformer_input_fingerprint(current, model=model)
            if expected != actual:
                raise AnalysisConflictError("分析中に元データが更新されました。再実行してください。")
            full_analysis = group_analysis_for_row(latest, include_research_rows=True)
            full_analysis["transformer"] = {"result": result, "stale": False}
            progress(95, "分析結果を保存しています。")
            archived = archive_group_analysis(
                latest, full_analysis, "transformer-" + request_id,
                kind="transformer_topics", app_url=app_url, check_cancelled=cancelled,
            )
            result["archive_id"] = archived["id"]
            result["vault_status"] = archived["vault_status"]
            with database_connection() as connection:
                cursor = connection.execute("""
                    UPDATE library_items SET transformer_analysis_json=?
                    WHERE id=? AND revision_count=? AND analysis_revision=?
                """, (json.dumps(result, ensure_ascii=False), latest["id"],
                      analysis["item"]["revision_count"], analysis["item"]["analysis_revision"]))
                if cursor.rowcount != 1:
                    raise AnalysisConflictError("保存直前にデータが更新されました。再実行してください。")
                connection.execute("""
                    UPDATE transformer_analysis_requests SET status='completed', progress=100,
                        message='Transformerテーマ分析を保存しました。', updated_at=? WHERE request_id=?
                """, (utc_now_iso(), request_id))
    except TransformerAnalysisCancelled as exc:
        update_transformer_request(request_id, "cancelled", progress_value, str(exc))
    except AnalysisConflictError as exc:
        update_transformer_request(request_id, "stale", progress_value, str(exc))
    except Exception as exc:
        update_transformer_request(
            request_id, "failed", progress_value,
            "Transformer分析を実行できませんでした: "
            + public_diagnostic_text(str(exc), reveal_local_paths=False)[:700],
        )
    finally:
        with transformer_jobs_lock:
            transformer_cancel_events.pop(request_id, None)


def start_transformer_analysis_command(
    item_id: str, payload: dict[str, Any], *, app_url: str
) -> tuple[dict[str, Any], int]:
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", request_id):
        raise AnalysisCommandRequestError("リクエストIDが正しくありません。", 400)
    if any(type(payload.get(key)) is not int for key in ("source_revision", "analysis_revision")):
        raise AnalysisCommandRequestError(
            "元データと分析のrevisionを指定してください。", 400
        )
    try:
        max_topics = int(payload.get("max_topics", 8))
        min_topic_size = int(payload.get("min_topic_size", 2))
        topic_count = int(payload.get("topic_count", 0))
        if (not 2 <= max_topics <= 12 or not 2 <= min_topic_size <= 20
                or topic_count not in {0, *range(2, 13)}):
            raise ValueError
    except (TypeError, ValueError):
        raise AnalysisCommandRequestError(
            "テーマ上限・固定数は2〜12、最小発話数は2〜20で指定してください。",
            400,
        )
    mode = str(payload.get("mode") or "auto")
    if mode not in TOPIC_MODES:
        raise AnalysisCommandRequestError(
            "テーマの決め方は自動・候補・手動のいずれかで指定してください。",
            400,
        )
    try:
        min_similarity = float(payload.get("min_similarity", DEFAULT_MANUAL_MIN_SIMILARITY))
        if not 0.0 <= min_similarity <= 0.95:
            raise ValueError
    except (TypeError, ValueError):
        raise AnalysisCommandRequestError(
            "割り当てのしきい値は0〜0.95で指定してください。", 400
        )
    if mode == "candidate" and topic_count < 2:
        raise AnalysisCommandRequestError(
            "候補から選ぶときは、テーマ数を指定してください。", 400
        )
    if mode == "auto":
        topic_count = 0
    model = str(os.environ.get("MOJIOKOSI_TRANSFORMER_MODEL", DEFAULT_TRANSFORMER_MODEL)).strip()
    if not model or len(model) > 200:
        raise AnalysisCommandRequestError(
            "Transformerモデルの設定が正しくありません。", 400
        )
    with transformer_jobs_lock:
        row = library_row(item_id)
        if row is None:
            raise AnalysisCommandRequestError(
                "処理済みデータが見つかりません。", 404
            )
        with database_connection() as connection:
            previous = connection.execute(
                "SELECT * FROM transformer_analysis_requests WHERE request_id=?", (request_id,)
            ).fetchone()
            if previous:
                expected = {
                    "item_id": item_id, "model": model,
                    "source_revision": payload["source_revision"],
                    "analysis_revision": payload["analysis_revision"],
                    "max_topics": max_topics, "min_topic_size": min_topic_size,
                    "topic_count": topic_count, "mode": mode,
                }
                if any(previous[key] != value for key, value in expected.items()):
                    raise AnalysisCommandRequestError(
                        "リクエストIDが別の指定に使われています。", 409
                    )
                return {"run": public_transformer_request(previous)}, 200
            active = connection.execute("""
                SELECT * FROM transformer_analysis_requests WHERE item_id=?
                    AND status IN ('queued','running','cancelling') LIMIT 1
            """, (item_id,)).fetchone()
            if active:
                raise AnalysisCommandRequestError(
                    "この会話のTransformer分析は実行中です。",
                    409,
                    details={"run": public_transformer_request(active)},
                )
        if (payload["source_revision"] != int(row["revision_count"])
                or payload["analysis_revision"] != int(row["analysis_revision"])):
            raise AnalysisCommandRequestError(
                "データが更新されています。分析を再読み込みしてください。",
                409,
                details={"conflict": True},
            )
        analysis = group_analysis_for_row(row)
        if not included_segments(analysis):
            raise AnalysisCommandRequestError(
                "Transformer分析に利用できる発話がありません。", 400
            )
        manual_topics = list(analysis.get("config", {}).get("transformer_topics") or [])
        if mode == "manual" and not 2 <= len(manual_topics) <= MAX_MANUAL_TOPICS:
            raise AnalysisCommandRequestError(
                f"手動で割り当てるには、テーマを2〜{MAX_MANUAL_TOPICS}件定義して保存してください。",
                400,
            )
        saved_result = json_load(row["transformer_analysis_json"], {}) \
            if "transformer_analysis_json" in row.keys() else {}
        fingerprint = transformer_input_fingerprint(analysis, model=model)
        now = utc_now_iso()
        with database_connection() as connection:
            connection.execute("""
                INSERT INTO transformer_analysis_requests
                (request_id,item_id,source_revision,analysis_revision,fingerprint,model,
                 max_topics,min_topic_size,topic_count,mode,min_similarity,
                 status,message,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,'queued','モデルの準備を開始します。',?,?)
            """, (request_id, item_id, payload["source_revision"], payload["analysis_revision"],
                  fingerprint, model, max_topics, min_topic_size, topic_count, mode,
                  min_similarity, now, now))
            run = connection.execute(
                "SELECT * FROM transformer_analysis_requests WHERE request_id=?", (request_id,)
            ).fetchone()
        event = threading.Event()
        transformer_cancel_events[request_id] = event
        try:
            threading.Thread(
                target=run_transformer_analysis_job,
                args=(request_id, analysis, model, max_topics, min_topic_size,
                      topic_count, event, app_url),
                kwargs={"mode": mode, "manual_topics": manual_topics,
                        "min_similarity": min_similarity,
                        "saved_result": saved_result if isinstance(saved_result, dict) else {}},
                name=f"transformer-{item_id}", daemon=True,
            ).start()
        except RuntimeError:
            transformer_cancel_events.pop(request_id, None)
            update_transformer_request(request_id, "failed", 0, "分析処理を開始できませんでした。")
            raise AnalysisCommandRequestError(
                "分析処理を開始できませんでした。", 503
            )
        return {"run": public_transformer_request(run)}, 202


def cancel_transformer_analysis_command(
    item_id: str, request_id: str
) -> dict[str, Any]:
    with transformer_jobs_lock, database_connection() as connection:
        row = connection.execute("""
            SELECT * FROM transformer_analysis_requests WHERE item_id=? AND request_id=?
        """, (item_id, request_id)).fetchone()
        if row is None:
            raise AnalysisCommandRequestError(
                "Transformer分析処理が見つかりません。", 404
            )
        if row["status"] in {"queued", "running", "cancelling"}:
            event = transformer_cancel_events.get(row["request_id"])
            if event:
                event.set()
            connection.execute("""
                UPDATE transformer_analysis_requests SET status='cancelling',
                    message='中止しています。' WHERE request_id=?
            """, (row["request_id"],))
        return {"ok": True}


def run_segment_classifications_command(
    item_id: str, payload: dict[str, Any], *, app_url: str
) -> dict[str, Any]:
    if any(type(payload.get(key)) is not int for key in ("source_revision", "analysis_revision")):
        raise AnalysisCommandRequestError(
            "元データと分析のrevisionを指定してください。", 400
        )
    if "use_jev" not in payload or not isinstance(payload.get("use_jev"), bool):
        raise AnalysisCommandRequestError(
            "Jevへ発話を送信するか use_jev で明示してください。", 400
        )
    request_id = str(payload.get("request_id") or uuid.uuid4().hex)
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", request_id):
        raise AnalysisCommandRequestError("リクエストIDが正しくありません。", 400)

    row = library_row(item_id)
    if row is None:
        raise AnalysisCommandRequestError("データが見つかりません。", 404)
    source_revision = int(row["revision_count"] or 0)
    analysis_revision = int(row["analysis_revision"] or 0)
    if (payload["source_revision"] != source_revision
            or payload["analysis_revision"] != analysis_revision):
        raise AnalysisCommandRequestError(
            "データが更新されています。分析を再読み込みしてください。",
            409,
            details={"conflict": True},
        )

    try:
        analysis = group_analysis_for_row(row)
        segments = analysis["segments"]
        if not segments:
            raise AnalysisCommandRequestError("分類できる発話がありません。", 400)
        transformer_state = analysis.get("transformer", {})
        transformer_result = (
            transformer_state.get("result") if not transformer_state.get("stale") else None
        )
        llm_proposals: dict[str, dict[str, Any]] = {}
        llm_usage: dict[str, Any] = {}
        if payload["use_jev"]:
            token_config = load_token_config()
            if not token_config.typesafe_api_key:
                raise ValueError("tokens.json に typesafe_api_key を設定してください。")
            llm_proposals, llm_usage = classify_segments_with_jev(
                segments,
                segment_classification_topic_candidates(analysis["config"].get("codebook", [])),
                token_config.typesafe_api_key,
                token_config.typesafe_model,
            )
        result = build_segment_classification_result(
            segments, analysis["annotations"], analysis["config"].get("codebook", []),
            transformer_result, llm_proposals,
            source_revision=source_revision, analysis_revision=analysis_revision,
            llm_usage=llm_usage,
        )
        result["generated_at"] = utc_now_iso()
        result["request_id"] = request_id
        with library_write_lock:
            latest = library_row(item_id)
            if latest is None:
                raise AnalysisCommandRequestError("データが削除されています。", 404)
            if (int(latest["revision_count"] or 0) != source_revision
                    or int(latest["analysis_revision"] or 0) != analysis_revision):
                raise AnalysisCommandRequestError(
                    "実行中にデータが更新されました。もう一度実行してください。",
                    409,
                    details={"conflict": True},
                )
            with database_connection() as connection:
                cursor = connection.execute(
                    """UPDATE library_items SET segment_classification_json=?
                       WHERE id=? AND revision_count=? AND analysis_revision=?""",
                    (json.dumps(result, ensure_ascii=False), item_id,
                     source_revision, analysis_revision),
                )
                if cursor.rowcount != 1:
                    raise AnalysisConflictError(
                        "保存前にデータが更新されました。もう一度実行してください。"
                    )
        latest = library_row(item_id)
        refreshed = group_analysis_for_row(latest)
        archive_warning = ""
        public_run = None
        try:
            archived = archive_segment_classification(
                latest, refreshed, result, "segment-classification-" + request_id,
                app_url=app_url,
            )
            public_run = analysis_archive_store().public(
                archived, local=local_path_access_allowed()
            )
            result["archive_id"] = archived["id"]
            with database_connection() as connection:
                connection.execute(
                    "UPDATE library_items SET segment_classification_json=? WHERE id=?",
                    (json.dumps(result, ensure_ascii=False), item_id),
                )
            refreshed = group_analysis_for_row(library_row(item_id))
        except (OSError, ValueError, TypeError, sqlite3.Error, StoreConflict) as exc:
            archive_warning = (
                "分類結果は保存しましたが、固定分析履歴の作成に失敗しました: "
                + public_diagnostic_text(str(exc), reveal_local_paths=False)[:500]
            )
        return {
            "segment_classification": refreshed["segment_classification"],
            "run": public_run, "archive_warning": archive_warning,
        }
    except AnalysisCommandRequestError:
        raise
    except AnalysisConflictError as exc:
        raise AnalysisCommandRequestError(
            str(exc), 409, details={"conflict": True}
        ) from exc
    except (ValueError, RuntimeError) as exc:
        raise AnalysisCommandRequestError(
            public_diagnostic_text(str(exc), reveal_local_paths=False)[:700], 400
        ) from exc
    except (OSError, urllib.error.URLError, sqlite3.Error) as exc:
        raise AnalysisCommandRequestError(
            "発話分類を実行できませんでした: "
            + public_diagnostic_text(str(exc), reveal_local_paths=False)[:500],
            500,
        ) from exc


def meeting_minutes_export_row(item_id: str) -> tuple[sqlite3.Row, dict[str, Any]]:
    return obsidian_workflows().meeting_minutes_export_row(item_id)


register_obsidian_routes(
    app,
    local_access_allowed=local_path_access_allowed,
    library_row=library_row,
    row_segments=row_segments,
    workbench=obsidian_workbench,
    normalize_efforts=normalize_efforts,
    write_lock=library_write_lock,
    meeting_export_row=meeting_minutes_export_row,
    meeting_fingerprint=meeting_minutes_fingerprint,
    archive_meeting_minutes=archive_meeting_minutes,
    publish_meeting_minutes=publish_meeting_minutes_to_obsidian,
    log_warning=app.logger.warning,
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
            for table in ("transcript_versions", "transcript_preparations", "transcript_preparation_events"):
                connection.execute(f"DELETE FROM {table} WHERE item_id=?", (item_id,))
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
    retire_input_vault(item_id)
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


def start_transcription_job_command(
    form: Any, upload: Any, *, admission_id: str | None
) -> tuple[dict[str, Any], int]:
    upload_dir: Path | None = None
    reserved_output_dir: Path | None = None
    registered_job_id: str | None = None
    try:
        with jobs_lock:
            if any(job.status in ACTIVE_JOB_STATUSES for job in jobs.values()):
                raise JobRequestError(
                    "別の文字起こしを処理中です。完了または中止までお待ちください。",
                    409,
                )
        source_path_raw = form.get("source_path", "").strip().strip('"')
        direct_input_path: Path | None = None
        if source_path_raw:
            if not local_path_access_allowed():
                raise ValueError("Direct local paths are disabled for remote access; upload the media instead.")
            direct_input_path = resolve_local_media_path(source_path_raw)
            original_name = direct_input_path.name
        elif upload is not None and upload.filename:
            original_name = Path(upload.filename).name
        else:
            raise ValueError("処理する音声・動画ファイルを選択してください。")
        original_name = normalize_source_name(original_name)
        if Path(original_name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError("対応形式は MP4/MOV/MKV/WAV/MP3/M4A/FLAC です。")

        model_name = form.get("model_name", "base")
        if model_name not in MODEL_NAMES:
            raise ValueError("認識モデルが不正です。")
        language_raw = form.get("language", "ja").strip()
        language = language_raw or None
        if language not in LANGUAGES:
            raise ValueError("言語が不正です。")
        audio_preprocess = parse_audio_preprocess(form=form)
        conversation_mode = form.get("conversation_mode", "meeting").strip()
        if conversation_mode not in CONVERSATION_MODES:
            raise ValueError("会話モードが不正です。")
        custom_vocabulary = normalize_custom_vocabulary(
            form.get("custom_vocabulary", "")
        )
        # Save here as well as from the UI's background save so a term entered
        # immediately before pressing start is retained for the next job.
        save_custom_vocabulary(custom_vocabulary)
        device = form.get("device", "cuda")
        diarization_device = form.get("diarization_device", "cpu")
        if device not in {"cpu", "cuda"} or diarization_device not in {"cpu", "cuda"}:
            raise ValueError("処理装置の指定が不正です。")
        machine = get_machine_profile()
        if (device == "cuda" or diarization_device == "cuda") and not machine["gpu"]["cuda_available"]:
            raise ValueError(
                "このマシンではGPU (CUDA)を利用できません。"
                "文字起こし装置と話者分離装置をCPUに設定してください。"
            )
        min_speakers = parse_optional_int("min_speakers", form=form)
        max_speakers = parse_optional_int("max_speakers", form=form)
        num_speakers = parse_optional_int("num_speakers", form=form)
        if min_speakers and max_speakers and min_speakers > max_speakers:
            raise ValueError("最少話者数は最多話者数以下にしてください。")
        triple_pass = parse_bool("triple_pass", form=form)
        boost_quiet_speech = parse_bool("boost_quiet_speech", default=True, form=form)
        if boost_quiet_speech or triple_pass:
            vad_onset = parse_optional_float(
                "vad_onset", 0.35, 0.05, 0.95, form=form
            )
            vad_offset = parse_optional_float(
                "vad_offset", 0.25, 0.05, 0.95, form=form
            )
            if vad_offset > vad_onset:
                raise ValueError("VAD offset は onset 以下にしてください。")
            # Keep quiet speech discoverable without accepting nearly silent
            # hallucinations, which often duplicate or tear adjacent turns.
            no_speech_threshold = 0.8
        else:
            vad_onset = 0.5
            vad_offset = 0.363
            no_speech_threshold = 0.6

        provider = form.get("ai_provider", "none")
        if provider not in AI_PROVIDERS:
            raise ValueError("AI プロバイダーが不正です。")
        finishing_mode_value = form.get("transcript_finishing_mode", "").strip()
        transcript_finishing_mode = finishing_mode_value or "custom"
        if transcript_finishing_mode not in TRANSCRIPT_FINISHING_MODES:
            raise ValueError("文章整形モードの指定が不正です。")
        clean_transcript = parse_bool("clean_transcript", form=form)
        detect_names = parse_bool("detect_speaker_names", form=form)
        create_outline = parse_bool("create_outline", form=form)
        finish_in_obsidian = parse_bool(
            "finish_in_obsidian", default=not finishing_mode_value, form=form
        )
        ai_efforts = normalize_efforts({
            key: form.get("ai_effort_" + key, "auto")
            for key in ("outline", "cleanup", "name_extract", "name_verify")
        })
        recommended_cleanup = False
        jev_compare = parse_bool("jev_compare", form=form)
        if transcript_finishing_mode == "off":
            clean_transcript = False
            detect_names = False
            create_outline = False
            jev_compare = False
            finish_in_obsidian = False
        elif transcript_finishing_mode == "recommended":
            # Jev triages each utterance and the configured cleanup effort
            # controls how much context the finishing LLM may read and rewrite.
            clean_transcript = False
            create_outline = False
            jev_compare = False
        elif transcript_finishing_mode == "advanced":
            clean_transcript = True
            detect_names = True
            finish_in_obsidian = False
            if provider == "none":
                raise ValueError("高度モードでは使用するAIを選択してください。")
        if provider == "none":
            clean_transcript = False
            detect_names = False
            create_outline = False
            jev_compare = False
        elif jev_compare:
            # The comparison needs a result from the existing finishing AI.
            clean_transcript = True
        emotion_analysis = parse_bool("emotion_analysis", form=form)
        emotion_model = form.get("emotion_model", "kushinada").strip() or "kushinada"
        if emotion_model not in AIST_EMOTION_MODEL_CHOICES:
            raise ValueError("感情分析モデルの指定が不正です。")
        token_config = load_token_config()
        if not token_config.huggingface_token:
            raise ValueError("tokens.json に huggingface_token を設定してください。")
        recommended_cleanup = bool(
            transcript_finishing_mode == "recommended"
            and provider != "none"
            and not finish_in_obsidian
            and ai_efforts.get("cleanup") != "off"
            and token_config.typesafe_api_key
        )
        if jev_compare and not token_config.typesafe_api_key:
            raise ValueError("Jev比較には tokens.json の typesafe_api_key が必要です。")
        ai_api_key = ""
        ai_model = ""
        ai_base_url = ""
        if clean_transcript or recommended_cleanup or detect_names or create_outline:
            ai_api_key, ai_model = configured_ai_credentials(token_config, provider)
            if provider == "lmstudio":
                ai_base_url = lmstudio_base_url(token_config.lmstudio_base_url)
                if not ai_model:
                    raise ValueError(local_llm_model_required_message())
            elif not ai_api_key:
                raise ValueError(
                    f"tokens.json に {ai_provider_label(provider)} のAPIキーを設定してください。"
                )

        output_raw = form.get("output_dir", "").strip().strip('"')
        if output_raw and not local_path_access_allowed():
            raise ValueError("Custom output paths are disabled for remote access.")
        output_root = prepare_output_root(output_raw)

        job_id = str(admission_id or uuid.uuid4().hex)
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
            num_speakers=num_speakers,
            device=device,
            diarization_device=diarization_device,
            triple_pass=triple_pass,
            boost_quiet_speech=boost_quiet_speech,
            vad_onset=vad_onset,
            vad_offset=vad_offset,
            no_speech_threshold=no_speech_threshold,
            write_srt=parse_bool("write_srt", form=form),
            write_json=True,
            burn_subtitled_video=parse_bool("burn_subtitled_video", form=form),
            ai_provider=provider,
            clean_transcript=clean_transcript,
            detect_speaker_names=detect_names,
            create_outline=create_outline,
            emotion_analysis=emotion_analysis,
            emotion_model=emotion_model,
            ai_api_key=ai_api_key,
            ai_model=ai_model,
            ai_base_url=ai_base_url,
            owns_output_dir=True,
            ai_efforts=ai_efforts,
            finish_in_obsidian=finish_in_obsidian,
            conversation_mode=conversation_mode,
            custom_vocabulary=custom_vocabulary,
            recommended_cleanup=recommended_cleanup,
            jev_compare=jev_compare,
            jev_api_key=token_config.typesafe_api_key,
            jev_model=token_config.typesafe_model,
            transcript_finishing_mode=transcript_finishing_mode,
            write_word_cloud=parse_bool("write_word_cloud", form=form),
            generate_meeting_minutes=parse_bool("generate_meeting_minutes", form=form),
        )
        job = JobRecord(
            id=job_id,
            source_name=original_name,
            output_dir=output_dir,
            write_srt=options.write_srt,
            write_json=True,
            conversation_mode=conversation_mode,
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
        return job.public(), 202
    except RequestEntityTooLarge:
        if registered_job_id:
            with jobs_lock:
                jobs.pop(registered_job_id, None)
        if upload_dir is not None:
            shutil.rmtree(upload_dir, ignore_errors=True)
        if reserved_output_dir is not None:
            remove_owned_directory(reserved_output_dir, ignore_errors=True)
        raise
    except JobRequestError:
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
        raise JobRequestError(str(exc), 400) from exc
    except (RuntimeError, OSError) as exc:
        if registered_job_id:
            with jobs_lock:
                jobs.pop(registered_job_id, None)
        if upload_dir is not None:
            shutil.rmtree(upload_dir, ignore_errors=True)
        if reserved_output_dir is not None:
            remove_owned_directory(reserved_output_dir, ignore_errors=True)
        raise JobRequestError(str(exc), 500) from exc


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


register_library_group_routes(
    app,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    library_write_lock=library_write_lock,
)


register_training_routes(
    app,
    remote_access_enabled=lambda: REMOTE_ACCESS_ENABLED,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    refresh_training_exports=refresh_training_exports,
    training_events_from_connection=lambda *args, **kwargs: training_events_from_connection(*args, **kwargs),
)


register_export_routes(
    app,
    database_connection=lambda *args, **kwargs: database_connection(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    list_speaker_registry=list_speaker_registry,
    meeting_minutes_export_row=meeting_minutes_export_row,
    row_segments=lambda *args, **kwargs: row_segments(*args, **kwargs),
    row_session_profile=lambda *args, **kwargs: row_session_profile(*args, **kwargs),
    row_speaker_profiles=lambda *args, **kwargs: row_speaker_profiles(*args, **kwargs),
)


register_analysis_view_routes(
    app,
    AnalysisConflictError=AnalysisConflictError,
    analysis_archive_store=lambda *args, **kwargs: analysis_archive_store(*args, **kwargs),
    build_research_analysis=lambda *args, **kwargs: build_research_analysis(*args, **kwargs),
    group_analysis_for_row=lambda *args, **kwargs: group_analysis_for_row(*args, **kwargs),
    library_row=lambda *args, **kwargs: library_row(*args, **kwargs),
    public_diagnostic_text=public_diagnostic_text,
    save_group_analysis=save_group_analysis,
    transformer_semantic_search=lambda *args, **kwargs: transformer_semantic_search(*args, **kwargs),
)


register_ai_routes(
    app,
    lmstudio_reasoning_settings=lambda *args, **kwargs: lmstudio_reasoning_settings(*args, **kwargs),
    load_token_config=lambda *args, **kwargs: load_token_config(*args, **kwargs),
)


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
        application_lifecycle().shutdown()


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
    start_obsidian_watcher()
    try:
        app.run(host=host, port=port, threaded=True, use_reloader=False)
    finally:
        application_lifecycle().stop_watcher()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
