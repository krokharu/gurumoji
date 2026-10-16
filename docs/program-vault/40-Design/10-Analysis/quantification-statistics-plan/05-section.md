---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-05
title: 発話の数値化とjamovi型統計の自動実行計画：6. LLMによるコード・評定
summary: 6. LLMによるコード・評定。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 113
- 132
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：6. LLMによるコード・評定

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 6. LLMによるコード・評定

既存の`call_ai_json`、実行中だけの参照番号、`enum`による根拠IDの制約、1回の修正再試行を共通化して使う。

| 項目 | 設計 |
| --- | --- |
| 実行の入口 | 分析画面の「AIで数値化」ボタンだけ。①試行（検証サンプル、または利用者が選んだ少数の発話）②全件、の2段階で実行する。文字起こしジョブ、統計の実行、保存、Vault出力からは呼ばない |
| 送信前の確認 | 送信先（事業者・モデル）、対象の発話数、推定トークン、1回の上限、話者台帳と会話話者の同意の状態を表示する |
| 同意の扱い | 同意しなかった話者の発話は送らず、除外した件数を結果に記録する。同意が未確認の話者を含む場合は警告し、利用者の確認を記録する |
| 送る情報 | 発話本文、話者ID、役割、判定に必要な文脈。話者の氏名・仮名・所属は送らない |
| 入力 | コードブック（ID・定義・含める例・除外する例）、評定基準（1〜5の各段階の説明と例）、対象発話と文脈（直前の質問、同じ話者の前後）。文脈は判定の対象外であることを、プロンプトとschemaで区別する |
| 出力 | 発話ごと・コードごとに`ref`、`code_id`、`present`（有／無）、`evidence_quote`、`confidence`。評定は`score`（1〜5、判定できない場合は`null`） |
| サーバーでの検証 | `ref`と`code_id`は`enum`。`evidence_quote`は対象発話本文の部分文字列と完全に一致すること（文脈からの引用は拒否）。応答にない発話は「未判定」とし、「なし」や0にしない |
| キャッシュと再開 | 発話本文のhash、コードブック版、プロンプト版、モデルが同じ判定は再利用し、送り直さない。上限トークンに達する前に止める。失敗したバッチだけ再実行する |
| 安定性 | 検証サンプルと、無作為に選んだ安定性確認用の部分（抽出確率を記録）だけ3回実行し、それ以外は1回。実行間のαがしきい値未満のコードは、全件を3回にするか、コードブックを直す |
| 保存 | AIのラベルは`annotation.codes`に書かず、別のデータセット（案：`ai_code_labels`）に保存する。provider、model、プロンプト版のhash、schemaのhash、コードブック版のhash、エフォート、実行番号、日時を記録する。人のコードへの採用は研究者の明示操作だけにし、採用の記録を残す |
| 送信の記録 | 件数、hash、事業者、モデル、日時、トークンだけを残し、本文はログに残さない。OpenAIへの要求は既存どおり`store: false` |
| 使用量 | `app.extract_ai_token_usage`で記録し、キャンセルと進捗は既存のAI要求台帳の方式に合わせる。新しいschema名は`ai_effort.SCHEMA_STAGES`の既存段階へ対応付ける |
| させないこと | 検定の選択、統計量やp値の計算、報告文の数値、コードブックの自動変更 |
