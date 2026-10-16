---
note_type: reference-section
status: proposed
updated: 2026-09-25
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/rules
note_id: design-analysis-method-rules-section-02
title: 分析手法ごとのObsidian登録規約：根拠の種類
summary: 根拠の種類。出典ノート「分析手法ごとのObsidian登録規約」の分割本文。
parent_note_id: design-analysis-method-rules
source_path: 40-Design/method-rules.md
source_sha256: b12c64c4bba7906a0e26cb253b7c8e6d2b1eca2ff8b8342118d27ab8c2cdc9a4
source_body_lines:
- 47
- 68
split_on: '2026-10-11'
---

# 分析手法ごとのObsidian登録規約：根拠の種類

親索引・状態・確認版：[[40-Design/50-Governance/method-rules/00-Index]]。必要な本文だけを取得する。

## 根拠の種類

発話に基づく主張は、原文へ戻るための参照を必須にする。統計集計の主張は、対象集合のスナップショット・対象数・結果表の行キーを根拠にする。集計値の説明のために恣意的な1発話を「全体の根拠」として付けない。

関係は `supports`（支持）、`contradicts`（反証）、`context`（文脈）、`follow_up`（追加確認）、`derived_from`（導出元）から選ぶ。ノートには関係名の見出しとリンクを書く。機械向けの複雑な関係・大量の発話IDはJSONに保存し、YAMLプロパティへ深く入れ子にしない。[Obsidian公式：プロパティ](https://help.obsidian.md/Editing+and+formatting/Properties)

## 新しい分析手法の登録手順

1. [[90-Templates/10-Analysis/method-registration|手法登録票]] を作り、英小文字・数字・アンダースコアの `method_id` と版を割り当てる。
2. 研究上の目的、入力単位、必須列、ID、対象・除外、パラメーター、利用条件を記載する。
3. 出力JSON schema、CSV列、必須成果物、図の形式、根拠の規則を定義する。
4. `execution_kind` を `builtin`／`external`／`manual` として、計算を担当するアダプターまたは外部ツールを登録する。
5. 正常、空、1話者、対象外ID、欠測、古い入力、重複実行の架空サンプルを用意する。
6. サーバーでschema・ID・hash・対象版を検証し、登録プレビューでノート・表・リンクを確認する。
7. 条件・根拠・原文へ戻れることを確認して手法を有効化する。式や対象単位が変わったら手法版を上げる。

追加の完了条件（2026-09-20設計）：新設・拡張する手法は、登録票にUI入口・設定、結果と根拠、比較・再利用、状態と操作検証も記入する。計算・保存/APIと対応するUIを一組として公開し、画面がモックだけの段階で「利用可能」にしない。詳細は[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]の「分析手法とUIの対応確認」。共通部品の利用や既存編集画面への往復は認め、手法ごとに専用画面を量産しない。

登録票やJSONは宣言的なデータとして読む。ファイル内の任意Python・JavaScript・シェルコマンドを自動実行する仕組みにはしない。

2026-09-20追加設計（未実装）：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]の図6では、LLM分析専用オーケストレーターと疑似人格の相談で、この登録票に沿う手法別契約の原案を作る。入出力の型に単位・尺度・欠測・キー・根拠と後続手法の要件を含め、既存の登録・検証経路へ渡す。相談の合意だけでは有効化せず、schema・実装能力の確認と試行を行い、採用した版を固定する。結果の形は表だけに限定せず、主張集合・関係表・系列・ベクトルを必要に応じて追加する。生成案が既存の専門家定義や人の確定コードを直接上書きすることはない。
