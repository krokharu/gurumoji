---
note_type: reference-section
status: in-progress
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/tests
- gurumoji/obsidian
note_id: tests-obsidian-safety-plan-section-02
title: Obsidian連携の安全性テスト計画：原則
summary: 原則。出典ノート「Obsidian連携の安全性テスト計画」の分割本文。
parent_note_id: tests-obsidian-safety-plan
source_path: 50-Tests/obsidian-safety-test-plan.md
source_sha256: 5244a19b68353e0baee8e78523afc1299e1d0d9188c030b57c1153b7afb63f7b
source_body_lines:
- 20
- 71
split_on: '2026-10-11'
---

# Obsidian連携の安全性テスト計画：原則

親索引・状態・確認版：[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index]]。必要な本文だけを取得する。

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
| 生成ノートの初版・編集履歴・更新判定 | `test_vault_note_policy.py`: `test_new_note_keeps_its_first_version_in_the_interview_history`、`test_researcher_edit_is_kept_then_latest_version_is_written`、`test_note_written_before_this_policy_gets_its_first_copy_before_update` | 一部 | Windowsで旧ノートのCRLFとテストのLF hashが異なると、同内容でも`edit_saved`になる。履歴は保持されるが、改行正規化と分類を確認する |
| 新規作成：添付 | 議事録のCSV／JSONについては未確認 | 不明 | 同じ名前の添付を上書きしないこと、日本語の添付名 |
| 更新：人のノートを変更しない | `test_obsidian_layout.py`: `test_theme_sync_keeps_all_human_bytes_and_tracks_removed_links`、`test_finishing_sync_does_not_read_or_write_researcher_notes` | あり | 一般的な生成ノートと`.obsidian`の保護は別課題（OBS-03／04） |
| 競合：外部で編集した生成ノートを上書きしない | `test_four_vaults.py`: `test_human_edits_and_deletions_are_preserved_not_overwritten`、`test_analysis_storage.py`: `test_human_notes_are_never_overwritten_and_retry_never_calls_ai` | あり | ナビゲーションノート（`managed_note`）の、何も通知しないスキップの記録 |
| 競合：処理中の編集 | `test_obsidian_finishing.py`: `test_edit_during_finishing_is_preserved_and_cannot_be_applied`、`test_source_edit_after_generation_blocks_apply` | あり | なし |
| 競合：人のノートへの同期書き込み | `test_obsidian_layout.py`のテーマ・仕上げ保護2件 | あり | 人のノートに書かない方式で解決。生成ノート一般のhash照合直後の競合（OBS-04）は未検証 |
| 競合：状態を失った後に作業台を作り直す | `test_obsidian_finishing.py`: `test_missing_state_never_overwrites_existing_initial_notes`、`test_create_only_write_preserves_a_concurrent_file` | あり | 自動復元ではなく、既存ノートを保持して停止することを検証 |
| リネーム・移動 | `test_obsidian_finishing.py`: `test_metadata_edits_and_moved_notes_preserve_finishing_and_apply`、`test_ambiguous_moved_note_is_rejected` | あり（仕上げのみ） | 分析ノートを移動した後に再保存しても、再作成・二重作成しないこと。Wikilinkの全形式が移行後も保持されること（`rewrite_links` の単体テストは一部あり） |
| 削除：復元可能 | `test_vault_coverage.py`: `test_deleted_conversation_keeps_a_marked_ledger`、`test_obsidian_layout.py`: `test_deleted_conversation_is_marked_and_notes_are_kept`、`test_four_vaults.py`: `test_deleting_conversation_marks_research_vault_and_keeps_notes` | あり | `test_backend_safety.py` のゴミ箱の5件（削除→復元で行が一致、競合の拒否と完全削除、保持期間、起動時の保留項目の完了・破棄）でDATA-01も確認 |
| 重複：2回処理しても二重に生成しない | `test_analysis_storage.py`のidempotency、`test_four_vaults.py`の再公開、`test_obsidian_finishing.py`のラッチ、`test_obsidian_layout.py`のテーマ同期 | あり | テーマの別ノートも2回目はバイト一致。元テーマは初回から変更しない |
| 異常終了：書き込み途中 | `test_analysis_storage.py`: `test_mid_write_failure_retries_deterministically_and_detects_tamper`、`test_interrupted_save_recovers_original_package_after_edit_without_reanalysis`、`test_obsidian_layout.py`: `test_interrupted_migration_resumes_from_same_backup` | 一部 | `VaultRegistry` の `pending` hashからの回復。`os.replace` が失敗したときに一時ファイルが残らないこと |
| 移行：リンクと引用 | `test_obsidian_layout.py`: `test_migration_updates_catalog_links_and_preserves_literal_quotes_and_backup`、`test_legacy_fences_and_quote_literals_are_never_rewritten` | あり | 利用者が作った空フォルダーを削除しないこと（OBS-13）、Dry Run（OBS-16） |
| Vaultの誤認：入れ子・書き込み禁止のルート | `test_four_vaults.py`: `test_software_and_research_vaults_are_not_generated_roots` | 一部 | 親フォルダーに `.obsidian` がある場合に停止すること（OBS-10） |
| `.obsidian` を変更しない | `test_obsidian_layout.py`: `test_existing_vault_settings_are_never_rewritten`、`test_new_vault_is_configured_once_and_user_changes_stay`、ワークスペース編集の保持 | あり | Obsidian起動中にアプリのブックマークグループを更新したときの競合（OBS-04） |
| ファイル名：禁止文字・末尾・同名・長さ | なし | なし | `register`、`graph_node_path` の規則とパス長の上限（OBS-14） |
| CSRF：ブラウザー由来のPOST | `test_interview_comparison.py`: `test_browser_requests_require_csrf_and_save_the_displayed_input_version`、`test_browser_e2e.py`: `test_comparison_and_unsaved_navigation_regressions` | あり | Origin／Sec-Fetchヘッダーと実ブラウザーで比較・保存を検証。`apiFetch`内部の`window.fetch`は許可する |
| 監視：停止の表示・ログ | `test_obsidian_finishing.py`: `test_application_watcher_executes_saved_checkbox_and_stops`、`test_backend_safety.py`: `test_config_reports_a_stopped_obsidian_watcher`、`test_application_lifecycle.py`: `test_not_started_is_reported_before_the_watcher_runs` | 一部 | スキップのログに本文が含まれないことの自動確認（OBS-15）。実ブラウザーでの表示確認 |
