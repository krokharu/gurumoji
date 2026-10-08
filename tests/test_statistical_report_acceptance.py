"""G0.5a-02/04: real acceptance boundaries, synthetic input and temporary SQLite.

The original a02 NumericRegressions and StepRegressions exposed failures on
ac4bc6cef2e806a2bf52f503625fb7a1363c20e3. These a04 fixtures adopt schema 2
and continue to check rejection or human-pending without expectedFailure.
The existing StatisticalExpertTests fixture is composed, not inherited, so its
ten tests are not rediscovered here. Negative responses preserve original
calculation data; separate storage/recovery tests explicitly alter temporary
SQLite metadata and constant-input tests remain wholly synthetic.

Handoff inspection table (requirements, NOT a proposed response schema):
QA-01 | result/row/column/variable/scope/input/hash binding | verified cells and
        code rendering follow accepted 07 and statistical-cells-v1.
QA-02 | phase x required step x actor x contract version | use W-knowledge's
        accepted declaration with unchanged actual plan/report step IDs.
QA-03 | causal/unadjusted/unread claims | retain semantic review as unreviewed;
        structural acceptance must not certify a researcher's interpretation.
G0.5a-04/FIX01 uses accepted 07 schema 2: numerical result prose is quarantined,
structural integers remain unverified drafts, and correct result numbers are
selected via the nine-key binding and rendered by code. Actor
prose remains unverified; only Handler results certify code attempts and no
researcher record is fabricated. No skip/expectedFailure weakens the checks.
"""
import copy
import json
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.expert_agents import validate_report, cell_binding, render_statistical_cell, NUMERIC_BINDING_FIELDS
import test_statistical_expert_agents as statistical_fixtures


DOMAINS = (
    ("exp-correlation", "pearson", "cor-ai-plan", "cor-ai-report"),
    ("exp-descriptive-statistics", "descriptive_statistics", "desc-ai-plan", "desc-ai-report"),
    ("exp-group-comparison-statistics", "anova", "grp-ai-plan", "grp-ai-report"),
)


def table_rows(packet):
    return next(iter(packet["calculations"][0]["datasets"].values()))["rows"]


def correlation_row(packet):
    return next(row for row in table_rows(packet)
                if row["variable_a"] == "duration_seconds" and row["variable_b"] == "characters")


def correlation_text(row, **changes):
    values = {**row, **changes}
    return (f"row_id={values['row_id']}; Pearson {values['variable_a']} / {values['variable_b']}; "
            f"coefficient={values['coefficient']}; n={values['n']}; missing={values['missing']}; "
            f"p_value={values['p_value']}; exploratory; p is unadjusted.")


def set_bindings(raw, packet, row, columns):
    calc = packet["calculations"][0]
    dataset = next(iter(calc["datasets"]))
    raw["expert_report"]["numeric_bindings"] = [cell_binding(calc, dataset, row, column) for column in columns]


