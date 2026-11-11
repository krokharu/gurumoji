"""Handler of the Core pipeline: map every chunk, then let Core act on a bounded state.

The service keeps run/task persistence, budgets, stopping and recovery. This
module decides which tasks exist, builds their inputs, accepts their results
into the append-only analysis state and applies Core's chosen action.
"""
from __future__ import annotations

import copy
import json

from ..analysis_core import AnalysisContractError, fingerprint
from . import analysis_state, full_text_pipeline, pipeline_context
from .expert_agents import validate_shape

VERSION = pipeline_context.VERSION
ROLE = {"extract": "interpretation", "expert": "interpretation", "verify": "verification",
        "critic": "critic", "core": "core"}
CRITIC_PREFIX = "critic: "
COMPLETING = {"question_satisfied", "no_more_evidence"}
MAP_BODY_CHARS = 1200
KNOWN_THEMES = 20
IDLE_ROUNDS_LIMIT = 3
MAX_REASK = 2  # consecutive rejected Core answers asked again before the run stops
REASK_CODES = ("pipeline_", "state_", "expert_format_mismatch", "expert_reference_mismatch")


def _error(message, code):
    return AnalysisContractError(message, code=code)


def _now():
    from ..analysis_orchestration import _now
    return _now()


def _evidence(initial):
    return [row for row in initial["evidence"] if not row["excluded"]]


def _research_question(run, initial):
    question = run["config"].get("research_question")
    if isinstance(question, str) and question.strip():
        return question
    config = initial["analysis"].get("config")
    question = config.get("research_question") if isinstance(config, dict) else None
    return question if isinstance(question, str) and question.strip() else run["config"]["question"]


def _profile(run, expert_id):
    if not expert_id or "expert_agents" not in run:
        return None
    from .expert_agents import expert_profile
    return expert_profile(run["expert_agents"], expert_id)


def _register(svc, db, run, op, question, *, phase, evidence_ids=(), **extra):
    intent = {"role": ROLE[op], "question": question, "evidence_ids": list(evidence_ids), "kind": "analysis",
              "replicate_id": extra.pop("replicate_id", None), "pipeline": {"op": op, **extra}}
    return svc._register(db, run, intent, phase=phase, automatic=True)


def _coverage(run, state):
    return full_text_pipeline.coverage(run["pipeline"]["plan"], set(state["sources"].values()))


def _progress(svc, db, run, state):
    # Verification and critique are the Handler's at stop time, so no to-do list of them is shown.
    return {"iteration": run["iteration"], "min_iterations": run["config"].get("min_iterations", 0),
            "completed_core_iterations": svc._completed_core_iterations(db, run),
            "open_critic_questions": len(_open_critic_questions(state)),
            "live_claims": len(_live_claims(state)),
            "next_step": _next_step(state)}


def _next_step(state):
    """What the Handler can see is outstanding for Core itself; reviews are not listed (they are the Handler's)."""
    open_questions = len(_open_critic_questions(state))
    if open_questions:
        return (f"批判の問いが{open_questions}件開いています。question_closedのresolutionは、"
                "revised=開始時から対象主張の本文・根拠を変更、accepted_limit=対象をcontested/rejected、"
                "withdrawn=問いの撤回理由をreasonに記入。必要な変更を先に適用してください。閉じるまで終了できません。")
    if state["claims"]:
        return "開いている問いはありません。研究質問に答える主張が揃っていれば、propose_stopで終了を提案できます。"
    return "主張がまだありません。見出しから主張を作ってください。"


def _claim_hash(claim):
    return analysis_state.claim_digest(claim)


def _live_claims(state):
    return [(claim_id, claim) for claim_id, claim in sorted(state["claims"].items()) if claim["status"] != "rejected"]


def _unverified_claims(state):
    return [claim_id for claim_id, claim in _live_claims(state)
            if claim.get("verification", {}).get("digest") != _claim_hash(claim)]


def _unreviewed_claims(state, critiqued):
    return [claim_id for claim_id, claim in _live_claims(state) if critiqued.get(claim_id) != _claim_hash(claim)]


def _open_critic_questions(state):
    return [q for q, row in sorted(state["questions"].items())
            if row["status"] == "open" and row["text"].startswith(CRITIC_PREFIX)]


# Inputs ------------------------------------------------------------------------------------

