import array
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

from app import (
    run_audio_interval_preprocess,
    run_audio_preprocess,
    run_diarization_audio_preprocess,
)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
class AudioPreprocessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-preprocess-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_wav(self, name, samples, rate=16000, channels=1):
        path = self.root / name
        data = array.array("h", samples)
        if sys.byteorder != "little":
            data.byteswap()
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(channels)
            audio.setsampwidth(2)
            audio.setframerate(rate)
            audio.writeframes(data.tobytes())
        return path

    def read_wav(self, path):
        with wave.open(str(path), "rb") as audio:
            self.assertEqual(audio.getframerate(), 16000)
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            samples = array.array("h", audio.readframes(audio.getnframes()))
        if sys.byteorder != "little":
            samples.byteswap()
        return samples

    def assert_markers_preserved(self, samples, expected_frames):
        self.assertAlmostEqual(len(samples), expected_frames, delta=1)
        # Allow 1 ms for changes in the peak shape from filtering/resampling,
        # while rejecting the denoiser's 25 ms shift from the original media.
        peak = max(range(8000, 24000), key=lambda index: abs(samples[index]))
        self.assertAlmostEqual(peak, 16000, delta=16)
        # The final marker is only 12.5 ms from EOF: an uncompensated FFT
        # denoiser delays it past EOF and loses it entirely.
        tail_peak = max(abs(value) for value in samples[-400:])
        self.assertGreater(tail_peak, abs(samples[peak]) * 0.1)

    def test_full_audio_preserves_timing_tail_and_duration_across_sample_rates(self):
        for rate in (8000, 16000, 44100, 48000):
            # Deliberately do not end on an FFT frame boundary.
            frames = round(rate * 4.013)
            samples = [0] * frames
            samples[rate] = 16000
            samples[frames - round(rate * 0.0125)] = 16000
            source = self.write_wav("markers.wav", samples, rate)
            for preset in ("light", "standard", "strong"):
                with self.subTest(rate=rate, preset=preset):
                    output = self.root / "processed.wav"
                    run_audio_preprocess(source, output, preset)
                    self.assert_markers_preserved(
                        self.read_wav(output), round(frames / rate * 16000)
                    )

    def test_interval_preserves_timing_and_tail(self):
        samples = [0] * (10 * 16000)
        start, end = 5.25, 9.25
        samples[round((start + 1) * 16000)] = 16000
        samples[round((end - 0.0125) * 16000)] = 16000
        source = self.write_wav("markers.wav", samples)
        for preset in ("none", "light", "standard", "strong"):
            with self.subTest(preset=preset):
                output = self.root / "clip.wav"
                run_audio_interval_preprocess(source, output, start, end, preset)
                self.assert_markers_preserved(self.read_wav(output), 64000)

    def test_interval_duration_is_exact_near_eof_and_at_fractional_boundaries(self):
        source = self.write_wav(
            "tone.wav",
            (round(3200 * math.sin(2 * math.pi * 440 * n / 16000))
             for n in range(10 * 16000)),
        )
        for start, end in ((5.25, 9.25), (1.234, 5.678), (9.25, 10)):
            for preset in ("none", "light", "standard", "strong"):
                with self.subTest(start=start, end=end, preset=preset):
                    output = self.root / "clip.wav"
                    run_audio_interval_preprocess(source, output, start, end, preset)
                    self.assertEqual(
                        len(self.read_wav(output)), round((end - start) * 16000)
                    )

    def test_normalizes_final_mono_loudness_for_stereo_and_single_channel_audio(self):
        tone = [round(3200 * math.sin(2 * math.pi * 440 * n / 16000))
                for n in range(10 * 16000)]
        inputs = {
            "mono": self.write_wav("mono.wav", tone),
            "stereo": self.write_wav(
                "stereo.wav", (value for sample in tone for value in (sample, sample)),
                channels=2,
            ),
            "one_silent_channel": self.write_wav(
                "one_silent.wav", (value for sample in tone for value in (sample, 0)),
                channels=2,
            ),
        }
        for name, source in inputs.items():
            for preset in ("light", "standard", "strong"):
                with self.subTest(input=name, preset=preset):
                    output = self.root / "processed.wav"
                    run_audio_preprocess(source, output, preset)
                    self.read_wav(output)
                    measured = subprocess.run(
                        ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(output),
                         "-af", "loudnorm=I=-18:print_format=json", "-f", "null", "-"],
                        capture_output=True, text=True, check=True, timeout=30,
                    )
                    metrics, _ = json.JSONDecoder().raw_decode(
                        measured.stderr[measured.stderr.rfind("{"):]
                    )
                    self.assertAlmostEqual(float(metrics["input_i"]), -18, delta=0.3)

    def test_silence_stays_silent_without_changing_duration(self):
        source = self.write_wav("silence.wav", [0] * 64001)
        for preset in ("light", "standard", "strong"):
            with self.subTest(preset=preset):
                output = self.root / "processed.wav"
                run_audio_preprocess(source, output, preset)
                samples = self.read_wav(output)
                self.assertEqual(len(samples), 64001)
                self.assertFalse(any(samples))

    def test_diarization_input_lifts_only_too_quiet_speech(self):
        rate = 16000

        def tone(seconds, amplitude):
            return [
                round(amplitude * 32767 * math.sin(2 * math.pi * 180 * index / rate))
                for index in range(int(seconds * rate))
            ]

        # Quiet speaker (-34 dBFS peak), a loud speaker (-6 dBFS), then silence.
        samples = tone(3, 0.02) + tone(3, 0.5) + [0] * (2 * rate)
        source = self.write_wav("speakers.wav", samples, rate=rate)
        output = self.root / "diarization.wav"
        run_diarization_audio_preprocess(source, output)
        processed = self.read_wav(output)

        def rms(values, start, end):
            window = values[int(start * rate):int(end * rate)]
            return math.sqrt(sum(value * value for value in window) / len(window))

        self.assertAlmostEqual(len(processed), len(samples), delta=1)
        quiet_gain = rms(processed, 2.0, 3.0) / rms(samples, 2.0, 3.0)
        loud_gain = rms(processed, 3.5, 5.5) / rms(samples, 3.5, 5.5)
        self.assertGreater(quiet_gain, 3.0)
        self.assertLessEqual(quiet_gain, 4.05)
        self.assertAlmostEqual(loud_gain, 1.0, delta=0.02)
        self.assertLessEqual(max(abs(value) for value in processed), 0.5 * 32767 * 1.01)
        self.assertFalse(any(processed[int(6.2 * rate):]))

    def test_diarization_input_preserves_timing_and_tail(self):
        for rate in (16000, 48000):
            frames = round(rate * 4.013)
            samples = [0] * frames
            samples[rate] = 16000
            samples[frames - round(rate * 0.0125)] = 16000
            source = self.write_wav("markers.wav", samples, rate)
            with self.subTest(rate=rate):
                output = self.root / "diarization.wav"
                run_diarization_audio_preprocess(source, output)
                self.assert_markers_preserved(
                    self.read_wav(output), round(frames / rate * 16000)
                )


if __name__ == "__main__":
    unittest.main()
