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
note_id: design-known-issues-section-02
title: 既知の問題点と改善方法（収束フェーズ）：BUG：動作不良
summary: BUG：動作不良。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 34
- 51
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：BUG：動作不良

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## BUG：動作不良

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-01 | 高 | グループインタビュー比較の2つのPOSTが、CSRFヘッダー `X-Gurumoji-Request` を付けずに `fetch` で送信している | `static/interview-comparison.js`: `runComparison`、`saveComparison` が `fetch(...)` を直接使う。`app.py`: `enforce_request_security` は、ブラウザー由来（Origin／Referer／Sec-Fetch-Site あり）でヘッダーのないPOSTに403を返す。テスト `tests/test_interview_comparison.py`・`test_vault_coverage.py` はブラウザー由来のヘッダーを付けない `test_client` で送るため通過する | ブラウザーから比較の実行・保存ができない可能性が高い（実ブラウザーでは未確認） | `app.js` の `apiFetch` を使う（新しいラッパーは作らない）。ブラウザーE2Eテスト、またはOriginを付けたテストクライアントで回帰テストを追加する | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |

## ARCH：アーキテクチャ

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法 | 状態 | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ARCH-01 | 中 | `app.py`（約15,700行）に、API・パイプライン・編集トランザクション・分析集計・議事録・出力・AI呼び出し・Obsidian監視が集中している | [[10-Architecture/10-System/system-map/00-Index\|system-map]] | 変更の影響が読めない。AIや人が既存関数を見落とし、同じものを再実装しやすい | 全面的な書き換えはしない。責務ごとに既存モジュールへ関数を移すだけの変更を、1レビュー1責務で行う（例：議事録 → 新設ではなく既存の分析側へ。Obsidian呼び出し → `obsidian_finishing`・`vault_registry` 側へ）。ルートは最後まで `app.py` に残す | 未対応 | 保留：大規模移設は不具合修正後 |
| ARCH-02 | 中 | 保存・Vault系のモジュール間に循環依存があり、関数内importで回避している | `analysis_store` ⇄ `obsidian_layout`／`vault_registry`、`obsidian_finishing` ⇄ `obsidian_layout`、`obsidian_migration` → `obsidian_finishing` | 読み込み順に依存する不具合、テストしにくい | 下位の共通関数（`safe_path`、`write_atomic`、`markdown`、frontmatterの入出力）を、依存の最下層になる1か所にまとめ、一方向の依存にする。既存の上位モジュールには置けないため、新しいファイルが必要な数少ないケースになる（理由をADRに書く） | 未対応 | 保留：共通層が必要になった時点で局所抽出 |
| ARCH-03 | 中 | 同じ値を複数の場所で算出している | ResearchVaultのパス3か所（`ObsidianLayout`・`ObsidianWorkbench`・`AnalysisStore` の `__init__`）、Software Vaultのパス2か所（`vault_registry.SOFTWARE_ROOT`、`app.vault_registry`）、アプリURL・ポート3か所（`archive_ai_finishing` 内、`archive_app_url`、既定引数の `http://127.0.0.1:7860`） | 保存先の変更やポート変更の一部だけが反映され、リンク切れや別フォルダーへの書き込みが起きる | パスは `VaultRegistry`（または既存の台帳）から、URLは `archive_app_url` から取得するように統一する | 未対応 | 保留：保存先変更の実害を確認してから |
| ARCH-04 | 低中 | 原子的書き込みの関数が重複している | `analysis_store.write_atomic`、`app.py`: `atomic_write_text`、`atomic_write_bytes`、`durable_write_json`、`temporary_output_path`、`sync_directory_metadata` | `fsync` やフォルダー同期の扱いに差があり、片方だけ修正される | フォルダーの同期も含む1実装に統一し、他は薄い呼び出しにする | 対応済み（`5c2e0e9`：`durable_files.write_durably` に一本化し、`write_atomic`・`atomic_write_text/bytes`・`durable_write_json` は薄い呼び出し。フォルダー同期を含む） | 保留：原子性・耐久性の要件を先に比較 |
| ARCH-05 | 中 | フロントエンドのAPI呼び出しが各JSに散らばり、`apiFetch` と生の `fetch` が混在している | [[10-Architecture/10-System/system-map/00-Index\|system-map]]、BUG-01 | セキュリティヘッダーやエラー処理の漏れ | 全ての呼び出しを `apiFetch` に統一する。エンドポイント文字列の重複は、画面を整理するときに合わせて整理する | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | 統合 → BUG-01 |
| ARCH-06 | 低 | AI入力の分割関数が3種類ある | `app.chunk_segments`（テストからしか参照されない）、`analysis_insights.bounded_batches`、`ai_finishing.fragments` | 使われていないコードが残る | `chunk_segments` をDeprecated候補にする（[[20-Modules/10-Inventory/feature-inventory/00-Index\|feature-inventory]] の確認項目を満たしてから整理） | 対応済み（`00dae84`：確認項目を満たした `chunk_segments` を削除し、テストの意図を `test_ai_finishing` へ移した） | 保留：利用箇所とテストの意図を確認してから |
| ARCH-07 | 中 | 同じ目的の処理経路が二重になっている | AI仕上げ（ジョブ内／Obsidian）、話者特定3経路、議事録Markdown生成2種、議事録のVault出力2系統、保存API2系統、ダウンロードAPI2系統 | 片方の経路だけ修正される。UIの入口が増える | [[20-Modules/10-Inventory/feature-inventory/00-Index\|feature-inventory]] の「Duplicate」表の方針で1つにまとめる。APIの互換は残し、実装は共通化する | 一部対応（2026-09-25。AI仕上げは入口を2つ残し、「全体アウトライン → 全文校正 → Jev比較」と段階の記録を `services/ai/transcript_finishing.run_full_cleanup` に共通化した。失敗時はジョブ内が警告して続行、Obsidianが停止。話者特定・議事録・保存API・ダウンロードAPIは未対応） | 保留：用途の異なる経路を一律統合しない |
