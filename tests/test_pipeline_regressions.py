import sys
import tempfile
import time
import types
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import app


class DisplaySegmentRegressionTests(unittest.TestCase):
    def test_splits_one_whisperx_segment_at_word_speaker_changes(self):
        segments = app.make_display_segments([{
            "start": 0.0,
            "end": 3.0,
            "speaker": "SPEAKER_00",
            "text": "こんにちははい続けます",
            "words": [
                {"start": 0.0, "end": 1.0, "word": "こんにちは", "speaker": "SPEAKER_00"},
                {"start": 1.0, "end": 1.3, "word": "はい", "speaker": "SPEAKER_01"},
                {"start": 1.3, "end": 3.0, "word": "続けます", "speaker": "SPEAKER_00"},
            ],
        }])

        self.assertEqual(
            [(item["speaker"], item["text"]) for item in segments],
            [
                ("SPEAKER_00", "こんにちは"),
                ("SPEAKER_01", "はい"),
                ("SPEAKER_00", "続けます"),
            ],
        )
        self.assertEqual([(item["start"], item["end"]) for item in segments], [(0.0, 1.0), (1.0, 1.3), (1.3, 3.0)])

    def test_smooths_short_non_backchannel_speaker_island(self):
        segments = app.make_display_segments([{
            "start": 0.0,
            "end": 2.0,
            "speaker": "SPEAKER_00",
            "text": "この件について",
            "words": [
                {"start": 0.0, "end": 0.8, "word": "この", "speaker": "SPEAKER_00"},
                {"start": 0.8, "end": 1.1, "word": "件", "speaker": "SPEAKER_01"},
                {"start": 1.1, "end": 2.0, "word": "について", "speaker": "SPEAKER_00"},
            ],
        }])

        self.assertEqual(segments, [{
            "start": 0.0,
            "end": 2.0,
            "speaker": "SPEAKER_00",
            "text": "この件について",
        }])

    def test_missing_words_uses_original_segment_fallback(self):
        self.assertEqual(
            app.make_display_segments([{
                "start": 2.0,
                "end": 4.0,
                "speaker": "SPEAKER_02",
                "text": "元の発話",
            }]),
            [{"start": 2.0, "end": 4.0, "speaker": "SPEAKER_02", "text": "元の発話"}],
        )

    def test_unknown_speaker_chunks_are_not_assumed_to_be_the_same_person(self):
        segments = app.make_display_segments([
            {"start": 0.0, "end": 1.0, "text": "一つ目"},
            {"start": 1.1, "end": 2.0, "text": "二つ目"},
        ])
        self.assertEqual(len(segments), 2)

    def test_smooths_short_cross_segment_speaker_island(self):
        segments = app.make_display_segments([
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "説明を続けます"},
            {"start": 2.0, "end": 2.8, "speaker": "SPEAKER_01", "text": "途中"},
            {"start": 2.8, "end": 4.0, "speaker": "SPEAKER_00", "text": "以上です"},
        ])

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["speaker"], "SPEAKER_00")
        self.assertIn("途中", segments[0]["text"])


