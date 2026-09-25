import json
import tempfile
import unittest
from itertools import permutations
from pathlib import Path
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_method_registry import METHODS
from gurumoji.obsidian_layout import unpack
from gurumoji.vault_registry import GENERATED, VaultRegistry, entity_key


def read_notes(root: Path) -> dict[str, tuple[dict, str]]:
    return {path.relative_to(root).as_posix(): unpack(path.read_text(encoding="utf-8"))
            for path in root.rglob("*.md") if ".obsidian" not in path.parts}


class VaultRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.software = base / "repo" / "docs" / "program-vault"
        self.registry = VaultRegistry(base / "data" / "library.sqlite3", self.software)
        self.segments = [
            {"id": "s1", "speaker": "SPEAKER_00", "start": 0.0, "end": 2.5, "text": "秘密の発言です"},
            {"id": "s2", "speaker": "UNKNOWN", "start": 3.0, "end": 2.0, "text": ""},
        ]
        self.note = f"10-Inputs/input-{entity_key('job-1')}.md"

    def publish(self, revision=0, segments=None, whisper=None):
        return self.registry.publish_input(
            item_id="job-1", title="面談.wav", segments=segments or self.segments, revision=revision,
            language="ja", source_kind="whisper" if whisper else None,
            whisper=whisper)

    def test_whisper_ledger_has_provenance_and_quality_but_no_text_or_secrets(self):
        status = self.publish(whisper={"model": "large-v3", "device": "cuda", "hf_token": "hf_secret"})
        self.assertEqual(status, "written")
        roots = self.registry.roots()
        for kind in GENERATED:
            self.assertEqual(roots[kind].parent, self.registry.data / "obsidian")
            self.assertTrue((roots[kind] / ".obsidian/app.json").is_file())
            self.assertTrue((roots[kind] / "00-Home.md").is_file())
        for first, second in permutations([roots[kind] for kind in GENERATED], 2):
            self.assertFalse(first.is_relative_to(second))
        self.assertFalse(self.software.exists())
        props, body = read_notes(roots["input"])[self.note]
        self.assertEqual((props["vault_kind"], props["revision"]), ("input", 0))
        self.assertTrue(props["source_hash"].startswith("sha256:"))
        self.assertIn("large-v3", body)
        self.assertIn("| UNKNOWN話者 | 1 |", body)
        self.assertIn("| 時刻が不正な発話 | 1 |", body)
        vault_text = "\n".join(path.read_text(encoding="utf-8") for path in roots["input"].rglob("*.md"))
        self.assertNotIn("秘密の発言", vault_text)
        self.assertNotIn("hf_secret", vault_text)
        self.assertIn("input-item-" + entity_key("job-1"), (roots["input"] / "00-Index.md").read_text(encoding="utf-8"))

    def test_republish_is_byte_stable_and_edits_keep_whisper_settings(self):
        self.publish(whisper={"model": "large-v3"})
        root = self.registry.root("input")
        before = {path: path.read_bytes() for path in root.rglob("*.md")}
        self.assertEqual(self.publish(), "unchanged")
        self.assertEqual({path: path.read_bytes() for path in root.rglob("*.md")}, before)
        edited = [{**self.segments[0], "text": "直した発言"}, self.segments[1]]
        self.assertEqual(self.publish(revision=1, segments=edited), "written")
        props, body = read_notes(root)[self.note]
        self.assertEqual(props["revision"], 1)
        self.assertIn("large-v3", body)
        self.assertIn("Whisper文字起こし", body)

    def test_human_edits_are_kept_in_history_and_deletions_are_not_recreated(self):
        self.publish()
        root = self.registry.root("input")
        path = root / self.note
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n研究者のメモ\n")
        self.assertEqual(self.publish(revision=1), "overwritten")
        self.assertNotIn("研究者のメモ", path.read_text(encoding="utf-8"))
        self.assertEqual(read_notes(root)[self.note][0]["revision"], 1)
        history = sorted((root / "99-Archive/history").rglob("*.md"))
        self.assertEqual(sorted(p.name.split("-", 1)[1] for p in history if p.parent.name.startswith("input-")),
                         ["edited.md", "first.md"])
        edited = next(p for p in history if p.name.endswith("-edited.md"))
        self.assertIn("研究者のメモ", edited.read_text(encoding="utf-8"))
        self.assertNotIn("99-Archive", (root / "00-Index.md").read_text(encoding="utf-8"))
        path.unlink()
        self.assertEqual(self.publish(revision=2), "missing")
        self.assertFalse(path.exists())
        self.assertIn("削除を検出", (root / "00-Index.md").read_text(encoding="utf-8"))
        (root / "00-Index.md").unlink()
        self.publish(revision=2)
        self.assertTrue((root / "00-Index.md").exists())

    def test_software_and_research_vaults_are_not_generated_roots(self):
        data = self.registry.load()
        with self.assertRaises(ValueError):
            self.registry._write(data, "software", "x.md", "software-x", {}, "# x")
        data["vaults"]["input"]["root"] = "obsidian/ResearchVault"
        self.registry.save(data)
        with self.assertRaises(ValueError):
            self.registry.roots()


class AnalysisVaultTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.store = app.analysis_archive_store()

    def test_saved_analysis_is_split_across_input_orchestrator_and_visualization(self):
        with patch.object(app, "call_ai_json") as ai:
            response = self.client.post(self.fixture.url + "/runs", json=self.fixture.payload("archive-request-000001"))
            ai.assert_not_called()
        self.assertEqual(response.status_code, 200, response.get_json())
        run = response.get_json()["run"]
        roots = self.store.vaults.roots()
        orchestrator = read_notes(roots["orchestrator"])
        props, body = orchestrator[f"20-Runs/run-{run['id']}.md"]
        self.assertEqual((props["run_id"], props["status"]), (run["id"], "current"))
        self.assertIn("[[10-Methods/morphology", body)
        for method_id, _, _ in METHODS:
            self.assertIn(f"10-Methods/{method_id}.md", orchestrator)
        artifact_ids = {artifact["id"] for artifact in run["artifacts"]}
        visuals = {path: note for path, note in read_notes(roots["visualization"]).items()
                   if path.startswith(f"10-Visuals/run-{run['id']}/")}
        self.assertTrue(visuals)
        self.assertNotIn(f"10-Visuals/run-{run['id']}/ai_insights.md", visuals)  # not run
        self.assertIn("| 値 | `turn_count` |", visuals[f"10-Visuals/run-{run['id']}/participation.md"][1])
        self.assertEqual(len(props["artifact_ids"]), 1)  # full list stays in the body table
        for visual_props, _ in visuals.values():
            self.assertTrue(set(visual_props["artifact_ids"]) <= artifact_ids)
        inputs = read_notes(roots["input"])
        snapshots = [note for path, note in inputs.items() if path.startswith("20-Snapshots/")]
        self.assertEqual([note[0]["input_snapshot_id"] for note in snapshots], [props["input_snapshot_id"]])
        self.assertIn(f"10-Inputs/input-{entity_key('content')}.md", inputs)
        # Transcript quotes stay in ResearchVault; the four Vaults hold IDs and summaries only.
        generated = "\n".join(path.read_text(encoding="utf-8") for kind in GENERATED for path in roots[kind].rglob("*.md"))
        self.assertNotIn("価格を価格で比べる", generated)
        self.assertIn("価格を価格で比べる", "\n".join(p.read_text(encoding="utf-8") for p in self.store.vault.rglob("*.md")))
        catalog = json.loads(self.store.vaults.catalog_file.read_text(encoding="utf-8"))
        locations = [(entry["vault"], entry["path"]) for entry in catalog["notes"].values()]
        self.assertEqual(len(locations), len(set(locations)))

        before = {path: path.read_bytes() for kind in GENERATED for path in roots[kind].rglob("*.md")}
        self.store.publish(run["id"])
        self.assertEqual({path: path.read_bytes() for kind in GENERATED for path in roots[kind].rglob("*.md")}, before)

        data = self.client.get(self.fixture.url).get_json()
        config = data["config"]
        config["research_question"] = "別の問い"
        self.client.put(self.fixture.url, json={"source_revision": 0, "config": config,
                                                "analysis_revision": data["item"]["analysis_revision"]})
        self.assertEqual(read_notes(roots["orchestrator"])[f"20-Runs/run-{run['id']}.md"][0]["status"], "stale")
        self.assertTrue(all(note[0]["status"] == "stale" for path, note in read_notes(roots["visualization"]).items()
                            if path.startswith(f"10-Visuals/run-{run['id']}/")))

    def test_deleting_conversation_marks_research_vault_and_keeps_notes(self):
        with patch.object(app, "call_ai_json"):
            response = self.client.post(self.fixture.url + "/runs", json=self.fixture.payload("archive-request-000001"))
        self.assertEqual(response.status_code, 200, response.get_json())
        notes_before = {p for p in self.store.vault.rglob("*.md")}
        deleted = self.client.delete("/api/library/content")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        record = self.store.layout.load()["interviews"]["content"]
        self.assertEqual(record["status"], "アプリから削除済み")
        self.assertTrue(record["deleted_at"])
        hub = (self.store.vault / record["hub"]).read_text(encoding="utf-8")
        self.assertEqual(unpack(hub)[0]["status"], "アプリから削除済み")
        self.assertTrue(notes_before <= set(self.store.vault.rglob("*.md")))

    def test_whisper_hook_records_settings_and_edit_keeps_them(self):
        row = app.library_row("content")
        app.publish_input_vault(row, {"model": "large-v3", "language": "ja", "device": "cpu", "hf_token": "hf_secret"})
        root = self.store.vaults.root("input")
        path = f"10-Inputs/input-{entity_key('content')}.md"
        props, body = read_notes(root)[path]
        self.assertEqual(props["revision"], int(row["revision_count"]))
        self.assertIn("large-v3", body)
        self.assertNotIn("hf_secret", body)
        app.publish_input_vault(app.library_row("content"))
        self.assertIn("Whisper文字起こし", read_notes(root)[path][1])


if __name__ == "__main__":
    unittest.main()
