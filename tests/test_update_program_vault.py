import contextlib
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_program_vault.py"
spec = importlib.util.spec_from_file_location("update_program_vault", SCRIPT)
updater = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = updater
spec.loader.exec_module(updater)


def note(note_id: str, title: str, body: str = "本文") -> str:
    return f"---\nnote_id: {note_id}\ntitle: {title}\nstatus: current\n---\n\n# {title}\n\n{body}\n"


@unittest.skipUnless(shutil.which("git"), "git is required")
class ProgramVaultUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gurumoji-vault-update-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.origin = self.root / "origin.git"
        self.upstream = self.root / "upstream"
        self.local = self.root / "local"
        self.run_git(self.root, "init", "--quiet", "--bare", "-b", "main", str(self.origin))
        self.run_git(self.root, "clone", "--quiet", str(self.origin), str(self.upstream))
        self.configure(self.upstream)
        self.write(self.upstream, "00-Home.md", note("program-home", "ホーム"))
        self.write(self.upstream, "20-Modules/module-map.md", note("program-module-map", "対応表"))
        self.commit_and_push(self.upstream, "initial vault")
        self.run_git(self.root, "clone", "--quiet", str(self.origin), str(self.local))
        self.configure(self.local)

    def run_git(self, cwd, *args):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    def configure(self, repo):
        self.run_git(repo, "config", "user.email", "test@example.invalid")
        self.run_git(repo, "config", "user.name", "Test")
        self.run_git(repo, "checkout", "--quiet", "-B", "main")

    def write(self, repo, relative, text):
        path = repo / "docs" / "program-vault" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit_and_push(self, repo, message):
        self.run_git(repo, "add", "-A")
        self.run_git(repo, "commit", "--quiet", "-m", message)
        self.run_git(repo, "push", "--quiet", "origin", "main")

    def publish_update(self):
        self.write(self.upstream, "20-Modules/module-map.md", note("program-module-map", "対応表", "新しい本文"))
        self.write(self.upstream, "70-Changes/app-py-phase5.md", note("change-app-py-phase5", "分割の記録"))
        self.commit_and_push(self.upstream, "document the split")

    def main(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = updater.main([*args, "--repo", str(self.local)])
        return code, output.getvalue()

    def test_check_lists_upstream_notes_without_changing_the_clone(self):
        self.publish_update()
        head = (self.local / ".git" / "HEAD").read_text()
        code, output = self.main("check", "--remote", "origin", "--branch", "main")
        self.assertEqual(code, 0)
        self.assertIn("[追加] 分割の記録 (change-app-py-phase5)", output)
        self.assertIn("[更新] 対応表 (program-module-map)", output)
        self.assertEqual((self.local / ".git" / "HEAD").read_text(), head)
        self.assertNotIn("新しい本文", (self.local / "docs/program-vault/20-Modules/module-map.md").read_text(encoding="utf-8"))

    def test_apply_fast_forwards_the_vault_in_the_repository(self):
        self.publish_update()
        code, output = self.main("apply", "--remote", "origin", "--branch", "main")
        self.assertEqual(code, 0, output)
        vault = self.local / "docs" / "program-vault"
        self.assertTrue((vault / "70-Changes" / "app-py-phase5.md").is_file())
        self.assertIn("新しい本文", (vault / "20-Modules" / "module-map.md").read_text(encoding="utf-8"))

    def test_apply_stops_when_the_same_note_has_uncommitted_local_edits(self):
        self.publish_update()
        edited = self.local / "docs" / "program-vault" / "20-Modules" / "module-map.md"
        edited.write_text("利用者のメモ\n", encoding="utf-8")
        code, output = self.main("apply", "--remote", "origin", "--branch", "main")
        self.assertEqual(code, 1)
        self.assertIn("20-Modules/module-map.md", output)
        self.assertEqual(edited.read_text(encoding="utf-8"), "利用者のメモ\n")
        self.assertFalse((self.local / "docs/program-vault/70-Changes").exists())

    def test_target_sync_keeps_local_edits_and_parks_removed_notes(self):
        target = self.root / "PersonalVault"
        (target / ".obsidian").mkdir(parents=True)
        (target / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")
        code, _ = self.main("apply", "--remote", "origin", "--branch", "main", "--target", str(target))
        self.assertEqual(code, 0)
        self.assertTrue((target / "00-Home.md").is_file())

        (target / "20-Modules" / "module-map.md").write_text("利用者の追記\n", encoding="utf-8")
        self.publish_update()
        (self.upstream / "docs/program-vault/00-Home.md").unlink()
        self.commit_and_push(self.upstream, "remove home")
        code, output = self.main("apply", "--remote", "origin", "--branch", "main", "--target", str(target))

        self.assertEqual(code, 1)
        self.assertEqual((target / "20-Modules/module-map.md").read_text(encoding="utf-8"), "利用者の追記\n")
        incoming = target / ".gurumoji-sync" / "incoming" / "20-Modules" / "module-map.md"
        self.assertIn("新しい本文", incoming.read_text(encoding="utf-8"))
        self.assertTrue((target / "70-Changes" / "app-py-phase5.md").is_file())
        self.assertFalse((target / "00-Home.md").exists())
        self.assertTrue((target / ".gurumoji-sync" / "removed" / "00-Home.md").is_file())
        self.assertEqual((target / ".obsidian" / "workspace.json").read_text(encoding="utf-8"), "{}")
        self.assertIn("20-Modules/module-map.md", output)


if __name__ == "__main__":
    unittest.main()
