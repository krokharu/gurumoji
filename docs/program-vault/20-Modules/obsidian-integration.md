---
note_id: program-obsidian-integration
note_type: module
title: Obsidian連携の現状構造と安全性
summary: ResearchVaultと生成4 Vaultの書き込み経路、所有情報、競合・移行の現行実装を示す。
status: current
feature: obsidian-storage
verified: 2026-09-14
tags:
  - gurumoji/program
  - gurumoji/obsidian
---

# Obsidian連携の現状構造と安全性

- **確認元：** `src/gurumoji/obsidian_layout.py`、`obsidian_finishing.py`、`obsidian_migration.py`、`vault_registry.py`、`analysis_store.py`、`app.py`（`start_obsidian_watcher`、`run_obsidian_finishing`、`publish_input_vault`、`publish_meeting_minutes_to_obsidian`）、`web/library_deletion.py`（`_delete_library_item_locked`）。
- **確認条件：** 作業ツリー（2026-09-14）。OBS-01/02/05/07の優先修正を反映済み。[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]。
- **関連ノート：** 危険箇所の対応状況は [[40-Design/known-issues]] の `OBS-*` で管理する。改善方針は [[40-Design/convergence-plan]] と [[40-Design/decisions]] に書く。利用者向けの操作手順は `docs/OBSIDIAN_FINISHING.md` と `docs/OBSIDIAN_GRAPH.md` にある。

## 接続方法

- Obsidianプラグインではない。Pythonアプリが、Vaultフォルダー内のMarkdown・JSONを `pathlib` で直接読み書きする。Obsidian本体との通信やAPI呼び出しはない。Obsidianを閉じていてもアプリは動作する。
- Obsidian Plugin API（`Vault.process`、`FileManager.processFrontMatter`、`normalizePath`、ゴミ箱への移動）は使えない。代わりに次の処理を自前で実装している。
  - `analysis_store.safe_path`：相対パスだけを許可する。`\`・`:`・`..`・`.` は拒否する。途中のシンボリックリンクとジャンクションも拒否し、ルートの外を指すパスを拒否する。
  - `analysis_store.write_atomic`：同じフォルダーに `.<name>.<uuid>.tmp` を作り、`fsync` してから `os.replace` で置き換える。`create_only=True`の場合は`os.link`で排他的に新規作成し、既存ファイルを置き換えない。いずれも一時ファイルを後片付けする。フォルダーの `fsync` はしない。
  - hash台帳：アプリが書いた内容のhashを記録し、ファイルが変わっていれば上書きしない（書き込み主体によって挙動が異なる。下記参照）。
- 開く操作は `obsidian://open?path=<絶対パス>` のURIだけで行う（`ObsidianWorkbench.public`、`AnalysisStore.public`）。

## Vaultの指定方法

| Vault | ルート | 決め方 | アプリの書き込み |
| --- | --- | --- | --- |
| ResearchVault | `<data>/obsidian/ResearchVault` | `ObsidianLayout.__init__`、`ObsidianWorkbench.__init__`、`AnalysisStore.__init__` の3か所で、それぞれ `database_file.parent` から算出 | する |
| Input／Visualization／Orchestrator | `<data>/obsidian/InputVault` など | `vaults.json` の `root`。`obsidian/<英数字_->` だけを許可し、`ResearchVault` と重複は拒否（`VaultRegistry.root`、`roots`） | する |
| Software | `docs/program-vault` | `vault_registry.SOFTWARE_ROOT` と、`app.vault_registry()` から渡す引数の2か所 | しない（`_write` が拒否） |

- `<data>` は `MOJIOKOSI_DATA_DIR`、未設定なら `runtime/data`。
- Vaultの場所を変える設定UIはない。
- 利用者のDocuments配下や既存Vaultを探したり推測したりする処理はない。
- アプリ専用のVaultは、存在しなければアプリが作成する。

## 保存場所とノートの種類

### ResearchVault

