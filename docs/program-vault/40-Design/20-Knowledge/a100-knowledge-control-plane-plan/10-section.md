---
note_type: reference-section
status: in-progress
updated: 2026-09-30
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/knowledge-builder
- gurumoji/colab
- gurumoji/plan
note_id: design-a100-knowledge-control-plane-plan-section-10
title: A100知識推論コントロールプレーン計画：13. テスト計画
summary: 13. テスト計画。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 513
- 544
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：13. テスト計画

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 13. テスト計画

- unit: 状態遷移、集計、score gate、予算計算、unknown処理、event projection。
- API: loopback制限、CSRF/Origin、revision競合、秘密値除外、Source本文除外。
- transport: 部分ZIP、hash不一致、stale generation、重複import、期限切れ、checkpoint再開。
- integration: 一時SQLite＋一時Drive相当＋mock workerでjob作成からacceptedまで。
- Colab実機: 1件だけで接続、A100 preflight、推論、切断、再接続、結果受理を確認する。
- Vault: 実Vaultを使わず一時Vaultで生成ノート、stale、競合を確認する。
- UI: 17×複数モデルの表、0/unknown、長いID、失敗、タスク追加・編集・実行・停止、実行ボタン二重押下、reduced-motion、キーボード操作。

全体suiteはP4、P5、P7の境界変更時に実行し、通常は対象モジュールのfocused testsを先に実行する。

## 14. リスクと抑止策

| リスク | 抑止策 |
| --- | --- |
| A100が割り当たらない | GPUを前提にqueueをclaimせず、手動選択を待つ。別profileへ明示的に再発行 |
| Colab停止・最大寿命 | 短いjob、1件ごとの結果確定、checkpoint、Drive上のheartbeat、再実行可能設計 |
| Pro利用枠超過 | Google側の追加購入無効化、reserve、実測予測、空キュー即終了、unknown時停止 |
| Web UI経由の制限回避と判定される | Notebook操作の自動化をせず、Driveのデータ搬送だけを自動化 |
| AIが不正な作業を指示 | work order schema、allowed action allowlist、人の承認、任意shell禁止 |
| 知識量の水増し | Claim数だけでなく必須coverage、根拠数、重複、評価gateを併記 |
| candidateを完成扱い | succeeded、accepted、approved、packed、publishedを分離 |
| Gitへのprivate成果物流入 | runtime配下へ統一、ignore、pre-commit secret/large-file検査 |
| 既存の未コミット作業との衝突 | P0で保全し、専用ブランチ開始前に変更の所有と保存先を確定 |

## 15. 着手順

最初の実装単位はP0とP1に限定する。ここではColabを動かさず、既存のJobStoreと成果物を読み取って、正しい集計を表示するところまでにする。その結果を確認してからP2のグラフ、P3の変更操作、P4のDrive自動搬送へ進む。

この順序により、現在すでに存在する17専門家分の候補、accepted Commit、A100実測、評価契約を失わず、管理画面を新しい正本にしてしまう事故を避けられる。
