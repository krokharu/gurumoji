---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-27
title: 専門家知識制作・実行報告書：2026-09-28 12:47 UTC A100 SCAT draft review
summary: 2026-09-28 12:47 UTC A100 SCAT draft review。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 329
- 340
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 12:47 UTC A100 SCAT draft review

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 12:47 UTC A100 SCAT draft review

- Shimizu et al. (2023) のMDPI公式論文Methods §2.5から6段階の適用手順とSCAT経験者による監督の2候補を生成したが、1件は「グループの言い換え」を「再構成」と誤記し、もう1件は単一研究を複数研究のように読める表現だったため、両方保留した。いずれもprimary JobStoreには取り込まず、根拠箇所と用語を明確にしたJobを再準備した。
- 結果ZIP SHA-256は`46eea2a95fe6e5036cd1b36194755fded1d0f6eecfa7cb5016a62aa0bd8ead5c`と`dc19be62c0e22bfa916f736454572933f876301c245f5c99e2080e4e2f6302f7`。推論は1,687 input tokens、255 output tokens、46.672秒。残高は85.77から85.49 CUへ減少し、停止後のactive sessionは0。

### 2026-09-28 12:56 UTC A100 SCAT wording revision

- 修正版では、(1) SCATの一般的な4段階説明と区別した本研究固有の6段階手順（ステップ3はデータグループの言い換え）、(2) Shimizu et al.（2023）の単一研究で分析がSCAT経験者に監督されたという事実を生成・照合した。どちらも既存の文献ノートとSCAT事例表に要約済みの内容を、primary JobStoreで個別に参照できるClaimとして未承認候補Commitにした。[MDPI publisher article](https://www.mdpi.com/2673-9259/3/1/2)。
- Commit SHA-256はjob 01 `b1ef9d2746ce557a4650ce93ea8d593651f43d85f02eaeaa3749acf87749bb36`、job 02 `3c8f81961feca6d4b1338d1be636162565c05ec2b8b06ef7dee501a34a010957`。結果ZIP SHA-256は`ac7078f78dee69df0a7293e948ded84e7ee118343cfe8fcf082702e885f113cf`と`7a21160cc3c7c7d6137be3ca8a4ab1e39adadf7c02e378f84719fea9108c09d6`。PDF Source SHA-256は`b7d8fe5964a2de5d8a6c5c858d41468baff10bd8e0d40ce5245add6656266612`、選択した言い換え根拠スナップショットは`6055a83011fe4215c275f61a2832f18d56a30cfd22c0decd2f85a5a9731f723f`。
- 2回のセッション作成要求はService Unavailableとなり、その都度sessions/status/logで割当なしを確認した後、同名で3回目の作成に成功。A100-SXM4-40GB StandardとTransformers 4.51.3、Tokenizers 0.21.4、Hub 0.30.2を確認。推論は1,743 input tokens、316 output tokens、56.365秒。残高は85.49から85.07 CUへ減少し、停止後のactive sessionは0。
- primary JobStoreは92 accepted Commit（91 Claim、92 Source）、全17領域、整合性エラー0、Pack 0。直近7バッチ15生成のうち12件を受理し、3件を保留した。P6の体系整理・反復評価・Pack承認は未完了。
