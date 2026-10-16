---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research-section-03
title: GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：4 研究論文が示すことと示さないこと
summary: 4 研究論文が示すことと示さないこと。出典ノート「GurumojiのUI設計をAIに依頼するための調査と実践テンプレート」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research
source_path: 40-Design/ui-design-research/2026-10-02/prompt-research.md
source_sha256: 7f17ce12573593c6bdc2e07d39f5f4251c5749bb84459f9eb17cde77cae80c66
source_body_lines:
- 81
- 102
split_on: '2026-10-11'
---

# GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：4 研究論文が示すことと示さないこと

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-research]]。必要な本文だけを取得する。

## 4 研究論文が示すことと示さないこと

### 4.1 画像再現と実務の完成は違う

NAACL 2025のDesign2Codeは484件の実Webページを用い、視覚要素の再現とレイアウトを細かく評価した。静的な参考画像からコードを作る能力を調べる資料として重要だが、長い研究作業や保存の正しさを測ったものではない。[R1](https://aclanthology.org/2025.naacl-long.199/)

DesignBenchは900ページで生成・編集・修復を分け、複数のUI実装方式を評価する。特に編集・修復ではコード文脈が有用だったという結果は、「修正は画像だけを渡せばよい」という考えへの反証となる。ただし対象はClaude 3.7、GPT-4o、Gemini 2.0等の当時のモデルとベンチマークであり、画像を不要にする一般則ではない。[R2](https://arxiv.org/html/2506.06251v3)

### 4.2 見た目と操作のフィードバックを分ける

WebGen-Benchは101件のWebサイト生成指示と647件のテストケースを用いる。評価指標はYESを1、PARTIALを0.5として全テストケース数で割る、**部分点込みのテストケース加重スコア**。WebGen-Agentの報告では、Claude 3.5 Sonnetを使ったBolt.diyの26.4%に対し、WebGen-Agentは51.9%だった。Webサイトが丸ごと完成した割合や、全機能が成功した割合ではない。[R3](https://arxiv.org/html/2505.03733v2)、[R4](https://arxiv.org/html/2509.22644v1)

WebGen-AgentはICLR 2026の会議ポスターとして公式記録を確認した。数値と手法の確認に使った版はarXiv v1であり、閲覧した版と現在の出版状況を分けて記録している。[ICLR 2026公式記録](https://iclr.cc/virtual/2026/poster/10008256)

この比較はプロンプト1行の効果ではなく、描画・GUI評価・選択を含むシステム全体の比較である。論文はネットワーク条件や応答速度を対象外としており、Gurumojiの長時間処理や実保存の保証には追加検証が要る。[R4](https://arxiv.org/html/2509.22644v1)

採用するのは数字の予測ではなく、視覚、操作、実行エラーを別々の観測として反復に戻す方法である。

### 4.3 最新の時間短縮報告は慎重に読む

2026年9月22日提出のFigma MakeのRCTプレプリントは、デザイナー50名とPM50名、3つの定型課題を対象とし、完了した課題の所要時間について約20%の短縮を報告する。ただし著者はFigma所属、完了者に限る分析、固定順序の参照デザイン課題、品質は主に自己評価という制約がある。デザイナー群の総合効果は分析・記述で扱いが異なるため、単純な全員一律の短縮率を引用すべきではない。本番研究作業で同じ改善が得られる証拠とはしない。[R5](https://arxiv.org/html/2609.26725v1)