class _AcceptanceFixture:
    def setUp(self):
        self.harness = statistical_fixtures.StatisticalExpertTests(methodName="runTest")
        self.addCleanup(self.harness.doCleanups)
        self.harness.setUp()
        self.original_report = self.harness.expert_report

    def _report(self, context, mutate):
        raw = self.original_report(context)
        packet = context["expert_request"]
        outputs = raw["expert_report"]["outputs"]
        raw["summary"] = "Synthetic AI draft; semantic review pending."
        outputs.update(
            analysis_plan="Use only the Handler's fixed exploratory input.",
            prerequisite_review="Independence and researcher decisions remain unverified.",
            quality_record="Only supplied rows read; omitted rows and source excerpts remain unread.",
            limitations="AI draft; no causal inference, multiple-testing correction or confirmed human review.")
        if not packet["calculations"]:
            outputs["result_explanation"] = "No calculation performed; request the allowlisted Handler tool."
            # Use ANOVA for the group's numeric explanation control, rather
            # than the fixture's first (cross-tabulation) tool.
            if packet["expert_id"] == "exp-group-comparison-statistics":
                raw["analysis_requests"][0]["method_id"] = "anova"
        elif packet["calculations"][0]["method_id"] == "pearson":
            set_bindings(raw, packet, correlation_row(packet), ("coefficient", "n", "missing", "p_value"))
            outputs["result_explanation"] = "Exploratory association of duration and characters; p is unadjusted."
        elif packet["calculations"][0]["method_id"] == "descriptive_statistics":
            row = next(row for row in table_rows(packet)
                       if row["scope"] == "overall" and row["variable"] == "characters")
            set_bindings(raw, packet, row, ("mean", "n", "missing"))
            outputs["result_explanation"] = "Exploratory overall characters summary."
        else:
            row = next(row for row in table_rows(packet) if row["outcome"] == "characters")
            set_bindings(raw, packet, row, ("statistic", "n", "p_value", "effect_size"))
            outputs["result_explanation"] = "Exploratory ANOVA of characters by speaker; p is unadjusted."
        if mutate is not None:
            mutate(raw, packet)
        return raw

    def _exercise(self, expert="exp-correlation", method="pearson", mutate=None):
        h = self.harness
        before_analysis = copy.deepcopy(h.analysis)
        run = h.start(expert)
        calculation = None
        if method is not None:
            calculation = h.dispatch(run, statistical_fixtures.tool_intent(method))
            self.assertEqual(calculation["status"], "succeeded")
            fixed = h.service.result("synthetic", run["run_id"], calculation["result_id"])
        h.expert_report = lambda context: self._report(context, mutate)
        task = h.dispatch(run, statistical_fixtures.fixtures.intent(
            "interpretation", expert_id=expert,
            dependencies=[calculation["task_id"]] if calculation else []))
        stored = h.service.result("synthetic", run["run_id"], task["result_id"])
        context = h.calls[-1][1]
        self.assertEqual(h.analysis, before_analysis)
        self.assertEqual(context["expert_request"]["response_phase"],
                         "result_explanation" if calculation else "analysis_plan")
        if calculation:
            if task["status"] == "succeeded":
                self.assertEqual(stored["raw"]["expert_report"]["calculation_result_ids"], [calculation["result_id"]])
            self.assertEqual(h.service.result("synthetic", run["run_id"], calculation["result_id"]), fixed)
        return run, task, stored, context

    def _validate(self, stored, context):
        packet = context["expert_request"]
        validate_report(packet["knowledge"], stored["raw"],
                        [row["evidence_id"] for row in context["raw_evidence"]],
                        [row["result_id"] for row in packet["calculations"]],
                        calculations=packet["calculations"], response_phase=packet["response_phase"])

    def _reject(self, mutate, *, expert="exp-correlation", method="pearson"):
        _, task, stored, context = self._exercise(expert, method, mutate)
        # Separate subtests keep both boundary failures visible on the baseline.
        with self.subTest(boundary="validate_report"):
            with self.assertRaises(AnalysisContractError):
                self._validate(stored, context)
        with self.subTest(boundary="Handler"):
            self.assertEqual(task["status"], "quarantined",
                             "Invalid explanation was accepted with its correct calculation result ID")
            self.assertEqual(stored["validation_status"], "quarantined")

    def _accept(self, expert, method, mutate=None):
        run, task, stored, context = self._exercise(expert, method, mutate)
        self._validate(stored, context)
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(stored["validation_status"], "valid")
        self.assertEqual(stored["content_status"], "unreviewed")
        self.assertEqual(stored["statistical_review"]["status"], "human_pending")
        self.assertFalse(stored["statistical_review"]["eligible_as_confirmed_evidence"])
        self.assertEqual(stored["raw"]["claims"], [])
        return run, task, stored, context

    def _accept_path(self, expert, method, plan_step, report_step):
        run, _, plan, _ = self._accept(expert, None)
        self.assertEqual(plan["raw"]["expert_report"]["status"], "needs_calculation")
        self.assertEqual(plan["raw"]["expert_report"]["performed_step_ids"], [plan_step])
        request = plan["raw"]["analysis_requests"][0]
        self.assertEqual(request["method_id"], method)
        calculation = self.harness.dispatch(run, request)
        self.assertEqual(calculation["status"], "succeeded")
        fixed = self.harness.service.result("synthetic", run["run_id"], calculation["result_id"])
        task = self.harness.dispatch(run, statistical_fixtures.fixtures.intent(
            "interpretation", expert_id=expert, question="Explain the verified calculation",
            dependencies=[calculation["task_id"]]))
        stored = self.harness.service.result("synthetic", run["run_id"], task["result_id"])
        self._validate(stored, self.harness.calls[-1][1])
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(stored["validation_status"], "valid")
        self.assertEqual(stored["content_status"], "unreviewed")
        self.assertEqual(stored["raw"]["expert_report"]["performed_step_ids"], [report_step])
        self.assertEqual(stored["raw"]["expert_report"]["calculation_result_ids"], [calculation["result_id"]])
        self.assertEqual(self.harness.service.result("synthetic", run["run_id"], calculation["result_id"]), fixed)


