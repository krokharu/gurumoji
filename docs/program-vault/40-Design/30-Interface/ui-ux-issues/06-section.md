---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-06
title: Web UI デザイン・UX 問題点一覧：E. 実装・保守（デザイン負債）
summary: E. 実装・保守（デザイン負債）。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 81
- 89
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：E. 実装・保守（デザイン負債）

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## E. 実装・保守（デザイン負債）

| ID | 重要度 | 問題 | 根拠（コード） | 影響 | 改善案 | 状態（2026-09-26） | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-26 | 中 | CSSで同じセレクターを何度も定義し直している | `style.css`（1,579行）で `.library-filters`, `.registry-guide`, `.registry-toolbar`, `.library-thumbnail`, `.library-actions` が複数回定義されている。`@media (max-width: 959px)` のブロックも複数ある | 後に書いた定義が優先されることに頼っており、変更がどこに影響するか読めない | 画面ごとにファイルか節を分け、重複した定義を統合する | 未対応 | 保留：同一セレクターだけで重複と判断しない |
| UX-27 | 中 | ボタンの基本スタイルの既定値が特殊 | `.primary-button` の既定が `width: 100%; margin-top: 34px;`、ボタン共通の `gap: 35px` | 使う箇所ごとに `width: auto; margin: 0` などの打ち消しが多数必要になる | 基本スタイルは幅を内容に合わせ、余白なしにする。全幅にしたい場合は修飾クラスで指定する | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：ボタンの既定を内容幅・外側余白なしにした | 保留：全画面に影響する既定スタイル変更は後回し |
| UX-28 | 低 | 同じ部品が重複し、グローバルなスタイルがあちこちで打ち消されている | AIトークン使用量のマークアップが `#progress-ai-usage` と `#result-ai-usage` に重複している。グローバルな `details` スタイルがすべての折りたたみ要素に枠線と余白を付け、各所で打ち消されている | 修正漏れや、見た目のばらつきが起きやすい | テンプレートの部品にする。`details` の既定スタイルは外す | 一部対応（2026-09-16に実装、HEAD 2f13f98に収録）：全 `details` に付く枠線と余白を外した。AIトークン使用量のマークアップは進捗と作業画面に2つ残る | 保留：共通化だけの変更は後回し |
| UX-29 | 低 | ダークモードに対応していない | `prefers-color-scheme` の指定がない。色の多くを変数ではなく直接指定している | 暗い環境で長時間作業するとまぶしい | 色を変数に移してから検討する（優先度は低い） | 未対応 | 保留：追加機能として保留 |
