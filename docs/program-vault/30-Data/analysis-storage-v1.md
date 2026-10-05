---
note_id: program-analysis-storage-v1
note_type: data-model
title: AI仕上げ・文章分析の保存契約 v1
summary: AI仕上げと文章分析の固定保存、ResearchVault公開、保存履歴の契約を定める。
status: current
feature: analysis-storage
verified: 2026-10-05
updated: 2026-10-05
schema_version: 1
tags:
  - gurumoji/program
  - gurumoji/analysis
  - gurumoji/obsidian
---

# AI仕上げ・文章分析の保存契約 v1

`ai_finishing.py`、`analysis_method_registry.py`、`analysis_store.py` と `app.py` の保存APIが実装済み。これは現在の動作の説明であり、[[40-Design/obsidian-plan|全体計画]]のうち差分取り込み・外部手法登録等は後続工程である。

## 利用の流れ

1. AI仕上げを選んで文字起こしすると、校正前後の本文・話者と工程の成否を自動記録する。議題の各要点には発話IDと生成時点の根拠を保存する。
2. 「分析・可視化」で保存済み会話を選び、研究質問・コード・除外を保存する。
3. 冒頭の見解の下にある「分析結果をObsidianに保存」を押す。全件の文章分析と実行条件を固定し、研究用Vaultに見解・表の抜粋・根拠を登録する。
4. KWICは「この検索をObsidianに保存」で、現在の検索条件に一致する全件を保存する。画面の50件表示に限定しない。
5. 任意のAI見解は生成成功時に自動記録する。「保存履歴」からJSON／CSVの取得、Obsidianでの閲覧、保存失敗の再試行ができる。
6. 統合実行では、確定した入力版からM0〜M7をサーバー側で進行する。手動モードは定義を下書き保存し、少数試行に合格した版を採用してから全件測定する。画面を閉じてもpipeline IDから状態を復元できる。

AI再生成は利用者の生成操作に限る。保存・履歴確認・再試行でAIを呼ばない。過去の会話を一括移行する機能ではなく、既存会話は保存ボタンを押した時点から履歴を蓄積する。

## 保存先と正本

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

[[40-Design/core-handler-routing-reorganization-plan]]のFLOW-1のうち、この全件表保存だけを実装した。意味上の列型/単位の共通定義、親子run/依存manifest、汎用の後続分析接続まで実装済みという意味ではない。関連検証は`tests/test_analysis_fixed_run.py`、`test_analysis_storage.py`、`test_orchestration_publication.py`。

## ノートと根拠

ResearchVaultの会話は`10-インタビュー/I###-<名前>/`にまとめる。概要は`I###-概要.md`、分析の入口は`I###-分析まとめ.md`、実行結果は同じフォルダーの`履歴/分析/<run-id>/`に保存する（`ObsidianLayout.note_path/analysis_dir`）。実行ノートから各`method-<id>.md`に移動できる。手法別ノートには見解、根拠、主要表の先頭10行・最大8列、分析単位・解析器、全件データ、限界を記録する。KWICの引用表示は先頭50件、AI仕上げの変更リンクは先頭100発話までで、全件はJSON／CSVに残る。旧`20-Conversations`・`40-Analyses`は移行前の配置。

引用は各インタビューフォルダーの`履歴/引用/<source-hash>/part-0001.md`に200発話ごとに保存する（`ObsidianLayout.source_dir`、`AnalysisStore.source_notes`）。旧`25-Sources`は移行前の配置。原文の文字列を維持してMarkdown用にエスケープし、発話IDはUTF-8の16進表現を使った`s-<hex>`ブロックIDに対応付ける。AIの根拠は生成当時の本文を使う。現在の本文・時刻・話者が異なる場合、リンクから現在の音声へ自動で進めず保存済み引用を案内する。

