---
note_id: design-model-context-and-work-memory
note_type: section-index
title: モデル別コンテキスト管理と作業記録の保存計画
summary: ローカルモデルの実入力予算、段階別契約、全発話の分割、専門知識の選択とDB来歴を試験導入。実モデルの全体分析と役割別品質評価は継続中。
status: in_progress
updated: 2026-10-06
feature: analysis-orchestration
tags:
- gurumoji/program
- gurumoji/plan
- gurumoji/ai
- gurumoji/storage
content_updated: '2026-10-11'
source_sha256: 5deb802e628cb0041fcc9fb6b42ddf5ac43615a40641f4aa9d09e449c34d9323
source_path: 40-Design/model-context-and-work-memory-plan.md
---

# モデル別コンテキスト管理と作業記録の保存計画

ローカルモデルの実入力予算、段階別契約、全発話の分割、専門知識の選択とDB来歴を試験導入。実モデルの全体分析と役割別品質評価は継続中。

状態は元資料の `in_progress` を引き継ぐ。改装日は内容の再検証日ではない。

## 必要な論点だけ読む

- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/01-section|モデル別コンテキスト管理と作業記録の保存計画]] — 本文 1,968字
- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/02-section|参考事例と採用する考え方]] — 本文 1,723字
- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/03-section|入力をトークンで予算化する]] — 本文 1,682字
- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/04-section|初期分析と反復の進め方]] — 本文 2,312字
- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/05-section|実装の順序と完了条件]] — 本文 1,924字
- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/06-section|計画作成時の記録（実装前）]] — 本文 1,876字
- [[40-Design/20-Knowledge/model-context-and-work-memory-plan/07-section|2026-10-06 Coreへの依存を減らす修正]] — 本文 1,274字
