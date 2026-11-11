"""Run the transcription job while the application supplies its mutable boundaries."""

from __future__ import annotations

import gc
import json
import shutil
import sqlite3
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any, Mapping

from ...ai_effort import cleanup_enabled
from ...ai_finishing import FINISHING_VERSION, RECOMMENDED_FINISHING_VERSION
from ..ai.transcript_finishing import run_full_cleanup
from ..notation import NOTATION_VERSION
from .prior_context import recognition_hint_terms

class _TranscriptionJob:
    def __init__(self, job: Any, options: Any, dependencies: Mapping[str, Any]) -> None:
        self.job = job
        self.options = options
        self.dependencies = dependencies
        self.TranscriptionReporter = dependencies["TranscriptionReporter"]
        self.CONVERSATION_MODES = dependencies["CONVERSATION_MODES"]
        self.DIARIZATION_MODEL = dependencies["DIARIZATION_MODEL"]
        self.MAX_LOG_LINES = dependencies["MAX_LOG_LINES"]
        self.NORMAL_NO_SPEECH_THRESHOLD = dependencies["NORMAL_NO_SPEECH_THRESHOLD"]
        self.NORMAL_VAD_OFFSET = dependencies["NORMAL_VAD_OFFSET"]
        self.NORMAL_VAD_ONSET = dependencies["NORMAL_VAD_ONSET"]
        self.TRIPLE_PASS_GAP_CONTEXT_SECONDS = dependencies["TRIPLE_PASS_GAP_CONTEXT_SECONDS"]
        self.TRIPLE_PASS_MIN_GAP_SECONDS = dependencies["TRIPLE_PASS_MIN_GAP_SECONDS"]
        self.UPLOAD_DIRECTORY = dependencies["UPLOAD_DIRECTORY"]
        self.WHISPER_SAMPLE_RATE = dependencies["WHISPER_SAMPLE_RATE"]
        self.aist_emotion_model_keys = dependencies["aist_emotion_model_keys"]
        self.apply_speaker_identity_repairs = dependencies["apply_speaker_identity_repairs"]
        self.attach_jev_comparison = dependencies["attach_jev_comparison"]
        self.audio_preprocess_label = dependencies["audio_preprocess_label"]
        self.build_emotion_analysis_summary = dependencies["build_emotion_analysis_summary"]
        self.build_meeting_minutes = dependencies["build_meeting_minutes"]
        self.clean_recommended_segments_with_ai = dependencies["clean_recommended_segments_with_ai"]
        self.clean_segments_with_ai = dependencies["clean_segments_with_ai"]
        self.cleanup_uncommitted_job_artifacts = dependencies["cleanup_uncommitted_job_artifacts"]
        self.commit_staged_media = dependencies["commit_staged_media"]
        self.configure_huggingface_hub_compatibility = dependencies["configure_huggingface_hub_compatibility"]
        self.configure_speechbrain_lazy_import_compatibility = dependencies["configure_speechbrain_lazy_import_compatibility"]
        self.create_diarization_pipeline = dependencies["create_diarization_pipeline"]
        self.create_outline_with_ai = dependencies["create_outline_with_ai"]
        self.detect_speaker_names_with_ai = dependencies["detect_speaker_names_with_ai"]
        self.diarization_access_error_message = dependencies["diarization_access_error_message"]
        self.display_time = dependencies["display_time"]
        self.ensure_segment_ids = dependencies["ensure_segment_ids"]
        self.find_long_asr_gaps = dependencies["find_long_asr_gaps"]
        self.is_diarization_access_error = dependencies["is_diarization_access_error"]
        self.is_video_path = dependencies["is_video_path"]
        self.jobs_lock = dependencies["jobs_lock"]
        self.json_load = dependencies["json_load"]
        self.make_display_segments = dependencies["make_display_segments"]
        self.merge_ai_usage = dependencies["merge_ai_usage"]
        self.merge_supplemental_asr_segments = dependencies["merge_supplemental_asr_segments"]
        self.normalize_ai_usage = dependencies["normalize_ai_usage"]
        self.normalize_asr_segments = dependencies["normalize_asr_segments"]
        self.normalize_conversation_speaker_profiles = dependencies["normalize_conversation_speaker_profiles"]
        self.normalize_meeting_minutes = dependencies["normalize_meeting_minutes"]
        self.obsidian_workbench = dependencies["obsidian_workbench"]
        self.offset_asr_segments_to_gap = dependencies["offset_asr_segments_to_gap"]
        self.path_entry_exists = dependencies["path_entry_exists"]
        self.publish_input_vault = dependencies["publish_input_vault"]
        self.publish_meeting_minutes_to_obsidian = dependencies["publish_meeting_minutes_to_obsidian"]
        self.register_detected_speakers = dependencies["register_detected_speakers"]
        self.review_segments_with_jev = dependencies["review_segments_with_jev"]
        self.row_segments = dependencies["row_segments"]
        self.row_session_profile = dependencies["row_session_profile"]
        self.row_speaker_profiles = dependencies["row_speaker_profiles"]
        self.run_aist_emotion_analysis = dependencies["run_aist_emotion_analysis"]
        self.run_audio_interval_preprocess = dependencies["run_audio_interval_preprocess"]
        self.run_audio_preprocess = dependencies["run_audio_preprocess"]
        self.run_diarization_audio_preprocess = dependencies["run_diarization_audio_preprocess"]
        self.safe_output_stem = dependencies["safe_output_stem"]
        self.safe_token_count = dependencies["safe_token_count"]
        self.session_profile_from_media = dependencies["session_profile_from_media"]
        self.stage_media_archive = dependencies["stage_media_archive"]
        self.transcript_formatting_result = dependencies["transcript_formatting_result"]
        self.update_job = dependencies["update_job"]
        self.upsert_library_item = dependencies["upsert_library_item"]
        self.whisper_vault_settings = dependencies["whisper_vault_settings"]
        self.whisper_vocabulary_prompt = dependencies["whisper_vocabulary_prompt"]
        self.write_outputs = dependencies["write_outputs"]
        self.write_subtitled_video_assets = dependencies["write_subtitled_video_assets"]
        self.model: Any = None
        self.model_a: Any = None
        self.audio: Any = None
        self.diarize_model: Any = None
        self.diarize_segments: Any = None
        self.staged_media_path: Path | None = None

        self.reporter = self.TranscriptionReporter(
            job=self.job,
            update_job=self.update_job,
            jobs_lock=self.jobs_lock,
            normalize_usage=self.normalize_ai_usage,
            merge_usage=self.merge_ai_usage,
        )
        self.status = self.reporter.status
        self.progress = self.reporter.progress
        self.set_stage = self.reporter.stage
        self.record_ai_usage = self.reporter.record_ai_usage
        self.check_cancelled = self.reporter.check_cancelled
        self.record_warning = self.reporter.warning

    def run(self) -> None:
        with self.jobs_lock:
            self.job.status = "running"
        try:
            self._prepare_environment()
            if self.options.transcription_backend in ("qwen3_nemotron", "haas_ja"):
                self._run_external_stack()
            else:
                self._configure_whisper()
                self._transcribe_whisper()
                self._align()
                self._diarize()
                self._assign_speakers()
            self._prepare_finishing()
            self._finish_transcript()
            self._analyze_emotion()
            self._identify_speakers()
            self._prepare_minutes()
            self._write_results()
        except InterruptedError as exc:
            with self.jobs_lock:
                self.job.status = "cancelled"
                self.job.error = str(exc)
            self.set_stage("cancelled", "処理を中止", self.job.stage_progress)
            self.status(str(exc))
        except Exception as exc:
            details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            with self.jobs_lock:
                self.job.status = "failed"
                self.job.error = details
            self.set_stage("failed", "エラー", self.job.stage_progress)
            self.status("処理を完了できませんでした: " + details)
        finally:
            if self.staged_media_path is not None:
                self.staged_media_path.unlink(missing_ok=True)
            with self.jobs_lock:
                terminal_status = self.job.status
                if self.job.status in {"completed", "failed", "cancelled"}:
                    self.job.finished_at = time.time()
            if terminal_status in {"failed", "cancelled"}:
                cleanup_warnings = self.cleanup_uncommitted_job_artifacts(self.job, self.options)
                if cleanup_warnings:
                    with self.jobs_lock:
                        warning_text = "\n".join(cleanup_warnings)
                        self.job.output_warning = "\n".join(
                            value for value in (self.job.output_warning, warning_text) if value
                        )
                        self.job.logs.extend(cleanup_warnings)
                        self.job.logs = self.job.logs[-self.MAX_LOG_LINES:]
            if self.model is not None:
                del self.model
            if self.model_a is not None:
                del self.model_a
            self.diarize_model = None
            self.diarize_segments = None
            self.audio = None
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            # Processing files and any uploaded browser copy are isolated in this job directory.
            upload_parent = self.options.work_dir.resolve()
            upload_root = self.UPLOAD_DIRECTORY.resolve()
            if upload_parent.parent == upload_root and upload_parent.name == self.job.id:
                shutil.rmtree(upload_parent, ignore_errors=True)

    def _prepare_environment(self) -> None:
        self.check_cancelled()
        self.set_stage("environment", "処理環境の確認", 5)
        self.progress(2)
        self.status("処理環境を確認しています…")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg が見つかりません。README の手順でインストールしてください。")
        self.internal_work_dir = self.options.work_dir / ".pipeline_internal"
        self.internal_work_dir.mkdir(parents=True, exist_ok=True)
        self.processing_input_path = self.options.input_path
        if self.options.audio_preprocess != "none":
            label = self.audio_preprocess_label(self.options.audio_preprocess)
            self.set_stage("preprocess", "音声の前処理", 10)
            self.status(f"文字起こし用に音声を前処理しています（{label}）…")
            processed_path = self.internal_work_dir / "preprocessed.wav"
            self.processing_input_path = self.run_audio_preprocess(
                self.options.input_path,
                processed_path,
                self.options.audio_preprocess,
                self.check_cancelled,
            )
            self.set_stage("preprocess", "音声の前処理", 100)
            self.status("前処理済み音声を使用します（16kHz / mono / WAV）。")
        else:
            self.status("音声前処理は行わず、元ファイルの音声を使用します。")
        self.check_cancelled()
        self.set_stage("environment", "処理環境の確認", 100)
        self.progress(8)

    def _prepare_finishing(self) -> None:
        # Speaker identification uses the unedited transcript as a dedicated
        # source so text cleanup cannot remove or rewrite a self-introduction.
        self.speaker_identity_segments = [dict(item) for item in self.segments]
        self.obsidian_prepared = False
        self.finishing_stages = {"outline_context": "not_requested", "cleanup": "not_requested",
                            "recommended_cleanup": "not_requested",
                            "jev_comparison": "not_requested",
                            "speaker_identity": "not_requested", "outline": "not_requested"}
        self.jev_usage: dict[str, Any] = {}
        self.check_cancelled()
        self.set_stage("speaker_assignment", "話者ラベルの割り当て", 100)

        # Diarization and the full decoded audio are no longer needed. Releasing
        # them before optional emotion inference substantially reduces peak VRAM.
        self.diarize_segments = None
        self.diarize_model = None
        self.audio = None
        self.result = None
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


    def _run_external_stack(self) -> None:
        haas_selected = self.options.transcription_backend == "haas_ja"
        asr_label = "Haas-ja" if haas_selected else "Qwen3-ASR / ForcedAligner"
        import numpy as np
        import torch
        import wave
        import whisperx
        self.torch = torch

        from .haas_stack import run_haas_stack
        from .qwen_stack import run_qwen_stack

        self.device = self.options.device
        diarization_device = self.options.diarization_device
        if (self.device == "cuda" or diarization_device == "cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable. Select CPU or install a CUDA-enabled PyTorch runtime.")
        self.set_stage("transcription", asr_label, 10)
        self.status(
            "Running Haas-ja (experimental, official release)."
            if haas_selected
            else "Running Qwen3-ASR with Qwen3 ForcedAligner."
        )
        qwen_audio = whisperx.load_audio(str(self.processing_input_path))
        qwen_audio_path = self.internal_work_dir / "qwen-asr-input.wav"
        pcm_audio = (np.clip(np.asarray(qwen_audio), -1.0, 1.0) * 32767).astype("<i2")
        with wave.open(str(qwen_audio_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.WHISPER_SAMPLE_RATE)
            wav_file.writeframes(pcm_audio.tobytes())
        del qwen_audio, pcm_audio

        if self.processing_input_path != self.options.input_path:
            qwen_diarization_path = self.run_diarization_audio_preprocess(
                self.options.input_path,
                self.internal_work_dir / "nemotron-input.wav",
                self.check_cancelled,
            )
        else:
            qwen_diarization_path = qwen_audio_path

        qwen_result = (run_haas_stack if haas_selected else run_qwen_stack)(
            asr_audio_path=qwen_audio_path,
            diarization_audio_path=qwen_diarization_path,
            work_dir=self.internal_work_dir,
            language=self.options.language,
            asr_device=self.device,
            diarization_device=diarization_device,
            status=self.status,
            check_cancelled=self.check_cancelled,
        )
        self.language_code = self.options.language or qwen_result.get("language")
        self.result = {"language": self.language_code, "segments": qwen_result["segments"]}
        self.audio = None
        self.set_stage("transcription", asr_label, 100)
        self.progress(64)
        self.set_stage("alignment", "Segment timestamps" if haas_selected else "Qwen3 ForcedAligner", 100)
        self.progress(72)
        self.set_stage("diarization", "Nemotron 3 Diarization", 100)
        self.progress(80)
        self.set_stage("speaker_assignment", "Speaker assignment", 100)
        self.segments = self.ensure_segment_ids(self.job.id, self.make_display_segments(self.result["segments"]))
        if not self.segments:
            raise RuntimeError(f"{asr_label} returned no transcript segments.")

    def _configure_whisper(self) -> None:
        try:
            import torch

            self.configure_huggingface_hub_compatibility()
            import whisperx

            self.configure_speechbrain_lazy_import_compatibility()
            from whisperx.diarize import DiarizationPipeline
        except ImportError as exc:
            raise RuntimeError("必要な Python パッケージがありません。run.bat でセットアップしてください。") from exc

        self.device = self.options.device
        diarization_device = self.options.diarization_device
        needs_cuda = self.device == "cuda" or diarization_device == "cuda"
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
        use_openai_whisper = self.device == "cpu" or (capability is not None and capability[0] < 7)
        if self.device == "cuda":
            assert capability is not None
            self.status(
                f"GPU: {gpu_name} / VRAM {vram_gib:.1f} GB / "
                f"Compute Capability {capability[0]}.{capability[1]}"
            )
            if capability[0] < 7 and self.options.model_name not in {"tiny", "base"}:
                raise RuntimeError("旧世代 4 GB GPU では tiny / base だけを選べます。")
        else:
            self.status("文字起こしは CPU を使用します。")

        backend = "OpenAI Whisper" if use_openai_whisper else "WhisperX (faster-whisper)"
        hint_terms = recognition_hint_terms(
            self.options.custom_vocabulary, self.options.prior_speakers, self.options.prior_outline
        )
        vocabulary_prompt = self.whisper_vocabulary_prompt(hint_terms)
        if vocabulary_prompt:
            self.status(
                f"単語登録・事前話者情報・事前アウトラインをWhisperの認識ヒントに使用します"
                f"（{len(hint_terms)}語・先頭から順に使用）。"
            )

        self.torch = torch
        self.whisperx = whisperx
        self.DiarizationPipeline = DiarizationPipeline
        self.diarization_device = diarization_device
        self.compute_type = compute_type
        self.use_openai_whisper = use_openai_whisper
        self.backend = backend
        self.hint_terms = hint_terms
        self.vocabulary_prompt = vocabulary_prompt
        if self.options.triple_pass:
            self.status(
                f"詳細処理を使います。通常結果の{self.TRIPLE_PASS_MIN_GAP_SECONDS:g}秒以上の空白だけを、"
                "軽め・強めの順で切り出して補完します。"
            )
        elif self.options.boost_quiet_speech:
            self.status(
                "小さい声を拾いやすくする設定を使います（"
                + self._decoding_settings_text(
                    self.options.vad_onset, self.options.vad_offset, self.options.no_speech_threshold
                )
                + "）…"
            )


    def _transcribe_whisper(self) -> None:
        if self.options.triple_pass:
            primary_vad_onset = self.NORMAL_VAD_ONSET
            primary_vad_offset = self.NORMAL_VAD_OFFSET
            primary_no_speech_threshold = self.NORMAL_NO_SPEECH_THRESHOLD
            primary_progress = 26
        else:
            primary_vad_onset = self.options.vad_onset
            primary_vad_offset = self.options.vad_offset
            primary_no_speech_threshold = self.options.no_speech_threshold
            primary_progress = 52

        self.result, self.audio = self._transcribe_pass(
            "通常モード",
            self.processing_input_path,
            self.options.language,
            primary_vad_onset,
            primary_vad_offset,
            primary_no_speech_threshold,
            primary_progress,
        )
        self.language_code = self.options.language or self.result.get("language")

        if self.options.triple_pass:
            audio_duration = len(self.audio) / self.WHISPER_SAMPLE_RATE
            original_segments = self.result.get("segments", [])
            original_count = len(self.normalize_asr_segments(original_segments))

            light_gaps = self.find_long_asr_gaps(original_segments, audio_duration)
            light_result = self._transcribe_gap_pass(
                "2回目（軽め）",
                "light",
                light_gaps,
                audio_duration,
                self.language_code,
                self.options.vad_onset,
                self.options.vad_offset,
                self.options.no_speech_threshold,
                38,
            )
            if not self.language_code:
                self.language_code = light_result.get("language")
            after_light, light_counts = self.merge_supplemental_asr_segments(
                original_segments,
                [("長い空白・軽め", light_result.get("segments", []))],
            )

            strong_gaps = self.find_long_asr_gaps(after_light, audio_duration)
            strong_result = self._transcribe_gap_pass(
                "3回目（強め）",
                "strong",
                strong_gaps,
                audio_duration,
                self.language_code,
                self.options.vad_onset,
                self.options.vad_offset,
                self.options.no_speech_threshold,
                50,
            )
            if not self.language_code:
                self.language_code = strong_result.get("language")
            merged_segments, strong_counts = self.merge_supplemental_asr_segments(
                after_light,
                [("長い空白・強め", strong_result.get("segments", []))],
            )
            self.result = dict(self.result)
            self.result["segments"] = merged_segments
            if self.language_code:
                self.result["language"] = self.language_code
            self.status(
                "詳細処理の統合完了: "
                f"通常 {original_count} 区間、"
                f"2回目 {len(light_gaps)} 空白から +{light_counts.get('長い空白・軽め', 0)}、"
                f"3回目 {len(strong_gaps)} 空白から +{strong_counts.get('長い空白・強め', 0)} を追加しました。"
            )
        self.check_cancelled()
        self.progress(52)


    def _decoding_settings_text(self, 
        vad_onset: float, vad_offset: float, no_speech_threshold: float
    ) -> str:
        # OpenAI Whisper has no VAD stage, so only the no-speech threshold
        # reaches the decoder there; never report VAD values it ignores.
        if self.use_openai_whisper:
            return (
                f"VADなし・無音判定しきい値 no_speech_threshold={no_speech_threshold:.2f}"
            )
        return f"VAD onset={vad_onset:.2f}, offset={vad_offset:.2f}"

    def _release_asr_model(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()

    def _load_asr_model(self, 
        language_hint: str | None,
        vad_onset: float,
        vad_offset: float,
        no_speech_threshold: float,
    ) -> None:
        if self.use_openai_whisper:
            import whisper

            self.model = whisper.load_model(self.options.model_name, device=self.device)
        else:
            asr_options: dict[str, Any] = {
                "no_speech_threshold": no_speech_threshold,
            }
            if self.vocabulary_prompt:
                # WhisperX stores faster-whisper decoding options on the
                # pipeline when the model is loaded; its transcribe()
                # method does not accept initial_prompt.
                asr_options["initial_prompt"] = self.vocabulary_prompt
            self.model = self.whisperx.load_model(
                self.options.model_name,
                self.device,
                device_index=0,
                compute_type=self.compute_type,
                language=language_hint,
                asr_options=asr_options,
                vad_options={"vad_onset": vad_onset, "vad_offset": vad_offset},
            )

    def _transcribe_pass(self, 
        pass_label: str,
        audio_path: Path,
        language_hint: str | None,
        vad_onset: float,
        vad_offset: float,
        no_speech_threshold: float,
        progress_value: int,
    ) -> tuple[dict[str, Any], Any]:
        self.set_stage("transcription", f"{pass_label}の文字起こし", 10)
        self.status(f"{pass_label}: 音声認識モデルを読み込んでいます（{self.options.model_name} / {self.backend}）…")
        # ?????????????????????????
        self._load_asr_model(
            language_hint,
            vad_onset,
            vad_offset,
            no_speech_threshold,
        )
        self.check_cancelled()
        self.set_stage("transcription", f"{pass_label}の文字起こし", 35)

        self.status(
            f"{pass_label}: 音声を読み込み、文字起こししています（"
            + self._decoding_settings_text(vad_onset, vad_offset, no_speech_threshold)
            + "）…"
        )
        pass_audio = self.whisperx.load_audio(str(audio_path))
        if self.use_openai_whisper:
            transcribe_kwargs: dict[str, Any] = {
                "language": language_hint,
                "fp16": False,
                "verbose": False,
                "condition_on_previous_text": False,
                "no_speech_threshold": no_speech_threshold,
                "word_timestamps": True,
            }
        else:
            transcribe_kwargs = {"batch_size": 1}
        if self.vocabulary_prompt and self.use_openai_whisper:
            transcribe_kwargs["initial_prompt"] = self.vocabulary_prompt
        pass_result = self.model.transcribe(pass_audio, **transcribe_kwargs)
        self.set_stage("transcription", f"{pass_label}の文字起こし", 90)
        self._release_asr_model()
        self.check_cancelled()
        self.set_stage("transcription", f"{pass_label}の文字起こし", 100)
        self.progress(progress_value)
        return pass_result, pass_audio

    def _transcribe_gap_pass(self, 
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
            self.set_stage("transcription", f"{pass_label}の文字起こし", 100)
            self.status(f"{pass_label}: {self.TRIPLE_PASS_MIN_GAP_SECONDS:g}秒以上の空白はありません。")
            self.progress(progress_value)
            return {"segments": [], "language": language_hint}

        total_gap_seconds = sum(end - start for start, end in gaps)
        self.set_stage("transcription", f"{pass_label}の文字起こし", 10)
        self.status(
            f"{pass_label}: {len(gaps)}か所、計{total_gap_seconds:.1f}秒の空白だけを再確認します。"
        )
        self.status(f"{pass_label}: 音声認識モデルを読み込んでいます（{self.options.model_name} / {self.backend}）…")
        # ?????????????????????????
        self._load_asr_model(
            language_hint,
            vad_onset,
            vad_offset,
            no_speech_threshold,
        )
        detected_language = language_hint
        collected: list[dict[str, Any]] = []
        try:
            for index, (gap_start, gap_end) in enumerate(gaps, 1):
                self.check_cancelled()
                self.set_stage(
                    "transcription",
                    f"{pass_label}の文字起こし",
                    15 + round(75 * (index - 1) / max(1, len(gaps))),
                )
                clip_start = max(0.0, gap_start - self.TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                clip_end = min(audio_duration, gap_end + self.TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                self.status(
                    f"{pass_label}: 空白 {index}/{len(gaps)} "
                    f"（{self.display_time(gap_start)}–{self.display_time(gap_end)}）を切り出して再文字起こししています…"
                )
                clip_path = self.internal_work_dir / f"gap_{preset}_{index:04d}.wav"
                try:
                    self.run_audio_interval_preprocess(
                        self.options.input_path,
                        clip_path,
                        clip_start,
                        clip_end,
                        preset,
                        self.check_cancelled,
                    )
                    clip_audio = self.whisperx.load_audio(str(clip_path))
                    if self.use_openai_whisper:
                        transcribe_kwargs = {
                            "language": detected_language,
                            "fp16": False,
                            "verbose": False,
                            "condition_on_previous_text": False,
                            "no_speech_threshold": no_speech_threshold,
                            "word_timestamps": True,
                        }
                    else:
                        transcribe_kwargs = {"batch_size": 1}
                    if self.vocabulary_prompt and self.use_openai_whisper:
                        transcribe_kwargs["initial_prompt"] = self.vocabulary_prompt
                    clip_result = self.model.transcribe(clip_audio, **transcribe_kwargs)
                    if not detected_language:
                        detected_language = clip_result.get("language")
                    collected.extend(
                        self.offset_asr_segments_to_gap(
                            clip_result.get("segments", []),
                            clip_start,
                            gap_start,
                            gap_end,
                        )
                    )
                finally:
                    clip_path.unlink(missing_ok=True)
        finally:
            self._release_asr_model()
        self.check_cancelled()
        self.set_stage("transcription", f"{pass_label}の文字起こし", 100)
        self.progress(progress_value)
        return {"segments": collected, "language": detected_language}

    def _align(self) -> None:
        if self.language_code:
            try:
                self.set_stage("alignment", "発話時刻の補正", 10)
                self.status("発話時刻を整えています…")
                self.model_a, metadata = self.whisperx.load_align_model(language_code=self.language_code, device=self.device)
                self.result = self.whisperx.align(
                    self.result["segments"], self.model_a, metadata, self.audio, self.device, return_char_alignments=False
                )
            except InterruptedError:
                raise
            except Exception as exc:
                self.status(f"時刻補正を省略しました: {exc}")
            finally:
                if self.model_a is not None:
                    del self.model_a
                    self.model_a = None
                gc.collect()
                if self.device == "cuda":
                    self.torch.cuda.empty_cache()
        self.check_cancelled()
        self.set_stage("alignment", "発話時刻の補正", 100)
        self.progress(64)


    def _diarize(self) -> None:
        self.set_stage("diarization", "話者の分離", 10)
        if self.processing_input_path != self.options.input_path:
            # The transcription presets denoise, band-limit and normalize, which
            # reshapes the voice characteristics speaker embeddings compare.
            # Diarize the original recording instead, with only too-quiet speech
            # lifted so soft speakers still reach the segmentation model.
            # Both filters preserve timing, so every stage shares one clock.
            self.status("話者分離用に、元音声の小さすぎる声だけを持ち上げています…")
            diarization_path = self.run_diarization_audio_preprocess(
                self.options.input_path,
                self.internal_work_dir / "diarization.wav",
                self.check_cancelled,
            )
            self.audio = None
            gc.collect()
            self.audio = self.whisperx.load_audio(str(diarization_path))
            diarization_path.unlink(missing_ok=True)
            self.check_cancelled()
        self.status(f"話者を分離しています（{self.diarization_device.upper()}）…")
        try:
            self.diarize_model = self.create_diarization_pipeline(
                self.DiarizationPipeline, self.options.hf_token, self.diarization_device
            )
        except Exception as exc:
            if self.is_diarization_access_error(exc):
                raise RuntimeError(self.diarization_access_error_message(self.DIARIZATION_MODEL)) from exc
            raise
        diarize_kwargs: dict[str, int] = {}
        if self.options.num_speakers is not None:
            diarize_kwargs["num_speakers"] = self.options.num_speakers
        elif self.options.min_speakers is not None:
            diarize_kwargs["min_speakers"] = self.options.min_speakers
        if self.options.num_speakers is None and self.options.max_speakers is not None:
            diarize_kwargs["max_speakers"] = self.options.max_speakers
        self.diarize_segments = self.diarize_model(self.audio, **diarize_kwargs)
        self.check_cancelled()
        self.set_stage("diarization", "話者の分離", 100)
        self.progress(80)


    def _assign_speakers(self) -> None:
        self.set_stage("speaker_assignment", "話者ラベルの割り当て", 15)
        self.status("話者ラベルを文字起こしに対応付けています…")
        self.result = self.whisperx.assign_word_speakers(
            self.diarize_segments,
            self.result,
            fill_nearest=True,
        )
        self.segments = self.ensure_segment_ids(self.job.id, self.make_display_segments(self.result.get("segments", [])))
        if not self.segments:
            raise RuntimeError("文字起こし結果が空でした。音声が含まれているか確認してください。")

    def _finish_transcript(self) -> None:
        # Freeze the ASR/diarization output before any AI rewriting.
        self.segments = self.ensure_segment_ids(self.job.id, self.segments)
        self.imported_transcript = json.loads(json.dumps(self.segments, ensure_ascii=False))
        self.set_stage("finishing", "文字起こしの仕上げ", 10)
        self.ai_base_kwargs = (
            {"base_url": self.options.ai_base_url}
            if self.options.ai_provider == "lmstudio" else {}
        )
        if any(level != "auto" for key, level in self.options.ai_efforts.items()
               if key != "notation" or level != "off"):
            self.ai_base_kwargs["ai_efforts"] = self.options.ai_efforts
        context_outline: dict[str, Any] | None = None
        if (self.options.recommended_cleanup and not self.options.finish_in_obsidian
                and self.options.ai_efforts.get("cleanup", "medium") != "off"):
            try:
                cleanup_effort = self.options.ai_efforts.get("cleanup", "medium")
                if cleanup_effort == "auto":
                    cleanup_effort = "medium"
                if cleanup_effort in {"high", "ultra"}:
                    self.status("おすすめ文章整形の参照用アウトラインを作成しています…")
                    context_outline = self.create_outline_with_ai(
                        self.segments, {}, self.options.ai_provider, self.options.ai_api_key, self.options.ai_model,
                        self.status, self.check_cancelled, self.record_ai_usage, **self.ai_base_kwargs,
                    )
                    if not context_outline.get("sections"):
                        raise RuntimeError("会話全体のアウトラインが空でした。")
                    self.finishing_stages["outline_context"] = "completed"
                recommended_reviews, self.jev_usage = self.review_segments_with_jev(
                    self.imported_transcript,
                    self.options.jev_api_key,
                    self.options.jev_model,
                    self.status,
                    self.check_cancelled,
                    outline=context_outline,
                )
                self.segments = self.clean_recommended_segments_with_ai(
                    self.segments,
                    recommended_reviews,
                    self.options.ai_provider,
                    self.options.ai_api_key,
                    self.options.ai_model,
                    self.status,
                    self.check_cancelled,
                    self.record_ai_usage,
                    effort=cleanup_effort,
                    outline=context_outline,
                    **self.ai_base_kwargs,
                )
                self.finishing_stages["recommended_cleanup"] = "completed"
                self.check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                self.finishing_stages["recommended_cleanup"] = "failed"
                self.record_warning(
                    "おすすめのJev判定・発話単位LLM整形を省略しました。元の文字起こしを保存します: "
                    + details
                )
        full_cleanup = None
        if ((self.options.clean_transcript or self.options.jev_compare or self.options.ai_efforts.get("notation", "off") != "off")
                and not self.options.finish_in_obsidian):
            # The same order and stage record as the Obsidian workbench (ARCH-07).




            full_cleanup = run_full_cleanup(
                self.segments,
                check_cancelled=self.check_cancelled,
                create_context_outline=self._create_context_outline,
                clean_with_outline=(self._clean_with_outline
                                    if self.options.clean_transcript and cleanup_enabled(self.options.ai_efforts)
                                    else None),
                review_with_jev=self._review_original_with_jev if self.options.jev_compare else None,
                attach_jev=self.attach_jev_comparison,
                on_failure=self._warn_full_cleanup,
                ai_efforts=self.options.ai_efforts,
                unify_notation=lambda source: self.dependencies["unify_notation"](
                    source, self.options.ai_provider, self.options.ai_api_key, self.options.ai_model,
                    self.check_cancelled, self.record_ai_usage, **self.ai_base_kwargs),
            )
            self.segments = full_cleanup["segments"]
            self.finishing_stages.update(full_cleanup["stages"])
            if full_cleanup["stages"].get("jev_comparison") == "completed":
                self.jev_usage = full_cleanup["jev_usage"]
        self.finishing_history = [{
            "segments": json.loads(json.dumps(full_cleanup["before_notation"] if full_cleanup else self.segments, ensure_ascii=False)), "speaker_names": {},
            "origin": "ai" if any(self.finishing_stages.get(s) == "completed" for s in (
                "cleanup", "recommended_cleanup", "jev_comparison")) else "rule",
            "process": "ai_finishing" if any(self.finishing_stages.get(s) == "completed" for s in (
                "cleanup", "recommended_cleanup", "jev_comparison")) else "import_processing",
            "process_version": FINISHING_VERSION,
            "metadata": {"run_id": self.job.id, "provider": self.options.ai_provider, "model": self.options.ai_model,
                         "stages": dict(self.finishing_stages), "recommended_version": RECOMMENDED_FINISHING_VERSION},
        }]
        if full_cleanup and full_cleanup["notation"] is not None:
            self.finishing_history.append({"segments": json.loads(json.dumps(self.segments, ensure_ascii=False)),
                "speaker_names": {}, "origin": "ai", "process": "notation", "process_version": NOTATION_VERSION,
                "metadata": {"run_id": self.job.id, "provider": self.options.ai_provider, "model": self.options.ai_model,
                             "notation": full_cleanup["notation"]}})
        self.set_stage("finishing", "文字起こしの仕上げ", 100)
        self.progress(88)

    def _create_context_outline(self, source: list[dict[str, Any]]) -> dict[str, Any]:
        self.status("再校正に先立ち、会話全体のアウトラインを作成しています…")
        return self.create_outline_with_ai(
            source, {}, self.options.ai_provider, self.options.ai_api_key, self.options.ai_model,
            self.status, self.check_cancelled, self.record_ai_usage, **self.ai_base_kwargs,
        )

    def _clean_with_outline(self,
        source: list[dict[str, Any]], outline: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return self.clean_segments_with_ai(
            source,
            self.options.ai_provider,
            self.options.ai_api_key,
            self.options.ai_model,
            self.status,
            self.check_cancelled,
            self.record_ai_usage,
            outline=outline,
            **self.ai_base_kwargs,
        )

    def _review_original_with_jev(self, outline: dict[str, Any]) -> tuple[dict, dict]:
        return self.review_segments_with_jev(
            self.imported_transcript,
            self.options.jev_api_key,
            self.options.jev_model,
            self.status,
            self.check_cancelled,
            outline=outline,
        )

    def _warn_full_cleanup(self, stage: str, exc: BaseException | None) -> None:
        if exc is None:
            self.record_warning("現行AIの文字整形が完了しなかったため、Jevとの比較を省略しました。")
            return
        details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        if stage == "outline_context":
            self.record_warning("再校正用の全体アウトラインを作成できませんでした: " + str(exc))
        elif stage == "cleanup":
            self.record_warning("AI文字整形を省略しました。元の文字起こしを保存します: " + details)
        elif stage == "notation":
            self.record_warning("表記ゆれの統一に失敗しました。統一前の本文を保存します: " + details)
        else:
            self.record_warning("Jevによる修正要否の比較を省略しました: " + details)

    def _analyze_emotion(self) -> None:
        self.emotion_analysis: dict[str, Any] | None = None
        if self.options.emotion_analysis:
            emotion_model_keys = self.aist_emotion_model_keys(self.options.emotion_model)
            try:
                self.set_stage("emotion", "音声感情の分析", 10)
                # Emotion models depend on loudness dynamics that the
                # transcription preprocessing deliberately flattens.
                self.segments, self.emotion_analysis = self.run_aist_emotion_analysis(
                    self.options.input_path,
                    self.segments,
                    self.options.emotion_model,
                    self.options.hf_token,
                    self.device,
                    self.internal_work_dir / "emotion_work",
                    self.status,
                    self.check_cancelled,
                )
                self.status("AIST感情分析が完了しました。")
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                self.record_warning("AIST感情分析は失敗しました。文字起こし処理は続行します: " + details)
                self.emotion_analysis = self.build_emotion_analysis_summary(
                    self.segments,
                    emotion_model_keys,
                    status="failed",
                    error=details,
                )
            self.set_stage("emotion", "音声感情の分析", 100)
        self.progress(90)
        self.finishing_history.append({"segments": json.loads(json.dumps(self.segments, ensure_ascii=False)),
                                  "speaker_names": {}, "origin": "rule", "process": "emotion_projection"})

    def _identify_speakers(self):
        self.speaker_names: dict[str, str] = {}
        speaker_identity_diagnostics: dict[str, Any] = {}
        speaker_repair_summary = {
            "alias_count": 0,
            "aliased_segments": 0,
            "corrected_segments": 0,
        }
        # Name identification does not rewrite the transcript, so it can run
        # with the standard Obsidian finishing flow as well.  That makes the
        # first result use verified names instead of diarization numbers.
        if self.options.detect_speaker_names:
            self.set_stage("speaker_names", "話者名の確認", 10)
            self.status("文字校正とは独立した2段階処理で、自己紹介と話者ラベルを確認しています…")
            try:
                self.check_cancelled()
                self.speaker_names = self.detect_speaker_names_with_ai(
                    self.speaker_identity_segments,
                    self.options.ai_provider,
                    self.options.ai_api_key,
                    self.options.ai_model,
                    self.check_cancelled,
                    self.record_ai_usage,
                    self.status,
                    speaker_identity_diagnostics.update,
                    known_speakers=self.options.prior_speakers,
                    **self.ai_base_kwargs,
                )
                self.segments, self.speaker_names, speaker_repair_summary = self.apply_speaker_identity_repairs(
                    self.segments,
                    self.speaker_names,
                    speaker_identity_diagnostics,
                )
                self.finishing_stages["speaker_identity"] = "completed"
                if any(speaker_repair_summary.values()):
                    self.status(
                        "AI話者連続性修復: "
                        f"重複ラベル {speaker_repair_summary['alias_count']}件 / "
                        f"ラベル統合発話 {speaker_repair_summary['aliased_segments']}件 / "
                        f"断裂修正 {speaker_repair_summary['corrected_segments']}件"
                    )
                    if self.emotion_analysis is not None:
                        self.emotion_analysis = self.build_emotion_analysis_summary(
                            self.segments,
                            self.aist_emotion_model_keys(self.options.emotion_model),
                            status=str(self.emotion_analysis.get("status") or "completed"),
                            error=str(self.emotion_analysis.get("error") or ""),
                        )
                self.check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                self.record_warning("AI話者名推定を省略しました。話者ラベルで保存します: " + details)
                self.finishing_stages["speaker_identity"] = "failed"
            self.set_stage("speaker_names", "話者名の確認", 100)
        if self.finishing_stages["speaker_identity"] == "completed":
            self.finishing_history.append({"segments": json.loads(json.dumps(self.segments, ensure_ascii=False)),
                "speaker_names": dict(self.speaker_names), "origin": "ai", "process": "ai_finishing",
                "process_version": FINISHING_VERSION,
                "metadata": {"run_id": self.job.id, "provider": self.options.ai_provider, "model": self.options.ai_model,
                             "stages": {"speaker_identity": "completed"}}})
        self.segments, self.formatting_result = self.transcript_formatting_result(
            self.imported_transcript,
            self.segments,
            mode=self.options.transcript_finishing_mode,
            audio_preprocess=self.options.audio_preprocess,
            speaker_names=self.speaker_names,
            speaker_diagnostics=speaker_identity_diagnostics,
            speaker_repair_summary=speaker_repair_summary,
            finishing_stages=self.finishing_stages,
            ai_usage=self.job.ai_usage,
            jev_usage=self.jev_usage,
        )
        formatting_summary = self.formatting_result["summary"]
        self.status(
            "整形チェック完了: "
            f"文字調整 {formatting_summary['text_change_count']}件 / "
            f"AI文章置換 {formatting_summary['recommended_replacement_count']}件 / "
            f"境界確認 {formatting_summary['boundary_warning_count']}件 / "
            f"ノイズ候補 {formatting_summary['noise_candidate_count']}件 / "
            f"話者統合 {formatting_summary['speaker_relabel_count']}発話"
        )
        self.speaker_profiles = self.normalize_conversation_speaker_profiles(
            None,
            {str(item.get("speaker") or "UNKNOWN") for item in self.segments},
            self.speaker_names,
        )
        self.speaker_profiles, self.speaker_registration_summary = self.register_detected_speakers(
            self.speaker_profiles,
            self.speaker_names,
        )
        if self.speaker_registration_summary["created"]:
            self.status(
                "自己紹介から確認した話者を話者管理に登録しました: "
                + "、".join(
                    self.speaker_names[label]
                    for label in self.speaker_registration_summary["created"]
                    if self.speaker_names.get(label)
                )
            )
        if self.speaker_registration_summary["temporary"]:
            self.status(
                "台帳に一致しない話者を、この会話のみの一時話者として登録しました: "
                + "、".join(self.speaker_registration_summary["temporary"].values())
            )

    def _prepare_minutes(self):
        if self.options.finish_in_obsidian:
            try:
                # Work notes are researcher-owned after their first creation.
                # Create them only after the non-text-changing identity pass,
                # so their headers already show names without overwriting a
                # note a researcher may later edit.
                self.obsidian_workbench().prepare(
                    self.job.id, self.options.source_name, self.segments, revision=0,
                    provider=self.options.ai_provider, model=self.options.ai_model,
                    ai_efforts=self.options.ai_efforts,
                    detect_names=self.options.detect_speaker_names or self.options.ai_provider == "none",
                    create_outline=self.options.create_outline or self.options.ai_provider == "none",
                    jev_compare=self.options.jev_compare, ready=False,
                    speaker_names=self.speaker_names,
                )
                self.obsidian_prepared = True
                self.status("Whisperの原文と会話全文をObsidianに保存しました。仕上げは操作ノートから実行できます。")
            except (OSError, ValueError) as exc:
                self.record_warning("Obsidianの作業ノートを保存できませんでした。処理完了後に「Obsidianで仕上げ」から再試行してください: " + str(exc))
        self.session_profile = self.session_profile_from_media(self.options.input_path, self.check_cancelled)
        self.session_profile["session_type"] = self.CONVERSATION_MODES.get(
            self.options.conversation_mode, "meeting"
        )
        if self.session_profile.get("session_date"):
            self.status(
                "動画の撮影日時から実施日を自動入力しました: "
                f"{self.session_profile['session_date']}"
            )
        self.progress(94)
        self.outline: dict[str, Any] | None = None
        if self.options.create_outline and not self.options.finish_in_obsidian:
            try:
                self.set_stage("outline", "議題アウトラインの作成", 10)
                self.outline = self.create_outline_with_ai(
                    self.segments,
                    self.speaker_names,
                    self.options.ai_provider,
                    self.options.ai_api_key,
                    self.options.ai_model,
                    self.status,
                    self.check_cancelled,
                    self.record_ai_usage,
                    **self.ai_base_kwargs,
                )
                self.finishing_stages["outline"] = "completed"
                self.check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                self.finishing_stages["outline"] = "failed"
                self.record_warning("AIアウトライン作成を省略しました。文字起こし結果は保存します: " + details)
            self.set_stage("outline", "議題アウトラインの作成", 100)
        final_usage = self.normalize_ai_usage(self.job.ai_usage)
        self.formatting_result["summary"]["llm_request_count"] = (
            self.safe_token_count(final_usage.get("request_count"))
            + self.safe_token_count(self.jev_usage.get("request_count"))
        )
        self.meeting_minutes: dict[str, Any] | None = None
        if self.options.conversation_mode == "meeting" and self.options.generate_meeting_minutes:
            self.set_stage("meeting_minutes", "会議議事録とタスク候補の作成", 20)
            self.status("会議のタスク・優先度・期限候補と分析サマリーを作成しています…")
            self.meeting_minutes = self.build_meeting_minutes(
                self.segments, self.speaker_names, self.session_profile, self.outline
            )
            self.set_stage("meeting_minutes", "会議議事録とタスク候補の作成", 100)
        self.progress(97)
        self.check_cancelled()


    def _write_results(self) -> None:
        self.set_stage("output", "結果ファイルの保存", 10)
        self.status("出力ファイルを書き出しています…")
        files = self.write_outputs(
            self.options.source_name,
            self.options.output_dir,
            self.segments,
            self.language_code,
            self.speaker_names,
            self.options.write_srt,
            self.options.write_json,
            self.outline,
            self.emotion_analysis,
            self.speaker_profiles,
            self.meeting_minutes,
            self.check_cancelled,
            formatting_result=self.formatting_result,
            write_word_cloud_file=self.options.write_word_cloud,
            session_profile=self.session_profile,
        )
        self.check_cancelled()
        self.set_stage("output", "結果ファイルの保存", 45)
        if self.options.burn_subtitled_video:
            if self.is_video_path(self.options.input_path):
                optional_stem = self.safe_output_stem(self.options.source_name)
                optional_ass = self.options.output_dir / f'{optional_stem}_話者カラー字幕.ass'
                optional_video = self.options.output_dir / f'{optional_stem}_字幕付き.mp4'
                optional_ass_existed = self.path_entry_exists(optional_ass)
                optional_video_existed = self.path_entry_exists(optional_video)
                self.status("話者名・テーマカラー付き字幕を動画へ焼き込んでいます…")
                try:
                    files.extend(self.write_subtitled_video_assets(
                        self.options.input_path,
                        self.options.source_name,
                        self.options.output_dir,
                        self.segments,
                        self.speaker_names,
                        self.speaker_profiles,
                        self.check_cancelled,
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
                    self.record_warning(warning)
            else:
                self.status("音声ファイルのため、字幕焼き込み動画の作成は省略しました。")
        self.check_cancelled()
        self.set_stage("output", "結果ファイルの保存", 75)
        self.status("元の音声・動画をライブラリへ保存しています…")
        media_target, self.staged_media_path = self.stage_media_archive(
            self.job.id, self.options.input_path, self.check_cancelled
        )
        self.check_cancelled()
        with self.jobs_lock:
            if self.job.cancel_event.is_set():
                raise InterruptedError("The transcription job was cancelled.")
            self.job.status = "committing"
        saved_media_path = self.commit_staged_media(media_target, self.staged_media_path)
        self.staged_media_path = None
        persisted = self.upsert_library_item(
            item_id=self.job.id,
            source_name=self.options.source_name,
            output_dir=self.options.output_dir,
            media_path=saved_media_path,
            original_media_path=self.options.input_path,
            language=self.language_code,
            segments=self.segments,
            speaker_names=self.speaker_names,
            outline=self.outline,
            emotion_analysis=self.emotion_analysis,
            files=files,
            write_srt=self.options.write_srt,
            original_segments=self.imported_transcript,
            finishing_history=self.finishing_history,
            write_json=True,
            burn_subtitled_video=self.options.burn_subtitled_video,
            session_profile=self.session_profile,
            speaker_profiles=self.speaker_profiles,
            ai_usage=self.job.ai_usage,
            meeting_minutes=self.meeting_minutes,
            formatting_result=self.formatting_result,
        )
        self.publish_input_vault(persisted, self.whisper_vault_settings(self.options, self.language_code))
        if self.obsidian_prepared:
            try:
                self.obsidian_workbench().activate(self.job.id, int(persisted["revision_count"] or 0), self.segments)
            except (OSError, ValueError) as exc:
                self.record_warning("原文は保存済みです。「Obsidianで仕上げ」から作業状態の更新を再試行してください: " + str(exc))
            try:
                self.publish_meeting_minutes_to_obsidian(persisted)
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
                # Transcript persistence is authoritative; a meeting note can be retried later.
                self.record_warning("会議議事録のObsidian公開を後で再試行してください: " + str(exc))
        with self.jobs_lock:
            self.job.segments = self.row_segments(persisted)
            self.job.speaker_names = self.speaker_names
            self.job.session_profile = self.row_session_profile(persisted)
            self.job.speaker_profiles = self.row_speaker_profiles(persisted, self.job.segments, self.speaker_names)
            self.job.speaker_registration = self.speaker_registration_summary
            self.job.outline = self.outline
            try:
                persisted_minutes = self.json_load(persisted["meeting_minutes_json"], {})
            except (KeyError, TypeError, IndexError):
                persisted_minutes = self.meeting_minutes or {}
            self.job.meeting_minutes = self.normalize_meeting_minutes(persisted_minutes)
            self.job.emotion_analysis = self.emotion_analysis
            self.job.formatting_result = self.formatting_result
            self.job.media_path = saved_media_path
            self.job.files = files
            self.job.language = self.language_code
            self.job.status = "completed"
        self.set_stage("completed", "処理完了", 100)
        self.progress(100)
        self.status("Transcription completed and output files were saved.")


def run_transcription_job(job: Any, options: Any, dependencies: Mapping[str, Any]) -> None:
    _TranscriptionJob(job, options, dependencies).run()
