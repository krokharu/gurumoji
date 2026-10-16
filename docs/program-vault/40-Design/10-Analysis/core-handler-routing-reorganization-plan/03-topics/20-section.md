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
note_id: design-core-handler-routing-reorganization-section-20
title: コア・ハンドラー・ルーティング再編案：AI管理とローカルのオーケストレーター用データ
summary: AI管理とローカルのオーケストレーター用データ。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1247
- 1277
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：AI管理とローカルのオーケストレーター用データ

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## AI管理とローカルのオーケストレーター用データ

この節は追加設計であり、以下の「現行」以外は未実装の提案である。ローカルデータは現行コードが参照するSoftware Vaultと設定上の実行データ領域を対象とする。追加のローカルデータは所在・形式・所有者を特定してから接続し、実Vaultの一括読み込み・移動を前提にしない。

### 1. 現行の役割と実行先

| 役割 | 現行の実装・実行先 | 設計上の位置付け |
| --- | --- | --- |
| 文章生成・整形・見解・アウトライン | `call_ai_json`：OpenAI／Googleはクラウド、LM Studioは同一PCのloopback | 生成役。操作ごとのモデル・設定を固定して実行 |
| 修正要否の判定 | `jev_review.py`＋`review_segments_with_jev`：TypeSafeのクラウド | 判定役。原文を書き換えず、生成AIの変更候補との一致・不一致を示す |
| 発話分類の提案 | `segment_classification.py`＋`classify_segments_with_jev` | ルール・Jev・既存Transformer・手動値を別々に保持する |
| 音声認識・埋め込み・統計 | Whisper、Transformer、既存の分析コード | ローカル計算。生成AI providerと同じ選択欄や状態モデルへ押し込まない |
| 手法選択・前提検証・実行順序 | 既存Handler、分析方針、`method_experts.py` | コードが制御する。専門家定義は手順・制約を与える知識であり、常駐する別LLMではない |

既存の`TokenConfig`／`load_token_config`、`ai_effort.py`、`post_json`／`ai_http_worker.py`、モデル設定UIを利用する。Jevは`call_ai_json`の生成用JSON schemaとは異なるChoice形式を使うため、通信・取消などの共通部分を共有しても、その要求・応答契約は分ける。

### 2. クラウド／ローカルを管理する方針

| 研究データの送信方針（提案） | 許可する実行 | 許可しない実行 |
| --- | --- | --- |
| `local_only` | 同一PCのLM Studioとローカル分析 | OpenAI／Google／Jevへの研究データ送信、LAN・外部ホストへの自動切替 |
| `cloud_allowed` | 操作で選ばれ、許可されたprovider・役割・データ範囲 | APIキーがあるだけの未選択provider呼び出し、無関係なデータの送信 |

- **生成AIがローカルでも、Jevを使う操作はクラウド送信を含む。** `jev_compare`と分類の`use_jev`を別の送信判断として扱う。`local_only`とJev有効が両立しない要求は開始前に理由を返し、黙ってクラウド実行したりJev済みと表示したりしない。
- 利用者が操作・保存済み設定で指定した送信方針と役割を実行要求へ固定する。実行の途中で設定ファイルが変わっても、既存要求の送信先・モデルを変えない。既存設定の移行時は現在のprovider／Jev指定を明示して取り込み、同意済み範囲を広げない。許可の再確認をバッチごとには求めない。
- LM Studioは現在のloopback制限を維持する。LAN上のサーバーを使う拡張は同一PCのローカル実行と区別し、接続・送信契約を別途設計する。
- 接続不能、モデル未読込、JSON出力非対応、メモリー不足を開始前に可能な範囲で確認する。失敗時に他のproviderへ自動で送らない。別モデルで再実行する場合は、元の失敗記録を残した別の実行として扱う。
- `local_only`は研究データの送信範囲を表す。モデルの初回ダウンロードや更新まで禁止する完全オフラインとは区別する。オフライン運用時は必要モデルを事前配置し、取得が必要なら理由を示して停止する。

モデルの価格や性能を固定値で選ぶ自動ルーターは初期導入しない。必要能力（生成／Choice判定、構造化出力、入力長、エフォート設定）と利用可能性を確認し、まず利用者の明示選択を優先する。
