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
note_id: design-a100-knowledge-control-plane-plan-section-08
title: A100知識推論コントロールプレーン計画：10. モデルと作業配分
summary: 10. モデルと作業配分。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 412
- 446
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：10. モデルと作業配分

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 10. モデルと作業配分

| 作業 | 既定実行先 | 理由 |
| --- | --- | --- |
| ファイル選択、hash、schema、重複、権利route判定 | Pythonコード | 決定的で安価 |
| キュー整理、失敗分類、次の候補提案 | ローカルLLM | private情報を端末外へ出さず常時利用可能 |
| Claim候補生成、比較、難しい意味審査 | A100 | 大きいモデルを必要なときだけ使用 |
| 実装変更、テスト修正、契約レビュー | Codex | コード作業としてwork order単位で実施 |
| 最終承認、権利判断、公開判断 | 人 | AIから分離する |

モデルprofileには、対象task、許可route、revision、量子化、context、max input/output tokens、parallelism、最大試行回数、日次/月次予算を設定する。画面で「モデルを何回使うか」を手動指定できるが、同じ出力を無条件に繰り返さず、repeatの目的を `品質確認 / 独立評価 / 失敗再試行 / 比較` から選ばせる。

## 11. API案

| Method / path | 用途 |
| --- | --- |
| `GET /api/knowledge-console/summary` | ダッシュボード集計 |
| `GET /api/knowledge-console/experts` | 専門家×モデル指標 |
| `GET/POST /api/knowledge-console/tasks` | タスクの一覧・draft作成 |
| `GET/PUT /api/knowledge-console/tasks/<id>` | draftの取得・revision付き編集 |
| `POST /api/knowledge-console/tasks/<id>/execute` | preflight後に一度だけキュー投入・開始 |
| `POST /api/knowledge-console/tasks/<id>/duplicate` | draftとして複製 |
| `POST /api/knowledge-console/jobs/<id>/cancel` | 次の安全点で取消 |
| `POST /api/knowledge-console/jobs/<id>/retry` | 新generationの作成 |
| `GET /api/knowledge-console/sessions` | Colab/local session状態 |
| `POST /api/knowledge-console/drive/sync` | Drive差分同期。runtime起動はしない |
| `GET/PUT /api/knowledge-console/budget` | 予算方針と残高観測 |
| `GET /api/knowledge-console/graph` | stable IDのnodes/edges |
| `GET /api/knowledge-console/events` | SSEによる状態イベント |
| `POST /api/knowledge-console/traces` | 一時テストデータから分析traceを開始 |
| `GET /api/knowledge-console/traces/<id>` | 使用した知識ブロック、stable ID、結果を取得 |
| `GET /api/knowledge-console/traces/<id>/events` | 再生用の順序付きアクセスeventを取得 |

APIは秘密値、Source本文、評価問題、ローカル絶対パスを返さない。変更APIはCSRF、Origin、Content-Type、revisionを検証し、監査イベントを必須にする。
