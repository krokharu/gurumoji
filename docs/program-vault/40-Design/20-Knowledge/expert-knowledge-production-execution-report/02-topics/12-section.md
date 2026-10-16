---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-12
title: 専門家知識制作・実行報告書：2026-09-28 04:12 UTC A100 prompt v3 correction batch
summary: 2026-09-28 04:12 UTC A100 prompt v3 correction batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 206
- 213
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 04:12 UTC A100 prompt v3 correction batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 04:12 UTC A100 prompt v3 correction batch

- Updated the generation prompt to preserve qualifier strength, distinguish means from modes, retain technical method names, and keep numerical findings within their cited sample or corpus. The v3 hash is `245d9cf3b16dd9612e494b5580e60f5c3b5a330c6db96d3e3d89c525a9dfaa62`.
- Ran 12 retries on an NVIDIA A100 80GB with pinned Qwen3-32B-AWQ. All result ZIP hashes matched their Colab status records. Recorded inference time totaled 228.183 seconds (20,906 input tokens and 1,403 output tokens), excluding setup and transfer.
- Imported jobs 02, 03, 05, and 07 as unapproved candidates. Held jobs 01, 04, and 06 for unresolved scope or terminology issues. Marked five identical outputs as duplicates and did not import them. No candidate was approved or published to a Knowledge Pack.
- The BERTopic independence qualifier was preserved in v3. Mean/mode conflation, the GiNZA training-subset qualifier, and the class-based TF-IDF name remained wrong and are still held. A source-backed candidate now exists for 14 of 17 expert domains; uncovered domains: exp-kj-method, exp-quantitative-text-analysis, exp-speech-emotion-recognition.
- The first execution attempt recorded the recurring Tokenizers kernel mismatch; the pinned package was installed, the kernel restarted, and all 12 jobs then completed. The A100 session was stopped.
