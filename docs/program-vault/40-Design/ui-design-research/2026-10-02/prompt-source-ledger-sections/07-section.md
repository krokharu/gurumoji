---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger-section-07
title: Gurumoji UI生成プロンプト調査の出典台帳：R3 WebGen-Bench Evaluating LLMs on Generating Interactive and Functional Websites from Scratch
summary: R3 WebGen-Bench Evaluating LLMs on Generating Interactive and Functional Websites from Scratch。出典ノート「Gurumoji UI生成プロンプト調査の出典台帳」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger
source_path: 40-Design/ui-design-research/2026-10-02/prompt-source-ledger.md
source_sha256: faf65733696071261e28ff8a5388a458405f1b6eb6056f7b544ec91896c59092
source_body_lines:
- 276
- 301
split_on: '2026-10-11'
---

# Gurumoji UI生成プロンプト調査の出典台帳：R3 WebGen-Bench Evaluating LLMs on Generating Interactive and Functional Websites from Scratch

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-source-ledger]]。必要な本文だけを取得する。

### R3 WebGen-Bench Evaluating LLMs on Generating Interactive and Functional Websites from Scratch

- 発行元: Lu et al.
- URL: https://arxiv.org/html/2505.03733v2
- 日付: 2025-08-11 (version_revised)
- 確認した版・範囲: arXiv v2; initial 2025-05-06
- 確認箇所: Abstract; 3.2 Test Case Construction and Evaluation; Table 3 and 4.2 score definition; Appendix B limitations
- 根拠の強さ: 経験的根拠の候補。採録状況と一般化を断定しない
- 支持すること: 101指示・647ケースの評価。YES=1、PARTIAL=0.5のテストケース加重スコア
- 制約: 既存Flaskアプリの改修・長期保存を直接評価していない

### R4 WebGen-Agent Enhancing Interactive Website Generation with Multi-Level Feedback and Step-Level Reinforcement Learning

- 発行元: Lu et al.
- URL: https://arxiv.org/html/2509.22644v1
- 日付: 2025-09-26 (submitted)
- 確認した版・範囲: 数値・方法はarXiv v1を確認。出版状況はICLR 2026公式ポスター記録で別確認
- 確認箇所: arXiv v1 Table 1; 3.1 Benchmark Dataset and Baselines; 2.1 Workflow; Appendix A; ICLR official poster record
- 根拠の強さ: ICLR 2026会議発表の公式記録あり。限定された課題での経験的根拠
- 支持すること: Claude 3.5 Sonnetの部分点込みテストケース加重スコアが26.4%から51.9%へ変化したシステム比較
- 制約: サイト全体の成功率ではなく、プロンプト単体の効果でもない。速度・複雑なネットワーク条件は対象外
- 出版状況: ICLR 2026 conference poster
- 出版状況の確認先: https://iclr.cc/virtual/2026/poster/10008256
- 会議発表日: 2026-04-23（論文初出日とは区別）
- 評価式: 100 × (YES件数 + 0.5 × PARTIAL件数) ÷ 全テストケース数。サイト全体の成功率ではない
