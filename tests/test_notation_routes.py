"""Run actual in-job and workbench composition paths, with no models or Vaults."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from gurumoji.ai_effort import normalize_efforts
from gurumoji.services import notation
from test_notation import analyze
import test_notation_workflows as workflow_fixtures
import test_pipeline_regressions as pipeline_fixtures


class NotationRouteTests(unittest.TestCase):
    def test_in_job_recommended_and_full_use_same_notation_after_cleanup(self):
        fixture = pipeline_fixtures.TranscriptionJobRegressionTests()
        for mode in ("recommended", "advanced"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                job = fixture.job(root)
                seen = []
                def finish(source, *args, **kwargs):
                    seen.append(source)
                    return notation.resolve(source, notation.detect(source, terms=["AI"], analyze=analyze))
                def clean(source, *args, **kwargs):
                    return [{**s, "text": "AI ＡＩ"} for s in source]
                with fixture.fake_pipeline() as calls, patch.object(app, "unify_notation", side_effect=finish), \
                        patch.object(app, "clean_segments_with_ai", side_effect=clean), \
                        patch.object(app, "clean_recommended_segments_with_ai", side_effect=clean), \
                        patch.object(app, "review_segments_with_jev", return_value=({}, {})):
                    options = fixture.options(root, transcript_finishing_mode=mode,
                        recommended_cleanup=mode == "recommended", clean_transcript=mode == "advanced",
                        jev_compare=False, ai_efforts=normalize_efforts({"notation": "medium"}))
                    app.run_transcription_job(job, options)
                self.assertEqual(job.status, "completed", getattr(job, "error", ""))
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0][0]["text"], "AI ＡＩ")
                saved = calls["upsert"].call_args.kwargs["finishing_history"]
                recorded = next(s for s in saved if s["process"] == "notation")
                self.assertEqual(recorded["segments"][0]["text"], "AI AI")

    def test_workbench_and_shared_finisher_equal_and_apply_has_distinct_delta(self):
        fixture = workflow_fixtures.NotationWorkflowTests("test_preview_is_read_only_no_llm_and_stale_preview_rejected")
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        app.save_custom_vocabulary(["AI", "サーバー"])
        state = {"item_id": "c", "revision": 0, "ai_efforts": {"cleanup": "off", "notation": "medium"}}
        with patch.object(app, "load_token_config", return_value=app.TokenConfig()), \
                patch.object(app, "configured_ai_credentials", return_value=("", "mock")), \
                patch.object(app, "call_ai_json") as call:
            result = app.run_obsidian_finishing("finish", state, fixture.raw, {}, "lmstudio", lambda: None)
            direct = app.unify_notation(fixture.raw, "lmstudio", "", "mock", lambda: None, item_id="c")
            self.assertEqual(result["segments"], direct["segments"])
            self.assertEqual(result["notation"], direct["notation"])
            call.assert_not_called()
        context = {**result, "before": fixture.raw, "revision": 0, "run_id": "mock-obsidian"}
        with patch.object(app, "publish_input_vault"), patch.object(app, "archive_ai_finishing"):
            app.run_obsidian_finishing("apply", state, result["segments"], context, "lmstudio", lambda: None)
        with app.database_connection() as db:
            from gurumoji import transcript_preparation as h
            changes = h._changes(db, "c")
            self.assertTrue(any(c["origin"] == "ai" and c["process"] == "notation" for c in changes))
            self.assertEqual(h.read_version(db, "c", 2)["source"], h.source(app.library_row("c")))


if __name__ == "__main__":
    unittest.main()
