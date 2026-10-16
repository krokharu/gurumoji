---
note_type: reference-section
status: current
verified: 2026-10-05
updated: 2026-10-06
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
note_id: module-analysis-orchestration-section-03
title: Core・Handler自律分析と実行状態UI：API
summary: API。出典ノート「Core・Handler自律分析と実行状態UI」の分割本文。
parent_note_id: module-analysis-orchestration
source_path: 20-Modules/analysis-orchestration.md
source_sha256: 145ca8522ee906fad2e00812f0dcd27f6c2c4f143f52b9c715fc81da9060e96c
source_body_lines:
- 70
- 95
split_on: '2026-10-11'
---

# Core・Handler自律分析と実行状態UI：API

親索引・状態・確認版：[[20-Modules/20-Analysis/analysis-orchestration/00-Index]]。必要な本文だけを取得する。

## API

批判者のissue対象ID/版は、今回のreview_targetに一致する単一候補を生成用JSON schemaへ渡す。共有schemaは変更せず呼出しごとにコピーし、別run/別版へ制約が漏れない。返答の対象版・状態と指摘一覧の整合性は採用前にも検証し、不正応答を後から補正して成功扱いにしない。

Coreのcritique_responses/label_decisionsも今回実在するissue_id/proposal_idを生成候補にする。存在しない場合は配列のmaxItems=0。生成時の制約に加え、既存の採用前参照検証を維持する。架空の批判応答やラベル判断を修復して採用しない。

基本パス: `/api/library/<item_id>/analysis/orchestration`

- POST: 開始。JSON条件、`request_id`、入力revision、`question`、停止設定、モデル設定を渡す
- GET: 保存済みrun一覧。モデル呼出しなし
- `/<run_id>` GET: 状態、役割、タスク、イベント、usage、批判応答
- `/<run_id>/cancel` POST: 新規発注停止と取消し
- `/<run_id>/resume` POST: 初期段階/分析の明示的な復旧。状態により確認が必要
- `/<run_id>/publication/retry` POST: 同じ封印済み成果物・同じ公開範囲の保存/公開だけ再試行。条件変更不可
- `/<run_id>/results` GET: 初期版と保存履歴
- `/<run_id>/results/<result_id>` GET: 個別結果
- `/<run_id>/export.json` / `export.md` GET: 完全履歴JSON / Obsidian用ノートのダウンロード

画面更新・アニメーションはstatus/eventフラグとCSSのみ。表示のためのLLM呼出しは0回。token数はproviderの実測を受信した場合だけ表示し、未計測や一部不明を0扱いしない。

開始条件に `context_evidence_limit`（1〜120、既定120）と `context_text_limit`（1〜60000文字、既定60000）を指定できる。ローカルモデルの入力枠に合わせて1呼び出しの原文量を減らしても、全量の固定入力は保持する。各contextの `coverage` は利用可能件数・提供件数・省略件数を区別する。未読範囲を既読や確認済みにしない。これらは文字数・発話数の上限であり、根拠索引や結果履歴も含む総token数の保証ではない。

`context_index_limit`（0〜120、既定0）は各呼出しの根拠ID索引を先頭から制限する。0は従来通り省略なし。原文だけを減らしても323件のランダムID索引が入力枠を圧迫したため追加した。coverageのindex_available_count/index_provided_count/index_omitted_countに索引の省略を別記する。固定入力全量は保持するが、索引外の発話を自動で順次読む機能はない。制限した範囲の試験を全発話の分析完了と扱わない。

Handlerの `call_timeout_seconds` は実際のAI通信へ渡す。通信worker側の上限600秒は残る。既定の通信240秒で一律に切る旧動作からの修正であり、内部再送を追加しない。