プロパティは単純なYAML値にし、大量のIDや入れ子の結果はJSONに置く。リンクはVault内のノートパスとブロックIDで生成する。[Obsidian公式：プロパティ](https://help.obsidian.md/properties)、[内部リンクとブロック参照](https://help.obsidian.md/links)

各CSV／JSONにはアプリで取得するリンクだけを付ける。端末固有の `file:///` パスは、PCのユーザー名などがVaultに残り、移動で切れるため書かない（OBS-12）。音声リンクとアプリからの取得にはサーバーの起動が必要。「Obsidianで開く」はローカルパスへのアクセスが許可された環境で表示する。[Obsidian公式：URI](https://help.obsidian.md/uri)

## AI仕上げと分析の規約

Whisper原文を先に保存し、Obsidianの専用作業ノートから仕上げを実行する。対象は各インタビューフォルダーの全文・アウトライン・操作ノートで、生成版は`履歴/仕上げ/`に残す。旧`15-Finishing`は移行前の配置。一般的な双方向同期とは分離し、人の既存ノートを自動更新しない。現在の作業版は概要・状態ノートから開く。操作、原文保護、重複実行防止、競合時の扱いは [Obsidianで文字起こしを仕上げる](../../OBSIDIAN_FINISHING.md) を参照する。

- 校正はID・発話順・話者・時刻を固定し、明白な誤変換と句読点を直す。要約・解釈・テーマ付与は別工程とする。長い単独発話も分割し、末尾まで処理する。失敗した分割片があれば校正結果全体を採用しない。
- 話者の修復を選んだ場合は校正前の本文を独立した入力に用いる。修復したラベルと原ラベルを変更CSVに残す。
- Jev比較を選んだ場合は、校正前の同じ発話をTypeSafeへ送り「修正が必要／修正不要」の二択だけを判定する。現行AIの変更有無と合わせた4区分、確率、確信度、モデル、使用量を`jev_review`と`ai_jev_comparison.csv`へ固定保存する。音声を判定した結果として扱わず、原音確認を必須の注意事項にする。
- 発話分類は、手動確定値とテンプレート規則・Jev・Transformerの提案を別レイヤーで保持する。発話種別、重要度、要確認度、機密らしさの0〜100値は確認用スコアであり、校正済み確率や法的な機密判定ではない。AI提案を手動注釈へ自動反映しない。
- 議題は各要点の根拠IDをサーバーで検証する。時刻を原文から計算し、`bullet_evidence` と `evidence` に根拠を保存する。既存の根拠IDがない議題には「旧形式」と表示する。
- AI見解は研究質問を優先し、1項目に1つの主張と根拠IDを持たせる。語の一致を合意とみなさず、少数意見・否定を保持する。人のコード・メモへ自動反映しない。
- 空結果、未実行、利用不可、簡易分割、古い対象、工程の一部失敗を `empty / not_run / unavailable / fallback / stale / partial` で区別する。
- 発話・話者・条件・注釈を更新すると旧実行を「更新が必要」にする。話者台帳の更新は保守的に全履歴を更新対象にする。固定JSON／CSV・過去引用は上書きしない。
- 分析準備の追加・更新・削除も、SQLiteトリガーで同じトランザクション中に対象会話の単独実行・比較実行を`stale=1`にする。ロールバック時は更新待ちへの変更も戻す。修正前の古い履歴を一括補正する処理はない。

## 書き出しと回復

入力識別値・手法版・条件・AI生成IDから同一結果を判定する。同じリクエストIDの重複は再利用し、別入力への流用は409にする。`ai_finishing`・`ai_insights`では要求IDも識別に入り、明示的な再生成は別の履歴になる。それ以外のkindでは同じfingerprintの完了runを再利用する。provider・model・結果本文は、それだけでは識別に含まれないため、新しい実行種類へこの再利用規則を無条件に適用しない。追加分析の再送・再利用・明示再実行は再編計画のFLOW-1で別途定義する。

DBに再試行用パッケージを登録 → 一時ファイルから各JSON／CSVを置換 → hashと件数をDBに確定 → Markdownを生成、の順に保存する。起動時に中断中の書き出しを検出する。「保存済み結果から再試行」は当時のパッケージを使うので、後から本文を編集しても過去版を現在の内容に置き換えない。

`analysis_pending_packages`は計算後の保存回復だけを担当する。統合実行の受付・計画・step試行は別のpipeline台帳へ保存し、起動時に実行中attemptを`interrupted`へ移してpipelineを再試行待ちにする。再試行は世代を更新し、失敗したstepから新しいattemptを作る。確定済みの親成果物と結果runは再利用し、公開再試行で分析やAIを繰り返さない。

分析の生成ノートが人に編集されていたら、編集版を各インタビューの `履歴/ノート変更/` に写してから最新版で上書きする。削除されていたら作り直さず、保存結果の `vault_notes` と `90-運用/同期状況.md` で知らせる（2026-09-25、OBS-04）。保存済みのJSON／CSVは変更しない。考察は各インタビューの`I###-研究メモ.md`に書く。旧`60-ResearchNotes`は移行前の配置。ノートの自動マージは行わない。書き込み主体ごとの差異は[[20-Modules/obsidian-integration]]を参照する。

会話をアプリで削除しても、固定結果とVaultの履歴は自動削除しない。削除済み会話のアプリAPI・音声リンクは使用できなくなる。完全に消去する場合はバックアップを含め、保存した実行・入力・ノートを別途整理する。バックアップと復元は [[60-Operations/backup-restore]] の手順で、DB・メディア・`analysis_store`・各Vault・台帳を一組で扱う。

## APIと拡張手順

| 操作 | API |
| --- | --- |
| 組み込み手法一覧 | `GET /api/analysis/methods` |
| 統合実行の能力一覧 | `GET /api/analysis/pipeline-capabilities`。提供中と未提供の手法・形式・provider役割を区別する |
| 手動定義の保存 | `PUT /api/library/<id>/analysis/definitions/<definition-id>`。`expected_revision`を検証する |
| 手動定義の少数試行 | `POST /api/library/<id>/analysis/definitions/<definition-id>/trials`。固定入力の最大20件を既定にし外部通信しない |
| 計画プレビュー | `POST /api/library/<id>/analysis/plans/preview`。副作用なくPlanEnvelopeとExecutionBindingを返す |
| 統合実行の開始 | `POST /api/library/<id>/analysis/pipelines`。`request_id`、入力版、local-only方針、定義ID、公開先を固定する |
| 統合実行の状態 | `GET /api/library/<id>/analysis/pipelines/<pipeline-id>`。milestone、step attempt、event、公開先別状態を返す |
| 統合実行の取消・再試行 | `POST .../<pipeline-id>/cancel` / `retry`。取消は世代単位、再試行は失敗箇所から行う |
| インタビュー比較 | `POST /api/library/interview-comparison`。応答に対象会話ごとの`input_fingerprints`を含む |
| 比較の固定保存 | `POST /api/library/interview-comparison/runs`。集計時の`item_ids`・`allow_different_content`・`input_fingerprints`と`request_id`を送る。入力版の欠落は400、現在版との不一致は409で再集計が必要 |
| 全件分析／KWICの固定保存 | `POST /api/library/<id>/analysis/runs`。`request_id`, `source_revision`, `analysis_revision` と任意の `kwic: {q, mode, speaker}` |
| Transformerテーマ分析の実行 | `POST /api/library/<id>/analysis/transformer`。`request_id`, `source_revision`, `analysis_revision`, `mode`（`auto`／`candidate`／`manual`）、`max_topics`／`min_topic_size`（自動）、`topic_count`（候補）、`min_similarity`（手動）。手動のテーマ定義は保存済みの分析設定 `config.transformer_topics` から読む |
| 発話分類の実行 | `POST /api/library/<id>/analysis/classifications`。`request_id`, `source_revision`, `analysis_revision`, `use_jev`を送る。テンプレートは常に実行し、最新のTransformer結果があれば話題提案として併記する。結果は`segment_classifications.csv`と`segment_classification_crosstabs.csv`へ固定保存する |
| 保存履歴 | `GET /api/library/<id>/analysis/runs`。直近100件。古い成果物は保持 |
| 保存・Vault生成の再試行 | `POST /api/analysis/runs/<run-id>/vault` |
| 成果物取得 | `GET /api/analysis/artifacts/<artifact-id>`。hashを検証して返す |
| 固定runのZIP取得 | `GET /api/analysis/runs/<run-id>/export.zip`。manifest、parameters、result、表CSVを同じ固定成果物から束ねる |

保存結果（`run`）の `vault_status` はResearchVaultへの書き出しだけを表す。Input／Orchestrator／Visualizationへの書き出しは `vault_outputs`（Vaultごとの `status`：`published`／`failed`／`conflict`／`unknown` と `error`）と `vault_outputs_complete` で返す。正本（固定成果物とResearchVault）の保存が成功していれば、生成Vaultが失敗しても保存は成功扱いのまま（ADR-009）。「保存履歴」は未完了のVaultと理由を示し、上の再試行で書き直せる（OBS-18）。

新しい組み込み手法は [[40-Design/method-rules|登録規約]] を満たし、`analysis_method_registry.METHODS` にID・表示名・CSVデータセットを追加する。計算は既存の分析層へ、詳細と状態・単位・解析器の対応付けは `method_results` へ加える。CSVの列定義、根拠IDの検証、空・除外・更新時の検証を追加し、計算が変わった版を更新する。ファイルから任意コードを実行する登録方式にはしない。登録手法の一覧・件数は現行の`METHODS`を正本とする。

複数会話のインタビュー比較と固定保存は実装済み。ResearchVaultでは`40-研究/インタビュー比較/comparison-<run-id>.md`に保存する。比較画面から保存履歴、成果物、Obsidianノートを開き、固定済み成果物からVault保存を再試行できる（UX-33）。研究メモ・解釈・コード案の差分取り込み、外部R／Python等の結果登録、図の自動添付、保存先変更UI、バックアップ専用UIも後続工程。

検証先：`tests/test_analysis_core_contracts.py`、`tests/test_analysis_plan_binding.py`、`tests/test_analysis_snapshot_commit.py`、`tests/test_analysis_milestones.py`、`tests/test_analysis_recovery.py`、`tests/test_analysis_research_protocol.py`、`tests/test_analysis_exports.py`、`tests/test_analysis_publication.py`、`tests/test_analysis_storage.py`、`tests/test_content_browser.py`。AI通信はモックを用い、実Vaultは使わない。

2026-09-21のWindows作業ツリーで `PYTHONPATH=src;tests` を設定し、`.venv\Scripts\python.exe -m unittest discover -s tests` の550件が成功した。手動定義の少数試行からM0〜M7完了までをChromiumでも確認した。実APIによる生成品質・料金の検証は行っていない。

関連：[[current-storage]]、[[40-Design/storage-policy]]、[[20-Modules/module-map]]。


## 発話時間の欠測契約（2026-10-04）

`focus-group-local-5`／手法registry `text-analysis-store-9` から、観測済み発話がすべて時刻欠測なら話者・属性群・司会・全体の時間を `null` とする。有効な時刻のある真の0秒は0、空集合の合計も0を維持する。一部欠測時の `speaking_seconds`／`total_speaking_seconds` は時刻あり発話の小計で、`timed_turn_count` と `missing_time_turn_count` を併記する。既存話者CSVのcoverage列を維持し、属性群CSVには同2列を追加する。

全体割合は含めた全発話、参加者割合・Gini・HHI・均等度はその対象話者集合に時刻欠測がある、または総時間0の場合に `null`。除外発話は対象集合へ戻さず、UNKNOWN・未観測話者・欠測のみの話者を0秒の分母として補完しない。従来の有効時刻話者の分母人数は保ち、その対象候補に欠測があることを別coverageで示す。割合を算出できない場合の集中・低比率候補は出力しない。数値文字列の既存Python float互換は維持し、巨大整数の変換overflowは欠測扱いとする。

固定CSVの欠測は空欄、型付きJSONは `null` を保持する。pipelineは受付済みsnapshotの計算版から `result.algorithms.automatic` と手法engine版を記録する。旧snapshot・旧固定packageの値を新仕様へ再計算・書換えせず、旧計算版を保持する。新版の表にはcoverageの要約を添える。実データ移行・DB schema変更はない。


## 発話別役割が混在する話者（2026-10-04）

`focus-group-local-6`／registry `text-analysis-store-10` では、含めた発話の同一話者に複数役割がある場合、派生話者行を `role=mixed`、`role_status=mixed` とし、`observed_roles` に元の役割集合を順序固定で保存する。これは表示・集計の状態であり、人が選ぶ役割や原発話・会話プロファイル・準備記録を書き換えない。原因発話を分析から除外すれば残る単一役割へ戻る。

話者総時間・全体時間・全体割合は時間coverageが有効なら保持する。司会等を除く参加者集合は役割配分が不確定なので割合・最大割合・Gini・HHI・均等度を算出せず、`unavailable_reason=mixed_roles` を返す。実参加人数は研究者の登録値を維持し、観測参加発言者人数は混在時 `null` として推測しない。司会時間・司会割合・司会質問候補と `group_by=role` の時間・割合は `null`、`role_aggregation_status=mixed` を添え、時刻欠測とは区別する。

`exclude_moderator=false` の全観測話者集合は役割に依存しないため、時間coverageが完全なら従来名 `participant_percent` を含む割合・均等度を保持し、分母を全観測話者と明示する。UNKNOWNや未観測者を新規分母へ加えない。旧v4/v5のsnapshotや固定packageは保存時の値・元計算版で保持し、v6へ再計算・再ラベルしない。


## 固定runの保存版表示（2026-10-04）

read-only要約は保存手法の `engine.version` を「保存した計算版」、`method_version` を「手法registry版」として別々に投影する。`result.algorithms` は独立した「保存した算法一覧」で表示し、手法へ推測で結合しない。保存記録間で値が異なっても両方を残し、現在の定数や別記録で欠落を補完しない。

空・未記録は「記録なし」、bool・複合値等の未対応形式は「表示できない形式」。有限数値の0も保存された版として保持する。要約の共通16 KiB文字budget、最大12手法・20算法、版文字列256文字の上限を使う。元に値がありbudgetで省略された場合は「省略（全ファイルで確認）」とし、未記録へ変換しない。完全な保存JSONとhashは変更しない。


## 固定packageの読取整合境界（2026-10-04）

破損・外部復旧等でcatalogとmanifestの内容が変わったpackageを想定し、ZIP member名も検証する。絶対パス・親/現在ディレクトリ要素・空要素・backslash・drive/ADS colon・制御文字・Windows予約名・末尾dot/space等を拒否する。大文字小文字/Unicode正規化後の衝突と、同名ファイル/ディレクトリの衝突も停止する。安全な入れ子・日本語・単独の正規化前Unicode名は元綴りのまま保持する。名前を安全な文字列へ自動改名する処理ではない。

入力JSONは生成時と同じcanonical化（library_idを含む）からsnapshot digestを再計算し、run/manifestのsnapshot IDと照合する。個別artifactとmanifestのhashだけ整合しても、入力とsnapshot IDが異なる場合は固定run取得・preview・ZIPを409で停止する。元bytes・catalog・manifestを再生成/修復しない。ZIPには検証済みcontent集合を使い、検証後に別catalog名を再取得して混ぜない。通常の生成APIから不正名やこの不整合を作成できるとの確認ではなく、既存packageの読取検証の強化である。


## 時間系出力の残る欠測境界（2026-10-04）

`focus-group-local-7`／registry `text-analysis-store-11` では、timebin用の集合に真の0秒発話を含める。時刻あり発話が0件ならtimelineは空表、0→0の発話は終端0・開始件数1、10→10は終端10・開始件数1を保持する。従来の正duration集合を使う話者遷移・gap・overlapは変えない。旧v6の仮0行は固定snapshot/CSV内では元値のまま保持する。

感情別`seconds`とコード別`speaking_seconds`は全欠測時null、一部欠測時は既知小計とし、`timed_turn_count`/`missing_time_turn_count`を追加する。コード0件は空集合の合計0のまま。`overview.session_duration`は従来同様に除外を含む全発話の最大終了位置であり、時刻あり0件ならnull。`session_timed_turn_count`/`session_missing_time_turn_count`で、分析に含めた集合のcoverageと区別する。録音ファイルの全長を推測する値ではない。

一覧・個別の`library_public.duration`も既存analysis時刻boundsに基づく非破壊の読取projectionへ統一する。無効な時刻値で一覧全体を500にせず、全欠測null・真0・既存Python float互換の数値文字列を維持し、`timed_turn_count`/`missing_time_turn_count`を併記する。原発話・DBは書き換えない。

個別ライブラリのfull応答には、既存Python float互換の数値文字列を画面計測でも使えるよう、表示専用の`segment_timings`を添える。元発話ID・順序・件数・start/end/time_unknownとの一致、有効性の厳密なtrue、正規化値の有限性・順序・上限を確認した場合だけ利用する。ID重複・構造差・局所時刻編集・不正projectionは通常の数値guardへ戻す。原発話と保存本文へ混ぜず、DB永続化や自動保存はしない。音声seekのguardは別契約のまま。開始/終了時刻の編集は話者時間表示も同時に更新する。

数値時刻の計測では、既存Python契約で偽となる`time_unknown`のnull/false/0/空文字/空JSON配列/空JSON objectを限定的に扱う。空containerのprojection結合は同じ型かつ両方空の場合だけ値一致とし、非空化・型変更は旧投影を失効させる。局所時刻編集後は現在の数値boundsと同じmarker規則を使うため、未変更の空markerだけを理由に不明へ戻さない。一般のdeep equal・数値文字列parserは追加せず、原marker、保存本文、音声/evidenceのguardは変更しない。
