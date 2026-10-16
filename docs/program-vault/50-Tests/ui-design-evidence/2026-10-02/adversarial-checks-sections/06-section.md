---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks-section-06
title: 'Gurumoji デザイン監査の独立反証チェック：第6巡: 固定viewer提案と既存helperの境界（19:28–19:30 UTC）'
summary: '第6巡: 固定viewer提案と既存helperの境界（19:28–19:30 UTC）。出典ノート「Gurumoji デザイン監査の独立反証チェック」の分割本文。'
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks
source_path: 50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md
source_sha256: fec531750b3b1eeb8616de26b52688a81b740a197d67d9f5682156883db2fd50
source_body_lines:
- 238
- 248
split_on: '2026-10-11'
---

# Gurumoji デザイン監査の独立反証チェック：第6巡: 固定viewer提案と既存helperの境界（19:28–19:30 UTC）

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/adversarial-checks]]。必要な本文だけを取得する。

## 第6巡: 固定viewer提案と既存helperの境界（19:28–19:30 UTC）

第2稿W02保存／rollback、W04固定viewer最小契約を静的照合。提案を未実装と明記し、artifact再利用・任意run lookup案・route/history拡張・旧binaryguardを分けた点は現コードと整合した。新しいprobeは作っていない。

W04へ次の補足を要求:

- `AnalysisStore.read_artifact:304–312`のDB sha256照合は**保存時bytesとの整合性**を検証する。「真正性」という語で発信者の真正性・攻撃者に対する保証まで含めない
- `evidenceDetails:45–73`は欠落引用IDを`:58`でskipし、欠測時刻を`:62`で0へ寄せる。新viewerが要求する「引用欠落を明示」「欠測時刻を0秒としない」は既存factory無変更では満たさない
- `openInsightMedia:86–90`は数値差を比較するがNaN/欠測を明示拒否しない。固定viewerの原音guardは、保存時／現在の双方の時刻が有限かつvalidであることを先に確かめる必要がある。text/speaker/time一致、target ID、run文脈はadapterで明示し、既存live-state依存をそのまま持ち込まない

これは固定viewerの設計依存の指摘であり、現行GUIで誤seekや欠落表示を実観測した記録ではない。既存artifact payloadとAPIのfield位置は `services/analysis_archive.py:60–103`、`analysis_store.py:315–321,400–423` に照合済み。
