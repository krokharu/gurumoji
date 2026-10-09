"""Closed Gemma/LM Studio counter, not production measurement acceptance.

The caller provides the unchanged effective Jinja, an owned read-only tokenizer,
AND a fresh condition reader. No SDK loading, inference, config changes or IO are
performed here. The reader must inspect the current loaded instance and effective
config, not return a cached acceptance manifest. Tokenizer identity must identify
its actual immutable model/tokenizer artifacts, not merely a friendly model name.

The response schema is REST grammar configuration. This renderer does not pass it
to Jinja. The finite Issue34 P4 example supports that example's exact input/usage;
it does NOT establish general REST schema/template equivalence. A production
caller must independently verify a C0/Windows receipt for its fixed source SHA,
conditions and schema scope before supplying acceptance_anchor/synthetic_only.
complete_coverage describes this closed mapping only; it is not such a receipt.
Fresh snapshots cannot rule out server mutation between the final check and send.
Strict raw usage equality in RequestBudget remains mandatory.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
from typing import Callable

from .request_budget import BudgetHold, COVERAGE, HASH_PATTERN, payload_hash

MODEL = "google/gemma-4-12b"
TEMPLATE_SHA256 = "6a1015c47ccfcfa67c3b772385bccee357a4d37c3cda37bd202e9047f391ab82"
# Construct fresh dictionaries; callers cannot mutate renderer settings globally.
def renderer_variables() -> dict:
    return {"enable_thinking": False, "preserve_thinking": False,
        "add_generation_prompt": True, "bos_token": "<bos>", "eos_token": "<eos>"}


CONDITION_KEYS = frozenset({"model", "model_identity", "tokenizer", "loaded_instance_id",
    "context_tokens", "parallel", "quantization", "reasoning_effort",
    "effective_config_hash", "template_sha256", "renderer_variables"})
PAYLOAD_KEYS = frozenset({"model", "messages", "temperature", "stream", "max_tokens", "reasoning_effort"})
SCHEMA_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})


def _reject(reason: str) -> None:
    raise BudgetHold(reason) from None


def _schema(node: dict, depth: int = 0) -> None:
    """A deliberately finite JSON Schema subset; unsupported dialects fail closed.

    Supports typed objects/arrays/scalars and anyOf, with descriptions, enums,
    constants and basic scalar/array bounds. No refs, remote resolution, arbitrary
    annotations or schema-dialect guessing. Acceptance of REST grammar is separate.
    """
    reason = "renderer_schema_not_supported"
    if type(node) is not dict or depth > 64:
        _reject(reason)
    common = {"type", "description", "title", "enum", "const"}
    kind = node.get("type")
    allowed = {
        "object": {"properties", "required", "additionalProperties"},
        "array": {"items", "minItems", "maxItems", "uniqueItems"},
        "string": {"minLength", "maxLength", "pattern"},
        "number": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
        "integer": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
        "boolean": set(), "null": set(),
    }
    if "anyOf" in node:
        if set(node) - {"anyOf", "description", "title"} or type(node["anyOf"]) is not list or not node["anyOf"]:
            _reject(reason)
        for child in node["anyOf"]:
            _schema(child, depth + 1)
    elif type(kind) is not str or kind not in SCHEMA_TYPES or set(node) - common - allowed[kind]:
        _reject(reason)
    for key in ("description", "title", "pattern"):
        if key in node and type(node[key]) is not str:
            _reject(reason)
    if "pattern" in node:
        try:
            re.compile(node["pattern"])
        except re.error:
            _reject(reason)
    if kind == "object":
        props, required = node.get("properties"), node.get("required")
        if (type(props) is not dict or any(type(k) is not str for k in props)
                or node.get("additionalProperties") is not False or type(required) is not list
                or any(type(k) is not str for k in required) or len(set(required)) != len(required)
                or not set(required) <= set(props)):
            _reject(reason)
        for child in props.values():
            _schema(child, depth + 1)
    elif kind == "array":
        _schema(node.get("items"), depth + 1)
        if "uniqueItems" in node and type(node["uniqueItems"]) is not bool:
            _reject(reason)
    for low, high in (("minItems", "maxItems"), ("minLength", "maxLength")):
        for key in (low, high):
            if key in node and (type(node[key]) is not int or node[key] < 0):
                _reject(reason)
        if low in node and high in node and node[low] > node[high]:
            _reject(reason)
    for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"):
        if key in node and (type(node[key]) not in (int, float) or not math.isfinite(node[key])):
            _reject(reason)
    if "multipleOf" in node and node["multipleOf"] <= 0:
        _reject(reason)
    if "minimum" in node and "maximum" in node and node["minimum"] > node["maximum"]:
        _reject(reason)
    if "enum" in node:
        if type(node["enum"]) is not list or not node["enum"]:
            _reject(reason)
        hashes = [payload_hash(v) for v in node["enum"]]
        if len(set(hashes)) != len(hashes):
            _reject(reason)
    # Scalar constants/enumerations cannot contradict their declared type.
    for value in node.get("enum", []) + ([node["const"]] if "const" in node else []):
        if not {"object": type(value) is dict, "array": type(value) is list,
                "string": type(value) is str, "number": type(value) in (int, float),
                "integer": type(value) is int, "boolean": type(value) is bool,
                "null": value is None}.get(kind, False):
            _reject(reason)


def validate_payload(payload: dict) -> None:
    """Validate without normalization, marker replacement or input mutation."""
    reason = "renderer_payload_not_supported"
    try:
        if type(payload) is not dict or set(payload) not in (PAYLOAD_KEYS, PAYLOAD_KEYS | {"response_format"}):
            _reject(reason)
        if (payload["model"] != MODEL or type(payload["model"]) is not str
                or type(payload["temperature"]) is not float or payload["temperature"] != 0.1
                or payload["stream"] is not False or payload["reasoning_effort"] != "none"
                or type(payload["max_tokens"]) is not int or not 1 <= payload["max_tokens"] <= 4096):
            _reject(reason)
        reason = "renderer_messages_not_supported"
        messages = payload["messages"]
        if type(messages) is not list or len(messages) != 2:
            _reject(reason)
        for message, role in zip(messages, ("system", "user")):
            if (type(message) is not dict or set(message) != {"role", "content"}
                    or message["role"] != role or type(message["content"]) is not str):
                _reject(reason)
        if "response_format" in payload:
            reason = "renderer_schema_not_supported"
            fmt = payload["response_format"]
            if type(fmt) is not dict or set(fmt) != {"type", "json_schema"} or fmt["type"] != "json_schema":
                _reject(reason)
            schema = fmt["json_schema"]
            if (type(schema) is not dict or set(schema) != {"name", "strict", "schema"}
                    or type(schema["name"]) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", schema["name"])
                    or schema["strict"] is not True or type(schema["schema"]) is not dict
                    or schema["schema"].get("type") != "object"):
                _reject(reason)
            _schema(schema["schema"])
        # Also reject NaN/Infinity, cycles, non-JSON values and invalid UTF-8.
        payload_hash(payload)
    except BudgetHold:
        raise
    except Exception:
        _reject(reason)


class LMStudioTemplateCounter:
    """Callable RequestBudget token_counter with a final-dispatch verifier seam.

    effective_template is the exact UTF-8 getLoadConfig template (no trailing LF
    added). verify_conditions() returns the freshly observed CONDITION_KEYS
    manifest. Identity/hash values are externally pinned, never auto-discovered
    or self-approved here. Passing the object itself preserves dispatch checking;
    wrapping only __call__ without its verifier is rejected by RequestBudget.
    """

    def __init__(self, *, effective_template: str, conditions: dict,
            tokenize: Callable[[str], list[int]], verify_conditions: Callable[[], dict],
            proof_source: str, acceptance_anchor: str, synthetic_only: bool):
        try:
            if (type(effective_template) is not str
                    or hashlib.sha256(effective_template.encode("utf-8")).hexdigest() != TEMPLATE_SHA256):
                _reject("renderer_conditions_changed")
            fixed = {"model": MODEL, "context_tokens": 32768, "parallel": 1,
                "quantization": "Q4_K_M", "reasoning_effort": "none",
                "template_sha256": TEMPLATE_SHA256, "renderer_variables": renderer_variables()}
            if (type(conditions) is not dict or set(conditions) != CONDITION_KEYS
                    or any(payload_hash(conditions[k]) != payload_hash(v) for k, v in fixed.items())):
                _reject("renderer_conditions_changed")
            for key in ("model_identity", "tokenizer", "loaded_instance_id"):
                if type(conditions[key]) is not str or not conditions[key].strip() or len(conditions[key]) > 512:
                    _reject("renderer_conditions_changed")
            if not isinstance(conditions["effective_config_hash"], str) or not HASH_PATTERN.fullmatch(conditions["effective_config_hash"]):
                _reject("renderer_conditions_changed")
            if (not callable(tokenize) or not callable(verify_conditions) or type(synthetic_only) is not bool
                    or any(type(v) is not str or not v.strip() or len(v) > 512 for v in (proof_source, acceptance_anchor))):
                _reject("renderer_conditions_changed")
            self._manifest_hash = payload_hash(conditions)
            self._tokenize, self._verify_conditions = tokenize, verify_conditions
            self._proof_conditions = {"model": MODEL, "context_tokens": 32768,
                "tokenizer": conditions["tokenizer"], "template": "sha256:" + TEMPLATE_SHA256,
                "source": proof_source, "acceptance_anchor": acceptance_anchor,
                "model_conditions_hash": self._manifest_hash, "synthetic_only": synthetic_only,
                "usage_policy": "reasoning_disabled"}
            # Lazy import keeps the existing stdlib-only HTTP worker independent
            # of Jinja. No dependency installation or alternative renderer.
            from jinja2.sandbox import ImmutableSandboxedEnvironment
            self._template = ImmutableSandboxedEnvironment(autoescape=False).from_string(effective_template)
        except BudgetHold:
            raise
        except Exception:
            _reject("renderer_conditions_changed")

    @property
    def budget_conditions(self) -> dict:
        """A defensive copy in the RequestBudget proof vocabulary."""
        return copy.deepcopy(self._proof_conditions)

    validate_payload = staticmethod(validate_payload)

    def _fresh(self) -> None:
        try:
            observed = self._verify_conditions()
            if type(observed) is not dict or payload_hash(observed) != self._manifest_hash:
                _reject("renderer_conditions_changed")
        except Exception:
            _reject("renderer_conditions_changed")

    def render(self, payload: dict) -> str:
        """Raw strings enter the fixed template unchanged, including literal markers.

        The pinned Jinja itself trims boundary whitespace. Do not strip/normalize
        the payload or rewrite that template to hide this difference.
        """
        validate_payload(payload)
        try:
            return self._template.render(messages=copy.deepcopy(payload["messages"]),
                tools=[], **renderer_variables())
        except Exception:
            _reject("renderer_payload_not_supported")

    def __call__(self, payload: dict) -> dict:
        validate_payload(payload)
        original_hash = payload_hash(payload)
        self._fresh()
        rendered = self.render(payload)
        try:
            ids = self._tokenize(rendered)
            # A count integer, booleans, lazy iterators and guessed offsets are
            # not a tokenizer result. Materialized actual integer IDs only.
            if type(ids) not in (list, tuple) or not ids or any(type(i) is not int or i < 0 for i in ids):
                _reject("renderer_tokenizer_unknown")
            counted = len(ids)
        except Exception:
            _reject("renderer_tokenizer_unknown")
        self._fresh()
        if payload_hash(payload) != original_hash:
            _reject("request_changed")
        return {**self.budget_conditions, "payload_hash": original_hash,
            "input_tokens": counted, "complete_coverage": True, "covered_fields": sorted(COVERAGE),
            "rendered_hash": "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "fresh_verification_required": True}

    def verify_before_dispatch(self, payload: dict, proof: dict) -> None:
        """Invoked by RequestBudget immediately before dispatching its worker.

        The shared worker validates ticket/payload hashes and absolute deadlines;
        it cannot carry Python callbacks over IPC. This does not claim to verify
        conditions atomically inside the remote model server's HTTP operation.
        """
        validate_payload(payload)
        if (type(proof) is not dict or proof.get("payload_hash") != payload_hash(payload)
                or any(payload_hash(proof.get(k)) != payload_hash(v) for k, v in self.budget_conditions.items())
                or proof.get("fresh_verification_required") is not True):
            _reject("token_proof_unknown")
        self._fresh()
