---
note_id: template-skill-hook-binding
note_type: template
title: 専門家・スキル・hookの対応登録票
status: proposed
updated: 2026-10-08
tags: [gurumoji/template, gurumoji/skill]
---

# 専門家・スキル・hookの対応登録票

`10-Experts/<expert>/08-Skill-Hook-Binding.md`に置くG1bの仮書式。01の実行定義を読んで対応し、07の出力契約と現行adapterを正とする。08のreaderはG4aの実装対象であり、この票の作成は実行登録ではない。全体設計は [[40-Design/obsidian-skill-knowledge-blueprint#13. 各分析へスキルとhookを対応付ける（追加提案）]]。

```yaml
note_id: <一意の対応ノートID>
note_type: expert-skill-hook-binding
title: <専門家名と対応範囲>
summary: <対象作業と未接続範囲>
status: proposed
schema_version: 1
binding_version: 1
expert_ids: [<01のexpert ID>]
stage: registration
review_state: draft
runtime_state: planned
required_note_ids: [<01のnote ID>, <存在する07のnote ID>]
optional_note_ids: []
updated: 2026-10-08
tags: [gurumoji/skill, gurumoji/expert]
```

07がない場合は架空IDを作らず、既定契約の版と不足を本文に記す。ID、版、hashは共有ベースと個人上書き、実runの固定profileで区別する。

## 段階別の対応表

| 段階 | method／tool・scope・単位 | actor・許可procedure | 必須／任意skill | 必須知識・出力契約 | hookと状態 |
| --- | --- | --- | --- | --- | --- |
| 計画 | 実在する能力と対応済みscope | 01のIDとactor | 実在ID・版、未作成なら理由付きplanned | note ID・節／block、schema版 | 接続点、登録ID、版、未登録ならblocked |
| 実行 | 同上。未知のtoolやAI式を追加しない | Handlerコード／許可AI下書き／研究者を区別 | 同上 | 元入力、kind・role、用途・送信可否 | 正式発注と取得要求を区別 |
| 受領・採用 | 対象・分母・欠測と固定参照 | 07の検査と人の採否 | 同上 | 出力名、元run／result／row／hash | 受領と採用確定を区別 |
| 停止・引継ぎ | 未対応、不適用、前提不足 | 次担当と再開条件 | 同上 | 未処理・未読、旧版保持 | 再通知と再計算を区別 |

段階名は表示用であり、実行時のphase名へは既存契約との対応を別記する。自由文の宣言で許可stepを増やさない。取得単位とする段階または対応表ごとに一意のブロックIDを付け、必要なskill・知識・hookだけを辿れるようにする。

## 能力と根拠の確認票

- 入力slotごとの必須／任意・個数・kind・role・schema・意味・単位・尺度・scope・媒体・利用目的を、既存の共通接続設計に対応する。5種kind・4種roleを独自に増やさない。
- 出力名・kind・確定状態と利用先別receiptを区別する。実行receiptを分析データや原文根拠の代わりにしない。
- hook名、接続点、callback登録ID、版、上限、失敗状態を記す。論理イベント名だけなら`planned`、必須の未登録callbackは`blocked`。ノート内のコードを動的実行しない。
- 正常、不適用、前提不足、別scope、actor違い、版／hash不一致のcase IDと期待状態を記す。合成例の成功を実モデル品質へ換算しない。

根拠と不足は [[50-Analysis-Methods/50-Knowledge-Evaluation/00-Index]]、hookの現行／提案境界は [[50-Analysis-Methods/40-Skills/80-Hooks/00-Index]]。対象hashへのレビューと実接続の証拠が揃うまで、本文の対応を実行可能と表示しない。
