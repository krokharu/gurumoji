---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-04
title: Web UI デザイン・UX 問題点一覧：C. 視覚デザイン・一貫性
summary: C. 視覚デザイン・一貫性。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 62
- 72
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：C. 視覚デザイン・一貫性

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## C. 視覚デザイン・一貫性

| ID | 重要度 | 問題 | 根拠（コード） | 影響 | 改善案 | 状態（2026-09-26） | 選別（2026-09-14） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-17 | 中 | ~~文字が非常に小さい箇所が多い~~ 対応（2026-09-14、`1b8fe41`に収録済み）：`:root` に `--text-min: .7rem`（約11px）を定義し、`style.css` の .7rem未満の指定166か所をこの変数に置き換えた。`ai-effort.css` の11pxは12pxにした。案の.75remより小さくしたのは、密な分析ダッシュボードの配置を崩さないため | `style.css` に `font-size: .4x–.5xrem`（約8〜9.6px）が25か所あり、`.6xrem` も多数。分析ダッシュボード、トークン使用量、リソースモニター、アンケート分析などに集中している | 判読しにくい。高DPI以外の環境や高齢の利用者に厳しい | 本文の最小サイズを .75rem（12px）程度に決め、変数（トークン）で管理する | 対応済み（`1b8fe41`） | P1：優先 |
| UX-18 | 中 | AIエフォート設定だけが別のデザインになっている | `ai-effort.css` は青系（`#315ed0`, `#678bef`）とpx単位を使い、未定義の変数 `var(--bg)` を参照している。Obsidian仕上げの浮き表示も青系 | 緑基調のデザインから浮いて見え、別のアプリのように見える | `style.css` の `:root` の変数に合わせる。未定義の変数は削除する | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：`ai-effort.css` を共通の緑系トークンに合わせ、未定義の `var(--bg)` を削除 | 保留：未定義変数は局所修正候補。配色統一は保留 |
| UX-19 | 低 | 補助テキストのコントラストが足りない可能性がある | `.drop-zone-copy small`（`#8a948f`）、`.product-signature`（`#87918c`）、無効状態（`#9aa39e`）が明るい背景の上にある | WCAGの4.5:1を満たさない可能性がある（計測は未実施） | コントラストを計測し、`--muted` 以上の濃さにする | 未対応 | 保留：実背景・状態ごとの計測後に判断 |
| UX-20 | 低 | 常にアニメーションし続ける要素がある | `.status-pill.ready` の `token-glow` が無限に繰り返す。ハードウェアランプも発光している | 状態が正常なのに注意を引きつける | 状態が変わった時だけ1回動かす（prefers-reduced-motion の設定時は停止済み） | 対応済み（UI再設計、2026-09-16に実装、HEAD 2f13f98に収録。[[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]）：正常状態のトークン表示の点滅をやめ、動くのは処理中のチップだけ | 保留：reduce-motion対応あり。常時発光の変更は保留 |
| UX-21 | 低 | 英字の見出しラベルと日本語の見出しが全カードで二重になっている | `GROUP INTERVIEW ANALYSIS` などの `.eyebrow` がほぼすべてのカードにある。スプラッシュの `aria-label` は英語 | 情報量が増え、読み上げの言語もそろわない | 英字ラベルは主な画面の見出しだけに減らす。`aria-label` は日本語にする | 一部対応（2026-09-16に実装、HEAD 2f13f98に収録）：カードの英字ラベル（`.eyebrow`）を日本語の小見出しにした。分析サイドバーと進捗・トークン使用量の英字表記は残る | 保留：装飾・表記は該当画面改修時 |
| UX-22 | 低 | 説明文が多すぎる。技術的な文字列をそのまま表示している | AIエフォートの説明が2段落あるなど、各カードに長い説明がある。マシン診断にCPUの生の文字列（例：`Intel64 Family 6 Model …`）を表示している | 主な操作が文章に埋もれる | 説明は1行にし、詳細はヘルプの折りたたみに移す。CPU表示は「20スレッド」などの要約にする | 未対応 | 保留：説明の必要性を操作ごとに確認 |
