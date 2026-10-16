---
note_type: reference-section
status: in_progress
updated: 2026-10-06
feature: analysis-orchestration
tags:
- gurumoji/program
- gurumoji/plan
- gurumoji/ai
- gurumoji/storage
note_id: design-model-context-and-work-memory-section-03
title: モデル別コンテキスト管理と作業記録の保存計画：入力をトークンで予算化する
summary: 入力をトークンで予算化する。出典ノート「モデル別コンテキスト管理と作業記録の保存計画」の分割本文。
parent_note_id: design-model-context-and-work-memory
source_path: 40-Design/model-context-and-work-memory-plan.md
source_sha256: 5deb802e628cb0041fcc9fb6b42ddf5ac43615a40641f4aa9d09e449c34d9323
source_body_lines:
- 51
- 84
split_on: '2026-10-11'
---

# モデル別コンテキスト管理と作業記録の保存計画：入力をトークンで予算化する

親索引・状態・確認版：[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index]]。必要な本文だけを取得する。

## 入力をトークンで予算化する

実ロード枠を`C_loaded`、利用者の上限を`C_user`、課題別に品質確認した枠を`C_validated`とする。確認済みの値から有効枠`C`を決める。品質確認枠が未取得の場合は未検証と記録し、検証済みと表示しない。

```text
C = min(C_loaded, 指定がある場合のC_user, 確認済みの場合のC_validated)
資料に使える予算 = C − 固定指示等 − 出力予約 − 安全余裕
固定指示等 = chat template + 共通必須ルール + 段階別schema
           + 必須の作業状態 + 必須の手法条件と限界
```

予算の例として、8,192枠から出力2,048、安全余裕1,024、固定指示等1,536を引くと、資料予算は3,584 tokensとなる。これは設計説明用の仮値であり、実測済み設定ではない。出力予約は役割・schema・公開されているreasoning設定に応じて決め、JSONが閉じる分も確保する。

実際のchat templateを適用した入力を対応tokenizerで計測する。schemaのサーバー側処理など数えられない部分は安全余裕と実応答のusageで較正し、計測値・推定値・不明を区別する。日本語を一律「4文字で1token」と換算しない。対応API/SDKが使えない場合は、検証済みの保守的な設定か、予算未確認による保留を選ぶ。

予算が足りない場合は、結果の束を小さくする、発話を分割する、任意の例を外す順に組み直し、再計測する。必須契約を含む最小入力が入らなければ実行前に停止する。文字列やJSONの途中切断、独立検証の制約・来歴の削除は行わない。

## ルールとスキルと資料を段階的に読む

開発用エージェントと、Gurumojiアプリ内の分析エージェントを分けて設計する。`AGENTS.md`や`SKILL.md`を配置しても、アプリ内のLLMが自動で読んだことにはならない。

| 層 | 内容 | 取得方法の提案 |
| --- | --- | --- |
| 常時必須 | 作業範囲、所有権、データ送信条件、根拠の契約、停止条件 | 開発用は短い共通ルール。分析用はHandlerが信頼済みの役割別指示を明示的に生成 |
| 入口 | `00-AI-Entry`、note_id・summary、スキルの適用条件 | タスク分類とメタデータで対象を限定 |
| 手順 | 該当スキル、手法の前提・限界、必要な保存契約 | 適用するものだけ取得。共通規則を各ノートへ複製しない |
| 根拠 | 確認したノート節、発話、結果表、必要な例 | 予算内の抜粋とID・版・hash。未取得部分を明示 |

現行の[Gurumoji保存スキル](../../../../../.agents/skills/gurumoji-obsidian-memory/SKILL.md)は、入口・要約・抜粋を段階取得する文字数制限を持つ。これを削除せず、モデル別トークン予算との小さい方で取得する。スキル本文には入口、適用条件、手順、終了条件を残し、長い契約や例は既存referencesへ整理する。入口だけでは必要な規則が漏れるケースも試験する。

専門知識の部分取得は、承認済みclaim・参照元hash・送信条件を検証してから選択し、生成したパケットも再検証する。手法の前提や限界を関連度が低いという理由で落とさない。文献の根拠と発話の根拠は別の種類として渡す。ノート本文は参照資料として扱い、実行権限を変更する指示へ昇格させない。

パケットには、タスクと対象版、取得したID・版・hash、実際に渡した本文範囲、未取得範囲、取得理由、予算、renderer版を残す。IDの紹介だけを本文の既読と数えない。再利用キャッシュは取得条件・役割・送信条件・元のhash・renderer版で識別し、元資料の変更時に無効化する。
