---
title: "Visualization acceptance v1: isolated Web baseline plan"
status: proposed
version: 1.0
evaluation_version: 1
research_approved: false
measurement_status: unmeasured
source_plan: "PLAN-R5 §13 / P13"
source_plan_sha256: "821f86ef155c48f876cc4a04ac7b0059ca24abfaa5f0dd7895d62456a2867693"
source_blueprint: "Blueprint §19"
source_blueprint_sha256: "40380edce6f39105c83e07d97a0a8b05a15557ffcb29ef2f21dfe3d196eba7b5"
---

# Visualization acceptance v1: isolated Web baseline plan

## Purpose and status

The source-of-truth plan is PLAN-R5 §13, raw SHA-256 `821f86ef155c48f876cc4a04ac7b0059ca24abfaa5f0dd7895d62456a2867693`; the related blueprint is §19, raw SHA-256 `40380edce6f39105c83e07d97a0a8b05a15557ffcb29ef2f21dfe3d196eba7b5`. Their version and contents are unchanged. The plan distinguishes V01 documentation / scope freeze from the later isolated Web baseline and independent review.

## Frozen evaluation universe and acceptance rules

Freeze `evaluation_version: 1` before any UI measurement. The unit is one predeclared display slot per method × scope × output slot. Do not count chart variants, cards, colors, candidate counts, or multiple representations of a slot as extra units. Do not remove unavailable, failed, unmeasured, or inconvenient slots after seeing results. An applicability exception requires a preregistered reason; changing the universe or its applicability requires a new evaluation version and a documented rationale before measurement.

- Readability denominator: all six planned slots, when all six are applicable (`n=6`). Target at least 80%; the passing integer count is `ceil(0.80 × 6) = 5/6` (83.3%).
- Chart-appropriateness denominator: the four chart-planned slots A02–A05 (`n=4`). Target at least 70%; the passing integer count is `ceil(0.70 × 4) = 3/4` (75%). A01 and A06 are table/card and comparison displays respectively, and are not silently added to this chart denominator.
- Operational requirements VIZ-07 and VIZ-08 are separately mandatory, each 100% across all applicable checks. The full synthetic VIZ-01?08 target is 8/8, separate from the 6/4 analysis rates. They do not enter readability or chart-appropriateness rates because they assess dependency and coverage/receipt integrity, not whether a user can read an analysis display.
- Report the numerator, denominator, applicable count, exclusions with preregistered reasons, and each failure / unavailable / unmeasured state. Never convert missing, unsupported, failed, or unrun output to zero or pass.

## Frozen synthetic slot matrix

All fixture group names and IDs below are invented `TEST-V01-*` identifiers, not user or research data. C0 / the isolated-baseline implementer must freeze the actual fixture and source hashes and record the actual fixed run and artifact IDs before browser measurement. The `pending` hash fields are intentionally not fabricated. The prepared baseline record must include for every slot: `method_id`, scope, `output_slot_id`, applicability and reason, chart appropriateness, expected data and root table/dataset, fixed run, input and artifact table, claim-to-source hash references, evidence IDs, normal and isolated negative conditions, and actual readability / chart result. Actual scores stay null until observed.

| Slot | Planned method / scope / output slot | Expected display and data roots | Synthetic evidence and claim reference (planned IDs; hashes pending freeze) | Applicability / chart | Actual result |
| --- | --- | --- | --- | --- | --- |
| A01 | `qualitative_coding` / `overall` / `TEST-V01-A01-theme-support-counter` | Theme candidate and support/counter-evidence count table plus cards; roots: invented theme rows, supporting and counter utterance references, and the fixed qualitative report / coverage table | Run `TEST-V01-RUN-A01`; input `TEST-V01-IN-A01`; artifact table `TEST-V01-TABLE-A01`; claims `TEST-V01-CLAIM-A01-*`; evidence `TEST-V01-UTT-A01-*`; source and fixture SHA-256: pending Sol freeze | Applicable in synthetic fixture; chart-appropriate: no, table/cards | readability `null`; chart `null`; unmeasured |
| A02 | `participation` / `overall` / `TEST-V01-A02-participation-time` | Participation bar and timeline; roots: speaker/group counts, utterance-time bins, fixed denominator and coverage | Run `TEST-V01-RUN-A02`; input `TEST-V01-IN-A02`; artifact table `TEST-V01-TABLE-A02`; claims `TEST-V01-CLAIM-A02-*`; evidence `TEST-V01-UTT-A02-*`; source and fixture SHA-256: pending Sol freeze | Applicable in synthetic fixture; chart-appropriate: yes | readability `null`; chart `null`; unmeasured |
| A03 | `descriptive_statistics` / `overall` / `TEST-V01-A03-distribution-summary` | Descriptive distribution plus numeric summary table; roots: fixed variable, observations, units, missing/excluded counts, and verified summary rows | Run `TEST-V01-RUN-A03`; input `TEST-V01-IN-A03`; artifact table `TEST-V01-TABLE-A03`; claims `TEST-V01-CLAIM-A03-*`; evidence `TEST-V01-ROW-A03-*`; source and fixture SHA-256: pending Sol freeze | Applicable in synthetic fixture; chart-appropriate: yes | readability `null`; chart `null`; unmeasured |
| A04 | `correlation` / `overall` / `TEST-V01-A04-correlation-matrix` | Correlation heatmap and coefficient cells; roots: verified correlation rows with variables, coefficient, sample size, missingness, status and source row IDs | Run `TEST-V01-RUN-A04`; input `TEST-V01-IN-A04`; artifact table `TEST-V01-TABLE-A04`; claims `TEST-V01-CLAIM-A04-*`; evidence `TEST-V01-ROW-A04-*`; source and fixture SHA-256: pending Sol freeze | Applicable in synthetic fixture; chart-appropriate: yes | readability `null`; chart `null`; unmeasured |
| A05 | `group_statistics` / `overall` / `TEST-V01-A05-crosstab` | Crosstab stacked bar with frequency/proportion table; roots: fixed row/column categories, counts, denominator, missing category, and calculation rows | Run `TEST-V01-RUN-A05`; input `TEST-V01-IN-A05`; artifact table `TEST-V01-TABLE-A05`; claims `TEST-V01-CLAIM-A05-*`; evidence `TEST-V01-ROW-A05-*`; source and fixture SHA-256: pending Sol freeze | Applicable in synthetic fixture; chart-appropriate: yes | readability `null`; chart `null`; unmeasured |
| A06 | `interview_comparison` / `comparison` / `TEST-V01-A06-comparison` | Comparison parallel/difference display; roots: fixed comparison run, aligned dimensions, units, denominators, and per-group result rows | Run `TEST-V01-RUN-A06`; input `TEST-V01-IN-A06`; artifact table `TEST-V01-TABLE-A06`; claims `TEST-V01-CLAIM-A06-*`; evidence `TEST-V01-ROW-A06-*`; source and fixture SHA-256: pending Sol freeze | Applicable in synthetic fixture; chart-appropriate: no, comparison display | readability `null`; chart `null`; unmeasured |

