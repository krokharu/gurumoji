---
note_id: program-ai-entry
note_type: ai-entry
title: AI向けタスク別入口
summary: AIが変更対象に応じて必要最小限のSoftware Vaultノートとコードへ進むための入口。
status: current
updated: 2026-09-20
feature: development-workflow
tags:
  - gurumoji/program
  - gurumoji/ai
---

# AI向けタスク別入口

これは探索の入口であり、実装の正本ではない。まず依頼を分類し、この表の最も近い入口ノートと対象コードだけを読む。`00-Home`、`00-Index`、Vault全体、リポジトリ全体を初手で通読しない。

| 依頼の種類 | 最初に読むノート | 次に読むもの |
| --- | --- | --- |
| Vault構造、同期、移行、ノート所有権、生成物の保存 | [[20-Modules/obsidian-integration]] | [[30-Data/four-vaults-v1]]、対象モジュール、適用時は `gurumoji-obsidian-memory` の参照資料 |
| 分析手法、専門家定義、AIプロンプトの制約 | [[50-Analysis-Methods/00-Index]] | [[40-Design/method-rules]]、対象の手法ノートと実装 |
| 構成、設定、起動経路、保存先 | [[10-Architecture/system-map]] | 対象モジュールと設定 |
| 個別モジュール、API、UI | [[20-Modules/module-map]] | 対象コードと隣接テスト。画面導線は [[20-Modules/ui-screens]] |
| 現在の課題、優先度、予定作業 | [[40-Design/known-issues]] | [[40-Design/convergence-plan]]、対象コード |
| 文書だけの修正 | [[00-Index]] | 対象ノートだけ |

入口で対象を絞れない場合にだけ `.claude/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py` を使い、返された候補のfrontmatterと必要な抜粋だけを読む。テンプレート、アーカイブ、実行時Vaultは依頼に必要な場合だけ扱う。

変更が保存形式、競合処理、同期または移行に及ぶときは、[[40-Design/ai-development-rules]] と該当する契約資料を追加で読む。現行コードと設定を最終的な正本とし、ノートとの食い違いは上位の指示に従って明示する。
