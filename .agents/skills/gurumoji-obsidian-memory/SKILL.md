---
name: gurumoji-obsidian-memory
description: GurumojiのObsidianデータ構造（VaultRegistry、4+1 Vault、保存契約、同期・移行、AnalysisStore成果物）を参照・変更・検証するときに使う。Obsidian連携の設計書や契約、最小限のノート抽出が必要な場合に適用する。
---

# Gurumoji Obsidian Memory

Gurumoji の人が読む知識は Obsidian Markdown に、機械的な検索・整合性・大きな構造化データは SQLite、JSON、CSV に置く。詳細な開発上の安全策は `docs/program-vault/40-Design/ai-development-rules.md` を参照する。現在のコードと設定で、保存先・正本・IDを確認する。

パスの基準:
- `docs/` と `src/` はリポジトリルート基準
- `references/` と `scripts/` は本スキル配下（`.agents/skills/gurumoji-obsidian-memory/`）を指す

## 作業の入口

1. まず `docs/program-vault/00-AI-Entry.md` で変更対象を絞る。選ばれたコード、設定、入口ノートだけを読む。対象 Vault 直下の `00-Home.md` / `00-Index.md` は入口で足りない場合だけ読み、関連を絞れない場合だけ下の候補抽出を使う。
2. Vault の配置、正本、ID、同期境界を変えるときは [Vault contract](references/vault-contract.md) を読む。検索・要約・AI入力・ノート書き込みを変えるときは [Retrieval and write protocol](references/retrieval-and-write.md) を読む。
3. 正本・保存先・IDを変える変更には、互換性、移行／ロールバック、対象の回帰テストを含める。通常の保存内容の変更に、この一式を機械的に要求しない。

## 候補抽出（スクリプト実行）

入口ノートで対象を絞れないときだけ、リポジトリルートから次を実行する。`--vault` は必須で、Vault のルートを1つだけ指す（Software Vault は `docs/program-vault`）。

```bash
python .agents/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py \
  --vault docs/program-vault --query "調べたいこと" --max-notes 4 --max-chars 8000
```

出力は選定ノートの provenance と抜粋だけで、Vault は書き換えない。返された候補の frontmatter と必要な抜粋だけを読む。`90-Templates` と `99-Archive` は既定で除外し、必要なときだけ `--include-templates` / `--include-archived` を付ける。実行時 Vault（`<data>/obsidian/...`）は依頼に必要な場合だけ対象にする。

## 常に守る境界

- Vault 間の関連は stable ID とカタログ／manifest で解決し、表示名や Vault をまたぐ Wikilink に依存しない。
- 人が所有する本文、タグ、別名は置換しない。Input／Visualization／Orchestrator の生成ノートは `VaultRegistry` の競合処理を通す。ResearchVault は `AnalysisStore`、`ObsidianLayout`、`ObsidianFinishing` の既存経路と、それぞれの競合処理を使う。
- 同期は AI 再実行、重い再分析、外部送信を暗黙に起動しない。古い派生物は stale として示す。
- AI入力と検索インデックスに資格情報、個人情報、不要な原文・CSV・JSONを入れない。実 Vault ではなく一時Vaultで検証する。