class StatisticalAcceptanceControls(_AcceptanceFixture, unittest.TestCase):
    def test_correlation_plan_and_result_steps(self):
        self._accept_path(*DOMAINS[0])

    def test_descriptive_plan_and_result_steps(self):
        self._accept_path(*DOMAINS[1])

    def test_group_comparison_plan_and_result_steps(self):
        self._accept_path(*DOMAINS[2])

    def test_correct_coefficient_rounding_and_small_p_are_accepted(self):
        _, _, stored, context = self._accept("exp-correlation", "pearson")
        cells = {c["binding"]["column"]: c for c in stored["statistical_review"]["rendered_cells"]}
        row = correlation_row(context["expert_request"])
        self.assertEqual(cells["coefficient"]["value"], row["coefficient"])
        self.assertEqual(cells["coefficient"]["display"], "0.976")
        self.assertEqual(cells["p_value"]["display"], "0.0044")
        self.assertFalse(cells["p_value"]["p_zero_display_is_exact_zero"])

    def test_correct_mean_rounding_is_accepted(self):
        def rounded(raw, packet):
            row = next(row for row in table_rows(packet)
                       if row["scope"] == "overall" and row["variable"] == "duration_seconds")
            self.assertEqual((row["n"], row["missing"], row["mean"]), (5, 1, 4.8))
            set_bindings(raw, packet, row, ("mean", "n", "missing"))
        _, _, stored, _ = self._accept("exp-descriptive-statistics", "descriptive_statistics", rounded)
        self.assertEqual([c["display"] for c in stored["statistical_review"]["rendered_cells"]], ["4.800", "5", "1"])

    def test_empty_result_steps_are_already_rejected(self):
        for expert, method, _, _ in DOMAINS:
            with self.subTest(expert=expert):
                self._reject(lambda raw, _: raw["expert_report"].update(performed_step_ids=[]),
                             expert=expert, method=method)

    def test_explicit_researcher_or_code_step_ids_are_already_rejected(self):
        for expert, method, _, _ in DOMAINS:
            definition = self.harness.catalog.definition(expert)
            for actor in ("researcher", "code"):
                step = next(step for step in definition["procedure"] if step["actor"] == actor)
                with self.subTest(expert=expert, actor=actor):
                    self._reject(lambda raw, _, sid=step["id"]:
                                 raw["expert_report"].update(performed_step_ids=[sid]),
                                 expert=expert, method=method)

    def test_qa03_causal_unread_and_unadjusted_conclusions_remain_unreviewed(self):
        texts = (
            "The observed correlation proves duration causes characters.",
            "These supplied rows prove the same association in every omitted row and unread source.",
            "The unadjusted significant pair establishes a confirmed finding across all tested pairs.",
        )
        for text in texts:
            with self.subTest(conclusion=text):
                def semantic_claim(raw, _):
                    raw["expert_report"]["outputs"]["result_explanation"] = text
                    raw["expert_report"]["outputs"]["quality_record"] = "All semantic checks passed."
                run, task, stored, _ = self._exercise(mutate=semantic_claim)
                # Known prohibited assertions are isolated; all other semantic
                # questions still require a researcher's record.
                self.assertEqual(task["status"], "quarantined")
                self.assertEqual(task["error"], "expert_prohibited_conclusion")
                self.assertEqual(stored["content_status"], "unreviewed")
                self.assertEqual(stored["raw"]["expert_report"]["outputs"]["result_explanation"], text)
                self.assertEqual(stored["raw"]["claims"], [])
                for _ in range(2):
                    self.harness.service.status("synthetic", run["run_id"])
                    reread = self.harness.service.result("synthetic", run["run_id"], task["result_id"])
                    self.assertEqual(reread, stored)

    def test_bounded_explanation_does_not_become_confirmed_interpretation(self):
        def bounded(raw, _):
            raw["expert_report"]["outputs"]["result_explanation"] += " No causal inference; omitted rows unread."
        self._accept("exp-correlation", "pearson", bounded)

    def test_negative_causal_caution_is_accepted_as_human_pending(self):
        def bounded(raw, _):
            raw["expert_report"]["outputs"]["result_explanation"] = "Correlation does not prove duration causes characters."
        _, _, stored, _ = self._accept("exp-correlation", "pearson", bounded)
        self.assertEqual(stored["statistical_review"]["semantic_review"], "undetermined")

    def test_structural_numbers_remain_drafts_in_plan_and_report(self):
        for method in (None, "pearson"):
            for text in ("Compare 2 variables after the researcher chooses the pair.",
                         "1. Select 2 variables after researcher confirmation.\n2. Request 1 method.",
                         "Use at most 2 tests after the researcher approves the plan.",
                         "At most 2 methods may be proposed; see step 2."):
                with self.subTest(method=method, text=text):
                    def structure(raw, _):
                        raw["expert_report"]["outputs"]["analysis_plan"] = text
                    _, _, stored, _ = self._accept("exp-correlation", method, structure)
                    self.assertEqual(stored["raw"]["expert_report"]["outputs"]["analysis_plan"], text)
                    self.assertEqual(stored["statistical_review"]["free_text_status"], "unverified_ai_draft")

    def test_structural_text_does_not_authorize_free_statistical_values(self):
        for text in ("Compare 2 variables; coefficient=-0.125.", "1. p=0.05; N=99.",
                     "Use -2 variables.", "Compare 2.5 variables.", "The mean is 19.5.",
                     "The CI is [-0.9, +1.0]; 100% are confirmed."):
            for method in (None, "pearson"):
                with self.subTest(text=text, method=method):
                    self._reject(lambda raw, _, text=text: raw["expert_report"]["outputs"].update(analysis_plan=text), method=method)

    def test_japanese_structural_integers_keep_original_pending_draft(self):
        for text in ("2つの変数を研究者の選択後に比較する。", "手順 2を研究者と確認する。"):
            for method in (None, "pearson"):
                with self.subTest(text=text, method=method):
                    _, _, stored, _ = self._accept("exp-correlation", method,
                        lambda raw, _, text=text: raw["expert_report"]["outputs"].update(analysis_plan=text))
                    self.assertEqual(stored["raw"]["expert_report"]["outputs"]["analysis_plan"], text)
                    review = stored["statistical_review"]
                    self.assertEqual(review["free_text_status"], "unverified_ai_draft")
                    self.assertEqual(review["researcher_record_status"], "unsupported")
                    self.assertEqual(review["semantic_review"], "undetermined")

    def test_single_quote_caution_and_observed_negative_remain_pending(self):
        for text in (
            "Do not claim 'The observed correlation proves duration causes characters'; researcher review is pending.",
            "No observed correlation proves duration causes characters.",
        ):
            with self.subTest(text=text):
                _, _, stored, _ = self._accept("exp-correlation", "pearson",
                    lambda raw, _, text=text: raw["expert_report"]["outputs"].update(result_explanation=text))
                self.assertEqual(stored["raw"]["expert_report"]["outputs"]["result_explanation"], text)
                self.assertEqual(stored["statistical_review"]["semantic_review"], "undetermined")

    def test_japanese_structure_does_not_allow_result_numbers_or_mixed_values(self):
        for text in (
            "-2つの変数を研究者の選択後に比較する。",
            "2.5つの変数を研究者の選択後に比較する。",
            "手順 +2を研究者と確認する。",
            "2つの変数を研究者の選択後に比較する。r=-0.125; p=0.05; N=99。",
            "手順 2を研究者と確認する。CI=[-0.9, 1.0]; 100%。",
            "平均2であった。", "変数2つが有意だった。",
        ):
            for method in (None, "pearson"):
                with self.subTest(text=text, method=method):
                    self._reject(lambda raw, _, text=text: raw["expert_report"]["outputs"].update(analysis_plan=text), method=method)

    def test_single_quotes_and_local_no_do_not_exempt_other_assertions(self):
        for text in (
            "'The observed correlation proves duration causes characters'.",
            "Do not claim 'The observed correlation proves duration causes characters'; the observed correlation proves duration causes characters.",
            "No observed correlation proves duration causes characters; the observed correlation proves duration causes characters.",
            "There are no missing rows, but the observed correlation proves duration causes characters.",
        ):
            with self.subTest(text=text):
                self._reject(lambda raw, _, text=text: raw["expert_report"]["outputs"].update(result_explanation=text))

    def test_negative_and_quoted_cautions_keep_semantic_review_pending(self):
        for text in (
            "Correlation does not prove causation.",
            "No correlation proves causation.",
            "Correlation cannot prove duration causes characters.",
            "These supplied rows do not prove the same association in every omitted row and unread source.",
            "The unadjusted pair does not establish a confirmed finding across all tested pairs.",
            'Do not claim "The observed correlation proves duration causes characters"; researcher review is pending.',
            'The claim "correlation proves causation" is unsupported; researcher review is pending.',
            "相関は因果を証明していない。",
        ):
            with self.subTest(text=text):
                _, _, stored, _ = self._accept("exp-correlation", "pearson",
                    lambda raw, _, text=text: raw["expert_report"]["outputs"].update(result_explanation=text))
                self.assertEqual(stored["statistical_review"]["semantic_review"], "undetermined")

    def test_unrelated_negation_does_not_hide_prohibited_assertions(self):
        for text in (
            "There are no missing rows; the observed correlation proves duration causes characters.",
            "There are no calculation errors; these supplied rows prove the same association in every omitted row and unread source.",
            "There are no missing rows; the unadjusted significant pair establishes a confirmed finding across all tested pairs.",
            "There are no missing rows, but the observed correlation proves duration causes characters.",
            'No missing rows were observed; "The observed correlation proves duration causes characters".',
            'Do not claim "correlation proves causation"; the observed correlation proves duration causes characters.',
            "Correlation does not prove causation and the observed correlation proves duration causes characters.",
            "The unadjusted pair does not establish a confirmed finding but establishes a confirmed finding elsewhere.",
        ):
            with self.subTest(text=text):
                self._reject(lambda raw, _, text=text: raw["expert_report"]["outputs"].update(result_explanation=text))


