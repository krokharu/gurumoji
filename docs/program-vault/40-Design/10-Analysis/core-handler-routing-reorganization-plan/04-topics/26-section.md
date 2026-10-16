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
note_id: design-core-handler-routing-reorganization-section-26
title: コア・ハンドラー・ルーティング再編案：検証対象と受け入れ条件
summary: 検証対象と受け入れ条件。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1495
- 1522
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：検証対象と受け入れ条件

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 検証対象と受け入れ条件

既存テストを優先し、移した実装をなぞるだけのテストや全出力の巨大snapshotは増やさない。以下は実装時に使う検証先であり、今回の文書改訂でテストを実行済みという意味ではない。

| 変更範囲 | 既存の主な検証先 | 追加する場合の観点 |
| --- | --- | --- |
| 手法一覧・履歴・成果物、固定保存 | `test_analysis_storage.py`、`test_analysis_method_view.py` | FlaskなしのHandler、404／409、保存回数、AI未呼び出し |
| 入力・認証・ジョブ | `test_backend_safety.py` | endpoint変更後の上限・受付hook、同時送信、予約解放 |
| 編集・入力版・stale | `test_edit_recovery.py`、`test_transcript_preparation.py`、`test_analysis.py` | 元の回復情報と単独／比較runの無効化 |
| AI・Transformer・分類 | `test_content_analysis.py`、`test_transformer_analysis.py`、`test_segment_classification.py` | 取消・thread失敗・入力変更・呼び出し回数 |
| AI接続・設定・Jev | `test_ai_model_settings.py`、`test_ai_http_worker.py`、`test_jev_review.py`、`test_segment_classification.py` | ローカルとクラウドの境界、local_only時のJev拒否、実行中の設定固定、無制限再送なし、確率検証・手動値の保持 |
| オーケストレーターの知識・来歴 | `test_method_experts.py`、`test_analysis_storage.py`、`test_four_vaults.py` | 選択した定義だけの読取、AI補助不可・文献欠落、knowledge hash更新、本文・秘密値の除外、旧run読取 |
| Vault・watcher | `test_analysis_storage.py`、`test_obsidian_finishing.py`、`test_obsidian_layout.py`、`test_four_vaults.py` | 保存済みパッケージの再利用、所有権、起動・停止 |
| 起動・UI全体 | `test_launcher.py`、`test_browser_e2e.py`、`test_content_browser.py` | 互換import、静的配信、代表操作、二重初期化なし |

局所移動では該当テストと隣接境界を実行する。共通hook・起動・状態共有を変えた段階で検証範囲を広げ、全体に及ぶ変更では既存の全体テストも行う。重いモデルや外部AIはスタブ化し、再編検証のために実データや実Vaultを使わない。

挙動を維持する構造再編の共通受け入れ条件（AI管理・分析フローの動作拡張はAI-1〜AI-3とFLOW-0〜FLOW-5bの条件を別途適用）：

- 変更対象の公開URL、method、HTTP status、JSON、必要なheaderと配信仕様が互換。
- DB schema、保存配置、stable ID、hash、分析契約の版、Vault所有権ルールを維持。
- Vault再試行・中断保存の回復が保存済み入力と結果を使用し、AI・分析の追加実行がない。初回保存の既存集計は維持。
- 会話編集、話者台帳・分析準備変更のstale伝播と既存triggerが維持される。
- Runtime状態、cancel event、lockの所有者が重複せず、失敗時に解放される。
- 新設したRouting／Handler／Coreが`app.py`へ逆依存しない。
- 少なくとも移行対象の実用的なHandlerをFlaskなしで検証できる。
- 実Vaultを変更せず、対象に必要な既存テストと追加検証が通る。