| パス | 内容 | 書く処理 | 所有 |
| --- | --- | --- | --- |
| `00-ホーム.md`、`01-分析結果.md`、`インタビュー一覧.base`、`10-インタビュー/インタビュー一覧.md`、`90-運用/使い方.md`、`40-研究/分析手法/<group>.md` | ナビゲーション | `ObsidianLayout.publish_navigation` → `managed_note` | アプリ（hashで確認） |
| `10-インタビュー/I###-<名前>/I###-概要.md` | インタビューの入口 | `ObsidianLayout.update` → `managed_note` | アプリ（hashで確認） |
| `…/I###-研究メモ.md` | 研究者のメモ | 無いときだけ作成 | 研究者 |
| `…/I###-保存原文.md`、`I###-全文.md`、`I###-アウトライン.md`、`I###-操作.md`、`I###-状態.md` | 仕上げの作業台 | `ObsidianWorkbench.prepare` → `save_note` | 全文・アウトライン・操作は研究者（`managed_by: researcher`）、状態・原文はアプリ |
| `…/履歴/仕上げ/I###-{アウトライン,仕上げ結果,仕上げ後アウトライン}-<run>.md` | AIの生成版。常に新しいパス | `ObsidianWorkbench.execute` | 結果は研究者が編集してよい |
| `…/I###-会議議事録-r<rev>-<hash>.md`、`…/添付/I###-{タスク,連携}-*.{csv,json}` | 会議議事録と添付 | `ObsidianWorkbench.publish_meeting_minutes` | アプリ（既存なら書かない） |
| `…/I###-分析まとめ.md`、`…/履歴/分析/<run>/…`、`…/履歴/引用/<snapshot>/part-*.md`、`40-研究/インタビュー比較/comparison-<run>.md`、`90-運用/Gurumoji-SavedAnalyses.md` | 分析結果・引用原文・グラフ用ノード | `AnalysisStore.write_note` | アプリ（SQLite `obsidian_notes` のhashで確認） |
| `20-テーマ/*.md` | テーマ。研究者が作成する | `sync_themes`は存在確認だけを行い、読み書きしない | 研究者 |
| `40-研究/テーマ関連/<hash>.md` | テーマとインタビューの関連一覧 | `sync_themes` → `managed_note` | アプリ（hashで確認。編集・削除済みなら保持） |
| `.obsidian/core-plugins.json`、`appearance.json`、`bookmarks.json`、`workspaces.json`、`workspace.json`、`graph.json`、`snippets/gurumoji-reading.css` | 表示設定 | `ObsidianLayout.configure` | 利用者（アプリも書く） |

### 3つの生成Vault

`00-Home.md`、`00-Index.md`、`10-Inputs`、`20-Snapshots`、`10-Visuals`、`10-Methods`、`20-Runs`、`99-Archive`、`.obsidian/app.json`（無いときだけ `{}` を作成）。ファイル名はASCIIのIDだけ。詳細は [[30-Data/four-vaults-v1]]。

### Vault外の制御ファイル

| ファイル | 内容 |
| --- | --- |
| `<data>/obsidian_layout/interviews.json` | 会話IDとインタビューコード・フォルダーの対応。`managed` にナビ系ノートのhashを保存 |
| `<data>/obsidian_layout/vaults.json` | 3 Vaultのルート、ノートごとの `sha256`・`pending`・`sync` |
| `<data>/obsidian_layout/migration-v1.json`、`migration-pending.json`、`backup-*` | 移行記録とバックアップ |
| `<data>/obsidian_workbench/<sha(item)>/state.json` ほか | 仕上げの状態、`note_ids`、元ノートのfingerprint、候補結果 |
| SQLite `obsidian_notes`、`analysis_runs.note_path`・`vault_status` | 分析ノートのhashと公開状態 |

## データフロー

### アプリ → Obsidian

```text
操作（保存・分析保存・ジョブ完了・仕上げ）
  → 正本を先に確定（SQLite / analysis_store / output）
  → ノート本文を文字列連結で生成（markdown() でエスケープ、発話は引用ブロック＋^s-<hex>）
  → プロパティを付与（生成関数は4種類。後述）
  → 保存先を決定（interviews.json のコードとフォルダー、または ID によるASCIIパス）
  → safe_path で検証 → 所有hashを照合 → write_atomic
  → 台帳にhashを記録（obsidian_notes / interviews.json / vaults.json / state.json）
  → ナビゲーション・索引・.obsidian を更新
```

### Obsidian → アプリ

| 読み込み | 実装 | アプリへの反映 |
| --- | --- | --- |
| 操作ノートのチェックと `provider` | `ObsidianWorkbench.selection`（64KB上限） | AI実行のきっかけ（状態をラッチ） |
| 全文・結果ノートの発話本文 | `parse_transcript`（ブロックIDの順序と一致を必須とする） | 「結果をアプリへ反映」のときだけDBへ保存 |
| アウトラインノート | `parse_outline`（`##` 見出しと箇条書き） | AI仕上げの参照。反映時に出力用アウトラインとして保存 |
| ノートの移動先 | `locate_note`（Vault全体の `.md` の先頭65KBから `note_id` を探す） | `state.json` のパスを更新 |
| 研究メモのテーマリンク | `sync_themes`（コードブロックを除いた `[[20-テーマ/…]]`） | 別の生成ノートに関連一覧を書く（DBには入れない） |
| 旧階層の全ノートのプロパティ | `migrate` | パスの対応表とDB参照を更新 |

