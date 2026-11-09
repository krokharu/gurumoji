"""分割された分析タスクの完了条件。"""
from collections import Counter

from ..analysis_core import fingerprint


def analysis_processing_tasks_complete(run, tasks, results, decisions):
    """未送信の分割親は、範囲を欠かさない有効な子孫が揃った場合だけ完了とする。"""
    if not tasks:
        return False
    task_ids = [task.get("task_id") for task in tasks]
    if not all(task_ids) or len(task_ids) != len(set(task_ids)):
        return False
    result_index = {result.get("result_id"): result for result in results}
    assessed = {entry.get("result_id") for decision in decisions
                for entry in decision.get("result_assessments", [])}

    def scope(task):
        value = task.get("intent", {}).get("scope")
        return value if isinstance(value, dict) else {}

    def valid(task, ancestors, split_child=False):
        task_id = task["task_id"]
        if task_id in ancestors or task.get("run_id") != run.get("run_id") or task.get("dataset_version") != run.get("input_hash"):
            return False
        if task.get("status") == "succeeded":
            if not split_child:
                return True
            result = result_index.get(task.get("result_id"))
            return bool(result and result.get("task_id") == task_id and result.get("run_id") == run.get("run_id")
                        and result.get("attempt_id") == task.get("attempt_id") and result.get("validation_status") == "valid"
                        and task.get("validation_status") == "valid" and not result.get("stale") and not task.get("stale"))
        phase = task.get("phase", "")
        reason = task.get("error")
        if task.get("status") != "blocked" or not phase.endswith("_split") or reason not in {"context_page_split", "context_requirement_split"}:
            return False
        base_phase = phase[:-6]
        if reason == "context_page_split":
            key = "owned_evidence_ids"
        else:
            key = "requirement_keys"
        expected = scope(task).get(key)
        if expected is None and reason == "context_requirement_split" and base_phase in {"initial_routing", "initial_labels"}:
            expected = [fingerprint(value) for value in run.get("initial_analysis_report", {}).get("label_requirements", [])]
        if not isinstance(expected, list) or len(expected) < 2 or any(not isinstance(x, str) or not x for x in expected):
            return False
        children = [child for child in tasks if child.get("parent_task_id") == task_id
                    and child.get("phase") in {base_phase, base_phase + "_split"}]
        if len(children) != 2:
            return False
        combined = []
        for child in children:
            values = scope(child).get(key)
            if (not isinstance(values, list) or not values or any(not isinstance(x, str) or not x for x in values)
                    or child.get("role") != task.get("role") or child.get("method_id") != task.get("method_id")
                    or child.get("intent", {}).get("parent_task_id") != task_id
                    or not valid(child, ancestors | {task_id}, True)):
                return False
            combined.extend(values)
        if Counter(combined) != Counter(expected):
            return False
        leaves = [child for child in children if child.get("status") == "succeeded"]
        return all(child.get("role") in {"core", "orchestrator"} or child.get("result_id") in assessed for child in leaves)

    return all(valid(task, set()) for task in tasks)
