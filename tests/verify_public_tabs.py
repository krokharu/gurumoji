"""実データに接続せず、現行テンプレートの独立タブをEdgeで検証する。"""
from pathlib import Path
import json
import mimetypes
import subprocess
import sys
from urllib.parse import unquote, urlparse
from playwright.sync_api import sync_playwright, expect

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
static = root / 'src/gurumoji/static'
renderer = Path(__file__).parent / 'dom/render_fixture.py'
html = subprocess.check_output([sys.executable, str(renderer), str(root)], encoding='utf-8')
errors, blocked, checks, requests = [], [], [], []
folders, tags, groups = [], [], []

def respond(route):
    request = route.request
    url = urlparse(request.url)
    requests.append(url.path)
    if url.hostname != 'prior-data.invalid':
        blocked.append(request.url)
        route.abort()
        return
    if url.path == '/':
        route.fulfill(body=html, content_type='text/html; charset=utf-8')
        return
    if url.path.startswith('/static/'):
        path = (static / unquote(url.path[len('/static/'):])).resolve()
        if path.is_relative_to(static) and path.is_file():
            route.fulfill(body=path.read_bytes(), content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        else:
            blocked.append(url.path)
            route.fulfill(status=404)
        return
    data = {}
    if url.path == '/api/config':
        data = {'ok': True, 'runtime': {'browser_upload': True}, 'default_output_dir': '/synthetic/output'}
    elif url.path == '/api/jobs/active':
        data = {'job': None}
    elif url.path == '/api/custom-vocabulary':
        data = {'terms': []}
    elif url.path == '/api/speakers':
        data = {'speakers': [], 'registry_revision': 0}
    elif url.path == '/api/library/catalog':
        data = {'items': [], 'groups': groups, 'tags': tags, 'definitions': []}
    elif url.path == '/api/library':
        data = {'items': [], 'groups': folders, 'data_groups': groups, 'tags': tags,
                'facets': {'speakers': [], 'emotions': []}, 'total': 0, 'has_more': False}
    elif url.path == '/api/library/groups' and request.method == 'POST':
        data = {'id': 'synthetic-folder', 'name': request.post_data_json['name'], 'item_count': 0}
        folders.append(data)
    elif url.path == '/api/library/tags' and request.method == 'POST':
        data = {'tag_id': 'synthetic-tag', 'name': request.post_data_json['name'], 'item_count': 0}
        tags.append(data)
    elif url.path == '/api/library/data-groups' and request.method == 'POST':
        data = {'group_id': 'synthetic-group', 'name': request.post_data_json['name'],
                'kind': 'manual', 'item_count': 0, 'item_ids': []}
        groups.append(data)
    elif url.path == '/api/training':
        data = {'event_count': 0, 'ready_count': 0}
    elif url.path.startswith('/api/'):
        data = {'items': [], 'runs': [], 'records': []}
    else:
        blocked.append(url.path)
    route.fulfill(json=data)

panels = [('show-new-button', 'new', 'create-view'), ('show-library-button', 'data', 'library-card'),
          ('show-analysis-button', 'analysis', 'analysis-card'), ('show-speakers-button', 'speakers', 'speaker-registry-card'),
          ('prior-presets-button', 'presets', 'preset-data-card'), ('prior-folders-button', 'folders', 'library-group-dialog'),
          ('prior-catalog-button', 'catalog', 'data-catalog-dialog'), ('prior-internal-button', 'internal', 'internal-data-card')]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context()
    context.route('**/*', respond)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://prior-data.invalid/', wait_until='networkidle')
    page.evaluate("document.body.classList.remove('booting'); document.querySelector('#boot-splash')?.remove()")
    expect(page.locator('.app-nav [role=tab]')).to_have_count(8)
    assert page.locator('#prior-data-menu').count() == 0
    for width in (1800, 1360, 390):
        page.set_viewport_size({'width': width, 'height': 1000 if width > 400 else 844})
        for button, route, panel in panels:
            page.locator('#' + button).click()
            expect(page.locator('#' + panel)).to_be_visible()
            expect(page.locator('#' + button)).to_have_attribute('aria-selected', 'true')
            assert page.url.endswith('#/' + route), page.url
            assert page.locator('.app-nav [aria-selected=true]').count() == 1
            for other_button, other_route, other_panel in panels:
                if panel != other_panel:
                    expect(page.locator('#' + other_panel)).to_be_hidden()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, panel, '横方向のはみ出し')
            header = page.locator('.app-bar').bounding_box()['height']
            assert abs(float(page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--app-bar-height')").strip('px ')) - header) <= 1
            checks.append({'width': width, 'route': route, 'passed': True})
        page.screenshot(path=str(out / f'tabs-{width}.png'))
    page.locator('#prior-presets-button').click()
    page.locator('#preset-manager-select').select_option('mode:chat')
    page.locator('#preset-manager-name').fill('検証用プリセット')
    page.locator('#preset-manager-save').click()
    expect(page.locator('#preset-manager-status')).to_contain_text('保存しました')
    page.locator('#preset-manager-select').select_option('mode:meeting')
    page.locator('#preset-manager-select').select_option('user:検証用プリセット')
    expect(page.locator('input[name=conversation_mode][value=chat]')).to_be_checked()
    page.reload(wait_until='networkidle')
    page.evaluate("document.body.classList.remove('booting'); document.querySelector('#boot-splash')?.remove()")
    expect(page.locator('#preset-data-card')).to_be_visible()
    page.locator('#preset-manager-select').select_option('user:検証用プリセット')
    expect(page.locator('#preset-manager-delete')).to_be_visible()
    page.locator('#preset-manager-delete').click()
    expect(page.locator('#preset-manager-status')).to_contain_text('削除しました')
    assert page.locator('#preset-manager-select option[value^="user:"]').count() == 0
    checks.append({'presets': '保存・適用・再読み込み・削除', 'passed': True})
    page.locator('#prior-folders-button').click()
    page.locator('#library-group-name').fill('検証用フォルダー')
    page.locator('#library-group-create-form [type=submit]').click()
    expect(page.locator('#library-group-message')).to_contain_text('作成しました')
    expect(page.locator('#library-group-list input')).to_have_value('検証用フォルダー')
    page.locator('#prior-catalog-button').click()
    page.locator('#data-tag-name').fill('検証用タグ')
    page.locator('#data-tag-form [type=submit]').click()
    expect(page.locator('#data-catalog-status')).to_contain_text('タグを作成しました')
    page.locator('#data-group-name').fill('検証用グループ')
    page.locator('#data-group-form [type=submit]').click()
    expect(page.locator('#data-catalog-status')).to_contain_text('分析グループを保存しました')
    checks.append({'management': 'フォルダー・タグ・分析グループの作成', 'passed': True})
    page.reload(wait_until='networkidle')
    page.evaluate("document.body.classList.remove('booting'); document.querySelector('#boot-splash')?.remove()")
    expect(page.locator('#data-catalog-dialog')).to_be_visible()
    expect(page.locator('#data-catalog-status')).to_have_text('')
    page.locator('#prior-internal-button').click()
    page.go_back(wait_until='networkidle')
    expect(page.locator('#data-catalog-dialog')).to_be_visible()
    page.go_forward(wait_until='networkidle')
    expect(page.locator('#internal-data-card')).to_be_visible()
    page.locator('#prior-internal-button').focus()
    page.keyboard.press('Home')
    expect(page.locator('#show-new-button')).to_be_focused()
    expect(page.locator('#internal-data-card')).to_be_visible()
    page.keyboard.press('Enter')
    expect(page.locator('#create-view')).to_be_visible()
    checks.append({'navigation': 'URL復元・戻る・進む・キーボード移動', 'passed': True})
    page.locator('#show-speakers-button').click()
    page.evaluate('speakerRegistryDirty = true')
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.locator('#prior-presets-button').click()
    expect(page.locator('#speaker-registry-card')).to_be_visible()
    assert page.url.endswith('#/speakers')
    page.once('dialog', lambda dialog: dialog.accept())
    page.locator('#prior-presets-button').click()
    expect(page.locator('#preset-data-card')).to_be_visible()
    checks.append({'unsaved': '話者の未保存編集を保護して新タブへの移動を中止できる', 'passed': True})
    # 公開準備中の機能は、案内表示と通信の両方を確認する。
    page.set_viewport_size({'width': 1800, 'height': 1000})
    page.locator('#show-analysis-button').click()
    expect(page.locator('.analysis-coming-soon')).to_be_visible()
    expect(page.locator('#analysis-run-button')).to_be_hidden()
    page.locator('#prior-internal-button').click()
    expect(page.locator('#internal-data-card')).to_contain_text('Coming Soon')
    assert page.locator('[data-open-obussql], #finish-in-obsidian, [data-obsidian-watcher-pill]').count() == 0
    assert not [p for p in requests if p.startswith('/api/') and any(s in p for s in ('/analysis', '/obussql', '/obsidian'))]
    checks.append({'public_exclusions': '分析・内部データはComing Soon、Obsidian・ObusSQLのUIと通信なし', 'passed': True})
    page.locator('#show-new-button').click()
    page.locator('#stitch-person-name').fill('合成参加者')
    page.locator('#stitch-person-role').fill('司会')
    page.locator('#stitch-person-add').click()
    people = json.loads(page.locator('#stitch-prior-speakers').input_value())
    assert people == [{'name': '合成参加者', 'role': '司会'}], people
    page.locator('[name=prior_outline]').fill('検証用の議題')
    assert page.locator('[name=prior_outline]').input_value() == '検証用の議題'
    checks.append({'prior_inputs': '参加者・役割・議題を文字起こしフォームへ反映', 'passed': True})
    page.locator('#open-general-settings').click()
    expect(page.locator('#gs-language')).to_be_disabled()
    expect(page.locator('#gs-language-title')).to_contain_text('Coming Soon')
    page.locator('[name=gs-theme][value=mocha]').check()
    expect(page.locator('html')).to_have_attribute('data-theme', 'mocha')
    page.locator('#gs-folder-input').fill('/synthetic/registered-output')
    page.locator('#gs-folder-add').click()
    expect(page.locator('#gs-folder-list')).to_contain_text('/synthetic/registered-output')
    page.locator('[name=gs-mode][value=group_interview]').check()
    settings = page.evaluate("JSON.parse(localStorage.getItem('gurumoji.generalSettings.v1'))")
    assert settings['mode'] == 'group_interview' and settings['defaultFolder'] == '/synthetic/registered-output'
    page.locator('#general-settings-dialog button[type=submit]').click()
    page.reload(wait_until='networkidle')
    page.evaluate("document.body.classList.remove('booting'); document.querySelector('#boot-splash')?.remove()")
    expect(page.locator('html')).to_have_attribute('data-theme', 'mocha')
    expect(page.locator('[name=conversation_mode][value=group_interview]')).to_be_checked()
    assert page.locator('#stitch-output-dir').input_value() == '/synthetic/registered-output'
    page.screenshot(path=str(out/'public-new-screen.png'))
    checks.append({'general_settings': 'テーマ・保存先・モードを保存し再読込で復元', 'passed': True})
    browser.close()
assert not errors, errors
assert not blocked, blocked
result = {'checks': checks, 'page_errors': errors, 'blocked_requests': blocked,
          'isolation': '全リクエストを合成応答へ差し替え。アプリ起動・実DB・runtime・Vaultアクセスなし。'}
(out / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'checks': len(checks), 'page_errors': errors, 'blocked_requests': blocked}))
