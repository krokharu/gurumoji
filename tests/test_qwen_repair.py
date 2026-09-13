import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('qwen_repair', Path(__file__).resolve().parents[1] / 'scripts/repair_qwen_download.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class QwenRepairTests(unittest.TestCase):
    def run_repair(self, path, published, downloaded=None):
        expected = hashlib.sha256(published).hexdigest()
        responses = [io.BytesIO(json.dumps({'sha': 'fixed-revision'}).encode()),
                     io.BytesIO(json.dumps([{'path': repair.FILENAME, 'size': len(published),
                                            'lfs': {'oid': expected}}]).encode()),
                     io.BytesIO(published if downloaded is None else downloaded)]
        with patch('sys.argv', ['repair', str(path), '--repair']), \
                patch.object(repair.urllib.request, 'urlopen', side_effect=responses), \
                patch('sys.stdout', new_callable=io.StringIO):
            repair.main()

    def test_verified_replacement_preserves_original_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / repair.FILENAME
            path.write_bytes(b'broken model')
            original_hash = repair.digest(path)
            self.run_repair(path, b'verified model')
            self.assertEqual(path.read_bytes(), b'verified model')
            self.assertEqual(path.with_suffix(f'.gguf.backup-{original_hash[:12]}').read_bytes(), b'broken model')

    def test_failed_download_hash_never_replaces_original(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / repair.FILENAME
            path.write_bytes(b'original')
            with self.assertRaises(SystemExit):
                self.run_repair(path, b'correct model', b'corrupt model')
            self.assertEqual(path.read_bytes(), b'original')
            self.assertFalse(list(Path(folder).glob('*.backup-*')))

    def test_failed_install_restores_original(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / repair.FILENAME
            path.write_bytes(b'original')
            rename = Path.rename
            def fail_install(source, target):
                if str(source).endswith('.part'):
                    raise OSError('simulated failure')
                return rename(source, target)
            with patch.object(Path, 'rename', fail_install), self.assertRaises(OSError):
                self.run_repair(path, b'verified model')
            self.assertEqual(path.read_bytes(), b'original')

    def test_matching_model_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / repair.FILENAME
            path.write_bytes(b'verified model')
            timestamp = path.stat().st_mtime_ns
            self.run_repair(path, b'verified model')
            self.assertEqual(path.stat().st_mtime_ns, timestamp)
            self.assertEqual(list(Path(folder).iterdir()), [path])
