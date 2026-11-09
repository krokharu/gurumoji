"""固定済みの統計結果をObusSQL専用codecへ結び付ける。"""
from __future__ import annotations

from collections import defaultdict
import copy
from decimal import Context, Decimal, Inexact, localcontext
import json
from uuid import NAMESPACE_URL, uuid5

from ..analysis_core import AnalysisContractError, fingerprint

VERSION = 1
PROFILE = "gurumoji-metrics-v1"
GUIDANCE = (
    "\n統計専用契約: metric_context.recordsは固定済みの集計です。metric_selectionsで参照と演算だけを選びます。"
    "valueは元のvalueを正確に復唱し、diff/ratio/max/minのvalueはnullです。算術はアプリが実行します。"
    "今回は提示済み集計の報告です。metric_context.sourcesの各keyについて、metric_selectionsの同じ欄へ演算を1件ずつ返します。"
    "全ての欄が必須で、operandsはその欄のrefsだけから選びます。"
    "valueのoperandsは必ず1個です。diff/ratioは2個、max/minは2個以上です。"
    "値がnullならnullのままvalueで選び、母数・欠測・値なしを報告します。研究質問の未解決点はunresolvedへ残します。"
    "同じ指標・単位・粒度の値だけを比較します。原文やSQLを再実行できない理由で提示済みの集計を未取得扱いにしません。"
    "集計表の値を発話の根拠と混同せずclaims=[]とします。summaryは検討手順だけを書き、"
    "統計報告の数値と本文はデコーダーが生成します。元の統計結果は読み取り専用です。"
)


def _fail(code="metric_contract_invalid"):
    raise AnalysisContractError("統計専用codecの参照・値・入力版を確認できません。", code=code)


def require_available():
    try:
        from obusql_agent.metric_codec import MetricEncoder, MetricDecoder, MetricResult, EncodedMetrics
    except ImportError:
        raise AnalysisContractError("統計専用codecの固定版を導入してください。requirements-obussql-metric.txtを確認してください。",
                                    code="metric_codec_unavailable") from None
    return MetricEncoder, MetricDecoder, MetricResult, EncodedMetrics


def _number(value):
    if type(value) not in {int, float, str, Decimal}:
        _fail()
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number.as_tuple().exponent < -12:
            _fail()
        return format(number, "f")
    except (ValueError, ArithmeticError):
        _fail()


def _count(value):
    if type(value) is not int or value < 0:
        _fail()
    return value


