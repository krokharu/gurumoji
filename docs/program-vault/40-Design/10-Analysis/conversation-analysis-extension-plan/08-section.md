---
note_type: reference-section
status: planned
feature: analysis
updated: 2026-09-16
tags:
- gurumoji/analysis
- gurumoji/design
- gurumoji/conversation
note_id: design-conversation-analysis-extension-section-08
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合：採否一覧
summary: 採否一覧。出典ノート「会話分析の拡張計画：既存分析とTransformer系推論の統合」の分割本文。
parent_note_id: design-conversation-analysis-extension
source_path: 40-Design/conversation-analysis-extension-plan.md
source_sha256: 53dc673b9392c2b03a1b6fd2a103f326b15690c0702376bab2e403dfda7f9bfb
source_body_lines:
- 152
- 197
split_on: '2026-10-11'
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合：採否一覧

親索引・状態・確認版：[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index]]。必要な本文だけを取得する。

## 採否一覧

| 区分 | 対象 | 根拠 |
| --- | --- | --- |
| 既存機能で対応 | 手動コード、手動相互作用リンク、質問候補、話者・時間集計、E5検索、感情の発話ID結合、固定保存 | 既に発話ID、根拠表示、CSV、stale、編集UIを持つ。ただし自動分類／一般応答推定ではない |
| 既存機能を拡張 | M01、M02、M09の確認表示、M10の原本／整文比較 | 手動分析・形態素・保存・UIを再利用でき、まずAの結合で価値を測れる |
| 新規追加 | 自動発話行為、対象別stance/NLI、一般応答リンク候補・関係分類、予測の版付き結果schema | いずれも現在の`METHODS`、API、CSV、UIには存在しない |
| PoC後に判断 | ゼロショットNLI、stance、Cross-Encoder再順位付け、教師あり／SetFit／追加学習 | 日本語会話・既存ラベル・実機コストでの利益が未測定 |
| 保留 | BERTopicによる未知話題発見、談話構造をAI要約の入力にするB、共同学習C | 既存テーマ／特徴語で足りる可能性があり、上流誤りの伝播を未測定 |
| 不採用（現段階） | 感情＝賛否、NLI＝同意／反対、相づち＝賛成、共起ネットワーク＝応答グラフ、外部検索情報をstance入力へ混入、全過去発話の総当たり、未確認AI予測を正解扱い | 各々がタスク定義、根拠、計算コスト、または評価の境界を壊す |

## 未確認事項

1. 実際に利用する日本語グループ会話の件数、話者・順序・本文の確認率、研究質問、対象の粒度、個人情報・外部送信の許可範囲。
2. 人手注釈者数、注釈ガイドの妥当性、クラス別件数、session単位の十分な分割数、不一致理由。
3. 日本語の発話行為、stance、応答関係に対する候補モデルの性能、否定・婉曲・相づち・省略への頑健性、閾値・校正、CPU/GPU実測。
4. E5-base／mDeBERTa／BERTopic／Sentence Transformers／SetFitの実装時の正確なrevision、ライセンス、依存競合、モデル容量、Windows／Colabでのメモリと中断・解放の挙動。
5. AnalysisStore成果物だけで人手確認履歴を十分に表現できるか。新DB契約が必要なら、[[40-Design/50-Governance/ai-development-rules|ai-development-rules]]と保存契約を読み、移行・後方互換・テストを別計画にする。

## 出典（2026-09-16確認）

### 事前調査の一次資料・公式資料

