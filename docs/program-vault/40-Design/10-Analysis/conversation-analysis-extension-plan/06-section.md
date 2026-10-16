---
note_type: reference-section
status: planned
feature: analysis
updated: 2026-09-16
tags:
- gurumoji/analysis
- gurumoji/design
- gurumoji/conversation
note_id: design-conversation-analysis-extension-section-06
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合：教師データ・評価・誤り伝播
summary: 教師データ・評価・誤り伝播。出典ノート「会話分析の拡張計画：既存分析とTransformer系推論の統合」の分割本文。
parent_note_id: design-conversation-analysis-extension
source_path: 40-Design/conversation-analysis-extension-plan.md
source_sha256: 53dc673b9392c2b03a1b6fd2a103f326b15690c0702376bab2e403dfda7f9bfb
source_body_lines:
- 117
- 137
split_on: '2026-10-11'
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合：教師データ・評価・誤り伝播

親索引・状態・確認版：[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index]]。必要な本文だけを取得する。

## 教師データ・評価・誤り伝播

### 評価セットの作り方

- 実装前に、研究質問・対象・ラベル定義・判断不能・境界例・複数ラベルを記した短い注釈ガイドを版管理する。質問、相づち、婉曲な反対、条件付き意見、複数対象、自己訂正、同時発話、文字起こし誤りを含める。
- Train／Validation／Testは先に`session_id`等のグループで分ける。同じ会話の前後文脈、応答ペア、重複文書が分割をまたがないようにする。GroupKFold等は候補だが、分割可能な会話数を実測してから採用する [S17]。
- 正解は人手確認済みのラベルとリンクだけにする。AIの未確認予測は疑似ラベルとして明示し、独立評価データに混ぜない。可能なら複数人で不一致理由を記録する。

### 比較実験

| 対象 | 必須ベースライン | 主指標 | 失敗を隠さない指標 |
| --- | --- | --- | --- |
| 発話行為／内容分類 | 既存質問正規表現、手動コード、規則、TF-IDF＋線形分類器、必要時NLIゼロショット | Macro F1、クラス別F1、混同行列。多ラベルはMicro F1も | 保留率、誤りの種類、ラベル定義／文脈条件別の差 |
| stance／NLI | 明示対象だけの規則、対象未解決の保留 | 対象特定の正しさ、stance F1、NLIの方向別／三値精度 | 対象不明、条件付き・混合、neutralと低確信の混同、外部情報あり／なしの差 |
| 応答関係 | 直前発話、時間近傍、手動リンク | 候補Recall@K、最終link Precision/Recall/F1、関係分類F1 | 応答先なし、複数応答、相づち、自己補足、候補外正解の割合 |
| BERTopic／既存ラベル説明 | 現行K-meansテーマ、既存の特徴語・手動コード | 代表例の人手解釈可能性、必要時Coherence／Diversityの計算法を明示 | 外れ値率、文書単位・前処理・seed変更への安定性、話者横断文書の誤帰属 |
| 統合／要約 | 既存のみ、新規単体、Aの結合 | 根拠発話の正確さ、意見帰属、少数意見保持、元発話への到達手間 | 誤った賛否集計、上流が人手正解の場合とAI推定の場合の差 |
| 運用 | CPU／GPUの既存実行経路 | 処理時間、RAM/VRAM、追加API費用、再実行時間、キャッシュ再利用率 | モデル未導入／CPUのみ／メモリ不足／中断／staleの挙動 |

効果は同じ評価データで「既存のみ／新規のみ／組合せ」を比較して初めて判断する。閾値、必要ラベル数、速度、VRAM、精度の数値は本計画では仮定しない。採用閾値を置く場合は、研究目的に対する許容誤りとベースライン比較から事前に決め、探索中のTestで調整しない。
