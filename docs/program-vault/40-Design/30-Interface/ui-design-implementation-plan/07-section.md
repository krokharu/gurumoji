---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-07
title: Gurumoji UI改善の実装計画：W07 タスク別入口を段階導入する
summary: W07 タスク別入口を段階導入する。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 153
- 163
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：W07 タスク別入口を段階導入する

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

### W07 タスク別入口を段階導入する

- 対象: `templates/views/analysis.html:111–139`、`app.js`のnavigation、`analysis-visualizations.js:1014–1031`、ADR-118
- UI-0: 現行と候補の同一fixtureの画面map。UI-1: 結果を見る入口。UI-2: 比較入口。UI-3: 計画・試行・採用。UI-4: データ・出力。これは導入単位の提案で、既存再編計画の詳細番号との整合を着手前に確認する
- 比較案: [初期仕様8図の契約説明](../../ui-design-assets/2026-10-02/prototypes/comparison.md)を保持し、密度・日本語表示は[clean v2](../../ui-design-assets/2026-10-02/prototypes/v2/index.html)を使う。v2は同一fixtureの1280px／390px比較8図＋定義変更後の補助2図で、18件の独立比較ではない。Aは既存モード＋段階レビュー／根拠details、Bは4タスク＋対照面／根拠pane。初期候補はA、Bの各要素は独立比較。既存実装との距離と静止レビューに基づく暫定案で、学習・速度・好みの優位は未確認
- 引継ぐレビュー: [画面外凡例](../../ui-design-assets/2026-10-02/prototypes/v2/outside-legend.md)にAPI・保存・移行条件、[独立批評](../../../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)に初回と修正後のhashを置く。MC-02〜06の情報不足は静止図で補われ、MC-01は試行版と失効状態を補強。MC-01の動作とMC-07のdisabled／現在地は受入待ち。初回8図と修正後10図の再レビューを重複した実験数にしない
- 比較の分離: Mはnavを固定して段階レビュー対対照面、Eはnavと結果を固定してdetails対pane、NはM/Eを固定して3モード対4タスクを調べる。A/B全体の差を1つの要素の因果効果にしない。静止図は情報の所在だけをレビューし、click数・focus・完遂率を測定済みとしない
- 合格: S01〜S05の同等課題で正しい初手、完遂、戻り回数、対象版の説明、誤実行を比較。重大な保存／研究誤認が増えれば採用しない。速度差だけで決めない
- 出典: DG-05、ADR-118、UX:S08/UX:S11/UX:S13、PR:T2/PR:T3/PR:T8
- 移行／rollback: top navと旧hash/queryを維持。既存rendererを使う小さなadapterと切替点を設け、新旧結果の二重描画を避ける。入力draft／filter／履歴を保ったまま旧配置へ戻せるようにする
