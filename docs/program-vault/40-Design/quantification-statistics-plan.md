---
note_id: design-quantification-statistics-plan-legacy-path
note_type: path-redirect
title: 発話の数値化とjamovi型統計の自動実行計画（移動先案内）
summary: 本文と同じnote_idは移動先に保持。通常検索は移動先を使用する。
status: deprecated
updated: '2026-10-11'
redirect_to: 40-Design/10-Analysis/quantification-statistics-plan/00-Index.md
tags:
- gurumoji/redirect
---

# 発話の数値化とjamovi型統計の自動実行計画

本文：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index|発話の数値化とjamovi型統計の自動実行計画]]。旧パスの互換案内。

## 0. 決定事項

[[40-Design/10-Analysis/quantification-statistics-plan/01-section#0. 決定事項|移動した本文を読む]]

## 1. 要点

[[40-Design/10-Analysis/quantification-statistics-plan/02-section#1. 要点|移動した本文を読む]]

## 2. 現状

[[40-Design/10-Analysis/quantification-statistics-plan/02-section#2. 現状|移動した本文を読む]]

## 3. 設計原則

[[40-Design/10-Analysis/quantification-statistics-plan/03-section#3. 設計原則|移動した本文を読む]]

## 4. 全体の流れ

[[40-Design/10-Analysis/quantification-statistics-plan/03-section#4. 全体の流れ|移動した本文を読む]]

## 5. 数値化の手段

[[40-Design/10-Analysis/quantification-statistics-plan/04-section#5. 数値化の手段|移動した本文を読む]]

## 6. LLMによるコード・評定

[[40-Design/10-Analysis/quantification-statistics-plan/05-section#6. LLMによるコード・評定|移動した本文を読む]]

## 7. 妥当性ゲート

[[40-Design/10-Analysis/quantification-statistics-plan/06-section#7. 妥当性ゲート|移動した本文を読む]]

## 8. 分析単位とデータセット

[[40-Design/10-Analysis/quantification-statistics-plan/06-section#8. 分析単位とデータセット|移動した本文を読む]]

## 9. 統計解析計画と検定の自動選択

[[40-Design/10-Analysis/quantification-statistics-plan/07-section#9. 統計解析計画と検定の自動選択|移動した本文を読む]]

### 9.1 計画

[[40-Design/10-Analysis/quantification-statistics-plan/07-section#9.1 計画|移動した本文を読む]]

### 9.2 選択表（jamoviとの対応）

[[40-Design/10-Analysis/quantification-statistics-plan/07-section#9.2 選択表（jamoviとの対応）|移動した本文を読む]]

### 9.3 選択と実行の規則

[[40-Design/10-Analysis/quantification-statistics-plan/07-section#9.3 選択と実行の規則|移動した本文を読む]]

### 9.4 jamoviとRでの再現

[[40-Design/10-Analysis/quantification-statistics-plan/07-section#9.4 jamoviとRでの再現|移動した本文を読む]]

## 10. 既存モジュールへの統合

[[40-Design/10-Analysis/quantification-statistics-plan/08-section#10. 既存モジュールへの統合|移動した本文を読む]]

## 11. 実装の順序

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#11. 実装の順序|移動した本文を読む]]

### 着手の条件

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#着手の条件|移動した本文を読む]]

### Phase 0：決定の実装と契約

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 0：決定の実装と契約|移動した本文を読む]]

### OBS-18：生成Vaultの書き出し失敗を保存APIに集約する

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#OBS-18：生成Vaultの書き出し失敗を保存APIに集約する|移動した本文を読む]]

### Phase 1a：SciPyの検定・集約・jamovi出力（AIなし）

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 1a：SciPyの検定・集約・jamovi出力（AIなし）|移動した本文を読む]]

### Phase 1b：statsmodelsによる分析

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 1b：statsmodelsによる分析|移動した本文を読む]]

### Phase 2：決定的な数値化（ルール辞書・会話構造）

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 2：決定的な数値化（ルール辞書・会話構造）|移動した本文を読む]]

### Phase 3：LLMのコード・評定と妥当性ゲート（同時に出す）

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 3：LLMのコード・評定と妥当性ゲート（同時に出す）|移動した本文を読む]]

### Phase 4：Transformer分類器と能動学習

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 4：Transformer分類器と能動学習|移動した本文を読む]]

### Phase 5：発展（誤分類の補正・音響・外部R）

[[40-Design/10-Analysis/quantification-statistics-plan/09-section#Phase 5：発展（誤分類の補正・音響・外部R）|移動した本文を読む]]

## 12. 配布条件（ライセンス）

[[40-Design/10-Analysis/quantification-statistics-plan/10-section#12. 配布条件（ライセンス）|移動した本文を読む]]

## 13. Phase 0で決める既定値

[[40-Design/10-Analysis/quantification-statistics-plan/11-section#13. Phase 0で決める既定値|移動した本文を読む]]

## 14. 採用しない案

[[40-Design/10-Analysis/quantification-statistics-plan/11-section#14. 採用しない案|移動した本文を読む]]

## 15. 文献

[[40-Design/10-Analysis/quantification-statistics-plan/11-section#15. 文献|移動した本文を読む]]

### 検定の選択・補正・入れ子

[[40-Design/10-Analysis/quantification-statistics-plan/11-section#検定の選択・補正・入れ子|移動した本文を読む]]

### コーディングの信頼性・自動測定の妥当性

[[40-Design/10-Analysis/quantification-statistics-plan/11-section#コーディングの信頼性・自動測定の妥当性|移動した本文を読む]]

### LLM・Transformer以外の数値化

[[40-Design/10-Analysis/quantification-statistics-plan/11-section#LLM・Transformer以外の数値化|移動した本文を読む]]
