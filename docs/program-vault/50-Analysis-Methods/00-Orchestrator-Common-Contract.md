---
note_id: analysis-orchestrator-common-contract
note_type: design-knowledge
title: 分析オーケストレーター共通契約
status: proposed
updated: 2026-09-14
tags:
  - gurumoji/analysis
  - gurumoji/orchestrator
---

# 分析オーケストレーター共通契約

個別オーケストレーターは「分析を実行する」だけでなく、再現可能な対象集合を作り、結果と根拠を保存し、解釈不能な状態を成功扱いしない責務を持つ。

## 最小入力契約

| 項目 | 必須内容 |
| --- | --- |
| 対象 | `item_id`、`source_revision`、`analysis_revision`、発話ID集合 |
| 設定 | 手法固有パラメーター、除外規則、分析単位、比較軸 |
| 実行環境 | `method_id`、アルゴリズム版、解析器／ライブラリ版、モデル名・revision・seed |
| 根拠 | 結果行から辿れる発話ID、または元表の行キー |
| 保存先 | 固定 `result.json`、全件CSV、Obsidian要約ノート。画面プレビューだけを根拠にしない |

## 共通の実行状態

`not_run`、`completed`、`empty`、`unavailable`、`fallback`、`partial`、`stale` を区別する。`fallback` はGiNZA不在時の簡易形態素解析、`stale` は入力・設定・モデルが変わり結果が現行でない状態であり、どちらも通常の完了結果と混ぜない。

## 必須のゲート

1. **入力妥当性**: 空本文、無効時刻、`UNKNOWN` 話者、除外発話、欠測を数え、手法の前提を満たすか判断する。
2. **設計妥当性**: 分析単位（現行の計量分析は原則「発話」）と、研究質問・比較軸が整合しているか確認する。
3. **計算妥当性**: 乱数seed、候補パラメーター、エンジン・モデル版を結果に残す。統計では実行可能性、期待度数、群数、N、仮定注記を確認する。
4. **根拠妥当性**: 要約・AI出力・テーマ名には発話IDを必須にし、IDが現行本文と一致しない場合は`stale`または失敗にする。
5. **解釈ゲート**: 自動値から合意、因果、重要性、本人の感情、遮り等を断定しない。人の検証・反例・文脈確認を要求する。

## オーケストレーターの出力

`plan`（選択理由・前提）、`run`（入力fingerprint・環境・状態）、`artifacts`（JSON／CSV／ノート）、`evidence`（発話ID・行キー）、`warnings`（前提違反・限界）、`next_actions`（人が判断する問い）を分けて返す。生成AI系はモデル応答を研究者のコードや手動メモへ自動反映しない。

関連: [[40-Design/method-rules|分析手法ごとのObsidian登録規約]]、[[30-Data/analysis-storage-v1|文章分析の保存仕様]]
