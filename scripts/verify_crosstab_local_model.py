"""独立した合成DBでクロス集計の実モデル経路を検証する。"""
from __future__ import annotations

import argparse
import copy
import json
import sqlite3
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root, output = args.source_root.resolve(), args.output.resolve()
sys.path.insert(0, str(root / 'src'))
from gurumoji.analysis_core import fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.services.ai import client as ai_client
from gurumoji.services.ai.settings import lmstudio_reasoning_settings

MODEL, BASE = 'google/gemma-4-12b-qat', 'http://127.0.0.1:1234/v1'
QUESTION = ('話者×コードのクロス集計を必須実行してください。価格と味のセル件数・行内割合・分母・欠測を確認し、'
            '集計結果と限界の報告に限定してください。コードは合成試験用の固定分類です。'
            'コードなしは欠測のまま扱い、ラベルを変更しません。複数コードは重複回答です。'
            '追加データは取得できません。追加分析は明らかな計算不整合がある場合だけとし、'
            '摘要は200文字程度、主張は原文で裏付けられる場合だけ2件以内にしてください。')
output.mkdir(parents=True, exist_ok=True)
path = output / 'synthetic.sqlite'
if path.exists():
    raise RuntimeError('既存の試験DBは上書きしません。')
calls, errors = [], []


