---
note_id: method-segment-classification
note_type: analysis-method
method_id: segment_classification
method_version: text-analysis-store-8
algorithm_version: segment-classification-1
execution_kind: builtin
title: 発話種別・重要度・要確認・機密らしさ
status: current
tags: [gurumoji/analysis, gurumoji/conversation, gurumoji/orchestrator]
---

# 発話種別・重要度・要確認・機密らしさ（`segment_classification`）

## 実装契約

発話ごとに、研究者の手動確定値と3種類の自動提案を分けて保存する。

- テンプレート：日本語の表記・語句と既存Jev文字起こし確認値を使う決定的な規則
- Jev：発話種別、研究上の重要度、再確認の必要性、機密情報らしさをChoice問題として判定する。コードブックがあれば話題候補も問う
- Transformer：既存の意味クラスタ／手動テーマへの割当結果だけを再利用する

発話種別は質問、回答、提案、依頼、確認、同意、留保、反対、自己訂正、相づち、情報共有、その他から選ぶ。3スコアは0〜100で保存する。`segment_classifications`は全発話の比較、`segment_classification_crosstabs`は提案元×発話種別、手動×Jev、テンプレート×Jev、Transformer話題×Jev、手動コード×Jevの度数を保持する。

## オーケストレーターの判断

- 自動値は提案であり、手動値を上書きしない。「手動欄へ反映」後も確認途中として保存する。
- 発話本文、コードブック、手動注釈、採用するTransformer結果のいずれかが変わったら最新提案を更新対象にする。
- Jevへ送るのは発話本文と短い前後文脈、任意のコードブック定義である。音声、同意条件、組織固有の機密区分は見ていない。
- クロス集計は記述的な度数である。AI同士の一致を妥当性や正解率と呼ばない。

## 言えないこと

重要度・要確認度・機密らしさは校正済み確率ではない。機密らしさの値は法的分類、アクセス権、匿名化要否を確定しない。Transformerの意味的な近さは発話機能、賛否、重要性を表さない。テンプレートとJevの一致は人手による正解との一致ではない。

## 実装位置

`src/gurumoji/segment_classification.py`、`app.py`の`/api/library/<id>/analysis/classifications`、`analysis_method_registry.py`。手動値は`analysis_annotations_json`、最新提案は`segment_classification_json`、固定結果は`analysis_store`の`segment_classification`実行として保存する。
