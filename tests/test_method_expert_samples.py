"""Fictional group-interview samples through the app: each expert accepts, warns about or refuses the data.

This is the sample verification recorded in docs/program-vault/50-Tests/method-expert-sample-verification.md.
Morphology runs on the fallback analyser here; the GiNZA path was checked separately (see that note).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import research_analysis
from gurumoji import method_experts as experts
from gurumoji import transformer_analysis

QUESTION = "家計簿アプリの記録の継続を妨げる要因と支える要因は何か"
LINES = [
    ("MOD", "今日は架空の家計簿アプリを一週間使ってみた感想を伺います。最初に使い始めたときの印象はどうでしたか？"),
    ("A", "入力画面が分かりやすくて、初日から毎日記録できました。"),
    ("B", "私は項目の分類が細かすぎて、どこに入れるか迷いました。"),
    ("C", "分類は迷いましたが、レシートの読み取りは便利でした。"),
    ("MOD", "分類で迷ったのはどんな場面でしたか？"),
    ("B", "外食と食料品の区別です。コンビニで買ったお弁当をどちらにするか決められませんでした。"),
    ("A", "それは私も同じでした。結局、外食に入れましたが自信はないです。"),
    ("C", "私は食料品に入れていました。人によって違うと比べにくいですね。"),
    ("MOD", "記録を続けるうえで役に立った機能はありますか？"),
    ("C", "通知です。夜に一度知らせてくれるので、入力を忘れませんでした。"),
    ("A", "通知は便利ですが、少し多いと感じる日もありました。"),
    ("B", "私は通知を切りました。自分のタイミングで入力したいので。"),
    ("MOD", "逆に、使いにくかった点はどこでしょうか？"),
    ("A", "グラフの画面を開くまでに何回も押す必要がありました。"),
    ("B", "グラフの色が似ていて、項目の違いが分かりにくかったです。"),
    ("C", "私はグラフをあまり見なかったので、困りませんでした。"),
    ("MOD", "一週間使ってみて、支出への意識は変わりましたか？"),
    ("B", "コンビニに寄る回数が多いと分かって、少し控えるようになりました。"),
    ("C", "意識はしましたが、行動はあまり変わっていないと思います。"),
    ("A", "記録するだけで満足してしまって、見直しはしていませんでした。"),
    ("MOD", "最後に、続けて使いたいかどうかを教えてください。"),
    ("A", "分類の説明が増えるなら続けたいです。"),
    ("C", "レシートの読み取りがあるので続けると思います。"),
    ("B", "グラフが見やすくなれば、また使ってみたいです。"),
]
NAMES = {"MOD": "司会", "A": "参加者A", "B": "参加者B", "C": "参加者C"}
PROFILE = {"session_type": "focus_group", "objective": "架空の家計簿アプリの使い勝手と継続意向を把握する",
           "moderator_guide": "印象／分類／役立つ機能／使いにくい点／意識の変化／継続意向",
           "comparison_group": "架空の家計簿アプリ評価"}
PRIMARY_EXPERTS = {
    "qualitative_content": "exp-qualitative-content-analysis", "thematic": "exp-thematic-analysis",
    "framework": "exp-framework-method", "scat": "exp-scat", "mgta": "exp-m-gta", "kj": "exp-kj-method",
    "quantitative_text": "exp-quantitative-text-analysis", "interaction": "exp-focus-group-interaction",
}


def failed(review):
    """(check name, severity, result) for every check a full or saved review did not pass."""
    rows = review["checks"] if "checks" in review else review["unmet_checks"]
    return {(row["check"], row["severity"], row["result"]) for row in rows if row["result"] in {"fail", "not_evaluable"}}


class ExpertSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix="gurumoji-expert-samples-")
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        for patcher in (patch.object(app, "DATABASE_FILE", cls.root / "library.sqlite3"),
                        patch.object(research_analysis, "_load_ginza", return_value=(None, "test fallback")),
                        patch.object(research_analysis, "_load_sudachi", return_value=(None, "test fallback"))):
            patcher.start()
            cls.addClassCleanup(patcher.stop)
        research_analysis._RESEARCH_CACHE.clear()
        cls.addClassCleanup(research_analysis._RESEARCH_CACHE.clear)
        app.initialize_library()
        cls.client = app.app.test_client()
        # Three participants and a moderator, with times and stored emotion labels (no model inference).
        cls.add("fit")
        cls.confirm("fit")
        cls.add("no_question", profile={"session_type": "focus_group"})
        cls.add("one_speaker", [line for line in LINES if line[0] == "A"][:8])
        cls.confirm("one_speaker")
        cls.add("no_times", times=False)
        cls.add("long", [("ABC"[index % 3], f"{index}回目の発言です。分類と通知について短く述べました。")
                         for index in range(450)], emotions=())
        cls.confirm("long")
        cls.add("sparse_emotion", emotions=(1, 2))
        cls.confirm("sparse_emotion")

    @classmethod
    def add(cls, item_id, lines=LINES, *, times=True, emotions=None, profile=PROFILE):
        segments = []
        for index, (speaker, text) in enumerate(lines):
            segment = {"id": f"{item_id}_{index:03d}", "speaker": speaker, "text": text,
                       "start": index * 6.0 if times else None, "end": index * 6.0 + 5.0 if times else None}
            if emotions is None or index in emotions:
                segment["emotions"] = {"sample": {"label": "neutral", "label_ja": "中立", "model_name": "架空の保存済み推定"}}
            segments.append(segment)
        speakers = sorted({speaker for speaker, _ in lines})
        app.upsert_library_item(
            item_id=item_id, source_name=f"架空の座談会_{item_id}.wav", output_dir=cls.root / "out" / item_id,
            media_path=None, language="ja", segments=segments, speaker_names={s: NAMES[s] for s in speakers},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True, session_profile=profile,
            speaker_profiles={s: {"display_name": NAMES[s], "session_role": "moderator" if s == "MOD" else "participant"}
                              for s in speakers})

    @classmethod
    def confirm(cls, item_id):
        data = cls.client.get(f"/api/library/{item_id}/analysis").get_json()
        prep = data["manual"]["preparation"]
        records = {s["id"]: {"text_status": "transcript_checked", "speaker_verified": True, "boundary_verified": True,
                             "role": "moderator" if s["speaker"] == "MOD" else "participant"} for s in data["segments"]}
        response = cls.client.put(f"/api/library/{item_id}/preparation", json={
            "revision": prep["revision"], "source_hash": prep["source_hash"], "records": records,
            "order_verified": True, "confirm": True, "participant_count": 3,
            "metadata_sources": "架空の参加者名簿", "review_analysis": True})
        if response.status_code != 200:
            raise AssertionError(response.get_json())

    def configure(self, item_id, method, question=QUESTION):
        data = self.client.get(f"/api/library/{item_id}/analysis").get_json()
        response = self.client.put(f"/api/library/{item_id}/analysis", json={
            "source_revision": data["item"]["revision_count"], "analysis_revision": data["item"]["analysis_revision"],
            "config": {**data["config"], "analysis_method": method, "research_question": question}})
        self.assertEqual(response.status_code, 200, response.get_json())
        return self.client.get(f"/api/library/{item_id}/analysis").get_json()

    def draft(self, item_id, request_id, step_id="", basis_id=""):
        """Request AI insights; a fake provider answers with the given procedure step and basis."""
        data = self.client.get(f"/api/library/{item_id}/analysis").get_json()
        with patch.object(app, "load_token_config", return_value=app.TokenConfig(openai_api_key="test-key")), \
                patch.object(app.threading, "Thread") as thread:
            response = self.client.post(f"/api/library/{item_id}/analysis/insights", json={
                "request_id": request_id, "provider": "openai", "source_revision": data["item"]["revision_count"],
                "analysis_revision": data["item"]["analysis_revision"]})
        if response.status_code != 202:
            return response

        def answer(provider, api_key, model, system, prompt, name, schema, *args, **kwargs):
            refs = schema["properties"]["findings"]["items"]["properties"]["segment_ids"]["items"]["enum"]
            return {"findings": [{"category": "themes", "title": "候補", "text": "架空のサンプルへの下書き。",
                                  "segment_ids": [refs[0]], "method_step": step_id, "basis_ids": [basis_id]}]}

        with patch.object(app, "call_ai_json", side_effect=answer):
            app.run_analysis_insight_job(*thread.call_args.kwargs["args"])
        return self.client.get(f"/api/library/{item_id}/analysis/insights")

    def result(self, run_id):
        store = app.analysis_archive_store()
        artifact = next(a["id"] for a in store.artifacts(run_id) if a["name"] == "result.json")
        return json.loads(store.read_artifact(artifact)[1])

    def saved(self, item_id, request_id):
        row = app.library_row(item_id)
        run = app.archive_group_analysis(row, app.group_analysis_for_row(row, include_research_rows=True), request_id)
        result = self.result(run["id"])
        return run, {method["method_id"]: method for method in result["methods"]}, result

    def test_each_selected_method_loads_its_expert_and_only_the_plan_experts(self):
        for method, expert_id in PRIMARY_EXPERTS.items():
            with self.subTest(method):
                self.configure("fit", method)
                catalog = experts.ExpertCatalog()
                with patch.object(experts, "_default_catalog", catalog):
                    data = self.client.get("/api/library/fit/analysis").get_json()
                reviews = data["experts"]["experts"]
                self.assertEqual((reviews[0]["expert_id"], reviews[0]["selection"]), (expert_id, "researcher"))
                planned = {row["method_id"] for row in data["manual"]["focus_group_plan"]["methods"]}
                self.assertEqual({review["expert_id"] for review in reviews},
                                 {catalog.expert_for_method(method_id) for method_id in planned})
                read = {path.split("/")[2] for path in catalog.read_log
                        if not path.startswith("properties:") and path.split("/")[1] == "10-Experts"}
                self.assertEqual(read, {catalog.index()[review["expert_id"]]["folder"] for review in reviews})
                steps = catalog.definition(expert_id)["procedure"]
                self.assertEqual(data["manual"]["focus_group_plan"]["procedure"],
                                 [f"{step['title']}（担当：{experts.ACTOR_LABELS[step['actor']]}）" for step in steps])
                report = self.client.get("/api/library/fit/analysis/export.md").get_data(as_text=True)
                self.assertIn(f"### {reviews[0]['title']}（主・研究者が選択）", report)

    def test_ai_drafts_follow_the_primary_expert_or_are_refused(self):
        refused = set()
        for method, expert_id in PRIMARY_EXPERTS.items():
            with self.subTest(method):
                data = self.configure("fit", method)
                request_id = "sample-ai-draft-" + method.replace("_", "-")
                context = experts.ai_context(data["experts"])
                if context is None:
                    response = self.draft("fit", request_id)
                    self.assertEqual(response.status_code, 409)
                    self.assertTrue(response.get_json()["expert_blocked"])
                    refused.add(method)
                    continue
                step = context["steps"][0]
                insights = self.draft("fit", request_id, step["id"], step["basis"][0]).get_json()
                self.assertEqual(insights["run"]["status"], "completed")
                finding = insights["insights"]["ai"]["findings"][0]
                self.assertEqual((finding["method_step"], finding["basis_ids"]), (step["id"], [step["basis"][0]]))
                self.assertEqual(insights["insights"]["ai"]["expert"]["expert_id"], expert_id)
        self.assertEqual(refused, {"kj", "quantitative_text"})

    def test_fabricated_basis_fails_the_job_and_keeps_the_previous_draft(self):
        self.configure("fit", "thematic")
        self.draft("fit", "sample-fabricated-valid", "ta-p3", "LIT-oka-2022-reflexive-ta-ja")
        insights = self.draft("fit", "sample-fabricated-invalid", "ta-p2", "LIT-fabricated-2099").get_json()
        self.assertEqual(insights["run"]["status"], "failed")
        self.assertIn("登録されていない文献ID", insights["run"]["message"])
        self.assertEqual(insights["insights"]["ai"]["findings"][0]["basis_ids"], ["LIT-oka-2022-reflexive-ta-ja"])

    def test_unsuitable_samples_are_refused_or_warned_by_the_responsible_expert(self):
        cases = [
            ("no_question", "qualitative_content", "", "blocked", ("research_question_present", "block", "fail")),
            ("no_question", "thematic", "", "blocked", ("research_question_present", "block", "fail")),
            # M-GTA needs an analysis theme of its own; the session objective does not count.
            ("fit", "mgta", "", "blocked", ("research_question_present", "block", "fail")),
            ("one_speaker", "framework", QUESTION, "blocked", ("min_speakers", "block", "fail")),
            ("no_times", "interaction", QUESTION, "blocked", ("speaker_order_confirmed", "block", "fail")),
            ("long", "scat", QUESTION, "needs_attention", ("max_included_segments", "warn", "fail")),
            ("long", "kj", QUESTION, "needs_attention", ("max_included_segments", "warn", "fail")),
            ("one_speaker", "quantitative_text", QUESTION, "needs_attention", ("min_included_segments", "warn", "fail")),
        ]
        for item_id, method, question, status, check in cases:
            with self.subTest(item=item_id, method=method):
                review = self.configure(item_id, method, question)["experts"]["experts"][0]
                self.assertEqual(review["status"], status)
                self.assertIn(check, failed(review))
                if status == "blocked":
                    request_id = f"sample-refused-{item_id}-{method}".replace("_", "-")
                    self.assertEqual(self.draft(item_id, request_id).status_code, 409)
        report = self.client.get("/api/library/no_times/analysis/export.md").get_data(as_text=True)
        self.assertIn("[分析を始めない・満たさない]", report)

    def test_saved_results_carry_the_expert_judgement_of_each_produced_method(self):
        self.configure("fit", "thematic")
        _, fit, result = self.saved("fit", "sample-saved-fit-0001")
        _, one, _ = self.saved("one_speaker", "sample-saved-one-speaker-0001")
        _, untimed, _ = self.saved("no_times", "sample-saved-no-times-0001")
        _, sparse, _ = self.saved("sparse_emotion", "sample-saved-sparse-emotion-0001")
        responsible = {
            "participation": "exp-participation-balance", "conversation_dynamics": "exp-conversation-timing",
            "descriptive_statistics": "exp-descriptive-statistics", "group_statistics": "exp-group-comparison-statistics",
            "correlation": "exp-correlation", "audio_emotion": "exp-speech-emotion-recognition",
            "morphology": "exp-japanese-text-preprocessing", "lexical_frequency": "exp-quantitative-text-analysis",
        }
        for method_id, expert_id in responsible.items():
            self.assertEqual(fit[method_id]["expert_review"]["expert_id"], expert_id, method_id)
        # No result, no judgement: Transformer topics were not run and syntax needs GiNZA.
        self.assertNotIn("expert_review", fit["transformer_topics"])
        self.assertNotIn("expert_review", fit["syntax"])
        self.assertEqual(fit["participation"]["expert_review"]["status"], "ready")
        cases = [
            (one, "participation", "blocked", ("min_speakers", "block", "fail")),
            (one, "group_statistics", "blocked", ("statistics_min_groups", "block", "fail")),
            (one, "correlation", "needs_attention", ("min_included_segments", "warn", "fail")),
            (untimed, "conversation_dynamics", "blocked", ("valid_time_ratio_min", "block", "fail")),
            (sparse, "audio_emotion", "needs_attention", ("emotion_coverage_min", "warn", "fail")),
            (fit, "morphology", "needs_attention", ("morphology_engine_ready", "warn", "fail")),
        ]
        for methods, method_id, status, check in cases:
            with self.subTest(method_id=method_id, status=status):
                review = methods[method_id]["expert_review"]
                self.assertEqual(review["status"], status)
                self.assertIn(check, failed(review))
                self.assertIn(f"担当専門家：{review['title']}", "\n".join(methods[method_id]["limitations"]))
        self.assertIn("exp-thematic-analysis", result["algorithms"]["experts"])

    def test_transformer_results_are_judged_only_when_produced(self):
        analysis = app.group_analysis_for_row(app.library_row("fit"))
        stored = {"fingerprint": transformer_analysis.transformer_input_fingerprint(
                      analysis, model=app.DEFAULT_TRANSFORMER_MODEL),
                  "engine": {"name": app.DEFAULT_TRANSFORMER_MODEL}, "quality": {"silhouette_cosine": 0.32},
                  "topics": [{"topic_id": 1, "label": "分類の迷い", "segment_count": 3,
                              "representative_segment_ids": [s["id"] for s in analysis["segments"][5:8]]}]}
        cases = [(stored, "completed", "ready"),
                 ({**stored, "quality": {"silhouette_cosine": 0.05}}, "completed", "needs_attention"),
                 ({**stored, "fingerprint": "0" * 64}, "stale", "blocked"),
                 ({}, "not_run", None)]
        for value, state, status in cases:
            with self.subTest(state=state, status=status):
                with app.database_connection() as connection:
                    connection.execute("UPDATE library_items SET transformer_analysis_json=? WHERE id='fit'",
                                       (json.dumps(value),))
                full = app.group_analysis_for_row(app.library_row("fit"), include_research_rows=True)
                datasets = {name: app.analysis_csv_rows(full, name) for name in app.ANALYSIS_CSV_FIELDS}
                method = next(m for m in app.method_results(full, datasets) if m["method_id"] == "transformer_topics")
                experts.attach_method_reviews([method], full)
                self.assertEqual((method["status"], method.get("expert_review", {}).get("status")), (state, status))

    def test_note_update_makes_saved_expert_drafts_stale_and_saves_a_new_run(self):
        copy = self.root / "knowledge-copy"
        shutil.copytree(experts.SOFTWARE_ROOT / "50-Analysis-Methods", copy / "50-Analysis-Methods")
        note = copy / "50-Analysis-Methods/10-Experts/thematic-analysis/02-Procedure.md"
        with patch.object(experts, "_default_catalog", experts.ExpertCatalog(copy)):
            self.configure("fit", "thematic", QUESTION + "（ノート更新の確認）")
            drafted = self.draft("fit", "sample-note-update-draft", "ta-p3", "LIT-oka-2022-reflexive-ta-ja").get_json()
            first, _, _ = self.saved("fit", "sample-note-update-run-1")
            again, _, _ = self.saved("fit", "sample-note-update-run-2")
            note.write_text(note.read_text(encoding="utf-8") + "\n確認の観点を追記。\n", encoding="utf-8")
            insights = self.client.get("/api/library/fit/analysis/insights").get_json()["insights"]
            changed, _, _ = self.saved("fit", "sample-note-update-run-3")
        self.assertFalse(drafted["insights"]["stale"])
        self.assertTrue(insights["stale"])
        self.assertEqual(first["id"], again["id"])
        self.assertNotEqual(first["id"], changed["id"])

    def test_cross_session_comparison_is_judged_in_its_own_run(self):
        self.add("fit_second")
        selection = {"item_ids": ["fit", "fit_second"], "allow_different_content": False}
        compared = self.client.post("/api/library/interview-comparison", json=selection)
        self.assertEqual(compared.status_code, 200, compared.get_json())
        saved = self.client.post("/api/library/interview-comparison/runs", json={
            **selection, "request_id": "sample-comparison-run-0001",
            "input_fingerprints": compared.get_json()["input_fingerprints"]})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        review = self.result(saved.get_json()["run"]["id"])["methods"][0]["expert_review"]
        self.assertEqual((review["expert_id"], review["status"]), ("exp-cross-session-comparison", "ready"))
        single = [{"method_id": "interview_comparison", "status": "completed"}]
        experts.attach_method_reviews(single, {"segments": [], "config": {}}, context={"session_count": 1})
        self.assertIn(("comparison_sessions_min", "block", "fail"), failed(single[0]["expert_review"]))


if __name__ == "__main__":
    unittest.main()
