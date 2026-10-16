---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger-section-03
title: Gurumoji UI生成プロンプト調査の出典台帳：G1 Prompt design strategies
summary: G1 Prompt design strategies。出典ノート「Gurumoji UI生成プロンプト調査の出典台帳」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger
source_path: 40-Design/ui-design-research/2026-10-02/prompt-source-ledger.md
source_sha256: faf65733696071261e28ff8a5388a458405f1b6eb6056f7b544ec91896c59092
source_body_lines:
- 89
- 132
split_on: '2026-10-11'
---

# Gurumoji UI生成プロンプト調査の出典台帳：G1 Prompt design strategies

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-source-ledger]]。必要な本文だけを取得する。

### G1 Prompt design strategies

- 発行元: Google
- URL: https://ai.google.dev/gemini-api/docs/prompting-strategies
- 日付: 不明 (unknown)
- 確認した版・範囲: Gemini一般とGemini 3の節
- 確認箇所: Clear and specific instructions; Context; Gemini 3
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 明確な文脈・制約・具体例、反復
- 制約: モデルと課題ごとに最適条件は異なる

### G2 What is new in Gemini 3.5 Flash

- 発行元: Google
- URL: https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5
- 日付: 2026-09-23 (last_updated)
- 確認した版・範囲: Gemini 3.5 Flash
- 確認箇所: Prompting best practices; footer last updated
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 簡潔な指示、長い文脈と依頼の分離
- 制約: モデル選定や最新全製品順位の根拠にはしない

### G3 Stitch DESIGN.md open-source announcement

- 発行元: Google Labs
- URL: https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/
- 日付: 2026-04-21 (published)
- 確認した版・範囲: draft specification announcement
- 確認箇所: Main article
- 根拠の強さ: 公開日と発表内容に強い。因果評価ではない
- 支持すること: DESIGN.md draftの公開と設計意図共有の目的
- 制約: 発表文は効果の独立検証ではない

### G4 DESIGN.md Format Specification

- 発行元: Google Labs
- URL: https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
- 日付: 不明 (unknown)
- 確認した版・範囲: alpha / main at retrieval
- 確認箇所: File structure; Design Tokens; Sections
- 根拠の強さ: 形式確認に強い。alphaのため安定性は限定的
- 支持すること: 任意YAMLトークンとMarkdown意図の分離
- 制約: alphaで変更可能。ファイル名だけで自動読込は保証しない
