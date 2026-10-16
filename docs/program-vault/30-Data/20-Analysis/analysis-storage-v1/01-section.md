---
note_type: reference-section
status: current
feature: analysis-storage
verified: 2026-10-13
updated: 2026-10-13
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/obsidian
note_id: program-analysis-storage-v1-section-01
title: AI仕上げ・文章分析の保存契約 v1：AI仕上げ・文章分析の保存契約 v1
summary: AI仕上げ・文章分析の保存契約 v1。出典ノート「AI仕上げ・文章分析の保存契約 v1」の分割本文。
parent_note_id: program-analysis-storage-v1
source_path: 30-Data/analysis-storage-v1.md
source_sha256: 31b48be809af0922124aea608b12aec7e8f935b513ca61743fecd5d9e06bc885
source_body_lines:
- 1
- 65
split_on: '2026-10-11'
---

# AI仕上げ・文章分析の保存契約 v1：AI仕上げ・文章分析の保存契約 v1

親索引・状態・確認版：[[30-Data/20-Analysis/analysis-storage-v1/00-Index]]。必要な本文だけを取得する。


# AI仕上げ・文章分析の保存契約 v1

`ai_finishing.py`、`analysis_method_registry.py`、`analysis_store.py` と `app.py` の保存APIが実装済み。これは現在の動作の説明であり、[[40-Design/40-Storage/obsidian-plan|全体計画]]のうち差分取り込み・外部手法登録等は後続工程である。

## 利用の流れ

1. AI仕上げを選んで文字起こしすると、校正前後の本文・話者と工程の成否を自動記録する。議題の各要点には発話IDと生成時点の根拠を保存する。
2. 「分析・可視化」で保存済み会話を選び、研究質問・コード・除外を保存する。
3. 冒頭の見解の下にある「分析結果をObsidianに保存」を押す。全件の文章分析と実行条件を固定し、研究用Vaultに見解・表の抜粋・根拠を登録する。
4. KWICは「この検索をObsidianに保存」で、現在の検索条件に一致する全件を保存する。画面の50件表示に限定しない。
5. 任意のAI見解は生成成功時に自動記録する。「保存履歴」からJSON／CSVの取得、Obsidianでの閲覧、保存失敗の再試行ができる。
6. 統合実行では、確定した入力版からM0〜M7をサーバー側で進行する。手動モードは定義を下書き保存し、少数試行に合格した版を採用してから全件測定する。画面を閉じてもpipeline IDから状態を復元できる。

AI再生成は利用者の生成操作に限る。保存・履歴確認・再試行でAIを呼ばない。過去の会話を一括移行する機能ではなく、既存会話は保存ボタンを押した時点から履歴を蓄積する。

## 保存パッケージ版2（2026-10-13、段階4-2）

新規writerは`STORE_VERSION=2`。既存の版なし・版1はそのまま読み、既存ファイルを変換しない。以下の版1の記録に対し、版2では`result.json`を条件・算法・表／文書参照に絞り、文書は`documents/result.json`、F4〜F6・F8は型付き表1回、F1〜F3は固定DB参照にする。表形式自体は`table_format_version=1`を維持する。

CSVを固定packageへ保存せず、`/api/analysis/runs/<run_id>/tables/<name>.csv`・成果物取得・Vault公開・ZIPで生成する。Vaultに件数と行hash、生成CSVのURLを記録する。ZIPは参照先の全行とCSVを同梱し、内部manifestのhash・参照を同梱物へ合わせる。

`segment_labels`は実行ID・行キーで追記し、モデル／指示／設定・入力文脈・結果hashと出所を保持する。同じ実行IDの不一致は拒否し、後の推論で過去の参照を変更しない。`segment_embeddings`は同じ鍵の異なるBLOBを拒否し、packageは当時の入力hashとベクトルhashを照合する。研究者注釈の正本とノート所有権は従来の経路を維持する。

固定packageの検証は再計算せず、参照の欠落・不一致を`missing_reference`にする。読み手はF1だけ同じ解析器の版でbackground再計算し、一致した行だけ復旧して再検証する。作り直し中・不一致／版利用不可を表示し、F2・F3の欠落は再推論や別実行で補わない。旧コードへの戻しは版2を未対応として拒否する。実データ移行は今回行っていない。

## 保存先と正本（以下は版1の記録）

| 保存先 | 役割 |
| --- | --- |
| SQLite `library_items` | 最新の本文・話者・会話情報・分析条件・手動注釈（研究者が定義するTransformerテーマの見出し・手がかり語・シード発話、手動の発話種別・3スコアを含む）、互換用の最新AI見解、最新のTransformer結果、最新の発話分類提案 |
| SQLite `analysis_runs` | 実行ID、入力識別値、入力版、手法版、日時、モデル、完了・更新待ち・Vault状態 |
| SQLite `analysis_artifacts` | ファイルID・相対パス・SHA-256・バイト数・CSV行数。ファイル本体の重複保存はしない |
| SQLite `obsidian_notes` | アプリ生成ノートのID・パス・最後に書いたhash。手書き内容の保護に使用 |
| SQLite `analysis_pending_packages` | 書き出し中・失敗時だけ、再試行するための入力と結果を保持する一時的な記録。成果物の確定と同時に削除 |
| SQLite `analysis_definitions` | 手動測定定義の版、draft/adopted/retired状態、最後の少数試行。楽観的revisionで更新する |
| SQLite `analysis_pipeline_requests` | 確定したPlanEnvelope、ExecutionBinding、固定snapshot、M0〜M7の現在地、結果runとの関連 |
| SQLite `analysis_step_attempts` | stepごとの世代・試行番号・状態・成果物・HandlerReport・失敗理由。最新attemptだけを進行判定に使う |
| SQLite `analysis_pipeline_publications` | Input／Orchestrator／Visualizationごとの公開状態、package hash、エラー。計算済み結果と独立して再試行する |
| SQLite `analysis_pipeline_events` | pipelineとmilestoneの開始・確定・待機・完了を時系列で表示する監査イベント |
| `data/analysis_store/inputs/<hash>/input.json` | 実行時点の発話・注釈・実効話者情報と、保存済み原文。共通の入力版を再利用 |
| `data/analysis_store/runs/<id>/` | `manifest.json`、`parameters.json`、`result.json`、`tables/*.csv`。2026-10-05の版付き拡張では型付き全件表`tables/*.json`も保存する |
| `data/obsidian/ResearchVault` | 分析を読むためのノート・保存時点の引用・研究者自身のメモ |
| `docs/program-vault` | プログラム仕様・手法規約・テスト・運用方法。実会話を格納しない |
| 既存の `output`、`data/media` | TXT・JSON・SRT・Excel等の既存出力と音声・動画。従来どおり保持 |