def context(svc, db, run, task):
    """Model request for one pipeline task; its schema and offer are pinned to the task."""
    spec = task["intent"]["pipeline"]
    op = spec["op"]
    initial = svc._initial(db, run["initial_id"])
    evidence = _evidence(initial)
    question = _research_question(run, initial)
    state = analysis_state.load_state(db, run["run_id"])
    if op == "extract":
        plan = run["pipeline"]["plan"]
        full_text_pipeline.verify_plan(plan, evidence)
        chunk = next(c for c in plan["chunks"] if c["chunk_id"] == spec["chunk_id"])
        # Chunks are read in registration order; headings already used steer later chunks to reuse them.
        groups = sorted(analysis_state.themes(state).values(), key=lambda g: (-len(g["observation_ids"]), g["theme"]))
        known = [g["theme"] for g in groups[:KNOWN_THEMES]]
        task["pipeline_known_themes"] = known
        request = pipeline_context.extract_request(plan, chunk, evidence, research_question=question,
                                                   profile=_profile(run, next(iter(run["config"].get("expert_ids", [])), None)),
                                                   known_themes=known)
    elif op == "verify":
        request = pipeline_context.verify_request(state, spec["claim_id"], evidence, research_question=question)
        task["pipeline_claim_hash"] = _claim_hash(state["claims"][spec["claim_id"]])
    elif op == "critic":
        request = pipeline_context.critic_request(state, spec["claim_id"], evidence, research_question=question)
        task["pipeline_claim_hash"] = _claim_hash(state["claims"][spec["claim_id"]])
    elif op == "expert":
        request, offer = pipeline_context.expert_request(state, _profile(run, spec["expert_id"]), research_question=question)
        task["pipeline_offer"] = offer
    elif op == "core":
        reask = run["pipeline"].get("reask")
        notice = (f"直前のあなたの応答は契約に合わず採用されませんでした（{reask['code']}）。"
                  + (reask.get("condition") or "見出し・主張・操作は、提示した候補だけを使って指定し直してください。")) if reask else ""
        request, offer = pipeline_context.fitted_core_request(
            state, _coverage(run, state), experts=run["config"].get("expert_ids", []), research_question=question,
            instructions=run["config"]["question"], progress=_progress(svc, db, run, state), notice=notice)
        task["pipeline_offer"] = offer
    else:
        raise _error("未対応のpipelineタスクです。", "pipeline_task_invalid")
    request["task_id"] = task["task_id"]  # request-budget identity only; not part of the model input
    task["pipeline_schema"] = copy.deepcopy(request["schema"])
    if "refs" in request:
        task["pipeline_refs"] = request.pop("refs")
    if "omitted" in request:
        task["pipeline_verify_omitted"] = request.pop("omitted")
    task["pipeline_state_hash"] = analysis_state.state_hash(state)
    task["pipeline_planned_characters"] = request["planned_characters"]
    return request


# Acceptance --------------------------------------------------------------------------------

def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _core_events(state, raw, task):
    """Translate Core's state_ops into state events; IDs are fixed by task and position.

    Ops are replayed on a working copy so later ops see earlier ones. An op that would change
    nothing (same status, same text, nothing new to link) yields no event, and a new claim with
    the text of a live claim is linked to that claim instead of being added again.
    """
    working = copy.deepcopy(state)
    groups = analysis_state.themes(working)
    events = []

    def emit(event):
        nonlocal working, groups
        working = analysis_state.apply(working, event)
        groups = analysis_state.themes(working)
        events.append(event)

    for index, op in enumerate(raw["state_ops"]):
        name, seed = op["op"], [task["task_id"], index]
        if name == "claim_from_themes":
            members = list(dict.fromkeys(o for theme in dict.fromkeys(op["themes"])
                                         for o in groups[analysis_state._key(theme)]["observation_ids"]))
            counter = [o for o in members if working["observations"][o]["kind"] == "exception"]
            support = [o for o in members if o not in counter] or counter
            counter = [o for o in counter if o not in support]
            twin = next((cid for cid, claim in working["claims"].items() if claim["status"] != "rejected"
                         and analysis_state._key(claim["text"]) == analysis_state._key(op["text"])), None)
            if twin is None:
                emit({"op": "claim_added", "claim_id": "clm_" + fingerprint(seed)[7:19], "text": op["text"],
                      "support": support, "counter": counter})
                continue
            known = set(working["claims"][twin]["support"]) | set(working["claims"][twin]["counter"])
            fresh_support = [o for o in support if o not in known]
            fresh_counter = [o for o in counter if o not in known]
            if fresh_support or fresh_counter:
                emit({"op": "claim_linked", "claim_id": twin, "support": fresh_support, "counter": fresh_counter})
        elif name == "question_added":
            emit(analysis_state.question_event(working, "qst_" + fingerprint(seed)[7:19], op["text"],
                                               claim_id=op["claim_id"]))
        elif name == "claim_revise":
            if working["claims"][op["claim_id"]]["text"] != op["text"]:
                emit({"op": "claim_revised", "claim_id": op["claim_id"], "text": op["text"]})
        elif name == "claim_status":
            claim = working["claims"][op["claim_id"]]
            if claim["status"] != op["status"]:
                emit(copy.deepcopy(op))
        else:
            emit(copy.deepcopy(op))
    return events