class GapSupplementRegressionTests(unittest.TestCase):
    def test_context_only_segment_at_gap_edge_is_dropped(self):
        shifted = app.offset_asr_segments_to_gap(
            [{"start": 0.0, "end": 0.9, "text": "直前の発話"}],
            clip_start=9.25,
            gap_start=10.0,
            gap_end=13.0,
        )

        self.assertEqual(shifted, [])

    def test_gap_recovery_is_clipped_and_context_words_are_removed(self):
        shifted = app.offset_asr_segments_to_gap(
            [{
                "start": 0.5,
                "end": 4.25,
                "text": "前補完後",
                "words": [
                    {"start": 0.5, "end": 0.7, "word": "前"},
                    {"start": 1.0, "end": 3.0, "word": "補完"},
                    {"start": 4.1, "end": 4.25, "word": "後"},
                ],
            }],
            clip_start=9.25,
            gap_start=10.0,
            gap_end=13.0,
        )

        self.assertEqual(len(shifted), 1)
        self.assertEqual((shifted[0]["start"], shifted[0]["end"]), (10.0, 13.0))
        self.assertEqual(shifted[0]["text"], "補完")
        self.assertEqual(len(shifted[0]["words"]), 1)

    def test_nearby_short_acknowledgement_is_not_added_twice(self):
        primary = [{"start": 10.0, "end": 10.5, "text": "はい"}]
        supplemental = [{"start": 10.55, "end": 11.0, "text": "はい"}]

        merged, counts = app.merge_supplemental_asr_segments(
            primary,
            [("再確認", supplemental)],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(counts, {"再確認": 0})

    def test_distant_short_acknowledgement_is_kept(self):
        primary = [{"start": 10.0, "end": 10.5, "text": "はい"}]
        supplemental = [{"start": 13.0, "end": 13.5, "text": "はい"}]

        merged, counts = app.merge_supplemental_asr_segments(
            primary,
            [("再確認", supplemental)],
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(counts, {"再確認": 1})

    def test_context_heavy_supplement_without_word_times_is_dropped(self):
        shifted = app.offset_asr_segments_to_gap(
            [{"start": 0.0, "end": 4.0, "text": "前後を含む発話"}],
            clip_start=9.25,
            gap_start=10.0,
            gap_end=13.0,
        )

        self.assertEqual(shifted, [])

    def test_near_duplicate_with_minor_asr_variation_is_not_added(self):
        primary = [{"start": 10.0, "end": 12.0, "text": "詳しい説明をします"}]
        supplemental = [{"start": 10.1, "end": 12.1, "text": "詳しく説明をします"}]

        merged, counts = app.merge_supplemental_asr_segments(
            primary,
            [("小声補完", supplemental)],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(counts, {"小声補完": 0})


class SpeakerIdentityRegressionTests(unittest.TestCase):
    def test_identity_context_is_selected_by_time_text_and_cues_not_fixed_turn_count(self):
        short_records = [
            {
                "id": index,
                "speaker": f"SPEAKER_{index % 6:02d}",
                "start": index * 3.0,
                "end": index * 3.0 + 2.0,
                "text": "自己紹介をお願いします" if index == 0 else f"短い自己紹介 {index}",
            }
            for index in range(30)
        ]
        long_records = [
            {**record, "text": record["text"] + ("長い発話" * 300)}
            for record in short_records
        ]

        short_context = app.speaker_identity_context_records(short_records)
        long_context = app.speaker_identity_context_records(
            long_records, character_budget=2500
        )

        self.assertGreater(len(short_context), 25)
        self.assertLess(len(long_context), len(short_context))

    def test_identity_context_includes_late_arrival_without_opening_invitation(self):
        records = [
            {"id": 0, "speaker": "SPEAKER_00", "start": 0.0, "end": 3.0, "text": "会議を始めます"},
            {"id": 1, "speaker": "SPEAKER_00", "start": 300.0, "end": 303.0, "text": "次の議題です"},
            {"id": 2, "speaker": "SPEAKER_03", "start": 620.0, "end": 626.0, "text": "遅れてすみません山田と申しますよろしくお願いします"},
        ]

        context = app.speaker_identity_context_records(records)

        self.assertIn(2, [record["id"] for record in context])

    def test_identity_extraction_and_link_verification_are_two_separate_calls(self):
        segments = [
            {"start": 2.0, "end": 3.0, "speaker": "SPEAKER_00", "text": "田中と申します"},
            {"start": 610.0, "end": 612.0, "speaker": "SPEAKER_01", "text": "佐藤です"},
        ]
        responses = [
            {"speaker_names": [{"speaker": "SPEAKER_00", "name": "田中", "evidence": "田中と申します"}]},
            {"speaker_names": [
                {"speaker": "SPEAKER_00", "name": "田中", "evidence": "田中と申します"},
                {"speaker": "SPEAKER_01", "name": "佐藤", "evidence": "佐藤です"},
            ]},
        ]
        statuses = []

        with patch.object(app, "call_ai_json", side_effect=responses) as call:
            names = app.detect_speaker_names_with_ai(
                segments,
                "google",
                "secret",
                "gemini-test",
                status_callback=statuses.append,
            )

        self.assertEqual(names, {"SPEAKER_00": "田中", "SPEAKER_01": "佐藤"})
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args_list[0].args[5], "speaker_identity_extraction")
        self.assertEqual(call.call_args_list[1].args[5], "speaker_identity_link_verification")
        self.assertIn("佐藤です", call.call_args_list[0].args[4])
        self.assertEqual(len(statuses), 2)

    def test_evidence_segment_id_overrides_incorrect_model_speaker_link(self):
        segments = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "司会です"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01", "text": "田中と申します"},
        ]
        response = {"speaker_names": [{
            "speaker": "SPEAKER_00",
            "name": "田中",
            "evidence": "田中と申します",
            "evidence_segment_ids": [1],
        }]}

        with patch.object(app, "call_ai_json", side_effect=[response, response]):
            names = app.detect_speaker_names_with_ai(
                segments, "openai", "secret", "test-model"
            )

        self.assertEqual(names, {"SPEAKER_01": "田中"})

    def test_multiple_names_for_one_diarization_label_are_not_overwritten(self):
        segments = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_08", "text": "田中です"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_08", "text": "佐藤です"},
        ]
        response = {"speaker_names": [
            {
                "speaker": "SPEAKER_08", "name": "田中", "evidence": "田中です",
                "evidence_segment_ids": [0],
            },
            {
                "speaker": "SPEAKER_08", "name": "佐藤", "evidence": "佐藤です",
                "evidence_segment_ids": [1],
            },
        ]}
        diagnostics = {}

        with patch.object(app, "call_ai_json", side_effect=[response, response]):
            names = app.detect_speaker_names_with_ai(
                segments,
                "google",
                "secret",
                "test-model",
                diagnostics_callback=diagnostics.update,
            )

        self.assertEqual(names, {})
        self.assertEqual(
            diagnostics["ambiguous_labels"],
            {"SPEAKER_08": ["田中", "佐藤"]},
        )

    def test_contextual_self_introduction_accepts_asr_honorific_variation(self):
        segments = [
            {
                "start": 60.0,
                "end": 64.0,
                "speaker": "SPEAKER_08",
                "text": "簡単に一人ずつ自己紹介をお願いいたします",
            },
            {
                "start": 102.0,
                "end": 107.0,
                "speaker": "SPEAKER_01",
                "text": "片割さんです出身は静岡ですよろしくお願いします",
            },
        ]
        response = {"speaker_names": [{
            "speaker": "SPEAKER_01",
            "name": "片割さん",
            "evidence": "片割さんです出身は静岡ですよろしくお願いします",
            "evidence_segment_ids": [1],
        }]}

        with patch.object(app, "call_ai_json", side_effect=[response, response]) as call:
            names = app.detect_speaker_names_with_ai(
                segments, "google", "secret", "test-model"
            )

        self.assertEqual(names, {"SPEAKER_01": "片割"})
        self.assertIn("固定表現の完全一致を条件にしません", call.call_args_list[0].args[3])
        self.assertIn("出身地・所属・役割・挨拶", call.call_args_list[1].args[3])

    def test_verified_aliases_and_short_fragment_corrections_are_applied(self):
        segments = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "田中です"},
            {"start": 2.0, "end": 2.6, "speaker": "SPEAKER_01", "text": "説明の"},
            {"start": 2.6, "end": 4.0, "speaker": "SPEAKER_00", "text": "続きです"},
            {"start": 4.0, "end": 6.0, "speaker": "SPEAKER_02", "text": "田中です"},
        ]
        first = {"speaker_names": [
            {"speaker": "SPEAKER_00", "name": "田中", "evidence": "田中です", "evidence_segment_ids": [0]},
            {"speaker": "SPEAKER_02", "name": "田中", "evidence": "田中です", "evidence_segment_ids": [3]},
        ]}
        verified = {
            **first,
            "speaker_aliases": [{
                "canonical_speaker": "SPEAKER_00",
                "alias_speaker": "SPEAKER_02",
                "confidence": 0.98,
                "evidence_segment_ids": [0, 3],
            }],
            "segment_speaker_corrections": [{
                "segment_id": 1,
                "speaker": "SPEAKER_00",
                "confidence": 0.99,
                "evidence_segment_ids": [0, 1, 2],
            }],
        }
        diagnostics = {}

        with patch.object(app, "call_ai_json", side_effect=[first, verified]):
            names = app.detect_speaker_names_with_ai(
                segments,
                "google",
                "secret",
                "test-model",
                diagnostics_callback=diagnostics.update,
            )

        repaired, repaired_names, summary = app.apply_speaker_identity_repairs(
            segments,
            names,
            diagnostics,
        )
        self.assertEqual({item["speaker"] for item in repaired}, {"SPEAKER_00"})
        self.assertEqual(repaired_names, {"SPEAKER_00": "田中"})
        self.assertEqual(summary["alias_count"], 1)
        self.assertEqual(summary["aliased_segments"], 1)
        self.assertEqual(summary["corrected_segments"], 1)


