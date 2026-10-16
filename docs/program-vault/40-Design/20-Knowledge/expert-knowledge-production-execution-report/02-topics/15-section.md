---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-15
title: 専門家知識制作・実行報告書：2026-09-28 06:43 UTC A100 source and qualifier follow-up
summary: 2026-09-28 06:43 UTC A100 source and qualifier follow-up。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 230
- 239
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 06:43 UTC A100 source and qualifier follow-up

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 06:43 UTC A100 source and qualifier follow-up

- Completed eight hash-bound Qwen3-32B-AWQ jobs on the NVIDIA A100 80GB: six initial jobs and two narrowed revisions. All result ZIP hashes matched the Colab status records; source-record and extracted-evidence hashes also matched the local manifest. Inference metadata totaled 141.902 seconds, 7,249 input tokens, and 815 output tokens, excluding setup and transfers.
- The first attempt for the six initial jobs failed because the worker required Tokenizers 0.21.4. Installed the pinned Transformers 4.51.3, Tokenizers 0.21.4, and Hugging Face Hub 0.30.2 versions, restarted the kernel, and reran the jobs successfully.
- Imported jobs 01, 02, 03, 05, and 08 into the primary JobStore as unapproved candidate commits. Their claims cover SciPy `describe`'s `ddof` behavior, BERTopic's class-based TF-IDF, GiNZA v5's stated training data, SCAT's four-step description, and the majority qualifier in Zhang et al.'s cross-corpus SER review. Commit SHA-256 values are in `output/knowledge-colab-batch/b20260928t061000.json`.
- Held jobs 04, 06, and 07: two KJ claims failed to identify the workflow as specific to the cited study, and one SER claim dropped the source's “majority” qualifier. No candidate was approved or published to a Knowledge Pack.
- Added Shimizu et al. (2023) as a SCAT application source, keeping its study-specific six-step adaptation separate from the method's primary sources. Repaired and indexed the existing Kanzaki–Sakai, Knight et al., Ziegler, and Zhang notes; updated the SCAT, KJ, quantitative-text, speech-emotion, and Japanese-preprocessing case references. The literature index now lists 87 notes.
- The primary JobStore contains 60 accepted unapproved candidate commits and zero Knowledge Packs. The Colab stop request returned 404; a follow-up status check pruned the stale local session record and reported the session not found.
