---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger-section-06
title: Gurumoji UI生成プロンプト調査の出典台帳：P1 Visual comparisons
summary: P1 Visual comparisons。出典ノート「Gurumoji UI生成プロンプト調査の出典台帳」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger
source_path: 40-Design/ui-design-research/2026-10-02/prompt-source-ledger.md
source_sha256: faf65733696071261e28ff8a5388a458405f1b6eb6056f7b544ec91896c59092
source_body_lines:
- 232
- 275
split_on: '2026-10-11'
---

# Gurumoji UI生成プロンプト調査の出典台帳：P1 Visual comparisons

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-source-ledger]]。必要な本文だけを取得する。

### P1 Visual comparisons

- 発行元: Microsoft Playwright
- URL: https://playwright.dev/docs/test-snapshots
- 日付: 不明 (unknown)
- 確認した版・範囲: Playwright docs取得時点
- 確認箇所: Generating screenshots; environment warning; Updating screenshots
- 根拠の強さ: 当該ツールの仕様と制約に強い。未実行の機能は未検証
- 支持すること: 同じ環境の基準画像比較と視覚差分
- 制約: OS・フォント・ブラウザー差を解消する万能テストではない

### P2 Accessibility testing

- 発行元: Microsoft Playwright
- URL: https://playwright.dev/docs/accessibility-testing
- 日付: 不明 (unknown)
- 確認した版・範囲: Playwright docs取得時点
- 確認箇所: Scanning for WCAG violations; Scanning parts; automated testing limitation
- 根拠の強さ: 当該ツールの仕様と制約に強い。未実行の機能は未検証
- 支持すること: 状態ごとの自動検査と検出限界
- 制約: 自動検査成功はWCAG全面適合ではない

### R1 Design2Code Benchmarking Multimodal Code Generation for Automated Front-End Engineering

- 発行元: ACL Anthology / Si et al.
- URL: https://aclanthology.org/2025.naacl-long.199/
- 日付: 2025-04 (published_month)
- 確認した版・範囲: NAACL 2025 final paper
- 確認箇所: Abstract; conference metadata
- 根拠の強さ: 対象条件での経験的根拠。外的妥当性は限定的
- 支持すること: 484ページの視覚要素・レイアウト評価
- 制約: 静的再現の評価。現在モデル順位や保存品質は示さない

### R2 DesignBench A Comprehensive Benchmark for MLLM-based Front-end Code Generation

- 発行元: Xiao et al.
- URL: https://arxiv.org/html/2506.06251v3
- 日付: 2026-03-15 (version_revised)
- 確認した版・範囲: arXiv v3; initial 2025-06-06
- 確認箇所: Abstract; 6.4 RQ4; Threats to Validity
- 根拠の強さ: 経験的根拠の候補。採録状況と一般化を断定しない
- 支持すること: 生成・編集・修復の分離、編集でのコード文脈の有用性
- 制約: 旧世代モデル中心。HTMLの会議情報はプレースホルダーを含むため採録を断定しない
