"""一時DB・一時Vaultと専用ブラウザーで開発版の接続操作を検証する。"""
from contextlib import closing
import gc
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify, render_template, request
from werkzeug.serving import make_server
try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    sync_playwright = expect = None

from gurumoji.vault_registry import VaultRegistry, entity_key
from gurumoji.web.obussql_routes import register_obussql_routes
from gurumoji.web.security import make_request_guards, register_request_security

ROOT = Path(os.environ.get("GURUMOJI_TEST_SOURCE_ROOT", Path(__file__).resolve().parents[1])).resolve()
pytestmark = [pytest.mark.browser, pytest.mark.skipif(
    not os.environ.get("GURUMOJI_TEST_SOURCE_ROOT") or not os.environ.get("GURUMOJI_BROWSER_EXECUTABLE")
    or sync_playwright is None, reason="対象srcと専用ブラウザーを明示した場合だけ実行する")]



def snapshot(root):
    return {str(p.relative_to(root)): (sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def browser():
    executable = os.environ["GURUMOJI_BROWSER_EXECUTABLE"]
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(executable_path=executable, headless=True)
        yield instance
        instance.close()


@pytest.fixture
def ui(tmp_path, monkeypatch, browser):
    from gurumoji.services.obussql import ObusSQLService
    monkeypatch.setenv("MOJIOKOSI_OBUSSQL_ENABLED", "1")
    database = tmp_path / "data/library.sqlite3"
    database.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(database)) as db:
        db.execute("CREATE TABLE application_metadata(key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO application_metadata VALUES('library_id', ?)", ("a" * 32,))
        db.commit()
    registry = VaultRegistry(database, tmp_path / "software")
    registry.publish_input(item_id="synthetic", title="ObusSQL検証（合成データ）", segments=[], revision=1)
    note_id = "input-item-" + entity_key("synthetic")
    entry = registry.load()["notes"][note_id]
    service = ObusSQLService(database, lambda: registry)
    gc.collect()
    before = snapshot(tmp_path)
    app = Flask(__name__, template_folder=str(ROOT / "src/gurumoji/templates"),
                static_folder=str(ROOT / "src/gurumoji/static"))
    guards = make_request_guards(remote_access_enabled=lambda: False, remote_access_token=lambda: "",
                                remote_local_paths_enabled=lambda: False)
    register_request_security(app, remote_access_enabled=lambda: False, remote_access_token=lambda: "",
        remote_local_paths_enabled=lambda: False, max_media_upload_bytes=lambda: 1048576,
        max_csv_upload_bytes=lambda: 1048576, max_json_request_bytes=lambda: 65536,
        multipart_overhead_bytes=1024, is_colab_runtime=lambda: False,
        trusted_request_hosts=guards[0], remote_auth_valid=guards[2], request_origin_allowed=guards[3],
        admit_transcription_job=lambda: None, release_job_admission=lambda: None)
    register_obussql_routes(app, local_access_allowed=guards[1], service_factory=lambda: service)
    previews = []

    @app.before_request
    def capture_preview():
        if request.path == "/api/obsidian/obussql/preview":
            previews.append((request.get_json(), request.headers.get("X-Gurumoji-Request")))

    @app.get("/")
    def index():
        return render_template("index.html", app_name="Gurumoji 開発版（合成データ）", app_version="test",
            local_llm_label="検証用ローカルLLM", local_llm_short_label="Local", obsidian_enabled=True,
            runtime=dict(label="合成環境", native_file_dialog=False, browser_upload=True, colab=False,
                         source_path_example="/synthetic/input.wav", qwen_setup_note="合成環境"))

    @app.route("/api/<path:rest>", methods=["GET", "POST"])
    def synthetic_api(rest):
        if rest == "config":
            return jsonify(ok=True, runtime={"browser_upload": True}, default_output_dir="/synthetic/output",
                hf=False, openai=False, google=False, typesafe=False, lmstudio=False,
                obsidian_watcher={"state": "running", "message": "合成環境で監視中"})
        return jsonify(items=[], speakers=[], groups=[], terms=[], runs=[], job=None,
                       event_count=0, ready_count=0, registry_revision=0,
                       pagination={"offset": 0, "limit": 50, "total": 0, "has_more": False})

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    context = browser.new_context(viewport={"width": 1440, "height": 1050})
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(origin + "/") else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(origin)
        expect(page.locator("body")).not_to_have_class(re.compile(r".*\bbooting\b.*"))
        expect(page.locator("[data-obussql-pill]").first).to_contain_text("接続済み")
        yield SimpleNamespace(page=page, context=context, origin=origin, errors=errors, root=tmp_path,
                              before=before, previews=previews, note_id=note_id, note_hash=entry["sha256"])
    finally:
        context.close()
        server.shutdown()
        thread.join(timeout=5)
        gc.collect()
        assert not errors, errors



def open_obussql(ui):
    page = ui.page
    if not page.locator("#connection-dialog").evaluate("element => element.open"):
        page.locator("#connection-button").click()
    page.locator("#connection-dialog [data-open-obussql]").click()
    expect(page.locator("#obussql-dialog")).to_be_visible()
    expect(page.locator("#obussql-notes input").first).to_be_visible()


def select_query(ui):
    ui.page.locator("#obussql-notes label").filter(has_text="ObusSQL検証（合成データ）").locator("input").check()
    ui.page.locator("#obussql-query").fill("Whisper")


def reply(text):
    return {"context": {"schema_version": "bounded-context-v1", "selection": [
        {"node": {"original": {"quote": {"resource_id": "synthetic", "text": text,
            "line_start": 1, "line_end": 1, "source_revision": "a" * 64}}}}]}}


def test_native_connection_and_readonly_search(ui):
    open_obussql(ui)
    select_query(ui)
    ui.page.locator("#obussql-search").click()
    expect(ui.page.locator("#obussql-results pre").first).to_contain_text("Whisper")
    expect(ui.page.locator("#obussql-results small").first).to_contain_text("行")
    assert ui.previews == [({"notes": [{"note_id": ui.note_id, "sha256": ui.note_hash}], "query": "Whisper"}, "1")]
    assert snapshot(ui.root) == ui.before
    artifact = os.environ.get("GURUMOJI_TEST_ARTIFACTS")
    if artifact:
        folder = Path(artifact)
        folder.mkdir(parents=True, exist_ok=True)
        ui.page.screenshot(path=str(folder / "obussql-connected.png"), full_page=True)
        ui.page.set_viewport_size({"width": 390, "height": 844})
        box = ui.page.locator("#obussql-dialog").bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= 391
        assert ui.page.locator("#obussql-dialog").evaluate("element => element.scrollWidth <= element.clientWidth + 1")
        ui.page.screenshot(path=str(folder / "obussql-connected-mobile.png"), full_page=True)


def test_all_screens_and_default_language_enabled(ui):
    page = ui.page
    assert "Coming Soon" not in page.content()
    page.locator("[data-open-general-settings]").first.click()
    expect(page.locator("#gs-language")).to_be_enabled()
    page.locator("#gs-language").select_option("en")
    assert page.evaluate("() => languageSelect.value") == "en"
    assert json.loads(page.evaluate("() => localStorage.getItem('gurumoji.generalSettings.v1')"))["language"] == "en"
    page.keyboard.press("Escape")
    page.reload()
    expect(page.locator("body")).not_to_have_class(re.compile(r".*\bbooting\b.*"))
    assert page.evaluate("() => languageSelect.value") == "en"
    page.locator("#show-analysis-button").click()
    expect(page.locator("#analysis-title")).to_be_visible()
    expect(page.locator("#analysis-run-button")).to_be_visible()
    page.locator("#prior-internal-button").click()
    expect(page.locator("#internal-data-card [data-open-obussql]")).to_be_visible()


def test_disabled_connection_does_not_list_notes(ui):
    ui.page.route("**/api/obsidian/obussql", lambda route: route.fulfill(json={"available": False, "message": "接続は無効です。"}))
    seen = []
    ui.page.on("request", lambda request: seen.append(request.url) if "/obussql/notes" in request.url else None)
    ui.page.locator("#connection-button").click()
    ui.page.locator("#connection-dialog [data-open-obussql]").click()
    expect(ui.page.locator("#obussql-dialog [data-obussql-pill]")).to_contain_text("未接続")
    expect(ui.page.locator("#obussql-search")).to_be_disabled()
    assert ui.page.locator("#obussql-notes input").count() == 0
    assert not seen
    assert snapshot(ui.root) == ui.before


def test_selection_limit_and_untrusted_title_is_text(ui):
    title = '<img src=x onerror="window.injected=true">合成ノート'
    rows = [{"note_id": f"synthetic-{i}", "sha256": "b" * 64, "title": title, "vault": "input"} for i in range(17)]
    ui.page.route("**/api/obsidian/obussql/notes?*", lambda route: route.fulfill(json={"notes": rows, "next_offset": None}))
    open_obussql(ui)
    boxes = ui.page.locator("#obussql-notes input")
    for i in range(16): boxes.nth(i).check()
    boxes.nth(16).click()
    expect(boxes.nth(16)).not_to_be_checked()
    expect(ui.page.locator("#obussql-selected-count")).to_have_text("16 / 16件を選択")
    expect(ui.page.locator("#obussql-message")).to_contain_text("最大16件")
    assert ui.page.locator("#obussql-notes img").count() == 0
    assert ui.page.evaluate("() => window.injected === undefined")


def test_changed_query_ignores_old_response(ui):
    pending = []
    ui.page.route("**/api/obsidian/obussql/preview", lambda route: pending.append(route))
    open_obussql(ui)
    select_query(ui)
    ui.page.locator("#obussql-search").click()
    expect(ui.page.locator("#obussql-message")).to_contain_text("検索しています")
    ui.page.locator("#obussql-query").fill("変更後の検索")
    assert len(pending) == 1
    pending[0].fulfill(json=reply("古い検索結果"))
    expect(ui.page.locator("#obussql-search")).to_be_enabled()
    assert ui.page.locator("#obussql-results article").count() == 0
    assert "古い検索結果" not in ui.page.locator("#obussql-message").inner_text()


def test_reopened_dialog_keeps_new_search_owner(ui):
    pending = []
    ui.page.route("**/api/obsidian/obussql/preview", lambda route: pending.append(route))
    open_obussql(ui)
    select_query(ui)
    ui.page.locator("#obussql-search").click()
    expect(ui.page.locator("#obussql-message")).to_contain_text("検索しています")
    ui.page.locator("#obussql-close").click()
    open_obussql(ui)
    select_query(ui)
    ui.page.locator("#obussql-search").click()
    expect(ui.page.locator("#obussql-message")).to_contain_text("検索しています")
    assert len(pending) == 2
    pending[0].fulfill(json=reply("古い結果"))
    ui.page.wait_for_timeout(100)
    expect(ui.page.locator("#obussql-search")).to_be_disabled()
    assert ui.page.locator("#obussql-results article").count() == 0
    pending[1].fulfill(json=reply("最新の結果"))
    expect(ui.page.locator("#obussql-results pre")).to_have_text("最新の結果")
    expect(ui.page.locator("#obussql-search")).to_be_enabled()


def test_error_clears_previous_results(ui):
    open_obussql(ui)
    select_query(ui)
    ui.page.locator("#obussql-search").click()
    expect(ui.page.locator("#obussql-results pre").first).to_be_visible()
    ui.page.route("**/api/obsidian/obussql/preview", lambda route: route.fulfill(status=409, json={"error": "ノートの版が変わりました。再確認してください。"}))
    ui.page.locator("#obussql-query").fill("変更後")
    ui.page.locator("#obussql-search").click()
    expect(ui.page.locator("#obussql-message")).to_contain_text("版が変わりました")
    assert ui.page.locator("#obussql-results article").count() == 0
