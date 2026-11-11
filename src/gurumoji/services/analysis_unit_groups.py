"""Pure structural pooling of Store-prepared, complete utterance carriers.

This is not a Store/permission/adoption bridge. The caller must verify every
source snapshot, saved definition/adoption record and current policy before
calling, and again at execute/save/fresh boundaries. A self-consistent hash is
not evidence of authority or scientific equivalence.
"""

from __future__ import annotations

import copy
import math

from ..analysis_core import (
    AnalysisContractError, TABLE_PILOT_MAX_BYTES, _connection_hash,
    _connection_source_ref, canonical, fingerprint, validate_connection_actor,
)


_MAX_DEPTH = 16
_MAX_ROWS = 2000
_MAX_FIELDS = 256
_TABLE_KEYS = {
    "fields", "rows", "unit", "variables", "sources", "source_utterances",
    "input_hashes", "definition_adoption_refs", "denominators", "scope",
}
_SCOPE_KEYS = {
    "scope_id", "manifest_hash", "mode", "input_refs", "conversation_ids",
    "member_ids", "context_ids",
}
_VARIABLE_KEYS = {
    "variable_id", "version", "definition_hash", "definition_ref", "value_type",
    "scale", "unit", "value_domain", "generation", "validity",
}
_BASE_FIELDS = {"unit_id", "conversation_id", "value_status"}
_IDENTITY_FIELDS = _BASE_FIELDS | {"speaker_id"}
_STATES = {"observed", "missing", "unknown", "unprocessed", "excluded"}
_VALUE_TYPES = {"string": {str}, "integer": {int}, "number": {int, float}, "boolean": {bool}}


def _require(condition, code, field=""):
    if not condition:
        raise AnalysisContractError(
            "発話表の統合契約が一致しません。", code="unit_pool_" + code, field=field,
        )


