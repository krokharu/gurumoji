"""分割された未送信タスクと子孫の完了判定。"""
import copy
import unittest

from gurumoji.analysis_core import fingerprint
from gurumoji.services.orchestration_task_completion import analysis_processing_tasks_complete


class SplitCompletionTests(unittest.TestCase):
    def setUp(self):
        self.run = {"run_id": "run", "input_hash": "input", "initial_analysis_report": {"label_requirements": []}}
        self.results = []
        self.decisions = []

    def task(self, identifier, status, phase, scope, *, parent=None, error="", role="interpretation"):
        value = {"task_id": identifier, "run_id": "run", "dataset_version": "input", "attempt_id": "a-" + identifier,
                 "status": status, "validation_status": "valid" if status == "succeeded" else "pending",
                 "phase": phase, "error": error, "role": role, "method_id": "method", "parent_task_id": parent,
                 "intent": {"parent_task_id": parent, "scope": scope}}
        if status == "succeeded":
            value["result_id"] = "r-" + identifier
            self.results.append({"result_id": value["result_id"], "run_id": "run", "task_id": identifier,
                                 "attempt_id": value["attempt_id"], "validation_status": "valid"})
            self.decisions.append({"result_assessments": [{"result_id": value["result_id"]}]})
        return value

    def check(self, tasks):
        return analysis_processing_tasks_complete(self.run, tasks, self.results, self.decisions)

    def test_nested_split_requires_complete_nonoverlapping_coverage(self):
        parent = self.task("p", "blocked", "initial_analysis_split", {"owned_evidence_ids": ["1", "2", "3"]}, error="context_page_split")
        branch = self.task("b", "blocked", "initial_analysis_split", {"owned_evidence_ids": ["1", "2"]}, parent="p", error="context_page_split")
        tasks = [parent, branch, self.task("c", "succeeded", "initial_analysis", {"owned_evidence_ids": ["3"]}, parent="p"),
                 self.task("d", "succeeded", "initial_analysis", {"owned_evidence_ids": ["1"]}, parent="b"),
                 self.task("e", "succeeded", "initial_analysis", {"owned_evidence_ids": ["2"]}, parent="b")]
        self.assertTrue(self.check(tasks))
        for mutation in ("missing_child", "wrong_scope", "failed_child", "unassessed", "invalid_result", "wrong_reason"):
            with self.subTest(mutation=mutation):
                modified, results, decisions = copy.deepcopy(tasks), copy.deepcopy(self.results), copy.deepcopy(self.decisions)
                if mutation == "missing_child": modified.pop()
                if mutation == "wrong_scope": modified[-1]["intent"]["scope"]["owned_evidence_ids"] = ["1"]
                if mutation == "failed_child": modified[-1]["status"] = "failed"
                if mutation == "unassessed": decisions.pop()
                if mutation == "invalid_result": results[-1]["validation_status"] = "quarantined"
                if mutation == "wrong_reason": modified[0]["error"] = "context_budget_exceeded"
                self.assertFalse(analysis_processing_tasks_complete(self.run, modified, results, decisions))

    def test_requirement_split_uses_frozen_report_when_parent_scope_absent(self):
        self.run["initial_analysis_report"]["label_requirements"] = [{"name": "a"}, {"name": "b"}]
        ids = [fingerprint(value) for value in self.run["initial_analysis_report"]["label_requirements"]]
        parent = self.task("p", "blocked", "initial_routing_split", {}, error="context_requirement_split", role="core")
        a = self.task("a", "succeeded", "initial_routing", {"requirement_keys": ids[:1]}, parent="p", role="core")
        b = self.task("b", "succeeded", "initial_routing", {"requirement_keys": ids[1:]}, parent="p", role="core")
        self.assertTrue(self.check([parent, a, b]))
        b["intent"]["scope"]["requirement_keys"] = ids[:1]
        self.assertFalse(self.check([parent, a, b]))


if __name__ == "__main__":
    unittest.main()
