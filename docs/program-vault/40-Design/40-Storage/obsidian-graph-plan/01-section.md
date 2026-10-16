---
note_type: reference-section
status: implemented-core
updated: 2026-09-13
tags:
- gurumoji/design
- gurumoji/obsidian
note_id: design-obsidian-graph-plan-section-01
title: Obsidianの全体・インタビュー別表示の再設計：Obsidianの全体・インタビュー別表示の再設計
summary: Obsidianの全体・インタビュー別表示の再設計。出典ノート「Obsidianの全体・インタビュー別表示の再設計」の分割本文。
parent_note_id: design-obsidian-graph-plan
source_path: 40-Design/obsidian-graph-plan.md
source_sha256: d7f8d5d46b4275fac23f14d8d9d1fb557a8b435726b481718766a13349aae72a
source_body_lines:
- 1
- 27
split_on: '2026-10-11'
---

# Obsidianの全体・インタビュー別表示の再設計：Obsidianの全体・インタビュー別表示の再設計

親索引・状態・確認版：[[40-Design/40-Storage/obsidian-graph-plan/00-Index]]。必要な本文だけを取得する。


# Obsidianの全体・インタビュー別表示の再設計

研究用Vaultを1つに保ち、「研究全体」「インタビュー1件」「関連する研究」の表示を切り替える。標準機能による構成を実装し、2026-09-13に63ノートをバックアップ付きで移行した。保存済み3件の入口とグラフをObsidian 1.13.7で確認済み。以下は設計時の方針であり、実際の操作と保存仕様は [グラフの使い方](../../../../OBSIDIAN_GRAPH.md) を参照。コミュニティプラグインは未導入。

## 現状と改善点

調査対象は `runtime/data/obsidian/ResearchVault`。2026-09-13時点でMarkdownは63件、用途別のトップレベルフォルダーは14個。手法定義19件、テンプレート8件、索引フォルダー5件なども同じVaultにある。確認できた `.obsidian` の設定ファイルは `app.json` のみで、グラフ・ブックマーク・ワークスペースの設定ファイルはまだない。実際のObsidian画面は未確認。

仕上げ・会話の入口・引用原文・分析結果が別フォルダーに分散し、生成版のIDがファイル名や階層に現れる。今後、過去版や手法別結果が増えるほど、読む対象を選びにくくなる構成と考えられる。

グラフの点はノート、線は内部リンクである。フォルダーをまとめてもリンク関係は自動では整理されない。保存階層の整理と、表示対象・リンクの設計を一緒に行う。[公式：Graph view](https://help.obsidian.md/plugins/graph)

## 1. 日常の入口を3つにする

| 表示 | 主に表示するもの | 開き方 |
| --- | --- | --- |
| 研究全体 | インタビューの概要、確定したテーマ、必要な研究プロジェクト | 絞り込み済みの全体グラフをブックマーク |
| インタビュー別 | 選んだ1件の概要、全文、アウトライン、分析まとめ、メモ、関連テーマ | そのインタビュー用の絞り込みグラフをブックマーク |
| 関連を探索 | 今開いているノートの周辺。別のインタビューとの関係も含む | ローカルグラフ、深度1を基本・必要時に2 |

ここでいう「全体」は研究用Vault全体。プログラム資料用の `docs/program-vault` は引き続き別Vaultとし、研究用グラフに混在させない。

インタビューごとにVaultを複製すると、共通テーマを通した横断閲覧と設定管理が分散するため、今回の目的では同じVault内で表示を分ける。

全体グラフはブックマークできるが、ローカルグラフは直接ブックマークできない。インタビュー別の固定表示には、フィルターを設定した全体グラフを使う。ローカルグラフは深度を上げると共通テーマ経由で別インタビューまで広がるため、1件限定の表示と区別する。[公式：Bookmarks](https://help.obsidian.md/plugins/bookmarks)
