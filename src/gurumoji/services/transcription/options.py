"""Transcription job options and the values the start form accepts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...ai_effort import normalize_efforts
from ...jev_review import JEV_DEFAULT_MODEL


ACTIVE_JOB_STATUSES = frozenset({"queued", "running", "committing"})
MODEL_NAMES = {"tiny", "base", "small", "medium", "large-v3"}
LANGUAGES = {None, "ja", "en", "zh", "ko"}
AIST_EMOTION_MODEL_CHOICES = {"kushinada", "izanami", "both"}
CONVERSATION_MODES = {
    "meeting": "meeting",
    "group_interview": "focus_group",
    "chat": "chat",
}
# The one place for the new-job defaults: the form renders them, /api/config
# returns them and the start handler falls back to them (CFG-03).
DEFAULT_CONVERSATION_MODE = "meeting"
DEFAULT_FINISH_IN_OBSIDIAN = True
# Recognition settings each recording type writes into the form (keys as app.js reads them).
CONVERSATION_MODE_PRESETS = {
    "meeting": {
        "label": "会議モード", "minSpeakers": 2, "maxSpeakers": 10, "audioPreprocess": "standard",
        "boostQuietSpeech": True, "triplePass": False, "vadOnset": "0.35", "vadOffset": "0.25",
        "hint": "会議向けの設定を適用中。話者数や前処理は「認識・話者分離」で変更できます。",
    },
    "group_interview": {
        "label": "グループインタビューモード", "minSpeakers": 3, "maxSpeakers": 12, "audioPreprocess": "standard",
        "boostQuietSpeech": True, "triplePass": False, "vadOnset": "0.30", "vadOffset": "0.22",
        "hint": "グループインタビュー向けの設定を適用中。話者数や前処理は「認識・話者分離」で変更できます。",
    },
    "chat": {
        "label": "雑談モード", "minSpeakers": 2, "maxSpeakers": 6, "audioPreprocess": "light",
        "boostQuietSpeech": True, "triplePass": False, "vadOnset": "0.42", "vadOffset": "0.30",
        "hint": "雑談向けの設定を適用中。話者数や前処理は「認識・話者分離」で変更できます。",
    },
}


def job_defaults() -> dict:
    return {"conversation_mode": DEFAULT_CONVERSATION_MODE,
            "finish_in_obsidian": DEFAULT_FINISH_IN_OBSIDIAN,
            "conversation_mode_presets": CONVERSATION_MODE_PRESETS}


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
    finish_in_obsidian: bool = DEFAULT_FINISH_IN_OBSIDIAN
    ai_efforts: dict = field(default_factory=normalize_efforts)
    num_speakers: int | None = None
    conversation_mode: str = DEFAULT_CONVERSATION_MODE
    custom_vocabulary: tuple[str, ...] = ()
    recommended_cleanup: bool = False
    jev_compare: bool = False
    jev_api_key: str = ""
    jev_model: str = JEV_DEFAULT_MODEL
    transcript_finishing_mode: str = "custom"
    write_word_cloud: bool = False
    generate_meeting_minutes: bool = False
