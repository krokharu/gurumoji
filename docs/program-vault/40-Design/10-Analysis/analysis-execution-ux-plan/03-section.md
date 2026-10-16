---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/ui
- gurumoji/orchestrator
note_id: analysis-execution-ux-plan-section-03
title: 分析実行UX統合・段階分析設計：5. 分析の段階
summary: 5. 分析の段階。出典ノート「分析実行UX統合・段階分析設計」の分割本文。
parent_note_id: analysis-execution-ux-plan
source_path: 40-Design/analysis-execution-ux-plan.md
source_sha256: 1bc504e638f40bdced00fbee6a2763e8bffc51f74a85ded0fd11d17cdacf2d93
source_body_lines:
- 162
- 201
split_on: '2026-10-11'
---

# 分析実行UX統合・段階分析設計：5. 分析の段階

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-execution-ux-plan/00-Index]]。必要な本文だけを取得する。

## 5. 分析の段階

段階番号は利用者に順序を伝えるための表示であり、すべての分析が必ず直列になることを意味しない。独立した処理は同じ段階内で並行実行できるが、初期実装では競合と負荷を避けるため逐次実行でもよい。

| 段階 | 名称 | 主な処理 | 完了条件 | 次へ進めない例 |
| --- | --- | --- | --- | --- |
| 0 | 準備・入力確認 | 本文版、発話ID、話者、除外、分析設定、モデル利用可否を固定 | 固定した計画と入力fingerprintを保存 | 未保存の編集、空本文、設定不足、本文版競合 |
| 1 | 基礎分析 | 発話量、時間推移、語彙、形態素、係り受け、記述統計、ローカル見解 | 手法ごとの結果状態と警告を保存 | 解析器が利用不可、必要件数不足 |
| 2 | 構造化・特徴抽出 | Transformerテーマ、意味ベクトル、選択されたAI数値化・分類用の特徴 | 後続が参照できる固定artifactと行IDを保存 | モデル未取得、テーマ定義不足、外部送信未許可 |
| 3 | 依存分析 | 発話分類、クロス集計、群比較、親結果を入力にする追加分析 | 親run・artifact・hashとの依存を記録して保存 | 親段階失敗、尺度・キー不一致、必要列不足 |
| 4 | 解釈支援・検証 | AI見解、反例・少数意見、手法前提、根拠照合、研究者の確認待ち | 主張と根拠ID、限界、確認状態を保存 | 研究質問不足、専門家ゲート不適合、根拠不成立 |
| 5 | 確定・公開 | 固定JSON／表、閲覧用出力、Vault公開 | AnalysisStoreへの確定後に段階完了 | 保存失敗、Vault競合。Vault失敗は分析計算の失敗と分ける |

### 5.1 データ待ちと再分析

後からデータが揃う処理は、失敗ではなく `確認待ち`または`待機`にする。

例：

- 事前アンケートが未取込 → 群比較は待機。基礎分析は完了として保持。
- Transformer結果が未完了 → それを使う発話分類だけ待機。
- 手動テーマが1件 → 手動割当は確認待ち。自動テーマ分析は選択可能。
- 研究質問が空欄 → AI見解は確認待ち。ローカル集計は実行可能。
- 本文・話者・設定が更新 → 過去runは保持したまま `更新が必要`とし、新しい計画で必要段階を再分析。

待機解除時に全分析をやり直さず、固定済み親結果の再利用条件を検証したうえで、その段階以降だけを新しい試行として実行する。現在版へ黙って差し替えない。

## 6. 実行状態と結果状態

画面では分かりやすくまとめて見せるが、内部では次を別軸で保持する。

| 軸 | 例 | 正本・扱い |
| --- | --- | --- |
| 計画要求 | `draft / accepted / running / completed / cancelled` | 提案済み `analysis_pipeline_requests` |
| 段階の試行 | `waiting / ready / running / completed / failed / cancelled / interrupted / blocked` | 提案済み `analysis_step_attempts` |
| 分析結果 | `not_run / completed / empty / unavailable / fallback / partial / stale` | 手法結果と固定run |
| 保存・公開 | 保存中、保存済み、Vault競合、再公開待ち | AnalysisStore、保留パッケージ、Vault状態 |

`completed`は結果runの保存確定後とする。Vault公開失敗、結果の`partial`、現在版から見た`stale`を、段階実行の失敗と混同しない。