## Mapping to PLAN-R5 VIZ-01–08

| Plan item | v1 treatment | Rate treatment |
| --- | --- | --- |
| VIZ-01 themes and support/counter evidence | A01 covers the table/cards, evidence relation, and coverage root. | Readability denominator includes A01; chart denominator excludes it. |
| VIZ-02 participation / utterance timeline | A02 covers count and time views with fixed scope and denominator. | Included in both denominators. |
| VIZ-03 descriptive summary | A03 covers distribution and summary with units, exclusions, and exact numeric rows. | Included in both denominators. |
| VIZ-04 correlation | A04 covers coefficient cells, sample size, missingness, and the non-causal interpretation boundary. | Included in both denominators. |
| VIZ-05 crosstab / group summary | A05 covers categories, count and proportion, denominator, and zero-category semantics. | Included in both denominators. |
| VIZ-06 comparison | A06 covers the fixed comparison run, aligned units, and reasoned “not comparable” state where appropriate. | Readability denominator includes A06; chart denominator excludes it. |
| VIZ-07 analysis dependency map | Mandatory synthetic operational checks verify dependency bindings, fixed result identity, and meaning links; retain missing, stale, failed, and waiting states distinctly. | Mandatory operational item; full synthetic VIZ-01?08 target 8/8, separate from analysis rates. |
| VIZ-08 result coverage / delivery map | Mandatory synthetic operational checks cover target, request, result, delivered/received receipt, and progress without collapsing duplicate delivery or claiming completion from a partial receipt. | Mandatory operational item; full synthetic VIZ-01?08 target 8/8, separate from analysis rates. |

## Required state and evidence semantics

Freeze the method-question applicability and actual denominators for the later real-model trial before measuring that trial. The current M source count of 323 is fixed context only: its model, output, and run are unavailable here, so its rate is unmeasured. Do not force correlation or quantitative methods into the real-M denominator, and do not reuse the synthetic `6` / `4` denominators as real-M rates.

For the real-M report, keep mandatory theme/support-counter/report coverage, result coverage, and dependency coverage as separate measures; report the relevant applicable mandatory slots at a 100% target. Keep that report distinct from the synthetic UI readability and chart-appropriateness scores. The source method registry currently identifies version `text-analysis-store-12`; this is a source observation, not a promise that all planned methods have a compatible saved output or renderer.

Use explicit state values such as `not_applicable` with reason, `unsupported`, `missing`, `stale`, `failed` with reason, `waiting`, `not_run`, and `unmeasured`. Numeric zero is a measured value only when the fixed source data actually contains zero. An output that is not computed or unavailable must not be displayed as zero. Preserve old results when a new request fails. Unsupported states are visible and count as failures for applicable acceptance slots unless a preregistered applicability reason excludes that slot.

For each slot, bind claims and displayed values to fixed source rows or utterance IDs and their frozen hashes. Evidence controls must open the exact utterance / row from the selected fixed artifact, then return to the same run and view state. Keep AI candidates, source evidence, and researcher-adopted interpretation distinct. A rendered view, link, JSON response, or download by itself does not establish evidence traceability or readability.

## Later isolated browser measurement protocol

Separate Sol task (<=0.5 h): run the isolated UI baseline; independent Sol review is required. This plan is not a UI pass. Use `tests/test_qualitative_visualization.py` and `tests/browser_support.py` after confirming environment/browser. Viewports: 1360x900 and 390x844; if configured to 1440x900, record it.

Measure each fixed slot at desktop and mobile. Check keyboard access, text alternatives, evidence-to-row/utterance navigation and return, focus/scroll restoration, filters, old-result retention after request failure, missing/zero distinction, and explicit unsupported states. Record exact app/source version, fixed run and artifact IDs, input/fixture/source SHA-256, evidence IDs, viewport, screenshot/evidence IDs, command and outcome. Preserve each error and reason independently from an app-defect judgment. Do not infer UI success from imports, CPU behavior, endpoint response alone, or a synthetic contract result.

## Ownership and change control

Author status: proposed / draft. Research approval: not requested or granted. UI baseline status: planned / unmeasured. Independent review status: pending.

If applicability, slot definition, unit, target, or denominator changes after evaluation starts, preserve this v1 definition and create a new evaluation version before collecting results. Record what changed, why, and which prior measurements are no longer comparable. Never retroactively redefine a failed or unmeasured slot out of the denominator.
