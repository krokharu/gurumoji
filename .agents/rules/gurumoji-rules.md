# Gurumoji 共通ルールの入口

共通の作業規約は [AGENTS.md](../../AGENTS.md) に集約する。重複した承認フロー、設定方法、Vault の書き込み規則を別々に定義しない。実行環境の判定は AGENTS.md の表に従う。

- Orca の worktree（Windows）: [orca-worktree.md](orca-worktree.md) と [windows-local.md](windows-local.md)
- 利用者の Windows メイン checkout: [windows-local.md](windows-local.md)
- dot の Linux CPU 配置: [dot-cloud.md](dot-cloud.md)
- Gurumoji の Vault 保存・検索・同期設計を扱う場合のみ: [gurumoji-obsidian-memory](../skills/gurumoji-obsidian-memory/SKILL.md)

`GEMINI.md` は旧 Gemini／Antigravity 向け入口として保持する。`.env` の読み込みや GPU の可用性は現行ランチャー・実環境で確認する。
