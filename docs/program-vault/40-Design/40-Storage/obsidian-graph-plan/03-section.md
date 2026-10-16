---
note_type: reference-section
status: implemented-core
updated: 2026-09-13
tags:
- gurumoji/design
- gurumoji/obsidian
note_id: design-obsidian-graph-plan-section-03
title: Obsidianの全体・インタビュー別表示の再設計：4. 画面構成
summary: 4. 画面構成。出典ノート「Obsidianの全体・インタビュー別表示の再設計」の分割本文。
parent_note_id: design-obsidian-graph-plan
source_path: 40-Design/obsidian-graph-plan.md
source_sha256: d7f8d5d46b4275fac23f14d8d9d1fb557a8b435726b481718766a13349aae72a
source_body_lines:
- 110
- 146
split_on: '2026-10-11'
---

# Obsidianの全体・インタビュー別表示の再設計：4. 画面構成

親索引・状態・確認版：[[40-Design/40-Storage/obsidian-graph-plan/00-Index]]。必要な本文だけを取得する。

## 4. 画面構成

- 「研究全体」：左にインタビュー一覧、中央に全体グラフ、右に選んだ概要・テーマ。
- 「インタビュー作業」：左に概要、中央に全文とアウトライン、右にローカルグラフまたは対象限定グラフ。
- ブックマークを「研究全体」「インタビュー別」「履歴・運用」にまとめる。普段はファイル一覧よりブックマークと概要ノートを入口にする。

この2つの画面配置はWorkspacesで保存する。対象インタビューは概要・ブックマークから選ぶ。Workspacesがインタビューの所属フィルターを自動生成するとは扱わず、表示対象の生成はアプリ側の役割とする。[公式：Workspaces](https://help.obsidian.md/plugins/workspaces)

インタビュー一覧にはBasesで日付・タイトル・仕上げ状態・テーマを表示する。これは一覧・絞り込み用であり、グラフの代替ではない。使用中のObsidianの対応状況を確認し、利用できない場合は静的なリンク一覧で同じ入口を用意する。[公式：Bases](https://help.obsidian.md/bases)

## 5. 必要なプラグイン

初期実装に必須のコミュニティプラグインは0個。次の標準機能で全体・インタビュー別の表示を構成する。

| 機能 | 採用 | 用途 |
| --- | --- | --- |
| Graph view | 必須・標準 | 全体グラフ、対象限定グラフ、ローカルグラフ |
| Bookmarks | 必須・標準 | 絞り込み済みグラフと概要を呼び出す |
| Workspaces | 推奨・標準 | 全体を見る配置と作業する配置の切り替え |
| Bases | 推奨・標準 | インタビューの一覧・並べ替え・絞り込み |
| Backlinks / Properties view | 推奨・標準 | 参照元と所属情報の確認 |
| Canvas | 任意・標準 | 位置を固定した比較図、議題や引用カードの整理 |

位置を固定して図を読む用途はCanvasが適している。グラフの自動配置とは別の表示として使う。[公式：Canvas](https://help.obsidian.md/plugins/canvas)

さらに「上下・横の関係を整理したナビゲーション」が必要なら、次の組み合わせを第二段階で試す。

| コミュニティプラグイン | 用途・依存関係 |
| --- | --- |
| [ExcaliBrain](https://github.com/zsviczian/excalibrain) | 親・子・関連ノートを配置した関係図。今回の追加候補 |
| [Excalidraw](https://github.com/zsviczian/obsidian-excalidraw-plugin) | ExcaliBrainの描画に必須。手書き図にも利用可能 |
| [Dataview](https://github.com/blacksmithgu/obsidian-dataview) | ExcaliBrainに必須。条件に応じた集計にも利用可能 |

ExcaliBrainの開発元はExcalidrawとDataviewの両方の導入・有効化を必須としている。親子関係の自動推定を研究上の意味と混同しないよう、必要な場合は概要→分析、分析→根拠などの関係を明示的に設定する。標準グラフで読みやすくなるか確認してから追加する。

記事にあるText Generator、ChatGPT MDなどのAIプラグインは、今回のグラフ表示には不要。AI仕上げは既存のGurumoji連携で実行する。Templater・QuickAddも、概要やタグの生成をアプリ側で行う初期構成には必須ではない。