def _bounded_json(value):
    """Reject non-JSON objects and bound work before recursive JSON encoding."""
    pending = [(value, 0)]
    nodes = lower_bound = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        _require(depth <= _MAX_DEPTH, "depth")
        _require(nodes + len(pending) <= TABLE_PILOT_MAX_BYTES, "byte_limit")
        kind = type(item)
        _require(kind in {dict, list, str, int, float, bool, type(None)}, "json_type")
        lower_bound += len(item) if kind is str else max(1, item.bit_length() // 4) if kind is int else 1
        _require(lower_bound <= TABLE_PILOT_MAX_BYTES, "byte_limit")
        if kind is dict:
            _require(len(item) <= TABLE_PILOT_MAX_BYTES, "byte_limit")
            for key, child in item.items():
                _require(type(key) is str, "json_key")
                pending.append((key, depth + 1))
                pending.append((child, depth + 1))
        elif kind is list:
            _require(len(item) <= TABLE_PILOT_MAX_BYTES, "byte_limit")
            pending.extend((child, depth + 1) for child in item)
        elif kind is str:
            _require(len(item) <= TABLE_PILOT_MAX_BYTES, "byte_limit")
        elif kind is float:
            _require(math.isfinite(item), "nonfinite")
        elif kind is int:
            _require(item.bit_length() <= TABLE_PILOT_MAX_BYTES, "byte_limit")
    try:
        encoded = canonical(value)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _require(False, "json_encoding")
    _require(len(encoded) <= TABLE_PILOT_MAX_BYTES, "byte_limit")


def _identifier(value):
    return type(value) is str and bool(value.strip())


def _ids(value, *, nonempty=False, maximum=_MAX_ROWS):
    return (type(value) is list and (bool(value) or not nonempty)
            and len(value) <= maximum and all(_identifier(v) for v in value)
            and len(set(value)) == len(value))


def _reference(value):
    # Saved HumanRecord refs are artifact/human-record-v1, not memo bodies.
    if type(value) is dict and value.get("target_type") == "artifact":
        return "utterance_id" not in value and _connection_source_ref(
            {**value, "target_type": "definition"},
        )
    return _connection_source_ref(value)


def _refs(value, *, nonempty=False):
    return (type(value) is list and (bool(value) or not nonempty)
            and len(value) <= _MAX_ROWS and all(_reference(v) for v in value)
            and len({canonical(v) for v in value}) == len(value))


def _scope(scope):
    _require(type(scope) is dict and set(scope) == _SCOPE_KEYS, "scope_shape")
    _require(_identifier(scope["scope_id"]) and scope["mode"] == "dataset", "scope_mode")
    _require(_refs(scope["input_refs"], nonempty=True), "scope_refs")
    _require(_ids(scope["conversation_ids"], nonempty=True, maximum=16)
             and _ids(scope["member_ids"]) and _ids(scope["context_ids"]), "scope_ids")
    _require(not set(scope["member_ids"]) & set(scope["context_ids"]), "scope_overlap")
    _require(_connection_hash(scope["manifest_hash"])
             and fingerprint({k: v for k, v in scope.items() if k != "manifest_hash"})
             == scope["manifest_hash"], "scope_hash")


def _variables(table):
    variables = table["variables"]
    _require(type(variables) is list and len(variables) == len(table["fields"]), "variables")
    by_id = {}
    for variable in variables:
        _require(type(variable) is dict and set(variable) == _VARIABLE_KEYS, "variable_shape")
        name = variable["variable_id"]
        _require(_identifier(name) and name in table["fields"] and name not in by_id,
                 "variable_membership")
        _require(type(variable["version"]) is int and variable["version"] >= 1
                 and type(variable["value_type"]) is str and variable["value_type"] in _VALUE_TYPES
                 and type(variable["scale"]) is str
                 and variable["scale"] in {"nominal", "ordinal", "interval", "ratio"}
                 and variable["unit"] == "utterance" and _identifier(variable["value_domain"])
                 and type(variable["validity"]) is str
                 and variable["validity"] in {"candidate", "structural_checked", "human_reviewed", "unknown"},
                 "variable_definition", name)
        _require(_reference(variable["definition_ref"])
                 and _connection_hash(variable["definition_hash"])
                 and variable["definition_hash"] == variable["definition_ref"]["content_hash"],
                 "variable_reference", name)
        try:
            validate_connection_actor(variable["generation"])
        except AnalysisContractError:
            _require(False, "variable_generation", name)
        by_id[name] = variable
    _require(set(by_id) == set(table["fields"]), "variable_membership")
    return by_id


def _table(table):
    _require(type(table) is dict and _TABLE_KEYS <= set(table)
             and set(table) <= _TABLE_KEYS | {"version", "theme_id"}, "table_shape")
    _require(table["unit"] == "utterance", "unit")
    _require("version" not in table or table["version"] == "unit-table-2", "version")
    _require("theme_id" not in table or _identifier(table["theme_id"]), "theme")
    _require(_ids(table["fields"], nonempty=True, maximum=_MAX_FIELDS)
             and _BASE_FIELDS <= set(table["fields"]), "fields")
    _require(type(table["rows"]) is list and 1 <= len(table["rows"]) <= _MAX_ROWS, "rows")
    _scope(table["scope"])
    _require(len(table["scope"]["conversation_ids"]) == 1, "conversation")
    cid = table["scope"]["conversation_ids"][0]
    _require(_ids(table["input_hashes"], nonempty=True) and len(table["input_hashes"]) == 1
             and _connection_hash(table["input_hashes"][0]), "input_hash")
    input_hash = table["input_hashes"][0]
    _require(_refs(table["definition_adoption_refs"]), "adoption_refs")
    variables = _variables(table)
    for key in ("sources", "source_utterances", "denominators"):
        _require(type(table[key]) is dict and len(table[key]) <= _MAX_ROWS, key)
    libraries = {ref["library_id"] for ref in table["scope"]["input_refs"]
                 if ref["target_type"] == "snapshot"}
    _require(bool(libraries), "source_snapshot")
    row_ids, utterance_ids = set(), set()
    for row in table["rows"]:
        _require(type(row) is dict and _BASE_FIELDS <= set(row)
                 and set(row) <= set(table["fields"]), "row_shape")
        uid, status = row["unit_id"], row["value_status"]
        _require(_identifier(uid) and uid not in row_ids and row["conversation_id"] == cid,
                 "row_identity")
        _require(type(status) is str and status in _STATES, "row_status")
        _require(table["sources"].get(uid) == [uid], "source_alignment")
        source = table["source_utterances"].get(uid)
        _require(type(source) is dict
                 and set(source) == {"conversation_id", "input_hash", "utterance_id"}, "source_utterance")
        raw_id = source["utterance_id"]
        _require(source["conversation_id"] == cid and source["input_hash"] == input_hash
                 and _identifier(raw_id) and raw_id not in utterance_ids, "source_identity")
        _require(uid in {"utterance:" + fingerprint([library, cid, input_hash, raw_id])[7:]
                         for library in libraries}, "qualified_id")
        denominator = table["denominators"].get(uid)
        _require(type(denominator) is dict and {"included", "observed"} <= set(denominator)
                 and set(denominator) <= {"included", "observed", "missing", "unknown", "unprocessed", "excluded"}
                 and all(type(n) is int and 0 <= n <= 1 for n in denominator.values())
                 and denominator["observed"] <= denominator["included"], "denominator")
        counted_states = {"observed", "missing", "unknown", "unprocessed"}
        counted = sum(denominator.get(state, 0) for state in counted_states)
        _require(counted <= denominator["included"]
                 and (not counted_states <= set(denominator) or counted == denominator["included"])
                 and ("excluded" not in denominator or denominator["included"] + denominator["excluded"] == 1),
                 "denominator")
        # Projection preserves original denominators even when marking a row
        # excluded. They are provenance, not recomputed from current states.
        for name, definition in variables.items():
            value = row.get(name)
            _require(value is None or type(value) in _VALUE_TYPES[definition["value_type"]],
                     "value_type", name)
            if name not in _IDENTITY_FIELDS:
                _require(status != "observed" or value is not None, "observed_missing", name)
                _require(status not in {"missing", "unknown", "unprocessed"} or value is None,
                         "nonobserved_value", name)
        row_ids.add(uid)
        utterance_ids.add(raw_id)
    _require(all(set(table[key]) == row_ids for key in ("sources", "source_utterances", "denominators")),
             "population")
    scope_ids = set(table["scope"]["member_ids"]) | set(table["scope"]["context_ids"])
    _require(len(scope_ids) == len(row_ids), "population")
    # Legacy single scopes use evidence IDs unavailable in this carrier. Their
    # counts do not prove identity. Never union them into qualified group IDs.
    if any(s.startswith("utterance:") for s in scope_ids):
        _require(scope_ids == row_ids, "scope_population")
    return cid, variables


def pool_unit_tables(tables, *, group_scope) -> dict:
    """Pool 2..16 different conversations without modifying either argument.

    Input is the actual ``AnalysisStore.prepare_connected`` utterance shape.
    Fields/variables must agree exactly (including the complete definition ref,
    hash, version, generation and validity); no cross-definition equivalence is
    inferred. All rows, null/absent values, states and provenance are retained.
    Rows, fields, variables, hashes and adoption refs are ordered canonically.
    The supplied seven-field group scope is preserved, including its hash.

    The caller constructs that dataset scope from all row unit IDs: excluded
    rows go to context_ids, every other row to member_ids. Its input_refs are
    the exact union of source scopes. Raw evidence IDs from source scopes are
    never used as group membership. Store must separately join its verified
    snapshot.evidence (evidence_id, utterance_id, excluded) to source_utterances
    (conversation_id, input_hash, utterance_id); those raw identities cannot be
    recovered from this carrier. Original source-scope population counts are
    only a structural check, not that join or proof of completeness/authority.
    Snapshot reference content_hash and the input_hash are distinct contracts.

    Limits: 16 JSON levels, 256 fields, 2000 total rows/source identities and
    TABLE_PILOT_MAX_BYTES for the combined arguments and returned payload.
    Raises AnalysisContractError with unit_pool_* codes; never truncates.
    """
    _require(type(tables) is list and 2 <= len(tables) <= 16, "cardinality")
    _bounded_json({"tables": tables, "group_scope": group_scope})
    _scope(group_scope)
    conversations, all_ids, source_refs, adoptions, hashes = set(), set(), {}, {}, set()
    fields = variables = None
    theme = ("theme_id" in tables[0], tables[0].get("theme_id")) if type(tables[0]) is dict else None
    rows, sources, utterances, denominators = [], {}, {}, {}
    for table in tables:
        cid, definitions = _table(table)
        _require(cid not in conversations, "duplicate_conversation")
        _require(theme == ("theme_id" in table, table.get("theme_id")), "theme_mismatch")
        if fields is None:
            fields, variables = sorted(table["fields"]), definitions
        else:
            _require(fields == sorted(table["fields"]), "field_mismatch")
            _require(canonical(variables) == canonical(definitions), "definition_mismatch")
        ids = set(table["sources"])
        _require(not all_ids & ids, "duplicate_unit")
        conversations.add(cid)
        all_ids.update(ids)
        _require(len(all_ids) <= _MAX_ROWS, "row_limit")
        for ref in table["scope"]["input_refs"]:
            source_refs[canonical(ref)] = ref
        for ref in table["definition_adoption_refs"]:
            adoptions[canonical(ref)] = ref
        hashes.update(table["input_hashes"])
        rows.extend(table["rows"])
        sources.update(table["sources"])
        utterances.update(table["source_utterances"])
        denominators.update(table["denominators"])
    _require(set(group_scope["conversation_ids"]) == conversations, "group_conversations")
    _require({canonical(ref) for ref in group_scope["input_refs"]} == set(source_refs), "group_sources")
    _require(set(group_scope["member_ids"]) == {r["unit_id"] for r in rows if r["value_status"] != "excluded"}
             and set(group_scope["context_ids"]) == {r["unit_id"] for r in rows if r["value_status"] == "excluded"},
             "group_population")
    result = {
        "version": "unit-table-2", "unit": "utterance", "fields": fields,
        "rows": sorted(rows, key=lambda r: (r["conversation_id"], r["unit_id"])),
        "variables": [variables[name] for name in fields],
        "sources": {uid: sources[uid] for uid in sorted(all_ids)},
        "source_utterances": {uid: utterances[uid] for uid in sorted(all_ids)},
        "denominators": {uid: denominators[uid] for uid in sorted(all_ids)},
        "input_hashes": sorted(hashes),
        "definition_adoption_refs": [adoptions[key] for key in sorted(adoptions)],
        "scope": group_scope,
    }
    if theme[0]:
        result["theme_id"] = theme[1]
    _bounded_json(result)
    return copy.deepcopy(result)
