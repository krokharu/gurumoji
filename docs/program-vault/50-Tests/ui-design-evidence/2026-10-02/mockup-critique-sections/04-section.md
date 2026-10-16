---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique-section-04
title: Gurumoji 静止モックアップの独立批評：操作可能な試作で必須になる確認
summary: 操作可能な試作で必須になる確認。出典ノート「Gurumoji 静止モックアップの独立批評」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique
source_path: 50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md
source_sha256: a5930f15d27ba0bde495c47e25e7920c6463caf23571b284ea0a61df3c58cbb7
source_body_lines:
- 132
- 160
split_on: '2026-10-11'
---

# Gurumoji 静止モックアップの独立批評：操作可能な試作で必須になる確認

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/mockup-critique]]。必要な本文だけを取得する。

## 操作可能な試作で必須になる確認

以下は**要求と試験計画**であり、PNGで確認した結果ではない。

1. **定義の編集・再試行:** Bの左fieldを変える／Aで定義へ戻ると、右の試行binding、確認check、採用可能状態がどう変わるか。遅れて返った旧試行を現在の結果へ採用しない。試行連打の多重送信も確認
2. **採用と実行:** 未チェック時は採用できない。checkedでもserverのレビューbindingを満たすかは別。採用の成功／不明／競合を区別し、全件実行の対象・採用版・処理内容・送信先・保存先は次の実行準備で確認できる
3. **既採用の保護:** fixtureの旧`dur_base`と新`dur_review`を分離し、取消・試行失敗・通信断で旧採用版を維持する。画面上の「新しい定義」だけで合格にしない
4. **根拠を開いて戻る:** 同じrun、result、filter、選択引用、scrollへ戻る。Aのdetailsは起点へfocus。B desktopはpaneの非modal/modalモデルを決め、閉じた後に起点へfocus。B mobileの戻るは前の結果状態を復元し、再計算を始めない
5. **current sourceへの移動:** 保存引用12版と現在13版を混ぜない。現在の発話を開いて戻っても保存引用は固定。音声の無効理由をkeyboard/ATでも取得できる。別fixtureで同版・音声ありの通常再生→戻るも試す
6. **読み順・役割:** 表はheader/rowの対応、mobile cardは発話IDと値/理由の関連を持つ。tabsは適切なkeyboard操作と選択状態、disclosureはexpanded状態、checkboxは関連labelを持つ。status更新でページ全体を読み上げ直さない
7. **長文・狭幅:** 320 CSS px、200%/400%相当、長い日本語の定義・話者・引用、複数根拠、0件/全欠測/試行失敗、未知のlegacy来歴を確認。tableの二次元性で周囲の操作の横overflowを正当化しない

実装前に全状態の美しい画面を作る必要はないが、少なくとも「定義編集後・試行失効」「採用応答不明」「根拠版不明」の3状態を短いstoryboard又は状態表で補い、誤った成功を描かないことを確認する。

## 初回レビュー画像の識別

初回レビューは2026-10-02 19:48〜19:51 UTC頃。以下はレビューしたPNGのSHA-256。生成側が同じ名前を更新しても初回指摘の対象を特定できるように残す。

| ファイル | SHA-256 |
|---|---|
| a-evidence-390.png | `6c6627deffb3ae536f71b2702581585d3dfbed4eee0e793de2ced671f1ad79b0` |
| a-evidence-desktop.png | `4a11e24ad2f355c7d4336e57ee07edee30676e6ee1d1be527a66fcf9e338e295` |
| a-measurement-390.png | `fadafdc462890ececa1f71718b16d30ee016e08dc56e8d64e09191d78e3c28ba` |
| a-measurement-desktop.png | `648b8ee1c6fa6f1b703abe54d6db4931538c15530ac7b1d64164fece81830a59` |
| b-evidence-390.png | `b506985edd19a1b20ccd20dbc173cfc9112d3d6a670e80ada40e6d366c6e5e18` |
| b-evidence-desktop.png | `65247427cefac7b6b0e3250e12b8c23d04ac44ba3c5699faffb1ec93b0544de1` |
| b-measurement-390.png | `88c5615bab1c311c663031caccf7a720730df7d2aa6526fca2f720a0fffd0ba4` |
| b-measurement-desktop.png | `0a7064783f5ca91786ee4a5eeec179f7ab01b8e24f30c89a00538e1460b641b5` |
