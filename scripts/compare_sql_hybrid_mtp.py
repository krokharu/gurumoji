"""同じ合成課題でSQL・全文生成・ID選択とSQL復元を比較する。"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import statistics
import sys
import time

import benchmark_gemma_speculative as bench
import lmstudio as lms

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/validation/obussql-sql-hybrid-mtp-20261110'
OUT.mkdir(parents=True, exist_ok=True)
bench.OUT = OUT


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def make_cases():
    for name, context, expected in bench.tasks():
        yield {'name': name, 'kind': 'records', 'context': context, 'expected': {'records': expected}}
    for name, context, expected in bench.reasoning_tasks():
        yield {'name': name, 'kind': 'rules', 'context': context, 'expected': expected}


def make_database(case):
    start = time.perf_counter()
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE source(id TEXT PRIMARY KEY,body TEXT NOT NULL,consent INT,retest TEXT,submitted INT,withdrawn INT,value INT)')
    if case['kind'] == 'records':
        rows = case['context']['results']
        for row in rows:
            db.execute('INSERT INTO source(id,body) VALUES (?,?)', (row['evidence_id'], json.dumps(row, ensure_ascii=False)))
    else:
        rows = case['context']['rows']
        for row in rows:
            db.execute('INSERT INTO source VALUES (?,?,?,?,?,?,?)', (row['id'], json.dumps(row, ensure_ascii=False), row['consent'], row['retest'], row['submitted'], row['withdrawn'], row['value']))
    db.commit()
    return db, time.perf_counter()-start


def restore_ids(case, db, ids):
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate source IDs')
    rows = []
    for eid in ids:
        found = db.execute('SELECT body FROM source WHERE id=?', (eid,)).fetchone()
        if found is None:
            raise ValueError('unissued source ID')
        rows.append(json.loads(found[0]))
    if case['kind'] == 'records':
        return {'records': [{k: r[k] for k in ('evidence_id', 'condition', 'exception', 'value')} for r in rows]}
    # 合計と表示順はホストが確定し、モデルから数値を転記しない。
    return {'ids': sorted(ids), 'total': sum(r['value'] for r in rows)}


def pure_sql(case, db):
    if case['kind'] == 'records':
        ids = re.findall(r'(?:check-)?ev-\d{4}', case['context']['question'])
    else:
        # 自由文からSQLを生成する試験ではなく、事前定義された2条件を実行する。
        where = "retest='positive' AND submitted=1" if case['name'].endswith('strict') else "(retest='positive' OR (retest='negative' AND submitted=1))"
        ids = [r[0] for r in db.execute('SELECT id FROM source WHERE consent=1 AND withdrawn=0 AND ' + where + ' ORDER BY id')]
    result = restore_ids(case, db, ids)
    return json.loads(json.dumps(result, ensure_ascii=False, separators=(',', ':')))


def build_request(case, method):
    context = case['context']
    if method == 'full':
        if case['kind'] == 'records':
            user, guidance = bench.payload(context, 'adaptive')
            count = len(re.findall(r'(?:check-)?ev-\d{4}', context['question']))
            system = bench.SYSTEM.replace('指定順に2件だけ返す。', f'指定順に{count}件だけ返す。') + guidance
            keys = ('evidence_id', 'condition', 'exception', 'value')
            schema = {'type': 'object', 'additionalProperties': False, 'required': ['records'], 'properties': {
                'records': {'type': 'array', 'minItems': count, 'maxItems': count, 'items': {
                    'type': 'object', 'additionalProperties': False, 'required': list(keys),
                    'properties': {k: {'type': 'integer' if k == 'value' else 'string'} for k in keys}}}}}
        else:
            user = json.dumps(context, ensure_ascii=False, separators=(',', ':'))
            system = '合成資料のruleに従って採用者を判定する。採用したidを昇順のidsに、採用者のvalueの合計を整数totalに入れ、JSONで返す。例外・否定・不明を厳密に区別する。'
            schema = {'type': 'object', 'additionalProperties': False, 'required': ['ids', 'total'], 'properties': {
                'ids': {'type': 'array', 'items': {'type': 'string', 'enum': [r['id'] for r in context['rows']]}}, 'total': {'type': 'integer'}}}
    else:
        system = '資料の条件に従い、該当する出典IDだけをJSONのids配列で返す。指定順がある場合はその順序、条件判定ならID昇順にする。'
        if case['kind'] == 'records':
            ids = [r['evidence_id'] for r in context['results']]
            user = json.dumps({'question': context['question'], 'available_ids': ids}, ensure_ascii=False, separators=(',', ':'))
        else:
            ids = [r['id'] for r in context['rows']]
            user = json.dumps({'rule': context['rule'], 'rows': [{k: v for k, v in r.items() if k != 'value'} for r in context['rows']]}, ensure_ascii=False, separators=(',', ':'))
        array = {'type': 'array', 'items': {'type': 'string', 'enum': ids}}
        if case['kind'] == 'records':
            count = len(re.findall(r'(?:check-)?ev-\d{4}', context['question']))
            array.update(minItems=count, maxItems=count)
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['ids'], 'properties': {'ids': array}}
    return {'model': 'synthetic-spec-test', 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'temperature': 0, 'seed': 42, 'top_p': 1, 'top_k': 0, 'min_p': 0, 'repeat_penalty': 1, 'max_tokens': 1400,
        'chat_template_kwargs': {'enable_thinking': False}, 'cache_prompt': False, 'stream': True,
        'stream_options': {'include_usage': True},
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'comparison_result', 'strict': True, 'schema': schema}}}


def call(case, db, method, phase, repeat):
    start = time.perf_counter()
    body = build_request(case, method)
    row = {'case': case['name'], 'kind': case['kind'], 'method': method, 'phase': phase, 'repeat': repeat,
           'expected': case['expected'], 'request_sha256': hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
    row['prepare_ms'] = (time.perf_counter()-start) * 1000
    text, thoughts, events = '', '', []
    model_start = time.perf_counter()
    try:
        with bench.post('/v1/chat/completions', body) as response:
            for line in response:
                if not line.startswith(b'data: '):
                    continue
                raw = line[6:].strip()
                if raw == b'[DONE]':
                    break
                event = json.loads(raw)
                events.append(event)
                if event.get('timings'):
                    row['timings'] = event['timings']
                if event.get('usage'):
                    row['usage'] = event['usage']
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {})
                    content = delta.get('content') or ''
                    thought = delta.get('reasoning_content') or ''
                    if 'ttft_seconds' not in row and (content or thought):
                        row['ttft_seconds'] = time.perf_counter()-model_start
                    text += content
                    thoughts += thought
                    if choice.get('finish_reason'):
                        row['finish_reason'] = choice['finish_reason']
        row['model_seconds'] = time.perf_counter()-model_start
        parsed = json.loads(text)
        resolve = time.perf_counter()
        result = parsed if method == 'full' else restore_ids(case, db, parsed['ids'])
        result = json.loads(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        row.update(parsed=parsed, result=result, exact=result == case['expected'], sql_resolve_ms=(time.perf_counter()-resolve)*1000)
    except Exception as exc:
        row.update(error=str(exc), exact=False)
    row.update(text=text, reasoning=thoughts, events=events, elapsed_seconds=time.perf_counter()-start)
    return row


def main():
    report = {'calls': [], 'sql': [], 'warmups': [], 'conditions': [], 'restored': False,
              'limitations': ['SQLは既知の条件を事前クエリ化。自由文からSQLを生成する性能は含まない。',
                  '意味検索・自由な研究解釈は含まない。SQLのDB作成とAIのモデルロードは時間から除外し別掲。',
                  'ハイブリッドはAIがIDだけ選び、SQLが原文復元・数値取得・合計を行う。',
                  '推論OFF、同一エンジンb9553、全GPU、parallel1/context8192、cache_prompt=false。']}
    cases = list(make_cases())
    connections = {}
    for case in cases:
        db, setup = make_database(case)
        connections[case['name']] = db
        durations, good = [], 0
        for _ in range(200):
            start = time.perf_counter()
            result = pure_sql(case, db)
            durations.append((time.perf_counter()-start)*1000)
            good += result == case['expected']
        report['sql'].append({'case': case['name'], 'kind': case['kind'], 'n': 200, 'exact': good,
            'median_ms': statistics.median(durations), 'mean_ms': statistics.mean(durations), 'setup_seconds': setup, 'result': result})
    save('comparison.json', report)
    ps = json.loads(bench.cli('ps', '--json'))
    assert len(ps) == 1 and ps[0]['identifier'] == bench.MODEL and ps[0]['status'] == 'idle' and ps[0]['queued'] == 0
    original = bench.get('http://127.0.0.1:1234/api/v1/models')
    save('original-models.json', original)
    with lms.Client() as client:
        config = client.llm.model(bench.MODEL).get_load_config().to_dict()
    save('original-sdk-config.json', config)
    process, log = None, None
    try:
        bench.cli('unload', bench.MODEL)
        for phase, nmax in [('normal', 0), ('mtp5', 5)]:
            print('LOAD', phase, flush=True)
            process, log, log_path, command, load_seconds = bench.start_server('compare-' + phase, nmax)
            report['conditions'].append({'phase': phase, 'command': command, 'load_seconds': load_seconds})
            for method in ('full', 'hybrid'):
                warm = call(cases[0], connections[cases[0]['name']], method, phase, -1)
                report['warmups'].append(warm)
            for repeat in range(2):
                batch = cases if not repeat else list(reversed(cases))
                for index, case in enumerate(batch):
                    methods = ('full', 'hybrid') if (index+repeat) % 2 == 0 else ('hybrid', 'full')
                    for method in methods:
                        row = call(case, connections[case['name']], method, phase, repeat)
                        report['calls'].append(row)
                        save('comparison.json', report)
                        print('RESULT', phase, method, case['name'], repeat, row['exact'], round(row['elapsed_seconds'], 4), row.get('timings', {}).get('prompt_n'), flush=True)
            bench.stop_server(process, log)
            process, log = None, None
    except Exception as exc:
        report['error'] = str(exc)
        print('ERROR', str(exc), flush=True)
    finally:
        if process is not None:
            bench.stop_server(process, log)
        for db in connections.values():
            db.close()
        print('Restoring original model.', flush=True)
        try:
            bench.cli('load', bench.MODEL, '--identifier', bench.MODEL, '--gpu', str(config['gpu']['ratio']),
                '--context-length', str(ps[0]['contextLength']), '--parallel', str(ps[0]['parallel']), '--no-speculative-draft-mtp', '-y')
            after = bench.get('http://127.0.0.1:1234/api/v1/models')
            save('restored-models.json', after)
            report['restored'] = after == original
        except Exception as exc:
            report['restoration_error'] = str(exc)
        save('comparison.json', report)
        print('FINISHED', len(report['calls']), 'model responses; restored=', report['restored'], flush=True)


if __name__ == '__main__':
    main()
