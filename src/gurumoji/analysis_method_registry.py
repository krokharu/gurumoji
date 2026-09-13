"""Versioned output contracts for saved text-analysis results."""
from __future__ import annotations

REGISTRY_VERSION = "text-analysis-store-5"

COMMON_EXPORT_FIELDS = {
    "schema_version", "item_id", "source_name", "revision_count", "analysis_revision",
    "analysis_updated_at", "generated_at", "algorithm_version",
}

PREVIEW_FIELD_PRIORITIES = {
    "transformer_topics": [
        "topic_id", "label", "keywords", "segment_count", "speaker_count",
        "backchannel_count", "average_similarity", "representative_segment_ids",
    ],
    "transformer_assignments": [
        "speaker_name", "topic_label", "start", "end", "similarity", "text", "segment_id",
    ],
    "transformer_backchannels": [
        "speaker_name", "kind", "text", "topic_label", "responds_to_speaker_name",
        "time_gap", "link_method", "segment_id",
    ],
    "transformer_backchannel_rates": [
        "speaker_name", "speaker_group", "topic_label", "opportunity_count",
        "responded_target_count", "response_rate_percent", "backchannel_count",
        "backchannels_per_100_opportunities",
    ],
    "transformer_backchannel_tests": [
        "test", "dimension", "n", "p_value", "effect_size", "status",
        "interpretation", "assumption_note",
    ],
    "transformer_speaker_results": [
        "speaker_name", "result_label", "topic_label", "confidence", "basis",
        "matched_cues", "evidence_texts", "evidence_segment_ids",
    ],
}


def preview_fields(dataset: str, fields: list[str]) -> list[str]:
    selected = [field for field in PREVIEW_FIELD_PRIORITIES.get(dataset, []) if field in fields]
    selected.extend(field for field in fields if field not in COMMON_EXPORT_FIELDS and field not in selected)
    return selected[:8]


METHODS = [
    ("local_insights", "ローカル見解", ["insights"]),
    ("speaker_characteristics", "話者別特徴語", ["characteristic_terms"]),
    ("transformer_topics", "Transformerテーマ分析", ["transformer_topics", "transformer_assignments", "transformer_speakers", "transformer_timeline", "transformer_outliers", "transformer_backchannels", "transformer_backchannel_speakers", "transformer_backchannel_rates", "transformer_backchannel_tests", "transformer_speaker_results"]),
    ("participation", "発話量・参加バランス", ["speakers", "groups", "summary", "observations"]),
    ("conversation_dynamics", "会話の時間構造", ["transitions", "gaps", "overlaps", "timeline"]),
    ("morphology", "形態素・品詞", ["morphemes", "pos_frequency"]),
    ("syntax", "係り受け", ["dependencies"]),
    ("lexical_frequency", "語彙頻度", ["term_frequency", "keywords"]),
    ("cooccurrence", "共起", ["cooccurrence"]),
    ("descriptive_statistics", "記述統計・度数", ["descriptives", "frequencies"]),
    ("group_statistics", "クロス集計・群間比較", ["crosstabs", "statistical_tests"]),
    ("correlation", "相関", ["correlations"]),
    ("qualitative_coding", "手動コード・重要引用", ["codes", "coded_segments", "case_matrix", "interactions", "important_quotes", "context"]),
    ("ai_insights", "AI見解・下書き", ["insights"]),
    ("audio_emotion", "音声感情推定", ["emotions"]),
    ("outline", "議題・アウトライン", []),
    ("kwic", "文脈検索", ["kwic"]),
    ("ai_finishing", "AI仕上げ・変更記録", ["ai_changes"]),
]

