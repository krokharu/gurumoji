---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-08
title: Gurumoji 改善セッション：同日：AI反復が0回だった理由
summary: 同日：AI反復が0回だった理由。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 173
- 190
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：AI反復が0回だった理由

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：AI反復が0回だった理由

- 前回のテスト範囲を基本分析に絞ったため、自律分析は未開始だった。`output/malatang-smoke/run.py` は `group_analysis_for_row` と参加量／会話動態のmethod adapterを呼ぶが、`AnalysisOrchestrationService.start`、`run`、AI runnerは呼ばない。method adapterは既存集計とCSVを結果形式へ変換するだけで、Coreの反復処理ではない。
- 現行の開始経路は `POST /api/library/<item_id>/analysis/orchestration` → `service.start` → 保存・schedule → `_run_analysis`。Coreタスク登録直前に `iteration` を加算する。通常の基本分析から自動でこの経路へ入る実装ではない。`max_iterations` は指定する場合に1以上を要求し、前回はその設定検証自体を通っていない。
- 前回と同じローカルDBをSQLite読取専用で照合し、`orchestration_*` テーブルなし、対象itemの旧AI見解request 0件を確認。既存pipeline requestは2件あるが、別の台帳であり自律反復の回数には換算しない。この調査から別DB・別環境の実行履歴までは断定しない。
- 前回の「AIループ0回」はテストでAI開始処理を呼ばなかったことの説明であり、保存runのiterationを測定した数値ではなかった。接続障害、準備状態draft、回数制限で停止したという根拠はない。調査中もAI推論・実行開始・実DB/Vaultの書き込みは行っていない。本体変更なし。

### 同日：実AI開始・反復試験とWindows修正

- 目的は基本分析だけの確認から、既存POST開始・Core・批判レビュー・次のCoreという実経路を検証すること。基点は引き続き`main / 2f2479ca638c569f6978bec47c509646bd92ff67`、変更は未コミット。再現用に`scripts/test_saved_autonomous_analysis.py`を追加し、元DBは読取専用、SQLite backup先だけに追加台帳を作る。媒体参照をコピーで外し、Vault公開を禁止する。AI応答のmock置換・クラウド送信なし。
- WindowsでCSVのsys.maxsizeがC long幅を超えてimport失敗したため、受理される幅へ下げる。raw SQLite factoryのconnectionもcommit/rollback後に閉じ、Windowsの一時DB削除失敗を修正した。Handlerのcall_timeout_secondsを実通信workerへ渡す。Coreの空要約・解釈担当へのlabel_frequency指定は登録前に隔離する。モデル用プロンプト・schemaで次の作業/終了判断、終了理由コード、発話IDと根拠IDの使い分けを明示した。
- 実モデルの初期失敗も保持する。GPT-OSS 20Bの既存8192枠では要求拒否、65536枠/部分GPUでは通信timeout、32768枠では全項目が空のCore応答を得た。空応答を分析成功としない。Qwen3 8Bは推論ONや文字列だけの/no_thinkで長時間生成/timeoutになり、実capabilityのoff設定からreasoning_effort=noneを送る試験へ切り替えた。停止した試験は取消し・timeoutのまま保存する。
- 原文24件にしても全323件の根拠ID索引が残り、後続criticで入力枠超過のHTTP 400が発生した。context_index_limitを追加し、原文と索引の省略を別々に記録する。既定0は従来の全索引。全量固定snapshotは323件を保持する。索引の外を順次読む処理は追加していない。
- **反復動作は確認済み、分析完了は未達**。最終の実試験は`output/malatang-autonomous/20261005T003035Z-4120cd7e/result.json`、run `run_cd826f0356f34003993b0e24d7c3c177`。Qwen3 8B、実ロード32768枠、並列1、原文/索引各48件。Core成功2回、critic成功1回、実測AI呼出し3回、input 72,651/output 1,802 token、約67秒。不正/失敗タスク0。criticが根拠不足を指摘し、Coreがその指摘への採否を返さなかったためhuman_review_requiredで停止した。厳格なpassed=falseを保持し、全323発話の解釈完了や固定成果物保存成功とは扱わない。24件の前試験もCore2/critic1が成功し、人の確認待ちで停止した。
- 元入力hashは前後とも`7dc5067452160de02239ef10a9ee7c2861ccbe49b00c96f197085bea9775d7ef`、revisionも維持。実利用者データは読取りだけ、書込みは試験コピーのみ。config/tokens.jsonを変更せず、試験モデルのロード設定は一時変更とする。GPU実測は生成中99%/VRAM約11GBで、コード調査・unittest・待機時の低使用率と区別する。
- 最終の関連unittestは128件成功・失敗0（24.415秒）。対象はCSV、実試験の判定、analysis_queries、fixed_run、orchestration本体/adapter/route/integration、review、durable integration。git diff --checkと対象Python compileも成功。保存台帳からの再判定、変更コードhash、試験module一覧は同試験ディレクトリのverification.jsonに記録。厳格な元result.jsonは書き換えない。終了時にGPT-OSS 20B・8192枠・並列4・TTL3600秒を再ロードし、idle/queued 0を確認した。
- 音声文字起こし、話者分離推論、ブラウザーUI、実Vault公開、研究者による確定解釈は未実行。次の課題は未提示範囲の参照と、モデルの批判応答欠落への対処。反復回数を増やすだけで研究上の根拠不足は解消しない。
