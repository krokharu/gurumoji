---
note_id: template-skill-definition
note_type: template
title: 分析スキルの登録票
status: proposed
updated: 2026-10-08
tags: [gurumoji/template, gurumoji/skill]
---

# 分析スキルの登録票

G1bの登録書式候補。使い方と実行接続の境界は [[50-Analysis-Methods/40-Skills/00-Index]]、設計根拠は [[40-Design/obsidian-skill-knowledge-blueprint#4. スキルノートの契約案]]。このテンプレートと未記入例を実行候補へ登録しない。アプリの01定義・07契約を変更する書式ではない。

## 登録前の確認

既存の専門家・method・toolと許可procedureを先に探す。新しいスキルIDは既存IDとの重複を検査し、用途に必要な入力・出力・停止条件を一単位にする。文献未取得、未対応adapter、研究者の未回答はそれぞれ不足として残す。

## 前付の書式

山括弧の値は記入場所であり、実在IDではない。`note_id`と`skill_id`は登録時に確定する。前付は単純な値とリスト、複雑な依存は本文の版付きブロックに置く。

```yaml
note_id: <一意のノートID>
note_type: executable-skill
title: <人が読む作業名>
summary: <問い・入力・返すものを一文で>
status: proposed
schema_version: 1
skill_id: <一意のスキルID>
skill_version: 1
expert_ids: [<既存expert ID>]
stage: <既存契約と照合した段階>
review_state: draft
runtime_state: planned
required_note_ids: [<実在する必須note ID>]
optional_note_ids: []
guards_block_id: <固有ID-guards>
procedure_block_id: <固有ID-procedure>
output_block_id: <固有ID-output>
updated: 2026-10-08
tags: [gurumoji/skill]
```

## 本文の必須項目

| 項目 | 記入・検査すること |
| --- | --- |
| 条件と入力 | 研究上の問い、探索／確認、分析単位、scope、元資料ID・版・hash、必要媒体、用途と送信可否 |
| 必須確認 | 前提・除外・欠測・分母・反復、必須知識、判断不能時の保留、禁止結論 |
| 段階別手順 | actor、01の許可procedure ID、読むnote ID・節／block ID、既存method／toolと依存。人の判断をAIへ移さない |
| 出力 | 07の出力名・schema版との対応、計算表の固定参照、根拠発話ID、候補／確定の区別、未処理・限界 |
| 停止と引継ぎ | 未登録・参照切れ・版不一致・未配信・予算不足・未対応scopeの理由、次担当と再開条件 |
| 根拠と評価 | 出典ID・確認範囲・位置、正常／不適用／反例のcase ID、対象hashへのレビュー、実モデル・人評価の未実行範囲 |

依存を指定する本文ブロックには、schema版、`note_id`、必要な`block_id`または節範囲、固定版・hashの取得方法を記す。必須・任意のID集合は前付と一致させる。ブロックIDは英字・数字・ハイフンで付け、表は表全体の後に独立したID行を置く。ID欠落や曖昧な節名を全文自由取得で補わない。

## レビューと接続

`review_state: reviewed`は対象hashへのレビューを記録した場合だけ。文書レビュー、合成検証、実モデルの適切な適用、人の研究上の採否を分ける。`runtime_state: connected`には登録reader・callback・adapterと実経路の検証が必要。現行G1bではノートを作っても接続済みにしない。研究者の本文や実データをこの票へ複製せず、正本は [[30-Data/analysis-storage-v1]] の参照へ戻す。
