---
note_id: design-analysis-reuse-snapshot-package-plan
note_type: architecture-plan
title: 確定済みstepの再利用・入力スナップショット版2・保存パッケージ版2の計画
summary: 確定済みstep再利用・入力snapshot版2・保存package版2は実装済み。基点47ecd0a。最終の検証とQ23の同内容run再利用は本体計画の2026-10-16実施記録を参照。実モデル品質の採用とは区別する。
status: in-progress
updated: '2026-10-16'
feature: architecture
base_commit: 47ecd0a
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
---

# 確定済みstepの再利用・入力スナップショット版2・保存パッケージ版2の計画

2026-10-12、[[40-Design/10-Analysis/analysis-immediate-changes-plan|分析基盤の今やる変更の実施計画]]の点検から3件を分けた。3件とも実装済みで、実施記録と最終検証は本体計画を参照する。以下は設計時の契約を保持する。Q23により同一の科学的内容は既存runを再利用するが、異なる結果の推論参照・欠落検知・復旧条件は維持する。

## 1. 範囲と前提

| 計画 | 元の箇所 | 見つかった問題 |
| --- | --- | --- |
| 計画1 確定済みstepの再利用 | A-P4「確定済み成果はhash一致で再利用」 | 再利用の仕組みがない。`reused` 状態は一度も設定されない |
| 計画2 入力スナップショット版2 | B2「archive_snapshotはhashの参照だけ」 | 保存時まで固定入力の中身が残らない。版1と版2の結果の一致を確認していない |
| 計画3 保存パッケージ版2の読み手 | 第8節「保存した分析パッケージの形式（版2）」 | 既存の検証と読み手が版1の形を前提にしている |

前提は本体の第1節と同じ（1人用ローカルアプリ、SQLは追加だけ、テストは架空データ・一時DB、利用者DBは試験用データだけ）。

## 2. 計画1：確定済みstepの再利用

### 現状

- `start()` は新しいpipelineの全stepを `planned` で作り、すべて計算し直す。
- `reused` は遷移表と成功扱い（`TERMINAL_SUCCESS`）にあるが、入る遷移がなく、一度も設定されない。
- AnalysisStoreの保存は同じfingerprintの保存結果を再利用する。ただしparametersに `pipeline_id`・`plan_hash` が入るため、別のpipelineとは一致しない。
- 各stepの成果は `analysis_step_attempts.artifact_json` にある。保存（`_save_package`）と図の仕様（`_chart_specs`）は、最新の試行の成果を読む。

### 方針

- **対象は計算するstepだけ**：`participation`・`conversation_dynamics`・`manual_measurement`。`freeze_input`・`execution_binding`・`chart_specs`（IDにpipeline_idを含む）・`save_result`・`publish_result` は毎回実行する。軽いか、pipelineに固有のため。
- **再利用キー**：`fingerprint({ライブラリ, item_id, step_id, 計画中のstep定義, スナップショットのanalysis_hash（計画2）, 手法の版（REGISTRY_VERSION・pipelineの版・自動集計のalgorithm_version）, 束縛した定義のhash（manual_measurementのみ）})`。
- **元の試行の条件**：`committed` で、確定時に記録した成果hashが `artifact_json` と一致すること。元のpipelineが完了・失敗・取消のどれかは問わない。
- **判断はコア**：分析コアの純粋関数が、Runtimeの集めた候補から `reuse` か `dispatch` を返す（A-P2の `CoreDecision` 形式、reason_codeは `REUSED_COMMITTED_STEP` など）。候補は1回の読込で集める。
- **遷移**：step表に `checking → reused`（guard `step.reuse_verified`）を加える。本体のA-P3の `reserved` から `reused` を外す。
- **成果の持ち方**：元の試行の成果をコピーし、`reused_from`（元のattempt_id）と成果hashを記録する。下流の保存・図の仕様を変えずに済む。イベント `step_reused` を残す。
- **DB（追加だけ）**：`analysis_step_attempts` に `reuse_key TEXT NOT NULL DEFAULT ''` と `artifact_hash TEXT NOT NULL DEFAULT ''` を加え、`(reuse_key, status)` に索引を張る。既存の行は空のままなので、再利用の候補にならない。
- **利用者の操作**：開始要求に `reuse: "auto" | "none"`（既定 `auto`）を加える。画面のstep一覧に「再利用（元の実行の日時）」を出す。保存パッケージのparametersに、再利用したstepと元の試行IDを記録する。

### 確認

- 失敗または取消したpipelineの後に新しいpipelineを始めると、確定済みstepが再利用され、手法が呼ばれない（呼出し回数で確認）。
- 入力・定義・手法の版のどれかが違えば再利用しない。成果hashが合わない場合も再利用しない。
- `reuse: "none"` で全部計算した結果が、再利用した結果と一致する。
- 書込トランザクション数が、再利用しない場合以下に収まる。
- 「再利用」の表示を画面操作で確認する。
- 関連テスト：`test_analysis_milestones`・`test_analysis_generation_safety`・`test_analysis_recovery`。

