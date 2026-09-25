# Gurumoji Gemini Agent Instructions

本ファイルは、Google Antigravity / Gemini エージェント向けに最適化された最上位の指示書です。

## 優先順位とスコープ

指示の適用順序:
1. システム要件・安全性要件
2. ユーザーの最新の個別指示
3. 本ファイル（`GEMINI.md`）および `.agents/rules/gurumoji-rules.md`
4. 該当するスキル（`.agents/skills/gurumoji-obsidian-memory` 等）
5. プロジェクト内ドキュメント

Obsidianノートは「設計上の根拠・記録」であり、現行コードや設定、ユーザー指示を上書きするものではありません。乖離がある場合はコードと設定を最終的な正本とし、ユーザー指示に従ってください。

## 必須行動ルール（ユーザー指定）

1. **日本語での報告**: すべての思考報告、進捗、対話は日本語で行う。
2. **自律実行と承認フロー**: **「タスクと設計図のみ許可を求め、それ以外の作業はすべて自動実行」** する。承認を得た計画に沿って自律的に完了まで作業を進めること。
3. **データベースの保全**: **SQLのカラムを変更（削除・リネーム・型変更）しない。** 新しいカラムの追加（`ADD COLUMN`）のみ許可される。
4. **設定・パスの管理**: パス、グローバル設定、外部サービスキーはすべて `.env` で一元管理し、コードやドキュメントに個人環境の絶対パスをハードコードしない。

## ドキュメント探索とObsidian Vault規約

- **最短アクセス**: ドキュメント全体やリポジトリ全体を初手で走査せず、必ず [docs/program-vault/00-AI-Entry.md](docs/program-vault/00-AI-Entry.md) を起点に対象モジュールや設計ノートを絞り込む。
- **スキルの適用**: Vaultのレイアウト、ノート所有権、分析保存データ、同期、移行に関するタスクを行う場合は、スキル `gurumoji-obsidian-memory` を使用し、必要最小限のコンテキストを取得する。
- **5つのVault（4+1 Vault）の役割分離**:
  - `Software Vault` (`docs/program-vault`): 設計仕様・手法定義（Git管理・アプリ書き込み不可）
  - `Research Vault` (`<data>/obsidian/ResearchVault`): 研究者向け本文・AI仕上げ作業台
  - `Input Vault` (`<data>/obsidian/InputVault`): 文字起こし台帳・入力スナップショット
  - `Visualization Vault` (`<data>/obsidian/VisualizationVault`): 図表仕様・CSV来歴
  - `Orchestrator Vault` (`<data>/obsidian/OrchestratorVault`): 手法カード・実行記録（Runs）
- **人間所有ノートの保護**:
  - 研究者が執筆した考察、タグ、別名を破壊・上書きしない。
  - 生成ノートは必ず `VaultRegistry` によるハッシュ検証・競合検知を通す。
  - テストは実際の運用Vaultではなく、一時Vault（テンポラリ）を使用して実行する。

## 「Obsidianを更新」と依頼されたとき

プログラム資料Vault（`docs/program-vault`）の更新をGitから取り込む依頼として扱う（実行時Vaultは対象外）。`python scripts/update_program_vault.py check` で取り込まれるノートを示し、続けて `python scripts/update_program_vault.py apply` を実行する。別フォルダーのVaultには `--target <フォルダー>` または環境変数 `GURUMOJI_PROGRAM_VAULT_TARGET` を使う。終了コード1（ローカル編集やローカルだけのコミットとの競合）は、表示された対象を報告して利用者の判断を待ち、merge・rebase・reset・上書きで解消しない。手順は [docs/OBSIDIAN_VAULTS.md](docs/OBSIDIAN_VAULTS.md#プログラム資料vaultの更新)。
