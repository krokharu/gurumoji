---
note_type: reference-section
status: current
feature: project-status
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/issues
note_id: design-known-issues-section-03
title: 既知の問題点と改善方法（収束フェーズ）：OBS：Obsidian連携（データ保全）
summary: OBS：Obsidian連携（データ保全）。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 52
- 73
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：OBS：Obsidian連携（データ保全）

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## OBS：Obsidian連携（データ保全）

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OBS-01 | 高 | テーマ同期が、研究者の作ったテーマノートを所有確認なしに再生成・上書きする | `ObsidianLayout.sync_themes`：10秒ごとに `20-テーマ/*.md` の全体を読み、`unpack` → プロパティ変更 → `pack` → `write_atomic` する。関連がないノートにも `graph_kind`、タグ、`<!-- gurumoji:interviews -->` 区間を追加する | ①Obsidianでの編集保存と、読み込みから書き込みまでの間に競合すると、編集が消える。②YAMLのコメント・書式が失われる。③利用者の `graph/*`・`interview/*` タグが削除される。④初回同期で全テーマノートが書き換わる | ①書き込む直前にhashとmtimeを再確認し、変わっていればスキップしてログに残す（compare-and-swap）。②プロパティは変更するキーの行だけを書き換え、解析できない形式なら書かない。③アプリ管理のタグに名前空間を分ける（例：`gurumoji/graph/*`）。移行は別のADRで決める。④mtimeが変わったメモだけを読む | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| OBS-02 | 中高 | 仕上げノート（研究者が所有）のプロパティ更新に、競合検出がない | `ObsidianLayout.sync_finishing` → `decorate` → `write_atomic` | 編集中の本文が失われうる | OBS-01と同じ仕組みを使う | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| OBS-03 | 中 | アプリが `.obsidian` の設定を変更する | `ObsidianLayout.configure`：`core-plugins.json`（コアプラグインを有効化）、`appearance.json`（CSSスニペットを有効化）、`bookmarks.json`（Gurumojiグループを置き換え）、`workspaces.json`（追加）、`workspace.json`・`graph.json`（無ければ作成） | 利用者の表示設定が変わる。Obsidianの起動中は互いに上書きしうる。`publish_navigation` から頻繁に呼ばれる | Vaultを新規作成したときの初期化だけで書く。既存のVaultでは画面で「推奨設定を適用」の明示操作にし、書く前に差分を表示する | 対応済み（`d989318`：新規Vaultの初回だけ設定を書き、`obsidian_settings`に記録。ADR-103をaccepted。「推奨設定を適用」画面は後続） | P1：優先 |
| OBS-04 | 高（統合課題） | 書き込み主体が5つ・台帳が4つあり、競合時の挙動が統一されていない | `VaultRegistry._write`（conflict／missingを表示）、`AnalysisStore.write_note`（例外）、`ObsidianLayout.managed_note`（黙ってスキップ・削除されたノートは再作成）、`ObsidianWorkbench.save_note`（判定なし）、`decorate`・`sync_themes`（判定なし）。台帳は SQLite `obsidian_notes`、`interviews.json`、`vaults.json`、`state.json` | 「人の編集を上書きしない」保証がノートの種類によって異なる | `VaultRegistry._write` の方式（予定hashを記録 → 書き込み → 確定、conflict／missingを索引に表示）を基準にし、判定ロジックを1つの関数に統合する。台帳は当面併存させ、移行は別ADRで決める | 対応済み（2026-09-25。判定を `vault_note_policy.write_generated_note` に統合。利用者の決定により、研究者が編集した生成ノートは編集版を履歴に写してから最新版で上書きし、最初の版も作成時に履歴へ写す。削除はナビだけ作り直す。台帳は併存） | 保留：P0後に所有別の契約を整理 |
| OBS-05 | 中 | 作業台の初期ノートを、既存ファイルを確認せずに書く | `ObsidianWorkbench.prepare` → `save_note` → `note`（`write_atomic`）。`state.json` が無いと初回扱いになる | バックアップを片側だけ戻した、`obsidian_workbench` を消した、などの場合に、研究者が編集した `I###-全文.md`・`I###-操作.md` が上書きされる | 対象のパスにファイルがあり、台帳にhashがなければ、連番の新しいパスに作成して状態ノートで知らせる | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| OBS-06 | 中 | frontmatterの生成・解析が複数実装されている | 生成：`analysis_store.frontmatter`、`obsidian_layout.pack`、`obsidian_finishing.with_properties`、`VaultRegistry._write`。解析：`obsidian_layout.unpack`（上限なし）、`obsidian_finishing.split_properties`（64KB上限）、旧形式の `provider:` 正規表現 | 型や書式が揺れる。片方だけ修正される | 既存の `obsidian_layout` の `unpack`／`pack` に集約する（新しいファイルは作らない。ARCH-02で共通層を作る場合はそこへ移す）。上限とエラーメッセージを統一する | 未対応 | 保留：人のノートと生成物を同じYAML処理にしない |
| OBS-07 | 中 | プロパティの書き戻しが、全体の再シリアライズになっている | `pack` と `yaml.safe_dump` | コメントや書式が失われる。`tags` の文字列が配列に型変換される | 変更するキーだけを行単位で更新する。未知の形式（複数行の文字列、アンカーなど）があれば書かずに停止する。依存を追加する場合（YAMLのround-trip対応ライブラリ）は別途判断する | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | 統合 → OBS-01／OBS-02 |
| OBS-08 | 低中 | 監視がポーリングで、テーマ同期のたびに全インタビューのトップのノートを全読み込みする | `start_obsidian_watcher`（2秒、10秒）、`sync_themes` | Vaultが大きくなるとI/Oが増える。クラウド同期フォルダーで負荷が高くなる | mtimeとサイズのキャッシュで、変更があったファイルだけを読む | 対応済み（`d408cf8`：更新日時とサイズのキャッシュ。300インタビュー・変更なしで307ms／604回読み込み→69ms／4回） | 保留：性能を計測してから |
| OBS-09 | 中 | 起動時の復旧・移行が失敗すると、監視が停止したまま気づけない | `start_obsidian_watcher` の例外時に `stop.set()` して終了する | 操作ノートのチェックに反応せず、利用者には理由が分からない | 監視の状態（稼働中／停止と理由）を `GET /api/config` などに含め、画面に表示する | 対応済み（2026-09-25。`services/obsidian_watcher.WatcherStatus` が状態を持ち、`GET /api/config` と `GET …/obsidian-finishing` の `watcher` で返す。接続ダイアログの「Obsidian監視」と仕上げパネルに停止理由を表示する。例外の本文はリモート閲覧では返さない） | P1：優先 |
| OBS-10 | 中 | Vaultが入れ子になる危険を検出していない | 実環境の `runtime/data/obsidian/` に `.obsidian` と `無題のファイル*.base` があり、親フォルダーが保管庫として開かれた痕跡がある。3つの生成Vaultも同じ `obsidian/` の直下に作られる | 親Vaultの検索・グラフ・リンク解決に、子Vaultのノートが混ざる | Vaultを作成・書き込みする前に、ルートの親方向に `.obsidian` がないか確認し、あれば停止して警告する。痕跡のファイルは削除せず、利用者に案内する | 対応済み（`5d00359`：`vault_registry.nesting_warnings` が上位の `.obsidian` を検出し、`/api/config` と「接続と処理装置」に警告。保存は止めず、痕跡は削除しない） | 保留：生成先の警告を検討。全保存停止案は不採用 |
| OBS-11 | 低中 | 会話を削除した後も、ResearchVaultの概要・一覧が「保存済み」のまま | `_delete_library_item_locked` は `retire_input_vault` だけを呼び、`interviews.json` と概要ノートは更新しない | 削除済みの会話を判別できない | 状態を「アプリから削除済み」に更新する（ノートは来歴として残す） | 対応済み（`a64c1c2`、`bf2a82d`：`ObsidianLayout.mark_deleted`／`clear_deleted`） | P1：優先 |
| OBS-12 | 低中 | 分析ノートに `file:///` の絶対パスリンクを書く | `AnalysisStore.publish` の `local_links` | 端末に依存する。Vaultを共有するとPCのユーザー名などが残る。移動するとリンクが切れる | アプリ経由のURLだけにする。既存のノートは再生成で置き換える（所有hashが一致するものだけ） | 対応済み（`8fd1c3d`：新規ノートはアプリURLだけ。既存ノートは再生成時に置き換わる） | P1：優先 |
| OBS-13 | 低 | 移行処理が、Vault全体の空フォルダーを削除する | `obsidian_migration.migrate` の最後の `rmdir` ループ | 他の環境で初めて移行するとき、利用者の空フォルダーが消える（移行済みの環境では実行されない） | 移行元フォルダーだけに限定する | 対応済み（`5e64bef`：移行でファイルを移したフォルダーと、その結果空になった親だけを削除） | P2：後続 |
| OBS-14 | 中 | パス長の上限を事前に確認していない | 例：`10-インタビュー/I001-<最大48字>/履歴/分析/<run_id 32字>/graph/結果-<手法>-表-01-<最大72字>.md` にデータフォルダーの位置が加わる（未計測） | Windowsで書き込みに失敗し、`vault_status=conflict` になる | 書き込み前にフルパスの長さを計算する。上限を超える場合は、短いID名とtitleで作る。ファイル名の生成を1つの関数にまとめる（`ObsidianLayout.register` の正規表現、`graph_node_path`、`safe_output_stem` を統一） | 対応済み（`dbcc058`：Windowsでは `PATH_LIMIT=250`。グラフノード名とインタビューのフォルダー名を、Vaultの位置に応じてhash付きで短縮。ファイル名生成の一本化（ADR-104）は未着手） | 保留：長いパスで再現・環境条件を確認してから |
| OBS-15 | 中 | Obsidian操作の監査ログがない | `managed_note` のスキップ、`sync_themes` の書き込みは記録されない | 「なぜ更新されないか」「いつ書き換えたか」を追跡できない | 既存の `<data>/obsidian_layout/` に、操作ログ（日時・Vault・相対パス・操作 CREATE／UPDATE／SKIP／CONFLICT／MISSING／MIGRATE・前後hash・理由）をJSON Lines形式で残す。本文は記録しない | 一部対応（2026-09-25。生成ノートの作成・更新・編集の保存・欠落・再作成を `<data>/obsidian_layout/note_changes.jsonl` に記録し、`90-運用/同期状況.md` に表示する。移行・`.obsidian` 設定・`.base`／CSSのスキップは未記録） | 統合 → OBS-09 |
| OBS-16 | 低中 | 大量変更にDry Runがない | `migrate` はバックアップを取るが、変更予定の一覧を事前に出さない | 移行・再生成の影響を事前に確認できない | 移行・一括再生成・リンク変換に「計画のみ」モードを設ける（件数、作成／更新／移動／削除の予定、競合） | 未対応 | 保留：次の一括移行の着手条件 |
| OBS-17 | 低 | 原子的書き込みがロックされたファイルに弱い | `write_atomic` は `os.replace` だけで、フォルダーの `fsync` をしない | 同期ソフトやウイルス対策ソフトがファイルを掴むと失敗する | 短いリトライを入れ、失敗を記録する（ARCH-04と一緒に対応） | 対応済み（`5c2e0e9`：`durable_move` が他プロセスのロック中は短い間隔で5回まで再試行） | 保留：ロック失敗を再現してから |
