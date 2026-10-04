# Gurumoji 共通ルールの入口

このクラウド版では共通の作業規約を [AGENTS.md](../../AGENTS.md) に集約する。重複した承認フロー、設定方法、Vault の書き込み規則を別々に定義しない。

- dot の Linux CPU 配置: [dot-cloud.md](dot-cloud.md)
- 利用者の Windows 環境を扱う場合の参照: [windows-local.md](windows-local.md)
- Gurumoji の Vault 保存・検索・同期設計を扱う場合のみ: [gurumoji-obsidian-memory](../skills/gurumoji-obsidian-memory/SKILL.md)

`GEMINI.md` は旧 Gemini／Antigravity 向け入口として保持する。dot の作業では `AGENTS.md` を入口とし、`.env` の読み込みや GPU の可用性は現行ランチャー・実環境で確認する。この整理は利用者の PC 上の元ファイルを変更しない。
