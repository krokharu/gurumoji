---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-03
title: 設計判断の記録（ADR）：ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）
summary: ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 37
- 48
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）

- 状態: 採用・実装。基点 `75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、branch `krokharu/エージェント設計図改善` の未コミット変更。実データ移行・別環境反映は未実施。
- 背景: 利用者の「オブシディアン管理用エージェントを追加し、CoreやHandlerから情報を受け取り管理、基本的にデータをObsidianとリンクして配置」の依頼。
- 決定: Pythonの `ObsidianManagementAgent` を共通Handlerへ依存注入する。Coreの採用判断とHandlerの実行記録はSQLiteへ確定後に渡し、管理ノート・既存catalog/indexを `VaultRegistry` の安全な生成ノート経路で更新する。追加のLLM・自由なファイル操作・新しい分析タスクは導入しない。
- 決定: 説明・短いAI要約・索引はOrchestrator Markdown、全量台帳/表/発話はSQLite/AnalysisStoreを正本に維持し、ID・版・hash・API/artifactリンクで結ぶ。索引は各直近40件と総件数、要約1200文字までで省略を明示。完成済み固定packageのみartifact参照を載せ、未保存を保存成功へ変えない。
- 保存範囲: 新規 `obsidian_management` は既定trueで開始前にOFF可能。旧runの設定欠落はfalse、再開/管理再試行で範囲を変更しない。原文を含む4 Vault一式公開の既定OFFは維持し、管理設定と画面で分ける。管理ノートもrestricted。SQL schema追加・移行は不要。
- 所有権/復旧: 研究者所有ノートを更新しない。生成ノートの編集は既存履歴へ保存、削除は自動復元しない。status/downloadのGETは読取りだけ。管理更新失敗は独立した状態で示し、明示再試行は分析を再実行しない。封印exportは保存receiptに固定し、閲覧時のファイル状態でpackageを変えない。
- 理由/代替案: 整理のための追加AIや全データのノート複製は、再現性・保存主体・原文公開範囲を曖昧にするため不採用。アプリの保存正本とObsidianの索引を既存責務で結ぶ。開発用役割Markdownだけを置く案では実行時の受渡しが成立しないため、実コードへの接続も行う。
- 検証/影響: 自律分析129件、Vault/保存/閲覧72件、最終管理/自律分析/HTTP/公開75件、DOM29件、実Edge操作2件が成功（別バッチ・重複あり）。一時DB/Vaultと合成入力のみ、実AI・実Vault・Linuxクラウドは未実施。詳しいコマンド・文字コードによる初回失敗・既存警告は [[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]。
- 関連: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、[[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]、`src/gurumoji/services/obsidian_management.py`、`vault_registry.py`、`analysis_orchestration.py`、`.agents/agents/gurumoji-obsidian-manager.md`（別系列の歴史参照。`eb46e68793ef78e71fcae5493e6e5fa4c2354335`に存在するが、Downloads基点には役割文書・実装`services/obsidian_management.py`とも存在しない。現在系列の責務は[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）|decisions#Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）]]を参照）。Windows/クラウドともOS別分岐を足さず共通実装を使う。
