"""一時DBで使う新パイプラインの合成応答。実モデル評価ではない。"""
from gurumoji.services import full_text_pipeline


def scripted_reply(schema_name, packet):
    """送信要求から合成応答を作り、実モデルを使わず実際の実行経路を検証する。"""
    role = schema_name.rsplit("_", 1)[-1]
    if role == "extract":
        refs = [row[0] for row in packet["utterances"]["rows"]]
        return {"chunk_id": packet["chunk"]["chunk_id"], "uncovered_notes": "", "observations": [
            {"evidence_ids": refs[:2], "statement": "傾向の観察", "kind": "pattern", "reuse_theme": "",
             "new_theme": f"区間{packet['chunk']['index'] % 3}"},
            {"evidence_ids": refs[-1:], "statement": "例外の観察", "kind": "exception", "reuse_theme": "",
             "new_theme": f"区間{packet['chunk']['index'] % 3}"}]}
    if role == "verify":
        rows = packet["utterances"]["rows"]
        return {"claim_id": packet["claim"]["claim_id"], "judgements": {
            row[0]: {"judgement": "supports", "note": "支持"} for row in rows}}
    if role == "critic":
        return {"claim_id": packet["claim"]["claim_id"], "issues": [], "no_issue_reason": "指摘なし"}
    if role == "expert":
        return {"expert_id": packet["expert"]["expert_id"], "proposals": []}
    state = packet["state"]
    if state["claims"] == [] and state["themes"]:
        return {"summary": "整理", "reason": "見出しから主張を作る", "action": {"op": "none"},
                "state_ops": [{"op": "claim_from_themes", "themes": [state["themes"][0]["theme"]], "text": "主張"}]}
    cov = packet["coverage"]
    if cov["remaining_chunk_ids"]:
        return {"summary": "再読", "reason": "未読区間", "state_ops": [],
                "action": {"op": "reread_chunk", "chunk_id": cov["remaining_chunk_ids"][0]}}
    return {"summary": "終了", "reason": "整理済み", "state_ops": [],
            "action": {"op": "propose_stop", "stop_reason": "question_satisfied"}}


def reply(request):
    return scripted_reply(request["schema_name"], request["packet"])


def pin(service, db, run):
    if "pipeline" not in run:
        initial = service._initial(db, run["initial_id"])
        evidence = [row for row in initial["evidence"] if not row["excluded"]]
        run["pipeline"] = {"version": "core-pipeline-1", "plan": full_text_pipeline.plan_chunks(
            evidence, input_version=run["input_hash"], body_chars=1200), "critiqued": {}}
        service._write_run(db, run)


def core_task(service, db, run, **extra):
    pin(service, db, run)
    return service._register(db, run, {"role": "core", "question": "合成の判断", "pipeline": {"op": "core"}, **extra},
                             phase="core", automatic=True)


def start(service, item_id, payload, **kwargs):
    """公開payloadを通した後で、試験用の内部設定・固定知識だけを注入する。"""
    import copy
    from unittest.mock import patch
    import gurumoji.core_pipeline_service as orchestration
    payload = copy.deepcopy(payload)
    internal = {key: payload.pop(key) for key in ("call_timeout_seconds", "max_result_bytes") if key in payload}
    if "adapter_version" in payload:
        assert payload.pop("adapter_version") == "core-pipeline-1"
    supplied = {key: payload.pop(key) for key in ("expert_inputs", "skill_context") if key in payload}
    validate = orchestration.validate_orchestration_payload
    provider = service.expert_provider
    with patch.object(orchestration, "validate_orchestration_payload", side_effect=lambda p: {**validate(p), **internal}):
        if supplied and provider:
            with patch.object(service, "expert_provider", side_effect=lambda config: provider({**config, **supplied})):
                return service.start(item_id, payload, **kwargs)
        return service.start(item_id, payload, **kwargs)


