"""Opt-in real Windows AT acceptance harness; GUI actions belong to the operator.

Run with the repository's existing Windows Python and PYTHONPATH=src;tests.
No model, real library, shared browser profile or Vault is used. JSON lines on
stdin select observations, viewport, a bounded synthetic HTTP delay, or exit.
This is evidence support, not a claim that accessibility attributes prove AT.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import sys
import tempfile
import threading
from unittest.mock import patch


def readonly_snapshot(root, database_file):
    with closing(sqlite3.connect(Path(database_file).as_uri() + "?mode=ro", uri=True)) as db:
        logical = "\n".join(db.iterdump()).encode("utf-8")
    return {"db": hashlib.sha256(logical).hexdigest(),
            "files": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in root.rglob("*") if p.is_file()}}


def main():
    if os.environ.get("GURUMOJI_RUN_REAL_AT") != "1":
        raise SystemExit("NOTRUN: explicit GURUMOJI_RUN_REAL_AT=1 is required")
    evidence = Path(sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gurumoji-r9-at-import-") as isolated:
        os.environ.update(MOJIOKOSI_DATA_DIR=isolated + "/data",
                          MOJIOKOSI_OUTPUT_DIR=isolated + "/output",
                          MOJIOKOSI_BACKUP_DIR=isolated + "/backup")
        from test_ai_data_export_independent import IndependentExportTests
        import app
        from gurumoji.web import export_routes
        from playwright.sync_api import sync_playwright

        fixture = IndependentExportTests()
        fixture.setUp()
        release = threading.Event()
        entered = threading.Event()
        delayed_enabled = threading.Event()
        original = export_routes.extract_frames
        observations, network, downloads, external, errors = [], [], [], [], []

        before = readonly_snapshot(fixture.root, app.DATABASE_FILE)

        def delayed(*args, **kwargs):
            if delayed_enabled.is_set():
                entered.set()
                if not release.wait(180):
                    raise RuntimeError("bounded real-AT fixture delay expired")
            return original(*args, **kwargs)

        try:
            with fixture.http_server() as origin, patch.object(export_routes, "extract_frames", side_effect=delayed), sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    headless=False, chromium_sandbox=True,
                    args=["--disable-background-networking", "--no-first-run", "--no-default-browser-check"],
                )
                context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
                from urllib.parse import urlsplit
                def guard(route):
                    if urlsplit(route.request.url).hostname != "127.0.0.1":
                        external.append(route.request.url)
                        route.abort()
                    else:
                        route.continue_()
                context.route("**/*", guard)
                page = context.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("response", lambda r: network.append({"url": r.url, "method": r.request.method, "status": r.status}))
                page.on("download", lambda d: downloads.append(d.suggested_filename))
                page.goto(origin)
                print(json.dumps({"ready": True, "origin": origin, "fixture": str(fixture.root), "browser": browser.version,
                                  "cwd": str(Path.cwd()), "before": before}, ensure_ascii=False), flush=True)
                commands = queue.Queue()
                def read_commands():
                    for raw in sys.stdin:
                        commands.put(raw)
                    commands.put('{"op":"exit"}')
                threading.Thread(target=read_commands, daemon=True).start()
                while True:
                    # Keep Playwright's HTTP routing alive during native AT input.
                    page.wait_for_timeout(50)
                    try:
                        line = commands.get_nowait()
                    except queue.Empty:
                        continue
                    command = json.loads(line)
                    op = command["op"]
                    if op == "exit":
                        break
                    if op == "width":
                        page.set_viewport_size({"width": command["width"], "height": 900})
                    elif op == "delay":
                        entered.clear(); release.clear(); delayed_enabled.set()
                    elif op == "release":
                        release.set(); delayed_enabled.clear()
                    name = command.get("name", f"observation-{len(observations)}")
                    page.wait_for_timeout(200)
                    state = page.evaluate("""() => ({url:location.href, title:document.title, viewport:{width:innerWidth,height:innerHeight},
                        focus:{tag:document.activeElement?.tagName,id:document.activeElement?.id,text:document.activeElement?.textContent?.slice(0,200)},
                        export:[...document.querySelectorAll('[data-ai-data-export]')].filter(n=>n.getBoundingClientRect().height).map(n=>({open:n.open,busy:n.getAttribute('aria-busy'),status:n.querySelector('[role=status]')?.textContent}))})""")
                    after = readonly_snapshot(fixture.root, app.DATABASE_FILE)
                    state.update(name=name, readonly_unchanged=after == before, http_delay_entered=entered.is_set(),
                                 network=list(network), downloads=list(downloads), external=list(external), errors=list(errors))
                    page.screenshot(path=str(evidence / f"{name}.png"))
                    observations.append(state)
                    (evidence / "browser-observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(json.dumps(state, ensure_ascii=False), flush=True)
                release.set()
                context.close(); browser.close()
        finally:
            release.set()
            final = readonly_snapshot(fixture.root, app.DATABASE_FILE)
            (evidence / "readonly-receipt.json").write_text(json.dumps({"before": before, "after": final,
                "unchanged": before == final, "external": external, "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
            fixture.doCleanups()


if __name__ == "__main__":
    main()
