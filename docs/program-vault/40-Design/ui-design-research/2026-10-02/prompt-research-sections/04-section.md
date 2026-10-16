---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research-section-04
title: GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：5 Gurumojiに適した設計情報の分け方
summary: 5 Gurumojiに適した設計情報の分け方。出典ノート「GurumojiのUI設計をAIに依頼するための調査と実践テンプレート」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research
source_path: 40-Design/ui-design-research/2026-10-02/prompt-research.md
source_sha256: 7f17ce12573593c6bdc2e07d39f5f4251c5749bb84459f9eb17cde77cae80c66
source_body_lines:
- 103
- 137
split_on: '2026-10-11'
---

# GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：5 Gurumojiに適した設計情報の分け方

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-research]]。必要な本文だけを取得する。

## 5 Gurumojiに適した設計情報の分け方

以下のファイル構成は**提案**。この調査ではアプリに作成していない。既存の資料に同じ責務があるなら新設せずリンクする。

|資料|役割|入れないもの|
|---|---|---|
|短い作業brief|誰の何の作業を改善するか、変更範囲、完了条件|全仕様の複製|
|DESIGN.md|文字階層、色の役割、密度、余白、レイアウト、部品の使い方|実API契約の代用品、未確認の「現行」記述|
|画面・状態仕様|対象画面、操作、状態、遷移、復帰、エラー|色だけで意味を決めるルール|
|既存トークン定義|実際に描画へ使う値|文書だけにある第2の正本|
|コンポーネント事例|通常・focus・disabled・loading等の実例|網羅性を装った静止画だけの一覧|
|受入ケース|手順、期待値、確認方法、環境|「いい感じ」だけの判定|
|参照manifest|画像の版、画面幅、状態、参考にする属性|出所不明の「最新スクリーンショット」|

### 5.1 DESIGN.mdを過大評価しない

Googleの公式形式では、色・文字・余白等の値はfrontmatter、理由と使い方は本文に置く。本文の標準的な節はOverview、Colors、Typography、Layout、Elevation & Depth、Shapes、Components、Do's and Don'ts。必要でない節は省略できる。[G4](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md)

公式リポジトリには形式、参照、色コントラスト等のlintとdiffがある。ただし、その成功はアプリ全体のアクセシビリティ、実際のCSS適用、正しい日本語折り返し、操作の正しさを証明しない。本調査ではCLIを導入・実行していない。[G5](https://github.com/google-labs-code/design.md)

DTCG 2025.10はトークン交換の安定版Community Group Reportだが、W3C Recommendationではない。GoogleのDESIGN.md alpha、DTCGトークンJSON、既存CSS変数の3つを同一形式として扱わない。[D1](https://www.designtokens.org/tr/2025.10/format/)

### 5.2 Gurumojiで明記する設計の理由

- 緑は何を表すのか。ブランド、選択、保存成功、話者属性を無条件で同じ色にしない
- 紙色は長文を読む作業面なのか。背景を増やすだけで階層を作らない
- 原文、AIの提案、研究者の確定した編集は何で区別するか。色だけに頼らない
- 「保存済み」「分析が古い」「分析中」「一部だけ更新」「過去の結果」をどう区別するか
- 主操作は何か。画面の全操作を同じ強さのボタンにしない
- 根拠の引用はどの発話ID・版へ戻るか。スクロール位置や選択状態をどう復元するか
- 長い発話を読む幅と、比較・一覧の密度をどう両立するか
- モバイルでは情報をただ縦積みするのか、作業順に再編成するのか。隠す情報と再表示手段を明記する

上記は製品に合わせた設計課題であり、まだ全てが実装上の不具合だという意味ではない。
