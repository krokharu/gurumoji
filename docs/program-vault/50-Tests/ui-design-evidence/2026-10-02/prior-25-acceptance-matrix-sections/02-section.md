---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prior-25-acceptance-matrix-section-02
title: 25件の独立受入対応表（クラウド時点）：表：A06
summary: 表：A06。出典ノート「25件の独立受入対応表（クラウド時点）」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prior-25-acceptance-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/prior-25-acceptance-matrix.md
source_sha256: 831c67d4cd8918fa7a02ac8e46b3786b6b645dddb3f50446b3b809c5ce0cc4e0
source_body_lines:
- 23
- 32
split_on: '2026-10-11'
---

# 25件の独立受入対応表（クラウド時点）：表：A06

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prior-25-acceptance-matrix]]。必要な本文だけを取得する。

| ID | 指摘 | 受入基準 | 判定 | 根拠・残る確認 |
|---|---|---|---|---|
| A06 | Chronological physical metrics | Stored late10–12/unknown/early0–11 yields overlap10–11=1s and no gap, invariant under input permutation while original IDs/order stay intact. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A07 | Explicit participation denominator | Known participant count3 but one observed speaker: actual count vs observed count separated; balance labeled observed-speaker scope unless confirmed roster supports zero rows; UNKNOWN separately disclosed. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A08 | Consistent exact term matching | education/cat/dog: normalized cat crosstab agrees with KWIC e2 only; substring mode, if supported, explicit; target segment IDs inspectable. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A09 | Complete DF denominator | A cats/stopword-only yields document_count2 and cat50%; blank/excluded/stopword scopes defined and align characteristic comparison. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A10 | Split interval seconds | 50–80s +90–100s at60s bins yields10s/30s, counts by start only; total seconds preserved and20s session does not extend to300s. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Synthetic vectors/tokenizer/model only; real model quality not empirically validated; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A11 | Measured token truncation | 1200 chars under6000 but above512 tokens reports token truncation and IDs/ranges/context; own text lost after context detected. Unmeasurable injected vectors remain unknown, not zero. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Synthetic vectors/tokenizer/model only; real model quality not empirically validated; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A12 | Pinned embedding model revision | Cached old-revision utterances require old-revision descriptors; mismatched new-revision rejects. Legacy unknown revision warns/recomputes; same dimensions insufficient. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Synthetic vectors/tokenizer/model only; real model quality not empirically validated; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A13 | Enforced fixed topic count | 6 vectors with2 unique values requested3 must not report success; invalid candidate has actual2 and no valid silhouette; fixed2 can succeed. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Synthetic vectors/tokenizer/model only; real model quality not empirically validated; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A14 | Preserve tiny p-values | Repeated A=[1,2,3],B=[3,4,5] gives nonzero~3.83986e-13 in JSON/CSV; UI scientific/threshold rendering not0. Disclose utterance pseudoreplication and multiplicity. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| V01 | Same-second Vault registry recovery | Freeze note time; remove ledger, republish byte-identical notes: restore metadata/hash/status without note rewrite/history/log mutation; edited note archived first; archive failure safe; deletion still protected. | addressed | vault-independent-tests.log: 33 passed with fixed timestamp; source review: registry finalization independent of writer callback; Final broad suite includes Vault; source hash stable |