研究メモ・解釈・コード案のDBへの取り込みは未実装（[[40-Design/sync-contract]]）。

## Markdownの生成方法

- テンプレートエンジンは使わず、Pythonの文字列連結で組み立てる。
- 本文は `analysis_store.markdown()` でエスケープする（`html.escape` のあと、Markdown記号をバックスラッシュでエスケープ）。
- 原文は引用ブロックにする。表のセルには160文字までしか入れない。
- 長い原文は200発話ごとにページを分ける（`AnalysisStore.source_notes`）。
- callout（`> [!info]` など）を使う。プラグインは使わない。

## Frontmatter（Properties）

| 処理 | 実装 | 方式 | 注意 |
| --- | --- | --- | --- |
| 生成 | `analysis_store.frontmatter` | 1行ずつ `key: <json.dumps>` | JSON形式の値（YAMLとしても有効） |
| 生成 | `obsidian_layout.pack` | `yaml.safe_dump`（`sort_keys=False`） | 全体を再生成する |
| 生成 | `obsidian_finishing.with_properties` | `yaml.safe_dump`（ブロック形式） | 同上 |
| 生成 | `VaultRegistry._write` 内 | `yaml.safe_dump` | 同上 |
| 解析 | `obsidian_layout.unpack` | 先頭の `---` 区間を `yaml.safe_load` | サイズ上限なし。YAMLのエラーはそのまま例外 |
| 解析 | `obsidian_finishing.split_properties` | 同上 | 64KB上限。エラーを日本語メッセージに変換 |

`ObsidianLayout.decorate`は生成する文字列のプロパティを整える。人が編集した既存の仕上げノートに対する`sync_finishing`からの再シリアライズは廃止した。`sync_themes`もテーマ本文・プロパティを読み書きせず、別の生成ノートへ関連情報を保存する。

- 人のノートのYAMLコメント・引用形式・アンカー・未知のキー・独自タグ・改行はバイト単位で保持する。
- 仕上げノートの`graph/*`等は作成時点のまま。最新版の場所は概要と状態ノートを使う。
- 生成ノートは全体を再生成するが、所有hashが異なる既存内容を上書きしない。一般的なhash確認直後の競合はOBS-04として残る。

## Wikilink

- 生成するリンクは次の3形式。Vault内の完全パスで、拡張子なし。
  - `[[<path>|<alias>]]`
  - `[[<path>#^s-<hex>|<label>]]`
  - `[[<path>]]`
- ブロックIDは `^s-` の後に、発話IDのUTF-8バイト列をhex化した値を付ける（Obsidianのブロック ID の文字制約への対応）。
- Vaultをまたぐリンクは作らず、IDで対応付ける（[[30-Data/four-vaults-v1]]）。
- アプリにはノートを改名する処理がない。移動・改名されたノートは、仕上げの場合 `note_id` で探す。分析ノートは `missing`／競合として扱い、再作成しない。リンクの追従はObsidianの「内部リンクを自動更新」に依存する。
- 移行処理 `rewrite_links` は `[[…]]` の中身だけを対応表で置き換え、`#heading`、`|alias`、`#^block` の部分は残す。引用行（`>`）とコードフェンスの中は書き換えない。正規表現は `![[…]]` の内側にも一致するため、埋め込みも移動先に置き換わる。
- テーマ同期は、`![[…]]` と、エスケープされた `\[[` を関連付けに使わない。

## 添付ファイル

- アプリが作る添付は、会議議事録の `タスクCSV` と `連携JSON` だけ。保存先は各インタビューの `添付/` フォルダー。
  - ファイル名にrevisionと内容hashを含め、同じ名前のファイルがあれば書かない。
  - Obsidianの「添付ファイルの保存場所」設定は読まない。
- `80-添付/` はフォルダーを作るだけで、アプリは使っていない。
- 分析の表CSVはVaultへ複製しない。ノートにはアプリ経由のURL（`http://127.0.0.1:<port>/api/analysis/artifacts/<id>`）だけを書く。端末固有の `file:///` 絶対パスは新しく書かない（OBS-12）。既存ノートに残るリンクは、そのノートが再生成されたときに置き換わる。
- 画像添付と、既存添付の移動・削除を行う処理はない（移行処理では `80-Attachments/` → `80-添付/` へ移す）。

