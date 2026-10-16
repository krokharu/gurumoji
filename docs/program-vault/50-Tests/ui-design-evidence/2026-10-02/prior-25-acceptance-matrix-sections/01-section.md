---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prior-25-acceptance-matrix-section-01
title: 25件の独立受入対応表（クラウド時点）：25件の独立受入対応表（クラウド時点）
summary: 25件の独立受入対応表（クラウド時点）。出典ノート「25件の独立受入対応表（クラウド時点）」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prior-25-acceptance-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/prior-25-acceptance-matrix.md
source_sha256: 831c67d4cd8918fa7a02ac8e46b3786b6b645dddb3f50446b3b809c5ce0cc4e0
source_body_lines:
- 1
- 22
split_on: '2026-10-11'
---

# 25件の独立受入対応表（クラウド時点）：25件の独立受入対応表（クラウド時点）

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prior-25-acceptance-matrix]]。必要な本文だけを取得する。


# 25件の独立受入対応表（クラウド時点）

15 addressed / 10 partial / 0 open。UIのpartialは実Windowsブラウザー受入待ち。実装不在を意味しない。科学的妥当性・実モデル精度を合格と断定しない。

| ID | 指摘 | 受入基準 | 判定 | 根拠・残る確認 |
|---|---|---|---|---|
| UI-01 | Keyboard edit entry | No-media two-segment saved/reloaded fixture; Tab/Enter opens second utterance, changes text/time, saves. Media-backed edit does not autoplay. Desktop and 390px. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-02 | Readiness prerequisites | No HF, failed config, uncached model, valid config: never claim runnable while required state missing/unconfirmed; reason and correction entry visible. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-03 | Complete transmission summary | LM Studio + full finishing + TypeSafe configured: comparison requires explicit choice; all enabled text destinations listed. OFF/AI-none/recommended/Obsidian combinations match plan. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-04 | Local undo for utterance deletion | Edit first utterance, delete second, undo; preserves first edit and every deleted attribute/ID, restores focus. Repeated deletion/undo and saved reload boundary safe. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-05 | Visible deletion failure | Result view DELETE 409/500/network failure: visible live error, original data/media retained, duplicate request blocked; retry success alone navigates/updates list. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-06 | Preserve manual configuration | Delayed config/profile and later config refresh cannot overwrite manually selected model/devices; explicit reset alone applies recommendations. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-07 | CSV preview and explicit apply | Duplicate participant code and unknown question column: preview counts/mapping before persistence; cancel leaves persisted state unchanged; confirm matches preview. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-08 | Conflict draft export | Two revisions/tabs: 409 preserves draft; download is unsaved client data, includes provenance/revision; no server overwrite; latest reload can be compared. Both transcript and speakers. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md |
| UI-09 | Environment-accurate location copy | Linux cloud/Windows/Colab fixture: paths and save/upload distinction correct; no implication cloud save is device download. Obsidian server-only caveat and alternative. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md; Actual Obsidian destination reachability not verified |
| UI-10 | Accessible save feedback | Save success/conflict/warning have appropriate live roles; tabpanels reference actual tab IDs; no repeated whole-page announcement. | partial | Implementation complete; source review plus API/template/Node contracts passed; Actual Windows browser acceptance pending; see windows-browser-acceptance.md; Actual screen-reader speech not verified |
| A01 | Complete exports | 250 distinct words yield 250 ordinary JSON/CSV/XLSX term rows, 100% summed TF rate within tolerance. UI preview may cap at 200. Cooccurrence internal cap disclosed with total/export count and limit reason. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A02 | Conservative speaker-result claims | Original negation/hearsay five phrases produce no affirmative self-change/support result. Positive controls remain candidate; negation/question/conditional/quote handled conservatively. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Synthetic vectors/tokenizer/model only; real model quality not empirically validated; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A03 | Respect explicit roles | Explicit participant 60/20/20 remains in results/backchannel population; only confirmed moderator excluded. Inferred suggestion separate from explicit role. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Synthetic vectors/tokenizer/model only; real model quality not empirically validated; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A04 | Configuration-sensitive staleness | Changing bin/theme/label stop words changes result fingerprint and marks stored result stale in display/search/export; compatible embedding reuse remains separate. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
| A05 | Generated-input export provenance | Old revision1/new revision2+hash: CSV/XLSX old rows keep old source identity and stale=true. Legacy provenance unknown is labeled, never borrowed from current preparation. | addressed | 17 independent acceptance tests across theme/metrics/staleness/export; see individual test logs; Final independent acceptance:17 passed; broad864 passed,2 browser blocked,10 skipped,24 deselected; source hash stable |
