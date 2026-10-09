"""Bounded read hooks inside a Core-issued expert task; no analysis dispatch."""
from __future__ import annotations

import copy
import json

from ..analysis_core import AnalysisContractError, fingerprint

VERSION = "expert-data-hooks-3"
MAX_ROUNDS = 2
MAX_REQUESTS = 3
MAX_CHARS = 12000
REQUEST_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["name", "evidence_ids", "result_id", "table_id", "offset", "limit"],
    "properties": {
        "name": {"type": "string", "enum": ["read_evidence", "read_calculation_table"]},
        "evidence_ids": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "result_id": {"type": "string", "maxLength": 200},
        "table_id": {"type": "string", "maxLength": 200},
        "offset": {"type": "integer"}, "limit": {"type": "integer"},
    },
}


def fail(code="expert_hook_invalid"):
    raise AnalysisContractError("専門家のデータ取得hookを確認してください。", code=code)


def prepare_context(context, *, evidence_limit=120, text_limit=60000):
    """Start with excerpts and an index; the fixed source stays with Handler."""
    value = copy.deepcopy(context)
    provided, remaining, omitted_text = [], min(MAX_CHARS, text_limit), 0
    for row in value["raw_evidence"]:
        if len(provided) >= min(12, evidence_limit) or remaining <= 0:
            break
        text = row["text"][:remaining]
        provided.append({**row, "text": text, "text_offset": 0,
                         "total_text_characters": len(row["text"]),
                         "omitted_text_characters": len(row["text"]) - len(text)})
        omitted_text += len(row["text"]) - len(text)
        remaining -= len(text)
    coverage = value["coverage"]
    coverage.update(provided_count=len(provided), omitted_count=coverage["available_count"] - len(provided),
                    complete=len(provided) == coverage["available_count"] and not omitted_text,
                    excerpt_text_incomplete=bool(omitted_text))
    value["raw_evidence"] = provided
    packet = value["expert_request"]
    packet["evidence"] = [{k: row.get(k) for k in ("evidence_id", "utterance_id", "text", "speaker")}
                          for row in provided]
    packet["coverage"] = copy.deepcopy(coverage)
    selected = set(context["task"]["intent"].get("evidence_ids", []))
    index = [row for row in coverage["evidence_index"] if not selected or row["evidence_id"] in selected]
    value["expert_hooks"] = {
        "version": VERSION, "max_rounds": MAX_ROUNDS,
        "context_evidence_limit": evidence_limit, "context_text_limit": text_limit,
        "evidence_index": index,
        "calculation_tables": [{"result_id": result["result_id"], "table_id": name,
                                "total_rows": table["total_rows"]}
                               for result in packet.get("calculations", [])
                               for name, table in result["datasets"].items()],
        "scope": "read only within the Core-issued task; new computations require Core approval",
    }
    return value


def read_data(request, *, evidence, calculations, allowed_evidence_ids, data_version,
              max_chars=MAX_CHARS, evidence_limit=8):
    """Only immutable evidence and already-validated calculation tables are read."""
    from .expert_agents import validate_shape
    validate_shape(REQUEST_SCHEMA, request)
    if request["offset"] < 0 or not 1 <= request["limit"] <= 40:
        fail()
    remaining = min(MAX_CHARS, max_chars)
    if request["name"] == "read_evidence":
        ids = request["evidence_ids"]
        if (not ids or len(set(ids)) != len(ids) or request["result_id"] or request["table_id"]
                or not set(ids) <= set(allowed_evidence_ids)):
            fail("expert_hook_scope_mismatch")
        rows = {row["evidence_id"]: row for row in evidence if not row["excluded"]}
        if not set(ids) <= set(rows):
            fail("evidence_missing")
        provided = []
        for eid in ids[:min(request["limit"], evidence_limit)]:
            row = rows[eid]
            start = min(request["offset"], len(row["text"]))
            text = row["text"][start:start + remaining]
            if not text and remaining <= 0:
                break
            provided.append({**{k: row.get(k) for k in ("evidence_id", "utterance_id", "speaker")},
                             "text": text, "text_offset": start,
                             "total_text_characters": len(row["text"]),
                             "omitted_text_characters": len(row["text"]) - len(text)})
            remaining -= len(text)
        content = {"evidence": provided, "requested_count": len(ids),
                   "provided_count": len(provided), "omitted_count": len(ids) - len(provided),
                   "complete": len(provided) == len(ids) and all(not r["omitted_text_characters"] for r in provided)}
        source_hash = fingerprint([rows[eid] for eid in ids])
    else:
        if request["evidence_ids"] or request["result_id"] not in calculations:
            fail("expert_hook_scope_mismatch")
        raw, metadata = calculations[request["result_id"]]
        table = raw["datasets"].get(request["table_id"])
        if table is None:
            fail("expert_hook_table_missing")
        offset, limit = request["offset"], request["limit"]
        if offset > len(table["rows"]):
            fail()
        provided = []
        for row in table["rows"][offset:offset + limit]:
            size = len(json.dumps(row, ensure_ascii=False))
            if size > remaining:
                break
            provided.append(copy.deepcopy(row))
            remaining -= size
        content = {"result_id": metadata["result_id"], "method_id": raw["method_id"],
                   "table_id": request["table_id"], "fields": copy.deepcopy(table["fields"]),
                   "rows": provided, "offset": offset, "total_rows": len(table["rows"]),
                   "next_offset": offset + len(provided), "omitted_rows": len(table["rows"]) - len(provided),
                   "complete": offset == 0 and len(provided) == len(table["rows"])}
        source_hash = metadata["raw_hash"]
    return {"hook": request["name"], "version": VERSION, "data_version": data_version,
            "source_hash": source_hash, **content}


