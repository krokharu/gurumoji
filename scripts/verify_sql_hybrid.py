"""合成原文だけでSQL・ハイブリッドの実モデル境界と表示を確認する。"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/validation/sql-hybrid-selection-20261110'
sys.path.insert(0, str(ROOT / 'src'))


def model_check():
    from gurumoji.services import evidence_retrieval as sql
    from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
    rows = [dict(evidence_id='synthetic-one', utterance_id='u1', text='合成観察：測定値13。撤回した対象を除く。', speaker='A', start=0, end=1),
            dict(evidence_id='synthetic-two', utterance_id='u2', text='合成観察：測定値27。不明を陰性に含めない。', speaker='B', start=1, end=2)]
    calls = []
    def provider(provider, key, model, system, user, stage, schema, check, usage, base, timeout, **kwargs):
        check()
        body = {'model': model, 'temperature': 0, 'max_tokens': 1200, 'reasoning_effort': 'none',
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema', 'json_schema': {'name': 'synthetic_selection', 'strict': True, 'schema': schema}}}
        start = time.perf_counter()
        request = urllib.request.Request('http://127.0.0.1:1234/v1/chat/completions',
            data=json.dumps(body, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as result:
            response = json.load(result)
        calls.append({'elapsed_seconds': time.perf_counter()-start, 'response': response})
        usage({'reported': False})
        return json.loads(response['choices'][0]['message']['content'])
    resolve, runner = make_orchestration_adapters(call_ai_json=provider,
        load_token_config=lambda: SimpleNamespace(lmstudio_base_url='http://127.0.0.1:1234/v1'),
        configured_ai_credentials=lambda *_: ('', 'google/gemma-4-12b-qat'))
    results = []
    for mode in ('sql', 'hybrid'):
        options = resolve({'evidence_mode': mode, 'metric_codec_version': 0, 'local_reasoning': 'off'})
        raw = runner('interpretation', {'question': '測定値27の発話だけについて、1件のobservationとその根拠IDを返す。',
            'raw_evidence': rows}, options, lambda: None, lambda _: None)
        original = copy.deepcopy(raw)
        resolved = sql.resolve_citations(rows, raw, allowed_ids={r['evidence_id'] for r in rows}, dataset_version='synthetic-fixed-v1')
        assert resolved['sources'] == [rows[1]], (mode, raw, resolved)
        assert raw == original
        results.append({'mode': mode, 'raw': raw, 'resolved': resolved, 'measurement': calls[-1]})
        print(mode, 'one model call, source matched', calls[-1]['elapsed_seconds'], flush=True)
    assert len(calls) == 2
    (OUT / 'model.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


def browser_check():
    from playwright.sync_api import sync_playwright
    html = subprocess.check_output([str(ROOT / '.venv/Scripts/python.exe'),
        str(ROOT / 'output/validation/development-assets-20261016/tests/dom/render_fixture.py'), str(ROOT)], encoding='utf-8')
    styles = re.findall(r'href="(/static/[^"?]+\.css)', html)
    html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<link\b[^>]*>', '', html)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1100, 'height': 900})
        page.route('**/*', lambda route: route.abort())
        page.set_content(html)
        for source in styles:
            page.add_style_tag(content=(ROOT / 'src/gurumoji' / source.lstrip('/')).read_text(encoding='utf-8'))
        page.evaluate("document.querySelector('#orchestration-settings').showModal()")
        select = page.locator('#orchestration-evidence-mode')
        assert select.input_value() == 'sql'
        select.select_option('hybrid')
        assert select.input_value() == 'hybrid'
        for name, width, height in [('desktop', 1100, 900), ('mobile', 412, 915)]:
            page.set_viewport_size({'width': width, 'height': height})
            select.scroll_into_view_if_needed()
            assert select.is_visible()
            box = select.bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1, box
            page.screenshot(path=str(OUT / (name + '.png')))
        browser.close()
    print('Edge: desktop and mobile selection passed', flush=True)


def record_check():
    log = (OUT / 'unittest.log').read_text(encoding='utf-8')
    assert re.search(r'Ran 140 tests', log) and log.strip().endswith('OK')
    models = json.loads((OUT / 'model.json').read_text(encoding='utf-8'))
    assert [r['mode'] for r in models] == ['sql', 'hybrid']
    assert all(r['resolved']['sources'][0]['evidence_id'] == 'synthetic-two' for r in models)
    assert all((OUT / f'{name}.png').is_file() for name in ('desktop', 'mobile'))
    targets = ['src/gurumoji/services/evidence_retrieval.py', 'src/gurumoji/services/maf_dev_bridge.py',
        'src/gurumoji/services/model_context.py', 'src/gurumoji/services/analysis_orchestration_adapters.py',
        'src/gurumoji/analysis_orchestration.py', 'src/gurumoji/static/analysis-orchestration.js',
        'src/gurumoji/templates/views/analysis-orchestration.html', 'docs/OBUSSQL.md']
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in targets}
    report = {'python_tests': 140, 'dom_tests': 30, 'real_model_calls': 2,
        'real_browser': ['Edge desktop 1100x900', 'Edge mobile 412x915'], 'default': 'sql',
        'hybrid': '既存分析AIの引用IDをSQLで原文に復元。追加AI呼出しなし。',
        'adapter_version': 'core-handler-prompts-52-sql-evidence-hybrid', 'source_sha256': hashes,
        'limitations': ['全分析をSQLだけで行う機能ではない。解釈AIと既存の決定的集計は継続する。',
            'SQLでの原文照合は、AIの意味解釈や研究上の妥当性を承認しない。',
            '実研究データと実Vaultは試験に使わず、実利用者アプリは再起動していない。',
            '実モデルは各方式1件の小規模確認。過去のID専用ベンチマークと処理内容は異なるため速度効果を転用しない。']}
    (OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    note = ROOT / 'output/validation/development-assets-20261016/docs/program-vault/60-Operations/20-Development/gurumoji-improvement-session/02-topics/16-section.md'
    title = '## 2026-11-10: SQLを標準にしてハイブリッドを選択可能にする'
    assert title not in note.read_text(encoding='utf-8')
    text = f'''

{title}

- 利用者の「SQLを基本として、ハイブリット方式を選択肢として使えるようにして」に対応。利用者checkoutはkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486と既存未コミット変更。対象以外の編集を保持し、commit/pushなし。
- 対象は自律分析の根拠取得・引用原文の復元。解釈には両方式で既存AIを使い、数量・統計は既存の決定的処理を維持する。自由な研究質問への全分析をSQLだけで完結する機能ではない。MTPは生成エンジンの設定として両方式と独立に併用できる。
- 新規runのevidence_modeはsqlが既定。hybridも明示選択でき、不正値は開始前に拒否する。分析設定の「根拠の取得方式」、POST開始payload、保存config、履歴表示まで接続。再開時に別方式へ暗黙に変えない。adapter契約はcore-handler-prompts-52-sql-evidence-hybridへ更新し、旧runを新方式として再開しない。
- SQL索引はrun単位の一時SQLite。固定発話をJSONとhash付きで登録し、256件ずつ全候補をparameter bindingで取得する。指定ID、全文一致、最大8検索文字列で順位付けし、完全な発話単位で上限内に選んで発話順に戻す。本文だけでなく呼出し側の投影項目（ID・話者・時刻等）と型を照合する。MAFではrun中に索引を再利用し、終了時にclose。通常adapterでもSQL取得を使う。管理ノートの読取プレビューとcodecは従来のObusSQL接続を維持する。
- ハイブリッドは追加の検索AIを呼ばず、既存分析AIのclaims/issues/label_patches/label_definitions/label_requirements/claim_verdictsの引用IDを使用する。将来読むintents/analysis_requestsの対象IDは引用と区別する。原応答を従来のraw_jsonへ保存して既存検証を通した後、SQLで復元した原文・話者・時刻・入力版・hashを既存result metadataのevidence_resolutionへ追加する。AI原応答を書き換えず、未提示・不存在の引用IDと件数/文字数上限超過は隔離する。SQLへの自動fallbackはしない。引用原文は保存結果ビューへtextContentで表示する。
- 既存SQLカラム・保存先・Vault同期を変更しない。追加は既存configとresult metadataの任意JSON項目で、旧結果の閲覧は継続する。原文・数値の照合は引用の同一性の確認であり、意味の妥当性を証明しない。実利用者アプリの再起動は行っておらず、反映後は再起動して新規runで選択する。
- 合成の一時DB/VaultだけでPython関連10モジュール140件成功。SQL注入文字列、1,220件目の一致、指定ID優先、本文/話者/時刻差替え、hash破損、重複/未提示/不存在のID、上限、4スレッド読取、将来の依頼IDの分離、両モードの開始→結果保存→HTTP書き出し、原応答保持、AI呼出し数が増えないことを検証。初期の旧Flask結合fixtureは、以前のCore応答形式を現行next_step契約に返して失敗していたため、旧形式fixtureの設定をcore_control_version=0と明示した。製品のCore制御は1のまま、専用Core契約試験も同時に成功。MAFフラグ有効時に旧provider stubが追加kwargsを受け取れない点も切り分け、通常Flask試験は通常プロファイル、MAF試験は試験内で有効化した。
- DOM操作30件成功（新規2件を含む）。SQL既定、選択したhybridの送信、履歴、原文表示、HTML注入拒否、閲覧による追加AIなしを確認。Edgeで実テンプレートのPC幅1100×900とモバイル幅412×915を開き、既定と選択操作・横にはみ出さないことを確認。スクリーンショットを目視確認した。ブラウザーは合成画面で、実利用者データへ接続していない。
- LM Studioの同じgoogle/gemma-4-12b-qatへ実AI境界の要求を各方式1回、計2回。いずれも指定した2件目の発話IDを返し、SQLから取得した条件・例外・数値を含む原文が完全一致。SQL側4.735秒、hybrid側5.016秒の小規模確認で、追加の分析AI呼出しは各1回。これは以前のID専用応答による高速化ベンチマークとは異なるため、その速度効果を製品へ転用しない。LM Studioのモデル設定・接続先・認証設定は変更していない。
- 構文確認、JavaScript検査、対象差分の空白検査は成功。実研究データでの意味の正答率、全アプリ全試験、実稼働アプリの反映後確認は未実行。証跡は利用者checkoutのoutput/validation/sql-hybrid-selection-20261110/summary.json、unittest.log、model.json、desktop.png、mobile.png。実装hashはsummary.json。再現用verify_sql_hybrid.pyと新規試験は開発資料worktreeだけに保存した。
'''
    with note.open('ab') as stream:
        stream.write(text.encode('utf-8'))
    print('recorded SQL/hybrid validation', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['model', 'browser', 'record'])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {'model': model_check, 'browser': browser_check, 'record': record_check}[args.mode]()