class StatisticalNumericRegressions(_AcceptanceFixture, unittest.TestCase):
    def _correlation_change(self, **changes):
        def mutate(raw, packet):
            raw["expert_report"]["outputs"]["result_explanation"] = correlation_text(
                correlation_row(packet), **changes)
        self._reject(mutate)

    def test_wrong_coefficient_with_correct_result_and_row_ids(self):
        self._correlation_change(coefficient=0.125)

    def test_wrong_sign_with_correct_result_and_row_ids(self):
        self._correlation_change(coefficient=-0.97606673)

    def test_wrong_n_with_correct_result_and_row_ids(self):
        self._correlation_change(n=6)

    def test_wrong_missing_count_with_correct_result_and_row_ids(self):
        self._correlation_change(missing=0)

    def test_wrong_p_with_correct_result_and_row_ids(self):
        self._correlation_change(p_value=0.9)

    def test_wrong_variable_pair_with_correct_result_and_row_ids(self):
        self._reject(lambda raw, _: raw["expert_report"]["numeric_bindings"][0].update(variables=["duration_seconds", "token_count"]))

    def test_value_from_another_computed_row_with_correct_result_and_row_ids(self):
        def swap(raw, packet):
            row = correlation_row(packet)
            other = next(row for row in table_rows(packet)
                         if row["variable_a"] == "characters" and row["variable_b"] == "characters_per_minute")
            self.assertNotEqual(row["coefficient"], other["coefficient"])
            binding = raw["expert_report"]["numeric_bindings"][0]
            binding["row_id"] = other["row_id"]
        self._reject(swap)

    def test_uncomputed_row_cannot_borrow_computed_values(self):
        def swap(raw, packet):
            source = correlation_row(packet)
            target = next(row for row in table_rows(packet)
                          if row["variable_a"] == "duration_seconds" and row["variable_b"] == "token_count")
            self.assertIsNone(target["coefficient"])
            self.assertEqual(target["status"], "not_computable")
            set_bindings(raw, packet, target, ("coefficient", "p_value"))
            raw["expert_report"]["numeric_bindings"][0]["value"] = source["coefficient"]
        self._reject(swap)

    def test_ci_absent_from_calculation_cannot_be_invented(self):
        def invent(raw, packet):
            row = correlation_row(packet)
            self.assertFalse(any("confidence" in key or key.startswith("ci_") for key in row))
            raw["expert_report"]["outputs"]["result_explanation"] += " 95% CI=[0.90, 0.99]."
        self._reject(invent)

    def test_adjusted_p_absent_from_calculation_cannot_be_invented(self):
        def invent(raw, packet):
            self.assertEqual(correlation_row(packet)["p_value_adjustment"], "none")
            raw["expert_report"]["outputs"]["result_explanation"] += " Holm-adjusted p=0.001."
        self._reject(invent)

    def test_descriptive_wrong_mean_with_correct_result_and_row_ids(self):
        def wrong(raw, _):
            raw["expert_report"]["outputs"]["result_explanation"] = "overall characters; mean=99.5"
        self._reject(wrong, expert="exp-descriptive-statistics", method="descriptive_statistics")

    def test_group_row_value_cannot_be_presented_as_overall_mean(self):
        def swap(raw, packet):
            group = next(row for row in table_rows(packet)
                         if row["scope"] == "group" and row["group_id"] == "B" and row["variable"] == "characters")
            self.assertEqual(group["mean"], 30.0)
            raw["expert_report"]["numeric_bindings"][0]["row_id"] = group["row_id"]
        self._reject(swap, expert="exp-descriptive-statistics", method="descriptive_statistics")

    def test_group_comparison_wrong_effect_size_with_correct_result_and_row_ids(self):
        def wrong(raw, packet):
            row = next(row for row in table_rows(packet) if row["outcome"] == "characters")
            raw["expert_report"]["outputs"]["result_explanation"] = "eta_squared=0.01"
        self._reject(wrong, expert="exp-group-comparison-statistics", method="anova")


