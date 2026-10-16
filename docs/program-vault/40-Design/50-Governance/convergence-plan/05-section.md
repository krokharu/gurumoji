---
note_type: reference-section
status: in-progress
updated: 2026-09-15
tags:
- gurumoji/program
- gurumoji/design
note_id: design-convergence-plan-section-05
title: アプリ収束計画（整理・統合・安全化）：A. 現在のアプリの目的
summary: A. 現在のアプリの目的。出典ノート「アプリ収束計画（整理・統合・安全化）」の分割本文。
parent_note_id: design-convergence-plan
source_path: 40-Design/convergence-plan.md
source_sha256: b60640ba092a802e2735beeefa7dc160b6c69c609f7930b46554a0d1751d92d6
source_body_lines:
- 184
- 251
split_on: '2026-10-11'
---

# アプリ収束計画（整理・統合・安全化）：A. 現在のアプリの目的

親索引・状態・確認版：[[40-Design/50-Governance/convergence-plan/00-Index]]。必要な本文だけを取得する。

## A. 現在のアプリの目的

ローカルPCで会議やグループインタビューを文字起こし・話者分離する。研究者が確認した逐語録を正本として保存し、根拠となる発話にたどれる分析結果を固定保存して、Obsidianで読み・考察する研究ワークベンチである（詳細は [[10-Architecture/10-System/system-map/00-Index|system-map]]）。

## B. 主要機能

Coreは次の5つ。それ以外は [[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]] で Supporting／Optional に分類した。

1. 文字起こしと話者分離
2. 逐語録の確認・編集保存
3. 処理済みデータの一覧
4. 分析・可視化
5. 分析結果の固定保存

## C. 重複している機能

[[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]] の「Duplicate」表を参照。主なものは次のとおり。

- AI仕上げの2経路
- 話者特定の3経路
- 議事録のMarkdown生成とVault出力の二重化
- Vaultへの書き込み主体5つと台帳4つ
- frontmatterの実装複数
- 原子的書き込み関数の重複

## D. 不要・Legacy候補

| 対象 | 分類 |
| --- | --- |
| `chunk_segments` | Deprecated候補 |
| `runtime/gurumoji.sqlite3` と `runtime/` 直下の検証出力 | Unknown |
| `obsidian_migration`、旧形式の作業ノート解析、`src/*.py` の互換import | 互換のため残す |

## E. アーキテクチャ上の問題

ARCH-01〜07、CFG-01〜04、DOC-01〜03（[[40-Design/50-Governance/known-issues/00-Index|known-issues]]）。

## F. Obsidian連携の現在構造

[[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]

## G. Obsidian連携で危険な部分

OBS-01〜17。重要度の高いものは次のとおり。

- **OBS-01：** テーマ同期が、所有を確認せずに上書きする
- **OBS-04：** 書き込み主体・台帳・競合時の挙動がばらばら
- **OBS-02／05：** 研究者のノートで、読み込みから書き込みまでの間の競合を検出しない
- **OBS-03：** `.obsidian` を変更する
- **OBS-10：** Vaultの入れ子を検出しない

## H. 統合すべき処理

新しいファイルを作る前に、既存モジュールへ統合できない理由を確認して書く。

| 統合対象 | 現在 | 統合先（既存を優先） | 新しいファイルの要否 |
| --- | --- | --- | --- |
| Vaultへの書き込み判定（所有hash・conflict・missing・ログ） | 5つの書き込み主体（[[20-Modules/30-Storage/obsidian-integration/00-Index\|obsidian-integration]]） | `VaultRegistry._write` の方式を、共通の書き込み関数へ | 共通層を作る場合だけ必要（ARCH-02）。理由：`analysis_store` は上位のモジュールで、Obsidian層から参照すると循環するため |
| frontmatterの入出力 | 生成4、解析2 | `obsidian_layout.unpack`／`pack` を拡張し、キー単位の更新を追加 | 不要 |
| パス・ファイル名の生成 | `ObsidianLayout.register`、`graph_node_path`、`safe_output_stem`、`safe_media_filename` | Vault用は `obsidian_layout`、出力用は `app.py` の既存関数に集約し、禁止文字・末尾・長さ・同名の規則を共通化 | 不要 |
| Vaultのルート算出 | 3か所と2か所 | `VaultRegistry`（`vaults.json` に ResearchVault も登録） | 不要 |
| 原子的書き込み | 5関数 | 1実装（フォルダーの同期を含む） | ARCH-02の共通層に置く |
| アプリURL | 3か所 | `archive_app_url` | 不要 |
| APIクライアント | `apiFetch` と `fetch` | `apiFetch` | 不要 |
| AI仕上げの経路 | ジョブ内とObsidian | 実装は `ai_finishing`。UIの経路はObsidianだけ | 不要 |
| 議事録の出力 | 2つのレンダラーと2系統のVault出力 | 中間データ `normalize_meeting_minutes` を1つにし、出力の役割を分けて明記 | 不要 |
| 設定の正本 | 分散 | [[40-Design/50-Governance/known-issues/00-Index\|known-issues]] の設定表 | 秘密でないアプリ設定ファイルを1つ（CFG-02） |
