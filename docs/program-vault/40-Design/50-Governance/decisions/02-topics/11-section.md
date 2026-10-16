---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-11
title: 設計判断の記録（ADR）：ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む
summary: ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 377
- 402
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む

- **状態：** accepted、実装済み（2026-09-16）
- **背景：** 分析方針（`build_focus_group_analysis_plan`）は、どの手法を選んでも同じ汎用の手順を示し、手法ごとの前提・適用条件・禁止事項・品質基準を持っていなかった。手法の知識は `50-Analysis-Methods` の手法ノートに実装の観点でまとめられていたが、方法論の文献の確認範囲と査読状態は記録されていなかった。
- **決定：**
  - 分析手法ごとの専門家定義（17人）を `docs/program-vault/50-Analysis-Methods/10-Experts/<専門家>/` に置き、`01-Expert.md` の「実行定義」（YAML）を正本にする。文献ノートは `20-Literature`、全専門家に共通する規則は `08-Common-Knowledge`、調査の記録は `30-Research-Logs` に置く。
  - `src/gurumoji/method_experts.py` を新設する。分析設定の主手法と、分析方針の補助手法の専門家だけを読み込み、実行定義の適用条件を登録済みの判定でコード評価する。専門家のノートと参照文献のノートから知識hashを計算する。
  - 分析データ（`group_analysis_for_row`）に `experts` を加え、分析方針の手順を主の専門家の手順に置き換える。分析レポートに専門家の確認の節を加える。保存記録（`archive_group_analysis`、`archive_interview_comparison`）では、結果を出した手法の結果に担当専門家の確認を付け、`algorithms.experts` に知識hashを残す。保存する手法ノートの「限界と追加確認」には、担当専門家の判定、満たさない条件、示してはいけない結論、文献IDを加える。
  - AI見解は、研究者が主手法を選び、その専門家定義がAI補助を許可し、分析を始めない条件がない場合だけ専門家モードで生成する。出力には許可された手順の段階IDと、その段階の文献IDを必須にし、サーバーで検証する。使える文献IDは、文献ノートが存在するものに限る。KJ法・計量テキスト分析を主手法にした場合、主の専門家の分析を始めない条件がある場合、AI下書きの段階の根拠となる文献ノートがすべて見つからない場合は生成しない（409）。主手法が未選択（`auto`）の場合は従来どおり手法に依存しない下書きとする。
  - 専門家モードの入力fingerprintには専門家の知識hashを含める。未選択（`auto`）の場合のfingerprintは変えない。
  - 実行時にWeb検索や文献の再取得は行わず、AIには専門家の短い指示（`brief`）と段階ID・文献IDだけを渡す。
  - 一覧と詳細のAPI：`GET /api/analysis/experts`、`GET /api/analysis/experts/<expert_id>`。画面は既存の「対象データの確認と分析方針」パネルに専門家の確認を表示する。
- **理由：**
  - 手法の知識の既存の置き場所がSoftware Vaultの `50-Analysis-Methods` で、Gitで版を管理でき、アプリが読み取れる。
  - PersonaVault（ADR-114）は議論用でアプリは読み書きしない。OrchestratorVaultは生成物の保存先で、人が書く知識の正本に向かない。
  - 新しい依存を加えない（PyYAMLと `obsidian_layout.unpack` を再利用）。
  - 判定を登録済みの名前だけに限り、ノートに書かれたコードを実行しない（[[40-Design/50-Governance/method-rules/00-Index|method-rules]] の宣言的な登録の方針）。
- **代替案：** 専門家の知識をコードの定数にする（研究者が読めず、文献との対応を追えない）。Vault全体や文献本文をAIに渡す（トークンが増え、未確認の内容が混ざる）。実行ごとにWeb検索する（再現性がなく、外部送信が増える）。
- **結果・影響：**
  - 研究者が主手法を選んで生成した既存のAI見解は、この変更後に一度「更新が必要」になる。
  - 専門家定義を変えたら `definition_version` を上げ、知識の確認日を更新する。登録の規則は [[40-Design/50-Governance/method-rules/00-Index|method-rules]] の「専門家定義の登録」。
  - `docs/program-vault` がない配布形態では、専門家の確認は「利用不可」になり、AI見解は手法に依存しない下書きとして動く。
  - 同じ入力の保存は既存の記録を返すが、専門家の知識hashは保存記録の同一性（`algorithms`）に含まれるため、ノートを更新した後の保存は新しい記録になる。
  - テスト：`tests/test_method_experts.py`、`tests/test_method_expert_samples.py`（架空のサンプルによる検証。記録は [[50-Tests/20-Analysis/method-expert-sample-verification|method-expert-sample-verification]]）。
- **関連：** [[50-Analysis-Methods/10-Experts/00-Index]]、[[50-Analysis-Methods/08-Common-Knowledge/04-AI-Assistance-Boundaries]]、[[50-Analysis-Methods/30-Research-Logs/00-Index]]
