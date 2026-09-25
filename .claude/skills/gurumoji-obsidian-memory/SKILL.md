---
name: gurumoji-obsidian-memory
description: Gurumoji の Obsidian データ構造を変更するときに使う。VaultRegistry、Vault 間の保存契約、同期・移行、または AnalysisStore の Vault公開・成果物契約を変更する依頼で適用する。通常の文書編集、Obsidianと無関係なDB変更、一般的なアプリ修正、利用者としてのノート操作には使わない。
---

# Gurumoji Obsidian Memory

Gurumoji の人が読む知識は Obsidian Markdown に、機械的な検索・整合性・大きな構造化データは SQLite、JSON、CSV に置く。詳細な開発上の安全策は `docs/program-vault/40-Design/ai-development-rules.md` を参照する。現在のコードと設定で、保存先・正本・IDを確認する。

パスの基準は2つある。`docs/` と `src/` はリポジトリルート基準、`references/` と `scripts/` はこのスキル配下（`.claude/skills/gurumoji-obsidian-memory/`）を指す。

## 作業の入口

1. まず `docs/program-vault/00-AI-Entry.md` で変更対象を絞る。選ばれたコード、設定、入口ノートだけを読む。対象 Vault 直下の `00-Home.md` / `00-Index.md` は入口で足りない場合だけ読み、関連を絞れない場合だけ下の候補抽出を使う。
2. Vault の配置、正本、ID、同期境界を変えるときは [Vault contract](references/vault-contract.md) を読む。検索・要約・AI入力・ノート書き込みを変えるときは [Retrieval and write protocol](references/retrieval-and-write.md) を読む。
3. 正本・保存先・IDを変える変更には、互換性、移行／ロールバック、対象の回帰テストを含める。通常の保存内容の変更に、この一式を機械的に要求しない。

## 候補抽出

入口ノートで対象を絞れないときだけ、リポジトリルートから次を実行する。`--vault` は必須で、Vault のルートを1つだけ指す（Software Vault は `docs/program-vault`）。

```bash
python .claude/skills/gurumoji-obsidian-memory/scripts/retrieve_memory.py \
  --vault docs/program-vault --query "調べたいこと" --max-notes 4 --max-chars 8000
```

出力は選定ノートの provenance と抜粋だけで、Vault は書き換えない。返された候補の frontmatter と必要な抜粋だけを読む。`90-Templates` と `99-Archive` は既定で除外し、必要なときだけ `--include-templates` / `--include-archived` を付ける。実行時 Vault（`<data>/obsidian/...`）は依頼に必要な場合だけ対象にする。

## 常に守る境界

- Vault 間の関連は stable ID とカタログ／manifest で解決し、表示名や Vault をまたぐ Wikilink に依存しない。
- 人が所有するノート（全文・操作・研究メモ・仕上げ結果・テーマ）の本文、タグ、別名は置換しない。アプリの生成ノートは、Input／Visualization／Orchestrator なら `VaultRegistry`、ResearchVault なら `AnalysisStore`、`ObsidianLayout`、`ObsidianFinishing` の既存経路を使う。どれも共通判定 `vault_note_policy` を通り、研究者が編集した生成ノートは履歴に写してから最新版で上書きする。
- 同期は AI 再実行、重い再分析、外部送信を暗黙に起動しない。古い派生物は stale として示す。
- AI入力と検索インデックスに資格情報、個人情報、不要な原文・CSV・JSONを入れない。実 Vault ではなく一時Vaultで検証する。

このスキルはGurumoji固有の記憶アーキテクチャ用である。単発の文章編集や、既存の研究ノートを利用者として操作するだけの依頼には適用しない。
