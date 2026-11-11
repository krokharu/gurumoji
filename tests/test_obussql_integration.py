"""Gurumoji's opt-in source/transport boundary; never use an actual user Vault.

Run with the application worktree's src first on PYTHONPATH. ObusSQL's native
package is optional; the final smoke test runs only when it is installed.
"""
from dataclasses import dataclass
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask
import pytest

from gurumoji.services import obussql as bridge
from gurumoji.vault_registry import VaultRegistry, entity_key
from gurumoji.web.obussql_routes import register_obussql_routes
from gurumoji.web.security import make_request_guards, register_request_security


@pytest.fixture
def notes(tmp_path):
    database = tmp_path / "data" / "library.sqlite3"
    database.parent.mkdir(exist_ok=True)
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE application_metadata(key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO application_metadata VALUES('library_id', ?)", ("a" * 32,))
    registry = VaultRegistry(database, tmp_path / "software")
    registry.publish_input(item_id="sample", title="synthetic.wav", segments=[], revision=1)
    note_id = "input-item-" + entity_key("sample")
    entry = registry.load()["notes"][note_id]
    selection = bridge.NoteSelection(note_id, entry["sha256"])
    source = bridge.ManagedNoteSource(database, registry)
    service = bridge.ObusSQLService(database, lambda: registry)
    path = registry.root("input") / entry["path"]
    return SimpleNamespace(database=database, registry=registry, selection=selection,
                           source=source, service=service, path=path)


def request_for(notes):
    return {"notes": [{"note_id": notes.selection.note_id, "sha256": notes.selection.sha256}], "query": "Whisper"}


def files_under(root):
    return {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def test_disabled_never_loads_optional_package_or_sources(monkeypatch, tmp_path):
    before = set(tmp_path.rglob("*"))
    monkeypatch.delenv(bridge.ENV_ENABLED, raising=False)
    importer = Mock(side_effect=AssertionError("optional import"))
    probe = Mock(side_effect=AssertionError("metadata access"))
    registry = Mock(side_effect=AssertionError("Vault access"))
    monkeypatch.setattr(bridge, "import_module", importer)
    monkeypatch.setattr(bridge.metadata, "version", probe)
    assert bridge.status()["status"] == "disabled"
    with pytest.raises(bridge.ObusSQLError, match="無効"):
        bridge.ObusSQLService(tmp_path / "missing.sqlite3", registry).preview({})
    assert set(tmp_path.rglob("*")) == before
    importer.assert_not_called()
    probe.assert_not_called()
    registry.assert_not_called()


@pytest.mark.parametrize("mode,expected", [
    ("python", "python_unsupported"), ("missing", "not_installed"),
    ("version", "incompatible"), ("native", "import_failed"),
])
def test_unavailable_diagnostics_hide_dependency_exception(monkeypatch, mode, expected):
    monkeypatch.setenv(bridge.ENV_ENABLED, "1")
    monkeypatch.setattr(bridge.sys, "version_info", (3, 11) if mode == "python" else (3, 12))
    def version(_name):
        if mode == "missing":
            raise metadata.PackageNotFoundError("sensitive-path")
        return "9.9.9" if mode == "version" else bridge.PACKAGE_VERSION
    monkeypatch.setattr(bridge.metadata, "version", version)
    monkeypatch.setattr(bridge, "import_module", Mock(side_effect=OSError("sensitive-path")))
    result = bridge.status()
    assert result["status"] == expected
    assert not result["available"]
    assert "sensitive-path" not in json.dumps(result)


@pytest.mark.parametrize("python", [(3, 10), (3, 11), (3, 13)])
def test_maf_requires_python_312_before_probing_dependencies(monkeypatch, python):
    monkeypatch.setenv(bridge.ENV_ENABLED, "1")
    monkeypatch.setattr(bridge.sys, "version_info", python)
    probe = Mock(side_effect=AssertionError("dependency probe"))
    monkeypatch.setattr(bridge.metadata, "version", probe)
    assert bridge.maf_status()["status"] == "python_unsupported"
    probe.assert_not_called()


@pytest.mark.parametrize("package", ["obussql-maf", "agent-framework-core"])
@pytest.mark.parametrize("condition", ["missing", "wrong"])
def test_maf_dependencies_fail_before_any_runtime_import(monkeypatch, package, condition):
    monkeypatch.setenv(bridge.ENV_ENABLED, "1")
    monkeypatch.setattr(bridge.sys, "version_info", (3, 12))
    def version(name):
        if name == package:
            if condition == "missing":
                raise metadata.PackageNotFoundError("sensitive-path")
            return "unknown"
        return {"obussql-maf": "0.1.0.dev0", "agent-framework-core": "1.22.0"}[name]
    importer = Mock(side_effect=AssertionError("MAF import"))
    monkeypatch.setattr(bridge.metadata, "version", version)
    monkeypatch.setattr(bridge, "import_module", importer)
    result = bridge.maf_status()
    assert result["status"] == ("not_installed" if condition == "missing" else "incompatible")
    assert result["execution_ready"] is False
    assert "sensitive" not in json.dumps(result)
    importer.assert_not_called()


@pytest.mark.parametrize("readiness", ["NOT_READY", "READY", "READY_SYNTHETIC", "raises"])
def test_maf_uses_upstream_readiness_without_running_or_falling_back(monkeypatch, readiness):
    monkeypatch.setenv(bridge.ENV_ENABLED, "1")
    monkeypatch.setattr(bridge.sys, "version_info", (3, 12))
    monkeypatch.setattr(bridge.metadata, "version", {
        "obussql-maf": "0.1.0.dev0", "agent-framework-core": "1.22.0",
    }.__getitem__)
    unavailable = object()
    runtime = SimpleNamespace(
        readiness=Mock(return_value=SimpleNamespace(status=readiness, code=unavailable)),
        run=Mock(side_effect=AssertionError("workflow must never run")),
    )
    if readiness == "raises":
        runtime.readiness.side_effect = RuntimeError("sensitive-path")
    api = SimpleNamespace(
        PRODUCTION_PROFILE="obus.maf.pipeline.v1", TESTED_CORE_VERSION="1.22.0",
        RuntimeConfig=Mock(return_value=object()), create_runtime=Mock(return_value=runtime),
        ErrorCode=SimpleNamespace(HOST_BINDING_UNAVAILABLE=unavailable),
    )
    importer = Mock(return_value=api)
    monkeypatch.setattr(bridge, "import_module", importer)
    result = bridge.maf_status()
    assert result["execution_ready"] is False
    if readiness == "NOT_READY":
        assert result["status"] == "host_binding_unavailable"
        assert result["package_available"] is True
    else:
        assert result["status"] == ("import_failed" if readiness == "raises" else "incompatible")
        assert result["package_available"] is False
    assert "sensitive" not in json.dumps(result)
    importer.assert_called_once_with("obussql_maf")
    api.RuntimeConfig.assert_called_once_with(profile_id="obus.maf.pipeline.v1", enabled=True)
    api.create_runtime.assert_called_once_with(api.RuntimeConfig.return_value)
    runtime.run.assert_not_called()


def test_missing_maf_does_not_disable_the_read_preview(monkeypatch):
    monkeypatch.setenv(bridge.ENV_ENABLED, "1")
    monkeypatch.setattr(bridge.sys, "version_info", (3, 12))
    monkeypatch.setattr(bridge, "_load_api", lambda: api_double())
    monkeypatch.setattr(bridge.metadata, "version", Mock(side_effect=metadata.PackageNotFoundError))
    result = bridge.status()
    assert result["status"] == "available_for_preview"
    assert result["available"] is True
    assert result["maf"]["status"] == "not_installed"
    assert result["maf"]["execution_ready"] is False


def test_registered_source_preserves_bytes_identity_and_does_not_write(notes, tmp_path):
    before = files_under(tmp_path)
    snapshot, = notes.source.capture((notes.selection,))
    assert snapshot.raw == notes.path.read_bytes()
    assert snapshot.provenance()["project_id"] == "a" * 32
    assert snapshot.provenance()["resource_id"] == notes.selection.note_id
    assert snapshot.provenance()["source_revision"] == sha256(snapshot.raw).hexdigest()
    assert snapshot.revision == 1
    assert "raw" not in repr(snapshot)
    assert files_under(tmp_path) == before


def test_bom_crlf_and_renamed_note_preserve_original_identity(notes):
    raw = b"\xef\xbb\xbf" + notes.path.read_bytes().replace(b"\n", b"\r\n")
    renamed = notes.path.with_name("renamed.md")
    notes.path.rename(renamed)
    renamed.write_bytes(raw)
    catalog = notes.registry.load()
    entry = catalog["notes"][notes.selection.note_id]
    entry.update(path=renamed.relative_to(notes.registry.root("input")).as_posix(), sha256=sha256(raw).hexdigest())
    notes.registry.save(catalog)
    selection = bridge.NoteSelection(notes.selection.note_id, entry["sha256"])
    snapshot, = notes.source.capture((selection,))
    assert snapshot.raw == raw
    assert snapshot.provenance()["resource_id"] == notes.selection.note_id


@pytest.mark.parametrize("change", ["edited", "deleted", "stale", "pending", "missing", "alias", "research", "outside", "header"])
def test_unreadable_or_changed_sources_fail_without_repair(notes, tmp_path, change):
    catalog = notes.registry.load()
    entry = catalog["notes"][notes.selection.note_id]
    selection = notes.selection
    if change == "edited":
        notes.path.write_bytes(notes.path.read_bytes() + b"\nResearcher's own text\n")
    elif change == "deleted":
        notes.path.unlink()
    elif change == "stale":
        entry["status"] = "stale"
    elif change == "pending":
        entry["pending"] = "b" * 64
    elif change == "missing":
        entry["sync"] = "missing"
    elif change == "alias":
        catalog["notes"]["second-identity"] = dict(entry)
    elif change == "research":
        catalog["vaults"]["input"]["root"] = "obsidian/researchvault"
    elif change == "outside":
        entry["path"] = "../../tokens.md"
    elif change == "header":
        raw = notes.path.read_bytes().replace(notes.selection.note_id.encode(), b"a-different-id")
        notes.path.write_bytes(raw)
        entry["sha256"] = sha256(raw).hexdigest()
        selection = bridge.NoteSelection(notes.selection.note_id, entry["sha256"])
    notes.registry.save(catalog)
    before = files_under(tmp_path)
    with pytest.raises(bridge.ObusSQLError):
        notes.source.capture((selection,))
    assert files_under(tmp_path) == before


def test_preflights_complete_batch_before_reading_a_note(notes, monkeypatch):
    original = Path.open
    def guarded(path, *args, **kwargs):
        if path.suffix == ".md":
            raise AssertionError("a note opened before complete preflight")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(bridge.ObusSQLError) as error:
        notes.source.capture((notes.selection, bridge.NoteSelection("unknown", "b" * 64)))
    assert error.value.code == "source_unavailable"


def test_missing_database_is_not_created(tmp_path):
    database = tmp_path / "absent.sqlite3"
    source = bridge.ManagedNoteSource(database, VaultRegistry(database))
    with pytest.raises(bridge.ObusSQLError):
        source.capture((bridge.NoteSelection("unknown", "b" * 64),))
    assert not database.exists()


@pytest.mark.parametrize("limit_name", ["MAX_NOTE_BYTES", "MAX_SOURCE_BYTES"])
def test_source_read_is_bounded(notes, monkeypatch, limit_name):
    monkeypatch.setattr(bridge, limit_name, 32)
    with pytest.raises(bridge.ObusSQLError) as error:
        notes.source.capture((notes.selection,))
    assert error.value.code == "source_too_large"


def test_symlink_is_not_followed(notes, tmp_path):
    target = tmp_path / "outside.md"
    notes.path.rename(target)
    try:
        notes.path.symlink_to(target)
    except OSError:
        pytest.skip("OS does not permit unprivileged symbolic links")
    with pytest.raises(bridge.ObusSQLError):
        notes.source.capture((notes.selection,))


@dataclass(frozen=True)
class Scope:
    app_id: str
    project_id: str


@dataclass(frozen=True)
class Source:
    source_id: str
    scope: Scope


@dataclass(frozen=True)
class Resource:
    resource_id: str
    source: Source


@dataclass(frozen=True)
class ReadContext:
    actor_id: str
    agent_id: str
    scope: Scope


class SourceVersionChanged(ValueError):
    pass


def api_double(callback=lambda: None):
    """A transport double, not a replacement parser or retrieval implementation."""
    class Backend:
        def __init__(self, read_current):
            self.read_current, self.grants, self.raw = read_current, set(), {}

        def put(self, resource, raw):
            self.raw[resource] = raw
            return sha256(raw).hexdigest()

        def grant(self, context, resource):
            self.grants.add((context, resource))

    def retrieve(backend, context, selections, **options):
        assert context == ReadContext("gurumoji-local-user", "obussql-preview", Scope("gurumoji", "a" * 32))
        assert options["budget"].max_bytes == bridge.MAX_RETRIEVAL_BYTES
        assert options["candidate_limit"] == 10000
        assert options["read_limits"].max_source_bytes == bridge.MAX_SOURCE_BYTES
        for resource, revision in selections:
            assert (context, resource) in backend.grants
            assert resource.source.source_id == "vault:input"
            assert sha256(backend.read_current(resource)).hexdigest() == revision
        callback()
        return SimpleNamespace(serialized_payload='{"selection":[]}',
                               measurement=SimpleNamespace(utf8_bytes=16, token_count=None))
    return SimpleNamespace(Scope=Scope, Source=Source, Resource=Resource, ReadContext=ReadContext,
                           MemoryBackend=Backend, retrieve_context=retrieve, ReadLimits=SimpleNamespace,
                           PayloadBudget=SimpleNamespace, SourceVersionChanged=SourceVersionChanged)


def test_preview_scopes_exact_selection_and_has_no_persistent_effects(notes, tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "_load_api", lambda: api_double())
    before = files_under(tmp_path)
    result = notes.service.preview(request_for(notes))
    assert result["stage"] == "read_only_preview"
    assert result["sources"][0]["source_revision"] == notes.selection.sha256
    assert result["measurement"]["token_count"] is None
    assert files_under(tmp_path) == before


@pytest.mark.parametrize("change", ["bytes", "catalog", "library"])
def test_even_empty_results_revalidate_sources_and_library(notes, monkeypatch, change):
    def mutate():
        if change == "bytes":
            notes.path.write_bytes(notes.path.read_bytes() + b"\nchanged\n")
        elif change == "catalog":
            catalog = notes.registry.load()
            catalog["notes"][notes.selection.note_id]["revision"] = 2
            notes.registry.save(catalog)
        else:
            with sqlite3.connect(notes.database) as db:
                db.execute("UPDATE application_metadata SET value=? WHERE key='library_id'", ("b" * 32,))
    monkeypatch.setattr(bridge, "_load_api", lambda: api_double(mutate))
    with pytest.raises(bridge.ObusSQLError) as error:
        notes.service.preview(request_for(notes))
    assert error.value.code == "source_changed"


@pytest.mark.parametrize("payload", [None, {}, {"notes": [], "query": "x"},
    {"notes": [{"path": "../tokens.json"}], "query": "x"},
    {"notes": [{"note_id": "a", "sha256": "0" * 64}], "query": "x", "actor_id": "admin"},
    {"notes": [{"note_id": "a", "sha256": "0" * 64}] * 17, "query": "x"},
    {"notes": [{"note_id": "a", "sha256": "0" * 64}] * 2, "query": "x"},
    {"notes": [{"note_id": "a", "sha256": "0" * 64}], "query": " "},
])
def test_invalid_requests_do_not_open_sources(monkeypatch, tmp_path, payload):
    monkeypatch.setattr(bridge, "_load_api", lambda: api_double())
    registry = Mock(side_effect=AssertionError("source touched"))
    with pytest.raises(bridge.ObusSQLError) as error:
        bridge.ObusSQLService(tmp_path / "missing.sqlite3", registry).preview(payload)
    assert error.value.http_status == 400
    registry.assert_not_called()


def client_for(service_factory, *, local=True):
    app = Flask(__name__)
    guards = make_request_guards(remote_access_enabled=lambda: False, remote_access_token=lambda: "",
                                remote_local_paths_enabled=lambda: False)
    register_request_security(app, remote_access_enabled=lambda: False, remote_access_token=lambda: "",
        remote_local_paths_enabled=lambda: False, max_media_upload_bytes=lambda: 1048576,
        max_csv_upload_bytes=lambda: 1048576, max_json_request_bytes=lambda: 65536,
        multipart_overhead_bytes=1024, is_colab_runtime=lambda: False,
        trusted_request_hosts=guards[0], remote_auth_valid=guards[2], request_origin_allowed=guards[3],
        admit_transcription_job=lambda: None, release_job_admission=lambda: None)
    register_obussql_routes(app, local_access_allowed=guards[1] if local else lambda: False,
                           service_factory=service_factory)
    return app.test_client()


def test_http_denies_remote_host_cross_origin_and_csrf_before_service():
    factory = Mock(side_effect=AssertionError("source touched"))
    client = client_for(factory)
    assert client.get("/api/obsidian/obussql", environ_overrides={"REMOTE_ADDR": "192.0.2.1"}).status_code == 403
    assert client.get("/api/obsidian/obussql", headers={"Host": "untrusted.invalid"}).status_code == 400
    assert client.post("/api/obsidian/obussql/preview", json={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/obsidian/obussql/preview", json={}, headers={"Origin": "http://localhost"}).status_code == 403
    assert client_for(factory, local=False).post("/api/obsidian/obussql/preview", json={}).status_code == 403
    factory.assert_not_called()


def test_http_disabled_is_available_without_package_or_db(monkeypatch, tmp_path):
    before = set(tmp_path.rglob("*"))
    monkeypatch.delenv(bridge.ENV_ENABLED, raising=False)
    client = client_for(lambda: bridge.ObusSQLService(tmp_path / "missing.sqlite3", Mock()))
    assert client.get("/api/obsidian/obussql").json["status"] == "disabled"
    response = client.post("/api/obsidian/obussql/preview", json={})
    assert response.status_code == 503
    assert response.json["code"] == "disabled"
    assert set(tmp_path.rglob("*")) == before


def test_backend_error_is_redacted(notes, monkeypatch):
    def failure():
        raise RuntimeError("sensitive-path or credential-like text")
    monkeypatch.setattr(bridge, "_load_api", lambda: api_double(failure))
    response = client_for(lambda: notes.service).post("/api/obsidian/obussql/preview", json=request_for(notes))
    assert response.status_code == 422
    assert response.json["code"] == "preview_failed"
    assert "sensitive" not in response.get_data(as_text=True)


def test_real_optional_package_preview(notes, monkeypatch, tmp_path):
    try:
        metadata.version("obsipg")
    except metadata.PackageNotFoundError:
        pytest.skip("native ObusSQL package not installed; this is not an end-to-end acceptance")
    monkeypatch.setenv(bridge.ENV_ENABLED, "1")
    before = files_under(tmp_path)
    result = notes.service.preview(request_for(notes))
    assert result["context"]["schema_version"] == "gurumoji-summary-context-v1"
    assert result["context"]["scope"]["project_id"] == "a" * 32
    assert result["context"]["selected_blocks"] > 0
    assert result["measurement"]["utf8_bytes"] <= bridge.MAX_PAYLOAD_BYTES
    assert files_under(tmp_path) == before


@pytest.mark.parametrize('query', ['存在しない検索語', '末尾の重要根拠'])
def test_real_preview_large_note_keeps_bounded_context_without_losing_tail(notes, monkeypatch, tmp_path, query):
    monkeypatch.setenv(bridge.ENV_ENABLED, '1')
    catalog = notes.registry.load()
    entry = catalog['notes'][notes.selection.note_id]
    body = '\n\n'.join(f'合成の段落{i}。' for i in range(1200)) + '\n\n末尾の重要根拠。\n'
    notes.registry._write(catalog, entry['vault'], entry['path'], notes.selection.note_id,
        {'title': '大きな合成ノート', 'status': 'current', 'revision': 1, 'source_hash': ''}, body)
    notes.registry.save(catalog)
    current = catalog['notes'][notes.selection.note_id]
    before = files_under(tmp_path)
    result = notes.service.preview({'notes': [{'note_id': notes.selection.note_id, 'sha256': current['sha256']}], 'query': query})
    assert result['measurement']['utf8_bytes'] <= bridge.MAX_PAYLOAD_BYTES
    assert result['context']['examined_blocks'] > 1024
    assert result['context']['exclusion_summary']['total'] > 1000
    if query == '末尾の重要根拠':
        assert any('末尾の重要根拠' in r['node']['original']['quote']['text'] for r in result['context']['selection'])
    else:
        assert result['context']['selection'] == []
    assert files_under(tmp_path) == before