PROMPT = """\nCoreから受け取った今回の指示範囲内で、必要なデータだけをhookで追加取得できます。
read_evidence: expert_hooks.evidence_indexのIDをevidence_idsに指定します。
offsetは原文の文字位置、limitは取得する発話数（最大8）。result_idとtable_idは空文字です。
read_calculation_table: expert_hooks.calculation_tablesのresult_idとtable_idを指定します。
offsetは表の行位置、limitは行数（最大40）。evidence_idsは空配列です。
応答はexpert_responseの中でデータ要求か報告のどちらかを返します。
データ要求: {"expert_response":{"mode":"read","hook_requests":[取得要求]}}。
報告・主張・追加分析案は同時に返せません。データ取得は分析・計算の新規発注ではありません。
最終報告: {"expert_response":{"mode":"report","result":通常の専門家応答}}。
resultにはsummary/claims/analysis_requests/label_patches/expert_reportをすべて含めます。
hook_requestsはreadの中だけに置き、resultには入れません。
今回の入力が抜粋であることだけを理由に対象外と判断せず、必要な未読根拠は取得して確認します。
追加取得は最大2巡です。同じ要求を繰り返さず、必要な要求をまとめてください。
入力の抜粋・省略・未読範囲を全量と扱いません。新しい計算・分析はanalysis_requestsでCoreへ提案します。
"""


