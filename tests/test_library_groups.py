import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class LibraryGroupApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-library-groups-")
        self.addCleanup(self.temp.cleanup)
        self.database_patch = patch.object(
            app, "DATABASE_FILE", Path(self.temp.name) / "library.sqlite3"
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        app.initialize_library()
        self.client = app.app.test_client()
        for item_id, name in (("alpha", "A会議"), ("beta", "B会議"), ("gamma", "C会議")):
            app.upsert_library_item(
                item_id=item_id,
                source_name=name,
                output_dir=Path(self.temp.name) / item_id,
                media_path=None,
                language="ja",
                segments=[],
                speaker_names={},
                outline=None,
                emotion_analysis=None,
                files=[],
                write_srt=False,
                write_json=True,
            )

    def create_group(self, name):
        response = self.client.post("/api/library/groups", json={"name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def assign(self, item_id, group_id):
        response = self.client.put(
            f"/api/library/{item_id}/group", json={"group_id": group_id}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_list_matches_the_item_view_and_parses_each_transcript_once(self):
        # PERF-01: the list reuses its parsed utterances and never derives utterance IDs.
        segments = [
            {"speaker": "SPEAKER_01", "start": 0, "end": 2.5, "text": "議題を始めます",
             "emotions": {"kushinada": {"label_ja": "中立"}}},
            "壊れた行",
            {"speaker": "SPEAKER_00", "start": 3, "end": 7.25, "text": "賛成です"},
        ]
        app.upsert_library_item(
            item_id="delta", source_name="D会議", output_dir=Path(self.temp.name) / "delta",
            media_path=None, language="ja", segments=segments, speaker_names={"SPEAKER_01": "司会"},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True)
        from gurumoji.services import library_rows
        with patch.object(library_rows, "ensure_segment_ids", wraps=library_rows.ensure_segment_ids) as ids:
            listed = self.client.get("/api/library?keyword=議題").get_json()
        ids.assert_not_called()
        self.assertEqual([item["id"] for item in listed["items"]], ["delta"])
        entry = listed["items"][0]
        expected = app.library_public(app.library_row("delta"), full=False, match_count=1, group_name="")
        self.assertEqual(entry, expected)
        self.assertEqual((entry["segment_count"], entry["duration"], entry["speakers"], entry["emotions"]),
                         (2, 7.25, ["司会", "話者 1"], ["中立"]))

    def test_groups_can_be_created_assigned_filtered_and_sorted(self):
        research = self.create_group("調査A")
        meetings = self.create_group("会議")
        self.assign("alpha", meetings["id"])
        self.assign("beta", research["id"])

        catalog = self.client.get("/api/library?sort=group").get_json()
        self.assertEqual(
            [item["id"] for item in catalog["items"]],
            ["alpha", "beta", "gamma"],
        )
        self.assertEqual(
            {group["name"]: group["item_count"] for group in catalog["groups"]},
            {"会議": 1, "調査A": 1},
        )
        filtered = self.client.get(
            "/api/library", query_string={"group": research["id"]}
        ).get_json()
        self.assertEqual([item["id"] for item in filtered["items"]], ["beta"])
        ungrouped = self.client.get(
            "/api/library", query_string={"group": "__ungrouped__"}
        ).get_json()
        self.assertEqual([item["id"] for item in ungrouped["items"]], ["gamma"])

    def test_group_changes_do_not_change_transcript_revision(self):
        group = self.create_group("年度別")
        before = self.client.get("/api/library/alpha").get_json()
        assigned = self.assign("alpha", group["id"])
        after = self.client.get("/api/library/alpha").get_json()

        self.assertEqual(assigned["group_name"], "年度別")
        self.assertEqual(after["group_id"], group["id"])
        self.assertEqual(after["revision_count"], before["revision_count"])

    def test_groups_can_be_renamed_and_delete_only_unassigns_items(self):
        group = self.create_group("仮グループ")
        self.assign("alpha", group["id"])
        renamed = self.client.put(
            f"/api/library/groups/{group['id']}", json={"name": "確定グループ"}
        )
        self.assertEqual(renamed.status_code, 200, renamed.get_json())
        self.assertEqual(renamed.get_json()["name"], "確定グループ")

        deleted = self.client.delete(f"/api/library/groups/{group['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertEqual(deleted.get_json()["unassigned_count"], 1)
        item = self.client.get("/api/library/alpha").get_json()
        self.assertEqual(item["group_id"], "")
        self.assertEqual(item["group_name"], "")

    def test_group_names_are_required_and_case_insensitively_unique(self):
        self.create_group("Team")
        duplicate = self.client.post("/api/library/groups", json={"name": "team"})
        self.assertEqual(duplicate.status_code, 409)
        missing = self.client.post("/api/library/groups", json={"name": "  "})
        self.assertEqual(missing.status_code, 400)
        missing_group = self.client.put(
            "/api/library/alpha/group", json={"group_id": "missing"}
        )
        self.assertEqual(missing_group.status_code, 404)


if __name__ == "__main__":
    unittest.main()
