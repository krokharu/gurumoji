import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import app
import transformer_analysis as subject


def fixture():
    texts = [
        ("s1", "A", "価格が高く導入しにくい", 0, 3),
        ("s2", "B", "料金が高いので予算に合わない", 4, 7),
        ("s3", "A", "画面の操作を簡単にしてほしい", 8, 11),
        ("s4", "B", "操作方法が分かりにくかった", 12, 15),
        ("s5", "C", "研修資料は紙で配ってほしい", 16, 19),
        ("s6", "C", "紙の説明書があると安心する", 20, 23),
    ]
    segments = [{"id": sid, "speaker": speaker, "speaker_name": f"参加者{speaker}",
                 "role": "participant", "text": text, "start": start, "end": end,
                 "excluded": False, "annotation": {}}
                for sid, speaker, text, start, end in texts]
    morphemes = []
    terms = {"s1": ["価格", "導入"], "s2": ["価格", "予算"],
             "s3": ["操作", "画面"], "s4": ["操作", "方法"],
             "s5": ["紙", "資料"], "s6": ["紙", "説明書"]}
    for sid, values in terms.items():
        for value in values:
            morphemes.append({"segment_id": sid, "normalized": value,
                              "is_content": True, "is_stop": False, "excluded": False})
    analysis = {"item": {"id": "transformer", "revision_count": 0, "analysis_revision": 0},
                "config": {"time_bin_seconds": 60}, "segments": segments}
    embeddings = np.asarray([
        [1, .02, 0], [.99, .05, 0], [0, 1, .02], [.03, .99, 0],
        [0, .02, 1], [.02, 0, .99],
    ], dtype="float32")
    return analysis, morphemes, embeddings


