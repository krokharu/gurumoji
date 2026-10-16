---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-13
title: 配布用専門家の知識・プロンプト制作計画：P4 評価記録と決定的な受入gate
summary: P4 評価記録と決定的な受入gate。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 504
- 513
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：P4 評価記録と決定的な受入gate

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### P4 評価記録と決定的な受入gate

- `src/gurumoji/knowledge_builder/evaluation.py`を追加。Evaluationはexpert・Pack root・suite/rubric・model config・prompt template・renderer・rendered requestのhash、repeat index、opaque case/item ID、category別passed/total、critical/blocking violationを束ね、各expert・各repeatで個別判定する。repeatは1/2のみとし、全体平均で不合格を救済するAPIは作らない。
- gateは計画の最終40問（内容理解15・適用判断15・判断保留10）を固定し、知識checklist item IDをhashと通過IDに結びつける。根拠支持は重大Claim全件と一般Claimから`min(60, population)`件を分けて記録し、母数hash・審査ID・不支持IDを照合する。適用は14/15以上かつ重大誤適用0、保留10/10、根拠支持95%以上かつ重大不支持0、知識範囲90%以上・必須項目100%、整理95%以上、引用・構造・プライバシーは40/40を要求。critical/blocking違反は点数で相殺しない。
- `validate_repeat_pair()`は同一expert・Pack・suite・rubric・model config・prompt/renderer・要求集合でrepeat 1/2の両方がpassし、run/evaluation IDが異なることを確認する。結果は平均化しない。
- Suite本文、回答、promptや解答キーはEvaluation/JobStoreに記録しない。case/item IDと計測値のみを保持する。モデル設定はrevision・量子化・context・sampling設定を正規化してhash化する。
- Sourceにはstructured HTTPS `license_url`を保持。export routeでは著者、paper年、license URL、明示的改変注記をSource側で検査し、不足時にfail-closed。promptは記録された注記のみを使い、欠損から翻案事実を生成しない。
- 検証: Evaluation 8件、contracts/JobStore 17件、context 8件、Pack builder 7件成功。対象moduleの`py_compile`と`git diff --check`成功。Sol read-only再監修で、重大/一般Claim母集団、item checklist、40件の全件指標、2 repeat gateに算術上のブロッカーなし。sealed suite/実応答を評価器自体が照合しない制限は明記済み。
- これは評価結果の形式・件数・hashと閾値/2 repeat組の検査であり、実際のPack・sealed suite・モデル出力を実行して採点するrunnerではない。意味的な原典支持も自動採点しない。原文spanを隔離した審査suite、実問40件/専門家、独立した意味審査、2 repeat実走は未実施。
