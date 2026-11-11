"""保存済み合成DBを別プロセスで再読し、再計算と専用decoderを照合する。"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--directory', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source_root.resolve() / 'src'))
from gurumoji.analysis_core import fingerprint
from gurumoji.services.analysis_orchestration_methods import run_orchestration_method
from gurumoji.services.metric_delivery import validate
from gurumoji.services.orchestration_required_methods import required_progress

directory = args.directory.resolve()
with sqlite3.connect((directory / 'synthetic.sqlite').as_uri() + '?mode=ro', uri=True) as db:
    run = json.loads(db.execute('SELECT state_json FROM orchestration_runs').fetchone()[0])
    tasks = [json.loads(row[0]) for row in db.execute('SELECT state_json FROM orchestration_tasks')]
    records = [(json.loads(raw), json.loads(meta)) for raw, meta in db.execute('SELECT raw_json,state_json FROM orchestration_results')]
    decisions = [json.loads(row[0]) for row in db.execute('SELECT payload_json FROM orchestration_decisions')]
    assert all(fingerprint(raw) == meta['raw_hash'] for raw, meta in records)
    snapshot = json.loads(db.execute('SELECT snapshot_json FROM orchestration_initials WHERE initial_id=?',
                                    (run['initial_id'],)).fetchone()[0])
    original = fingerprint(snapshot)
    result, metadata = next((raw, meta) for raw, meta in records if raw.get('method_id') == 'cross_tabulation')
    task = next(task for task in tasks if task['task_id'] == metadata['task_id'])
    snapshot['orchestration_task'] = task
    snapshot['orchestration_labels'] = json.loads(db.execute(
        'SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?',
        (run['run_id'], task['annotation_version'])).fetchone()[0])
    recalculated = run_orchestration_method('cross_tabulation', snapshot)
    assert fingerprint(recalculated) == metadata['raw_hash']
    assert {(r['speaker'], r['label']): r['count'] for r in result['rows']} == {
        ('A', '価格'): 2, ('A', '味'): 1, ('B', '価格'): 1, ('B', '味'): 3}
    receipts = 0
    for response, meta in records:
        if not meta.get('metric_validation'):
            continue
        source_task = next(task for task in tasks if task['task_id'] == meta['task_id'])
        assert validate(db, run, source_task, response) == meta['metric_validation']
        receipts += 1
    progress = required_progress(run['config']['required_methods'], tasks, [meta for _, meta in records], decisions,
        dataset_version=run['input_hash'], annotation_version=run['annotation_version'],
        codebook_version=run['codebook_version'], run_stale=run.get('stale', False))
    assert receipts and all(entry['complete'] for entry in progress)
    assert all(task['status'] == 'succeeded' for task in tasks)
    assert run.get('analysis_processing_complete') or run['status'] == 'completed'
    saved = json.loads(db.execute('SELECT snapshot_json FROM orchestration_initials WHERE initial_id=?',
                                 (run['initial_id'],)).fetchone()[0])
    assert fingerprint(saved) == original
    report = {'result': 'passed', 'run_id': run['run_id'], 'database_mode': 'ro', 'raw_hashes_match': True,
              'recalculated_result_hash_matches': True, 'metric_decoder_receipts_match': receipts,
              'required_methods_complete': True, 'fixed_input_unchanged': True}
(directory / 'fresh-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
