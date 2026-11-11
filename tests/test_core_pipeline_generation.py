"""ローカルの生成条件と中断応答の扱いを、合成入力だけで検証する。"""
from unittest.mock import Mock, patch

import json

import pytest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.core_pipeline_service import validate_orchestration_payload
from gurumoji.services import pipeline_context
from gurumoji.services.pipeline_adapter import call_pipeline
from gurumoji.services.ai.client import call_ai_json


@pytest.mark.parametrize("value", [None, [], {}, True, "on"])
def test_invalid_reasoning_rejected(value):
    with pytest.raises(AnalysisContractError):
        validate_orchestration_payload({"model": "TEST-model", "local_reasoning": value})


@pytest.mark.parametrize("value", [None, True, 127, 16385, 3.5, "4096"])
def test_invalid_output_limit_rejected(value):
    with pytest.raises(AnalysisContractError):
        validate_orchestration_payload({"model": "TEST-model", "local_max_output_tokens": value})


def test_new_runs_freeze_explicit_defaults_and_allow_model_default():
    config = validate_orchestration_payload({"model": "TEST-model"})
    assert config["local_reasoning"] == "off"
    assert config["local_max_output_tokens"] == 4096
    assert config["call_timeout_seconds"] == 120
    configured = validate_orchestration_payload({"model": "TEST-model", "local_reasoning": "auto",
                                                 "local_max_output_tokens": 2048})
    assert configured["local_reasoning"] == "auto"
    assert configured["local_max_output_tokens"] == 2048


@pytest.mark.parametrize("provider,options,expected", [
    ("lmstudio", {"local_reasoning": "off", "local_max_output_tokens": 4096},
                 {"local_reasoning_level": "off", "max_output_tokens": 4096}),
    ("lmstudio", {"local_reasoning": "auto", "local_max_output_tokens": 2048},
                 {"local_reasoning_level": "auto", "max_output_tokens": 2048}),
    ("lmstudio", {}, {}),
    ("openai", {"local_reasoning": "off", "local_max_output_tokens": 4096}, {}),
    ("google", {"local_reasoning": "off", "local_max_output_tokens": 4096}, {}),
])
def test_adapter_transfers_only_frozen_local_conditions(provider, options, expected):
    call = Mock(return_value={"TEST": True})
    request = pipeline_context.request("core", {}, {"type": "object"})
    result = call_pipeline(request, role="core", provider=provider, model="TEST-model", api_key="",
                           base_url="", options=options, call_ai_json=call,
                           check_cancelled=lambda: None, record_usage=lambda _: None)
    assert result == {"TEST": True}
    assert call.call_args.kwargs == expected


def test_budget_callbacks_preserve_generation_conditions():
    call = Mock(return_value={})
    budget, raw_usage = object(), Mock()
    request = pipeline_context.request("core", {}, {"type": "object"})
    request["task_id"] = "TEST-task"
    call_pipeline(request, role="core", provider="lmstudio", model="TEST-model", api_key="", base_url="",
                  options={"local_reasoning": "off", "local_max_output_tokens": 4096,
                           "_request_budget": budget, "_budget_attempt_id": "TEST-attempt",
                           "_raw_usage_callback": raw_usage},
                  call_ai_json=call, check_cancelled=lambda: None, record_usage=lambda _: None)
    assert call.call_args.kwargs == {"local_reasoning_level": "off", "max_output_tokens": 4096,
                                    "request_budget": budget, "task_id": "TEST-task",
                                    "attempt_id": "TEST-attempt:0", "raw_usage_callback": raw_usage}


def test_truncated_valid_json_records_usage_but_is_never_accepted():
    # JSON自体が正しくても、プロバイダーが上限到達を報告した応答は採用しない。
    post = Mock(return_value={"choices": [{"finish_reason": "length", "message": {"content": '{"ok":true}'}}],
                              "usage": {"prompt_tokens": 10, "completion_tokens": 128, "total_tokens": 138}})
    usage = []
    with pytest.raises(RuntimeError, match="トークン上限"):
        call_ai_json("lmstudio", "", "TEST-model", "TEST", "TEST", "gurumoji_pipeline_core", {},
                     post=post, lmstudio_base=lambda _: "http://TEST/v1", lmstudio_model_id=lambda m: m,
                     lmstudio_reasoning=lambda *_: {}, providers={"lmstudio"},
                     usage_callback=usage.append, max_output_tokens=128)
    assert post.call_args.args[2]["max_tokens"] == 128
    assert usage[0]["output_tokens"] == 128


@pytest.mark.parametrize("replay", [
    {}, {"local_reasoning": "off"}, {"local_reasoning": "auto"},
    {"local_max_output_tokens": 4096}, {"local_max_output_tokens": 2048},
    {"question": "TEST-changed-question"},
])
def test_preupgrade_start_replay_preserves_original_generation_conditions(replay):
    # 旧版の開始POSTと応答不明の再送を再現し、読取りだけで照合できることを確認する。
    import gurumoji.core_pipeline_service as service_module
    from test_developed_analysis_orchestration import RuntimeTests

    fixture = RuntimeTests()
    fixture.setUp()
    validate = service_module.validate_orchestration_payload

    def old_config(payload):
        config = validate(payload)
        for key in ("local_reasoning", "local_max_output_tokens"):
            config.pop(key)
        return config

    try:
        with patch.object(service_module, "validate_orchestration_payload", side_effect=old_config):
            original = fixture.start(request_id="TEST-upgrade-replay")
        with fixture.service._db() as db:
            before = tuple(db.execute("SELECT request_hash,state_json FROM orchestration_runs WHERE run_id=?",
                                      (original["run_id"],)).fetchone())
        if replay:
            with pytest.raises(AnalysisContractError) as caught:
                fixture.start(request_id="TEST-upgrade-replay", **replay)
            assert caught.value.code == "request_conflict"
        else:
            restored = fixture.start(request_id="TEST-upgrade-replay")
            assert restored["run_id"] == original["run_id"]
            assert "local_reasoning" not in restored["config"]
            assert "local_max_output_tokens" not in restored["config"]
        with fixture.service._db() as db:
            after = tuple(db.execute("SELECT request_hash,state_json FROM orchestration_runs WHERE run_id=?",
                                     (original["run_id"],)).fetchone())
            assert db.execute("SELECT COUNT(*) FROM orchestration_runs").fetchone()[0] == 1
        assert after == before
        assert fixture.calls == []
        assert json.loads(after[1])["config"] == original["config"]
    finally:
        fixture.doCleanups()


@pytest.mark.parametrize("present_field", ["local_reasoning", "local_max_output_tokens"])
def test_partially_versioned_config_cannot_use_preupgrade_replay(present_field):
    import gurumoji.core_pipeline_service as service_module
    from test_developed_analysis_orchestration import RuntimeTests

    fixture = RuntimeTests()
    fixture.setUp()
    validate = service_module.validate_orchestration_payload

    def partial_config(payload):
        config = validate(payload)
        missing = {"local_reasoning", "local_max_output_tokens"} - {present_field}
        config.pop(missing.pop())
        return config

    try:
        with patch.object(service_module, "validate_orchestration_payload", side_effect=partial_config):
            fixture.start(request_id="TEST-partial-upgrade")
        with pytest.raises(AnalysisContractError) as caught:
            fixture.start(request_id="TEST-partial-upgrade")
        assert caught.value.code == "request_conflict"
    finally:
        fixture.doCleanups()
