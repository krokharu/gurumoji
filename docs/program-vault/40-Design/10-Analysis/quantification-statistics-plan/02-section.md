---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-02
title: 発話の数値化とjamovi型統計の自動実行計画：1. 要点
summary: 1. 要点。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 24
- 50
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：1. 要点

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 1. 要点

1. 自動化するのは「数値化 → 変数カタログ → 分析用データセット → 統計解析計画 → 検定の選択と実行 → 固定保存とjamovi再現ファイル」の流れ。この統計処理の中ではLLMを変数生成に使い、検定の選択、統計量、報告文の数値はコードが決定的に作る。別の分析タスクとして行うLLMの根拠付き見解・意味分析・計画提案は、再編計画の分析担当／計画担当の契約で扱う。
2. 数値化は、ルール辞書と会話構造、Transformer埋め込みと軽量分類器、LLM、人手コードを組み合わせる。LLMが出した帰納的なコード案は、研究者がコードブックに採用するまで変数にしない。
3. AI由来の変数は、人手の検証サンプルで一致度のゲートを通るまで、確認的な検定に使わない。
4. 群比較の既定は、話者単位へ集約した表で行う。発話単位の分析には、話者でクラスター化したGEEやクラスター頑健標準誤差を付ける。
5. 本計画で追加するAIによる変数生成は「AIで数値化」から明示的に実行する。文字起こしや統計の実行に数値化を混ぜず、固定データの統計はAIを呼ばず何度でも再実行できる。既存のAI仕上げ・見解生成や、別タスクのLLM分析まで禁止する意味ではない。
6. 最初に作るのは、AIを使わない統計エンジン（Phase 1a）。発話時間、手動コード、質問候補、感情ラベル、相づち、事前アンケートといった既存の変数だけで使える。

## 2. 現状

| 項目 | 現状 | 根拠 |
| --- | --- | --- |
| 検定 | 発話単位で、一元配置分散分析（等分散を仮定）、Kruskal–Wallis、Pearsonのカイ二乗、Pearson／Spearman相関。t検定、Welch補正、事後検定、Fisherの正確検定、多重比較の補正はない | `research_analysis._statistics_analysis` |
| 数値変数 | 発話時間、文字数、形態素数、内容語数、語彙多様性、発話速度（文字/分）の6つ | `research_analysis.NUMERIC_VARIABLES` |
| 統計の比較軸 | 話者または役割だけ。参加バランスの比較軸は、事前アンケート項目（`attribute:<項目>`）まで選べる | `statistics_group_by`（`research_analysis`）、`group_by`（`app.normalize_analysis_group_by`、`group_analysis_for_row`） |
| 重複 | カイ二乗検定が2か所にある。事前アンケートの相関はブラウザー側で別に計算している | `transformer_analysis._backchannel_test`、`static/app.js:speakerSurveyCorrelation` |
| 複数会話 | 2〜8件のインタビューを記述的に比較する。発話を独立標本として検定しない方針をdocstringに明記 | `app.build_interview_comparison` |
| 新規作成フォーム | `finish_in_obsidian`、`ai_provider`（アプリ内AI仕上げ）、`emotion_analysis`がある。文字起こしジョブの中にAIの経路がある（ADR-010） | `templates/index.html` |
| LLM | OpenAI、Gemini、LM Studio（ColabではOllama）へ、JSON Schemaの厳格な出力を要求する。実行中だけの参照番号（`E0001`）、根拠IDの`enum`、検証失敗時の1回の再試行がある。既存のAI見解は話者名（`speaker_name`）も送る | `app.call_ai_json`、`analysis_insights.create_ai_insights`、`ai_http_worker.py` |
| Transformer | `intfloat/multilingual-e5-small`（384次元）の埋め込みとK-means。ベクトルを結果に保存する | `transformer_analysis.encode_texts`、`_pack_vectors` |
| 人手コード | コードブック（定義・含める例・除外する例）。1発話に複数コード。AI候補と確定コードを区別する規約がある | [[40-Design/50-Governance/method-rules/00-Index\|method-rules]]の`qualitative_coding` |
| 分析方針の表 | `analysis_plan`（section、item、status、value、role、data_sufficiency、reason、limitation） | `app.build_focus_group_analysis_plan` |
| 開発環境 | `.venv`にSciPy 1.18.1、scikit-learn 1.9.1、pandas 3.0.3、torch 2.8（CUDA 12.8）、transformers 4.57.6。statsmodels、R、jamovi本体は未導入 | 2026-09-15に確認 |

SciPy 1.18.1だけで使える関数：`ttest_ind(equal_var=False)`（Welch）、`f_oneway(equal_var=False)`（Welchの分散分析）、`tukey_hsd(equal_var=False)`（Games–Howell）、`mannwhitneyu`、`ttest_rel`、`wilcoxon`、`friedmanchisquare`、`chi2_contingency(method=…)`（並べ替え・モンテカルロ）、`fisher_exact`（2×2。それ以外は`method`を指定）、`binomtest`、`chisquare`、`kendalltau`、`contingency.odds_ratio`、`false_discovery_control`（Benjamini–Hochberg）、`permutation_test`、`bootstrap`。
