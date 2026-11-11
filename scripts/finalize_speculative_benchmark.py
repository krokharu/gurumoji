"""生応答を独立採点し、MTPの比較結果と復元確認を既存ノートへ記録する。"""
import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import subprocess
import urllib.request

from benchmark_gemma_speculative import tasks, reasoning_tasks, TARGET, DRAFT

root = Path(__file__).resolve().parents[4]
out = root / 'output/validation/obussql-speculative-20261110'
load = lambda name: json.loads((out / name).read_text(encoding='utf-8'))
main = load('benchmark.json')
reasoning = load('reasoning.json')
assert len(main['calls']) == 50 and len(reasoning['calls']) == 8
assert main['restored'] and reasoning['restored']

# 推論課題の正解は別経路の一時SQLiteでも照合する。
oracles = {name: {'records': expected} for name, _, expected in tasks()}
for name, context, expected in reasoning_tasks():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE source(id TEXT,consent INT,retest TEXT,submitted INT,withdrawn INT,value INT)')
    db.executemany('INSERT INTO source VALUES (:id,:consent,:retest,:submitted,:withdrawn,:value)', context['rows'])
    condition = "retest='positive' AND submitted=1" if name.endswith('strict') else "(retest='positive' OR (retest='negative' AND submitted=1))"
    rows = db.execute('SELECT id,value FROM source WHERE consent=1 AND withdrawn=0 AND ' + condition + ' ORDER BY id').fetchall()
    oracle = {'ids': [r[0] for r in rows], 'total': sum(r[1] for r in rows)}
    assert oracle == expected
    oracles[name] = oracle
    db.close()

rescored = {'explanation': '推論フラグとストリーム差分の変数名衝突を修正。生応答を変更せずJSONを再parseし、一時SQLiteで別途検証した期待値と比較する。初期採点はinitial_exactへ保持。', 'calls': []}
for report in (main, reasoning):
    for row in report['calls']:
        parsed = json.loads(row['text'])
        assert parsed == row['parsed']
        exact = parsed == oracles[row['case']]
        assert row['finish_reason'] == 'stop'
        assert row['timings']['cache_n'] == 0
        if report is reasoning:
            assert row['reasoning']
            row['initial_exact'] = row['exact']
            row['exact'] = exact
            rescored['calls'].append(row)
        else:
            assert row['exact'] == exact
            assert not row['reasoning']
        assert exact, (row['label'], row['case'])
(out / 'reasoning-scored.json').write_text(json.dumps(rescored, ensure_ascii=False, indent=2), encoding='utf-8')


def aggregate(rows):
    drafted = sum(r['timings'].get('draft_n', 0) for r in rows)
    accepted = sum(r['timings'].get('draft_n_accepted', 0) for r in rows)
    return {'n': len(rows), 'exact': sum(r['exact'] for r in rows),
        'elapsed_seconds_mean': statistics.mean(r['elapsed_seconds'] for r in rows),
        'ttft_seconds_mean': statistics.mean(r['first_token_seconds'] for r in rows),
        'input_tokens_mean': statistics.mean(r['timings']['prompt_n'] for r in rows),
        'predicted_tokens_total': sum(r['timings']['predicted_n'] for r in rows),
        'weighted_generated_tokens_per_second': sum(r['timings']['predicted_n'] for r in rows) * 1000 / sum(r['timings']['predicted_ms'] for r in rows),
        'drafted': drafted, 'accepted': accepted, 'acceptance_rate': accepted / drafted if drafted else None,
        'all_cache_n_zero': all(r['timings']['cache_n'] == 0 for r in rows)}


def by_label(rows):
    return {label: aggregate([r for r in rows if r['label'] == label]) for label in sorted({r['label'] for r in rows})}


baseline = [r for r in main['calls'] if r['label'].startswith('baseline')]
grouped = by_label(main['calls'])
grouped['baseline-combined'] = aggregate(baseline)
for label in ('mtp2', 'mtp3', 'mtp5'):
    grouped[label]['generation_speedup'] = grouped[label]['weighted_generated_tokens_per_second'] / grouped['baseline-combined']['weighted_generated_tokens_per_second']
    grouped[label]['total_time_reduction'] = 1 - grouped[label]['elapsed_seconds_mean'] / grouped['baseline-combined']['elapsed_seconds_mean']
for name in {r['case'] for r in main['calls']}:
    assert len({r['timings']['prompt_n'] for r in main['calls'] if r['case'] == name}) == 1
mtp = [r for r in main['calls'] + reasoning['calls'] if 'mtp' in r['label']]
assert all(r['timings']['draft_n'] > 0 and r['timings']['draft_n_accepted'] > 0 for r in mtp)
current_models = json.load(urllib.request.urlopen('http://127.0.0.1:1234/api/v1/models', timeout=10))
assert current_models == load('original-models.json') == load('restored-models.json')
scripts = [Path(__file__).with_name(name) for name in ['probe_gemma_speculative.py', 'prepare_speculative_engine.py', 'benchmark_gemma_speculative.py', 'finalize_speculative_benchmark.py']]
for path in scripts:
    text = path.read_text(encoding='utf-8')
    ast.parse(text)
    assert all(line == line.rstrip() for line in text.splitlines())
