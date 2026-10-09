---
note_id: analysis-hooks-index
note_type: method-group
title: 分析hookの入口と登録境界
summary: 現行の追加取得プロトコルと将来のライフサイクル通知を分け、版・受領・停止を確認する。
status: proposed
review_state: draft
runtime_state: planned
updated: 2026-10-08
tags: [gurumoji/analysis, gurumoji/hook]
---

# 分析hookの入口と登録境界

この入口はアプリの分析hookを扱う。開発用Codexのライフサイクルhookとは別。登録書式は [[90-Templates/skill-hook-binding]]、責務と提案は [[40-Design/obsidian-skill-knowledge-blueprint#11. hookで取得・検査・引継ぎを接続する（追加提案）]]。

## 現行の追加取得

| 要求名 | 実装と読む対象 | 検査する境界 |
| --- | --- | --- |
| `read_evidence` | `services/expert_data_hooks.py`。今回の許可された根拠IDの原文 | IDを推測補修しない。読取receiptとモデルへの実配信を区別し、未読・未配信を処理済みにしない |
| `read_calculation_table` | 同ファイル。同runの正式な計算resultと型付き表の指定行 | result／table／row、入力版・hash、実配信範囲を照合。原表の全行hashを抜粋から作り直さない |

受入前基準`ac4bc6c`は`expert-data-hooks-2`。G0.5aの独立レビューと301件の回帰後、rootの`0fbfb402af9d9bdd18a495565288bf5ed273d5f4`へ内部hook版3／adapter版10／bundle版3を統合し、統合後の301件も成功した。2巡×各最大3要求・取得上限12,000文字を維持し、読取receiptと実配信receipt、壊れた受領情報の隔離、旧hook版2の凍結読取と再開停止を検査した。これはCPU上の構造検証であり、実モデルや全文の処理成功を認定しない。利用時は固定runのhook版・実装commit・許可集合を確認し、ここに書いた版を実runの版へ上書きしない。今回のF03やM03の実モデル上限は各試験票で別に固定する。

## 提案中のライフサイクル接続

| 接続点 | 責務 | G1bでの状態 |
| --- | --- | --- |
| `task_prepare` | 必須入力、actor、scope、用途、予算を正式発注前に検査 | 論理名。汎用callback未登録 |
| `knowledge_requested`／`data_requested` | 必要範囲の取得、版・配信範囲を記録 | 汎用登録は未実装。既存取得要求と同一視しない |
| `output_received` | 応答を候補保存し、型・参照・意味・採否を検査 | 論理名。候補受領を確定にしない |
| `label_version_committed`／`dataset_committed` | 採用と固定保存の確定後に利用先へ通知 | 汎用通知登録は未実装 |
| `scope_manifest_committed`／`section_result_committed` | 対応済みscopeで区間と全体を引継ぐ | 未対応scopeは理由付き保留 |
| `checkpoint`／`resuming`／`failed`／`stopped` | 永続状態・世代・期限を再確認して停止・復旧する | 論理イベント名。通知再送で生成を再実行しない |
| `memory_projection_requested` | 確定結果を既存の非LLM管理担当へ投影 | 汎用callback登録は未実装。投影失敗と分析成否を分ける |

必要な接続点が未登録なら、その依存作業を`blocked`として返す。ノート名・論理イベント名からcallbackの存在を推測しない。G4で信頼された登録ID・版・入出力・上限・冪等キー・利用先別receiptを実装と照合する。自由なコード実行、権限拡大、上限撤去は登録票の対象外。
