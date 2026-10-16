---
note_id: design-core-handler-routing-reorganization-legacy-path
note_type: path-redirect
title: コア・ハンドラー・ルーティング再編案（移動先案内）
summary: 本文と同じnote_idは移動先に保持。通常検索は移動先を使用する。
status: deprecated
updated: '2026-10-11'
redirect_to: 40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index.md
tags:
- gurumoji/redirect
---

# コア・ハンドラー・ルーティング再編案

本文：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|コア・ハンドラー・ルーティング再編案]]。旧パスの互換案内。

## 作業の進め方：実装を依頼されたときの入口

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/01-section#作業の進め方：実装を依頼されたときの入口|移動した本文を読む]]

### 1回の作業で行うこと

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/01-section#1回の作業で行うこと|移動した本文を読む]]

### 段階の選び方と終了条件

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/01-section#段階の選び方と終了条件|移動した本文を読む]]

## 結論

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/02-section#結論|移動した本文を読む]]

### 評価と修正判断

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/02-section#評価と修正判断|移動した本文を読む]]

## この資料の基準

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/03-section#この資料の基準|移動した本文を読む]]

## 分析の関連設計図：原文から追加分析まで

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/03-section#分析の関連設計図：原文から追加分析まで|移動した本文を読む]]

### 図1：文字起こし・アウトライン・分析箇所・分析手法の関係

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/03-section#図1：文字起こし・アウトライン・分析箇所・分析手法の関係|移動した本文を読む]]

### 図2：分析結果からTransformer・Jevへつなぐ2経路

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/04-section#図2：分析結果からTransformer・Jevへつなぐ2経路|移動した本文を読む]]

### 分析同士のつながりは、実行依存と意味上の関連を分ける

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/05-section#分析同士のつながりは、実行依存と意味上の関連を分ける|移動した本文を読む]]

#### 計画案から確定入力への変換（FLOW-1で追加）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/05-section#計画案から確定入力への変換（FLOW-1で追加）|移動した本文を読む]]

#### 再送・再利用・新規実行の識別（FLOW-1で追加）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/05-section#再送・再利用・新規実行の識別（FLOW-1で追加）|移動した本文を読む]]

#### 段階実行の状態と再開（FLOW-1〜2で追加）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/05-section#段階実行の状態と再開（FLOW-1〜2で追加）|移動した本文を読む]]

### 図3：専用オーケストレーターの介入とローカルLLM

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/06-section#図3：専用オーケストレーターの介入とローカルLLM|移動した本文を読む]]

### 図4：分析用RAWと出力データの明確な分離

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/07-section#図4：分析用RAWと出力データの明確な分離|移動した本文を読む]]

### 図5：LLM・Transformer・Jevのカラム生成から統計分析へ

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/08-section#図5：LLM・Transformer・Jevのカラム生成から統計分析へ|移動した本文を読む]]

#### 現行コードでできること・不足していること

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/08-section#現行コードでできること・不足していること|移動した本文を読む]]

#### LLMにも分析とデータ作成を担当させる

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/08-section#LLMにも分析とデータ作成を担当させる|移動した本文を読む]]

#### カラムとデータセットの最小契約

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/08-section#カラムとデータセットの最小契約|移動した本文を読む]]

#### 統計分析への接続と実行順序

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/01-topics/08-section#統計分析への接続と実行順序|移動した本文を読む]]

### 図6：LLM分析専用オーケストレーターと、相談で作る手法別の型

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/09-section#図6：LLM分析専用オーケストレーターと、相談で作る手法別の型|移動した本文を読む]]

#### 相談する役割と、LLM・Jevの使い分け

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/09-section#相談する役割と、LLM・Jevの使い分け|移動した本文を読む]]

#### 手法別契約で先に決めること

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/09-section#手法別契約で先に決めること|移動した本文を読む]]

#### クロス集計以外へつなぐ結果の形

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/09-section#クロス集計以外へつなぐ結果の形|移動した本文を読む]]

#### 型の採用・保存・再利用と、増やしすぎない境界

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/09-section#型の採用・保存・再利用と、増やしすぎない境界|移動した本文を読む]]

### 図7：多様な分析を探す・読む・比較するUI

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/10-section#図7：多様な分析を探す・読む・比較するUI|移動した本文を読む]]

#### 現行UIの問題と、再利用するもの

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/10-section#現行UIの問題と、再利用するもの|移動した本文を読む]]

#### 画面の骨格と情報の優先順位

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/11-section#画面の骨格と情報の優先順位|移動した本文を読む]]

#### 結果形式ごとの読み方

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/11-section#結果形式ごとの読み方|移動した本文を読む]]

#### 分析手法とUIの対応確認（2026-09-20）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/12-section#分析手法とUIの対応確認（2026-09-20）|移動した本文を読む]]

##### 現行の登録21手法と、新UIでの受け持ち

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/12-section#現行の登録21手法と、新UIでの受け持ち|移動した本文を読む]]

