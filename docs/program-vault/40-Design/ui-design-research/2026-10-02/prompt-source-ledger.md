---
note_id: "ui-archive-40-design-ui-design-research-2026-10-02-prompt-source-ledger"
note_type: "research-reference"
title: "Gurumoji UI生成プロンプト調査の出典台帳"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

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

### G5 DESIGN.md repository README

- 発行元: Google Labs
- URL: https://github.com/google-labs-code/design.md
- 日付: 不明 (unknown)
- 確認した版・範囲: alpha / main at retrieval
- 確認箇所: Getting Started; CLI Reference; Linting Rules; Status
- 根拠の強さ: 当該ツールの仕様と制約に強い。未実行の機能は未検証
- 支持すること: lint・diffと形式変換の存在、範囲
- 制約: CLIは本調査で未実行。lintはアプリ全体の適合証明ではない

### F1 Create a Figma Make file

- 発行元: Figma
- URL: https://help.figma.com/hc/en-us/articles/31304485164695-Create-a-Figma-Make-file
- 日付: 不明 (unknown)
- 確認した版・範囲: 動的Help Center
- 確認箇所: Best practices; Prompting; Working with attachments
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: task/context/constraints、参照と忠実再現、段階的編集
- 制約: Figmaでの推奨を任意のエージェントの機能と混同しない

### F2 Add guidelines to Figma Make

- 発行元: Figma
- URL: https://help.figma.com/hc/en-us/articles/33665861260823-Add-guidelines-to-Figma-Make
- 日付: 不明 (unknown)
- 確認した版・範囲: 動的Help Center
- 確認箇所: Content of Guidelines.md; Add guidelines
- 根拠の強さ: 当該ツールの仕様と制約に強い。未実行の機能は未検証
- 支持すること: 継続的な設計ルールをguidelinesファイルへ記述
- 制約: 自動読込はFigma Make固有の挙動

### F3 Write design system guidelines for Make kits

- 発行元: Figma
- URL: https://help.figma.com/hc/en-us/articles/43602393097239-Write-design-system-guidelines-for-Make-kits
- 日付: 不明 (unknown)
- 確認した版・範囲: 動的Help Center
- 確認箇所: Important considerations; Guidelines structure; Guidelines content
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 簡潔な入口と用途別文書で設計情報を渡す
- 制約: サンプルの見た目や読み順は自製品の要件ではない

### V1 Screenshots and Files

- 発行元: Vercel
- URL: https://v0.app/docs/screenshots
- 日付: 不明 (unknown)
- 確認した版・範囲: v0 docs取得時点
- 確認箇所: How it works; Best practices
- 根拠の強さ: 製品の推奨として強い。効果の一般化は限定的
- 支持すること: 画像に挙動・フロー・例外を補足する
- 制約: 見た目から推測した機能は実際の動作保証ではない

### V2 Design mode

- 発行元: Vercel
- URL: https://v0.app/docs/design-mode
- 日付: 不明 (unknown)
- 確認した版・範囲: v0 docs取得時点
- 確認箇所: Direct visual tweaks; Instructions; Undo redo preview
- 根拠の強さ: 当該ツールの仕様と制約に強い。未実行の機能は未検証
- 支持すること: 局所的な見た目の調整と構造変更を使い分ける
- 制約: 他アプリで同機能があるとは仮定しない

### D1 Design Tokens Format Module 2025.10

- 発行元: Design Tokens Community Group
- URL: https://www.designtokens.org/tr/2025.10/format/
- 日付: 2025-10-28 (published)
- 確認した版・範囲: 2025.10 stable
- 確認箇所: Status of This Document; Conformance
- 根拠の強さ: 交換形式の規範として強い。W3C標準とは別
- 支持すること: トークンの交換形式と仕様の正式な位置付け
- 制約: W3C RecommendationでもGoogle DESIGN.md形式そのものでもない

### W1 Web Content Accessibility Guidelines WCAG 2.2

- 発行元: W3C
- URL: https://www.w3.org/TR/WCAG22/
- 日付: 2024-12-12 (published_revision)
- 確認した版・範囲: WCAG 2.2 Recommendation
- 確認箇所: 1.4.3; 1.4.10; 1.4.11; 2.4.11; 2.5.8; 4.1.3
- 根拠の強さ: 適合条件の規範として強い
- 支持すること: 文字・操作・reflow等の成功基準
- 制約: 一部のチェックだけで全体適合とはいえない

### W2 Understanding Target Size Minimum

- 発行元: W3C WAI
- URL: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum
- 日付: 不明 (unknown)
- 確認した版・範囲: SC 2.5.8 Level AA
- 確認箇所: Success Criterion; Exceptions; Size requirement
- 根拠の強さ: 規範の解釈に有用。基準本文と区別
- 支持すること: 24 CSS pxと例外の解釈
- 制約: Understandingは説明資料。AAとAAAや推奨を区別する

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

### R5 Does AI Save Time on Product Design A Randomized Controlled Experiment of AI Prompt-to-Design Workflows

- 発行元: Stewart et al. / Figma
- URL: https://arxiv.org/html/2609.26725v1
- 日付: 2026-09-22 (submitted)
- 確認した版・範囲: arXiv v1
- 確認箇所: Authors; Methodology; Results; 5.2 Limitations
- 根拠の強さ: 無作為割付だが事業者研究・分析条件・査読状況未確認の制約あり
- 支持すること: 100名・定型3課題での完了時間比較
- 制約: Figma所属著者、完了課題条件付き、自己評価品質、固定順序。実務一般化は未確認

### L1 README

- 発行元: Gurumoji repository
- URL: ../../app/README.md
- 日付: 不明 (not_checked)
- 確認した版・範囲: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
- 確認箇所: 冒頭と主な機能
- 根拠の強さ: 製品説明として有用。実行時の機能確認ではない
- 支持すること: 製品用途と機能範囲の背景
- 制約: 本文の機能説明は実コード・操作・環境別受入で別途確認する

## 採用しなかった入口と留意点

- https://stitch.withgoogle.com/docs/design-md/specification: Web取得で本文0行。公式GitHub仕様を代替参照した。アクセス制限回避は行っていない。
- https://developers.openai.com/api/docs/guides/latest-model: 取得ページに複数世代の記述が共存。UI設計本文では対象世代の明確な個別資料を優先。
- https://ai.google.dev/gemini-api/docs/gemini-3: deprecatedと明示されていたため、リンク先Gemini 3.5の個別ガイドを参照。
- 二次情報: SNS投稿や二次まとめは発見の手掛かりに留め、技術的な主張の根拠には使用していない。

比較実験の計画値、画面幅、試行回数、テンプレートの具体的な設計案は本調査の提案。出典の実験結果と混同しない。