`data` は実際にはDBファイルの親ディレクトリであり、通常は `MOJIOKOSI_DATA_DIR` で指定される。全件CSVはUTF-8 BOM付きで、文字列のCSV数式解釈を抑止する。JSONでは数値・文字列・`null`等を区別するが、CSV自体は型付きの保存形式ではない。

`analysis_store.csv_bytes`は`null`と空文字をともに空欄へ変換し、先頭の空白を除いた文字列が`=`・`+`・`-`・`@`で始まる場合は`'`を付ける。したがって、元の`=A`と`'=A`などをCSVから一意に復元できない。CSVは全件の表計算用出力として保持し、機械処理では対応する`result.json`の型付き値を優先する。型・欠測理由を必要とする再取り込みで、空欄や`'`を推測で元に戻さない。

### 型付き全件表の追加（2026-10-05、ADR-124）

実装は`src/gurumoji/analysis_store.py`の`table_package`、`AnalysisStore.save/read_table/verified_package`。新しく作成するrunは、各CSVに対応する`tables/<dataset_id>.json`を保存する。既存result.json内の配列が全件かを推測して重複排除せず、表の完全な読取口を明示する。`STORE_VERSION=1`を維持し、manifestへ`table_format_version=1`と`typed_tables`（dataset ID→JSON data/CSV export名）を追加する。

表のschemaは次のとおり。

| 項目 | 意味 |
| --- | --- |
| format / schema_version | `gurumoji.analysis-table` / 1。表形式の識別子と版 |
| dataset_id / run_id / input_snapshot_id | dataset・固定run・入力snapshotの対応。manifest/catalogと照合 |
| source_revision / analysis_revision | 保存した入力と注釈の版。現在の本文から補完しない |
| fields | CSVの列順。追加の行属性もJSON側では保持する |
| columns | 列名、observed_types、absent_count、null_count。観測型はnull/boolean/integer/number/string/array/object |
| row_count / rows | 全件数と全行。各行は`row_id`と元の型付き`values`を持つ |

行IDは`<dataset_id>:<1始まりの行番号>`で、固定run内で安定する。runを越えた同一発話の結合には元のutterance/segment/evidence IDを使い、この行番号で同一性を推測しない。null、空文字、0、文字列の数値、真偽値、配列とJSON風文字列を区別し、存在しないキーもnullへ補完しない。入力にある理由・根拠・単位・対象集合・分母は行属性またはresult/parameters JSONに保持する。未記録の欠測理由や単位は推測しない。空表のobserved_typesは空配列で、未観測をstring等と宣言しない。

CSVはこのJSON互換値から生成し、UTF-8 BOM・空欄化・数式対策を維持する。新しい出力のネストしたobjectのキー順はcanonical JSONから決まり、元のobjectの挿入順をCSVセルへ固定する契約ではない。旧CSVの内容・hashは変更しない。

読取りでは既存の全artifact hash/manifest検証に加え、表のschema・run/snapshot/revision・行数/行ID・観測型/欠測数とCSVとの一致を照合する。欠落・未知の版・JSONキー重複・非有限値・不整合は停止し、現在データから再計算しない。機械処理は`AnalysisStore.read_table(run_id, dataset_id)`を使う。既存artifact取得とZIPにもJSON表が含まれる。Researchの手法ノートには型付き全件データと表計算・共有用のリンクを併記し、研究者ノートの履歴保護経路を維持する。

旧runの閲覧/CSV取得/ZIPは互換維持するが、型付き表のないrunにread_tableを呼ぶと明示拒否する。既存の完了runを同条件で再利用してもJSON表を後付けしない。新しいpending packageは表形式版を固定し、失敗後も当時のデータで再試行する。同じ保存要求の再試行では、本文/分析revision、provider/model、アプリURLもpendingの保存開始時の値を使い、呼出し側の変更で部分成果物と不整合にしない。版のない旧pendingは従来のCSVのみの形式で復旧する。移行やDB schema変更は行わない。古いwriterは新形式のpendingを再試行できるとは扱わず、rollback前に保存処理を停止/完了し、未完分は対応する新版で復旧する。

[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]のFLOW-1のうち、この全件表保存だけを実装した。意味上の列型/単位の共通定義、親子run/依存manifest、汎用の後続分析接続まで実装済みという意味ではない。関連検証は`tests/test_analysis_fixed_run.py`、`test_analysis_storage.py`、`test_orchestration_publication.py`。
