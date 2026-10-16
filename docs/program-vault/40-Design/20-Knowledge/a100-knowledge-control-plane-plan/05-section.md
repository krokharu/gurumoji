---
note_type: reference-section
status: in-progress
updated: 2026-09-30
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/knowledge-builder
- gurumoji/colab
- gurumoji/plan
note_id: design-a100-knowledge-control-plane-plan-section-05
title: A100知識推論コントロールプレーン計画：4. 管理する指標
summary: 4. 管理する指標。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 227
- 269
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：4. 管理する指標

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 4. 管理する指標

「知識量」を1つの曖昧な数字にはしない。専門家・モデル・Pack版ごとに次を表示する。

| 区分 | 指標 | 意味 |
| --- | --- | --- |
| 知識量 | approved claims / candidate claims | 採用済み主張数と未審査候補数 |
| 知識量 | sources / evidence anchors | 出典数と原文へ戻れる根拠箇所数 |
| 知識量 | mandatory coverage | 必須項目の充足数と総数 |
| 知識量 | context tokens / pack bytes | 実際にモデルへ渡せる量と配布物の大きさ |
| 品質 | evaluation categories | knowledge coverage、mandatory items、evidence support、knowledge organization、content understanding、applicability、abstention、citation integrity、privacy leakage、structure integrity |
| 品質 | verdict / repeat | 2回の独立評価ごとのpass/fail。平均で失敗を隠さない |
| 推論 | attempts / succeeded / accepted | 試行回数、モデル処理成功数、ローカル受理数 |
| 推論 | approved / packed | 人の承認数、Pack収録数 |
| 利用量 | input/output tokens、wall time、GPU time、CU delta | 取得できた実測値だけ。未取得値を0にしない |

一覧用の「総合スコア」は参考表示に留める。合否は既存の決定的gateを使用し、critical failure、blocking violation、必須カテゴリ未達を平均点で相殺しない。

## 5. 状態モデル

画面上の「推論済み」と「推論終了」を別概念として扱う。

- `has_inference`: 試行が1回以上ある派生値。
- `latest_run_state`: 最新試行の実行状態。
- `review_state`: 結果の審査状態。
- `publication_state`: PackとObsidianへの公開状態。

推論runの状態は次に固定する。

```text
draft -> queued -> claimed -> running -> checkpointed
                                  |          |
                                  +------> succeeded -> importing -> accepted
                                  |                         |
                                  +------> failed           +-> rejected

queued/running/checkpointed -> expired | cancelled | interrupted
accepted -> reviewed_approved | reviewed_rejected
reviewed_approved -> packed -> published
```

`succeeded`はColab上で結果ZIPを生成できた状態、`accepted`はローカルでhash・schema・権利・generationを検証して受理した状態、`reviewed_approved`は独立審査済みの状態とする。この3つを同じ「完了」にまとめない。
