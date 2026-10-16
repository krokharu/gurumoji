---
note_type: reference-section
status: planned
feature: analysis
updated: 2026-09-16
tags:
- gurumoji/analysis
- gurumoji/design
- gurumoji/conversation
note_id: design-conversation-analysis-extension-section-07
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合：実装フェーズとチケット案
summary: 実装フェーズとチケット案。出典ノート「会話分析の拡張計画：既存分析とTransformer系推論の統合」の分割本文。
parent_note_id: design-conversation-analysis-extension
source_path: 40-Design/conversation-analysis-extension-plan.md
source_sha256: 53dc673b9392c2b03a1b6fd2a103f326b15690c0702376bab2e403dfda7f9bfb
source_body_lines:
- 138
- 151
split_on: '2026-10-11'
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合：実装フェーズとチケット案

親索引・状態・確認版：[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index]]。必要な本文だけを取得する。

## 実装フェーズとチケット案

| Phase | 目的・優先度 | 想定変更対象と再利用 | 入出力・評価・完了条件 | 取りやめ条件 |
| --- | --- | --- | --- | --- |
| 0 | **最優先**。研究質問、対象、注釈ガイド、session分割、既存データ品質を確定 | `transcript_preparation`、手動コード／リンクUI、`prepared_turns`を読む。コード変更なしでも開始可能 | ラベル・保留・境界例・正解作成手順、評価用会話の分割、原本／整文条件を記録。手法ごとの適用条件を満たす | 話者・順序・本文確認が必要水準に達せず、正解作成者も確保できない |
| 1 | **最優先**。最小共通契約と固定保存の設計 | `analysis_store.py`、`analysis_method_registry.py`、`app.py:archive_group_analysis`、[[40-Design/50-Governance/method-rules/00-Index\|method-rules]] | `utterance_labels`、`stance`、`nli`、`relations`、`documents`のCSV／JSON schema、fingerprint、stale、予測／確認状態、根拠IDの検証を定義。架空データの空・削除先・本文変更を検証 | 既存AnalysisStoreだけで版・確認履歴を安全に保持できないと判明し、保存契約の追加設計が未承認 |
| 2 | **最高の最初の実装単位**。M01の低コスト分類とA結合 | 新しい手法アダプター、既存`research_analysis`、`analysis-content.js`／`app.js`の発話・CSV表示。規則型と既存質問候補を再利用 | `dialogue_act`の規則ベースライン、保留、手動確認、ラベル別語彙／コード表。既存のみ／規則のみ／確認後の評価を完了 | 人手評価で既存質問候補／手動コードより使える根拠表示・分類利益がない |
| 3 | M05、明示対象のstance、NLIの限定PoC | `transformer_analysis.semantic_search`、手動relation、話者・時刻・質問候補、既存テーマ | Top-K候補生成と手動確認を分離。明示対象stanceはrelationなしで評価し、NLIは方向と三値を保存 | 候補Recall@Kが低い、対象特定の誤りで賛否表示が危険、またはNLIが人手判断を上回らない |
| 4 | M08/M04。既存分類を説明するBERTopicと未知話題探索を分けて比較 | 現行E5、形態素、コード、topic結果。BERTopicは新規任意依存として隔離 | Manual Topic Modeling対既存特徴語、次に文書単位別の発見的PoC。発話ID対応、外れ値、安定性、解釈可能性を評価 | 既存K-means／特徴語より説明可能性が上がらない、少量会話で不安定、依存・実行コストが利益を上回る |
| 5 | M09。教師あり／追加学習を比較 | scikit-learn、固定E5、必要時Transformers／SetFit。既存編集・確認UIを再利用 | session分割で線形・固定embedding・追加学習を同条件比較。人手確定ラベルの来歴とモデルrevisionを保存 | 軽量方式を越えない、ラベル定義が不安定、未知セッションに汎化しない、運用負荷が大きい |
| 6 | M06/M07を含む統合表示・要約・回帰 | method overview、根拠表示、CSV／Excel、ResearchVault、ブラウザーテスト | 予測／確定・stale・失敗表示、根拠追跡、少数意見・帰属の回帰評価、保存／再試行／exportを確認 | 確定していない構造を要約の事実として表示するリスクを解消できない |

独立に進められるのは、Phase 0の注釈設計、Phase 1の保存schema設計、Phase 2の規則ベースライン、Phase 4の既存ラベル説明の机上比較である。Phase 3の一般的な応答リンク、Phase 5の学習、Phase 6の要約入力は、それぞれの人手評価を通った結果だけに依存する。