# Navigation categories describe the implemented methods, not external engines.
METHOD_GROUPS = [
    ("text", "KH Coder系・計量テキスト分析",
     "語彙頻度・共起・特徴語・文脈を比較します。KH Coderの考え方を参照した独自実装で、KH Coder本体の出力ではありません。",
     ("local_insights", "morphology", "syntax", "lexical_frequency", "cooccurrence", "speaker_characteristics", "kwic")),
    ("transformer", "Transformer系・意味分析",
     "多言語E5による本文テーマ分析と、HuBERT・wav2vec 2.0による音声感情推定を確認します。",
     ("transformer_topics", "audio_emotion")),
    ("ai", "生成AI・アウトライン・仕上げ",
     "AI見解、議題・アウトライン、文字起こしの仕上げ記録を確認します。",
     ("ai_insights", "outline", "ai_finishing")),
    ("statistics", "統計・群間比較",
     "記述統計、クロス集計、群間比較、相関を確認します。",
     ("descriptive_statistics", "group_statistics", "correlation")),
    ("conversation", "会話構造・参加バランス",
     "発話量、話者交替、間、重なりなど会話の構造を確認します。",
     ("participation", "conversation_dynamics")),
    ("qualitative", "質的分析・コード・引用",
     "手動コードと重要引用を、元の発言や文脈と合わせて確認します。",
     ("qualitative_coding",)),
]

METHOD_STATUS_LABELS = {
    "completed": "結果あり", "empty": "データなし", "not_run": "未実行",
    "unavailable": "利用不可", "fallback": "簡易解析", "stale": "更新が必要",
    "partial": "一部完了",
}


def method_status_label(method: dict) -> str:
    status = METHOD_STATUS_LABELS.get(method.get("status"), str(method.get("status") or "状態不明"))
    return status + ("／入力変更後・再確認が必要" if method.get("stale") else "")


def transformer_note_content(result: dict) -> tuple[list[dict], list[dict]]:
    """Create searchable summaries and evidence-linked findings for the Vault note."""
    findings: list[dict] = []
    summaries: list[dict] = []
    for topic in result.get("topics", []):
        segment_ids = [str(value) for value in topic.get("representative_segment_ids", []) if value]
        if segment_ids:
            findings.append({
                "title": f"テーマ {topic.get('topic_id', '')}：{topic.get('label', '')}",
                "text": (
                    f"{topic.get('segment_count', 0)}発話、{topic.get('speaker_count', 0)}話者、"
                    f"相づち{topic.get('backchannel_count', 0)}件。"
                ),
                "segment_ids": segment_ids,
            })
    kind_labels = {"agreement": "同意的応答", "continuer": "継続促進",
                   "confirmation": "確認", "courtesy": "謝意"}
    for row in result.get("backchannels", []):
        segment_ids = [str(value) for value in (
            row.get("segment_id"), row.get("responds_to_segment_id"),
        ) if value]
        if segment_ids:
            findings.append({
                "title": f"相づち：{row.get('speaker_name', row.get('speaker', ''))}／{row.get('topic_label', '紐付けなし')}",
                "text": (
                    f"種類：{kind_labels.get(row.get('kind'), row.get('kind', '応答'))}。"
                    f"相づち本文：{row.get('text', '')}。"
                    f"応答先：{row.get('responds_to_speaker_name') or '推定できず'}。"
                ),
                "segment_ids": segment_ids,
            })
    for row in result.get("speaker_results", []):
        segment_ids = [str(value) for value in row.get("evidence_segment_ids", []) if value]
        if segment_ids:
            findings.append({
                "title": f"話者別リザルト：{row.get('speaker_name', row.get('speaker', ''))}／{row.get('result_label', '')}",
                "text": f"対象話題：{row.get('topic_label', '紐付けなし')}。{row.get('basis', '')}",
                "segment_ids": segment_ids,
            })
    for row in result.get("backchannel_rates", []):
        if row.get("scope") != "overall" or row.get("speaker_group") != "participant":
            continue
        rate = row.get("response_rate_percent")
        summaries.append({
            "title": f"相づち応答率：{row.get('speaker_name', row.get('speaker', ''))}",
            "text": (
                f"反応機会{row.get('opportunity_count', 0)}件、応答した対象発話"
                f"{row.get('responded_target_count', 0)}件、応答率"
                f"{'算出不能' if rate is None else str(rate) + '%'}、相づち総数{row.get('backchannel_count', 0)}件。"
            ),
        })
    for row in result.get("backchannel_tests", []):
        p_value = row.get("p_value")
        effect = row.get("effect_size")
        summaries.append({
            "title": f"相づち統計：{row.get('test', '')}",
            "text": (
                f"状態：{row.get('status', '')}。p値：{'算出不能' if p_value is None else p_value}。"
                f"Cramér's V：{'算出不能' if effect is None else effect}。"
                f"{row.get('interpretation', '')} {row.get('assumption_note', '')}"
            ),
        })
    return findings, summaries


