---
note_id: analysis-peer-reviewed-references
note_type: bibliography
title: 分析手法の査読文献一覧
status: current
verified: 2026-09-14
tags:
  - gurumoji/analysis
  - gurumoji/bibliography
---

# 分析手法の査読文献一覧

以下はこの知識ベースで使う基礎文献。リンク先は出版社、学会の公式論文アーカイブ、またはDOIとし、2026-09-14に書誌情報を確認した。実装固有のライブラリ文書やモデル配布ページは別扱いである。

## テキスト・文脈

- **[Salton & Buckley 1988](https://doi.org/10.1016/0306-4573(88)90021-0)**. *Term-weighting approaches in automatic text retrieval*. Information Processing & Management, 24(5), 513–523. TF–IDFの重み付け。
- **[Kilgarriff 2001](https://kilgarriff.co.uk/Publications/2001-K-CompCorpIJCL.pdf)**. *Comparing Corpora*. International Journal of Corpus Linguistics, 6(1), 97–133. コーパス比較・頻度差の検定的解釈の注意。
- **[Callon et al. 1983](https://doi.org/10.1177/053901883022002003)**. *From translations to problematic networks: An introduction to co-word analysis*. Social Science Information, 22(2), 191–235. 共語／共起ネットワーク。
- **[Kudo, Yamamoto & Matsumoto 2004](https://aclanthology.org/W04-3230/)**. *Applying Conditional Random Fields to Japanese Morphological Analysis*. EMNLP 2004, 230–237. 日本語の形態素境界・品詞。
- **[Omura & Asahara 2018](https://aclanthology.org/W18-6014/)**. *UD-Japanese BCCWJ*. UDW 2018, 117–125. 日本語UD資源。
- **[Nivre et al. 2020](https://aclanthology.org/2020.lrec-1.497/)**. *Universal Dependencies v2: An Evergrowing Multilingual Treebank Collection*. LREC 2020, 4034–4043. UDの形態・係り受け層。

## 意味・音声

- **[Reimers & Gurevych 2019](https://aclanthology.org/D19-1410/)**. *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks*. EMNLP-IJCNLP 2019, 3982–3992. 文埋め込みによる類似度。
- **[Lloyd 1982](https://doi.org/10.1109/TIT.1982.1056489)**. *Least Squares Quantization in PCM*. IEEE Transactions on Information Theory, 28(2), 129–137. Lloyd型k-means反復の基礎。
- **[Rousseeuw 1987](https://doi.org/10.1016/0377-0427(87)90125-7)**. *Silhouettes: A Graphical Aid to the Interpretation and Validation of Cluster Analysis*. Journal of Computational and Applied Mathematics, 20, 53–65. silhouette係数。
- **[Baevski et al. 2020](https://proceedings.neurips.cc/paper/2020/hash/92d1e1eb1cd6f9fba3227870bb6d7f07-Abstract.html)**. *wav2vec 2.0*. NeurIPS 2020. 自己教師あり音声表現。
- **[Hsu et al. 2021](https://doi.org/10.1109/TASLP.2021.3122291)**. *HuBERT: Self-Supervised Speech Representation Learning by Masked Prediction of Hidden Units*. IEEE/ACM TASLP, 29, 3451–3460. HuBERT。
- **[Kosaka et al. 2023](https://doi.org/10.1587/transinf.2023HCP0010)**. *Simultaneous Adaptation of Acoustic and Language Models for Emotional Speech Recognition Using Tweet Data*. IEICE Transactions on Information and Systems. JTESを用いた日本語感情音声認識。

## 会話・質的分析・生成AI

- **[Stephan & Mishler 1952](https://doi.org/10.2307/2088227)**. *The Distribution of Participation in Small Groups: An Exponential Approximation*. American Sociological Review, 17(5), 598–608. 小集団における参加分布。
- **[Sacks, Schegloff & Jefferson 1974](https://doi.org/10.2307/412243)**. *A Simplest Systematics for the Organization of Turn-Taking for Conversation*. Language, 50(4), 696–735. 会話のターン交替。
- **[Heldner & Edlund 2010](https://doi.org/10.1016/j.wocn.2010.08.002)**. *Pauses, gaps and overlaps in conversations*. Journal of Phonetics, 38(4), 555–568. ポーズ・間・重なりの分布と閾値の問題。
- **[Braun & Clarke 2006](https://doi.org/10.1191/1478088706qp063oa)**. *Using thematic analysis in psychology*. Qualitative Research in Psychology, 3(2), 77–101. テーマ分析と研究者の解釈手順。
- **[Hsieh & Shannon 2005](https://doi.org/10.1177/1049732305276687)**. *Three Approaches to Qualitative Content Analysis*. Qualitative Health Research, 15(9), 1277–1288. 質的内容分析における慣習的・有向的・要約的アプローチと、コードの出所の違い。
- **[Gale et al. 2013](https://doi.org/10.1186/1471-2288-13-117)**. *Using the framework method for the analysis of qualitative data in multi-disciplinary health research*. BMC Medical Research Methodology, 13, 117. フレームワーク分析の行列化と、元データへ戻る手順。
- **[Kitzinger 1994](https://doi.org/10.1111/1467-9566.ep11347023)**. *The methodology of focus groups: the importance of interaction between research participants*. Sociology of Health & Illness, 16(1), 103–121. フォーカスグループで参加者間の相互作用を明示的に扱う必要性。
- **[Gilardi, Alizadeh & Kubli 2023](https://doi.org/10.1073/pnas.2305016120)**. *ChatGPT outperforms crowd workers for text-annotation tasks*. PNAS, 120(30), e2305016120. LLMを補助的なテキスト注釈に使う際の評価例。

## 統計

- **[Cochran 1952](https://doi.org/10.1214/aoms/1177729380)**. *The χ² Test of Goodness of Fit*. Annals of Mathematical Statistics, 23(3), 315–345. カイ二乗と小さい期待度数の留意。
- **[Kruskal & Wallis 1952](https://doi.org/10.1080/01621459.1952.10483441)**. *Use of Ranks in One-Criterion Variance Analysis*. Journal of the American Statistical Association, 47(260), 583–621. Kruskal–Wallis検定。
- **[Spearman 1904](https://doi.org/10.2307/1412159)**. *The Proof and Measurement of Association between Two Things*. American Journal of Psychology, 15(1), 72–101. 順位相関。

> 注意: 論文が方法の理論・評価を支持しても、Gurumojiのデータ、話者分離、文字起こし、設定、研究デザインで結果が妥当であることを自動的に保証しない。
