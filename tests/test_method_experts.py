"""Method experts: Software Vault definitions drive checks, procedures, reports and AI drafts."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import analysis_insights as content
import research_analysis
import test_content_analysis as support
from gurumoji import method_experts as experts
from gurumoji.analysis_method_registry import METHODS
from gurumoji.obsidian_layout import unpack
from gurumoji.vault_registry import SOFTWARE_ROOT

EXPECTED_REGISTRY_EXPERTS = {
    "lexical_frequency": "exp-quantitative-text-analysis", "cooccurrence": "exp-quantitative-text-analysis",
    "speaker_characteristics": "exp-quantitative-text-analysis", "kwic": "exp-quantitative-text-analysis",
    "participation": "exp-participation-balance", "conversation_dynamics": "exp-conversation-timing",
    "descriptive_statistics": "exp-descriptive-statistics", "group_statistics": "exp-group-comparison-statistics",
    "correlation": "exp-correlation", "transformer_topics": "exp-embedding-topic-exploration",
    "audio_emotion": "exp-speech-emotion-recognition", "morphology": "exp-japanese-text-preprocessing",
    "syntax": "exp-japanese-text-preprocessing", "interview_comparison": "exp-cross-session-comparison",
}
# Tools, AI vehicles and editing aids: not research methods, so no expert (see 10-Experts/00-Index).
METHODS_WITHOUT_EXPERT = {"local_insights", "qualitative_coding", "ai_insights", "outline", "ai_finishing",
                          "meeting_minutes", "segment_classification"}
LITERATURE_FIELDS = {"note_id", "note_type", "literature_id", "title", "authors", "year", "venue", "source_type",
                     "peer_review", "peer_review_basis", "doi", "url", "accessed", "access_scope",
                     "access_detail", "correction_status", "related_experts", "status", "updated", "tags"}


def synthetic(method="thematic", *, question="改善意見はどう形成されたか", included=6, speakers=3,
              participants=2, order_verified=True, unknown_turns=0, auxiliaries=("interaction", "quantitative_text")):
    """A fictitious analysis dict: only the values expert checks read."""
    primary = "qualitative_content" if method == "auto" else method
    rows = [{"method_id": primary, "role": "主"}] + [{"method_id": m, "role": "補助"} for m in auxiliaries]
    return {
        "config": {"analysis_method": method, "research_question": question, "group_by": "none",
                   "method_rationale": ""},
        "item": {"id": "sample", "revision_count": 0, "analysis_revision": 0, "session_profile": {}},
        "automatic": {"overview": {"included_segment_count": included, "segment_count": included,
                                   "speaker_count": speakers, "participant_count": participants},
                      "data_quality": {"invalid_time_segments": 0, "unknown_speaker_segments": unknown_turns,
                                       "emotion_coverage_percent": 0.0}},
        "manual": {"preparation": {"status": "confirmed", "order_verified": order_verified,
                                   "unknown_speaker_turns": unknown_turns, "analysis_needs_review": False},
                   "codebook": [], "coded_segment_count": 0, "interaction_links": [],
                   "focus_group_plan": {"methods": rows}},
        "research": {"linguistics": {"engine": {"status": "ready", "syntax": "GiNZA"}},
                     "statistics": {"engine": {"status": "ready"}, "group_count": 2, "tests": []}},
        "transformer": {"result": None, "stale": False},
        "segments": [],
    }


def by_id(block):
    return {review["expert_id"]: review for review in block["experts"]}


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = experts.ExpertCatalog()
        self.index = self.catalog.index()

    def test_root_is_the_software_vault_the_registry_uses(self):
        self.assertEqual(experts.SOFTWARE_ROOT, app.PROJECT_DIRECTORY / "docs" / "program-vault")

    def test_every_selectable_method_and_registry_method_has_the_documented_expert(self):
        for method in app.ANALYSIS_METHODS:
            if method != "auto":
                owners = [e for e, entry in self.index.items() if method in entry["analysis_method_ids"]]
                self.assertEqual(len(owners), 1, method)
        registry = {key for key, *_ in METHODS}
        self.assertEqual(set(EXPECTED_REGISTRY_EXPERTS) | METHODS_WITHOUT_EXPERT, registry)
        for method, expert_id in EXPECTED_REGISTRY_EXPERTS.items():
            self.assertEqual(self.catalog.expert_for_method(method, registry=True), expert_id, method)
        for method in METHODS_WITHOUT_EXPERT:
            self.assertIsNone(self.catalog.expert_for_method(method, registry=True), method)
        self.assertEqual(len(self.index), 17)

    def test_definitions_are_valid_and_every_reference_resolves(self):
        for expert_id, entry in self.index.items():
            with self.subTest(expert_id):
                definition = self.catalog.definition(expert_id)
                knowledge = self.catalog.knowledge(expert_id, definition)
                self.assertEqual((knowledge["missing_references"], knowledge["missing_notes"]), ([], []))
                for item in definition["out_of_scope"]:
                    if item.get("handoff"):
                        self.assertIn(item["handoff"], self.index)
                folder = SOFTWARE_ROOT / experts.EXPERTS_DIR / entry["folder"]
                for name in experts.KNOWLEDGE_NOTES:
                    props, _ = unpack((folder / name).read_text(encoding="utf-8"))
                    self.assertEqual(props.get("expert_id"), expert_id, name)

    def test_literature_notes_record_access_scope_and_peer_review_basis(self):
        notes = [path for path in (SOFTWARE_ROOT / experts.LITERATURE_DIR).glob("*.md") if path.name != "00-Index.md"]
        self.assertGreaterEqual(len(notes), 70)
        seen = set()
        for path in notes:
            props, body = unpack(path.read_text(encoding="utf-8"))
            with self.subTest(path.name):
                self.assertLessEqual(LITERATURE_FIELDS, set(props))
                self.assertEqual(props["literature_id"], path.stem)
                self.assertIn(props["access_scope"], {"full_text", "abstract", "bibliographic", "official_page"})
                self.assertIn(props["peer_review"], {"confirmed", "not_peer_reviewed", "unconfirmed"})
                self.assertTrue(str(props["peer_review_basis"]).strip())
                if props["access_scope"] == "bibliographic":
                    self.assertIn("内容は記載しない", body)
                self.assertNotIn(props["note_id"], seen)
                seen.add(props["note_id"])

    def test_ai_assistance_is_method_specific(self):
        kj = self.catalog.definition("exp-kj-method")["ai_assist"]
        self.assertFalse(kj["allowed"])
        thematic = self.catalog.definition("exp-thematic-analysis")
        steps = {step["id"]: step for step in thematic["procedure"]}
        self.assertTrue(thematic["ai_assist"]["allowed"])
        for step_id in thematic["ai_assist"]["steps"]:
            self.assertEqual(steps[step_id]["actor"], "ai_draft")
            self.assertTrue(any(value.startswith(("LIT-", "RES-")) for value in steps[step_id]["basis"]))
        # Schools stay distinct: reflexive TA does not inherit content analysis reliability checks.
        self.assertNotIn("codebook_min_codes", {c["check"] for c in thematic["quality_checks"]})


class SelectionTests(unittest.TestCase):
    def test_only_selected_experts_and_their_literature_are_read(self):
        catalog = experts.ExpertCatalog()
        block = experts.review_for_analysis(synthetic("thematic"), catalog)
        self.assertEqual([r["expert_id"] for r in block["experts"]],
                         ["exp-thematic-analysis", "exp-focus-group-interaction", "exp-quantitative-text-analysis"])
        selected = {"thematic-analysis", "focus-group-interaction", "quantitative-text-analysis"}
        cited = {reference["note"] + ".md" for review in block["experts"] for reference in review["references"]}
        full_reads = [path for path in catalog.read_log if not path.startswith("properties:")]
        self.assertTrue(full_reads)
        for path in full_reads:
            area = path.split("/")[1]
            if area == "10-Experts":
                self.assertIn(path.split("/")[2], selected, path)
            elif area == "20-Literature":
                self.assertIn(path, cited, path)
            else:
                self.assertEqual(area, "08-Common-Knowledge", path)
        self.assertFalse(any("LIT-kinoshita-2007-mgta" in path or "kushinada" in path for path in full_reads))

    def test_unselected_method_is_provisional_and_ai_stays_generic(self):
        block = experts.review_for_analysis(synthetic("auto"))
        self.assertEqual((block["experts"][0]["expert_id"], block["experts"][0]["selection"]),
                         ("exp-qualitative-content-analysis", "provisional"))
        self.assertEqual(block["ai"]["mode"], "generic")

    def test_conditions_that_block_the_method_also_block_ai(self):
        block = experts.review_for_analysis(synthetic("thematic", question=""))
        thematic = by_id(block)["exp-thematic-analysis"]
        self.assertEqual(thematic["status"], "blocked")
        self.assertEqual(block["ai"]["mode"], "blocked")
        self.assertIn("研究質問", experts.ai_block_reason(block))

    def test_kj_method_never_uses_ai_drafts(self):
        block = experts.review_for_analysis(synthetic("kj"))
        self.assertEqual(by_id(block)["exp-kj-method"]["status"], "ready")
        self.assertEqual(block["ai"]["mode"], "blocked")

    def test_unsuitable_data_is_warned_or_blocked_by_the_responsible_expert(self):
        scat = by_id(experts.review_for_analysis(synthetic("scat", included=450)))["exp-scat"]
        self.assertEqual(scat["status"], "needs_attention")
        self.assertIn(("scat-a3", "fail"), {(c["id"], c["result"]) for c in scat["checks"]})
        interaction = by_id(experts.review_for_analysis(synthetic("thematic", order_verified=False,
                                                                  unknown_turns=2)))["exp-focus-group-interaction"]
        self.assertEqual(interaction["status"], "blocked")
        self.assertIn("研究者が確認する項目", "\n".join(experts.report_lines(
            experts.review_for_analysis(synthetic("thematic")))))

    def test_report_separates_methodological_basis_and_denies_unperformed_reviews(self):
        lines = "\n".join(experts.report_lines(experts.review_for_analysis(synthetic("thematic"))))
        self.assertIn("方法論の根拠（文献ノート）", lines)
        self.assertIn("LIT-braun-clarke-2006-thematic（査読確認済み・本文確認）", lines)
        self.assertIn("独立したレビューは行っていません", lines)


class KnowledgeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-experts-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(SOFTWARE_ROOT / "50-Analysis-Methods", self.root / "50-Analysis-Methods")
        self.catalog = experts.ExpertCatalog(self.root)

    def test_updated_note_changes_knowledge_hash_and_ai_fingerprint(self):
        analysis = synthetic("thematic")
        before = experts.review_for_analysis(analysis, self.catalog)
        note = self.root / "50-Analysis-Methods/10-Experts/thematic-analysis/02-Procedure.md"
        note.write_text(note.read_text(encoding="utf-8") + "\n追記：確認の観点を加えた。\n", encoding="utf-8")
        after = experts.review_for_analysis(analysis, self.catalog)
        self.assertNotEqual(before["experts"][0]["knowledge_hash"], after["experts"][0]["knowledge_hash"])
        self.assertNotEqual(before["ai"]["fingerprint"], after["ai"]["fingerprint"])
        self.assertNotEqual(content.input_fingerprint({**analysis, "experts": before}),
                            content.input_fingerprint({**analysis, "experts": after}))

    def test_missing_literature_note_is_shown_and_never_cited_by_ai(self):
        (self.root / "50-Analysis-Methods/20-Literature/LIT-oka-2022-reflexive-ta-ja.md").unlink()
        block = experts.review_for_analysis(synthetic("thematic"), self.catalog)
        thematic = block["experts"][0]
        self.assertIn("LIT-oka-2022-reflexive-ta-ja", thematic["missing_references"])
        self.assertFalse(thematic["readiness"]["references_resolved"])
        self.assertEqual(thematic["status"], "needs_attention")
        self.assertIn("見つからない文献ノート", "\n".join(experts.report_lines(block)))
        # ta-p3 rests only on the missing note, so it is withdrawn; ta-p2 keeps its other basis.
        context = experts.ai_context(block, self.catalog)
        self.assertEqual([(step["id"], step["basis"]) for step in context["steps"]],
                         [("ta-p2", ["LIT-braun-clarke-2006-thematic"])])

    def test_ai_context_rejects_knowledge_changed_since_review(self):
        analysis = synthetic("thematic", auxiliaries=())
        before = experts.review_for_analysis(analysis, self.catalog)
        original = experts.ai_context(before, self.catalog)
        note = self.root / "50-Analysis-Methods/10-Experts/thematic-analysis/02-Procedure.md"
        note.write_text(note.read_text(encoding="utf-8") + "\n確認手順を更新。\n", encoding="utf-8")
        with self.assertRaisesRegex(experts.ExpertDefinitionError, "定義・知識が更新"):
            experts.ai_context(before, self.catalog)
        after = experts.review_for_analysis(analysis, self.catalog)
        refreshed = experts.ai_context(after, self.catalog)
        self.assertNotEqual(original["knowledge_hash"], refreshed["knowledge_hash"])
        self.assertEqual(refreshed["knowledge_hash"], after["ai"]["knowledge_hash"])

    def test_ai_context_never_combines_new_instructions_with_old_hash(self):
        analysis = synthetic("thematic", auxiliaries=())
        before = experts.review_for_analysis(analysis, self.catalog)
        original = experts.ai_context(before, self.catalog)
        note = self.root / "50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert.md"
        text = note.read_text(encoding="utf-8")
        self.assertIn(original["brief"], text)
        changed_brief = original["brief"] + " 根拠の確認を追加する。"
        note.write_text(text.replace(original["brief"], changed_brief, 1), encoding="utf-8")
        with self.assertRaisesRegex(experts.ExpertDefinitionError, "定義・知識が更新"):
            experts.ai_context(before, self.catalog)
        refreshed = experts.ai_context(experts.review_for_analysis(analysis, self.catalog), self.catalog)
        self.assertEqual(refreshed["brief"], changed_brief)
        self.assertNotEqual(refreshed["knowledge_hash"], original["knowledge_hash"])

    def test_ai_is_blocked_when_no_ai_step_has_an_existing_basis_note(self):
        for name in ("LIT-oka-2022-reflexive-ta-ja", "LIT-braun-clarke-2006-thematic"):
            (self.root / f"50-Analysis-Methods/20-Literature/{name}.md").unlink()
        block = experts.review_for_analysis(synthetic("thematic"), self.catalog)
        self.assertEqual(block["ai"]["mode"], "blocked")
        self.assertIn("根拠となる文献ノートが見つからない", experts.ai_block_reason(block))

    def test_invalid_definition_is_reported_and_blocks_method_specific_ai(self):
        note = self.root / "50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert.md"
        note.write_text(note.read_text(encoding="utf-8").replace(
            "check: research_question_present", "check: run_arbitrary_code", 1), encoding="utf-8")
        block = experts.review_for_analysis(synthetic("thematic"), self.catalog)
        self.assertEqual(block["experts"][0]["status"], "definition_error")
        self.assertEqual(block["ai"]["mode"], "blocked")

    def test_missing_expert_folder_falls_back_to_generic_behaviour(self):
        block = experts.review_for_analysis(synthetic("thematic"), experts.ExpertCatalog(self.root / "none"))
        self.assertEqual((block["status"], block["ai"]["mode"]), ("unavailable", "generic"))


class LocalKnowledgeTests(unittest.TestCase):
    """A local, gitignored tree (ADR-120) can add or shadow notes without touching the Software Vault base."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-local-knowledge-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "base"
        self.local = Path(self.temp.name) / "local"
        shutil.copytree(SOFTWARE_ROOT / "50-Analysis-Methods", self.root / "50-Analysis-Methods")

    def test_missing_local_directory_behaves_like_base_only(self):
        index = experts.ExpertCatalog(self.root, self.local).index()
        self.assertEqual(len(index), 17)
        self.assertTrue(all(entry["source"] == "base" for entry in index.values()))

    def test_local_only_expert_folder_is_added_with_its_own_source(self):
        folder = self.local / "50-Analysis-Methods/10-Experts/my-local-expert"
        base_folder = self.root / "50-Analysis-Methods/10-Experts/thematic-analysis"
        folder.mkdir(parents=True)
        for name in experts.KNOWLEDGE_NOTES:
            text = (base_folder / name).read_text(encoding="utf-8")
            text = text.replace("exp-thematic-analysis", "exp-my-local-expert").replace(
                "thematic-analysis", "my-local-expert")
            (folder / name).write_text(text, encoding="utf-8")
        catalog = experts.ExpertCatalog(self.root, self.local)
        index = catalog.index()
        self.assertEqual(len(index), 18)
        self.assertEqual(index["exp-my-local-expert"]["source"], "local")
        knowledge = catalog.knowledge("exp-my-local-expert", catalog.definition("exp-my-local-expert"))
        self.assertEqual((knowledge["missing_references"], knowledge["missing_notes"]), ([], []))

    def test_local_note_shadows_the_base_note_and_changes_the_knowledge_hash(self):
        override = self.local / "50-Analysis-Methods/10-Experts/thematic-analysis"
        override.mkdir(parents=True)
        base_note = self.root / "50-Analysis-Methods/10-Experts/thematic-analysis/02-Procedure.md"
        (override / "02-Procedure.md").write_text(
            base_note.read_text(encoding="utf-8") + "\n追記：ローカル環境だけの確認観点。\n", encoding="utf-8")
        base_only = experts.ExpertCatalog(self.root, self.local / "does-not-exist")
        with_local = experts.ExpertCatalog(self.root, self.local)
        self.assertEqual(base_only.index()["exp-thematic-analysis"]["source"], "base")
        self.assertEqual(with_local.index()["exp-thematic-analysis"]["source"], "local_override")
        base_knowledge = base_only.knowledge("exp-thematic-analysis", base_only.definition("exp-thematic-analysis"))
        local_knowledge = with_local.knowledge("exp-thematic-analysis", with_local.definition("exp-thematic-analysis"))
        self.assertNotEqual(base_knowledge["knowledge_hash"], local_knowledge["knowledge_hash"])


