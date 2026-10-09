"""Lossless Core metadata delivery, using synthetic records and real seams."""
import copy
import itertools
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, canonical, fingerprint
from gurumoji.analysis_orchestration import AnalysisOrchestrationService
from gurumoji.services import analysis_orchestration_adapters as adapters
import test_analysis_orchestration as support
import test_orchestration_core_context_delivery as core_support


class CoreMetadataProjectionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.resolve, self.runner = adapters.make_orchestration_adapters(
            call_ai_json=lambda *args: self.calls.append(args) or support.core(),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        self.context = {"task": {"role": "core", "task_id": "consumer", "dependencies": [],
            "intent": {"kind": "analysis", "question": "Different question"}, "title": "Different title"},
            "question": "Synthetic question", "results": [
                {"result_id": f"result-{i}", "task_id": f"task-{i}", "attempt_id": f"attempt-{i}",
                 "role": "interpretation", "raw_hash": fingerprint({"summary": f"Body {i}"}),
                 "content": {"summary": f"Body {i}"}, "received_at": f"synthetic-time-{i}",
                 "run_id": "synthetic-run", "dataset_version": "synthetic-input", "annotation_version": 0,
                 "validation_status": "valid", "content_status": "unreviewed", "stale": False, "error": ""}
                for i in range(8)], "raw_evidence": [], "labels": {}}
        self.context["_result_metadata_hash"] = fingerprint(self.context["results"])

    def wire(self, role="core", context=None):
        self.runner(role, context or self.context, self.resolve({}), lambda: None, lambda _: None)
        return json.loads(self.calls[-1][4])

    def test_repeated_metadata_has_explicit_lossless_delivery(self):
        wire = self.wire()
        self.assertIn("result_metadata", wire)
        self.assertNotIn("_result_metadata_hash", wire)
        self.assertEqual([row["content"] for row in wire["results"]],
                         [row["content"] for row in self.context["results"]])
        self.assertIn("references", self.calls[-1][3])
        self.assertEqual(self.context["results"][0]["run_id"], "synthetic-run")

    def test_inverse_preserves_all_fields_types_and_unknown_nested_metadata(self):
        self.context["results"][0]["unknown_metadata"] = {"nested": [None, False, 0, "", {"missing": "unprocessed"}]}
        self.context["results"][1]["metadata_ref"] = {"ordinary_unknown_field": True}
        for row in self.context["results"]:
            row["annotation_version"] = None
        self.context["_result_metadata_hash"] = fingerprint(self.context["results"])
        original = copy.deepcopy(self.context)
        for role in ("core", "critic"):
            with self.subTest(role=role):
                wire = self.wire(role)
                restored = adapters._restore_core_result_metadata(wire, expected_hash=original["_result_metadata_hash"])
                self.assertEqual(canonical(restored["results"]), canonical(original["results"]))
                self.assertEqual(restored["raw_evidence"], original["raw_evidence"])
                self.assertEqual(restored["labels"], original["labels"])
                self.assertEqual(restored["task"]["title"], "Different title")
                self.assertEqual(restored["task"]["intent"]["question"], "Different question")
                bound = {**wire, "_result_metadata_hash": original["_result_metadata_hash"]}
                self.assertEqual(adapters._project_core_result_metadata(bound), wire)
        self.assertEqual(self.context, original)

    def test_missing_is_not_null_and_distinct_groups_are_not_coerced(self):
        rows = self.context["results"]
        for i in range(8, 9):
            rows.append({**copy.deepcopy(rows[0]), "result_id": f"result-{i}", "task_id": f"task-{i}"})
        for row in rows[2:4]: row["annotation_version"] = None
        for row in rows[4:6]: row["annotation_version"] = False
        for row in rows[6:8]: row["annotation_version"] = 0
        del rows[8]["annotation_version"]
        self.context["_result_metadata_hash"] = fingerprint(rows)
        wire = self.wire()
        restored = adapters._restore_core_result_metadata(wire, expected_hash=self.context["_result_metadata_hash"])
        self.assertEqual(canonical(restored["results"]), canonical(rows))
        self.assertNotIn("annotation_version", wire["results"][8])
        self.assertNotIn(8, [ref[0] for ref in wire["result_metadata"]["references"]])
        values = [row[2] for row in wire["result_metadata"]["rows"]]
        self.assertEqual({type(value) for value in values}, {int, bool, type(None)})

    def test_adopted_references_unadopted_and_explicit_dependencies_stay_inline(self):
        adopted = {"result_id": "adopted", "raw_hash": "sha256:original", "body_not_delivered": True}
        unadopted = {**copy.deepcopy(self.context["results"][0]), "result_id": "unadopted", "role": "core"}
        self.context["results"].extend([adopted, unadopted])
        self.context["task"]["dependencies"] = ["task-1"]
        self.context["_result_metadata_hash"] = fingerprint(self.context["results"])
        wire = self.wire()
        self.assertEqual(wire["results"][1], self.context["results"][1])
        self.assertEqual(wire["results"][-2:], [adopted, unadopted])
        self.assertEqual([ref[0] for ref in wire["result_metadata"]["references"]], [0, 2, 3, 4, 5, 6, 7])

    def test_malformed_projection_and_self_rehashed_mutations_fail_closed(self):
        wire = self.wire(); expected = self.context["_result_metadata_hash"]
        mutations = {
            "column name": lambda w: w["result_metadata"]["columns"].__setitem__(0, "other"),
            "column order": lambda w: w["result_metadata"]["columns"].reverse(),
            "missing column": lambda w: w["result_metadata"]["columns"].pop(),
            "row length": lambda w: w["result_metadata"]["rows"][0].pop(),
            "duplicate row": lambda w: w["result_metadata"]["rows"].append(copy.deepcopy(w["result_metadata"]["rows"][0])),
            "unknown reference": lambda w: w["result_metadata"]["references"][0].__setitem__(1, 99),
            "boolean reference": lambda w: w["result_metadata"]["references"][0].__setitem__(0, False),
            "duplicate reference": lambda w: w["result_metadata"]["references"].append([0, 0]),
            "missing reference": lambda w: w["result_metadata"]["references"].pop(),
            "reference order": lambda w: w["result_metadata"]["references"].reverse(),
            "missing result": lambda w: w["results"].pop(),
            "duplicate result": lambda w: w["results"].__setitem__(1, copy.deepcopy(w["results"][0])),
            "result order": lambda w: w["results"].reverse(),
            "metadata collision": lambda w: w["results"][0].update(run_id="foreign"),
            "changed shared run": lambda w: w["result_metadata"]["rows"][0].__setitem__(0, "foreign"),
            "changed body": lambda w: w["results"][0]["content"].update(summary="Changed body"),
            "changed task": lambda w: w["results"][0].update(task_id="foreign"),
            "changed attempt": lambda w: w["results"][0].update(attempt_id="foreign"),
            "changed role": lambda w: w["results"][0].update(role="core"),
            "null table": lambda w: w.update(result_metadata=None),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(wire); mutate(bad)
                with self.assertRaises(AnalysisContractError) as error:
                    adapters._restore_core_result_metadata(bad, expected_hash=expected)
                self.assertEqual(error.exception.code, "result_metadata_delivery_mismatch")
        bad = copy.deepcopy(wire)
        tampered_original = copy.deepcopy(self.context["results"])
        tampered_original[0]["content"]["summary"] = "Changed and rehashed"
        bad["results"][0]["content"]["summary"] = "Changed and rehashed"
        bad["result_metadata"]["source_hash"] = fingerprint(tampered_original)
        with self.assertRaises(AnalysisContractError):
            adapters._restore_core_result_metadata(bad, expected_hash=expected)
        with self.assertRaises(AnalysisContractError):
            self.wire(context=bad)  # No independent Handler binding in the wire.

    def test_non_target_delivery_and_unique_metadata_are_unchanged(self):
        for role, kind in (("interpretation", "analysis"), ("verification", "analysis"), ("critic", "clarification")):
            context = copy.deepcopy(self.context); context.pop("_result_metadata_hash")
            context["task"]["intent"]["kind"] = kind
            with self.subTest(role=role, kind=kind):
                self.assertEqual(self.wire(role, context), context)
        for i, row in enumerate(self.context["results"]): row["run_id"] = f"run-{i}"
        self.context["_result_metadata_hash"] = fingerprint(self.context["results"])
        wire = self.wire()
        self.assertNotIn("result_metadata", wire)
        self.assertEqual(wire["results"], self.context["results"])

    def test_table_row_order_and_unused_rows_are_rejected(self):
        for row in self.context["results"][4:]: row["annotation_version"] = 1
        expected = self.context["_result_metadata_hash"] = fingerprint(self.context["results"])
        wire = self.wire()
        self.assertEqual(len(wire["result_metadata"]["rows"]), 2)
        for compensate in (False, True):
            with self.subTest(compensate=compensate):
                bad = copy.deepcopy(wire)
                bad["result_metadata"]["rows"].reverse()
                if compensate:
                    for reference in bad["result_metadata"]["references"]: reference[1] = 1 - reference[1]
                with self.assertRaises(AnalysisContractError):
                    adapters._restore_core_result_metadata(bad, expected_hash=expected)
        bad = copy.deepcopy(wire)
        bad["result_metadata"]["rows"].append(["unused", "unknown", None, "unknown", "unprocessed", True, "missing"])
        with self.assertRaises(AnalysisContractError):
            adapters._restore_core_result_metadata(bad, expected_hash=expected)

    def test_large_legitimate_body_is_not_shortened_and_transport_preflight_still_raises(self):
        from gurumoji import ai_http_worker
        from gurumoji.services.ai import client
        from gurumoji.services.ai.request_budget import BudgetHold
        from test_ai_request_budget import CONDITIONS, count_proof
        from test_ai_request_budget_extended_m import make_extended_budget
        self.context["results"][0]["content"]["summary"] = "Synthetic legitimate large body " * 4000
        self.context["_result_metadata_hash"] = fingerprint(self.context["results"])
        wire = self.wire()
        self.assertEqual(wire["results"][0]["content"], self.context["results"][0]["content"])
        args = self.calls[-1]
        url, headers, payload = client.lmstudio_request("http://127.0.0.1:9/v1", "", CONDITIONS["model"],
            args[3], args[4], args[5], args[6], {})
        seen = []
        def counter(actual):
            seen.append(copy.deepcopy(actual))
            # Synthetic limit evidence, not a tokenizer measurement or capacity claim.
            return count_proof(actual, input_tokens=24577)
        budget = make_extended_budget(token_counter=counter)
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), \
             patch.object(client.subprocess, "run", side_effect=AssertionError("No worker dispatch")) as dispatch:
            with self.assertRaises(BudgetHold):
                client.post_json(url, headers, payload, worker_file=Path(ai_http_worker.__file__),
                    run_subprocess=dispatch, request_budget=budget, task_id="task", attempt_id="oversized",
                    timeout=240, retry_delays=())
            dispatch.assert_not_called()
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["max_tokens"], 4096)
        delivered = json.loads(seen[0]["messages"][1]["content"])
        self.assertEqual(delivered["results"][0]["content"], self.context["results"][0]["content"])
        self.assertEqual(budget.ledger()["entry_count"], 0)
        self.assertEqual(budget.ledger()["actual_wire_calls"], 0)


class CoreMetadataSavedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.history = core_support.CoreHistoryDeliveryTests(methodName="runTest")
        self.history.setUp(); self.addCleanup(self.history.doCleanups)
        self.h = self.history.h
        self.calls = []
        self.resolve, self.runner = adapters.make_orchestration_adapters(
            call_ai_json=lambda *args: self.calls.append(args) or support.core(),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))

    def wire(self, task):
        context = self.h.context(task)
        self.runner(task["role"], context, self.resolve({}), lambda: None, lambda _: None)
        wire = json.loads(self.calls[-1][4])
        self.assertEqual(adapters._restore_core_result_metadata(wire, expected_hash=fingerprint(context["results"]))["results"],
                         context["results"])
        return context, wire

    def test_twenty_window_dependency_and_unadopted_core_body_stay_complete(self):
        adopted = self.history.produce_core()
        unadopted = self.history.produce_core(adopt=False, summary="Unadopted Core body remains explicit")
        for i in range(22): self.h.produce(f"Independent saved result {i}")
        task = self.h.register("core", dependencies=[adopted["task_id"], unadopted["task_id"]])
        saved, before = self.h.saved(), self.h.path.read_bytes()
        original, wire = self.wire(task)
        self.assertIn("result_metadata", wire)
        self.assertEqual(len(wire["results"]), 22)
        self.assertEqual(wire["results"][:2], original["results"][:2])
        for result in wire["results"][:2]:
            self.assertIn("content", result)
            self.assertNotIn("body_not_delivered", result)
        self.assertEqual(self.h.saved(), saved)
        self.assertEqual(self.h.path.read_bytes(), before)

    def test_missing_decision_is_body_retention_and_cancelled_source_is_rejected(self):
        prior = self.history.produce_core(adopt=False)
        for i in range(8): self.h.produce(f"Independent saved result {i}")
        consumer = self.h.register("core")
        original, wire = self.wire(consumer)
        self.assertEqual(wire["results"][0], original["results"][0])
        self.assertIn("content", wire["results"][0])
        self.assertNotIn("body_not_delivered", wire["results"][0])
        calls = len(self.calls)
        self.h.mutate_task(prior, status="cancelled")
        with self.assertRaises(AnalysisContractError) as caught:
            self.wire(consumer)
        self.assertEqual(caught.exception.code, "result_integrity_mismatch")
        self.assertEqual(len(self.calls), calls)

    def test_changed_delivery_hash_stops_before_transport_and_other_roles_get_no_binding(self):
        for i in range(8): self.h.produce(f"Independent saved result {i}")
        context = self.h.context(self.h.register("core"))
        original_results = copy.deepcopy(context["results"])
        context["results"].reverse()
        with self.assertRaises(AnalysisContractError) as caught:
            self.runner("core", context, self.resolve({}), lambda: None, lambda _: None)
        self.assertEqual(caught.exception.code, "result_metadata_delivery_mismatch")
        self.assertEqual(self.calls, [])
        self.assertEqual(list(reversed(context["results"])), original_results)
        for role, extra in (("interpretation", {}), ("verification", {}),
                            ("statistics", {"method_id": "participation"}),
                            ("critic", {"kind": "clarification", "result_id": self.h.saved()["raw_results"][0]["result_id"]})):
            with self.subTest(role=role):
                self.assertNotIn("_result_metadata_hash", self.h.context(self.h.register(role, **extra)))