## 3. 計画2：入力スナップショット版2

### 現状

- `build_analysis_pipeline_snapshot` は、`include_research_rows=True` で会話の分析全体を入れ、`archive_snapshot` を加える。1件約8.2MBで、うち計量テキストの詳細が約5.5MB。
- 読む箇所：
  - 手法step：`run_analysis_pipeline_method` → `analysis_csv_rows`・`method_results`。`automatic`・`manual` の多くの節、`segments`・`item`・版を `[]` で読むため、節がないとKeyErrorになる
  - `manual_measurement`：`segments`
  - O01：`automatic.overview`・`data_quality`・`segments`
  - `_save_package`：`archive_snapshot` と `analysis.algorithm_version`
- AnalysisStoreが `inputs/<snapshot_id>/input.json` を書くのは保存時だけ。受付から保存まで、固定入力の中身は `snapshot_json` にしかない。
- 自律分析は本番では別の初期分析（staged builder）を使い、このスナップショットを読まない。ただし `initial_builder` のない経路は同じ関数を使い、`research` を含む節を読む。

### 方針

- **版2は版1の部分集合にする。** 計量テキスト分析の行は必ず除く（既存の `include_research_rows=False` を使う）。発話分類・Transformer結果（約1.0MB）は、下の同値確認で影響がないと分かった場合だけ除く。入れる節は `SNAPSHOT_V2_SECTIONS` として1か所で定義し、スナップショットに一覧として記録する。
- **`archive_snapshot` はhash参照にせず、そのまま持つ。** 受付時点の固定入力が保存時まで残り、AnalysisStoreの `snapshot_id`（=保存結果の同一性）も変わらない。
- **`analysis_hash` を入れる。** 固定したanalysisのhashで、計画1の再利用キーに使う。
- **読込**：`_run` は版1と版2を同じ形で読む。必要な節がなければ受付時に `invalid_snapshot` で止める。新しい手法が別の節を必要とする場合は、`SNAPSHOT_V2_SECTIONS` に加える。
- **自律分析の配線**：`app.py` で自律分析へ渡す `snapshot_builder` は、版1と同じ作り方の関数に分ける。自律分析が版2の影響を受けないようにする。
- **旧コードとの関係**：版2は版1の部分集合なので、計量テキストの行を使わない限り旧コードでも読める。B2の別テーブル化（`snapshot_ref`）を行った場合だけ、旧コードで読めなくなる。
- B2の別テーブル化の判断（Q4：状態列の読込が1ms以上なら別テーブル）は変えない。

### 確認

- **同値**：架空の3会話（本体C5）について、版1と版2から作った次の値が一致する。
  - `participation`・`conversation_dynamics`・`manual_measurement` の成果
  - O01の計画文脈
  - `archive_snapshot`
  - 保存結果の `snapshot_id` とfingerprint
- **大きさ**：版1と版2を比べる。状態列の読込時間をQ4の基準で測る。
- **旧形式**：版1の既存行を読める。自律分析の既存テストが変わらず合格する。
- 関連テスト：`test_analysis_snapshot_commit`・`test_analysis_snapshot_fingerprint`・`test_analysis_definition_safety`・`test_analysis_milestones`。

## 4. 計画3：保存パッケージ版2の読み手と検証

### 現状の読み手

| 読み手 | 場所 | 版1を前提にしている点 |
| --- | --- | --- |
| 固定packageの検証・保存時の重複確認 | `analysis_store.verified_package`・`_verified_package` | `schema_version` がNoneか1でなければ拒否 |
| 型付き表の検証 | `_verify_typed_tables` | 型付き表（JSON）とCSVが1対1、件数が一致 |
| 表の読込 | `read_table` | `typed_tables` の参照先がpackage内にある |
| 生成Vaultへの公開 | `_publish_generated_vaults`（CSVの見出し）、`_publish_research`（`tables/<名前>.csv/json` へのリンク） | CSVが成果物としてある |
| 手法・図表ノート | `vault_registry`（`tables/*.csv` の成果物ID・行数・sha256） | 同上 |
| 保存結果の照会・ZIP書出し | `handlers/analysis_queries`（CSVの列数・件数の検査、packageの中身をそのままZIP化） | 同上。行がpackage内にある |
| 成果物の取得 | `/api/analysis/artifacts/<id>`、`static/analysis-storage.js`（`tables/measurements.csv` を探す） | 同上 |
| 自律分析・比較の公開 | `analysis_orchestration_publication`・`_publish_comparison` | 版の検査 |