class ExpertAiDraftTests(unittest.TestCase):
    def setUp(self):
        self.expert = experts.ai_context(experts.review_for_analysis(synthetic("thematic")))
        self.analysis, _ = support.fixture()

    def test_generic_runs_keep_their_fingerprint(self):
        before = content.input_fingerprint(self.analysis)
        self.analysis["experts"] = {"ai": {"mode": "generic"}}
        self.assertEqual(before, content.input_fingerprint(self.analysis))
        self.analysis["experts"] = {"ai": {"mode": "expert", "fingerprint": self.expert["fingerprint"]}}
        self.assertNotEqual(before, content.input_fingerprint(self.analysis))

    def test_drafts_carry_registered_steps_and_basis_but_no_note_text(self):
        systems, schemas = [], []

        def call(system, prompt, schema):
            systems.append(system)
            schemas.append(schema)
            refs = schema["properties"]["findings"]["items"]["properties"]["segment_ids"]["items"]["enum"]
            return {"findings": [{"category": "themes", "title": "価格を比べる話題の候補", "text": "価格の比較が語られている。",
                                  "segment_ids": [refs[0]], "method_step": "ta-p3",
                                  "basis_ids": ["LIT-oka-2022-reflexive-ta-ja"]}]}

        result = content.create_ai_insights(self.analysis, call, lambda *a: None, lambda: None, expert=self.expert)
        self.assertEqual((result[0]["method_step"], result[0]["basis_ids"]), ("ta-p3", ["LIT-oka-2022-reflexive-ta-ja"]))
        self.assertIn(self.expert["brief"], systems[0])
        self.assertNotIn("## 研究目的", systems[0])
        fields = schemas[0]["properties"]["findings"]["items"]["properties"]
        self.assertEqual(set(fields["method_step"]["enum"]), {"ta-p2", "ta-p3"})
        self.assertNotIn("LIT-mayring-2000-qca", fields["basis_ids"]["items"]["enum"])

    def test_fabricated_literature_is_rejected_after_one_retry(self):
        calls = []

        def call(system, prompt, schema):
            calls.append(1)
            refs = schema["properties"]["findings"]["items"]["properties"]["segment_ids"]["items"]["enum"]
            return {"findings": [{"category": "themes", "title": "候補", "text": "本文", "segment_ids": [refs[0]],
                                  "method_step": "ta-p2", "basis_ids": ["LIT-fabricated-2099"]}]}

        with self.assertRaisesRegex(ValueError, "登録されていない文献ID"):
            content.create_ai_insights(self.analysis, call, lambda *a: None, lambda: None, expert=self.expert)
        self.assertEqual(len(calls), 2)


