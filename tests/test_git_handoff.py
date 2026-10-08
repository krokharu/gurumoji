"""Offline receipt checks using only synthetic files and temporary Git repos."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_git_handoff.py"
SPEC = importlib.util.spec_from_file_location("check_git_handoff", SCRIPT)
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


class GitHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root_patch = patch.object(handoff, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        (self.root / "docs").mkdir()
        self.payload = b"synthetic receipt\n"
        (self.root / "payload.txt").write_bytes(self.payload)
        self.manifest = {
            "schema_version": 1,
            "source_commit": "a" * 40,
            "base_commit": "b" * 40,
            "branch": "shared/receipt",
            "status": "engineering_hold",
            "files": [{"path": "payload.txt", "sha256": hashlib.sha256(self.payload).hexdigest(),
                       "bytes": len(self.payload)}],
        }
        self.write_manifest(self.manifest)
        self.git("init", "--quiet")
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True,
                                       stderr=subprocess.PIPE).strip()

    def write_manifest(self, value):
        (self.root / "docs/git-handoff-manifest.json").write_text(json.dumps(value), encoding="utf-8")

    def commit(self):
        self.git("add", "payload.txt", "docs/git-handoff-manifest.json")
        self.git("-c", "user.name=Receipt Test", "-c", "user.email=receipt@example.invalid",
                 "commit", "--quiet", "--allow-empty", "-m", "Synthetic receipt")
        self.head = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/shared/receipt", self.head)

    def receipt(self, *args):
        with patch.object(sys, "argv", [str(SCRIPT), *args]), contextlib.redirect_stdout(io.StringIO()) as out:
            code = handoff.main()
        return code, json.loads(out.getvalue())

    def test_clean_fixed_sha_and_git_guards(self):
        code, result = self.receipt("--expected-commit", self.head)
        self.assertEqual(code, 0)
        self.assertTrue(result["received"])
        self.assertEqual(result["checked_files"], 1)
        self.assertEqual(result["engineering_status"], "engineering_hold")
        self.assertFalse(result["dirty"])
        code, result = self.receipt("--expected-commit", "c" * 40)
        self.assertEqual(code, 1)
        self.assertFalse(result["expected_commit_matches"])
        (self.root / "untracked.txt").write_text("synthetic", encoding="utf-8")
        code, result = self.receipt()
        self.assertEqual(code, 1)
        self.assertTrue(result["dirty"])
        self.assertEqual(self.git("rev-parse", "HEAD"), self.head)

    def test_missing_and_different_remote_ref(self):
        previous = self.head
        self.commit()
        self.git("update-ref", "refs/remotes/origin/shared/receipt", previous)
        self.assertFalse(self.receipt()[1]["received"])
        self.git("update-ref", "-d", "refs/remotes/origin/shared/receipt")
        code, result = self.receipt()
        self.assertEqual(code, 1)
        self.assertIsNone(result["remote_commit"])

    def test_schema_empty_duplicate_and_malformed_rows_fail_before_fetch(self):
        variants = [None, [], {}, dict(self.manifest, schema_version=True),
                    dict(self.manifest, schema_version=2), dict(self.manifest, status=""),
                    dict(self.manifest, source_commit="bad"), dict(self.manifest, branch="bad:ref"),
                    dict(self.manifest, files=[]), dict(self.manifest, files={}),
                    dict(self.manifest, files=[None]),
                    dict(self.manifest, files=self.manifest["files"] * 2)]
        for field, values in {"sha256": [None, "g" * 64, "a" * 63],
                              "bytes": [None, True, -1, 1.0, "18"],
                              "path": [None, "", "/tmp/outside", "../outside", "a/../payload.txt",
                                       "./payload.txt", "a//b", "C:/outside", "a\\b", "a\x00b"]}.items():
            for value in values:
                variant = copy.deepcopy(self.manifest)
                variant["files"][0][field] = value
                variants.append(variant)
        for variant in variants:
            with self.subTest(manifest=variant):
                self.write_manifest(variant)
                with patch.object(handoff, "git", side_effect=AssertionError("must not fetch or inspect Git")):
                    code, result = self.receipt("--fetch")
                self.assertEqual(code, 1)
                self.assertFalse(result["received"])
                self.assertIn("manifest_error", result)

    def test_bad_json_duplicate_keys_and_missing_manifest(self):
        target = self.root / "docs/git-handoff-manifest.json"
        for text in ('{', '{"schema_version": 1, "schema_version": 1}', '\xff'):
            with self.subTest(text=text):
                target.write_bytes(text.encode("latin1"))
                code, result = self.receipt()
                self.assertEqual(code, 1)
                self.assertFalse(result["received"])
                self.assertIn("manifest_error", result)
        target.unlink()
        self.assertIn("manifest_error", self.receipt()[1])

    def test_nonportable_components_rejected_on_every_host_before_fetch(self):
        names = ["payload.txt.", "payload.txt ", "dir./payload.txt", "dir /payload.txt",
                 "CON", "prn.txt", "aux.log", "NUL.data", "con .txt", "CONIN$", "CONOUT$.txt",
                 "COM1.txt", "com9", "LPT1", "lpt9.log", "COM¹.txt", "LPT²", "COM³",
                 "dir/NUL.txt/file.txt", 'bad"name', "bad<name", "bad>name",
                 "bad|name", "bad?name", "bad*name"]
        for name in names:
            with self.subTest(path=name):
                manifest = copy.deepcopy(self.manifest)
                manifest["files"][0]["path"] = name
                self.write_manifest(manifest)
                with patch.object(handoff, "git", side_effect=AssertionError("must not fetch or inspect Git")):
                    code, result = self.receipt("--fetch")
                self.assertEqual(code, 1)
                self.assertFalse(result["received"])
                self.assertIn("nonportable path component", result["manifest_error"])
        for name in ("console.txt", "COM10.txt", "LPT0.txt", "dir.with.dots/file name.txt"):
            with self.subTest(valid_path=name):
                manifest = copy.deepcopy(self.manifest)
                manifest["files"][0]["path"] = name
                handoff.validate_manifest(manifest)

    def test_case_equivalent_duplicates_rejected_on_every_host(self):
        for names in (("payload.txt", "PAYLOAD.TXT"),
                      ("Dir/payload.txt", "dir/PAYLOAD.txt")):
            with self.subTest(paths=names):
                manifest = copy.deepcopy(self.manifest)
                manifest["files"] = [dict(manifest["files"][0], path=name) for name in names]
                self.write_manifest(manifest)
                self.commit()
                self.assertEqual(self.git("status", "--porcelain"), "")
                with patch.object(handoff, "git", side_effect=AssertionError("must not fetch or inspect Git")):
                    code, result = self.receipt("--fetch")
                self.assertEqual(code, 1)
                self.assertFalse(result["received"])
                self.assertIn("duplicate file path", result["manifest_error"])

    def test_declared_bytes_and_hash_checked_even_in_clean_checkout(self):
        for field, value in (("bytes", 0), ("sha256", "0" * 64)):
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                manifest["files"][0][field] = value
                self.write_manifest(manifest)
                self.commit()
                code, result = self.receipt()
                self.assertEqual(code, 1)
                self.assertFalse(result["received"])
                self.assertFalse(result["dirty"])
                self.assertEqual(result["mismatches"], ["payload.txt"])

    def test_missing_directory_outside_symlink_and_read_error(self):
        target = self.root / "payload.txt"
        target.unlink()
        self.assertEqual(self.receipt()[1]["mismatches"], ["payload.txt"])
        target.mkdir()
        self.assertEqual(self.receipt()[1]["mismatches"], ["payload.txt"])
        target.rmdir()
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "outside.txt"
            outside.write_bytes(self.payload)
            try:
                target.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            self.assertEqual(self.receipt()[1]["mismatches"], ["payload.txt"])
        target.unlink()
        target.write_bytes(self.payload)
        with patch.object(Path, "read_bytes", side_effect=PermissionError("synthetic read denial")):
            code, result = self.receipt()
        self.assertEqual(code, 1)
        self.assertEqual(result["mismatches"], ["payload.txt"])


if __name__ == "__main__":
    unittest.main()
