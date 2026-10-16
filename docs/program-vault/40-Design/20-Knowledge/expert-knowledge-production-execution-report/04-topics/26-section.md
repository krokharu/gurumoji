---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-26
title: 専門家知識制作・実行報告書：2026-09-28 12:00 UTC A100 cross-corpus SER batch
summary: 2026-09-28 12:00 UTC A100 cross-corpus SER batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 322
- 328
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 12:00 UTC A100 cross-corpus SER batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 12:00 UTC A100 cross-corpus SER batch

- Zhang et al. (2021) のFrontiers公式論文 p.2から、`exp-speech-emotion-recognition`向けに2件を生成し、原文と既存Claimに照合して未承認候補として受理した。(1) 学習・テストコーパス間の言語、文化、distribution mode、データ規模の差が、SER手法の汎化を妨げる固有変動を生じうる。(2) 基本的なcross-corpus SERシステムの二段階は、感情分類器とdomain-invariant feature extraction。[Frontiers publisher article](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2021.784514/full)。
- Commit SHA-256はjob 01 `2f4ffc9bf6b4c61945c2cebd317e83c22404f2ce2e693aeae9098b056aba1079`、job 02 `7bd05f3dbcf6850052011af4abf8a612984957f9041937efb3842bbede309bc9`。結果ZIP SHA-256は`392fc73b3263f265ca387fb24c8f562bcc0d25d6c0c3588084b4360226a3daea`と`2cd68d9bcd625ad1ebbf2f03d1a501a0664b963226a0b5f32db369d631bc347c`。PDF Source SHA-256は`2f3b80d1cd0247d0b36e99cbdff14c5f14ee680a08b35ada4a46c4a43c7b9d81`、選択した言い換え根拠スナップショットは`eea0b5e63bb544624308d84d5a9a06a95f4fefd3be586607752cb0e7e9760527`。
- PreflightでA100-SXM4-40GB StandardとTransformers 4.51.3、Tokenizers 0.21.4、Hub 0.30.2を確認。推論は1,556 input tokens、203 output tokens、39.497秒。Job 02はbundle転送の停滞と推論前の接続断があったが、Kernel再起動後に同じJobを一度実行し、Status/resultのSHA-256一致を確認した。残高は87.33から86.28 CUへ減少し、停止後のactive sessionは0。
- Speech-emotion-recognitionの候補Claimは5件。P6全体は進行中で、17専門家の反復評価、体系的な重複・不足整理、Pack承認は未完了。
