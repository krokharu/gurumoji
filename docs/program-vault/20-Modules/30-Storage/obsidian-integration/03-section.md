---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-03
title: Obsidian連携の現状構造と安全性：データフロー
summary: データフロー。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 62
- 97
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：データフロー

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## データフロー

### アプリ → Obsidian

```text
操作（保存・分析保存・ジョブ完了・仕上げ）
  → 正本を先に確定（SQLite / analysis_store / output）
  → ノート本文を文字列連結で生成（markdown() でエスケープ、発話は引用ブロック＋^s-<hex>）
  → プロパティを付与（生成関数は4種類。後述）
  → 保存先を決定（interviews.json のコードとフォルダー、または ID によるASCIIパス）
  → safe_path で検証 → 所有hashを照合 → write_atomic
  → 台帳にhashを記録（obsidian_notes / interviews.json / vaults.json / state.json）
  → ナビゲーション・索引・.obsidian を更新
```

### Obsidian → アプリ

| 読み込み | 実装 | アプリへの反映 |
| --- | --- | --- |
| 操作ノートのチェックと `provider` | `ObsidianWorkbench.selection`（64KB上限） | AI実行のきっかけ（状態をラッチ） |
| 全文・結果ノートの発話本文 | `parse_transcript`（ブロックIDの順序と一致を必須とする） | 「結果をアプリへ反映」のときだけDBへ保存 |
| アウトラインノート | `parse_outline`（`##` 見出しと箇条書き） | AI仕上げの参照。反映時に出力用アウトラインとして保存 |
| ノートの移動先 | `locate_note`（Vault全体の `.md` の先頭65KBから `note_id` を探す） | `state.json` のパスを更新 |
| 研究メモのテーマリンク | `sync_themes`（コードブロックを除いた `[[20-テーマ/…]]`） | 別の生成ノートに関連一覧を書く（DBには入れない） |
| 旧階層の全ノートのプロパティ | `migrate` | パスの対応表とDB参照を更新 |

研究メモ・解釈・コード案のDBへの取り込みは未実装（[[40-Design/40-Storage/sync-contract|sync-contract]]）。

## Markdownの生成方法

- テンプレートエンジンは使わず、Pythonの文字列連結で組み立てる。
- 本文は `analysis_store.markdown()` でエスケープする（`html.escape` のあと、Markdown記号をバックスラッシュでエスケープ）。
- 原文は引用ブロックにする。表のセルには160文字までしか入れない。
- 長い原文は200発話ごとにページを分ける（`AnalysisStore.source_notes`）。
- callout（`> [!info]` など）を使う。プラグインは使わない。
