---
note_type: reference-section
status: proposed
updated: 2026-09-25
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/rules
note_id: design-analysis-method-rules-section-04
title: 分析手法ごとのObsidian登録規約：将来手法を保存する場合の追加項目
summary: 将来手法を保存する場合の追加項目。出典ノート「分析手法ごとのObsidian登録規約」の分割本文。
parent_note_id: design-analysis-method-rules
source_path: 40-Design/method-rules.md
source_sha256: b12c64c4bba7906a0e26cb253b7c8e6d2b1eca2ff8b8342118d27ab8c2cdc9a4
source_body_lines:
- 113
- 125
split_on: '2026-10-11'
---

# 分析手法ごとのObsidian登録規約：将来手法を保存する場合の追加項目

親索引・状態・確認版：[[40-Design/50-Governance/method-rules/00-Index]]。必要な本文だけを取得する。

## 将来手法を保存する場合の追加項目

以下は登録形式を用意する候補であり、現在このプログラムが計算する機能ではない。

| 候補 | 追加して保持するもの |
| --- | --- |
| テーマ分析・SCAT等の質的分析 | 採用した方法の版・工程、概念化前後の記述、理論記述、研究者、反例、原文への対応 |
| 複数会話の比較 | 会話IDと入力版の集合、包含基準、分析単位、比較条件。1会話の結果と混在させない |
| 外部R／Python等の統計結果 | スクリプト識別値、環境、入力hash、結果表、未確認の再現条件。再計算済みと表示しない |

外部結果を元の入力版に結び付けられない場合は `unverified` として保管し、現行の分析結果や確定した根拠として扱わない。

関連：[[40-Design/40-Storage/storage-policy|storage-policy]]、[[40-Design/40-Storage/sync-contract|sync-contract]]、[[90-Templates/10-Analysis/research-result|research-result]]。