def validate_result(svc, db, run, task, raw):
    """Accept one result for exactly the input it was given, or raise; nothing is repaired."""
    spec = task["intent"]["pipeline"]
    op = spec["op"]
    if analysis_state.state_hash(analysis_state.load_state(db, run["run_id"])) != task.get("pipeline_state_hash") \
            and op in {"core", "expert"}:
        raise _error("入力時から分析状態が変わっています。", "pipeline_state_changed")
    validate_shape(task["pipeline_schema"], raw)
    result_id = task["result_id"]
    state = analysis_state.load_state(db, run["run_id"])
    if op == "extract":
        chunk = next(c for c in run["pipeline"]["plan"]["chunks"] if c["chunk_id"] == spec["chunk_id"])
        accepted = full_text_pipeline.accept_extract(chunk, raw, task.get("pipeline_known_themes", []))
        analysis_state.append_event(db, run["run_id"], analysis_state.observations_event(
            chunk["chunk_id"], result_id, accepted), source_result_id=result_id, created_at=_now())
    elif op == "core":
        pipeline_context.check_core(raw, task["pipeline_offer"])
        try:
            _core_events(state, raw, task)
        except AnalysisContractError as exc:
            if exc.code == "state_resolution_mismatch":
                # applyが作った条件だけを再依頼へ渡し、モデルの自由記述は転送しない。
                task["pipeline_resolution_condition"] = str(exc)
            raise
    elif op == "verify":
        claim = state["claims"][spec["claim_id"]]
        if _claim_hash(claim) != task["pipeline_claim_hash"]:
            raise _error("検証中に主張が変わっています。", "pipeline_state_changed")
        # Supports only count: the utterances already rest in the claim. A contradiction is new
        # evidence and becomes a counter observation; unclear judgements are counted, not linked.
        counts = {"supports": 0, "contradicts": 0, "unclear": 0}
        rows, counter = [], []
        for index, (ref, item) in enumerate(raw["judgements"].items()):
            counts[item["judgement"]] += 1
            if item["judgement"] != "contradicts":
                continue
            observation_id = "obs_" + fingerprint([task["task_id"], index])[7:23]
            rows.append({"observation_id": observation_id, "evidence_ids": [task["pipeline_refs"][ref]],
                         "statement": item["note"].strip() or "contradicts", "kind": "exception",
                         "theme": claim["text"][:40], "origin": "verify"})
            counter.append(observation_id)
        events = []
        if rows:
            events += [{"op": "observations_added", "chunk_id": "vrf_" + task["task_id"], "result_id": result_id,
                        "observations": rows},
                       {"op": "claim_linked", "claim_id": spec["claim_id"], "support": [], "counter": counter}]
        for event in events:
            state = analysis_state.append_event(db, run["run_id"], event, source_result_id=result_id, created_at=_now())
        analysis_state.append_event(db, run["run_id"], {
            "op": "claim_verified", "claim_id": spec["claim_id"],
            "claim_digest": _claim_hash(state["claims"][spec["claim_id"]]), **counts,
            "omitted": task.get("pipeline_verify_omitted", 0)},
            source_result_id=result_id, created_at=_now())
    elif op == "critic":
        for index, issue in enumerate(raw["issues"]):
            if not _text(issue["text"]):
                raise _error("批判の本文が空です。", "pipeline_text_invalid")
            state = analysis_state.append_event(db, run["run_id"], analysis_state.question_event(
                state, "qst_" + fingerprint([task["task_id"], index])[7:19],
                (CRITIC_PREFIX + issue["text"])[:analysis_state.TEXT_CHARS], claim_id=spec["claim_id"]),
                source_result_id=result_id, created_at=_now())
        if not raw["issues"] and not _text(raw["no_issue_reason"]):
            raise _error("指摘なしの理由が空です。", "pipeline_text_invalid")
        run["pipeline"]["critiqued"][spec["claim_id"]] = task["pipeline_claim_hash"]
        svc._write_run(db, run)
    elif op == "expert":
        groups = analysis_state.themes(state)
        for index, proposal in enumerate(raw["proposals"]):
            if not _text(proposal["text"]):
                raise _error("解釈案の本文が空です。", "pipeline_text_invalid")
            members = groups[analysis_state._key(proposal["theme"])]["observation_ids"]
            counter = [o for o in members if state["observations"][o]["kind"] == "exception"]
            support = [o for o in members if o not in counter] or counter
            analysis_state.append_event(db, run["run_id"], {
                "op": "claim_added", "claim_id": "clm_" + fingerprint([task["task_id"], index])[7:19],
                "text": proposal["text"], "support": support, "counter": [o for o in counter if o not in support]},
                source_result_id=result_id, created_at=_now())
            state = analysis_state.load_state(db, run["run_id"])
    return None


