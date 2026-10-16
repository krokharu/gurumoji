---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-knowledge-section-01
title: Gurumoji 設計知識の入口：Gurumoji 設計知識の入口
summary: Gurumoji 設計知識の入口。出典ノート「Gurumoji 設計知識の入口」の分割本文。
parent_note_id: design-ui-knowledge
source_path: 40-Design/ui-design-knowledge.md
source_sha256: 91d434fb547e4d56ecae2bd1c1b0f471f816a06c2e275bfe5735e8440a809428
source_body_lines:
- 1
- 37
split_on: '2026-10-11'
---

# Gurumoji 設計知識の入口：Gurumoji 設計知識の入口

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-knowledge/00-Index]]。必要な本文だけを取得する。


# Gurumoji 設計知識の入口

第4稿 0.4 · 2026-10-02 UTC · 確認HEAD `88f5e3e`（0.3文書統合）／ソース基準 `ddc23abe`・実装 `59ebd24`  
後続の調査・設計・実装で、必要な根拠だけを読むための索引。全資料の常時読込や、この文書だけによる実装判断を求めない。

source_headは調査時のソース基準版を指す。文書だけのcommitでrepoのHEADが進んでも、アプリの新実装やUI再検証を意味しない。実際のHEADと、[統合検証](../../../50-Tests/ui-design-evidence/2026-10-02/integration-validation.json)のsource／test hash保全を分けて記録する。ブラウザーへ配信された版との一致や実画面の受入は別途確認する。

## 最初に読むもの

1. [AGENTS.md](../../../../../AGENTS.md)と実際のHEAD・差分。コードが実装の正本
2. [DESIGN案](../ui-design-contract/00-Index.md)。意図、不変条件、提案を把握
3. 対象のW項目だけ[実装計画](../ui-design-implementation-plan/00-Index.md)で選び、DGの[証拠対応表](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md)からコードへ進む
4. 必要な[シナリオ](../../../50-Tests/30-Interface/ui-design-scenarios/00-Index.md)と[受入方法](../../../50-Tests/30-Interface/ui-design-acceptance.md)を読む

## 作業から選ぶ詳細資料

| 今の仕事 | 読む箇所 | 対応する根拠と注意 |
|---|---|---|
| 現行画面と能力を理解 | [監査](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md)§2、[独立反証](../../../50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md)H1/H2 | 上部4入口、M0〜M7永続実装済み。基礎pipelineと個別分析は別 |
| 分析の実行入口を直す | DG-01、W01、S01 | CSS非表示は確認済み。API／保存済み表示の削除ではない |
| 手動測定・試行・採用 | DG-02、W02、S02、[prompt](../../ui-design-research/2026-10-02/prompt-research.md)T11、[定義版probe](../../../50-Tests/ui-design-evidence/2026-10-02/definition-lifecycle-probe.json) | 説明は測定命令ではない。既採用上書き・実行時の版ずれも対処 |
| 保存・再分析・版 | DG-03/06/11、W03/04、S03/04、prompt T5 | 計算、保存、Vault、研究者確認は別軸 |
| 根拠から原音へ戻る | W04、S04、[UX](../../ui-design-research/2026-10-02/ux-research.md)K01/K05/K13、prompt T6 | 入力版・引用・filter・focusの往復契約 |
| 履歴と比較 | DG-04/05、W06/07、S05 | 上限はUX-34既知。古い保存物は消えていない |
| 日本語とaccessibility | W05/08、S06/07、UXの基準表、prompt §8 | 現行描画とATが必要。候補font-sizeはWCAG規定値ではない |
| 見た目の方向を比較 | prompt T2/T3/T8、W07/08、[clean v2](../../ui-design-assets/2026-10-02/prototypes/v2/index.html) | 同じ内容・状態・幅で比較。静かな緑紙色を出発点に。静止全長図を実viewportと見なさない |
| 小さな既存修正を実装 | prompt T7/T9、対象コードと隣接test | Flask/素のJSを維持。新スタック導入を既定にしない |
| 検証結果を引き継ぐ | prompt T10、受入方法、計画§4/5 | V1〜V5とpassed/failed/not-runを分離 |
| 短い日本語・送信／保存の説明 | [文言仕様](../ui-microcopy-state-catalog/00-Index.md)J01〜25、[独立契約確認](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md)、W01/03 | handlerの実効果と実payloadへ合わせる。25箇所は新規不具合数ではない |

[レビュー済みの3タスクbrief](../../ui-design-research/2026-10-02/prompt-workflow-task-briefs.md)はW01/W02/W04の短い再利用入口。[公式参照パターン](../../ui-design-research/2026-10-02/reference-patterns.md)は根拠往復、提案と適用、再生と選択、出力の省略項目を検討するときだけ読む。[出典台帳](../../ui-design-research/2026-10-02/prompt-source-ledger.md)はprompt調査の出典URL・確認範囲・根拠の強さを確かめるときだけ読む。公式マニュアル／静止画像／設計推論を実操作の証明と混ぜない。

画面案は、[仕様注釈付きv1](../../ui-design-assets/2026-10-02/prototypes/comparison.md)の8図と、clean v2の比較8図＋補助状態2図を区別する。開発条件は[画面外凡例](../../ui-design-assets/2026-10-02/prototypes/v2/outside-legend.md)、可視情報の修正と残留条件は[独立批評](../../../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)の末尾を読む。初回と再レビューの図数を足して評価件数にしない。MCは静止設計案の指摘IDでありDGの現行欠陥数とは別。Aは暫定候補、Bの各要素は利用者検証待ち。着手時の事実／技術gate／選好の区別は実装計画§6に集約する。

prompt T1は現行理解、T4はDESIGN抽出。11テンプレートすべてを一度に付けず、対象フローの1〜2個と必要なコード・受入だけを使う。
