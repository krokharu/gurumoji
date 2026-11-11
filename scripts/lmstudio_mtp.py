"""LM Studioの外部MTPヘッドを有効化し、合成資料で速度を比較する。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

import lmstudio as lms
import lmstudio.json_api as api
from lmstudio._kv_config import _api_override_kv_config_stack

import benchmark_gemma_speculative as bench
import compare_sql_hybrid_mtp as hybrid

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/validation/obussql-lmstudio-mtp-20261110'
MODEL = bench.MODEL
DRAFT_KEY = 'ensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant/gemma-4-12B-it-qat-q4_0-assistant.gguf'
BASE_CONVERTER = api.load_config_to_kv_config_stack


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def load(client, mtp, context=16384, parallel=4, gpu=0.8, nmax=5):
    # SDK 1.5が未公開のロード項目を除去するため、通信時のKV層へ限定して補う。
    fields = {
        'llm.load.llama.autoFit': False,
        'llm.load.numParallelSessions': parallel,
        'llm.load.llama.contextCheckpoints': 0,
        'llm.load.llama.speculativeDecoding.draftMtp': False,
        'llm.load.llama.speculativeDecoding.draftSimple': False,
        'llm.load.llama.speculativeDecoding.draftDflashSidecar': False,
        'llm.load.llama.speculativeDecoding.draftDsparkSidecar': False,
        'llm.load.llama.speculativeDecoding.draftMtpSidecar': mtp,
        'llm.load.llama.speculativeDecoding.draftModel': DRAFT_KEY if mtp else '',
        'llm.load.llama.speculativeDecoding.draftMaxTokens': nmax,
        'llm.load.llama.speculativeDecoding.draftMinTokens': 0,
        'llm.load.llama.speculativeDecoding.draftMinContinueProbability': 0,
    }
    def converter(config, config_type):
        stack = BASE_CONVERTER(config, config_type).to_dict()
        ordinary = stack['layers'][0]['config']['fields']
        return _api_override_kv_config_stack(ordinary + [{'key': k, 'value': v} for k, v in fields.items()])
    api.load_config_to_kv_config_stack = converter
    try:
        start = time.perf_counter()
        model = client.llm.load_new_instance(MODEL, instance_identifier=MODEL, ttl=None,
            config={'contextLength': context, 'gpu': {'ratio': gpu}, 'flashAttention': True})
        return model, time.perf_counter() - start, fields
    finally:
        api.load_config_to_kv_config_stack = BASE_CONVERTER


def call(case, db, method, phase, repeat, reasoning=False):
    prepared = hybrid.build_request(case, method)
    system, user = [m['content'] for m in prepared['messages']]
    # 測定順による長い共通prefixの再利用を避け、全方式で同じ識別子を渡す。
    body = {'model': MODEL, 'input': user,
        'system_prompt': f"Measurement {case['name']} {repeat}.\n" + system,
        'temperature': 0, 'max_output_tokens': 3200 if reasoning else 1400,
        'reasoning': 'on' if reasoning else 'off', 'store': False}
    row = {'case': case['name'], 'phase': phase, 'method': method, 'repeat': repeat,
        'reasoning': reasoning, 'expected': case['expected'],
        'request_sha256': hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    start = time.perf_counter()
    try:
        with bench.post('/api/v1/chat', body) as response:
            result = json.load(response)
        row['model_seconds'] = time.perf_counter() - start
        row['response'] = result
        row['stats'] = result.get('stats', {})
        text = '\n'.join(x['content'] for x in result['output'] if x['type'] == 'message')
        row['text'] = text
        stripped = text.strip()
        if stripped.startswith('```'):
            stripped = stripped.split('\n', 1)[1].rsplit('```', 1)[0]
        parsed = json.loads(stripped)
        row['parsed'] = parsed
        resolved = parsed if method == 'full' else hybrid.restore_ids(case, db, parsed['ids'])
        row.update(result=resolved, exact=resolved == case['expected'])
    except Exception as exc:
        row.update(error=str(exc), exact=False)
    row['elapsed_seconds'] = time.perf_counter() - start
    return row


def benchmark(report):
    cases = list(hybrid.make_cases())
    report.update(calls=[], conditions=[], quality_scope='合成7課題。実研究資料・実Vaultは使わない。')
    dbs = {case['name']: hybrid.make_database(case)[0] for case in cases}
    with lms.Client() as client:
        for phase, mtp, nmax, repeats in [('normal-first', False, 5, 1), ('mtp3', True, 3, 2),
                ('mtp5', True, 5, 2), ('normal-last', False, 5, 1)]:
            model, elapsed, fields = load(client, mtp, nmax=nmax)
            # SDK統計で、対象ヘッドの提案・採用をロードごとに確認する。
            proof = model.respond('Repeat exactly: Synthetic MTP verification.', config={'temperature': 0, 'maxTokens': 64})
            condition = {'phase': phase, 'load_seconds': elapsed, 'fields': fields,
                'sdk_config': model.get_load_config().to_dict(), 'proof_stats': proof.stats.to_dict(),
                'api_models': bench.get('http://127.0.0.1:1234/api/v1/models')}
            report['conditions'].append(condition)
            print('PHASE', phase, json.dumps(condition['proof_stats']), flush=True)
            for repeat in range(repeats):
                for index, case in enumerate(cases):
                    for method in (['full', 'hybrid'] if (index+repeat) % 2 == 0 else ['hybrid', 'full']):
                        row = call(case, dbs[case['name']], method, phase, repeat)
                        report['calls'].append(row)
                        save('benchmark.json', report)
                        print(json.dumps({k: row[k] for k in ('case', 'phase', 'method', 'repeat', 'exact', 'elapsed_seconds')} | {'stats': row.get('stats'), 'error': row.get('error')}, ensure_ascii=False), flush=True)
            if phase in ('normal-first', 'mtp5'):
                for case in cases:
                    if case['kind'] == 'rules':
                        row = call(case, dbs[case['name']], 'full', phase, 10, reasoning=True)
                        report['calls'].append(row)
                        save('benchmark.json', report)
                        print('REASONING', phase, case['name'], row['exact'], row['elapsed_seconds'], flush=True)
            bench.cli('unload', MODEL)
    for db in dbs.values():
        db.close()


def restore():
    loaded = json.loads(bench.cli('ps', '--json'))
    assert all(row['status'] == 'idle' and row['queued'] == 0 for row in loaded if row['identifier'] == MODEL)
    if any(row['identifier'] == MODEL for row in loaded):
        bench.cli('unload', MODEL)
    return bench.cli('load', MODEL, '--identifier', MODEL, '--gpu', '0.8', '--context-length', '16384',
        '--parallel', '4', '--no-speculative-draft-mtp', '-y')


def install_defaults(nmax=5):
    """モデル固有の既定値だけを保存し、元のbytesを復元できるよう保持する。"""
    target = Path.home() / '.lmstudio/.internal/user-concrete-model-default-config/google/gemma-4-12b-qat.json'
    record = OUT / 'defaults-backup.json'
    if record.exists():
        backup = json.loads(record.read_text(encoding='utf-8'))
        assert backup['path'] == str(target)
    else:
        previous = target.read_bytes() if target.exists() else None
        import base64
        backup = {'path': str(target), 'existed': previous is not None,
            'original_base64': base64.b64encode(previous).decode() if previous is not None else None}
        save('defaults-backup.json', backup)
    current = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'preset': '', 'operation': {'fields': []}, 'load': {'fields': []}}
    selected = {
        'llm.load.llama.speculativeDecoding.draftMtp': False,
        'llm.load.llama.speculativeDecoding.draftSimple': False,
        'llm.load.llama.speculativeDecoding.draftDflashSidecar': False,
        'llm.load.llama.speculativeDecoding.draftDsparkSidecar': False,
        'llm.load.llama.speculativeDecoding.draftMtpSidecar': True,
        'llm.load.llama.speculativeDecoding.draftModel': DRAFT_KEY,
        'llm.load.llama.speculativeDecoding.draftMaxTokens': nmax,
        'llm.load.llama.speculativeDecoding.draftMinTokens': 0,
        'llm.load.llama.speculativeDecoding.draftMinContinueProbability': 0,
        'llm.load.llama.autoFit': False,
        'llm.load.contextLength': 16384,
        'llm.load.numParallelSessions': 4,
        'llm.load.llama.contextCheckpoints': 0,
        'llm.load.llama.flashAttention': True,
    }
    gpu_stack = BASE_CONVERTER({'gpu': {'ratio': 0.8}}, lms.LlmLoadModelConfig).to_dict()
    selected.update({field['key']: field['value'] for field in gpu_stack['layers'][0]['config']['fields']})
    existing = [field for field in current['load']['fields'] if field['key'] not in selected]
    current['load']['fields'] = existing + [{'key': k, 'value': v} for k, v in selected.items()]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    save('installed-defaults.json', current)
    return target


def rollback_defaults():
    import base64
    backup = json.loads((OUT / 'defaults-backup.json').read_text(encoding='utf-8'))
    target = Path(backup['path'])
    expected = Path.home() / '.lmstudio/.internal/user-concrete-model-default-config/google/gemma-4-12b-qat.json'
    assert target.resolve() == expected.resolve()
    if backup['existed']:
        target.write_bytes(base64.b64decode(backup['original_base64']))
    elif target.exists():
        # 自分の保存後に利用者が変更した内容は削除しない。
        assert json.loads(target.read_text(encoding='utf-8')) == json.loads((OUT / 'installed-defaults.json').read_text(encoding='utf-8'))
        target.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['probe', 'benchmark', 'enable', 'restore', 'install', 'rollback'])
    parser.add_argument('--draft-tokens', type=int, choices=[3, 5], default=5)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode in ('restore', 'rollback'):
        if args.mode == 'rollback':
            rollback_defaults()
        print(restore())
        return
    ps = json.loads(bench.cli('ps', '--json'))
    assert len(ps) == 1 and ps[0]['identifier'] == MODEL and ps[0]['status'] == 'idle' and ps[0]['queued'] == 0, ps
    original = bench.get('http://127.0.0.1:1234/api/v1/models')
    if not (OUT / 'original-models.json').exists():
        save('original-models.json', original)
    report = {'mode': args.mode, 'runs': []}
    success = False
    bench.PORT = 1234
    try:
        bench.cli('unload', MODEL)
        if args.mode == 'install':
            report['defaults_path'] = str(install_defaults(args.draft_tokens))
            # 追加のロード引数なしで設定を継承することまで確認する。
            report['load'] = bench.cli('load', MODEL, '--identifier', MODEL, '-y')
            with lms.Client() as client:
                proof = client.llm.model(MODEL).respond('Repeat exactly: Synthetic MTP verification.', config={'temperature': 0, 'maxTokens': 64})
                report['proof_stats'] = proof.stats.to_dict()
                assert report['proof_stats'].get('totalDraftTokensCount', 0) > 0, report
            report['api_models'] = bench.get('http://127.0.0.1:1234/api/v1/models')
            success = True
            print(json.dumps(report['proof_stats']), flush=True)
            return
        if args.mode == 'benchmark':
            benchmark(report)
            success = True
            return
        with lms.Client() as client:
            model, elapsed, fields = load(client, True)
            report.update(load_seconds=elapsed, fields=fields)
            print('LM Studio sidecar loaded in', elapsed, flush=True)
            result = model.respond('Repeat exactly: Synthetic MTP test completed.', config={'temperature': 0, 'maxTokens': 64})
            report.update(probe_text=str(result), probe_stats=result.stats.to_dict())
            print(json.dumps(report, ensure_ascii=False), flush=True)
            success = True
    except Exception as exc:
        report['error'] = str(exc)
        print(report['error'], flush=True)
        if args.mode == 'install' and report.get('defaults_path'):
            rollback_defaults()
            report['defaults_rolled_back'] = True
    finally:
        if args.mode not in ('enable', 'install') or not success:
            report['restore'] = restore()
            report['restored_models'] = bench.get('http://127.0.0.1:1234/api/v1/models')
            stored_original = json.loads((OUT / 'original-models.json').read_text(encoding='utf-8'))
            # drafterの追加とTTLはロード設定の復元判定から除く。
            def configs(value):
                return [(m['key'], [{k: v for k, v in i.items() if k != 'remaining_ttl_seconds'} for i in m['loaded_instances']])
                    for m in value['models'] if m['loaded_instances']]
            report['original_restored'] = configs(report['restored_models']) == configs(stored_original)
        save(args.mode + '.json', report)


if __name__ == '__main__':
    main()
