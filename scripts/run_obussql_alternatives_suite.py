"""モデル呼出しとCPU測定を逐次実行し、測定同士の競合を避ける。"""
import json
from pathlib import Path
import subprocess
import sys
import time

scripts = Path(__file__).resolve().parent
out = scripts.parents[3] / 'output/validation/obussql-alternatives-20261110'
report = []
for script, mode in [
    ('compare_obussql_external_plans.py', 'generation'),
    ('compare_obussql_external_plans.py', 'structured'),
    ('compare_obussql_external_plans.py', 'host'),
    ('compare_obussql_external_plans.py', 'cache'),
    ('compare_obussql_external_plans.py', 'speculative'),
    ('test_obussql_retrieval_compression.py', 'retrieval'),
    ('test_obussql_retrieval_compression.py', 'compression'),
]:
    print('START', mode, flush=True)
    start = time.perf_counter()
    result = subprocess.run([sys.executable, '-u', str(scripts / script), mode], cwd=scripts.parents[3])
    report.append({'mode': mode, 'exit_code': result.returncode, 'elapsed_seconds': time.perf_counter()-start})
    (out / 'suite.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('FINISH', mode, result.returncode, flush=True)
