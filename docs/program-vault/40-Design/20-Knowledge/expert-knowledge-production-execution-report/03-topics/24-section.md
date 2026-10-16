---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-24
title: 専門家知識制作・実行報告書：2026-09-28 11:22 UTC A100 conversation-timing denominator batch
summary: 2026-09-28 11:22 UTC A100 conversation-timing denominator batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 308
- 314
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 11:22 UTC A100 conversation-timing denominator batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 11:22 UTC A100 conversation-timing denominator batch

- Processed two hash-bound Qwen3-32B-AWQ jobs from Levinson and Torreira (2015), Sections 5.2.1–5.2.2. Both were checked against the publisher's full text and accepted as unapproved candidates for `exp-conversation-timing`: (1) between-overlaps were 30.1% of all floor transfers in the 348-conversation (~38-hour) sample; (2) after silent parts were excluded, single-speaker speech was 95.3% of the remaining speech signal. The denominators are distinct and retained in each Claim. [Publisher article](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.00731/full).
- Commit SHA-256 values: job 01 `f6e966d7d971179a9c02d6c91b5c5a1f0c7a465fc5c377b82046dba4583d0550`; job 02 `8d9970f0dd06e8d8cbcacc905f79a5402f2ebbd8b6c0c08dd8a269473a8c44a6`. The official publisher PDF SHA-256 is `bda17c1efd9ad7914fca32e9b444141b2a7c6fc5f55ffc37678b08627205dd96`; the separate local evidence-text paraphrase has SHA-256 `4c6f0a7d54e4a19d35e70bae5c1a83df9d748b3cc39624d1408233d2505e088f`.
- Preflight confirmed NVIDIA A100-SXM4-80GB and Transformers 4.51.3, Tokenizers 0.21.4, and Hugging Face Hub 0.30.2. Inference totaled 1,548 input tokens, 251 output tokens, and 45.844 seconds, excluding setup and transfers. The session was stopped; Colab reported no active sessions and 87.55 compute units remaining, down 0.33 CU from the pre-session balance.
- A read-only primary JobStore audit verified SQLite integrity, 84 accepted Commit manifests, 83 Claim artifacts, 84 Source artifacts, coverage of all 17 expert domains, zero artifact/hash/evidence errors, and zero Knowledge Packs. The inventory remains 17 valid expert definitions, 87 literature notes, and 116 resolved expert references. Updated the conversation-timing case table; no candidate was approved or published.
