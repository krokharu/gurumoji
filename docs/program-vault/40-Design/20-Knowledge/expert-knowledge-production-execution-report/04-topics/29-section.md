---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-29
title: 専門家知識制作・実行報告書：2026-09-28 14:05 UTC A100 group-comparison API batch
summary: 2026-09-28 14:05 UTC A100 group-comparison API batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 356
- 363
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 14:05 UTC A100 group-comparison API batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 14:05 UTC A100 group-comparison API batch

- SciPy v1.18.0公式`stats.f_oneway` APIページ（文書SHA-256 `f1f260998e47f0d7d994c8a08574901fdaa828cba0ce80fc47af47e125ce43a7`）から、`exp-group-comparison-statistics`向けに2件を生成し、API記述と実装を照合して未承認候補Commitとして受理した。(1) `equal_var=True`が等分散を仮定する標準ANOVAの既定で、`False`がWelch ANOVAを選ぶ。(2) `nan_policy`は`propagate`、`omit`、`raise`を受け付け、既定は`propagate`。選択した言い換え根拠スナップショットSHA-256は`bc89e5d6e0719e3c5cf227e1907bc85f5af41dc5b2c20e39dd1a7502f6c9b068`。[SciPy v1.18.0 API reference](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.f_oneway.html)。
- Commit SHA-256はjob 01 `de08b63b6dd338d4bc0a850f572e44315d65402f4abdd800a77cf581b232f957`、job 02 `89159aa2aa11960902bf64c53760fd29173e653dc8a99dfc293a7487ba83b012`。結果ZIP SHA-256は`785c13380468ad8996cbe0f4b7b6156283eb2e0af2ae7d43c6774ad7f604520e`と`d00811bf9de722e8e343adc7600d26501bf9d049b30abc2ff03bbdcaca544f8a`。各バンドル、抜粋、Sourceのハッシュ対応は`output/knowledge-colab-batch/b20260928t140200.json`に記録した。
- 起動要求は2回Service Unavailableとなり、各回の後に割当0を確認してから同名の3回目で単一A100 Standardを作成した。Transformers 4.51.3、Tokenizers 0.21.4、Hub 0.30.2をカーネル再起動後に確認。推論は1,609 input tokens、186 output tokens、35.817秒。残高は83.31から83.13 CUへ0.18 CU減少し、停止後のactive sessionは0。
- 現在の`src/gurumoji/research_analysis.py`は`stats.f_oneway(*samples)`を呼び、`equal_var=False`を指定していないため、Welch ANOVAは未実装。`None`と有限でない数値は呼出し前に除外され、SciPyの`nan_policy`には委ねていない。公式API資料はソフトウェア仕様であり、Welch型ANOVAの方法論文献を確認したことにはならない。
- 読み取り専用のprimary JobStore監査でSQLite integrity `ok`、97 accepted Commit、96 Claim、97 Source、17/17 expert domain、artifact/hash/evidenceエラー0、Knowledge Pack 0を確認した。`group-comparison-statistics`は6 Claimとなった。SciPy公式APIノート、事例表、未解決事項、分析手順を更新した。Candidateの承認・公開とP6の体系整理・実データ評価は未完了。
