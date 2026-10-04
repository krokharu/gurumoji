---
note_id: module-analysis-orchestration
note_type: module
title: Core・Handler自律分析と実行状態UI
summary: 固定分析を残した自律分析、初期全量保持、批判応答、停止・復旧の契約。
status: current
verified: 2026-10-04
schema_version: 1
tags:
  - gurumoji/program
  - gurumoji/analysis
---

# Core・Handler自律分析と実行状態UI

基点は `0d9239ac9d041d78d298c68a235738b3fe549a2a`。初版は `dot/core-handler-orchestration-20261004`。継続版は `dot/core-handler-durable-output-20261004`（基点 `f3e16ba`）。実装と検証の最新状態は [[60-Operations/dot-cloud-development-handoff]] の自律分析節を参照する。

## 責務と既存機能

- Coreは問い、現在の見解、矛盾、不足、追加案、批判への採否理由、分析上の終了を返す
- HandlerはPythonコード。正式タスク、固定入力、予算、並列数、保存、停止、復旧を扱い、AIとして表示しない
- 会話解釈・独立検証・批判者は既存JSON AI transportを使う。役割ごとの実provider/modelを固定し台帳・画面へ表示する
- 数量・統計系統は既存決定的集計adapterと、版付きラベルの実再集計 `label_frequency` を利用する。モデル名は捏造せず、Python集計と表示する
- 従来M0–M7、測定定義、safe publication、再試行世代管理は残る。自律分析は実行設定から選ぶ追加経路

## 実行・保存

`src/gurumoji/analysis_orchestration.py` が追記型結果と状態機械、`services/analysis_orchestration_adapters.py` が既存providerとの境界、`web/analysis_orchestration_routes.py` がHTTPを担当する。SQLiteの追加テーブルを使い、既存カラムの削除・型変更はしない。

追加テーブルは `orchestration_initials`、`orchestration_runs`、`orchestration_tasks`、`orchestration_results`、`orchestration_events`、`orchestration_decisions`、`orchestration_issues`、`orchestration_responses`、`orchestration_label_versions`、`orchestration_label_proposals`、`orchestration_usage`。DBを通常バックアップしたうえで既存起動経路のCREATE IF NOT EXISTSで追加する。旧版アプリはこの追加データを読まず、既存形式を保つ。新機能の利用をやめる場合も追加履歴を削除せず保持する。

初期分析は入力版・テンプレート版・設定に紐付く全量スナップショット。反復結果で初期版を上書きしない。タスク、結果、主張、根拠、批判、採否、ラベル版はそれぞれ参照可能にする。不正な参照・形式は正常な採用結果にしない。

専門家の追加案はCoreの判断を経てHandlerが正式発注する。独立検証は初期/Coreの期待結論を見ない。批判者は対象版と根拠を見て、指摘なし・未判定も返せる。終了案への批判とCoreの採否理由を残し、手動停止や上限到達ではレビューを無断追加しない。

### 初期構築のcheckpoint

本番経路は `base → linguistics → statistics → content → snapshot` の5段階。runを先に保存してからバックグラウンドで実行し、段階の完了出力・入力hash・前段hash・アルゴリズム版を保存する。再起動/段階失敗では停止し、利用者の再開操作で未完段階だけを実行する。完成済みの数量・統計を再計算しない。初期全量snapshotが確定するまでCoreは呼ばない。保存rowと選択済み専門知識を固定し、段階間で新しい版を混ぜない。

追加テーブルは `orchestration_initial_builds`、`orchestration_initial_stages`。旧版の確定済み初期snapshotも保持・再利用する。

モデル呼出しとHTML表示は分離する。`app.call_orchestration_ai_json` は1タスクにつき1回のtransport dispatchとし、既存HTTP clientの内部再送をこの経路だけ無効にする。不明な外部実行を勝手に再送しない。既存AI経路の再試行方針は変更しない。

## 停止設定

時間、Core巡回数、重要度、AIお任せの4モード。AIお任せでは時間・巡回数を無上限にできるが、呼出し数・タスク数等の運用上限と手動停止は残る。重要度の高/中/低は未校正の暫定基準であり、確率・LLM自信・p値ではない。実費用を確実に取得できないため金額上限は受理せず、呼出し数・タスク数の上限で制御する。

ブラウザーを閉じても取消しにはしない。再表示は台帳を読み、実行を再発注しない。プロセス中断や応答不明は、完了済み結果を残して復旧判断を待つ。時間上限到達後の外部処理の物理的停止はproviderにも依存する。

## API

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

## 機密性・限界

既定はlocal_only。クラウドAIへ原文・分析結果を送る場合、選択providerと明示同意を必要とする。認証情報は既存設定から都度読み、run設定へ保存しない。会話中の命令は実行指示として扱わない。

この版は探索分析。未使用検証データの隔離を保証する確認的統計ワークフローは実装しないため、confirmatory要求は拒否する。統計手法は実装済み能力に限定し、自由なPython実行・ネット検索・追加インストール・自己権限拡大は許可しない。

ラベル案と採用版は自律分析run内で保持し、元の研究者ラベルを勝手に書き換えない。`label_frequency` は全対象または明示した根拠ID範囲で、現在の固定ラベル版から度数・分母・欠測を実際に再計算する。旧版依存結果はstaleとして残す。既存の参加量・時系列adapterは初期全範囲の参照に限定し、部分範囲やラベル依存の再計算へ転用しない。Obsidian用ノートは完全台帳のダウンロードに加え、新runの明示選択で既存安全経路から公開できる。元データ・研究者所有ノートの保護と既存出版経路を維持する。

## 固定成果物と4先一式の公開

正常に分析完了したrunは、台帳全量を一度封印し、既存 `AnalysisStore.save(publish=False)` で固定packageへ保存する。原結果、初期版、批判/採否、ラベル各版は `result.json` の `orchestration` に完全保存し、可読ノートには要約/根拠/未解決批判を投影する。封印後のイベントや遅延結果を再試行時に取り込まない。

Vault公開は新runの既定OFF。選択できる単位は **Input・Orchestrator・Visualization・Researchの4先一式**。内部requested_targetsは既存の3先配列、effective_writersはResearchを含む4先。個別Vault選択ではない。Researchには発話本文も複製する。旧runの公開範囲を後から拡張しない。

追加テーブルは `orchestration_publications`、`orchestration_publication_attempts`。公開先/封印hash/世代/試行主体をguardし、`AnalysisStore.publish(reuse_completed=True)` と既存生成ノートpolicyを使用する。汎用の直接再公開/refreshから専用guardを迂回させない。保存成功、分析完了、公開処理完了を別々に表示する。

一部失敗は同じpackageとscopeで公開だけ再試行し、AI・統計・初期構築を再実行しない。既存契約に合わせ4writer一式を再確認するため、失敗先だけの再試行ではない。編集済み生成ノートの履歴を保存し、削除済み生成ノートを勝手に復元しない。writerがpublishedでも全ノート存在の保証ではない。

入力変更後も固定成果物は保持してstaleを示し、Vaultへの公開は競合として止める。取消/停止/失敗runを自動公開しない。実際の私有Vaultや移入研究Vaultに接続した検証は行っていない。

## 検証

合成会話・一時DB・mock providerのみ。対象は `tests/test_analysis_orchestration*.py`、`tests/test_orchestration_review.py` とUI回帰。実際の外部AIの品質・費用・Windows実機は別途検証する。具体的な成功/失敗/未実行は運用引継ぎに記録する。
