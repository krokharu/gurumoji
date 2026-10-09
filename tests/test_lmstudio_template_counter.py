"""Finite Issue34 CPU fixtures, never live model/schema measurement acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import traceback
import unittest

from gurumoji.services.ai.lmstudio_template_counter import (
    LMStudioTemplateCounter, MODEL, TEMPLATE_SHA256, renderer_variables,
)
from gurumoji.services.ai.request_budget import BudgetHold, payload_hash
from test_ai_request_budget import Clock, make_budget, reserve, receipt

FIXTURE = json.loads((Path(__file__).parent / "fixtures/lmstudio/gemma_counter_synthetic.json").read_text(encoding="utf-8"))
P4 = next(p for p in FIXTURE["positive"] if p["name"] == "P4-logged-exact")
MANIFEST = {"model": MODEL, "model_identity": "synthetic-owned-GGUF-sha256",
    "tokenizer": "synthetic-owned-tokenizer-sha256", "loaded_instance_id": "synthetic-instance-1",
    "context_tokens": 32768, "parallel": 1, "quantization": "Q4_K_M", "reasoning_effort": "none",
    "effective_config_hash": "sha256:" + FIXTURE["template_source"]["raw_config_sha256"],
    "template_sha256": TEMPLATE_SHA256, "renderer_variables": renderer_variables()}


def counter(**changes):
    def tokenizer(rendered):
        if rendered != P4["rendered"]:
            raise AssertionError("Only the finite P4 token fixture is supported")
        return list(P4["token_ids"])
    args = dict(effective_template=FIXTURE["effective_template"], conditions=copy.deepcopy(MANIFEST),
        tokenize=tokenizer, verify_conditions=lambda: copy.deepcopy(MANIFEST),
        proof_source="Issue34-P4-synthetic-replay", acceptance_anchor="CPU-only-NOT-ACCEPTED",
        synthetic_only=True)
    args.update(changes)
    return LMStudioTemplateCounter(**args)


def budget_for(value, **changes):
    c = value.budget_conditions
    return make_budget(token_counter=value, model=c["model"], context_tokens=c["context_tokens"],
        tokenizer_id=c["tokenizer"], template_id=c["template"], proof_source=c["source"],
        acceptance_anchor=c["acceptance_anchor"], model_conditions_hash=c["model_conditions_hash"],
        synthetic_only=c["synthetic_only"], usage_policy=c["usage_policy"], **changes)


class TemplateCounterTests(unittest.TestCase):
    def test_fixed_jinja_all_positive_render_bytes_and_P4_actual_50_ids(self):
        value = counter()
        self.assertEqual(hashlib.sha256(FIXTURE["effective_template"].encode()).hexdigest(), TEMPLATE_SHA256)
        for sample in FIXTURE["positive"]:
            with self.subTest(name=sample["name"]):
                payload = copy.deepcopy(sample["payload"])
                self.assertEqual(value.render(payload).encode(), sample["rendered"].encode())
                if "rendered_sha256" in sample:
                    self.assertEqual(hashlib.sha256(value.render(payload).encode()).hexdigest(), sample["rendered_sha256"])
                self.assertEqual(payload, sample["payload"])
        proof = value(P4["payload"])
        self.assertEqual(proof["input_tokens"], 50)
        self.assertEqual(proof["input_tokens"], P4["raw_usage"]["prompt_tokens"])
        self.assertEqual(proof["payload_hash"], payload_hash(P4["payload"]))
        self.assertTrue(proof["synthetic_only"])
        self.assertNotIn("measurement_ready", proof)
        self.assertFalse(FIXTURE["measurement_ready"])

    def test_all_published_negative_mutations_rejected_before_tokenizer(self):
        value = counter(tokenize=lambda _: self.fail("negative reached tokenizer"))
        for sample in FIXTURE["negative"]:
            payload = copy.deepcopy(P4["payload"])
            payload.update(copy.deepcopy(sample["payload"]))
            if "remove_key" in sample:
                del payload[sample["remove_key"]]
            with self.subTest(name=sample["name"]), self.assertRaisesRegex(BudgetHold, sample["expected_rejection"]):
                value(payload)

    def test_unicode_and_literal_markers_remain_raw_payload_and_render_data(self):
        value = counter()
        for body in ('日本語😀 e\u0301 é <bos> <|think|>\n<|channel>thought\n<channel|>',
                     'line\r\nline\n日本語\u200d😀'):
            payload = copy.deepcopy(P4["payload"])
            payload["messages"][1]["content"] = body
            before = copy.deepcopy(payload)
            self.assertIn(body, value.render(payload))
            self.assertEqual(payload, before)
        payload["messages"][1]["content"] = " \t raw \n"
        self.assertIn("\nraw<turn|>", value.render(payload))  # The fixed template's trim, not ours.
        self.assertEqual(payload["messages"][1]["content"], " \t raw \n")

    def test_closed_output_temperature_json_and_schema_bounds(self):
        value = counter(tokenize=lambda _: [1])
        for output in (1, 4096):
            payload = copy.deepcopy(P4["payload"]); payload["max_tokens"] = output
            self.assertEqual(value(payload)["input_tokens"], 1)
        for key, bad in (("max_tokens", 0), ("max_tokens", 4097), ("max_tokens", True),
                         ("max_tokens", 1.0), ("max_tokens", float("nan")),
                         ("temperature", float("nan")), ("temperature", float("inf")),
                         ("temperature", True), ("reasoning_effort", None), ("seed", 1)):
            payload = copy.deepcopy(P4["payload"]); payload[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(BudgetHold): value(payload)
        root = P4["payload"]["response_format"]["json_schema"]["schema"]
        bad_schemas = [None, {}, {"type": "impossible"}, {**root, "unknown": 1},
            {**root, "required": ["absent"]}, {**root, "required": ["ok", "ok"]},
            {**root, "additionalProperties": True}, {**root, "description": float("nan")},
            {**root, "properties": {"ok": {"type": "integer", "minimum": True}}},
            {**root, "properties": {"ok": {"type": "string", "pattern": "["}}},
            {**root, "properties": {"ok": {"type": "string", "enum": [True]}}},
            {**root, "properties": {"ok": {"$ref": "https://invalid.example/schema"}}}]
        for bad in bad_schemas:
            payload = copy.deepcopy(P4["payload"]); payload["response_format"]["json_schema"]["schema"] = bad
            with self.subTest(schema=bad), self.assertRaisesRegex(BudgetHold, "renderer_schema_not_supported"):
                value(payload)

    def test_schema_is_hash_bound_REST_grammar_not_general_live_equivalence(self):
        value = counter(tokenize=lambda _: [1])
        first = copy.deepcopy(P4["payload"]); second = copy.deepcopy(first)
        second["response_format"]["json_schema"]["schema"]["description"] = "Different grammar metadata"
        self.assertEqual(value.render(first), value.render(second))
        self.assertNotEqual(value(first)["payload_hash"], value(second)["payload_hash"])
        self.assertEqual(FIXTURE["REST_schema_general_proof"], "PENDING")

    def test_template_and_all_pinned_conditions_reject_changes(self):
        with self.assertRaisesRegex(BudgetHold, "renderer_conditions_changed"):
            counter(effective_template=FIXTURE["effective_template"] + "\n")
        for key, bad in (("model", "other"), ("context_tokens", 32768.0), ("parallel", 2),
                         ("quantization", "Q8"), ("reasoning_effort", "high"),
                         ("template_sha256", "0" * 64), ("renderer_variables", {})):
            manifest = copy.deepcopy(MANIFEST); manifest[key] = bad
            with self.subTest(key=key), self.assertRaisesRegex(BudgetHold, "renderer_conditions_changed"):
                counter(conditions=manifest)
        for key in MANIFEST:
            state = copy.deepcopy(MANIFEST)
            value = counter(verify_conditions=lambda: state)
            state[key] = "changed"
            with self.subTest(fresh_key=key), self.assertRaisesRegex(BudgetHold, "renderer_conditions_changed"):
                value(P4["payload"])

    def test_fresh_verification_before_after_count_and_immediately_predispatch(self):
        events, state = [], copy.deepcopy(MANIFEST)
        def fresh(): events.append("fresh"); return copy.deepcopy(state)
        def tokenize(rendered): events.append("tokenize"); return P4["token_ids"]
        value = counter(verify_conditions=fresh, tokenize=tokenize)
        budget = budget_for(value)
        reserved = reserve(budget, payload=P4["payload"])
        self.assertEqual(events, ["fresh", "tokenize", "fresh"])
        budget.dispatch_timeout(reserved["ticket"], reserved["payload"])
        self.assertEqual(events, ["fresh", "tokenize", "fresh", "fresh"])
        state["effective_config_hash"] = payload_hash("changed")
        with self.assertRaisesRegex(BudgetHold, "parent_deadline_or_ticket"):
            budget.dispatch_timeout(reserved["ticket"], reserved["payload"])
        ledger = budget.ledger()
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4146)
        self.assertEqual(ledger["entries"][0]["state"], "unknown")
        self.assertFalse(ledger["measurement_ready"])

    def test_mid_count_change_or_unknown_reader_stops_reservation(self):
        state = copy.deepcopy(MANIFEST)
        def tokenize(_):
            state["loaded_instance_id"] = "new-instance"
            return [1]
        value = counter(verify_conditions=lambda: state, tokenize=tokenize)
        budget = budget_for(value)
        with self.assertRaisesRegex(BudgetHold, "renderer_conditions_changed"):
            reserve(budget, payload=P4["payload"])
        self.assertEqual(budget.ledger()["entry_count"], 0)
        for observed in (None, True, {}, {**MANIFEST, "extra": 0}):
            value = counter(verify_conditions=lambda: observed)
            with self.subTest(observed=observed), self.assertRaisesRegex(BudgetHold, "renderer_conditions_changed"):
                value(P4["payload"])

    def test_tokenizer_errors_counts_and_bad_ids_are_not_proofs_or_provider_leaks(self):
        for ids in (50, None, True, [], [True], [1.0], [-1], iter([1])):
            value = counter(tokenize=lambda _: ids)
            with self.subTest(ids=ids), self.assertRaisesRegex(BudgetHold, "renderer_tokenizer_unknown"):
                value(P4["payload"])
        def fail(_): raise RuntimeError("private-provider-body")
        try:
            counter(tokenize=fail)(P4["payload"])
        except BudgetHold as exc:
            self.assertNotIn("private-provider-body", "".join(traceback.format_exception(exc)))
        else: self.fail("must reject")

    def test_invalid_original_output_cannot_be_hidden_by_budget_4096_cap(self):
        for bad in (True, float("nan"), 0, 4097):
            payload = copy.deepcopy(P4["payload"]); payload["max_tokens"] = bad
            budget = budget_for(counter())
            with self.subTest(bad=bad), self.assertRaisesRegex(BudgetHold, "renderer_payload_not_supported"):
                reserve(budget, payload=payload)
            self.assertEqual(budget.ledger()["entry_count"], 0)

    def test_stripped_dispatch_verifier_rejected_and_strict_50_usage_retained(self):
        value = counter()
        budget = budget_for(value)
        budget._counter = lambda p: value(p)  # Unsupported wrapper loses verifier.
        with self.assertRaisesRegex(BudgetHold, "token_proof_unknown"):
            reserve(budget, payload=P4["payload"])
        for raw, passes in ((P4["raw_usage"], True), ({}, False),
                            ({"prompt_tokens": 47, "completion_tokens": 1, "total_tokens": 48}, False)):
            clock = Clock(); budget = budget_for(value, clock=clock)
            reserved = reserve(budget, payload=P4["payload"])
            args = (reserved["ticket"], receipt(reserved["ticket"], clock), {"usage": raw})
            if passes:
                budget.finish(*args, transport_ok=True, http_status=200)
                self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 51)
            else:
                with self.assertRaisesRegex(BudgetHold, "usage_unknown"):
                    budget.finish(*args, transport_ok=True, http_status=200)
                self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4146)


if __name__ == "__main__":
    unittest.main()
