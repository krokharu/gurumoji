---
note_id: template-knowledge-evaluation
note_type: template
title: 知識充足と評価ケースの登録票
status: proposed
updated: 2026-10-08
tags: [gurumoji/template, gurumoji/evaluation]
---

# 知識充足と評価ケースの登録票

G1b〜G4の評価書式。文書の存在、根拠の確認、実行接続、合成検証、実モデル品質、人の採否を分ける。未実行や欠測を成功／ゼロに置き換えない。入口は [[50-Analysis-Methods/50-Knowledge-Evaluation/00-Index]]。

```yaml
note_id: <一意の評価ノートID>
note_type: knowledge-evaluation
title: <専門家・作業段階・評価対象>
summary: <確認済み範囲と残る不足>
status: proposed
schema_version: 1
expert_ids: [<既存expert ID>]
stage: <評価対象段階>
review_state: draft
runtime_state: planned
case_ids: [<実在または本ノートで定義するcase ID>]
updated: 2026-10-08
tags: [gurumoji/evaluation]
```

## 固定する対象

| 項目 | 記録する値 |
| --- | --- |
| 取得元 | note ID、版、raw byte hash、取得日時、base／local／実runの区別、必要節／block |
| 実装 | 対象commit、dirty差分hash、adapter／契約／hook版、実行host、許可範囲 |
| 入力 | 合成／実データの区別、入力版・対象ID集合・hash、分析単位、分母・欠測・除外・未読 |
| 条件 | 正常／不適用／不足／反例、既存能力、期待状態と独立した根拠、停止条件 |
| 予算 | 担当、最大時間、呼出し・token・取得・deadlineの上限、欠測時の扱い |

## 結果と人の確認

caseごとに、実コマンド・結果・件数・時間・artifact参照、成功／失敗／未実行と次担当を記す。集計は対象集合と分母を先に固定し、失敗や未測定を後から除かない。期待値を実装に合わせて変えず、変更理由と対象版を残す。

人向け評価は「根拠を追えるか」「反例で解釈を修正できるか」「何を人が判断するか」を確認する。未回答は未評価、未対応は理由付き保留。技術的に完了したrun、AI下書きの意味的品質、研究者の確定解釈は別欄にする。研究者の本文を登録票へ転載しない。

## レビュー記録

作者と独立した担当が対象hash、正常／異常対、制約を確認した場合にだけ、その範囲の文書レビューを記録する。`review_state`の変更だけで採用を確定しない。重大な未判定は`human_pending`相当の保留を維持し、後続の確定根拠へ昇格させない。保存と所有権は [[40-Design/ai-development-rules]] と [[30-Data/analysis-storage-v1]] に従う。