def run_with_hooks(context, schema, call, execute, reserve_call, record_round):
    """Keep the expert in its task while Python serves bounded read requests."""
    from .expert_agents import validate_shape, bind_evidence_ids, numeric_binding_schema
    value, final_schema = copy.deepcopy(context), copy.deepcopy(schema)
    # This history contains only rows in model inputs, not all Handler reads.
    delivered_calculations = copy.deepcopy(value["expert_request"].get("calculations", []))
    seen = set()
    supplied_ids = {row["evidence_id"] for row in value["raw_evidence"]}
    for round_index in range(MAX_ROUNDS + 1):
        report_schema = {"type": "object", "additionalProperties": False, "required": ["mode", "result"],
                         "properties": {"mode": {"type": "string", "enum": ["report"]}, "result": copy.deepcopy(final_schema)}}
        read_schema = {"type": "object", "additionalProperties": False, "required": ["mode", "hook_requests"],
                       "properties": {"mode": {"type": "string", "enum": ["read"]},
                                      "hook_requests": {"type": "array", "minItems": 1, "maxItems": MAX_REQUESTS,
                                                        "items": copy.deepcopy(REQUEST_SCHEMA)}}}
        response_schema = {"anyOf": [read_schema, report_schema]} if round_index < MAX_ROUNDS else report_schema
        wire_schema = {"type": "object", "additionalProperties": False, "required": ["expert_response"],
                       "properties": {"expert_response": response_schema}}
        raw = call(value, wire_schema, round_index)
        # Terminal results are durably saved and validated by Handler. Preserve
        # malformed terminal reports there instead of losing the provider reply.
        response = raw.get("expert_response") if isinstance(raw, dict) else None
        if (isinstance(response, dict) and response.get("mode") == "report"
                and set(raw) == {"expert_response"} and set(response) == {"mode", "result"}
                and isinstance(response["result"], dict)):
            return response["result"]
        record_round(raw)
        validate_shape(wire_schema, raw)
        requests = response["hook_requests"]
        packets = []
        for request in requests:
            key = fingerprint(request)
            if key in seen:
                fail("expert_hook_no_progress")
            seen.add(key)
            packets.append(execute(request))
        new_evidence = []
        for packet in packets:
            if packet["hook"] == "read_evidence":
                new_evidence.extend(packet["evidence"])
                # Text appears once; receipts and coverage remain separately visible.
                value.setdefault("expert_hook_results", []).append({k: v for k, v in packet.items() if k != "evidence"})
            else:
                value.setdefault("expert_hook_results", []).append(packet)
                matches = [result for result in delivered_calculations if result["result_id"] == packet.get("result_id")]
                if len(matches) != 1 or packet.get("table_id") not in matches[0]["datasets"]:
                    fail("expert_hook_delivery_mismatch")
                result = matches[0]
                if (packet.get("version") != VERSION or packet.get("data_version") != value["data_version"]
                        or packet.get("source_hash") != result["raw_hash"]):
                    fail("expert_hook_delivery_mismatch")
                table = result["datasets"][packet["table_id"]]
                by_id = {row["row_id"]: row for row in table["rows"]}
                for row in packet["rows"]:
                    if row["row_id"] in by_id and fingerprint(by_id[row["row_id"]]) != fingerprint(row):
                        fail("expert_hook_delivery_mismatch")
                    by_id[row["row_id"]] = copy.deepcopy(row)
                table["rows"] = list(by_id.values())
                # Initial rows were already sent. Continuations carry each hook
                # packet once and preserve the original full-table manifest.
                for original in value["expert_request"].get("calculations", []):
                    if original["result_id"] == packet["result_id"]:
                        original["datasets"][packet["table_id"]].update(
                            rows=[], omitted_rows=table["total_rows"], read_via_hook_results=True)
        provided, keys = [], set()
        remaining = value["expert_hooks"]["context_text_limit"]
        for row in [*new_evidence, *value["raw_evidence"]]:
            key = (row["evidence_id"], row.get("text_offset", 0))
            if key in keys:
                continue
            if len(provided) >= value["expert_hooks"]["context_evidence_limit"] or remaining <= 0:
                break
            keys.add(key)
            text = row["text"][:remaining]
            total = row.get("total_text_characters", len(row["text"]))
            provided.append({**row, "text": text, "omitted_text_characters": total - len(text)})
            remaining -= len(text)
        value["raw_evidence"] = provided
        supplied_ids.update(row["evidence_id"] for row in provided)
        value["expert_request"]["evidence"] = [{"evidence_id": row["evidence_id"], "utterance_id": row["utterance_id"]}
                                                for row in provided]
        coverage = value["coverage"]
        count = len({row["evidence_id"] for row in provided})
        coverage.update(provided_count=count, omitted_count=coverage["available_count"] - count,
                        complete=count == coverage["available_count"] and all(not row["omitted_text_characters"] for row in provided))
        value["expert_request"]["coverage"] = copy.deepcopy(coverage)
        bind_evidence_ids(final_schema, sorted(supplied_ids))
        report = final_schema.get("properties", {}).get("expert_report", {}).get("properties", {})
        if "numeric_bindings" in report:
            report["numeric_bindings"] = numeric_binding_schema(delivered_calculations)
        calculation_packets = [packet for packet in value.get("expert_hook_results", [])
                               if packet["hook"] == "read_calculation_table"]
        # Legacy evidence-only callbacks still receive their ID list. With
        # calculations, Handler verifies hashes of the actual continuation
        # packets before reserving the next model call or authorizing rows.
        reserve_call({"evidence_ids": sorted(supplied_ids), "calculation_packets": copy.deepcopy(calculation_packets)}
                     if calculation_packets else sorted(supplied_ids))
    fail("expert_hook_round_limit")