class StatisticalStepRegressions(_AcceptanceFixture, unittest.TestCase):
    def test_empty_plan_steps_are_incomplete_in_each_domain(self):
        for expert, _, _, _ in DOMAINS:
            with self.subTest(expert=expert):
                self._reject(lambda raw, _: raw["expert_report"].update(performed_step_ids=[]),
                             expert=expert, method=None)

    def test_explanation_with_only_plan_step_is_incomplete_in_each_domain(self):
        for expert, method, plan_step, _ in DOMAINS:
            with self.subTest(expert=expert):
                self._reject(lambda raw, _, sid=plan_step:
                             raw["expert_report"].update(performed_step_ids=[sid]),
                             expert=expert, method=method)

    def test_plan_cannot_claim_result_step_before_calculation(self):
        for expert, _, _, report_step in DOMAINS:
            with self.subTest(expert=expert):
                self._reject(lambda raw, _, sid=report_step:
                             raw["expert_report"].update(performed_step_ids=[sid]),
                             expert=expert, method=None)

    def test_allowed_ai_step_does_not_certify_human_or_code_execution(self):
        for expert, method, _, _ in DOMAINS:
            for actor in ("researcher", "code"):
                with self.subTest(expert=expert, claimed_actor=actor):
                    def impersonate(raw, _, actor=actor):
                        raw["expert_report"]["outputs"]["quality_record"] = (
                            "I personally executed the Handler calculation and verified its code."
                            if actor == "code" else
                            "I completed the researcher's independence checks and final interpretation approval.")
                    _, _, stored, _ = self._accept(expert, method, impersonate)
                    review = stored["statistical_review"]
                    self.assertEqual(review["researcher_record_status"], "unsupported")
                    self.assertTrue(review["researcher_steps_pending"])
                    self.assertEqual(review["semantic_review"], "undetermined")
                    self.assertFalse(review["eligible_as_confirmed_evidence"])
                    self.assertEqual(review["code_steps"][0]["status"], "verified_attempt")


