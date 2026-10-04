"""Deterministic regression coverage for A02–A05 and A10–A13; no model/API calls."""
import copy
import csv
import io
import json
import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import app
import transformer_analysis as subject
import test_transformer_analysis as support


def run(analysis=None, vectors=None, **kwargs):
    source, morphemes, embeddings = support.fixture()
    return subject.analyze_transformer_topics(
        analysis or source, morphemes, embeddings=embeddings if vectors is None else vectors,
        model_name="fixture", engine={"name": "fixture", "revision": "fixture-revision", "dimensions": 3},
        **kwargs,
    )


class TransformerScientificContractTests(unittest.TestCase):
    def test_a02_negative_quoted_third_party_and_conditional_cues_are_not_positive_outcomes(self):
        cases = {
            "考えは変わっていません。": {"opinion_maintained"},
            "この案に賛成できません。": set(),
            "新しい見方は得られなかった。": set(),
            "彼は『初めて知った』と言いました。": set(),
            "彼は初めて知った。": set(),
            "意見が変わるとは思わない。": set(),
            "意見が変わりましたか？": set(),
            "もし意見が変わったら知らせます。": set(),
            "初めて知ったわけではない。": set(),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                values = subject._detect_speaker_results(text)
                self.assertEqual({row["result_code"] for row in values}, expected)
                self.assertTrue(all(row["confidence"] == "unverified_candidate" for row in values))

    def test_a02_positive_cues_remain_unreviewed_and_conflicting_cues_are_ambiguous(self):
        for text in ("考えが変わりました。", "新しい見方を得ました。", "この案に賛成です。"):
            with self.subTest(text=text):
                values = subject._detect_speaker_results(text)
                self.assertTrue(values)
                self.assertTrue(all(row["confidence"] == "unverified_candidate" for row in values))
                self.assertTrue(all("候補" in row["result_label"] for row in values))
        values = subject._detect_speaker_results("考えが変わりました。考えは変わらない。")
        self.assertEqual({row["result_code"] for row in values}, {"outcome_ambiguous"})
        analysis, _, _ = support.fixture()
        analysis["segments"][0]["text"] = "考えが変わりました。"
        result = run(analysis)
        candidate = next(row for row in result["speaker_results"] if row["speaker"] == "A")
        self.assertEqual(candidate["review_status"], "unreviewed")
        self.assertTrue(candidate["researcher_review_required"])
        self.assertEqual(candidate["evidence_segment_ids"], ["s1"])

    def test_a03_active_registered_participant_is_included_but_registered_facilitator_is_not(self):
        analysis, _, _ = support.fixture()
        for row in analysis["segments"]:
            row["end"] = row["start"] + (30 if row["speaker"] == "A" else 10)
            row["role_source"] = "preparation"
        analysis["segments"][0]["text"] = "考えが変わりました。"
        result = run(analysis)
        self.assertEqual(result["quality"]["dominant_speaker"], "A")
        self.assertEqual(result["quality"]["dominant_speaker_percent"], 60)
        self.assertTrue(all(row["speaker_group"] == "participant" for row in result["assignments"]))
        self.assertEqual(sum(row["participant_segment_count"] for row in result["topics"]), 6)
        self.assertTrue(any(row["speaker"] == "A" and row["confidence"] == "unverified_candidate"
                            for row in result["speaker_results"]))
        self.assertEqual({row["speaker"] for row in result["backchannel_rates"]
                          if row["scope"] == "overall" and row["speaker_group"] == "participant"}, {"A", "B", "C"})
        for row in analysis["segments"]:
            if row["speaker"] == "A":
                row["role"] = "moderator"
        facilitator = next(row for row in run(analysis)["speaker_results"] if row["speaker"] == "A")
        self.assertEqual(facilitator["result_code"], "not_applicable")
        self.assertEqual(facilitator["role_source"], "preparation")
        self.assertEqual(subject._speaker_group({"speaker": "A"}, "A"), "participant")

    def test_a04_result_settings_change_staleness_without_discarding_embeddings(self):
        analysis, _, _ = support.fixture()
        result = run(analysis)
        self.assertEqual(result["fingerprint"], subject.transformer_input_fingerprint(
            analysis, model="fixture", parameters=result["parameters"]))
        for key, value in (("time_bin_seconds", 300), ("stop_words", ["価格"]),
                           ("transformer_topics", [{"label": "別のテーマ", "cues": ["予算"]}])):
            with self.subTest(key=key):
                changed = copy.deepcopy(analysis)
                changed["config"][key] = value
                self.assertNotEqual(result["fingerprint"], subject.transformer_input_fingerprint(
                    changed, model="fixture", parameters=result["parameters"]))
                self.assertIsNotNone(subject.saved_embeddings(result, changed, model="fixture"))
        changed_parameters = {**result["parameters"], "topic_count": 2}
        self.assertNotEqual(result["fingerprint"], subject.transformer_input_fingerprint(
            analysis, model="fixture", parameters=changed_parameters))
        changed = copy.deepcopy(analysis)
        changed["segments"][0]["text"] += "変更"
        self.assertIsNone(subject.saved_embeddings(result, changed, model="fixture"))

    def test_a10_duration_is_allocated_by_overlap_and_counts_by_start(self):
        analysis, _, _ = support.fixture()
        analysis["segments"] = analysis["segments"][:2]
        analysis["segments"][0].update(start=50, end=80)
        analysis["segments"][1].update(start=90, end=100)
        result = run(analysis, np.array([[1., 0, 0], [1., .1, 0]]))
        self.assertEqual([row["speaking_seconds"] for row in result["timeline"]], [10, 30])
        self.assertEqual([row["segment_count"] for row in result["timeline"]], [1, 1])
        self.assertEqual([row["end"] for row in result["timeline"]], [60, 100])
        self.assertEqual(sum(row["speaking_seconds"] for row in result["timeline"]), 40)
        self.assertEqual(result["parameters"]["timeline_duration_unit"], "interval_overlap")

    def test_a12_unpinned_legacy_cache_is_not_reused_and_revisions_are_reconciled(self):
        analysis, _, _ = support.fixture()
        result = run(analysis)
        legacy = copy.deepcopy(result)
        legacy["engine"].pop("revision")
        self.assertIsNone(subject.saved_embeddings(legacy, analysis, model="fixture"))
        with patch.object(subject, "encode_texts", return_value=(
                np.array([[1., 0, 0], [0, 1., 0]]), {"name": "fixture", "revision": "different-revision"})) as encode:
            with self.assertRaisesRegex(ValueError, "revision"):
                run(analysis, mode="manual", manual_topics=[{"label": "価格"}, {"label": "操作"}])
            self.assertEqual(encode.call_args.kwargs["revision"], "fixture-revision")
        with patch.object(subject, "encode_texts", return_value=(
                np.array([[1., 0, 0]]), {"name": "fixture", "revision": "different-revision"})):
            with self.assertRaisesRegex(ValueError, "revision"):
                subject.semantic_search(result, "価格")

    def test_a13_fixed_count_must_match_actual_and_invalid_candidates_remain_visible(self):
        vectors = np.array([[1., 0, 0]] * 3 + [[0, 1., 0]] * 3)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaisesRegex(ValueError, "テーマ数"):
                run(vectors=vectors, topic_count=3, max_topics=3)
            valid = run(vectors=vectors, topic_count=2, max_topics=3)
        self.assertEqual(valid["coverage"]["topic_count"], 2)
        self.assertEqual(valid["quality"]["topic_count_status"], "satisfied")
        invalid = next(row for row in valid["quality"]["cluster_candidates"] if row["topic_count"] == 3)
        self.assertEqual(invalid["status"], "invalid_topic_count")
        self.assertEqual(invalid["actual_topic_count"], 2)
        self.assertIsNone(invalid["silhouette_cosine"])


class CharacterTokenizer:
    """One character per token; no external tokenizer or model is used."""
    truncation_side = "right"

    def __call__(self, texts, *, padding, truncation, max_length=None, return_tensors=None,
                 return_offsets_mapping=False):
        import torch
        sizes = [min(len(text), max_length) if truncation else len(text) for text in texts]
        if return_tensors != "pt":
            return {"input_ids": [[1] * size for size in sizes]}
        width = max(sizes)
        mask = torch.tensor([[1] * size + [0] * (width - size) for size in sizes])
        result = {"input_ids": mask, "attention_mask": mask}
        if return_offsets_mapping:
            result["offset_mapping"] = torch.tensor([
                [[index, index + 1] for index in range(size)] + [[0, 0]] * (width - size)
                for size in sizes])
        return result


class ConstantModel:
    config = SimpleNamespace(_commit_hash="fixture-revision")

    def __call__(self, **inputs):
        import torch
        batch, width = inputs["input_ids"].shape
        return SimpleNamespace(last_hidden_state=torch.ones((batch, width, 3)))


class TransformerTruncationTests(unittest.TestCase):
    def test_a11_measures_token_cutoff_and_target_lost_behind_context(self):
        analysis, _, _ = support.fixture()
        analysis["segments"] = analysis["segments"][:2]
        analysis["segments"][0].update(text="内容" * 600, start=0, end=10, speaker="A")
        analysis["segments"][1].update(text="新しい視点を得ました。", start=11, end=20, speaker="A")
        with patch.object(subject, "_load_model", return_value=(CharacterTokenizer(), ConstantModel(), "cpu")):
            result = subject.analyze_transformer_topics(analysis, [], model_name="fixture")
        coverage = result["coverage"]
        self.assertEqual(coverage["character_truncated_segment_count"], 0)
        self.assertEqual(coverage["token_truncated_segment_count"], 2)
        self.assertEqual(coverage["truncated_segment_ids"], ["s1", "s2"])
        self.assertEqual(coverage["token_measurement_status"], "measured")
        long, target = result["input_manifest"]
        self.assertGreater(long["token_count_after_character_limit"], 512)
        self.assertEqual(long["used_token_count"], 512)
        self.assertEqual(long["retained_character_end"], 512 - len("passage: "))
        self.assertEqual(target["context_segment_ids"], ["s1", "s2"])
        self.assertEqual(target["target_character_start"], 1201)
        self.assertEqual(target["target_retention_status"], "omitted")
        self.assertEqual(long["target_retention_status"], "partially_retained")
        self.assertEqual(subject.transformer_csv_sources(result)["transformer_input_coverage"], result["input_manifest"])

    def test_a11_slow_tokenizer_reports_token_loss_without_inventing_character_range(self):
        class SlowTokenizer(CharacterTokenizer):
            def __call__(self, texts, *, return_offsets_mapping=False, **kwargs):
                if return_offsets_mapping:
                    raise NotImplementedError("offset mapping unavailable")
                return super().__call__(texts, **kwargs)
        analysis, _, _ = support.fixture()
        analysis["segments"] = analysis["segments"][:2]
        analysis["segments"][0]["text"] = "内容" * 600
        with patch.object(subject, "_load_model", return_value=(SlowTokenizer(), ConstantModel(), "cpu")):
            result = subject.analyze_transformer_topics(analysis, [], model_name="fixture")
        self.assertEqual(result["coverage"]["token_truncated_segment_count"], 1)
        entry = result["input_manifest"][0]
        self.assertEqual(entry["retained_range_status"], "unavailable")
        self.assertIsNone(entry["retained_character_end"])
        self.assertEqual(entry["target_retention_status"], "unknown")

    def test_a11_character_cap_and_unknown_measurement_are_not_false_zero(self):
        analysis, _, _ = support.fixture()
        analysis["segments"][0]["text"] = "内容" * 3100
        injected = run(analysis)
        self.assertEqual(injected["coverage"]["character_truncated_segment_ids"], ["s1"])
        self.assertIsNone(injected["coverage"]["token_truncated_segment_count"])
        self.assertIsNone(injected["coverage"]["truncated_segment_count"])
        self.assertEqual(injected["coverage"]["token_measurement_status"], "unavailable")


class TransformerExportProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.TransformerApiTests("test_worker_persists_result_and_exports_csv")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client, self.url = self.fixture.client, self.fixture.url

    def store_result(self, legacy=False):
        analysis = app.group_analysis_for_row(app.library_row("transformer"), include_research_rows=True)
        result = run(analysis)
        result.update(generated_at="2000-01-01T00:00:00Z", source_revision=1, analysis_revision=1)
        if legacy:
            result.pop("source_provenance")
        else:
            result["source_provenance"].update(source_revision=1, analysis_revision=1,
                source_hash="old-input-hash", input_version=1, analysis_needs_review=False)
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET transformer_analysis_json=?, revision_count=2, analysis_revision=2 WHERE id='transformer'",
                               (json.dumps(result, ensure_ascii=False),))
        return result

    def test_a05_csv_json_and_workbook_preserve_generation_identity_and_stale(self):
        self.store_result()
        response = self.client.get(self.url + "/export.csv?dataset=transformer_topics")
        self.assertEqual(response.status_code, 200)
        row = next(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
        self.assertEqual(row["revision_count"], "1")
        self.assertEqual(row["input_version"], "1")
        self.assertEqual(row["source_hash"], "old-input-hash")
        self.assertEqual(row["current_revision_count"], "2")
        self.assertNotEqual(row["current_source_hash"], row["source_hash"])
        self.assertEqual(row["result_stale"], "1")
        self.assertEqual(row["analysis_needs_review"], "1")
        self.assertEqual(row["provenance_status"], "recorded")
        self.assertEqual(row["interpretation_status"], "unverified_candidate")
        response = self.client.get(self.url + "/export.json")
        self.assertEqual(response.status_code, 200)
        exported = response.get_json()
        self.assertTrue(exported["transformer"]["stale"])
        self.assertEqual(exported["transformer"]["result"]["source_provenance"]["source_hash"], "old-input-hash")
        response = self.client.get(self.url + "/export.xlsx")
        self.assertEqual(response.status_code, 200)
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(response.data), read_only=True)
        found = False
        for sheet in workbook:
            rows = list(sheet.values)
            if rows and "source_hash" in rows[0] and "topic_id" in rows[0] and "label" in rows[0]:
                values = dict(zip(rows[0], rows[1]))
                self.assertEqual(values["source_hash"], "old-input-hash")
                self.assertTrue(values["result_stale"])
                self.assertEqual(values["revision_count"], 1)
                found = True
        self.assertTrue(found)
        workbook.close()

    def test_a05_legacy_missing_hash_does_not_inherit_current_input(self):
        self.store_result(legacy=True)
        response = self.client.get(self.url + "/export.csv?dataset=transformer_topics")
        row = next(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
        self.assertEqual(row["revision_count"], "1")
        self.assertEqual(row["source_hash"], "")
        self.assertEqual(row["input_version"], "")
        self.assertEqual(row["generated_at"], "2000-01-01T00:00:00Z")
        self.assertEqual(row["provenance_status"], "legacy_unknown")
        self.assertEqual(row["result_stale"], "1")

    def test_a12_manual_job_reuses_vectors_and_requests_their_exact_revision(self):
        self.fixture.save_manual_topics([{"label": "価格"}, {"label": "操作"}])
        analysis = app.group_analysis_for_row(app.library_row("transformer"), include_research_rows=True)
        saved = subject.analyze_transformer_topics(
            analysis, self.fixture.morphemes, embeddings=self.fixture.embeddings,
            engine={"name": subject.DEFAULT_MODEL, "revision": "pinned-old-revision"})
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET transformer_analysis_json=? WHERE id='transformer'",
                               (json.dumps(saved),))
        with patch.object(app.threading, "Thread") as thread:
            response = self.client.post(self.url + "/transformer", json={
                **self.fixture.payload("transformer-pinned-cache-job"), "mode": "manual"})
            args, kwargs = thread.call_args.kwargs["args"], thread.call_args.kwargs["kwargs"]
        self.assertEqual(response.status_code, 202)
        with patch.object(app, "build_research_analysis", return_value={"linguistics": {"morphemes": self.fixture.morphemes}}), \
             patch.object(subject, "encode_texts", return_value=(np.array([[1., 0, 0], [0, 1., 0]]),
                 {"name": subject.DEFAULT_MODEL, "revision": "pinned-old-revision"})) as encode, \
             patch.object(app, "archive_group_analysis", return_value={"id": "synthetic", "vault_status": "saved"}):
            app.run_transformer_analysis_job(*args, **kwargs)
        self.assertEqual(encode.call_count, 1)
        self.assertEqual(encode.call_args.kwargs["kind"], "query")
        self.assertEqual(encode.call_args.kwargs["revision"], "pinned-old-revision")
        status = self.client.get(self.url + "/transformer").get_json()
        self.assertEqual(status["run"]["status"], "completed", status["run"]["message"])
        self.assertTrue(status["transformer"]["result"]["coverage"]["reused_embeddings"])

    def test_a04_settings_save_marks_result_stale_and_blocks_semantic_search(self):
        analysis = app.group_analysis_for_row(app.library_row("transformer"), include_research_rows=True)
        result = subject.analyze_transformer_topics(
            analysis, self.fixture.morphemes, embeddings=self.fixture.embeddings,
            engine={"name": subject.DEFAULT_MODEL, "revision": "fixture-revision"})
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET transformer_analysis_json=? WHERE id='transformer'",
                               (json.dumps(result),))
        before = self.client.get(self.url).get_json()
        self.assertFalse(before["transformer"]["stale"])
        response = self.client.put(self.url, json={
            "source_revision": before["item"]["revision_count"],
            "analysis_revision": before["item"]["analysis_revision"],
            "config": {**before["config"], "time_bin_seconds": 60 if before["config"]["time_bin_seconds"] != 60 else 300},
            "annotations": {},
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["transformer"]["stale"])
        self.assertEqual(self.client.get(self.url + "/semantic-search?q=価格").status_code, 409)


if __name__ == "__main__":
    unittest.main()