## 書き込み主体ごとの競合処理

| 書き込み主体 | 対象 | 所有・変更の判定 | 外部で編集済みの場合 | 外部で削除・移動済みの場合 |
| --- | --- | --- | --- | --- |
| `VaultRegistry._write` | 3 Vaultの全ノート | `vaults.json` の `sha256`・`pending`（書き込み前に予定hashを記録） | `conflict`。上書きせず索引に表示 | `missing`。再作成しない |
| `AnalysisStore.write_note` | ResearchVaultの分析ノート | SQLite `obsidian_notes.sha256` | `StoreConflict`。`vault_status=conflict` | `StoreConflict`。再作成しない |
| `ObsidianLayout.managed_note` | ナビ・概要・CSSスニペット | `interviews.json` の `managed` hash | 何も通知せずスキップ（ログなし） | **再作成する** |
| `ObsidianWorkbench.save_note`、`note` | 仕上げノート、状態ノート | 状態以外は排他的な新規作成。状態は毎回更新。管理状態を失い初期ノートが残る場合は停止 | 状態以外は同名ノートがあれば停止して保持 | 新しい生成パスに作成。移動済み作業ノートは既存の探索規則に従う |
| `ObsidianLayout.sync_finishing` | 概要・ナビゲーション | 生成側の所有hashを確認。人の作業ノートは読み書きしない | 人の編集をそのまま保持 | 人のノートは作らない |
| `ObsidianLayout.sync_themes` | `40-研究/テーマ関連/*.md` | `managed_note`の所有hash。人のテーマノートは存在確認のみ | 生成関連ノートの競合は警告しスキップ | 管理済み関連ノートの欠落は再作成しない |
| `ObsidianLayout.configure` | `.obsidian/*.json` | **判定なし**。読んで変更して書く。CSSスニペットだけ `managed_note` | 利用者の設定を変更する。Obsidianが起動中なら互いに上書きしうる（OBS-03） | 作成する |
| `ObsidianWorkbench.execute`（反映） | DB | revision一致、元ノートのfingerprint一致、反映中の結果ノートの変更なし、`library_write_lock` | 停止してエラーを状態ノートに表示 | `note_id` で1件に特定できなければ停止 |
| `obsidian_migration.migrate` | ResearchVault全体 | バックアップと移行前後のhash | 中断（`ValueError`） | 移行先に別の内容があれば中断 |

## 同期とファイル監視

- 監視は、OSのファイル監視APIではなくポーリングで行う。`app.py` の `start_obsidian_watcher` がデーモンスレッドを1本起動する（`main` から起動する場合だけ）。
  1. 最初に `ObsidianWorkbench.recover`（`running` の状態を `interrupted` にする）と `migrate` を実行する。
  2. その後、2秒ごとに `poll_once`、10秒ごとに `sync_themes` を実行する。
- ループを防ぐ仕組みは次のとおり。
  - 操作ノートの選択が、前回確認した選択（`observed`）と同じなら何もしない（ラッチ）。再実行するには、一度チェックを外して保存する必要がある。
  - AIの生成物は常に新しいパスに書くため、監視対象の元ノートを書き換えない。
  - テーマ同期と生成Vaultへの書き出しは、生成結果が同じなら書かない（冪等）。
  - 反映後に更新するのは別のVault（InputVault）とDBで、操作ノートは状態ノート経由の表示だけ。
- 起動時の `recover`・`migrate` が失敗すると、監視スレッドは停止する。画面への通知はない（OBS-09）。

## エラー処理

- Vaultへの書き出しに失敗しても、正本（文字起こし・編集保存・分析の固定保存）は失敗させない。該当する処理は `publish_input_vault`、`retire_input_vault`、`AnalysisStore.publish_vaults`、`refresh_archive_index`。失敗は `logging` のwarningに出すか、`vault_status` に記録する。
- 仕上げの例外は `state.json` と状態ノートに `error` として表示する。
- 監視ループの例外はログに出して継続する。
- `managed_note`一般のスキップ記録はない。テーマ同期では生成関連ノートの競合と研究メモの解析失敗をwarningに出す。Obsidian操作全体の監査ログ（作成・更新・競合・スキップ）はない（OBS-15）。

## バックアップ