##### 新設・拡張する分析と、同時に追加するUI

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/12-section#新設・拡張する分析と、同時に追加するUI|移動した本文を読む]]

##### 手法登録にUIの対応を含める

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/12-section#手法登録にUIの対応を含める|移動した本文を読む]]

#### 比較と追加分析を、その結果から始める

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/13-section#比較と追加分析を、その結果から始める|移動した本文を読む]]

#### 分析計画・疑似人格の相談を見せる画面

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/13-section#分析計画・疑似人格の相談を見せる画面|移動した本文を読む]]

#### データ・出力と、履歴・戻る操作

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/13-section#データ・出力と、履歴・戻る操作|移動した本文を読む]]

#### UIの導入順序と確認条件

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/14-section#UIの導入順序と確認条件|移動した本文を読む]]

### 図の実装順序と受け入れ条件

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/14-section#図の実装順序と受け入れ条件|移動した本文を読む]]

## 現行システム構成図

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/15-section#現行システム構成図|移動した本文を読む]]

### 現行構成で責務が交差している場所

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/15-section#現行構成で責務が交差している場所|移動した本文を読む]]

## 現行ER図（SQLite）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/02-topics/16-section#現行ER図（SQLite）|移動した本文を読む]]

## 現行ER図（成果物・Obsidianを含む概念関係）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/17-section#現行ER図（成果物・Obsidianを含む概念関係）|移動した本文を読む]]

## 現行ユースケース図

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/18-section#現行ユースケース図|移動した本文を読む]]

## 改訂案の構成と依存方向

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/18-section#改訂案の構成と依存方向|移動した本文を読む]]

### 各境界の最小契約

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/18-section#各境界の最小契約|移動した本文を読む]]

### 初回に必要な構成

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/18-section#初回に必要な構成|移動した本文を読む]]

## 維持する契約と分けて扱う課題

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/19-section#維持する契約と分けて扱う課題|移動した本文を読む]]

### 分析プログラム

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/19-section#分析プログラム|移動した本文を読む]]

### 状態と回復

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/19-section#状態と回復|移動した本文を読む]]

### 出力・Vault

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/19-section#出力・Vault|移動した本文を読む]]

## AI管理とローカルのオーケストレーター用データ

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/20-section#AI管理とローカルのオーケストレーター用データ|移動した本文を読む]]

### 1. 現行の役割と実行先

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/20-section#1. 現行の役割と実行先|移動した本文を読む]]

### 2. クラウド／ローカルを管理する方針

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/20-section#2. クラウド／ローカルを管理する方針|移動した本文を読む]]

### 3. Jevの使い道と判断の限界

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/21-section#3. Jevの使い道と判断の限界|移動した本文を読む]]

### 4. ローカルデータの所在と正本

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/21-section#4. ローカルデータの所在と正本|移動した本文を読む]]

### 5. AI呼び出しの実行境界

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/22-section#5. AI呼び出しの実行境界|移動した本文を読む]]

### 6. 実行要求・設定・来歴の管理

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/22-section#6. 実行要求・設定・来歴の管理|移動した本文を読む]]

### 7. 利用者に見せる管理情報

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/23-section#7. 利用者に見せる管理情報|移動した本文を読む]]

### 8. AI管理の導入順序

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/23-section#8. AI管理の導入順序|移動した本文を読む]]

## 段階的な移行プラン

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#段階的な移行プラン|移動した本文を読む]]

### Phase 0：対象と比較基準を固定

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#Phase 0：対象と比較基準を固定|移動した本文を読む]]

### Phase 1：読み取り3ルートを縦切りで分離

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#Phase 1：読み取り3ルートを縦切りで分離|移動した本文を読む]]

### Phase 2：固定保存・Vault再試行を同じ境界へ移す

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#Phase 2：固定保存・Vault再試行を同じ境界へ移す|移動した本文を読む]]

### Phase 3：効果のある機能だけ同じ手順で拡張

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#Phase 3：効果のある機能だけ同じ手順で拡張|移動した本文を読む]]

### Phase 4：互換入口と不要な橋渡しを整理

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#Phase 4：互換入口と不要な橋渡しを整理|移動した本文を読む]]

### Phase 5：app.py に残った処理の移動（2026-09-25）

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/03-topics/24-section#Phase 5：app.py に残った処理の移動（2026-09-25）|移動した本文を読む]]

## 移行時の必須確認

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/25-section#移行時の必須確認|移動した本文を読む]]

### Blueprint、HTTP、配信

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/25-section#Blueprint、HTTP、配信|移動した本文を読む]]

### 保存・同時実行・回復

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/25-section#保存・同時実行・回復|移動した本文を読む]]

### 差し戻しと中断

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/25-section#差し戻しと中断|移動した本文を読む]]

## 検証対象と受け入れ条件

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/26-section#検証対象と受け入れ条件|移動した本文を読む]]

## 採用判断

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/27-section#採用判断|移動した本文を読む]]

## 実装根拠

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/04-topics/27-section#実装根拠|移動した本文を読む]]