def records_for(result, identity):
    """既存表の値だけを使用する。未対応の割合・検定値は推測して変換しない。"""
    _, _, MetricResult, _ = require_available()
    raw = result["content"]
    method = raw.get("method_id") or raw.get("method", {}).get("method_id")
    if method not in {"participation", "conversation_dynamics", "label_frequency", "cross_tabulation"}:
        _fail("metric_method_unsupported")
    revision = PROFILE + ":" + method
    if method in {"label_frequency", "cross_tabulation"}:
        revision += ":" + str(raw["annotation_version"]) + ":" + str(raw["codebook_version"])
    filters = ("固定済み統計結果の全行。除外・欠測の扱いは元の集計契約に従う。",)
    filter_hash = fingerprint({"profile": PROFILE, "method": method, "manifest": raw.get("manifest"), "filters": filters})
    records = []

    def add(key, label, value, *, population, observed=None, missing=0, group="全体", unit="utterance",
            unit_label="発話", grain="発話", aggregate="count", value_class="count", path=""):
        population = _count(population)
        missing = _count(missing)
        observed = population - missing if observed is None else _count(observed)
        if observed < 0:
            _fail()
        decimal = None if observed == 0 else _number(value)
        scale = 0 if decimal is None else max(0, -Decimal(decimal).as_tuple().exponent)
        records.append(MetricResult.from_dict({
            "result_id": result["result_id"] + ":" + str(len(records)),
            "dataset_id": identity["initial_id"], "dataset_name": "固定会話の記述集計",
            "metric_id": method + ":" + key, "metric_revision": revision,
            "label": label, "value_class": value_class, "aggregate": aggregate,
            "value": decimal, "scale": scale, "rounding": "half_even",
            "unit": unit, "unit_label": unit_label, "grain": grain,
            "group": [{"dimension": "group", "label": "集計区分", "value": group}],
            "filters": list(filters), "filter_hash": filter_hash, "period": None,
            "population_count": population, "observed_count": observed, "missing_count": missing,
            "suppressed_count": 0, "basis": "dataset_version", "discovery_complete": True,
            "dataset_version": identity["data_version"], "observed_at": None,
            "consistency": "fixed_snapshot", "query_hash": fingerprint({"raw_hash": result["raw_hash"],
                "profile": PROFILE, "key": key, "path": path}),
            "source_ref": "db://orchestration_results/" + result["result_id"] + "/" + path}))

    if method == "participation":
        rows = raw["datasets"]["speakers"]["rows"]
        groups = [str(row.get("speaker_name") or row["speaker"]) for row in rows]
        if len(set(["全体", *groups])) != len(groups) + 1:
            _fail("metric_group_ambiguous")
        total = sum(_count(row["turn_count"]) for row in rows)
        add("turn_count", "発話数", total, population=total, path="datasets/speakers")
        for i, row in enumerate(rows):
            n = _count(row["turn_count"])
            group = str(row.get("speaker_name") or row["speaker"])
            add("turn_count", "発話数", n, population=n, group=group, path=f"datasets/speakers/{i}/turn_count")
            add("speaking_seconds", "発話時間の合計", row["speaking_seconds"], population=n,
                observed=_count(row["timed_turn_count"]), missing=_count(row["missing_time_turn_count"]),
                group=group, unit="second", unit_label="秒", value_class="amount", aggregate="sum",
                path=f"datasets/speakers/{i}/speaking_seconds")
            add("characters", "文字数の合計", row["characters"], population=n, group=group,
                unit="character", unit_label="文字", aggregate="sum", path=f"datasets/speakers/{i}/characters")
    elif method == "conversation_dynamics":
        for dataset, label in (("gaps", "記録済み無音区間"), ("overlaps", "記録済み重複区間")):
            rows = raw["datasets"][dataset]["rows"]
            add(dataset + "_count", label + "の件数", len(rows), population=len(rows),
                unit="interval", unit_label="区間", grain=label, path="datasets/" + dataset)
            observed = [row["seconds"] for row in rows if row.get("seconds") is not None]
            # 小数の桁数は元の値を保持し、codecに合わせる暗黙の丸めを行わない。
            with localcontext(Context(prec=50)) as arithmetic:
                arithmetic.traps[Inexact] = True
                duration = sum((Decimal(_number(v)) for v in observed), Decimal(0))
            add(dataset + "_seconds", label + "の時間合計", duration, population=len(rows),
                observed=len(observed), missing=len(rows) - len(observed), unit="second", unit_label="秒",
                grain=label, value_class="amount", aggregate="sum", path="datasets/" + dataset + "/seconds")
    elif method == "label_frequency":
        n, missing = _count(raw["denominator"]), _count(raw["missing_count"])
        if raw["dataset_version"] != identity["data_version"] or raw["annotation_version"] != identity["annotation_version"]:
            _fail("metric_source_changed")
        add("population", "ラベル集計対象数", n, population=n, path="denominator")
        add("missing", "ラベル欠測数", missing, population=n, path="missing_count")
        add("observed", "ラベル観測数", n - missing, population=n, path="denominator-minus-missing")
        for i, row in enumerate(raw["rows"]):
            count = _count(row["count"])
            if count > n - missing or row["denominator"] != n:
                _fail()
            add("frequency:" + raw["label_field"], "ラベル出現発話数", count, population=n,
                missing=missing, group=str(row["label"]), path=f"rows/{i}/count")
    else:
        n, missing = _count(raw["denominator"]), _count(raw["missing_count"])
        if (raw["dataset_version"] != identity["data_version"]
                or raw["annotation_version"] != identity["annotation_version"]
                or raw["observed_count"] != n - missing):
            _fail("metric_source_changed")
        add("population", "クロス集計対象発話数", n, population=n, path="denominator")
        add("missing", "話者またはラベルの欠測発話数", missing, population=n, path="missing_count")
        add("observed", "クロス集計有効発話数", n - missing, population=n, path="observed_count")
        groups = {row["speaker"]: row for row in raw["row_totals"]}
        for i, group in enumerate(raw["row_totals"]):
            size, absent = _count(group["denominator"]), _count(group["missing_count"])
            add("row_population", "話者内の対象発話数", size, population=size, group=group["speaker"],
                path=f"row_totals/{i}/denominator")
            add("row_missing", "話者内のラベル欠測発話数", absent, population=size, group=group["speaker"],
                path=f"row_totals/{i}/missing_count")
        for i, row in enumerate(raw["rows"]):
            group = groups[row["speaker"]]
            count = _count(row["count"])
            if (count > group["observed_count"] or row["row_denominator"] != group["denominator"]
                    or row["denominator"] != n):
                _fail()
            add("cell_count:" + raw["label_field"], "話者×ラベルの発話数", count,
                population=group["denominator"], missing=group["missing_count"],
                group=json.dumps([row["speaker"], row["label"]], ensure_ascii=False), path=f"rows/{i}/count")
    return records


