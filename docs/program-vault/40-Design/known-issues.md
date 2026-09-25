---
note_id: design-known-issues
note_type: issue-register
title: 既知の問題点と改善方法（収束フェーズ）
summary: 現行の課題ID、根拠、優先度、対応状態を管理する台帳。
status: current
feature: project-status
verified: 2026-09-25
tags:
  - gurumoji/program
  - gurumoji/design
  - gurumoji/issues
---

# 既知の問題点と改善方法（収束フェーズ）

**現在の状態（2026-09-25）：** 登録50件（BUG-03を追加）のうち、対応済み24件、一部対応1件（OBS-15）、未対応21件、状態欄が空のもの4件（DEV-01、UI-01〜03）。今回は、P1の未対応だったOBS-03／09／11／12／18とDATA-01／02／03、および新規のBUG-03に対応した。DATA-01は利用者の選択により「ゴミ箱＋一定期間後の自動削除」とした。残りの未対応は、収束計画で「保留」とした設計上の項目。

**前回の状態（2026-09-15）：** コミット`1b8fe41`に8件の対応を収録し、プッシュ済み。43件中、対応済み8件・一部対応1件（DOC-03）・未対応34件。元の問題・根拠・改善案は調査時点の記録で、採用した修正は「状態」のリンクを参照する。全体の集計は[[40-Design/convergence-plan#プッシュ済みの対応状況（2026-09-15）]]。

**Obsidian追加調査（2026-09-15）：** [[40-Design/known-issues#追加調査：Obsidian連携（2026-09-15）|未記載だった6件]]を追記し、すべて対応済み（未コミット）。上の件数には含めていない。

**追加調査：** [[40-Design/known-issues#追加調査：プログラム全体（2026-09-14）|未記載だった4件]] を追記し、登録は計43件。UI/UXの追加5件は [[40-Design/ui-ux-issues#追加調査：UI・UX（2026-09-14）]]。前回39件の選別は履歴として維持する。

- **確認元：** 作業ツリーのコードとドキュメント（2026-09-14）。問題・改善案は調査時点の記録。優先修正は各行の状態と[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]を参照する。
- **根拠と未確認：** 根拠欄にはファイル名・関数名を書く。実際に動かして確かめていない項目は「未確認」と書く。
- **関連ノート：** UIの細かい問題は [[40-Design/ui-ux-issues]]、実施順は [[40-Design/convergence-plan]] に書く。

**重要度：**

| 重要度 | 基準 |
| --- | --- |
| 高 | データ損失・誤動作・主要機能が使えない |
| 中 | 保守性の低下・迷い・事故の可能性 |
| 低 | 一貫性 |

**更新ルール：** 対応したら「状態」を `対応済み（commit／ADRへのリンク）` に変える。行は削除しない。

**2026-09-14の選別：** 全39件に選別欄を追加した。判断理由と最小の対応範囲は [[40-Design/convergence-plan#今回の取捨選択（2026-09-14）]]、記録は [[40-Design/decisions#ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない]]。P0〜P2は着手順であり、実装済みを意味しない。「統合」の項目も親課題の完了条件を満たすまで未対応のままとする。元の改善方法は候補として残し、採用範囲は選別結果を優先する。

再確認でOBS-01／OBS-07のコメント・独自タグ消失とOBS-05の既存全文上書きを一時Vaultで再現した。BUG-01、OBS-02はコードで経路を確認したが、実ブラウザーでの操作と同時編集の競合は未再現。ARCH-02のうち `obsidian_finishing` → `obsidian_layout` は片方向の参照であり、この組だけを循環依存とは扱わない。OBS-17のロック失敗とフォルダー同期による耐久性は別問題として検証する。

## BUG：動作不良

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-01 | 高 | グループインタビュー比較の2つのPOSTが、CSRFヘッダー `X-Gurumoji-Request` を付けずに `fetch` で送信している | `static/interview-comparison.js`: `runComparison`、`saveComparison` が `fetch(...)` を直接使う。`app.py`: `enforce_request_security` は、ブラウザー由来（Origin／Referer／Sec-Fetch-Site あり）でヘッダーのないPOSTに403を返す。テスト `tests/test_interview_comparison.py`・`test_vault_coverage.py` はブラウザー由来のヘッダーを付けない `test_client` で送るため通過する | ブラウザーから比較の実行・保存ができない可能性が高い（実ブラウザーでは未確認） | `app.js` の `apiFetch` を使う（新しいラッパーは作らない）。ブラウザーE2Eテスト、またはOriginを付けたテストクライアントで回帰テストを追加する | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |

## ARCH：アーキテクチャ

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ARCH-01 | 中 | `app.py`（約15,700行）に、API・パイプライン・編集トランザクション・分析集計・議事録・出力・AI呼び出し・Obsidian監視が集中している | [[10-Architecture/system-map]] | 変更の影響が読めない。AIや人が既存関数を見落とし、同じものを再実装しやすい | 全面的な書き換えはしない。責務ごとに既存モジュールへ関数を移すだけの変更を、1レビュー1責務で行う（例：議事録 → 新設ではなく既存の分析側へ。Obsidian呼び出し → `obsidian_finishing`・`vault_registry` 側へ）。ルートは最後まで `app.py` に残す | 未対応 | 保留：大規模移設は不具合修正後 |
| ARCH-02 | 中 | 保存・Vault系のモジュール間に循環依存があり、関数内importで回避している | `analysis_store` ⇄ `obsidian_layout`／`vault_registry`、`obsidian_finishing` ⇄ `obsidian_layout`、`obsidian_migration` → `obsidian_finishing` | 読み込み順に依存する不具合、テストしにくい | 下位の共通関数（`safe_path`、`write_atomic`、`markdown`、frontmatterの入出力）を、依存の最下層になる1か所にまとめ、一方向の依存にする。既存の上位モジュールには置けないため、新しいファイルが必要な数少ないケースになる（理由をADRに書く） | 未対応 | 保留：共通層が必要になった時点で局所抽出 |
| ARCH-03 | 中 | 同じ値を複数の場所で算出している | ResearchVaultのパス3か所（`ObsidianLayout`・`ObsidianWorkbench`・`AnalysisStore` の `__init__`）、Software Vaultのパス2か所（`vault_registry.SOFTWARE_ROOT`、`app.vault_registry`）、アプリURL・ポート3か所（`archive_ai_finishing` 内、`archive_app_url`、既定引数の `http://127.0.0.1:7860`） | 保存先の変更やポート変更の一部だけが反映され、リンク切れや別フォルダーへの書き込みが起きる | パスは `VaultRegistry`（または既存の台帳）から、URLは `archive_app_url` から取得するように統一する | 未対応 | 保留：保存先変更の実害を確認してから |
| ARCH-04 | 低中 | 原子的書き込みの関数が重複している | `analysis_store.write_atomic`、`app.py`: `atomic_write_text`、`atomic_write_bytes`、`durable_write_json`、`temporary_output_path`、`sync_directory_metadata` | `fsync` やフォルダー同期の扱いに差があり、片方だけ修正される | フォルダーの同期も含む1実装に統一し、他は薄い呼び出しにする | 未対応 | 保留：原子性・耐久性の要件を先に比較 |
| ARCH-05 | 中 | フロントエンドのAPI呼び出しが各JSに散らばり、`apiFetch` と生の `fetch` が混在している | [[10-Architecture/system-map]]、BUG-01 | セキュリティヘッダーやエラー処理の漏れ | 全ての呼び出しを `apiFetch` に統一する。エンドポイント文字列の重複は、画面を整理するときに合わせて整理する | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | 統合 → BUG-01 |
| ARCH-06 | 低 | AI入力の分割関数が3種類ある | `app.chunk_segments`（テストからしか参照されない）、`analysis_insights.bounded_batches`、`ai_finishing.fragments` | 使われていないコードが残る | `chunk_segments` をDeprecated候補にする（[[20-Modules/feature-inventory]] の確認項目を満たしてから整理） | 未対応 | 保留：利用箇所とテストの意図を確認してから |
| ARCH-07 | 中 | 同じ目的の処理経路が二重になっている | AI仕上げ（ジョブ内／Obsidian）、話者特定3経路、議事録Markdown生成2種、議事録のVault出力2系統、保存API2系統、ダウンロードAPI2系統 | 片方の経路だけ修正される。UIの入口が増える | [[20-Modules/feature-inventory]] の「Duplicate」表の方針で1つにまとめる。APIの互換は残し、実装は共通化する | 未対応 | 保留：用途の異なる経路を一律統合しない |

## OBS：Obsidian連携（データ保全）

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OBS-01 | 高 | テーマ同期が、研究者の作ったテーマノートを所有確認なしに再生成・上書きする | `ObsidianLayout.sync_themes`：10秒ごとに `20-テーマ/*.md` の全体を読み、`unpack` → プロパティ変更 → `pack` → `write_atomic` する。関連がないノートにも `graph_kind`、タグ、`<!-- gurumoji:interviews -->` 区間を追加する | ①Obsidianでの編集保存と、読み込みから書き込みまでの間に競合すると、編集が消える。②YAMLのコメント・書式が失われる。③利用者の `graph/*`・`interview/*` タグが削除される。④初回同期で全テーマノートが書き換わる | ①書き込む直前にhashとmtimeを再確認し、変わっていればスキップしてログに残す（compare-and-swap）。②プロパティは変更するキーの行だけを書き換え、解析できない形式なら書かない。③アプリ管理のタグに名前空間を分ける（例：`gurumoji/graph/*`）。移行は別のADRで決める。④mtimeが変わったメモだけを読む | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| OBS-02 | 中高 | 仕上げノート（研究者が所有）のプロパティ更新に、競合検出がない | `ObsidianLayout.sync_finishing` → `decorate` → `write_atomic` | 編集中の本文が失われうる | OBS-01と同じ仕組みを使う | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| OBS-03 | 中 | アプリが `.obsidian` の設定を変更する | `ObsidianLayout.configure`：`core-plugins.json`（コアプラグインを有効化）、`appearance.json`（CSSスニペットを有効化）、`bookmarks.json`（Gurumojiグループを置き換え）、`workspaces.json`（追加）、`workspace.json`・`graph.json`（無ければ作成） | 利用者の表示設定が変わる。Obsidianの起動中は互いに上書きしうる。`publish_navigation` から頻繁に呼ばれる | Vaultを新規作成したときの初期化だけで書く。既存のVaultでは画面で「推奨設定を適用」の明示操作にし、書く前に差分を表示する | 対応済み（`d989318`：新規Vaultの初回だけ設定を書き、`obsidian_settings`に記録。ADR-103をaccepted。「推奨設定を適用」画面は後続） | P1：優先 |
| OBS-04 | 高（統合課題） | 書き込み主体が5つ・台帳が4つあり、競合時の挙動が統一されていない | `VaultRegistry._write`（conflict／missingを表示）、`AnalysisStore.write_note`（例外）、`ObsidianLayout.managed_note`（黙ってスキップ・削除されたノートは再作成）、`ObsidianWorkbench.save_note`（判定なし）、`decorate`・`sync_themes`（判定なし）。台帳は SQLite `obsidian_notes`、`interviews.json`、`vaults.json`、`state.json` | 「人の編集を上書きしない」保証がノートの種類によって異なる | `VaultRegistry._write` の方式（予定hashを記録 → 書き込み → 確定、conflict／missingを索引に表示）を基準にし、判定ロジックを1つの関数に統合する。台帳は当面併存させ、移行は別ADRで決める | 未対応 | 保留：P0後に所有別の契約を整理 |
| OBS-05 | 中 | 作業台の初期ノートを、既存ファイルを確認せずに書く | `ObsidianWorkbench.prepare` → `save_note` → `note`（`write_atomic`）。`state.json` が無いと初回扱いになる | バックアップを片側だけ戻した、`obsidian_workbench` を消した、などの場合に、研究者が編集した `I###-全文.md`・`I###-操作.md` が上書きされる | 対象のパスにファイルがあり、台帳にhashがなければ、連番の新しいパスに作成して状態ノートで知らせる | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| OBS-06 | 中 | frontmatterの生成・解析が複数実装されている | 生成：`analysis_store.frontmatter`、`obsidian_layout.pack`、`obsidian_finishing.with_properties`、`VaultRegistry._write`。解析：`obsidian_layout.unpack`（上限なし）、`obsidian_finishing.split_properties`（64KB上限）、旧形式の `provider:` 正規表現 | 型や書式が揺れる。片方だけ修正される | 既存の `obsidian_layout` の `unpack`／`pack` に集約する（新しいファイルは作らない。ARCH-02で共通層を作る場合はそこへ移す）。上限とエラーメッセージを統一する | 未対応 | 保留：人のノートと生成物を同じYAML処理にしない |
| OBS-07 | 中 | プロパティの書き戻しが、全体の再シリアライズになっている | `pack` と `yaml.safe_dump` | コメントや書式が失われる。`tags` の文字列が配列に型変換される | 変更するキーだけを行単位で更新する。未知の形式（複数行の文字列、アンカーなど）があれば書かずに停止する。依存を追加する場合（YAMLのround-trip対応ライブラリ）は別途判断する | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | 統合 → OBS-01／OBS-02 |
| OBS-08 | 低中 | 監視がポーリングで、テーマ同期のたびに全インタビューのトップのノートを全読み込みする | `start_obsidian_watcher`（2秒、10秒）、`sync_themes` | Vaultが大きくなるとI/Oが増える。クラウド同期フォルダーで負荷が高くなる | mtimeとサイズのキャッシュで、変更があったファイルだけを読む | 未対応 | 保留：性能を計測してから |
| OBS-09 | 中 | 起動時の復旧・移行が失敗すると、監視が停止したまま気づけない | `start_obsidian_watcher` の例外時に `stop.set()` して終了する | 操作ノートのチェックに反応せず、利用者には理由が分からない | 監視の状態（稼働中／停止と理由）を `GET /api/config` などに含め、画面に表示する | 対応済み（`1969bf9`：`WatcherStatus`を`/api/config`の`runtime.obsidian_watcher`と「接続と処理装置」に表示） | P1：優先 |
| OBS-10 | 中 | Vaultが入れ子になる危険を検出していない | 実環境の `runtime/data/obsidian/` に `.obsidian` と `無題のファイル*.base` があり、親フォルダーが保管庫として開かれた痕跡がある。3つの生成Vaultも同じ `obsidian/` の直下に作られる | 親Vaultの検索・グラフ・リンク解決に、子Vaultのノートが混ざる | Vaultを作成・書き込みする前に、ルートの親方向に `.obsidian` がないか確認し、あれば停止して警告する。痕跡のファイルは削除せず、利用者に案内する | 未対応 | 保留：生成先の警告を検討。全保存停止案は不採用 |
| OBS-11 | 低中 | 会話を削除した後も、ResearchVaultの概要・一覧が「保存済み」のまま | `_delete_library_item_locked` は `retire_input_vault` だけを呼び、`interviews.json` と概要ノートは更新しない | 削除済みの会話を判別できない | 状態を「アプリから削除済み」に更新する（ノートは来歴として残す） | 対応済み（`a64c1c2`、`bf2a82d`：`ObsidianLayout.mark_deleted`／`clear_deleted`） | P1：優先 |
| OBS-12 | 低中 | 分析ノートに `file:///` の絶対パスリンクを書く | `AnalysisStore.publish` の `local_links` | 端末に依存する。Vaultを共有するとPCのユーザー名などが残る。移動するとリンクが切れる | アプリ経由のURLだけにする。既存のノートは再生成で置き換える（所有hashが一致するものだけ） | 対応済み（`8fd1c3d`：新規ノートはアプリURLだけ。既存ノートは再生成時に置き換わる） | P1：優先 |
| OBS-13 | 低 | 移行処理が、Vault全体の空フォルダーを削除する | `obsidian_migration.migrate` の最後の `rmdir` ループ | 他の環境で初めて移行するとき、利用者の空フォルダーが消える（移行済みの環境では実行されない） | 移行元フォルダーだけに限定する | 未対応 | P2：後続 |
| OBS-14 | 中 | パス長の上限を事前に確認していない | 例：`10-インタビュー/I001-<最大48字>/履歴/分析/<run_id 32字>/graph/結果-<手法>-表-01-<最大72字>.md` にデータフォルダーの位置が加わる（未計測） | Windowsで書き込みに失敗し、`vault_status=conflict` になる | 書き込み前にフルパスの長さを計算する。上限を超える場合は、短いID名とtitleで作る。ファイル名の生成を1つの関数にまとめる（`ObsidianLayout.register` の正規表現、`graph_node_path`、`safe_output_stem` を統一） | 未対応 | 保留：長いパスで再現・環境条件を確認してから |
| OBS-15 | 中 | Obsidian操作の監査ログがない | `managed_note` のスキップ、`sync_themes` の書き込みは記録されない | 「なぜ更新されないか」「いつ書き換えたか」を追跡できない | 既存の `<data>/obsidian_layout/` に、操作ログ（日時・Vault・相対パス・操作 CREATE／UPDATE／SKIP／CONFLICT／MISSING／MIGRATE・前後hash・理由）をJSON Lines形式で残す。本文は記録しない | 一部対応（`1969bf9`：スキップ理由をパスごとに1回ログへ出す。JSONL監査ログは計画どおり作らない） | 統合 → OBS-09 |
| OBS-16 | 低中 | 大量変更にDry Runがない | `migrate` はバックアップを取るが、変更予定の一覧を事前に出さない | 移行・再生成の影響を事前に確認できない | 移行・一括再生成・リンク変換に「計画のみ」モードを設ける（件数、作成／更新／移動／削除の予定、競合） | 未対応 | 保留：次の一括移行の着手条件 |
| OBS-17 | 低 | 原子的書き込みがロックされたファイルに弱い | `write_atomic` は `os.replace` だけで、フォルダーの `fsync` をしない | 同期ソフトやウイルス対策ソフトがファイルを掴むと失敗する | 短いリトライを入れ、失敗を記録する（ARCH-04と一緒に対応） | 未対応 | 保留：ロック失敗を再現してから |

## DATA：データ・保存

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-01 | 中 | 元メディアの削除が恒久削除になっている | `_delete_library_item_locked`：隔離フォルダーへ移したあと `shutil.rmtree` | 誤って削除すると元音声を復旧できない（出力は残る） | 既存の隔離の仕組みを使い、保持期間つきのゴミ箱にする。完全に削除する操作は別にする（[[40-Design/storage-policy]] の「別操作とする」方針） | 対応済み（2026-09-25：`services/library_trash`。削除はゴミ箱へ移り、一覧から復元・完全削除できる。保持日数は`MOJIOKOSI_TRASH_RETENTION_DAYS`（既定30日、利用者の選択）で、起動時に期限切れを削除） | P1：優先 |
| DATA-02 | 中 | Vaultの数と構成がドキュメントごとに食い違っている | `docs/OBSIDIAN_VAULTS.md` と `README.md` は「2つのVault」、[[30-Data/four-vaults-v1]] は Input／Visualization／Orchestrator に ResearchVault と Software を加えた構成 | 利用者やAIが保存先を誤解する | [[40-Design/convergence-plan]] のドキュメント統一で直す | 対応済み（`708948b`：`docs/OBSIDIAN_VAULTS.md`とREADMEを5つのVaultに統一。DOC-01／02の全件整理は含まない） | P1：優先 |
| DATA-03 | 低 | 同じ会話の情報が多くの場所に分散している | SQLite、`runtime/output`、`analysis_store`、ResearchVault、InputVault、`obsidian_workbench` | バックアップの漏れや、復元時の不整合 | 正本の分類は [[40-Design/storage-policy]] にある。バックアップと復元の単位を `60-Operations` の手順として作る | 対応済み（`708948b`：[[60-Operations/backup-restore]]） | P1：優先 |

## CFG：設定

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CFG-01 | 中 | 設定の置き場所が分散している | [[10-Architecture/system-map]] の「設定の所在」 | 同じ設定に正本が複数できる | 設定の種類ごとに正本を1つに決める（下表） | 未対応 | 保留：設定ごとの責務を維持 |
| CFG-02 | 中 | 秘密情報と利用者設定が同じファイルにあり、UIが秘密ファイルを書き換える | `config/tokens.json` に、APIキーと `openai_model` などの使用モデルが同居している。`update_token_model` がこのファイルを書き換える | 秘密ファイルの破損リスク。共有してよい設定と秘密が分けられない | 使用モデルは秘密ではない設定ファイルへ段階的に移す（読み込みは新旧両対応、書き込みは新しい方だけ） | 未対応 | 保留：移行・復元仕様が必要 |
| CFG-03 | 低 | 既定値が複数の場所に書かれている | 「Obsidianで仕上げ」の既定が、`JobOptions`・`parse_bool("finish_in_obsidian", default=True)`・`index.html` の `checked` の3か所。会話モードは `app.js` にだけある | 既定を変えるときに漏れる | サーバー側の既定を `GET /api/config` で返し、UIはそれを使う | 未対応 | 保留：既定値を変更する際に統合 |
| CFG-04 | 低 | AIエフォートが2か所にある | `localStorage`、`state.json` | 画面とObsidianで値が食い違う | 正本を会話ごとの `state.json`（仕上げ）とアプリ設定のどちらかに決める | 未対応 | 保留：既定値と実行別指定を区別してから |

設定ごとの正本（案）：

| 設定 | 正本 |
| --- | --- |
| APIキー・トークン | `tokens.json` だけ |
| 使用モデル・既定の処理条件 | アプリ設定ファイル（秘密を含まない） |
| 保存先・ポート・公開設定 | 環境変数（起動時に確定し、画面では表示だけ） |
| Vaultのルート | `vaults.json`（ResearchVaultも登録し、コード内の算出をやめる） |
| 会話ごとの分析条件 | SQLite |
| 仕上げの実行時オプション | 操作ノート → `state.json` |

## DOC：ドキュメント

| ID | 重要度 | 問題 | 根拠 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-01 | 中 | 同じ説明を別々の場所で管理している | `README.md`（約53KB）、`docs/*.md`（利用者向けの手順）、このVault（仕様） | 役割を決める。READMEは導入の入口、`docs/` は操作手順、Vaultは仕様・設計・問題点。同じ説明は書かずにリンクする | 未対応 | 統合 → DATA-02 |
| DOC-02 | 低中 | 一部が実装済みなのに `proposed` のままのノートがある | [[40-Design/storage-policy]]、[[40-Design/sync-contract]]（提案API `/api/obsidian/settings` などは未実装） | 実装済みの部分を `30-Data` へ移し、提案部分だけを残す | 未対応 | 統合 → DATA-02 |
| DOC-03 | 中 | AI向けの開発ルールがリポジトリにない | `AGENTS.md`・`CONTRIBUTING.md` がない | 2026-09-16にルート `AGENTS.md` を追加し、日常作業用の短い優先順位・探索・検証ルールを置いた。詳細は [[40-Design/ai-development-rules]] に分離した | 対応済み（未コミット） | 今回のAI運用ルール監査で対応 |

## DEV：開発時の残骸

| ID | 重要度 | 問題 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- |
| DEV-01 | 低 | `runtime/` 直下に由来が分からないファイルと検証出力がある（[[20-Modules/feature-inventory]] の「Unknown」） | 削除しない。利用者に確認してから、`runtime/archive` へ移すなどで整理する。検証スクリプトの出力先は `runtime/logs` などに決める | 未対応 | 保留：由来不明。データ削除・移動の対象外 |

## UI：画面の収束（詳細は [[40-Design/ui-ux-issues]]）

| ID | 重要度 | 問題 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- |
| UI-01 | 中 | Obsidian関連の入口が5か所に分かれている：新規作成のチェック、結果画面「Obsidianで仕上げ」、議事録パネル「Obsidianに保存」、分析「分析結果をObsidianに保存」、比較「比較結果を保存」 | 「保存・Obsidian」の操作を、会話ごとの1パネル（状態表示と操作）に集約する | 未対応 | 保留：異なる保存対象の一律集約案は不採用 |
| UI-02 | 中 | 「保存」の意味が複数ある：編集内容の保存、話者管理の保存、分析設定の保存、分析の固定保存、Obsidianへの保存 | ボタン名を「編集を保存」「分析条件を保存」「結果を記録（固定）」のように対象で区別する | 未対応 | 統合 → UX-04 |
| UI-03 | 中 | 移動の導線が重複し、URLにも反映されない（UX-01〜03） | [[40-Design/ui-ux-issues]] の推奨順に従う | 対応済み（UX-01／UX-03、UI再設計 2026-09-16、未コミット。[[20-Modules/ui-screens]]） | 統合 → UX-01／UX-03 |

## 追加調査：プログラム全体（2026-09-14）

以下4件は追加登録。登録後の修正状況は各行の状態に反映した。調査範囲・確認版・調査時の検証は [[40-Design/convergence-plan#追加調査と対応順（2026-09-14）]]。既存の台帳統合・監視停止・UI配置の問題とは分けて扱う。

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-02 | 高 | 比較結果の保存が、画面に表示した時点の入力版を確認せず、保存時点のデータで再集計する | `app.py:compare_group_interviews`、`save_interview_comparison_run`、`interview_comparison_request`。要求には会話IDと異内容比較の指定だけで、表示時の各revision・入力fingerprintがない。`static/interview-comparison.js:lastRequest`にも版を持たない | 比較を見た後に別画面・別タブで本文を編集すると、利用者が確認した結果と違うものが保存される。BUG-01のCSRF修正後にも残る独立した不具合 | 表示結果に構成会話ごとの入力fingerprint等を付け、保存時に照合。不一致なら409と再集計案内。クライアントの結果本文を無検証で保存しない。一時DBで表示時の対象発話2件→元データ編集→保存された結果1件、HTTP 200を再現した | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | P1：優先 |
| DATA-04 | 中 | 分析準備のrevision変更が、保存済み実行のDB上の`stale`へ伝播しない | `transcript_preparation.py:save/write_state`は準備テーブルだけを更新。`analysis_store.py:initialize_store`のstale用triggerに準備テーブルがなく、`refresh_vaults`はDBのstaleだけを参照。`app.py:archive_source_stamp`は準備revisionを含むが、`list_interview_comparison_runs`はfingerprintを再検証しない | 準備状態を含む固定成果物が古くなっても、比較一覧・Orchestratorの更新要否に反映されない。単一会話の履歴APIはfingerprintで補正するため、表示先によって判定が違う | 準備更新と同じトランザクションで当該会話・構成比較の実行をstaleにするか、同じ版照合を各経路で共有する。一時DBで準備revision更新後のfingerprint変化と、一覧再生成後も比較APIのstaleが0のままであることを再現。通常の準備保存APIを通すE2Eは未実施 | 対応済み（[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]） | P1：優先 |
| OBS-18 | 中 | Input・Visualization・Orchestratorへの書き出し失敗が、保存結果APIの状態へ集約されない | `AnalysisStore.publish_vaults`は例外をwarningに記録し、`VaultRegistry.publish_analysis`の戻り値も利用しない。その後`publish`はResearchVault成功時に`vault_status=completed,error=''`とする。`public`には生成3Vaultの同期結果がない。`VaultRegistry.run_status`は内容のcurrent/staleを返し、同期のconflict/missingとは異なる | 生成Vaultが欠けてもUIでは「Vaultを保存しました」となり、再試行ボタンの条件も満たさない。OBS-09のwatcher停止やOBS-04の書き込み所有判定とは異なる、保存APIの結果集約漏れ | 正本保存の成功は維持したまま、Vaultごとの書き出し状態・理由をAPIで返し、未完了の出力を再試行できるようにする。一時Vaultで生成側の書き込み例外を注入し、ResearchVault成功後もAPIに公開する値がcompleted・空errorであることを再現 | 対応済み（`7c1cfeb`：保存APIに`vault_outputs`／`vault_outputs_complete`。障害注入テストあり） | P1：優先 |
| PERF-01 | 中 | 会話一覧APIがページ分割なしで全会話・全発話JSONを読み込む | `app.py:list_library`の`SELECT * FROM library_items`→`fetchall`→各行の`row_segments`→全候補の`library_public`。検索語が空でも全文を展開する。`static/app.js:loadLibrary/loadAnalysisCatalog`と`interview-comparison.js:loadCatalog`が同じ一覧を要求する | 会話・発話が増えるほど、一覧表示や検索のたびに処理量とメモリー使用量が増える構造。Obsidian監視のI/O負荷（OBS-08）とは別。実環境で遅延が発生する件数・秒数は未計測 | まず100会話×各1万発話等のfixtureで時間・メモリー・応答サイズを測定。絞り込み用メタデータの索引、一覧用の軽い取得、ページ分割を検討し、検索・話者・感情facetの意味を保つ。負荷測定前に性能改善を断定しない | 未対応（構造確認・負荷未計測） | P2：測定後に判断 |

## 追加調査：プログラム全体（2026-09-25）

分析プログラムのリファクタリング後に、壊れた入力（終了時刻0、NaN、文字列の時刻、ID欠落・重複、`null`・数値の本文、巨大・負の時刻、300件の重なり）を分析APIと各エクスポートへ与えて確認した。落ちたのは次の1件だけだった。

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-03 | 中 | 発話の本文が`null`や数値だと、その会話の分析とエクスポートがすべて500になる | `transcript_preparation.view`が`segment.get("text", "").strip()`を呼ぶ。キーがあって値が`null`なら`None.strip()`。既存の`*_話者分離.json`を取り込む`services/output_import.py`は発話を検証せずに保存する | 取り込んだJSONに1件あるだけで、その会話の分析画面・JSON・CSV・Excelが開けない | 本文を文字列として読む`segment_text`を準備画面・行データ・確定検証で使う。分析・3種のエクスポート・確定の回帰テスト | 対応済み（`8cdd22f`） | P1：優先 |

## 追加調査：Obsidian連携（2026-09-15）

- **確認元：** コードと、実環境の `runtime/data/obsidian/ResearchVault` を確認した。OBS-19は実環境のノート、OBS-20〜23とOBS-24の①は一時Vaultで再現した。
- **テスト：** 修正に合わせて回帰テストを追加した（`tests/test_obsidian_layout.py`、`tests/test_obsidian_finishing.py`、`tests/test_analysis_storage.py`）。
- **未確認：** OBS-24の④は、Obsidianが独自キーを消すかどうかを確かめていない。

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OBS-19 | 中 | 手法別の表の中で、リンクの別名の区切り（縦棒）をエスケープしていない | `obsidian_layout.method_table`。実環境の `40-研究/分析手法/ai.md`・`I001-分析まとめ.md` に出ている | Obsidianで表の列がずれる | 表の中では縦棒をバックスラッシュでエスケープする（`vault_registry` と同じ書き方） | 対応済み（未コミット） | P0：最優先 |
| OBS-20 | 中高 | 作業ノートを削除すると、2秒ごとに状態ノート・`state.json`・`interviews.json`・ナビゲーションを書き直す | `ObsidianWorkbench.poll_once` は、ラッチ前の `refresh_paths` で例外が出た場合も毎回、公開処理を行う。一時Vaultで、状態ノートのhashが毎回変わることを再現 | 同期ソフトの負荷が上がる。メッセージは「一意に確認できません」で、削除が原因だと分からない | ラッチ前の同じエラーは1回だけ公開する。ノートが戻れば `ready` に戻す。見つからない場合と重複の場合で文言を分ける | 対応済み（未コミット） | P0：最優先 |
| OBS-21 | 中 | Obsidianのゴミ箱（`.trash`）にあるノートを、移動先として使う | `locate_note` がVault全体を `rglob` し、隠しフォルダーを除外していない。一時Vaultで、`work` が `.trash/…` に変わり、状態が `ready` のままになることを再現 | 削除したノートを入力にして、AI仕上げ・反映が進む | `.obsidian`・`.trash` などの隠しフォルダーを除外する（`obsidian_layout.find_notes` に集約） | 対応済み（未コミット） | P0：最優先 |
| OBS-22 | 中 | インタビューのフォルダーをObsidianで移動・改名すると、元の場所に概要と研究メモを作り直す | `ObsidianLayout.register` はパスを固定で記録する。`update` は研究メモを作成し、`managed_note` は概要を作り直す。テーマ同期も元のフォルダーだけを読む。一時Vaultで再現 | フォルダーが二重になる。移動した研究メモのテーマリンクが無視される。分析の保存で、`obsidian_notes` のパスと食い違って競合になる | 概要ノートの `note_id` で移動先を探し、`interviews.json` の folder・hub・links・managed を更新して `moved_from` を記録する。`AnalysisStore.follow_moves` が `obsidian_notes`・`analysis_runs.note_path` の接頭辞を同じように書き換える。見つからない（削除された）場合は従来どおり作り直し、再探索は60秒に1回までにする | 対応済み（未コミット） | P1：優先 |
| OBS-23 | 中 | 短い形式のテーマリンク（例：`[[働き方]]`）を認識しない | `sync_themes` の正規表現は `20-テーマ/` から始まるリンクだけを拾う。Obsidianの既定の新規リンク形式は「最短パス」。一時Vaultで再現 | 入力補完でリンクした研究メモが、テーマ関連に反映されない | Obsidianと同じく、Vault内（隠しフォルダーを除く）で名前が1つに決まり、`20-テーマ` 配下にある場合だけ解決する | 対応済み（未コミット） | P1：優先 |
| OBS-24 | 低 | 監視処理の小さな問題：①変化がなくても `interviews.json` を保存する ②テーマ関連の警告が10秒ごとに出る ③`.obsidian` のJSONが壊れているか型が違うと、例外でナビゲーションの生成全体が止まる ④ブックマークの独自キー `gurumoji` が消えると、グループが重複しうる | `managed_note`、`sync_themes`、`configure` | 不要な書き込み、ログの肥大、設定の重複 | ①hashが変わったときだけ保存する ②同じ警告は1回だけ出す ③読めない・型が違う設定は書き換えずに警告する ④キーがなくても、先頭がホームの「Gurumoji」グループなら置き換える | 対応済み（未コミット） | P2：後続 |
