"""Synthetic expert/Handler hook acceptance checks; no model, API or real Vault."""
import copy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.analysis_orchestration import validate_orchestration_payload
from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION, make_orchestration_adapters
from gurumoji.services import analysis_orchestration_adapters as adapters
from gurumoji.services.expert_data_hooks import read_data, VERSION
import test_expert_agents as expert_fixtures
import test_analysis_orchestration as fixtures


def ordered_wire_hash(value):
    """Test authority is the original input, including nested JSON key order."""
    return fingerprint(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False))


def decoded_index(packet):
    index = packet["expert_hooks"]["evidence_index"]
    if isinstance(index, list):
        return copy.deepcopy(index)
    if (not isinstance(index, dict) or set(index) != {"columns", "rows"}
            or index["columns"] != ["evidence_id"] or not isinstance(index["rows"], list)
            or any(not isinstance(row, list) or len(row) != 1 or not isinstance(row[0], str) or not row[0] for row in index["rows"])):
        raise ValueError("invalid independent index table")
    ids = [row[0] for row in index["rows"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate evidence ID")
    return [{"evidence_id": eid} for eid in ids]


def independently_decode_wire(wire, original):
    """Independent decoder: no production encoder, decoder or hash helper calls."""
    value = copy.deepcopy(wire)
    expected = ordered_wire_hash(original)
    def check(ok):
        if not ok:
            raise ValueError("independent wire proof mismatch")
    if "expert_wire_delivery" in value:
        marker = value.pop("expert_wire_delivery")
        check(isinstance(marker, dict) and set(marker) == {"format", "source_hash", "labels_table"})
        check(marker["format"] == "expert_wire_v1" and marker["source_hash"] == expected
              and type(marker["labels_table"]) is bool)
        value["expert_hooks"]["evidence_index"] = decoded_index(value)
        if marker["labels_table"]:
            table = value["labels"]
            check(isinstance(table, dict) and set(table) == {"owners", "columns", "rows", "field_orders", "row_orders"})
            owners, columns, rows = table["owners"], table["columns"], table["rows"]
            orders, references = table["field_orders"], table["row_orders"]
            check(all(isinstance(v, list) for v in (owners, columns, rows, orders, references)))
            check(all(isinstance(v, str) and v for v in owners) and len(set(owners)) == len(owners))
            check(all(isinstance(v, str) for v in columns) and len(set(columns)) == len(columns))
            check(len(owners) == len(rows) == len(references))
            check(all(isinstance(row, list) and len(row) == len(columns) for row in rows))
            check(all(isinstance(order, list) and all(type(i) is int and i in range(len(columns)) for i in order)
                      and len(order) == len(set(order)) for order in orders))
            check(len({json.dumps(order) for order in orders}) == len(orders))
            result, columns_seen, orders_seen = {}, [], []
            for position, owner in enumerate(owners):
                ref = references[position]
                check(type(ref) is int and 0 <= ref < len(orders))
                keys = orders[ref]
                check(all(rows[position][i] is None for i in range(len(columns)) if i not in keys))
                result[owner] = dict((columns[i], rows[position][i]) for i in keys)
                for i in keys:
                    if i not in columns_seen: columns_seen.append(i)
                if ref not in orders_seen: orders_seen.append(ref)
            check(columns_seen == list(range(len(columns))) and orders_seen == list(range(len(orders))))
            value["labels"] = result
    check(ordered_wire_hash(value) == expected)
    return value


def synthetic_wire_packet(count=323):
    labels = {}
    for i in range(count):
        fields = {"codes": [], "code": None, "theme": "", "sentiment": False, "dialogue_act": {},
                  "importance": 0, "review": {"z": [None, False, 0, "", {"last": 1, "first": 2}], "a": {}},
                  "category": ["synthetic", str(i % 3)]}
        if i % 7 == 0: fields.pop("theme")
        if i % 3 == 0: fields = dict(reversed(list(fields.items())))
        labels[f"u{i:03d}"] = fields
    return {"task": {"task_id": "synthetic-task", "intent": {"kind": "analysis", "evidence_ids": []},
                     "dependencies": ["actual-code-task"], "annotation_version": 0, "codebook_version": 1},
        "data_version": "synthetic-source-v1", "profile_hash": "synthetic-profile", "knowledge_hash": "synthetic-knowledge",
        "expert_hooks": {"version": VERSION, "evidence_index": [{"evidence_id": f"ev_synthetic_{i:03d}"} for i in range(count)],
                         "scope": "unchanged permission", "calculation_tables": [], "max_rounds": 2},
        "labels": labels, "raw_evidence": [{"evidence_id": f"ev_synthetic_{i:03d}", "utterance_id": f"u{i:03d}",
            "text": f"Public synthetic utterance {i:03d}", "speaker": "A", "text_offset": 0,
            "total_text_characters": 30, "omitted_text_characters": 0} for i in range(min(count, 12))],
        "coverage": {"scope": "all_included", "available_count": count, "provided_count": min(count, 12)}}


def request(name="read_evidence", ids=(), result_id="", table_id="", offset=0, limit=8):
    return dict(name=name, evidence_ids=list(ids), result_id=result_id, table_id=table_id, offset=offset, limit=limit)


def wire_response(raw):
    if raw.get("hook_requests"):
        response = {"mode": "read", "hook_requests": raw["hook_requests"]}
        if raw.get("expert_report") is not None:
            response["result"] = raw["expert_report"]
        return {"expert_response": response}
    return {"expert_response": {"mode": "report", "result": {k: v for k, v in raw.items() if k != "hook_requests"}}}


class ExpertDataHookTests(unittest.TestCase):
    def setUp(self):
        self.fixture = expert_fixtures.ExpertAgentTests("test_independent_verification_stays_blind")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.item.update(revision_count=1, analysis_revision=1)
        self.fixture.snap["analysis"]["segments"] = [
            {"id": f"u{i}", "text": "Synthetic utterance " + str(i), "speaker": "A"} for i in range(30)]
        self.service = self.fixture.service
        self.service.adapter_version = ADAPTER_VERSION
        self.calls = []
        self.respond = lambda _: {**copy.deepcopy(self.report), "hook_requests": []}
        def call(*args):
            self.calls.append((json.loads(args[4]), copy.deepcopy(args[6])))
            args[7]()
            args[8]({"input_tokens": 10, "output_tokens": 3, "total_tokens": 13, "reported": True})
            raw = self.respond(len(self.calls))
            return wire_response(raw) if "expert_response" in args[6]["properties"] else raw
        _, self.service.agent_runner = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))

    def dispatch(self, **config):
        self.run = self.fixture.start(adapter_version=ADAPTER_VERSION, **config)
        with self.service._db() as db:
            run = self.service._read_run(db, self.run["run_id"])
            initial = self.service._initial(db, run["initial_id"])
            self.ids = [r["evidence_id"] for r in initial["evidence"]]
            intent = fixtures.intent("interpretation", expert_id=expert_fixtures.EXPERT,
                                     evidence_ids=self.selected(self.ids) if hasattr(self, "selected") else [])
            self.task = self.service._register(db, run, intent, phase="specialists")
            context = self.service._context(db, run, self.task)
            self.report = self.fixture.report(context)
        self.service._execute(self.run["run_id"], self.task["task_id"])
        state = self.service.status("synthetic", self.run["run_id"])
        return state, next(t for t in state["tasks"] if t["task_id"] == self.task["task_id"])

    def hook_response(self, requests):
        return {"summary": "Read required evidence", "claims": [], "analysis_requests": [],
                "label_patches": [], "expert_report": None, "hook_requests": requests}

    def test_missing_evidence_is_read_on_demand_and_adopted_with_receipts(self):
        def response(n):
            if n == 1:
                return self.hook_response([request(ids=[self.ids[-1]])])
            report = copy.deepcopy(self.report)
            report["expert_report"]["evidence_ids"] = [self.ids[-1]]
            return {**report, "hook_requests": []}
        self.respond = response
        source_before = fingerprint(self.fixture.snap)
        state, task = self.dispatch()
        self.assertEqual(task["status"], "succeeded", task["error"])
        self.assertEqual(len(self.calls[0][0]["raw_evidence"]), 12)
        self.assertEqual(self.calls[0][0]["coverage"]["omitted_count"], 18)
        index = decoded_index(self.calls[0][0])
        self.assertEqual(len(index), 30)
        self.assertEqual(set(index[0]), {"evidence_id"})
        self.assertEqual(index, [{"evidence_id": eid} for eid in self.ids])
        self.assertNotIn("evidence_index", self.calls[0][0]["coverage"])
        self.assertNotIn("evidence_index", self.calls[0][0]["expert_request"]["coverage"])
        self.assertEqual(len(self.calls[1][0]["raw_evidence"]), 13)
        self.assertEqual(self.calls[1][0]["raw_evidence"][0]["text"], "Synthetic utterance 29")
        self.assertNotIn("evidence", self.calls[1][0]["expert_hook_results"][0])
        self.assertEqual(task["model_calls"], 2)
        self.assertEqual(state["usage"]["calls"], 2)
        self.assertEqual(state["usage"]["measured_calls"], 2)
        self.assertEqual(state["usage"]["total_tokens"], 26)
        self.assertEqual(len(task["expert_hook_reads"]), 1)
        self.assertEqual(len(task["expert_hook_responses"]), 1)
        self.assertIn(self.ids[-1], task["expert_evidence_ids"])
        self.assertEqual(fingerprint(self.fixture.snap), source_before)
        self.assertFalse(any(t["role"] == "statistics" for t in state["tasks"]))
        with self.service._db() as db:
            stored = db.execute("SELECT raw_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()[0]
        self.assertNotIn("hook_requests", json.loads(stored))
        self.service._validate_received(state["run_id"], task["task_id"])
        self.assertEqual(len(self.calls), 2, "durable validation must not replay hooks or model calls")

    def test_no_hook_needed_costs_one_call(self):
        _, task = self.dispatch()
        self.assertEqual(task["status"], "succeeded", task["error"])
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("expert_hook_reads", task)

    def test_context_limits_do_not_authorize_evidence_not_sent_to_model(self):
        def response(n):
            if n == 1:
                return self.hook_response([request(ids=[self.ids[-2]]), request(ids=[self.ids[-1]])])
            report = copy.deepcopy(self.report)
            report["expert_report"]["evidence_ids"] = [self.ids[-1]]
            return {**report, "hook_requests": []}
        self.respond = response
        _, task = self.dispatch(context_evidence_limit=1, context_text_limit=30)
        self.assertEqual(len(self.calls[1][0]["raw_evidence"]), 1)
        self.assertIn(self.ids[-2], task["expert_evidence_ids"])
        self.assertNotIn(self.ids[-1], task["expert_evidence_ids"])
        self.assertEqual(task["status"], "quarantined")
        self.assertEqual(len(task["expert_hook_reads"]), 2)
        self.assertEqual(self.calls[1][0]["expert_request"]["evidence"][0]["evidence_id"], self.ids[-2])

    def test_core_selected_scope_cannot_be_expanded_by_expert(self):
        self.selected = lambda ids: ids[:1]
        self.respond = lambda _: self.hook_response([request(ids=[self.ids[-1]])])
        state, task = self.dispatch()
        self.assertNotEqual(task["status"], "succeeded")
        self.assertEqual(state["status"], "recovery_required")
        self.assertNotIn("expert_hook_reads", task)
        self.assertEqual(len(self.calls), 1)

    def test_followup_calls_obey_existing_call_budget(self):
        self.respond = lambda _: self.hook_response([request(ids=[self.ids[-1]])])
        state, task = self.dispatch(max_calls=1)
        self.assertEqual(state["stop_reason"], "call_budget_limit")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(task["status"], "cancelled")

    def test_stop_after_read_prevents_followup(self):
        self.respond = lambda _: self.hook_response([request(ids=[self.ids[-1]])])
        original = self.service._expert_data_hook
        def hook(run_id, task, action, payload):
            packet = original(run_id, task, action, payload)
            if action == "read":
                self.service.cancel("synthetic", run_id)
            return packet
        self.service._expert_data_hook = hook
        state, task = self.dispatch()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(state["status"], "cancelled")

    def test_repeated_requests_do_not_loop(self):
        self.respond = lambda _: self.hook_response([request(ids=[self.ids[-1]])])
        _, task = self.dispatch()
        self.assertNotEqual(task["status"], "succeeded")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(task["expert_hook_reads"]), 1)

    def test_disabled_hooks_keep_full_existing_context_and_schema(self):
        self.respond = lambda _: copy.deepcopy(self.report)
        _, task = self.dispatch(expert_hooks=False)
        self.assertEqual(task["status"], "succeeded", task["error"])
        self.assertEqual(len(self.calls[0][0]["raw_evidence"]), 30)
        self.assertNotIn("hook_requests", self.calls[0][1]["properties"])
        self.assertNotIn("expert_hooks", self.calls[0][0])
        self.assertEqual(len(self.calls[0][0]["coverage"]["evidence_index"]), 30)

    def test_mixed_hook_and_analysis_response_is_rejected(self):
        def response(_):
            raw = self.hook_response([request(ids=[self.ids[-1]])])
            raw["expert_report"] = self.report["expert_report"]
            return raw
        self.respond = response
        _, task = self.dispatch()
        self.assertNotEqual(task["status"], "succeeded")
        self.assertNotIn("expert_hook_reads", task)

    def test_final_invalid_report_is_saved_and_quarantined(self):
        def response(_):
            report = copy.deepcopy(self.report)
            report["expert_report"]["evidence_ids"] = ["invented"]
            return {**report, "hook_requests": []}
        self.respond = response
        _, task = self.dispatch()
        self.assertEqual(task["status"], "quarantined")
        with self.service._db() as db:
            raw = json.loads(db.execute("SELECT raw_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()[0])
        self.assertEqual(raw["expert_report"]["evidence_ids"], ["invented"])

    def test_changed_input_is_not_read_after_model_request(self):
        def response(_):
            self.fixture.item["revision_count"] = 2
            return self.hook_response([request(ids=[self.ids[-1]])])
        self.respond = response
        _, task = self.dispatch()
        self.assertEqual(task["error"], "revision_conflict")
        self.assertNotIn("expert_hook_reads", task)

    def test_at_most_two_data_rounds_and_three_model_calls(self):
        self.respond = lambda n: self.hook_response([request(ids=[self.ids[-n]])])
        _, task = self.dispatch()
        self.assertNotEqual(task["status"], "succeeded")
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(task["expert_hook_reads"]), 2)
        self.assertEqual(len(task["expert_hook_responses"]), 3)

    def test_statistical_expert_reads_only_its_validated_calculation(self):
        import test_statistical_expert_agents as statistics_fixtures
        fixture = statistics_fixtures.StatisticalExpertTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        service = fixture.service
        service.adapter_version = ADAPTER_VERSION
        service.find_item = lambda _: {"id": "synthetic", "revision_count": 1, "analysis_revision": 1}
        run = fixture.start(adapter_version=ADAPTER_VERSION)
        calculated = fixture.dispatch(run, statistics_fixtures.tool_intent("pearson"))
        self.assertEqual(calculated["status"], "succeeded")
        with service._db() as db:
            saved = service._read_run(db, run["run_id"])
            task = service._register(db, saved, fixtures.intent("interpretation", expert_id="exp-correlation",
                dependencies=[calculated["task_id"]]), phase="specialists")
            context = service._context(db, saved, task)
            report = fixture.expert_report(context)
            calculation = context["expert_request"]["calculations"][0]
            table_id = next(iter(calculation["datasets"]))
        seen = []
        def call(*args):
            seen.append(json.loads(args[4]))
            if len(seen) == 1:
                return wire_response(self.hook_response([request("read_calculation_table", result_id=calculated["result_id"], table_id=table_id, limit=1)]))
            return wire_response({**report, "hook_requests": []})
        _, service.agent_runner = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        service._execute(run["run_id"], task["task_id"])
        state = service.status("synthetic", run["run_id"])
        completed = next(t for t in state["tasks"] if t["task_id"] == task["task_id"])
        self.assertEqual(completed["status"], "succeeded", completed["error"])
        self.assertEqual(seen[1]["expert_hook_results"][0]["source_hash"], calculation["raw_hash"])
        self.assertEqual(len(seen[1]["expert_hook_results"][0]["rows"]), 1)
        self.assertEqual([t["method_id"] for t in state["tasks"] if t["kind"] == "code"], ["pearson"])


class StatisticalHookDeliveryTests(unittest.TestCase):
    """Real Handler/adapter boundary; the reply binds a row received on demand."""
    def setUp(self):
        import test_statistical_expert_agents as statistics
        self.statistics = statistics
        self.fixture = statistics.StatisticalExpertTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.service = self.fixture.service
        self.service.adapter_version = ADAPTER_VERSION
        self.service.find_item = lambda _: {"id": "synthetic", "revision_count": 1, "analysis_revision": 1}
        self.calls = []

    def exercise(self, *, offsets=(8,), text_limit=60000, mutate_packet=None,
                 requests=None, final_row=None, before_continue=None, mutate_delivery=None):
        from gurumoji.services.expert_agents import cell_binding
        h, service = self.fixture, self.service
        run = h.start(adapter_version=ADAPTER_VERSION, context_text_limit=text_limit)
        calculated = [h.dispatch(run, self.statistics.tool_intent(method)) for method in ("pearson", "spearman")]
        self.assertTrue(all(t["status"] == "succeeded" for t in calculated))
        with service._db() as db:
            saved = service._read_run(db, run["run_id"])
            task = service._register(db, saved, fixtures.intent("interpretation", expert_id="exp-correlation",
                dependencies=[t["task_id"] for t in calculated]), phase="specialists")
            context = service._context(db, saved, task)
            self.calculation = context["expert_request"]["calculations"][0]
            self.report = h.expert_report(context)
        self.fixed = service.result("synthetic", run["run_id"], self.calculation["result_id"])
        self.original = self.fixed["raw"]["datasets"]["correlations"]["rows"]
        self.initial_ids = [r["row_id"] for r in self.calculation["datasets"]["correlations"]["rows"]]
        original_hook = service._expert_data_hook
        def hook(run_id, task, action, payload):
            if action == "continue" and mutate_delivery:
                mutate_delivery(payload)
            packet = original_hook(run_id, task, action, payload)
            if action == "read" and mutate_packet:
                mutate_packet(packet)
            if action == "continue" and before_continue:
                before_continue(run_id, task)
            return packet
        service._expert_data_hook = hook
        def call(*args):
            packet, schema = json.loads(args[4]), copy.deepcopy(args[6])
            self.calls.append((packet, schema))
            n = len(self.calls)
            if n <= len(offsets):
                reads = requests(self, n) if requests else [request("read_calculation_table",
                    result_id=self.calculation["result_id"], table_id="correlations", offset=offsets[n - 1], limit=1)]
                return {"expert_response": {"mode": "read", "hook_requests": reads}}
            raw = copy.deepcopy(self.report)
            row = self.original[offsets[-1]] if final_row is None else final_row(self)
            raw["expert_report"]["numeric_bindings"] = [cell_binding(self.calculation, "correlations", row, "coefficient")]
            raw["expert_report"]["calculation_result_ids"] = [self.calculation["result_id"]]
            return {"expert_response": {"mode": "report", "result": raw}}
        _, service.agent_runner = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="unused"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        service._execute(run["run_id"], task["task_id"])
        state = service.status("synthetic", run["run_id"])
        completed = next(t for t in state["tasks"] if t["task_id"] == task["task_id"])
        self.assertEqual(service.result("synthetic", run["run_id"], self.calculation["result_id"]), self.fixed)
        result = service.result("synthetic", run["run_id"], completed["result_id"]) if completed.get("result_id") else None
        return state, completed, result

    def test_row_beyond_initial_excerpt_is_delivered_bound_and_rendered(self):
        _, task, stored = self.exercise()
        row = self.original[8]
        self.assertNotIn(row["row_id"], self.initial_ids)
        self.assertEqual(self.calls[1][0]["expert_hook_results"][0]["rows"], [row])
        self.assertEqual(task["status"], "succeeded", task["error"])
        bindings = self.calls[1][1]["properties"]["expert_response"]["anyOf"][1]["properties"]["result"]["properties"]["expert_report"]["properties"]["numeric_bindings"]
        self.assertIn(row["row_id"], bindings["items"]["properties"]["row_id"]["enum"])
        self.assertIn(row["row_id"], task["expert_calculation_refs"][0]["provided_rows"]["correlations"])
        cell = stored["statistical_review"]["rendered_cells"][0]
        self.assertEqual(cell["value"], row["coefficient"])
        self.assertEqual(cell["binding"]["rows_hash"], self.fixed["raw"]["manifest"]["rows_hash"])
        self.assertEqual(stored["statistical_review"]["status"], "human_pending")

    def test_multiple_packets_and_pages_keep_exact_delivered_scope(self):
        def pages(h, n):
            return [request("read_calculation_table", result_id=h.calculation["result_id"],
                            table_id="correlations", offset=8 + 3 * (n - 1) + i, limit=1) for i in range(3)]
        _, task, stored = self.exercise(offsets=(8, 11), requests=pages, final_row=lambda h: h.original[13])
        self.assertEqual(task["status"], "succeeded", task["error"])
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(task["expert_hook_reads"]), 6)
        self.assertEqual(len(task["expert_hook_deliveries"]), 2)
        supplied = task["expert_calculation_refs"][0]["provided_rows"]["correlations"]
        self.assertEqual(set(supplied), {r["row_id"] for r in self.original[:14]})
        self.assertNotIn(self.original[14]["row_id"], supplied)
        self.assertEqual(len(self.calls[-1][0]["expert_hook_results"]), 6)
        self.assertEqual(stored["statistical_review"]["semantic_review"], "undetermined")

    def test_initial_rows_remain_usable_after_continuation_table_is_empty(self):
        _, task, _ = self.exercise(final_row=lambda h: h.original[0])
        self.assertEqual(self.calls[1][0]["expert_request"]["calculations"][0]["datasets"]["correlations"]["rows"], [])
        self.assertEqual(task["status"], "succeeded", task["error"])

    def test_cap_and_unread_rows_are_never_authorized(self):
        for capped in (True, False):
            with self.subTest(capped=capped):
                self.calls.clear()
                _, task, _ = self.exercise(text_limit=60 if capped else 60000,
                    final_row=lambda h: h.original[8 if capped else 14])
                self.assertEqual(task["status"], "quarantined")
                self.assertEqual(task["error"], "expert_reference_mismatch")
                if capped:
                    self.assertEqual(self.calls[1][0]["expert_hook_results"][0]["rows"], [])
                self.assertNotIn(self.original[8 if capped else 14]["row_id"], task["expert_calculation_refs"][0]["provided_rows"]["correlations"])

    def test_reads_without_delivery_proof_do_not_expand_final_scope(self):
        _, task, _ = self.exercise(mutate_delivery=lambda p: p["calculation_packets"].clear())
        self.assertEqual(len(task["expert_hook_reads"]), 1)
        self.assertNotIn("expert_hook_deliveries", task)
        self.assertEqual(task["status"], "quarantined")
        self.assertEqual(task["error"], "expert_reference_mismatch")

    def test_altered_packets_are_rejected_before_continuation(self):
        mutations = (
            lambda p: p.update(data_version="other"), lambda p: p.update(source_hash="changed"),
            lambda p: p.update(version="future"), lambda p: p.update(result_id="other"),
            lambda p: p["rows"][0].update(coefficient=-0.99),
            lambda p: p["rows"][0].update(row_id="invented"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.calls.clear()
                _, task, _ = self.exercise(mutate_packet=mutate)
                self.assertEqual(task["status"], "uncertain")
                self.assertEqual(task["error"], "expert_hook_delivery_mismatch")
                self.assertEqual(len(self.calls), 1)
                self.assertNotIn("expert_hook_deliveries", task)

    def test_unknown_other_run_and_table_requests_are_rejected(self):
        def other_run(h, _):
            other = h.fixture.start(adapter_version=ADAPTER_VERSION)
            calculated = h.fixture.dispatch(other, h.statistics.tool_intent("pearson"))
            return [request("read_calculation_table", result_id=calculated["result_id"], table_id="correlations", limit=1)]
        for make in (
            lambda h, _: [request("read_calculation_table", result_id="unknown", table_id="correlations")],
            lambda h, _: [request("read_calculation_table", result_id=h.calculation["result_id"], table_id="unknown")],
            other_run,
        ):
            with self.subTest(make=make):
                self.calls.clear()
                _, task, _ = self.exercise(requests=make)
                self.assertEqual(task["status"], "uncertain")
                self.assertIn(task["error"], {"expert_hook_scope_mismatch", "expert_hook_table_missing"})
                self.assertEqual(len(self.calls), 1)
                self.assertNotIn("expert_hook_deliveries", task)

    def test_stop_prevents_additional_model_call_and_promotion(self):
        state, task, stored = self.exercise(before_continue=lambda rid, _: self.service.cancel("synthetic", rid))
        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(stored)

    def test_received_delivery_receipt_recovery_never_reexecutes(self):
        mutations = {
            "generation": lambda t: t["expert_hook_deliveries"][0].update(generation=t["generation"] + 1),
            "attempt": lambda t: t["expert_hook_deliveries"][0].update(attempt_id="other"),
            "run": lambda t: t["expert_hook_reads"][0].update(run_id="other"),
            "version": lambda t: t["expert_hook_reads"][0].update(version="future"),
            "hash": lambda t: t["expert_hook_reads"][0].update(packet_hash="changed"),
            "source": lambda t: t["expert_hook_reads"][0].update(source_hash="changed"),
            "rows": lambda t: t["expert_hook_deliveries"][0]["packets"][0]["provided_rows"].update(correlations=["invented"]),
            "downgrade": lambda t: t["expert_calculation_refs"][0].pop("delivery_version"),
        }
        for broken in (None, *mutations):
            with self.subTest(broken=broken):
                self.calls.clear()
                state, task, stored = self.exercise()
                count = len(self.calls)
                with self.service._db() as db:
                    row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task["task_id"],)).fetchone()
                    current = json.loads(row[0])
                    current.update(status="received", validation_status="received")
                    if broken:
                        mutations[broken](current)
                    self.service._write_task(db, current)
                    metadata = copy.deepcopy(stored)
                    metadata.pop("raw")
                    metadata["validation_status"] = "received"
                    db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (json.dumps(metadata), task["result_id"]))
                self.service._validate_received(state["run_id"], task["task_id"])
                reread = self.service.result("synthetic", state["run_id"], task["result_id"])
                self.assertEqual(reread["validation_status"], "quarantined" if broken else "valid")
                if broken:
                    self.assertEqual(reread["error"], "expert_hook_delivery_mismatch")
                else:
                    self.assertEqual(reread["statistical_review"], stored["statistical_review"])
                self.assertEqual(len(self.calls), count)

    def test_legacy_hook_run_read_and_received_validation_do_not_replay(self):
        from gurumoji.analysis_orchestration import recover_orchestration_runs
        state, task, stored = self.exercise(final_row=lambda h: h.original[0])
        with self.service._db() as db:
            run = self.service._read_run(db, state["run_id"])
            run["config"]["expert_hook_version"] = "expert-data-hooks-2"
            run["config"]["adapter_version"] = "core-handler-prompts-9-statistical-cells"
            self.service._write_run(db, run)
            current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task["task_id"],)).fetchone()[0])
            current.update(status="received", validation_status="received")
            current.pop("expert_hook_deliveries")
            for ref in current["expert_calculation_refs"]:
                ref.pop("delivery_version")
                ref["provided_rows"] = ref.pop("initial_provided_rows")
            for read in current["expert_hook_reads"]:
                read["version"] = "expert-data-hooks-2"
                for key in ("provided_rows", "result_id", "table_id", "run_id", "task_id", "attempt_id", "generation"):
                    read.pop(key, None)
            self.service._write_task(db, current)
            metadata = copy.deepcopy(stored)
            metadata.pop("raw")
            metadata["validation_status"] = "received"
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (json.dumps(metadata), task["result_id"]))
            recover_orchestration_runs(db)
        count = len(self.calls)
        self.service._validate_received(state["run_id"], task["task_id"])
        reread = self.service.result("synthetic", state["run_id"], task["result_id"])
        self.assertEqual(reread["validation_status"], "valid")
        self.assertEqual(reread["raw_hash"], stored["raw_hash"])
        self.assertEqual(reread["statistical_review"], stored["statistical_review"])
        self.service.status("synthetic", state["run_id"])
        with self.assertRaises(AnalysisContractError) as caught:
            self.service.resume("synthetic", state["run_id"])
        self.assertEqual(caught.exception.code, "expert_hook_version_conflict")
        self.assertEqual(len(self.calls), count)

    def test_null_delivery_is_quarantined_without_raw_change_or_execution(self):
        state, task, stored = self.exercise()
        self.service.agent_runner = Mock(side_effect=AssertionError("recovery must not call AI"))
        self.service.method_runner = Mock(side_effect=AssertionError("recovery must not compute"))
        with self.service._db() as db:
            current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task["task_id"],)).fetchone()[0])
            current.update(status="received", validation_status="received", expert_hook_deliveries=[None])
            self.service._write_task(db, current)
            metadata = copy.deepcopy(stored)
            metadata.pop("raw")
            metadata["validation_status"] = "received"
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (json.dumps(metadata), task["result_id"]))
        self.service._validate_received(state["run_id"], task["task_id"])
        reread = self.service.result("synthetic", state["run_id"], task["result_id"])
        self.assertEqual(reread["validation_status"], "quarantined")
        self.assertEqual(reread["error"], "expert_hook_delivery_mismatch")
        self.assertEqual(reread["raw"], stored["raw"])
        self.assertEqual(reread["raw_hash"], stored["raw_hash"])
        self.service.agent_runner.assert_not_called()
        self.service.method_runner.assert_not_called()

    def test_received_json_receipt_shape_damage_is_quarantined(self):
        state, task, stored = self.exercise()
        self.service.agent_runner = Mock(side_effect=AssertionError("recovery must not call AI"))
        self.service.method_runner = Mock(side_effect=AssertionError("recovery must not compute"))
        with self.service._db() as db:
            original = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task["task_id"],)).fetchone()[0])
        def delivery(t): return t["expert_hook_deliveries"][0]
        def packet(t): return delivery(t)["packets"][0]
        def read(t): return t["expert_hook_reads"][0]
        mutations = {
            "delivery collection null": lambda t: t.update(expert_hook_deliveries=None),
            "delivery collection object": lambda t: t.update(expert_hook_deliveries={}),
            "delivery item string": lambda t: t.update(expert_hook_deliveries=["invalid"]),
            "delivery item array": lambda t: t.update(expert_hook_deliveries=[[]]),
            "delivery item empty": lambda t: t.update(expert_hook_deliveries=[{}]),
            "delivery identity missing": lambda t: delivery(t).pop("task_id"),
            "delivery call boolean": lambda t: delivery(t).update(model_call=True),
            "packet collection null": lambda t: delivery(t).update(packets=None),
            "packet collection object": lambda t: delivery(t).update(packets={}),
            "packet item null": lambda t: delivery(t).update(packets=[None]),
            "packet item string": lambda t: delivery(t).update(packets=["invalid"]),
            "packet item empty": lambda t: delivery(t).update(packets=[{}]),
            "packet hash missing": lambda t: packet(t).pop("packet_hash"),
            "packet hash null": lambda t: packet(t).update(packet_hash=None),
            "packet result array": lambda t: packet(t).update(result_id=[]),
            "packet rows null": lambda t: packet(t).update(provided_rows=None),
            "packet row list scalar": lambda t: packet(t).update(provided_rows={"correlations": "invalid"}),
            "packet row item object": lambda t: packet(t).update(provided_rows={"correlations": [{}]}),
            "read collection null": lambda t: t.update(expert_hook_reads=None),
            "read collection object": lambda t: t.update(expert_hook_reads={}),
            "read item null": lambda t: t.update(expert_hook_reads=[None]),
            "read item string": lambda t: t.update(expert_hook_reads=["invalid"]),
            "read item empty": lambda t: t.update(expert_hook_reads=[{}]),
            "read packet hash missing": lambda t: read(t).pop("packet_hash"),
            "read identity missing": lambda t: read(t).pop("attempt_id"),
            "read generation null": lambda t: read(t).update(generation=None),
            "read request null": lambda t: read(t).update(request=None),
            "read request empty": lambda t: read(t).update(request={}),
            "read request offset string": lambda t: read(t)["request"].update(offset="8"),
            "read row ids null": lambda t: read(t).update(provided_rows={"correlations": [None]}),
            "initial rows null": lambda t: t["expert_calculation_refs"][0].update(initial_provided_rows=None),
            "final row item object": lambda t: t["expert_calculation_refs"][0].update(provided_rows={"correlations": [{}]}),
        }
        for name, mutate in mutations.items():
            with self.subTest(damage=name):
                current = copy.deepcopy(original)
                current.update(status="received", validation_status="received")
                mutate(current)
                metadata = copy.deepcopy(stored)
                metadata.pop("raw")
                metadata["validation_status"] = "received"
                with self.service._db() as db:
                    self.service._write_task(db, current)
                    db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (json.dumps(metadata), task["result_id"]))
                self.service._validate_received(state["run_id"], task["task_id"])
                reread = self.service.result("synthetic", state["run_id"], task["result_id"])
                self.assertEqual(reread["validation_status"], "quarantined")
                self.assertEqual(reread["error"], "expert_hook_delivery_mismatch")
                self.assertEqual(reread["raw"], stored["raw"])
                self.assertEqual(reread["raw_hash"], stored["raw_hash"])
        self.service.agent_runner.assert_not_called()
        self.service.method_runner.assert_not_called()


