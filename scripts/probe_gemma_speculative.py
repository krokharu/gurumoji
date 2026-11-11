"""ロード時MTPを専用CPUインスタンスで調べ、利用中のモデルを保持する。"""
import json
from pathlib import Path
import subprocess
import time
import lmstudio as lms

root = Path(__file__).resolve().parents[4]
out = root / 'output/validation/obussql-speculative-20261110'
out.mkdir(parents=True, exist_ok=True)
model_key = 'google/gemma-4-12b-qat'
test_id = 'gurumoji-spec-probe-20261110'

def cli(*args):
    result = subprocess.run(['lms', *args], capture_output=True, encoding='utf-8', errors='replace', timeout=180)
    return {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}

report = {'before': json.loads(cli('ps', '--json')['stdout'])}
assert all(r.get('status') == 'idle' and not r.get('queued') for r in report['before'])
with lms.Client() as client:
    active = client.llm.model(model_key)
    config = active.get_load_config().to_dict()
    (out / 'original-sdk-config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Original configuration saved.', flush=True)
    try:
        start = time.perf_counter()
        report['load'] = cli('load', model_key, '--identifier', test_id, '--gpu', 'off', '--context-length', '2048',
            '--parallel', '1', '--speculative-draft-mtp', '--speculative-draft-max-tokens', '3', '-y')
        report['load_seconds'] = time.perf_counter() - start
        print(json.dumps(report['load'], ensure_ascii=False), flush=True)
        loaded = json.loads(cli('ps', '--json')['stdout'])
        if any(row['identifier'] == test_id for row in loaded):
            model = client.llm.model(test_id)
            report['config'] = model.get_load_config().to_dict()
            start = time.perf_counter()
            result = model.respond('次の文を正確に繰り返す：合成試験では、条件と例外と数値を変更しない。', config={'temperature': 0, 'maxTokens': 32})
            report.update(stats=result.stats.to_dict(), text=str(result), elapsed_seconds=time.perf_counter()-start)
            print(json.dumps(report.get('stats'), ensure_ascii=False), flush=True)
    except Exception as exc:
        report['error'] = str(exc)
        print(report['error'], flush=True)
    finally:
        loaded = json.loads(cli('ps', '--json')['stdout'])
        if any(row['identifier'] == test_id for row in loaded):
            report['unload'] = cli('unload', test_id)
        report['after'] = json.loads(cli('ps', '--json')['stdout'])
        report['original_config_unchanged'] = client.llm.model(model_key).get_load_config().to_dict() == config
        (out / 'mtp-cpu-probe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Probe finished; original config unchanged:', report['original_config_unchanged'], flush=True)
