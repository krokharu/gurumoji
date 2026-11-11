"""合成JSONだけでObusSQL入力配送の可逆性・予算・停止を確認する。"""
import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import context_delivery as delivery, model_context


@pytest.fixture(autouse=True)
def enable(monkeypatch):
    monkeypatch.setenv("MOJIOKOSI_OBUSSQL_ENABLED", "1")


def packet(value):
    return model_context.reference_messages({"task": {"role": "interpretation"}, "raw_evidence": [],
        "question": "合成の問い", "results": value}, compact_references=True)


def test_original_text_conditions_ids_and_types_roundtrip():
    shared = "条件・例外を削らない合成の長い文字列です。" * 3
    results = [{"result_id": "r" + str(i), "condition": shared, "exceptions": ["空文字", "引用\"と\\改行\n"],
                "value": number} for i, number in enumerate([None, True, 1, 1.0, -0.0, 1.5])]
    user, data = packet(results)
    original = model_context.restored_reference_context(user, data)
    candidate = delivery.prepare(user, data)
    assert candidate["roundtrip_verified"]
    assert model_context.restored_reference_context(candidate["user"], []) == original
    assert delivery.original_messages(candidate["user"], [])[0] == delivery._json(json.loads(user))
    assert results[1]["condition"] == shared


@pytest.mark.parametrize("kind", ["o", "a"])
def test_every_json_prefix_cut_preserves_exact_original_characters(kind):
    value = {"rows": [{"説明": "引用\"\\と\n日本語", "n": i, "condition": [None, True, -0.0]} for i in range(5)],
             "tail": "合成末尾"}
    if kind == "a":
        value = [value, {"other": "条件"}]
    canonical = delivery._json(value)
    for end in range(1, len(canonical) + 1):
        text = canonical[:end]
        parsed = delivery._json_prefix(text)
        assert delivery._restore_json(parsed) == text
        logical = {"value": parsed}
        # 正規化済みprefixを含む配送も、元の切断位置まで正確に復元する。
        normalized = {"value": text}
        with patch.object(delivery, "_normalize", return_value=logical):
            candidate = delivery._project(normalized, hashlib.sha256(delivery._json(normalized).encode()).hexdigest())
        assert delivery.restore(candidate) == normalized


def test_long_partial_embedded_json_uses_complete_rows_without_inventing_tail():
    text = delivery._json({"rows": [{"condition": "必須条件", "exception": "例外"} for _ in range(100)]})[:-7]
    user, data = packet([{"content_excerpt": text, "truncated": True}])
    candidate = delivery.prepare(user, data)
    assert '"$prefix"' not in candidate["user"]
    restored = model_context.restored_reference_context(candidate["user"], [])
    assert restored["results"][0] == {"content_excerpt": text, "truncated": True}


@pytest.mark.parametrize("value", [True, 1, 1.0, -0.0, None])
def test_shared_values_do_not_coerce_types(value):
    values = {"a": value, "b": value, "c": value}
    user, data = packet(values)
    prepared = delivery.prepare(user, data)
    restored = model_context.restored_reference_context(prepared["user"], [])["results"]
    assert delivery._json(values) == delivery._json(restored)


def test_mixed_equal_python_values_keep_distinct_json_types():
    user, data = packet({"a": True, "b": 1, "c": 1.0})
    prepared = delivery.prepare(user, data)
    restored = model_context.restored_reference_context(prepared["user"], [])["results"]
    assert delivery._json(restored) == '{"a":true,"b":1,"c":1.0}'


def test_reserved_keys_and_disabled_dependency_fall_back(monkeypatch):
    user, data = packet({"$s": 123})
    assert delivery.prepare(user, data) is None
    monkeypatch.setenv("MOJIOKOSI_OBUSSQL_ENABLED", "0")
    user, data = packet([{"valid": "合成"}])
    assert delivery.prepare(user, data) is None