hashes = {}
for path in [TARGET, DRAFT, *scripts]:
    with path.open('rb') as handle:
        hashes[str(path)] = hashlib.file_digest(handle, 'sha256').hexdigest()
long = [r for r in main['calls'] if r['case'] == 'long-eight-records']
summary = {'status': 'passed', 'measured_calls': 58, 'extraction_calls': 50, 'reasoning_calls': 8,
    'main': grouped, 'reasoning': by_label(reasoning['calls']), 'long_output': by_label(long),
    'long_output_text_identical': len({r['text'] for r in long}) == 1,
    'all_exact': True, 'all_complete': True, 'active_mtp_in_every_mtp_measurement': True,
    'mtp_measured_calls': len(mtp), 'original_models_and_load_config_restored': True,
    'source_hashes': hashes, 'engine_manifest': load('engine-manifest.json'),
    'limits': ['RTX5070 12GB、llama.cpp b9553、全GPU層、並列1、context8192、KV再利用なし、temperature0/seed42。',
        '同じエンジン内の通常生成とMTPの比較。元のLM StudioはGPU比0.8、並列4、context16384で設定が異なる。',
        'LM StudioのSDK予測時draft指定だけでなく、ロード時MTPも拒否を実測。現状の本体GGUFにはbundled MTP headがない。',
        '合成原文抽出と条件判定の品質。実研究資料、音声・画像、並列生成、温度を上げた分布一致は未検証。',
        '元の回答JSONの空白や出力tokensは一部異なる。採点は原文字列・数値・ID・否定・例外を一致で検査。',
        '推論ONの初期採点バグは生応答を保持して独立再採点。reasoning-scored.jsonへ修正値と初期値を保持。'],
    'branch': subprocess.check_output(['git', 'branch', '--show-current'], text=True, cwd=root).strip(),
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=root).strip()}
(out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
note = root / 'output/validation/development-assets-20261016/docs/program-vault/60-Operations/20-Development/gurumoji-improvement-session/02-topics/16-section.md'
title = '## 2026-11-10: Gemma QATの投機的デコードを実動比較'
base, best = grouped['baseline-combined'], grouped['mtp5']
reason = summary['reasoning']
record = f'''

{title}

- 利用者の「投機的デコードをしっかり試して」に基づき、前回の予測時API拒否から踏み込み、ロード時MTPと実生成を試験。利用者checkoutのHEADは{summary['head']}、ブランチは{summary['branch']}。評価コード・本記録は開発資料ブランチへ保持し、アプリコード・実利用者DB/Vault・認証・接続先は変更していない。
- LM Studio CLIのCPU専用インスタンスで `--speculative-draft-mtp` を実行すると、現行GGUFは「bundled supported MTP head」がないためロード拒否。試験専用インスタンスだけを扱い、この時点で元の設定は不変。公式issue2244にも外部Gemma assistantの制約が報告されている。外部assistantを内蔵型扱い・単独モデル扱いで強制せず、公式llama.cppの外部MTP経路へ切り替えた。
- 固定エンジンb9553/9e3b928fd8c9d14dbf15a8768b9fdd7e5c721d66、Windows CUDA13.3の配布zip2本を公式GitHubから取得し、公式asset digestとSHA256一致を確認。RTX5070/12GB、driver610.88。元のQAT本体は読み取りだけで使用し、対応assistantはensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant、revision e9aaf2d12229b0b11d7e8b2c8821c5648c48334e、322915136bytes、SHA256 25f143b4c15b20cd04216e35e99bd7a56afc6f65e7a4e090a3e20091bb590cbb。GoogleのQAT対応assistantを変換したApache-2.0の公開重み。取得物は検証output内だけに置いた。
- 利用中のGemmaがidle/queued0であることをCLIで確認し、ロード状態をAPIとSDKで保存。GPU比較中だけ元インスタンスをunloadし、専用localhost:19841のサーバーを起動した。終了処理finallyで試験プロセスを停止し、元のID・GPU比0.8・context16384・parallel4を復元。probe・本試験・推論ON追加試験の各段階で、全モデル一覧とロード設定が試験前後で完全一致した。APIサーバーやアプリ設定ファイルを切り替えず、実利用者の本文を入力していない。
- 予備GPU実動は原文抽出に完全一致し、draft75件中68件を採用、生成145.8tokens/sec。動いていない指定や通常生成へのfallbackを成功とせず、以後すべてのMTP測定でもdraft_n/acceptedが正であることを検査した。
- 本比較は同一エンジン・本体・テンプレート・schema・全GPU層・context8192・並列1、batch2048/ubatch512、temperature0/seed42、推論OFF、cache_prompt=false、cache-ram0/checkpoints0。反復表・異種表と各holdoutの4課題、および8件の長い原文出力の計5課題を各条件2回。通常生成を最初と最後に置いた計50測定と、各条件warmup5回を実行した。warmupは速度集計から除く。入力tokensは課題内で全条件同じで、全50回のcache_nは0。
- 通常生成（前後20回）は平均{base['elapsed_seconds_mean']:.3f}秒、重み付き生成速度{base['weighted_generated_tokens_per_second']:.2f}tokens/sec、20/20完全一致。MTP2は平均{grouped['mtp2']['elapsed_seconds_mean']:.3f}秒/{grouped['mtp2']['weighted_generated_tokens_per_second']:.2f}tokens/sec、採用{grouped['mtp2']['accepted']}/{grouped['mtp2']['drafted']}。MTP3は{grouped['mtp3']['elapsed_seconds_mean']:.3f}秒/{grouped['mtp3']['weighted_generated_tokens_per_second']:.2f}tokens/sec、採用{grouped['mtp3']['accepted']}/{grouped['mtp3']['drafted']}。MTP5は{best['elapsed_seconds_mean']:.3f}秒/{best['weighted_generated_tokens_per_second']:.2f}tokens/sec、採用{best['accepted']}/{best['drafted']}。MTP各10/10完全一致で、先読み5がこの範囲では最速。生成速度{best['generation_speedup']:.2f}倍、入力処理を含む総時間は{best['total_time_reduction']*100:.2f}%減。
- 本試験50回すべて、ID・条件・例外の原文字列・整数を期待値と一致で確認し、finish=stop。通常とMTPでJSON空白や出力tokensが異なる例はあるが、元の内容は変わっていない。長い8件出力では全条件400出力tokensで、JSON本文のbytes一致も{summary['long_output_text_identical']}。単なる出力短縮だけで速度差を説明する結果ではない。
- 推論ONも通常/MTP5で、撤回・未提出・検査不明・否定の例外判定と整数合計の2課題を各2回、計8測定。期待ID集合と合計は一時SQLiteでも独立照合した。通常は{reason['reasoning-baseline']['exact']}/4一致、平均{reason['reasoning-baseline']['elapsed_seconds_mean']:.3f}秒、{reason['reasoning-baseline']['weighted_generated_tokens_per_second']:.2f}tokens/sec。MTP5は{reason['reasoning-mtp5']['exact']}/4一致、平均{reason['reasoning-mtp5']['elapsed_seconds_mean']:.3f}秒、{reason['reasoning-mtp5']['weighted_generated_tokens_per_second']:.2f}tokens/sec。各応答で思考内容が非空であり、ONを確認。warmup2回は除く。
- 推論ONの初期採点に変数名衝突があり、一致を不一致と表示した。モデル要求・生応答・時間は影響なし。採点処理を修正し、生textを再parseして、別SQLite計算による期待値と独立再照合。初期値を消さずreasoning.jsonに保持し、修正値とinitial_exactはreasoning-scored.jsonに保存した。成功に見せるための期待値変更やモデル再生成はしていない。
- 検証済みは合成58測定、全件完全一致・完了。MTPは全34測定で提案・採用を実測。実研究データ・画像/音声・並列処理・高温度の分布同一性は未検証。元のLM Studio設定（GPU0.8/parallel4/context16384）と専用サーバー（全GPU/parallel1/context8192）は違うため、過去のアプリ時間との差をMTP単独効果とは扱わない。生成速度は実出力tokens合計/生成時間合計、総時間は呼出し平均で比較した。
- 判断: この機械・資料では先読み5のMTPは採用価値がある。ただし現行LM Studioの外部headロード制約は残り、今回の有効化は検証用llama.cppだけ。アプリの本番接続変更や恒久常駐は行っていない。最終的には元のモデルを復元した。モデル容量・補助重みのhashと実装hashはsummary.json、配布hashはengine-manifest.json。証跡は利用者checkoutのoutput/validation/obussql-speculative-20261110/にbenchmark.json（50件）/reasoning.json（8件、生採点）/reasoning-scored.json/summary.json、原設定・復元はoriginal-models/restored-models.json。専用サーバーログには合成入力だけを保持。
- 一次資料: https://github.com/ggml-org/llama.cpp/releases/tag/b9553 、https://github.com/ggml-org/llama.cpp/blob/b9553/docs/speculative.md 、https://ai.google.dev/gemma/docs/mtp/mtp 、https://huggingface.co/ensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant 、https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2244 。
'''
assert title not in note.read_text(encoding='utf-8')
with note.open('ab') as handle:
    handle.write(record.encode('utf-8'))
print(json.dumps({k: summary[k] for k in ('status', 'measured_calls', 'main', 'reasoning', 'long_output', 'long_output_text_identical', 'original_models_and_load_config_restored')}, ensure_ascii=False, indent=2))
