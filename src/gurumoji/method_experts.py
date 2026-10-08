"""Method-specific expert definitions read from the Software Vault at run time.

The canonical knowledge lives in ``docs/program-vault/50-Analysis-Methods/10-Experts``: one
folder per expert, whose ``01-Expert.md`` holds a machine-readable execution definition.
Only the experts selected for the analysis at hand are parsed. Their knowledge notes and the
literature notes they cite are hashed so that saved results can tell when the knowledge
changed; the optional specialist-agent reader renders bounded excerpts separately. Experts are definitions that
constrain procedure and explanation, not retrained models.

A second, local-only tree under ``LOCAL_KNOWLEDGE_DIR`` (outside the git-tracked Software
Vault) can add experts or literature notes, or shadow a base note by relative path, so each
installation can extend the shared knowledge without committing it. See ADR-120.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import yaml

from .analysis_method_registry import method_status_label
from .obsidian_layout import unpack
from .vault_registry import SOFTWARE_ROOT

SCHEMA_VERSION = 1
EXPERTS_DIR = Path("50-Analysis-Methods") / "10-Experts"
LITERATURE_DIR = Path("50-Analysis-Methods") / "20-Literature"
COMMON_DIR = Path("50-Analysis-Methods") / "08-Common-Knowledge"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_KNOWLEDGE_DIR = Path(
    os.environ.get("MOJIOKOSI_DATA_DIR", str(_PROJECT_ROOT / "runtime" / "data"))
) / "local_knowledge"
DEFINITION_NOTE = "01-Expert.md"
KNOWLEDGE_NOTES = ("00-Overview.md", "01-Expert.md", "02-Procedure.md", "03-Quality.md",
                   "04-Applicability-and-Limits.md", "05-Cases.md", "06-Open-Issues.md")
IMPLEMENTATION_BASIS = "implementation"
ROLE_LABELS = {"methodology": "方法論", "computational": "計算", "preprocessing": "前処理", "comparison": "比較"}
ACTOR_LABELS = {"researcher": "研究者", "code": "コード", "ai_draft": "AI下書き（研究者が確認）"}
SELECTION_LABELS = {"researcher": "研究者が選択", "provisional": "暫定（主手法が未選択）",
                    "plan": "分析方針の補助案", "result": "保存した手法結果",
                    "current": "現在のデータに対する確認", "preconditions": "実行前に確認する条件"}
STATUS_LABELS = {"ready": "適用条件を満たす", "needs_attention": "確認が必要",
                 "blocked": "この条件では分析を始めない", "definition_error": "専門家定義を読み込めない",
                 "definition_missing": "対応する専門家定義がない"}
RESULT_LABELS = {"pass": "満たす", "fail": "満たさない", "not_evaluable": "判定できない", "human": "研究者が確認"}
PRODUCED_STATES = {"completed", "fallback", "stale", "partial"}
REQUIRED_KEYS = (
    "expert_id", "definition_version", "knowledge_verified", "title", "role", "analysis_method_ids",
    "registry_method_ids", "school", "scope", "out_of_scope", "analysis_unit", "required_inputs",
    "applicability_checks", "procedure", "quality_checks", "prohibited_conclusions", "output_sections",
    "ai_assist", "literature", "common_notes", "open_issues", "readiness",
)
READINESS_KEYS = ("literature_checked", "procedure_documented", "integrated", "sample_verified")
REFERENCE_ID = re.compile(r"\A(?:LIT|RES)-[A-Za-z0-9][A-Za-z0-9-]*\Z")
EXPERT_ID = re.compile(r"\Aexp-[a-z0-9][a-z0-9-]*\Z")
ITEM_ID = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")
DEFINITION_BLOCK = re.compile(r"^## 実行定義[ \t]*\n+```yaml[ \t]*\n(.*?)\n```[ \t]*$", re.S | re.M)
EXPECTED_CELLS = re.compile(r"期待度数5未満: (\d+)/(\d+)セル")


class ExpertDefinitionError(ValueError):
    pass


class SkillContextError(ExpertDefinitionError):
    def __init__(self, reason, *, decision="blocked"):
        super().__init__("固定skill資料の取得条件を確認してください：" + reason)
        self.code, self.decision = "expert_skill_" + reason, decision


def _skill_range(body, name, native=None):
    """Exact native block/explicit section; never expand a missing block."""
    lines = body.splitlines()
    positions = {}
    in_fence = False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
        match = re.fullmatch(r"\^([A-Za-z0-9-]+)\s*", line) if not in_fence else None
        if match:
            if match[1] in positions: raise SkillContextError("duplicate_block_id")
            positions[match[1]] = i
    if in_fence: raise SkillContextError("malformed_fence")
    if native is None:
        matches = [(i, len(m[1])) for i, line in enumerate(lines)
                   if (m := re.fullmatch(r"(#{1,6})\s+(.+?)\s*", line)) and m[2] == name]
        if len(matches) != 1:
            raise SkillContextError("section_missing_or_ambiguous", decision="needs_input")
        start, level = matches[0]
        end = next((i for i in range(start + 1, len(lines))
                    if (m := re.match(r"^(#{1,6})\s", lines[i])) and len(m[1]) <= level), len(lines))
        if not any(line.strip() for line in lines[start + 1:end]):
            raise SkillContextError("section_empty", decision="needs_input")
        return "\n".join(lines[start:end]).strip()
    if native not in {"quote", "table", "paragraph"} or name not in positions:
        raise SkillContextError("block_missing", decision="needs_input")
    marker = positions[name]
    if marker < 2 or lines[marker - 1].strip(): raise SkillContextError("block_boundary")
    end = marker - 1
    while end and not lines[end - 1].strip(): end -= 1
    start = end
    if native == "quote":
        while start and (lines[start - 1] == ">" or lines[start - 1].startswith("> ")): start -= 1
    elif native == "table":
        while start and lines[start - 1].startswith("|"): start -= 1
    else:
        while start and lines[start - 1].strip(): start -= 1
    selected = lines[start:end]
    if not selected: raise SkillContextError("block_empty", decision="needs_input")
    if native == "table" and (len(selected) < 3 or not re.fullmatch(r"\|[\s|:\-]+\|", selected[1])):
        raise SkillContextError("malformed_table")
    if native == "quote" and sum(bool(re.match(r"^>\s*```", line)) for line in selected) % 2:
        raise SkillContextError("malformed_quote")
    if native == "paragraph" and any(re.match(r"^(?:#|\||>|```|\^)", line) for line in selected):
        raise SkillContextError("malformed_paragraph")
    return "\n".join(selected)


def _nested(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _text(value: Any) -> str:
    return str(value or "").strip()


# Each check reads only values the analysis already computed. It returns a result
# (pass / fail / not_evaluable) and the observed values, never a judgement of meaning.
def _research_question(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    question = _text(_nested(analysis, "config", "research_question"))
    objective = _text(_nested(analysis, "item", "session_profile", "objective"))
    ok = bool(question) or (bool(objective) and params.get("allow_objective", True))
    return ("pass" if ok else "fail"), {"research_question": bool(question), "objective": bool(objective)}


def _present(*path: str) -> Callable[[dict, dict, dict], tuple[str, dict]]:
    def check(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
        value = _text(_nested(analysis, *path))
        return ("pass" if value else "fail"), {path[-1]: bool(value)}
    return check


def _bounded(path: tuple[str, ...], bound: str) -> Callable[[dict, dict, dict], tuple[str, dict]]:
    def check(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
        value = _number(_nested(analysis, *path))
        limit = float(params[bound])
        if value is None:
            return "not_evaluable", {path[-1]: None, bound: params[bound]}
        ok = value >= limit if bound == "min" else value <= limit
        return ("pass" if ok else "fail"), {path[-1]: value, bound: params[bound]}
    return check


def _preparation(analysis: dict) -> dict | None:
    value = _nested(analysis, "manual", "preparation")
    return value if isinstance(value, dict) and value else None


def _preparation_confirmed(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    preparation = _preparation(analysis)
    if preparation is None:
        return "not_evaluable", {}
    return ("pass" if preparation.get("status") == "confirmed" else "fail"), {"status": preparation.get("status")}


def _analysis_basis_current(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    preparation = _preparation(analysis)
    if preparation is None:
        return "not_evaluable", {}
    stale = bool(preparation.get("analysis_needs_review"))
    return ("fail" if stale else "pass"), {"analysis_needs_review": stale}


def _speaker_order_confirmed(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    preparation = _preparation(analysis)
    if preparation is None:
        return "not_evaluable", {}
    unknown = _number(preparation.get("unknown_speaker_turns"))
    ordered = bool(preparation.get("order_verified"))
    return ("pass" if ordered and unknown == 0 else "fail"), {"order_verified": ordered, "unknown_speaker_turns": unknown}


def _ratio(numerator_path: tuple[str, ...], bound: str, invert: bool) -> Callable[[dict, dict, dict], tuple[str, dict]]:
    def check(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
        count = _number(_nested(analysis, "automatic", "overview", "segment_count"))
        part = _number(_nested(analysis, *numerator_path))
        if not count or part is None:
            return "not_evaluable", {"segment_count": count}
        ratio = round((1 - part / count) if invert else part / count, 4)
        ok = ratio >= float(params[bound]) if bound == "min" else ratio <= float(params[bound])
        return ("pass" if ok else "fail"), {"ratio": ratio, bound: params[bound]}
    return check


def _codebook(analysis: dict) -> list[dict]:
    codes = _nested(analysis, "manual", "codebook")
    return [code for code in codes if isinstance(code, dict)] if isinstance(codes, list) else []


def _codebook_min_codes(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    count = len(_codebook(analysis))
    return ("pass" if count >= int(params["min"]) else "fail"), {"codes": count, "min": params["min"]}


def _codebook_definitions(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    codes = _codebook(analysis)
    missing = sum(1 for code in codes if not _text(code.get("description")))
    return ("pass" if codes and not missing else "fail"), {"codes": len(codes), "without_definition": missing}


def _interaction_links(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    links = _nested(analysis, "manual", "interaction_links")
    count = sum(1 for link in links if isinstance(link, dict) and link.get("status") != "missing_target") \
        if isinstance(links, list) else 0
    return ("pass" if count >= int(params["min"]) else "fail"), {"links": count, "min": params["min"]}


def _comparison_axis(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    group_by = _text(_nested(analysis, "config", "group_by"))
    comparison = _text(_nested(analysis, "item", "session_profile", "comparison_group"))
    ok = group_by not in {"", "none"} or bool(comparison)
    return ("pass" if ok else "fail"), {"group_by": group_by or "none", "comparison_group": bool(comparison)}


def _statistics_engine_ready(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    status = _nested(analysis, "research", "statistics", "engine", "status")
    if status is None:
        return "not_evaluable", {}
    return ("pass" if status == "ready" else "fail"), {"status": status}


def _chi_square_expected(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    tests = _nested(analysis, "research", "statistics", "tests")
    ratios = []
    for row in tests if isinstance(tests, list) else []:
        match = EXPECTED_CELLS.search(str(row.get("assumption_note") or "")) if isinstance(row, dict) else None
        if match and int(match[2]) > 0:
            ratios.append(int(match[1]) / int(match[2]))
    if not ratios:
        return "not_evaluable", {}
    worst = round(max(ratios), 4)
    return ("pass" if worst <= float(params["max_low_ratio"]) else "fail"), {
        "worst_low_expected_ratio": worst, "max_low_ratio": params["max_low_ratio"], "tables": len(ratios)}


def _morphology_engine(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    status = _nested(analysis, "research", "linguistics", "engine", "status")
    if status is None:
        return "not_evaluable", {}
    return ("pass" if status != "fallback" else "fail"), {"status": status}


def _syntax_available(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    engine = _nested(analysis, "research", "linguistics", "engine")
    if not isinstance(engine, dict):
        return "not_evaluable", {}
    syntax = _text(engine.get("syntax"))
    return ("pass" if syntax and not syntax.startswith("利用不可") else "fail"), {"syntax": syntax or None}


def _transformer_current(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    transformer = analysis.get("transformer")
    if not isinstance(transformer, dict):
        return "not_evaluable", {}
    present = bool(transformer.get("result"))
    stale = bool(transformer.get("stale"))
    return ("pass" if present and not stale else "fail"), {"result": present, "stale": stale}


def _silhouette(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    value = _number(_nested(analysis, "transformer", "result", "quality", "silhouette_cosine"))
    if value is None:
        return "not_evaluable", {}
    return ("pass" if value >= float(params["min"]) else "fail"), {"silhouette_cosine": value, "min": params["min"]}


def _session_count(analysis: dict, params: dict, context: dict) -> tuple[str, dict]:
    count = _number(context.get("session_count"))
    if count is None:
        return "not_evaluable", {}
    return ("pass" if count >= float(params["min"]) else "fail"), {"session_count": count, "min": params["min"]}


CHECKS: dict[str, tuple[Callable[[dict, dict, dict], tuple[str, dict]], tuple[str, ...]]] = {
    "research_question_present": (_research_question, ()),
    "method_rationale_present": (_present("config", "method_rationale"), ()),
    "moderator_guide_present": (_present("item", "session_profile", "moderator_guide"), ()),
    "min_included_segments": (_bounded(("automatic", "overview", "included_segment_count"), "min"), ("min",)),
    "max_included_segments": (_bounded(("automatic", "overview", "included_segment_count"), "max"), ("max",)),
    "min_speakers": (_bounded(("automatic", "overview", "speaker_count"), "min"), ("min",)),
    "min_participants": (_bounded(("automatic", "overview", "participant_count"), "min"), ("min",)),
    "preparation_confirmed": (_preparation_confirmed, ()),
    "analysis_basis_current": (_analysis_basis_current, ()),
    "speaker_order_confirmed": (_speaker_order_confirmed, ()),
    "valid_time_ratio_min": (_ratio(("automatic", "data_quality", "invalid_time_segments"), "min", True), ("min",)),
    "unknown_speaker_ratio_max": (_ratio(("automatic", "data_quality", "unknown_speaker_segments"), "max", False), ("max",)),
    "codebook_min_codes": (_codebook_min_codes, ("min",)),
    "codebook_definitions_complete": (_codebook_definitions, ()),
    "coded_segments_min": (_bounded(("manual", "coded_segment_count"), "min"), ("min",)),
    "interaction_links_min": (_interaction_links, ("min",)),
    "comparison_axis_present": (_comparison_axis, ()),
    "statistics_engine_ready": (_statistics_engine_ready, ()),
    "statistics_min_groups": (_bounded(("research", "statistics", "group_count"), "min"), ("min",)),
    "chi_square_expected_cells": (_chi_square_expected, ("max_low_ratio",)),
    "morphology_engine_ready": (_morphology_engine, ()),
    "syntax_available": (_syntax_available, ()),
    "transformer_result_current": (_transformer_current, ()),
    "transformer_silhouette_min": (_silhouette, ("min",)),
    "emotion_coverage_min": (_bounded(("automatic", "data_quality", "emotion_coverage_percent"), "min"), ("min",)),
    "comparison_sessions_min": (_session_count, ("min",)),
}


def validate_definition(definition: Any, *, folder: str, props: dict | None = None) -> list[str]:
    """Return every contract violation of an execution definition (empty when valid)."""
    if not isinstance(definition, dict):
        return ["実行定義がYAMLのオブジェクトではありません。"]
    errors = [f"{key} がありません。" for key in REQUIRED_KEYS if key not in definition]
    if errors:
        return errors
    expert_id = str(definition["expert_id"])
    if not EXPERT_ID.match(expert_id) or expert_id != f"exp-{folder}":
        errors.append("expert_id がフォルダー名と一致しません。")
    if not isinstance(definition["definition_version"], int) or definition["definition_version"] < 1:
        errors.append("definition_version は1以上の整数にしてください。")
    if props is not None:
        for key in ("expert_id", "definition_version", "knowledge_verified", "title", "role",
                    "analysis_method_ids", "registry_method_ids"):
            if props.get(key) != definition.get(key):
                errors.append(f"プロパティと実行定義の {key} が一致しません。")
    if definition["role"] not in ROLE_LABELS:
        errors.append("role が不正です。")
    for key in ("analysis_method_ids", "registry_method_ids", "scope", "required_inputs",
                "prohibited_conclusions", "output_sections", "open_issues", "common_notes", "literature"):
        if not isinstance(definition[key], list) or not all(isinstance(value, str) and value for value in definition[key]):
            errors.append(f"{key} は文字列の一覧にしてください。")
    literature = set(definition["literature"]) if isinstance(definition["literature"], list) else set()
    errors += [f"文献IDの形式が不正です：{value}" for value in literature if not REFERENCE_ID.match(str(value))]
    if not definition["literature"]:
        errors.append("literature が空です。")

    def basis(owner: str, values: Any) -> None:
        if not isinstance(values, list) or not values:
            errors.append(f"{owner}：basis が空です。")
            return
        errors.extend(f"{owner}：文献一覧にない根拠です：{value}" for value in values
                      if value != IMPLEMENTATION_BASIS and value not in literature)

    seen: set[str] = set()

    def identifier(owner: str, value: Any) -> None:
        if not isinstance(value, str) or not ITEM_ID.match(value):
            errors.append(f"{owner}：id の形式が不正です。")
        elif value in seen:
            errors.append(f"{owner}：id が重複しています：{value}")
        else:
            seen.add(value)

    def check_spec(owner: str, spec: Any, *, quality: bool) -> None:
        if not isinstance(spec, dict):
            errors.append(f"{owner} がオブジェクトではありません。")
            return
        identifier(owner, spec.get("id"))
        name = spec.get("check")
        if name != "human_review" and name not in CHECKS:
            errors.append(f"{owner}：登録されていない判定です：{name}")
        elif name in CHECKS:
            params = spec.get("params") or {}
            missing = [key for key in CHECKS[name][1] if key not in params]
            if missing:
                errors.append(f"{owner}：判定のパラメーターがありません：{missing}")
        if quality:
            if not _text(spec.get("text")):
                errors.append(f"{owner}：text がありません。")
        else:
            if spec.get("severity") not in {"block", "warn"}:
                errors.append(f"{owner}：severity は block か warn にしてください。")
            if not _text(spec.get("message")):
                errors.append(f"{owner}：message がありません。")
        basis(owner, spec.get("basis"))

    for spec in definition["applicability_checks"] if isinstance(definition["applicability_checks"], list) else []:
        check_spec("applicability_checks", spec, quality=False)
    steps: dict[str, dict] = {}
    for step in definition["procedure"] if isinstance(definition["procedure"], list) else []:
        if not isinstance(step, dict):
            errors.append("procedure の段階がオブジェクトではありません。")
            continue
        identifier("procedure", step.get("id"))
        if not _text(step.get("title")) or step.get("actor") not in ACTOR_LABELS:
            errors.append(f"procedure {step.get('id')}：title または actor が不正です。")
        basis(f"procedure {step.get('id')}", step.get("basis"))
        steps[str(step.get("id"))] = step
    if not steps:
        errors.append("procedure が空です。")
    for spec in definition["quality_checks"] if isinstance(definition["quality_checks"], list) else []:
        check_spec("quality_checks", spec, quality=True)
    assist = definition["ai_assist"]
    if not isinstance(assist, dict) or not isinstance(assist.get("allowed"), bool):
        errors.append("ai_assist.allowed は true か false にしてください。")
    else:
        assist_steps = assist.get("steps") or []
        for step_id in assist_steps:
            step = steps.get(step_id)
            if step is None or step.get("actor") != "ai_draft":
                errors.append(f"ai_assist.steps：AI下書きの段階ではありません：{step_id}")
            elif not any(REFERENCE_ID.match(str(value)) for value in step.get("basis") or []):
                errors.append(f"ai_assist.steps：文献の根拠がない段階です：{step_id}")
        if assist["allowed"] and (not assist_steps or not _text(assist.get("brief")) or len(_text(assist.get("brief"))) > 1500):
            errors.append("AI補助を許可する場合は steps と1500文字以内の brief が必要です。")
        if not assist["allowed"] and (assist_steps or not _text(assist.get("reason"))):
            errors.append("AI補助を許可しない場合は steps を空にし、reason を書いてください。")
    school = definition["school"]
    if not isinstance(school, dict) or not isinstance(school.get("default"), dict) or not _text(school["default"].get("label")):
        errors.append("school.default に id と label が必要です。")
    elif not isinstance(school.get("alternatives", []), list):
        errors.append("school.alternatives は一覧にしてください。")
    for item in definition["out_of_scope"] if isinstance(definition["out_of_scope"], list) else [None]:
        if not isinstance(item, dict) or not _text(item.get("text")) or (
                item.get("handoff") is not None and not EXPERT_ID.match(str(item.get("handoff")))):
            errors.append("out_of_scope の項目には text と、必要なら専門家IDの handoff を書いてください。")
    readiness = definition["readiness"]
    if not isinstance(readiness, dict) or any(not isinstance(readiness.get(key), bool) for key in READINESS_KEYS):
        errors.append("readiness には4つの真偽値が必要です。")
    if not _text(definition["analysis_unit"]):
        errors.append("analysis_unit がありません。")
    return errors


SKILL_CONTEXT_VERSION = "expert-skill-context-1"
# Fixed Software Vault registrations; these never register executable methods.
SKILL_NOTE_REFS = json.loads(r'''{
  "data-analysis-asset-connection-v1": {"path":"30-Data/analysis-asset-connection-v1.md","raw_sha256":"00c42234f95ab433542432cddaf61b29191e0b9f00ae645127d882230bd5e9a5","version":{"schema_version":1,"proposal_revision":3,"updated":"2026-10-08"},"blocks":[["asset-types","quote"],["asset-hash","quote"],["asset-binding","quote"],["asset-measures","quote"],["ta-metadata","paragraph"]],"sections":[],"authority":false,"range_hashes":{"asset-types":"sha256:46576360afffab5542db20582b76c46d0f6c0e18cf65781460eb707d43bb8b28","asset-hash":"sha256:5ed480c1a88b6807de5e4bec872362d539f5667dc221b8141e4df74077813a21","asset-binding":"sha256:de9c0e2aa19e618fe39aeba725febc370940f2622fe7455451f83455cc2d708b","asset-measures":"sha256:92780394e0624115ade9e55c90141d49b3f8d83b66608ce714cc19fd6edaff68","ta-metadata":"sha256:6a75c118ada1b999589f3e9d2ffff16d1f5bb573fa1a31e239d1bd30b9c41692"}},
  "analysis-skills-index": {"path":"50-Analysis-Methods/40-Skills/00-Index.md","raw_sha256":"e569ef34c22279c72d80cc5732a48598d42617268207b1aaf39b08470ef00364","version":{"updated":"2026-10-08"},"blocks":[],"sections":["分析スキルの入口"],"authority":false,"range_hashes":{"分析スキルの入口":"sha256:f97e299af4492b34a8de3e3c20373206d4bfbd78212665cd9488d3407c8018c0"}},
  "skill-thematic-candidate-evidence": {"path":"50-Analysis-Methods/40-Skills/thematic-candidate-evidence.md","raw_sha256":"8f7860af502ba9dd6e33da259309284bd53f2fa64c9d91a5d0754c66c82b5527","version":{"schema_version":1,"skill_version":1,"proposal_revision":3,"updated":"2026-10-08"},"blocks":[["tce-guards","quote"],["tce-procedure","table"],["tce-output","quote"]],"sections":[],"authority":false,"range_hashes":{"tce-guards":"sha256:fe12eca80d37bf999401bd1e1a6f543a4f0163442bb2ec575d9736ce826d8432","tce-procedure":"sha256:62a669cc888347677854b8f38bb23955e7455681188b72c5d040ef009a8d82e9","tce-output":"sha256:ccfaff3d205f1f80af206a4eeb049817412633206659e0b769f1da6991bac92d"}},
  "skill-correlation-exploratory-evidence": {"path":"50-Analysis-Methods/40-Skills/correlation-exploratory-evidence.md","raw_sha256":"3d29a901c8fc64c7d0822310bb8e97e7137e661431dcd0851e25a766eb7eb2ec","version":{"schema_version":1,"skill_version":1,"proposal_revision":3,"updated":"2026-10-08"},"blocks":[["cee-guards","quote"],["cee-procedure","table"],["cee-output","quote"]],"sections":[],"authority":false,"range_hashes":{"cee-guards":"sha256:719b3c841c05fc31b014b2d5af46295a8b5d5364f5b94267e070a65b36ca6cb4","cee-procedure":"sha256:60e7792b9bd014c32ad3d988e50d1f4f6e511a7fba0207a327efd87c41c2e756","cee-output":"sha256:74b9c49730038059d1069e5afe5b8d917d382d1d3d116c7653437ee4951f26b1"}},
  "skill-group-comparison-exploratory-evidence": {"path":"50-Analysis-Methods/40-Skills/group-comparison-exploratory-evidence.md","raw_sha256":"eb1475f67af863bd232ef3b0701c7bea71c7405c7ce95b8a0fa854544574729d","version":{"schema_version":1,"skill_version":1,"proposal_revision":3,"updated":"2026-10-08"},"blocks":[["gcee-guards","quote"],["gcee-procedure","table"],["gcee-output","quote"]],"sections":[],"authority":false,"range_hashes":{"gcee-guards":"sha256:7c7f93cfc3a23797d4cfeb7769e7bfe61fb83ae9a401c83f02c5d66812ffbeeb","gcee-procedure":"sha256:c2b1d66378cb3cd93ebfd78e26c0dd5d32ca27f348d8eedd7510b7f41ae07cb1","gcee-output":"sha256:f146cdb74c3caa0af1a9d6416284402b5f7f9b23af4ea78e6afc4cae37a0fa29"}},
  "workflow-group-interview-evidence": {"path":"50-Analysis-Methods/40-Skills/group-interview-evidence-workflow.md","raw_sha256":"1a8ed0b31076f5ade8ddb30ca953ac00debf022a3b08b20b4544221a096a2a32","version":{"schema_version":1,"workflow_version":1,"proposal_revision":3,"updated":"2026-10-08"},"blocks":[["giew-units","quote"],["giew-binding","quote"],["giew-procedure-guards","quote"],["giew-purpose","table"],["giew-procedure","table"],["giew-cases","table"]],"sections":[],"authority":false,"range_hashes":{"giew-units":"sha256:448353e5413607556e0c818067760da0a592fc9dcbc011a32abcd48c76406954","giew-binding":"sha256:c7bd0b9f223ef2ea4dca2613c57c25c151efc81e2aff16e7bb479141b8ebea73","giew-procedure-guards":"sha256:f00d0ffc55f0954ea8748c2da2f4d4b75965e0899537fe03fab1cd52e87b65bd","giew-purpose":"sha256:0c5ce9317f436b7e70652d7091ab197ad935f837a7683ecbe9197c6213e7a4a2","giew-procedure":"sha256:509caedbef8537af7c6a2bb32a468f1c7710311343215e339c03c8d9effdeedf","giew-cases":"sha256:72f3a2130f8037dc549ffb904d6003c21608d6e7270733c169fad4857cc23f45"}},
  "expert-thematic-analysis-definition": {"path":"50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert.md","raw_sha256":"26dfcdfe87323ed33fe232c8c36489f24453adb58c2b2feaa48083996147ecdc","version":{"definition_version":2},"blocks":[],"sections":["テーマ分析の専門家（exp-thematic-analysis）"],"authority":true,"range_hashes":{"テーマ分析の専門家（exp-thematic-analysis）":"sha256:b5409ab7cfad2b445c25c65c05006b7d04b7a7dcb3de8066757c711f12b2888c"}},
  "expert-thematic-analysis-quality": {"path":"50-Analysis-Methods/10-Experts/thematic-analysis/03-Quality.md","raw_sha256":"84dd97a7f50d30485975148d8a48270055ddf890d1dd7dc5f7a291e8e57e235e","version":{"updated":"2026-09-16"},"blocks":[],"sections":["テーマ分析の専門家：判断基準と品質確認"],"authority":true,"range_hashes":{"テーマ分析の専門家：判断基準と品質確認":"sha256:428ee8794bc1b06a513a95abcc73f10a9c4aecdbb818550182895174019a6b80"}},
  "expert-thematic-analysis-limits": {"path":"50-Analysis-Methods/10-Experts/thematic-analysis/04-Applicability-and-Limits.md","raw_sha256":"c6caa930bb08cce37f495779e02998d90ce39743e143cb1198c459d7b654eab0","version":{"updated":"2026-09-28"},"blocks":[],"sections":["テーマ分析の専門家：適用条件と限界"],"authority":true,"range_hashes":{"テーマ分析の専門家：適用条件と限界":"sha256:3aa0967d34dc4cca3f2156726083ce7fdbc4628342e46bac857cf45930a50a09"}},
  "expert-thematic-analysis-procedure": {"path":"50-Analysis-Methods/10-Experts/thematic-analysis/02-Procedure.md","raw_sha256":"2df79e2b69385ccf8a2dbad744d1a91cb7e02c305b873642a18c81284fab2bc4","version":{"updated":"2026-09-16"},"blocks":[],"sections":["手順と各段階の確認事項","判断に迷いやすい点","典型的な失敗と修正","結果のまとめ方","分析の前に決めること","Byrne（2022）の本文から補う実務上の確認事項"],"authority":true,"range_hashes":{"手順と各段階の確認事項":"sha256:77f710f3fa656d3078ac9d02f6f281549b6b32054e3b374738a6363813cdc7e6","判断に迷いやすい点":"sha256:75ea995330f5bb4303c3a12d3800ee08b540196583c71d693e74c1ba26c2c642","典型的な失敗と修正":"sha256:9752a4ca3e39ab2efbc9718c598ea4aed9e109f480fbfe174bfba4f13b06fc1f","結果のまとめ方":"sha256:2b9f41142ba0708d71cde6fd0f7d83898be287b53e9af1b6a5bf76afa166fb5d","分析の前に決めること":"sha256:538a6aaab1e964d2f92933bd8f7e0c3cad3dd254c45128f82424ceec187c5709","Byrne（2022）の本文から補う実務上の確認事項":"sha256:3a9ac1ee06c6d150806204a9424a0d0167defc9b64d855cf7f1671d46595e80f"}},
  "expert-thematic-analysis-agent-contract": {"path":"50-Analysis-Methods/10-Experts/thematic-analysis/07-Agent-Contract.md","raw_sha256":"453adefd17b23e289352affafc4ae85d61afa1a6f094a34e774c806772050a65","version":{"updated":"2026-10-06"},"blocks":[],"sections":["テーマ分析エージェントの入出力契約"],"authority":true,"range_hashes":{"テーマ分析エージェントの入出力契約":"sha256:a6e29e870f13ab8f09e3795647930bc34ffe43fa788fbe91bad9b8274e270e95"}},
  "expert-thematic-analysis-skill-hook-binding": {"path":"50-Analysis-Methods/10-Experts/thematic-analysis/08-Skill-Hook-Binding.md","raw_sha256":"e4677c2271ff95ccdbd053119420d20c44ac1049b3c372e30c24b747037816ef","version":{"schema_version":1,"binding_version":2,"updated":"2026-10-08"},"blocks":[],"sections":["目的・取得用途・固定する出典","段階別の対応表","入力slot・論理kind・roleの照合案","hook・callback・上限・停止と再開","G3へ渡す正常・負例（仮書式の評価）","採否・独立レビューの保留"],"authority":false,"range_hashes":{"目的・取得用途・固定する出典":"sha256:1258073757a787b66ac4ba541464190ebb1e38b29ede03b6e27535ba662fc4eb","段階別の対応表":"sha256:e0e5e0e9f95082c28523b8c6ffe38c629a0fa359c4c1b8eb583a2efec18e83b2","入力slot・論理kind・roleの照合案":"sha256:05f928958df09b79dd7959d0a1f5a31e769ebc120ade7bec2181eaab5111185d","hook・callback・上限・停止と再開":"sha256:fec16b2e92d677239590d8c8342c54b7eaa71e79a3685456c8c878525948f0b1","G3へ渡す正常・負例（仮書式の評価）":"sha256:14757e8532b5f1791a85a157f514800dcdea151fb25bee4d657d5398e411f1b8","採否・独立レビューの保留":"sha256:08b9acb81d5dc44aa885289c15299777149b51fab6fd40c126a165c3d77c1e65"}},
  "analysis-common-evidence-and-claims": {"path":"50-Analysis-Methods/08-Common-Knowledge/01-Evidence-and-Claims.md","raw_sha256":"4bc68200e3461d3bd406d907fde972fec2b6be13969b86026b6b50a200247a14","version":{"updated":"2026-09-15"},"blocks":[],"sections":["観測・解釈・根拠の区別"],"authority":false,"range_hashes":{"観測・解釈・根拠の区別":"sha256:c0bcd3f2eec5b69dbb29482e0be2edf5da993744403f5b5f9abc96153f5f8768"}},
  "analysis-common-source-classification": {"path":"50-Analysis-Methods/08-Common-Knowledge/02-Source-Classification.md","raw_sha256":"3b88a99e9b5d3965f8e4f0c1c5c0445c993cc893dd2656fc7a1f3d8a787e7564","version":{"updated":"2026-09-15"},"blocks":[],"sections":["出典の区分と根拠の強さ"],"authority":false,"range_hashes":{"出典の区分と根拠の強さ":"sha256:e4fd1bb1334f45786c3d0b7c9ebf6e231df2932e377c6b11aae49940fd9800f1"}},
  "analysis-common-group-interview-data": {"path":"50-Analysis-Methods/08-Common-Knowledge/03-Group-Interview-Data.md","raw_sha256":"2e373a185b9a11729b5b3411cfa555dd8aa41fc5dec075c61818795d8450b95a","version":{"updated":"2026-09-15"},"blocks":[],"sections":["グループインタビューのデータに共通する注意"],"authority":false,"range_hashes":{"グループインタビューのデータに共通する注意":"sha256:02727957963785428d20b0be8de7e624035c79fcf236ca523f1a3a8ff9551f90"}},
  "analysis-common-ai-assistance-boundaries": {"path":"50-Analysis-Methods/08-Common-Knowledge/04-AI-Assistance-Boundaries.md","raw_sha256":"3dff4cc7b5da87855377e6851f7ba7ff4c33fe6a32a4aaff6178ae055f85599e","version":{"updated":"2026-09-16"},"blocks":[],"sections":["AIが担う範囲と禁止事項"],"authority":false,"range_hashes":{"AIが担う範囲と禁止事項":"sha256:eeb006f589f127249989fa12eb9b7acbc733c329a66de70c14181bbf85a27652"}},
  "expert-correlation-definition": {"path":"50-Analysis-Methods/10-Experts/correlation/01-Expert.md","raw_sha256":"5a499ea69a38f176a1212ab52d4fe85b8237aaf80ba6fd1b5deed148a14642bb","version":{"definition_version":2},"blocks":[],"sections":["相関の専門家（exp-correlation）"],"authority":true,"range_hashes":{"相関の専門家（exp-correlation）":"sha256:93d7e807b8857ad6b28fcf3a419699646fea845f3b4eb10d26da944b81726153"}},
  "expert-correlation-quality": {"path":"50-Analysis-Methods/10-Experts/correlation/03-Quality.md","raw_sha256":"fa8dcd1c4121132552e17d2991b4469ece84d9c1f86cd6621eabab3149fea49e","version":{"updated":"2026-09-16"},"blocks":[],"sections":["相関の専門家：判断基準と品質確認"],"authority":true,"range_hashes":{"相関の専門家：判断基準と品質確認":"sha256:913749b134e6f0e5265bee8856161859fdb38a5fe92bd085dc3b0838663c95bd"}},
  "expert-correlation-limits": {"path":"50-Analysis-Methods/10-Experts/correlation/04-Applicability-and-Limits.md","raw_sha256":"fe7aaaeab6959575ce7924353730f2d5592fd11fe86b942786525ed1e95e0a14","version":{"updated":"2026-09-16"},"blocks":[],"sections":["相関の専門家：適用条件と限界"],"authority":true,"range_hashes":{"相関の専門家：適用条件と限界":"sha256:fb48a2854bbae8e44e106ce177064e1dca4b6fe867e293a7c409944dadba77a1"}},
  "expert-correlation-procedure": {"path":"50-Analysis-Methods/10-Experts/correlation/02-Procedure.md","raw_sha256":"77bb9f85f528dec64e7c3605252f34fd55e962fa698a12e602349f7892bc909e","version":{"updated":"2026-09-16"},"blocks":[],"sections":["手順と各段階の確認事項","判断に迷いやすい点","典型的な失敗と修正","結果のまとめ方"],"authority":true,"range_hashes":{"手順と各段階の確認事項":"sha256:c651f874c8b2297308484b1631bb05bb9a50fef6f6cabb3c39a9e32840d4bf37","判断に迷いやすい点":"sha256:febfd42534d5c4ad85ea0192f9e57947e8c3c3f1f7f07fd8fba089033aafa14f","典型的な失敗と修正":"sha256:ad482661fa081c24a9d49b30c59effa0c0c3a16e31b9256f5120f53e11cd384e","結果のまとめ方":"sha256:1bb5762722ca8c403d9371dca2993e807c7976687708849bf0f367f1d77f6a99"}},
  "expert-correlation-agent-contract": {"path":"50-Analysis-Methods/10-Experts/correlation/07-Agent-Contract.md","raw_sha256":"92c02db1e1db0f68ed2ff0febd3b5d5615149a748bf0b2a7a534dc06478bb3d2","version":{"updated":"2026-10-08"},"blocks":[],"sections":["相関専門家の入出力契約"],"authority":true,"range_hashes":{"相関専門家の入出力契約":"sha256:b1166034cfcd463ce13bd621ca26a5156667849b104df2305c870cf5c30869e3"}},
  "expert-correlation-skill-hook-binding": {"path":"50-Analysis-Methods/10-Experts/correlation/08-Skill-Hook-Binding.md","raw_sha256":"4834067229ad482d05316df8d504a6cfdc17e8c652b58318801675e9560ffe66","version":{"schema_version":1,"binding_version":6,"updated":"2026-10-08"},"blocks":[],"sections":["目的・取得用途・固定する出典","段階別の対応表","入力slot・論理kind・roleの照合案","hook・callback・上限・停止と再開","G3へ渡す正常・負例（仮書式の評価）","採否・独立レビューの保留"],"authority":false,"range_hashes":{"目的・取得用途・固定する出典":"sha256:f0d8ebceede6c3f111df16509a313257636d58fcf767f7948802d9a666d65d51","段階別の対応表":"sha256:b335d912ccbe72ee09009e6f3c5648eaed70aef9ca451c0f558316952b330f58","入力slot・論理kind・roleの照合案":"sha256:40dc856b40c3ca86b61a9824ee3ed1f5beb00d89de43b63175292cf948e9a3eb","hook・callback・上限・停止と再開":"sha256:be2f1cdb5e1e89f29ab1e71182f08361c55b3be92362e1c41a8d667058235630","G3へ渡す正常・負例（仮書式の評価）":"sha256:050c21f13603f17f5191a650739acdec37b494893a135bf10fc623badcf0e38d","採否・独立レビューの保留":"sha256:c1eb97461b27ff6104ccc5fae296bd6d50ad573d32223fcb4550171cccfabe16"}},
  "expert-group-comparison-statistics-definition": {"path":"50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert.md","raw_sha256":"15ac2cd8ffd7c02a9ffd8d99215a6a2a31fc1b776d3702da23e73b05f3fc9906","version":{"definition_version":2},"blocks":[],"sections":["群間比較の専門家（exp-group-comparison-statistics）"],"authority":true,"range_hashes":{"群間比較の専門家（exp-group-comparison-statistics）":"sha256:a1f58874f456a02ab30189b70c968e4a8190693faaa7a6861693f73b6ff177f2"}},
  "expert-group-comparison-statistics-quality": {"path":"50-Analysis-Methods/10-Experts/group-comparison-statistics/03-Quality.md","raw_sha256":"de1017b055957be6137ea7915cfce736236e18d75b5acebe47e5ed6f6b5c3709","version":{"updated":"2026-09-16"},"blocks":[],"sections":["群間比較の専門家：判断基準と品質確認"],"authority":true,"range_hashes":{"群間比較の専門家：判断基準と品質確認":"sha256:26bbb6609f059eab0ee9f046f264e7f98c781fadff9694af6e9efefbdc5a1a03"}},
  "expert-group-comparison-statistics-limits": {"path":"50-Analysis-Methods/10-Experts/group-comparison-statistics/04-Applicability-and-Limits.md","raw_sha256":"71f3ca8c3438b523efc0edb4541f85314c12990debe44afc29a0559e9f294a3a","version":{"updated":"2026-09-16"},"blocks":[],"sections":["群間比較の専門家：適用条件と限界"],"authority":true,"range_hashes":{"群間比較の専門家：適用条件と限界":"sha256:fb3502fabe21110f1e37f491877860329ff62603ae3e15517ea943433a763176"}},
  "expert-group-comparison-statistics-procedure": {"path":"50-Analysis-Methods/10-Experts/group-comparison-statistics/02-Procedure.md","raw_sha256":"61b70f55d5be860a88554f1ed51437dce3f5e3039eff780fe01ebbc97f068f14","version":{"updated":"2026-09-16"},"blocks":[],"sections":["手順と各段階の確認事項","判断に迷いやすい点","典型的な失敗と修正","結果のまとめ方"],"authority":true,"range_hashes":{"手順と各段階の確認事項":"sha256:1e6cd12e742d750a9fcb8f39cb14a0ebaa72ae1fc922dc9ee5751396e6537059","判断に迷いやすい点":"sha256:59ea391cd16ee07900b75fefc9b403bcaf3ba6e245549c91cdd2456a2aa87d54","典型的な失敗と修正":"sha256:e6c82b4901674ac43e27bd13118dfcff4cb9c1894761e0e4cc2beda53f192aff","結果のまとめ方":"sha256:a957058df02fcc9176efe3c0117e580d5243eca84f7d229883e067c9447d54f3"}},
  "expert-group-comparison-statistics-agent-contract": {"path":"50-Analysis-Methods/10-Experts/group-comparison-statistics/07-Agent-Contract.md","raw_sha256":"a1ed398b0e6f759448fd4b327eccb1d672f5bada923a4f377e82f98a16ed0c5a","version":{"updated":"2026-10-08"},"blocks":[],"sections":["群間比較専門家の入出力契約"],"authority":true,"range_hashes":{"群間比較専門家の入出力契約":"sha256:d7b95326127776ecc07008699d25509bb5347a1e21dce8557e6f97efd3534e82"}},
  "expert-group-comparison-statistics-skill-hook-binding": {"path":"50-Analysis-Methods/10-Experts/group-comparison-statistics/08-Skill-Hook-Binding.md","raw_sha256":"5080fbf445fc4668ca803ffa0cfe4ef5ad00f302786dc3644bb1d9c24f903be4","version":{"schema_version":1,"binding_version":6,"updated":"2026-10-08"},"blocks":[],"sections":["目的・取得用途・固定する出典","段階別の対応表","入力slot・論理kind・roleの照合案","hook・callback・上限・停止と再開","G3へ渡す正常・負例（仮書式の評価）","採否・独立レビューの保留"],"authority":false,"range_hashes":{"目的・取得用途・固定する出典":"sha256:e0bc8f8287703d7cea78613d55490bb034178ad685ce0f51a9bbfd41a820f3e8","段階別の対応表":"sha256:e1124aceee81704a9d4add487cbe0773d16898231e0a5d1aaf770586a5e91d03","入力slot・論理kind・roleの照合案":"sha256:db02e2b43f275b6a1d7575e9518ecfc6b186355a7c56584042ee0a3ae253b60f","hook・callback・上限・停止と再開":"sha256:8279b20f717e4af91545c36f5eebfc02c7d48d56960b8df2ac014bcc65eb41a3","G3へ渡す正常・負例（仮書式の評価）":"sha256:c10bdecdd9f25e83112854195a1650962254288c6e6483c1d442390b148722e2","採否・独立レビューの保留":"sha256:c1eb97461b27ff6104ccc5fae296bd6d50ad573d32223fcb4550171cccfabe16"}},
  "expert-focus-group-interaction-definition": {"path":"50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert.md","raw_sha256":"502131e409de7b141a166658ee63a5935e0e1aca95efd7112f99bd9b316dde82","version":{"definition_version":1},"blocks":[],"sections":["フォーカスグループの相互作用分析の専門家（exp-focus-group-interaction）"],"authority":true,"range_hashes":{"フォーカスグループの相互作用分析の専門家（exp-focus-group-interaction）":"sha256:7fd9f1fc4d8dc7311206e38164cf1db1860aadc8c90e8eadf5c31056f5395ee8"}},
  "expert-focus-group-interaction-quality": {"path":"50-Analysis-Methods/10-Experts/focus-group-interaction/03-Quality.md","raw_sha256":"a08de475a427660f1d0d90d76d2d0401b137567f8ee464648776f736e3d28c52","version":{"updated":"2026-09-16"},"blocks":[],"sections":["フォーカスグループの相互作用分析の専門家：判断基準と品質確認"],"authority":true,"range_hashes":{"フォーカスグループの相互作用分析の専門家：判断基準と品質確認":"sha256:07286e109898d081a1d35d8db398262f9b05b941e8aa7b1a8c6ecbc2d67f05d4"}},
  "expert-focus-group-interaction-limits": {"path":"50-Analysis-Methods/10-Experts/focus-group-interaction/04-Applicability-and-Limits.md","raw_sha256":"1ae6ecc9e2de687e4fd6c4934c300932cc03ddb3395d3d0dd5c0b8e8318e4ddd","version":{"updated":"2026-09-16"},"blocks":[],"sections":["フォーカスグループの相互作用分析の専門家：適用条件と限界"],"authority":true,"range_hashes":{"フォーカスグループの相互作用分析の専門家：適用条件と限界":"sha256:d77c9180b42e70321f1107fead03b1a5a36546b457056cd023897da5d44dbfe7"}},
  "expert-focus-group-interaction-procedure": {"path":"50-Analysis-Methods/10-Experts/focus-group-interaction/02-Procedure.md","raw_sha256":"e8a2e4681379ce6fd8c0919b6328b7cf0347057a9944e081627135a9aa3d2178","version":{"updated":"2026-09-16"},"blocks":[],"sections":["手順と各段階の確認事項","判断に迷いやすい点","典型的な失敗と修正","結果のまとめ方","Gurumojiでの記録"],"authority":true,"range_hashes":{"手順と各段階の確認事項":"sha256:789874201249c31f6da725a05f8a335449a5591b928d0ea27f75b575cef92551","判断に迷いやすい点":"sha256:a1c418882d7d19a1be5014236b9f290b5949f982ce726d6d4e0d3029e1d7b291","典型的な失敗と修正":"sha256:9b61824c8b67cc173d7c35402157758e06b0822b5fa66b812d9855a44127c9b9","結果のまとめ方":"sha256:013e5920237198a1cf00edc44fddd71a351cdc2c0f23e0b52b9b42bb73d4e0c1","Gurumojiでの記録":"sha256:7e937b3394bba0500f68e0e60032845ca17f1f14304d878b638daee7a14f4809"}},
  "transcript-preparation-v1": {"path":"30-Data/transcript-preparation-v1.md","raw_sha256":"d28d51f6c1232c0577d8d368da7396535f7ac161b756ca3cd43a0ab833e9d2cb","version":{"updated":"2026-09-14"},"blocks":[],"sections":["逐語録の分析準備"],"authority":false,"range_hashes":{"逐語録の分析準備":"sha256:1cbf3d82dbbb67df00db526cd4f2de58c89352a949259ad469c286d426a25a33"}}
}''')
SKILL_EXPERTS = {
    "exp-thematic-analysis": ("thematic-analysis", "skill-thematic-candidate-evidence"),
    "exp-correlation": ("correlation", "skill-correlation-exploratory-evidence"),
    "exp-group-comparison-statistics": ("group-comparison-statistics", "skill-group-comparison-exploratory-evidence"),
}


class ExpertCatalog:
    """Loads expert definitions lazily; every file read is logged for traceability tests."""

    def __init__(self, root: Path | str | None = None, local_root: Path | str | None = None):
        self.root = Path(root) if root is not None else SOFTWARE_ROOT
        self.local_root = Path(local_root) if local_root is not None else LOCAL_KNOWLEDGE_DIR
        self.read_log: list[str] = []
        self._lock = threading.RLock()
        self._files: dict[str, tuple[tuple[int, int], dict]] = {}
        self._frontmatter: dict[str, tuple[tuple[int, int], dict]] = {}
        self._definitions: dict[str, dict] = {}

    def _resolve(self, relative: Path) -> Path:
        """A local note shadows the base note at the same relative path; otherwise fall back."""
        local = self.local_root / relative
        return local if local.exists() else self.root / relative

    def _stat(self, relative: Path) -> tuple[int, int] | None:
        try:
            stat = self._resolve(relative).stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def _note(self, relative: Path) -> dict | None:
        key = relative.as_posix()
        with self._lock:
            stamp = self._stat(relative)
            if stamp is None:
                return None
            cached = self._files.get(key)
            if cached and cached[0] == stamp:
                return cached[1]
            data = self._resolve(relative).read_bytes()
            self.read_log.append(key)
            try:
                props, body = unpack(data.decode("utf-8"))
            except (ValueError, UnicodeDecodeError, yaml.YAMLError):
                props, body = {}, ""
            entry = {"sha256": hashlib.sha256(data).hexdigest(), "props": props, "body": body}
            self._files[key] = (stamp, entry)
            return entry

    def _properties(self, relative: Path) -> dict:
        """Read only the property block, so unselected experts' bodies stay unread."""
        key = relative.as_posix()
        with self._lock:
            stamp = self._stat(relative)
            if stamp is None:
                return {}
            cached = self._frontmatter.get(key)
            if cached and cached[0] == stamp:
                return cached[1]
            lines = []
            with self._resolve(relative).open("r", encoding="utf-8") as handle:
                if handle.readline().strip() == "---":
                    for line in handle:
                        if line.rstrip("\r\n") == "---":
                            break
                        lines.append(line)
            self.read_log.append("properties:" + key)
            try:
                props = unpack("---\n" + "".join(lines) + "---\n")[0] if lines else {}
            except (ValueError, yaml.YAMLError):
                props = {}
            self._frontmatter[key] = (stamp, props)
            return props

    def _expert_folders(self) -> dict[str, str]:
        """Every expert folder name, mapped to its source: local-only, local override, or base."""
        try:
            base = {path.name for path in (self.root / EXPERTS_DIR).iterdir() if path.is_dir()}
        except OSError:
            base = set()
        try:
            local = {path.name for path in (self.local_root / EXPERTS_DIR).iterdir() if path.is_dir()}
        except OSError:
            local = set()
        sources = {folder: "base" for folder in base}
        for folder in local:
            sources[folder] = "local_override" if folder in base else "local"
        return dict(sorted(sources.items()))

    def index(self) -> dict[str, dict]:
        entries = {}
        for folder, source in self._expert_folders().items():
            props = self._properties(EXPERTS_DIR / folder / DEFINITION_NOTE)
            if props.get("note_type") != "expert-definition" or not EXPERT_ID.match(str(props.get("expert_id") or "")):
                continue
            entries[str(props["expert_id"])] = {
                "expert_id": str(props["expert_id"]), "folder": folder, "title": _text(props.get("title")),
                "role": props.get("role"), "role_label": ROLE_LABELS.get(props.get("role"), ""),
                "analysis_method_ids": list(props.get("analysis_method_ids") or []),
                "registry_method_ids": list(props.get("registry_method_ids") or []),
                "definition_version": props.get("definition_version"),
                "knowledge_verified": str(props.get("knowledge_verified") or ""),
                "definition_note": (EXPERTS_DIR / folder / "01-Expert").as_posix(),
                "source": source,
            }
        return entries

    def expert_for_method(self, method_id: str, *, registry: bool = False) -> str | None:
        field = "registry_method_ids" if registry else "analysis_method_ids"
        return next((expert_id for expert_id, entry in self.index().items() if method_id in entry[field]), None)

    def definition(self, expert_id: str) -> dict:
        entry = self.index().get(expert_id)
        if entry is None:
            raise ExpertDefinitionError(f"専門家定義が見つかりません：{expert_id}")
        note = self._note(EXPERTS_DIR / entry["folder"] / DEFINITION_NOTE)
        if note is None:
            raise ExpertDefinitionError(f"専門家定義を読み込めません：{expert_id}")
        with self._lock:
            cached = self._definitions.get(note["sha256"])
            if cached is not None:
                return cached
        match = DEFINITION_BLOCK.search(note["body"])
        if not match:
            raise ExpertDefinitionError(f"実行定義のブロックがありません：{expert_id}")
        try:
            definition = yaml.safe_load(match[1])
        except yaml.YAMLError as exc:
            raise ExpertDefinitionError(f"実行定義のYAMLが不正です：{expert_id}") from exc
        errors = validate_definition(definition, folder=entry["folder"], props=note["props"])
        if errors:
            raise ExpertDefinitionError(f"{expert_id}：" + " / ".join(errors[:5]))
        with self._lock:
            self._definitions[note["sha256"]] = definition
        return definition

    def knowledge(self, expert_id: str, definition: dict) -> dict:
        folder = self.index()[expert_id]["folder"]
        parts, missing_notes, references, missing_references = [], [], [], []
        for name in KNOWLEDGE_NOTES:
            relative = EXPERTS_DIR / folder / name
            note = self._note(relative)
            if note is None:
                missing_notes.append(relative.as_posix())
            else:
                parts.append((relative.as_posix(), note["sha256"]))
        for stem in definition["common_notes"]:
            relative = COMMON_DIR / f"{stem}.md"
            note = self._note(relative)
            if note is None:
                missing_notes.append(relative.as_posix())
            else:
                parts.append((relative.as_posix(), note["sha256"]))
        for reference in definition["literature"]:
            relative = LITERATURE_DIR / f"{reference}.md"
            note = self._note(relative)
            if note is None:
                missing_references.append(reference)
                continue
            parts.append((relative.as_posix(), note["sha256"]))
            props = note["props"]
            references.append({
                "id": reference, "title": _text(props.get("title")), "year": str(props.get("year") or ""),
                "source_type": props.get("source_type"), "peer_review": props.get("peer_review"),
                "access_scope": props.get("access_scope"), "correction_status": props.get("correction_status"),
                "note": relative.with_suffix("").as_posix(),
            })
        digest = hashlib.sha256(json.dumps(sorted(parts), separators=(",", ":")).encode("utf-8")).hexdigest()
        return {"knowledge_hash": "sha256:" + digest, "references": references,
                "missing_references": missing_references, "missing_notes": missing_notes,
                "notes": sorted(path for path, _ in parts)}

    def _skill_note_ids(self, expert_id, workflow=False):
        if not isinstance(expert_id, str): raise SkillContextError("expert_unregistered", decision="rejected")
        if expert_id not in SKILL_EXPERTS:
            # Prototype coverage does not define the authoritative expert registry.
            # Index reads definition frontmatter only, never all knowledge bodies.
            for root in (self.root, self.local_root):
                if root.is_symlink() or root.resolve() != root.absolute():
                    raise SkillContextError("path_escape")
            for folder in self._expert_folders():
                relative = EXPERTS_DIR / folder / DEFINITION_NOTE
                candidate = self._resolve(relative)
                root = self.local_root if candidate == self.local_root / relative else self.root
                if not candidate.resolve().is_relative_to(root.resolve()):
                    raise SkillContextError("path_escape")
            known = expert_id in self.index()
            raise SkillContextError("expert_unsupported" if known else "expert_unregistered",
                                    decision="unsupported" if known else "rejected")
        if type(workflow) is not bool: raise SkillContextError("selection_invalid", decision="rejected")
        folder, skill_id = SKILL_EXPERTS[expert_id]
        prefix = "expert-" + folder + "-"
        selected = {"data-analysis-asset-connection-v1", "analysis-skills-index", skill_id}
        selected.update(key for key in SKILL_NOTE_REFS if key.startswith(prefix) or key.startswith("analysis-common-"))
        if workflow:
            selected.update({"workflow-group-interview-evidence", "skill-thematic-candidate-evidence", "transcript-preparation-v1"})
            selected.update(key for key in SKILL_NOTE_REFS if key.startswith("expert-focus-group-interaction-"))
        return sorted(selected)

    def read_skill_note(self, expert_id, note_id, *, workflow=False, reference=None):
        """Read registered bytes afresh, including same-size/same-mtime edits.

        Roots are the existing bounded Software Vault/local overlay roots. No
        researcher Vault discovery, arbitrary path or missing-block expansion.
        Receipt verification applies to bytes read now, not future file state.
        """
        if note_id not in self._skill_note_ids(expert_id, workflow):
            raise SkillContextError("note_out_of_scope", decision="rejected")
        spec = SKILL_NOTE_REFS[note_id]
        identity = {k: spec[k] for k in ("path", "raw_sha256", "version")}
        if reference is not None:
            try:
                if json.dumps(reference, sort_keys=True, allow_nan=False) != json.dumps(identity, sort_keys=True, allow_nan=False):
                    raise SkillContextError("reference_mismatch")
            except (TypeError, ValueError):
                raise SkillContextError("reference_mismatch") from None
        relative = Path(spec["path"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in spec["path"]:
            raise SkillContextError("path_escape")
        path, origin = None, None
        for root, label in ((self.local_root, "local_override"), (self.root, "base")):
            if root.is_symlink() or root.is_junction(): raise SkillContextError("root_escape")
            resolved_root = root.resolve()
            candidate = root / relative
            resolved = candidate.resolve()
            if not resolved.is_relative_to(resolved_root): raise SkillContextError("path_escape")
            if candidate.exists():
                if not resolved.is_file(): raise SkillContextError("registered_file_invalid")
                path, origin = resolved, label
                break
        if path is None: raise SkillContextError("note_missing", decision="needs_input")
        try:
            if path.stat().st_size > 131072: raise SkillContextError("note_byte_limit", decision="needs_input")
            with path.open("rb") as handle:
                data = handle.read(131073)
        except OSError:
            raise SkillContextError("note_unavailable", decision="needs_input") from None
        self.read_log.append("skill:" + relative.as_posix())
        if len(data) > 131072: raise SkillContextError("note_byte_limit", decision="needs_input")
        if hashlib.sha256(data).hexdigest() != spec["raw_sha256"]:
            raise SkillContextError("raw_hash_mismatch")
        try:
            props, body = unpack(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, yaml.YAMLError):
            raise SkillContextError("note_malformed") from None
        if props.get("note_id") != note_id: raise SkillContextError("note_id_mismatch")
        for key, expected in spec["version"].items():
            actual = props.get(key)
            if not isinstance(actual, (str, int, bool)): actual = str(actual)
            if type(actual) is not type(expected) or actual != expected:
                raise SkillContextError("version_mismatch")
        parts = [{"type": native, "id": name, "text": _skill_range(body, name, native)}
                 for name, native in spec["blocks"]]
        parts.extend({"type": "section", "id": name, "text": _skill_range(body, name)} for name in spec["sections"])
        for part in parts:
            part["range_utf8_hash"] = "sha256:" + hashlib.sha256(part["text"].encode("utf-8")).hexdigest()
            expected = spec.get("range_hashes", {}).get(part["id"])
            if expected is not None and expected != part["range_utf8_hash"]:
                raise SkillContextError("range_incomplete")
        return {"note_id": note_id, "path": relative.as_posix(), "version": dict(spec["version"]),
                "raw_byte_hash": "sha256:" + spec["raw_sha256"], "source": origin, "parts": parts,
                "receipt_type": "knowledge_read", "verification_scope": "bytes_read_at_receipt",
                "unselected_body_characters": max(0, len(body) - sum(len(p["text"]) for p in parts)),
                "delivery_state": "not_measured", "human_adoption": "unanswered"}

    def skill_context(self, expert_id, *, workflow=False, max_bytes=262144):
        """Opt-in complete required ranges; default currentPack is untouched."""
        if type(max_bytes) is not int or not 1 <= max_bytes <= 262144:
            raise SkillContextError("context_byte_limit", decision="needs_input")
        sources = [self.read_skill_note(expert_id, nid, workflow=workflow)
                   for nid in self._skill_note_ids(expert_id, workflow)]
        if sum(len(part["text"].encode("utf-8")) for source in sources for part in source["parts"]) > max_bytes:
            raise SkillContextError("context_byte_limit", decision="needs_input")
        definition_source = next(s for s in sources if s["note_id"] == "expert-" + SKILL_EXPERTS[expert_id][0] + "-definition")
        body = "\n\n".join(part["text"] for part in definition_source["parts"])
        match = DEFINITION_BLOCK.search(body)
        if not match: raise SkillContextError("authority_missing")
        definition = yaml.safe_load(match[1])
        if validate_definition(definition, folder=SKILL_EXPERTS[expert_id][0]): raise SkillContextError("authority_invalid")
        # YAML dates in this existing descriptive field are not runtime objects.
        definition["knowledge_verified"] = str(definition["knowledge_verified"])
        result = {"version": SKILL_CONTEXT_VERSION, "expert_id": expert_id, "workflow_selected": workflow,
                  "status": "draft", "runtime_state": "planned", "production_default_enabled": False,
                  "definition": definition, "sources": sources, "literature_body_read": False,
                  "human_adoption": "unanswered", "meaning_review": "undetermined"}
        result["context_hash"] = "sha256:" + hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        return result

    def review(self, expert_id: str, analysis: dict, *, role: str = "主", method_id: str = "",
               selection: str = "researcher", context: dict | None = None) -> dict:
        base = {"expert_id": expert_id, "role": role, "method_id": method_id, "selection": selection,
                "selection_label": SELECTION_LABELS.get(selection, selection)}
        try:
            definition = self.definition(expert_id)
        except (ExpertDefinitionError, OSError) as exc:
            return {**base, "status": "definition_error", "status_label": STATUS_LABELS["definition_error"],
                    "message": str(exc)}
        knowledge = self.knowledge(expert_id, definition)
        checks = [evaluate_check(spec, analysis, context or {}) for spec in definition["applicability_checks"]]
        quality = [evaluate_check({**spec, "severity": "warn", "message": spec["text"]}, analysis, context or {})
                   for spec in definition["quality_checks"]]
        blocked = any(check["result"] == "fail" and check["severity"] == "block" for check in checks)
        attention = any(check["result"] in {"fail", "not_evaluable"} for check in checks) \
            or bool(knowledge["missing_references"] or knowledge["missing_notes"])
        status = "blocked" if blocked else "needs_attention" if attention else "ready"
        assist = definition["ai_assist"]
        school = definition["school"]
        return {
            **base,
            "title": definition["title"], "role_label": ROLE_LABELS[definition["role"]],
            "expert_role": definition["role"], "definition_version": definition["definition_version"],
            "knowledge_verified": str(definition["knowledge_verified"]),
            "definition_note": (EXPERTS_DIR / self.index()[expert_id]["folder"] / "01-Expert").as_posix(),
            "knowledge_hash": knowledge["knowledge_hash"],
            "status": status, "status_label": STATUS_LABELS[status],
            "school": {"default": school["default"], "alternatives": school.get("alternatives") or []},
            "analysis_unit": definition["analysis_unit"], "scope": definition["scope"],
            "out_of_scope": definition["out_of_scope"], "required_inputs": definition["required_inputs"],
            "checks": checks,
            "quality_checks": quality,
            "procedure": [{"id": step["id"], "title": step["title"], "actor": step["actor"],
                           "actor_label": ACTOR_LABELS[step["actor"]], "basis": step["basis"]}
                          for step in definition["procedure"]],
            "prohibited_conclusions": definition["prohibited_conclusions"],
            "output_sections": definition["output_sections"],
            "ai_assist": {"allowed": assist["allowed"], "steps": list(assist.get("steps") or []),
                          "reason": _text(assist.get("reason"))},
            "references": knowledge["references"], "missing_references": knowledge["missing_references"],
            "missing_notes": knowledge["missing_notes"], "knowledge_notes": knowledge["notes"],
            "open_issues": definition["open_issues"],
            "readiness": {**{key: definition["readiness"][key] for key in READINESS_KEYS},
                          "references_resolved": not knowledge["missing_references"],
                          "has_open_issues": bool(definition["open_issues"])},
        }


def evaluate_check(spec: dict, analysis: dict, context: dict) -> dict:
    name = spec["check"]
    if name == "human_review":
        result, observed = "human", {}
    else:
        try:
            result, observed = CHECKS[name][0](analysis, spec.get("params") or {}, context)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            result, observed = "not_evaluable", {}
    return {"id": spec["id"], "check": name, "severity": spec.get("severity", "warn"), "result": result,
            "result_label": RESULT_LABELS[result], "message": _text(spec.get("message")),
            "basis": list(spec.get("basis") or []), "observed": observed}


_default_catalog: ExpertCatalog | None = None
_default_lock = threading.Lock()


def default_catalog() -> ExpertCatalog:
    global _default_catalog
    with _default_lock:
        if _default_catalog is None:
            _default_catalog = ExpertCatalog()
        return _default_catalog


def _fingerprint(review: dict) -> str:
    payload = {key: review.get(key) for key in ("expert_id", "definition_version", "knowledge_hash")}
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def review_for_analysis(analysis: dict, catalog: ExpertCatalog | None = None) -> dict:
    """Select the primary and auxiliary experts named by the analysis plan, and review only them."""
    catalog = catalog or default_catalog()
    index = catalog.index()
    if not index:
        return {"schema_version": SCHEMA_VERSION, "status": "unavailable", "experts": [],
                "message": "専門家定義（docs/program-vault/50-Analysis-Methods/10-Experts）が見つかりません。",
                "ai": {"mode": "generic", "reason": "専門家定義がないため、手法に依存しない下書きとして生成します。"}}
    selected = _text(_nested(analysis, "config", "analysis_method")) or "auto"
    rows = _nested(analysis, "manual", "focus_group_plan", "methods")
    reviews, seen = [], set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        method_id = _text(row.get("method_id"))
        role = "主" if row.get("role") == "主" else "補助"
        selection = ("provisional" if selected == "auto" else "researcher") if role == "主" else "plan"
        expert_id = catalog.expert_for_method(method_id)
        if expert_id is None:
            reviews.append({"expert_id": "", "method_id": method_id, "role": role, "selection": selection,
                            "selection_label": SELECTION_LABELS[selection], "status": "definition_missing",
                            "status_label": STATUS_LABELS["definition_missing"]})
            continue
        if expert_id not in seen:
            seen.add(expert_id)
            reviews.append(catalog.review(expert_id, analysis, role=role, method_id=method_id, selection=selection))
    primary = next((review for review in reviews if review["role"] == "主"), None)
    ai: dict[str, Any] = {"mode": "generic",
                          "reason": "主手法が未選択（暫定）のため、AI見解は手法に依存しない下書きとして生成します。"}
    if primary and primary["selection"] == "researcher":
        if primary["status"] in {"definition_error", "definition_missing"}:
            ai = {"mode": "blocked", "expert_id": primary["expert_id"],
                  "reason": "選択した手法の専門家定義を読み込めないため、AI見解を生成しません。"}
        elif not primary["ai_assist"]["allowed"]:
            ai = {"mode": "blocked", "expert_id": primary["expert_id"],
                  "reason": primary["ai_assist"]["reason"] or f"{primary['title']}ではAI見解を手順に含めません。"}
        elif primary["status"] == "blocked":
            unmet = "／".join(check["message"] for check in primary["checks"]
                             if check["result"] == "fail" and check["severity"] == "block")
            ai = {"mode": "blocked", "expert_id": primary["expert_id"],
                  "reason": f"{primary['title']}の適用条件を満たしていないため、AI見解を生成しません：{unmet}"}
        else:
            # A draft may cite only literature whose note exists, so each AI step needs a resolvable basis.
            resolved = {reference["id"] for reference in primary["references"]}
            steps = [step["id"] for step in primary["procedure"]
                     if step["id"] in primary["ai_assist"]["steps"] and any(value in resolved for value in step["basis"])]
            if steps:
                ai = {"mode": "expert", "expert_id": primary["expert_id"],
                      "definition_version": primary["definition_version"], "knowledge_hash": primary["knowledge_hash"],
                      "fingerprint": _fingerprint(primary), "steps": steps}
            else:
                ai = {"mode": "blocked", "expert_id": primary["expert_id"],
                      "reason": "AI下書きの段階の根拠となる文献ノートが見つからないため、AI見解を生成しません："
                                + _labels(primary["missing_references"])}
    return {"schema_version": SCHEMA_VERSION, "status": "available", "experts": reviews, "ai": ai,
            "note": "専門家は実行定義を読み込んで手順と説明を制御します。専門家どうしの合議や独立したレビューは行っていません。"}


def ai_block_reason(experts: dict | None) -> str:
    ai = (experts or {}).get("ai") or {}
    return _text(ai.get("reason")) if ai.get("mode") == "blocked" else ""


def ai_context(experts: dict | None, catalog: ExpertCatalog | None = None) -> dict | None:
    """Short, method-specific instructions for AI insights; no note text or literature is included."""
    ai = (experts or {}).get("ai") or {}
    if ai.get("mode") != "expert":
        return None
    catalog = catalog or default_catalog()
    definition = catalog.definition(ai["expert_id"])
    knowledge = catalog.knowledge(ai["expert_id"], definition)
    if (definition["definition_version"] != ai.get("definition_version")
            or knowledge["knowledge_hash"] != ai.get("knowledge_hash")):
        raise ExpertDefinitionError("専門家の定義・知識が更新されています。分析条件を再確認してから生成してください。")
    primary = next((review for review in (experts or {}).get("experts", [])
                    if review.get("expert_id") == ai["expert_id"]), {})
    resolved = {reference["id"] for reference in primary.get("references", [])}
    allowed = set(ai.get("steps") or [])
    steps = [{"id": step["id"], "title": step["title"],
              "basis": [value for value in step["basis"] if REFERENCE_ID.match(str(value)) and value in resolved]}
             for step in definition["procedure"] if step["id"] in allowed]
    return {"expert_id": definition["expert_id"], "title": definition["title"],
            "definition_version": definition["definition_version"], "knowledge_hash": ai["knowledge_hash"],
            "fingerprint": ai["fingerprint"], "brief": _text(definition["ai_assist"]["brief"]),
            "steps": steps, "prohibited_conclusions": definition["prohibited_conclusions"][:8]}


def compact_review(review: dict) -> dict:
    keys = ("expert_id", "title", "role_label", "selection", "definition_version", "knowledge_verified",
            "knowledge_hash", "status", "status_label", "definition_note", "prohibited_conclusions",
            "missing_references", "message")
    compact = {key: review[key] for key in keys if key in review}
    compact["unmet_checks"] = [{key: check[key] for key in ("id", "check", "severity", "result", "message", "basis")}
                               for check in review.get("checks", []) if check["result"] in {"fail", "not_evaluable"}]
    compact["human_checks"] = [{"id": check["id"], "text": check["message"], "basis": check["basis"]}
                               for check in review.get("quality_checks", []) if check["result"] == "human"]
    compact["reference_ids"] = [reference["id"] for reference in review.get("references", [])]
    return compact


def limitation_lines(review: dict) -> list[str]:
    """Readable lines for saved method notes: who judged the result, what is unmet, and the basis notes."""
    if not review.get("knowledge_hash"):
        return [f"担当専門家の定義を読み込めませんでした：{review.get('message') or review.get('expert_id', '')}"]
    lines = [f"担当専門家：{review['title']}（{review['expert_id']}、第{review['definition_version']}版、"
             f"定義 {review['definition_note']}）。適用条件：{review['status_label']}。"]
    for check in review["unmet_checks"]:
        level = "分析を始めない条件" if check["severity"] == "block" and check["result"] == "fail" else "要確認"
        lines.append(f"[{level}] {check['message']}（根拠：{_labels(check['basis'])}）")
    if review["human_checks"]:
        lines.append(f"研究者が確認する項目が{len(review['human_checks'])}件あります（アプリは確認済みとして扱いません）。")
    lines += [f"示してはいけない結論：{item}" for item in review["prohibited_conclusions"]]
    lines.append(f"方法論の根拠（文献ノート）：{_labels(review['reference_ids'])}")
    if review.get("missing_references"):
        lines.append(f"見つからない文献ノート：{_labels(review['missing_references'])}")
    return lines


def attach_method_reviews(methods: list[dict], analysis: dict, *, context: dict | None = None,
                          catalog: ExpertCatalog | None = None) -> dict[str, str]:
    """Attach the responsible expert's review to each method that produced a result."""
    catalog = catalog or default_catalog()
    reviews: dict[str, dict] = {}
    for method in methods:
        if method.get("status") not in PRODUCED_STATES:
            continue
        expert_id = catalog.expert_for_method(str(method.get("method_id") or ""), registry=True)
        if expert_id is None:
            continue
        if expert_id not in reviews:
            reviews[expert_id] = catalog.review(expert_id, analysis, role="補助", method_id=method["method_id"],
                                                selection="result", context=context)
        method["expert_review"] = compact_review(reviews[expert_id])
        # Saved notes render limitations, so the expert's judgement and basis travel with the result.
        method["limitations"] = [*method.get("limitations", []), *limitation_lines(method["expert_review"])]
    return {expert_id: review["knowledge_hash"] for expert_id, review in sorted(reviews.items())
            if review.get("knowledge_hash")}


VERDICT_LABELS = {
    "ok": "結果あり・条件を満たす", "check": "結果あり・要確認",
    "stop": "結果あり・この条件では使わない", "none": "結果なし",
    "no_expert": "結果あり・担当専門家なし",
}
# Why a function has no expert of its own (see 50-Analysis-Methods/10-Experts/00-Index).
NO_EXPERT_NOTES = {
    "local_insights": "原文を読む順番を提案する探索補助で、分析手法ではないため担当専門家を置いていません。",
    "qualitative_coding": "質的分析の各専門家が共通に使う記録の道具で、手法ではないため担当専門家を置いていません。",
    "ai_insights": "方法論の専門家の手順をAIで下書きする手段です。主手法に選んだ専門家の定義に従います。",
    "outline": "会話をたどるための中間成果物で、分析手法ではありません。",
    "ai_finishing": "逐語録の編集と監査の工程で、分析手法ではありません。",
}


def method_overview(methods: list[dict], analysis: dict, *, context: dict | None = None,
                    catalog: ExpertCatalog | None = None) -> dict:
    """One row per method: what it produced, and what the responsible expert says about that data.

    A method without a result gets the expert's conditions for running it, never a judgement of a result.
    """
    catalog = catalog or default_catalog()
    experts: dict[str, dict] = {}
    rows = []
    for method in methods:
        method_id = _text(method.get("method_id"))
        produced = method.get("status") in PRODUCED_STATES
        expert_id = catalog.expert_for_method(method_id, registry=True) or ""
        if expert_id and expert_id not in experts:
            review = catalog.review(expert_id, analysis, role="担当", method_id=method_id,
                                    selection="current" if produced else "preconditions", context=context)
            experts[expert_id] = {key: value for key, value in review.items() if key != "knowledge_notes"}
        review = experts.get(expert_id)
        if not produced:
            verdict = "none"
        elif review is None:
            verdict = "no_expert"
        else:
            verdict = {"ready": "ok", "needs_attention": "check"}.get(review["status"], "stop")
        unmet = [check for check in (review or {}).get("checks", []) if check["result"] in {"fail", "not_evaluable"}]
        rows.append({
            "method_id": method_id, "title": _text(method.get("title")), "status": _text(method.get("status")),
            "status_label": method_status_label(method), "analysis_unit": _text(method.get("analysis_unit")),
            "datasets": list(method.get("datasets") or []),
            "result_counts": {preview["dataset"]: preview["total"] for preview in method.get("previews") or []},
            "limitations": list(method.get("limitations") or []), "produced": produced,
            "verdict": verdict, "verdict_label": VERDICT_LABELS[verdict],
            "verdict_reason": unmet[0]["message"] if unmet else "",
            "expert_id": expert_id, "expert_note": "" if expert_id else NO_EXPERT_NOTES.get(method_id, ""),
            "expert_scope": ("result" if produced else "preconditions") if review else "",
        })
    counts = Counter(row["verdict"] for row in rows)
    return {"schema_version": SCHEMA_VERSION, "summary": {key: counts.get(key, 0) for key in VERDICT_LABELS},
            "methods": rows, "experts": experts}


def knowledge_hashes(experts: dict | None) -> dict[str, str]:
    return {review["expert_id"]: review["knowledge_hash"] for review in (experts or {}).get("experts", [])
            if review.get("knowledge_hash")}


def plan_procedure(experts: dict | None) -> list[str]:
    primary = next((review for review in (experts or {}).get("experts", [])
                    if review.get("role") == "主" and review.get("procedure")), None)
    if primary is None:
        return []
    return [f"{step['title']}（担当：{step['actor_label']}）" for step in primary["procedure"]]


def _labels(values: list[str]) -> str:
    return "、".join(values) if values else "なし"


def report_lines(experts: dict | None) -> list[str]:
    experts = experts or {}
    lines = ["", "## 手法の専門家による確認", ""]
    if experts.get("status") != "available":
        return lines + [f"- {experts.get('message') or '専門家定義を読み込んでいません。'}"]
    lines.append(f"- {experts.get('note', '')}")
    lines.append("- ここに示すのは方法論上の根拠（専門家定義と文献ノート）。データ上の根拠（発話ID）は各結果の節に示す。")
    for review in experts.get("experts", []):
        title = review.get("title") or review.get("method_id") or "不明な手法"
        lines += ["", f"### {title}（{review.get('role', '')}・{review.get('selection_label', '')}）", ""]
        if review.get("status") in {"definition_error", "definition_missing"}:
            lines.append(f"- 状態：{review.get('status_label')}。{review.get('message', '')}")
            continue
        school = review["school"]
        alternatives = [item.get("label", "") for item in school.get("alternatives", [])]
        lines += [
            f"- 状態：{review['status_label']}。定義 {review['definition_note']}（第{review['definition_version']}版、"
            f"知識の確認日 {review['knowledge_verified']}、知識hash {review['knowledge_hash'][:19]}）",
            f"- 採用する流派：{school['default'].get('label', '')}（ほかの流派：{_labels(alternatives)}）",
            f"- 分析単位：{review['analysis_unit']}",
        ]
        unmet = [check for check in review["checks"] if check["result"] in {"fail", "not_evaluable"}]
        if unmet:
            lines.append("- 満たさない、または判定できない条件：")
            for check in unmet:
                level = "分析を始めない" if check["severity"] == "block" and check["result"] == "fail" else "要確認"
                lines.append(f"  - [{level}・{check['result_label']}] {check['message']}（根拠：{_labels(check['basis'])}）")
        human = [check for check in review["quality_checks"] if check["result"] == "human"]
        if human:
            lines.append("- 研究者が確認する項目（アプリは確認済みと表示しない）：")
            lines += [f"  - {check['message']}" for check in human]
        lines.append("- 手順と担当：")
        lines += [f"  {index}. {step['title']}（{step['actor_label']}）"
                  for index, step in enumerate(review["procedure"], 1)]
        lines.append("- 示してはいけない結論：")
        lines += [f"  - {item}" for item in review["prohibited_conclusions"]]
        lines.append("- 方法論の根拠（文献ノート）：")
        peer = {"confirmed": "査読確認済み", "not_peer_reviewed": "査読なし", "unconfirmed": "査読未確認"}
        scope = {"full_text": "本文確認", "abstract": "要旨確認", "bibliographic": "書誌のみ", "official_page": "公式ページ"}
        lines += [f"  - {reference['id']}（{peer.get(reference['peer_review'], '不明')}・"
                  f"{scope.get(reference['access_scope'], '不明')}）" for reference in review["references"]]
        if review["missing_references"]:
            lines.append(f"- 見つからない文献ノート：{_labels(review['missing_references'])}")
        if review["open_issues"]:
            lines.append(f"- 未解決事項：{len(review['open_issues'])}件（{review['definition_note']} を参照）")
    return lines


def catalog_summary(catalog: ExpertCatalog | None = None) -> dict:
    catalog = catalog or default_catalog()
    experts = sorted(catalog.index().values(), key=lambda entry: entry["expert_id"])
    return {"schema_version": SCHEMA_VERSION, "available": bool(experts), "experts": experts}


def expert_detail(expert_id: str, catalog: ExpertCatalog | None = None) -> dict:
    catalog = catalog or default_catalog()
    definition = catalog.definition(expert_id)
    knowledge = catalog.knowledge(expert_id, definition)
    return {"schema_version": SCHEMA_VERSION, "expert": catalog.index()[expert_id],
            "definition": json.loads(json.dumps(definition, ensure_ascii=False, default=str)),
            "knowledge_hash": knowledge["knowledge_hash"], "references": knowledge["references"],
            "missing_references": knowledge["missing_references"], "missing_notes": knowledge["missing_notes"]}
