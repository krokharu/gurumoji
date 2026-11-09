"""Coreの追加分析と終了を排他的に表現する。"""
from __future__ import annotations

import copy

from .model_context import ReferenceResponseError


GUIDANCE = ("\n次の判断はnext_stepだけで返します。必要な追加分析があるならkind=analyze、"
            "intentsに1件以上を入れstop=nullにします。追加分析が不要ならkind=finish、"
            "intents=[]としstopに終了理由を記入します。未解決で人の判断が必要なら"
            "stop.reason=human_review_requiredです。終了と追加依頼を同時に選びません。")


class CoreControlResponseError(ReferenceResponseError):
    def __init__(self, response):
        super().__init__(response)
        self.code = "core_control_invalid"
        self.args = ("Coreの追加分析と終了の指定が回答形式に一致しません。原応答を保持して隔離します。",)


def controlled_schema(schema):
    value = copy.deepcopy(schema)
    properties = value["properties"]
    intents = properties.pop("intents")
    stop = properties.pop("stop")
    stop_object = next(part for part in stop["anyOf"] if part.get("type") == "object")
    def branch(kind, intent_schema, stop_schema):
        fields = {"kind": {"type": "string", "enum": [kind]},
                  "intents": intent_schema, "stop": stop_schema}
        return {"type": "object", "additionalProperties": False,
                "required": list(fields), "properties": fields}
    analyze_intents = copy.deepcopy(intents)
    analyze_intents["minItems"] = 1
    finish_intents = copy.deepcopy(intents)
    finish_intents["maxItems"] = 0
    finish_intents["items"] = {}
    properties["next_step"] = {"anyOf": [branch("analyze", analyze_intents, {"type": "null"}),
                                         branch("finish", finish_intents, stop_object)]}
    value["required"] = [key for key in value["required"] if key not in {"intents", "stop"}]
    value["required"].append("next_step")
    return value


def project_response(response):
    if not isinstance(response, dict) or "intents" in response or "stop" in response:
        raise CoreControlResponseError(response)
    step = response.get("next_step")
    if not isinstance(step, dict) or set(step) != {"kind", "intents", "stop"}:
        raise CoreControlResponseError(response)
    intents, stop = step["intents"], step["stop"]
    if not isinstance(intents, list):
        raise CoreControlResponseError(response)
    if step["kind"] == "analyze":
        valid = bool(intents) and stop is None
    elif step["kind"] == "finish":
        valid = (not intents and isinstance(stop, dict) and set(stop) == {"reason", "summary", "unresolved"}
                 and isinstance(stop["reason"], str)
                 and stop["reason"] in {"question_satisfied", "no_more_evidence", "human_review_required"}
                 and isinstance(stop["summary"], str) and isinstance(stop["unresolved"], list)
                 and all(isinstance(value, str) for value in stop["unresolved"]))
    else:
        valid = False
    if not valid:
        raise CoreControlResponseError(response)
    value = copy.deepcopy(response)
    value.update(intents=copy.deepcopy(intents), stop=copy.deepcopy(stop))
    return value
