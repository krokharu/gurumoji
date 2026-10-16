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
note_id: design-a100-knowledge-control-plane-plan-section-11
title: A100知識推論コントロールプレーン計画：16. 外部仕様上の前提
summary: 16. 外部仕様上の前提。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 545
- 548
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：16. 外部仕様上の前提

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 16. 外部仕様上の前提

- Google Colab FAQ: managed runtimeの利用制限、変動するusage limits、通常最大12時間、十分なCompute UnitがあるPro+の最大24時間、free-of-charge tierでのWeb UI中心利用やremote controlの制限。<https://research.google.com/colaboratory/faq.html>
- Colab Enterprise runtime管理: Enterpriseではruntimeのstart/delete/reconnectに公式の管理経路がある。通常版Colabとは別adapterとして扱う。<https://cloud.google.com/colab/docs/manage-runtimes>
