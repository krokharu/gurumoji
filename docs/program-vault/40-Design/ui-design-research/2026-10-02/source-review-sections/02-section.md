---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review-section-02
title: Gurumoji 設計調査の独立出典監査：最新モデルガイドと仕様の照合
summary: 最新モデルガイドと仕様の照合。出典ノート「Gurumoji 設計調査の独立出典監査」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review
source_path: 40-Design/ui-design-research/2026-10-02/source-review.md
source_sha256: 444a9f0716d8b24c2d90b4ab5ddd61f1c7727e707a5c9d4bb7b1e547494f42d5
source_body_lines:
- 44
- 70
split_on: '2026-10-11'
---

# Gurumoji 設計調査の独立出典監査：最新モデルガイドと仕様の照合

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/source-review]]。必要な本文だけを取得する。

## 最新モデルガイドと仕様の照合

以下は製品の公式助言としての確認であり、独立した効果測定や最良モデル認定ではない。

| ID | 監査した主張 | 判定と条件 | 原資料 |
|---|---|---|---|
| O1 | フロントエンド指示の対象は GPT-5.5。既存設計・用途に合う業務画面を重視 | 確認。本文冒頭と Build with empathy に一致。「全現行モデルの共通最適解」にはしない | [OpenAI frontend](https://developers.openai.com/api/docs/guides/frontend-prompt) |
| O2 | GPT-5.4 記事は2026-03-20。参照と描画後検証を推奨 | 日付・方針を確認。低い推論設定に関する助言を他モデルや複雑な仕様作業へ移植しないという限定は適切 | [GPT-5.4 記事](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4) |
| O3 | Astra 記事は2026-09-11。常設文脈を整理し、完了と境界を明確化 | 日付・方針を確認。UIの比較実験ではない。「仕様不要」への読み替え不可 | [Astra 記事](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) |
| A1 | 一般指針に旧世代の美観プロンプト例がある | 確認。モデル一覧は更新されるが、Frontend例にはOpus4.5/4.6の記述が残る。段落ごとの対象世代を読む | [Claude 一般指針](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) |
| A2 | Opus4.8 は具体的代案・複数方向案を推奨 | 確認。書体や背景色の禁止はモデルの既定スタイルを変える例であり、普遍的UX則ではない | [Opus4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8) |
| A3 | Opus5.5 は抽象的なAI感の回避より、実出力の特定パターンを見て反復する | 確認。公開日不明の扱いも妥当 | [Opus5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5) |
| A4 | テスト・ビルド・画像で結果を確認可能にする | 確認。確認手段の推奨であり、利用者受入の代替ではない | [Claude Code](https://code.claude.com/docs/en/best-practices) |
| G1 | 明確な指示、区分した文脈、例、反復 | 確認。長く書くこと自体の推奨ではない | [Gemini 一般指針](https://ai.google.dev/gemini-api/docs/prompting-strategies) |
| G2 | Gemini3.5 Flash ページの更新日は2026-09-23。簡潔さと長文後の依頼を推奨 | フッターと Prompting best practices を確認。該当助言はGemini3.x向けと書かれている | [Gemini3.5](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5) |
| G3 | Googleが2026-04-21にDESIGN.md draft仕様を公開 | 日付・draftの表現を確認 | [Google発表](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/) |
| G4 | 任意YAML frontmatterとMarkdown本文、alpha、標準節、省略可 | 確認。トークン値と説明文の役割は区別される。存在する標準節の順序も仕様の一部。単にファイルを置けば全製品が自動で読むという主張はしない | [Google仕様](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md) |
| G5 | lint・diff・exportがあり、alphaで変更され得る | READMEで確認。CLI未実行の明示は適切。lintの形式・限定的色対検査をアプリのWCAG適合へ広げない | [公式リポジトリ](https://github.com/google-labs-code/design.md) |
| D1 | DTCG2025.10は安定したトークン交換仕様だがW3C Recommendationではない | 2025-10-28のFinal Community Group Report表記を確認。Status節はW3C Standards Track外と明示。GoogleのYAMLと同一形式ではない | [DTCG2025.10](https://www.designtokens.org/tr/2025.10/format/) |
| F1 | task/context/constraints、画像と構造化Figmaフレームの差、対象を絞る編集 | 公式本文で確認。フレームの情報量と操作契約の正しさは別 | [Figma Make作成](https://help.figma.com/hc/en-us/articles/31304485164695-Create-a-Figma-Make-file) |
| F2 | Guidelines.mdで継続的指針を渡せる | 確認。ファイル名の大文字小文字は公式ページ内でも混在するため、実環境のファイルと読込みを確認する | [Figma guidelines](https://help.figma.com/hc/en-us/articles/33665861260823-Add-guidelines-to-Figma-Make) |
| F3 | 短い入口から用途別の細かい資料へ案内 | 確認。サンプルの数値・美的嗜好はGurumoji要件ではない | [Make kits指針](https://help.figma.com/hc/en-us/articles/43602393097239-Write-design-system-guidelines-for-Make-kits) |
| V1 | 高解像度画像・対象切抜き・挙動や例外の補足 | 確認。画像から推測する機能は実システムの保存契約を検証しない | [v0 Screenshots](https://v0.app/docs/screenshots) |
| V2 | 局所的な外観調整と自然言語の構造変更を使い分ける | 確認。既存Flaskアプリをv0推奨スタックへ変える因果的根拠にはならない | [v0 Design mode](https://v0.app/docs/design-mode) |
| P1 | 比較画像のOS・ブラウザー・フォント等の環境を揃える | 確認。公式の環境差警告と一致 | [Playwright画像比較](https://playwright.dev/docs/test-snapshots) |
| P2 | 自動アクセシビリティ検査と手動・利用者評価を併用 | 確認。サンプルのWCAG2.1タグだけをコピーして2.2全体を検査済みとはしない | [Playwright accessibility](https://playwright.dev/docs/accessibility-testing) |
