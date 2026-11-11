"""SQLとAIの役割・同条件の速度・失敗を区別して比較結果を記録する。"""
import ast
import hashlib
import json
from pathlib import Path
import statistics
import urllib.request

import compare_sql_hybrid_mtp as experiment

ROOT = Path(__file__).resolve().parents[4]
OUT = experiment.OUT
report = json.loads((OUT / 'comparison.json').read_text(encoding='utf-8'))
assert len(report['calls']) == 56 and report['restored']
assert len({(r['phase'], r['method'], r['case'], r['repeat']) for r in report['calls']}) == 56
cases = list(experiment.make_cases())
(OUT / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
by_case = {c['name']: c for c in cases}
dbs = {}
for case in cases:
    db, _ = experiment.make_database(case)
    assert experiment.pure_sql(case, db) == case['expected']
    if case['kind'] == 'rules':
        where = "retest='positive' AND submitted=1" if case['name'].endswith('strict') else "(retest='positive' OR (retest='negative' AND submitted=1))"
        total = db.execute('SELECT SUM(value) FROM source WHERE consent=1 AND withdrawn=0 AND ' + where).fetchone()[0]
        assert total == case['expected']['total']
    dbs[case['name']] = db
for row in report['calls']:
    parsed = json.loads(row['text'])
    assert parsed == row['parsed'] and not row['reasoning']
    assert row['finish_reason'] == 'stop' and row['timings']['cache_n'] == 0
    result = parsed if row['method'] == 'full' else experiment.restore_ids(by_case[row['case']], dbs[row['case']], parsed['ids'])
    assert result == row['result']
    assert row['exact'] == (result == by_case[row['case']]['expected'])
    if row['phase'] == 'mtp5':
        assert row['timings']['draft_n'] > 0 and row['timings']['draft_n_accepted'] > 0
for db in dbs.values():
    db.close()


def summarize(rows):
    names = sorted({r['case'] for r in rows})
    return {'calls': len(rows), 'exact_calls': sum(r['exact'] for r in rows), 'cases': len(names),
        'all_repeats_exact_cases': sum(all(r['exact'] for r in rows if r['case'] == name) for name in names),
        'mean_seconds': statistics.mean(r['elapsed_seconds'] for r in rows),
        'median_seconds': statistics.median(r['elapsed_seconds'] for r in rows),
        'mean_input_tokens': statistics.mean(r['timings']['prompt_n'] for r in rows),
        'mean_generated_tokens': statistics.mean(r['timings']['predicted_n'] for r in rows),
        'generated_tokens_per_second': sum(r['timings']['predicted_n'] for r in rows)*1000/sum(r['timings']['predicted_ms'] for r in rows),
        'by_kind': {kind: {'calls': len(rs), 'exact': sum(r['exact'] for r in rs), 'mean_seconds': statistics.mean(r['elapsed_seconds'] for r in rs)}
            for kind in ('records', 'rules') if (rs := [r for r in rows if r['kind'] == kind])}}


groups = {phase + '_' + method: summarize([r for r in report['calls'] if r['phase'] == phase and r['method'] == method])
          for phase in ('normal', 'mtp5') for method in ('full', 'hybrid')}
sql = report['sql']
summary = {'status': 'completed', 'groups': groups,
    'sql': {'cases': len(sql), 'correct_cases': sum(r['exact'] == r['n'] for r in sql),
        'calls': sum(r['n'] for r in sql), 'exact_calls': sum(r['exact'] for r in sql),
        'mean_of_case_medians_ms': statistics.mean(r['median_ms'] for r in sql),
        'mean_of_case_means_ms': statistics.mean(r['mean_ms'] for r in sql),
        'mean_input_tokens': 0, 'model_calls': 0, 'setup_seconds_mean': statistics.mean(r['setup_seconds'] for r in sql)},
    'hybrid_mtp_vs_full_mtp': {'time_reduction': 1-groups['mtp5_hybrid']['mean_seconds']/groups['mtp5_full']['mean_seconds'],
        'input_reduction': 1-groups['mtp5_hybrid']['mean_input_tokens']/groups['mtp5_full']['mean_input_tokens']},
    'failures': [{k: r.get(k) for k in ('phase', 'method', 'case', 'repeat', 'expected', 'parsed', 'result', 'finish_reason', 'error')}
        for r in report['calls'] if not r['exact']],
    'limitations': report['limitations'] + [
        'SQL側の決定的処理はSQLite照合とPythonのJSON投影・整数合計を含む。SQL SUMによる別照合も一致した。',
        '5抽出課題と2条件判定・合計課題。AI各方式は各課題2回。SQLは各課題200回の温まった一時DB。',
        '自由文をSQLへ変換する時間・誤りは測っていない。既知条件を事前に実装できる仕事での比較。',
        '新規DB作成とモデルロードは別掲。画面・アプリ外側のHTTP応答時間は対象外。',
        '生成中のキャッシュ再利用なし、入力型と各方式の責務を保持。ハイブリッドはモデル出力をIDへ限定している。',
        '実研究資料・自由な意味解釈・未知の検索条件・並列生成・他モデルは未検証。'],
    'restored_original_inventory_and_load_config': report['restored'], 'model_calls_measured': len(report['calls']),
    'warmups_excluded': len(report['warmups']), 'all_model_responses_complete': True,
    'all_mtp_calls_actually_drafted_and_accepted': True, 'application_changed': False, 'real_user_data_used': False}
before = json.loads((OUT / 'original-models.json').read_text(encoding='utf-8'))
after = json.load(urllib.request.urlopen('http://127.0.0.1:1234/api/v1/models', timeout=10))
assert before == after == json.loads((OUT / 'restored-models.json').read_text(encoding='utf-8'))
scripts = [Path(__file__), Path(__file__).with_name('compare_sql_hybrid_mtp.py'), Path(__file__).with_name('benchmark_gemma_speculative.py')]
summary['script_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts}
for p in scripts:
    text = p.read_text(encoding='utf-8')
    ast.parse(text)
    assert all(line == line.rstrip() for line in text.splitlines())
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
note = ROOT / 'output/validation/development-assets-20261016/docs/program-vault/60-Operations/20-Development/gurumoji-improvement-session/02-topics/16-section.md'
title = '## 2026-11-10: SQL・投機的デコード・ハイブリッドの同条件比較'
text = f'''

{title}

- 利用者の「投機的デコード SQL ハイブリット 比較して」に基づき、過去の異なる条件の値を並べるだけでなく、新しい同条件試験を実施。利用者checkoutはkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486と既存未コミット実装。コード・本記録は開発資料worktreeへ保持し、アプリ・実利用者DB/Vault・認証・本番接続は変更していない。
- 比較は、全文をAIが返す方式、AIがIDだけ選んでSQL/ホストが原文・数値・合計を確定する方式、それぞれの通常生成/MTP5、およびAIを呼ばないSQL/ホスト処理。MTPはモデルの高速生成、SQLはデータ処理なので併用可能である。元の通常処理との比較も対照として保持した。
- 5つの原文抽出と2つの条件判定・整数合計、計7合成課題。AI方式は各課題2回、4方式で計56測定とwarmup4回。SQL側は各課題200回、計1400回。通常/MTPとも同じGemma4 12B QAT、本体/assistantは前回と同じhashの固定重み、公式llama.cpp b9553、RTX5070全GPU、context8192/parallel1、batch2048/ubatch512、temperature0/seed42、推論OFF、cache_prompt=false。モデル・DBの作成時間は除外し別掲し、SQLは照合・復元・JSON化・整数合計、AI側は入力準備・生成・復元・JSON化を含めた。
- SQLは平均{summary['sql']['mean_of_case_medians_ms']:.6f}ms（課題別中央値の平均）、1400/1400一致、7/7課題、モデル入力0/呼出し0。SQL側の合計はPythonによる整数合計を含む決定的なホスト処理で、SQL SUMでも別照合した。既知の2条件を事前クエリ化しているため、自由文からSQLを生成する時間・品質を含まない。未知条件にもSQLだけで答えられるという評価ではない。
- 通常AI全文は平均{groups['normal_full']['mean_seconds']:.6f}秒、入力{groups['normal_full']['mean_input_tokens']:.2f}tokens、{groups['normal_full']['exact_calls']}/14一致。通常AI+SQLは{groups['normal_hybrid']['mean_seconds']:.6f}秒/{groups['normal_hybrid']['mean_input_tokens']:.2f}tokens/{groups['normal_hybrid']['exact_calls']}/14一致。MTP5全文は{groups['mtp5_full']['mean_seconds']:.6f}秒/{groups['mtp5_full']['mean_input_tokens']:.2f}tokens/{groups['mtp5_full']['exact_calls']}/14一致。MTP5+SQLは{groups['mtp5_hybrid']['mean_seconds']:.6f}秒/{groups['mtp5_hybrid']['mean_input_tokens']:.2f}tokens/{groups['mtp5_hybrid']['exact_calls']}/14一致。
- MTP5+SQLはMTP5全文に比べ総時間{summary['hybrid_mtp_vs_full_mtp']['time_reduction']*100:.2f}%減、AI入力{summary['hybrid_mtp_vs_full_mtp']['input_reduction']*100:.2f}%減。生成は全応答finish=stop、思考内容なし、cache_n=0を確認。MTPの全28測定で実draft/採用が正であることを確認し、通常生成へのfallbackを成功扱いしていない。
- 不正答はsummary.jsonのfailuresへ期待値・実応答ごと保持。例外のある条件課題でID集合が合っていても、AI全文方式が合計228を188と返す例を確認。AIが選んだIDからホストが元値を取得・計算する方式ではこの転記・算術の責務をAIへ持たせない。試験は推論OFFであり、以前の推論ONで8/8正答した結果と混同しない。今回の小さな課題集合の正答率を一般的な研究品質とは扱わない。
- 判断: 明示ID・既知条件の定型処理はSQL/ホスト単独が最速で、不要なAIを追加する意義は小さい。自然文の条件判断をAIへ任せ、出典本文・整数を元データへ戻す用途では、MTP5+SQLがAI全文より有望。自由な意味検索、未知の条件、研究上の解釈、並列動作は未検証である。今回の7課題で優位なことと、全分析工程の最適構成を区別する。
- 一時SQLiteと合成資料だけを使用。元のモデルidle/queued0を確認してから一時unloadし、測定後は専用サーバーを停止、元のID/GPU0.8/context16384/parallel4を復元。全モデル一覧とロード設定の前後一致を確認した。commit/pushなし。証跡は利用者checkoutのoutput/validation/obussql-sql-hybrid-mtp-20261110/にcomparison.json（56測定・1400SQL照合・warmup・ロード時間）/cases.json/summary.jsonと原設定・復元JSON。2本の新規スクリプトと利用helperのAST・空白・hashを検査した。アプリを変更していないため既存回帰試験を再実行していない。
'''
assert title not in note.read_text(encoding='utf-8')
assert '\ufffd' not in text and '??' not in text
with note.open('ab') as handle:
    handle.write(text.encode('utf-8'))
print(json.dumps(summary, ensure_ascii=False, indent=2))
