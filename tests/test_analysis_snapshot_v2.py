import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_pipeline import measure_segments
from gurumoji.analysis_plan_advisor import planning_context
from gurumoji.analysis_store import digest
from gurumoji.services import group_analysis
from gurumoji import research_analysis
from gurumoji.services.analysis_pipeline_adapters import (
    SNAPSHOT_V2_SECTIONS, run_analysis_pipeline_method, validate_pipeline_snapshot,
)


class SnapshotV2Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.data = json.loads((Path(__file__).parent / "fixtures/analysis_three_conversations.json").read_text(encoding="utf-8"))

    def test_three_conversation_method_measurement_adviser_and_saved_identity_parity(self):
        for conversation in self.data["conversations"]:
            source = conversation["analysis"]
            item_id = source["item"]["id"]
            app.upsert_library_item(item_id=item_id, source_name=item_id, output_dir=Path(self.fixture.temp.name) / item_id,
                                    media_path=None, language="ja", segments=source["segments"],
                                    speaker_names={}, files=[], outline=None, emotion_analysis=None,
                                    write_srt=False, write_json=True)
            row = app.library_row(item_id)
            with patch.object(group_analysis, "utc_now_iso", return_value="2026-10-12T00:00:00Z"):
                old = app.build_analysis_pipeline_snapshot(row, schema_version=1)
                new = app.build_analysis_pipeline_snapshot(row)
            with self.subTest(item=item_id):
                self.assertEqual(new["schema_version"], 2)
                validate_pipeline_snapshot(new)
                for method in ("participation", "conversation_dynamics"):
                    with patch.object(research_analysis, "build_research_analysis", side_effect=AssertionError("unrelated research recalculation")):
                        self.assertEqual(run_analysis_pipeline_method(method, old), run_analysis_pipeline_method(method, new))
                definitions = [self.data["definitions"][key] for key in conversation["definition_refs"]]
                self.assertEqual(measure_segments(old["analysis"], definitions), measure_segments(new["analysis"], definitions))
                self.assertEqual(planning_context(old["analysis"], "窓口の改善"), planning_context(new["analysis"], "窓口の改善"))
                self.assertEqual(old["archive_snapshot"], new["archive_snapshot"])
                self.assertEqual(old["analysis"]["segment_classification"], new["analysis"]["segment_classification"])
                self.assertEqual(old["analysis"]["transformer"], new["analysis"]["transformer"])
                self.assertNotIn("morphemes", new["analysis"]["research"]["linguistics"])
                self.assertNotIn("dependencies", new["analysis"]["research"]["linguistics"])
                self.assertLess(len(json.dumps(new)), len(json.dumps(old)))
                store = app.analysis_archive_store()
                kwargs = dict(item_id=item_id, kind="milestone_analysis", result={"algorithms": {"automatic": new["analysis"]["algorithm_version"]}, "parameters": {}},
                              datasets={}, input_fingerprint=new["input_hash"], source_revision=new["source_revision"],
                              analysis_revision=new["analysis_revision"], publish=False)
                first = store.save(snapshot=old["archive_snapshot"], request_id="synthetic-v1-" + item_id, **kwargs)
                # Compare snapshot versions within one save request; inference runs have separate identities.
                second = store.save(snapshot=new["archive_snapshot"], request_id="synthetic-v1-" + item_id, **kwargs)
                self.assertEqual(first["snapshot_id"], second["snapshot_id"])
                self.assertEqual(first["fingerprint"], second["fingerprint"])
                self.assertEqual(first["snapshot_id"], digest({**new["archive_snapshot"], "library_id": store.library_id()}))

    def test_incomplete_or_tampered_v2_rejected_before_accepting_request(self):
        row = app.library_row("content")
        valid = app.build_analysis_pipeline_snapshot(row)
        service = app.analysis_pipeline_service()
        service._schedule = lambda *_: None
        for section in SNAPSHOT_V2_SECTIONS:
            invalid = copy.deepcopy(valid)
            parent = invalid["analysis"]
            parts = section.split(".")
            for part in parts[:-1]:
                parent = parent[part]
            parent.pop(parts[-1])
            invalid["analysis_hash"] = fingerprint(invalid["analysis"])
            with self.subTest(section=section), patch.object(service, "snapshot_builder", return_value=invalid):
                with self.assertRaises(AnalysisContractError) as caught:
                    service.start("content", {"request_id": "invalid-snapshot-request-001", "source_revision": row["revision_count"],
                                               "analysis_revision": row["analysis_revision"], "definition_ids": []}, app_url="http://synthetic.invalid")
                self.assertEqual(caught.exception.code, "invalid_snapshot")
        altered = copy.deepcopy(valid)
        altered["analysis"]["segments"][0]["text"] = "tampered"
        with self.assertRaises(AnalysisContractError):
            validate_pipeline_snapshot(altered)
        with app.database_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_pipeline_requests").fetchone()[0], 0)

    def test_legacy_inline_snapshot_executes_and_orchestration_stays_v1(self):
        row = app.library_row("content")
        legacy = app.build_analysis_pipeline_snapshot(row, schema_version=1)
        self.assertIs(validate_pipeline_snapshot(legacy), legacy)
        self.assertEqual(app.build_analysis_orchestration_snapshot(row)["schema_version"], 1)
        service = app.analysis_pipeline_service()
        service._schedule = lambda *_: None
        with patch.object(service, "snapshot_builder", return_value=legacy):
            run, code = service.start("content", {"request_id": "legacy-snapshot-request-001", "source_revision": row["revision_count"],
                                                   "analysis_revision": row["analysis_revision"], "definition_ids": [], "publication_targets": []},
                                      app_url="http://synthetic.invalid")
        self.assertEqual(code, 202)
        service._run(run["pipeline_id"], "http://synthetic.invalid")
        self.assertEqual(service.status("content", run["pipeline_id"], ensure_running=False)["status"], "completed")