class AtomicOutputRegressionTests(unittest.TestCase):
    def test_failed_replace_keeps_previous_final_file(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-atomic-") as temporary:
            root = Path(temporary)
            target = root / "result.txt"
            target.write_text("previous", encoding="utf-8")

            with patch.object(app.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    app.atomic_write_text(target, "new")

            self.assertEqual(target.read_text(encoding="utf-8"), "previous")
            self.assertEqual(list(root.iterdir()), [target])

    def test_cancelled_copy_keeps_previous_final_file(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-copy-") as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            target = root / "media.bin"
            source.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
            target.write_bytes(b"previous")
            checks = 0

            def check_cancelled():
                nonlocal checks
                checks += 1
                if checks >= 2:
                    raise InterruptedError("cancelled")

            with self.assertRaises(InterruptedError):
                app.atomic_copy_file(source, target, check_cancelled)

            self.assertEqual(target.read_bytes(), b"previous")
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["media.bin", "source.bin"])


class CancellableSubprocessRegressionTests(unittest.TestCase):
    def test_cancellation_terminates_a_running_child_promptly(self):
        checks = 0

        def check_cancelled():
            nonlocal checks
            checks += 1
            if checks >= 2:
                raise InterruptedError("cancelled")

        started_at = time.monotonic()
        with self.assertRaises(InterruptedError):
            app.run_cancellable_subprocess(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                timeout=10,
                check_cancelled=check_cancelled,
            )
        self.assertLess(time.monotonic() - started_at, 5.0)


class EmotionRegressionTests(unittest.TestCase):
    def test_emotion_analysis_does_not_swallow_interrupted_error(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-emotion-") as temporary:
            def cancelled():
                raise InterruptedError("cancelled")

            with self.assertRaises(InterruptedError):
                app.run_aist_emotion_analysis(
                    Path(temporary) / "audio.wav",
                    [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "発話"}],
                    "kushinada",
                    "token",
                    "cpu",
                    Path(temporary),
                    lambda _message: None,
                    cancelled,
                )

    def test_emotion_csv_escapes_spreadsheet_formulas(self):
        body = app.emotion_csv_text(
            [{
                "start": 0.0,
                "end": 1.0,
                "speaker": "SPEAKER_00",
                "text": '=HYPERLINK("https://example.invalid")',
                "emotions": {"kushinada": {"label": "neu", "label_ja": "平常"}},
            }],
            {"SPEAKER_00": "+cmd"},
        )
        self.assertIn("'+cmd", body)
        self.assertIn("'=HYPERLINK", body)


class TranscriptionJobRegressionTests(unittest.TestCase):
    @staticmethod
    def options(root: Path, **overrides):
        values = {
            "input_path": root / "input.wav",
            "work_dir": root,
            "source_name": "input.wav",
            "output_dir": root / "output",
            "model_name": "tiny",
            "language": None,
            "hf_token": "token",
            "audio_preprocess": "none",
            "min_speakers": None,
            "max_speakers": None,
            "device": "cpu",
            "diarization_device": "cpu",
            "triple_pass": False,
            "boost_quiet_speech": False,
            "vad_onset": 0.5,
            "vad_offset": 0.36,
            "no_speech_threshold": 0.6,
            "write_srt": True,
            "write_json": True,
            "burn_subtitled_video": False,
            "ai_provider": "openai",
            "clean_transcript": False,
            "detect_speaker_names": False,
            "create_outline": False,
            "emotion_analysis": False,
            "emotion_model": "kushinada",
            "ai_api_key": "key",
            "ai_model": "model",
        }
        values.update(overrides)
        return app.JobOptions(**values)

    @contextmanager
    def fake_pipeline(self):
        torch_module = types.ModuleType("torch")
        torch_module.cuda = types.SimpleNamespace(
            is_available=lambda: False,
            empty_cache=lambda: None,
        )

        class FakeWhisperModel:
            def transcribe(self, _audio, **_kwargs):
                return {
                    "language": None,
                    "segments": [{
                        "start": 0.0,
                        "end": 1.0,
                        "speaker": "SPEAKER_00",
                        "text": "元の文字起こし",
                        "words": [{
                            "start": 0.0,
                            "end": 1.0,
                            "word": "元の文字起こし",
                            "speaker": "SPEAKER_00",
                        }],
                    }],
                }

        whisper_module = types.ModuleType("whisper")
        whisper_module.load_model = lambda *_args, **_kwargs: FakeWhisperModel()
        whisperx_module = types.ModuleType("whisperx")
        whisperx_module.__path__ = []
        whisperx_module.load_audio = lambda _path: [0.0]
        whisperx_module.assign_word_speakers = lambda _diarization, result, **_kwargs: result

        class FakeDiarizationPipeline:
            def __init__(self, model_name=None, token=None, device=None):
                self.model_name = model_name

            def __call__(self, _audio, **_kwargs):
                return []

        diarize_module = types.ModuleType("whisperx.diarize")
        diarize_module.DiarizationPipeline = FakeDiarizationPipeline

        modules = {
            "torch": torch_module,
            "whisper": whisper_module,
            "whisperx": whisperx_module,
            "whisperx.diarize": diarize_module,
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, modules))
            stack.enter_context(patch.object(app.shutil, "which", return_value="ffmpeg"))
            stack.enter_context(patch.object(app, "configure_huggingface_hub_compatibility"))
            stack.enter_context(patch.object(app, "configure_speechbrain_lazy_import_compatibility"))
            write_outputs = stack.enter_context(patch.object(app, "write_outputs", return_value=[]))
            stage_media = stack.enter_context(
                patch.object(
                    app,
                    "stage_media_archive",
                    side_effect=lambda _id, path, _check: (path, path),
                )
            )
            commit_media = stack.enter_context(
                patch.object(app, "commit_staged_media", side_effect=lambda target, _staged: target)
            )
            upsert = stack.enter_context(patch.object(app, "upsert_library_item", return_value=object()))
            stack.enter_context(patch.object(app, "row_segments", return_value=[{
                "start": 0.0,
                "end": 1.0,
                "speaker": "SPEAKER_00",
                "text": "元の文字起こし",
            }]))
            stack.enter_context(patch.object(app, "row_session_profile", return_value={}))
            stack.enter_context(patch.object(app, "row_speaker_profiles", return_value={}))
            yield {
                "write_outputs": write_outputs,
                "stage_media": stage_media,
                "commit_media": commit_media,
                "upsert": upsert,
            }

    @staticmethod
    def job(root: Path):
        return app.JobRecord("job-id", "input.wav", root / "output", True, True)

    def test_optional_ai_failures_warn_but_core_result_completes(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-") as temporary:
            root = Path(temporary)
            job = self.job(root)
            options = self.options(
                root,
                clean_transcript=True,
                detect_speaker_names=True,
                create_outline=True,
            )
            with self.fake_pipeline() as calls, \
                    patch.object(app, "clean_segments_with_ai", side_effect=RuntimeError("cleanup failed")), \
                    patch.object(app, "detect_speaker_names_with_ai", side_effect=RuntimeError("names failed")), \
                    patch.object(app, "create_outline_with_ai", side_effect=RuntimeError("outline failed")):
                app.run_transcription_job(job, options)

            self.assertEqual(job.status, "completed")
            self.assertIn("AI文字整形を省略", job.output_warning)
            self.assertIn("AI話者名推定を省略", job.output_warning)
            self.assertIn("AIアウトライン作成を省略", job.output_warning)
            self.assertTrue(calls["write_outputs"].called)
            self.assertTrue(calls["upsert"].called)

    def test_speaker_identity_uses_unedited_transcript_independently(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-identity-source-") as temporary:
            root = Path(temporary)
            job = self.job(root)
            options = self.options(
                root,
                clean_transcript=True,
                detect_speaker_names=True,
            )
            identity_inputs = []

            def clean(segments, *_args):
                return [{**segment, "text": "校正後の文"} for segment in segments]

            def identify(segments, *_args):
                identity_inputs.extend(segments)
                return {"SPEAKER_00": "話者名"}

            with self.fake_pipeline(), \
                    patch.object(app, "clean_segments_with_ai", side_effect=clean), \
                    patch.object(app, "detect_speaker_names_with_ai", side_effect=identify):
                app.run_transcription_job(job, options)

            self.assertEqual(job.status, "completed")
            self.assertEqual(identity_inputs[0]["text"], "元の文字起こし")

    def test_ai_usage_is_accumulated_and_saved_with_the_job(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-") as temporary:
            root = Path(temporary)
            job = self.job(root)
            options = self.options(root, clean_transcript=True)

            def clean_with_usage(segments, *_args):
                usage_callback = _args[-1]
                usage_callback({
                    "provider": "openai", "model": "model", "request_count": 1,
                    "input_tokens": 100, "output_tokens": 20, "total_tokens": 120,
                    "cached_tokens": 10, "reasoning_tokens": 4, "reported": True,
                })
                usage_callback({
                    "provider": "openai", "model": "model", "request_count": 1,
                    "input_tokens": 80, "output_tokens": 15, "total_tokens": 95,
                    "cached_tokens": 0, "reasoning_tokens": 3, "reported": True,
                })
                return segments

            with self.fake_pipeline() as calls, patch.object(
                app, "clean_segments_with_ai", side_effect=clean_with_usage
            ):
                app.run_transcription_job(job, options)

            self.assertEqual(job.status, "completed")
            self.assertEqual(job.ai_usage["request_count"], 2)
            self.assertEqual(job.ai_usage["input_tokens"], 180)
            self.assertEqual(job.ai_usage["output_tokens"], 35)
            self.assertEqual(job.ai_usage["total_tokens"], 215)
            self.assertEqual(job.ai_usage["cached_tokens"], 10)
            self.assertEqual(job.ai_usage["reasoning_tokens"], 7)
            self.assertEqual(calls["upsert"].call_args.kwargs["ai_usage"]["total_tokens"], 215)

    def test_emotion_interruption_cancels_job_before_outputs(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-") as temporary:
            root = Path(temporary)
            job = self.job(root)
            options = self.options(root, emotion_analysis=True)
            with self.fake_pipeline() as calls, patch.object(
                app,
                "run_aist_emotion_analysis",
                side_effect=InterruptedError("cancelled in emotion"),
            ):
                app.run_transcription_job(job, options)

            self.assertEqual(job.status, "cancelled")
            calls["write_outputs"].assert_not_called()
            calls["upsert"].assert_not_called()

    def test_preprocessed_audio_uses_internal_subdirectory(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-") as temporary:
            root = Path(temporary)
            source = root / "preprocessed.wav"
            job = self.job(root)
            options = self.options(
                root,
                input_path=source,
                source_name=source.name,
                audio_preprocess="standard",
            )
            destinations = []

            def preprocess(_source, destination, _preset, _check):
                destinations.append(destination)
                return destination

            with self.fake_pipeline(), patch.object(app, "run_audio_preprocess", side_effect=preprocess):
                app.run_transcription_job(job, options)

            self.assertEqual(job.status, "completed")
            self.assertEqual(destinations, [root / ".pipeline_internal" / "preprocessed.wav"])
            self.assertNotEqual(destinations[0], source)

    def test_cancellation_during_output_never_becomes_completed(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-") as temporary:
            root = Path(temporary)
            job = self.job(root)
            options = self.options(root)

            def cancel_during_output(*args):
                job.cancel_event.set()
                args[-1]()

            with self.fake_pipeline() as calls:
                calls["write_outputs"].side_effect = cancel_during_output
                app.run_transcription_job(job, options)

            self.assertEqual(job.status, "cancelled")
            calls["upsert"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
