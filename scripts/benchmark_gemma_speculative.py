"""同一本体でMTPを実測し、試験後は元のLM Studioロード設定を復元する。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/validation/obussql-speculative-20261110'
sys.path.insert(0, str(ROOT / 'src'))
os.environ['MOJIOKOSI_OBUSSQL_ENABLED'] = '1'
from compare_obussql_five import cases
from compare_obussql_external_plans import payload, SYSTEM
import lmstudio as lms

MODEL = 'google/gemma-4-12b-qat'
TARGET = Path.home() / '.lmstudio/models/lmstudio-community/gemma-4-12B-it-QAT-GGUF/gemma-4-12B-it-QAT-Q4_0.gguf'
DRAFT = OUT / 'draft/gemma-4-12B-it-qat-q4_0-assistant.gguf'
EXE = OUT / 'engine/b9553/llama-server.exe'
PORT = 19841


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def cli(*args):
    result = subprocess.run(['lms', *args], capture_output=True, encoding='utf-8', errors='replace', timeout=240)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def get(url):
    return json.load(urllib.request.urlopen(url, timeout=5))


def post(path, body):
    request = urllib.request.Request(f'http://127.0.0.1:{PORT}' + path,
        data=json.dumps(body, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(request, timeout=180)


def start_server(label, nmax, ngl=99, reasoning=False):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', PORT))
    command = [str(EXE), '-m', str(TARGET), '--alias', 'synthetic-spec-test', '--host', '127.0.0.1', '--port', str(PORT),
        '-c', '8192', '-np', '1', '-ngl', str(ngl), '-fa', 'on', '-b', '2048', '-ub', '512', '--fit', 'off',
        '--jinja', '--reasoning', 'on' if reasoning else 'off', '--metrics', '--cache-ram', '0', '--ctx-checkpoints', '0']
    if nmax:
        command += ['-md', str(DRAFT), '--spec-type', 'draft-mtp', '-ngld', '99',
                    '--spec-draft-n-max', str(nmax), '--spec-draft-n-min', '0', '--spec-draft-p-min', '0']
    else:
        command += ['--spec-type', 'none']
    log_path = OUT / (label + '.log')
    log = log_path.open('wb')
    process = subprocess.Popen(command, cwd=EXE.parent, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW)
    begin = time.perf_counter()
    while time.perf_counter() - begin < 120:
        if process.poll() is not None:
            log.close()
            raise RuntimeError(f'{label} exited {process.returncode}: ' + log_path.read_text(encoding='utf-8', errors='replace')[-7000:])
        try:
            health = get(f'http://127.0.0.1:{PORT}/health')
            if health.get('status') == 'ok':
                return process, log, log_path, command, time.perf_counter()-begin
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    process.terminate()
    process.wait(timeout=20)
    log.close()
    raise TimeoutError(label + ' not ready')


def stop_server(process, log):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    log.close()


def tasks():
    for held in (False, True):
        for name, context, expected in cases(held):
            yield ('heldout-' if held else 'original-') + name, context, expected
    name, context, _ = list(cases(True))[1]
    selected = [2, 9, 16, 23, 30, 37, 44, 47]
    expected = [{k: context['results'][i][k] for k in ('evidence_id', 'condition', 'exception', 'value')} for i in selected]
    context = {**context, 'question': '指定IDだけを指定順に抽出し、原文と整数をそのまま返す: ' + ', '.join(r['evidence_id'] for r in expected)}
    yield 'long-eight-records', context, expected


def reasoning_tasks():
    facts = [
        (True, 'positive', True, False, 19), (True, 'positive', True, True, 23),
        (False, 'positive', True, False, 29), (True, 'negative', True, False, 31),
        (True, 'positive', False, False, 37), (True, 'positive', True, False, 41),
        (True, 'unknown', True, False, 43), (True, 'positive', True, False, 47),
        (True, 'positive', True, False, 53), (False, 'negative', False, False, 59)]
    rows = [dict(zip(('consent', 'retest', 'submitted', 'withdrawn', 'value'), values)) | {'id': f's{i:02}'} for i, values in enumerate(facts)]
    rules = [
        ('strict', '同意あり、検査positive、資料提出済みの全条件を満たす人だけ採用。withdrawn=trueは例外なく除外。unknownを陰性や陽性として扱わない。',
         lambda r: r['consent'] and r['retest'] == 'positive' and r['submitted'] and not r['withdrawn']),
        ('exception', '同意ありで撤回なしが必須。検査positiveなら資料未提出でも採用。検査negativeなら提出済みだけ採用。unknownは除外。withdrawn=trueは例外なく除外。',
         lambda r: r['consent'] and not r['withdrawn'] and (r['retest'] == 'positive' or (r['retest'] == 'negative' and r['submitted'])))]
    for name, rule, eligible in rules:
        selected = [r for r in rows if eligible(r)]
        yield 'reasoning-' + name, {'rule': rule, 'rows': rows}, {'ids': [r['id'] for r in selected], 'total': sum(r['value'] for r in selected)}


def request_task(name, context, expected, label, repeat):
    reasoning = name.startswith('reasoning-')
    if reasoning:
        user = json.dumps(context, ensure_ascii=False, separators=(',', ':'))
        guidance = ''
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['ids', 'total'], 'properties': {
            'ids': {'type': 'array', 'items': {'type': 'string', 'enum': [r['id'] for r in context['rows']]}},
            'total': {'type': 'integer'}}}
        system = '合成資料のruleに従って採用者を判定する。採用したidを昇順のidsに、採用者のvalueの合計を整数totalに入れ、JSONで返す。例外・否定・不明を厳密に区別する。'
    else:
        user, guidance = payload(context, 'adaptive')
        keys = ('evidence_id', 'condition', 'exception', 'value')
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['records'], 'properties': {
            'records': {'type': 'array', 'minItems': len(expected), 'maxItems': len(expected), 'items': {
                'type': 'object', 'additionalProperties': False, 'required': list(keys),
                'properties': {k: {'type': 'integer' if k == 'value' else 'string'} for k in keys}}}}}
        system = SYSTEM.replace('指定順に2件だけ返す。', f'指定順に{len(expected)}件だけ返す。')
    body = {'model': 'synthetic-spec-test', 'messages': [{'role': 'system', 'content': system + guidance}, {'role': 'user', 'content': user}],
        'temperature': 0, 'seed': 42, 'top_p': 1, 'top_k': 0, 'min_p': 0, 'repeat_penalty': 1, 'max_tokens': 3200 if reasoning else 1400,
        'chat_template_kwargs': {'enable_thinking': reasoning}, 'cache_prompt': False, 'stream': True,
        'stream_options': {'include_usage': True},
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'source_records', 'strict': True, 'schema': schema}}}
    row = {'case': name, 'label': label, 'repeat': repeat, 'expected': expected,
           'request_sha256': hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    start = time.perf_counter()
    text, thoughts, events = '', '', []
    try:
        first = None
        with post('/v1/chat/completions', body) as response:
            for line in response:
                if not line.startswith(b'data: '):
                    continue
                raw = line[6:].strip()
                if raw == b'[DONE]':
                    break
                event = json.loads(raw)
                events.append(event)
                if 'timings' in event:
                    row['timings'] = event['timings']
                if 'usage' in event:
                    row['usage'] = event['usage']
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    content = delta.get('content') or ''
                    reasoning_delta = delta.get('reasoning_content') or ''
                    if first is None and (content or reasoning_delta):
                        first = time.perf_counter() - start
                    text += content
                    thoughts += reasoning_delta
                    if choice.get('finish_reason'):
                        row['finish_reason'] = choice['finish_reason']
        row['first_token_seconds'] = first
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        expected_payload = expected if isinstance(expected, dict) else {'records': expected}
        row.update(text=text, reasoning=thoughts, parsed=parsed, exact=parsed == expected_payload, events=events)
    except Exception as exc:
        row.update(error=str(exc), exact=False, text=text, reasoning=thoughts, events=events)
    row['elapsed_seconds'] = time.perf_counter()-start
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe-only', action='store_true')
    parser.add_argument('--reasoning-check', action='store_true')
    parser.add_argument('--output', default='benchmark.json')
    args = parser.parse_args()
    ps = json.loads(cli('ps', '--json'))
    assert len(ps) == 1 and ps[0]['identifier'] == MODEL and ps[0]['status'] == 'idle' and ps[0]['queued'] == 0
    original = get('http://127.0.0.1:1234/api/v1/models')
    save('original-models.json', original)
    with lms.Client() as client:
        config = client.llm.model(MODEL).get_load_config().to_dict()
    save('original-sdk-config.json', config)
    report = {'conditions': [], 'calls': [], 'warmups': [], 'probe': args.probe_only, 'engine': 'b9553',
              'scope': '同一本体・同一テンプレート・推論OFF。cache_prompt=false。合成原文抽出のみ。', 'restored': False}
    conditions = [('probe-mtp3', 3, 99)] if args.probe_only else [
        ('baseline-first', 0, 99), ('mtp2', 2, 99), ('mtp3', 3, 99), ('mtp5', 5, 99), ('baseline-last', 0, 99)]
    task_source = tasks
    if args.reasoning_check:
        conditions = [('reasoning-baseline', 0, 99), ('reasoning-mtp5', 5, 99)]
        task_source = reasoning_tasks
        report['scope'] = '同一本体・推論ON・条件と例外の判定および整数合計。cache_prompt=false。合成2課題を各2回。'
    process, log = None, None
    try:
        print('Temporarily unloading idle original model.', flush=True)
        cli('unload', MODEL)
        for label, nmax, ngl in conditions:
            print('LOAD', label, flush=True)
            process, log, log_path, command, load_seconds = start_server(label, nmax, ngl, reasoning=args.reasoning_check)
            report['conditions'].append({'label': label, 'draft_max': nmax, 'gpu_layers': ngl,
                'command': command, 'load_seconds': load_seconds, 'props': get(f'http://127.0.0.1:{PORT}/props')})
            warm = request_task(*next(task_source()), label, -1)
            report['warmups'].append(warm)
            print('WARM', label, warm['exact'], warm.get('timings'), flush=True)
            if args.probe_only:
                report['calls'].append(warm)
            else:
                for repeat in range(2):
                    batch = list(task_source())
                    if repeat:
                        batch.reverse()
                    for name, context, expected in batch:
                        row = request_task(name, context, expected, label, repeat)
                        report['calls'].append(row)
                        save(args.output, report)
                        print('RESULT', label, name, repeat, row['exact'], round(row['elapsed_seconds'], 3), row.get('timings'), flush=True)
            stop_server(process, log)
            process, log = None, None
            report['conditions'][-1]['draft_log_lines'] = [line for line in log_path.read_text(encoding='utf-8', errors='replace').splitlines()
                if any(term in line.lower() for term in ('drafted', 'accepted', 'draft-mtp', 'speculative', 'offload'))]
            save(args.output, report)
    except Exception as exc:
        report['error'] = str(exc)
        print('BENCHMARK ERROR', str(exc), flush=True)
    finally:
        if process is not None:
            stop_server(process, log)
        print('Restoring original LM Studio model.', flush=True)
        try:
            cli('load', MODEL, '--identifier', MODEL, '--gpu', str(config['gpu']['ratio']),
                '--context-length', str(ps[0]['contextLength']), '--parallel', str(ps[0]['parallel']), '--no-speculative-draft-mtp', '-y')
            after = get('http://127.0.0.1:1234/api/v1/models')
            save('restored-models.json', after)
            report['restored'] = after == original
            report['restored_ps'] = json.loads(cli('ps', '--json'))
            if not report['restored']:
                report['restoration_difference'] = {'before': original, 'after': after}
        except Exception as exc:
            report['restoration_error'] = str(exc)
        save(args.output, report)
        print('FINISHED', 'restored=', report['restored'], 'calls=', len(report['calls']), flush=True)


if __name__ == '__main__':
    main()
