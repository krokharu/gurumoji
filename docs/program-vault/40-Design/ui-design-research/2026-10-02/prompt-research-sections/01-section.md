---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research-section-01
title: GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：GurumojiのUI設計をAIに依頼するための調査と実践テンプレート
summary: GurumojiのUI設計をAIに依頼するための調査と実践テンプレート。出典ノート「GurumojiのUI設計をAIに依頼するための調査と実践テンプレート」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research
source_path: 40-Design/ui-design-research/2026-10-02/prompt-research.md
source_sha256: 7f17ce12573593c6bdc2e07d39f5f4251c5749bb84459f9eb17cde77cae80c66
source_body_lines:
- 1
- 24
split_on: '2026-10-11'
---

# GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：GurumojiのUI設計をAIに依頼するための調査と実践テンプレート

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-research]]。必要な本文だけを取得する。


# GurumojiのUI設計をAIに依頼するための調査と実践テンプレート

調査基準日 2026年10月2日 UTC  
対象 既存の日本語研究支援Webアプリの設計改善  
版 1.1  
検証範囲 公開一次資料と研究論文の確認、既存READMEの参照。新たなモデル比較実験、利用者調査、アプリ変更、公開は実施していない

## 1 結論

Gurumojiでは「AIっぽくない画面にして」という依頼を、**研究者がどの根拠を見て、どの状態を理解し、何を確実に終えられる画面にするか**へ置き換える。配色やフォントの禁止語を増やすより、対象作業、既存の不変条件、情報の優先順位、見本の使い方、完了を判定する証拠を渡す。

最初に採用したい実務上の方針は次の7点。これらは一次資料を踏まえた本調査の提案であり、Gurumojiで効果測定済みの結論ではない。

1. **現行画面とコードを基点にする**。新規アプリ用のReact/Tailwindテンプレートへ勝手に置き換えない
2. **1つの主要フローを単位に依頼する**。「発話修正→保存→分析更新の必要性→再分析」のように、画面をまたぐ完了まで定義する
3. **外観の規則と操作の規則を分ける**。DESIGN.mdは視覚的意図、画面仕様は状態遷移、既存コードは実際の契約の確認先とする
4. **参考画像には採用する部分を注釈する**。密度、文字階層、余白、ペイン構成のどれを参考にするかを指定する
5. **初稿を実際に描画して確認する**。スクリーンショット、DOMやCSSの値、操作結果、保存結果はそれぞれ異なる証拠として扱う
6. **修正は観察できる差分で依頼する**。「洗練させて」ではなく「保存状態が本文より目立つ」「根拠から戻ると選択位置が失われる」などとする
7. **評価済みと未確認を分ける**。ビルド成功を使いやすさの確認に、Linuxの結果をWindows実画面の受入に、旧版画像を現行不具合の証拠にしない

公式ガイドの共通項は、文脈に合った具体性、再利用できる設計情報、小さい反復、検証可能な完了条件である。ただし各社のサンプルの美的嗜好まで共通ではない。[OpenAIの設計指針](https://developers.openai.com/api/docs/guides/frontend-prompt)、[Claude Codeの検証指針](https://code.claude.com/docs/en/best-practices)、[Googleのプロンプト指針](https://ai.google.dev/gemini-api/docs/prompting-strategies)、[Figma Makeの作成ガイド](https://help.figma.com/hc/en-us/articles/31304485164695-Create-a-Figma-Make-file)
