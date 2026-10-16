---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-01
title: 発話の数値化とjamovi型統計の自動実行計画：発話の数値化とjamovi型統計の自動実行計画（第2版）
summary: 発話の数値化とjamovi型統計の自動実行計画（第2版）。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 1
- 23
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：発話の数値化とjamovi型統計の自動実行計画（第2版）

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。


# 発話の数値化とjamovi型統計の自動実行計画（第2版）

逐語録をルール・Transformer・LLM・人手で変数にし、jamoviで実行できるt検定やクロス集計のカイ二乗検定などを自動で実行するための計画。

- **位置づけ：** 提案。アプリのコードは未変更。確認版はブランチ`agent/expand-analysis-ai-workflows`のHEAD`967799a`と、2026-09-15の未コミット作業ツリー。
- **第2版で変えたこと：** 利用者の決定（2026-09-15）と、8人格のパネルによる議論を反映した。パネルと議事録はPersonaVault（`<data>/obsidian/PersonaVault`）の`PNL-quantification-statistics`と`DLB-20260915-quantification-statistics`。Vault間はリンクせず、IDで参照する（ADR-007）。決定は[[40-Design/50-Governance/decisions/00-Index|decisions]]のADR-110〜114に記録した。
- **収束計画との関係：** ADR-106（追加より統合）に合わせ、既存の重複を統合しながら進める。[[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]]の課題とは、ファイルが重ならない範囲で並行する。
- **根拠：** [[40-Design/50-Governance/method-rules/00-Index|method-rules]]、[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]、[[50-Analysis-Methods/03-Statistics/00-Index]]。
- **2026-09-20の接続設計：** [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]の図5で、LLM・Transformer・Jevによるカラム生成から本計画の変数カタログ・データセット・統計実行への接続を明示した。既存のJev／Transformer列とクロス集計は再利用する。任意の生成列を選ぶ共通の統計経路と、一般LLMによる定義済みコード・評定の生成は未実装。既存の分類CSVの`llm_*`列はJevの値であり、一般LLMの生成列と混同しない。

## 0. 決定事項

| 項目 | 決定 | 決めた人 | ADR |
| --- | --- | --- | --- |
| 着手の順序 | 進行中の作業の確定 → Phase 0 → OBS-18 → Phase 1a → 1b → 2 → 3 → 4 → 5 | 人格パネル（利用者が委任） | ADR-110 |
| クラウドLLMへの送信 | 許可する。AI数値化は専用のボタンからだけ実行し、文字起こし・統計の実行とボタンを分ける | 利用者（ボタンの詳細はパネル） | ADR-111 |
| statsmodels | 0.15系を依存に追加する | 利用者 | ADR-112 |
| 配布条件 | 本体はMITライセンス。第三者ライセンス一覧を付け、GPL・AGPLのライブラリはプロセス内に取り込まない | パネル（利用者の方針「使っているライブラリに即す」） | ADR-113 |
| 議論用の人格 | 人格の定義と記憶をPersonaVaultに置き、OrchestratorVault（手法カード・実行記録）と用途を分ける | 利用者の指示に基づきパネル | ADR-114 |
| 検定の計算の置き場所 | 新しいモジュール`statistical_tests.py`にまとめる | パネル | ADR-110 |
| 複数会話の検定 | `interview_comparison`を拡張せず、別の実行種別`study_statistics`にする。画面は既存の比較パネルから始める | パネル | ADR-110 |
