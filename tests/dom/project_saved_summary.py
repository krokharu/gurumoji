"""Project synthetic saved results with the tested checkout's pure query function.

This intentionally does not import app, open a database, or start a server. The
JSON on stdin is test-owned synthetic data; it is never evaluated as Python.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "src"))
from gurumoji.handlers.analysis_queries import saved_result_summary

assert "app" not in sys.modules, "The offline projector must not import app"
results = json.load(sys.stdin)
before = deepcopy(results)
summaries = {name: saved_result_summary(result) for name, result in results.items()}
assert results == before, "Summary projection must not change saved values"
json.dump(summaries, sys.stdout, ensure_ascii=False, allow_nan=False)
sys.stdout.write("\n")