WIRE_OBSERVATIONS = []


class ExpertWireProjectionTests(unittest.TestCase):
    def test_323_exact_inverse_preserves_nested_values_presence_and_order(self):
        original = synthetic_wire_packet()
        before = json.dumps(original, ensure_ascii=False)
        wire = adapters._project_expert_wire(original)
        self.assertTrue(wire["expert_wire_delivery"]["labels_table"])
        self.assertEqual(wire["expert_hooks"]["evidence_index"]["columns"], ["evidence_id"])
        self.assertEqual(len(wire["expert_hooks"]["evidence_index"]["rows"]), 323)
        restored = independently_decode_wire(wire, original)
        self.assertEqual(json.dumps(restored, ensure_ascii=False), before)
        self.assertEqual(json.dumps(adapters._restore_expert_wire(wire, expected_hash=ordered_wire_hash(original)),
                                   ensure_ascii=False), before)
        self.assertEqual(json.dumps(original, ensure_ascii=False), before)
        self.assertNotIn("theme", restored["labels"]["u000"])
        self.assertIsNone(restored["labels"]["u001"]["code"])
        self.assertIs(restored["labels"]["u001"]["sentiment"], False)
        self.assertIs(type(restored["labels"]["u001"]["importance"]), int)
        self.assertEqual(restored["labels"]["u001"]["theme"], "")
        self.assertEqual(restored["task"]["intent"]["evidence_ids"], [])  # Valid dataset-wide scope.
        self.assertEqual(restored["raw_evidence"], original["raw_evidence"])
        self.assertEqual(restored["task"]["dependencies"], original["task"]["dependencies"])
        self.assertEqual(list(restored["labels"]), list(original["labels"]))
        for uid in original["labels"]:
            self.assertEqual(list(restored["labels"][uid]), list(original["labels"][uid]))

    def test_small_packets_fall_back_and_index_only_projection_keeps_optional_labels(self):
        for count in (0, 1):
            with self.subTest(count=count):
                source = synthetic_wire_packet(count)
                wire = adapters._project_expert_wire(source)
                self.assertNotIn("expert_wire_delivery", wire)
                self.assertEqual(json.dumps(wire), json.dumps(source))
                self.assertEqual(independently_decode_wire(wire, source), source)
        source = synthetic_wire_packet()
        del source["labels"]
        wire = adapters._project_expert_wire(source)
        self.assertFalse(wire["expert_wire_delivery"]["labels_table"])
        self.assertEqual(independently_decode_wire(wire, source), source)
        self.assertNotIn("labels", independently_decode_wire(wire, source))

    def test_malformed_foreign_reordered_and_self_rehashed_wire_is_rejected(self):
        source = synthetic_wire_packet()
        wire = adapters._project_expert_wire(source)
        changes = {
            "index duplicate column": lambda w: w["expert_hooks"]["evidence_index"]["columns"].append("evidence_id"),
            "index wrong column": lambda w: w["expert_hooks"]["evidence_index"].update(columns=["utterance_id"]),
            "index row type": lambda w: w["expert_hooks"]["evidence_index"]["rows"].__setitem__(0, {}),
            "index row width": lambda w: w["expert_hooks"]["evidence_index"]["rows"][0].append("extra"),
            "index nonstring ID": lambda w: w["expert_hooks"]["evidence_index"]["rows"][0].__setitem__(0, 0),
            "index foreign ID": lambda w: w["expert_hooks"]["evidence_index"]["rows"][0].__setitem__(0, "ev_foreign"),
            "index duplicate ID": lambda w: w["expert_hooks"]["evidence_index"]["rows"].__setitem__(1, copy.deepcopy(w["expert_hooks"]["evidence_index"]["rows"][0])),
            "index reordered": lambda w: w["expert_hooks"]["evidence_index"]["rows"].reverse(),
            "label duplicate columns": lambda w: w["labels"]["columns"].__setitem__(1, w["labels"]["columns"][0]),
            "label column type": lambda w: w["labels"]["columns"].__setitem__(0, 0),
            "label row width": lambda w: w["labels"]["rows"][0].pop(),
            "label row type": lambda w: w["labels"]["rows"].__setitem__(0, {}),
            "label duplicate owner": lambda w: w["labels"]["owners"].__setitem__(1, w["labels"]["owners"][0]),
            "label foreign owner": lambda w: w["labels"]["owners"].__setitem__(0, "foreign-owner"),
            "label owner order": lambda w: w["labels"]["owners"].reverse(),
            "label boolean order": lambda w: w["labels"]["row_orders"].__setitem__(0, False),
            "label missing order": lambda w: w["labels"]["row_orders"].pop(),
            "label duplicate present key": lambda w: w["labels"]["field_orders"][0].append(w["labels"]["field_orders"][0][0]),
            "label missing becomes null": lambda w: w["labels"]["field_orders"][0].append(w["labels"]["columns"].index("theme")),
            "label key order": lambda w: w["labels"]["field_orders"][0].reverse(),
            "null becomes zero": lambda w: w["labels"]["rows"][1].__setitem__(w["labels"]["columns"].index("code"), 0),
            "false becomes zero": lambda w: w["labels"]["rows"][1].__setitem__(w["labels"]["columns"].index("sentiment"), 0),
            "source version": lambda w: w.update(data_version="foreign-input"),
            "knowledge hash": lambda w: w.update(knowledge_hash="foreign-knowledge"),
            "raw fragment": lambda w: w["raw_evidence"][0].update(text_offset=1),
            "binding hash": lambda w: w["expert_wire_delivery"].update(source_hash="sha256:foreign"),
        }
        for name, change in changes.items():
            with self.subTest(change=name):
                bad = copy.deepcopy(wire); change(bad)
                with self.assertRaises(ValueError): independently_decode_wire(bad, source)
                with self.assertRaises(AnalysisContractError):
                    adapters._restore_expert_wire(bad, expected_hash=ordered_wire_hash(source))
        changed = copy.deepcopy(source)
        changed["expert_hooks"]["evidence_index"][0]["evidence_id"] = "ev_foreign"
        self_rehashed = adapters._project_expert_wire(changed)
        with self.assertRaises(ValueError): independently_decode_wire(self_rehashed, source)
        with self.assertRaises(AnalysisContractError):
            adapters._restore_expert_wire(self_rehashed, expected_hash=ordered_wire_hash(source))

    def test_invalid_source_ids_and_json_keys_never_get_silently_coerced(self):
        mutations = (
            lambda p: p["expert_hooks"]["evidence_index"][0].update(evidence_id=False),
            lambda p: p["expert_hooks"]["evidence_index"].append(copy.deepcopy(p["expert_hooks"]["evidence_index"][0])),
            lambda p: p["expert_hooks"]["evidence_index"][0].update(unknown="must not drop"),
            lambda p: p["labels"].update({0: {"code": None}}),
            lambda p: p["labels"]["u000"]["review"].update({1: "must not stringify"}),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                source = synthetic_wire_packet(); mutate(source)
                before = copy.deepcopy(source)
                with self.assertRaises(AnalysisContractError): adapters._project_expert_wire(source)
                self.assertEqual(source, before)

    def test_nonexpert_clarification_disabled_and_statistical_routes_do_not_project(self):
        calls = []
        response = {}
        def call(*args):
            calls.append(args)
            return wire_response(response) if "expert_response" in args[6]["properties"] else response
        resolve, runner = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        with patch.object(adapters, "_project_expert_wire", side_effect=AssertionError("non-target route")):
            for role in ("interpretation", "core", "critic", "verification"):
                context = {"task": {"task_id": "unchanged", "role": role, "dependencies": [], "intent": {"kind": "analysis"}},
                           "raw_evidence": [], "labels": {}, "results": []}
                runner(role, context, resolve({"model": "fixture"}), lambda: None, lambda _: None)
                self.assertNotIn("expert_wire_delivery", json.loads(calls[-1][4]))
            for statistical, clarification, enabled in ((False, False, False), (False, True, True), (True, False, True)):
                with self.subTest(statistical=statistical, clarification=clarification, hooks=enabled):
                    if statistical:
                        import test_statistical_expert_agents as statistics
                        helper = statistics.StatisticalExpertTests("runTest"); helper.setUp(); self.addCleanup(helper.doCleanups)
                        helper.service.find_item = lambda _: {"id": "synthetic", "revision_count": 1, "analysis_revision": 1}
                        run = helper.start(adapter_version=ADAPTER_VERSION)
                        expert = "exp-correlation"
                    else:
                        helper = expert_fixtures.ExpertAgentTests("runTest"); helper.setUp(); self.addCleanup(helper.doCleanups)
                        helper.item.update(revision_count=1, analysis_revision=1)
                        run = helper.start(adapter_version=ADAPTER_VERSION, expert_hooks=enabled)
                        expert = expert_fixtures.EXPERT
                    with helper.service._db() as db:
                        current = helper.service._read_run(db, run["run_id"])
                        intent = fixtures.intent("interpretation", expert_id=expert)
                        if clarification:
                            intent.update(kind="clarification", result_id=run["initial_id"], initial_sections=["segments"])
                        task = helper.service._register(db, current, intent, phase="specialists")
                        context = helper.service._context(db, current, task)
                    if clarification:
                        self.assertFalse(context["execution_allowed"])
                        self.assertEqual(context["clarification_target"]["initial_id"], run["initial_id"])
                    response = helper.expert_report(context) if statistical else helper.report(context)
                    before = json.dumps(context, ensure_ascii=False)
                    runner("interpretation", context, {**run["config"], "_expert_data_hook": lambda *_: self.fail("No read needed")},
                           lambda: None, lambda _: None)
                    self.assertNotIn("expert_wire_delivery", json.loads(calls[-1][4]))
                    self.assertEqual(json.dumps(context, ensure_ascii=False), before)

    def test_actual_323_handler_hook_store_and_fresh_preserve_internal_packets(self):
        import app
        import test_content_analysis as content
        import gurumoji.services.expert_data_hooks as hooks
        from gurumoji.analysis_orchestration import AnalysisOrchestrationService
        from gurumoji.analysis_store import AnalysisStore
        from gurumoji.services.analysis_orchestration_publication import build_orchestration_package
        fixture = content.ContentApiTests("runTest"); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        helper = expert_fixtures.ExpertAgentTests("runTest"); helper.setUp(); self.addCleanup(helper.doCleanups)
        source_labels = synthetic_wire_packet()["labels"]
        helper.snap["analysis"]["segments"] = [{"id": uid, "text": f"Public synthetic utterance {i:03d}",
            "speaker": "A" if i % 2 else "B", "annotation": labels, "excluded": False}
            for i, (uid, labels) in enumerate(source_labels.items())]
        service = helper.service
        service.connect, service.find_item = app.database_connection, app.library_row
        service.adapter_version = ADAPTER_VERSION
        item = dict(app.library_row("content"))
        helper.snap["source_revision"] = item["revision_count"]
        helper.snap["analysis_revision"] = item["analysis_revision"]
        original_source = copy.deepcopy(helper.snap)
        calls, internal, handler_inputs = [], [], []
        report, ids = {}, []
        def call(*args):
            calls.append({"prompt": args[3], "input": args[4], "schema": copy.deepcopy(args[6])})
            if len(calls) == 1:
                return wire_response({"hook_requests": [request(ids=[ids[-1]])]})
            response = copy.deepcopy(report); response["expert_report"]["evidence_ids"] = [ids[-1]]
            return wire_response(response)
        _, adapter = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"))
        def agent(role, context, *rest):
            before = copy.deepcopy(context); handler_inputs.append(before)
            result = adapter(role, context, *rest)
            self.assertEqual(json.dumps(context), json.dumps(before))
            return result
        service.agent_runner = agent
        original_hooks = hooks.run_with_hooks
        def observe(context, schema, callback, *rest):
            def outbound(packet, *args):
                before = copy.deepcopy(packet); internal.append(before)
                result = callback(packet, *args)
                self.assertIsInstance(packet["expert_hooks"]["evidence_index"], list)
                self.assertEqual(json.dumps(packet), json.dumps(before))
                return result
            return original_hooks(context, schema, outbound, *rest)
        guards = (patch("socket.socket.connect", side_effect=AssertionError("No network")),
                  patch.object(AnalysisStore, "_publish_generated_vaults", side_effect=AssertionError("No Vault")),
                  patch.object(AnalysisStore, "_publish_research", side_effect=AssertionError("No Vault")),
                  patch.object(hooks, "run_with_hooks", side_effect=observe))
        for guard in guards: guard.start(); self.addCleanup(guard.stop)
        run = service.start("content", {"model": "fixture", "adapter_version": ADAPTER_VERSION,
            "expert_ids": [expert_fixtures.EXPERT], "time_limit_seconds": None,
            "obsidian_management": False, "publication_targets": []})
        with service._db() as db:
            current = service._read_run(db, run["run_id"])
            initial = service._initial(db, current["initial_id"])
            ids.extend(row["evidence_id"] for row in initial["evidence"])
            task = service._register(db, current, fixtures.intent("interpretation", expert_id=expert_fixtures.EXPERT,
                                    evidence_ids=[]), phase="specialists")
            report.update(helper.report(service._context(db, current, task)))
        service._execute(run["run_id"], task["task_id"])
        exported = service.result("content", run["run_id"])
        saved_task = next(t for t in exported["run"]["tasks"] if t["task_id"] == task["task_id"])
        self.assertEqual(saved_task["status"], "succeeded", saved_task)
        self.assertEqual(saved_task["intent"]["evidence_ids"], [])
        self.assertEqual(saved_task["dependencies"], task["dependencies"])
        self.assertEqual(len(calls), 2)
        sizes = []
        for captured, original in zip(calls, internal):
            wire = json.loads(captured["input"])
            self.assertEqual(json.dumps(independently_decode_wire(wire, original)), json.dumps(original))
            self.assertEqual(decoded_index(wire), [{"evidence_id": eid} for eid in ids])
            old = {**captured, "input": json.dumps(original, ensure_ascii=False, separators=(",", ":")),
                   "prompt": captured["prompt"].removesuffix(adapters._EXPERT_WIRE_PROMPT)}
            old_size = len(json.dumps(old, ensure_ascii=False, separators=(",", ":")).encode())
            new_size = len(json.dumps(captured, ensure_ascii=False, separators=(",", ":")).encode())
            self.assertLess(new_size, old_size)
            sizes.append({"before": old_size, "after": new_size})
        self.assertEqual(len(internal[0]["raw_evidence"]), 12)
        self.assertEqual(len(internal[1]["raw_evidence"]), 13)
        self.assertEqual(internal[1]["raw_evidence"][0]["utterance_id"], "u322")
        self.assertEqual(helper.snap, original_source)
        # Keep the pre-existing Handler delivery window exactly; the adapter
        # does not expand it or remove any label owner within that delivery.
        delivered_owners = list(source_labels)[:run["config"]["context_evidence_limit"]]
        self.assertEqual(handler_inputs[0]["labels"], {uid: source_labels[uid] for uid in delivered_owners})
        self.assertEqual(exported["label_versions"][0]["labels"], source_labels)
        self.assertEqual(exported["initial"]["snapshot"]["analysis"], original_source["analysis"])
        snapshot, result, datasets = build_orchestration_package(exported, fingerprint(exported))
        store = app.analysis_archive_store()
        saved = store.save(item_id="content", kind="autonomous_analysis", snapshot=snapshot, result=result,
            datasets=datasets, request_id="expert-wire-cpu", input_fingerprint="v1", source_revision=item["revision_count"],
            analysis_revision=item["analysis_revision"], publish=False)
        artifact = next(row for row in store.public(saved)["artifacts"] if row["name"] == "result.json")
        fresh_store = AnalysisStore(store.database_file, store.connect)
        fresh = AnalysisOrchestrationService(connect=app.database_connection, find_item=app.library_row,
            snapshot_builder=lambda *_: self.fail("No source rebuild"), agent_runner=lambda *_: self.fail("No model"),
            method_runner=lambda *_: self.fail("No code rerun"), schedule=False)
        before = app.DATABASE_FILE.read_bytes()
        _, payload = fresh_store.read_artifact(artifact["id"])
        self.assertEqual(payload, store.read_artifact(artifact["id"])[1])
        persisted = json.loads(payload)["orchestration"]
        for key in ("initial", "raw_results", "label_versions", "decisions"):
            self.assertEqual(persisted[key], exported[key])
        self.assertEqual(persisted["run"]["tasks"], exported["run"]["tasks"])
        self.assertEqual(fresh.result("content", run["run_id"]), exported)
        self.assertEqual(app.DATABASE_FILE.read_bytes(), before)
        self.assertNotIn("expert_wire_delivery", json.dumps(exported))
        WIRE_OBSERVATIONS.append({"run_id": run["run_id"], "task_id": task["task_id"], "result_id": saved_task["result_id"],
            "source_hash": fingerprint(original_source), "packet_hashes": [ordered_wire_hash(p) for p in internal],
            "all_ids": ids, "count": 323, "scope": [], "call_field_bytes": sizes,
            "delivered_label_owners": len(internal[0]["labels"]), "saved_label_owners": len(source_labels),
            "store_package_sha256": hashlib.sha256(payload).hexdigest(),
            "saved_raw_hash": exported["raw_results"][0]["raw_hash"], "model_execution": "NOTRUN", "tokens": "NOTRUN"})


class ReadHookBoundaryTests(unittest.TestCase):
    def test_table_paging_preserves_zero_and_missing_values(self):
        raw = {"method_id": "pearson", "datasets": {"correlations": {"fields": ["n", "r"],
               "rows": [{"n": i, "r": None if i == 0 else 0.0} for i in range(50)]}}}
        meta = {"result_id": "result1", "raw_hash": fingerprint(raw)}
        packet = read_data(request("read_calculation_table", result_id="result1", table_id="correlations", limit=40),
            evidence=[], calculations={"result1": (raw, meta)}, allowed_evidence_ids=[], data_version="v1")
        self.assertEqual(packet["rows"][0], {"n": 0, "r": None})
        self.assertEqual(packet["rows"][1]["r"], 0.0)
        self.assertEqual(packet["next_offset"], 40)
        self.assertEqual(packet["omitted_rows"], 10)
        self.assertFalse(packet["complete"])
        self.assertEqual(packet["source_hash"], fingerprint(raw))
        self.assertEqual(len(raw["datasets"]["correlations"]["rows"]), 50)

    def test_unknown_hooks_results_tables_and_invalid_ranges_are_rejected(self):
        for value in (request("shell"), request(ids=["unknown"]), request(offset=-1, ids=["e1"]),
                      request(limit=0, ids=["e1"]), request(limit=True, ids=["e1"]),
                      request("read_calculation_table", result_id="other", table_id="x")):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError):
                read_data(value, evidence=[], calculations={}, allowed_evidence_ids=["e1"], data_version="v1")

    def test_large_evidence_excerpts_can_be_read_by_character_offset(self):
        evidence = [{"evidence_id": "e1", "utterance_id": "u1", "text": "x" * 13000 + "tail", "speaker": "A", "excluded": False}]
        packet = read_data(request(ids=["e1"], offset=13000), evidence=evidence,
                           calculations={}, allowed_evidence_ids=["e1"], data_version="v1")
        self.assertEqual(packet["evidence"][0]["text"], "tail")
        self.assertFalse(packet["complete"])
        self.assertEqual(packet["evidence"][0]["omitted_text_characters"], 13000)

    def test_configuration_is_versioned_and_strictly_boolean(self):
        self.assertEqual(validate_orchestration_payload({"model": "fixture"})["expert_hook_version"], VERSION)
        for value in ("yes", 1, None):
            with self.assertRaises(AnalysisContractError):
                validate_orchestration_payload({"model": "fixture", "expert_hooks": value})
        with self.assertRaises(AnalysisContractError):
            validate_orchestration_payload({"model": "fixture", "expert_hook_version": "future"})


if __name__ == "__main__":
    unittest.main()
