---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-02
title: 設計判断の記録（ADR）：ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）
summary: ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 17
- 36
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）

- 状態: Windows作業ツリーで実装。実モデル試験・制約は運用記録を参照。
- 判断: 記述統計・群間比較・相関の3専門家へ、専用Obsidian知識と入出力契約を渡す。専門家定義版2に分析案・説明のai_draft手順を追加し、既存code／researcher手順は代行しない。他分野のAI補助禁止は維持する。
- 判断: 検定ごとにLLMを増やさず、手法別ツール（記述統計、度数、クロス集計、ANOVA、Kruskal–Wallis、カイ二乗、Pearson、Spearman）をHandlerのallowlistへ接続。共通の既存Python統計エンジンで固定入力から計算し、指定手法の表を返す。任意コード・未実装検定・後から採用したラベル・部分範囲の計算は追加しない。
- 判断: analysis_requestsは提案。Coreが必要性を判断して正式intentを返し、Handlerが発注する。計算前のneeds_calculationを成功した数値結果と扱わず、計算後は同じrun・入力版・許可手法・hashを照合したcalculation_result_ids付き説明を作る。型付き数値表と説明下書きを区別する。
- 保存/互換性: 全計算表・row_id・対象集合・N/欠測/単位・run/task/result/input version/hashは既存SQLite/JSON台帳に保持。Obsidian管理ノートはIDでリンクする。SQL列変更・利用者データ移行なし。プロンプト版6・専門家bundle版2の新規runから適用し、旧runは版ガードで保護する。
- 限界: 形式・参照検査は数値に付けた説明の意味的妥当性を保証しない。人の確認と専門品質評価は必要。結果抜粋の未読行を明示する。
- 関連: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、[[50-Analysis-Methods/10-Experts/00-Index]]、[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]。

### ADR-127 専門家ごとの固定知識と宣言的入出力契約（2026-10-06）

- 状態: Windows作業ツリーで実装。実モデル・未実行範囲は運用記録を参照する
- 背景: Coreから担当への発注は存在したが、専門家のObsidian知識を担当へ渡す経路がなく、保存成功だけでは専門知識の活用を確認できなかった
- 判断: 既存ExpertCatalogとAI補助許可を再利用し、run開始時に選択知識・抜粋・適用条件・入出力契約を固定する。Coreは専門家IDを選び、Handlerがその専門家の知識を渡して正式実行する
- 判断: 分野別の入力・出力項目と型は `07-Agent-Contract.md` の宣言的YAMLで指定する。生成時のJSON Schemaと受信検査を対応させ、知識・発話・許可手順の参照を照合する。人・コードの手順をAIが実施したと扱わない
- 判断: モデルの重みへ知識を学習させず、固定された知識packetを呼出し文脈として渡す。全文profileは台帳へ保存し、モデル入力は重複を省き、未読範囲を明示する。独立検証へCoreの期待結論を渡さない
- 互換性: 既存カラム・初期結果・成果物・Vault所有権を維持する。プロンプト版を更新し、旧未完runを新しい契約へ自動移行しない。個人知識は既存local_knowledge配置で解決する
- 根拠: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、`50-Analysis-Methods/10-Experts/thematic-analysis/07-Agent-Contract.md`（別系列の歴史参照。`ac4bc6cef2e806a2bf52f503625fb7a1363c20e3`に存在するが、Downloads基点には文書・受信実装`services/expert_agents.py`とも存在しない。現在系列は[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・参照文脈（元系列ADR-127／2026-10-06）|decisions#Downloads再構成・参照文脈（元系列ADR-127／2026-10-06）]]を参照）。検証: [[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]
