---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-30
title: 専門家知識制作・実行報告書：2026-09-28 14:33 UTC A100 cross-session comparison batch
summary: 2026-09-28 14:33 UTC A100 cross-session comparison batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 364
- 371
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 14:33 UTC A100 cross-session comparison batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 14:33 UTC A100 cross-session comparison batch

- Poliandri et al.（2023）のFrontiers公式論文§4.2.2（CC BY 4.0、Source文書SHA-256 `ceff84c3d635dcc5f9ed70218851055e907d97817e13d92250b5a75ffd66058c`）から`exp-cross-session-comparison`向けに2件を生成した。(1) この研究の13件の同期オンライン・フォーカスグループのうち4件は校長、9件は教員のグループだった。(2) 異なる日程・参加者で行う各回に共通の管理プロトコルと同じスクリプトを使った。いずれも単一研究の事例として限定し、会話数の一般基準や確立済みの一般手順とはしていない。根拠スナップショットSHA-256は`8acd48a0c4814e608f1d9edbb005677a6bab0a4679c24f4e1dda098d8b0b71b5`。[Frontiers article](https://www.frontiersin.org/journals/sociology/articles/10.3389/fsoc.2023.1145264/full)。
- Commit SHA-256はjob 01 `bc6c0782cec7c68416c6e43b787f33e9ad2ac488693b247c7f00e113de629a22`、job 02 `01899da9ff77d6d79fa174e6635dadd06c3ee5a25b352200d5fc64774910f51a`。結果ZIP SHA-256は`cf94d7ba328a25f2b6a4564788a1109b30c2eccff96ee1ae584155c834912b56`と`8eff3062f01d2403dc64b414848dd5429d8c720e7655596f92e393e4e5c3370c`。バンドル、抜粋、Sourceと根拠の各ハッシュは`output/knowledge-colab-batch/b20260928t143300.json`に記録した。
- 2回のA100作成要求はService Unavailableとなり、各回の後に割当0を確認してから同名の3回目でStandard A100を確保した。Transformers 4.51.3、Tokenizers 0.21.4、Hub 0.30.2をカーネル再起動後に確認。推論は1,568 input tokens、214 output tokens、40.233秒。残高は83.13から82.75 CUへ0.38 CU減少し、停止後のactive sessionは0。
- Poliandri et al.の文献ノートへ会話間比較との関連と§4.2.2の条件を追記し、cross-session比較のケース表、手順、未解決事項に一研究の事例として登録した。一般的な複数フォーカスグループ比較手順と必要数の根拠は引き続き未確認。
- 読み取り専用のprimary JobStore監査でSQLite integrity `ok`、99 accepted Commit、98 Claim、99 Source、17/17 expert domain、artifact/hash/evidenceエラー0、Knowledge Pack 0を確認した。`cross-session-comparison`は6 Claim、`group-comparison-statistics`は6 Claim。今回のCandidateも承認・公開せず、P6の体系整理・実データ評価は未完了。