class ExpertApiTests(unittest.TestCase):
    item_id = "expert_fixture"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-experts-api-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for patcher in (patch.object(app, "DATABASE_FILE", root / "library.sqlite3"),
                        patch.object(research_analysis, "_load_ginza", return_value=(None, "test fallback")),
                        patch.object(research_analysis, "_load_sudachi", return_value=(None, "test fallback"))):
            patcher.start()
            self.addCleanup(patcher.stop)
        research_analysis._RESEARCH_CACHE.clear()
        app.initialize_library()
        self.client = app.app.test_client()
        segments = [
            {"id": "m1", "speaker": "MOD", "start": 0.0, "end": 2.0, "text": "使ってみてどうでしたか？"},
            {"id": "a1", "speaker": "A", "start": 2.2, "end": 5.0, "text": "操作が分かりにくいと感じました"},
            {"id": "b1", "speaker": "B", "start": 5.1, "end": 8.0, "text": "私も操作の説明が欲しいです"},
            {"id": "a2", "speaker": "A", "start": 8.2, "end": 11.0, "text": "説明があれば続けて使いたい"},
        ]
        app.upsert_library_item(
            item_id=self.item_id, source_name="架空の座談会.wav", output_dir=root / "out", media_path=None,
            language="ja", segments=segments, speaker_names={"MOD": "司会", "A": "参加者A", "B": "参加者B"},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True,
            session_profile={"session_type": "focus_group", "objective": "架空の製品の使い勝手を確かめる"},
            speaker_profiles={"MOD": {"display_name": "司会", "session_role": "moderator"},
                              "A": {"display_name": "参加者A", "session_role": "participant"},
                              "B": {"display_name": "参加者B", "session_role": "participant"}})

    def configure(self, method, question="使い勝手の課題は何か"):
        data = self.client.get(f"/api/library/{self.item_id}/analysis").get_json()
        response = self.client.put(f"/api/library/{self.item_id}/analysis", json={
            "source_revision": data["item"]["revision_count"], "analysis_revision": data["item"]["analysis_revision"],
            "config": {**data["config"], "analysis_method": method, "research_question": question}})
        self.assertEqual(response.status_code, 200, response.get_json())
        return self.client.get(f"/api/library/{self.item_id}/analysis").get_json()

    def test_selected_expert_drives_plan_procedure_and_report(self):
        data = self.configure("thematic")
        reviews = by_id(data["experts"])
        self.assertEqual(data["experts"]["experts"][0]["expert_id"], "exp-thematic-analysis")
        self.assertEqual(data["experts"]["ai"]["mode"], "expert")
        self.assertTrue(data["manual"]["focus_group_plan"]["procedure"][0].startswith("データに精通する"))
        # The auxiliary interaction expert refuses unverified speaker order instead of analysing it anyway.
        self.assertEqual(reviews["exp-focus-group-interaction"]["status"], "blocked")
        report = self.client.get(f"/api/library/{self.item_id}/analysis/export.md").get_data(as_text=True)
        self.assertIn("## 手法の専門家による確認", report)
        self.assertIn("[分析を始めない・満たさない] 話者と発話の順序が確認されていない", report)
        self.assertIn("LIT-oka-2022-reflexive-ta-ja", report)

    def test_kj_method_refuses_ai_insights_before_any_provider_call(self):
        data = self.configure("kj")
        response = self.client.post(f"/api/library/{self.item_id}/analysis/insights", json={
            "provider": "openai", "request_id": "kj-expert-block-0001",
            "source_revision": data["item"]["revision_count"], "analysis_revision": data["item"]["analysis_revision"]})
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertTrue(response.get_json()["expert_blocked"])

    def test_catalog_endpoints(self):
        self.assertEqual(len(self.client.get("/api/analysis/experts").get_json()["experts"]), 17)
        detail = self.client.get("/api/analysis/experts/exp-scat").get_json()
        self.assertEqual((detail["definition"]["expert_id"], detail["missing_references"]), ("exp-scat", []))
        self.assertEqual(self.client.get("/api/analysis/experts/exp-unknown").status_code, 404)

    def test_saved_run_records_reviews_for_produced_methods_only(self):
        self.configure("thematic")
        row = app.library_row(self.item_id)
        run = app.archive_group_analysis(row, app.group_analysis_for_row(row, include_research_rows=True),
                                         "expert-archive-0000001")
        store = app.analysis_archive_store()
        artifact = next(a["id"] for a in store.artifacts(run["id"]) if a["name"] == "result.json")
        result = json.loads(store.read_artifact(artifact)[1])
        methods = {method["method_id"]: method for method in result["methods"]}
        review = methods["participation"]["expert_review"]
        self.assertEqual(review["expert_id"], "exp-participation-balance")
        # Saved notes render limitations, so the judgement and its basis reach the Vault note.
        limitations = "\n".join(methods["participation"]["limitations"])
        self.assertIn(f"担当専門家：{review['title']}（exp-participation-balance", limitations)
        self.assertIn("方法論の根拠（文献ノート）：" + "、".join(review["reference_ids"]), limitations)
        self.assertNotIn("expert_review", methods["ai_insights"])
        self.assertIn("exp-thematic-analysis", result["algorithms"]["experts"])


if __name__ == "__main__":
    unittest.main()
