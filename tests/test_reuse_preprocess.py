"""RE-USE接続を一時音声と代替workerで確認する。実モデル品質は対象外。"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

from gurumoji.services.transcription import audio, reuse


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-reuse-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def wav(self, path, frames=16000):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x10\x00" * frames)
        return path

    def run_ffmpeg(self, args, **kwargs):
        return subprocess.run(args, capture_output=True, text=True, check=False)

    def processor(self):
        return audio.AudioProcessor(audio.AUDIO_PREPROCESS_PRESETS, 16000, self.run_ffmpeg)

    def test_reuse_is_a_model_not_an_empty_filter(self):
        with self.assertRaisesRegex(RuntimeError, "専用"):
            self.processor().filters("reuse")

    def test_unprepared_reuse_stops_before_conversion(self):
        with patch.object(reuse, "reuse_available", return_value=False), patch.object(self, "run_ffmpeg") as convert:
            with self.assertRaisesRegex(RuntimeError, "setup_reuse"):
                self.processor().preprocess(self.root/"in.wav", self.root/"out.wav", "reuse")
            convert.assert_not_called()

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpegが必要")
    def test_full_and_interval_route_to_model_and_clean_inputs(self):
        source = self.wav(self.root/"in.wav", 32000)
        target = self.root/"out.wav"
        def model(prepared, output, check):
            shutil.copyfile(prepared, output)
            return output
        with patch.object(reuse, "reuse_available", return_value=True), patch.object(reuse, "run_reuse", side_effect=model) as worker:
            self.processor().preprocess(source, target, "reuse")
            with wave.open(str(target)) as result:
                self.assertEqual(result.getnframes(), 32000)
            self.processor().preprocess_interval(source, target, 0.25, 1.25, "reuse")
            with wave.open(str(target)) as result:
                self.assertEqual(result.getnframes(), 16000)
            self.assertEqual(worker.call_count, 2)
        self.assertFalse(list(self.root.glob("*-reuse-input.wav")))
        self.assertFalse(list(self.root.glob("*-reuse-clip.wav")))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpegが必要")
    def test_model_failure_propagates_without_fallback(self):
        source = self.wav(self.root/"in.wav")
        with patch.object(reuse, "reuse_available", return_value=True), patch.object(reuse, "run_reuse", side_effect=InterruptedError("中止")):
            with self.assertRaises(InterruptedError):
                self.processor().preprocess(source, self.root/"out.wav", "reuse")
        self.assertFalse(list(self.root.glob("*-reuse-input.wav")))

    def test_worker_duration_is_validated(self):
        source = self.wav(self.root/"in.wav")
        destination = self.root/"out.wav"
        def worker(runtime, script, request, *args):
            payload = json.loads(request.read_text(encoding="utf-8"))
            self.assertEqual(payload["asr_audio"], str(source.resolve()))
            self.wav(Path(payload["result_path"]), 15999)
        with patch.object(reuse, "load_reuse_runtime", return_value={"model_directory":"/model"}), patch("gurumoji.services.transcription.wsl_stack.run_wsl_worker", side_effect=worker):
            with self.assertRaisesRegex(RuntimeError, "音声長"):
                reuse.run_reuse(source, destination)

    def test_runtime_rejects_a_different_workspace_and_revision(self):
        runtime = self.root/"runtime.json"
        runtime.write_text(json.dumps({"workspace":str(self.root),"ready":True}), encoding="utf-8")
        with patch.object(reuse,"RUNTIME_CONFIG",runtime):
            self.assertIsNone(reuse.load_reuse_runtime())

    def test_chunked_worker_preserves_short_tail_and_overlap(self):
        import numpy as np
        import soundfile as sf
        import torch
        path = reuse.REPOSITORY_ROOT/"scripts/reuse_audio_worker.py"
        spec = importlib.util.spec_from_file_location("reuse_worker_test", path)
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        stfts = types.ModuleType("models.stfts")
        stfts.mag_phase_stft = lambda samples,*args,**kwargs: (torch.ones_like(samples).unsqueeze(1),samples.unsqueeze(1),None)
        stfts.mag_phase_istft = lambda magnitude,phase,*args: phase.squeeze(1)
        config = {"stft_cfg":{"n_fft":320,"hop_size":40,"win_size":320,"sampling_rate":8000},"model_cfg":{"compress_factor":"relu_log1p"}}
        hann, tensor_to = torch.hann_window, torch.Tensor.to
        def cpu_to(tensor,*args,**kwargs):
            return tensor_to(tensor,*(('cpu',)+args[1:] if args and args[0]=='cuda' else args),**kwargs)
        with patch.dict(sys.modules,{"models":types.ModuleType("models"),"models.stfts":stfts}), patch.object(worker,"load_model",return_value=(lambda mag,phase:(mag,phase,None),config)), patch.object(torch,"hann_window",side_effect=lambda length,**kw:hann(length)), patch.object(torch.Tensor,"to",cpu_to):
            for frames in (1,200,1600,80000,80001,176123):
                source, output = self.root/"input.wav", self.root/"output.wav"
                samples = np.sin(np.arange(frames)*0.04).astype(np.float32)*0.2
                sf.write(source,samples,16000,subtype="PCM_16")
                reference,_ = sf.read(source,dtype="float32")
                worker.enhance({"model_directory":"/model","asr_audio":str(source),"result_path":str(output)})
                result,rate = sf.read(output,dtype="float32")
                self.assertEqual(rate,16000)
                self.assertEqual(len(result),frames)
                self.assertLessEqual(float(np.max(np.abs(reference-result))),2/32768)
                self.assertFalse(list(self.root.glob("*.partial.wav")))


if __name__ == "__main__":
    unittest.main()
