---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-23
title: 専門家知識制作・実行報告書：2026-09-28 11:00 UTC A100 FreeTxt sentiment and summarisation batch
summary: 2026-09-28 11:00 UTC A100 FreeTxt sentiment and summarisation batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 299
- 307
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 11:00 UTC A100 FreeTxt sentiment and summarisation batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 11:00 UTC A100 FreeTxt sentiment and summarisation batch

- Ran hash-bound Qwen3-32B-AWQ jobs on an NVIDIA A100-SXM4-80GB High-RAM runtime. Preflight confirmed the A100 and exact Transformers 4.51.3, Tokenizers 0.21.4, and Hugging Face Hub 0.30.2 distributions and modules.
- Job `b20260928t110000-01` produced the evidence-matched distinction between the model page's approximately 95% English accuracy report and the authors' approximately 73% result on manually annotated Welsh reviews. It was imported as an unapproved candidate, Commit SHA-256 `533663e8c194532ee44dacdd161feac4465c288d5fa2a329b0066c234a007edf`; inference used 873 input tokens, 158 output tokens, and 30.866 seconds.
- Job `b20260928t110000-02` reversed the source's comparison direction and incorrectly stated survey/feedback data were more useful than long-form documents. It was not imported and is held for revision. After making the direction explicit in Japanese and including the inequality, corrective Job `b20260928t110000-03` produced the supported statement that partners found the extractive summariser more useful for long-form documents than survey/feedback data; it was imported as an unapproved candidate, Commit SHA-256 `5b7864050cf8b7aab6e0b4112b8ef8f6b55e592151f7533f5a826f0270bf633b`. Corrective inference used 882 input tokens, 98 output tokens, and 16.640 seconds. The held inference used 853 input tokens, 98 output tokens, and 16.795 seconds.
- The two accepted result ZIP SHA-256 values are `0bd65f23dcec04483cc6d7d44a193e7b838fe1ff0bc62e3253db5e6b63e9a6cf` and `a7387805d62cc3a64216392ac7d4d6eaebfb000d4e448f67d231b21634612f2c`. Their shared Source SHA-256 `dffb0133c0c217516e64126f639a3c13db8501ea9f5c333dc4bdf2f4fbd15d3f` pins a curated paraphrase of selected browser-rendered Version-of-Record sections, not original PDF bytes. The repository identifies the article as CC BY 4.0 ([Cronfa PDF](https://cronfa.swan.ac.uk/Record/cronfa70086/Download/70086__34939__f82a24c8c3ea49aaad5c813e2a7643c7.pdf), [DOI](https://doi.org/10.1016/j.acorp.2024.100103)); `correction_status` remains `not_checked`.
- Across all three inference attempts, usage totaled 2,608 input tokens, 354 output tokens, and 64.301 seconds, excluding setup and transfers. The session was stopped; Colab reported no active sessions and 87.88 compute units remaining, down 0.53 CU from the pre-session balance.
- A read-only primary JobStore audit verified SQLite integrity, 82 accepted Commit manifests, 81 Claim artifacts, 82 Source artifacts, 17/17 covered expert domains, zero artifact/hash/evidence errors, and zero Knowledge Packs. The inventory reports 17 valid expert definitions, 87 literature notes, 116 resolved expert references, and no malformed frontmatter; the source metadata audit reports 92 references with processing rights still unreviewed or pending. Updated the FreeTxt literature note, literature index, quantitative-text case table, and current P2/P6 progress summaries. No candidate was approved or published.
