"""未実行の誤判定、証跡の欠落、実データへの試験副作用を防ぐ。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "scripts/run_tests.py"
    spec = importlib.util.spec_from_file_location("isolated_test_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outcome(*, selected=(), deselected=(), errors=(), skips=()):
    return dict(selected_nodeids=list(selected), deselected_nodeids=list(deselected),
                collection_errors=list(errors), collection_skips=list(skips))


def fake_process(monkeypatch, runner, metadata, xml="", exit_code=0):
    def run(command, **kwargs):
        report = Path(command[command.index("--report") + 1])
        report.with_suffix(".meta.json").write_text(json.dumps(metadata), encoding="utf-8")
        if xml:
            report.write_text(xml, encoding="utf-8")
        return SimpleNamespace(returncode=exit_code, stdout=b"stdout\n", stderr=b"stderr\n")
    monkeypatch.setattr(runner.subprocess, "run", run)


def test_filtered_exit_five_is_not_a_collection_failure(runner, tmp_path, monkeypatch):
    fake_process(monkeypatch, runner, outcome(deselected=["tests/test_sample.py::test_browser"]), exit_code=5)
    result = runner.run_file(Path("test_sample.py"), tmp_path)
    assert result["not_run"] and result["reason"] == "filtered"
    assert not result["collection_failure"]
    assert result["deselected_nodeids"] == ["tests/test_sample.py::test_browser"]


def test_empty_collection_stays_an_error(runner, tmp_path, monkeypatch):
    fake_process(monkeypatch, runner, outcome(), exit_code=5)
    result = runner.run_file(Path("test_sample.py"), tmp_path)
    assert result["status"] == "empty_collection"
    assert result["collection_failure"] and not result["not_run"]


def test_collection_error_is_preserved_without_inventing_an_executed_case(runner, tmp_path, monkeypatch):
    errors = [{"nodeid": "tests/test_sample.py", "reason": "ImportError: synthetic dependency"}]
    fake_process(monkeypatch, runner, outcome(errors=errors),
                 '<testsuite><testcase classname="" name="test_sample"><error>ImportError</error></testcase></testsuite>', 2)
    result = runner.run_file(Path("test_sample.py"), tmp_path)
    assert result["collection_errors"] == errors
    assert result["collection_failure"]
    assert result["executed_cases"] == []


def test_baseline_resolution_requires_the_exact_executed_case(runner, tmp_path, monkeypatch):
    selected = ["tests/test_sample.py::test_pass", "tests/test_sample.py::test_skip"]
    xml = ('<testsuite><testcase classname="tests.test_sample" name="test_pass"/>'
           '<testcase classname="tests.test_sample" name="test_skip"><skipped/></testcase></testsuite>')
    fake_process(monkeypatch, runner, outcome(selected=selected), xml)
    result = runner.run_file(Path("test_sample.py"), tmp_path)
    baseline = {"failures": ["test_sample.test_pass", "test_sample.test_skip", "test_sample.test_filtered"]}
    assert runner.compare_baseline([result], baseline) == {
        "resolved": ["test_sample.test_pass"],
        "not_tested": ["test_sample.test_filtered", "test_sample.test_skip"],
    }


def test_all_skipped_is_not_run_and_does_not_resolve_a_failure(runner, tmp_path, monkeypatch):
    fake_process(monkeypatch, runner, outcome(selected=["tests/test_sample.py::test_skip"]),
        '<testsuite><testcase classname="tests.test_sample" name="test_skip"><skipped/></testcase></testsuite>')
    result = runner.run_file(Path("test_sample.py"), tmp_path)
    assert result["not_run"] and result["reason"] == "all_skipped"
    assert runner.compare_baseline([result], {"failures": ["test_sample.test_skip"]})["resolved"] == []


@pytest.mark.parametrize("text_output", [False, True])
def test_timeout_preserves_partial_stdout_stderr_and_is_separate(runner, tmp_path, monkeypatch, text_output):
    seen = []
    def timeout(command, **kwargs):
        seen.append(kwargs["timeout"])
        report = Path(command[command.index("--report") + 1])
        report.with_suffix(".meta.json").write_text(json.dumps(outcome(selected=["test_sample.py::test_wait"])), encoding="utf-8")
        raise subprocess.TimeoutExpired(command, kwargs["timeout"],
            output="partial out\n" if text_output else b"partial out\n",
            stderr="partial err\n" if text_output else b"partial err\n")
    monkeypatch.setattr(runner.subprocess, "run", timeout)
    result = runner.run_file(Path("test_sample.py"), tmp_path, timeout_seconds=1.25)
    assert seen == [1.25]
    assert result["timeout"] and result["exit_code"] == 124
    assert not result["collection_failure"] and not result["not_run"]
    assert Path(result["report"]).with_suffix(".log").read_bytes() == b"partial out\npartial err\n"
    assert result["executed_cases"] == []
    assert result["selected_nodeids"] == ["test_sample.py::test_wait"]


def test_collection_metadata_is_saved_before_session_finishes(runner, tmp_path):
    report = tmp_path / "collection.meta.json"
    plugin = runner.CollectionMetadata(report, target="test_sample.py", scope="main", collect_only=False)
    plugin.pytest_deselected([SimpleNamespace(nodeid="test_sample.py::test_browser")])
    plugin.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid="test_sample.py::test_wait")]))
    metadata = json.loads(report.read_text(encoding="utf-8"))
    assert metadata["selected_nodeids"] == ["test_sample.py::test_wait"]
    assert metadata["deselected_nodeids"] == ["test_sample.py::test_browser"]
    assert "exit_code" not in metadata


def test_split_cases_do_not_overwrite_each_others_evidence(runner, tmp_path, monkeypatch):
    fake_process(monkeypatch, runner, outcome(selected=["tests/test_sample.py::test_ok"]),
        '<testsuite><testcase classname="tests.test_sample" name="test_ok"/></testsuite>')
    first = runner.run_file("test_sample.py::test_first", tmp_path)
    second = runner.run_file("test_sample.py::test_second", tmp_path)
    assert first["report"] != second["report"]
    assert all(Path(row["report"]).is_file() and Path(row["metadata"]).is_file() for row in (first, second))


def test_real_collection_records_selected_and_deselected_without_running(runner, tmp_path, monkeypatch):
    # リポジトリ外の合成試験だけを収集し、共有Tempの走査を防ぐ。
    monkeypatch.setenv("PYTEST_ADDOPTS", f'--rootdir="{tmp_path.as_posix()}" --confcutdir="{tmp_path.as_posix()}"')
    source = tmp_path / "test_synthetic_collection.py"
    source.write_text('import pytest\n'
        'def test_selected():\n    raise AssertionError("collect only must not execute")\n'
        '@pytest.mark.browser\ndef test_browser():\n    raise AssertionError("browser must not execute")\n'
        '@pytest.mark.real_model\ndef test_model():\n    raise AssertionError("model must not execute")\n', encoding="utf-8")
    result = runner.run_file(source, tmp_path, collect_only=True)
    if result["status"] != "collected":
        pytest.fail(json.dumps(result, ensure_ascii=False, indent=2))
    assert len(result["selected_nodeids"]) == 1
    assert result["selected_nodeids"][0].endswith("::test_selected")
    assert len(result["deselected_nodeids"]) == 2
    assert not result["executed_cases"]
    assert json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))["scope"] == "main"


def test_real_module_skip_is_not_run_with_its_reason(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTEST_ADDOPTS", f'--rootdir="{tmp_path.as_posix()}" --confcutdir="{tmp_path.as_posix()}"')
    source = tmp_path / "test_synthetic_skip.py"
    source.write_text('import unittest\nraise unittest.SkipTest("not-run: explicit public source required")\n', encoding="utf-8")
    result = runner.run_file(source, tmp_path)
    if not result["not_run"]:
        pytest.fail(json.dumps(result, ensure_ascii=False, indent=2))
    assert result["reason"] == "module_skip"
    assert "explicit public source required" in result["collection_skips"][0]["reason"]
    assert not result["collection_failure"] and not result["executed_cases"]


@pytest.mark.parametrize("mutation", [None, "source", "runtime"])
def test_main_splits_collected_cases_and_keeps_mutation_detection(runner, tmp_path, monkeypatch, mutation):
    import runtime_isolation
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_sample.py").touch()
    folder = tmp_path / "output/validation/evidence"
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **k: "synthetic-head\n")
    snapshots = iter([{}, {"runtime/private.db": "changed"} if mutation == "runtime" else {}])
    hashes = iter([{}, {"src/changed.py": "changed"} if mutation == "source" else {}])
    monkeypatch.setattr(runtime_isolation, "metadata_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(runner, "source_hashes", lambda: next(hashes))
    visits = []
    def execute(path, folder, **kwargs):
        visits.append((str(path), kwargs))
        row = dict(module="test_sample", target=str(path), tests=0, skipped=0, failures=[], executed_cases=[],
                   selected_nodeids=[], collection_failure=False, not_run=False, timeout=False, status="passed")
        if kwargs.get("collect_only"):
            row.update(status="collected", selected_nodeids=["tests/test_sample.py::test_first", "tests/test_sample.py::test_second"])
        else:
            row.update(tests=1, executed_cases=[runner.normalize_id(str(path).split("tests/")[-1])])
        return row
    monkeypatch.setattr(runner, "run_file", execute)
    monkeypatch.setattr(sys, "argv", ["run_tests.py", "--scope", "main", "--jobs", "2", "--timeout-seconds", "2.5",
        "--split-module", "test_sample", "--output", str(folder), "test_sample"])
    assert runner.main() == int(mutation is not None)
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["tests"] == 2 and summary["split_modules"] == ["test_sample"]
    assert len(summary["split_collections"]) == 1
    assert len(visits) == 3 and all(options["timeout_seconds"] == 2.5 for _, options in visits)
    assert sum("::test_" in target for target, _ in visits) == 2
    assert bool(summary["source_changes"]) == (mutation == "source")
    assert bool(summary["runtime_changes"]) == (mutation == "runtime")
