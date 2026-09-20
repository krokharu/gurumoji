---
note_id: analysis-method-selection-guide
note_type: knowledge-index
title: 分析手法と専門家の選び方
status: current
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/expert
---

# 分析手法と専門家の選び方

研究の問いとデータから、使う専門家を選ぶための整理（[整理]）。手法の選択は研究者が行い、アプリは自動で確定しない。各行の根拠は、リンク先の専門家定義と文献ノートにある。

## 最初に確認すること

1. 研究質問（または研究目的）が書かれているか。未記入なら、どの手法も「暫定」にとどまる。
2. 分析単位は発話（`turn`）でよいか。意味単位やケース（人・グループ）を単位にする手法では、研究者の作業で対応する。
3. 逐語録の準備状態（本文、区切り、話者、順序の確認）。相互作用や話者の比較を扱うなら、話者と順序の確認が前提になる（[[50-Analysis-Methods/08-Common-Knowledge/03-Group-Interview-Data]]）。

## 問いと専門家の対応

| 研究の問い・目的 | 主な専門家 | 補助に使える専門家 | 答えにくいこと・移す先 |
| --- | --- | --- | --- |
| 語られた内容をカテゴリーに体系的に整理したい（先行研究・理論の枠組みがある／ない） | [[50-Analysis-Methods/10-Experts/qualitative-content-analysis/01-Expert\|質的内容分析]] | 相互作用分析、計量テキスト分析 | 問いが非常に開かれていて全体的な解釈を求める場合はテーマ分析へ |
| 経験や考え方に共通する意味のパターンを解釈したい | [[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert\|テーマ分析]] | 相互作用分析 | テーマの頻度や代表性を示したい場合は、この手法の目的と合わない |
| 話者やグループなどのケースとテーマを行列で比べたい（共通の話題を扱う半構造化面接） | [[50-Analysis-Methods/10-Experts/framework-method/01-Expert\|フレームワーク法]] | 会話間比較 | 生活史や診療場面の会話など、ケース×テーマで扱うのが適さないデータ |
| 1つのケースや少量のデータから、段階を明示して理論記述まで行いたい | [[50-Analysis-Methods/10-Experts/scat/01-Expert\|SCAT]] | — | 大量のデータの全体像の把握 |
| 認識や行為が変化するプロセスを説明したい（ヒューマンサービス領域など） | [[50-Analysis-Methods/10-Experts/m-gta/01-Expert\|M-GTA]] | — | 人数や頻度による結果の提示 |
| 雑多な意見をボトムアップにまとめ、構造を図解したい | [[50-Analysis-Methods/10-Experts/kj-method/01-Expert\|KJ法]] | — | 事前のカテゴリーに当てはめる分類（質的内容分析の演繹的適用へ） |
| 語の偏りや共起から読むべき箇所を探す、明確な比較の枠組みで語の違いを見る | [[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert\|計量テキスト分析]] | 日本語の前処理 | 語の頻度から意見の重要性や支持人数を示すこと |
| その場で意見がどう形成され、同意・不同意がどう展開したか | [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert\|相互作用分析]] | 会話の時間構造、参加バランス | 話者と順序が未確認の逐語録での応答関係の確定 |
| 誰がどれだけ話したか、発言の偏り | [[50-Analysis-Methods/10-Experts/participation-balance/01-Expert\|参加バランス]] | — | 影響力、満足度、議論の質 |
| 話者交替、間、重なりの時間的な構造 | [[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert\|会話の時間構造]] | — | 沈黙の意味（同意・熟考）、遮りや対立の判定 |
| 数値の分布、群の比較、変数の関連を探索的に見る | [[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert\|記述統計]]、[[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|群間比較]]、[[50-Analysis-Methods/10-Experts/correlation/01-Expert\|相関]] | — | 因果や母集団への一般化 |
| 意味の近い発話のまとまりを探索する | [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert\|埋め込みによるテーマ探索]] | 計量テキスト分析 | テーマ分析のテーマの確定 |
| 音声モデルによる感情ラベルの分布を見る | [[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert\|音声感情推定]] | — | 本人が経験した感情の判定 |
| 複数回のインタビューを並べて比べる | [[50-Analysis-Methods/10-Experts/cross-session-comparison/01-Expert\|会話間比較]] | フレームワーク法 | 少数の会話からの推測統計による一般化 |

## 混同しやすい組み合わせ

- 「テーマ分析」と「Transformerテーマ分析」：名前が似ているが別の手法。埋め込みのクラスタは、テーマ分析のテーマの代わりにならない（[[50-Analysis-Methods/20-Literature/LIT-braun-clarke-2006-thematic]]、既存ノート [[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]]）。
- KJ法と類似度によるクラスタリング：KJ法のラベル集めは研究者がボトムアップで行う作業で、自動分類で置き換えない（[[50-Analysis-Methods/20-Literature/LIT-tanaka-kj-quick-manual]]）。
- 要約的な質的内容分析と計量テキスト分析：どちらも数えるが、前者は数えた後に文脈を解釈する質的内容分析の一形態で、後者は計量的分析と質的解釈を往復する方法として位置づけられている（[[50-Analysis-Methods/20-Literature/LIT-hsieh-shannon-2005-qca]]、[[50-Analysis-Methods/20-Literature/LIT-higuchi-2017-khcoder]]）。
- M-GTAと他のグラウンデッド・セオリー：M-GTAはデータの切片化をしない（[[50-Analysis-Methods/20-Literature/RES-mgta-society-official]]）。
- 内容の分析と相互作用の分析：何が語られたかと、どう応答し合ったかを別の表で扱い、同じ発話IDで照合する。

## 複数の専門家を使うとき

- 主の専門家を1人にし、補助の専門家はそれぞれの前提と出力を保ったまま並べる。
- 専門家どうしで見解や前提が食い違う場合は、統合せずに両方を示し、研究者が判断する。
- アプリは専門家どうしの合議や独立したレビューを行わない。行っていない合議を「確認済み」と表示しない。
