---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-04
title: Obsidian連携の現状構造と安全性：Frontmatter（Properties）
summary: Frontmatter（Properties）。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 98
- 126
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：Frontmatter（Properties）

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

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
- 生成ノートは全体を再生成する。所有hashと異なる内容（研究者の編集）は履歴に写してから最新版で上書きする（利用者の決定、2026-09-25）。hash確認から書き込みまでの短い間の競合は残る。

## Wikilink

- 生成するリンクは次の3形式。Vault内の完全パスで、拡張子なし。
  - `[[<path>|<alias>]]`
  - `[[<path>#^s-<hex>|<label>]]`
  - `[[<path>]]`
- ブロックIDは `^s-` の後に、発話IDのUTF-8バイト列をhex化した値を付ける（Obsidianのブロック ID の文字制約への対応）。
- Vaultをまたぐリンクは作らず、IDで対応付ける（[[30-Data/40-Vaults/four-vaults-v1|four-vaults-v1]]）。
- アプリにはノートを改名する処理がない。移動・改名されたノートは、仕上げの場合 `note_id` で探す。分析ノートは `missing`／競合として扱い、再作成しない。リンクの追従はObsidianの「内部リンクを自動更新」に依存する。
- 移行処理 `rewrite_links` は `[[…]]` の中身だけを対応表で置き換え、`#heading`、`|alias`、`#^block` の部分は残す。引用行（`>`）とコードフェンスの中は書き換えない。正規表現は `![[…]]` の内側にも一致するため、埋め込みも移動先に置き換わる。
- テーマ同期は、`![[…]]` と、エスケープされた `\[[` を関連付けに使わない。
