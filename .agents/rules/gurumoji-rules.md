# Gurumoji 開発ルール（Gemini / Antigravity）

本プロジェクトにおけるAIエージェントの行動指針および制約事項です。

## 1. ユーザー基本規約
- **日本語での報告**: すべての作業報告および対話は日本語で行う。
- **承認フロー**: タスクと設計図のみユーザーの許可を求め、許可取得後の作業はすべて自動実行する。
- **データベース変更の制約**: SQLのカラムを変更（削除や型変更含む）しない。新しいカラムの「追加（ADD COLUMN）」のみ許可される。
- **設定とパスの管理**: パスやグローバル設定、秘密情報（APIキー等）はすべて `.env` で管理し、コードやノート内にハードコードしない。

## 2. 優先順位と探索スコープ
- 指示の優先順位:
  1. システム・安全要件
  2. ユーザーの最新指示
  3. 本ルールおよび `GEMINI.md` / `AGENTS.md`
  4. 適用されるスキル（`gurumoji-obsidian-memory` 等）
  5. プロジェクト内ドキュメント
- Obsidianノートは「設計上の根拠（Design Evidence）」であり、現行コード・設定・ユーザー指示を上書きするものではない。
- 探索は対象を絞って行うこと。Vault全体やリポジトリ全体を初手で全探索せず、`docs/program-vault/00-AI-Entry.md` を起点に対象モジュールや設計ノートを特定して読む。

## 3. Obsidian連携およびデータの保護規約
- **5つのVault（4+1 Vault）の役割分離**:
  - `Software`（`docs/program-vault`）: 仕様・契約（Git管理、アプリ書き込み不可）
  - `Research`（`<data>/obsidian/ResearchVault`）: 研究者が読む本文・AI仕上げ作業台
  - `Input`（`<data>/obsidian/InputVault`）: Whisperパラメータ台帳・入力スナップショット
  - `Visualization`（`<data>/obsidian/VisualizationVault`）: 推奨図表・グラフ仕様・CSV来歴
  - `Orchestrator`（`<data>/obsidian/OrchestratorVault`）: 手法カード・実行記録（Runs）
- **ユーザー所有コンテンツの保護**:
  - 研究者が手動で記述・編集したノート内容、タグ、別名を上書き・破壊してはならない。
  - 生成ノートは必ず `VaultRegistry` や既存の競合処理（`conflict` / `missing` 検知）を通す。
- **テスト環境の安全性**:
  - 実際の運用Vault（本番Vault）に対してテスト書き込みを行わない。テスト時は一時ディレクトリ（`tmp` 等）を使用する。
