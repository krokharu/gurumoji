---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-11
title: 発話の数値化とjamovi型統計の自動実行計画：13. Phase 0で決める既定値
summary: 13. Phase 0で決める既定値。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 334
- 394
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：13. Phase 0で決める既定値

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 13. Phase 0で決める既定値

1. 検証サンプルの件数と層の設計（αの信頼区間の幅から決める）。
2. 最小N、補正の族、有意水準の既定値。
3. AI数値化の1回の上限トークンと、試行の件数。
4. 会話をまたいで参加者を同一とみなす条件（話者台帳の参加者コードの確認状態）。
5. `LICENSE`の著作権者名。
6. 既存のAI見解が話者名を送っている点を、ADR-111に揃えるか。

## 14. 採用しない案

- LLMに検定の選択、実行、p値の記述まで任せる。数値の誤生成、再現性の欠如、結果を見てからの分析の選び直しを防げない。
- 文字起こしジョブの中や、統計の実行・保存のたびにLLMを呼ぶ。利用者が意図しないトークンを使う。
- 話者の氏名・仮名・所属をLLMへ送る。
- 発話を独立標本とした検定を、群比較の既定にする。
- 正規性・等分散性の検定結果で、使う検定を自動的に切り替える。
- AIのラベルを人のコードの列へ自動で書き込む。
- 検証していないAIの変数で、確認的な結論を出す。
- GPL・AGPLのライブラリをimportする。
- jamoviの`.omv`を自前で書き出す。
- `interview_comparison`に多数の会話の推測統計を詰め込む。
- 統計用の画面を別に新設する。
- 人格パネルの議論をそのまま決定とする。決定はADRに記録し、利用者の決定を覆さない。

## 15. 文献

2026-09-15にCrossref、出版社、学会の論文ページで書誌情報を確認した。実装時に採用した文献は[[50-Analysis-Methods/99-Peer-Reviewed-References]]へ移す。既存の一覧にあるGilardi et al. 2023（LLMによる注釈）とReimers & Gurevych 2019（文埋め込み）も使う。

### 検定の選択・補正・入れ子

- **[Delacre, Lakens & Leys 2017](https://doi.org/10.5334/irsp.82)**. *Why Psychologists Should by Default Use Welch's t-test Instead of Student's t-test*. International Review of Social Psychology, 30(1), 92–101.
- **[Rasch, Kubinger & Moder 2011](https://doi.org/10.1007/s00362-009-0224-x)**. *The two-sample t test: pre-testing its assumptions does not pay off*. Statistical Papers, 52(1), 219–231.
- **[Games & Howell 1976](https://doi.org/10.3102/10769986001002113)**. *Pairwise Multiple Comparison Procedures with Unequal N's and/or Variances: A Monte Carlo Study*. Journal of Educational Statistics, 1(2), 113–125.
- **[Cochran 1954](https://doi.org/10.2307/3001616)**. *Some Methods for Strengthening the Common χ² Tests*. Biometrics, 10(4), 417–451.
- **[Holm 1979](https://www.jstor.org/stable/4615733)**. *A Simple Sequentially Rejective Multiple Test Procedure*. Scandinavian Journal of Statistics, 6(2), 65–70.
- **[Benjamini & Hochberg 1995](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)**. *Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing*. Journal of the Royal Statistical Society Series B, 57(1), 289–300.
- **[Aarts et al. 2014](https://doi.org/10.1038/nn.3648)**. *A solution to dependency: using multilevel analysis to accommodate nested data*. Nature Neuroscience, 17(4), 491–496.
- **[Jaeger 2008](https://doi.org/10.1016/j.jml.2007.11.007)**. *Categorical data analysis: Away from ANOVAs (transformation or not) and towards logit mixed models*. Journal of Memory and Language, 59(4), 434–446.

### コーディングの信頼性・自動測定の妥当性

- **[Krippendorff 2004](https://doi.org/10.1111/j.1468-2958.2004.tb00738.x)**. *Reliability in Content Analysis: Some Common Misconceptions and Recommendations*. Human Communication Research, 30(3), 411–433.
- **[Hayes & Krippendorff 2007](https://doi.org/10.1080/19312450709336664)**. *Answering the Call for a Standard Reliability Measure for Coding Data*. Communication Methods and Measures, 1(1), 77–89.
- **[Grimmer & Stewart 2013](https://doi.org/10.1093/pan/mps028)**. *Text as Data: The Promise and Pitfalls of Automatic Content Analysis Methods for Political Texts*. Political Analysis, 21(3), 267–297.
- **[Ziems et al. 2024](https://doi.org/10.1162/coli_a_00502)**. *Can Large Language Models Transform Computational Social Science?* Computational Linguistics, 50(1), 237–291.
- **[TeBlunthuis, Hase & Chan 2024](https://doi.org/10.1080/19312458.2023.2293713)**. *Misclassification in Automated Content Analysis Causes Bias in Regression. Can We Fix It? Yes We Can!* Communication Methods and Measures, 18(3), 278–299.
- **[Egami et al. 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d862f7f5445255090de13b825b880d59-Abstract-Conference.html)**. *Using Imperfect Surrogates for Downstream Inference: Design-based Supervised Learning for Social Science Applications of Large Language Models*. Advances in Neural Information Processing Systems 36 (NeurIPS 2023).
- **[Angelopoulos et al. 2023](https://doi.org/10.1126/science.adi6000)**. *Prediction-powered inference*. Science, 382(6671), 669–674.

### LLM・Transformer以外の数値化

- **[Igarashi, Okuda & Sasahara 2022](https://doi.org/10.3389/fpsyg.2022.841534)**. *Development of the Japanese Version of the Linguistic Inquiry and Word Count Dictionary 2015*. Frontiers in Psychology, 13, 841534.
- **[Roberts et al. 2014](https://doi.org/10.1111/ajps.12103)**. *Structural Topic Models for Open-Ended Survey Responses*. American Journal of Political Science, 58(4), 1064–1082.
- **[Eyben et al. 2016](https://doi.org/10.1109/TAFFC.2015.2457417)**. *The Geneva Minimalistic Acoustic Parameter Set (GeMAPS) for Voice Research and Affective Computing*. IEEE Transactions on Affective Computing, 7(2), 190–202.
- **[Jadoul, Thompson & de Boer 2018](https://doi.org/10.1016/j.wocn.2018.07.001)**. *Introducing Parselmouth: A Python interface to Praat*. Journal of Phonetics, 71, 1–15.

実装確認用（査読文献ではない）：[jmv（CRAN）](https://cran.r-project.org/web/packages/jmv/)、[statsmodels（PyPI）](https://pypi.org/project/statsmodels/)、[SciPyの統計関数](https://docs.scipy.org/doc/scipy/reference/stats.html)。

> 注意：文献が方法の妥当性を示しても、Gurumojiのデータ、話者分離、文字起こし、設定、研究デザインで結果が妥当であることは保証しない。

関連：[[40-Design/50-Governance/method-rules/00-Index|method-rules]]、[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]、[[50-Analysis-Methods/03-Statistics/00-Index]]、[[40-Design/50-Governance/ai-development-rules|ai-development-rules]]、[[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]]。
