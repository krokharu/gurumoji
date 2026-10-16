---
note_id: design-core-handler-routing-reorganization
note_type: section-index
title: コア・ハンドラー・ルーティング再編案
summary: 冒頭で着手範囲・作業手順・完了条件を定め、分析UI、追加分析の入力・保存・再開、LLMの手法別契約と知識固定を段階的な再編へ結ぶ。
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
content_updated: '2026-10-11'
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_path: 40-Design/core-handler-routing-reorganization-plan.md
---

# コア・ハンドラー・ルーティング再編案

冒頭で着手範囲・作業手順・完了条件を定め、分析UI、追加分析の入力・保存・再開、LLMの手法別契約と知識固定を段階的な再編へ結ぶ。

状態は元資料の `complete` を引き継ぐ。改装日は内容の再検証日ではない。

## 必要な論点だけ読む

- [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/00-Index|コア・ハンドラー・ルーティング再編案 ～ 図5：LLM・Transformer・Jevのカラム生成から統計分析へ]] — 8論点の入口
- [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/00-Index|図6：LLM分析専用オーケストレーターと、相談で作る手法別の型 ～ 現行ER図（SQLite）]] — 8論点の入口
- [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/00-Index|現行ER図（成果物・Obsidianを含む概念関係） ～ 段階的な移行プラン]] — 8論点の入口
- [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/00-Index|移行時の必須確認 ～ 採用判断]] — 3論点の入口
