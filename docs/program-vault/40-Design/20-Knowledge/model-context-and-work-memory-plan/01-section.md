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
note_id: design-model-context-and-work-memory-section-01
title: モデル別コンテキスト管理と作業記録の保存計画：モデル別コンテキスト管理と作業記録の保存計画
summary: モデル別コンテキスト管理と作業記録の保存計画。出典ノート「モデル別コンテキスト管理と作業記録の保存計画」の分割本文。
parent_note_id: design-model-context-and-work-memory
source_path: 40-Design/model-context-and-work-memory-plan.md
source_sha256: 5deb802e628cb0041fcc9fb6b42ddf5ac43615a40641f4aa9d09e449c34d9323
source_body_lines:
- 1
- 24
split_on: '2026-10-11'
---

# モデル別コンテキスト管理と作業記録の保存計画：モデル別コンテキスト管理と作業記録の保存計画

親索引・状態・確認版：[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index]]。必要な本文だけを取得する。


# モデル別コンテキスト管理と作業記録の保存計画

Gurumojiのローカル分析を、モデルの能力と入力予算に合わせて動かす計画。必要なルール・手法・根拠だけを取得し、会話を短くしても作業を再開できるようにする。設計判断と人が読む引継ぎはObsidian、機械が再開する状態はDB、全件の結果と入力は版付きJSONに保存する。

2026-10-05の「プランを実行して」に基づき、既存Handlerへ試験経路を追加した。`model_context_version=1`を明示した新規runだけに適用し、既定は0。実装済みの範囲と役割別品質の未評価を区別する。既存の[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]、[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index|expert-knowledge-production-plan]]、[[40-Design/40-Storage/storage-policy|storage-policy]]を補足する。

## 実装前の確認と改善対象

確認環境はWindows、ブランチ`main`、基点commitは`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`。以下は2026-10-05の既存未コミット変更を含む作業ツリーの調査結果。コードとテストを現行仕様の正本とする。

| 対象 | 確認した現状 | 本計画で追加すること |
| --- | --- | --- |
| [分析Handler](../../../../../src/gurumoji/analysis_orchestration.py)の`_context` | 発話数・文字数による上限。対象の先頭部分を渡し、全量を順次読むカーソルはない | 実モデルのトークン予算、対象版ごとの提示範囲、未提示部分の次タスク |
| [AI adapter](../../../../../src/gurumoji/services/analysis_orchestration_adapters.py) | 共通・役割別promptとschemaに初期分析・初期ルーティング等の指示を追加 | 段階専用の短い契約を選び、schemaも含めて予算化 |
| [AI設定](../../../../../src/gurumoji/services/ai/settings.py)の`available_ai_models` | 互換APIのモデル一覧を取得。実試験スクリプトは別途native APIでロード枠を記録 | 既存の選択経路へ、ロード中instanceの能力情報と評価済み役割を追加 |
| [分析履歴](../../../../../src/gurumoji/services/analysis_history.py) | 保存台帳をページ単位で読む。閲覧は再推論しない | 来歴・未処理・差分を小さく取得する内部経路へ再利用。公開APIへ秘密値やモデルの思考過程を追加しない |
| [専門知識](../../../../../src/gurumoji/knowledge_builder/expert_knowledge_context.py)の`build_expert_packet` | 専門家の承認済みclaimを全件収録し、過大入力を拒否。問い合わせ別の順位付けは未実装 | 必須の適用条件・限界を残した部分取得を別版で追加。承認・hash・送信先の検証を維持 |
| [保存分類](../../40-Storage/storage-policy.md)と[Vault統合](../../../20-Modules/30-Storage/obsidian-integration/00-Index.md) | SQLite、固定成果物、VaultRegistry、生成ノートの所有権・履歴保存経路がある | 既存の正本と保存経路に、入力パケットの来歴と再開用情報を接続 |

直近のマーラータン試験では323発話の固定入力に対し、各AIへの提示は48発話、未提示は275発話。Coreの採用判断3回の主張数は`0 / 0 / 0`で、重複した作業案を抑止して`no_new_tasks`で停止し、厳格判定は失敗だった。初期専門家への依頼、尺度下書きの作成、保存hashの検証は確認できている。試験記録（ローカル記録・Git未同梱：`../../../../../output/malatang-initial-specialists/20261005T091842Z-70c6bdb6/verification.json`）に戻れるが、`output`はローカルの未追跡成果物であり、共有先での存在は保証しない。

過去の入力枠超過は予算化の必要性を示す。一方、主張0件の原因をコンテキストだけに特定できていない。モデル能力、指示とschema、根拠の範囲、尺度定義から実際のコード付与までの未完了工程を分けて評価する。
