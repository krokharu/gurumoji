"""生の測定結果から集計と出自を作る。失敗・未計測は成功に補完しない。"""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import statistics
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/validation/obussql-alternatives-20261110'
sys.path.insert(0, str(OUT / 'deps'))


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def group(rows, key, mapper):
    return {value: mapper([r for r in rows if r[key] == value]) for value in sorted({r[key] for r in rows})}


def mean_stats(rows):
    stats = {'n': len(rows), 'exact': sum(r.get('exact', False) for r in rows),
             'elapsed_seconds_mean': statistics.mean(r['elapsed_seconds'] for r in rows)}
    for key in ('input_tokens', 'reasoning_output_tokens', 'total_output_tokens', 'time_to_first_token_seconds'):
        values = [r.get('stats', {}).get(key) for r in rows]
        available = [v for v in values if v is not None]
        stats[key + '_mean'] = statistics.mean(available) if available else None
    return stats


generation = read('generation.json')
structured = read('structured.json')
cache = read('cache.json')
retrieval = read('retrieval.json')
compression = read('compression.json')
host = read('host.json')
for r in host['calls']:
    usage = r.get('response', {}).get('usage', {})
    r['stats'] = {'input_tokens': usage.get('prompt_tokens'), 'total_output_tokens': usage.get('completion_tokens')}
for r in compression['calls']:
    r['inference_seconds'] = r['elapsed_seconds']
    r['elapsed_seconds'] += r['compress_seconds']
speculative = read('speculative.json')
if 'configured at load time' in speculative.get('error', ''):
    speculative['available_small_draft'] = False
    speculative['limitation'] = '現行エンジンはロード時の設定を要求し、予測時draft指定を拒否した。共有モデルの再ロードは行っておらず、速度・品質は未測定。小型draftも未導入。'
    (OUT / 'speculative.json').write_text(json.dumps(speculative, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {
    'scope': '合成の明示ID原文抽出4課題、日本語検索25問/132文書。Gemma4 12B QAT。研究解釈・実利用者データの品質保証ではない。',
    'reasoning_original_two_cases': group([r for r in generation['calls'] if r['case'].startswith('original')], 'profile', mean_stats),
    'formats_four_cases': group([r for r in generation['calls'] if r['profile'].endswith('-off')], 'profile', mean_stats),
    'structured_four_cases': group(structured['calls'], 'profile', mean_stats),
    'structured_failures': [{k: r.get(k) for k in ('case', 'profile', 'text', 'finish_reason', 'error')} for r in structured['calls'] if not r['exact']],
    'host_id_resolution': mean_stats(host['calls']),
    'deterministic_sql': {'exact': sum(r['exact'] for r in generation['sql']), 'n': len(generation['sql']),
        'query_ms_mean_of_case_medians': statistics.mean(r['query_ms_median'] for r in generation['sql']),
        'llm_calls': 0, 'scope': '明示IDで原文を取得する。意味解釈は行わない。DB作成時間は含まない。'},
    'cache': group(cache['calls'], 'stage', lambda rows: {
        'n': len(rows), 'ttft_median': statistics.median(r['stats']['time_to_first_token_seconds'] for r in rows),
        'elapsed_seconds_median': statistics.median(r['elapsed_seconds'] for r in rows),
        'input_tokens_mean': statistics.mean(r['stats']['input_tokens'] for r in rows)}),
    'cache_limitation': cache['limitation'],
    'retrieval': group(retrieval['measurements'], 'method', lambda rows: {
        'n': len(rows), 'hit3': sum(r['hit3'] for r in rows),
        'hit1': sum(r['hit1'] for r in rows) if all(r['hit1'] is not None for r in rows) else None,
        'ms_median': statistics.median(r['elapsed_ms'] for r in rows),
        'by_kind': group(rows, 'kind', lambda rs: {'n': len(rs), 'hit3': sum(r['hit3'] for r in rs)})}),
    'retrieval_setup_seconds': retrieval['setup_seconds'],
    'llmlingua2': mean_stats(compression['calls']) | {'load_seconds': compression['load_seconds'],
        'compress_seconds_mean': statistics.mean(r['compress_seconds'] for r in compression['calls']),
        'target_text_preserved': sum(r['source_target_texts_preserved'] for r in compression['calls']), 'lossless': False},
    'speculative': speculative,
    'counts': {'generation': len(generation['calls']), 'structured': len(structured['calls']), 'host': len(host['calls']),
        'cache': len(cache['calls']), 'compression': len(compression['calls']), 'speculative_probe': 1,
        'retrieval_questions': len(retrieval['questions']), 'retrieval_methods': len({r['method'] for r in retrieval['measurements']})},
    'limitations': ['各形式・課題は1回ずつで、実行順とモデル内キャッシュの影響を完全には除去できない。',
        'native APIはJSON形式を指示し、structuredはOpenAI互換APIのJSONスキーマを強制。2経路は別集計。',
        '検索時間は索引作成・モデルロードを除き、別掲。LLMLingua2は圧縮と生成の合計時間。',
        '検索はCPU4thread、生成はロード済みモデル。同時に複数の測定を実行していない。最初の生成試験中のみモデル重みを取得。',
        '投機的デコードはエンジンがロード時設定を要求して拒否。対応draftも未導入。実動速度と品質は未測定。',
        '既存アプリ・実利用者DB/Vault・共有モデルのロード設定は更新しない。'],
}
models_after = json.load(urllib.request.urlopen('http://127.0.0.1:1234/api/v1/models', timeout=10))
(OUT / 'models-after.json').write_text(json.dumps(models_after, ensure_ascii=False, indent=2), encoding='utf-8')
before = read('models-before.json')
summary['model_inventory_unchanged'] = before == models_after
files = [ROOT / name for name in ['src/gurumoji/services/context_delivery.py', 'src/gurumoji/services/model_context.py',
    'src/gurumoji/services/maf_dev_bridge.py', 'src/gurumoji/services/obussql.py']]
files += list(Path(__file__).parent.glob('*obussql*plans*.py'))
files += [Path(__file__), Path(__file__).with_name('test_obussql_retrieval_compression.py')]
summary['provenance'] = {'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'python': sys.executable, 'versions': {name: metadata.version(name) for name in ['torch', 'transformers', 'lmstudio', 'llmlingua', 'toon-format', 'rank-bm25', 'accelerate']},
    'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
for name, count in [('generation', 24), ('structured', 16), ('host', 4), ('cache', 8), ('compression', 4)]:
    assert summary['counts'][name] == count, (name, summary['counts'][name])
assert len(retrieval['questions']) == 25 and len(retrieval['corpus']) == 132
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