- 自動バックアップは移行処理だけ。Vault、`obsidian_workbench`、`analysis_store`、`interviews.json`、SQLite（backup API）を `obsidian_layout/backup-<uuid>` にコピーする。
- 通常の書き込みでは、上書き前のバックアップを取らない。所有hashが一致するノートだけを上書きする設計に依存している。
- 手動の手順は `docs/PROJECT_LAYOUT.md`（アプリを停止して `runtime/` 全体をコピー）と `docs/OBSIDIAN_VAULTS.md` にある。

## 削除方法

- アプリは通常動作でVaultのノートを削除しない。
- 会話を削除しても、ResearchVaultのノート、`interviews.json` の登録、`obsidian_workbench` はそのまま残る。概要ノートは「保存済み」の表示のまま（OBS-11）。InputVaultの台帳は `status: deleted` になる。
- ゴミ箱（`.trash` やOSのごみ箱）への移動はない。
- 移行処理だけは、バックアップ後に内容が変わっていない移行元ファイルを `unlink` し、Vault全体の空フォルダーを `rmdir` する（OBS-13）。

## テスト方法

- 既存の自動テストは、すべて一時ディレクトリにDB・Vaultを作る。実際のVaultは使わない。
  - `tests/test_obsidian_layout.py`
  - `tests/test_obsidian_finishing.py`
  - `tests/test_analysis_storage.py`
  - `tests/test_four_vaults.py`
  - `tests/test_vault_coverage.py`
- Obsidian実機での表示確認は `scripts/check_obsidian_graph.py`（CLIを有効にした環境）で行う。
- 不足しているケースと、テスト用Vaultの設計は [[50-Tests/obsidian-safety-test-plan]] にまとめた。

## 制限事項

- Obsidian公式APIに相当する安全策（原子的な内容の変更、frontmatterの部分更新、ゴミ箱、パスの正規化）は自前の実装で、機能が限られる。
- ポーリングのため、変更の反映に2〜10秒かかる。
- Windowsのパス長上限（260文字）を超える深いパスを事前に確認していない（OBS-14）。
- 同期ソフトやウイルス対策ソフトがファイルをロックすると、`os.replace` が失敗しうる。
- 利用者がVaultの親フォルダーを保管庫として開くと、Vaultが入れ子になる（実環境に痕跡あり、OBS-10）。

## 今後変更するときの注意事項

1. 新しい書き込み処理を作らない。まず [[40-Design/decisions]] ADR-101 の方針（1つの書き込み関数、書き込み前の予定hash、conflict・missingの表示）に合わせる。
2. 人が所有するノートの全体を再生成して上書きしない。テーマと仕上げノートにはADR-109を適用し、関連情報・現在の参照を別の生成ノートへ書く。hash再確認だけを外部編集に対する排他保証と扱わない。`.obsidian`の設定保護はOBS-03として残る。
3. Vaultのパスは既存の算出元から得る。新しくパスを組み立てない。ユーザーのVaultを推測しない。
4. 判断できない状態では書かずに止め、理由を状態ノート・索引・ログに残す。対象は、Vaultが特定できない、同じ名前がある、YAMLを解析できない、`note_id` が重複している、revisionが一致しない、など。
5. 削除・移動・一括変換を追加する場合は、バックアップ、変更予定の一覧を出すDry Run、再開可能な記録を先に設計する。
6. 変更したら、このノートの該当箇所、[[40-Design/known-issues]]、[[50-Tests/obsidian-safety-test-plan]]、利用者向けの `docs/OBSIDIAN_*.md` を同じレビュー単位で更新する。

## 危険箇所の要約（G）

| ID | 重要度 | 内容 |
| --- | --- | --- |
| OBS-01 | 高 | テーマ同期が、研究者のテーマノートを所有確認なしで10秒ごとに再シリアライズ・上書きする |
| OBS-04 | 高 | 書き込み主体が5つあり、台帳が4つ、競合時の挙動も4通り |
| OBS-02 | 中高 | 仕上げノートのプロパティ更新に、読み込みから書き込みまでの間の変更検出がない |
| OBS-05 | 中 | `state.json` を失ったり片側だけ復元したりすると、作業台の初期ノートが上書きされうる |
| OBS-03 | 中 | `.obsidian` の設定をアプリが変更する |
| OBS-10 | 中 | Vaultの入れ子の痕跡があるのに、検出していない |
| OBS-06／07 | 中 | frontmatterの実装が複数あり、全体を再シリアライズする |
| OBS-09／15 | 中 | 監視の停止とスキップが見えない |
| OBS-11／12／13／14 | 低〜中 | 削除後の表示、`file:///` 絶対パス、移行時の空フォルダー削除、パス長 |
