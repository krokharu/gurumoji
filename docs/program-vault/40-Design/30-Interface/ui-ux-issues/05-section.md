---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-05
title: Web UI デザイン・UX 問題点一覧：D. アクセシビリティ
summary: D. アクセシビリティ。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 73
- 80
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：D. アクセシビリティ

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## D. アクセシビリティ

| ID | 重要度 | 問題 | 根拠（コード） | 影響 | 改善案 | 状態（2026-09-26） | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-23 | 中 | ~~タブの役割を指定しているが、キーボード操作に対応していない~~ 対応（2026-09-14、`1b8fe41`に収録済み）：`syncTabStops` で選択中のタブだけをTab移動の対象にし、←→／Home／Endでタブ間を移動する（切り替えは未保存確認があるためEnter／Space）。`aria-controls` を1つのIDにし、ハブ外の `#result-card` から `role="tabpanel"` を外した | `role="tablist"`/`"tab"` を指定しているのに、矢印キーでの移動もフォーカス位置の管理（`tabindex`）もない。`#result-card` は `show-library-button` のタブパネルと宣言されているが、ハブの外にある。`aria-controls` に複数のIDを入れている | スクリーンリーダーの利用者に、タブとして正しく伝わらない | APG（WAI-ARIA Authoring Practices Guide）のTabsパターンに合わせる。または、`role` を外して通常のナビゲーションボタンにする | 対応済み（`1b8fe41`） | P1：優先 |
| UX-24 | 中 | ~~デスクトップでフォーカス表示のスタイルがそろっていない~~ 対応（2026-09-14、`1b8fe41`に収録済み）：共通の `:focus-visible` をメディアクエリの外（`style.css` 冒頭、`--focus-ring`）へ移し、`outline: none` の入力欄や話者表にも表示されるようにした | 共通の `:focus-visible` スタイルは `@media (max-width: 959px)` の中にしかない。表の入力欄などは `outline: none` にして、枠線の色だけで代わりに示している | デスクトップでキーボード操作をすると、現在位置が分かりにくい箇所がある | 共通の `:focus-visible` スタイルをメディアクエリの外に出す | 対応済み（`1b8fe41`） | P1：優先 |
| UX-25 | 低 | `.visually-hidden` という名前なのに、実際は完全に非表示にしている | `[hidden], .visually-hidden { display: none !important; }` | 読み上げ用テキストにこのクラスを使うと、読み上げもされなくなる | `display: none` 用のクラスと、見た目だけ隠す標準的なクラスに分ける | 未対応 | 保留：現用途は非表示file入力。クラス意味の変更は不採用 |
