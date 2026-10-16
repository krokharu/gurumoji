---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-06
title: 設計判断の記録（ADR）：提案（収束フェーズ）
summary: 提案（収束フェーズ）。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 210
- 248
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：提案（収束フェーズ）

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

## 提案（収束フェーズ）

### ADR-101 Vaultへの書き込み判定を1つの関数に統合する

- **状態：** proposed
- **背景：** 書き込み主体が5つあり、競合時の挙動がそれぞれ異なる（OBS-04）。
- **決定（案）：**
  - `VaultRegistry._write` の方式を、全ての書き込みに適用する。
    - 予定hashを記録してから書く。
    - 外部で編集されていれば `conflict` にする。
    - 削除・移動されていれば `missing` にし、再作成しない。
    - 結果を索引とログに出す。
  - `managed_note`・`AnalysisStore.write_note`・`ObsidianWorkbench.save_note` は、この関数を呼ぶだけにする。
- **理由：** 「人の編集を上書きしない」ことを、ノートの種類によらず保証するため。
- **代替案：** 各書き込み主体を個別に修正する（重複が残る）。
- **結果・影響（予定）：**
  - ナビゲーションノートが削除されたとき、再作成しない方針に変わる（`missing` を表示し、ボタンで再作成）。
  - 台帳の統合は別のADRで決める。
- **関連コード：** 上記の関数群

### ADR-102 人が所有するノートは、変更するキーと管理区間だけを更新し、書く直前に再確認する

- **状態：** proposed
- **背景：** テーマ同期と仕上げノートの装飾が、ノート全体を再生成して上書きしている（OBS-01、02、07）。
- **決定（案）：**
  - 変えるのは、プロパティのうち必要なキーの行と、`<!-- gurumoji:… -->` で囲んだ区間だけにする。
  - 書き込む直前に、読み込んだときのhash（とmtime）が変わっていないか確認し、変わっていれば書かずに `SKIP_CONFLICT` を記録する。
  - YAMLを解析できない場合や、未対応の形式の場合は書かない。
- **理由：** Obsidianの `processFrontMatter` や `Vault.process` に相当する安全性を、外部アプリで確保するため。
- **代替案：** YAMLのround-trip対応ライブラリを追加する（依存が増えるため、別途判断する）。
- **結果・影響（予定）：** アプリのタグ名前空間を移行する必要がある（例：`graph/*` → `gurumoji/graph/*`。移行は別ADR）。

### ADR-103 既存のVaultの `.obsidian` は、初回作成時と明示操作のとき以外は書かない

- **状態：** accepted（2026-09-25。明示操作の画面は未実装）
- **背景：** `configure` が、利用者の表示設定を繰り返し変更している（OBS-03）。
- **決定：** `.obsidian/` がまだないVaultを初めて整えるときだけ、既定の設定（コアプラグイン、CSSスニペットの有効化、グラフ、ブックマーク、ワークスペース）を書く。判定結果は `interviews.json` の `obsidian_settings`（`initialized`／`existing`）に1回だけ記録し、以後の同期では書かない。例外はアプリ自身のブックマークグループで、利用者が残している間だけ、内容が変わったときに更新する。削除されたグループは戻さない。既存のVaultに推奨設定を適用する「推奨表示設定を適用」操作は、収束計画どおり必須にせず後続とする。
- **理由：** 利用者の設定と、Obsidianが起動中に持っている設定を尊重するため。
