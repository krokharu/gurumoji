---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique-section-01
title: Gurumoji 静止モックアップの独立批評：Gurumoji 静止モックアップの独立批評
summary: Gurumoji 静止モックアップの独立批評。出典ノート「Gurumoji 静止モックアップの独立批評」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique
source_path: 50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md
source_sha256: a5930f15d27ba0bde495c47e25e7920c6463caf23571b284ea0a61df3c58cbb7
source_body_lines:
- 1
- 33
split_on: '2026-10-11'
---

# Gurumoji 静止モックアップの独立批評：Gurumoji 静止モックアップの独立批評

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/mockup-critique]]。必要な本文だけを取得する。


# Gurumoji 静止モックアップの独立批評

2026-10-02 UTC / v2 初回レビュー＋修正後10図の再確認 / 提案・未採用・未実装  
対象ソースHEAD: `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`  
対象: `prototypes/v2/rendered/` の比較PNG 8図と修正後に加わった補助状態2図。初回8図・修正後10図を `view_image` で実画素確認した。本文の座標・寸法・MC指摘は初回レビュー版に対するもの。修正後の判定は冒頭の要約と末尾を参照する。

## 結論

**段階導入はAを第一候補とし、Bのdesktop根拠paneは独立した仮説として残す。** Aは今回の静止状態では測定→確認→採用の現在地と主張→引用の所属を追いやすい。B desktopは同時対照の余地がある。B mobile初回の主張欠落は修正された。修正版でも研究者メモは別状態にあるため、画面の短さだけで「照合しやすい案」とは評価できない。

両案の大きな前進は、**計算済み0と欠測、平均の分母、採用と実行、分析時12版と現在13版、AI下書きと研究者メモ**を文章で分けたこと。quietな緑・紙色と既存構造を保つ方針にも異論はない。色替えや装飾の追加より、次の3点が先である。

1. 編集できる定義と右側の試行結果が、いつの同じ組合せなのかを短く可視化する
2. mobileの根拠にも、検討対象の主張と未確認状態を残す
3. 対象集合・欠測時の次操作・測定の限界を、採用前に読める位置に置く

**修正後の要約:** MC-02〜06の可視情報不足は修正版で補われた。MC-01は試行bindingと変更後の失効図で設計を補強したが、実際の状態遷移・server保証は未実装／未検証。MC-07は低優先の実装評価事項として残す。詳細は末尾「修正版の再確認」。

これは専門家による静止表示レビューであり、利用者の好み、作業速度、完遂率、誤り発見率を測った結論ではない。

## 読んだ資料と証拠の境界

- `prototypes/comparison.md`、`prototypes/verification.md`、`prototypes/synthetic-fixture.json`
- `prototypes/v2/wireframe-manifest.json`、`prototypes/v2/build-user-views.py`
- `draft-DESIGN.md` 全文、`current-design-audit.md` の測定・根拠・視覚・受入節、`reference-patterns.md` のA01/A02/B02と評価境界
- 必要部分の実装: `analysis_pipeline.py` の `_measurement_value` / `measure_segments`、`analysis_core.py` の `validate_definition`

初回時点ではv2 manifestが指す `outside-legend.md` は未配置だった。旧 `verification.md` は注釈入り初版の検査記録なので、それだけでv2を検査済みとは扱っていない。旧版の画面内注釈による密度評価は今回へ持ち込んでいない。

**実施:** PNGの文字・配置・対応・可視情報の所在の確認、同じfixtureとの照合、明示された算術の確認。  
**未実施:** 実アプリの起動・操作、HTML/CSSのブラウザ描画、pointer hit testing、Tab/矢印/Enter/Escape、focus復帰、screen reader、色覚／拡大reflow試験、Windowsフォント、日本語IME、保存・API・実行の検証、参加者を伴う利用者テスト。
