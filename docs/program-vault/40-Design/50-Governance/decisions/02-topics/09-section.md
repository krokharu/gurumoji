---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-09
title: 設計判断の記録（ADR）：ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする
summary: ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 324
- 347
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする

- **状態：** accepted（利用者の決定、2026-09-15。ボタンと送信条件の詳細は人格パネルで具体化。実装はPhase 3）
- **背景：** AI数値化はトークンを多く使う。文字起こしなどの操作と一緒に実行すると、利用者が意図しない費用が発生する。
- **決定：**
  - クラウドLLM（OpenAI、Gemini）への逐語録の送信を認める。
  - 「文字起こし」「AIで数値化」「統計を実行」を別のボタンにし、トークンを使うのは「AIで数値化」だけにする。
  - AI数値化は試行と全件の2段階にし、送信前に送信先、発話数、推定トークン、上限、同意の状態を表示する。
  - 同意しなかった話者の発話は送らず、除外した件数を結果に記録する。同意が未確認の話者を含む場合は警告し、確認を記録する。
  - 話者の氏名・仮名・所属は送らない。同じ判定はキャッシュから再利用し、失敗したバッチだけ再実行する。
- **理由：** 費用を事前に予測でき、統計は何度でも無料で再実行できる。送信の判断を、利用者の明示の操作に限る。
- **代替案：** 文字起こしジョブの中でAI数値化まで実行する。1つのボタンで数値化と統計をまとめて実行する。
- **結果・影響：** 統計の実行・保存・Vault出力がAIを呼ばないことをテストで確かめる。既存のAI見解は話者名（`speaker_name`）を送っており、この決定に揃えるかは別の課題として残す。
- **関連コード：** `templates/index.html`の新規作成フォーム（`finish_in_obsidian`、`ai_provider`）、`app.call_ai_json`、`analysis_insights.create_ai_insights`

### ADR-112 統計の依存にstatsmodelsを追加する

- **状態：** accepted（利用者の決定、2026-09-15。`config/requirements.txt`への追加はPhase 0）
- **背景：** SciPyだけでは、回帰、反復測定・要因の分散分析、GEE、混合モデルを実装できない。
- **決定：** statsmodels 0.15系を依存に追加する。importは関数内で行い、Webの起動を遅らせない。
- **理由：** BSD-3-Clauseで、配布条件（ADR-113）に合う。2026-09-15の`pip install --dry-run`で、0.15.0はnumpy 2.2.6、SciPy 1.18.1、pandas 3.0.3を変更せずに入り、追加されるのはpatsy 1.0.3（BSD-2-Clause）、formulaic 1.2.2（MIT）、interface-meta 2.0.1（MIT）だけと確認した。
- **代替案：** pingouin（GPL-3.0で、ADR-113の依存の方針に反する）。検定をすべて自前で実装する。
- **結果・影響：** セットアップのテストと、READMEの依存の記載を同じ変更で更新する。
