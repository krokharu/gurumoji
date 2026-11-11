"""合成会話と一時DBだけでローカル再分析を検証する。"""
from __future__ import annotations

import copy
import json
import sqlite3
import sys
import threading
import time
import urllib.request
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services.ai import client as ai_client
from gurumoji.services.ai.settings import lmstudio_reasoning_settings
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.services import group_analysis, segment_embeddings
from gurumoji import transcript_preparation

MODEL = 'google/gemma-4-12b-qat'
BASE = 'http://127.0.0.1:1234/v1'
PROMPT = '追加指示：待ち時間について反例を検討してください。'
calls = []
errors = []
OUTPUT = ROOT / 'output/validation/reanalysis-required-20261109/real-model/r7'


def transport(provider, key, model, system, user, name, schema, check, usage, base='', timeout_seconds=300, **kwargs):
    if provider != 'lmstudio' or model != MODEL or base != BASE:
        raise RuntimeError('ローカル試験の接続先が一致しません。')
    data = kwargs.get('data_messages') or []
    sent = json.dumps([system, user, data], ensure_ascii=False)

    call_record = {'schema': name, 'prompt_sent': PROMPT in sent,
                   'source_resource_sent': any('"resource_id":"reanalysis"' in value for value in data)}
    def post(url, headers, payload, **_kwargs):
        target = urlsplit(url)
        if target.scheme != 'http' or target.hostname != '127.0.0.1' or target.port != 1234:
            raise RuntimeError('許可されていない送信先です。')
        check()
        request = urllib.request.Request(url, json.dumps(payload).encode('utf-8'),
            headers={**headers, 'Content-Type': 'application/json'}, method='POST')
        calls.append(call_record)
        print(json.dumps({'event': 'call_started', **call_record}, ensure_ascii=False), flush=True)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'request.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        try:
            with urllib.request.urlopen(request, timeout=min(timeout_seconds, 300)) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read(65536).decode('utf-8', errors='replace')
            try:
                value = json.loads(body)
                reason = value.get('error', value) if isinstance(value, dict) else value
            except ValueError:
                reason = body
            record = {'http_status': exc.code, 'reason': str(reason)[:2000]}
            (OUTPUT / 'http-error.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'event': 'http_error', **record}, ensure_ascii=False), flush=True)
            raise

    result = ai_client.call_ai_json(provider, key, model, system, user, name, schema,
        post=post, lmstudio_base=lambda _: BASE, lmstudio_model_id=lambda value: value,
        lmstudio_reasoning=lmstudio_reasoning_settings, providers={'lmstudio'}, check_cancelled=check,
        usage_callback=usage, base_url=base, max_output_tokens=kwargs.get('max_output_tokens'),
        data_messages=data, local_reasoning_level=kwargs.get('local_reasoning_level'))
    if name == 'analysis_orchestration_core':
        next_step = result.get('next_step')
        call_record['next_step_kind'] = next_step.get('kind') if isinstance(next_step, dict) else None
        print(json.dumps({'event': 'core_response', 'next_step_kind': call_record['next_step_kind']}), flush=True)
    return result


def main():
    deadline = time.monotonic() + 900
    output = OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    config = SimpleNamespace(lmstudio_base_url=BASE)
    resolve, agent = make_orchestration_adapters(call_ai_json=transport,
        load_token_config=lambda: config, configured_ai_credentials=lambda *_: ('', MODEL))
    item = {'id': 'synthetic-item', 'revision': 'synthetic-v1', 'revision_count': 1, 'analysis_revision': 1}
    utterances = ['受付は早かったです。', '私は少し待ちました。', '午前は空いていたと思います。',
                  '午後は混んでいました。', '次は予約して行きたいです。']
    snapshot = {'input_hash': item['revision'], 'source_revision': 1, 'analysis_revision': 1,
        'analysis': {'segments': [{'id': f'u{i}', 'text': text, 'speaker': 'A' if i % 2 else 'B',
            'start': i * 4, 'end': i * 4 + 3, 'annotation': {'codes': []}}
            for i, text in enumerate(utterances, 1)], 'all_results': {}}}
    report = {'model': MODEL, 'adapter_version': ADAPTER_VERSION, 'runs': [], 'calls': calls, 'errors': errors, 'local_reasoning': 'off',
              'original_run_policy': 'コード結果の生成後に停止し、再分析の呼出しを優先'}
    @contextmanager
    def retained_test_directory():
        directory = output / 'data'
        directory.mkdir(parents=True, exist_ok=True)
        if (directory / 'synthetic.sqlite').exists():
            raise RuntimeError('既存の試験DBを上書きできません。')
        yield directory
    with retained_test_directory() as directory:
        path = Path(directory) / 'synthetic.sqlite'
        @contextmanager
        def connect():
            db = sqlite3.connect(path, timeout=30)
            try:
                with db:
                    yield db
            finally:
                db.close()
        segments = snapshot['analysis']['segments']
        row = {**item, 'source_name': '合成会話', 'segments_json': json.dumps(segments, ensure_ascii=False),
               'speaker_profiles_json': '{}', 'speaker_names_json': '{}', 'session_profile_json': '{}',
               'original_segments_json': '[]', 'original_segments_status': 'unavailable',
               'analysis_config_json': '{}', 'analysis_annotations_json': '{}',
               'analysis_updated_at': None, 'updated_at': '2026-01-01T00:00:00Z', 'media_path': '', 'outline_json': 'null'}
        with connect() as db:
            db.execute('CREATE TABLE analysis_runs (id TEXT, item_id TEXT, stale INTEGER)')
            db.execute('CREATE TABLE analysis_run_members (run_id TEXT, item_id TEXT)')
            db.execute('CREATE TABLE conversation_segments (item_id TEXT, segment_id TEXT)')
            db.execute('CREATE TABLE conversation_speakers (item_id TEXT, speaker_label TEXT, global_speaker_id TEXT)')
            db.execute('CREATE TABLE application_metadata (key TEXT PRIMARY KEY, value TEXT)')
            transcript_preparation.initialize(db)
            segment_embeddings.initialize(db)
        snapshot['analysis'] = group_analysis.group_analysis_for_row(row, connect=connect,
            row_segments=lambda _: segments, row_original_segments=lambda _: ({}, 'unavailable'),
            row_speaker_profiles=lambda *_: {}, row_session_profile=lambda _: {},
            list_speaker_registry=lambda **_: [], execute=True)
        for method in ('participation', 'conversation_dynamics'):
            run_orchestration_method(method, snapshot)
        source_run = {'id': None}
        def observed_agent(role, context, options, check, usage):
            if options.get('_run_id') == source_run['id']:
                print(json.dumps({'event': 'source_run_cancelled', 'run_id': source_run['id']}), flush=True)
                service.cancel(item['id'], options['_run_id'])
                check()
            try:
                return agent(role, context, options, check, usage)
            except Exception as exc:
                errors.append({'type': type(exc).__name__, 'code': getattr(exc, 'code', None)})
                print(json.dumps({'event': 'agent_error', **errors[-1]}), flush=True)
                raise
        service = AnalysisOrchestrationService(connect=connect, find_item=lambda name: item if name == item['id'] else None,
            source_fingerprint=lambda value: value['revision'], snapshot_builder=lambda _: copy.deepcopy(snapshot),
            agent_runner=observed_agent, method_runner=run_orchestration_method, adapter_version=ADAPTER_VERSION, schedule=False)
        payload = resolve({'question': '原文5発話の受付の待ち時間の違いを検討してください。追加取得はできません。現データで回答し、必要な場合だけ追加分析してください。摘要は200文字程度、主張は2件以内にしてください。', 'model': MODEL,
            'provider': 'lmstudio', 'provider_policy': 'local_only', 'stop_mode': 'auto',
            'max_iterations': 8, 'time_limit_seconds': None, 'max_calls': 40, 'max_tasks': 80, 'concurrency': 1,
            'call_timeout_seconds': 300, 'local_reasoning': 'off', 'model_context_version': 1, 'context_reference_version': 1,
            'specialist_orchestration_version': 1, 'core_progress_version': 1, 'core_control_version': 1, 'metric_codec_version': 1,
            'analysis_interval_version': 0, 'required_methods': ['participation', 'conversation_dynamics', 'label_frequency']})
        payload.update(initial_label_definitions_version=0, initial_specialist_analysis_version=0)
        def execute(options):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('試験全体の時間上限に到達しました。')
            value = service.start(item['id'], options)
            if not options.get('source_analysis_id'):
                source_run['id'] = value['run_id']
            timed_out = threading.Event()
            def stop_at_deadline():
                timed_out.set()
                print(json.dumps({'event': 'test_deadline_cancelled', 'run_id': value['run_id']}), flush=True)
                service.cancel(item['id'], value['run_id'])
            timer = threading.Timer(remaining, stop_at_deadline)
            timer.daemon = True
            timer.start()
            try:
                service.run(value['run_id'])
            finally:
                timer.cancel()
            state = service.status(item['id'], value['run_id'])
            report['runs'].append({'run_id': state['run_id'], 'status': state['status'],
                'test_deadline_reached': timed_out.is_set(),
                'stop_reason': state.get('stop_reason'), 'error': state.get('error'),
                'results': [{'result_id': r['result_id'], 'role': r['role'],
                    'validation_status': r['validation_status']} for r in state.get('results', [])],
                'usage': state.get('usage'), 'required_methods_progress': state.get('required_methods_progress')})
            print(json.dumps({'event': 'run_finished', **report['runs'][-1]}, ensure_ascii=False), flush=True)
            return state
        try:
            original = execute(payload)
            selected = next((r for r in original.get('results', []) if r.get('validation_status') == 'valid'), None)
            if selected:
                second = {**payload, 'request_id': 'synthetic-reanalysis',
                          'source_analysis_id': selected['result_id'], 'human_prompt': PROMPT}
                execute(second)
            else:
                report['reason'] = '参照できる検証済み結果がありません。'
        except Exception as exc:
            report['exception'] = {'type': type(exc).__name__, 'message': str(exc)}
        report['reanalysis_call_sent'] = any(call['prompt_sent'] and call['source_resource_sent'] for call in calls)
        (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'event': 'finished', 'reanalysis_call_sent': report['reanalysis_call_sent'],
                          'exception': report.get('exception')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
