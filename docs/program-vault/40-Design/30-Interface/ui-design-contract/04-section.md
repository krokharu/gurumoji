---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-contract-section-04
title: Gurumoji UI設計指針：6 視覚的意図
summary: 6 視覚的意図。出典ノート「Gurumoji UI設計指針」の分割本文。
parent_note_id: design-ui-contract
source_path: 40-Design/ui-design-contract.md
source_sha256: 0a2b9fa0a3c575013504d0f1d458a3927e626353dc7f4d65c1f326aea175c974
source_body_lines:
- 98
- 115
split_on: '2026-10-11'
---

# Gurumoji UI設計指針：6 視覚的意図

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-contract/00-Index]]。必要な本文だけを取得する。

## 6 視覚的意図

**日本語の長文と数値を落ち着いて照合できる、控えめな研究作業面。** 既存の緑・紙色・日本語sans-serifを保ち、強い色と面積は主操作・現在地・重要な状態へ配分する。AI感を避けるためだけの紫禁止、紙色禁止、セリフ導入は行わない。

通常の説明・操作名は短い日本語にする。ID等の来歴詳細と開発用のAPI／移行注記は分け、後者を利用者画面の常設警告にしない。[利用者表示v2](../../ui-design-assets/2026-10-02/prototypes/v2/index.html)は比較8図＋定義変更後の補助2図。初期の仕様注釈付き8図は契約確認用で、密度比較はv2を使う。[独立批評](../../../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)の修正確認は静止表示に限る。Aの段階導入を暫定候補にし、Bの対照面・根拠pane・4タスク入口は個別に利用者検証する。画面の短さを効率や好みの証拠にしない。

| 役割 | 現行値／資産 | 提案と検証境界 |
|---|---|---|
| 本文／作業面 | ink `#18211d`、paper `#f4f5f0`、card `#fffef9` | 継承。実背景・各stateのcontrastは別測定 |
| 主操作／選択 | green `#1c6b50`、dark `#13513c`、soft `#e9f2e6` | 継承。保存成功／人の確認／話者属性を同じ緑だけで表さない |
| 警告／補助／focus | orange `#e87941`、muted `#68736e`、35%緑ring | warning-text・muted-text・focus-ringの役割へ整理。色値はcomputed style後に確定 |
| 書体 | Yu Gothic UI / Hiragino / Meiryo / sans-serif | 継承。新規webfontを前提にしない |
| 文字階層 | 画面によって`.7rem`〜`.9375rem`等が混在 | 本文16px相当、label14〜15px相当、補助13px相当を比較候補にする。WCAG規定値ではない |
| 余白／角丸 | radius16/10px、部品に22px等、可変padding | 値を全統一する前に部品責務を揃える。要約と詳細を分け、警告を隠して密度を下げない |
| 幅／動き | content1280px、960/540pxの境界、既存reduced-motion | 当面維持。固定バー、選択nav、根拠往復のfocus/scrollを優先確認 |

DG-09で計算したdrop補助文字は白背景で3.128:1、話者概要の未保存文字は約2.63〜2.76:1。一方、分析sidebarの未保存は約5.99:1。すべての未保存表示やfocusを一律不合格とせず、CSS cascadeと実描画の用途ごとに直す。密度・幅・行間の候補は現行画像と同一条件で比べて採用する。
