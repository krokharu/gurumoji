---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-27
title: コア・ハンドラー・ルーティング再編案：採用判断
summary: 採用判断。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1523
- 1554
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：採用判断

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 採用判断

| 選択肢 | 判断 | 理由 |
| --- | --- | --- |
| 全面書き換え・7層の先行構築 | 不採用 | 保存・回復の危険と実装量が大きく、利益を確認するまでが長い |
| 全ルートを先にBlueprintへ移動 | 不採用 | endpoint・hook・循環依存の影響が広い一方、業務処理の検証容易性がまだ得られない |
| 機能別の小さな縦切り | 採用 | HTTP互換と独立検証の効果を早く確認でき、段階ごとに止められる |
| 完成した縦切りでいったん停止 | 許容 | 再編自体を目的化せず、優先課題や実装上の効果に合わせて継続を判断できる |

## 実装根拠

パスは特記のないものを`src/gurumoji/`配下として読む。行番号は移動で変わるため、識別子を基準にする。

| 論点 | 確認した現行実装 |
| --- | --- |
| endpoint依存の保護と受付 | `app.py`：`enforce_request_security`、`disable_development_cache` |
| 互換importと差し替え | `src/app.py`：`sys.modules`へのalias、`tests/test_analysis_storage.py`／`tests/test_analysis.py`の`app`差し替え |
| 初回の分離対象 | `app.py`：`get_analysis_methods`、`get_analysis_runs`、`get_analysis_artifact` |
| 固定保存・再試行 | `app.py`：`save_analysis_run`、`retry_analysis_vault`、`archive_group_analysis` |
| 起動・回復・終了 | `app.py`：`initialize_application`、`main`、`_run_initialized_application`、`start_obsidian_watcher` |
| 既存の結果契約 | `analysis_method_registry.py`：`METHODS`、`REGISTRY_VERSION`、`method_results` |
| AI設定・実行場所・通信 | `app.py`：`TokenConfig`、`lmstudio_base_url`、`call_ai_json`、`post_json`、`ai_http_worker.py`、`ai_effort.py` |
| Jevの役割と既存成果物 | `jev_review.py`、`segment_classification.py`、`app.py`：`review_segments_with_jev`、`classify_segments_with_jev`、`archive_ai_finishing` |
| ローカルの知識と実行記録 | `method_experts.py`：`ExpertCatalog`、`review_for_analysis`、`ai_context`、`vault_registry.py`：`publish_analysis` |
| 保存順・冪等性・回復 | `analysis_store.py`：`AnalysisStore.save`／`retry`、`initialize_store` |
| 外部キー・準備変更の無効化 | `transcript_preparation.py`：`initialize` |
| 循環依存の局所抽出候補 | `analysis_store.py`の`safe_path`／`write_atomic`／`markdown`、`obsidian_layout.py`等からの参照 |
| 再編と分ける優先不具合 | [[40-Design/50-Governance/known-issues/00-Index\|known-issues]]：OBS-18、[[40-Design/50-Governance/convergence-plan/00-Index\|convergence-plan]] |

関連：[[10-Architecture/10-System/system-map/00-Index|system-map]]、[[20-Modules/10-Inventory/module-map/00-Index|module-map]]、[[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]、[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]、[[30-Data/40-Vaults/four-vaults-v1|four-vaults-v1]]、[[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]]。

AI管理の関連：[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]、[[50-Analysis-Methods/10-Experts/00-Index]]、[[50-Analysis-Methods/08-Common-Knowledge/00-Index]]、[[50-Analysis-Methods/20-Literature/00-Index]]。
