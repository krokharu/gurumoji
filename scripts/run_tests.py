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
    return value.lstrip('.').removeprefix('tests.')


def source_hashes():
    paths=[p for directory in ('src','tests','scripts') for p in (ROOT/directory).rglob('*')
        if p.is_file() and p.suffix in {'.py','.js','.cjs','.html','.css','.json','.txt'}
        and not any(part in {'node_modules','__pycache__'} for part in p.parts)]
    paths += list((ROOT/'config').glob('requirements*.txt'))
    catalog=ROOT/'config/analysis_slide_templates.json'
    if catalog.is_file(): paths.append(catalog)
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


class CollectionMetadata:
    """実際の収集結果を、JUnitの実行結果と分けて保存する。"""

    def __init__(self, report, *, target, scope, collect_only):
        self.report = report
        self.data = dict(target=str(target), scope=scope, collect_only=collect_only,
            selected_nodeids=[], deselected_nodeids=[], collection_errors=[], collection_skips=[],
            sources={"main": str(ROOT), "public": os.environ.get("GURUMOJI_COLAB_SOURCE")})
        self.save()

    def save(self):
        self.report.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def pytest_collection_finish(self, session):
        self.data["selected_nodeids"] = [item.nodeid for item in session.items]
        self.save()

    def pytest_deselected(self, items):
        self.data["deselected_nodeids"].extend(item.nodeid for item in items)
        self.save()

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            field = "collection_errors" if report.failed else "collection_skips"
            self.data[field].append(dict(nodeid=report.nodeid, reason=str(report.longrepr)))
            self.save()

    def pytest_sessionfinish(self, session, exitstatus):
        self.data["exit_code"] = int(exitstatus)
        self.save()


def worker(path, result, *, scope="main", collect_only=False):
    from runtime_isolation import configure_environment, application_paths, protect_runtime
    with tempfile.TemporaryDirectory(prefix="gurumoji-test-worker-") as temporary:
        configure_environment(temporary)
        protect_runtime()
        # unittestでも、import時の保存先を一時領域へ統一する。
        import app
        for key, value in application_paths(temporary).items():
            if hasattr(app, key):
                setattr(app, key, value)
        import pytest
        plugin = CollectionMetadata(result.with_suffix(".meta.json"), target=path, scope=scope, collect_only=collect_only)
        options = [str(path), "-q", "--tb=short", "-m", "not real_model and not browser",
            "--junitxml=" + str(result), "-o", "junit_family=xunit2", "-p", "no:cacheprovider"]
        if collect_only:
            options.append("--collect-only")
        return pytest.main(options, plugins=[plugin])


