---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/ui
- gurumoji/orchestrator
note_id: analysis-execution-ux-plan-section-06
title: 分析実行UX統合・段階分析設計：12. 初期実装の範囲
summary: 12. 初期実装の範囲。出典ノート「分析実行UX統合・段階分析設計」の分割本文。
parent_note_id: analysis-execution-ux-plan
source_path: 40-Design/analysis-execution-ux-plan.md
source_sha256: 1bc504e638f40bdced00fbee6a2763e8bffc51f74a85ded0fd11d17cdacf2d93
source_body_lines:
- 332
- 338
split_on: '2026-10-11'
---

# 分析実行UX統合・段階分析設計：12. 初期実装の範囲

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-execution-ux-plan/00-Index]]。必要な本文だけを取得する。

## 12. 初期実装の範囲

最初の実装単位は Phase 1〜2 とする。対象は単一インタビューの既存4処理（基礎再集計、Transformer、発話分類、AI見解）に限定し、共通実行パネルと実行中画面へ接続する。

永続pipeline、後続分析DAG、疑似人格の相談、常時監視による自動再実行、複数会話をまたぐ一括実行は同時に実装しない。Phase 1〜2で操作モデルを検証してから、Phase 3以降の保存契約を版付きで追加する。

関連：[[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]、[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]、[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]、[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]、[[40-Design/50-Governance/decisions/02-topics/09-section#ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする|ADR-111]]、[[40-Design/50-Governance/decisions/02-topics/14-section#ADR-118 分析UIを、結果閲覧・比較・計画・データ出力の作業単位へ整理する|ADR-118]]