- [S01: ISO 24617-2 dialogue acts and application-specific annotations (2024)](https://aclanthology.org/2024.isa-1.15/)／[ISO standard, second edition (2020)](https://aclanthology.org/2020.lrec-1.69/) — 発話行為と用途固有注釈を分ける出発点。日本語会話での本計画ラベルの性能は未確認。
- [S02: Multi-Task Stance Detection with Sentiment and Stance Lexicons (2019)](https://aclanthology.org/D19-1657/) — 感情とstanceを別タスクとして扱う出発点。
- [S03: JGLUE / JNLI](https://github.com/yahoojapan/JGLUE#jnli) — 日本語NLIの形式確認用。会話・応答関係の正解データではない。
- [S04: Transformers ZeroShotClassificationPipeline](https://huggingface.co/docs/transformers/en/main_classes/pipelines#transformers.ZeroShotClassificationPipeline) — NLI型候補ラベル・テンプレートの公式API。実装時の版はrequirementsと照合する。
- [S05: scikit-learn sparse text classification example](https://scikit-learn.org/stable/auto_examples/text/plot_document_classification_20newsgroups.html) — TF-IDF＋線形分類器を比較に含める根拠。
- [S06: Dialogue Discourse Parsing as Generation (2024)](https://aclanthology.org/2024.sigdial-1.1/)／[S07: Domain Integration for Multi-Party Dialogue Discourse Parsing (2021)](https://aclanthology.org/2021.codi-main.11/) — 談話構造と領域適応の調査入口。
- [S08: Sentence Transformers Retrieve & Re-Rank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) — bi-encoder候補検索とCross-Encoder再順位付けを分ける根拠。応答先判定器そのものではない。
- [S09: BERTopic Algorithm](https://maartengr.github.io/BERTopic/algorithm/algorithm.html)、[Embeddings](https://maartengr.github.io/BERTopic/getting_started/embeddings/embeddings.html)、[Vectorizers](https://maartengr.github.io/BERTopic/getting_started/vectorizers/vectorizers.html) — 構成要素の公式資料。
- [S10: Topics per Class](https://maartengr.github.io/BERTopic/getting_started/topicsperclass/topicsperclass.html)／[Topics over Time](https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html) — 共通topicのクラス／時間比較の候補。
- [S11: BERTopic Manual Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/manual/manual.html) — 既存ラベルを渡し、埋め込み・次元削減・クラスタリングを飛ばしてc-TF-IDF表現を作る公式資料。未知話題発見と区別する。
- [S12: BERTopic Topic Distributions](https://maartengr.github.io/BERTopic/getting_started/distribution/distribution.html) — 文書内の複数topic分布の候補。集計単位の二重計上に注意。
- [S13: Transformers Text Classification](https://huggingface.co/docs/transformers/en/tasks/sequence_classification)／[S14: SetFit conceptual guide](https://huggingface.co/docs/setfit/en/conceptual_guides/setfit) — 追加学習候補。必要件数・性能は未計測。
- [S15: multilingual-e5-base model card](https://huggingface.co/intfloat/multilingual-e5-base) — MIT、768次元、接頭辞、512 token上限を確認。検索ベンチマークを会話分析へ一般化しない。
- [S16: mDeBERTa-v3-base-mnli-xnli model card](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) — MIT、XNLI/MNLI由来の多言語NLI候補を確認。日本語会話の直接評価は未確認。
- [S17: scikit-learn Cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html)／[Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) — group分割と未校正スコアを確率扱いしないための公式資料。
- [S18: Leveraging Discourse Structure for Extractive Meeting Summarization (2024)](https://arxiv.org/abs/2405.11055) — 談話構造と会議要約の調査入口。英語研究を本システムの効果保証としない。
- [S19: Is External Information Useful for Stance Detection with LLMs? (2025)](https://aclanthology.org/2025.findings-acl.764/) — 外部情報のstance入力を既定にしない根拠。

### プロジェクト内の関連資料

- [[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]] — 現行E5＋K-meansの契約、限界、テーマ分析との区別。
- [[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]、[[30-Data/30-Transcript/transcript-preparation-v1|transcript-preparation-v1]]、[[40-Design/50-Governance/method-rules/00-Index|method-rules]] — 保存、版、根拠、登録の現行契約。
- [[20-Modules/10-Inventory/module-map/00-Index|module-map]]、[[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]] — 実装・UIの入口。
