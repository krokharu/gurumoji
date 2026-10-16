---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger-section-02
title: Gurumoji UI生成プロンプト調査の出典台帳：A1 Prompting best practices
summary: A1 Prompting best practices。出典ノート「Gurumoji UI生成プロンプト調査の出典台帳」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger
source_path: 40-Design/ui-design-research/2026-10-02/prompt-source-ledger.md
source_sha256: faf65733696071261e28ff8a5388a458405f1b6eb6056f7b544ec91896c59092
source_body_lines:
- 45
- 88
split_on: '2026-10-11'
---

# Gurumoji UI生成プロンプト調査の出典台帳：A1 Prompting best practices

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-source-ledger]]。必要な本文だけを取得する。

### A1 Prompting best practices

- 発行元: Anthropic
- URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- 日付: 不明 (unknown)
- 確認した版・範囲: 動的ページ、旧世代例を含む
- 確認箇所: General principles; Frontend design
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 明確な指示・文脈構造・具体例
- 制約: 古いFrontend例は全モデル共通の最新最適解ではない

### A2 Prompting Claude Opus 4.8

- 発行元: Anthropic
- URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8
- 日付: 不明 (unknown)
- 確認した版・範囲: Claude Opus 4.8
- 確認箇所: Design and frontend defaults
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 具体的方向を指定し、既定スタイルからの逸脱を検討する
- 制約: 例示のフォントや色の禁止を製品へ機械的に移植しない

### A3 Prompting Claude Opus 5.5

- 発行元: Anthropic
- URL: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
- 日付: 不明 (unknown)
- 確認した版・範囲: Claude Opus 5.5
- 確認箇所: Frontend design defaults; Tools for complex visual inputs
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 抽象的なAIらしさ回避より具体的パターンと反復
- 制約: 当該モデルの公式助言、独立した比較実験ではない

### A4 Best practices for Claude Code

- 発行元: Anthropic
- URL: https://code.claude.com/docs/en/best-practices
- 日付: 不明 (unknown)
- 確認した版・範囲: 取得時点のClaude Code docs
- 確認箇所: Give Claude a way to verify its work; Write an effective CLAUDE.md
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: テストや画像など実行可能な検証対象を渡す
- 制約: 自動検証だけで利用者受入まで確定するものではない