### 方針

- **版の判定を集合にする。** `STORE_VERSION` を単純に上げると版1が読めなくなる。受け付ける版を `{None, 1, 2}` で判定し、版ごとに検証関数を分ける。版1の検証は変えない。
- **CSVは保存しない。** 版2のCSVは、書出し・ZIP・成果物の取得・Vault公開の時に型付き表から作る。保存する行は型付き表だけになる（Q11「同じ行は1回だけ保存」）。
  - 取得用に `/api/analysis/runs/<run_id>/tables/<名前>.csv` を加え、`analysis-storage.js` とVaultノートのリンクを版2ではこちらへ向ける。
  - Vaultノートには、型付き表の行数とhashを書く。
- **参照（F1〜F3）の照合**：参照は {表の種類, 鍵の集合のhash, 版, 行数, 行のhash} とする。読込時に行を集め、hashを照合する。
  - F2は本体第8節に従い、推論の実行IDと行キーの集合を参照に含める。本文・手法・モデルの版が同じでも再実行の結果は別版とし、保存済みpackageの参照先を最新結果へ付け替えない。参照した実行の行が欠けた場合、同じ条件の別実行や再推論で代用しない。
- **欠落時は自動で作り直し、照合できた場合だけ使う（2026-10-12 決定）。推測で埋めない。**
  - `verified_package` 自体は今までどおり再計算しない。参照先の行がない、またはhashが合わない場合は `missing_reference` を返す。
  - 読み手が `missing_reference` を受け取ると、F1（派生データ用SQLite、バックアップ対象外）の不足分を自動で再計算する。同じ解析器・版から作り、参照のhashと一致した場合だけ書き込む。その後、もう一度 `verified_package` で確かめてから表示する。
  - 再計算は画面の応答を待たせない処理で行い、作り直し中であることを表示する。同じ参照の作り直しは同時に1つだけにする。
  - 解析器の版が使えない場合、またはhashが一致しない場合は、「参照先の行がありません（作り直しても一致しません）」と表示し、値は出さない。
  - 会話の削除で消えたF2・F3の行は作り直せないため、欠落として表示する（試験用データのため許容、本体第1節）。
- **ZIP書出し**：版2は、型付き表から作ったCSVと参照先の行をZIPへ入れ、ZIP内で完結させる。
- **旧コードとの関係**：版2のpackageは、旧コードでは「形式に対応していません」として拒否される。壊れはしない。

### 確認

- 版1の既存packageが、上の表のすべての読み手で今までどおり読める。
- 架空の3会話で、版2の型付き表とその場で作ったCSVが、同じ入力の版1と値で一致する。
- 同じ本文・モデル・手法の版で異なる推論結果を2回保存する。各packageが指定した実行の行だけを読み、後の実行後も先のpackageの値・行数・hashが変わらない。同じ実行IDへの不一致の再保存は拒否され、参照行の欠落時に他の実行で補われない。
- F1の参照先の行を消すと、自動で作り直して照合し、読めるようになる。解析器の版を変えた場合や、hashが合わない場合は欠落表示になり、値を出さない。F2・F3の行を消すと欠落表示になる。
- Vault公開・ZIP書出し・成果物の取得・画面の表表示を、画面操作で確認する。
- 関連テスト：`test_analysis_storage`・`test_analysis_exports`・`test_analysis_publication`・`test_four_vaults`・`test_obsidian_layout`・`test_vault_coverage`・`test_analysis_fixed_run`・`test_analysis_history_viewer`。

## 5. 実施順

本体の段階表（第13節）に組み込む。

| 計画 | 本体の段階 | 前提 |
| --- | --- | --- |
| 計画2 | 段階2（B2と同時） | 架空データ（C5） |
| 計画1 | 段階3（A-P2の後） | 計画2の `analysis_hash`、A-P3の遷移表 |
| 計画3 | 段階4（F2〜F8と同時） | F1の派生データ用SQLite（段階2） |

## 6. 判断（2026-10-12 確定）

| 判断 | 決定 | 理由 |
| --- | --- | --- |
| 再利用の既定 | `auto`（`none` も選べる） | 失敗・取消の後に計算し直す手間をなくす。`none` で同値の確認もできる |
| スナップショットから除く節 | 計量テキストの行は必ず除く。発話分類・Transformer結果は同値確認の後に判断 | 確実に使わない部分だけで5.5MB減る |
| 版2のCSV | 保存せず、使う時に型付き表から作る | 二重保存をなくす本体Q11と一致する |
| 参照先の欠落 | 自動で作り直し、hashが一致した場合だけ使う。一致しなければ欠落表示 | 利用者の操作を待たずに読めるようにする。照合は `verified_package` で行い、固定packageの値を推測で埋めない原則は保つ |
