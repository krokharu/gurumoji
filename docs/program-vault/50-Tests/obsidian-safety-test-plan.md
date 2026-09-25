---
note_id: tests-obsidian-safety-plan
note_type: test-plan
title: Obsidian連携の安全性テスト計画
status: in-progress
updated: 2026-09-15
tags:
  - gurumoji/program
  - gurumoji/tests
  - gurumoji/obsidian
---

# Obsidian連携の安全性テスト計画

Obsidian連携で、利用者のノートを壊さないことを確認するためのテスト計画。現状の構造は [[20-Modules/obsidian-integration]]、問題IDは [[40-Design/known-issues]] を参照する。2026-09-14にOBS-01/02/05/07、比較API、未保存確認・応答順序の回帰テストを追加した。実装と検証結果は[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]。

## 追加済みの検証（2026-09-14）

| 対象 | テスト | 確認すること |
| --- | --- | --- |
| テーマの保護 | `test_obsidian_layout.py:test_theme_sync_keeps_all_human_bytes_and_tracks_removed_links` | CRLF・YAMLコメント・アンカー・独自タグ・不正YAMLを持つ人のテーマのバイト一致、別の関連ノートの更新・リンク解除・冪等性 |
| 仕上げの保護 | `test_obsidian_layout.py:test_finishing_sync_does_not_read_or_write_researcher_notes` | 人の全文・アウトライン・操作ノートが不正YAMLでも読み書きせず保持 |
| 管理状態の消失 | `test_obsidian_finishing.py:test_missing_state_never_overwrites_existing_initial_notes` | 初期ノートが残る状態で再作成を止め、繰り返しても全ノートを保持 |
| 新規作成の競合 | `test_obsidian_finishing.py:test_create_only_write_preserves_a_concurrent_file` | 作成直前に他者が同名ノートを置いても上書きせず、一時ファイルを除去 |
| 比較の保存契約 | `test_interview_comparison.py:test_browser_requests_require_csrf_and_save_the_displayed_input_version` | CSRF拒否と正常送信、版なし400・版違い409、同一要求の重複排除 |
| UIからの保存と移動 | `test_browser_e2e.py:test_comparison_and_unsaved_navigation_regressions` | 実ブラウザーで比較の集計・保存、処理中の条件固定、未保存取消、逆順応答と画面移動後の応答無視 |
| 準備の更新待ち伝播 | `test_vault_coverage.py:test_preparation_save_invalidates_single_and_comparison_runs_atomically` | 単独・比較履歴のstale、Vault状態への反映、トランザクション取消時の整合 |

以下の対応表もコミット`1b8fe41`のテスト実装へ更新した。「あり」は記載範囲の検証があることを示し、機能全体の安全性の保証ではない。全393件成功は収録前の検証記録で、2026-09-15の資料更新では再実行していない。

## 原則

- 利用者の実際のVault（`runtime/data/obsidian/**`、個人のVault）は使わない。
- 既存のテストは `tempfile.TemporaryDirectory` と `patch.object(app, "DATABASE_FILE", …)` を使って、一時フォルダーで実行している（例：`tests/test_interview_comparison.py`）。この方式を続ける。
- 手動で確認する場合は、`MOJIOKOSI_DATA_DIR` を一時フォルダーに向けてアプリを起動し、テスト用Vaultのコピーを Obsidian で開く。
- テストデータは架空の内容にし、実際の会話・参加者情報は使わない。

## テスト用Vault（fixture）の構成案

`tests/fixtures/obsidian-safety-vault/`（未作成）。テスト開始時に一時フォルダーへコピーしてから使う。

```text
obsidian-safety-vault/
  .obsidian/app.json, bookmarks.json（利用者の独自グループ入り）, appearance.json
  日本語タイトル.md
  English Title.md
  空白 と 記号 (テスト) & ＃.md
  frontmatter-配列.md          tags: [a, b]、aliases、コメント付きYAML、日付、null、複数行文字列
  wikilinks.md                 [[日本語タイトル]]、[[日本語タイトル|別名]]、[[日本語タイトル#見出し]]、
                               [[日本語タイトル#見出し|別名]]、[[日本語タイトル#^block1]]、![[画像.png]]、![[English Title]]
  block.md                     段落 ^block1、callout、コードフェンス内の [[リンク風文字列]]
  同名/メモ.md、別/メモ.md       同名ノート
  深い/入れ子/フォルダー/…/長いファイル名（Windowsのパス長上限付近）.md
  20-テーマ/働き方.md           利用者タグ graph/custom、独自プロパティ、利用者が書いた本文
  80-添付/画像.png、日本語 添付.pdf
```

## 要件と既存テストの対応

