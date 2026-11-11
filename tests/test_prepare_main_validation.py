"""架空Git repoで検証cloneの隔離・秘密除外・main優先を確認する。"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_main_validation.py"
SPEC = importlib.util.spec_from_file_location("prepare_main_validation", SCRIPT)
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


class PrepareMainValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "main"
        self.target = self.base / "validation"
        self.source.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "合成試験")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "core.hooksPath", str(self.base / "no-hooks"))
        self.write("src/app.py", b"main-code\r\n")
        self.write("src/removed.py", b"deleted\n")
        self.write("docs/program-vault/runtime.md", b"runtime-main\n")
        self.write("docs/program-vault/00-Catalog.json", b'{"main":true}\n')
        self.write("scripts/run.py", b"main-maintenance\n")
        self.write(".gitignore", b"runtime/\noutput/\n.env\nconfig/tokens.json\n")
        self.git("add", ".")
        self.git("commit", "-m", "合成mainを保存")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.git("switch", "-c", "archive/test")
        self.write("src/app.py", b"old-development-code\n")
        self.write("src/archive_only.py", b"never-copy\n")
        self.write("docs/program-vault/runtime.md", b"old-definition\n")
        self.write("docs/program-vault/00-Catalog.json", b'{"old":true}\n')
        self.write("docs/program-vault/design.md", b"saved-design\n")
        self.write("scripts/run.py", b"old-maintenance\n")
        self.write("scripts/run_tests.py", b"synthetic-runner\n")
        self.write("tests/test_contract.py", b"assert True\n")
        self.write("tests/.env", b"do-not-deliver\n")
        self.write("config/requirements-dev.txt", b"pytest\n")
        self.write("pytest.ini", b"[pytest]\n")
        self.write("devtools/console.py", b"synthetic-console\n")
        self.write(".agents/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py", b"synthetic-reader\n")
        self.write(".agents/rules/private.md", b"SYNTHETIC_UNSELECTED_RULE\n")
        self.git("add", ".")
        self.git("commit", "-m", "合成開発資料を保存")
        self.archive = self.git("rev-parse", "HEAD").decode().strip()
        self.git("switch", "main")

    def git(self, *arguments):
        return subprocess.check_output(["git", "--no-optional-locks", "-C", str(self.source), *arguments],
                                       stderr=subprocess.PIPE)

    def write(self, name, raw):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def run_prepare(self, **kwargs):
        return preparation.prepare(self.source, self.target, self.archive, **kwargs)

    def test_dirty_tracked_bytes_staging_and_deletions_are_preserved_without_touching_source(self):
        self.write("src/app.py", b"updated\r\n\x00\xff")
        self.write("src/staged.py", b"staged-addition\n")
        self.git("add", "src/staged.py")
        (self.source / "src/removed.py").unlink()
        self.write(".env", b"SYNTHETIC_PRIVATE_ENV")
        self.write("config/tokens.json", b"SYNTHETIC_PRIVATE_TOKEN")
        self.write("runtime/data/library.sqlite3", b"SYNTHETIC_PRIVATE_DB")
        self.write("output/private.txt", b"SYNTHETIC_PRIVATE_OUTPUT")
        self.write("src/untracked.py", b"SYNTHETIC_UNSELECTED_CODE")
        before_status = self.git("status", "--porcelain=v1", "-z")
        before_index = (self.source / ".git/index").read_bytes()
        before = {path.relative_to(self.source).as_posix(): path.read_bytes()
                  for path in self.source.rglob("*") if path.is_file() and ".git" not in path.parts}
        manifest = self.run_prepare()
        self.assertEqual((self.target / "src/app.py").read_bytes(), b"updated\r\n\x00\xff")
        self.assertEqual((self.target / "src/staged.py").read_bytes(), b"staged-addition\n")
        self.assertFalse((self.target / "src/removed.py").exists())
        self.assertEqual(manifest["main_deleted_paths"], ["src/removed.py"])
        self.assertEqual(manifest["source_head"], self.head)
        self.assertEqual(manifest["archive_commit"], self.archive)
        self.assertEqual(self.git("status", "--porcelain=v1", "-z"), before_status)
        self.assertEqual((self.source / ".git/index").read_bytes(), before_index)
        after = {path.relative_to(self.source).as_posix(): path.read_bytes()
                 for path in self.source.rglob("*") if path.is_file() and ".git" not in path.parts}
        self.assertEqual(before, after)
        for name in (".env", "config/tokens.json", "runtime/data/library.sqlite3", "output/private.txt",
                     "src/untracked.py", "tests/.env"):
            self.assertFalse((self.target / name).exists(), name)
        for record in manifest["files"]:
            self.assertEqual(hashlib.sha256((self.target / record["path"]).read_bytes()).hexdigest(), record["sha256"])
        saved = json.loads((self.target / "output/validation/prepare-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, manifest)

    def test_archive_only_supplements_assets_and_never_overwrites_main_or_copies_old_source(self):
        manifest = self.run_prepare()
        for name in ("src/app.py", "scripts/run.py", "docs/program-vault/runtime.md",
                     "docs/program-vault/00-Catalog.json"):
            self.assertEqual((self.target / name).read_bytes(), (self.source / name).read_bytes())
        for name in ("tests/test_contract.py", "scripts/run_tests.py", "docs/program-vault/design.md",
                     "config/requirements-dev.txt", "pytest.ini", "devtools/console.py"):
            self.assertTrue((self.target / name).is_file(), name)
        self.assertFalse((self.target / "src/archive_only.py").exists())
        self.assertEqual({row["path"] for row in manifest["files"] if row["origin"] == "archive"},
                         {"tests/test_contract.py", "scripts/run_tests.py", "docs/program-vault/design.md",
                          "config/requirements-dev.txt", "pytest.ini", "devtools/console.py",
                          ".agents/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py"})

    def test_only_exact_collection_reader_is_supplemented_from_agent_assets(self):
        self.run_prepare()
        reader=".agents/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py"
        self.assertEqual((self.target/reader).read_bytes(),b"synthetic-reader\n")
        self.assertFalse((self.target/".agents/rules/private.md").exists())

    def test_manifest_distinguishes_main_catalogue_scope_from_extra_archive_design_notes(self):
        manifest=self.run_prepare()
        prefix="docs/program-vault/"
        main_notes={row["path"][len(prefix):] for row in manifest["files"]
                    if row["origin"] in {"main","main-explicit"}
                    and row["path"].startswith(prefix) and row["path"].endswith(".md")}
        self.assertEqual(main_notes,{"runtime.md"})
        all_notes={path.name for path in (self.target/prefix).glob("*.md")}
        self.assertEqual(all_notes,{"runtime.md","design.md"})
        self.assertEqual((self.target/prefix/"00-Catalog.json").read_bytes(),b'{"main":true}\n')

    def test_explicit_untracked_application_change_is_included_without_sweeping_other_files(self):
        self.write("src/new.py", b"new-byte-snapshot\n")
        self.write("src/private.txt", b"SYNTHETIC_PRIVATE")
        manifest = self.run_prepare(include=["src/new.py"])
        self.assertEqual((self.target / "src/new.py").read_bytes(), b"new-byte-snapshot\n")
        self.assertFalse((self.target / "src/private.txt").exists())
        record = next(row for row in manifest["files"] if row["path"] == "src/new.py")
        self.assertEqual(record["origin"], "main-explicit")

    def test_protected_explicit_paths_and_traversal_are_rejected_before_target_creation(self):
        for name in (".env", ".env.local", "config/tokens.json", "runtime/data/db", "output/a", "../escape", "/absolute", "src/../escape"):
            with self.subTest(path=name), self.assertRaises(preparation.PreparationError):
                self.run_prepare(include=[name])
            self.assertFalse(self.target.exists())

    def test_existing_even_empty_target_is_refused(self):
        self.target.mkdir()
        with self.assertRaises(preparation.PreparationError):
            self.run_prepare()
        self.assertEqual(list(self.target.iterdir()), [])

    def test_source_and_target_overlaps_are_refused(self):
        for target in (self.source, self.source / "child", self.source.parent):
            with self.subTest(target=target), self.assertRaises(preparation.PreparationError):
                preparation.prepare(self.source, target, self.archive)
        self.assertFalse((self.source / "child").exists())

    def test_non_main_and_detached_sources_are_refused(self):
        self.git("switch", "archive/test")
        with self.assertRaises(preparation.PreparationError):
            self.run_prepare()
        self.git("checkout", "--detach", self.head)
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_prepare()
        self.assertFalse(self.target.exists())

    def test_tracked_symlink_mode_is_rejected_without_needing_os_symlink_permission(self):
        oid = self.git("hash-object", "src/app.py").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{oid},linked")
        with self.assertRaises(preparation.PreparationError):
            self.run_prepare()
        self.assertFalse(self.target.exists())

    def test_archive_symlink_asset_is_rejected_before_cloning(self):
        self.git("switch", "archive/test")
        oid = self.git("hash-object", "src/app.py").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{oid},tests/linked")
        self.git("commit", "-m", "合成リンクmodeを保存")
        self.archive = self.git("rev-parse", "HEAD").decode().strip()
        self.git("switch", "main")
        with self.assertRaises(preparation.PreparationError):
            self.run_prepare()
        self.assertFalse(self.target.exists())

    def test_real_symlink_paths_are_refused(self):
        link = self.base / "link"
        try:
            link.symlink_to(self.source, target_is_directory=True)
        except OSError:
            self.skipTest("Windows symlink作成権限なし。Git symlink modeは別試験で検証済み")
        with self.assertRaises(preparation.PreparationError):
            preparation.prepare(link, self.target, self.archive)
        with self.assertRaises(preparation.PreparationError):
            preparation.prepare(self.source, link / "child", self.archive)

    def test_source_change_during_preparation_is_detected(self):
        original = preparation.git
        def change_after_clone(repository, *arguments):
            result = original(repository, *arguments)
            if Path(repository) == self.target and arguments == ("read-tree", "HEAD"):
                self.write("src/app.py", b"concurrent-edit\n")
            return result
        with patch.object(preparation, "git", side_effect=change_after_clone):
            with self.assertRaises(preparation.PreparationError):
                self.run_prepare()
        self.assertFalse((self.target / "output/validation/prepare-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
