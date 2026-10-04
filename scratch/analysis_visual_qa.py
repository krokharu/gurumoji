"""Opt-in historical analysis screenshots; not part of pytest acceptance."""

import argparse
from contextlib import ExitStack, closing
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]
import browser_support  # noqa: E402


def _run(argv=None) -> int:
    browser_support.require_ui_browser()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", help="Screenshot prefix; 'after' also runs interaction assertions")
    label = parser.parse_args(argv).label
    from test_analysis_method_view import MethodViewFixture
    from werkzeug.serving import make_server
    import app

    with ExitStack() as cleanup:
        browser = cleanup.enter_context(browser_support.sandboxed_playwright_browser())
        fixture = MethodViewFixture()
        cleanup.callback(fixture.doCleanups)
        fixture.setUp()
        server = make_server("127.0.0.1", 0, app.app, threaded=True)
        cleanup.callback(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        cleanup.callback(thread.join, timeout=5)
        cleanup.callback(server.shutdown)
        cleanup.enter_context(patch.object(app, "get_machine_profile", return_value={}))
        cleanup.enter_context(patch.object(app, "load_token_config", return_value=app.TokenConfig()))
        out = ROOT / "output/design/analysis"
        out.mkdir(parents=True, exist_ok=True)
        with closing(browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)) as page:
            page.goto(f'http://127.0.0.1:{server.server_port}/#/analysis/{fixture.item_id}')
            page.locator('#analysis-desktop-content .analysis-result-intro').wait_for()
            page.locator('body:not(.booting)').wait_for()
            page.locator('#boot-splash').wait_for(state='hidden')
            page.screenshot(path=str(out / (label + '-desktop.png')))
            if label == 'after':
                for name in ['content', 'conversation', 'language', 'statistics', 'exports', 'overview']:
                    page.locator(f'#analysis-desktop-content [data-analysis-jump="{name}"]').click()
                    assert page.locator(f'#analysis-desktop-content [data-analysis-page="{name}"]').is_visible()
                    assert page.locator('#analysis-desktop-content [data-analysis-page]:visible').count() == 1
                page.locator('#analysis-desktop-content [data-analysis-jump="content"]').click()
                page.locator('#analysis-desktop-content [data-kwic-query]').fill('改善')
                page.locator('#analysis-desktop-content [data-analysis-jump="overview"]').click()
                page.locator('#analysis-desktop-content [data-analysis-jump="content"]').click()
                assert page.locator('#analysis-desktop-content [data-kwic-query]').input_value() == '改善'
                page.locator('#analysis-desktop-content [data-analysis-jump="overview"]').click()
            for width in [390, 768, 1024]:
                page.set_viewport_size({'width': width, 'height': 844})
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=str(out / f'{label}-{width}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow {width}'
                if label == 'after':
                    host = '#analysis-mobile-content' if width < 960 else '#analysis-desktop-content'
                    for name in ['content', 'conversation', 'language', 'statistics', 'exports', 'overview']:
                        button = page.locator(f'{host} [data-analysis-jump="{name}"]')
                        button.focus()
                        page.keyboard.press('Enter')
                        assert page.locator(f'{host} [data-analysis-page="{name}"]').is_visible()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow {width}/{name}'
                    page.locator('.analysis-more-actions > summary').click()
                    assert page.locator('#analysis-json-export').is_visible()
                    page.locator('#analysis-run-settings-button').click()
                    assert page.locator('#analysis-run-dialog').is_visible()
                    page.keyboard.press('Escape')
                    page.locator('.analysis-more-actions > summary').click()
            if label == 'after':
                page.goto(f'http://127.0.0.1:{server.server_port}/?view=analysis&item={fixture.item_id}&section=statistics')
                page.locator('#analysis-desktop-content [data-analysis-page="statistics"]').wait_for(state='visible')
    print("PASS: screenshots and responsive checks")
    return 0


def main(argv=None) -> int:
    try:
        return _run(argv)
    except unittest.SkipTest as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
