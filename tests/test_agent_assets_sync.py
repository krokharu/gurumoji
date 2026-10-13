import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_agent_assets.py"
spec = importlib.util.spec_from_file_location("sync_agent_assets", SCRIPT)
sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sync
spec.loader.exec_module(sync)


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


class RepositoryCopiesTests(unittest.TestCase):
    def test_claude_copies_match_agents_sources(self):
        self.assertEqual(sync.differences(ROOT), [],
                         "run: python scripts/sync_agent_assets.py apply")

    def test_links_in_claude_copies_resolve(self):
        for copy in sync.expected(ROOT):
            if copy.suffix != ".md":
                continue
            text = (ROOT / copy).read_text(encoding="utf-8")
            for link in sync.LINK.findall(text):
                path = link.partition("#")[0]
                if not path or "://" in path:
                    continue
                with self.subTest(copy=str(copy), link=link):
                    self.assertTrue((ROOT / copy).parent.joinpath(path).exists())


class SyncBehaviourTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gurumoji-agent-assets-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        write(self.root, "AGENTS.md", "# root\n")
        write(self.root, ".agents/rules/local.md", "# rule\n")
        write(self.root, ".agents/skills/demo/SKILL.md",
              "---\nname: demo\ndescription: d\n---\n\n"
              "[root](../../../AGENTS.md) [critic](../../agents/critic.md#top)\n"
              "run `.agents/skills/demo/scripts/x.py`\n")
        write(self.root, ".agents/skills/demo/scripts/x.py", "print('.agents/skills/')\n")
        write(self.root, ".agents/skills/demo/agents/openai.yaml", "interface: {}\n")
        write(self.root, ".agents/agents/critic.md",
              "---\nname: critic\ndescription: c\n---\n\n[rule](../rules/local.md) [web](https://example.com/a)\n")

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text(encoding="utf-8")

    def test_apply_writes_copies_with_resolvable_links(self):
        sync.apply(self.root)

        skill = self.read(".claude/skills/demo/SKILL.md")
        self.assertTrue(skill.startswith("---\nname: demo\ndescription: d\n---\n<!-- 生成物: .agents/skills/demo/SKILL.md"))
        self.assertIn("[root](../../../AGENTS.md)", skill)
        self.assertIn("[critic](../../agents/critic.md#top)", skill)
        self.assertIn("`.claude/skills/demo/scripts/x.py`", skill)
        self.assertEqual(self.read(".claude/skills/demo/scripts/x.py"), "print('.agents/skills/')\n")
        self.assertFalse((self.root / ".claude/skills/demo/agents").exists())

        critic = self.read(".claude/agents/critic.md")
        self.assertIn("[rule](../../.agents/rules/local.md)", critic)
        self.assertIn("[web](https://example.com/a)", critic)
        self.assertFalse((self.root / ".claude/rules").exists())
        self.assertEqual(sync.differences(self.root), [])

    def test_check_reports_edited_missing_and_stale_copies(self):
        sync.apply(self.root)
        write(self.root, ".claude/skills/demo/SKILL.md", "edited\n")
        os.remove(self.root / ".claude/agents/critic.md")
        write(self.root, ".claude/skills/demo/old.md", "left over\n")
        write(self.root, ".claude/skills/own/SKILL.md", "not generated\n")

        self.assertEqual(sync.differences(self.root), [
            "missing: .claude/agents/critic.md",
            "differs: .claude/skills/demo/SKILL.md",
            "stale: .claude/skills/demo/old.md",
        ])
        sync.apply(self.root)
        self.assertEqual(sync.differences(self.root), [])
        self.assertFalse((self.root / ".claude/skills/demo/old.md").exists())
        self.assertEqual(self.read(".claude/skills/own/SKILL.md"), "not generated\n")

    def test_removed_source_removes_only_generated_agent(self):
        sync.apply(self.root)
        write(self.root, ".claude/agents/hand-written.md", "---\nname: h\n---\nmine\n")
        os.remove(self.root / ".agents/agents/critic.md")

        self.assertIn("stale: .claude/agents/critic.md", sync.differences(self.root))
        sync.apply(self.root)
        self.assertFalse((self.root / ".claude/agents/critic.md").exists())
        self.assertTrue((self.root / ".claude/agents/hand-written.md").exists())


if __name__ == "__main__":
    unittest.main()
