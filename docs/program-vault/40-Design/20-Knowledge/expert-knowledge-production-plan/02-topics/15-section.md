---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-15
title: 配布用専門家の知識・プロンプト制作計画：計画表の工程番号に対する実状態
summary: 計画表の工程番号に対する実状態。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 532
- 542
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：計画表の工程番号に対する実状態

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### 計画表の工程番号に対する実状態

- P0: 部分完了。17専門家・76文献ノート・108参照の棚卸し、RTX 5070上のLM Studio JSON分類smoke、合成JobのDrive往路hash照合まで確認済み。分類5ケースは4/5一致で、自動監視判断には未承認。A100監視Notebookは毎時のGPU健全性確認と80分ごとのDrive照合を実装・Driveへ反映済みだが、ColabでのRun all、実A100結果のDrive保存、返却ZIPの一度だけの受理は未確認。Driveアプリ認証経路とローカル分類器の独立評価も残る。
- P1: 基本schemaとJob/Commit/Pack契約は実装・監修済み。Local Papers overlay契約と評価suiteアクセス隔離の運用統合は未完了。
- P2: 一部完了。116参照をmetadata-onlyで監査し、全件の参照解決とstatus/correction metadataの存在を確認した。24件は処理経路rightsを明示的に審査済み、92件は未確認または審査pending。Knight et al. (2024) のCC BY 4.0記事はlocal/指定Colab/exportでの出典付き言い換えを許可し、一般`remote_llm`は許可リスト外。同論文§2.2、3.2、3.4、4の選択箇所を確認し候補生成したが、他文献のrights審査、本文取得、引用範囲確認、Claimの選別・承認は未完了。
- P3: 不完了。builder/reader/evaluationの基盤はあるが、指定3専門家の知識・promptを同一呼出経路で生成して基準版比較・実評価したend-to-end試作はない。
- P4: 部分完了。ZIP送受信、generation lock、offline worker、Colab側Drive pollと固定Qwen3モデルadapterを実装し、CLI管理A100上で固定Qwen3の専門知識Jobを実行・受理した。ローカル側のDrive自動転送・fail-closedな監査停止、Colab実ランタイムによる遅延・切断・再起動試験は未実施。
- P5: 未完了。`source_ingestion.py`には審査済みSoftware Vault文献noteとhashを照合するPDF/TXT取込に加え、利用者指定のprivate PDF/TXT取込・検索・根拠読取の試作を追加した。private overlay builderの静的境界はあるが、実論文の取込実績、OCR、採用審査、既存分析readerへの統合・評価は未完了。公開資料をColabへ渡す経路とprivate資料をローカルに閉じる経路は別に審査する。
- P6: 進行中。17専門家すべてに出典付き候補Claimがあり、primary JobStoreに105 accepted Commit（104 Claim、105 Source）が保存されている。読み取り専用監査はSQLite integrity `ok`、17/17領域、artifact/hash/evidenceエラー0、Knowledge Pack 0。Byrne（2022）の2バッチでは計7件を生成し、5件を未承認候補Commitとして取り込んだ。初回の誤った著者名と意味ずれの出力は保留のまま、修正版2件を別Jobで受理した。日本語テキスト前処理は5 Claimとなり、GiNZA v5.2.0公式READMEに基づく候補を追加した。重複・不足の体系的な整理、prompt整備、17専門家全員の反復開発評価は未完了。
- P7: 未着手。承認済みBase版／Local Papers版のZIPは存在しない。
