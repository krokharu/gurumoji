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
note_id: design-a100-knowledge-control-plane-plan-section-03
title: A100知識推論コントロールプレーン計画：1. 決定
summary: 1. 決定。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 156
- 183
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：1. 決定

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 1. 決定

専用Web UIのソースは、開発中は `feature/knowledge-control-plane` ブランチでGit管理する。Gurumoji本体の画面・ルートへ統合せず、独立した開発ツールとして管理する。長期運用するソースをGit管理外にはしない。

Gitへ入れないものは、実行時DB、取得した論文、モデル、ジョブZIP、推論結果、Google OAuth資格情報、APIキー、ログ、利用量の生データである。開発アプリのデータは `KNOWLEDGE_CONSOLE_DATA_DIR` から解決し、未指定時は `runtime/knowledge-console-dev/` を使う。現在の `output/knowledge-*` は、内容と権利を確認してから実行時データ領域へ移し、今後の誤追加を `.gitignore` で防ぐ。

専用Web UIと専用アプリは別実装にしない。同じ独立ローカルWeb UIを次の2形態で使う。

1. ブラウザーから開く管理画面。
2. 同じ画面をPWAまたは軽量デスクトップシェルから開くインストール可能なアプリ。

Flask、HTML、JavaScriptを使うが、GurumojiのFlaskアプリには登録しない。専用プロセスは `127.0.0.1:7861`、専用仮想環境は `.venv-knowledge-console` を既定とする。ネイティブ通知や常駐トレイが必要になった段階でだけデスクトップシェルを追加する。

## 2. 目的と完成条件

この管理機能を、既存の `knowledge_builder`、`KnowledgeJobStore`、Colab ZIP transport、Qwen3 worker、評価契約の上に構築する。別の知識DBや別のジョブ正本は作らない。

完成条件は次のとおり。

1. 17専門家 × 使用モデルごとに、知識量、評価点、最終推論状態、推論回数、採用数、失敗数を確認できる。
2. A100、ローカルLLM、Codexに割り当てる作業を手動で選び、モデル、回数、同時実行数、token上限、時間上限、Compute Unit予算を設定できる。
3. 画面からタスクを追加し、タスクカードの「実行」ボタンで検証・キュー投入・開始まで進められる。
4. Colabが停止しても、受理済みCommitやチェックポイントを失わず、同じgenerationを重複採用しない。
5. Colabとの自動処理はGoogle Drive上の要求・結果・heartbeatの取得に限定し、通常版ColabのUIや利用制限を迂回しない。
6. 推論結果を直接Obsidianへ上書きせず、候補、審査済み、採用済み、Pack収録済みを区別する。
7. Source → Claim → Expert → Model run → Evaluation → Packのつながりを、状態変化とともにアニメーション表示できる。
8. 資格情報、private Source、評価問題と答え、ローカルパスを画面API、Colab bundle、ログへ漏らさない。
