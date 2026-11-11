"""出荷画面を合成APIだけで操作するブラウザー試験。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = args.source_root.resolve()
args.output.mkdir(parents=True, exist_ok=True)
fixture = Path(__file__).resolve().parents[1] / 'dom/render_fixture.py'
html = subprocess.check_output([sys.executable, str(fixture), str(root)], encoding='utf-8')
static = root / 'src/gurumoji/static'
methods = ['participation', 'conversation_dynamics', 'label_frequency', 'cross_tabulation']
posts, external, errors, unexpected = [], [], [], []
source = dict(source_analysis_id='result_old', source_run_id='run_old', source_result_id='result_old',
              original_question='合成会話の問い', source_revision=1, analysis_revision=2,
              content=dict(summary='合成の保存済み結果'))
progress = [dict(id=method, status='succeeded', task_id='task_'+method, result_id='result_'+method,
                 review=dict(disposition='adopt', reason='合成結果を確認'), core_integrated=True, complete=True)
            for method in methods]
run = dict(run_id='run_new', item_id='synthetic', status='stopped', phase='stopped',
           source_revision=1, analysis_revision=2, analysis_result_id='result_new',
           stop_reason='human_review_required', analysis_processing_complete=True,
           human_review_status='required', review_status='reviewed',
           config=dict(question='合成会話の問い'), required_methods_progress=progress,
           publication=dict(save_status='saved', result_run_id='result_new', publication_status='review_required',
                            publication_targets=['input', 'orchestrator', 'visualization'], outcomes={}),
           tasks=[], results=[], events=[], issues=[], roles=[], usage={}, allowed_actions=[], current_view={})
cross = dict(result_id='result_cross', validation_status='valid', raw=dict(
    method_id='cross_tabulation', label_field='codes', annotation_version=0, availability='partial',
    denominator=6, observed_count=5, missing_count=1, missing_speaker_count=0, missing_label_count=1,
    row_totals=[dict(speaker='A', denominator=3, missing_count=1), dict(speaker='B', denominator=3, missing_count=0)],
    column_totals=[dict(label='価格', count=3), dict(label='味', count=4)],
    rows=[dict(speaker=speaker, label=label, count=count, row_proportion=count/3)
          for speaker, label, count in [('A', '価格', 2), ('A', '味', 1), ('B', '価格', 1), ('B', '味', 3)]],
    limitations=['複数ラベルは合計100%を超える場合があります。']))
progress[-1]['calculation'] = dict(availability='partial', denominator=6, observed_count=5, missing_count=1)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport=dict(width=1360, height=1000), reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1');")
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(req):
        parsed = urlparse(req.request.url)
        path = unquote(parsed.path)
        if parsed.hostname != 'gurumoji.invalid':
            external.append(req.request.url); req.abort(); return
        if path == '/':
            req.fulfill(body=html, content_type='text/html'); return
        if path.startswith('/static/'):
            file = (static / path.removeprefix('/static/')).resolve()
            if static in file.parents and file.is_file(): req.fulfill(path=str(file)); return
            req.fulfill(status=404, body=''); return
        if path.startswith('/api/'):
            if path.endswith('/reanalysis/source/result_old'):
                req.fulfill(json={'source': source}); return
            if path.endswith('/analysis/orchestration') and req.request.method == 'POST':
                posts.append(req.request.post_data_json); req.fulfill(status=202, json={'run': run}); return
            if path.endswith('/analysis/orchestration/run_new'):
                req.fulfill(json={'run': run}); return
            if path.endswith('/analysis/orchestration/run_new/results'):
                req.fulfill(json={'raw_results': [cross]}); return
            if path == '/api/config':
                req.fulfill(json={'ok': True, 'runtime': {'browser_upload': True}}); return
            if path == '/api/jobs/active': req.fulfill(json={'job': None}); return
            if path == '/api/speakers': req.fulfill(json={'speakers': [], 'registry_revision': 0}); return
            if path == '/api/library':
                req.fulfill(json={'items': [], 'groups': [], 'pagination': {'offset': 0, 'limit': 50, 'total': 0, 'has_more': False}}); return
            if path == '/api/library/interview-comparison/runs': req.fulfill(json={'runs': []}); return
            if path in ['/api/custom-vocabulary', '/api/training', '/api/obsidian/obussql']:
                req.fulfill(json={}); return
            unexpected.append(path); req.fulfill(status=404, json={'error': '合成未定義'}); return
        unexpected.append(path); req.abort()
    page.route('**/*', route)
    page.goto('https://gurumoji.invalid/#/new')
    page.wait_for_function("configLoadState==='loaded'")
    page.evaluate("""() => {
        analysisState.itemId='synthetic';
        analysisState.data={item:{id:'synthetic',source_name:'合成会話',revision_count:1,analysis_revision:2}};
        analysisState.config={research_question:'合成会話の問い'};
        analysisState.dirty=false; preparationDirty=false;
        document.querySelector('#analysis-run-dialog').showModal();
    }""")
    page.locator('#orchestration-open').click()
    expect(page.locator('#orchestration-settings')).to_be_visible()
    for method in methods:
        page.locator(f'input[name="orchestration_required_method"][value="{method}"]').check()
    page.locator('#orchestration-source-analysis-id').fill('result_old')
    page.locator('#orchestration-source-load').click()
    expect(page.locator('#orchestration-source-status')).to_contain_text('参照結果を確認しました')
    page.locator('#orchestration-human-prompt').fill('合成の反例と欠測を再検討')
    page.locator('#orchestration-publication-all').check()
    for width in [1360, 390]:
        page.set_viewport_size(dict(width=width, height=1000))
        page.locator('#orchestration-human-prompt').focus()
        assert page.evaluate("document.activeElement.id") == 'orchestration-human-prompt'
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('#orchestration-settings').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
        page.screenshot(path=str(args.output / f'settings-{width}.png'), full_page=True)
        page.locator('input[name="orchestration_required_method"][value="label_frequency"]').focus()
        page.screenshot(path=str(args.output / f'methods-{width}.png'), full_page=True)
    page.locator('#orchestration-start').click()
    expect(page.locator('#orchestration-live')).to_be_visible()
    expect(page.locator('#orchestration-run-identity')).to_contain_text('run_new')
    expect(page.locator('#orchestration-result-identity')).to_contain_text('result_new')
    expect(page.locator('#orchestration-processing-state')).to_contain_text('分析処理は完了')
    expect(page.locator('#orchestration-save-status')).to_contain_text('保存済み')
    expect(page.locator('#orchestration-publication-scope')).to_contain_text('保留')
    expect(page.locator('#orchestration-required-progress li')).to_have_count(4)
    assert all(row.get_attribute('data-complete') == 'true' for row in page.locator('#orchestration-required-progress li').all())
    assert len(posts) == 1 and posts[0]['required_methods'] == methods
    assert posts[0]['source_analysis_id'] == 'result_old' and posts[0]['human_prompt'] == '合成の反例と欠測を再検討'
    for width in [1360, 390]:
        page.set_viewport_size(dict(width=width, height=1000))
        page.locator('#orchestration-live-close').focus()
        assert page.evaluate("document.activeElement.id") == 'orchestration-live-close'
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('#orchestration-live').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
        page.screenshot(path=str(args.output / f'completed-{width}.png'), full_page=True)
        page.locator('#orchestration-save-status').scroll_into_view_if_needed()
        page.screenshot(path=str(args.output / f'output-{width}.png'), full_page=True)
    page.locator('#orchestration-results').click()
    expect(page.locator('#orchestration-result-content table tbody tr')).to_have_count(2)
    expect(page.locator('#orchestration-result-content table tbody tr').first).to_contain_text('2（66.7%）')
    expect(page.locator('#orchestration-result-content table tbody tr').last).to_contain_text('3（100%）')
    for width in [1360, 390]:
        page.set_viewport_size(dict(width=width, height=1000))
        page.locator('.orchestration-crosstab-scroll').scroll_into_view_if_needed()
        page.locator('.orchestration-crosstab-scroll').focus()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('.orchestration-crosstab').screenshot(path=str(args.output / f'crosstab-{width}.png'))
    assert not errors, errors
    assert not external, external
    assert not unexpected, unexpected
    browser.close()
result = dict(result='passed', viewports=[1360, 390], post_count=len(posts),
              page_errors=errors, external_requests=external, unexpected_requests=unexpected,
              backend='合成応答のみ')
(args.output / 'browser-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
