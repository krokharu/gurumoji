---
note_type: reference-section
status: current
feature: project-status
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/issues
note_id: design-known-issues-section-06
title: 既知の問題点と改善方法（収束フェーズ）：DOC：ドキュメント
summary: DOC：ドキュメント。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 102
- 123
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：DOC：ドキュメント

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## DOC：ドキュメント

| ID | 重要度 | 問題 | 根拠 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-01 | 中 | 同じ説明を別々の場所で管理している | `README.md`（約53KB）、`docs/*.md`（利用者向けの手順）、このVault（仕様） | 役割を決める。READMEは導入の入口、`docs/` は操作手順、Vaultは仕様・設計・問題点。同じ説明は書かずにリンクする | 未対応 | 統合 → DATA-02 |
| DOC-02 | 低中 | 一部が実装済みなのに `proposed` のままのノートがある | [[40-Design/40-Storage/storage-policy\|storage-policy]]、[[40-Design/40-Storage/sync-contract\|sync-contract]]（提案API `/api/obsidian/settings` などは未実装） | 実装済みの部分を `30-Data` へ移し、提案部分だけを残す | 未対応 | 統合 → DATA-02 |
| DOC-03 | 中 | AI向けの開発ルールがリポジトリにない | `AGENTS.md`・`CONTRIBUTING.md` がない | 2026-09-16にルート `AGENTS.md` を追加し、日常作業用の短い優先順位・探索・検証ルールを置いた。詳細は [[40-Design/50-Governance/ai-development-rules\|ai-development-rules]] に分離した | 対応済み（最新版`2f13f98`に収録） | 今回のAI運用ルール監査で対応 |

## DEV：開発時の残骸

| ID | 重要度 | 問題 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- |
| DEV-01 | 低 | `runtime/` 直下に由来が分からないファイルと検証出力がある（[[20-Modules/10-Inventory/feature-inventory/00-Index\|feature-inventory]] の「Unknown」） | 削除しない。利用者に確認してから、`runtime/archive` へ移すなどで整理する。検証スクリプトの出力先は `runtime/logs` などに決める | 未対応 | 保留：由来不明。データ削除・移動の対象外 |

## UI：画面の収束（詳細は [[40-Design/30-Interface/ui-ux-issues/00-Index|ui-ux-issues]]）

| ID | 重要度 | 問題 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- |
| UI-01 | 中 | Obsidian関連の入口が5か所に分かれている：新規作成のチェック、結果画面「Obsidianで仕上げ」、議事録パネル「Obsidianに保存」、分析「分析結果をObsidianに保存」、比較「比較結果を保存」 | 「保存・Obsidian」の操作を、会話ごとの1パネル（状態表示と操作）に集約する | 未対応 | 保留：異なる保存対象の一律集約案は不採用 |
| UI-02 | 中 | 「保存」の意味が複数ある：編集内容の保存、話者管理の保存、分析設定の保存、分析の固定保存、Obsidianへの保存 | ボタン名を「編集を保存」「分析条件を保存」「結果を記録（固定）」のように対象で区別する | 未対応 | 統合 → UX-04 |
| UI-03 | 中 | 移動の導線が重複し、URLにも反映されない（UX-01〜03） | [[40-Design/30-Interface/ui-ux-issues/00-Index\|ui-ux-issues]] の推奨順に従う | 対応済み（UX-01／UX-03、UI再設計を最新版`2f13f98`に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]） | 統合 → UX-01／UX-03 |
