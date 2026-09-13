---
note_id: program-analysis-storage-v1
note_type: data-model
title: AI仕上げ・文章分析の保存契約 v1
status: current
verified: 2026-09-13
schema_version: 1
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
| SQLite `library_items` | 最新の本文・話者・会話情報・分析条件・手動注釈、互換用の最新AI見解 |
| SQLite `analysis_runs` | 実行ID、入力識別値、入力版、手法版、日時、モデル、完了・更新待ち・Vault状態 |
| SQLite `analysis_artifacts` | ファイルID・相対パス・SHA-256・バイト数・CSV行数。ファイル本体の重複保存はしない |
| SQLite `obsidian_notes` | アプリ生成ノートのID・パス・最後に書いたhash。手書き内容の保護に使用 |
| SQLite `analysis_pending_packages` | 書き出し中・失敗時だけ、再試行するための入力と結果を保持する一時的な記録。成果物の確定と同時に削除 |
| `data/analysis_store/inputs/<hash>/input.json` | 実行時点の発話・注釈・実効話者情報と、保存済み原文。共通の入力版を再利用 |
| `data/analysis_store/runs/<id>/` | `manifest.json`、`parameters.json`、`result.json`、`tables/*.csv`。固定された結果の正本 |
| `data/obsidian/ResearchVault` | 分析を読むためのノート・保存時点の引用・研究者自身のメモ |
| `docs/program-vault` | プログラム仕様・手法規約・テスト・運用方法。実会話を格納しない |
| 既存の `output`、`data/media` | TXT・JSON・SRT・Excel等の既存出力と音声・動画。従来どおり保持 |

`data` は実際にはDBファイルの親ディレクトリであり、通常は `MOJIOKOSI_DATA_DIR` で指定される。全件CSVはUTF-8 BOM付き。数値列の型・JSONの数値精度を維持し、文字列のCSV数式解釈を抑止する。

## ノートと根拠

会話は `20-Conversations/conversation-<key>.md`、結果は `40-Analyses/<conversation-key>/<run-id>/` に保存する。実行ノートから各 `method-<id>.md` に移動できる。手法別ノートには見解、根拠、主要表の先頭10行・最大8列、分析単位・解析器、全件データ、限界を記録する。KWICの引用表示は先頭50件、AI仕上げの変更リンクは先頭100発話までで、全件はJSON／CSVに残る。

引用は `25-Sources/<source-hash>/part-0001.md` の200発話ごとのページに保存する。原文の文字列を維持してMarkdown用にエスケープし、発話IDはUTF-8の16進表現を使った `s-<hex>` ブロックIDに対応付ける。AIの根拠は生成当時の本文を使う。現在の本文・時刻・話者が異なる場合、リンクから現在の音声へ自動で進めず保存済み引用を案内する。