class CoreRoleAuthorityTests(unittest.TestCase):
    """Actual saved adoption, with mutations confined to temporary SQL rows."""
    def setUp(self):
        self.history = core_support.CoreHistoryDeliveryTests(methodName="runTest")
        self.history.setUp(); self.addCleanup(self.history.doCleanups)
        self.h = self.history.h
        self.prior = self.history.produce_core()
        self.consumers = [self.h.register(role) for role in ("core", "critic")]
        for consumer in self.consumers:
            self.history.assert_reference(self.h.context(consumer)["results"][0], self.prior)
        with self.h.service._db() as db:
            self.originals = {table: dict(db.execute(f"SELECT rowid AS saved_rowid,* FROM {table} WHERE {key}=?",
                (self.prior["task_id"] if key == "task_id" else self.prior["result_id"],)).fetchone())
                for table, key in (("orchestration_results", "result_id"), ("orchestration_tasks", "task_id"),
                                   ("orchestration_decisions", "result_id"))}
        decision = self.originals["orchestration_decisions"]
        self.assertEqual(json.loads(decision["payload_json"])["role"], "core")
        self.assertEqual(decision["result_id"], self.prior["result_id"])

    def restore(self):
        with self.h.service._db() as db:
            for table, saved in self.originals.items():
                fields = [key for key in saved if key != "saved_rowid"]
                db.execute(f"UPDATE {table} SET " + ",".join(f"{key}=?" for key in fields) + " WHERE rowid=?",
                           [saved[key] for key in fields] + [saved["saved_rowid"]])

    def mutate(self, table, *, physical=None, changes=None, missing=()):
        column = "payload_json" if table == "orchestration_decisions" else "state_json"
        rowid = self.originals[table]["saved_rowid"]
        with self.h.service._db() as db:
            row = dict(db.execute(f"SELECT * FROM {table} WHERE rowid=?", (rowid,)).fetchone())
            updates = dict(physical or {})
            if changes is not None or missing:
                state = json.loads(row[column]); state.update(changes or {})
                for field in missing: state.pop(field, None)
                updates[column] = canonical(state).decode()
            db.execute(f"UPDATE {table} SET " + ",".join(f"{key}=?" for key in updates) + " WHERE rowid=?",
                       [*updates.values(), rowid])

    def reject_readonly(self):
        before, calls = self.h.path.read_bytes(), len(self.h.calls)
        statements = []
        for consumer in self.consumers:
            with self.subTest(consumer=consumer["role"]), self.h.service._db() as db:
                run = self.h.service._read_run(db, self.h.run["run_id"])
                db.set_trace_callback(statements.append)
                with self.assertRaises(AnalysisContractError) as caught:
                    self.h.service._context(db, run, consumer)
                self.assertEqual(caught.exception.code, "result_integrity_mismatch")
        self.assertEqual(self.h.path.read_bytes(), before)
        self.assertEqual(len(self.h.calls), calls)
        self.assertFalse([sql for sql in statements if sql.lstrip().split()[0].upper() in
                          {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"}])

    def test_saved_result_role_alone_cannot_demote_adopted_core(self):
        for role in ("critic", "interpretation", "statistics", "verification", "", None):
            with self.subTest(result_role=role):
                self.restore(); self.mutate("orchestration_results", changes={"role": role})
                with self.h.service._db() as db:
                    result = dict(db.execute("SELECT * FROM orchestration_results WHERE result_id=?", (self.prior["result_id"],)).fetchone())
                    for field in ("result_id", "run_id", "task_id", "raw_json"):
                        self.assertEqual(result[field], self.originals["orchestration_results"][field])
                    self.assertEqual(json.loads(result["state_json"])["raw_hash"],
                                     json.loads(self.originals["orchestration_results"]["state_json"])["raw_hash"])
                    self.assertEqual(dict(db.execute("SELECT rowid AS saved_rowid,* FROM orchestration_decisions WHERE result_id=?",
                        (self.prior["result_id"],)).fetchone()), self.originals["orchestration_decisions"])
                self.reject_readonly()
        self.restore(); self.mutate("orchestration_results", missing=("role",))
        self.reject_readonly()

    def test_saved_source_role_alone_cannot_demote_adopted_core(self):
        for role in ("critic", "interpretation", "statistics", "verification", "", None):
            with self.subTest(source_role=role):
                self.restore(); self.mutate("orchestration_tasks", changes={"role": role})
                self.reject_readonly()

    def test_both_saved_roles_cannot_override_actual_committed_decision(self):
        for role in ("critic", "interpretation", "statistics", "verification", "", None):
            with self.subTest(both_roles=role):
                self.restore()
                for table in ("orchestration_results", "orchestration_tasks"):
                    self.mutate(table, changes={"role": role})
                with self.h.service._db() as db:
                    self.assertEqual(dict(db.execute("SELECT rowid AS saved_rowid,* FROM orchestration_decisions WHERE result_id=?",
                        (self.prior["result_id"],)).fetchone()), self.originals["orchestration_decisions"])
                self.reject_readonly()

    def test_result_metadata_identity_cannot_redirect_role_authority(self):
        other = self.h.produce("Unrelated legitimate expert result")
        for field, value in (("result_id", other["result_id"]), ("task_id", other["task_id"]),
                             ("run_id", "foreign-run"), ("result_id", None), ("task_id", None)):
            with self.subTest(field=field, value=value):
                self.restore()
                self.mutate("orchestration_results", changes={"role": "critic", field: value})
                self.mutate("orchestration_tasks", changes={"role": "critic"})
                self.reject_readonly()

    def test_physical_source_and_result_identities_are_not_repaired(self):
        for table, physical in (("orchestration_results", {"task_id": "foreign-task"}),
                                ("orchestration_results", {"result_id": "foreign-result"}),
                                ("orchestration_tasks", {"task_id": "foreign-task"}),
                                ("orchestration_tasks", {"run_id": "foreign-run"})):
            with self.subTest(table=table, physical=physical):
                self.restore()
                self.mutate("orchestration_results", changes={"role": "critic"})
                self.mutate("orchestration_tasks", changes={"role": "critic"})
                self.mutate(table, physical=physical)
                self.reject_readonly()

    def test_original_source_and_result_validation_still_gates_core_history(self):
        mutations = {
            "orchestration_results": ({"dataset_version": "old"}, {"attempt_id": None}, {"attempt_id": "other"},
                {"raw_hash": "sha256:other"}, {"stale": True}, {"validation_status": "quarantined"}),
            "orchestration_tasks": ({"task_id": "other"}, {"result_id": "other"}, {"run_id": "foreign"},
                {"dataset_version": "old"}, {"attempt_id": None}, {"attempt_id": "other"}, {"stale": True},
                {"status": "cancelled"}, {"status": "queued"}, {"validation_status": "quarantined"})}
        for table, cases in mutations.items():
            for change in cases:
                with self.subTest(table=table, change=change):
                    self.restore(); self.mutate(table, changes=change); self.reject_readonly()

    def test_committed_decision_identity_role_and_content_remain_authoritative(self):
        for change in ({"role": "critic"}, {"task_id": "other"}, {"result_id": "other"},
                       {"summary": "Changed adopted summary"}, {"alternatives": ["Changed adopted content"]}):
            with self.subTest(change=change):
                self.restore(); self.mutate("orchestration_decisions", changes=change); self.reject_readonly()
        self.restore(); self.mutate("orchestration_decisions", missing=("result_id",))
        self.reject_readonly()
        self.restore(); self.mutate("orchestration_decisions", physical={"run_id": "foreign-run"})
        self.reject_readonly()
        self.restore()
        raw = json.loads(self.originals["orchestration_results"]["raw_json"])
        raw["summary"] = "Changed raw with matching self hash"
        self.mutate("orchestration_results", physical={"raw_json": canonical(raw).decode()}, changes={"raw_hash": fingerprint(raw)})
        self.reject_readonly()

    def test_real_execute_rejects_wrong_role_before_dispatch(self):
        self.mutate("orchestration_results", changes={"role": "critic"})
        self.mutate("orchestration_tasks", changes={"role": "critic"})
        calls = len(self.h.calls)
        before = self.h.saved()["raw_results"]
        self.h.service._execute(self.h.run["run_id"], self.consumers[0]["task_id"])
        self.assertEqual(len(self.h.calls), calls)
        saved = self.h.saved()
        self.assertEqual(saved["raw_results"], before)
        task = next(row for row in saved["run"]["tasks"] if row["task_id"] == self.consumers[0]["task_id"])
        self.assertEqual((task["status"], task["error"]), ("failed", "result_integrity_mismatch"))
        self.assertEqual(saved["run"]["calls_started"], 1)

    def test_valid_mixed_results_and_unadopted_core_keep_original_bodies(self):
        unadopted = self.history.produce_core(adopt=False)
        expert = self.h.produce("Legitimate expert result")
        critic = self.h.register("critic")
        self.h.response = support.critic({})
        self.h.service._execute(self.h.run["run_id"], critic["task_id"])
        self.h.service.method_runner = lambda name, snapshot: {"method": {"method_id": name},
            "datasets": {"summary": {"fields": ["n"], "rows": [{"n": 7}]}}}
        statistic = self.h.register("statistics", method_id="participation")
        self.h.service._execute(self.h.run["run_id"], statistic["task_id"])
        expected = self.h.saved()
        with self.h.service._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orchestration_decisions").fetchone()[0], 1)
        for role in ("core", "critic"):
            consumer = self.h.register(role)
            before = self.h.path.read_bytes()
            delivered = self.h.context(consumer)["results"]
            self.history.assert_reference(delivered[0], self.prior)
            bodies = {row["task_id"]: row for row in delivered if "content" in row}
            for task in (unadopted, expert, critic, statistic):
                original = next(row for row in expected["raw_results"] if row["task_id"] == task["task_id"])
                self.assertEqual(original["validation_status"], "valid")
                self.assertEqual(bodies[task["task_id"]], {**{k: v for k, v in original.items() if k != "raw"}, "content": original["raw"]})
            self.assertEqual(self.h.path.read_bytes(), before)


class CoreMetadataServiceTests(unittest.TestCase):
    def run_cycle(self, project):
        import app
        import test_content_analysis as content_support
        from gurumoji.analysis_store import AnalysisStore
        from gurumoji.method_experts import ExpertCatalog
        from gurumoji.services.expert_agents import ExpertAgentRegistry
        from gurumoji.services.analysis_orchestration_publication import AnalysisOrchestrationPublicationService
        from test_expert_data_hooks import request
        fixture = content_support.ContentApiTests(methodName="runTest")
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        for guard in (patch("socket.socket.connect", side_effect=AssertionError("No network")),
                      patch.object(AnalysisStore, "_publish_generated_vaults", side_effect=AssertionError("No Vault")),
                      patch.object(AnalysisStore, "_publish_research", side_effect=AssertionError("No Vault"))):
            guard.start(); self.addCleanup(guard.stop)
        registry = ExpertAgentRegistry(ExpertCatalog(root=Path(__file__).resolve().parents[1] / "docs/program-vault",
            local_root=Path(fixture.temp.name) / "synthetic-local-knowledge"))
        snapshot = {"input_hash": "synthetic-323-v1", "source_revision": 0, "analysis_revision": 1,
            "analysis": {"segments": [{"id": f"u{i}", "text": f"Synthetic scope utterance {i}",
                "speaker": "UNKNOWN" if i == 0 else f"S{i % 3}", "valid_time": False,
                "annotation": {"codes": ["synthetic"]}, "excluded": False} for i in range(323)],
                "automatic": {"overview": {"included_segment_count": 323, "speaker_count": 4}},
                "all_results": {"preserved_missing": None, "preserved_zero": 0, "uncomputed": "unprocessed"}}}
        wires, replies, rounds, preimages = [], [], {}, []
        projector = adapters._project_core_result_metadata
        def project_delivery(context):
            original = copy.deepcopy(context)
            expected = original.pop("_result_metadata_hash", None)
            projected = projector(context) if project else original
            restored = adapters._restore_core_result_metadata(projected, expected_hash=expected) if expected else projected
            self.assertEqual(canonical(restored), canonical(original))
            preimages.append(original)
            return projected
        def transport(*args, **kwargs):
            context = json.loads(args[4]); role = args[5].removeprefix("analysis_orchestration_")
            wires.append({"role": role, "context": copy.deepcopy(context), "input_bytes": len(args[4].encode()),
                "rendered_bytes": len(canonical({"system": args[3], "input": args[4], "output_schema": args[6]}))})
            args[7](); args[8]({"reported": False})
            if role == "core":
                iteration = context["task"]["iteration"]
                ids = [row["evidence_id"] for row in core_support.decode_index(context["coverage"]["evidence_index"])]
                self.assertEqual(len(ids), 323)
                if iteration <= 9:
                    # Nine full 36-row scopes cover323 IDs, with one explicit
                    # overlap in the final scope rather than an invented324th.
                    start = min((iteration - 1) * 36, len(ids) - 36)
                    raw = support.core(summary="Synthetic integrated view", intents=[support.intent("interpretation",
                        kind="analysis", expert_id="exp-thematic-analysis", question=f"Synthetic independent scope {iteration}",
                        evidence_ids=ids[start:start + 36])])
                else:
                    responses = [{"issue_id": row["issue_id"], "disposition": "defer", "reason": "Human interpretation remains pending",
                                  "impact": "Keep the observation bounded"} for row in context["issues"]]
                    raw = support.stop(summary="Synthetic integrated view", claims=[{"claim_id": "synthetic-observation",
                        "text": "Synthetic evidence only", "kind": "observation", "evidence_ids": [ids[0]]}],
                        critique_responses=responses)
            elif role == "interpretation":
                task_id = context["task"]["task_id"]
                rounds[task_id] = rounds.get(task_id, 0) + 1
                if rounds[task_id] == 1:
                    provided = {row["evidence_id"] for row in context["raw_evidence"]}
                    remaining = [row["evidence_id"] for row in context["expert_hooks"]["evidence_index"] if row["evidence_id"] not in provided]
                    self.assertEqual(len(remaining), 24)
                    return {"expert_response": {"mode": "read", "hook_requests": [request(ids=remaining[i:i + 8]) for i in range(0, 24, 8)]}}
                packet = context["expert_request"]; profile = packet["knowledge"]
                raw = {"summary": "Synthetic independent expert draft", "claims": [], "analysis_requests": [], "label_patches": [],
                    "expert_report": {"expert_id": packet["expert_id"], "profile_hash": packet["profile_hash"],
                        "knowledge_hash": packet["knowledge_hash"], "status": "draft",
                        "outputs": {field["id"]: "Synthetic bounded draft; human interpretation remains pending" for field in profile["output_fields"]},
                        "evidence_ids": [row["evidence_id"] for row in context["raw_evidence"]],
                        "knowledge_note_ids": [profile["knowledge"][0]["note_id"]],
                        "performed_step_ids": [profile["allowed_steps"][0]["id"]], "missing_inputs": [],
                        "limitations": "Synthetic input only; human decisions unverified"}}
            elif role == "critic":
                target = context["review_target"]
                raw = support.critic(context, [{"issue_key": "synthetic-human-review", "target_id": target["target_id"],
                    "target_version": target["target_version"], "severity": "low", "reason": "Human interpretation pending",
                    "evidence_ids": [context["raw_evidence"][0]["evidence_id"]], "missing_evidence": "Human review",
                    "alternative": "Bounded alternative", "proposed_test": "Researcher review"}])
            else:
                raw = {"summary": "Synthetic blind verification", "claims": []}
            replies.append((role, copy.deepcopy(raw)))
            return {"expert_response": {"mode": "report", "result": raw}} if "expert_response" in args[6]["properties"] else raw
        _, runner = adapters.make_orchestration_adapters(call_ai_json=transport,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        service = AnalysisOrchestrationService(connect=app.database_connection, find_item=app.library_row,
            snapshot_builder=lambda _: copy.deepcopy(snapshot), source_fingerprint=lambda _: snapshot["input_hash"],
            agent_runner=runner, method_runner=lambda *_: self.fail("No statistics in this cycle"),
            expert_provider=registry.freeze, adapter_version=adapters.ADAPTER_VERSION, schedule=False)
        serial = itertools.count(1)
        with patch("gurumoji.analysis_orchestration._id", side_effect=lambda prefix: f"{prefix}_{next(serial):06d}"), \
             patch("gurumoji.analysis_orchestration._now", return_value="2026-01-01T00:00:00+00:00"), \
             patch("gurumoji.analysis_orchestration.time.time", return_value=1767225600.0), \
             patch.object(adapters, "_project_core_result_metadata", side_effect=project_delivery):
            run = service.start("content", {"request_id": "synthetic-nine-scope-31", "model": "synthetic",
                "question": "Synthetic full index inquiry", "adapter_version": adapters.ADAPTER_VERSION,
                "expert_ids": ["exp-thematic-analysis"], "expert_hooks": True,
                "expert_inputs": {"exp-thematic-analysis": {"analysis_premises": None}}, "concurrency": 1,
                "context_evidence_limit": 120, "context_index_limit": 0,
                "context_evidence_limits_by_role": {"core": 12, "critic": 12, "verification": 12, "interpretation": 120},
                "max_calls": 32, "max_tasks": 40, "time_limit_seconds": 8400, "obsidian_management": False,
                "publication_targets": []})
            service.run(run["run_id"])
        exported = service.result("content", run["run_id"])
        self.assertEqual(exported["run"]["status"], "completed", exported["run"])
        self.assertEqual(len(wires), 31)
        self.assertEqual(len(rounds), 9)
        self.assertEqual(set(rounds.values()), {2})
        self.assertEqual(len(exported["decisions"]), 11)
        self.assertTrue(all(task["status"] == "succeeded" for task in exported["run"]["tasks"]))
        self.assertEqual([(row["role"], row["raw"]) for row in exported["raw_results"]], replies)
        tasks = [task for task in exported["run"]["tasks"] if task["role"] == "interpretation"]
        self.assertTrue(all(len(task["intent"]["evidence_ids"]) == 36 for task in tasks))
        self.assertEqual(len(set().union(*(set(task["expert_evidence_ids"]) for task in tasks))), 323)
        with service._db() as db:
            rows = {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                    for table in ("orchestration_results", "orchestration_tasks", "orchestration_decisions", "orchestration_label_versions")}
        fresh_service = AnalysisOrchestrationService(connect=app.database_connection, find_item=app.library_row,
            snapshot_builder=lambda *_: self.fail("No rebuild"), source_fingerprint=lambda _: snapshot["input_hash"],
            agent_runner=lambda *_: self.fail("No fresh model"), method_runner=lambda *_: self.fail("No fresh method"), schedule=False)
        self.assertEqual(fresh_service.result("content", run["run_id"]), exported)
        store = app.analysis_archive_store()
        publisher = AnalysisOrchestrationPublicationService(connect=app.database_connection, store_factory=lambda: store,
            source_guard=lambda db, item, expected: {"id": item}, export_locked=service.result_locked)
        publication = publisher.finalize("content", run["run_id"])
        self.assertEqual(publication["save_status"], "saved", publication)
        self.assertEqual(publication["publication_status"], "not_selected")
        artifact = next(row for row in publication["result_run"]["artifacts"] if row["name"] == "result.json")
        fresh_store = AnalysisStore(store.database_file, store.connect)
        _, package = fresh_store.read_artifact(artifact["id"])
        self.assertEqual(package, store.read_artifact(artifact["id"])[1])
        self.assertEqual(json.loads(package)["orchestration"]["raw_results"], exported["raw_results"])
        with service._db() as db:
            after = {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")] for table in rows}
        self.assertEqual(after, rows)
        return {"wires": wires, "preimages": preimages, "exported": exported, "rows": rows, "package": package}

    def test_real_31_wire_cycle_is_lossless_and_store_fresh_bytes_match(self):
        before = self.run_cycle(False)
        self.doCleanups()
        after = self.run_cycle(True)
        self.assertEqual(before["rows"], after["rows"])
        self.assertEqual(before["exported"], after["exported"])
        self.assertEqual(before["package"], after["package"])
        self.assertEqual(before["preimages"], after["preimages"])
        measurements = []
        for index, (old, new) in enumerate(zip(before["wires"], after["wires"]), 1):
            self.assertEqual(old["role"], new["role"])
            if new["role"] in {"core", "critic"}:
                restored = adapters._restore_core_result_metadata(new["context"], expected_hash=fingerprint(old["context"]["results"]))
                self.assertEqual(restored, old["context"])
                self.assertEqual(len(core_support.decode_index(new["context"]["coverage"]["evidence_index"])), 323)
                self.assertLessEqual(new["rendered_bytes"], old["rendered_bytes"])
            else:
                self.assertEqual(new, old)
            measurements.append({"wire": index, "role": new["role"], "input_before": old["input_bytes"],
                "input_after": new["input_bytes"], "rendered_before": old["rendered_bytes"], "rendered_after": new["rendered_bytes"]})
        self.assertEqual(after["wires"][-1]["role"], "core")
        self.assertLess(after["wires"][-1]["rendered_bytes"], before["wires"][-1]["rendered_bytes"])
        print("SYNTHETIC_31_WIRE_BYTES=" + json.dumps(measurements, separators=(",", ":")))


if __name__ == "__main__":
    unittest.main()
