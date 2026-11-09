"""Opt-in, read-only ObusSQL preview over explicitly selected managed notes.

SQLite and VaultRegistry remain authoritative. The experimental obsipg package
is imported only after opt-in; its MemoryBackend lives for one preview request.
No source registration, persistent index, synchronization or model call occurs.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from hashlib import sha256
from importlib import import_module, metadata
import json
from pathlib import Path
import re
import sqlite3
import sys
from types import SimpleNamespace

import yaml

from ..env_settings import env_enabled
from .durable_files import path_has_reparse_ancestor

ENV_ENABLED = "MOJIOKOSI_OBUSSQL_ENABLED"
REFERENCE_COMMIT = "07128acfe13c1162552f7928b5ab0e7c954fac1b"
PACKAGE_VERSION = "0.0.1.dev0"
MAF_REFERENCE_COMMIT = "07128acfe13c1162552f7928b5ab0e7c954fac1b"
MAF_PACKAGE_VERSION = "0.1.0.dev0"
MAF_CORE_VERSION = "1.22.0"
MAF_PROFILE = "obus.maf.pipeline.v1"
MAX_NOTES = 16
MAX_LIST_NOTES = 100
MAX_NOTE_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 16 * 1024
GENERATED_VAULTS = ("input", "visualization", "orchestrator")


class ObusSQLError(ValueError):
    """Public errors carry fixed messages, never third-party exception text."""

    def __init__(self, code: str, message: str, http_status: int = 409):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _unavailable() -> ObusSQLError:
    return ObusSQLError("source_unavailable", "指定した管理ノートを読み取れません。")


def _changed() -> ObusSQLError:
    return ObusSQLError("source_changed", "ノートまたは台帳の版が変わりました。対象を確認し直してください。")


def _load_api():
    if not env_enabled(ENV_ENABLED):
        raise ObusSQLError("disabled", "ObusSQL接続は無効です。", 503)
    if sys.version_info < (3, 12):
        raise ObusSQLError("python_unsupported", "ObusSQLの試用にはPython 3.12以上が必要です。", 503)
    try:
        version = metadata.version("obsipg")
    except metadata.PackageNotFoundError:
        raise ObusSQLError("not_installed", "任意依存のobsipgが導入されていません。", 503) from None
    if version != PACKAGE_VERSION:
        raise ObusSQLError("incompatible", "obsipgの版が接続基盤の確認対象と異なります。", 503)
    try:
        native = import_module("obsipg")
        contracts = import_module("obsipg.contracts")
        memory = import_module("obsipg.memory")
        backend = import_module("obsipg.backend")
        retrieval = import_module("obsipg.retrieval")
        measurement = import_module("obsipg.measurement")
        api = SimpleNamespace(
            Scope=contracts.Scope, Source=contracts.Source, Resource=contracts.Resource,
            ReadContext=contracts.ReadContext, MemoryBackend=memory.MemoryBackend,
            ReadLimits=backend.ReadLimits, PayloadBudget=measurement.PayloadBudget,
            retrieve_context=retrieval.retrieve_context,
            SourceVersionChanged=native.SourceVersionChanged,
        )
        if (native.__version__ != PACKAGE_VERSION or not all(callable(value) for value in vars(api).values())
                or not isinstance(api.SourceVersionChanged, type) or not issubclass(api.SourceVersionChanged, Exception)):
            raise ValueError("unsupported API")
        return api
    except Exception:
        # Optional native wheels can fail for ABI/DLL reasons. Keep the app usable
        # and do not return paths or arbitrary exception content to a browser.
        raise ObusSQLError("import_failed", "obsipgの読取APIを読み込めません。導入版と実行環境を確認してください。", 503) from None


def maf_status() -> dict:
    """上流mainの独立したMAF拡張を診断し、ワークフローは実行しない。"""
    result = {
        "package": "obussql-maf", "expected_version": MAF_PACKAGE_VERSION,
        "framework": "agent-framework-core", "expected_framework_version": MAF_CORE_VERSION,
        "reference_commit": MAF_REFERENCE_COMMIT, "profile_id": MAF_PROFILE,
        "package_available": False, "execution_ready": False,
    }
    if not env_enabled(ENV_ENABLED):
        return {**result, "status": "disabled", "message": "MAF拡張の接続診断は無効です。"}
    if sys.version_info[:2] != (3, 12):
        return {**result, "status": "python_unsupported", "message": "このMAF拡張の対象はPython 3.12です。"}
    try:
        if (metadata.version("obussql-maf") != MAF_PACKAGE_VERSION
                or metadata.version("agent-framework-core") != MAF_CORE_VERSION):
            return {**result, "status": "incompatible", "message": "MAF拡張またはフレームワークの版が確認対象と異なります。"}
        api = import_module("obussql_maf")
        if api.PRODUCTION_PROFILE != MAF_PROFILE or api.TESTED_CORE_VERSION != MAF_CORE_VERSION:
            return {**result, "status": "incompatible", "message": "MAF拡張のプロファイルが確認対象と異なります。"}
        runtime = api.create_runtime(api.RuntimeConfig(profile_id=MAF_PROFILE, enabled=True))
        readiness = runtime.readiness()
        if readiness.status != "NOT_READY" or readiness.code is not api.ErrorCode.HOST_BINDING_UNAVAILABLE:
            # A changed upstream contract cannot silently enable Gurumoji work.
            return {**result, "status": "incompatible", "message": "MAF拡張の実行契約を再確認してください。"}
    except metadata.PackageNotFoundError:
        return {**result, "status": "not_installed", "message": "任意依存のMAF拡張またはフレームワークが導入されていません。"}
    except Exception:
        return {**result, "status": "import_failed", "message": "MAF拡張の接続状態を確認できません。"}
    return {**result, "package_available": True, "status": "host_binding_unavailable",
            "message": "MAF拡張を確認しました。グルモジの実行接続は未構成です。"}


def status() -> dict:
    from .maf_dev_bridge import status as dev_status
    result = {
        "enabled": env_enabled(ENV_ENABLED), "stage": "read_only_preview",
        "package": "obsipg", "expected_version": PACKAGE_VERSION,
        "reference_commit": REFERENCE_COMMIT,
        "maf": maf_status(),
        "dev_bridge": dev_status(),
        "limits": {"notes": MAX_NOTES, "note_bytes": MAX_NOTE_BYTES,
                   "source_bytes": MAX_SOURCE_BYTES, "payload_bytes": MAX_PAYLOAD_BYTES},
    }
    try:
        _load_api()
    except ObusSQLError as exc:
        return {**result, "available": False, "status": exc.code, "message": str(exc)}
    return {**result, "available": True, "status": "available_for_preview",
            "message": "明示した管理ノートの読取プレビューを試用できます。本接続の検証は別途必要です。"}


@dataclass(frozen=True)
class NoteSelection:
    note_id: str
    sha256: str

    def __post_init__(self):
        if (not isinstance(self.note_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", self.note_id)
                or not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)):
            raise ObusSQLError("invalid_request", "note_idと64桁のsha256を指定してください。", 400)


def _request(payload) -> tuple[tuple[NoteSelection, ...], str]:
    if not isinstance(payload, dict) or set(payload) != {"notes", "query"}:
        raise ObusSQLError("invalid_request", "notesとqueryを指定してください。", 400)
    notes, query = payload["notes"], payload["query"]
    if not isinstance(notes, list) or not 1 <= len(notes) <= MAX_NOTES:
        raise ObusSQLError("invalid_request", f"ノートは1〜{MAX_NOTES}件を指定してください。", 400)
    if not isinstance(query, str) or not query.strip() or len(query) > 512:
        raise ObusSQLError("invalid_request", "検索語は1〜512文字で指定してください。", 400)
    if any(not isinstance(note, dict) or set(note) != {"note_id", "sha256"} for note in notes):
        raise ObusSQLError("invalid_request", "各ノートにはnote_idとsha256だけを指定してください。", 400)
    selections = tuple(NoteSelection(**note) for note in notes)
    if len({note.note_id for note in selections}) != len(selections):
        raise ObusSQLError("invalid_request", "note_idが重複しています。", 400)
    return selections, query


@dataclass(frozen=True)
class NoteSnapshot:
    library_id: str
    selection: NoteSelection
    vault: str
    revision: int | str | None
    source_hash: str
    raw: bytes = field(repr=False)

    def provenance(self) -> dict:
        return {"app_id": "gurumoji", "project_id": self.library_id,
                "source_id": "vault:" + self.vault, "resource_id": self.selection.note_id,
                "source_revision": self.selection.sha256,
                "revision": self.revision, "source_hash": self.source_hash}


class ManagedNoteSource:
    """A bounded connector to VaultRegistry; never discovers arbitrary files."""

    def __init__(self, database_file: Path, registry):
        self.database_file = Path(database_file)
        self.registry = registry
        if self.database_file.parent.resolve() != registry.data.resolve():
            raise _unavailable()

    def _library_id(self) -> str:
        if path_has_reparse_ancestor(self.database_file):
            raise _unavailable()
        # mode=ro also prevents creating a new library when configuration is wrong.
        with closing(sqlite3.connect(self.database_file.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
            row = db.execute("SELECT value FROM application_metadata WHERE key='library_id'").fetchone()
        if row is None or not isinstance(row[0], str) or not re.fullmatch(r"[0-9a-f]{32}", row[0]):
            raise _unavailable()
        return row[0]

    def list_notes(self, offset: int = 0) -> dict:
        """Return bounded catalog entries; actual bytes are checked on preview."""
        from ..vault_registry import VAULT_LOCK

        if type(offset) is not int or not 0 <= offset <= 1000000:
            raise ObusSQLError("invalid_request", "一覧の位置が不正です。", 400)
        try:
            with VAULT_LOCK:
                self._library_id()
                if path_has_reparse_ancestor(self.registry.catalog_file):
                    raise _unavailable()
                catalog = self.registry.load()
                entries = catalog["notes"]
                if not isinstance(entries, dict):
                    raise _unavailable()
                aliases = {}
                for entry in entries.values():
                    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                        key = (entry.get("vault"), entry["path"].casefold())
                        aliases[key] = aliases.get(key, 0) + 1
                notes = []
                for note_id, entry in entries.items():
                    if not isinstance(entry, dict) or entry.get("vault") not in GENERATED_VAULTS:
                        continue
                    if entry.get("status") != "current" or entry.get("sync") != "current" or entry.get("pending"):
                        continue
                    path = entry.get("path")
                    title = entry.get("title", "")
                    if (not isinstance(path, str) or not path.endswith(".md")
                            or any(part.startswith(".") or part == "99-Archive" for part in path.split("/"))
                            or aliases.get((entry["vault"], path.casefold())) != 1
                            or not isinstance(title, str)):
                        continue
                    try:
                        selection = NoteSelection(note_id, entry.get("sha256"))
                    except ObusSQLError:
                        continue
                    notes.append({"note_id": selection.note_id, "sha256": selection.sha256,
                                  "vault": entry["vault"], "title": title[:200]})
                notes.sort(key=lambda note: (note["vault"], note["title"].casefold(), note["note_id"]))
                page = notes[offset:offset + MAX_LIST_NOTES]
                next_offset = offset + len(page) if offset + len(page) < len(notes) else None
                return {"notes": page, "next_offset": next_offset, "limit": MAX_LIST_NOTES}
        except ObusSQLError:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error, yaml.YAMLError):
            raise _unavailable() from None

    def capture(self, selections: tuple[NoteSelection, ...]) -> tuple[NoteSnapshot, ...]:
        from ..analysis_store import safe_path
        from ..obsidian_layout import unpack
        from ..vault_registry import VAULT_LOCK

        if (not isinstance(selections, tuple) or not 1 <= len(selections) <= MAX_NOTES
                or any(type(note) is not NoteSelection for note in selections)
                or len({note.note_id for note in selections}) != len(selections)):
            raise _unavailable()
        try:
            with VAULT_LOCK:
                library_id = self._library_id()
                if path_has_reparse_ancestor(self.registry.catalog_file):
                    raise _unavailable()
                catalog = self.registry.load()
                roots = {kind: self.registry.root(kind, catalog) for kind in GENERATED_VAULTS}
                if (len({root.resolve() for root in roots.values()}) != len(roots)
                        or any(root.name.casefold() in {"researchvault", "personavault"} for root in roots.values())):
                    raise _unavailable()
                prepared = []
                paths = set()
                # Check the entire selection before opening any selected note.
                for selection in selections:
                    entry = catalog["notes"].get(selection.note_id)
                    if not isinstance(entry, dict) or entry.get("vault") not in GENERATED_VAULTS:
                        raise _unavailable()
                    if (entry.get("sync") != "current" or entry.get("pending")
                            or entry.get("status") != "current" or entry.get("sha256") != selection.sha256):
                        raise _changed()
                    relative = entry["path"]
                    if (not isinstance(relative, str) or not relative.endswith(".md")
                            or any(part.startswith(".") or part == "99-Archive" for part in relative.split("/"))):
                        raise _unavailable()
                    root = roots[entry["vault"]]
                    path = safe_path(root, relative)
                    if path_has_reparse_ancestor(path) or not path.is_file():
                        raise _unavailable()
                    resolved = path.resolve()
                    if resolved in paths:
                        raise _unavailable()
                    paths.add(resolved)
                    # Ambiguous catalog aliases must not read the same note as
                    # another identity, even when only one alias is selected.
                    if sum(other.get("vault") == entry["vault"] and Path(other.get("path", "")) == Path(relative)
                           for other in catalog["notes"].values()) != 1:
                        raise _unavailable()
                    prepared.append((selection, entry, path))
                snapshots = []
                total = 0
                for selection, entry, path in prepared:
                    with path.open("rb") as stream:
                        raw = stream.read(min(MAX_NOTE_BYTES, MAX_SOURCE_BYTES - total) + 1)
                    total += len(raw)
                    if len(raw) > MAX_NOTE_BYTES or total > MAX_SOURCE_BYTES:
                        raise ObusSQLError("source_too_large", "対象ノートが読取上限を超えています。", 413)
                    if sha256(raw).hexdigest() != selection.sha256:
                        raise _changed()
                    props, _body = unpack(raw.decode("utf-8-sig"))
                    if (props.get("note_id") != selection.note_id or props.get("vault_kind") != entry["vault"]
                            or props.get("managed_by") != "gurumoji"):
                        raise _unavailable()
                    revision, source_hash = entry.get("revision"), entry.get("source_hash", "")
                    if (revision is not None and (type(revision) not in (int, str) or len(str(revision)) > 128)
                            or not isinstance(source_hash, str) or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}|", source_hash)
                            or props.get("revision") != revision or props.get("source_hash", "") != source_hash
                            or props.get("status") != "current"):
                        raise _changed()
                    snapshots.append(NoteSnapshot(library_id, selection, entry["vault"],
                                                  revision, source_hash, raw))
                return tuple(snapshots)
        except ObusSQLError:
            raise
        except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error, yaml.YAMLError):
            raise _unavailable() from None


class ObusSQLService:
    def __init__(self, database_file: Path, registry_factory):
        self.database_file = Path(database_file)
        self.registry_factory = registry_factory

    def list_notes(self, offset: int = 0) -> dict:
        _load_api()  # Disabled or unavailable integration never opens the catalog.
        return ManagedNoteSource(self.database_file, self.registry_factory()).list_notes(offset)

    def preview(self, payload) -> dict:
        api = _load_api()  # Off/missing dependencies never open SQLite or a Vault.
        selections, query = _request(payload)
        source = ManagedNoteSource(self.database_file, self.registry_factory())
        snapshots = source.capture(selections)
        try:
            scope = api.Scope("gurumoji", snapshots[0].library_id)
            # This port is used only after the local HTTP guard, or by a trusted host.
            # Request JSON cannot set actor/agent/scope or grant access to other notes.
            context = api.ReadContext("gurumoji-local-user", "obussql-preview", scope)
            resources = {api.Resource(s.selection.note_id, api.Source("vault:" + s.vault, scope)): s
                         for s in snapshots}

            def read_current(resource):
                snapshot = resources.get(resource)
                if snapshot is None:
                    raise _unavailable()
                current = source.capture((snapshot.selection,))[0]
                if current != snapshot:
                    raise _changed()
                return current.raw

            backend = api.MemoryBackend(read_current)
            selected = []
            for resource, snapshot in resources.items():
                revision = backend.put(resource, snapshot.raw)
                if revision != snapshot.selection.sha256:
                    raise _changed()
                backend.grant(context, resource)
                selected.append((resource, revision))
            pack = api.retrieve_context(
                backend, context, tuple(selected), query=query,
                budget=api.PayloadBudget(max_bytes=MAX_PAYLOAD_BYTES), candidate_limit=1024,
                read_limits=api.ReadLimits(max_source_bytes=MAX_SOURCE_BYTES, max_document_bytes=MAX_NOTE_BYTES),
            )
            result = {"stage": "read_only_preview", "sources": [s.provenance() for s in snapshots],
                      "context": json.loads(pack.serialized_payload),
                      "measurement": {"utf8_bytes": pack.measurement.utf8_bytes,
                                      "token_count": pack.measurement.token_count}}
        except ObusSQLError:
            raise
        except api.SourceVersionChanged:
            raise _changed() from None
        except Exception:
            raise ObusSQLError("preview_failed", "ObusSQLの読取プレビューに失敗しました。対象と導入版を確認してください。", 422) from None
        finally:
            # Recheck the complete set even on zero matches or backend failure.
            # Catalog-only changes and library replacement also invalidate it.
            if source.capture(selections) != snapshots:
                raise _changed()
        return result
