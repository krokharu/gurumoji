"""Exercise the new transcription screen in an isolated real browser session."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

import app  # noqa: E402

OUTPUT = REPO / "output" / "design" / "video-input"


def browser_executable() -> str | None:
    candidates = [shutil.which(name) for name in ("msedge", "chrome", "chromium", "chromium-browser")]
    candidates += [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def install_fixtures(page, *, ai_ready: bool = False) -> dict:
    machine = {"cpu": {"available": True, "name": "QA CPU", "logical_threads": 4},
               "gpu": {"cuda_available": False, "reason": "QA", "vram_gib": 0},
               "memory_gib": 8, "recommended": {"model_name": "base", "device": "cpu",
               "diarization_device": "cpu"}}
    config = {"ok": True, **app.TokenConfig().availability(),
              "lmstudio": False, "lmstudio_status": {"reachable": False},
              "default_output_dir": "", "machine": machine,
              "runtime": {"colab": False, "native_file_dialog": False}}
    if ai_ready:
        config.update({"openai": True, "openai_model": "qa-model", "typesafe": True,
                       "typesafe_model": "qa-jev-model"})
    page.route("**/api/config", lambda route: route.fulfill(json=config))
    page.route("**/api/custom-vocabulary", lambda route: route.fulfill(json={"terms": []}))
    page.route("**/api/ai/lmstudio-reasoning", lambda route: route.fulfill(json={"ok": False}))
    return config


def inspect_initial(page, width: int, height: int) -> dict:
    page.goto("/#/new", wait_until="domcontentloaded")
    page.locator("#job-form").wait_for(state="visible")
    page.locator("body:not(.booting)").wait_for(state="attached")
    page.locator("#boot-splash").wait_for(state="hidden")
    return page.evaluate(
        """({width, height}) => {
          const cta = document.querySelector('#start-button');
          const rect = cta.getBoundingClientRect();
          const panels = [...document.querySelectorAll('[data-settings-panel]')];
          return {
            requested_viewport: [width, height],
            actual_viewport: [innerWidth, innerHeight],
            document_width: document.documentElement.scrollWidth,
            form_visible: document.querySelector('#job-form').getBoundingClientRect().width > 0,
            all_panels_closed: panels.length === 5 && panels.every(panel => !panel.open),
            no_horizontal_overflow: document.documentElement.scrollWidth <= innerWidth,
            cta_rect: {top: rect.top, bottom: rect.bottom, width: rect.width},
            cta_visible: rect.width > 0 && rect.top >= 0 && rect.bottom <= innerHeight,
            cta_initially_disabled: cta.disabled,
          };
        }""",
        {"width": width, "height": height},
    )


def inspect_fonts(page) -> dict:
    return page.evaluate(
        """() => {
          const size = selector => parseFloat(getComputedStyle(document.querySelector(selector)).fontSize);
          return {
            setting_label: size('.settings-summary-label'),
            setting_value: size('.settings-summary-row strong'),
            mode_title: size('.conversation-mode-option-body strong'),
            mode_help: size('.conversation-mode-option-body small'),
            panel_title: size('.settings-panel > summary span'),
            panel_help: size('.settings-panel > summary small'),
          };
        }"""
    )


def run_interactions(page, config_fixture: dict) -> dict:
    results: dict[str, bool | int] = {}
    posts: list[dict] = []

    def mock_jobs(route):
        request = route.request
        posts.append({"method": request.method, "body": request.post_data_buffer or b""})
        route.fulfill(status=400, content_type="application/json", body='{"error":"QA capture complete"}')

    page.route("**/api/jobs", mock_jobs)
    finishing_summary = page.locator('#settings-summary [data-open-panel="finishing"]')
    results["default_finishing_is_off_with_model_absent"] = (
        "しない" in finishing_summary.inner_text()
        and "使用モデルなし" in finishing_summary.inner_text()
        and "Obsidianに保存してあとで整える" in finishing_summary.inner_text()
    )
    recognition_summary = page.locator('#settings-summary [data-open-panel="recognition"]')
    recognition_summary.click()
    page.locator("#transcription-device").select_option("cuda")
    page.locator("#diarization-device").select_option("cuda")
    page.locator("#model-name").select_option("small")
    results["gpu_and_model_are_visible"] = (
        "GPU" in recognition_summary.inner_text()
        and "small" in recognition_summary.inner_text()
    )
    page.locator("#transcription-device").select_option("cpu")
    page.locator("#diarization-device").select_option("cpu")
    results["cpu_selection_is_visible"] = "CPU" in recognition_summary.inner_text()
    page.locator('[data-settings-panel="recognition"]').evaluate("el => el.open = false")
    finishing_summary.click()
    finishing_panel = page.locator('[data-settings-panel="finishing"]')
    page.locator('input[name="transcript_finishing_mode"][value="advanced"]').check()
    page.locator("#ai-provider").select_option("openai")
    results["provider_model_and_enabled_state_are_visible"] = (
        "する" in finishing_summary.inner_text()
        and "OpenAI" in finishing_summary.inner_text()
        and "qa-model" in finishing_summary.inner_text()
    )
    page.locator('input[name="transcript_finishing_mode"][value="off"]').check()
    results["off_mode_hides_unused_model"] = (
        "しない" in finishing_summary.inner_text()
        and "使用モデルなし" in finishing_summary.inner_text()
    )
    page.locator('input[name="transcript_finishing_mode"][value="recommended"]').check()
    page.locator("#ai-provider").select_option("none")
    config_fixture.update({"lmstudio": True, "lmstudio_model": "qa-local-model"})
    page.evaluate("loadConfig()")
    page.wait_for_timeout(50)
    results["explicit_none_survives_config_refresh"] = page.locator("#ai-provider").input_value() == "none"
    finishing_panel.evaluate("el => el.open = false")
    panel = page.locator('[data-settings-panel="recognition"]')
    page.locator('#settings-summary [data-open-panel="recognition"]').click()
    results["settings_row_opens_panel"] = panel.evaluate("el => el.open && el.getBoundingClientRect().width > 0")
    page.locator('#model-name').select_option("small")
    results["summary_updates"] = "small" in page.locator('[data-settings-value="recognition"]').inner_text()
    panel.locator("summary").click()
    results["panel_can_close"] = not panel.evaluate("el => el.open")

    file_input = page.locator("#input-file")
    file_input.set_input_files({"name": "unsupported.exe", "mimeType": "application/octet-stream", "buffer": b"qa"})
    results["invalid_file_feedback"] = (
        page.locator("#path-error").is_visible()
        and file_input.evaluate("el => el.files.length === 0")
        and page.locator("#start-button").is_disabled()
    )
    file_input.set_input_files({"name": "sample.mp4", "mimeType": "video/mp4", "buffer": b"qa"})
    results["valid_file_selected"] = (
        file_input.evaluate("el => el.files[0]?.name === 'sample.mp4'")
        and page.locator("#start-button").is_enabled()
        and "sample.mp4" in page.locator("#path-detail").inner_text()
    )

    page.locator('#settings-summary [data-open-panel="recognition"]').click()
    page.locator('[name="min_speakers"]').fill("0")
    panel.locator("summary").click()
    page.evaluate("document.querySelector('#job-form').requestSubmit(document.querySelector('#start-button'))")
    results["invalid_recognition_reopens_panel_without_post"] = panel.evaluate("el => el.open") and len(posts) == 0
    page.locator('[name="min_speakers"]').fill("1")
    panel.locator("summary").click()
    page.locator('#settings-summary [data-open-panel="finishing"]').click()
    page.locator('input[name="transcript_finishing_mode"][value="advanced"]').check()
    page.locator("#ai-provider").select_option("none")
    finishing = page.locator('[data-settings-panel="finishing"]')
    finishing.evaluate("el => el.open = false")
    page.evaluate("document.querySelector('#job-form').requestSubmit(document.querySelector('#start-button'))")
    page.wait_for_timeout(300)
    results["invalid_finishing_reopens_panel_without_post"] = finishing.evaluate("el => el.open") and len(posts) == 0

    page.locator('input[name="transcript_finishing_mode"][value="recommended"]').check()
    page.evaluate("document.querySelector('#job-form').requestSubmit(document.querySelector('#start-button'))")
    page.wait_for_timeout(300)
    results["mocked_submit_once"] = len(posts) == 1
    results["mocked_payload_has_selected_file"] = bool(posts and b'filename="sample.mp4"' in posts[0]["body"])
    results["mocked_method_post"] = bool(posts and posts[0]["method"] == "POST")
    results["mocked_posts_count"] = len(posts)
    return results


def run_mobile(page) -> dict:
    results: dict[str, bool] = {}
    inspect_initial(page, 390, 844)
    results["starts_on_file_step"] = page.locator("#setup-source").is_visible() and not page.locator("#setup-settings").is_visible()
    page.evaluate(
        """() => {
          const transfer = new DataTransfer();
          transfer.items.add(new File(['qa'], 'mobile.mp4', {type: 'video/mp4'}));
          document.querySelector('#file-drop-zone').dispatchEvent(
            new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: transfer})
          );
        }"""
    )
    results["drop_selects_file"] = page.locator("#input-file").evaluate("el => el.files[0]?.name === 'mobile.mp4'")
    page.locator("#mobile-step-next").click()
    results["settings_step_visible"] = page.locator("#setup-settings").is_visible() and not page.locator("#setup-source").is_visible()
    results["settings_step_active"] = page.locator('[data-flow-step="2"]').evaluate("el => el.classList.contains('active')")
    results["settings_no_overflow"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(OUTPUT / "final-mobile-settings.png"), full_page=False, animations="disabled")
    row = page.locator('#settings-summary [data-open-panel="recognition"]')
    row.focus()
    page.keyboard.press("Enter")
    results["keyboard_opens_settings"] = page.locator('[data-settings-panel="recognition"]').evaluate("el => el.open")
    page.locator('#settings-summary [data-open-panel="recognition"]').click()
    page.locator("#mobile-step-next").click()
    results["start_step_visible"] = page.locator("#setup-launch").is_visible() and page.locator("#start-button").is_enabled()
    results["start_step_active"] = page.locator('[data-flow-step="3"]').evaluate("el => el.classList.contains('active')")
    results["start_no_overflow"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    results["review_shows_file"] = "mobile.mp4" in page.locator(".launch-mobile-review").inner_text()
    page.screenshot(path=str(OUTPUT / "final-mobile-start.png"), full_page=False, animations="disabled")
    return results


def main() -> int:
    executable = browser_executable()
    if not executable:
        raise RuntimeError("Chrome, Edge, or Chromium is required for browser QA.")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="video-input-qa-") as temporary:
        root = Path(temporary)
        original_database = app.DATABASE_FILE
        app.DATABASE_FILE = root / "library.sqlite3"
        app.initialize_library()
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None

        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        report: dict = {"viewports": {}, "interactions": {}, "mobile": {}}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=executable, headless=True,
                    args=["--disable-gpu", "--disable-background-networking", "--no-sandbox"],
                )
                try:
                    for width, height in ((1440, 900), (1280, 800), (390, 844)):
                        context = browser.new_context(
                            viewport={"width": width, "height": height},
                            device_scale_factor=1, base_url=base_url,
                        )
                        page = context.new_page()
                        install_fixtures(page)
                        report["viewports"][f"{width}x{height}"] = inspect_initial(page, width, height)
                        page.screenshot(path=str(OUTPUT / f"final-{width}x{height}.png"), full_page=False, animations="disabled")
                        context.close()

                    context = browser.new_context(
                        viewport={"width": 1440, "height": 900},
                        device_scale_factor=1, base_url=base_url,
                    )
                    page = context.new_page()
                    interaction_config = install_fixtures(page, ai_ready=True)
                    inspect_initial(page, 1440, 900)
                    report["fonts"] = inspect_fonts(page)
                    report["interactions"] = run_interactions(page, interaction_config)
                    context.close()

                    context = browser.new_context(
                        viewport={"width": 390, "height": 844},
                        device_scale_factor=1, base_url=base_url,
                    )
                    page = context.new_page()
                    install_fixtures(page)
                    report["mobile"] = run_mobile(page)
                    context.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            with app.jobs_lock:
                app.jobs.clear()
                app._job_admission_id = None
            app.DATABASE_FILE = original_database

    fonts = report["fonts"]
    report["font_size_pass"] = all(fonts[key] >= 15 for key in ("setting_label", "setting_value", "mode_title", "panel_title")) and all(
        fonts[key] >= 13 for key in ("mode_help", "panel_help")
    )
    (OUTPUT / "browser-qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    viewports_pass = all(
        item["form_visible"] and item["all_panels_closed"] and item["no_horizontal_overflow"]
        and item["cta_initially_disabled"]
        and (width == "390x844" or item["cta_visible"])
        for width, item in report["viewports"].items()
    )
    interactions_pass = all(value is True for key, value in report["interactions"].items() if key != "mocked_posts_count")
    mobile_pass = all(value is True for value in report["mobile"].values())
    return 0 if viewports_pass and interactions_pass and mobile_pass and report["font_size_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
