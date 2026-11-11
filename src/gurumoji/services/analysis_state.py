"""Bounded analysis state: an append-only event log replayed into observations, claims and questions.

Map results and Core decisions are diffs; the current state is never stored
in place. Core reads view(), whose size depends on its limits, not on how many
observations or rounds exist. Every listed item keeps its ID so the rest can
be requested; omitted counts are reported, never treated as read.
"""
from __future__ import annotations

import copy
import json
import unicodedata

from ..analysis_core import AnalysisContractError, fingerprint

VERSION = "analysis-state-1"
CLAIM_STATUSES = ("open", "supported", "contested", "rejected")
RESOLUTIONS = ("revised", "accepted_limit", "withdrawn")
TEXT_CHARS = 200
REASON_CHARS = 200


def _error(message, code="state_event_invalid"):
    return AnalysisContractError(message, code=code)


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise _error("状態の本文が空か長すぎます。")
    return value


def _key(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def empty():
    return {"version": VERSION, "sources": {}, "observations": {}, "claims": {}, "questions": {}, "event_count": 0}


def observations_event(chunk_id, result_id, accepted):
    """Event for one accepted map result; observation IDs are fixed by chunk, result and position."""
    rows = []
    for index, item in enumerate(accepted["observations"]):
        rows.append({"observation_id": "obs_" + fingerprint([chunk_id, result_id, index, item])[7:23], **copy.deepcopy(item)})
    return {"op": "observations_added", "chunk_id": chunk_id, "result_id": result_id, "observations": rows}


def _ids(state, values, *, kind="observations"):
    if not isinstance(values, list) or len(set(values)) != len(values) or any(v not in state[kind] for v in values):
        raise _error("状態に存在しないIDを参照しています。", "state_reference_unknown")
    return list(values)


def question_event(state, question_id, text, *, claim_id=None):
    """問いの開始時点をイベントの連番と主張の内容に固定する。"""
    if claim_id is not None and (not isinstance(claim_id, str) or claim_id not in state["claims"]):
        raise _error("問いの対象主張が見つかりません。", "state_reference_unknown")
    return {"op": "question_added", "question_id": question_id, "text": text, "claim_id": claim_id,
            "claim_digest": claim_digest(state["claims"][claim_id]) if claim_id is not None else None,
            "opened_at_event": state["event_count"] + 1}


def apply(state, event):
    """Return the next state, or raise without changing the given one."""
    state = copy.deepcopy(state)
    op = event.get("op") if isinstance(event, dict) else None
    if op == "observations_added":
        chunk_id, result_id = event.get("chunk_id"), event.get("result_id")
        if (not isinstance(chunk_id, str) or not isinstance(result_id, str)
                or result_id in state["sources"] or chunk_id in state["sources"].values()):
            raise _error("各チャンクの抽出結果は一度だけ追加します。", "state_duplicate")
        state["sources"][result_id] = chunk_id
        for row in event.get("observations", []):
            if (not isinstance(row, dict) or row.get("observation_id") in state["observations"]
                    or row.get("kind") not in ("pattern", "exception", "unclear")
                    or not isinstance(row.get("evidence_ids"), list) or not row["evidence_ids"]):
                raise _error("観察の形式が不正か重複しています。", "state_duplicate")
            _text(row.get("statement"), TEXT_CHARS), _text(row.get("theme"), TEXT_CHARS)
            state["observations"][row["observation_id"]] = {**copy.deepcopy(row), "chunk_id": event["chunk_id"],
                                                            "result_id": event["result_id"]}
    elif op == "claim_added":
        claim_id = event.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id.startswith("clm_") or claim_id in state["claims"]:
            raise _error("主張IDが不正か重複しています。", "state_duplicate")
        support, counter = _ids(state, event.get("support", [])), _ids(state, event.get("counter", []))
        if set(support) & set(counter) or not support:
            raise _error("主張には支持観察が必要で、同じ観察を支持と反例に重ねません。")
        state["claims"][claim_id] = {"text": _text(event.get("text"), TEXT_CHARS), "support": support,
                                     "counter": counter, "status": "open", "reason": ""}
    elif op == "claim_linked":
        claim = state["claims"].get(event.get("claim_id"))
        if claim is None:
            raise _error("主張が見つかりません。", "state_reference_unknown")
        support, counter = _ids(state, event.get("support", [])), _ids(state, event.get("counter", []))
        merged_support = list(dict.fromkeys(claim["support"] + support))
        merged_counter = list(dict.fromkeys(claim["counter"] + counter))
        if set(merged_support) & set(merged_counter) or not support and not counter:
            raise _error("同じ観察を支持と反例に重ねず、追加する観察を指定してください。")
        claim.update(support=merged_support, counter=merged_counter)
    elif op == "claim_revised":
        claim = state["claims"].get(event.get("claim_id"))
        if claim is None:
            raise _error("修正する主張が見つかりません。", "state_reference_unknown")
        claim["text"] = _text(event.get("text"), TEXT_CHARS)
    elif op == "claim_verified":
        claim = state["claims"].get(event.get("claim_id"))
        counts = [event.get(key) for key in ("supports", "contradicts", "unclear")]
        if claim is None or any(type(value) is not int or value < 0 for value in counts):
            raise _error("検証結果の主張または件数が不正です。", "state_reference_unknown")
        if event.get("claim_digest") != claim_digest(claim):
            raise _error("検証後に主張の内容が変わっています。", "state_claim_changed")
        omitted = event.get("omitted", 0)
        if type(omitted) is not int or omitted < 0:
            raise _error("検証で表示しなかった根拠の件数が不正です。", "state_reference_unknown")
        claim["verification"] = {"digest": event["claim_digest"], "supports": counts[0],
                                 "contradicts": counts[1], "unclear": counts[2], "omitted": omitted}
    elif op == "claim_status":
        claim = state["claims"].get(event.get("claim_id"))
        if claim is None or event.get("status") not in CLAIM_STATUSES:
            raise _error("主張または状態が不正です。", "state_reference_unknown")
        claim.update(status=event["status"], reason=_text(event.get("reason"), REASON_CHARS))
    elif op == "question_added":
        question_id = event.get("question_id")
        if not isinstance(question_id, str) or not question_id.startswith("qst_") or question_id in state["questions"]:
            raise _error("問いIDが不正か重複しています。", "state_duplicate")
        if not {"claim_id", "claim_digest", "opened_at_event"} <= event.keys():
            raise _error("問いには対象主張・開始時のdigest・イベント連番が必要です。")
        expected = question_event(state, question_id, event.get("text"), claim_id=event["claim_id"])
        if (event["claim_digest"] != expected["claim_digest"]
                or type(event["opened_at_event"]) is not int
                or event["opened_at_event"] != expected["opened_at_event"]):
            raise _error("問いの開始時点と対象主張の内容が一致しません。", "state_claim_changed")
        claim = state["claims"].get(event["claim_id"])
        observation_ids = list(dict.fromkeys(claim["support"] + claim["counter"])) if claim else []
        evidence_ids = list(dict.fromkeys(e for o in observation_ids for e in state["observations"][o]["evidence_ids"]))
        state["questions"][question_id] = {
            "text": _text(event.get("text"), TEXT_CHARS), "status": "open", "reason": "",
            **{key: event[key] for key in ("claim_id", "claim_digest", "opened_at_event")},
            "observation_ids": observation_ids, "evidence_ids": evidence_ids,
            "closed_at_event": None, "resolution": None}
    elif op == "question_closed":
        question = state["questions"].get(event.get("question_id"))
        if question is None or question["status"] != "open":
            raise _error("閉じる問いが見つかりません。", "state_reference_unknown")
        resolution, reason = event.get("resolution"), event.get("reason")
        claim = state["claims"].get(question["claim_id"])
        missing = None
        if resolution not in RESOLUTIONS:
            missing = "resolutionはrevised・accepted_limit・withdrawnのいずれかが必須です。"
        elif resolution == "revised" and (claim is None or claim_digest(claim) == question["claim_digest"]):
            missing = "revisedには対象主張が必要で、claim_revise等で開始時から本文または根拠を変更してください。"
        elif resolution == "accepted_limit" and (claim is None or claim["status"] not in ("contested", "rejected")):
            missing = "accepted_limitには対象主張が必要で、先にclaim_statusをcontestedかrejectedにしてください。"
        elif not isinstance(reason, str) or len(reason) > REASON_CHARS or (resolution == "withdrawn" and not reason.strip()):
            missing = "reasonは200字以内の文字列で、withdrawnには空でない撤回理由が必要です。"
        if missing:
            raise _error(f"{event['question_id']}: {missing}", "state_resolution_mismatch")
        question.update(status="closed", reason=reason, resolution=resolution, closed_at_event=state["event_count"] + 1)
    else:
        raise _error("未対応の状態操作です。")
    state["event_count"] += 1
    return state


def replay(events):
    state = empty()
    for event in events:
        state = apply(state, event)
    return state


def state_hash(state):
    """Identity of the analysis content. The event counter is excluded: an event that changes
    nothing must not look like progress."""
    return fingerprint({key: value for key, value in state.items() if key != "event_count"})


def claim_digest(claim):
    """Content identity of a claim: what it says and which observations it rests on.

    Status, reason and verification are not part of it, so a status change does not
    void a review, while any change to the evidence does.
    """
    return fingerprint({"text": claim["text"], "support": claim["support"], "counter": claim["counter"]})


def intention_provenance(state, question_id):
    """開始時の根拠を返す。外部ストアのIDやhashは補わない。"""
    if question_id not in state["questions"]:
        raise _error("問いが見つかりません。", "state_reference_unknown")
    question = state["questions"][question_id]
    return {"question_id": question_id, **{key: copy.deepcopy(question[key]) for key in (
        "claim_id", "claim_digest", "observation_ids", "evidence_ids", "opened_at_event", "closed_at_event", "resolution")}}


def themes(state):
    """Deterministic grouping by normalized theme; counts are of observations, not utterances.

    Observations that only record a verification (origin "verify") are evidence for a claim,
    not material for new headings. A rejected claim releases its observations again.
    """
    claimed = {obs for claim in state["claims"].values() if claim["status"] != "rejected"
               for obs in claim["support"] + claim["counter"]}
    groups = {}
    for observation_id, row in state["observations"].items():
        if row.get("origin") == "verify":
            continue
        group = groups.setdefault(_key(row["theme"]), {"theme": row["theme"], "observation_ids": [],
                                                       "pattern": 0, "exception": 0, "unclear": 0,
                                                       "unclaimed": 0, "chunks": set()})
        group["observation_ids"].append(observation_id)
        group[row["kind"]] += 1
        group["unclaimed"] += observation_id not in claimed
        group["chunks"].add(row["chunk_id"])
    return groups


def view(state, *, max_claims=12, max_themes=12, max_questions=8, max_examples=2):
    """Bounded Core view. A heading or claim shows up to max_examples patterns and up to as many
    exceptions, so neither the majority nor the minority is the only thing Core sees of it."""
    observations = state["observations"]

    def examples_of(ids):
        patterns = [o for o in ids if observations[o]["kind"] == "pattern"][:max_examples]
        exceptions = [o for o in ids if observations[o]["kind"] == "exception"][:max_examples]
        unclear = [o for o in ids if observations[o]["kind"] == "unclear"][:1] if max_examples and not (patterns or exceptions) else []
        return [example(o) for o in patterns + exceptions + unclear]

    def example(observation_id):
        # Core acts on themes, claims and questions; observation/evidence IDs stay with the Handler.
        row = observations[observation_id]
        return [row["kind"], row["statement"]]

    order = {status: index for index, status in enumerate(("contested", "open", "supported", "rejected"))}
    claims = sorted(state["claims"].items(), key=lambda pair: (
        order[pair[1]["status"]], -(len(pair[1]["support"]) + len(pair[1]["counter"])), pair[0]))
    def verification(claim):
        saved = claim.get("verification")
        if not saved or saved["digest"] != claim_digest(claim):
            return None
        return {key: saved.get(key, 0) for key in ("supports", "contradicts", "unclear", "omitted")}

    claim_rows = [{"claim_id": claim_id, "text": claim["text"], "status": claim["status"],
                   "verification": verification(claim),
                   "support_count": len(claim["support"]), "counter_count": len(claim["counter"]),
                   "examples": examples_of(claim["support"] + claim["counter"])}
                  for claim_id, claim in claims[:max_claims]]
    groups = sorted(themes(state).values(), key=lambda g: (-g["unclaimed"], -g["exception"], _key(g["theme"])))
    theme_rows = []
    for group in groups[:max_themes]:
        theme_rows.append({"theme": group["theme"], "observations": len(group["observation_ids"]),
                           "pattern": group["pattern"], "exception": group["exception"], "unclear": group["unclear"],
                           "unclaimed": group["unclaimed"], "chunks": len(group["chunks"]),
                           "examples": examples_of(group["observation_ids"])})
    open_questions = sorted(q for q, row in state["questions"].items() if row["status"] == "open")
    return {"version": VERSION, "state_hash": state_hash(state),
            "totals": {"observations": len(observations), "claims": len(state["claims"]),
                       "themes": len(groups), "open_questions": len(open_questions)},
            "claims": claim_rows, "themes": theme_rows,
            "questions": [{"question_id": q, **{key: state["questions"][q][key]
                           for key in ("text", "claim_id", "resolution")}} for q in open_questions[:max_questions]],
            "omitted": {"claims": max(0, len(claims) - max_claims), "themes": max(0, len(groups) - max_themes),
                        "questions": max(0, len(open_questions) - max_questions),
                        "omitted_is_read": False}}


def initialize_state_store(connection):
    """Add-only table; existing tables and columns are untouched."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS orchestration_state_events (run_id TEXT NOT NULL, seq INTEGER NOT NULL, "
        "op TEXT NOT NULL, payload_json TEXT NOT NULL, source_result_id TEXT, state_hash TEXT NOT NULL, "
        "created_at TEXT NOT NULL, PRIMARY KEY (run_id, seq))")


def load_state(connection, run_id):
    """Replay a run's events; the last stored hash must equal the replayed state."""
    rows = connection.execute("SELECT seq,payload_json,state_hash FROM orchestration_state_events "
                              "WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
    state = empty()
    for index, row in enumerate(rows):
        if row[0] != index + 1:
            raise _error("状態イベントの連番が欠けています。", "state_integrity_mismatch")
        state = apply(state, json.loads(row[1]))
        if state_hash(state) != row[2]:
            raise _error("状態イベントのhashが一致しません。", "state_integrity_mismatch")
    return state


def append_event(connection, run_id, event, *, source_result_id=None, created_at):
    """Validate against the replayed state, then store the event with the resulting hash."""
    state = load_state(connection, run_id)
    following = apply(state, event)
    connection.execute("INSERT INTO orchestration_state_events "
                       "(run_id,seq,op,payload_json,source_result_id,state_hash,created_at) VALUES (?,?,?,?,?,?,?)",
                       (run_id, following["event_count"], event["op"], json.dumps(event, ensure_ascii=False),
                        source_result_id, state_hash(following), created_at))
    return following
