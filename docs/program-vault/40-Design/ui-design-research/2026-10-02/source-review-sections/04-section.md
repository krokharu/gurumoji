---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review-section-04
title: Gurumoji 設計調査の独立出典監査：アクセシビリティの数値と規範の照合
summary: アクセシビリティの数値と規範の照合。出典ノート「Gurumoji 設計調査の独立出典監査」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review
source_path: 40-Design/ui-design-research/2026-10-02/source-review.md
source_sha256: 444a9f0716d8b24c2d90b4ab5ddd61f1c7727e707a5c9d4bb7b1e547494f42d5
source_body_lines:
- 109
- 128
split_on: '2026-10-11'
---

# Gurumoji 設計調査の独立出典監査：アクセシビリティの数値と規範の照合

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/source-review]]。必要な本文だけを取得する。

## アクセシビリティの数値と規範の照合

WCAG本文、Understanding、ARIA APGを分ける両調査の説明は適切。これらは同じ強さの規範ではなく、いずれもGurumoji現行画面の合格を証明しない。

| ID | 判定 | 重要な境界 | 一次資料 |
|---|---|---|---|
| W1/S22 | 2024-12-12版WCAG2.2 Recommendationを確認 | 抜粋の通過だけでAA適合を宣言しない | [WCAG2.2](https://www.w3.org/TR/WCAG22/) |
| W2/S24 | 2.5.8の24×24 CSS pxと例外を確認 | 見えるアイコン寸法だけでなく操作対象。44×44を全AA要求にしない。解説ページの2026-05-11更新も確認。仕様発行日とは別 | [Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) |
| S25 | 2.4.11でフォーカス対象が完全に隠れないことを確認 | 外側のフォーカス枠ではなく対象部品の隠れ方。枠の可視性は2.4.7等も別に評価。2pxを2.4.11の数値要求としない | [Focus Not Obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) |
| S26 | 状態メッセージのプログラムによる識別を確認 | 毎秒の読み上げが義務ではない。通知頻度の設計はD | [Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) |
| S27 | 320 CSS px相当のreflowと二次元例外を確認 | 390pxだけの画面確認では不足。200%文字拡大は別基準1.4.4 | [Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) |
| S28 | 通常文字4.5:1、大きい文字3:1を確認 | 例外・大きい文字の定義・表示状態を考慮。全文字を無条件に同じ閾値で分類しない | [Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) |
| S29 | 必要な非テキスト情報の3:1を確認 | 隣接色と必要な識別情報が対象。装飾全てに3:1を要求する意味ではない | [Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) |
| S30a | キーボード操作の要求を確認 | native要素の採用だけで複合UI全体の動作は保証されない | [Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html) |
| S30b | 一文字等のショートカットに停止・再割当・フォーカス時限定の代替を確認 | IME中に発火させない条件は製品の追加設計推論 | [Character Shortcuts](https://www.w3.org/WAI/WCAG22/Understanding/character-key-shortcuts.html) |
| S30c | ドラッグの単一ポインター代替を確認 | キーボード代替だけで2.5.7達成とは限らない | [Dragging](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html) |
| S23a | タブの役割・状態・矢印キーを確認 | 遅延がある場合の手動activationはAPGの推奨。すべてのナビゲーションをtabへ変える指示ではない | [APG Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) |
| S23b | モーダルのフォーカス・内部移動・閉じる操作を確認 | 起動元が消える等の復帰先例外あり。本文の「通常は」は適切 | [APG Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) |
| S23c | 複合UIのキーボード設計を確認 | ARIAを付けただけでは操作実装は増えない | [APG Keyboard](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) |