def with_expert(service, expert_id, *, selected=False):
    """型付き候補・統計の単発契約を新しい送信包みで検証してからパイプラインを駆動する。"""
    original_run, original_agent = service.run, service.agent_runner
    def agent(role, request, *args):
        if "expert_request" in request["packet"]:
            return original_agent(role, response_packet(request, service=service), *args)
        return reply(request)
    service.agent_runner = agent
    def drive(run_id):
        with service._db() as db:
            run = service._read_run(db, run_id)
            if any(t.get("expert_agent") for t in service._tasks(db, run_id)):
                return original_run(run_id)
            task = service._register(db, run, {"role": "interpretation", "expert_id": expert_id,
                "question": run["config"]["question"], "why_now": "単発契約の検査", "success_criteria": "固定根拠と契約に適合",
                **({"evidence_ids": [row["evidence_id"] for row in service._initial(db, run["initial_id"])["evidence"][:2]]} if selected else {})}, phase="specialists")
        service._execute(run_id, task["task_id"])
        with service._db() as db:
            saved = next(t for t in service._tasks(db, run_id) if t["task_id"] == task["task_id"])
        if saved["status"] == "succeeded":
            original_run(run_id)
    service.run = drive
    return service


def task(service, db, run, role, **extra):
    from gurumoji.services import analysis_state
    pin(service, db, run)
    spec = {"op": "core"}
    if role == "interpretation":
        spec = {"op": "extract", "chunk_id": run["pipeline"]["plan"]["chunks"][0]["chunk_id"]}
    elif role in {"verification", "critic"}:
        state = analysis_state.load_state(db, run["run_id"])
        if not state["claims"]:
            eid = service._initial(db, run["initial_id"])["evidence"][0]["evidence_id"]
            analysis_state.append_event(db, run["run_id"], {"op": "observations_added", "chunk_id": "fixture",
                "result_id": "fixture", "observations": [{"observation_id": "obs_fixture", "evidence_ids": [eid],
                "statement": "合成の観察", "kind": "pattern", "theme": "合成"}]}, created_at="fixture")
            analysis_state.append_event(db, run["run_id"], {"op": "claim_added", "claim_id": "clm_fixture",
                "text": "合成の主張", "support": ["obs_fixture"], "counter": []}, created_at="fixture")
        spec = {"op": "verify" if role == "verification" else "critic", "claim_id": "clm_fixture"}
    return service._register(db, run, {"role": role, "question": "合成のタスク", "why_now": "試験",
        "success_criteria": "契約の検査", "pipeline": spec, **extra}, phase="core", automatic=True)


def limit_delivery(service, *, rows=None, characters=None):
    """負例の実配送を試験内で制限し、固定原本と配送証跡は一致させる。"""
    import copy
    from gurumoji.services.expert_agents import focus_group_interaction_delivery
    if rows is None and characters is None:
        return
    original = service._context
    def context(db, run, task):
        request = original(db, run, task)
        if "expert_request" not in request.get("packet", {}):
            return request
        packet = request["packet"]
        if rows is not None:
            packet["raw_evidence"] = packet["raw_evidence"][:rows]
        if characters is not None:
            for row in packet["raw_evidence"]:
                row["text"] = row["text"][:characters]
        packet["expert_request"]["evidence"] = copy.deepcopy(packet["raw_evidence"])
        profile = run["expert_agents"]["profiles"][task["expert_agent"]["expert_id"]]
        source = service._thematic_source(db, run, profile, service._initial(db, run["initial_id"]))
        packet["expert_request"]["delivery_coverage"] = focus_group_interaction_delivery(source, packet)
        task["expert_fgi_delivery"] = copy.deepcopy(packet["expert_request"]["delivery_coverage"])
        task["expert_evidence_ids"] = [r["evidence_id"] for r in packet["raw_evidence"]]
        return request
    service._context = context


def response_packet(request, *, service=None):
    """合成応答の生成器が、実際に送るschemaとpacketの両方を参照する。"""
    import copy
    packet = copy.deepcopy(request["packet"])
    if service is not None:
        import json
        with service._db() as db:
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (request["task_id"],)).fetchone()
            packet["task"] = json.loads(row[0])
            if "expert_request" in packet:
                run = service._read_run(db, packet["task"]["run_id"])
                packet["expert_request"]["knowledge"] = copy.deepcopy(run["expert_agents"]["profiles"][packet["expert_request"]["expert_id"]])
    if "expert_request" in packet:
        expert = packet["expert_request"]
        profile = expert["knowledge"]
        profile["profile_hash"] = expert["profile_hash"]
        profile["knowledge_hash"] = expert["knowledge_hash"]
        profile["output_schema"] = request["schema"]["properties"]["expert_report"]["properties"]["outputs"]
        if "typed_contract" in expert:
            profile["typed_contract"] = expert["typed_contract"]
        if "statistical_tools" in expert:
            profile["statistical_tools"] = expert["statistical_tools"]
    return packet
