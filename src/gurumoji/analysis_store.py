"""Immutable analysis artifacts, SQLite catalog, and evidence-linked Vault notes.

The artifact catalog commits before Vault publication. A failed or edited Vault
can be retried from the saved package without repeating analysis or AI calls.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import html
import io
import json
import logging
import os
import re
import threading
import uuid
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, urlencode

from .analysis_method_registry import REGISTRY_VERSION, METHOD_GROUPS
from .analysis_core import PUBLICATION_TARGETS, EFFECTIVE_PUBLICATION_WRITERS, validate_publication_targets
from .services.durable_files import write_durably

LOGGER = logging.getLogger(__name__)
STORE_LOCK = threading.RLock()
STORE_VERSION = 1
TABLE_FORMAT_VERSION = 1


class StoreConflict(ValueError):
    pass


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def initialize_store(connection) -> None:
    connection.execute("INSERT OR IGNORE INTO application_metadata(key,value) VALUES ('library_id',?)", (uuid.uuid4().hex,))
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_runs (
        id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
        kind TEXT NOT NULL, fingerprint TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
        snapshot_id TEXT NOT NULL, source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
        created_at TEXT NOT NULL, status TEXT NOT NULL, vault_status TEXT NOT NULL DEFAULT 'pending',
        stale INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
        note_path TEXT NOT NULL DEFAULT '', app_url TEXT NOT NULL DEFAULT '',
        provider TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '')""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_publication_attempts (
        attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
        package_hash TEXT NOT NULL, requested_json TEXT NOT NULL, effective_json TEXT NOT NULL,
        executed_json TEXT NOT NULL DEFAULT '[]', outcomes_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, ended_at TEXT,
        UNIQUE(run_id,sequence))""")
    for attempt in connection.execute("SELECT attempt_id,outcomes_json FROM analysis_publication_attempts WHERE status='publishing'").fetchall():
        outcomes = json.loads(attempt["outcomes_json"])
        for value in outcomes.values():
            if value.get("status") == "pending":
                value.update(status="unknown", error="再起動で公開結果の確認が中断されました。")
        connection.execute("UPDATE analysis_publication_attempts SET status='incomplete',outcomes_json=?,error=?,ended_at=? WHERE attempt_id=?",
                           (canonical(outcomes).decode(), "公開試行が中断されました。", datetime.now(timezone.utc).isoformat(), attempt["attempt_id"]))
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_runs_item ON analysis_runs(item_id,created_at)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_artifacts (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, path TEXT NOT NULL,
        name TEXT NOT NULL, media_type TEXT NOT NULL, sha256 TEXT NOT NULL,
        bytes INTEGER NOT NULL, rows INTEGER, UNIQUE(run_id,path))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS obsidian_notes (
        path TEXT PRIMARY KEY, note_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
        sha256 TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pending_packages (
        run_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)""")
    # A multi-conversation run (interview comparison) records every member conversation.
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_run_members (
        run_id TEXT NOT NULL, item_id TEXT NOT NULL, PRIMARY KEY(run_id,item_id))""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_run_members_item ON analysis_run_members(item_id)")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_member_changed
        AFTER UPDATE OF segments_json,speaker_names_json,speaker_profiles_json,session_profile_json,
            analysis_config_json,analysis_annotations_json,revision_count,analysis_revision,outline_json,emotion_analysis_json ON library_items
        BEGIN UPDATE analysis_runs SET stale=1
            WHERE id IN (SELECT run_id FROM analysis_run_members WHERE item_id=NEW.id); END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_input_changed
        AFTER UPDATE OF segments_json,speaker_names_json,speaker_profiles_json,session_profile_json,
            analysis_config_json,analysis_annotations_json,revision_count,analysis_revision,outline_json,emotion_analysis_json ON library_items
        BEGIN UPDATE analysis_runs SET stale=1 WHERE item_id=NEW.id; END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_speaker_changed
        AFTER UPDATE ON speaker_registry BEGIN UPDATE analysis_runs SET stale=1; END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_registry_changed
        AFTER UPDATE OF value ON application_metadata WHEN NEW.key='speaker_registry_revision'
        BEGIN UPDATE analysis_runs SET stale=1; END""")
    connection.execute("UPDATE analysis_runs SET status='interrupted',error='保存が中断されました。再保存してください。' WHERE status='writing'")


def safe_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("保存パスが正しくありません。")
    parts = Path(relative).parts
    if Path(relative).is_absolute() or any(part in {"..", "."} for part in parts):
        raise ValueError("保存先の外は参照できません。")
    # Detect links in each component, including the configured root itself.
    target = root / relative
    for part in [root, *root.parents, *target.parents, target]:
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("リンクを経由する保存先には書き出せません。")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("保存先の外は参照できません。")
    return target


def _artifact_member_key(name: str) -> str:
    """Validate portable ZIP-member syntax without repairing the stored name.

    Filesystem containment remains safe_path's responsibility. Output stem
    sanitizers would silently rename immutable members, so they cannot be used here.
    """
    if (not isinstance(name, str) or not name or name.startswith("/")
            or re.search(r'[<>:"\\|?*\x00-\x1f\x7f]', name)):
        raise StoreConflict("固定packageのファイル名が安全な相対パスではありません。")
    parts = name.split("/")
    if any(part in {"", ".", ".."} or part.endswith((".", " ")) or PureWindowsPath(part).is_reserved() for part in parts):
        raise StoreConflict("固定packageのファイル名に未対応のパス要素があります。")
    if len(name.encode("utf-8")) > 65535:
        raise StoreConflict("固定packageのファイル名がZIPの上限を超えています。")
    # Case-insensitive / normalization-insensitive destinations must not overwrite
    # another member. The original spelling and file bytes are never changed.
    return unicodedata.normalize("NFC", name).casefold()


def write_atomic(path: Path, data: bytes, *, create_only: bool = False) -> None:
    # One implementation with the transcript outputs: folder sync and lock retries included (ARCH-04, OBS-17).
    write_durably(path, data, create_only=create_only)


def markdown(value) -> str:
    text = html.escape(str(value or ""), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|^~$])", r"\\\1", text)


# Windows without long-path support fails at 260 characters; stay below it with a margin (OBS-14).
PATH_LIMIT = 250 if os.name == "nt" else 4000


def fit_name(stem: str, available: int) -> str:
    """Shorten ``stem`` to ``available`` characters, kept unique and stable by a short hash."""
    if len(stem) <= available:
        return stem
    tag = "-" + hashlib.sha256(stem.encode("utf-8")).hexdigest()[:8]
    keep = max(0, available - len(tag))
    return stem[:keep].rstrip(" ._-") + tag if keep else tag[1:]


def graph_node_path(run_dir: str, prefix: str, label: str, root: Path | None = None) -> str:
    """Make readable, filesystem-safe names for nodes shown in Obsidian Graph.

    With ``root``, the name is shortened when the full path would pass PATH_LIMIT.
    """
    clean = re.sub(r'[\\/:*?"<>|#^\[\]%\x00-\x1f]', "_", str(label)).strip(" ._")
    clean = re.sub(r"\s+", " ", clean)[:72] or "結果"
    stem = f"{prefix}-{clean}"
    if root is not None:
        over = len(str(Path(root) / run_dir / "graph" / (stem + ".md"))) - PATH_LIMIT
        if over > 0:
            stem = fit_name(stem, max(12, len(stem) - over))
    return f"{run_dir}/graph/{stem}.md"


