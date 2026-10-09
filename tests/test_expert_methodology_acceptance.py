"""G5 synthetic CPU observations, separate from semantic quality and adoption.

No model, SDK, real database/Vault, or researcher HumanRecord is used. RESULTS
contains observations for the external receipt runner; this module writes none.
CurrentPack acceptance means only accepted_unreviewed_draft, including bad prose.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji import method_experts as experts
from gurumoji.services.expert_agents import (
    ExpertAgentRegistry, request_packet, validate_report, cell_binding,
    validate_numeric_bindings,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {}
AI_ALLOWED = {
    "exp-qualitative-content-analysis", "exp-thematic-analysis", "exp-framework-method",
    "exp-scat", "exp-m-gta", "exp-focus-group-interaction", "exp-descriptive-statistics",
    "exp-group-comparison-statistics", "exp-correlation",
}


def synthetic_analysis(texts):
    segments = [{"id": f"u{i}", "speaker": "A" if i % 2 else "B", "text": text,
                 "excluded": False} for i, text in enumerate(texts, 1)]
    return {
        "segments": segments,
        "config": {"research_question": "相談相手獲得の過程", "group_by": "speaker",
                   "method_rationale": "合成条件のみ"},
        "item": {"session_profile": {"moderator_guide": "相談機会と支援相手"}},
        "automatic": {"overview": {"included_segment_count": len(segments),
            "segment_count": len(segments), "speaker_count": len({s['speaker'] for s in segments}),
            "participant_count": len({s['speaker'] for s in segments})},
            "data_quality": {"invalid_time_segments": 0, "unknown_speaker_segments": 0}},
        "manual": {"preparation": {"status": "confirmed", "order_verified": True,
            "unknown_speaker_turns": 0, "analysis_needs_review": False},
            "codebook": [], "coded_segment_count": 0},
    }


class ExpertMethodologyAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.empty = tempfile.TemporaryDirectory(prefix="methodology-empty-local-")
        cls.addClassCleanup(cls.empty.cleanup)
        cls.catalog = experts.ExpertCatalog(ROOT / "docs/program-vault", cls.empty.name)
        cls.registry = ExpertAgentRegistry(cls.catalog)
        # Any accidental network connection fails before leaving the CPU probe.
        guard = patch("socket.socket.connect", side_effect=AssertionError("No network in G5 probe"))
        guard.start()
        cls.addClassCleanup(guard.stop)

    def record(self, number, expert_id, analysis, route, normal, negative, **details):
        definition = self.catalog.definition(expert_id)
        entry = self.catalog.index()[expert_id]
        raw = (ROOT / "docs/program-vault" / experts.EXPERTS_DIR / entry["folder"] / "01-Expert.md").read_bytes()
        RESULTS[number] = {
            "expert_id": expert_id, "case_ids": [f"M33-{number:02d}-N", f"M33-{number:02d}-X"],
            "definition_version": definition["definition_version"],
            "definition_raw_sha256": hashlib.sha256(raw).hexdigest(),
            "knowledge_hash": self.catalog.knowledge(expert_id, definition)["knowledge_hash"],
            "source_id": f"synthetic-M33-{number:02d}", "source_version": fingerprint(analysis),
            "source_hash": fingerprint(analysis), "execution_actor": "Python handwritten synthetic fixture", "route": route,
            "normal": normal, "negative": negative,
            "semantic_quality": "NOTRUN: no model or researcher evaluation",
            "researcher_adoption": "NOTRUN: no HumanRecord entered",
            "save_provenance": "NOTRUN: pure Catalog/code/validator probes do not save runs",
            **details,
        }

    def forbidden(self, expert_id):
        definition = self.catalog.definition(expert_id)
        self.assertFalse(definition["ai_assist"]["allowed"])
        self.assertEqual(definition["ai_assist"]["steps"], [])
        with self.assertRaises(AnalysisContractError) as caught:
            self.registry.freeze({"expert_ids": [expert_id]})
        self.assertEqual(caught.exception.code, "expert_ai_unavailable")

    def c1_pair(self, number, expert_id, texts, field, normal, negative, premises):
        analysis = synthetic_analysis(texts)
        before = deepcopy(analysis)
        profile = self.registry.freeze({"expert_ids": [expert_id],
            "expert_inputs": {expert_id: {"analysis_premises": premises}}})["profiles"][expert_id]
        self.assertTrue(all(step["actor"] == "ai_draft" for step in profile["allowed_steps"]))
        evidence = [{"evidence_id": f"e:{s['id']}", "utterance_id": s["id"],
                     "text": s["text"], "speaker": s["speaker"]} for s in analysis["segments"]]
        context = {"question": analysis["config"]["research_question"], "task": {"title": "合成候補のみ"},
            "data_version": fingerprint(analysis), "annotation_version": "synthetic-annotations-v1",
            "raw_evidence": evidence, "coverage": {"scope": "dataset", "total": len(evidence)}}
        packet = request_packet(profile, context, analysis)
        self.assertEqual(packet["evidence"], evidence)
        self.assertEqual(packet["data_version"], fingerprint(analysis))
        self.assertEqual(packet["profile_hash"], profile["profile_hash"])
        self.assertEqual(profile["contract_version"], 1)
        ids = [row["evidence_id"] for row in evidence]
        raw = {"summary": "合成の未確認下書き", "claims": [], "analysis_requests": [], "label_patches": [],
            "expert_report": {"expert_id": expert_id, "profile_hash": profile["profile_hash"],
                "knowledge_hash": profile["knowledge_hash"], "status": "draft",
                "outputs": {key: "研究者の判断は未実施。候補以外は未確認。" for key in profile["output_schema"]["properties"]},
                "evidence_ids": ids, "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                "performed_step_ids": {1: ["qca-p5"], 2: ["ta-p3"], 3: ["fw-p6"],
                    4: ["scat-p2", "scat-p6"], 5: ["mgta-p4", "mgta-p5"], 8: ["fgi-p3", "fgi-p5"]}[number],
                "missing_inputs": [], "limitations": "合成の構造確認のみ。研究者採否と意味品質は未評価。"}}
        self.assertIn(field, raw["expert_report"]["outputs"])
        raw["expert_report"]["outputs"][field] = normal
        self.assertEqual(validate_report(profile, raw, ids), [])
        bad = deepcopy(raw)
        bad["expert_report"]["outputs"][field] = negative
        self.assertEqual(validate_report(profile, bad, ids), [])
        # Structural refusal remains active even while semantic prose is accepted.
        for mutation in ({"evidence_ids": ["outside"]}, {"profile_hash": "wrong"},
                         {"performed_step_ids": [profile["human_steps"][0]["id"]]}):
            malformed = deepcopy(bad)
            malformed["expert_report"].update(mutation)
            with self.assertRaises(AnalysisContractError):
                validate_report(profile, malformed, ids)
        self.assertEqual(analysis, before)
        self.assertNotIn("HumanRecord", raw["expert_report"])
        self.record(number, expert_id, analysis, "Registry.freeze -> request_packet -> currentPack validate_report",
            "accepted_unreviewed_draft", "accepted_unreviewed_draft", normal_input=normal,
            negative_input=negative, negative_meaning="不適切な合成散文を構造検証は拒否しない",
            profile_hash=profile["profile_hash"], evidence_ids=ids,
            normal_response_hash=fingerprint(raw), negative_response_hash=fingerprint(bad),
            performed_step_ids=raw["expert_report"]["performed_step_ids"],
            structural_mutations="outside evidence, wrong profile hash, researcher step rejected",
            c1_provenance_limit="C1 checks supplied evidence IDs and allowed steps, not actor_id or semantic linkage to source text hashes",
            typed_contract="NOTRUN: explicitly selected typed contracts require separate probes")

    def test_01_qualitative_content_analysis(self):
        self.c1_pair(1, "exp-qualitative-content-analysis", ["聞きたいが先輩が接客中"], "section_03",
            "u1は『相手の業務状況による相談機会の制約』の候補。定義・典型例・境界は研究者が確認する。",
            "12発話あるので12人の最重要課題。κ未計算だが信頼性確認済み。",
            "研究者定義のカテゴリーに照らし、帰納的候補と確定を区別する")

    def test_02_thematic_analysis(self):
        self.c1_pair(2, "exp-thematic-analysis", ["質問すると無能と思われそう", "一度助けてもらうと次は聞けた"],
            "candidate_themes", "u1/u2から『能力評価への警戒と相談の許可感』を候補にする。全体・反例の照合待ち。",
            "質問項目『相談の困りごと』をそのまま最重要テーマとし、AI候補を研究者確定テーマとする。",
            "再帰的テーマ分析の初期コードと初期テーマ候補のみ")

    def test_03_framework_method(self):
        self.c1_pair(3, "exp-framework-method", ["新人Aは勤務中に相談できない", "新人Bは支援相手に言及しない"],
            "section_03", "A/B×相談機会/支援相手のセル要約候補にu1/u2を付す。語られない支援は不在としない。",
            "件数ヒートマップでチャート化済み。空セルは支援なし。13/20は母集団の支持率。",
            "共通質問の新人A/Bをケースとして仮置き。研究者によるケースと枠組みの確定待ち")

    def test_04_scat(self):
        self.c1_pair(4, "exp-scat", ["忙しそうで声をかけられなかった"], "section_02",
            "u1の〈1〉候補は『忙しそう』。〈5〉候補は『忙しさは観察か推測か』。〈2〉〜〈4〉は研究者待ち。",
            "AIが〈2〉〜〈4〉と完成理論を生成したのでSCAT実施済み。〈4〉は長い説明文で確定。",
            "AIは原文語句〈1〉と疑問〈5〉のみ")

    def test_05_m_gta(self):
        self.c1_pair(5, "exp-m-gta", ["歓迎されたので聞けた", "歓迎されても相談しない"], "section_02",
            "『相談の許可感』に対するu1の具体例とu2の反対例候補。前後文脈・概念定義の採否は研究者待ち。",
            "焦点者なしに語句を細切れ自動コード化してM-GTA完成。検索結果が増えないため理論的飽和。",
            "焦点者は入職1年未満の新人。研究者定義『相談の許可感』に関わる候補探索")

    def test_08_focus_group_interaction(self):
        self.c1_pair(8, "exp-focus-group-interaction",
            ["毎週対面にしたい", "毎週は難しい。月1回なら", "では月1回に変えます", "それなら参加できます"],
            "section_03", "u1→u2は不同意、u1→u3は意見変更の候補。前後・司会の影響を研究者が確認する。",
            "『そうですね』だけで集団合意が確定。沈黙も同意。AI出力を人確認済みとする。",
            "話者・順序を合成fixtureとして固定。実研究者の確認は代行しない")

    def test_18_all_definitions_keep_nine_allowed_eight_forbidden(self):
        index = self.catalog.index()
        self.assertEqual(len(index), 17)
        allowed = {eid for eid in index if self.catalog.definition(eid)["ai_assist"]["allowed"]}
        self.assertEqual(allowed, AI_ALLOWED)
        for eid in set(index) - allowed:
            self.forbidden(eid)
        for eid in allowed:
            bundle = self.registry.freeze({"expert_ids": [eid]})
            profile = bundle["profiles"][eid]
            self.assertEqual(bundle["bundle_hash"], fingerprint({k: v for k, v in bundle.items() if k != "bundle_hash"}))
            self.assertEqual(profile["profile_hash"], fingerprint({k: v for k, v in profile.items() if k != "profile_hash"}))
            self.assertEqual({s["id"] for s in profile["allowed_steps"]}, set(self.catalog.definition(eid)["ai_assist"]["steps"]))
            self.assertTrue(all(s["actor"] == "ai_draft" for s in profile["allowed_steps"]))
            knowledge = self.catalog.knowledge(eid, self.catalog.definition(eid))
            by_note = {self.catalog._note(Path(p))["props"]["note_id"]: self.catalog._note(Path(p)) for p in knowledge["notes"]}
            for source in profile["knowledge"]:
                self.assertEqual(source["source_hash"], "sha256:" + by_note[source["note_id"]]["sha256"])
                self.assertIn("revision", source)

    def statistical_pair(self, number, expert_id, method, dataset, column, negative):
        from gurumoji.services.analysis_orchestration_methods import (
            run_orchestration_method, validate_statistical_result, calculation_packet,
        )
        analysis = {
            "segments": [{"id": f"u{i}", "speaker": "A" if i < 3 else "B", "text": "x" * count,
                "characters": count, "duration": i + 2, "valid_time": i != 1, "excluded": False,
                "question_candidate": i % 2 == 0, "annotation": {}}
                for i, count in enumerate((5, 9, 13, 20, 30))],
            "config": {"statistics_group_by": "speaker"}, "manual": {"codebook": []},
            "automatic": {"overview": {"included_segment_count": 5, "speaker_count": 2}},
            "research": {"linguistics": {"morphemes": [], "engine": {"status": "fallback"}}},
        }
        analysis["segments"].append({"id": "excluded", "speaker": "C", "text": "outside",
                                     "characters": 10000, "excluded": True})
        evidence = [{"evidence_id": f"e:{s['id']}", "utterance_id": s["id"],
                     "text": s["text"], "speaker": s["speaker"], "excluded": s["excluded"]}
                    for s in analysis["segments"]]
        source_version = fingerprint(analysis)
        task = {"method_id": method, "dataset_version": source_version}
        snapshot = {"input_hash": source_version, "source_revision": 1, "analysis_revision": 1,
                    "analysis": analysis, "evidence": evidence, "orchestration_task": task}
        before = deepcopy(snapshot)
        rawcalc = run_orchestration_method(method, snapshot)
        validate_statistical_result(rawcalc, task, evidence)
        self.assertEqual(rawcalc["manifest"]["included_count"], 5)
        self.assertEqual(rawcalc["manifest"]["excluded_count"], 1)
        self.assertEqual(set(rawcalc["manifest"]["evidence_ids"]), {r["evidence_id"] for r in evidence if not r["excluded"]})
        self.assertEqual(rawcalc["manifest"]["rows_hash"], fingerprint(rawcalc["datasets"][dataset]["rows"]))
        calc = calculation_packet(rawcalc, {"result_id": f"synthetic-result-{method}",
            "task_id": f"synthetic-code-{method}", "raw_hash": fingerprint(rawcalc)}, max_chars=100000)
        rows = calc["datasets"][dataset]["rows"]
        if dataset == "descriptives":
            row = next(r for r in rows if r["scope"] == "overall" and r["variable"] == "duration_seconds")
            chars = next(r for r in rows if r["scope"] == "overall" and r["variable"] == "characters")
            self.assertEqual((row["n"], row["missing"], row["mean"]), (4, 1, 4.25))
            self.assertEqual((chars["n"], chars["missing"], chars["maximum"]), (5, 0, 30))
        elif dataset == "correlations":
            row = next(r for r in rows if {r["variable_a"], r["variable_b"]} == {"duration_seconds", "characters"})
            self.assertEqual((row["n"], row["missing"]), (4, 1))
        else:
            row = next(r for r in rows if type(r.get(column)) in (int, float))
        binding = cell_binding(calc, dataset, row, column)
        self.assertEqual(len(binding), 9)
        rendered = validate_numeric_bindings([binding], [calc])[0]
        self.assertEqual(rendered["value"], row[column])
        if dataset == "crosstabs":
            self.assertEqual(rendered["denominators"]["total_percent"], 5)
        profile = self.registry.freeze({"expert_ids": [expert_id]})["profiles"][expert_id]
        raw = {"summary": "固定セルの説明候補", "claims": [], "analysis_requests": [], "label_patches": [],
            "expert_report": {"expert_id": expert_id, "profile_hash": profile["profile_hash"],
                "knowledge_hash": profile["knowledge_hash"], "status": "draft",
                "outputs": {key: "固定セルだけを参照する探索的な説明候補。欠測と未計算を区別し、独立性と本人採否は未確認。"
                            for key in profile["output_schema"]["properties"]},
                "evidence_ids": [r["evidence_id"] for r in evidence if not r["excluded"]],
                "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                "performed_step_ids": profile["phase_requirements"]["result_explanation"]["ai_draft"],
                "missing_inputs": [], "limitations": "探索的な下書き。研究者の意味判断・採否は未実施。",
                "calculation_result_ids": [calc["result_id"]], "numeric_bindings": [binding]}}
        ids = raw["expert_report"]["evidence_ids"]
        def validate(value):
            return validate_report(profile, value, ids, [calc["result_id"]], calculations=[calc],
                                   response_phase="result_explanation")
        self.assertEqual(validate(raw), [rendered])
        bad = deepcopy(raw)
        bad["expert_report"]["outputs"]["result_explanation"] = negative
        self.assertEqual(validate(bad), [rendered])
        for key in ("dataset_version", "computation_input_hash", "rows_hash"):
            wrong = deepcopy(bad)
            wrong["expert_report"]["numeric_bindings"][0][key] = "wrong"
            with self.assertRaises(AnalysisContractError) as caught:
                validate(wrong)
            self.assertEqual(caught.exception.code, "expert_numeric_binding_mismatch")
        wrong = deepcopy(rawcalc)
        wrong["datasets"][dataset]["rows"][0][column] = 99999
        with self.assertRaises(AnalysisContractError) as caught:
            validate_statistical_result(wrong, task, evidence)
        self.assertEqual(caught.exception.code, "statistics_result_mismatch")
        self.assertEqual(snapshot, before)
        self.record(number, expert_id, analysis,
            "run_orchestration_method -> validate_statistical_result -> calculation_packet -> validate_report",
            "fixed_numeric_cells; accepted_unreviewed_draft", "accepted_unreviewed_draft",
            negative_input=negative, negative_meaning="数値の束縛が正しくても不適切散文は意味検証されない",
            profile_hash=profile["profile_hash"], binding=binding, rendered_cell=rendered,
            normal_response_hash=fingerprint(raw), negative_response_hash=fingerprint(bad),
            calculation_raw_hash=fingerprint(rawcalc), included=5, excluded=1,
            structural_mutations="wrong dataset version/input hash/rows hash and changed calculation row rejected")

    def test_11_descriptive_statistics(self):
        self.statistical_pair(11, "exp-descriptive-statistics", "descriptive_statistics", "descriptives", "mean",
                              "同じ話者の各発話をそれぞれ別人として集計した。")

    def test_12_group_comparison_statistics(self):
        self.statistical_pair(12, "exp-group-comparison-statistics", "crosstabs", "crosstabs", "count",
                              "標準ANOVAの結果はWelch法による群間比較であり、多重比較補正済みである。")

    def test_13_correlation(self):
        self.statistical_pair(13, "exp-correlation", "pearson", "correlations", "coefficient",
                              "Spearmanの近似はこの小標本でも必ず正確であり、説明変数が結果を引き起こした。")

    def code_catalog_pair(self, expert_id, path, value, expected_status, failed_ids):
        analysis = synthetic_analysis(["合成の対象発話"] * 20)
        analysis["automatic"]["data_quality"]["emotion_coverage_percent"] = 80
        analysis["research"] = {"linguistics": {"engine": {"status": "ready", "syntax": "GiNZA"}}}
        analysis["transformer"] = {"result": {"quality": {"silhouette_cosine": .2}}, "stale": False}
        positive = self.catalog.review(expert_id, analysis, context={"session_count": 2})
        self.assertEqual(positive["status"], "ready")
        for check in positive["checks"] + positive["quality_checks"]:
            if check["check"] == "human_review":
                self.assertEqual(check["result"], "human")
        negative = deepcopy(analysis)
        context = {"session_count": 2}
        if path:
            target = negative
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
        else:
            context["session_count"] = value
        rejected = self.catalog.review(expert_id, negative, context=context)
        self.assertEqual(rejected["status"], expected_status)
        self.assertEqual({c["id"] for c in rejected["checks"] if c["result"] == "fail"}, failed_ids)
        self.forbidden(expert_id)
        return {"normal_status": positive["status"], "negative_status": rejected["status"],
                "failed_checks": sorted(failed_ids), "changed_path": list(path), "changed_value": value,
                "meaning_detector": "NOTRUN: Catalog evaluates conditions, not methodological prose"}

    def test_06_kj_method(self):
        eid = "exp-kj-method"
        condition = self.code_catalog_pair(eid, ("automatic", "overview", "included_segment_count"),
                                           0, "blocked", {"kj-a2"})
        analysis = synthetic_analysis(["価格はよいが予約が難しい"])
        normal = self.catalog.review(eid, analysis)
        self.assertNotEqual(normal["status"], "blocked")
        self.assertTrue(all(step["actor"] == "researcher" for step in normal["procedure"]))
        self.record(6, eid, analysis, "Catalog.review + Registry AI refusal",
            "input condition accepted; researcher grouping NOTRUN", "empty input blocked; automatic KJ completion NOTRUN",
            catalog=condition, normal_input="u1の二メッセージを研究者が二ラベル・表札へ整理する設計例",
            negative_input="自動クラスタをKJ完成品、最大の島を最重要意見とする",
            unlock_condition="研究者によるラベル・表札・孤立ラベルの実記録が必要。専用実装なし、AIへの代行許可なし")

    def test_07_quantitative_text_analysis(self):
        from gurumoji import research_analysis as ra
        eid = "exp-quantitative-text-analysis"
        condition = self.code_catalog_pair(eid, ("research", "linguistics", "engine", "status"),
                                           "fallback", "needs_attention", {"qta-a3"})
        segments = [{"id": "u1", "speaker": "A", "text": "費用 費用 費用"},
                    {"id": "u2", "speaker": "B", "text": "費用"}]
        with patch.object(ra, "_load_ginza", return_value=(None, "fixture disabled")), \
             patch.object(ra, "_load_sudachi", return_value=(None, "fixture disabled")):
            result = ra._linguistic_analysis(segments, {})
        self.assertEqual([(r["term_frequency"], r["document_frequency"], r["speaker_frequency"])
                          for r in result["term_frequency"]], [(4, 2, 2)])
        self.assertEqual(result["engine"]["status"], "fallback")
        self.assertIn("研究データとして使用できません", result["engine"]["message"])
        self.record(7, eid, segments, "_linguistic_analysis forced regex fallback + Catalog",
            "TF=4, DF=2, observed speakers=2", "fallback warning; four occurrences do not establish four people",
            catalog=condition, negative_meaning="最多語の重要性・支持人数・共起因果の意味検出はNOTRUN",
            unlock_condition="固定した正式解析器の別受入と、研究者による原文・否定・引用の確認")

    def test_09_participation_balance(self):
        from gurumoji.services import group_analysis as ga
        eid = "exp-participation-balance"
        condition = self.code_catalog_pair(eid, ("automatic", "overview", "speaker_count"),
                                           1, "blocked", {"part-a1"})
        buckets = {speaker: {"speaking_seconds": 30, "turn_count": 1, "timed_turn_count": 1}
                   for speaker in ("A", "B")}
        def balance(labels):
            return ga._participation_balance(buckets, [], participant_labels=labels, balance_labels=labels,
                balance_population=labels, mixed_role_speaker_count=0, exclude_moderator=True)
        normal, single = balance(["A", "B"]), balance(["A"])
        self.assertEqual((normal["gini"], normal["normalized_evenness"], normal["hhi"]), (0, 1, .5))
        self.assertFalse(normal["participant_roster_available"])
        self.assertIsNone(normal["unobserved_participant_count"])
        self.assertEqual((single["gini"], single["normalized_evenness"], single["hhi"], single["metric_status"]),
                         (0, 1, 1, "computed"))
        self.record(9, eid, buckets, "_participation_balance + Catalog",
            "observed A/B each 30 sec: Gini0/evenness1/HHI.5; roster unavailable",
            "singleton helper still computed: 0/1/1; no fairness conclusion", catalog=condition,
            negative_meaning="単独観測値から公平性・全員均等を結論できない。意味判定は人待ち")

    def test_10_conversation_timing(self):
        from gurumoji.services import group_analysis as ga
        eid = "exp-conversation-timing"
        condition = self.code_catalog_pair(eid, ("automatic", "data_quality", "invalid_time_segments"),
                                           11, "blocked", {"time-a1", "time-a2"})
        timeline = [{"id": uid, "speaker": speaker, "speaker_name": speaker, "start": start, "end": end}
            for uid, speaker, start, end in (("u1", "A", 0, 2), ("u2", "B", 5.5, 7), ("u3", "A", 6.5, 8))]
        gaps = ga._long_gaps(timeline, 3)
        overlaps, truncated = ga._overlap_candidates(timeline, .2)
        self.assertEqual([r["seconds"] for r in gaps], [3.5])
        self.assertEqual([(r["seconds"], r["from_segment_id"], r["to_segment_id"]) for r in overlaps],
                         [(.5, "u2", "u3")])
        self.assertFalse(truncated)
        unknown = [dict(row, time_unknown=True) for row in timeline]
        self.assertEqual(ga._long_gaps(unknown, 3), [])
        self.assertEqual(ga._overlap_candidates(unknown, .2), ([], False))
        self.record(10, eid, timeline, "_long_gaps/_overlap_candidates + Catalog",
            "gap3.5 sec and overlap.5 sec candidates", "missing time yields no candidates, not evidence of absence",
            catalog=condition, negative_meaning="重なり=対立／無音=同意という意味検出はNOTRUN",
            provenance_limit="long_gaps output has names/time but no utterance IDs; fixture retains original timeline")

    def test_14_embedding_topic_exploration(self):
        from gurumoji import transformer_analysis as ta
        eid = "exp-embedding-topic-exploration"
        condition = self.code_catalog_pair(eid, ("transformer", "stale"), True, "blocked", {"emb-a1"})
        source = [{"id": "u1", "speaker": "A", "text": "駅まで歩く", "start": 0, "end": 1},
                  {"id": "u2", "speaker": "A", "text": "バスの本数", "start": 2, "end": 3}]
        values, expanded, manifest = ta._contextual_texts(source, [0], include_manifest=True)
        self.assertEqual((values, expanded), (["駅まで歩く バスの本数"], 1))
        self.assertEqual(manifest[0]["context_segment_ids"], ["u1", "u2"])
        other = deepcopy(source)
        other[1]["speaker"] = "B"
        values, expanded, manifest = ta._contextual_texts(other, [0], include_manifest=True)
        self.assertEqual((values, expanded), (["駅まで歩く"], 0))
        self.assertEqual(manifest[0]["context_segment_ids"], ["u1"])
        self.record(14, eid, source, "_contextual_texts + Catalog stale check",
            "same-speaker context expanded with source IDs", "different speaker not concatenated; stale result blocked",
            catalog=condition, negative_meaning="便利／便利でないの近さ=合意、高silhouette=TA成功は未検証",
            unlock_condition="実embedding/clusterはNOTRUN。モデル実行許可と別の意味評価、研究者の代表・境界例確認が必要")

    def test_15_speech_emotion_recognition(self):
        from collections import Counter
        from gurumoji.services.group_analysis import analysis_emotion_entries
        eid = "exp-speech-emotion-recognition"
        condition = self.code_catalog_pair(eid, ("automatic", "data_quality", "emotion_coverage_percent"),
                                           .5, "blocked", {"ser-a1", "ser-a2"})
        labels = ["ang"] * 3 + ["hap"] * 2 + ["sad"] + ["neu"] * 2 + [None, None]
        source = [{"id": f"u{i}", "emotions": {"synthetic-model-fold0": {"label": label, "model_name": "synthetic"}} if label else {}}
                  for i, label in enumerate(labels)]
        parsed = [analysis_emotion_entries(row) for row in source]
        observed = Counter(row["label"] for group in parsed for row in group)
        self.assertEqual(observed, {"ang": 3, "hap": 2, "sad": 1, "neu": 2})
        self.assertEqual(sum(bool(group) for group in parsed), 8)
        self.assertEqual(sum(not group for group in parsed), 2)
        self.assertEqual(analysis_emotion_entries({"emotions": {"synthetic": {"label": ""}}}), [])
        self.record(15, eid, source, "analysis_emotion_entries + Catalog coverage check",
            "synthetic labels ang3/hap2/sad1/neu2; observed8/10, missing2",
            "empty label remains absent; .5 percent fails existing min1 check", catalog=condition,
            negative_meaning="分類ang=本人の怒り／model card精度=会話精度の意味検出はNOTRUN",
            unlock_condition="実音声・モデル推論はNOTRUN。別許可と参照ラベル・聴取者・領域差の評価が必要")

    def test_16_japanese_text_preprocessing(self):
        from gurumoji import research_analysis as ra
        eid = "exp-japanese-text-preprocessing"
        condition = self.code_catalog_pair(eid, ("research", "linguistics", "engine"),
            {"status": "fallback", "syntax": "利用不可"}, "needs_attention", {"pre-a1", "pre-a2"})
        text = "ええと、予約は、取り直しました"
        segments = [{"id": "u1", "speaker": "A", "text": text}]
        morphemes, _ = ra._analyze_with_fallback(segments, set())
        self.assertTrue(morphemes)
        self.assertTrue(all(text[r["begin"]:r["end"]] == r["surface"] for r in morphemes))
        self.assertTrue(all(r["segment_id"] == "u1" and r["pos_detail"] == "簡易文字種分割" for r in morphemes))
        with patch.object(ra, "_load_ginza", return_value=(None, "fixture disabled")), \
             patch.object(ra, "_load_sudachi", return_value=(None, "fixture disabled")):
            fallback = ra._linguistic_analysis(segments, {})
        self.assertEqual(fallback["engine"]["status"], "fallback")
        self.assertEqual(fallback["dependencies"], [])
        self.record(16, eid, segments, "_analyze_with_fallback/_linguistic_analysis + Catalog",
            "regex surface offsets and u1 retained", "fallback/syntax unavailable distinguished; empty edges not absence",
            catalog=condition, unlock_condition="正式GiNZA/Sudachiの形態素・構文精度はNOTRUN。固定モデル/辞書の別受入と原文監査が必要")

    def test_17_cross_session_comparison(self):
        from collections import Counter
        from gurumoji.services.interview_comparison import build_interview_comparison
        eid = "exp-cross-session-comparison"
        condition = self.code_catalog_pair(eid, (), 1, "blocked", {"cmp-a1"})
        rows = [{"id": sid, "source_name": sid} for sid in ("A", "B")]
        def analysis(sad_count, coverage):
            return {"segments": [{"id": f"u{i}", "text": "費用"} for i in range(100)], "config": {},
                "automatic": {"overview": {}, "data_quality": {"emotion_coverage_percent": coverage},
                    "emotions": [{"model": "fixture", "label": "sad", "count": sad_count}]}, "manual": {}}
        analyses = {"A": analysis(20, 100), "B": analysis(20, 100)}
        kwargs = {"allow_different_content": False, "row_session_profile": lambda row: {},
            "interview_comparison_identity": lambda profile: ("same", "same", "fixture"),
            "group_analysis_for_row": lambda row: analyses[row["id"]], "text_mining_counter": lambda *args: Counter()}
        normal = build_interview_comparison(rows, **kwargs)
        self.assertEqual([r["rate_per_100_segments"] for r in normal["emotion_comparison"][0]["interviews"]], [20, 20])
        analyses["B"] = analysis(1, 5)
        negative = build_interview_comparison(rows, **kwargs)
        self.assertEqual([r["rate_per_100_segments"] for r in negative["emotion_comparison"][0]["interviews"]], [20, 1])
        self.assertTrue(all("emotion_coverage_percent" not in row for row in negative["interviews"]))
        self.record(17, eid, analyses, "build_interview_comparison injected synthetic aggregates + Catalog",
            "same coverage A/B returns20/20 per100", "different coverage returns20/1; coverage is not propagated",
            catalog=condition, negative_meaning="推定済み内では両者20%。この値だけで感情差や独立性を結論できない",
            unlock_condition="反復参加者の独立性と質問設計は研究者確認待ち。上流推論・実比較保存はNOTRUN")


if __name__ == "__main__":
    unittest.main()
