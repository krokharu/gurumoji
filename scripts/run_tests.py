"""Isolated module workers, complete collection and reproducible failure comparison.

python scripts/run_tests.py --jobs 4 [test_module ...]
python scripts/run_tests.py --jobs 1 --baseline output/validation/previous/summary.json
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "src"), str(ROOT)]


def normalize_id(value):
    value = value.replace("\\", "/").replace("tests/", "").replace(".py", "").replace('::','.')
    return value.removeprefix('tests.')


def source_hashes():
    paths=[p for directory in ('src','tests','scripts') for p in (ROOT/directory).rglob('*')
        if p.is_file() and p.suffix in {'.py','.js','.cjs','.html','.css','.json','.txt'}
        and not any(part in {'node_modules','__pycache__'} for part in p.parts)]
    paths += list((ROOT/'config').glob('requirements*.txt'))
    catalog=ROOT/'config/analysis_slide_templates.json'
    if catalog.is_file(): paths.append(catalog)
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def worker(path, result):
    from runtime_isolation import configure_environment, application_paths, protect_runtime
    with tempfile.TemporaryDirectory(prefix="gurumoji-test-worker-") as temporary:
        configure_environment(temporary)
        protect_runtime()
        # Patch import-time constants too, so unittest has the same isolation.
        import app
        for key, value in application_paths(temporary).items():
            if hasattr(app, key):
                setattr(app, key, value)
        import pytest
        return pytest.main([str(path), "-q", "--tb=short", "-m", "not real_model and not browser",
            "--junitxml=" + str(result), "-o", "junit_family=xunit2", "-p", "no:cacheprovider"])


def run_file(path, folder):
    started = time.monotonic()
    report = folder / (path.stem + ".xml")
    report.unlink(missing_ok=True)
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT / "src"), str(ROOT))),
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    try:
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(path),
            "--report", str(report)], cwd=ROOT, env=environment, capture_output=True, timeout=600)
        (folder / (path.stem + ".log")).write_bytes(process.stdout + process.stderr)
        result = dict(module=path.stem, exit_code=process.returncode, tests=0, failures=[], skipped=0,
            seconds=round(time.monotonic() - started, 3), collected=False)
        if report.exists():
            for case in ET.parse(report).iter("testcase"):
                result["tests"] += 1
                if case.find("skipped") is not None:
                    result["skipped"] += 1
                if case.find("failure") is not None or case.find("error") is not None:
                    result["failures"].append(normalize_id(case.attrib.get('classname',path.stem) + "." + case.attrib["name"]))
            result["collected"] = result["tests"] > 0 and (
                process.returncode==0 and not result['failures'] or process.returncode==1 and bool(result['failures']))
        return result
    except (subprocess.TimeoutExpired,ET.ParseError):
        return dict(module=path.stem, exit_code=124, tests=0, failures=[], skipped=0,
            collected=False, seconds=round(time.monotonic() - started, 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker, args.report)
    if not 1 <= args.jobs <= 20:
        parser.error("--jobs must be between 1 and 20")
    folder = (args.output or ROOT / "output" / "validation" / time.strftime("tests-%Y%m%d-%H%M%S")).resolve()
    if not folder.is_relative_to((ROOT / "output" / "validation").resolve()):
        parser.error("test evidence must be under output/validation")
    folder.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / "tests" / (name.removesuffix(".py") + ".py") for name in args.modules] if args.modules else sorted((ROOT / "tests").glob("test_*.py"))
    if any(not p.is_file() or p.parent != ROOT / "tests" for p in paths):
        parser.error("modules must name existing tests/test_*.py files")
    from runtime_isolation import metadata_snapshot
    before = metadata_snapshot()
    hashes_before=source_hashes()
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda path: run_file(path, folder), paths))
    after = metadata_snapshot()
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    failures = sorted({identity for row in results for identity in row["failures"]})
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    known = set(baseline.get("failures", [])) if baseline else set()
    collected_modules={row['module'] for row in results if row['collected']}
    exercised={identity for identity in known if identity.split('.')[0] in collected_modules}
    flaky_file = ROOT / "tests" / "flaky.txt"
    flaky = {line.strip() for line in flaky_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")} if flaky_file.exists() else set()
    summary = dict(head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        jobs=args.jobs, command=sys.argv, seconds=round(time.monotonic() - started, 3),
        tests=sum(row["tests"] for row in results), skipped=sum(row["skipped"] for row in results),
        failures=failures, new_failures=sorted(set(failures) - known - flaky),
        resolved=sorted(exercised - set(failures)), not_tested=sorted(known-exercised), flaky=sorted(set(failures) & flaky),
        collection_failures=[row["module"] for row in results if not row["collected"]],
        runtime_changes=changed, results=results,
        source_hashes=source_hashes())
    summary['source_changes']=sorted(key for key in hashes_before.keys() | summary['source_hashes'].keys()
        if hashes_before.get(key)!=summary['source_hashes'].get(key))
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("tests", "skipped", "seconds", "new_failures", "collection_failures", "runtime_changes")}, ensure_ascii=False))
    print("Evidence: " + str(folder / "summary.json"))
    return int(bool(summary["new_failures"] or summary["collection_failures"] or changed or summary['source_changes']))


if __name__ == "__main__":
    raise SystemExit(main())