# Driving -----------------------------------------------------------------------------------

def _start_map(svc, db, run):
    initial = svc._initial(db, run["initial_id"])
    evidence = _evidence(initial)
    tags = svc._outline_tags(db, run["initial_id"], initial)
    plan = full_text_pipeline.plan_chunks(evidence, tags["tags"] if tags else None, input_version=run["input_hash"],
                                          body_chars=MAP_BODY_CHARS)
    run["pipeline"] = {"version": VERSION, "plan": plan, "critiqued": {}}
    run["phase"] = "map"
    svc._write_run(db, run)
    svc._event(db, run["run_id"], "map_planned", f"本文を{len(plan['chunks'])}区間に分けて抽出します。",
               plan_hash=plan["plan_hash"], chunk_count=len(plan["chunks"]), evidence_count=plan["evidence_count"])
    for chunk in plan["chunks"]:
        ids = list(dict.fromkeys(segment[0] for segment in chunk["segments"]))
        _register(svc, db, run, "extract", f"本文区間{chunk['index'] + 1}の抽出", phase="map",
                  evidence_ids=ids, chunk_id=chunk["chunk_id"])


def _adopt_core(svc, db, run, task, result):
    meta, raw = json.loads(result["state_json"]), json.loads(result["raw_json"])
    if fingerprint(raw) != meta["raw_hash"] or meta.get("task_id") != task["task_id"]:
        raise _error("保存済みCore結果のhashが一致しません。", "result_integrity_mismatch")
    if db.execute("SELECT 1 FROM orchestration_decisions WHERE result_id=?", (meta["result_id"],)).fetchone():
        return
    state = analysis_state.load_state(db, run["run_id"])
    state_before = analysis_state.state_hash(state)
    for event in _core_events(state, raw, task):
        state = analysis_state.append_event(db, run["run_id"], event, source_result_id=meta["result_id"], created_at=_now())
    from ..analysis_orchestration import _id, _json
    decision = {"decision_id": _id("decision"), "result_id": meta["result_id"], "task_id": task["task_id"],
                "iteration": run["iteration"], "created_at": _now(), "summary": raw["summary"],
                "annotation_version": task["annotation_version"], "after_annotation_version": run["annotation_version"],
                "action": raw["action"], "reason": raw["reason"], "state_hash": analysis_state.state_hash(state)}
    db.execute("INSERT INTO orchestration_decisions VALUES (?,?,?,?)",
               (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
    run["last_decision_id"] = decision["decision_id"]
    run["pipeline"].pop("reask", None)
    run["pipeline"]["reask_count"] = 0
    run["current_view"] = {"summary": raw["summary"], "state_hash": decision["state_hash"],
        "claims": [{"claim_id": claim_id, "text": claim["text"], "kind": "interpretation",
                    "evidence_ids": pipeline_context.claim_evidence_ids(state, claim)}
                   for claim_id, claim in _live_claims(state)]}
    run["view_version"] += 1
    svc._event(db, run["run_id"], "core_decision", raw["summary"] or raw["reason"], source="core", target="handler",
               task_id=task["task_id"], action=raw["action"]["op"])
    # A decision that changes nothing and asks for nothing is idle; repeated idling is not progress.
    idle = analysis_state.state_hash(state) == state_before and raw["action"]["op"] == "none"
    run["pipeline"]["idle_rounds"] = run["pipeline"].get("idle_rounds", 0) + 1 if idle else 0
    if run["pipeline"]["idle_rounds"] >= IDLE_ROUNDS_LIMIT:
        svc._event(db, run["run_id"], "no_progress", "状態を変えず次の操作も選ばない判断が続いたため、人の確認へ回します。",
                   idle_rounds=run["pipeline"]["idle_rounds"])
        svc._stop(db, run, "human_review_required")
        return
    _act(svc, db, run, raw["action"], state)


def _act(svc, db, run, action, state):
    op = action["op"]
    replicate = analysis_state.state_hash(state)[7:19]
    registered = []
    if op == "reread_chunk":
        chunk = next(c for c in run["pipeline"]["plan"]["chunks"] if c["chunk_id"] == action["chunk_id"])
        ids = list(dict.fromkeys(segment[0] for segment in chunk["segments"]))
        registered.append(_register(svc, db, run, "extract", f"本文区間{chunk['index'] + 1}の再抽出", phase="actions",
                                    evidence_ids=ids, chunk_id=chunk["chunk_id"], replicate_id=replicate))
    elif op == "expert_interpret":
        registered.append(_register(svc, db, run, "expert", f"専門家{action['expert_id']}の解釈", phase="actions",
                                    expert_id=action["expert_id"], replicate_id=replicate))
    elif op == "propose_stop":
        _propose_stop(svc, db, run, action["stop_reason"], state)
        return
    if run["status"] in {"completed", "stopped", "cancelled", "failed"}:
        return
    run["phase"] = "actions" if any(registered) else "core"
    svc._write_run(db, run)


def _reask_core(svc, db, run, task):
    """A Core answer rejected for breaking the contract is asked again, a bounded number of times.

    The rejected result stays stored and quarantined; the new request carries the rejection code so
    the model can correct itself. Transport failures and unknown outcomes never come here.
    """
    if task is None or task["status"] != "quarantined":
        return False
    code = task.get("error") or ""
    count = run["pipeline"].get("reask_count", 0)
    if not code.startswith(REASK_CODES) or count >= MAX_REASK:
        return False
    run["pipeline"]["reask_count"] = count + 1
    run["pipeline"]["reask"] = {"code": code, "attempt": count + 1,
                                "condition": task.get("pipeline_resolution_condition", "")}
    svc._event(db, run["run_id"], "core_response_rejected", "契約に合わないCore応答を保存し、同じ入力で再依頼します。",
               task_id=task["task_id"], code=code, attempt=count + 1, limit=MAX_REASK)
    registered = _register(svc, db, run, "core", run["config"]["question"], phase="core",
                           replicate_id=f"reask-{count + 1}")
    svc._write_run(db, run)
    return registered is not None


def _propose_stop(svc, db, run, reason, state):
    if reason == "human_review_required":
        svc._stop(db, run, reason)
        return
    if svc._continue_minimum_iterations(db, run, reason):
        return
    # Verification first: it can add counter evidence, which would void a critique made before it.
    replicate = analysis_state.state_hash(state)[7:19]
    for kind, claims, title in (("verify", _unverified_claims(state), "終了前の原文検証"),
                                ("critic", _unreviewed_claims(state, run["pipeline"]["critiqued"]), "終了前レビュー")):
        if not claims:
            continue
        registered = [_register(svc, db, run, kind, f"{title}: 主張{claim_id}", phase="actions",
                                claim_id=claim_id, replicate_id=replicate) for claim_id in claims]
        if not any(registered):
            # Every review of this content was asked before and not adopted: asking again is the same
            # input, so stop for a person instead of looping on the proposal.
            svc._event(db, run["run_id"], "review_unavailable", f"{title}の結果が採用されておらず、同じ依頼は繰り返せません。",
                       claims=claims, review=kind)
            svc._stop(db, run, "human_review_required")
            return
        run["phase"] = "actions"
        svc._event(db, run["run_id"], "stop_review_requested", f"{title}を未実施の主張へ回します。",
                   claims=claims, review=kind, proposed_stop_reason=reason)
        svc._write_run(db, run)
        return
    if _open_critic_questions(state):
        run["phase"] = "core"
        svc._event(db, run["run_id"], "stop_rejected_open_questions", "批判の問いが開いているため終了しません。",
                   open_questions=len(_open_critic_questions(state)))
        svc._write_run(db, run)
        return
    coverage = _coverage(run, state)
    completed = reason in COMPLETING and coverage["complete"]
    if completed:
        run["review_status"] = "reviewed"
    svc._stop(db, run, reason if completed or reason not in COMPLETING else "full_text_incomplete", completed=completed)


def drive(svc, run_id):
    """Same durable driving contract as the legacy loop: persisted phases, no duplicate drivers."""
    from ..analysis_orchestration import TERMINAL
    try:
        with svc._db() as db:
            run = svc._read_run(db, run_id)
            if run["status"] in TERMINAL or run["status"] == "recovery_required":
                return
            svc._check_version(run)
            if any(t["status"] in {"running", "uncertain"} for t in svc._tasks(db, run_id)):
                run.update(status="recovery_required", error="進行中だった呼出しを照合してから再開してください。")
                svc._write_run(db, run)
                return
            if run["started_at"] is None:
                run["started_at"] = _now()
                svc._start_deadline(run)
            run["status"] = "running"
            svc._write_run(db, run)
            if "pipeline" not in run:
                _start_map(svc, db, run)
        while True:
            with svc._db() as db:
                run = svc._read_run(db, run_id)
                if run["status"] in TERMINAL or run["status"] == "recovery_required":
                    return
                limit = svc._limit(db, run)
                if limit:
                    svc._stop(db, run, limit)
                    return
                if run["phase"] == "core":
                    tasks = [t for t in svc._tasks(db, run_id) if t["role"] == "core" and t["iteration"] == run["iteration"]]
                    decided = tasks and tasks[-1]["status"] == "succeeded" and db.execute(
                        "SELECT 1 FROM orchestration_decisions WHERE result_id=?", (tasks[-1].get("result_id"),)).fetchone()
                    if not tasks or decided:
                        limit = svc._limit(db, run, new_round=True)
                        if limit:
                            svc._stop(db, run, limit)
                            return
                        run["iteration"] += 1
                        _register(svc, db, run, "core", run["config"]["question"], phase="core")
                        svc._write_run(db, run)
            svc._drain_tasks(run_id)
            with svc._db() as db:
                run = svc._read_run(db, run_id)
                if run["status"] in TERMINAL or run["status"] == "recovery_required":
                    return
                if any(t["status"] == "failed" for t in svc._tasks(db, run_id)):
                    svc._stop(db, run, svc._budget_reason(run) or "execution_failure")
                    return
                if run["phase"] in {"map", "actions"}:
                    if run["phase"] == "map":
                        coverage = _coverage(run, analysis_state.load_state(db, run_id))
                        svc._event(db, run_id, "map_completed",
                                   f"本文{coverage['evidence_read_count']}/{coverage['evidence_count']}件を抽出に採用しました。",
                                   **{k: coverage[k] for k in ("accepted_chunk_count", "chunk_count", "complete")})
                    run["phase"] = "core"
                    svc._write_run(db, run)
                    continue
                task = next((t for t in reversed(svc._tasks(db, run_id))
                             if t["role"] == "core" and t["iteration"] == run["iteration"]), None)
                if task is None or task["status"] != "succeeded":
                    if _reask_core(svc, db, run, task):
                        continue
                    svc._stop(db, run, svc._budget_reason(run) or "execution_failure")
                    return
                result = db.execute("SELECT * FROM orchestration_results WHERE task_id=? AND result_id=?",
                                    (task["task_id"], task["result_id"])).fetchone()
                db.execute("SAVEPOINT pipeline_adoption")
                try:
                    svc._require_budget(run, task["task_id"])
                    _adopt_core(svc, db, run, task, result)
                    svc._require_budget(run, task["task_id"])
                except AnalysisContractError as exc:
                    db.execute("ROLLBACK TO pipeline_adoption")
                    run = svc._read_run(db, run_id)
                    run["error"] = exc.code
                    if exc.code == "result_integrity_mismatch":
                        task.update(status="quarantined", validation_status="quarantined", error=exc.code)
                        meta = json.loads(result["state_json"])
                        meta.update(validation_status="quarantined", error=exc.code)
                        svc._write_task(db, task)
                        db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?",
                                   (json.dumps(meta, ensure_ascii=False), result["result_id"]))
                    svc._stop(db, run, svc._budget_reason(run, task["task_id"]) or "execution_failure")
                    return
                finally:
                    db.execute("RELEASE pipeline_adoption")
                if run["status"] not in TERMINAL:
                    svc._write_run(db, run)
    except Exception as exc:
        with svc._db() as db:
            run = svc._read_run(db, run_id)
            if run["status"] not in TERMINAL:
                run["error"] = getattr(exc, "code", type(exc).__name__)
                svc._stop(db, run, svc._budget_reason(run) or "execution_failure")
