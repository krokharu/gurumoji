---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-23
title: コア・ハンドラー・ルーティング再編案：7. 利用者に見せる管理情報
summary: 7. 利用者に見せる管理情報。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1359
- 1380
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：7. 利用者に見せる管理情報

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

### 7. 利用者に見せる管理情報

既存のAI設定・実行開始・進捗・結果画面を拡張する。独立したAI管理ダッシュボードは初期には作らない。

- 開始前：生成用model、Jev利用の有無、段階ごとの送信先、対象データの範囲、選択した専門家と実行できない理由。
- 進捗：実行中の段階、バッチ進捗、実行先、取消可否。内部のadapter名や保存実装は表示しない。
- 結果：生成案・Jev判定・手動確定値、不一致、未実行／失敗、使用モデル、知識版、取得できたusageを区別する。
- 再試行：「保存済み結果のVault再公開」と「AIを再実行」を別の操作として示す。前者では送信も再課金も発生させない。

### 8. AI管理の導入順序

構造再編と動作拡張は別の変更としてレビューするが、どちらも本計画に含める。

| 段階 | 内容・依存 | 完了条件 |
| --- | --- | --- |
| AI-0：接続境界の抽出 | Phase 1の方式を確認後、`call_ai_json`、Jev呼び出し、資格情報解決を必要最小限の接続モジュールへ移す。`ai_http_worker`と現在の形式・取消・再試行を再利用 | 同じ入力で同じ送信先・回数・payload。既存provider／Jevのテストが通り、新モジュールから`app.py`への逆importがない |
| AI-1：送信方針と実行設定 | AI-0後。既存設定・UIに段階別の実行先、`local_only`／`cloud_allowed`、能力確認、実行中に変わらない設定を追加 | local_only時のJevを含む研究データのクラウド送信が0件。キーの有無だけで実行されず、設定変更が進行中要求へ混入しない |
| AI-2：知識と実行来歴 | AI-1とPhase 2の保存境界確認後。既存ExpertCatalogと入力・知識hashを結び、送信前に実際のcontext packetを版付きで固定保存 | 選択した知識だけを使用。旧runを読める。定義変更後も当時の指示を取得でき、バッチへ新旧の指示が混在しない。Vault再公開のAI呼出し0件 |
| AI-3：確認作業の改善 | AI-2後、必要なら既存のJev不一致・分類結果の表示順を改善 | 追加推論なしで確認候補を辿れ、原文・手動値・未判定が保持される |

役割別LLMの相談は利用者の追加要求によりFLOW-5bへ含める。AI-0〜AI-3や構造再編の前提にはしない。初期対象外は、専門家ごとの常駐プロセス、無制限の合議、モデル自動学習、全VaultのベクトルDB化、別のオーケストレーター製品・汎用プラグイン基盤、全モデルの一斉実行。必要な役割だけを上限付きで呼び、採用済み契約では相談を省く。
