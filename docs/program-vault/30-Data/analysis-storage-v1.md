---
note_id: program-analysis-storage-v1
note_type: data-model
title: AI仕上げ・文章分析の保存契約 v1
summary: AI仕上げと文章分析の固定保存、ResearchVault公開、保存履歴の契約を定める。
status: current
feature: analysis-storage
verified: 2026-09-20
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

AI再生成は利用者の生成操作に限る。保存・履歴確認・再試行でAIを呼ばない。過去の会話を一括移行する機能ではなく、既存会話は保存ボタンを押した時点から履歴を蓄積する。

## 保存先と正本

| 保存先 | 役割 |
| --- | --- |
| SQLite `library_items` | 最新の本文・話者・会話情報・分析条件・手動注釈（研究者が定義するTransformerテーマの見出し・手がかり語・シード発話、手動の発話種別・3スコアを含む）、互換用の最新AI見解、最新のTransformer結果、最新の発話分類提案 |
| SQLite `analysis_runs` | 実行ID、入力識別値、入力版、手法版、日時、モデル、完了・更新待ち・Vault状態 |
| SQLite `analysis_artifacts` | ファイルID・相対パス・SHA-256・バイト数・CSV行数。ファイル本体の重複保存はしない |
| SQLite `obsidian_notes` | アプリ生成ノートのID・パス・最後に書いたhash。手書き内容の保護に使用 |
| SQLite `analysis_pending_packages` | 書き出し中・失敗時だけ、再試行するための入力と結果を保持する一時的な記録。成果物の確定と同時に削除 |
| `data/analysis_store/inputs/<hash>/input.json` | 実行時点の発話・注釈・実効話者情報と、保存済み原文。共通の入力版を再利用 |
| `data/analysis_store/runs/<id>/` | `manifest.json`、`parameters.json`、`result.json`、`tables/*.csv`。固定された結果の正本 |
| `data/obsidian/ResearchVault` | 分析を読むためのノート・保存時点の引用・研究者自身のメモ |
| `docs/program-vault` | プログラム仕様・手法規約・テスト・運用方法。実会話を格納しない |
| 既存の `output`、`data/media` | TXT・JSON・SRT・Excel等の既存出力と音声・動画。従来どおり保持 |

`data` は実際にはDBファイルの親ディレクトリであり、通常は `MOJIOKOSI_DATA_DIR` で指定される。全件CSVはUTF-8 BOM付きで、文字列のCSV数式解釈を抑止する。JSONでは数値・文字列・`null`等を区別するが、CSV自体は型付きの保存形式ではない。

`analysis_store.csv_bytes`は`null`と空文字をともに空欄へ変換し、先頭の空白を除いた文字列が`=`・`+`・`-`・`@`で始まる場合は`'`を付ける。したがって、元の`=A`と`'=A`などをCSVから一意に復元できない。CSVは全件の表計算用出力として保持し、機械処理では対応する`result.json`の型付き値を優先する。型・欠測理由を必要とする再取り込みで、空欄や`'`を推測で元に戻さない。

後続分析向けの型付き全件表は[[40-Design/core-handler-routing-reorganization-plan]]のFLOW-1で追加する版付き拡張であり、現行v1が任意の型付き表や依存manifestを保存できるという意味ではない。旧CSVの内容・hash・数式対策は変更しない。

## ノートと根拠

ResearchVaultの会話は`10-インタビュー/I###-<名前>/`にまとめる。概要は`I###-概要.md`、分析の入口は`I###-分析まとめ.md`、実行結果は同じフォルダーの`履歴/分析/<run-id>/`に保存する（`ObsidianLayout.note_path/analysis_dir`）。実行ノートから各`method-<id>.md`に移動できる。手法別ノートには見解、根拠、主要表の先頭10行・最大8列、分析単位・解析器、全件データ、限界を記録する。KWICの引用表示は先頭50件、AI仕上げの変更リンクは先頭100発話までで、全件はJSON／CSVに残る。旧`20-Conversations`・`40-Analyses`は移行前の配置。

引用は各インタビューフォルダーの`履歴/引用/<source-hash>/part-0001.md`に200発話ごとに保存する（`ObsidianLayout.source_dir`、`AnalysisStore.source_notes`）。旧`25-Sources`は移行前の配置。原文の文字列を維持してMarkdown用にエスケープし、発話IDはUTF-8の16進表現を使った`s-<hex>`ブロックIDに対応付ける。AIの根拠は生成当時の本文を使う。現在の本文・時刻・話者が異なる場合、リンクから現在の音声へ自動で進めず保存済み引用を案内する。