def test_payload_tamper_and_extra_messages_are_rejected():
    user, data = packet([{"reason": "同じ合成文字列" * 10} for _ in range(4)])
    candidate = delivery.prepare(user, data)
    changed = json.loads(candidate["user"])
    changed["instruction"]["question"] += "改変"
    with pytest.raises(ValueError, match="hash_mismatch"):
        delivery.restore(changed)
    with pytest.raises(ValueError, match="extra_messages"):
        delivery.original_messages(candidate["user"], ["追加資料"])


def budget(n):
    return {"template_input_tokens": n, "count_method": "loaded_model_tokenizer", "fits": n < 1000,
            "model": "synthetic", "model_info_sha256": "model", "load_config_sha256": "load",
            "loaded_context_length": 16384, "output_reserve": 3200, "safety_margin": 512}


@pytest.mark.parametrize("candidate_tokens,expected_format", [(800, delivery.FORMAT), (1200, "native_json")])
def test_smaller_full_template_only_is_selected(candidate_tokens, expected_format):
    user, data = packet([{"text": "合成のデータ"} for _ in range(4)])
    baseline = budget(1100)
    before = copy.deepcopy(baseline)
    system, sent, messages, chosen = delivery.select("system", user, data, baseline,
        lambda *args: budget(candidate_tokens))
    assert chosen["context_delivery"]["format"] == expected_format
    assert chosen["context_delivery"]["saved_tokens"] == max(0, 1100 - candidate_tokens)
    assert model_context.restored_reference_context(sent, messages) == model_context.restored_reference_context(user, data)
    assert baseline == before


def test_model_change_during_comparison_stops_before_inference():
    user, data = packet([{"text": "合成"}])
    with pytest.raises(AnalysisContractError) as error:
        delivery.select("system", user, data, budget(1100),
            lambda *args: {**budget(800), "load_config_sha256": "changed"})
    assert error.value.code == "context_budget_unavailable"


def test_obussql_verification_failure_is_not_hidden_by_native_fallback():
    from obsipg.delivery_codec import ResponseCodecAdapter
    from obsipg.delivery_contracts import DeliveryCoverage, DeliveryResult, DeliveryStatus
    bad = DeliveryResult(DeliveryStatus.VERIFICATION_FAILED, "TEST", DeliveryCoverage(("test",)), operation="response_encode")
    user, data = packet([{"text": "合成"}])
    with patch.object(ResponseCodecAdapter, "encode", return_value=bad), pytest.raises(AnalysisContractError) as error:
        delivery.prepare(user, data)
    assert error.value.code == "context_delivery_invalid"


def test_real_adapter_dispatches_only_selected_packet_and_records_actual_hashes():
    from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
    calls, manifests = [], []
    def provider(*args, **kwargs):
        calls.append((args, kwargs))
        return {"summary": "合成の回答", "claims": []}
    def meter(model, base, system, user, schema, **kwargs):
        result = budget(800 if json.loads(user).get("format") == delivery.FORMAT else 1100)
        result["output_reserve"] = 3200
        return result
    resolve, run = make_orchestration_adapters(call_ai_json=provider, context_meter=meter,
        load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
        configured_ai_credentials=lambda *_: ("", "synthetic"))
    context = {"task": {"role": "interpretation", "phase": "initial_analysis"}, "data_version": "version",
        "raw_evidence": [{"evidence_id": "original-evidence-id", "utterance_id": "original-utterance-id",
                          "text": "合成の条件と例外", "speaker": "A", "start": 0, "end": 1}]}
    run("interpretation", context, resolve({"model_context_version": 1}), lambda: None, manifests.append)
    assert len(calls) == 1
    args, keywords = calls[0]
    assert json.loads(args[4])["format"] == delivery.FORMAT
    assert keywords["data_messages"] == []
    manifest = manifests[0]["context_manifest"]
    assert manifest["user_sha256"] == model_context.digest(args[4])
    assert manifest["system_sha256"] == model_context.digest(args[3])
    assert manifest["budget"]["context_delivery"]["roundtrip_verified"]
    assert manifest["provided_evidence_ids"] == ["original-evidence-id"]
    restored = model_context.restored_reference_context(args[4], keywords["data_messages"])
    assert restored["raw_evidence"][0]["text"] == "合成の条件と例外"
