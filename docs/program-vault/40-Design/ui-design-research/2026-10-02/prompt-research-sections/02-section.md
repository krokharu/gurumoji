---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research-section-02
title: GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：2 根拠の読み方と調査限界
summary: 2 根拠の読み方と調査限界。出典ノート「GurumojiのUI設計をAIに依頼するための調査と実践テンプレート」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research
source_path: 40-Design/ui-design-research/2026-10-02/prompt-research.md
source_sha256: 7f17ce12573593c6bdc2e07d39f5f4251c5749bb84459f9eb17cde77cae80c66
source_body_lines:
- 25
- 80
split_on: '2026-10-11'
---

# GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：2 根拠の読み方と調査限界

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-research]]。必要な本文だけを取得する。

## 2 根拠の読み方と調査限界

### 2.1 根拠の区分

|区分|何を支持するか|支持しないこと|
|---|---|---|
|仕様・標準|形式、必要条件、適合条件|その仕様を使えば見た目や作業効率が自動的に向上するという因果|
|ベンダー公式ガイド|当該製品の機能、推奨する使い方|独立した他社比較、全モデルに普遍的な効果|
|査読付きベンチマーク|指定された課題、モデル、評価条件での結果|現在の全モデル順位、実務・日本語・研究者での同じ効果|
|プレプリント|新しい実験結果の候補と再現可能な方法|査読通過、一般化された確定知見|
|Gurumoji向け提案|この製品で次に検証する仮説|既存仕様やユーザー調査により確定した需要|

閲覧日と公開日は別々に扱った。更新日が本文で確認できないWeb文書は、公開日を推定せず「不明」とした。検索エンジンの「最近クロール」は記事の公開日でも、内容全体の更新日でもない。本文に当たった資料のURL、確認箇所、適用範囲は `prompt-source-ledger.json` と `prompt-source-ledger.md` に記録している。

本資料は「全製品中で最もUIが上手いモデル」のランキングではない。比較には同じ課題、素材、環境、評価基準、反復予算が必要であり、この調査ではその実験を行っていない。

### 2.2 Gurumojiの前提

READMEには文字起こし、話者分離、発話編集、分析、根拠音声への移動、出力、Obsidian関連機能が記載されている。デスクトップの研究作業を主眼とし、390 CSS px程度のスマートフォン画面も対象とする。これは製品・作業の前提であり、実利用者へのインタビューから作られた検証済みペルソナではない。

参照したアプリHEADは `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`。この調査でのREADME参照とGit状態確認は読み取りのみ。既存25改善のうちWindows GUIで受入待ちの10項目を「未実装」と再分類しない。実装、設計提案、環境ごとの受入状況は別の軸で記録する。

## 3 各社の現在の指針から何を採用するか

### 3.1 OpenAI

2026年3月20日のGPT-5.4向け記事は、視覚参照、設計上の制約、内容の構成、描画後の確認を勧める。現在取得したフロントエンド用指示ページは対象をGPT-5.5と明記し、作業用アプリは業務に合った静かな構成と既存設計を重視する。2026年9月11日のAstra向け記事は、長い常設指示を整理し、必要な資料へ条件付きで案内し、完了条件を明確にする方向へ進んでいる。**「細かな仕様は必要、すべての手順を毎回長文で命令する必要はない」**と読むのが妥当。

Gurumojiでは、保存・分析・根拠確認の要件を短く固定し、対象画面の詳細だけを追加する。GPT-5.4の記事にある低い推論設定の推奨を、そのまま他世代・複雑な状態設計へ適用しない。これらのガイドだけでは最適設定は決まらない。[O1](https://developers.openai.com/api/docs/guides/frontend-prompt)、[O2](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4)、[O3](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)

### 3.2 Anthropic

一般ガイドに残る旧世代向けの美観例は、特徴的な書体、配色、演出を強く誘導する。Opus 4.8専用ガイドは、具体的な代替仕様や方向案の比較を勧める。取得時点のOpus 5.5専用ガイドでも、抽象的な「AIらしさを避ける」だけでは別の既定スタイルへ移るため、初稿を見て特定のパターンを修正する方針になっている。

採用するのは、**具体的な代替案と観察に基づく修正**。フォントや紙色の全面禁止は採用しない。Gurumoji既存の緑・紙色は、単に別モデルの典型例に似ているという理由で捨てる必要はない。必要なのはこの製品での役割と可読性である。[A1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)、[A2](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8)、[A3](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)

Claude Code公式は、テスト、ビルド、比較画像など、モデルが結果を確かめられる対象を渡すことを重視する。これは美観プロンプト単独より、Gurumojiの既存改善に適した運用である。[A4](https://code.claude.com/docs/en/best-practices)

### 3.3 Google GeminiとStitch

Geminiの一般ガイドは明確な指示、区切られた文脈、具体例、段階的な処理を扱う。2026年9月23日更新のGemini 3.5 Flashガイドは、古い世代向けの複雑なプロンプトを持ち込まず、簡潔な指示にするよう勧めている。長い資料を渡す場合は、資料と最後の具体的な依頼を分ける。[G1](https://ai.google.dev/gemini-api/docs/prompting-strategies)、[G2](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5)

Stitchは2026年4月21日にDESIGN.mdのdraft仕様を公開した。公式仕様の核は、任意のYAML frontmatterによるトークンと、Markdownによる意図・使い方の分離。取得時点でalphaであり、標準化が完了した不変の規格ではない。**形式を採用することと、ツールが自動で読み込むことは別**なので、利用先で読み込みを確かめる。[G3](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/)、[G4](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md)

### 3.4 Figma Make

Figmaの公式資料は、タスク・文脈・制約の指定、参考と忠実再現の区別、小さい対象への編集を重視する。Figmaフレームは構造化データを含むため、画像から値を推測する場合とは情報量が異なる。Guidelines.mdは設計上の規則を継続的に渡す仕組みで、Make kit向けには簡潔な入口と用途別の小さい資料を勧めている。

Gurumojiへの応用は、最初から全画面を再生成することではなく、対象フローとその状態群だけを切り出すこと。Figma専用の自動読み込みを、任意のエージェントでも同じと仮定しない。[F1](https://help.figma.com/hc/en-us/articles/31304485164695-Create-a-Figma-Make-file)、[F2](https://help.figma.com/hc/en-us/articles/33665861260823-Add-guidelines-to-Figma-Make)、[F3](https://help.figma.com/hc/en-us/articles/43602393097239-Write-design-system-guidelines-for-Make-kits)

### 3.5 v0

v0は高解像度の全体画像または対象箇所の切り抜きと、挙動・例外の補足を推奨する。選択箇所に対するDesign modeでは、局所的な見た目の調整と自然言語による構造変更を使い分ける。Gurumojiにも、**局所調整で済むものを全面再生成しない**という考え方が使える。

一方、v0の推奨スタックを理由に既存のFlaskと素のJavaScriptを置き換える根拠はない。また「スクリーンショットから推測した機能」は、実際の保存・分析・出力契約の証拠にはならない。[V1](https://v0.app/docs/screenshots)、[V2](https://v0.app/docs/design-mode)
