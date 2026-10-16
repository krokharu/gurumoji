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
note_id: design-a100-knowledge-control-plane-plan-section-01
title: A100知識推論コントロールプレーン計画：A100知識推論コントロールプレーン計画
summary: A100知識推論コントロールプレーン計画。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 1
- 30
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：A100知識推論コントロールプレーン計画

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。


# A100知識推論コントロールプレーン計画

## 実装状況（2026-09-29）

MVPはGurumoji本体から分離した開発専用アプリとして実装済み。
`run_knowledge_console.bat` から別プロセス・別Python環境・別ポートで起動し、
既定では `runtime/knowledge-console-dev/knowledge_builder/state.sqlite3` に
task・trace・eventを保存する。17専門家のサンプル指標、タスク追加、
A100タスクの保存順投入と並列実行、別タブの知識ブロック再生を提供する。

A100実行は公開HTTPトンネルを使わず、PCからDrive APIで共有フォルダへHMAC署名済み
`KCC_Task_*.json`を投入する(Drive for desktopの同期待ちを避けるため。
同期フォルダ指定は後方互換のフォールバック)。PC側のOAuthトークンはデータディレクトリの
`google_drive_token.json`に保存し、初回認可には`google_oauth_client.json`
(デスクトップアプリ用OAuthクライアント)が必要である。どちらもWeb UIの「接続セットアップ」から設定する。
WorkerはセッションごとのフォルダIDとQueue Secretを、共有フォルダ外のマイドライブ直下の非共有ファイル
`KCC_Session.json`へ書き、ノートブック出力には表示しない。PCは自アカウント所有かつ非共有の同名ファイルだけを読み、
Secretはメモリにだけ保持する(手動貼り付けは同期フォルダ等の上級設定として残す)。専用Colab Drive WorkerはA100と固定モデルを確認し、
3秒間隔でタスクを確認して最大4件を並列推論(llama-serverの4スロット、PC側も最大4件)し、署名済み`KCC_Result_*.json`を同じフォルダへ返す。
heartbeatはColabのDrive認証直後から別スレッドで30秒ごとに更新し、起動フェーズ(準備・ビルド・ダウンロード%・検証・読込・ready・failed/stopped)を含める。
起動時はモデルのダウンロードとllama.cppのビルド(sm_80のみ)を並行させ、ビルド済みllama-serverを
同じフォルダに`KCC_Cache_llama-server_*.tar.gz`として保存する。キャッシュは実行アカウント自身が所有し最終更新したものだけを再利用する。
モデル(GGUF)も同じフォルダに`KCC_Cache_model_*`として保存し、次回はDrive API(drive.mountは大容量で不安定なため不使用)で取得する。Driveの`sha256Checksum`が固定値と一致すれば手元の再ハッシュを省き、無い場合は手元で検証、取得失敗時はHugging Face(`HF_XET_FIXED_DOWNLOAD_CONCURRENCY=4`)へ戻る。初回のDrive保存はWorker準備完了後に並行して行う。
Workerノートブックは段階ごとのセル(準備・llama.cpp・モデル・サーバー・Worker・状態表示)に分かれ、実行中はセル内の状態表示(進捗・速度・残り時間・GPU・PCへの送信)を約1秒ごとに更新する(PCとの交信間隔は変えない)。失敗したセルはheartbeatでfailedを報告し、状態を保ったままそのセルから再実行できる。
共有フォルダ内のKCCファイルは用途別サブフォルダに分ける: `KCC_出力データ`(KCC_Result_*)、`KCC_モデルデータ`(KCC_Cache_*)、`KCC_一時データ`(KCC_Task_*・heartbeat)。WorkerがサブフォルダIDをKCC_Session.jsonで公開し、起動時に直下の旧KCCファイルを移動する。Gurumoji_*など他のファイルは動かさない。
heartbeatには実行中ジョブ(タスク名・経過秒)、待ち・完了・失敗件数、直近の完了(所要時間・tok/s)、GPUメモリを含め、Web UIの「A100 アクティビティ」に表示する。PCの確認は通常5分ごと、A100実タスク実行中だけ30秒ごと。経過時間は画面側で1秒ごとに加算する。
UIは新しいheartbeatを確認できない場合に実送信を開始せず、擬似完了へ
フォールバックしない。Compute Unitの実測と自動停止は引き続き未接続である。
