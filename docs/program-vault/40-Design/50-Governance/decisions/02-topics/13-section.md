---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-13
title: 設計判断の記録（ADR）：ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する
summary: ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 425
- 442
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する

- **状態：** accepted、実装済み（2026-09-16、2026-09-25に最新版`2f13f98`へ収録）
- **背景：** 新規作成の詳細設定（単語登録、AIエフォートなど）が常に開いており、手順表示がデスクトップ4段階・左ナビ6項目・スマホ4ステップの3種類あった（UX-05）。結果画面は1ページに議事録から発話編集までが縦に並び（UX-02）、移動ボタンが2か所にあり（UX-03）、表示中の画面がURLに残らなかった（UX-01）。処理中の進捗カードは画面をまたいで表示され（UX-16）、CPU/GPU表示は3か所にあった（UX-09）。部分修正を重ねても導線の問題が残るため、利用者から画面構造の全面的な見直しを許可された。
- **決定：**
  - 上部バーの4タブ（新規作成・処理済みデータ・分析・可視化・話者管理）と、1件の作業画面を画面の単位にする。各画面にハッシュのURL（`#/new`、`#/data`、`#/data/<id>`、`#/analysis/<id>`、`#/speakers`）を持たせ、`popstate` で戻る操作に対応する。旧 `?view=`／`?item=` は初回表示で置き換える。
  - 新規作成は「ファイル → 設定 → 開始」の3ステップにし、デスクトップとスマホで同じ手順表示を使う。設定は要約と「変更」ボタンで示し、詳細パネルは閉じた状態で置く。
  - 作業画面は「発話の確認・編集」「会話・話者」「議事録・アウトライン」「ファイル・管理」のタブに分け、保存バーは保存とObsidianでの仕上げの2つだけにする。
  - トークン・モデル・マシン診断は「接続と処理装置」ダイアログにまとめ、処理中の状況は上部バーのチップで示す。
  - 実行中ジョブのIDを表示中データのIDと分け、別画面で作業中に完了しても作業中のデータを置き換えない。
- **理由：** API・保存形式・フォーム項目名・既存の要素IDを保つことで、バックエンドと4つの補助スクリプト（分析内容、保存履歴、比較、AIエフォート）を変更せずに再利用できる。新しい依存やフレームワークを加えない。
- **代替案：** 既存画面のCSS調整と並べ替えだけで済ませる（常時表示の設定と重複導線が残る）。SPAフレームワークへ移行する（依存追加と全面的な書き換えが必要）。デスクトップとスマホに別フォームを持つ（手順表示の不一致が再発する）。
- **結果・影響：**
  - 画面から外した部品のID（`processed-data-hub`、`show-library-list-button`、`show-library-analysis-button`、`result-context-name`）を参照する外部スクリプトは動かない。リポジトリ内に参照は残していない。
  - 画面構成と旧機能の移動先は [[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]。解消した問題は [[40-Design/30-Interface/ui-ux-issues/00-Index|ui-ux-issues]] の状態欄。
  - テスト：`tests/test_ui_defaults.py`（`test_redesigned_navigation_routes_and_item_workspace` ほか）、`tests/test_browser_e2e.py`。
- **関連：** [[40-Design/30-Interface/ui-ux-issues/00-Index|ui-ux-issues]]、[[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]