| 要件 | 既存テスト | 状態 | 不足している点 |
| --- | --- | --- | --- |
| 新規作成：Markdown生成・根拠リンク | `test_analysis_storage.py`: `test_full_package_catalog_notes_links_and_idempotency_without_ai`、`test_saved_analysis_builds_visible_type_result_and_outline_graph_nodes` | あり | なし |
| 新規作成：frontmatter・日本語 | `test_obsidian_finishing.py`: `test_recording_is_one_note_and_arbitrary_text_round_trips`、`test_native_properties_blocks_and_legacy_notes_round_trip` | 一部 | 記号や空白を含むタイトル、YAMLで特別な意味を持つ値（`yes`、`null`、`:`） |
| 新規作成：危険な文字列のエスケープ | `test_analysis_storage.py`: `test_raw_quotes_are_preserved_and_unsafe_markdown_is_escaped`、`test_path_traversal_request_validation_and_formula_safety` | あり | なし |
| 新規作成：添付 | 議事録のCSV／JSONについては未確認 | 不明 | 同じ名前の添付を上書きしないこと、日本語の添付名 |
| 更新：人のノートを変更しない | `test_obsidian_layout.py`: `test_theme_sync_keeps_all_human_bytes_and_tracks_removed_links`、`test_finishing_sync_does_not_read_or_write_researcher_notes` | あり | 一般的な生成ノートと`.obsidian`の保護は別課題（OBS-03／04） |
| 競合：外部で編集した生成ノートを上書きしない | `test_four_vaults.py`: `test_human_edits_and_deletions_are_preserved_not_overwritten`、`test_analysis_storage.py`: `test_human_notes_are_never_overwritten_and_retry_never_calls_ai` | あり | ナビゲーションノート（`managed_note`）の、何も通知しないスキップの記録 |
| 競合：処理中の編集 | `test_obsidian_finishing.py`: `test_edit_during_finishing_is_preserved_and_cannot_be_applied`、`test_source_edit_after_generation_blocks_apply` | あり | なし |
| 競合：人のノートへの同期書き込み | `test_obsidian_layout.py`のテーマ・仕上げ保護2件 | あり | 人のノートに書かない方式で解決。生成ノート一般のhash照合直後の競合（OBS-04）は未検証 |
| 競合：状態を失った後に作業台を作り直す | `test_obsidian_finishing.py`: `test_missing_state_never_overwrites_existing_initial_notes`、`test_create_only_write_preserves_a_concurrent_file` | あり | 自動復元ではなく、既存ノートを保持して停止することを検証 |
| リネーム・移動 | `test_obsidian_finishing.py`: `test_metadata_edits_and_moved_notes_preserve_finishing_and_apply`、`test_ambiguous_moved_note_is_rejected` | あり（仕上げのみ） | 分析ノートを移動した後に再保存しても、再作成・二重作成しないこと。Wikilinkの全形式が移行後も保持されること（`rewrite_links` の単体テストは一部あり） |
| 削除：復元可能 | `test_vault_coverage.py`: `test_deleted_conversation_keeps_a_marked_ledger`、`test_obsidian_layout.py`: `test_deleted_conversation_is_marked_and_notes_are_kept`、`test_four_vaults.py`: `test_deleting_conversation_marks_research_vault_and_keeps_notes` | 一部 | メディアをゴミ箱から復元できること（DATA-01。未実装） |
| 重複：2回処理しても二重に生成しない | `test_analysis_storage.py`のidempotency、`test_four_vaults.py`の再公開、`test_obsidian_finishing.py`のラッチ、`test_obsidian_layout.py`のテーマ同期 | あり | テーマの別ノートも2回目はバイト一致。元テーマは初回から変更しない |
| 異常終了：書き込み途中 | `test_analysis_storage.py`: `test_mid_write_failure_retries_deterministically_and_detects_tamper`、`test_interrupted_save_recovers_original_package_after_edit_without_reanalysis`、`test_obsidian_layout.py`: `test_interrupted_migration_resumes_from_same_backup` | 一部 | `VaultRegistry` の `pending` hashからの回復。`os.replace` が失敗したときに一時ファイルが残らないこと |
| 移行：リンクと引用 | `test_obsidian_layout.py`: `test_migration_updates_catalog_links_and_preserves_literal_quotes_and_backup`、`test_legacy_fences_and_quote_literals_are_never_rewritten` | あり | 利用者が作った空フォルダーを削除しないこと（OBS-13）、Dry Run（OBS-16） |
| Vaultの誤認：入れ子・書き込み禁止のルート | `test_four_vaults.py`: `test_software_and_research_vaults_are_not_generated_roots` | 一部 | 親フォルダーに `.obsidian` がある場合に停止すること（OBS-10） |
| `.obsidian` を変更しない | `test_obsidian_layout.py`（ワークスペース編集の保持） | 一部 | 既存Vaultの `core-plugins.json`・`appearance.json` を変更しないこと（OBS-03、ADR-103 の採用後） |
| ファイル名：禁止文字・末尾・同名・長さ | なし | なし | `register`、`graph_node_path` の規則とパス長の上限（OBS-14） |
| CSRF：ブラウザー由来のPOST | `test_interview_comparison.py`: `test_browser_requests_require_csrf_and_save_the_displayed_input_version`、`test_browser_e2e.py`: `test_comparison_and_unsaved_navigation_regressions` | あり | Origin／Sec-Fetchヘッダーと実ブラウザーで比較・保存を検証。`apiFetch`内部の`window.fetch`は許可する |
| 監視：停止の表示・ログ | `test_obsidian_finishing.py`: `test_application_watcher_executes_saved_checkbox_and_stops` | 一部 | `recover`・`migrate` が失敗したときに状態として公開されること（OBS-09）、操作ログに本文が含まれないこと（OBS-15） |