class StatisticalBindingBoundaries(_AcceptanceFixture, unittest.TestCase):
    def test_missing_each_of_nine_keys_and_unknown_keys_are_rejected(self):
        for key in NUMERIC_BINDING_FIELDS:
            with self.subTest(missing_key=key):
                self._reject(lambda raw, _, key=key: raw["expert_report"]["numeric_bindings"][0].pop(key))
        for key, value in (("value", 0.1), ("display", "0.100"), ("decimal_places", 3)):
            with self.subTest(unknown_key=key):
                self._reject(lambda raw, _, key=key, value=value: raw["expert_report"]["numeric_bindings"][0].update({key: value}))

    def test_every_cell_address_dimension_is_checked(self):
        replacements = {"result_id": "foreign", "dataset": "tests", "row_id": "invented", "column": "adjusted_p",
                        "variables": ["characters", "duration_seconds"],
                        "target": {"scope": "all_included_initial", "selectors": {"method": "Spearman"}},
                        "dataset_version": "old", "computation_input_hash": "wrong", "rows_hash": "excerpt_hash"}
        for key, value in replacements.items():
            with self.subTest(dimension=key):
                self._reject(lambda raw, _, key=key, value=value: raw["expert_report"]["numeric_bindings"][0].update({key: value}))
        for target in ({"scope": "selected", "selectors": {"method": "Pearson"}},
                       {"scope": "all_included_initial", "selectors": {}},
                       {"scope": "all_included_initial", "selectors": {"method": "Pearson", "extra": "injected"}}):
            with self.subTest(target=target):
                self._reject(lambda raw, _, target=target: raw["expert_report"]["numeric_bindings"][0].update(target=target))

    def test_empty_duplicate_bindings_and_duplicate_steps_are_rejected(self):
        mutations = (lambda report: report.update(numeric_bindings=[]),
                     lambda report: report["numeric_bindings"].append(copy.deepcopy(report["numeric_bindings"][0])),
                     lambda report: report["performed_step_ids"].append(report["performed_step_ids"][0]),
                     lambda report: report["calculation_result_ids"].append(report["calculation_result_ids"][0]))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self._reject(lambda raw, _, mutate=mutate: mutate(raw["expert_report"]))

    def test_absent_ci_and_adjusted_p_columns_cannot_be_bound(self):
        for column in ("ci_low", "ci_high", "adjusted_p_value"):
            with self.subTest(column=column):
                self._reject(lambda raw, _, column=column: raw["expert_report"]["numeric_bindings"][0].update(column=column))

    def test_numeric_prose_in_every_display_field_is_quarantined_without_correction(self):
        paths = (("summary",), ("expert_report", "limitations"), *(("expert_report", "outputs", field) for field in
                 ("analysis_plan", "prerequisite_review", "result_explanation", "quality_record", "limitations")))
        for path in paths:
            with self.subTest(path=path):
                def mutate(raw, _, path=path):
                    target = raw
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = "coefficient=-0.125; n=99"
                self._reject(mutate)

    def test_unprovided_original_row_is_rejected_and_supplied_row_keeps_full_hash(self):
        h = self.harness
        run = h.start()
        task = h.dispatch(run, statistical_fixtures.tool_intent("pearson"))
        fixed = h.service.result("synthetic", run["run_id"], task["result_id"])
        original = fixed["raw"]
        from gurumoji.services.analysis_orchestration_methods import calculation_packet as real_packet
        def bounded(raw, meta, **kwargs):
            packet = real_packet(raw, meta, **kwargs)
            table = packet["datasets"]["correlations"]
            table["rows"] = [correlation_row({"calculations": [packet]})]
            table["omitted_rows"] = table["total_rows"] - 1
            return packet
        h.expert_report = lambda context: self._report(context, None)
        with patch("gurumoji.services.analysis_orchestration_methods.calculation_packet", side_effect=bounded):
            good = h.dispatch(run, statistical_fixtures.fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[task["task_id"]]))
            stored = h.service.result("synthetic", run["run_id"], good["result_id"])
            self.assertEqual(good["status"], "succeeded")
            self.assertEqual(stored["statistical_review"]["rendered_cells"][0]["binding"]["rows_hash"], original["manifest"]["rows_hash"])
            other = next(row for row in original["datasets"]["correlations"]["rows"] if row["row_id"] != correlation_row(h.calls[-1][1]["expert_request"])["row_id"])
            def hidden(raw, packet):
                set_bindings(raw, packet, other, ("coefficient",))
            h.expert_report = lambda context: self._report(context, hidden)
            bad = h.dispatch(run, statistical_fixtures.fixtures.intent("interpretation", expert_id="exp-correlation", question="Hidden cell", dependencies=[task["task_id"]]))
        self.assertEqual(bad["status"], "quarantined")
        self.assertEqual(h.service.result("synthetic", run["run_id"], task["result_id"]), fixed)

    def test_null_cells_preserve_reason_and_partial_calculation_status(self):
        def unavailable(raw, packet):
            row = next(row for row in table_rows(packet) if row["status"] == "not_computable")
            set_bindings(raw, packet, row, ("coefficient", "p_value", "n", "missing"))
        _, _, stored, context = self._accept("exp-correlation", "pearson", unavailable)
        cells = stored["statistical_review"]["rendered_cells"]
        self.assertIsNone(cells[0]["value"])
        self.assertEqual(cells[0]["cell_status"], "not_computable")
        self.assertIn("not_computable", cells[0]["display"])
        self.assertEqual(context["expert_request"]["calculations"][0]["status"], "partial")
        self.assertEqual(stored["statistical_review"]["code_steps"][0]["calculation_statuses"], ["partial"])

    def test_needs_input_and_not_applicable_are_saved_incomplete_and_block_dependencies(self):
        for expert, _, _, _ in DOMAINS:
            for status in ("needs_input", "not_applicable"):
                with self.subTest(expert=expert, status=status):
                    def incomplete(raw, packet, status=status):
                        check = packet["knowledge"]["applicability_checks"][0]["id"]
                        raw["analysis_requests"] = []
                        raw["expert_report"].update(status=status, performed_step_ids=[],
                                                   missing_inputs=[check + ": researcher input is missing"], numeric_bindings=[])
                    run, task, stored, context = self._exercise(expert=expert, method=None, mutate=incomplete)
                    self._validate(stored, context)
                    self.assertEqual(task["status"], "blocked")
                    self.assertEqual(stored["statistical_review"]["ai_status"], status)
                    self.assertFalse(stored["statistical_review"]["ai_complete"])
                    self.assertEqual(stored["content_status"], "unreviewed")
                    intent = statistical_fixtures.tool_intent("pearson")
                    intent["dependencies"] = [task["task_id"]]
                    with self.harness.service._db() as db:
                        saved = self.harness.service._read_run(db, run["run_id"])
                        downstream = self.harness.service._register(db, saved, intent, phase="specialists")
                    self.harness.service._drain_tasks(run["run_id"])
                    state = self.harness.service.status("synthetic", run["run_id"])
                    downstream = next(t for t in state["tasks"] if t["task_id"] == downstream["task_id"])
                    self.assertEqual(downstream["status"], "blocked")
                    self.assertEqual(downstream["error"], "dependency_failed")

    def test_exact_half_even_negative_zero_percent_small_p_and_counts(self):
        cases = (("coefficient", -0.0004, "0.000"), ("coefficient", 1.2345, "1.234"),
                 ("coefficient", 1.2355, "1.236"), ("p_value", 0.000001, "0.0000"),
                 ("percent", 12.345, "12.34%"), ("n", 5, "5"), ("missing", 0, "0"))
        for column, value, expected in cases:
            with self.subTest(column=column, value=value):
                cell = render_statistical_cell({"column": column, "dataset": "correlations"}, {column: value}, {})
                self.assertEqual(cell["display"], expected)
                self.assertEqual(cell["value"], value)
                self.assertFalse(cell["p_zero_display_is_exact_zero"])
        for value in (None, float("nan"), float("inf")):
            cell = render_statistical_cell({"column": "coefficient", "dataset": "correlations"}, {"coefficient": value, "status": "not_computable"}, {})
            self.assertEqual(cell["cell_status"], "not_computable")
            self.assertNotEqual(cell["display"], "0.000")

    def test_not_computed_is_a_verified_attempt_never_a_zero_success(self):
        h = self.harness
        for segment in h.analysis["segments"]:
            if not segment.get("excluded"):
                segment.update(text="constant", characters=8, duration=2, valid_time=True)
        h.analysis["research"].update(statistical_fixtures.build_research_statistics(h.analysis, h.analysis["research"]["linguistics"]))
        run = h.start()
        calc = h.dispatch(run, statistical_fixtures.tool_intent("pearson"))
        result = h.service.result("synthetic", run["run_id"], calc["result_id"])
        self.assertEqual(result["calculation_status"], "not_computed")
        h.expert_report = lambda context: self._report(context, None)
        task = h.dispatch(run, statistical_fixtures.fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[calc["task_id"]]))
        stored = h.service.result("synthetic", run["run_id"], task["result_id"])
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(stored["statistical_review"]["code_steps"][0]["calculation_statuses"], ["not_computed"])
        self.assertIsNone(stored["statistical_review"]["rendered_cells"][0]["value"])
        self.assertNotEqual(stored["statistical_review"]["rendered_cells"][0]["display"], "0.000")
        self.assertEqual(stored["statistical_review"]["status"], "human_pending")

    def test_all_eight_tools_bind_real_cells_with_units_and_registered_denominators(self):
        cases = (("exp-descriptive-statistics", "frequency_statistics", "percent"),
                 ("exp-group-comparison-statistics", "crosstabs", "row_percent"),
                 ("exp-group-comparison-statistics", "chi_square", "effect_size"),
                 ("exp-group-comparison-statistics", "kruskal_wallis", "statistic"),
                 ("exp-correlation", "spearman", "coefficient"))
        for expert, method, column in cases:
            with self.subTest(method=method):
                h = self.harness
                run = h.start(expert)
                calc = h.dispatch(run, statistical_fixtures.tool_intent(method))
                def report(context, column=column):
                    raw = self.original_report(context)
                    packet = context["expert_request"]
                    row = table_rows(packet)[0]
                    set_bindings(raw, packet, row, (column,))
                    return raw
                h.expert_report = report
                task = h.dispatch(run, statistical_fixtures.fixtures.intent("interpretation", expert_id=expert, dependencies=[calc["task_id"]]))
                stored = h.service.result("synthetic", run["run_id"], task["result_id"])
                self.assertEqual(task["status"], "succeeded", task.get("error"))
                cell = stored["statistical_review"]["rendered_cells"][0]
                self.assertEqual(cell["value"], table_rows(h.calls[-1][1]["expert_request"])[0][column])
                self.assertEqual(cell["manifest_context"]["included_count"], 6)
                if method == "frequency_statistics":
                    self.assertEqual(cell["denominators"]["percent"], 6)
                    self.assertEqual(cell["display"], "50.00%")
                elif method == "crosstabs":
                    self.assertEqual(cell["denominators"]["total_percent"], 6)
                    self.assertEqual(cell["denominators"]["row_percent"], 3)
                    self.assertTrue(cell["display"].endswith("%"))
                elif method == "spearman":
                    self.assertIn("unit_a", cell["row_context"])
                    self.assertEqual(cell["row_context"]["p_value_adjustment"], "none")

    def test_source_changed_after_delivery_is_rejected_with_original_reply_preserved(self):
        changes = ("raw_hash", "task_actor", "stale", "dataset_version", "attempt_id", "validation_status")
        h = self.harness
        for change in changes:
            with self.subTest(change=change):
                run = h.start()
                calc = h.dispatch(run, statistical_fixtures.tool_intent("pearson"))
                def reply(context, change=change):
                    raw = self._report(context, None)
                    with h.service._db() as db:
                        row = db.execute("SELECT state_json FROM orchestration_results WHERE result_id=?", (calc["result_id"],)).fetchone()
                        metadata = json.loads(row[0])
                        if change == "task_actor":
                            source = next(t for t in h.service._tasks(db, run["run_id"]) if t["task_id"] == calc["task_id"])
                            source["kind"] = "ai"
                            h.service._write_task(db, source)
                        else:
                            metadata[change] = {"raw_hash": "wrong", "stale": True, "dataset_version": "old",
                                                "attempt_id": "different", "validation_status": "quarantined"}[change]
                            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (json.dumps(metadata), calc["result_id"]))
                    return raw
                h.expert_report = reply
                task = h.dispatch(run, statistical_fixtures.fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[calc["task_id"]]))
                self.assertEqual(task["status"], "quarantined")
                self.assertEqual(task["error"], "statistics_result_mismatch")
                stored = h.service.result("synthetic", run["run_id"], task["result_id"])
                self.assertEqual(stored["raw"]["expert_report"]["status"], "draft")
                self.assertEqual(stored["content_status"], "unreviewed")

    def test_contract_version_or_hash_changed_after_delivery_is_rejected(self):
        h = self.harness
        for key in ("contract_version", "profile_hash", "knowledge_hash"):
            with self.subTest(key=key):
                run = h.start()
                calc = h.dispatch(run, statistical_fixtures.tool_intent("pearson"))
                def reply(context, key=key):
                    raw = self._report(context, None)
                    with h.service._db() as db:
                        task = next(t for t in h.service._tasks(db, run["run_id"]) if t["task_id"] == context["task"]["task_id"])
                        task["expert_agent"][key] = 1 if key == "contract_version" else "old"
                        h.service._write_task(db, task)
                    return raw
                h.expert_report = reply
                task = h.dispatch(run, statistical_fixtures.fixtures.intent("interpretation", expert_id="exp-correlation", dependencies=[calc["task_id"]]))
                self.assertEqual(task["status"], "quarantined")
                self.assertEqual(task["error"], "expert_knowledge_hash_mismatch")

    def test_human_pending_cannot_be_promoted_by_core_or_model_self_approval(self):
        h = self.harness
        run, _, stored, _ = self._accept("exp-correlation", "pearson")
        def core_reply(role, context, *args):
            return statistical_fixtures.fixtures.core(claims=[{"claim_id": "approved", "text": "Confirmed interpretation",
                "kind": "interpretation", "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}])
        h.service.agent_runner = core_reply
        with h.service._db() as db:
            saved = h.service._read_run(db, run["run_id"])
            task = h.service._register(db, saved, {"role": "core", "question": "Promote the statistical draft"}, phase="core", automatic=True)
        h.service._execute(run["run_id"], task["task_id"])
        state = h.service.status("synthetic", run["run_id"])
        core = next(t for t in state["tasks"] if t["task_id"] == task["task_id"])
        self.assertEqual(core["status"], "quarantined")
        self.assertEqual(core["error"], "statistical_human_review_required")
        self.assertEqual(h.service.result("synthetic", run["run_id"], stored["result_id"]), stored)

    def test_model_cannot_supply_researcher_records_or_remove_handler_pending(self):
        for field, value in (("researcher_records", [{"record_id": "fabricated", "approved": True}]),
                             ("human_pending", False), ("semantic_review", "approved")):
            with self.subTest(field=field):
                self._reject(lambda raw, _, field=field, value=value: raw["expert_report"].update({field: value}))

    def test_received_recovery_revalidates_saved_cells_or_quarantines_broken_receipt_without_execution(self):
        from gurumoji.analysis_orchestration import recover_orchestration_runs
        h = self.harness
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                run, task, stored, _ = self._accept("exp-correlation", "pearson")
                with h.service._db() as db:
                    state = next(t for t in h.service._tasks(db, run["run_id"]) if t["task_id"] == task["task_id"])
                    state.update(status="running", validation_status="pending")
                    if corrupt:
                        state["expert_calculation_refs"][0]["raw_hash"] = "broken_receipt"
                    h.service._write_task(db, state)
                    meta = {key: value for key, value in stored.items() if key != "raw"}
                    meta.pop("statistical_review")
                    meta["validation_status"] = "received"
                    db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (json.dumps(meta), task["result_id"]))
                    recover_orchestration_runs(db)
                before_calls = len(h.calls)
                with patch.object(h.service, "method_runner") as computation, patch.object(h.service, "agent_runner") as model:
                    h.service._validate_received(run["run_id"], task["task_id"])
                    h.service._validate_received(run["run_id"], task["task_id"])
                    computation.assert_not_called()
                    model.assert_not_called()
                reread = h.service.result("synthetic", run["run_id"], task["result_id"])
                self.assertEqual(reread["raw"], stored["raw"])
                self.assertEqual(reread["raw_hash"], stored["raw_hash"])
                self.assertEqual(reread["validation_status"], "quarantined" if corrupt else "valid")
                self.assertEqual(reread["content_status"], "unreviewed")
                if not corrupt:
                    self.assertEqual(reread["statistical_review"], stored["statistical_review"])
                self.assertEqual(len(h.calls), before_calls)


if __name__ == "__main__":
    unittest.main()