def run_file(path, folder, *, timeout_seconds=600, scope="main", collect_only=False):
    started = time.monotonic()
    target = str(path)
    module = Path(target.split("::", 1)[0]).stem
    suffix = "-collect" if collect_only else ""
    if "::" in target:
        suffix += "-" + hashlib.sha256(target.encode("utf-8")).hexdigest()[:12]
    report = folder / (module + suffix + ".xml")
    report.unlink(missing_ok=True)
    metadata_file = report.with_suffix(".meta.json")
    metadata_file.unlink(missing_ok=True)
    result = dict(module=module, target=target, exit_code=None, tests=0, failures=[], skipped=0,
        collected=False, executed_cases=[], selected_nodeids=[], deselected_nodeids=[],
        collection_errors=[], collection_skips=[], collection_failure=False, not_run=False,
        timeout=False, status="error", report=str(report), metadata=str(metadata_file))
    def read_metadata():
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            for field in ("selected_nodeids", "deselected_nodeids", "collection_errors", "collection_skips", "sources"):
                result[field] = metadata.get(field, [] if field != "sources" else {})
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT / "src"), str(ROOT))),
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    try:
        command = [sys.executable, str(Path(__file__).resolve()), "--worker", target,
            "--report", str(report), "--scope", scope]
        if collect_only:
            command.append("--collect-only")
        process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout_seconds)
        report.with_suffix(".log").write_bytes(process.stdout + process.stderr)
        result["exit_code"] = process.returncode
        read_metadata()
        if report.exists():
            for case in ET.parse(report).iter("testcase"):
                identity = normalize_id(case.attrib.get('classname', module) + "." + case.attrib["name"])
                # pytestはmodule単位SkipTestもtestcaseとして出力することがある。
                if not result["selected_nodeids"]:
                    continue
                result["tests"] += 1
                if case.find("skipped") is not None:
                    result["skipped"] += 1
                else:
                    result["executed_cases"].append(identity)
                if case.find("failure") is not None or case.find("error") is not None:
                    result["failures"].append(identity)
        result["collected"] = bool(result["selected_nodeids"]) and not result["collection_errors"]
        if result["collection_errors"]:
            result.update(status="collection_error", collection_failure=True)
        elif not result["selected_nodeids"] and (result["deselected_nodeids"] or result["collection_skips"]) and process.returncode in (0, 5):
            result.update(status="not_run", not_run=True,
                reason="module_skip" if result["collection_skips"] else "filtered")
        elif collect_only and result["collected"] and process.returncode == 0:
            result["status"] = "collected"
        elif result["tests"] and result["skipped"] == result["tests"] and process.returncode == 0:
            result.update(status="not_run", not_run=True, reason="all_skipped")
        elif not result["collected"]:
            result.update(status="empty_collection" if process.returncode == 5 else "worker_error", collection_failure=True)
        elif result["tests"] and (process.returncode == 0 and not result["failures"]
                                  or process.returncode == 1 and result["failures"]):
            result["status"] = "failed" if result["failures"] else "passed"
        else:
            result.update(status="worker_error", collection_failure=True)
    except subprocess.TimeoutExpired as error:
        def raw(value):
            return value.encode("utf-8") if isinstance(value, str) else value or b""
        report.with_suffix(".log").write_bytes(raw(error.stdout) + raw(error.stderr))
        result.update(exit_code=124, status="timeout", timeout=True)
        try:
            read_metadata()
        except (json.JSONDecodeError, OSError) as metadata_error:
            result["metadata_error"] = str(metadata_error)
    except (ET.ParseError, json.JSONDecodeError, OSError) as error:
        result.update(status="report_error", collection_failure=True, error=str(error))
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def compare_baseline(results, baseline):
    known = set(baseline.get("failures", [])) if baseline else set()
    failures = {identity for row in results for identity in row["failures"]}
    exercised = {identity for row in results for identity in row["executed_cases"]}
    return dict(resolved=sorted((known & exercised) - failures), not_tested=sorted(known - exercised))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--scope", choices=("main", "public"), default="main")
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--split-module", action="append", default=[])
    parser.add_argument("--worker")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--collect-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker, args.report, scope=args.scope, collect_only=args.collect_only)
    if not 1 <= args.jobs <= 20:
        parser.error("--jobs must be between 1 and 20")
    if not 0 < args.timeout_seconds < float("inf"):
        parser.error("--timeout-seconds must be finite and positive")
    folder = (args.output or ROOT / "output" / "validation" / time.strftime("tests-%Y%m%d-%H%M%S")).resolve()
    if not folder.is_relative_to((ROOT / "output" / "validation").resolve()):
        parser.error("test evidence must be under output/validation")
    folder.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / "tests" / (name.removesuffix(".py") + ".py") for name in args.modules] if args.modules else sorted((ROOT / "tests").glob("test_public_colab_*.py" if args.scope == "public" else "test_*.py"))
    if any(not p.is_file() or p.parent != ROOT / "tests" for p in paths):
        parser.error("modules must name existing tests/test_*.py files")
    split = {name.removesuffix(".py") for name in args.split_module}
    if split - {path.stem for path in paths}:
        parser.error("--split-module must name a selected module")
    from runtime_isolation import metadata_snapshot
    before = metadata_snapshot()
    hashes_before=source_hashes()
    started = time.monotonic()
    def execute(path, *, collect_only=False):
        return run_file(path, folder, timeout_seconds=args.timeout_seconds, scope=args.scope, collect_only=collect_only)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        collections = list(pool.map(lambda path: execute(path, collect_only=True), [path for path in paths if path.stem in split]))
        tasks = [path for path in paths if path.stem not in split]
        results = []
        for row in collections:
            if row["status"] == "collected":
                tasks.extend(str(ROOT / nodeid.split("::", 1)[0]) + "::" + nodeid.split("::", 1)[1]
                             for nodeid in row["selected_nodeids"])
            else:
                results.append(row)
        results.extend(pool.map(execute, tasks))
    after = metadata_snapshot()
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    failures = sorted({identity for row in results for identity in row["failures"]})
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    known = set(baseline.get("failures", [])) if baseline else set()
    comparison = compare_baseline(results, baseline)
    flaky_file = ROOT / "tests" / "flaky.txt"
    flaky = {line.strip() for line in flaky_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")} if flaky_file.exists() else set()
    summary = dict(head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        jobs=args.jobs, command=sys.argv, seconds=round(time.monotonic() - started, 3),
        scope=args.scope, timeout_seconds=args.timeout_seconds, split_modules=sorted(split),
        sources={"main": str(ROOT), "public": os.environ.get("GURUMOJI_COLAB_SOURCE")},
        tests=sum(row["tests"] for row in results), skipped=sum(row["skipped"] for row in results),
        failures=failures, new_failures=sorted(set(failures) - known - flaky),
        **comparison, flaky=sorted(set(failures) & flaky),
        collection_failures=sorted({row["module"] for row in results if row["collection_failure"]}),
        not_run=[dict(module=row["module"], target=row["target"], reason=row["reason"]) for row in results if row["not_run"]],
        timeouts=[dict(module=row["module"], target=row["target"]) for row in results if row["timeout"]],
        runtime_changes=changed, results=results, split_collections=collections,
        source_hashes=source_hashes())
    summary['source_changes']=sorted(key for key in hashes_before.keys() | summary['source_hashes'].keys()
        if hashes_before.get(key)!=summary['source_hashes'].get(key))
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("tests", "skipped", "seconds", "new_failures", "collection_failures", "not_run", "timeouts", "runtime_changes")}, ensure_ascii=False))
    print("Evidence: " + str(folder / "summary.json"))
    return int(bool(summary["new_failures"] or summary["collection_failures"] or summary["timeouts"] or changed or summary['source_changes']))


if __name__ == "__main__":
    raise SystemExit(main())