def transport(provider, key, model, system, user, name, schema, check, usage, base='', timeout_seconds=300, **kwargs):
    if provider != 'lmstudio' or model != MODEL or base != BASE:
        raise RuntimeError('試験の送信先がローカルモデルと一致しません。')
    record = {'schema': name, 'status': 'started'}
    calls.append(record)
    print(json.dumps({'event': 'call_started', 'number': len(calls), 'schema': name}), flush=True)
    started = time.monotonic()
    def post(url, headers, payload, **_):
        target = urlsplit(url)
        if target.scheme != 'http' or target.hostname != '127.0.0.1' or target.port != 1234:
            raise RuntimeError('試験の送信先を許可できません。')
        check()
        request = urllib.request.Request(url, json.dumps(payload).encode('utf-8'),
            headers={**headers, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read())
    try:
        result = ai_client.call_ai_json(provider, key, model, system, user, name, schema,
            post=post, lmstudio_base=lambda _: BASE, lmstudio_model_id=lambda value: value,
            lmstudio_reasoning=lmstudio_reasoning_settings, providers={'lmstudio'}, check_cancelled=check,
            usage_callback=usage, base_url=base, max_output_tokens=kwargs.get('max_output_tokens'),
            data_messages=kwargs.get('data_messages') or [], local_reasoning_level=kwargs.get('local_reasoning_level'))
        record.update(status='returned', seconds=round(time.monotonic() - started, 2))
        print(json.dumps({'event': 'call_finished', **record}), flush=True)
        return result
    except Exception as exc:
        record.update(status='failed', error_type=type(exc).__name__)
        errors.append({'type': type(exc).__name__, 'code': getattr(exc, 'code', None)})
        raise


@contextmanager
def connect():
    db = sqlite3.connect(path, timeout=30)
    try:
        with db:
            yield db
    finally:
        db.close()


samples = [('A', '価格が高いですが味は好きです。', ['価格', '味', '価格']),
           ('A', '追加料金が気になります。', ['価格']),
           ('A', '次回は友人と行きます。', []),
           ('B', '味が好きです。', ['味']),
           ('B', '価格と味を合わせて選びます。', ['価格', '味']),
           ('B', '辛い味が好きです。', ['味'])]
item = {'id': 'synthetic-crosstab', 'revision': 'synthetic-crosstab-v1', 'revision_count': 1, 'analysis_revision': 1}
snapshot = {'input_hash': item['revision'], 'source_revision': 1, 'analysis_revision': 1,
            'analysis': {'segments': [{'id': f'u{i}', 'speaker': speaker, 'text': text,
                                      'start': i * 4, 'end': i * 4 + 3, 'annotation': {'codes': labels}}
                                     for i, (speaker, text, labels) in enumerate(samples, 1)], 'all_results': {}}}
before = fingerprint(snapshot)
with connect() as db:
    db.execute('CREATE TABLE analysis_runs (id TEXT, item_id TEXT, stale INTEGER)')
    db.execute('CREATE TABLE analysis_run_members (run_id TEXT, item_id TEXT)')
resolve, agent = make_orchestration_adapters(call_ai_json=transport,
    load_token_config=lambda: SimpleNamespace(lmstudio_base_url=BASE),
    configured_ai_credentials=lambda *_: ('', MODEL))
service = AnalysisOrchestrationService(connect=connect,
    find_item=lambda key: item if key == item['id'] else None,
    source_fingerprint=lambda value: value['revision'], snapshot_builder=lambda _: copy.deepcopy(snapshot),
    agent_runner=agent, method_runner=run_orchestration_method, adapter_version=ADAPTER_VERSION, schedule=False)
payload = resolve({'question': QUESTION, 'provider': 'lmstudio', 'model': MODEL, 'provider_policy': 'local_only',
    'stop_mode': 'auto', 'max_iterations': 8, 'max_calls': 30, 'max_tasks': 60, 'concurrency': 1,
    'time_limit_seconds': None, 'call_timeout_seconds': 300, 'local_reasoning': 'off',
    'model_context_version': 1, 'context_reference_version': 1, 'metric_codec_version': 1,
    'specialist_orchestration_version': 1, 'core_progress_version': 1, 'core_control_version': 1,
    'analysis_interval_version': 0, 'required_methods': ['cross_tabulation']})
# 既存の合成コードに対する集計を試験し、新規ラベル作成の品質評価とは分ける。
payload.update(initial_label_definitions_version=0, initial_specialist_analysis_version=0)
state = service.start(item['id'], payload)
deadline = threading.Event()
def cancel_at_deadline():
    deadline.set()
    service.cancel(item['id'], state['run_id'])
timer = threading.Timer(900, cancel_at_deadline)
timer.daemon = True
timer.start()
report = {'model': MODEL, 'adapter_version': ADAPTER_VERSION, 'input_kind': 'synthetic', 'calls': calls,
          'errors': errors, 'scope': '既存の合成ラベルを指定したクロス集計。初回ラベル生成と実利用者データは対象外。'}
try:
    service.run(state['run_id'])
    final = service.status(item['id'], state['run_id'])
    exported = service.result(item['id'], state['run_id'])
    report.update(run_id=final['run_id'], status=final['status'], stop_reason=final.get('stop_reason'),
                  error=final.get('error'), analysis_processing_complete=final.get('analysis_processing_complete', False),
                  required_methods_progress=final['required_methods_progress'], usage=final['usage'],
                  tasks=[{k: task.get(k) for k in ('task_id', 'role', 'method_id', 'status', 'error')}
                         for task in final['tasks']], core_iterations=final['iteration'])
    (output / 'history.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding='utf-8')
    # 接続を開き直して原結果とhashを照合する。
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        records = db.execute('SELECT raw_json,state_json FROM orchestration_results WHERE run_id=?', (final['run_id'],)).fetchall()
        assert all(fingerprint(json.loads(raw)) == json.loads(meta)['raw_hash'] for raw, meta in records)
        raw, metadata = next((json.loads(raw), json.loads(meta)) for raw, meta in records
                             if json.loads(raw).get('method_id') == 'cross_tabulation')
        receipts = [json.loads(meta)['metric_validation'] for _, meta in records if json.loads(meta).get('metric_validation')]
        assert receipts and all(receipt['status'] == 'answered' for receipt in receipts)
        cells = {(row['speaker'], row['label']): row['count'] for row in raw['rows']}
        assert cells == {('A', '価格'): 2, ('A', '味'): 1, ('B', '価格'): 1, ('B', '味'): 3}
        assert (raw['denominator'], raw['observed_count'], raw['missing_count'], raw['total_assignments']) == (6, 5, 1, 7)
        assert next(row['row_proportion'] for row in raw['rows'] if (row['speaker'], row['label']) == ('A', '価格')) == 2 / 3
        report['fresh_verification'] = {'raw_hashes_valid': True, 'known_matrix_matched': True,
                                        'metric_decoder_receipts': len(receipts), 'source_unchanged': before == fingerprint(snapshot)}
        (output / 'cross-result.json').write_text(json.dumps({**metadata, 'raw': raw}, ensure_ascii=False, indent=2), encoding='utf-8')
    assert not deadline.is_set() and not errors
    assert all(task['status'] == 'succeeded' for task in final['tasks'])
    assert all(progress['complete'] for progress in final['required_methods_progress'])
    assert final.get('analysis_processing_complete') or final['status'] == 'completed'
    report['result'] = 'passed'
except Exception as exc:
    report.update(result='failed', exception={'type': type(exc).__name__, 'message': str(exc)})
finally:
    timer.cancel()
    report['deadline_reached'] = deadline.is_set()
    (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'event': 'finished', 'result': report['result'], 'run_id': state['run_id'],
                      'stop_reason': report.get('stop_reason'), 'exception': report.get('exception')}, ensure_ascii=False), flush=True)
if report['result'] != 'passed':
    raise SystemExit(1)
