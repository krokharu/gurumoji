"""公開版のモデル選択を合成画面と合成APIだけで検証する。"""
from pathlib import Path
import json, mimetypes, runpy, sys
from urllib.parse import unquote, urlparse
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from playwright.sync_api import sync_playwright, expect
root, out = (Path(value).resolve() for value in sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
assets = runpy.run_path(str(root / 'src/gurumoji/web/assets.py'))
env = Environment(loader=FileSystemLoader(root / 'src/gurumoji/templates'), undefined=StrictUndefined, autoescape=select_autoescape(['html']))
html = env.get_template('index.html').render(
    app_name='Gurumoji 検証画面', app_version='test',
    application_styles=assets['application_styles'](), application_scripts=assets['application_scripts'](),
    local_llm_label='Synthetic local LLM', local_llm_short_label='Local',
    runtime=dict(label='synthetic', native_file_dialog=False, colab=False, source_path_example='/synthetic/input.wav', qwen_setup_note='合成のQwen案内', haas_setup_note='合成のHaas案内'),
    url_for=lambda endpoint, filename: '/static/' + filename)
errors, blocked, checks = [], [], []
static = root / 'src/gurumoji/static'
models = {name: dict(status='cached', message='合成モデル') for name in ('tiny', 'base', 'small', 'medium', 'large-v3')}
config = dict(ok=True, huggingface=True, runtime=dict(browser_upload=True), default_output_dir='/synthetic/output',
    machine=dict(cpu=dict(available=True, name='Synthetic CPU'), gpu=dict(cuda_available=True, name='Synthetic GPU'), recommended=dict(device='cpu', diarization_device='cpu', model_name='base')),
    transcription_readiness=dict(whisperx=dict(blockers=[], notes=[], models=dict(cpu=models,cuda=models)), haas_ja=dict(blockers=[], notes=[]), qwen3_nemotron=dict(blockers=[], notes=[])))
def respond(route):
    url = urlparse(route.request.url)
    if url.hostname != 'haas-picker.invalid':
        blocked.append(route.request.url); route.abort(); return
    if url.path == '/':
        route.fulfill(body=html, content_type='text/html; charset=utf-8'); return
    if url.path.startswith('/static/'):
        path = (static / unquote(url.path[8:])).resolve()
        if path.is_relative_to(static) and path.is_file():
            route.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        else:
            blocked.append(url.path); route.fulfill(status=404)
        return
    data = {}
    if url.path == '/api/config': data = config
    elif url.path == '/api/jobs/active': data = dict(job=None)
    elif url.path == '/api/custom-vocabulary': data = dict(terms=[])
    elif url.path == '/api/speakers': data = dict(speakers=[], registry_revision=0)
    elif url.path == '/api/library': data = dict(items=[], groups=[], data_groups=[], tags=[], total=0, has_more=False, facets=dict(speakers=[], emotions=[]))
    elif url.path == '/api/library/catalog': data = dict(items=[], groups=[], tags=[], definitions=[])
    elif url.path == '/api/training': data = dict(event_count=0,ready_count=0)
    elif not url.path.startswith('/api/'):
        blocked.append(url.path)
    route.fulfill(json=data)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge',headless=True)
    context = browser.new_context(viewport=dict(width=1360,height=900),reduced_motion='reduce')
    context.route('**/*',respond)
    page = context.new_page()
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1')")
    page.goto('https://haas-picker.invalid/#/new',wait_until='networkidle')
    page.evaluate("document.body.classList.remove('booting'); document.querySelector('#boot-splash')?.remove()")
    page.wait_for_function("configLoadState === 'loaded'")
    tile = page.locator('[data-tile=model]')
    def choose(label):
        tile.click()
        page.get_by_role('option', name=label).click()
    choose('Haas-ja-v1.0')
    expect(page.locator('#transcription-backend')).to_have_value('haas_ja')
    expect(page.locator('[name=language]')).to_have_value('ja')
    expect(page.locator('#transcription-device')).to_have_value('cuda')
    assert page.locator('#transcription-device option[value=cpu]').evaluate('(el)=>el.disabled')
    expect(page.locator('#model-name')).to_be_disabled()
    expect(tile).to_be_enabled()
    expect(tile).to_contain_text('Haas')
    expect(tile).to_have_attribute('title', '認識モデル: Haas-ja-v1.0（公式・実験的） + Nemotron 3 Diarization')
    assert page.evaluate("new FormData(form).get('transcription_backend')") == 'haas_ja'
    assert page.evaluate("new FormData(form).get('device')") == 'cuda'
    checks.append('Haasをメニューから選択し、方式・日本語・GPU・表示・送信値が一致')
    for width,height in ((1360,900),(1800,1000),(1280,720)):
        page.set_viewport_size(dict(width=width,height=height))
        tile.click()
        option = page.get_by_role('option',name='Haas-ja-v1.0')
        expect(option).to_have_attribute('aria-selected','true')
        box = option.bounding_box()
        assert box['y'] >= 0 and box['y']+box['height'] <= height, box
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(out/f'haas-menu-{width}.png'))
        page.keyboard.press('Escape')
    checks.append('1280・1360・1800pxの選択表示と画面内配置')
    choose('WhisperX small')
    expect(page.locator('#transcription-backend')).to_have_value('whisperx')
    expect(page.locator('#model-name')).to_be_enabled()
    expect(page.locator('#model-name')).to_have_value('small')
    assert not page.locator('#transcription-device option[value=cpu]').evaluate('(el)=>el.disabled')
    assert page.evaluate("new FormData(form).get('model_name')") == 'small'
    tile.click(); expect(page.get_by_role('option',name='WhisperX small')).to_have_attribute('aria-selected','true'); page.keyboard.press('Escape')
    choose('Qwen3-ASR')
    expect(page.locator('#transcription-backend')).to_have_value('qwen3_nemotron')
    expect(tile).to_contain_text('Qwen3'); expect(tile).to_be_enabled()
    choose('Haas-ja-v1.0')
    page.locator('#stitch-preset-name').fill('合成Haas設定')
    page.locator('#stitch-preset-save').click()
    choose('WhisperX base')
    page.locator('#stitch-preset').select_option('user:合成Haas設定')
    expect(page.locator('#transcription-backend')).to_have_value('haas_ja')
    expect(tile).to_contain_text('Haas'); expect(tile).to_be_enabled()
    checks.append('WhisperX復帰・Qwen切替・Haasプリセット再適用')
    page.evaluate("tokenConfigSnapshot.transcription_readiness.haas_ja.blockers=['合成: Haas環境が未準備です']; updateCreateSummary()")
    assert '合成: Haas環境が未準備です' in page.evaluate('createReadiness().blockers')
    expect(page.locator('#start-button')).to_be_disabled()
    checks.append('環境未準備の案内と開始拒否を維持')
    page.set_viewport_size(dict(width=390,height=844))
    page.evaluate("openSettingsPanel('recognition')")
    page.locator('#transcription-backend').select_option('whisperx')
    page.locator('#transcription-backend').select_option('haas_ja')
    expect(page.locator('[data-choice-recognition-model]')).to_contain_text('Haas-ja-v1.0')
    expect(page.locator('#haas-backend-note')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(out/'haas-mobile.png'))
    checks.append('390pxの詳細設定からも選択・要約・案内が同期')
    browser.close()
assert not errors, errors
assert not blocked, blocked
(out/'verification.json').write_text(json.dumps(dict(checks=checks,page_errors=errors,blocked_requests=blocked,real_data_used=False),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(checks=len(checks),page_errors=errors,blocked_requests=blocked)))
