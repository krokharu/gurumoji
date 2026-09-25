import sys, threading, json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_analysis_method_view import MethodViewFixture
from test_browser_e2e import browser_executable
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
import app

out = ROOT / 'output/design/analysis'
out.mkdir(parents=True, exist_ok=True)
fixture = MethodViewFixture()
fixture.setUp()
server = make_server('127.0.0.1', 0, app.app, threaded=True)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    with patch.object(app, 'get_machine_profile', return_value={}), patch.object(app, 'load_token_config', return_value=app.TokenConfig()), sync_playwright() as p:
        browser = p.chromium.launch(executable_path=browser_executable(), headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        page.goto(f'http://127.0.0.1:{server.server_port}/#/analysis/{fixture.item_id}')
        page.locator('#analysis-desktop-content .analysis-result-intro').wait_for()
        page.locator('body:not(.booting)').wait_for()
        page.locator('#boot-splash').wait_for(state='hidden')
        page.screenshot(path=str(out / (sys.argv[1] + '-desktop.png')))
        if sys.argv[1] == 'after':
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
            page.screenshot(path=str(out / f'{sys.argv[1]}-{width}.png'))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'overflow {width}'
            if sys.argv[1] == 'after':
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
        if sys.argv[1] == 'after':
            page.goto(f'http://127.0.0.1:{server.server_port}/?view=analysis&item={fixture.item_id}&section=statistics')
            page.locator('#analysis-desktop-content [data-analysis-page="statistics"]').wait_for(state='visible')
        browser.close()
        print('PASS: screenshots and responsive checks')
finally:
    server.shutdown()
    server.server_close()
    fixture.doCleanups()
