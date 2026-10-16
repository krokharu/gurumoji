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
note_id: design-a100-knowledge-control-plane-plan-section-09
title: A100知識推論コントロールプレーン計画：12. 実装フェーズ
summary: 12. 実装フェーズ。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 447
- 512
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：12. 実装フェーズ

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 12. 実装フェーズ

### P0: 保全と棚卸し

- 現在の未コミット `knowledge_builder`、テスト、`output/knowledge-*` を内容別に棚卸しする。
- ソース、再現用の小さい匿名fixture、runtime/private成果物を分離する。
- runtime成果物を `<data>/knowledge_builder/` に統一し、Git除外規則を追加する。
- 現在のJobStoreを読み取り専用監査し、accepted Commit、17専門家、Claim/Source数、孤立stageを確認する。

受入条件: 既存DB・成果物を失わず、秘密・論文・モデル・実結果がGit候補に現れない。

### P1: 読み取り専用Console

- 独立したFlask開発アプリ、summary API、expert/model matrix、job/session一覧を実装する。
- 既存DBからのprojectionだけで表示し、状態変更ボタンはまだ置かない。
- unknownと0を区別し、hashと版を表示する。

受入条件: CLI監査結果と画面集計が一致し、Source本文をAPIへ出さない。

### P2: イベントとアニメーショングラフ

- `knowledge_events`と既存状態からのbackfillを実装する。
- 独立した「知識トレース」タブに、テストデータ入力、知識ブロック、filter、drill-down、SSE更新を追加する。
- context packetと選択Claimに基づくSource→Claim→Expert→Evaluation→Packのアクセスevent replayとreduced-motionを追加する。

受入条件: 同じテスト入力・固定版・event列から同じアクセス表示を再構築できる。アクセスしていない知識を参照済みと表示せず、アニメーション停止時も全情報を読める。

### P3: 手動キューとモデル管理

- model profile、work order、予算policy、タスク追加フォーム、実行ボタン、retry/cancelを追加する。
- ローカルLLMのschema限定plannerを接続する。
- Codex用work orderはコピー可能な指示と成果物受入条件まで生成し、実行開始は人が承認する。

受入条件: タスク追加後に再起動してもdraftが残る。実行ボタンの二重クリック・HTTP再送でもjobは1件だけ作られる。許可外route、予算超過、重複input、retry上限超過を実行前に拒否する。

### P4: Drive自動搬送と再開

- ローカルDrive adapter、heartbeat、checkpoint、結果importを実装する。
- 既存ZIP transportのclosed envelope、hash、generation lockをそのまま使用する。
- 切断、古いheartbeat、部分upload、重複結果、期限切れ、再接続後再開を一時Driveで検証する。

受入条件: runtimeを意図的に止めても、受理済み結果を重複採用せず、未完了jobだけを再開できる。

### P5: 予算停止とセッション管理

- CU観測、予測、reserve、soft/hard limit、idle終了を実装する。
- session開始時のpreflightでGPU、VRAM、model revision、空きディスクを検証する。
- 空キュー時の定期GPU probeを削除する。

受入条件: unknown利用量ではfail-openせず、予算超過jobを開始せず、終了理由を監査できる。

### P6: インストール可能アプリ

- PWA manifest、ローカルlauncher、更新手順を追加する。
- 必要性が確認できた場合だけデスクトップ通知とsystem trayを追加する。

受入条件: ブラウザー版とアプリ版が同じAPI・権限・画面を使い、別の状態を持たない。

### P7: Obsidian公開と運用受入

- approved/packed状態だけからOrchestratorVault用の小さい管理ノートを生成する。
- `VaultRegistry`を知識ノート種別へ拡張し、共通の生成ノート競合規則を通す。Software Vaultへは書かない。
- 一時Vaultで公開、stale、欠落、競合、復旧を検証する。

受入条件: 同期が推論を起動せず、private Sourceと実行秘密をノートへ出さず、stable IDで根拠まで追える。