class TransformerAnalysisTests(unittest.TestCase):
    def test_topics_are_evidence_linked_and_searchable(self):
        analysis, morphemes, embeddings = fixture()
        result = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=embeddings,
            engine={"name": "fixture", "dimensions": 3}, max_topics=3, min_topic_size=2,
        )
        self.assertEqual(result["coverage"]["segment_count"], 6)
        self.assertEqual(result["coverage"]["topic_count"], 3)
        self.assertEqual({row["segment_count"] for row in result["topics"]}, {2})
        self.assertEqual(set(result["evidence"]), {f"s{i}" for i in range(1, 7)})
        self.assertTrue(any("価格" in row["keywords"] for row in result["topics"]))
        self.assertEqual({row["speaker"] for row in result["speaker_results"]}, {"A", "B", "C"})
        self.assertEqual({row["result_code"] for row in result["speaker_results"]}, {"undetermined"})
        hits = subject.semantic_search(result, "価格", query_embedding=np.array([1, 0, 0]), limit=2)
        self.assertEqual({row["segment_id"] for row in hits}, {"s1", "s2"})
        self.assertGreaterEqual(hits[0]["score"], hits[1]["score"])

    def test_fingerprint_changes_with_evidence_but_not_generated_output(self):
        analysis, _, _ = fixture()
        before = subject.transformer_input_fingerprint(analysis)
        analysis["generated_at"] = "later"
        analysis["transformer"] = {"result": "ignored"}
        self.assertEqual(before, subject.transformer_input_fingerprint(analysis))
        analysis["segments"][0]["text"] += "。"
        self.assertNotEqual(before, subject.transformer_input_fingerprint(analysis))

    def test_rejects_empty_and_mismatched_vectors(self):
        analysis, morphemes, _ = fixture()
        empty = copy.deepcopy(analysis); empty["segments"] = []
        with self.assertRaises(ValueError):
            subject.analyze_transformer_topics(empty, morphemes, embeddings=np.empty((0, 3)))
        with self.assertRaises(ValueError):
            subject.analyze_transformer_topics(analysis, morphemes, embeddings=np.ones((2, 3)))

    def test_filters_backchannels_and_can_fix_topic_count(self):
        analysis, morphemes, embeddings = fixture()
        analysis["segments"].extend([
            {"id": "s7", "speaker": "A", "speaker_name": "参加者A", "role": "participant",
             "text": "はい", "start": 24, "end": 25, "excluded": False},
            {"id": "s8", "speaker": "B", "speaker_name": "参加者B", "role": "participant",
             "text": "？", "start": 26, "end": 27, "excluded": False},
        ])
        all_embeddings = np.vstack([embeddings, [[.5, .5, 0], [.5, 0, .5]]]).astype("float32")
        result = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=all_embeddings,
            engine={"name": "fixture", "dimensions": 3}, max_topics=3,
            min_topic_size=2, topic_count=2,
        )
        self.assertEqual(result["coverage"]["source_segment_count"], 8)
        self.assertEqual(result["coverage"]["segment_count"], 6)
        self.assertEqual(result["coverage"]["ignored_noise_segment_count"], 1)
        self.assertEqual(result["coverage"]["backchannel_segment_count"], 1)
        self.assertEqual(result["coverage"]["linked_backchannel_segment_count"], 1)
        self.assertEqual(result["coverage"]["topic_count"], 2)
        self.assertEqual(result["parameters"]["topic_count"], 2)
        self.assertEqual(len(result["assignments"]), 6)
        self.assertEqual(set(result["evidence"]), {f"s{i}" for i in range(1, 9)})
        self.assertEqual(result["backchannels"][0]["segment_id"], "s7")
        self.assertEqual(result["backchannels"][0]["responds_to_segment_id"], "s6")
        self.assertEqual(result["backchannels"][0]["kind"], "agreement")
        self.assertEqual(result["speaker_backchannels"][0]["speaker"], "A")
        linked_topic = result["backchannels"][0]["topic_id"]
        self.assertEqual(
            next(row for row in result["topics"] if row["topic_id"] == linked_topic)["backchannel_count"], 1
        )
        overall_rate = next(row for row in result["backchannel_rates"]
                            if row["speaker"] == "A" and row["scope"] == "overall")
        self.assertEqual(overall_rate["opportunity_count"], 4)
        self.assertEqual(overall_rate["responded_target_count"], 1)
        self.assertEqual(overall_rate["response_rate_percent"], 25.0)
        self.assertEqual(overall_rate["agreement_count"], 1)
        self.assertEqual(
            {row["test_id"] for row in result["backchannel_tests"]},
            {"response_by_speaker", "kind_by_speaker", "kind_by_topic"},
        )

    def test_backchannel_chi_square_reports_effect_size_and_sparse_cells(self):
        computed = subject._backchannel_test(
            "fixture", "fixture", "speaker x response",
            [[8, 12], [3, 17]], ["A", "B"], ["yes", "no"],
        )
        self.assertIn(computed["status"], {"computed", "computed_sparse"})
        self.assertIsNotNone(computed["p_value"])
        self.assertIsNotNone(computed["effect_size"])
        self.assertEqual(computed["effect_name"], "cramers_v")
        sparse = subject._backchannel_test(
            "sparse", "sparse", "speaker x response",
            [[1, 99], [0, 100]], ["A", "B"], ["yes", "no"],
        )
        self.assertEqual(sparse["status"], "computed_sparse")
        self.assertIn("p値から差を判定しません", sparse["interpretation"])

    def test_speaker_results_require_explicit_language_and_keep_topic_evidence(self):
        analysis, morphemes, embeddings = fixture()
        replacements = {
            "s1": "最初は反対でしたが、今は考えが変わりました。こちらがいいと思います",
            "s2": "意見は変わらないです。やっぱり価格がいいと思います",
            "s5": "皆さんの話から新しい視点を得ました",
        }
        for row in analysis["segments"]:
            if row["id"] in replacements:
                row["text"] = replacements[row["id"]]
        result = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=embeddings,
            engine={"name": "fixture", "dimensions": 3}, max_topics=3, min_topic_size=2,
        )
        by_speaker = {}
        for row in result["speaker_results"]:
            by_speaker.setdefault(row["speaker"], []).append(row)
        self.assertEqual(
            {row["result_code"] for row in by_speaker["A"]},
            {"opinion_changed", "preference_formed"},
        )
        self.assertEqual(
            {row["result_code"] for row in by_speaker["B"]},
            {"opinion_maintained", "preference_formed"},
        )
        self.assertEqual({row["result_code"] for row in by_speaker["C"]}, {"new_insight"})
        explicit_rows = [row for rows in by_speaker.values() for row in rows]
        self.assertTrue(all(row["topic_id"] for row in explicit_rows))
        self.assertTrue(all(row["evidence_segment_ids"] for row in explicit_rows))
        self.assertEqual(result["coverage"]["explicit_speaker_result_count"], 3)

    def test_semantic_search_skips_noise_in_legacy_saved_result(self):
        analysis, morphemes, embeddings = fixture()
        result = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=embeddings,
            engine={"name": "fixture", "dimensions": 3}, max_topics=3, min_topic_size=2,
        )
        result["assignments"][0]["text"] = "？"
        hits = subject.semantic_search(
            result, "価格", query_embedding=np.array([1, 0, 0]), limit=2,
        )
        self.assertNotEqual(hits[0]["segment_id"], "s1")

    def test_candidate_mode_keeps_the_whole_candidate_list(self):
        analysis, morphemes, embeddings = fixture()
        result = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=embeddings,
            engine={"name": "fixture", "dimensions": 3}, max_topics=3, min_topic_size=2,
            mode="candidate", topic_count=2,
        )
        self.assertEqual(result["parameters"]["mode"], "candidate")
        self.assertEqual(result["coverage"]["topic_count"], 2)
        self.assertEqual(
            {row["topic_count"] for row in result["quality"]["cluster_candidates"]}, {2, 3}
        )
        self.assertTrue(all(row["origin"] == "kmeans" for row in result["topics"]))

    def test_manual_mode_assigns_to_researcher_themes(self):
        analysis, morphemes, embeddings = fixture()
        manual_topics = [
            {"id": "topic_price", "label": "価格の話", "cues": ["価格", "料金"], "seed_segment_ids": ["s1"]},
            {"id": "topic_ui", "label": "操作の話", "cues": ["操作"], "seed_segment_ids": []},
        ]

        def fake_encode(texts, **kwargs):
            vectors = np.asarray([[1, 0, 0], [0, 1, 0]][:len(texts)], dtype="float32")
            return vectors, {"name": "fixture", "dimensions": 3, "device": "cpu"}

        with patch.object(subject, "encode_texts", side_effect=fake_encode):
            result = subject.analyze_transformer_topics(
                analysis, morphemes, embeddings=embeddings,
                engine={"name": "fixture", "dimensions": 3}, mode="manual",
                manual_topics=manual_topics, manual_min_similarity=0.5,
            )
        self.assertEqual(result["parameters"]["mode"], "manual")
        self.assertEqual(result["parameters"]["manual_min_similarity"], 0.5)
        self.assertEqual([row["label"] for row in result["topics"]], ["価格の話", "操作の話"])
        self.assertTrue(all(row["origin"] == "manual" for row in result["topics"]))
        self.assertEqual(result["topics"][0]["keywords"], ["価格", "料金"])
        self.assertEqual(result["topics"][0]["seed_segment_count"], 1)
        assigned = {row["segment_id"]: row["topic_label"] for row in result["assignments"]}
        self.assertEqual(assigned["s1"], "価格の話")
        self.assertEqual(assigned["s2"], "価格の話")
        self.assertEqual(assigned["s3"], "操作の話")
        self.assertEqual(assigned["s4"], "操作の話")
        # The two utterances about paper handouts match neither theme above the cut-off.
        self.assertEqual(assigned["s5"], "どのテーマにも近くない")
        self.assertEqual(result["coverage"]["unassigned_segment_count"], 2)
        self.assertTrue(any("しきい値" in line for line in result["limitations"]))

    def test_manual_mode_rejects_a_theme_without_cue_or_seed(self):
        analysis, morphemes, embeddings = fixture()
        with self.assertRaises(ValueError):
            subject.analyze_transformer_topics(
                analysis, morphemes, embeddings=embeddings,
                engine={"name": "fixture", "dimensions": 3}, mode="manual",
                manual_topics=[{"label": "空のテーマ"}],
            )

    def test_saved_vectors_are_reused_only_for_the_same_input(self):
        analysis, morphemes, embeddings = fixture()
        result = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=embeddings, model_name="fixture",
            engine={"name": "fixture", "dimensions": 3}, max_topics=3, min_topic_size=2,
        )
        reuse = subject.saved_embeddings(result, analysis, model="fixture")
        self.assertIsNotNone(reuse)
        vectors, segment_ids, engine = reuse
        self.assertEqual(segment_ids, [f"s{i}" for i in range(1, 7)])
        self.assertEqual(engine["vector_source"], "saved-int8")
        self.assertIsNone(subject.saved_embeddings(result, analysis, model="other-model"))
        changed = copy.deepcopy(analysis)
        changed["segments"][0]["text"] += "。"
        self.assertIsNone(subject.saved_embeddings(result, changed, model="fixture"))
        reused = subject.analyze_transformer_topics(
            analysis, morphemes, embeddings=vectors, embedding_segment_ids=segment_ids,
            engine=engine, mode="candidate", topic_count=3, max_topics=3, min_topic_size=2,
        )
        self.assertTrue(reused["coverage"]["reused_embeddings"])
        with self.assertRaises(ValueError):
            subject.analyze_transformer_topics(
                analysis, morphemes, embeddings=vectors,
                embedding_segment_ids=["s9"] + segment_ids[1:], engine=engine,
            )

    def test_dominant_default_participant_is_reported_as_facilitator_candidate(self):
        segment = {"speaker": "moderator-like", "role": "participant"}
        self.assertEqual(
            subject._speaker_group(segment, "moderator-like"), "facilitator_candidate"
        )


class TransformerApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-transformer-")
        self.addCleanup(self.temp.cleanup)
        self.database_patch = patch.object(app, "DATABASE_FILE", Path(self.temp.name) / "library.sqlite3")
        self.database_patch.start(); self.addCleanup(self.database_patch.stop)
        app.initialize_library()
        self.client = app.app.test_client()
        analysis, self.morphemes, self.embeddings = fixture()
        app.upsert_library_item(
            item_id="transformer", source_name="group.wav", output_dir=Path(self.temp.name) / "output",
            media_path=None, language="ja", segments=analysis["segments"],
            speaker_names={"A": "参加者A", "B": "参加者B", "C": "参加者C"}, files=[],
            outline=None, emotion_analysis=None, write_srt=False, write_json=True,
        )
        self.url = "/api/library/transformer/analysis"
        self.addCleanup(app.transformer_cancel_events.clear)

    def payload(self, request_id="transformer-request-0001"):
        data = self.client.get(self.url).get_json()
        return {"request_id": request_id, "source_revision": data["item"]["revision_count"],
                "analysis_revision": data["item"]["analysis_revision"],
                "max_topics": 3, "min_topic_size": 2, "topic_count": 0}

    def test_worker_persists_result_and_exports_csv(self):
        initial = self.client.get(self.url).get_json()
        self.assertIsNone(initial["transformer"]["result"])
        with patch.object(app.threading, "Thread") as thread:
            response = self.client.post(self.url + "/transformer", json=self.payload())
            args = thread.call_args.kwargs["args"]
        self.assertEqual(response.status_code, 202)

        def fake_analyze(analysis, morphemes, **kwargs):
            return subject.analyze_transformer_topics(
                analysis, self.morphemes, embeddings=self.embeddings,
                engine={"name": kwargs["model_name"], "dimensions": 3, "device": "cpu"},
                max_topics=kwargs["max_topics"], min_topic_size=kwargs["min_topic_size"],
            )

        with patch.object(app, "build_research_analysis", return_value={"linguistics": {"morphemes": self.morphemes}}), \
             patch.object(app, "analyze_transformer_topics", side_effect=fake_analyze), \
             patch.object(app, "archive_group_analysis", return_value={"id": "archive-1", "vault_status": "saved"}):
            app.run_transformer_analysis_job(*args)

        status = self.client.get(self.url + "/transformer").get_json()
        self.assertEqual(status["run"]["status"], "completed", status)
        self.assertFalse(status["transformer"]["stale"])
        self.assertEqual(status["transformer"]["result"]["coverage"]["topic_count"], 3)
        self.assertNotIn("vectors", status["transformer"]["result"])
        with app.database_connection() as connection:
            stored = connection.execute(
                "SELECT transformer_analysis_json FROM library_items WHERE id='transformer'"
            ).fetchone()[0]
        self.assertIn('"vectors"', stored)
        exported = self.client.get(self.url + "/export.csv?dataset=transformer_topics")
        self.assertEqual(exported.status_code, 200)
        exported_lines = exported.data.decode("utf-8-sig").splitlines()
        self.assertIn("topic_id", exported_lines[0])
        self.assertIn(subject.TRANSFORMER_ANALYSIS_VERSION, exported_lines[1])
        backchannels = self.client.get(self.url + "/export.csv?dataset=transformer_backchannels")
        self.assertEqual(backchannels.status_code, 200)
        self.assertIn("responds_to_segment_id", backchannels.data.decode("utf-8-sig").splitlines()[0])
        speaker_results = self.client.get(self.url + "/export.csv?dataset=transformer_speaker_results")
        self.assertEqual(speaker_results.status_code, 200)
        self.assertIn("result_code", speaker_results.data.decode("utf-8-sig").splitlines()[0])
        rates = self.client.get(self.url + "/export.csv?dataset=transformer_backchannel_rates")
        self.assertEqual(rates.status_code, 200)
        self.assertIn("response_rate_percent", rates.data.decode("utf-8-sig").splitlines()[0])
        tests = self.client.get(self.url + "/export.csv?dataset=transformer_backchannel_tests")
        self.assertEqual(tests.status_code, 200)
        self.assertIn("effect_size", tests.data.decode("utf-8-sig").splitlines()[0])

        with patch.object(app, "transformer_semantic_search", return_value=[{"segment_id": "s1", "score": .9}]):
            search = self.client.get(self.url + "/semantic-search?q=価格").get_json()
        self.assertEqual(search["hits"][0]["segment_id"], "s1")

    def test_archive_identity_includes_transformer_parameters_and_version(self):
        row = app.library_row("transformer")
        analysis = app.group_analysis_for_row(row, include_research_rows=True)
        analysis["transformer"] = {"result": {
            "parameters": {"topic_count": 6, "speaker_balancing": True},
            "algorithm_version": "transformer-topics-test",
        }}
        with patch.object(app, "analysis_archive_store") as factory:
            factory.return_value.save.return_value = {"id": "archive"}
            app.archive_group_analysis(row, analysis, "transformer-archive-test",
                                       kind="transformer_topics")
        saved = factory.return_value.save.call_args.kwargs["result"]
        self.assertEqual(saved["parameters"]["transformer"]["topic_count"], 6)
        self.assertEqual(saved["algorithms"]["transformer"], "transformer-topics-test")

    def save_manual_topics(self, topics):
        data = self.client.get(self.url).get_json()
        response = self.client.put(self.url, json={
            "source_revision": data["item"]["revision_count"],
            "analysis_revision": data["item"]["analysis_revision"],
            "config": {**data["config"], "transformer_topics": topics},
            "annotations": {},
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_manual_mode_needs_saved_themes_and_passes_them_to_the_worker(self):
        blocked = self.client.post(self.url + "/transformer", json={
            **self.payload("transformer-manual-without-themes"), "mode": "manual"})
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("2", blocked.get_json()["error"])
        # A heading alone is a usable descriptor, so a theme without cues is accepted.
        self.save_manual_topics([
            {"label": "価格の話", "cues": ["価格", "料金"]},
            {"label": "操作の話", "cues": ["操作"], "seed_segment_ids": ["s3"]},
        ])
        with patch.object(app.threading, "Thread") as thread:
            started = self.client.post(self.url + "/transformer", json={
                **self.payload("transformer-manual-ready-request"), "mode": "manual", "min_similarity": 0.75})
            options = thread.call_args.kwargs["kwargs"]
        self.assertEqual(started.status_code, 202)
        self.assertEqual(started.get_json()["run"]["mode"], "manual")
        self.assertEqual(options["mode"], "manual")
        self.assertEqual(options["min_similarity"], 0.75)
        self.assertEqual([topic["label"] for topic in options["manual_topics"]], ["価格の話", "操作の話"])
        self.assertEqual(options["manual_topics"][1]["seed_segment_ids"], ["s3"])

    def test_manual_worker_stores_researcher_themes_and_exports_origin(self):
        self.save_manual_topics([
            {"label": "価格の話", "cues": ["価格", "料金"]},
            {"label": "操作の話", "cues": ["操作", "画面"]},
        ])
        with patch.object(app.threading, "Thread") as thread:
            response = self.client.post(self.url + "/transformer", json={
                **self.payload("transformer-manual-worker-run"), "mode": "manual"})
            args = thread.call_args.kwargs["args"]
            options = thread.call_args.kwargs["kwargs"]
        self.assertEqual(response.status_code, 202)

        def fake_encode(texts, **kwargs):
            groups = (("価格", "料金", "予算"), ("操作", "画面", "方法"), ("紙", "資料", "説明書"))
            vectors = []
            for text in texts:
                vector = [0.0, 0.0, 0.0]
                for index, words in enumerate(groups):
                    if any(word in text for word in words):
                        vector[index] = 1.0
                vectors.append(vector or [1.0, 0.0, 0.0])
            return np.asarray(vectors, dtype="float32"), {
                "name": kwargs.get("model_name", "fixture"), "dimensions": 3, "device": "cpu"}

        with patch.object(app, "build_research_analysis", return_value={"linguistics": {"morphemes": self.morphemes}}), \
             patch.object(subject, "encode_texts", side_effect=fake_encode), \
             patch.object(app, "archive_group_analysis", return_value={"id": "archive-2", "vault_status": "saved"}):
            app.run_transformer_analysis_job(*args, **options)

        status = self.client.get(self.url + "/transformer").get_json()
        self.assertEqual(status["run"]["status"], "completed", status["run"]["message"])
        result = status["transformer"]["result"]
        self.assertEqual(result["parameters"]["mode"], "manual")
        self.assertEqual([row["label"] for row in result["topics"]], ["価格の話", "操作の話"])
        self.assertEqual(
            [topic["label"] for topic in result["parameters"]["manual_topics"]], ["価格の話", "操作の話"])
        exported = self.client.get(self.url + "/export.csv?dataset=transformer_topics")
        self.assertEqual(exported.status_code, 200)
        lines = exported.data.decode("utf-8-sig").splitlines()
        self.assertIn("origin", lines[0])
        self.assertTrue(any("manual" in line for line in lines[1:]))

    def test_candidate_mode_requires_a_topic_count(self):
        missing = self.client.post(self.url + "/transformer", json={
            **self.payload("transformer-candidate-no-count"), "mode": "candidate"})
        self.assertEqual(missing.status_code, 400)
        with patch.object(app.threading, "Thread") as thread:
            started = self.client.post(self.url + "/transformer", json={
                **self.payload("transformer-candidate-ready-req"), "mode": "candidate", "topic_count": 3})
            options = thread.call_args.kwargs["kwargs"]
        self.assertEqual(started.status_code, 202)
        self.assertEqual(options["mode"], "candidate")
        self.assertEqual(started.get_json()["run"]["topic_count"], 3)

    def test_validation_duplicate_cancel_and_interrupted_state(self):
        self.assertEqual(self.client.post(self.url + "/transformer", json={}).status_code, 400)
        self.assertEqual(self.client.post(
            self.url + "/transformer", json={**self.payload("invalid-topic-count"), "topic_count": 1}
        ).status_code, 400)
        payload = self.payload()
        with patch.object(app.threading, "Thread") as thread:
            first = self.client.post(self.url + "/transformer", json=payload)
            duplicate = self.client.post(self.url + "/transformer", json=payload)
            busy = self.client.post(self.url + "/transformer", json={**payload, "request_id": "transformer-request-0002"})
        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(busy.status_code, 409)
        cancelled = self.client.post(self.url + "/transformer/cancel", json={"request_id": payload["request_id"]})
        self.assertEqual(cancelled.status_code, 200)
        app.initialize_library()
        self.assertEqual(self.client.get(self.url + "/transformer").get_json()["run"]["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
