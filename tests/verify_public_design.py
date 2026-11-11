"""公開用デザインを実データ・サーバーなしで検証する。"""
from pathlib import Path
import ast, importlib.util, json, mimetypes, subprocess, sys
from urllib.parse import unquote, urlparse
from playwright.sync_api import sync_playwright, expect
root, out = map(lambda value: Path(value).resolve(), sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
static = root / 'src/gurumoji/static'
renderer = Path(__file__).parent / 'dom/render_fixture.py'
html = subprocess.check_output([sys.executable, str(renderer), str(root)], encoding='utf-8')
errors, missing, checks = [], [], []
def respond(route):
    url = urlparse(route.request.url)
    assert url.hostname == 'public-design.invalid'
    if url.path == '/':
        route.fulfill(body=html, content_type='text/html; charset=utf-8')
        return
    if url.path.startswith('/static/'):
        path = (static / unquote(url.path[8:])).resolve()
        if path.is_relative_to(static) and path.is_file():
            route.fulfill(body=path.read_bytes(), content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        else:
            missing.append(url.path)
            route.fulfill(status=404)
        return
    data = {'items': [], 'runs': [], 'records': []}
    if url.path == '/api/config':
        data = {'ok': True, 'runtime': {'browser_upload': True}, 'default_output_dir': '/synthetic/output'}
    elif url.path == '/api/jobs/active': data = {'job': None}
    elif url.path == '/api/custom-vocabulary': data = {'terms': []}
    elif url.path == '/api/speakers': data = {'speakers': [], 'registry_revision': 0}
    elif url.path == '/api/library/catalog': data = {'items': [], 'groups': [], 'tags': [], 'definitions': []}
    elif url.path == '/api/library': data = {'items': [], 'groups': [], 'data_groups': [], 'tags': [], 'facets': {'speakers': [], 'emotions': []}, 'total': 0, 'has_more': False}
    route.fulfill(json=data)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context()
    context.route('**/*', respond)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://public-design.invalid/', wait_until='networkidle')
    page.evaluate("document.body.classList.remove('booting'); document.querySelector('#boot-splash')?.remove()")
    for width in (2542, 1800, 1360, 390):
        page.set_viewport_size({'width': width, 'height': 1290 if width > 400 else 844})
        expect(page.locator('#create-view')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        if width >= 1280:
            expect(page.locator('.stitch-topbar')).to_be_visible()
            expect(page.locator('.stitch-speakers')).to_be_visible()
            expect(page.locator('.stitch-outline')).to_be_visible()
            page.locator('#stitch-confirm-toggle').click()
            expect(page.locator('#stitch-confirm-toggle')).to_have_attribute('aria-expanded', 'true')
            page.keyboard.press('Escape')
            expect(page.locator('#stitch-confirm-toggle')).to_have_attribute('aria-expanded', 'false')
        page.locator('#open-general-settings').click()
        expect(page.locator('#general-settings-dialog')).to_be_visible()
        page.locator('input[name=gs-theme][value=teal]').check()
        expect(page.locator('html')).to_have_attribute('data-theme', 'teal')
        page.locator('input[name=gs-theme][value=forest]').check()
        page.locator('#general-settings-dialog button[type=submit]').click()
        page.screenshot(path=str(out / f'design-{width}.png'), full_page=True)
        checks.append({'width': width, 'layout': True, 'settings': True})
    page.set_viewport_size({'width': 1800, 'height': 1000})
    page.locator('#prior-data-button').click()
    expect(page.locator('#prior-data-menu')).to_be_visible()
    page.locator('#show-speakers-button').click()
    expect(page.locator('#speaker-registry-card')).to_be_visible()
    page.locator('#show-new-button').click()
    expect(page.locator('#create-view')).to_be_visible()
    page.locator('#stitch-outline-text').fill('検証用「専門用語」と Kubernetes')
    expect(page.locator('[name=prior_outline]')).to_have_value('検証用「専門用語」と Kubernetes')
    checks.append({'navigation_and_outline': True})
    browser.close()
for path in root.joinpath('src/gurumoji').rglob('*.py'):
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
spec = importlib.util.spec_from_file_location('prior_context', root / 'src/gurumoji/services/transcription/prior_context.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
speakers = module.normalize_prior_speakers('[{"name":"検証話者", "role":"司会"}]')
assert speakers == (('検証話者', '司会'),)
assert module.recognition_hint_terms(('検証語',), speakers, '「専門用語」と Kubernetes') == ('検証語', '検証話者', '専門用語', 'Kubernetes')
try:
    module.normalize_prior_speakers('{}')
except ValueError:
    pass
else:
    raise AssertionError('不正な事前話者情報を受理')
assert not errors, errors
assert not missing, missing
result = {'checks': checks, 'page_errors': errors, 'missing_assets': missing, 'python_syntax': 'passed', 'prior_context': 'passed', 'real_data_used': False}
(out / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))