## 追加するテストケース（期待する結果）

1. **テーマノートを変更しない（OBS-01、07、追加済み）**
   - 準備：fixtureの `20-テーマ/働き方.md` を用意する。
   - 操作：`sync_themes` を2回実行する。
   - 期待：人のノートは初回からバイト一致。別の関連ノートだけを更新し、2回目は差分が出ない。
2. **人のノートへの同期書き込みをなくす（OBS-01、02、追加済み）**
   - 準備：人のテーマ・作業ノートへ独自プロパティと不正YAMLを含む内容を入れる。
   - 期待：人のノートを同期対象として読まず、書き込みも発生しない。生成ノート一般の書き込み直前競合（OBS-04）は別途必要。
3. **状態ファイルを失ってから作り直す（OBS-05、追加済み）**
   - 操作：`prepare` の後に全文ノートを編集し、`state.json` を削除して再度 `prepare` する。
   - 期待：編集した全文とほかの初期ノートが残り、復元確認のエラーで停止する。別パスの新規作成や既存ノートの自動採用はしない。
4. **Vaultの入れ子（OBS-10）**
   - 準備：`<data>/obsidian/.obsidian` を作る。
   - 期待：`publish_input` と `publish_navigation` がエラーで停止し、ファイルを作らない。
5. **ファイル名（OBS-14）**
   - 入力：`CON`、`a:b*c?`、末尾が `.` や空白、260文字に近いタイトル、同じタイトルが2件。
   - 期待：保存できる。上書きしない。パスが上限以内になる。
6. **Wikilinkの保持**
   - 準備：fixtureの `wikilinks.md` を、アプリ所有ではない場所に置く。
   - 操作：移行、テーマ同期、ナビゲーション再生成を実行する。
   - 期待：内容のバイト列が変わらない。
7. **添付**
   - 操作：同じ議事録を2回保存する。
   - 期待：添付は増えず、既存の添付も変わらない。日本語の添付名が扱える。
8. **CSRF（BUG-01、追加済み）**
   - 操作：`Origin: http://127.0.0.1:7860` と `Sec-Fetch-Site: same-origin` を付けて、比較APIへPOSTする。
   - 期待：ヘッダーがなければ403、`X-Gurumoji-Request: 1` があれば200。あわせて `static/*.js` に `apiFetch` 以外の `fetch(` がないことを検査する。
9. **削除後の表示（OBS-11）**
   - 操作：会話を削除する。
   - 期待：概要ノートの状態が「アプリから削除済み」になり、ノートは残る。
10. **操作ログ（OBS-15）**
    - 操作：作成・更新・競合・スキップを発生させる。
    - 期待：ログに操作とhashが残り、発話本文・APIキーは含まれない。

## 実行方法

リポジトリルートで、プロジェクトの仮想環境を使う。`src`と`tests`は子プロセスにも渡す。

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + (Join-Path (Get-Location) 'tests')
& .\.venv\Scripts\python.exe -X utf8 -m unittest test_obsidian_layout test_obsidian_finishing test_analysis_storage test_four_vaults test_vault_coverage -v
```

全体の実行は`& .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py"`。ブラウザーテストにはEdge／Chromeが必要。テストは一時DB・一時Vaultを使用する。アプリの起動を併用する場合は、原則に従い`MOJIOKOSI_DATA_DIR`・`MOJIOKOSI_OUTPUT_DIR`も一時フォルダーへ向ける。

結果を記録するときは、実行日、対象のcommit（または作業ツリー）、成功・失敗・スキップの理由を書く（[[20-Modules/module-map]]）。