def method_results(analysis: dict, datasets: dict, *, outline: dict | None = None,
                   finishing: dict | None = None, kwic: dict | None = None) -> list[dict]:
    research = analysis.get("research", {})
    engine = research.get("linguistics", {}).get("engine", {})
    insights = analysis.get("insights", {})
    results = []
    for key, title, tables in METHODS:
        if key == "kwic" and kwic is None or key == "ai_finishing" and finishing is None:
            continue
        findings = []
        summaries = []
        details = {}
        if key == "local_insights": findings = insights.get("local", [])
        if key == "ai_insights":
            details = insights.get("ai") or {}
            findings = details.get("findings", [])
        if key == "outline": details = outline or {}
        if key == "ai_finishing": details = finishing or {}
        if key == "kwic": details = kwic or {}
        selected = [name for name in tables if name in datasets]
        count = sum(len(datasets[name][1]) for name in selected)
        state = "completed" if count or findings or details else "empty"
        if key in {"ai_insights", "outline"} and not details: state = "not_run"
        if key == "transformer_topics":
            details = analysis.get("transformer", {})
            if not details.get("result"):
                state = "not_run"
            elif details.get("stale"):
                state = "stale"
            if details.get("result"):
                findings, summaries = transformer_note_content(details["result"])
        if key == "ai_insights" and insights.get("stale"): state = "stale"
        if key == "outline" and details.get("evidence"):
            current = {s['id']: s for s in analysis.get('segments', []) if not s.get('excluded')}
            if any(sid not in current or any(current[sid].get(k) != evidence.get(k) for k in ('text', 'speaker', 'start', 'end'))
                   for sid, evidence in details['evidence'].items()): state = "stale"
        if key in {"morphology", "lexical_frequency", "cooccurrence", "speaker_characteristics"} and engine.get("status") == "fallback":
            state = "fallback"
        if key == "syntax" and (not engine.get("syntax") or str(engine["syntax"]).startswith("利用不可")):
            state = "unavailable"
        if key == "ai_finishing" and "failed" in details.get("stages", {}).values(): state = "partial"
        method_engine = engine if key in {"morphology", "syntax", "lexical_frequency", "cooccurrence", "speaker_characteristics"} else {}
        limitations = research.get("limitations", analysis.get("cautions", []))
        if key == "transformer_topics" and details.get("result"):
            method_engine = details["result"].get("engine", {})
            limitations = details["result"].get("limitations", limitations)
        if key in {"descriptive_statistics", "group_statistics", "correlation"}:
            method_engine = research.get("statistics", {}).get("engine", {})
            if key in {"group_statistics", "correlation"} and method_engine.get("status") == "unavailable": state = "unavailable"
        unit = {"morphology": "形態素", "syntax": "形態素間の係り受け", "kwic": "出現箇所",
                "speaker_characteristics": "本文のある対象発話"}.get(key, research.get("analysis_unit", "発話"))
        if key == "transformer_topics" and details.get("result"):
            unit = details["result"].get("analysis_unit", unit)
        previews = [{"dataset": name, "fields": preview_fields(name, datasets[name][0]),
                     "rows": datasets[name][1][:10], "total": len(datasets[name][1])}
                    for name in selected if datasets[name][1] and key not in {"local_insights", "ai_insights", "kwic", "ai_finishing"}]
        results.append({"method_id": key, "method_version": REGISTRY_VERSION, "title": title,
                        "status": state, "datasets": selected, "findings": findings,
                        "summaries": summaries, "details": details, "previews": previews,
                        "analysis_unit": unit, "engine": method_engine,
                        "limitations": limitations})
    return results
