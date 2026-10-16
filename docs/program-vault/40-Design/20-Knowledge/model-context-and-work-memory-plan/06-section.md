---
note_type: reference-section
status: in_progress
updated: 2026-10-06
feature: analysis-orchestration
tags:
- gurumoji/program
- gurumoji/plan
- gurumoji/ai
- gurumoji/storage
note_id: design-model-context-and-work-memory-section-06
title: モデル別コンテキスト管理と作業記録の保存計画：計画作成時の記録（実装前）
summary: 計画作成時の記録（実装前）。出典ノート「モデル別コンテキスト管理と作業記録の保存計画」の分割本文。
parent_note_id: design-model-context-and-work-memory
source_path: 40-Design/model-context-and-work-memory-plan.md
source_sha256: 5deb802e628cb0041fcc9fb6b42ddf5ac43615a40641f4aa9d09e449c34d9323
source_body_lines:
- 150
- 174
split_on: '2026-10-11'
---

# モデル別コンテキスト管理と作業記録の保存計画：計画作成時の記録（実装前）

親索引・状態・確認版：[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index]]。必要な本文だけを取得する。

## 計画作成時の記録（実装前）

今回保存したのは本計画と入口からの参照。外部一次資料と対象コード・直近試験記録を確認した。実装、モデルロード、再推論、DB構造変更、実Vaultへの公開、Drive更新、commit/pushは未実行。利用者の原本DB・研究者所有のVaultには書き込んでいない。

文書のfrontmatter、提案ステータス、note_idの一意性、ローカル参照9件、Vault参照5件、入口からの参照3件、UTF-8と空白、対象差分を確認し成功した。外部一次資料への参照は7件。文書のみの変更のため、コードのunit testと実AI試験は今回実行していない。

次の実装単位はP0〜P1の入力計測と実行前予算判定とする。全量分割と保存拡張は、その最小単位を確認してから進める。直近試験の失敗を改善済みとせず、P4で内容統合まで再評価する。

## 2026-10-05 実装と試験導入

Windows、`main`、基点HEADは上記と同じ。実装の正本は`services/model_context.py`、既存adapter・Handler・AI transport、`method_experts.py`、Pack reader。依存に`lmstudio>=1.5,<2`を追加した。SDKのモデル探索は`list_loaded()`のhandleだけを使い、自動ロードする`model(key)`を使わない。

| 段階 | 実装と確認 | 残る範囲 |
| --- | --- | --- |
| P0/P1 | 実ロード枠、モデルと設定のhash、chat templateのtoken数、schemaの保守的な加算、出力予約、安全余裕を送信前に確認。超過・未取得は未送信としてDBへ記録 | cloudのtoken計測、価格やパラメーター数による自動割当は未対応 |
| P2 | 初期分析・Core担当指示・尺度設計・統合の段階別契約。全発話の所有範囲と前後1発話の境界を持つタスクを登録し、過大ページは推論前に再分割。必須要件はCore報告・尺度設計の別タスクへ分割。未評価結果を順序付きbatchで取得 | 巨大な単一発話・単一必須要件は保留。自由な全文検索や知識の自動順位付けは未追加 |
| P3 | `task.state_json`へ入力manifest・hash・提示ID・省略・評価対象・専門家briefとモデル予算を保存。原結果もmanifest hashを参照。親子タスクと未処理結果をDBで保持し、全結果は従来の固定JSONへ保存 | 汎用検索cache・新DB schema・研究者Vaultへの追加保存は未導入 |
| P4 | `model_context_version=1`を明示する新規runと試験CLIで評価。旧runはadapter版不一致で新契約による自動再実行を拒否 | 内容品質に合格した役割・モデル組合せの認定は継続中。既定0を維持 |

専門知識は通常brief経路を再利用し、`expert_step_ids`で許可済み手順だけを選択する。必須条件・禁止結論は省略しない。Pack v2は審査済み方針・root・claim hash・依存関係を検証して全claim単位で取得し、v1を維持する。実Packの選択方針や配布承認は今回作成していない。

合成試験では8K/16K/32Kの容量境界、未送信時の0推論、要件の保持、323発話の各役割での所有範囲・境界の非重複、blind検証、未評価結果の保持、保存済み結果を再利用する再開を確認した。最終の関連テスト159件が成功した。実モデル試験の成功・失敗と未検証の品質は運用ノートで区別する。

最終adapterはv21。結果数と提示した批判の応答数に応じて出力予約を増やし、主張以外の批判・尺度要求の根拠原文も取得する。v19の8B/16K全体試験は初期全役割323発話、専門家の尺度出力、Core統合23回まで成功したが、24回目は3200tokenの出力上限で停止した。v21で同じ停止場面の単発packetを4096token予約にすると契約検証は成功し、コピーDBも不変だった。v21の全体再試験は未実施。尺度下書きは未読・欠測の数値化や否定表現の誤分類があり、研究用尺度として未合格。P4の役割別品質認定と自動導入は完了していない。回ごとの取得・採否は運用ノートから実験記録へ参照できる。
