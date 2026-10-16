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
note_id: design-core-handler-routing-reorganization-section-21
title: コア・ハンドラー・ルーティング再編案：3. Jevの使い道と判断の限界
summary: 3. Jevの使い道と判断の限界。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1278
- 1310
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：3. Jevの使い道と判断の限界

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

### 3. Jevの使い道と判断の限界

| 用途 | 扱い | 根拠・成果物 |
| --- | --- | --- |
| ASRの誤り候補を絞る | 現行機能を維持。発話断片と周辺文脈から修正要否を判定 | `jev_review`、確率分布、model、版、発話ID |
| 生成AIの修正との比較 | 現行機能を維持。両方が指摘／生成AIのみ／Jevのみ／両方なしを提示 | `ai_jev_comparison`と元発話。多数決で修正を確定しない |
| 発話種別・テーマ候補・重要度・要確認度・機密らしさ | 現行の分類提案を維持。テーマは与えた候補内で判定 | 手動、ルール、Jev、Transformerの値を混ぜず、`segment_classifications`等へ保存 |
| 人が確認する候補の優先表示 | 将来拡張。既存の不一致・要確認値からコードで並べる | 追加のJev呼び出しを伴わず、並び順の理由と未判定を表示 |

Jevは音声を確認しておらず、ASRの正誤や研究上の妥当性を保証しない。応答の確率・confidenceを校正済みの正解率として扱わず、閾値は対象データで評価する。本文、手動コード、研究者の解釈は自動上書きしない。

機密らしさのJev判定はクラウド送信**後**に得られるため、送信してよいかを決める事前ゲートには使わない。送信可否はローカルの設定・必要範囲・除外処理で先に決める。Jevをオーケストレーター全体の承認者、手法選択の最終判断者、ローカル実行の代替にはしない。

### 4. ローカルデータの所在と正本

`<software>`は現在の`VaultRegistry.SOFTWARE_ROOT`、`<data>`は解決済みの`MOJIOKOSI_DATA_DIR`（未指定時は`runtime/data`）を表す。個人PCの絶対パスを埋め込まない。

| データ | 既存の所在・正本 | オーケストレーターでの利用 |
| --- | --- | --- |
| 共通契約・手法説明 | `<software>/50-Analysis-Methods/`、`08-Common-Knowledge/` | 入力・根拠・解釈の制約を確認。全ノートを毎回読む必要はない |
| 専門家の実行定義 | 同配下`10-Experts/<expert>/01-Expert.md` | `ExpertCatalog`で選択済みの専門家を解析し、適用条件・AI補助可否・許可段階を判定 |
| 専門家の補足知識・文献 | 専門家フォルダーの知識ノート、`20-Literature/` | 既存の参照解決と`knowledge_hash`を利用。全文をモデル入力へ複製しない |
| 調査経緯 | `30-Research-Logs/` | 人が出典の確認範囲を追う補助資料。毎回の実行入力にはしない |
| 対象会話・実行状態 | `<data>/library.sqlite3`、既存Workbench状態 | 会話ID、revision、除外条件、要求状態から必要な入力だけ取得 |
| 固定入力・結果・表 | `<data>/analysis_store/`の既存JSON／CSVと台帳 | `run_id`／`snapshot_id`／`artifact_id`で解決する正本。過去結果を上書きしない |
| 手法カード・実行記録 | `<data>/obsidian/OrchestratorVault/10-Methods/`、`20-Runs/` | 人が確認する出力。正本から生成し、ノートの編集だけで実行を開始しない |
| Vault位置・所有hash | `<data>/obsidian_layout/vaults.json` | `VaultRegistry`で参照・競合判定。別カタログを新設しない |
| provider設定・資格情報 | 現行の`config/tokens.json`と`TokenConfig` | 接続層だけが秘密値を解決。AI入力・Vault・実行manifestへキーを含めない |

**専門家定義はSoftware Vault、OrchestratorVaultは生成された手法カード・実行記録、機械処理の結果はDBと成果物、という現行の役割を維持する。** 同じ定義をOrchestratorVaultへコピーして第2の編集元を作らない。別のローカルデータが後で指定された場合は、所在・所有者・読取形式を確認して必要な参照だけを追加する。

現行の`method_experts.ai_context`は、許可されたAI段階、短いbrief、禁止結論、解決済み文献ID等の構造化した指示を作る。文献・知識ノートの全文を送らない仕様を維持する。「ローカルに知識がある」ことと「その全文をLLMが読んだ」ことを区別して表示する。
