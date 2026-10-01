---
note_id: res-scipy-f-oneway
note_type: literature
literature_id: RES-scipy-f-oneway
title: "SciPy v1.18.0 stats.f_oneway API reference"
authors:
  - SciPy community
year: 2026
venue: "SciPy v1.18.0 Manual"
source_type: official_resource
peer_review: not_peer_reviewed
peer_review_basis: "統計ライブラリの公式APIマニュアルで、学術誌査読論文ではない。"
doi: ""
url: https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.f_oneway.html
accessed: 2026-09-28
access_scope: official_page
access_detail: "SciPy v1.18.0 Manualのf_oneway関数ページを取得し、ParametersとNotesを確認。"
document_version: "scipy-v1.18.0-manual-f_oneway-retrieved-2026-09-28"
document_sha256: f1f260998e47f0d7d994c8a08574901fdaa828cba0ce80fc47af47e125ce43a7
license_id: BSD-3-Clause
license_url: https://opensource.org/license/bsd-3-clause
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex GPT-6 (read-only)"
rights_reviewed_at: 2026-09-28T02:42:13Z
rights_review_basis: >-
  SciPy's v1.18.0 developer guide states that code, documentation, and other
  contributor-added files are under its modified three-clause BSD license unless
  otherwise specified. Colab processing is limited to this public API documentation
  using our own model; export is limited to attributed, source-linked paraphrased
  claims. The project's remote_llm route remains disallowed.
correction_status: not_checked
related_experts:
  - exp-group-comparison-statistics
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/statistics
---

# SciPy `stats.f_oneway` 公式APIリファレンス

## 資料の目的

SciPyの一元配置分散分析関数が提供する引数と、標準ANOVAおよびWelch ANOVAの選択方法を示す。これは公式API資料であり、査読済みの方法論文献ではない。

## 主要な知見

- SciPy v1.18.0の`f_oneway`では、`equal_var=True`が既定で、等分散を仮定する標準的な一元配置分散分析を行う。`equal_var=False`を指定するとWelch ANOVAを行い、等分散を仮定しない。この引数はSciPy 1.16.0で追加された。
- `nan_policy`は`propagate`、`omit`、`raise`を受け付け、既定は`propagate`。`omit`は計算対象のaxis sliceごとにNaNを除外し、残ったデータが不足すればそのsliceの出力をNaNにする。`raise`ではNaNに対してValueErrorを発生させる。
- 公式Notesが標準ANOVAのp値について挙げる前提は、標本の独立性、各群の正規性、群間の等分散性。Welchを選ぶと等分散の前提は不要になるが、独立性や正規性まで解消するわけではない（公式Notesの前提からの整理）。

## プロジェクトへの適用上の注意

現在の実装は`src/gurumoji/research_analysis.py`で`stats.f_oneway(*samples)`を呼び、`equal_var`を渡していない。SciPy v1.18.0の仕様では既定の標準ANOVA経路となり、Welch ANOVAの選択は実装されていない。実行環境で使われるSciPyの版は別途確認が必要。

同じ処理では群ごとに`None`と有限でない数値を呼出し前に除外するため、この呼出しの欠損処理はSciPyの`nan_policy`引数ではなく前処理で決まる。公式APIの挙動をプロジェクトの分析設計の推奨と混同しない。発話は会話・話者内で依存する可能性があり、Welch ANOVAを選ぶだけで独立性の問題が解消するわけではない。

## 根拠の位置情報

SciPy v1.18.0 Manual「f_oneway」Parameters `equal_var`、`nan_policy`、NotesのANOVA assumptions。

## 未確認事項

Gurumoji実行環境でのSciPy実版、Welch ANOVAに関する方法論文献の追加確認、欠損値の前処理が他の統計量にも一貫しているか。
