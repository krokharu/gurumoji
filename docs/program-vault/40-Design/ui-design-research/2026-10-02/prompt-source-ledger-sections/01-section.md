---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger-section-01
title: Gurumoji UI生成プロンプト調査の出典台帳：Gurumoji UI生成プロンプト調査の出典台帳
summary: Gurumoji UI生成プロンプト調査の出典台帳。出典ノート「Gurumoji UI生成プロンプト調査の出典台帳」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger
source_path: 40-Design/ui-design-research/2026-10-02/prompt-source-ledger.md
source_sha256: faf65733696071261e28ff8a5388a458405f1b6eb6056f7b544ec91896c59092
source_body_lines:
- 1
- 44
split_on: '2026-10-11'
---

# Gurumoji UI生成プロンプト調査の出典台帳：Gurumoji UI生成プロンプト調査の出典台帳

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-source-ledger]]。必要な本文だけを取得する。


# Gurumoji UI生成プロンプト調査の出典台帳

確認日 2026年10月2日 UTC  
版 1.1  
本文 `prompt-research.md`  
公開日不明は本文に日付がなかったもの。クロール日から推定していない。
R4は閲覧したarXiv版とICLR 2026出版状況を分けて記録。加重スコアとサイト全体の成功率を区別する。

## 公開一次資料と研究論文

### O1 Frontend prompt instructions

- 発行元: OpenAI
- URL: https://developers.openai.com/api/docs/guides/frontend-prompt
- 日付: 不明 (unknown)
- 確認した版・範囲: 対象GPT-5.5
- 確認箇所: Frontend guidance; Build with empathy; Design instructions
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 用途と既存設計に合うUIの指示例
- 制約: 美的方針の推奨であり普遍的なUX法則ではない

### O2 Designing delightful frontends with GPT-5.4

- 発行元: OpenAI
- URL: https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4
- 日付: 2026-03-20 (published)
- 確認した版・範囲: GPT-5.4
- 確認箇所: Practical tips; Design system; Computer Use and Verification
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 参照・制約・描画後確認の推奨
- 制約: 推論設定や効果の記述を他世代へ一般化しない

### O3 Rethinking skills and prompts for GPT-6 Astra

- 発行元: OpenAI
- URL: https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
- 日付: 2026-09-11 (published)
- 確認した版・範囲: GPT-6 Astra
- 確認箇所: Better skills; Up-to-date AGENTS.md; Persistence
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 文脈の肥大化を避け、完了と境界を定義する
- 制約: モデル固有の挙動と推奨を含む