def prepare(context):
    """ホスト専用対応表と、AIへ渡す公開投影を分離する。"""
    Encoder, _, _, _ = require_available()
    identity = {"run_id": context["resources_origin"]["run_id"], "initial_id": context["initial"]["initial_id"],
                "data_version": context["data_version"], "annotation_version": context["annotation_version"],
                "task_id": context["task"]["task_id"]}
    sources = [r for r in context.get("results", []) if r.get("role") == "statistics"]
    if not sources:
        _fail("metric_sources_missing")
    records, bindings = [], []
    for source in sources:
        if fingerprint(source["content"]) != source["raw_hash"]:
            _fail("metric_source_changed")
        rows = records_for(source, identity)
        records.extend(rows)
        bindings.append({"result_id": source["result_id"], "raw_hash": source["raw_hash"],
                         "record_ids": [r.result_id for r in rows]})
    run_id = str(uuid5(NAMESPACE_URL, fingerprint({"identity": identity, "sources": bindings})))
    try:
        encoded = Encoder(records).encode(run_id=run_id)
    except ValueError:
        _fail("metric_codec_limit_or_invalid")
    state = encoded.to_state()
    contract = {"version": VERSION, "profile": PROFILE, "identity": identity, "sources": bindings,
                "state": state, "state_sha256": fingerprint(state)}
    value = copy.deepcopy(context)
    by_source = {s["result_id"]: set(s["record_ids"]) for s in bindings}
    for result in value["results"]:
        if result["result_id"] in by_source:
            result["content"] = {"read_scope": "metric_codec_projection", "metric_refs": [b["ref"] for b in state["bindings"]
                if b["record"]["result_id"] in by_source[result["result_id"]]],
                "limitations": result["content"].get("limitations", []), "raw_result_preserved": True}
    value["metric_context"] = encoded.model_payload
    # 必須の各集計元を最低1回選ぶための参照集合。内部ID・対応表は配送しない。
    value["metric_context"]["sources"] = [{"key": "source_" + str(i + 1), "refs": r["content"]["metric_refs"]}
        for i, r in enumerate(r for r in value["results"] if r["result_id"] in by_source)]
    if len(json.dumps(value["metric_context"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > 16 * 1024:
        _fail("metric_codec_limit_or_invalid")
    if len(bindings) > 4:
        _fail("metric_codec_limit_or_invalid")
    fields = {}
    by_ref = {b["ref"]: b["record"] for b in state["bindings"]}
    for source in value["metric_context"]["sources"]:
        variants, comparable = [], defaultdict(list)
        def item(operation, refs, minimum, maximum, values):
            return {"type": "object", "additionalProperties": False, "required": ["operation", "operands", "value"],
                "properties": {"operation": {"enum": [operation]}, "operands": {"type": "array", "minItems": minimum,
                    "maxItems": maximum, "uniqueItems": True, "items": {"enum": refs}}, "value": {"enum": values}}}
        for ref in source["refs"]:
            record = by_ref[ref]
            # valueは参照ごとに元値と結び付け、生成時にも誤写を拒否する。
            variants.append(item("value", [ref], 1, 1, [record["value"]]))
            if record["value"] is not None:
                key = tuple(record[k] for k in ("metric_id", "metric_revision", "value_class", "aggregate", "unit", "grain", "basis", "dataset_version", "filter_hash"))
                comparable[key].append(ref)
        for refs in comparable.values():
            if len(refs) < 2:
                continue
            first = by_ref[refs[0]]
            if first["value_class"] != "ratio":
                variants.append(item("diff", refs, 2, 2, [None]))
            if first["value_class"] in {"count", "amount"} and first["aggregate"] in {"count", "sum"}:
                variants.append(item("ratio", refs, 2, 2, [None]))
            for operation in ("max", "min"):
                variants.append(item(operation, refs, 2, len(refs), [None]))
        fields[source["key"]] = {"anyOf": variants}
    schema = {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}
    return value, contract, schema


def validate(db, run, task, response):
    """保存済みの原応答を、現在の同一runの固定結果と照合してからデコードする。"""
    contract = task.get("context_manifest", {}).get("metric_contract")
    expected = (run["config"].get("metric_codec_version") == VERSION and task["role"] == "orchestrator"
                and task["intent"].get("scope", {}).get("domain") == "statistics")
    if not expected:
        if contract or "metric_selections" in response:
            _fail()
        return None
    if not contract or contract.get("version") != VERSION or contract.get("profile") != PROFILE:
        _fail()
    identity = contract["identity"]
    if identity != {"run_id": run["run_id"], "initial_id": run["initial_id"], "data_version": run["input_hash"],
                    "annotation_version": task["annotation_version"], "task_id": task["task_id"]}:
        _fail("metric_source_changed")
    if fingerprint(contract["state"]) != contract["state_sha256"] or response.get("claims"):
        _fail()
    requested = task["context_manifest"].get("requested_result_ids", [])
    if set(requested) != {s["result_id"] for s in contract["sources"]}:
        _fail("metric_source_changed")
    sources = []
    for binding in contract["sources"]:
        row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                         (binding["result_id"], run["run_id"])).fetchone()
        if row is None:
            _fail("metric_source_changed")
        raw, meta = json.loads(row[0]), json.loads(row[1])
        if (meta.get("role") != "statistics" or meta["validation_status"] != "valid"
                or fingerprint(raw) != binding["raw_hash"] or meta["raw_hash"] != binding["raw_hash"]):
            _fail("metric_source_changed")
        sources.append({**meta, "content": raw})
    _, regenerated, _ = prepare({"resources_origin": {"run_id": run["run_id"]},
        "initial": {"initial_id": run["initial_id"]}, "data_version": run["input_hash"],
        "annotation_version": task["annotation_version"], "task": task, "results": sources})
    if fingerprint(regenerated) != fingerprint(contract):
        _fail("metric_source_changed")
    _, Decoder, _, Encoded = require_available()
    selections = response.get("metric_selections")
    keys = ["source_" + str(i + 1) for i in range(len(contract["sources"]))]
    if not isinstance(selections, dict) or set(selections) != set(keys):
        _fail("metric_coverage_incomplete")
    for key, source in zip(keys, contract["sources"]):
        allowed = {b["ref"] for b in contract["state"]["bindings"] if b["record"]["result_id"] in source["record_ids"]}
        operands = selections[key].get("operands") if isinstance(selections[key], dict) else None
        if not isinstance(operands, list) or any(not isinstance(r, str) or r not in allowed for r in operands):
            _fail("metric_reference_out_of_scope")
    try:
        decoded = Decoder(Encoded.from_state(contract["state"])).decode(
            {"status": "answered", "items": [selections[key] for key in keys]}, run_id=contract["state"]["run_id"])
    except (ValueError, KeyError) as exc:
        _fail(getattr(exc, "code", "metric_response_invalid"))
    selected = {m.result_id for item in decoded.items for m in item.operands}
    if decoded.status != "answered" or any(not selected.intersection(s["record_ids"]) for s in contract["sources"]):
        _fail("metric_coverage_incomplete")
    if len(decoded.items) > 4:
        _fail()
    return {"version": VERSION, "profile": PROFILE, "state_sha256": contract["state_sha256"],
            "encoder": "obusql_agent.metric_codec.MetricEncoder", "decoder": "obusql_agent.metric_codec.MetricDecoder",
            "status": decoded.status, "answer": decoded.answer, "source_result_ids": [s["result_id"] for s in contract["sources"]],
            "items": [{"citation": item.citation, "operation": item.operation, "value": item.result_value,
                       "unit": item.result_unit, "scale": item.scale, "rounding": item.rounding,
                       "source_records": [m.result_id for m in item.operands]} for item in decoded.items]}