プロパティは単純なYAML値にし、大量のIDや入れ子の結果はJSONに置く。リンクはVault内のノートパスとブロックIDで生成する。[Obsidian公式：プロパティ](https://help.obsidian.md/properties)、[内部リンクとブロック参照](https://help.obsidian.md/links)

各CSV／JSONにはアプリで取得するリンクと、保存PC上で開くローカルファイルのリンクを付ける。音声リンクとアプリからの取得にはサーバーの起動が必要。PCや配置を変えた場合はローカルファイルリンクの再出力が必要になる。「Obsidianで開く」はローカルパスへのアクセスが許可された環境で表示する。[Obsidian公式：URI](https://help.obsidian.md/uri)

## AI仕上げと分析の規約

Whisper原文を先に保存し、Obsidianの専用作業ノートから仕上げを実行する連携を追加した。対象は `15-Finishing` 配下の会話・全体アウトライン・操作ノートで、分析結果ノートの一般的な双方向同期とは分離する。操作、原文保護、重複実行防止、競合時の扱いは [Obsidianで文字起こしを仕上げる](../../OBSIDIAN_FINISHING.md) を参照する。

- 校正はID・発話順・話者・時刻を固定し、明白な誤変換と句読点を直す。要約・解釈・テーマ付与は別工程とする。長い単独発話も分割し、末尾まで処理する。失敗した分割片があれば校正結果全体を採用しない。
- 話者の修復を選んだ場合は校正前の本文を独立した入力に用いる。修復したラベルと原ラベルを変更CSVに残す。
- 議題は各要点の根拠IDをサーバーで検証する。時刻を原文から計算し、`bullet_evidence` と `evidence` に根拠を保存する。既存の根拠IDがない議題には「旧形式」と表示する。
- AI見解は研究質問を優先し、1項目に1つの主張と根拠IDを持たせる。語の一致を合意とみなさず、少数意見・否定を保持する。人のコード・メモへ自動反映しない。
- 空結果、未実行、利用不可、簡易分割、古い対象、工程の一部失敗を `empty / not_run / unavailable / fallback / stale / partial` で区別する。
- 発話・話者・条件・注釈を更新すると旧実行を「更新が必要」にする。話者台帳の更新は保守的に全履歴を更新対象にする。固定JSON／CSV・過去引用は上書きしない。

## 書き出しと回復

入力識別値・手法版・条件・AI生成IDから同一結果を判定する。同じリクエストIDの重複は再利用し、別入力への流用は409にする。AIを明示的に再生成した場合は別の履歴になる。

DBに再試行用パッケージを登録 → 一時ファイルから各JSON／CSVを置換 → hashと件数をDBに確定 → Markdownを生成、の順に保存する。起動時に中断中の書き出しを検出する。「保存済み結果から再試行」は当時のパッケージを使うので、後から本文を編集しても過去版を現在の内容に置き換えない。

Obsidianノートが人の編集・移動・削除によって変わっていたら同期を保留する。保存済みのJSON／CSVと手書き内容は保持する。手書きメモを `60-ResearchNotes` に分け、生成ノートを変更前の内容・場所に戻してから再試行できる。ノートの自動マージや強制上書きは行わない。

会話をアプリで削除しても、固定結果とVaultの履歴は自動削除しない。削除済み会話のアプリAPI・音声リンクは使用できなくなる。完全に消去する場合はバックアップを含め、保存した実行・入力・ノートを別途整理する。バックアップはアプリ停止後にDB・`analysis_store`・研究Vault・必要なメディアを一組で保存する。

## APIと拡張手順

| 操作 | API |
| --- | --- |
| 組み込み手法一覧 | `GET /api/analysis/methods` |
| 全件分析／KWICの固定保存 | `POST /api/library/<id>/analysis/runs`。`request_id`, `source_revision`, `analysis_revision` と任意の `kwic: {q, mode, speaker}` |
| 保存履歴 | `GET /api/library/<id>/analysis/runs`。直近100件。古い成果物は保持 |
| 保存・Vault生成の再試行 | `POST /api/analysis/runs/<run-id>/vault` |
| 成果物取得 | `GET /api/analysis/artifacts/<artifact-id>`。hashを検証して返す |

新しい組み込み手法は [[40-Design/method-rules|登録規約]] を満たし、`analysis_method_registry.METHODS` にID・表示名・CSVデータセットを追加する。計算は既存の分析層へ、詳細と状態・単位・解析器の対応付けは `method_results` へ加える。CSVの列定義、根拠IDの検証、空・除外・更新時の検証を追加し、計算が変わった版を更新する。ファイルから任意コードを実行する登録方式にはしない。現在はTransformerテーマ分析を含む18手法を登録している。

研究メモ・解釈・コード案の差分取り込み、外部R／Python等の結果登録、複数会話を束ねる分析、図の自動添付、保存先変更UI、バックアップ専用UIは未実装。今回の組み込み18手法の保存とは別に段階的に追加する。

検証先：`tests/test_ai_finishing.py`、`tests/test_analysis_storage.py`、`tests/test_content_analysis.py`、`tests/test_content_browser.py`。AI通信はモックを用いる。

2026-09-13のWindows作業ツリーで `python -X utf8 -m unittest discover -s tests` の272件が成功。ブラウザーのファイル保存待ちを実時間で確認する修正後に、`test_content_browser.py` の4件も再実行して成功した。実APIによる生成品質・料金の検証は行っていない。

関連：[[current-storage]]、[[40-Design/storage-policy]]、[[20-Modules/module-map]]。
