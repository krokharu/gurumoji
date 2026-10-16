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
note_id: design-a100-knowledge-control-plane-plan-section-06
title: A100知識推論コントロールプレーン計画：6. 追加データモデル
summary: 6. 追加データモデル。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 270
- 374
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：6. 追加データモデル

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 6. 追加データモデル

既存の `knowledge_jobs`、`knowledge_commits`、`knowledge_packs` は維持し、次の投影・運用テーブルを追加する。

| テーブル | 主な項目 |
| --- | --- |
| `knowledge_model_profiles` | route、model_id、revision、context上限、既定token上限、同時実行数、active |
| `knowledge_work_orders` | task_type、expert_id、actor、model_profile_id、priority、approval_state、allowed_actions、input hash |
| `knowledge_run_attempts` | job/generation/attempt、state、開始/終了、checkpoint、token、wall/GPU時間、エラー分類 |
| `knowledge_runtime_sessions` | runtime kind、GPU、接続状態、started/last heartbeat/ended、stop reason |
| `knowledge_usage_ledger` | session/run、metric名、値、単位、source、measured/estimated/unknown |
| `knowledge_budget_policies` | 月次CU上限、1 session上限、reserve、deadline、idle終了時間、Pay As You Go許可 |
| `knowledge_evaluation_index` | expert/model/pack、repeat、カテゴリ得点、verdict、evaluation hash |
| `knowledge_events` | 連番、時刻、entity type/ID、event type、前後状態、actor、correlation ID |

生のSource本文、秘密情報、評価問題、答えはこれらの運用テーブルへ入れない。UI用集計はviewまたは再構築可能なprojectionにし、二重の正本を作らない。

## 7. 画面構成

### ダッシュボード

- A100 runtime: `未接続 / 接続待ち / 実行中 / heartbeat遅延 / 終了 / 要手動再接続`
- 現在のGPU、worker/model revision、キュー長、現在のjob、経過時間、最終heartbeat
- 今月のCU予算、観測済み使用量、予約量、安全余白、状態がunknownの項目
- 17専門家の完成度、評価pass数、候補数、要審査数
- 「キューが空なので終了推奨」「予算停止」「Source権利不足」等の行動可能な警告

### AI・専門家マトリクス

行を17専門家、列をモデルにし、各セルに以下を表示する。

- approved/candidate Claim数
- 必須知識の充足率
- 最新評価点とpass/fail
- 推論回数、成功、受理、採用、失敗
- 最新状態、最終実行日時、使用token、GPU時間
- 使用したPack、prompt、model revisionのhash

### ジョブキュー

- 並べ替え、保留、取消、再試行、別モデルへの新generation発行
- Source route、期限、想定token、予算予約、依存jobを実行前に表示
- 同じ成果の重複投入をinput hashで警告
- retryは同じ試行の上書きではなく、新generationまたは新attemptとして記録

### Colabセッション

- Notebookを開く、接続手順、Run all確認、Drive認可確認
- heartbeatと結果ファイルの最終確認
- runtime消失時の「再接続して再開」手順
- checkpointから再開可能なjobと、最初から再実行が必要なjobの区別
- 終了条件と、利用者がColab側でruntimeを切断するための案内

### 作業指示

- ローカルLLM、Codex、A100へ出すwork orderを同じ形式で管理
- 目的、対象expert、入力ID、許可操作、禁止操作、成果物schema、予算、完了条件を表示
- LLM出力から任意shellを実行しない。許可済み操作のJSONだけを受け付ける
- Codex作業は自動連投せず、利用者が承認したwork orderだけを開始する

### タスク追加と実行

画面上部に「タスクを追加」ボタンを置く。押すと次の項目を持つ入力パネルを開く。

- タスク名と作業指示
- 対象の専門家。複数選択時は専門家ごとに独立jobを作る
- 実行先: `ローカルLLM / Colab A100 / Codex`
- モデルprofileとmodel revision
- 使用するSource、Claim、Pack、入力revision
- 実行回数と目的: `通常 / 独立評価 / 比較 / 失敗再試行`
- 優先度、期限、最大input/output tokens、最大時間、最大CU
- 完了条件と期待する成果物schema

「追加」はdraftを保存するだけで、AI実行や外部送信を開始しない。保存後は一覧にタスクカードを表示し、カードに次の操作を置く。

- `実行`: preflightを通して一度だけキューへ投入する
- `停止`: 実行中処理へcancelを伝え、次の安全点で停止する
- `再実行`: 元の記録を残したまま新generationを作る
- `複製`: 同じ条件をdraftとして複製し、モデルや予算を変更できる
- `結果を見る`: Claim、根拠、評価、ログ、利用量へ移動する

`実行`ボタンを押したときは、権利route、Source hash、model revision、重複input、予算、retry上限、runtime状態をサーバー側で再検証する。成功したらボタンを即座に無効化して`queued`または`running`へ切り替え、二重クリックや通信再送で同じjobを二重作成しない。

ローカルLLMは利用可能なら直ちに開始する。A100はheartbeatが生きていればDrive queueへ送り、未接続なら`waiting_for_runtime`として保存して「Colabを開く」ボタンを表示する。Codexはwork orderの内容確認を表示し、利用者の実行確認後に開始する。通常の実行は1回のボタン操作で進め、外部送信、追加費用の可能性、private Sourceを含む場合だけ短い確認画面を挟む。

一覧には `下書き / 実行待ち / 実行中 / 要再接続 / 要審査 / 完了 / 失敗 / 停止` のタブを用意する。タスク追加後や再起動後もSQLiteから同じ状態を復元する。

### 知識トレース（別タブ）

- ダッシュボードには現在状態の小さい概要だけを置き、アニメーション操作は独立した「知識トレース」タブへ分ける
- 利用者がテスト用の質問・会話断片を入力し、専門家、モデル、Pack、最大ステップ数を選んで分析を開始する
- テスト入力は既定で一時データとし、利用者が保存を選ばない限りSourceやClaimの正本へ採用しない
- 知識を「対象データ」「専門家ルール」「分析手法」「適用条件」「根拠文献」「例外・限界」「プライバシー」「出力形式」「評価基準」「分析モデル」の大きなブロックに分ける
- 各ブロックには実際に選択したstable ID、revision、hashを紐付ける。表示用の大分類だけからアクセスを推測しない
- モデルへcontext packetを渡した時点、Claimを選択した時点、根拠を照合した時点をeventとして記録し、実際に起きたアクセスだけを再生する
- 現在アクセス中はcyanの発光、参照済みはgreen、未使用はgray、権利・privacy gateで除外した知識はamberで表示する
- Source、Evidence anchor、Claim、Expert、Job、Model、Evaluation、Packをstable IDでdrill-downできる
- 再生、一時停止、前後ステップ、速度、scrubber、アクセス履歴、知識ブロック別の結果寄与を表示する
- 「結果への寄与」はattention値と偽らず、採用Claim数、引用根拠数、ルール適用数など説明可能な集計根拠を併記する
- job開始、Claim選択、根拠照合、保留判断、評価、Pack収録をevent順に再生する
- `prefers-reduced-motion`に従い、停止ボタンと静止表示を用意する
- アニメーション座標やフレームを正本にせず、`knowledge_events`とcontext packet記録から再現する

可視化はローカルに同梱したCytoscape.jsまたは同等の小さなライブラリを使用し、CDNを必須にしない。最初は2Dグラフと時系列再生に限定し、3D表示は行わない。
