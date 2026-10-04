---
note_id: design-ui-assets-2026-10-02
note_type: design-reference
title: "UI静止案の保存範囲（2026-10-02）"
summary: "v1仕様注釈図とv2利用者表示の正しい用途・版・収録範囲。"
status: current
updated: 2026-10-02
tags: [gurumoji/design, gurumoji/ui]
---

# UI静止案の保存範囲

- 比較の入口は[clean v2](prototypes/v2/index.html)。比較用8図と定義変更後の補助状態2図を収録した。画像は全長の静止図で、実viewport・操作・保存・ATの検証ではない
- [画面外凡例](prototypes/v2/outside-legend.md)は設計条件、[v1比較資料](prototypes/comparison.md)は初期の仕様注釈付き8図の説明。v1とv2を独立した利用者実験数へ合算しない
- [独立批評](../../../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)の初回／修正後は同じ設計案の反復。静止図の改善確認を現行アプリの受入へ置き換えない

v1はSVG 8図と自己完結HTML、v2はSVG 10図・PNG 10図と自己完結HTMLを保存する。すべて合成データ。fixture、説明、元の図一覧・静的検証JSONも保持する。builder／validatorスクリプト、描画ログ、v1の重複PNGは同梱しない。

各版のvalidation.jsonは元調査時の記録で、hash欄に列挙された全生成素材を同梱したというmanifestではない。本文に追加したSoftware Vault属性や相対リンクの調整も元hashの対象外。取り込み後のファイルとhashは[統合manifest](../../../50-Tests/ui-design-evidence/2026-10-02/integration-manifest.json)を使う。採用されたUIのスクリーンショットや操作できるアプリとして配布しない。
