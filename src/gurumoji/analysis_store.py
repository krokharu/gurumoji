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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from .analysis_method_registry import REGISTRY_VERSION, METHOD_GROUPS

LOGGER = logging.getLogger(__name__)
STORE_LOCK = threading.RLock()
STORE_VERSION = 1


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


def write_atomic(path: Path, data: bytes, *, create_only: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if create_only:
            # Publish the complete file without replacing a concurrently created note.
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def markdown(value) -> str:
    text = html.escape(str(value or ""), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|^~$])", r"\\\1", text)


def graph_node_path(run_dir: str, prefix: str, label: str) -> str:
    """Make readable, filesystem-safe names for nodes shown in Obsidian Graph."""
    clean = re.sub(r'[\\/:*?"<>|#^\[\]%\x00-\x1f]', "_", str(label)).strip(" ._")
    clean = re.sub(r"\s+", " ", clean)[:72] or "結果"
    return f"{run_dir}/graph/{prefix}-{clean}.md"


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


def frontmatter(note_id: str, title: str, **properties) -> str:
    data = {"note_id": note_id, "note_type": "analysis-result", "title": title,
            "schema_version": STORE_VERSION, "managed_by": "gurumoji", **properties}
    return "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in data.items()) + "\n---\n\n"


class AnalysisStore:
    def __init__(self, database_file: Path, connect):
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

    def publish_vaults(self, run_id: str) -> dict[str, str]:
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
                    with safe_path(self.root, artifact["path"]).open(encoding="utf-8-sig", newline="") as handle:
                        fields[name[len("tables/"):-len(".csv")]] = next(csv.reader(handle), [])
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

    def publication_outcomes(self, run_id: str) -> dict[str, dict[str, str]]:
        """Return per generated-Vault publication state for one fixed package."""
        run = self.get(run_id)
        if not run:
            raise LookupError("保存結果がありません。")
        if run_id in self._last_publication_outcomes:
            return copy.deepcopy(self._last_publication_outcomes[run_id])
        try:
            data = self.vaults.load()
        except (OSError, ValueError) as exc:
            return {kind: {"status": "unknown", "error": str(exc)}
                    for kind in ("input", "orchestrator", "visualization")}
        snapshot_note = "input-snapshot-" + str(run["snapshot_id"])
        run_note = "orchestrator-run-" + run_id
        visual_prefix = "visual-" + run_id + "-"

        def outcome(note_ids: list[str]) -> dict[str, str]:
            if not note_ids:
                return {"status": "unknown", "error": "公開対象ノートを確認できません。"}
            entries = [data.get("notes", {}).get(note_id) for note_id in note_ids]
            if any(entry is None for entry in entries):
                return {"status": "unknown", "error": "公開対象ノートがありません。"}
            sync = {str(entry.get("sync") or "unknown") for entry in entries if entry}
            if sync <= {"current"}:
                return {"status": "published", "error": ""}
            if "conflict" in sync:
                return {"status": "conflict", "error": "利用者の編集を保持したため競合しています。"}
            if "missing" in sync:
                return {"status": "failed", "error": "管理対象ノートが移動または削除されています。"}
            return {"status": "unknown", "error": "公開状態を確認できません。"}

        visual_ids = [note_id for note_id in data.get("notes", {}) if note_id.startswith(visual_prefix)]
        # A run with no tabular visual still has a valid Visualization publication:
        # its generated index/home are current and there was nothing to write.
        visual = outcome(visual_ids) if visual_ids else {"status": "published", "error": ""}
        return {
            "input": outcome([snapshot_note]),
            "orchestrator": outcome([run_note]),
            "visualization": visual,
        }

    def refresh_vaults(self, item_id: str) -> None:
        """Republish only runs whose stale state differs from their Orchestrator note.

        Comparisons that include this conversation are checked as well.
        """
        with self.connect() as conn:
            rows = conn.execute("""SELECT id,stale FROM analysis_runs WHERE status='completed' AND
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
        path = safe_path(self.root, row["path"])
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise StoreConflict("保存済みファイルが外部で変更されています。")
        return dict(row), content

    def public(self, row: dict, *, local: bool = False) -> dict:
        result = {key: row[key] for key in ("id", "item_id", "kind", "source_revision", "analysis_revision",
                  "created_at", "status", "vault_status", "stale", "error", "provider", "model")}
        result["artifacts"] = [{key: a[key] for key in ("id", "name", "media_type", "rows", "bytes")}
                               for a in self.artifacts(row["id"])]
        for artifact in result["artifacts"]:
            artifact["url"] = f"/api/analysis/artifacts/{artifact['id']}"
        result["obsidian_uri"] = ("obsidian://open?" + urlencode({"path": str(self.vault / row["note_path"])})
                                    if local and row["note_path"] and row["vault_status"] == "completed" else "")
        result["vault_notes"] = self.vault_notes(row["id"])
        return result

    def save(self, *, item_id: str, kind: str, snapshot: dict, result: dict, datasets: dict,
             request_id: str, input_fingerprint: str, source_revision: int, analysis_revision: int,
             app_url: str = "http://127.0.0.1:7860", provider: str = "", model: str = "",
             member_ids: list[str] | None = None, check_cancelled=lambda: None,
             publish: bool = True) -> dict:
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
                       "member_ids": list(member_ids or []), "publish": publish}
            with self.connect() as conn:
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
                else:
                    conn.execute("INSERT INTO analysis_pending_packages(run_id,payload_json) VALUES (?,?)", (run_id, canonical(pending).decode('utf-8')))
            try:
                files = {"input.json": (canonical(snapshot), "application/json", None),
                         "parameters.json": (canonical(result.get("parameters", {})), "application/json", None),
                         "result.json": (canonical(result), "application/json", None)}
                for name, (fields, rows) in datasets.items():
                    if not re.fullmatch(r"[a-z_]+", name): raise ValueError("表の名前が正しくありません。")
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
            with self.connect() as conn:
                row = conn.execute("SELECT payload_json FROM analysis_pending_packages WHERE run_id=?", (run_id,)).fetchone()
            if not row: raise StoreConflict("再保存用の入力がありません。分析画面から保存してください。")
            return self.save(**json.loads(row[0]))

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

    def publish(self, run_id: str) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run or run["status"] != "completed": raise LookupError("完了した保存結果がありません。")
            # Independent of ResearchVault conflicts: the four Vaults use their own hash catalog.
            self._note_events = []
            self.publish_vaults(run_id)
            try:
                if run["kind"] == "interview_comparison":
                    self._publish_comparison(run)
                    self._record_note_events(run_id)
                    return self.get(run_id)
                snapshot, result = self._read_package(run_id)
                item_id = run["item_id"]
                library_id = snapshot["library_id"]
                item_key = uuid.uuid5(uuid.NAMESPACE_URL, library_id + item_id).hex
                title = str(snapshot.get("title") or item_id)
                run_dir = self.layout.analysis_dir(item_id, title, run_id)
                originals = {s["id"]: s for s in snapshot.get("original_source", {}).get("segments", [])}
                source = [{**s, "text": originals.get(s["id"], s).get("text", "")}
                          for s in snapshot.get("segments", []) if not s.get("excluded")]
                refs = self.source_notes(source, item_id, title, run["app_url"])
                artifact_rows = self.artifacts(run_id)
                links = {a["name"]: f"[{a['name']}]({run['app_url']}/api/analysis/artifacts/{a['id']})" for a in artifact_rows}
                # No file:/// URI: it names the PC user and breaks when the Vault moves (OBS-12).
                local_links = {a["name"]: f"保存先 `analysis_store/{a['path']}`" for a in artifact_rows}
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
                        name = f"tables/{dataset}.csv"
                        if name in links: text += f"- {links[name]} / {local_links[name]}\n"
                    text += "\n## 限界と追加確認\n\n" + "\n".join("- " + markdown(v) for v in method.get("limitations", [])) + "\n"
                    self.write_note(target + ".md", f"analysis-{run_id}-{method_id}", item_id, text,
                                    graph_kind="analysis_result", graph_scope="detail")
                tree_links = self.publish_graph_tree(run_id, item_id, title, run_dir, result.get("methods", []))
                if tree_links:
                    main += "\n## 可視化用の分析ツリー\n\n"
                    main += "アウトライン、分析種別、結果の順にグラフでたどれます。\n\n"
                    main += "\n".join("- " + value for value in tree_links) + "\n"
                main += "\n## 再現用ファイル\n\n" + "\n".join("- " + value + " / " + local_links[name] for name, value in links.items()) + "\n"
                main += "\n研究者のメモはインタビューの概要から研究メモを開いて記録してください。\n"
                note_path = f"{run_dir}/analysis-{run_id}.md"
                self.write_note(note_path, f"analysis-{run_id}", item_id, main,
                                graph_kind="analysis", graph_scope="detail")
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET vault_status='completed',note_path=?,error='' WHERE id=?", (note_path, run_id))
                self.publish_index(item_id)
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
            group_path = graph_node_path(run_dir, f"分類-{group_id}", group_title)
            method_paths = []
            for method in selected:
                method_id = str(method["method_id"])
                method_path = graph_node_path(run_dir, f"手法-{method_id}", str(method["title"]))
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

    @staticmethod
    def _graph_result_nodes(run_dir: str, method: dict) -> list[tuple[str, str, str]]:
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
            nodes.append((graph_node_path(run_dir, f"アウトライン-{index:02d}", title), "アウトライン：" + title, body))
        for index, finding in enumerate(method.get("findings", [])[:12], 1):
            title = str(finding.get("title") or f"見解 {index}")
            body = "## 結果の要約\n\n" + markdown(finding.get("text")) + "\n"
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-見解-{index:02d}", title), "結果：" + title, body))
        for index, preview in enumerate(method.get("previews", [])[:12], 1):
            dataset = str(preview.get("dataset") or f"データ {index}")
            body = f"## {markdown(dataset)}\n\n全{preview.get('total', 0)}行のうち先頭{len(preview.get('rows', []))}行を表示します。\n\n"
            fields = preview.get("fields", [])[:4]
            for row in preview.get("rows", [])[:5]:
                values = " / ".join(markdown(str(row.get(field, ""))[:120]) for field in fields)
                body += "- " + values + "\n"
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-表-{index:02d}", dataset), "結果：" + dataset, body))
        if not nodes:
            state = markdown(method.get("status") or "不明")
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-状態", "実行状態"), "結果：実行状態", "## 保存時点の状態\n\n" + state + "\n"))
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
