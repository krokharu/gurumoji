"""HaasのWSL境界を利用者DB・Vaultに触れず検証する。"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gurumoji.services.transcription import haas_stack, qwen_stack, wsl_stack


class HaasContractTests(unittest.TestCase):
    def test_runtime_rejects_another_workspace(self):
        config = {'workspace': str(wsl_stack.REPOSITORY_ROOT), 'distribution': 'Ubuntu-24.04',
                  'python': '/dedicated/python', 'nemotron_python': '/dedicated/python'}
        with patch.object(Path, 'read_text', return_value=json.dumps(config)), patch.object(Path, 'is_file', return_value=True):
            self.assertEqual(wsl_stack.load_wsl_runtime(), config)
        config['workspace'] = str(wsl_stack.REPOSITORY_ROOT / 'other-worktree')
        with patch.object(Path, 'read_text', return_value=json.dumps(config)), patch.object(Path, 'is_file', return_value=True):
            self.assertIsNone(wsl_stack.load_wsl_runtime())

    def test_invalid_runtime_does_not_launch_wsl(self):
        for value in ('{', '[]', 'null', '{}'):
            with self.subTest(value=value), patch.object(Path, 'read_text', return_value=value), patch.object(Path, 'is_file', return_value=True), patch.object(subprocess, 'run') as launch:
                self.assertIsNone(wsl_stack.load_wsl_runtime())
                launch.assert_not_called()

    def test_cpu_fails_before_worker_launch(self):
        with patch.object(haas_stack, 'haas_stack_available', return_value=True), patch.object(haas_stack, 'run_haas_worker') as launch:
            with self.assertRaisesRegex(RuntimeError, 'GPU'):
                haas_stack.run_haas_stack(asr_audio_path=Path('a'), diarization_audio_path=Path('a'), work_dir=Path('.'), language='ja', asr_device='cpu', diarization_device='cpu', status=lambda _: None, check_cancelled=lambda: None)
            launch.assert_not_called()

    def test_cancel_terminates_linux_and_native_processes(self):
        process = Mock()
        process.poll.return_value = None
        cancel = Mock()
        def interrupted():
            raise InterruptedError()
        with patch.object(Path, 'open', return_value=io.StringIO()), patch.object(qwen_stack.subprocess, 'Popen', return_value=process):
            with self.assertRaises(InterruptedError):
                qwen_stack.run_worker(Path('python'), Path('worker'), Path('request'), Path('log'), 'test', lambda _: None, interrupted, command=['wsl.exe'], cancel_worker=cancel)
        cancel.assert_called_once()
        process.terminate.assert_called_once()


@unittest.skipUnless(sys.platform == 'win32' and wsl_stack.load_wsl_runtime(), '準備済みのWindows/WSL環境で実行')
class WslBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='haas-日本語 空白-', dir=wsl_stack.REPOSITORY_ROOT / 'scratch')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.runtime = dict(wsl_stack.load_wsl_runtime(), python='/usr/bin/python3', nemotron_python='/usr/bin/python3')

    def test_unicode_paths_and_result_roundtrip(self):
        audio = self.base / '音声 入力.txt'
        audio.write_text('利用者データを使わない試験', encoding='utf-8')
        result = self.base / '出力 結果.json'
        request = self.base / 'request.json'
        request.write_text(json.dumps({'asr_audio': str(audio), 'diarization_audio': str(audio), 'result_path': str(result)}), encoding='utf-8')
        worker = self.base / 'worker.py'
        worker.write_text('import json,sys\nfrom pathlib import Path\np=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))\ntext=Path(p["asr_audio"]).read_text(encoding="utf-8")\nassert Path(p["diarization_audio"]).is_file()\nPath(p["result_path"]).write_text(json.dumps({"text":text}),encoding="utf-8")\n', encoding='utf-8')
        wsl_stack.run_wsl_worker(self.runtime, worker, request, self.base / 'worker.log', '試験', lambda _: None, lambda: None)
        self.assertEqual(json.loads(result.read_text(encoding='utf-8'))['text'], audio.read_text(encoding='utf-8'))

    def test_cancel_stops_linux_process_group(self):
        started = self.base / 'started.txt'
        worker = self.base / 'sleeper.py'
        worker.write_text('import json,sys,time\nfrom pathlib import Path\np=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))\nPath(p["result_path"]).write_text("started",encoding="utf-8")\ntime.sleep(60)\n', encoding='utf-8')
        request = self.base / 'request.json'
        request.write_text(json.dumps({'result_path': str(started)}), encoding='utf-8')
        pids = []
        deadline = time.monotonic() + 25
        def check():
            if started.exists():
                pids.append(int(request.with_suffix('.pid').read_text(encoding='ascii')))
                raise InterruptedError()
            if time.monotonic() > deadline:
                raise TimeoutError('WSL試験ワーカーが起動しませんでした')
        with self.assertRaises(InterruptedError):
            wsl_stack.run_wsl_worker(self.runtime, worker, request, self.base / 'worker.log', '中止試験', lambda _: None, check)
        command = [*wsl_stack.wsl_command(self.runtime), '/bin/kill', '-0', '--', f'-{pids[0]}']
        for _ in range(30):
            probe = subprocess.run(command, capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            if probe.returncode:
                break
            time.sleep(0.1)
        self.assertNotEqual(probe.returncode, 0, 'Linuxプロセスグループが残っています')


if __name__ == '__main__':
    unittest.main()