def csv_bytes(fields: list[str], rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        values = {}
        for key in fields:
            value = row.get(key)
            if value is None: value = ""
            elif isinstance(value, (dict, list, tuple)): value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values[key] = value
        writer.writerow(values)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _table_value_type(value):
    if value is None:
        return "null"
    for kind, name in ((bool, "boolean"), (int, "integer"), (float, "number"), (str, "string")):
        if isinstance(value, kind):
            return name
    if isinstance(value, (list, tuple)):
        for child in value:
            _table_value_type(child)
        return "array"
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for child in value.values():
            _table_value_type(child)
        return "object"
    raise StoreConflict("型付き表にJSONで保持できない値があります。")


def table_package(name, fields, rows, *, run_id, snapshot_id, source_revision, analysis_revision):
    """Keep full typed values; absent keys and unknown semantics stay explicit."""
    if (not isinstance(fields, (list, tuple)) or any(not isinstance(f, str) for f in fields)
            or len(set(fields)) != len(fields) or not isinstance(rows, (list, tuple))
            or any(not isinstance(row, dict) or any(not isinstance(k, str) for k in row) for row in rows)):
        raise StoreConflict("型付き表の列・行形式が正しくありません。")
    names = list(fields) + sorted({key for row in rows for key in row} - set(fields))
    columns = []
    for key in names:
        columns.append({"name": key,
                        "observed_types": sorted({_table_value_type(row[key]) for row in rows if key in row}),
                        "absent_count": sum(key not in row for row in rows),
                        "null_count": sum(key in row and row[key] is None for row in rows)})
    return {"format": "gurumoji.analysis-table", "schema_version": TABLE_FORMAT_VERSION,
            "dataset_id": name, "run_id": run_id, "input_snapshot_id": snapshot_id,
            "source_revision": source_revision, "analysis_revision": analysis_revision,
            "fields": list(fields), "columns": columns, "row_count": len(rows),
            "rows": [{"row_id": f"{name}:{index}", "values": copy.deepcopy(row)}
                     for index, row in enumerate(rows, 1)]}


def _read_typed_json(data):
    def object_pairs(pairs):
        value = {}
        for key, child in pairs:
            if key in value:
                raise StoreConflict("型付き表のJSONキーが重複しています。")
            value[key] = child
        return value
    def reject_constant(_value):
        raise StoreConflict("型付き表に非有限値があります。")
    return json.loads(data, object_pairs_hook=object_pairs, parse_constant=reject_constant)


def frontmatter(note_id: str, title: str, **properties) -> str:
    data = {"note_id": note_id, "note_type": "analysis-result", "title": title,
            "schema_version": STORE_VERSION, "managed_by": "gurumoji", **properties}
    return "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in data.items()) + "\n---\n\n"


CONNECTION_METADATA_VERSION = 1
CONNECTION_METADATA_KIND = "connection_metadata"
# A storage schema describes observed JSON values, not a measurement or adapter.
CONNECTION_TABLE_SCHEMA = {"format": "gurumoji.analysis-table", "schema_version": 1,
                           "required": ["dataset_id", "run_id", "input_snapshot_id", "source_revision",
                                        "analysis_revision", "fields", "columns", "row_count", "rows"]}


class AssetBindingError(StoreConflict):
    def __init__(self, reason, decision="rejected"):
        self.reason, self.decision = reason, decision
        super().__init__("asset_connection_" + reason)


def _asset_hash(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _asset_fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise AssetBindingError("fields")


def _asset_id(value):
    return isinstance(value, str) and bool(value.strip())


def _asset_enum(value, choices):
    return isinstance(value, str) and value in choices


def _asset_ids(value, *, nonempty=False):
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(_asset_id(v) for v in value) and len(value) == len(set(value)))


def _asset_ref(ref):
    from .analysis_core import HASH_DOMAINS, _connection_hash, _connection_source_ref
    if isinstance(ref, dict) and ref.get("target_type") == "artifact":
        _asset_fields(ref, ("target_type", "target_id", "version", "content_hash", "hash_domain"), ("library_id", "locator"))
        return (all(_asset_id(ref[k]) for k in ("target_id", "version", "hash_domain"))
                and _connection_hash(ref["content_hash"]) and ref["hash_domain"] in HASH_DOMAINS
                and all(_asset_id(ref[k]) for k in ("library_id", "locator") if k in ref))
    return _connection_source_ref(ref)


def _asset_refs(refs, *, nonempty=False):
    return (isinstance(refs, list) and (bool(refs) or not nonempty)
            and all(_asset_ref(r) for r in refs) and len({digest(r) for r in refs}) == len(refs))


def _asset_key(key):
    _asset_fields(key, ("library_id", "store_run_id", "artifact_id", "output_name"))
    if not all(_asset_id(v) for v in key.values()): raise AssetBindingError("asset_key")
    return digest(key)


def _asset_scope(scope):
    from .analysis_core import _connection_hash
    fields = ("scope_id", "manifest_hash", "mode", "input_refs", "conversation_ids", "member_ids", "context_ids")
    _asset_fields(scope, fields)
    if (not _asset_id(scope["scope_id"]) or not _asset_enum(scope["mode"], {"dataset", "selection", "section", "episode"})
            or not _asset_refs(scope["input_refs"], nonempty=True)
            or not _asset_ids(scope["conversation_ids"], nonempty=True)
            or not all(_asset_ids(scope[k]) for k in ("member_ids", "context_ids"))
            or not _connection_hash(scope["manifest_hash"])
            or scope["manifest_hash"] != _asset_hash(canonical({k: v for k, v in scope.items() if k != "manifest_hash"}))):
        raise AssetBindingError("scope")


def _asset_meaning(meaning):
    from .analysis_core import CONNECTION_UNITS
    _asset_fields(meaning, ("definition_refs", "description", "status", "unit"))
    if (not _asset_refs(meaning["definition_refs"]) or not _asset_enum(meaning["unit"], CONNECTION_UNITS)
            or not _asset_enum(meaning["status"], {"declared", "unknown"})
            or (meaning["status"] == "unknown" and meaning["description"] is not None)
            or (meaning["status"] == "declared" and not _asset_id(meaning["description"]))):
        raise AssetBindingError("meaning")


def _asset_state(state):
    from .analysis_core import CONNECTION_PURPOSES, _connection_hash
    _asset_fields(state, ("asset_key", "target_content_hash", "target_domain", "state_revision", "policy_revision",
                         "status", "allowed_purposes", "send_policy", "destinations", "revoked",
                         "review_refs", "reason", "updated_at"))
    _asset_key(state["asset_key"])
    if (not _connection_hash(state["target_content_hash"]) or not _asset_enum(state["target_domain"],
            {"raw-bytes-v1", "ta-candidate-content-v1", "ta-theme-content-v1"})
            or any(type(state[k]) is not int or state[k] < 1 for k in ("state_revision", "policy_revision"))
            or not _asset_enum(state["status"], {"draft", "candidate", "adopted", "rejected", "retired", "stale", "unavailable"})
            or not _asset_ids(state["allowed_purposes"]) or not set(state["allowed_purposes"]) <= CONNECTION_PURPOSES
            or not _asset_enum(state["send_policy"], {"local_only", "permitted_destinations", "prohibited"})
            or not _asset_ids(state["destinations"]) or type(state["revoked"]) is not bool
            or not _asset_refs(state["review_refs"]) or not _asset_id(state["reason"])
            or not isinstance(state["updated_at"], str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", state["updated_at"])):
        raise AssetBindingError("state")
    try: datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))
    except ValueError: raise AssetBindingError("state_time") from None
    if state["send_policy"] != "permitted_destinations" and state["destinations"]:
        raise AssetBindingError("state_destinations")


def _asset_descriptor(asset, *, original=False):
    from .analysis_core import ASSET_KINDS, _connection_hash, _connection_schema, _connection_adapter, validate_connection_actor
    common = ("asset_key", "raw_byte_hash", "schema", "scope", "producer", "adapter", "meaning")
    if original:
        _asset_fields(asset, common + ("source_ref",))
        if not _asset_ref(asset["source_ref"]) or asset["source_ref"]["target_type"] != "snapshot":
            raise AssetBindingError("original_type", "unsupported")
    else:
        _asset_fields(asset, common + ("contract_id", "contract_version", "content_hash", "content_domain", "kind",
                                      "source_refs", "method_id", "method_version", "variables", "parent_refs"),
                      ("execution_run_id", "producer_task_id", "supersedes"))
        if (asset["contract_id"] != "gurumoji.analysis-asset-connection" or type(asset["contract_version"]) is not int
                or asset["contract_version"] != 1 or not _asset_enum(asset["kind"], ASSET_KINDS)
                or not _connection_hash(asset["content_hash"]) or not _asset_enum(asset["content_domain"],
                    {"raw-bytes-v1", "ta-candidate-content-v1", "ta-theme-content-v1"})
                or not _asset_refs(asset["source_refs"], nonempty=True) or not _asset_refs(asset["parent_refs"])
                or not all(_asset_id(asset[k]) for k in ("method_id", "method_version"))
                or (("execution_run_id" in asset) != ("producer_task_id" in asset))
                or not all(_asset_id(asset[k]) for k in ("execution_run_id", "producer_task_id") if k in asset)
                or ("supersedes" in asset and not _asset_refs(asset["supersedes"], nonempty=True))):
            raise AssetBindingError("asset")
        from .analysis_method_registry import connection_method_descriptor
        registered = connection_method_descriptor(asset["method_id"])
        if registered is None: raise AssetBindingError("method_unregistered")
        if asset["method_version"] != registered.get("method_version", registered["registry_version"]):
            raise AssetBindingError("method_version")
        if asset["asset_key"]["output_name"] not in {f"tables/{name}.json" for name in registered["output_names"]}:
            raise AssetBindingError("method_output_unregistered")
        if asset["content_domain"] != "raw-bytes-v1" or asset["kind"] != "observation_table":
            raise AssetBindingError("typed_schema_unimplemented", "unsupported")
        if not isinstance(asset["variables"], list): raise AssetBindingError("variables")
        ids = []
        for variable in asset["variables"]:
            _asset_fields(variable, ("variable_id", "version", "definition_hash", "value_type", "scale", "unit",
                                     "value_domain", "generation", "validity", "definition_ref"))
            validate_connection_actor(variable["generation"])
            if (not all(_asset_id(variable[k]) for k in ("variable_id", "unit", "value_domain"))
                    or type(variable["version"]) is not int or variable["version"] < 1
                    or not _asset_enum(variable["value_type"], {"string", "number", "integer", "boolean"})
                    or not _asset_enum(variable["scale"], {"nominal", "ordinal", "interval", "ratio"})
                    or not _asset_enum(variable["validity"], {"candidate", "structural_checked", "human_reviewed", "unknown"})
                    or not _asset_ref(variable["definition_ref"])
                    or variable["definition_hash"] != variable["definition_ref"]["content_hash"]):
                raise AssetBindingError("variable")
            ids.append(variable["variable_id"])
        if len(ids) != len(set(ids)): raise AssetBindingError("variable_duplicate")
    _asset_key(asset["asset_key"]); _asset_scope(asset["scope"]); _asset_meaning(asset["meaning"])
    validate_connection_actor(asset["producer"])
    if not original and not asset["parent_refs"]:
        raise AssetBindingError("derived_parent_missing")
    if not _connection_hash(asset["raw_byte_hash"]) or not _connection_schema(asset["schema"]):
        raise AssetBindingError("hash_or_schema")
    if asset["adapter"] is None:
        if asset["producer"]["kind"] != "researcher": raise AssetBindingError("adapter")
    elif not _connection_adapter(asset["adapter"]): raise AssetBindingError("adapter")


def _asset_transition(history, state, descriptor):
    _asset_state(state)
    target = (descriptor.get("content_hash", descriptor["raw_byte_hash"]),
              descriptor.get("content_domain", "raw-bytes-v1"))
    if (state["target_content_hash"], state["target_domain"]) != target:
        raise AssetBindingError("state_target_mismatch")
    revision = state["state_revision"]
    if revision in history:
        if canonical(history[revision]) != canonical(state): raise AssetBindingError("state_revision_conflict")
        return
    previous = history[max(history)] if history else None
    if revision != (previous["state_revision"] + 1 if previous else 1): raise AssetBindingError("state_revision_gap")
    if previous:
        changed = any(state[k] != previous[k] for k in ("allowed_purposes", "send_policy", "destinations", "revoked"))
        if state["policy_revision"] != previous["policy_revision"] + int(changed): raise AssetBindingError("policy_revision")
        if (not set(state["allowed_purposes"]) <= set(previous["allowed_purposes"])
                or not set(state["destinations"]) <= set(previous["destinations"])
                or (previous["revoked"] and not state["revoked"])
                or (previous["send_policy"] == "prohibited" and state["send_policy"] != "prohibited")
                or (previous["send_policy"] == "local_only" and state["send_policy"] not in {"local_only", "prohibited"})
                or (previous["send_policy"] == "permitted_destinations" and state["send_policy"] == "local_only"
                    and "local" not in previous["destinations"])
                or (previous["status"] == "adopted" and state["status"] in {"draft", "candidate"})):
            raise AssetBindingError("permission_widening_or_adopted_downgrade")
    elif state["policy_revision"] != 1: raise AssetBindingError("policy_revision")
    history[revision] = state


def _asset_producer_link(link, assets):
    from .analysis_core import _connection_hash
    _asset_fields(link, ("plan_id", "plan_version", "plan_hash", "generation", "execution_run_id",
                         "producer_task_id", "output_name", "asset_key"))
    if (not all(_asset_id(link[k]) for k in ("plan_id", "execution_run_id", "producer_task_id", "output_name"))
            or any(type(link[k]) is not int or link[k] < 1 for k in ("plan_version", "generation"))
            or not _connection_hash(link["plan_hash"])):
        raise AssetBindingError("producer_link")
    asset = assets.get(_asset_key(link["asset_key"]))
    if (asset is None or asset.get("execution_run_id") != link["execution_run_id"]
            or asset.get("producer_task_id") != link["producer_task_id"]
            or asset["asset_key"]["output_name"] != link["output_name"]):
        raise AssetBindingError("producer_identity")


class AnalysisStore:
    def __init__(self, database_file: Path, connect):
        self.database_file = Path(database_file).resolve()
        from .obsidian_layout import ObsidianLayout
        from .vault_registry import VaultRegistry
        self.layout = ObsidianLayout(database_file)
        self.vaults = VaultRegistry(database_file)
        self.connect = connect
        self.root = Path(database_file).parent / "analysis_store"
        self.vault = Path(database_file).parent / "obsidian" / "ResearchVault"
        self._last_publication_outcomes: dict[str, dict[str, dict[str, str]]] = {}
        self.note_log = Path(database_file).parent / "obsidian_layout" / "note_changes.jsonl"
        self.run_notes = Path(database_file).parent / "obsidian_layout" / "run_notes"
        self._note_events: list = []

    def _publish_generated_vaults(self, run_id: str) -> dict[str, str]:
        """Mirror a completed run into the Input, Orchestrator, and Visualization Vaults.

        Those Vaults hold ID-linked summaries only. A failure there never changes
        the run, its artifacts, or the ResearchVault publication.
        """
        run = self.get(run_id)
        if not run or run["status"] != "completed":
            return {}
        try:
            snapshot, result = self._read_package(run_id)
            artifacts = self.artifacts(run_id)
            fields = {}
            for artifact in artifacts:
                name = artifact["name"]
                if name.startswith("tables/") and name.endswith(".csv"):
                    content = self.read_artifact(artifact["id"])[1].decode("utf-8-sig")
                    fields[name[len("tables/"):-len(".csv")]] = next(csv.reader(io.StringIO(content)), [])
            self.vaults.note_events = []
            statuses = self.vaults.publish_analysis(run, snapshot, result, artifacts, fields)
            self._note_events.extend(self.vaults.note_events)
            outcomes = {
                kind: {"status": status, "error": "" if status == "published" else "公開先を確認してください。"}
                for kind, status in statuses.items()
            }
            self._last_publication_outcomes[run_id] = outcomes
            return statuses
        except (OSError, ValueError, LookupError, TypeError) as exc:
            LOGGER.warning("4 Vaultへの書き出しを完了できませんでした（%s）: %s", run_id, exc)
            outcomes = {kind: {"status": "failed", "error": str(exc)}
                        for kind in ("input", "orchestrator", "visualization")}
            self._last_publication_outcomes[run_id] = outcomes
            return {"error": str(exc)}

    def publication_attempts(self, run_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence", (run_id,),
            ).fetchall()
        return [{**{key: row[key] for key in ("attempt_id", "sequence", "package_hash", "status", "error", "created_at", "ended_at")},
                 **{key: json.loads(row[key + "_json"]) for key in ("requested", "effective", "executed", "outcomes")}}
                for row in rows]

    def publication_outcomes(self, run_id: str) -> dict[str, dict[str, str]]:
        """Only a durable attempt proves that these writers processed this package."""
        if not self.get(run_id):
            raise LookupError("保存結果がありません。")
        attempts = self.publication_attempts(run_id)
        if attempts:
            return copy.deepcopy(attempts[-1]["outcomes"])
        return {kind: {"status": "unknown", "error": "公開試行記録がなく、完了を確認できません。"}
                for kind in EFFECTIVE_PUBLICATION_WRITERS}

    def publish_vaults(self, run_id: str) -> dict[str, str]:
        """Compatibility entry point using the same scope and durable-attempt guard."""
        self.publish(run_id)
        return {kind: value["status"] for kind, value in self.publication_outcomes(run_id).items()
                if kind in PUBLICATION_TARGETS}

    def refresh_vaults(self, item_id: str) -> None:
        """Republish only runs whose stale state differs from their Orchestrator note.

        Comparisons that include this conversation are checked as well.
        Autonomous output requires its dedicated source/generation/attempt guard;
        generic refresh cannot authorize those writers.
        """
        with self.connect() as conn:
            rows = conn.execute("""SELECT id,stale FROM analysis_runs WHERE status='completed' AND kind!='autonomous_analysis' AND
                (item_id=? OR id IN (SELECT run_id FROM analysis_run_members WHERE item_id=?))""",
                                (item_id, item_id)).fetchall()
        for row in rows:
            try:
                current = self.vaults.run_status(row["id"])
            except (OSError, ValueError) as exc:
                LOGGER.warning("Vault台帳を読み込めませんでした: %s", exc)
                return
            if current != ("stale" if row["stale"] else "current"):
                self.publish_vaults(row["id"])

    def members(self, run_id: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT item_id FROM analysis_run_members WHERE run_id=? ORDER BY item_id",
                                (run_id,)).fetchall()
        return [row[0] for row in rows]

    def list_comparisons(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT * FROM analysis_runs WHERE kind='interview_comparison'
                ORDER BY created_at DESC,id DESC LIMIT 100""").fetchall()
        return [dict(row) for row in rows]

    def library_id(self) -> str:
        with self.connect() as conn:
            return conn.execute("SELECT value FROM application_metadata WHERE key='library_id'").fetchone()[0]

    def get(self, run_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def by_request(self, request_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM analysis_runs WHERE request_id=?", (request_id,)).fetchone()
        return dict(row) if row else None

    def list(self, item_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM analysis_runs WHERE item_id=? ORDER BY created_at DESC,id DESC LIMIT 100", (item_id,)).fetchall()
        return [dict(row) for row in rows]

    def artifacts(self, run_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM analysis_artifacts WHERE run_id=? ORDER BY name", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def read_artifact(self, artifact_id: str):
        with self.connect() as conn:
            row = conn.execute("""SELECT a.* FROM analysis_artifacts a JOIN analysis_runs r ON r.id=a.run_id
                WHERE a.id=? AND r.status='completed'""", (artifact_id,)).fetchone()
        if row is None: raise LookupError("保存済みファイルが見つかりません。")
        _artifact_member_key(row["name"])
        path = safe_path(self.root, row["path"])
        content = path.read_bytes()
        if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise StoreConflict("保存済みファイルが外部で変更されています。")
        return dict(row), content

    def public(self, row: dict, *, local: bool = False) -> dict:
        result = {key: row[key] for key in ("id", "item_id", "kind", "source_revision", "analysis_revision",
                  "created_at", "status", "vault_status", "stale", "error", "provider", "model")}
        result.update({key: row.get(key) for key in ("fingerprint", "input_fingerprint", "snapshot_id")})
        result["artifacts"] = [{key: a[key] for key in ("id", "name", "media_type", "rows", "bytes", "sha256")}
                               for a in self.artifacts(row["id"])]
        for artifact in result["artifacts"]:
            artifact["url"] = f"/api/analysis/artifacts/{artifact['id']}"
        result["obsidian_uri"] = ("obsidian://open?" + urlencode({"path": str(self.vault / row["note_path"])})
                                    if local and row["note_path"] and row["vault_status"] == "completed" else "")
        result["vault_notes"] = self.vault_notes(row["id"])
        # One SQLite read snapshot: never mix outcomes and writer evidence from
        # different publication attempts that finish during this GET.
        with self.connect() as connection:
            connection.execute("BEGIN")
            attempts = connection.execute("SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence", (row["id"],)).fetchall()
            result["publication_attempts"] = [
                {**{key: attempt[key] for key in ("attempt_id", "sequence", "package_hash", "status", "error", "created_at", "ended_at")},
                 **{key: json.loads(attempt[key + "_json"]) for key in ("requested", "effective", "executed", "outcomes")}}
                for attempt in attempts]
            result["publication_records"] = []
            if row["kind"] == "milestone_analysis" and connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='analysis_pipeline_publications'").fetchone():
                records = connection.execute("""SELECT target_role,status,error,result_run_id,package_hash
                    FROM analysis_pipeline_publications WHERE pipeline_id=(
                        SELECT pipeline_id FROM analysis_pipeline_requests WHERE result_run_id=?
                        ORDER BY created_at DESC,pipeline_id DESC LIMIT 1) ORDER BY target_role""", (row["id"],)).fetchall()
                result["publication_records"] = [dict(record) for record in records]
        latest = result["publication_attempts"][-1] if result["publication_attempts"] else {}
        all_outputs = latest.get("outcomes", {}) if latest else {
            kind: {"status": "unknown", "error": "公開試行記録がなく、完了を確認できません。"}
            for kind in EFFECTIVE_PUBLICATION_WRITERS}
        result["publication_outcomes"] = all_outputs
        result["vault_outputs"] = {kind: value for kind, value in all_outputs.items() if kind in PUBLICATION_TARGETS}
        requested = latest.get("requested", [])
        effective = latest.get("effective", [])
        executed = latest.get("executed", [])
        valid_scope = (isinstance(requested, list) and len(requested) == len(PUBLICATION_TARGETS)
                       and set(requested) == set(PUBLICATION_TARGETS)
                       and isinstance(effective, list) and len(effective) == len(EFFECTIVE_PUBLICATION_WRITERS)
                       and set(effective) == set(EFFECTIVE_PUBLICATION_WRITERS)
                       and isinstance(executed, list) and len(executed) == len(EFFECTIVE_PUBLICATION_WRITERS)
                       and set(executed) == set(EFFECTIVE_PUBLICATION_WRITERS))
        result["vault_outputs_complete"] = row["status"] == "completed" and bool(row.get("fingerprint")) and valid_scope and latest.get("status") == "completed" and latest.get("package_hash") == row.get("fingerprint") and all(
            kind in latest.get("effective", []) and kind in latest.get("executed", [])
            and all_outputs.get(kind, {}).get("status") == "published"
            for kind in EFFECTIVE_PUBLICATION_WRITERS)
        return result

    def _vault_outputs(self, row: dict) -> dict[str, dict[str, str]]:
        if row["status"] != "completed":
            return {}
        try:
            return {kind: value for kind, value in self.publication_outcomes(row["id"]).items()
                    if kind in PUBLICATION_TARGETS}
        except (OSError, ValueError, LookupError) as exc:
            return {kind: {"status": "unknown", "error": str(exc)}
                    for kind in ("input", "orchestrator", "visualization")}

    def save(self, *, item_id: str, kind: str, snapshot: dict, result: dict, datasets: dict,
             request_id: str, input_fingerprint: str, source_revision: int, analysis_revision: int,
             app_url: str = "http://127.0.0.1:7860", provider: str = "", model: str = "",
             member_ids: list[str] | None = None, check_cancelled=lambda: None,
             publish: bool = True, commit_guard=None, table_format_version=TABLE_FORMAT_VERSION) -> dict:
        with STORE_LOCK:
            check_cancelled()
            library_id = self.library_id()
            snapshot = {**snapshot, "library_id": library_id}
            snapshot_id = digest(snapshot)
            identity = {"snapshot": snapshot_id, "kind": kind, "registry": REGISTRY_VERSION,
                        "input_fingerprint": input_fingerprint,
                        "algorithms": result.get("algorithms", {}), "parameters": result.get("parameters", {}),
                        "ai_request": result.get("ai_request_id", "")}
            if kind in {"ai_finishing", "ai_insights"}: identity["request"] = request_id
            fingerprint = digest(identity)
            previous = self.by_request(request_id)
            if previous and (previous["item_id"] != item_id or previous["fingerprint"] != fingerprint):
                raise StoreConflict("リクエストIDが別の入力に使われています。")
            if not previous and kind not in {"ai_finishing", "ai_insights"}:
                with self.connect() as conn:
                    match = conn.execute("SELECT * FROM analysis_runs WHERE fingerprint=? AND item_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1", (fingerprint, item_id)).fetchone()
                if match: previous = dict(match)
            if previous and previous["status"] == "completed":
                if commit_guard is not None:
                    with self.connect() as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        commit_guard(connection)
                self._verified_package(previous["id"])
                if publish and previous["vault_status"] != "completed":
                    self.publish(previous["id"])
                elif publish:
                    try:
                        unpublished = self.vaults.run_status(previous["id"]) is None
                    except (OSError, ValueError):
                        unpublished = False
                    # Runs saved before the four Vaults existed are mirrored when saved again.
                    if unpublished:
                        self.publish_vaults(previous["id"])
                return self.get(previous["id"])
            run_id = previous["id"] if previous else uuid.uuid5(uuid.NAMESPACE_URL, library_id + request_id).hex
            now = previous["created_at"] if previous else datetime.now(timezone.utc).isoformat()
            result = copy.deepcopy(result)
            if "generated_at" in result.get("analysis", {}):
                result["analysis"]["generated_at"] = now
            pending = {"item_id": item_id, "kind": kind, "snapshot": snapshot, "result": result,
                       "datasets": datasets, "request_id": request_id, "input_fingerprint": input_fingerprint,
                       "source_revision": source_revision, "analysis_revision": analysis_revision,
                       "app_url": app_url, "provider": provider, "model": model,
                       "member_ids": list(member_ids or []), "publish": publish,
                       "table_format_version": table_format_version}
            with self.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if commit_guard is not None:
                    commit_guard(conn)
                conn.execute("""INSERT INTO analysis_runs(id,request_id,item_id,kind,fingerprint,input_fingerprint,
                    snapshot_id,source_revision,analysis_revision,created_at,status,app_url,provider,model)
                    VALUES (?,?,?,?,?,?,?,?,?,?,'writing',?,?,?) ON CONFLICT(id) DO UPDATE SET status='writing',error=''""",
                    (run_id, request_id, item_id, kind, fingerprint, input_fingerprint, snapshot_id,
                     source_revision, analysis_revision, now, app_url.rstrip("/"), provider, model))
                conn.executemany("INSERT OR IGNORE INTO analysis_run_members(run_id,item_id) VALUES (?,?)",
                                 [(run_id, member) for member in (member_ids or [])])
                existing = conn.execute("SELECT payload_json FROM analysis_pending_packages WHERE run_id=?", (run_id,)).fetchone()
                if existing:
                    pending = json.loads(existing[0])
                    snapshot, result, datasets = pending['snapshot'], pending['result'], pending['datasets']
                    # A partial package must keep its original provenance as
                    # well as its values, even when the retry caller changed.
                    source_revision = pending['source_revision']
                    analysis_revision = pending['analysis_revision']
                    app_url, provider, model = pending['app_url'], pending['provider'], pending['model']
                else:
                    if table_format_version == TABLE_FORMAT_VERSION:
                        # Reject non-string object keys before pending JSON can
                        # silently stringify them on a later retry.
                        for _fields, rows in datasets.values():
                            for row in rows:
                                _table_value_type(row)
                    conn.execute("INSERT INTO analysis_pending_packages(run_id,payload_json) VALUES (?,?)", (run_id, canonical(pending).decode('utf-8')))
            try:
                table_version = pending.get("table_format_version")
                if table_version is not None and (type(table_version) is not int or table_version != TABLE_FORMAT_VERSION):
                    raise StoreConflict("再試行する表の保存形式に対応していません。")
                files = {"input.json": (canonical(snapshot), "application/json", None),
                         "parameters.json": (canonical(result.get("parameters", {})), "application/json", None),
                         "result.json": (canonical(result), "application/json", None)}
                for name, (fields, rows) in datasets.items():
                    if not re.fullmatch(r"[a-z_]+", name): raise ValueError("表の名前が正しくありません。")
                    if table_version == TABLE_FORMAT_VERSION:
                        table = table_package(name, fields, rows, run_id=run_id, snapshot_id=snapshot_id,
                                              source_revision=source_revision, analysis_revision=analysis_revision)
                        table_data = canonical(table)
                        # Export from the same JSON-compatible values, including
                        # tuple-to-array normalization, never from a display preview.
                        exported = json.loads(table_data)
                        rows = [row["values"] for row in exported["rows"]]
                        files[f"tables/{name}.json"] = (table_data, "application/json", len(rows))
                    files[f"tables/{name}.csv"] = (csv_bytes(fields, rows), "text/csv", len(rows))
                artifacts = []
                for name, (content, media_type, rows) in files.items():
                    check_cancelled()
                    relative = (f"inputs/{snapshot_id}/input.json" if name == "input.json" else f"runs/{run_id}/{name}")
                    target = safe_path(self.root, relative)
                    if target.exists():
                        if target.read_bytes() != content: raise StoreConflict("既存の固定結果を上書きできません。")
                    else: write_atomic(target, content)
                    artifacts.append({"id": uuid.uuid5(uuid.NAMESPACE_URL, run_id + name).hex,
                                      "run_id": run_id, "path": relative, "name": name,
                                      "media_type": media_type, "sha256": hashlib.sha256(content).hexdigest(),
                                      "bytes": len(content), "rows": rows})
                manifest = {"schema_version": STORE_VERSION, "analysis_id": run_id, "library_id": library_id,
                            "conversation_id": item_id, "input_snapshot_id": snapshot_id,
                            "input_fingerprint": input_fingerprint, "fingerprint": fingerprint,
                            "kind": kind, "created_at": now, "source_revision": source_revision,
                            "analysis_revision": analysis_revision, "artifacts": artifacts,
                            "method_version": REGISTRY_VERSION, "provider": provider, "model": model}
                if table_version == TABLE_FORMAT_VERSION:
                    manifest.update(table_format_version=table_version,
                                    typed_tables={name: {"data": f"tables/{name}.json", "export": f"tables/{name}.csv"}
                                                  for name in datasets})
                content = canonical(manifest)
                target = safe_path(self.root, f"runs/{run_id}/manifest.json")
                if target.exists() and target.read_bytes() != content: raise StoreConflict("manifestが変更されています。")
                if not target.exists(): write_atomic(target, content)
                artifacts.append({"id": uuid.uuid5(uuid.NAMESPACE_URL, run_id + "manifest").hex,
                                  "run_id": run_id, "path": f"runs/{run_id}/manifest.json", "name": "manifest.json",
                                  "media_type": "application/json", "sha256": hashlib.sha256(content).hexdigest(),
                                  "bytes": len(content), "rows": None})
                check_cancelled()
                with self.connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    if commit_guard is not None:
                        commit_guard(conn)
                    for artifact in artifacts:
                        conn.execute("""INSERT OR REPLACE INTO analysis_artifacts
                            (id,run_id,path,name,media_type,sha256,bytes,rows) VALUES (:id,:run_id,:path,:name,:media_type,:sha256,:bytes,:rows)""", artifact)
                    conn.execute("UPDATE analysis_runs SET status='completed',error='' WHERE id=?", (run_id,))
                    conn.execute("DELETE FROM analysis_pending_packages WHERE run_id=?", (run_id,))
            except Exception:
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET status='failed',error='分析結果を保存できませんでした。再保存してください。' WHERE id=?", (run_id,))
                raise
            if publish:
                self.publish(run_id)
            return self.get(run_id)

    def retry(self, run_id: str) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run: raise LookupError("保存結果がありません。")
            if run['status'] == 'completed': return self.publish(run_id)
            if run['kind'] in {'milestone_analysis', 'autonomous_analysis'}:
                raise StoreConflict("未完了の固定保存は、その分析の専用画面から再試行してください。")
            with self.connect() as conn:
                row = conn.execute("SELECT payload_json FROM analysis_pending_packages WHERE run_id=?", (run_id,)).fetchone()
            if not row: raise StoreConflict("再保存用の入力がありません。分析画面から保存してください。")
            return self.save(**json.loads(row[0]))

    def _verified_package(self, run_id: str) -> tuple[dict, dict]:
        """Validate every immutable catalog artifact before any publication side effect."""
        snapshot, result, _manifest, _content = self.verified_package(run_id)
        return snapshot, result

    def verified_package(self, run_id: str) -> tuple[dict, dict, dict, dict[str, bytes]]:
        """Read the fixed package only; never recover, publish, stamp or rewrite it."""
        run = self.get(run_id)
        artifacts = self.artifacts(run_id)
        by_name = {artifact["name"]: artifact for artifact in artifacts}
        required = {"input.json", "result.json", "parameters.json", "manifest.json"}
        if not run or run["status"] != "completed" or not required <= by_name.keys():
            raise StoreConflict("固定packageが欠落しています。再計算せず停止しました。")
        member_keys = [_artifact_member_key(artifact["name"]) for artifact in artifacts]
        members = set(member_keys)
        if len(members) != len(member_keys) or any(
                "/".join(key.split("/")[:index]) in members
                for key in member_keys for index in range(1, len(key.split("/")))):
            raise StoreConflict("固定packageのファイル名が移動先で競合するため停止しました。")
        content = {artifact["name"]: self.read_artifact(artifact["id"])[1] for artifact in artifacts}
        manifest = json.loads(content["manifest.json"])
        if not isinstance(manifest, dict) or manifest.get("schema_version") not in (None, STORE_VERSION):
            raise StoreConflict("固定packageの形式に対応していません。")
        entries = manifest.get("artifacts")
        if not isinstance(entries, list) or any(not isinstance(entry, dict) or not isinstance(entry.get("name"), str) for entry in entries):
            raise StoreConflict("固定packageのmanifest形式が正しくありません。")
        expected = {artifact["name"]: artifact for artifact in entries}
        actual = {name: artifact for name, artifact in by_name.items() if name != "manifest.json"}
        if (len(by_name) != len(artifacts) or len(expected) != len(manifest.get("artifacts", []))
                or expected != actual or manifest.get("analysis_id") != run_id
                or manifest.get("fingerprint") != run["fingerprint"]
                or manifest.get("input_snapshot_id") != run["snapshot_id"]):
            raise StoreConflict("固定packageのmanifestが一致しません。再計算せず停止しました。")
        snapshot, result = json.loads(content["input.json"]), json.loads(content["result.json"])
        if not isinstance(snapshot, dict) or not isinstance(result, dict):
            raise StoreConflict("固定packageのJSON形式が正しくありません。")
        if digest(snapshot) != run["snapshot_id"]:
            raise StoreConflict("固定packageの入力snapshot hashが一致しません。再計算せず停止しました。")
        if result.get("schema_version") not in (None, STORE_VERSION):
            raise StoreConflict("固定結果の形式に対応していません。")
        parameters = json.loads(content["parameters.json"])
        if not isinstance(parameters, dict) or not isinstance(result.get("parameters", {}), dict):
            raise StoreConflict("固定packageの条件形式が正しくありません。")
        if parameters != result.get("parameters", {}):
            raise StoreConflict("固定packageの条件が一致しません。")
        self._verify_typed_tables(run, manifest, by_name, content)
        return snapshot, result, manifest, content

    @staticmethod
    def _verify_typed_tables(run, manifest, artifacts, content):
        json_names = {name for name in content if name.startswith("tables/") and name.endswith(".json")}
        if "table_format_version" not in manifest:
            if json_names or "typed_tables" in manifest:
                raise StoreConflict("型付き表の形式版が欠落しています。")
            return  # Legacy CSV remains readable; no inferred typed reconstruction.
        if type(manifest["table_format_version"]) is not int or manifest["table_format_version"] != TABLE_FORMAT_VERSION:
            raise StoreConflict("型付き表の保存形式に対応していません。")
        mapping = manifest.get("typed_tables")
        csv_names = {name for name in content if name.startswith("tables/") and name.endswith(".csv")}
        if (not isinstance(mapping, dict) or any(not re.fullmatch(r"[a-z_]+", name) for name in mapping)
                or json_names != {f"tables/{name}.json" for name in mapping}
                or csv_names != {f"tables/{name}.csv" for name in mapping}):
            raise StoreConflict("型付き表と共有CSVの対応が欠落しています。")
        for name, references in mapping.items():
            json_name, csv_name = f"tables/{name}.json", f"tables/{name}.csv"
            if references != {"data": json_name, "export": csv_name}:
                raise StoreConflict("型付き表の参照先が一致しません。")
            table = _read_typed_json(content[json_name])
            if (not isinstance(table, dict) or not isinstance(table.get("rows"), list)
                    or any(not isinstance(row, dict) or set(row) != {"row_id", "values"} for row in table["rows"])):
                raise StoreConflict("型付き表の行形式が正しくありません。")
            rows = [row["values"] for row in table["rows"]]
            expected_table = table_package(name, table.get("fields"), rows,
                                           run_id=run["id"], snapshot_id=run["snapshot_id"],
                                           source_revision=run["source_revision"], analysis_revision=run["analysis_revision"])
            if (canonical(table) != canonical(expected_table)
                    or artifacts[json_name]["media_type"] != "application/json"
                    or artifacts[csv_name]["media_type"] != "text/csv"
                    or type(artifacts[json_name]["rows"]) is not int or artifacts[json_name]["rows"] != len(rows)
                    or type(artifacts[csv_name]["rows"]) is not int or artifacts[csv_name]["rows"] != len(rows)
                    or csv_bytes(table["fields"], rows) != content[csv_name]):
                raise StoreConflict("型付き表の版・型・件数またはCSVとの対応が一致しません。")

    def read_table(self, run_id: str, dataset_id: str) -> dict:
        """Resolve a complete machine table through the verified saved manifest."""
        if not isinstance(dataset_id, str) or not re.fullmatch(r"[a-z_]+", dataset_id):
            raise StoreConflict("表の識別子が正しくありません。")
        _snapshot, _result, manifest, content = self.verified_package(run_id)
        references = manifest.get("typed_tables", {}).get(dataset_id)
        if references is None:
            raise StoreConflict("型付き全件表は保存されていません。CSVからの型推測は行いません。")
        return _read_typed_json(content[references["data"]])

    def _connection_content(self, descriptor, *, original=False):
        """Verify an explicit immutable address; never read a current library item."""
        _asset_descriptor(descriptor, original=original)
        key = descriptor["asset_key"]
        if key["library_id"] != self.library_id(): raise AssetBindingError("foreign_library")
        snapshot, _result, manifest, content = self.verified_package(key["store_run_id"])
        if manifest.get("library_id") != key["library_id"] or snapshot.get("library_id") != key["library_id"]:
            raise AssetBindingError("package_library_mismatch")
        artifact = next((row for row in self.artifacts(key["store_run_id"])
                         if row["id"] == key["artifact_id"] and row["name"] == key["output_name"]), None)
        if artifact is None: raise AssetBindingError("artifact_missing", "needs_input")
        raw = content[key["output_name"]]
        if _asset_hash(raw) != descriptor["raw_byte_hash"]: raise AssetBindingError("raw_hash_mismatch")
        if original:
            from .analysis_method_registry import connection_method_descriptor
            native = connection_method_descriptor("pearson")
            ref = descriptor["source_ref"]
            expected = {"target_type": "snapshot", "target_id": manifest["input_snapshot_id"],
                        "version": str(manifest["source_revision"]), "content_hash": _asset_hash(canonical(snapshot)),
                        "hash_domain": "canonical-json-v1", "library_id": key["library_id"]}
            if (key["output_name"] != "input.json" or canonical(ref) != canonical(expected)
                    or descriptor["schema"] != native["native_input_schema"]
                    or descriptor["adapter"] != native["native_adapter"]):
                raise AssetBindingError("original_reference_mismatch")
            if (not isinstance(snapshot.get("analysis"), dict) or not _asset_id(snapshot.get("input_hash"))
                    or type(snapshot.get("source_revision")) is not int or type(snapshot.get("analysis_revision")) is not int
                    or snapshot["source_revision"] < 0 or snapshot["analysis_revision"] < 0
                    or snapshot["source_revision"] != manifest["source_revision"]
                    or snapshot["analysis_revision"] != manifest["analysis_revision"]):
                raise AssetBindingError("original_payload_schema")
        else:
            dataset = key["output_name"].removeprefix("tables/").removesuffix(".json")
            if (key["output_name"] != f"tables/{dataset}.json" or dataset not in manifest.get("typed_tables", {})
                    or descriptor["schema"] != {"schema_id": "gurumoji.analysis-table", "version": 1,
                                               "schema_hash": _asset_hash(canonical(CONNECTION_TABLE_SCHEMA))}
                    or descriptor["adapter"] != {"adapter_id": "analysis-store-table", "version": "1"}):
                raise AssetBindingError("table_schema_or_hash", "unsupported")
            if descriptor["content_hash"] != _asset_hash(raw): raise AssetBindingError("content_hash_mismatch")
            table = self.read_table(key["store_run_id"], dataset)
            if set(v["variable_id"] for v in descriptor["variables"]) != {c["name"] for c in table["columns"]}:
                raise AssetBindingError("table_variable_coverage")
            for variable in descriptor["variables"]:
                for row in table["rows"]:
                    if variable["variable_id"] not in row["values"] or row["values"][variable["variable_id"]] is None:
                        continue
                    value = row["values"][variable["variable_id"]]
                    allowed = {"string": {str}, "number": {int, float}, "integer": {int}, "boolean": {bool}}
                    if type(value) not in allowed[variable["value_type"]]: raise AssetBindingError("variable_value_type")
        def check_times(value):
            if isinstance(value, dict):
                if value.get("valid_time") is False and any(value.get(k) is not None for k in ("start", "end", "duration")):
                    raise AssetBindingError("invalid_time_placeholder")
                for child in value.values(): check_times(child)
            elif isinstance(value, list):
                for child in value: check_times(child)
        check_times(_read_typed_json(raw))
        scope = descriptor["scope"]
        if scope["conversation_ids"] != [manifest["conversation_id"]]:
            raise AssetBindingError("scope_conversation")
        source = {"target_type": "snapshot", "target_id": manifest["input_snapshot_id"],
                  "version": str(manifest["source_revision"]), "content_hash": _asset_hash(canonical(snapshot)),
                  "hash_domain": "canonical-json-v1", "library_id": key["library_id"]}
        if scope["input_refs"] != [source] or (not original and source not in descriptor["source_refs"]):
            raise AssetBindingError("scope_input_version")
        # Only dataset scopes have a storage projection in this wave.
        if scope["mode"] != "dataset": raise AssetBindingError("scope_projection_unimplemented", "unsupported")
        evidence = snapshot.get("evidence")
        if (not isinstance(evidence, list) or any(not isinstance(e, dict) or not _asset_id(e.get("evidence_id"))
                or type(e.get("excluded")) is not bool for e in evidence)):
            raise AssetBindingError("scope_population_unavailable", "needs_input")
        ids = [e["evidence_id"] for e in evidence]
        if (len(ids) != len(set(ids))
                or set(scope["member_ids"]) != {e["evidence_id"] for e in evidence if not e["excluded"]}
                or set(scope["context_ids"]) != {e["evidence_id"] for e in evidence if e["excluded"]}):
            raise AssetBindingError("scope_population_mismatch")
        return raw, snapshot

    def _connection_packages(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT id FROM analysis_runs WHERE kind=? AND status='completed' ORDER BY id",
                                (CONNECTION_METADATA_KIND,)).fetchall()
        packages = []
        for row in rows:
            _snapshot, result, _manifest, _content = self.verified_package(row[0])
            value = result.get("connection_metadata")
            _asset_fields(value, ("version", "assets", "originals", "states", "producer_links"))
            if type(value["version"]) is not int or value["version"] != CONNECTION_METADATA_VERSION:
                raise AssetBindingError("metadata_version", "unsupported")
            if any(not isinstance(value[k], list) for k in ("assets", "originals", "states", "producer_links")):
                raise AssetBindingError("metadata_shape")
            packages.append((row[0], value))
        return packages

    def _connection_index(self):
        """State revisions select current permissions, never the latest asset/run."""
        assets, originals, states, links = {}, {}, {}, []
        for metadata_run, package in self._connection_packages():
            for field, target in (("assets", assets), ("originals", originals)):
                for descriptor in package[field]:
                    _asset_descriptor(descriptor, original=field == "originals")
                    key = _asset_key(descriptor["asset_key"])
                    if key in target and canonical(target[key]) != canonical(descriptor):
                        raise AssetBindingError("immutable_descriptor_changed")
                    target[key] = descriptor
            for state in package["states"]:
                _asset_state(state); key = _asset_key(state["asset_key"])
                revision = state["state_revision"]
                history = states.setdefault(key, {})
                if revision in history and canonical(history[revision]) != canonical(state):
                    raise AssetBindingError("state_revision_conflict")
                history[revision] = state
            links.extend(package["producer_links"])
        for key in assets.keys() & originals.keys(): raise AssetBindingError("source_kind_conflict")
        for key, history in states.items():
            descriptor = assets.get(key) or originals.get(key)
            if descriptor is None: raise AssetBindingError("state_target_missing", "needs_input")
            checked = {}
            for revision in sorted(history): _asset_transition(checked, history[revision], descriptor)
        for link in links: _asset_producer_link(link, assets)
        return assets, originals, states, links

    def save_connection_metadata(self, *, request_id, item_id, snapshot, metadata):
        """Append a new immutable metadata package via save, without SQL migration.

        This private opt-in route has no human adoption, publication or scheduler.
        State/policy and review/history bytes are outside the referenced payload.
        """
        _asset_fields(metadata, ("version", "assets", "originals", "states", "producer_links"))
        if type(metadata["version"]) is not int or metadata["version"] != CONNECTION_METADATA_VERSION:
            raise AssetBindingError("metadata_version", "unsupported")
        if any(not isinstance(metadata[k], list) for k in ("assets", "originals", "states", "producer_links")):
            raise AssetBindingError("metadata_shape")
        with STORE_LOCK:
            old_assets, old_originals, old_states, _links = self._connection_index()
            assets, originals = dict(old_assets), dict(old_originals)
            for field, target in (("assets", assets), ("originals", originals)):
                keys = []
                for descriptor in metadata[field]:
                    self._connection_content(descriptor, original=field == "originals")
                    key = _asset_key(descriptor["asset_key"]); keys.append(key)
                    if key in target and canonical(target[key]) != canonical(descriptor):
                        raise AssetBindingError("immutable_descriptor_changed")
                    target[key] = descriptor
                if len(keys) != len(set(keys)): raise AssetBindingError("duplicate_asset")
            if assets.keys() & originals.keys(): raise AssetBindingError("source_kind_conflict")
            # Referenced content stays a DAG, even when revisions use old keys.
            by_artifact = {a["asset_key"]["artifact_id"]: key for key, a in assets.items()}
            graph = {key: [by_artifact[r["target_id"]] for r in a["parent_refs"] + a.get("supersedes", [])
                           if r["target_type"] == "artifact" and r["target_id"] in by_artifact]
                     for key, a in assets.items()}
            visited, visiting = set(), set()
            def visit(key):
                if key in visiting: raise AssetBindingError("content_cycle")
                if key in visited: return
                visiting.add(key)
                for parent in graph.get(key, []): visit(parent)
                visiting.remove(key); visited.add(key)
            for key in graph: visit(key)
            histories = copy.deepcopy(old_states)
            for state in metadata["states"]: _asset_state(state)
            for state in sorted(metadata["states"], key=lambda s: s["state_revision"]):
                key = _asset_key(state["asset_key"])
                descriptor = assets.get(key) or originals.get(key)
                if descriptor is None: raise AssetBindingError("state_target_missing", "needs_input")
                _asset_transition(histories.setdefault(key, {}), state, descriptor)
            for link in metadata["producer_links"]:
                _asset_producer_link(link, assets)
                identity = {k:v for k,v in link.items() if k != "asset_key"}
                if any(canonical({k:v for k,v in old.items() if k != "asset_key"}) == canonical(identity)
                       and old["asset_key"] != link["asset_key"] for old in _links):
                    raise AssetBindingError("producer_mapping_changed")
            payload = json.loads(canonical(metadata))
            return self.save(item_id=item_id, kind=CONNECTION_METADATA_KIND, snapshot=snapshot,
                             result={"schema_version": STORE_VERSION, "parameters": {"metadata_hash": digest(payload)},
                                     "connection_metadata": payload}, datasets={}, request_id=request_id,
                             input_fingerprint=digest(snapshot), source_revision=1, analysis_revision=1, publish=False)

    def list_assets(self, *, output_name=None):
        """Enumerate distinct explicit choices, never choose/recompute/adopt one."""
        assets, _originals, _states, _links = self._connection_index()
        rows = []
        for asset in assets.values():
            if output_name is not None and asset["asset_key"]["output_name"] != output_name: continue
            self._connection_content(asset)
            rows.append(copy.deepcopy(asset))
        return sorted(rows, key=lambda a: canonical(a["asset_key"]))

    def _connection_parent(self, ref, context, links):
        source = ref["source"]
        matches = [link for link in links if all(link[k] == ref[k] for k in ("plan_id", "plan_version", "plan_hash", "generation"))
                   and link["producer_task_id"] == source["producer_task_id"] and link["output_name"] == source["output_name"]]
        unique = {digest(link): link for link in matches}
        if not unique: raise AssetBindingError("parent_mapping_unresolved", "needs_input")
        if len(unique) != 1: raise AssetBindingError("parent_mapping_ambiguous")
        link = next(iter(unique.values()))
        # The mapping is insufficient: the existing persisted producer ledger is authority.
        try:
            with self.connect() as conn:
                task_row = conn.execute("SELECT run_id,state_json FROM orchestration_tasks WHERE task_id=?",
                                        (link["producer_task_id"],)).fetchone()
                run_row = conn.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?",
                                       (link["execution_run_id"],)).fetchone()
                result_row = conn.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=? AND run_id=?",
                                          (link["producer_task_id"], link["execution_run_id"])).fetchone()
        except Exception as exc:
            import sqlite3
            if isinstance(exc, sqlite3.OperationalError): raise AssetBindingError("parent_ledger_unavailable", "needs_input") from None
            raise
        if not task_row or not run_row: raise AssetBindingError("parent_unresolved", "needs_input")
        task, run = _read_typed_json(task_row["state_json"]), _read_typed_json(run_row[0])
        if task.get("status") in {"failed", "cancelled", "quarantined", "blocked"}:
            raise AssetBindingError("parent_failed", "blocked")
        if task.get("status") != "succeeded" or not result_row: raise AssetBindingError("parent_unresolved", "needs_input")
        expected = {k: ref[k] for k in ("plan_id", "plan_version", "plan_hash", "generation")}
        if (task_row["run_id"] != link["execution_run_id"] or task.get("task_id") != link["producer_task_id"]
                or task.get("run_id") != link["execution_run_id"] or type(task.get("generation")) is not int
                or task["generation"] != ref["generation"]
                or canonical(run.get("asset_plan_identity")) != canonical(expected)):
            raise AssetBindingError("parent_plan_identity")
        raw, state = _read_typed_json(result_row[0]), _read_typed_json(result_row[1])
        if (state.get("validation_status") != "valid" or state.get("raw_hash") != _asset_hash(canonical(raw))
                or state.get("task_id") != link["producer_task_id"] or state.get("run_id") != link["execution_run_id"]):
            raise AssetBindingError("parent_result_integrity")
        return link["asset_key"]

    def bind_asset_inputs(self, *, slot, inputs, context, method_id, assess=None):
        """Read/resolve/revalidate only; eligibility never executes or adopts."""
        from .analysis_core import validate_connection_slot, assess_connection_inputs, _connection_hash
        from .analysis_method_registry import connection_method_descriptor
        base = {"version": "analysis-asset-bindings-1", "execution_enabled": False, "adoption_performed": False,
                "bindings": [], "payloads": [], "decision": "needs_input", "reason": "unresolved"}
        try:
            slot = validate_connection_slot(slot)
            _asset_fields(context, ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id",
                                    "purpose", "destination", "scope_id", "scope_manifest_hash", "cancelled"))
            from .analysis_core import CONNECTION_PURPOSES
            if (not all(_asset_id(context[k]) for k in ("plan_id", "consumer_task_id", "destination", "scope_id"))
                    or context["purpose"] not in CONNECTION_PURPOSES or type(context["cancelled"]) is not bool
                    or any(type(context[k]) is not int or context[k] < 1 for k in ("plan_version", "generation"))
                    or not all(_connection_hash(context[k]) for k in ("plan_hash", "scope_manifest_hash"))):
                raise AssetBindingError("context")
            if context["cancelled"]: raise AssetBindingError("cancelled", "blocked")
            descriptor = connection_method_descriptor(method_id)
            if descriptor is None: raise AssetBindingError("method_unregistered")
            if not isinstance(inputs, list): raise AssetBindingError("inputs")
            assets, originals, states, links = self._connection_index()
            envelopes, permissions, seen = [], [], set()
            base["parent_checks"] = []
            walked = set()
            def parent_permissions(asset, original, visiting=()):
                key = _asset_key(asset["asset_key"])
                if key in visiting: raise AssetBindingError("content_cycle")
                if key in walked: return
                self._connection_content(asset, original=original)
                history = states.get(key, {})
                if not history: raise AssetBindingError("parent_state_unknown", "needs_input")
                state = history[max(history)]
                if state["revoked"] or state["status"] in {"rejected", "retired", "stale", "unavailable"}:
                    raise AssetBindingError("parent_state_unavailable", "blocked")
                if state["status"] != "adopted": raise AssetBindingError("parent_not_adopted", "human_pending")
                if asset["producer"]["kind"] in {"ai", "researcher"} or state["review_refs"]:
                    raise AssetBindingError("parent_human_unverified", "human_pending")
                if (asset["scope"]["scope_id"], asset["scope"]["manifest_hash"]) != (context["scope_id"], context["scope_manifest_hash"]):
                    raise AssetBindingError("parent_scope_intersection", "blocked")
                permissions.append(state)
                base["parent_checks"].append({"asset_key": asset["asset_key"], "target_content_hash": state["target_content_hash"],
                                              "target_domain": state["target_domain"], "state_revision": state["state_revision"],
                                              "policy_revision": state["policy_revision"]})
                for parent_ref in asset.get("parent_refs", []):
                    if parent_ref["target_type"] == "artifact":
                        matches = [a for a in assets.values() if a["asset_key"]["artifact_id"] == parent_ref["target_id"]
                                   and str(a["schema"]["version"]) == parent_ref["version"]
                                   and a["content_hash"] == parent_ref["content_hash"] and a["content_domain"] == parent_ref["hash_domain"]
                                   and parent_ref.get("library_id") == a["asset_key"]["library_id"]]
                        parent_original = False
                    elif parent_ref["target_type"] == "snapshot":
                        matches = [a for a in originals.values() if canonical(a["source_ref"]) == canonical(parent_ref)]
                        parent_original = True
                    else: raise AssetBindingError("parent_reference_unimplemented", "unsupported")
                    if len(matches) != 1: raise AssetBindingError("parent_reference_unresolved", "needs_input")
                    parent_permissions(matches[0], parent_original, visiting + (key,))
                walked.add(key)
            for ref in inputs:
                _asset_fields(ref, ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id",
                                    "slot_id", "input_ref_id", "role", "selection", "omission_reason"), ("source", "selector"))
                if (any(ref[k] != context[k] or type(ref[k]) is not type(context[k]) for k in
                        ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id"))
                        or ref["slot_id"] != slot["slot_id"] or not _asset_id(ref["input_ref_id"])
                        or ref["input_ref_id"] in seen or ref["role"] not in slot["roles"]):
                    raise AssetBindingError("input_identity")
                seen.add(ref["input_ref_id"])
                if ref["selection"] == "omitted":
                    if slot["required"] or "source" in ref or "selector" in ref or not _asset_id(ref["omission_reason"]):
                        raise AssetBindingError("illegal_omission")
                    continue
                if ref["selection"] != "selected" or ref["omission_reason"] is not None:
                    raise AssetBindingError("selection")
                if "source" not in ref or "selector" not in ref: raise AssetBindingError("selected_unresolved", "needs_input")
                source = ref["source"]; selector = ref["selector"]
                _asset_fields(selector, ("row_ids", "column_ids", "range_ref", "selection_hash"))
                if (not _asset_ids(selector["row_ids"]) or not _asset_ids(selector["column_ids"])
                        or (selector["range_ref"] is not None and not _asset_ref(selector["range_ref"]))
                        or selector["selection_hash"] != _asset_hash(canonical({k: v for k, v in selector.items() if k != "selection_hash"}))):
                    raise AssetBindingError("selector")
                if not isinstance(source, dict): raise AssetBindingError("source")
                original = source.get("type") == "original"
                if original:
                    _asset_fields(source, ("type", "source_ref"))
                    from .analysis_core import _connection_source_ref
                    if not _connection_source_ref(source["source_ref"]): raise AssetBindingError("source_ref")
                    if source["source_ref"]["target_type"] != "snapshot":
                        raise AssetBindingError("original_type_unimplemented", "unsupported")
                    matches = [a for a in originals.values() if canonical(a["source_ref"]) == canonical(source["source_ref"])]
                    if not matches: raise AssetBindingError("original_unresolved", "needs_input")
                    if len(matches) != 1: raise AssetBindingError("original_ambiguous")
                    asset = matches[0]; key = asset["asset_key"]
                elif source.get("type") == "frozen":
                    _asset_fields(source, ("type", "asset_key", "content_hash", "content_domain"))
                    key = source["asset_key"]; key_id = _asset_key(key)
                    if key["library_id"] != self.library_id(): raise AssetBindingError("foreign_library")
                    asset = assets.get(key_id)
                    if not asset: raise AssetBindingError("asset_unresolved", "needs_input")
                    if (source["content_hash"], source["content_domain"]) != (asset["content_hash"], asset["content_domain"]):
                        raise AssetBindingError("content_target_mismatch")
                elif source.get("type") == "from_step":
                    _asset_fields(source, ("type", "producer_task_id", "output_name"))
                    if not all(_asset_id(source[k]) for k in ("producer_task_id", "output_name")):
                        raise AssetBindingError("from_step")
                    if source["producer_task_id"] == context["consumer_task_id"]: raise AssetBindingError("task_cycle")
                    key = self._connection_parent(ref, context, links); asset = assets.get(_asset_key(key))
                    if not asset: raise AssetBindingError("parent_not_saved", "needs_input")
                else: raise AssetBindingError("source_type")
                raw, snapshot = self._connection_content(asset, original=original)
                key_id = _asset_key(key)
                history = states.get(key_id, {})
                if not history: raise AssetBindingError("state_unknown", "needs_input")
                state = history[max(history)]
                if state["target_content_hash"] != asset.get("content_hash", asset["raw_byte_hash"]) or state["target_domain"] != asset.get("content_domain", "raw-bytes-v1"):
                    raise AssetBindingError("state_target_mismatch")
                if state["revoked"] or state["status"] in {"rejected", "retired", "stale", "unavailable"}:
                    raise AssetBindingError("state_unavailable", "blocked")
                if state["status"] != "adopted": raise AssetBindingError("not_adopted", "human_pending")
                if asset["producer"]["kind"] in {"ai", "researcher"} or state["review_refs"]:
                    # No trusted human-record adoption seam exists in this wave.
                    raise AssetBindingError("human_record_unverified", "human_pending")
                if asset["meaning"]["status"] != "declared": raise AssetBindingError("meaning_unknown", "human_pending")
                if context["purpose"] == "confirmatory" and not original and any(v["validity"] != "human_reviewed" for v in asset["variables"]):
                    raise AssetBindingError("variable_review_unconfirmed", "human_pending")
                scope = asset["scope"]
                if (scope["scope_id"], scope["manifest_hash"]) != (context["scope_id"], context["scope_manifest_hash"]):
                    raise AssetBindingError("scope_mismatch")
                if selector["range_ref"] is not None: raise AssetBindingError("range_adapter_unimplemented", "unsupported")
                if original:
                    if selector["row_ids"] or selector["column_ids"]: raise AssetBindingError("original_selector_unimplemented", "unsupported")
                    payload = _read_typed_json(raw)
                else:
                    payload = _read_typed_json(raw)
                    rows = {r["row_id"]: r for r in payload["rows"]}; columns = {c["name"] for c in payload["columns"]}
                    if not set(selector["row_ids"]) <= rows.keys() or not set(selector["column_ids"]) <= columns:
                        raise AssetBindingError("selector_id")
                    if selector["row_ids"]: payload["rows"] = [rows[r] for r in selector["row_ids"]]
                    if selector["column_ids"]:
                        keep = set(selector["column_ids"]); payload["fields"] = list(selector["column_ids"])
                        payload["columns"] = [c for c in payload["columns"] if c["name"] in keep]
                        payload["rows"] = [{**r, "values": {k: v for k, v in r["values"].items() if k in keep}} for r in payload["rows"]]
                    payload["row_count"] = len(payload["rows"])
                    # Projection has its own counts; source row IDs and raw bytes stay fixed.
                    for column in payload["columns"]:
                        name = column["name"]; selected_values = [r["values"] for r in payload["rows"]]
                        column.update(observed_types=sorted({_table_value_type(r[name]) for r in selected_values if name in r}),
                                      absent_count=sum(name not in r for r in selected_values),
                                      null_count=sum(name in r and r[name] is None for r in selected_values))
                payload_raw = canonical(payload)
                if len(payload_raw) > slot["max_bytes"]: raise AssetBindingError("payload_byte_limit", "needs_input")
                permissions.append(state)
                parent_permissions(asset, original)
                content_hash = asset.get("content_hash", asset["source_ref"]["content_hash"] if original else None)
                domain = asset.get("content_domain", asset["source_ref"]["hash_domain"] if original else None)
                binding_source = asset["source_ref"] if original else key
                identity = {"input": ref, "source": binding_source, "content_hash": content_hash, "content_domain": domain,
                            "selection_hash": selector["selection_hash"], "schema": asset["schema"]}
                binding = {"source_type": "original" if original else "artifact", "binding_id": _asset_hash(canonical(identity)),
                           "input_ref_id": ref["input_ref_id"], "source": copy.deepcopy(binding_source),
                           "content_hash": content_hash, "content_domain": domain, "selection_hash": selector["selection_hash"],
                           "schema": copy.deepcopy(asset["schema"]), "checked_state_revision": state["state_revision"],
                           "checked_policy_revision": state["policy_revision"], "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                           "decision": "unsupported", "reason": "consumer_adapter_unimplemented"}
                base["bindings"].append(binding)
                base["payloads"].append({"input_ref_id": ref["input_ref_id"], "payload_hash": _asset_hash(payload_raw),
                                         "payload_domain": "canonical-json-v1", "bytes": len(payload_raw), "value": payload})
                candidate = {"source_type": "original" if original else "artifact", "schema": asset["schema"],
                             "unit": asset["meaning"]["unit"], "scope_mode": scope["mode"], "scope_policy": "all_included_initial",
                             "actor": asset["producer"], "adapter": asset["adapter"], "purpose": context["purpose"],
                             "meaning_status": asset["meaning"]["status"], "human_review_state": "structural_checked"}
                candidate.update({"source_ref": asset["source_ref"]} if original else
                                 {"kind": asset["kind"], "content_hash": content_hash, "content_domain": domain})
                envelopes.append({"input_ref_id": ref["input_ref_id"], "selection": "selected", "role": ref["role"],
                                  "omission_reason": None, "candidate": candidate})
            if not envelopes: raise AssetBindingError("omitted_or_empty", "needs_input")
            purposes = set.intersection(*(set(s["allowed_purposes"]) for s in permissions))
            if context["purpose"] not in purposes: raise AssetBindingError("purpose_intersection", "blocked")
            if any(s["send_policy"] == "prohibited" or (s["send_policy"] == "local_only" and context["destination"] != "local")
                   or (s["send_policy"] == "permitted_destinations" and context["destination"] not in s["destinations"]) for s in permissions):
                raise AssetBindingError("destination_intersection", "blocked")
            total = sum(p["bytes"] for p in base["payloads"])
            if total > slot["max_bytes"]: raise AssetBindingError("payload_byte_limit", "needs_input")
            checked = assess(envelopes) if assess else assess_connection_inputs(slot, envelopes, descriptor)
            base["parent_checks"].sort(key=lambda row: canonical(row["asset_key"]))
            _new_assets, _new_originals, current_states, _new_links = self._connection_index()
            for check in base["parent_checks"]:
                current_history = current_states.get(_asset_key(check["asset_key"]), {})
                current_state = current_history[max(current_history)] if current_history else {}
                if any(current_state.get(k) != check[k] for k in
                       ("target_content_hash", "target_domain", "state_revision", "policy_revision")):
                    raise AssetBindingError("state_changed_during_resolution", "blocked")
            base.update(decision=checked["decision"], reason=checked["reason"], content_resolution=True,
                        state_policy_pre_adoption=True, actual_payload_bytes=total,
                        authority_check="registry_callback" if assess else "metadata_only",
                        effective_permissions={"purposes": sorted(purposes), "destination": context["destination"]},
                        input_refs_hash=_asset_hash(canonical(inputs)), context_hash=_asset_hash(canonical(context)))
            for binding in base["bindings"]: binding.update(decision=base["decision"], reason=base["reason"])
            if base["decision"] not in {"eligible", "unsupported"}:
                base["payloads"] = []
            return base
        except AssetBindingError as exc:
            base.update(decision=exc.decision, reason=exc.reason)
        except (ValueError, TypeError, KeyError, OSError):
            base.update(decision="rejected", reason="invalid_or_unverified")
        # Failed checks never deliver a partial payload.
        base["payloads"] = []
        for binding in base["bindings"]: binding.update(decision=base["decision"], reason=base["reason"])
        return base

    def prepare_table_pilot(self, method_id, request, *, expected_snapshot=None):
        """Resolve a bounded frozen table; no adoption, scheduler or inferred metadata."""
        from .analysis_core import validate_table_pilot_request, AnalysisContractError, fingerprint
        request = validate_table_pilot_request(method_id, request)
        binding = request["bindings"]
        context = binding["context"]
        if context["purpose"] not in {"descriptive", "exploratory"} or context["destination"] != "local":
            raise AnalysisContractError("局所記述・探索専用です。", code="table_policy_unsupported")
        receipt = self.bind_asset_inputs(method_id=method_id, **binding)
        if receipt["decision"] != "eligible":
            raise AnalysisContractError("固定表を利用できません。", code="table_input_" + receipt["reason"])
        assets = self._connection_index()[0]
        tables = []
        for resolved, delivered in zip(receipt["bindings"], receipt["payloads"]):
            asset = assets[_asset_key(resolved["source"])]
            _raw, original = self._connection_content(asset)
            if expected_snapshot is not None:
                for key in ("input_hash", "conversation_id", "source_revision", "analysis_revision"):
                    if original.get(key) != expected_snapshot.get(key):
                        raise AnalysisContractError("表の元入力版が異なります。", code="table_source_mismatch")
                if fingerprint(original.get("evidence")) != fingerprint(expected_snapshot.get("evidence")):
                    raise AnalysisContractError("発話集合が異なります。", code="table_source_mismatch")
            ref = next(r for r in binding["inputs"] if r["input_ref_id"] == resolved["input_ref_id"])
            if ref["selector"]["row_ids"] or ref["selector"]["column_ids"]:
                raise AnalysisContractError("部分選択は登録projectionで指定してください。", code="table_selector_unsupported")
            if any(v["unit"] != "utterance" for v in asset["variables"]):
                raise AnalysisContractError("変数の単位が異なります。", code="table_variable_unit")
            value = delivered["value"]
            fields = value["fields"]
            base = {"utterance_id", "conversation_id", "value_status"}
            if not base <= set(fields):
                raise AnalysisContractError("発話単位の基底列がありません。", code="table_base_columns")
            provenance_excluded = set()
            if asset["method_id"] in {"table_projection", "table_aggregate", "table_join"}:
                verified_descriptor = self.table_pilot_output_descriptor(asset["asset_key"]["store_run_id"])
                if verified_descriptor != asset:
                    raise AnalysisContractError("producer記録とdescriptorが異なります。", code="table_producer_mismatch")
                producer_result = self.verified_package(asset["asset_key"]["store_run_id"])[1]
                provenance_excluded = set(producer_result["population"]["excluded_ids"])
            evidence = original["evidence"]
            originals = {e.get("utterance_id", e["evidence_id"]): e for e in evidence}
            seen = set()
            measured = [request["parameters"][k] for k in ("value_column", "row_column", "column_column")
                        if k in request["parameters"]]
            if not set(measured) <= set(fields):
                raise AnalysisContractError("登録列がありません。", code="table_variable_missing")
            if method_id == "table_projection" and not set(request["parameters"]["columns"]) <= set(fields):
                raise AnalysisContractError("projection列がありません。", code="table_variable_missing")
            for row in value["rows"]:
                v = row["values"]; uid = v.get("utterance_id")
                if (not isinstance(uid, str) or not uid or uid in seen or uid not in originals
                        or v.get("conversation_id") != original["conversation_id"]
                        or v.get("value_status") not in {"observed", "excluded", "missing", "unprocessed", "unknown"}
                        or ((v["value_status"] == "excluded") != (originals[uid]["excluded"] or uid in provenance_excluded))):
                    raise AnalysisContractError("発話ID・状態・会話が不正です。", code="table_row_identity")
                status = v["value_status"]
                if ((status == "observed" and any(c not in v or v[c] is None for c in measured))
                        or (status in {"missing", "unprocessed", "unknown"} and any(v.get(c) is not None for c in measured))):
                    raise AnalysisContractError("状態と測定値が矛盾しています。", code="table_status_value")
                seen.add(uid)
            if seen != set(originals):
                raise AnalysisContractError("未処理発話も明示してください。", code="table_population_incomplete")
            tables.append({"table": copy.deepcopy(value), "variables": copy.deepcopy(asset["variables"]),
                           "scope": copy.deepcopy(asset["scope"])})
        if method_id == "table_join":
            if tables[0]["scope"] != tables[1]["scope"]:
                raise AnalysisContractError("結合対象の範囲が異なります。", code="table_join_scope")
            left = {r["values"]["utterance_id"]: r["values"] for r in tables[0]["table"]["rows"]}
            right = {r["values"]["utterance_id"]: r["values"] for r in tables[1]["table"]["rows"]}
            if left.keys() != right.keys() or any(
                    (left[i]["conversation_id"], left[i]["value_status"]) !=
                    (right[i]["conversation_id"], right[i]["value_status"]) for i in left):
                raise AnalysisContractError("結合の人口・会話・状態が異なります。", code="table_join_population")
            if (set(tables[0]["table"]["fields"]) & set(tables[1]["table"]["fields"])) - {"utterance_id", "conversation_id", "value_status"}:
                raise AnalysisContractError("非基底列が衝突します。", code="table_join_columns")
        from .analysis_core import TABLE_PILOT_MAX_BYTES
        if len(canonical(tables)) > TABLE_PILOT_MAX_BYTES:
            raise AnalysisContractError("実payloadのUTF8上限を超えました。", code="table_payload_byte_limit")
        return {"request": request, "receipt": receipt, "tables": tables,
                "content_hash": fingerprint(tables)}

    def table_pilot_carrier(self, raw, prepared):
        """Persist primitive utterance carriers with explicit projection omissions."""
        from .analysis_core import AnalysisContractError, fingerprint
        method = raw["method_id"]
        if method not in {"table_projection", "table_aggregate", "table_join"}:
            return raw["datasets"]["table"], None
        output = raw["datasets"]["table"]
        fields = [f for f in output["fields"] if f != "source_utterance_ids"]
        base = {"utterance_id", "conversation_id", "value_status"}
        if not base <= set(fields):
            raise AnalysisContractError("再利用表に基底列がありません。", code="table_carrier_columns")
        by_uid = {}
        for row in output["rows"]:
            uid = row["utterance_id"]
            if uid in by_uid or row["source_utterance_ids"] != [uid]:
                raise AnalysisContractError("再利用表の発話対応が不正です。", code="table_carrier_identity")
            by_uid[uid] = {k: row[k] for k in fields}
        original = prepared["tables"][0]["table"]["rows"]
        originals = {r["values"]["utterance_id"]: r for r in original}
        if method == "table_projection":
            selection = set(prepared["request"]["parameters"]["row_ids"])
            expected = {r["values"]["utterance_id"] for r in original if r["row_id"] in selection}
            if set(by_uid) != expected:
                raise AnalysisContractError("projection結果が選択と異なります。", code="table_carrier_selection")
            for uid in originals.keys() - by_uid.keys():
                by_uid[uid] = {k: originals[uid]["values"].get(k) for k in fields}
                by_uid[uid]["value_status"] = "excluded"
        elif set(by_uid) != set(originals):
            raise AnalysisContractError("結合・集計が発話を失いました。", code="table_carrier_population")
        rows = [by_uid[uid] for uid in sorted(by_uid)]
        variables = {}
        for table in prepared["tables"]:
            for variable in table["variables"]:
                if variable["variable_id"] in fields: variables.setdefault(variable["variable_id"], copy.deepcopy(variable))
        if method == "table_aggregate":
            actor = {"kind": "code", "actor_id": "table-pilot-1", "step_ids": [method]}
            definition = {"target_type": "definition", "target_id": "table-pilot-count-1", "version": "1",
                          "content_hash": fingerprint({"method": method, "parameters": prepared["request"]["parameters"]}),
                          "hash_domain": "canonical-json-v1"}
            variables["count"] = {"variable_id": "count", "version": 1, "definition_hash": definition["content_hash"],
                "value_type": "integer", "scale": "ratio", "unit": "utterance", "value_domain": "observed_indicator",
                "generation": actor, "validity": "structural_checked", "definition_ref": definition}
        if set(variables) != set(fields):
            raise AnalysisContractError("再利用変数が未定義です。", code="table_carrier_variables")
        parents = [{"target_type": "artifact", "target_id": b["source"]["artifact_id"], "version": "1",
                    "content_hash": b["content_hash"], "hash_domain": b["content_domain"],
                    "library_id": b["source"]["library_id"]} for b in prepared["receipt"]["bindings"]]
        exclusion_reasons = {}
        for parent in prepared["receipt"]["bindings"]:
            _snapshot, parent_result, _manifest, _content = self.verified_package(parent["source"]["store_run_id"])
            prior = parent_result.get("parameters", {}).get("table_pilot_provenance") or {}
            exclusion_reasons.update(prior.get("exclusion_reasons", {}))
        for uid in raw["population"]["excluded_ids"]:
            exclusion_reasons.setdefault(uid, "registered_projection_omission" if
                method == "table_projection" and originals[uid]["row_id"] not in set(prepared["request"]["parameters"]["row_ids"])
                and originals[uid]["values"]["value_status"] != "excluded" else "original_input_excluded")
        exclusion_reasons = {i:exclusion_reasons[i] for i in raw["population"]["excluded_ids"]}
        provenance = {"version": "table-pilot-1", "method_id": method, "scope": prepared["tables"][0]["scope"],
                      "exclusion_reasons": exclusion_reasons,
                      "variables": [variables[k] for k in fields], "parent_refs": parents,
                      "carrier_hash": fingerprint(rows), "population_hash": fingerprint(raw["population"])}
        return {"fields": fields, "rows": rows}, provenance

    def table_pilot_output_descriptor(self, run_id):
        """Verified technical descriptor only. Caller must explicitly supply state."""
        from .analysis_core import AnalysisContractError, fingerprint
        snapshot, result, manifest, content = self.verified_package(run_id)
        provenance = result.get("parameters", {}).get("table_pilot_provenance")
        if (not isinstance(provenance, dict) or provenance.get("version") != "table-pilot-1"
                or result.get("method_id") not in {"table_projection", "table_aggregate", "table_join"}
                or provenance.get("method_id") != result["method_id"] or result.get("method_version") != "table-pilot-1"
                or result.get("manifest", {}).get("rows_hash") != fingerprint(result["datasets"]["table"]["rows"])
                or provenance.get("population_hash") != fingerprint(result["population"])
                or not isinstance(provenance.get("exclusion_reasons"), dict)
                or set(provenance["exclusion_reasons"]) != set(result["population"]["excluded_ids"])
                or any(not isinstance(v, str) or not v for v in provenance["exclusion_reasons"].values())):
            raise AnalysisContractError("再利用producerは未対応です。", code="table_producer_unsupported")
        parameters = result["parameters"]
        with self.connect() as connection:
            execution = connection.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?",
                                           (parameters.get("execution_run_id"),)).fetchone()
            task_row = connection.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                          (parameters.get("task_id"), parameters.get("execution_run_id"))).fetchone()
            raw_row = connection.execute("SELECT state_json FROM orchestration_results WHERE task_id=? AND run_id=?",
                                         (parameters.get("task_id"), parameters.get("execution_run_id"))).fetchone()
        execution = _read_typed_json(execution[0]) if execution else {}
        task = _read_typed_json(task_row[0]) if task_row else {}
        receipt = _read_typed_json(raw_row[0]) if raw_row else {}
        original_raw = {k:v for k,v in result.items() if k != "parameters"}
        if (execution.get("cancel_requested") or execution.get("status") == "cancelled"
                or task.get("status") != "succeeded" or task.get("validation_status") != "valid"
                or task.get("table_store_run_id") != run_id or task.get("method_id") != result["method_id"]
                or receipt.get("validation_status") != "valid" or receipt.get("result_id") != task.get("result_id")
                or receipt.get("raw_hash") != fingerprint(original_raw)):
            raise AnalysisContractError("producerは未検証・停止しています。", code="table_producer_unvalidated")
        table = self.read_table(run_id, "table")
        if provenance["carrier_hash"] != fingerprint([r["values"] for r in table["rows"]]):
            raise AnalysisContractError("再利用carrierが異なります。", code="table_carrier_hash")
        artifact = next(a for a in manifest["artifacts"] if a["name"] == "tables/table.json")
        raw_hash = _asset_hash(content["tables/table.json"])
        return {"asset_key": {"library_id": manifest["library_id"], "store_run_id": run_id,
                             "artifact_id": artifact["id"], "output_name": "tables/table.json"},
            "raw_byte_hash": raw_hash, "schema": {"schema_id": "gurumoji.analysis-table", "version": 1,
                                                "schema_hash": _asset_hash(canonical(CONNECTION_TABLE_SCHEMA))},
            "scope": copy.deepcopy(provenance["scope"]),
            "producer": {"kind": "code", "actor_id": "table-pilot-1", "step_ids": [result["method_id"]]},
            "adapter": {"adapter_id": "analysis-store-table", "version": "1"},
            "meaning": {"definition_refs": [], "description": "Registered utterance table carrier; semantic review unanswered",
                        "status": "declared", "unit": "utterance"},
            "contract_id": "gurumoji.analysis-asset-connection", "contract_version": 1,
            "content_hash": raw_hash, "content_domain": "raw-bytes-v1", "kind": "observation_table",
            "source_refs": copy.deepcopy(provenance["scope"]["input_refs"]),
            "method_id": result["method_id"], "method_version": "table-pilot-1",
            "variables": copy.deepcopy(provenance["variables"]), "parent_refs": copy.deepcopy(provenance["parent_refs"])}

    def revalidate_table_pilot(self, prepared, *, expected_snapshot=None):
        from .analysis_core import AnalysisContractError
        request = prepared["request"]
        checked = self.revalidate_asset_inputs(prepared["receipt"], method_id=prepared.get("method_id", ""),
                                               **request["bindings"])
        if checked["decision"] != "eligible":
            raise AnalysisContractError("表の状態・権限が変わりました。", code="table_policy_changed")
        current = self.prepare_table_pilot(prepared["method_id"], request, expected_snapshot=expected_snapshot)
        if current["content_hash"] != prepared["content_hash"]:
            raise AnalysisContractError("表の内容が変わりました。", code="table_content_changed")
        return current

    def revalidate_asset_inputs(self, previous, **request):
        current = self.bind_asset_inputs(**request)
        fields = ("binding_id", "content_hash", "content_domain", "selection_hash", "schema",
                  "checked_state_revision", "checked_policy_revision")
        valid_previous = (isinstance(previous, dict) and previous.get("version") == "analysis-asset-bindings-1"
                          and previous.get("decision") in {"eligible", "unsupported"}
                          and previous.get("execution_enabled") is False and previous.get("adoption_performed") is False
                          and isinstance(previous.get("bindings"), list)
                          and all(isinstance(b, dict) and set(fields) <= set(b) for b in previous["bindings"]))
        if (not valid_previous or current.get("decision") not in {"eligible", "unsupported"}
                or previous.get("context_hash") != current.get("context_hash")
                or previous.get("input_refs_hash") != current.get("input_refs_hash")
                or previous.get("parent_checks") != current.get("parent_checks")
                or [{k: b[k] for k in fields} for b in previous.get("bindings", [])]
                    != [{k: b[k] for k in fields} for b in current["bindings"]]):
            current.update(decision="blocked", reason="pre_adoption_revalidation_changed", payloads=[])
        current["adoption_performed"] = False
        return current

    def _publication_scope(self, run: dict, result: dict, targets: list[str] | None) -> list[str]:
        if run["kind"] in {"milestone_analysis", "autonomous_analysis"}:
            saved = result.get("parameters", {}).get("publication_targets")
            if saved is None:
                raise StoreConflict("旧packageの公開範囲を確認できません。新しい範囲へ自動拡大しません。")
            saved = validate_publication_targets(saved)
            if targets is not None and validate_publication_targets(targets) != saved:
                raise StoreConflict("再公開は保存時の承認範囲から変更できません。")
            if run["kind"] == "autonomous_analysis" and saved and run.get("stale"):
                raise StoreConflict("入力変更後の自律分析はVaultへ公開できません。固定成果物を確認してください。")
            return saved
        return validate_publication_targets(list(PUBLICATION_TARGETS) if targets is None else targets)

    def _record_blocked_publication(self, run: dict, targets: list[str] | None, error: Exception) -> None:
        """Keep validation failures visible without claiming any writer ran."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute("SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run["id"],)).fetchone()
            if latest and latest["status"] == "publishing":
                return
            requested = json.loads(latest["requested_json"]) if latest else targets
            if requested is None and run["kind"] not in {"milestone_analysis", "autonomous_analysis"}:
                requested = list(PUBLICATION_TARGETS)
            if requested is None:
                return  # Legacy scope is unknown; never invent permission.
            requested = validate_publication_targets(requested)
            if targets is not None and validate_publication_targets(targets) != requested:
                return  # A request for a different scope was not accepted.
            effective = list(EFFECTIVE_PUBLICATION_WRITERS) if requested else []
            message = str(error)[:1000]
            outcomes = {kind: {"status": "failed" if kind in effective else "not_selected", "error": message}
                        for kind in EFFECTIVE_PUBLICATION_WRITERS}
            now = datetime.now(timezone.utc).isoformat()
            connection.execute("""INSERT INTO analysis_publication_attempts
                (attempt_id,run_id,sequence,package_hash,requested_json,effective_json,executed_json,outcomes_json,status,error,created_at,ended_at)
                VALUES (?,?,?,?,?,?,'[]',?,'blocked',?,?,?)""", (uuid.uuid4().hex, run["id"], latest["sequence"] + 1 if latest else 1,
                run["fingerprint"], canonical(requested).decode(), canonical(effective).decode(), canonical(outcomes).decode(), message, now, now))

    def publish(self, run_id: str, *, targets: list[str] | None = None, commit_guard=None,
                reuse_completed: bool = False) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run or run["status"] != "completed":
                raise LookupError("完了した保存結果がありません。")
            # Scope resolution reads the saved result and never recomputes a missing package.
            try:
                snapshot, result = self._verified_package(run_id)
                requested = self._publication_scope(run, result, targets)
                if run["kind"] == "autonomous_analysis" and requested and commit_guard is None:
                    raise StoreConflict("自律分析の公開は専用の保存・公開再試行から実行してください。")
            except (OSError, ValueError, KeyError, TypeError, LookupError) as exc:
                self._record_blocked_publication(run, targets, exc)
                raise
            effective = list(EFFECTIVE_PUBLICATION_WRITERS) if requested else []
            outcomes = {kind: {"status": "pending" if kind in effective else "not_selected", "error": ""}
                        for kind in EFFECTIVE_PUBLICATION_WRITERS}
            attempt_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if commit_guard is not None:
                    commit_guard(connection)
                latest = connection.execute("SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
                if latest and latest["status"] == "publishing":
                    raise StoreConflict("このpackageの公開試行はまだ実行中です。")
                if latest and (json.loads(latest["requested_json"]) != requested or latest["package_hash"] != run["fingerprint"]):
                    raise StoreConflict("公開試行の固定packageまたは承認範囲が一致しません。")
                # Pipeline cancellation may arrive after the publication committed.
                # Reuse only the latest durable success, after package verification,
                # scope checks and the caller's current-generation guard above.
                # Direct user-requested republication keeps its existing behavior.
                if (reuse_completed and latest and latest["status"] == "completed" and effective
                        and all(json.loads(latest["outcomes_json"]).get(kind, {}).get("status") == "published"
                                for kind in effective)):
                    return self.get(run_id)
                sequence = latest["sequence"] + 1 if latest else 1
                connection.execute("""INSERT INTO analysis_publication_attempts
                    (attempt_id,run_id,sequence,package_hash,requested_json,effective_json,outcomes_json,status,created_at)
                    VALUES (?,?,?,?,?,?,?,'publishing',?)""", (attempt_id, run_id, sequence, run["fingerprint"],
                    canonical(requested).decode(), canonical(effective).decode(), canonical(outcomes).decode(), now))
            executed: list[str] = []
            error = ""
            self._note_events = []
            self._last_publication_outcomes.pop(run_id, None)
            try:
                if requested:
                    executed.extend(PUBLICATION_TARGETS)
                    self._update_publication_attempt(attempt_id, executed, outcomes, "publishing")
                    self._publish_generated_vaults(run_id)
                    generated = self._last_publication_outcomes.get(run_id, {})
                    for kind in PUBLICATION_TARGETS:
                        outcomes[kind] = generated.get(kind, {"status": "unknown", "error": "公開結果が返されませんでした。"})
                    executed.append("research")
                    self._update_publication_attempt(attempt_id, executed, outcomes, "publishing")
                    published = self._publish_research(run_id)
                    state = published.get("vault_status", "unknown")
                    outcomes["research"] = {"status": "published" if state == "completed" else state,
                                             "error": str(published.get("error") or "")}
            except Exception as exc:
                error = str(exc)[:1000]
                for kind in effective:
                    if outcomes[kind]["status"] == "pending":
                        outcomes[kind] = {"status": "failed" if kind in executed else "unknown", "error": error}
            status = ("not_selected" if not effective else "completed" if all(
                outcomes[kind]["status"] == "published" for kind in effective) else "incomplete")
            self._update_publication_attempt(attempt_id, executed, outcomes, status, error)
            return self.get(run_id)

    def _update_publication_attempt(self, attempt_id: str, executed: list[str], outcomes: dict,
                                    status: str, error: str = "") -> None:
        with self.connect() as connection:
            connection.execute("""UPDATE analysis_publication_attempts SET executed_json=?,outcomes_json=?,status=?,error=?,ended_at=?
                WHERE attempt_id=? AND status='publishing'""", (canonical(executed).decode(), canonical(outcomes).decode(),
                status, error, None if status == "publishing" else datetime.now(timezone.utc).isoformat(), attempt_id))

    def _read_package(self, run_id: str) -> tuple[dict, dict]:
        artifacts = {a["name"]: a for a in self.artifacts(run_id)}
        return tuple(json.loads(self.read_artifact(artifacts[name]["id"])[1]) for name in ("input.json", "result.json"))

    def follow_moves(self, item_id: str) -> None:
        """Apply interview folder moves detected by ObsidianLayout to the SQLite catalog."""
        self.layout.follow(item_id)
        record = self.layout.load()["interviews"].get(item_id) or {}
        if not record.get("moved_from"):
            return
        with self.connect() as conn:
            for old in record["moved_from"]:
                prefix = old + "/"
                # substr from the "/" keeps the remainder of the path under the new folder.
                conn.execute("UPDATE OR IGNORE obsidian_notes SET path=?||substr(path,?) WHERE substr(path,1,?)=?",
                             (record["folder"], len(prefix), len(prefix), prefix))
                conn.execute("UPDATE analysis_runs SET note_path=?||substr(note_path,?) WHERE substr(note_path,1,?)=?",
                             (record["folder"], len(prefix), len(prefix), prefix))

    def write_note(self, relative: str, note_id: str, item_id: str, content: str,
                   *, graph_kind: str = "analysis", graph_scope: str | None = None,
                   navigation: bool = False) -> None:
        """Write through the shared Vault note policy (vault_note_policy, OBS-04).

        A researcher's edit is kept in the history before the latest version is
        written. A deleted note is recreated only when it is ``navigation``.
        """
        from .vault_note_policy import write_generated_note
        if item_id:
            content = self.layout.decorate(content, item_id, graph_kind,
                graph_scope or ("detail" if relative.endswith("-分析まとめ.md") else "history"))
            self.follow_moves(item_id)
        with self.connect() as conn:
            previous = conn.execute("SELECT * FROM obsidian_notes WHERE path=?", (relative,)).fetchone()
        result = write_generated_note(
            self.vault, relative, content.encode("utf-8"),
            known_hashes={previous["sha256"]} if previous else set(),
            ever_written=previous is not None, recreate_missing=navigation,
            log_file=self.note_log,
        )
        if result.notable:
            self._note_events.append(result)
        if result.action == "missing":
            return
        with self.connect() as conn:
            conn.execute("""INSERT INTO obsidian_notes(path,note_id,item_id,sha256,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,updated_at=excluded.updated_at""",
                (relative, note_id, item_id, result.sha256, datetime.now(timezone.utc).isoformat()))

    def _record_note_events(self, run_id: str) -> None:
        """Keep what the last Vault save did to researcher-touched notes, for the app screen."""
        target = self.run_notes / f"{run_id}.json"
        events = self._note_events
        self._note_events = []
        if not events:
            target.unlink(missing_ok=True)
            return
        summary = {
            "edit_saved": [{"vault": e.vault, "path": e.path, "history": e.history}
                           for e in events if e.action == "edit_saved"],
            "missing": [{"vault": e.vault, "path": e.path} for e in events if e.action == "missing"],
            "recreated": [{"vault": e.vault, "path": e.path} for e in events if e.action == "recreated"],
        }
        write_atomic(target, json.dumps(summary, ensure_ascii=False).encode("utf-8"))

    def vault_notes(self, run_id: str) -> dict:
        try:
            data = json.loads((self.run_notes / f"{run_id}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def source_notes(self, segments: list[dict], item_id: str, title: str, app_url: str) -> dict[str, str]:
        snapshot_id = digest({"segments": segments, "item_id": item_id, "title": title})
        refs = {}
        for index in range(0, len(segments), 200):
            page = self.layout.source_dir(item_id, title, snapshot_id) + f"/part-{index // 200 + 1:04d}"
            body = frontmatter(f"source-{snapshot_id}-{index}", title, note_type="source-snapshot",
                               conversation_id=item_id, input_snapshot_id=snapshot_id)
            body += f"# {markdown(title)}\n\n保存時点の原文です。\n\n"
            for segment in segments[index:index + 200]:
                sid = str(segment["id"])
                block = "s-" + sid.encode("utf-8").hex()
                refs[sid] = f"[[{page}#^{block}|{markdown(segment.get('speaker_name') or segment.get('speaker'))}・{segment.get('start', 0)}秒]]"
                body += f"### {markdown(segment.get('speaker_name') or segment.get('speaker'))} / {segment.get('start', 0)}–{segment.get('end', 0)}秒\n\n"
                body += "\n".join("> " + markdown(line) for line in str(segment.get("text") or "").splitlines()) + f"\n\n^{block}\n\n"
                params = urlencode({"view": "analysis", "item": item_id, "segment": sid,
                                    "text_hash": hashlib.sha256(str(segment.get("text") or "").strip().encode("utf-8")).hexdigest(),
                                    "start": segment.get("start", 0), "end": segment.get("end", 0),
                                    "speaker": segment.get("speaker", "UNKNOWN")})
                body += f"[アプリで発話を確認]({app_url}/?{params})\n\n"
            self.write_note(page + ".md", f"source-{snapshot_id}-{index}", item_id, body)
        return refs

    def _publish_comparison(self, run: dict) -> None:
        """ResearchVault note for a multi-interview comparison, kept apart from every interview folder."""
        snapshot, result = self._read_package(run["id"])
        interviews = self.layout.load()["interviews"]
        members = snapshot.get("members", [])
        title = str(snapshot.get("title") or "グループインタビュー比較")
        note_id = f"comparison-{run['id']}"
        text = frontmatter(note_id, title, note_type="interview-comparison", analysis_id=run["id"],
                           conversation_ids=[member["conversation_id"] for member in members],
                           input_snapshot_id=run["snapshot_id"], created=run["created_at"],
                           review_status="unreviewed", tags=["graph/overview"])
        text += f"# {markdown(title)}\n\n{run['created_at']} に保存した比較です。各インタビューの分析とは別の実行として保存しています。\n\n"
        text += "## 比較したインタビュー\n\n"
        for member in members:
            record = interviews.get(member["conversation_id"])
            label = markdown(member.get("title"))
            text += "- " + (f"[[{record['hub'][:-3]}|{record['code']} {label}]]" if record else label)
            text += f"（revision {int(member.get('source_revision') or 0)}）\n"
        for method in result.get("methods", []):
            text += "\n## 見解\n\n" + "".join(f"- {markdown(s.get('title'))}：{markdown(s.get('text'))}\n"
                                              for s in method.get("summaries", []))
            for preview in method.get("previews", []):
                fields = preview["fields"]
                text += f"\n### {markdown(preview['dataset'])}（全{preview['total']}行・先頭10行まで）\n\n"
                text += "| " + " | ".join(markdown(f) for f in fields) + " |\n"
                text += "| " + " | ".join("---" for _ in fields) + " |\n"
                for row in preview["rows"]:
                    text += "| " + " | ".join(markdown(str(row.get(f, ""))[:160]).replace("\n", "<br>") for f in fields) + " |\n"
            text += "\n## 限界と追加確認\n\n" + "\n".join("- " + markdown(v) for v in method.get("limitations", [])) + "\n"
        text += "\n## 再現用ファイル\n\n" + "\n".join(
            f"- [{a['name']}]({run['app_url']}/api/analysis/artifacts/{a['id']})" for a in self.artifacts(run["id"])) + "\n"
        note_path = f"40-研究/インタビュー比較/comparison-{run['id']}.md"
        self.write_note(note_path, note_id, "", text)
        with self.connect() as conn:
            conn.execute("UPDATE analysis_runs SET vault_status='completed',note_path=?,error='' WHERE id=?",
                         (note_path, run["id"]))

    def _publish_research(self, run_id: str) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run or run["status"] != "completed": raise LookupError("完了した保存結果がありません。")
            try:
                if run["kind"] == "interview_comparison":
                    self._publish_comparison(run)
                    self._record_note_events(run_id)
                    return self.get(run_id)
                snapshot, result = self._read_package(run_id)
                item_id = run["item_id"]
                title = str(snapshot.get("title") or item_id)
                run_dir = self.layout.analysis_dir(item_id, title, run_id)
                originals = {s["id"]: s for s in snapshot.get("original_source", {}).get("segments", [])}
                source = [{**s, "text": originals.get(s["id"], s).get("text", "")}
                          for s in snapshot.get("segments", []) if not s.get("excluded")]
                refs = self.source_notes(source, item_id, title, run["app_url"])
                artifact_rows = self.artifacts(run_id)
                links = {a["name"]: f"[{a['name']}]({run['app_url']}/api/analysis/artifacts/{a['id']})" for a in artifact_rows}
                main = frontmatter(f"analysis-{run_id}", title + "：保存済み分析", conversation_id=item_id,
                                   analysis_id=run_id, input_snapshot_id=run["snapshot_id"],
                                   source_revision=run["source_revision"], analysis_revision=run["analysis_revision"],
                                   created=run["created_at"], review_status="unreviewed")
                main += f"# {markdown(title)}：保存済み分析\n\n{run['created_at']} の固定結果です。\n\n"
                main += "## 見解と分析手法\n\n"
                for method in result.get("methods", []):
                    method_id = method["method_id"]
                    if not re.fullmatch(r"[a-z_]+", method_id): raise ValueError("手法IDが不正です。")
                    target = f"{run_dir}/method-{method_id}"
                    main += f"- [[{target}|{method['title']}]]（{method['status']}）\n"
                    text = frontmatter(f"analysis-{run_id}-{method_id}", method["title"], analysis_id=run_id,
                                       conversation_id=item_id, method_id=method_id,
                                       method_version=method["method_version"], run_status=method["status"],
                                       review_status="unreviewed", input_snapshot_id=run["snapshot_id"])
                    text += f"# {markdown(method['title'])}\n\n状態：{markdown(method['status'])}\n\n"
                    text += f"[[{run_dir}/analysis-{run_id}|この実行の全体]]\n\n"
                    active_refs = refs
                    evidence = method.get("details", {}).get("evidence")
                    if evidence:
                        active_refs = self.source_notes(list(evidence.values()), item_id, title + "：AI生成時点", run["app_url"])
                    text += "## 見解・観察\n\n"
                    for summary in method.get("summaries", []):
                        text += f"### {markdown(summary.get('title'))}\n\n{markdown(summary.get('text'))}\n\n"
                    for finding in method.get("findings", []):
                        if not finding.get("segment_ids") or any(s not in active_refs for s in finding["segment_ids"]):
                            raise StoreConflict("見解の根拠を保存済み原文に対応付けられません。")
                        text += f"### {markdown(finding.get('title'))}\n\n{markdown(finding.get('text'))}\n\n"
                        text += "根拠：" + " / ".join(active_refs[s] for s in finding.get("segment_ids", []) if s in active_refs) + "\n\n"
                    for section in method.get("details", {}).get("sections", []):
                        text += f"### {markdown(section.get('title'))}\n\n"
                        for bullet in section.get("bullet_evidence", []):
                            if not bullet.get("segment_ids") or any(s not in active_refs for s in bullet["segment_ids"]):
                                raise StoreConflict("議題の根拠を保存済み原文に対応付けられません。")
                            text += f"- {markdown(bullet['text'])}\n"
                            text += "  根拠：" + " / ".join(active_refs[s] for s in bullet["segment_ids"]) + "\n"
                        if not section.get("bullet_evidence"):
                            text += "旧形式の議題です。発話IDによる根拠は未登録です。\n\n"
                            text += "\n".join("- " + markdown(b) for b in section.get("bullets", [])) + "\n"
                    if method_id == "ai_finishing":
                        details = method["details"]
                        text += "工程の結果：" + markdown(json.dumps(details.get("stages", {}), ensure_ascii=False)) + "\n\n"
                        original_refs = self.source_notes(details.get("original_segments", []), item_id, title + "：AI仕上げ前", run["app_url"])
                        text += f"校正・話者変更：{len(details.get('changes', []))}発話\n\n"
                        for change in details.get("changes", [])[:100]:
                            sid = change["segment_id"]
                            text += f"- 原文：{original_refs.get(sid, markdown(sid))} → 保存後：{refs.get(sid, markdown(sid))}\n"
                    if method_id == "kwic":
                        details = method["details"]
                        text += f"検索語：{markdown(details.get('query'))} / {details.get('total', 0)}件\n\n"
                        for hit in details.get("hits", [])[:50]:
                            text += f"- {markdown(hit['left'] + hit['match'] + hit['right'])}：{refs.get(hit['segment_id'], '')}\n"
                    for preview in method.get("previews", []):
                        text += f"\n### {markdown(preview['dataset'])}（全{preview['total']}行・先頭10行まで）\n\n"
                        fields = preview["fields"]
                        text += "| " + " | ".join(markdown(f) for f in fields) + " |\n"
                        text += "| " + " | ".join("---" for _ in fields) + " |\n"
                        for row in preview["rows"]:
                            text += "| " + " | ".join(markdown(str(row.get(f, ""))[:160]).replace("\n", "<br>").replace("\r", "") for f in fields) + " |\n"
                    text += "\n## 条件と全件データ\n\n"
                    text += f"分析単位：{markdown(method.get('analysis_unit'))}\n\n"
                    text += "解析器：" + markdown(json.dumps(method.get("engine", {}), ensure_ascii=False)) + "\n\n"
                    text += links["parameters.json"] + " / " + links["result.json"] + "\n\n"
                    for dataset in method.get("datasets", []):
                        for extension, purpose in (("json", "型付き全件データ"), ("csv", "表計算・共有用")):
                            name = f"tables/{dataset}.{extension}"
                            if name in links: text += f"- {purpose}：{links[name]}\n"
                    text += "\n## 限界と追加確認\n\n" + "\n".join("- " + markdown(v) for v in method.get("limitations", [])) + "\n"
                    self.write_note(target + ".md", f"analysis-{run_id}-{method_id}", item_id, text,
                                    graph_kind="analysis_result", graph_scope="detail")
                tree_links = self.publish_graph_tree(run_id, item_id, title, run_dir, result.get("methods", []))
                if tree_links:
                    main += "\n## 可視化用の分析ツリー\n\n"
                    main += "アウトライン、分析種別、結果の順にグラフでたどれます。\n\n"
                    main += "\n".join("- " + value for value in tree_links) + "\n"
                main += "\n## 再現用ファイル\n\n" + "\n".join("- " + value for value in links.values()) + "\n"
                main += "\n研究者のメモはインタビューの概要から研究メモを開いて記録してください。\n"
                note_path = f"{run_dir}/analysis-{run_id}.md"
                self.write_note(note_path, f"analysis-{run_id}", item_id, main,
                                graph_kind="analysis", graph_scope="detail")
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET vault_status='completed',note_path=?,error='' WHERE id=?", (note_path, run_id))
                # Generated Vaults were already attempted above; do not recursively
                # start a second publication while updating this Research index.
                self._publish_index(item_id)
                self._record_note_events(run_id)
            except Exception as exc:
                message = str(exc) if isinstance(exc, StoreConflict) else "Vaultへの保存を完了できませんでした。結果ファイルは保持しています。"
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET vault_status='conflict',error=? WHERE id=?", (message, run_id))
            return self.get(run_id)

    def publish_graph_tree(self, run_id: str, item_id: str, title: str, run_dir: str,
                           methods: list[dict]) -> list[str]:
        """Create a compact, navigable graph tree for one immutable analysis run.

        The detailed method notes remain the audit trail.  These small notes are
        deliberately separate graph nodes so an Obsidian graph can show
        ``analysis group -> method -> result`` without rendering every CSV row.
        Outline sections are nodes too, because they are meaningful units a
        researcher can connect to themes and memos.
        """
        groups = {method_id: (group_id, group_title, description)
                  for group_id, group_title, description, method_ids in METHOD_GROUPS
                  for method_id in method_ids}
        grouped: dict[str, list[dict]] = {}
        for method in methods:
            method_id = str(method.get("method_id") or "")
            if method_id in groups:
                grouped.setdefault(groups[method_id][0], []).append(method)

        links: list[str] = []
        for group_id, group_title, description, _ in METHOD_GROUPS:
            selected = grouped.get(group_id, [])
            if not selected:
                continue
            group_path = graph_node_path(run_dir, f"分類-{group_id}", group_title, self.vault)
            method_paths = []
            for method in selected:
                method_id = str(method["method_id"])
                method_path = graph_node_path(run_dir, f"手法-{method_id}", str(method["title"]), self.vault)
                method_paths.append(method_path)
                result_path = f"{run_dir}/method-{method_id}.md"
                result_nodes = self._graph_result_nodes(run_dir, method)
                body = f"# 分析種別：{markdown(method['title'])}\n\n"
                body += f"[[{group_path[:-3]}|分類：{markdown(group_title)}]]\n\n"
                body += f"[[{result_path[:-3]}|この手法の詳細結果・根拠・条件]]\n\n"
                body += "## 結果\n\n"
                body += "\n".join("- [[" + path[:-3] + "]]" for path, _, _ in result_nodes) + "\n"
                if not result_nodes:
                    body += "- 保存時点では表示可能な結果がありません。\n"
                self.write_note(method_path, f"analysis-{run_id}-graph-method-{method_id}", item_id,
                                frontmatter(f"analysis-{run_id}-graph-method-{method_id}", method["title"],
                                            analysis_id=run_id, conversation_id=item_id,
                                            method_id=method_id, node_role="analysis_type") + body,
                                graph_kind="analysis_type", graph_scope="detail")
                for path, node_title, node_body in result_nodes:
                    kind = "outline" if method_id == "outline" else "analysis_result"
                    node_id = hashlib.sha256(path.encode()).hexdigest()[:16]
                    body = f"# {markdown(node_title)}\n\n[[{method_path[:-3]}|分析種別：{markdown(method['title'])}]]\n\n"
                    body += f"[[{result_path[:-3]}|詳細な結果・根拠・条件を開く]]\n\n" + node_body
                    self.write_note(path, f"analysis-{run_id}-graph-result-{node_id}", item_id,
                                    frontmatter(f"analysis-{run_id}-graph-result-{node_id}", node_title,
                                                analysis_id=run_id, conversation_id=item_id,
                                                method_id=method_id, node_role="outline_section" if kind == "outline" else "analysis_result") + body,
                                    graph_kind=kind, graph_scope="detail")
            body = f"# 分析分類：{markdown(group_title)}\n\n{markdown(description)}\n\n"
            body += "## 分析種別\n\n" + "\n".join("- [[" + path[:-3] + "]]" for path in method_paths) + "\n"
            self.write_note(group_path, f"analysis-{run_id}-graph-group-{group_id}", item_id,
                            frontmatter(f"analysis-{run_id}-graph-group-{group_id}", group_title,
                                        analysis_id=run_id, conversation_id=item_id,
                                        group_id=group_id, node_role="analysis_group") + body,
                            graph_kind="analysis_type", graph_scope="detail")
            links.append(f"[[{group_path[:-3]}|{markdown(group_title)}]]")
        return links

    def _graph_result_nodes(self, run_dir: str, method: dict) -> list[tuple[str, str, str]]:
        """Return bounded, human-readable leaves for a method's graph branch."""
        method_id = str(method["method_id"])
        nodes: list[tuple[str, str, str]] = []
        for index, section in enumerate(method.get("details", {}).get("sections", []), 1):
            title = str(section.get("title") or f"アウトライン {index}")
            body = "## アウトラインの内容\n\n"
            bullets = section.get("bullet_evidence") or []
            if bullets:
                body += "\n".join("- " + markdown(item.get("text")) for item in bullets) + "\n"
            else:
                body += "\n".join("- " + markdown(item) for item in section.get("bullets", [])) + "\n"
            nodes.append((graph_node_path(run_dir, f"アウトライン-{index:02d}", title, self.vault), "アウトライン：" + title, body))
        for index, finding in enumerate(method.get("findings", [])[:12], 1):
            title = str(finding.get("title") or f"見解 {index}")
            body = "## 結果の要約\n\n" + markdown(finding.get("text")) + "\n"
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-見解-{index:02d}", title, self.vault), "結果：" + title, body))
        for index, preview in enumerate(method.get("previews", [])[:12], 1):
            dataset = str(preview.get("dataset") or f"データ {index}")
            body = f"## {markdown(dataset)}\n\n全{preview.get('total', 0)}行のうち先頭{len(preview.get('rows', []))}行を表示します。\n\n"
            fields = preview.get("fields", [])[:4]
            for row in preview.get("rows", [])[:5]:
                values = " / ".join(markdown(str(row.get(field, ""))[:120]) for field in fields)
                body += "- " + values + "\n"
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-表-{index:02d}", dataset, self.vault), "結果：" + dataset, body))
        if not nodes:
            state = markdown(method.get("status") or "不明")
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-状態", "実行状態", self.vault), "結果：実行状態", "## 保存時点の状態\n\n" + state + "\n"))
        return nodes

    def publish_index(self, item_id: str) -> None:
        with STORE_LOCK:
            self.refresh_vaults(item_id)
            self._publish_index(item_id)

    def _publish_index(self, item_id: str) -> None:
        from .obsidian_layout import ANALYSIS_INDEX, link, method_table
        self.follow_moves(item_id)
        with self.connect() as conn:
            runs = [dict(r) for r in conn.execute("""SELECT * FROM analysis_runs
                WHERE item_id=? AND status='completed' AND note_path!=''
                ORDER BY created_at DESC,id DESC""", (item_id,)).fetchall()]
        if not runs: return
        snapshot, latest_result = self._read_package(runs[0]["id"])
        item_key = uuid.uuid5(uuid.NAMESPACE_URL, snapshot["library_id"] + item_id).hex
        title = str(snapshot.get("title") or item_id)
        note_id = f"conversation-{item_key}"
        text = frontmatter(note_id, title, note_type="conversation", conversation_id=item_id,
                           needs_update=bool(runs[0]["stale"]))
        text += f"# 分析まとめ\n\n[[{runs[0]['note_path'][:-3]}|最新の保存済み分析を開く]]\n\n"
        text += link(ANALYSIS_INDEX, "全インタビューの分析結果・手法別一覧") + "\n\n"
        # A later KWIC-only save must not hide text or emotion analyses.
        by_method = {}
        for run in runs:
            package = latest_result if run["id"] == runs[0]["id"] else self._read_package(run["id"])[1]
            run_dir = self.layout.analysis_dir(item_id, title, run["id"])
            for method in package.get("methods", []):
                method_id = method["method_id"]
                if not re.fullmatch(r"[a-z_]+", method_id): raise ValueError("手法IDが不正です。")
                path = f"{run_dir}/method-{method_id}.md"
                if method_id in by_method or not safe_path(self.vault, path).is_file(): continue
                by_method[method_id] = {"method_id": method_id, "title": method["title"],
                    "path": path, "status": method["status"], "stale": bool(run["stale"]),
                    "created_at": run["created_at"]}
        text += "## 手法別の分析結果\n\n各手法の最新の保存記録です。実行時点が異なる場合があるため、保存日時と状態を合わせて確認してください。\n\n"
        for _, group_title, description, method_ids in METHOD_GROUPS:
            selected = [by_method[key] for key in method_ids if key in by_method]
            text += "### " + group_title + "\n\n" + description + "\n\n"
            text += method_table(selected) + "\n" if selected else "この分類の保存記録はまだありません。\n\n"
        findings = [(method, finding) for method in latest_result.get("methods", [])
                    for finding in method.get("findings", [])]
        if findings:
            text += "## 最新の見解\n\n"
            run_dir = self.layout.analysis_dir(item_id, title, runs[0]["id"])
            for method, finding in findings[:5]:
                text += f"### {markdown(finding.get('title') or method['title'])}\n\n{markdown(finding.get('text'))}\n\n"
                text += f"[[{run_dir}/method-{method['method_id']}|根拠と分析条件]]\n\n"
        text += "## 保存履歴\n\n"
        for row in runs:
            status = "更新が必要" if row["stale"] else "保存時点の結果"
            text += f"- [[{row['note_path'][:-3]}|{row['created_at']} / {row['kind']}]]：{status}\n"
        summary = self.layout.note_path(item_id, title, "分析まとめ")
        self.write_note(summary, note_id, item_id, text, navigation=True)
        self.layout.update(item_id, title, {"analysis": summary}, analysis_methods=list(by_method.values()))
        # A dedicated generated index never overwrites the user's Home or guides.
        with self.connect() as conn:
            notes = conn.execute("SELECT path,note_id FROM obsidian_notes WHERE note_id LIKE 'conversation-%' ORDER BY path").fetchall()
        index = frontmatter("gurumoji-saved-analyses", "アプリから保存した分析", note_type="analysis-index")
        index += "# アプリから保存した分析\n\n" + "\n".join(f"- [[{n['path'][:-3]}]]" for n in notes) + "\n"
        self.write_note("90-運用/Gurumoji-SavedAnalyses.md", "gurumoji-saved-analyses", "", index, navigation=True)