プロパティは単純なYAML値にし、大量のIDや入れ子の結果はJSONに置く。リンクはVault内のノートパスとブロックIDで生成する。[Obsidian公式：プロパティ](https://help.obsidian.md/properties)、[内部リンクとブロック参照](https://help.obsidian.md/links)

各CSV／JSONにはアプリで取得するリンクと、保存PC上で開くローカルファイルのリンクを付ける。音声リンクとアプリからの取得にはサーバーの起動が必要。PCや配置を変えた場合はローカルファイルリンクの再出力が必要になる。「Obsidianで開く」はローカルパスへのアクセスが許可された環境で表示する。[Obsidian公式：URI](https://help.obsidian.md/uri)

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

`analysis_pending_packages`が回復するのは計算後の保存であり、推論中の計画・ステップを再開する台帳ではない。追加分析の受付・試行状態の永続化と明示再開は、再編計画のFLOW-1〜2の拡張として扱う。

分析の生成ノートが人の編集・移動・削除によって変わっていたら同期を保留する。保存済みのJSON／CSVと手書き内容は保持する。人の追記は各インタビューの`I###-研究メモ.md`などへ移し、生成ノートを変更前の内容・場所に戻してから再試行できる。旧`60-ResearchNotes`は移行前の配置。ノートの自動マージや強制上書きは行わない。ナビゲーションや設定を含む全書き込みの保護が統一済みという意味ではなく、差異は[[20-Modules/obsidian-integration]]を参照する。

会話をアプリで削除しても、固定結果とVaultの履歴は自動削除しない。削除済み会話のアプリAPI・音声リンクは使用できなくなる。完全に消去する場合はバックアップを含め、保存した実行・入力・ノートを別途整理する。バックアップはアプリ停止後にDB・`analysis_store`・研究Vault・必要なメディアを一組で保存する。

## APIと拡張手順

| 操作 | API |
| --- | --- |
| 組み込み手法一覧 | `GET /api/analysis/methods` |
| インタビュー比較 | `POST /api/library/interview-comparison`。応答に対象会話ごとの`input_fingerprints`を含む |
| 比較の固定保存 | `POST /api/library/interview-comparison/runs`。集計時の`item_ids`・`allow_different_content`・`input_fingerprints`と`request_id`を送る。入力版の欠落は400、現在版との不一致は409で再集計が必要 |
| 全件分析／KWICの固定保存 | `POST /api/library/<id>/analysis/runs`。`request_id`, `source_revision`, `analysis_revision` と任意の `kwic: {q, mode, speaker}` |
| Transformerテーマ分析の実行 | `POST /api/library/<id>/analysis/transformer`。`request_id`, `source_revision`, `analysis_revision`, `mode`（`auto`／`candidate`／`manual`）、`max_topics`／`min_topic_size`（自動）、`topic_count`（候補）、`min_similarity`（手動）。手動のテーマ定義は保存済みの分析設定 `config.transformer_topics` から読む |
| 発話分類の実行 | `POST /api/library/<id>/analysis/classifications`。`request_id`, `source_revision`, `analysis_revision`, `use_jev`を送る。テンプレートは常に実行し、最新のTransformer結果があれば話題提案として併記する。結果は`segment_classifications.csv`と`segment_classification_crosstabs.csv`へ固定保存する |
| 保存履歴 | `GET /api/library/<id>/analysis/runs`。直近100件。古い成果物は保持 |
| 保存・Vault生成の再試行 | `POST /api/analysis/runs/<run-id>/vault` |
| 成果物取得 | `GET /api/analysis/artifacts/<artifact-id>`。hashを検証して返す |

新しい組み込み手法は [[40-Design/method-rules|登録規約]] を満たし、`analysis_method_registry.METHODS` にID・表示名・CSVデータセットを追加する。計算は既存の分析層へ、詳細と状態・単位・解析器の対応付けは `method_results` へ加える。CSVの列定義、根拠IDの検証、空・除外・更新時の検証を追加し、計算が変わった版を更新する。ファイルから任意コードを実行する登録方式にはしない。登録手法の一覧・件数は現行の`METHODS`を正本とする。

複数会話のインタビュー比較と固定保存は実装済み。ResearchVaultでは`40-研究/インタビュー比較/comparison-<run-id>.md`に保存する。比較履歴のGET APIはあるが、Web画面から履歴・成果物・Vault再試行へ進む導線は未実装（UX-33）。研究メモ・解釈・コード案の差分取り込み、外部R／Python等の結果登録、図の自動添付、保存先変更UI、バックアップ専用UIも後続工程。

検証先：`tests/test_ai_finishing.py`、`tests/test_analysis_storage.py`、`tests/test_content_analysis.py`、`tests/test_content_browser.py`。AI通信はモックを用いる。

2026-09-13のWindows作業ツリーで `python -X utf8 -m unittest discover -s tests` の272件が成功。ブラウザーのファイル保存待ちを実時間で確認する修正後に、`test_content_browser.py` の4件も再実行して成功した。実APIによる生成品質・料金の検証は行っていない。

関連：[[current-storage]]、[[40-Design/storage-policy]]、[[20-Modules/module-map]]。
