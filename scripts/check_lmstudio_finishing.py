"""Run synthetic finishing checks against the configured local LM Studio model.

Run with PYTHONPATH=src. Never sends recording data or changes library records.
"""
import json
import argparse
import time
from pathlib import Path

import app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', help='Loaded model identifier; does not change app settings')
    parser.add_argument('--report', default='runtime/lmstudio-finishing-check.json')
    options = parser.parse_args()
    config = app.load_token_config()
    model = options.model or config.lmstudio_model
    report = {"model": model, "checks": []}
    destination = Path(options.report)
    destination.parent.mkdir(exist_ok=True)

    def save():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def check(label, operation):
        start = time.monotonic()
        print('START ' + label, flush=True)
        try:
            result = operation()
            item = {"check": label, "ok": True, "result": result}
        except Exception as exc:
            item = {"check": label, "ok": False, "error": str(exc)}
        item['seconds'] = round(time.monotonic() - start, 2)
        report['checks'].append(item)
        save()
        print(json.dumps(item, ensure_ascii=False), flush=True)
        return item

    kwargs = dict(base_url=config.lmstudio_base_url)
    args = ('lmstudio', config.lmstudio_api_key, model)
    schema = {"type": "object", "properties": {"answer": {"type": "integer"}},
              "required": ["answer"], "additionalProperties": False}
    for level in ('auto', 'low', 'medium', 'high'):
        def probe(level=level):
            result = app.call_ai_json(*args, '指定のJSON形式で回答してください。', '17と25の合計は？',
                                      'transcript_cleanup', schema, ai_efforts={'cleanup': level}, **kwargs)
            assert result == {'answer': 42}, result
            return result
        check('effort_' + level, probe)

    segments = [
        {'id': 'check-1', 'speaker': 'A', 'start': 0., 'end': 4., 'text': '私は田中です。今日は新しい予約画面について相談します。'},
        {'id': 'check-2', 'speaker': 'B', 'start': 4., 'end': 8., 'text': '私は佐藤です。予約ボタンが見つけにくいと思います。'},
        {'id': 'check-3', 'speaker': 'A', 'start': 8., 'end': 12., 'text': 'ではボタンを大きくする案を来週試しましょう。'},
        {'id': 'check-4', 'speaker': 'B', 'start': 12., 'end': 16., 'text': '費用についてはまだ決めていません。'}]
    efforts = {'outline': 'medium', 'cleanup': 'high', 'name_extract': 'low', 'name_verify': 'high'}
    kwargs['ai_efforts'] = efforts
    usage = []
    status = lambda message: print(message, flush=True)
    cancelled = lambda: None
    def make_outline():
        result = app.create_outline_with_ai(segments, {}, *args, status, cancelled, usage.append, **kwargs)
        assert result.get('sections'), 'Outline must contain at least one grounded topic'
        assert all(section.get('bullet_evidence') for section in result['sections']), 'Missing evidence'
        return result
    outline = check('outline', make_outline)
    if outline['ok']:
        def cleanup():
            revised = app.clean_segments_with_ai(segments, *args, status, cancelled, usage.append,
                                                outline=outline['result'], **kwargs)
            assert [s['id'] for s in revised] == [s['id'] for s in segments]
            assert len(revised) == len(segments) and all(s['text'].strip() for s in revised)
            return revised
        check('cleanup', cleanup)
    def names():
        requests_before = len(usage)
        result = app.detect_speaker_names_with_ai(segments, *args, cancelled, usage.append, status, **kwargs)
        assert result == {'A': '田中', 'B': '佐藤'}, result
        assert len(usage) - requests_before == 2, 'Both speaker passes must succeed; fallback is not a pass'
        return result
    check('speaker_identity', names)
    report['usage'] = usage
    report['all_passed'] = all(row['ok'] for row in report['checks']) and len(report['checks']) == 7
    save()
    raise SystemExit(0 if report['all_passed'] else 1)


if __name__ == '__main__':
    main()
