---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-contract-section-05
title: Gurumoji UI設計指針：7 アクセシビリティと評価
summary: 7 アクセシビリティと評価。出典ノート「Gurumoji UI設計指針」の分割本文。
parent_note_id: design-ui-contract
source_path: 40-Design/ui-design-contract.md
source_sha256: 0a2b9fa0a3c575013504d0f1d458a3927e626353dc7f4d65c1f326aea175c974
source_body_lines:
- 116
- 135
split_on: '2026-10-11'
---

# Gurumoji UI設計指針：7 アクセシビリティと評価

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-contract/00-Index]]。必要な本文だけを取得する。

## 7 アクセシビリティと評価

WCAG 2.2 AAを設計基準にする。通常文字4.5:1、大きな文字3:1、必要な非テキスト状態3:1を該当条件と例外込みで確認。24×24 CSS pxは2.5.8の原則であり例外がある。44pxやfocus面積のAAA要件をAA必須と誤記しない。

- 可視label、名前・役割・状態、実Tab/Enter/矢印、モーダルの開閉・focus復帰、固定バーに隠れないfocusを確認
- 日本語IME中と入力欄では文字ショートカットを誤発火させない。色だけで話者・選択・欠測を区別しない
- 200%拡大、320 CSS px相当、長い日本語、表の代替、reduced-motionを確認。表の二次元性を周囲の操作までの免除理由にしない
- 更新・保存・失敗は必要なlive通知を持つ。毎秒の進捗でページ全体を読み上げ直さない

受入は **V1 contract/unit、V2 component、V3 browser operability、V4 assistive technology、V5利用者理解** を別記し、各層にpassed/failed/not-runを記録する。V3はproduction CSSと通常pointer/keyboardが必要。非表示要素へのJS click、closed dialogへの値代入、production CSSなしのfixtureはV1/V2の補助証拠であり、操作受入へ繰り上げない。

成功は正しい対象・版での完遂、編集保持、誤測定／根拠不一致の発見、回復、出力整合を主に測る。時間や美観は補助指標。エージェントのシナリオ歩行は利用者実験ではない。詳細: [受入方法](../../../50-Tests/30-Interface/ui-design-acceptance.md)、UX:S22〜S30、PR:P1/PR:P2。

## 8 採用と保守

推奨順は可視入口・測定意味→状態／版／保存先→accessibility→履歴→タスク別構成・密度。P1の最小修正をIA全面移行まで待たせない。

着手前に[実装計画](../ui-design-implementation-plan/00-Index.md)§6のチェックリストで、確認済み事実、未実装の技術判断、利用者検証待ちの配置選択を区別する。

基本作業はdotで進め、意味のある節目だけSoftware Vaultへ対象commit、決定理由、検証と未実行、次の作業を残す。0.3文書は`88f5e3e`で統合済み。本0.4更新はSoftware Vaultの文書に反映し、アプリのコード・runtime・移入Vaultは変更していない。今後の実装・受入の節目に[運用引継ぎ](../../../60-Operations/20-Development/dot-cloud-development-handoff/00-Index.md)と既存ノートへ記録し、研究者所有ノートへ開発ログを複製しない。
