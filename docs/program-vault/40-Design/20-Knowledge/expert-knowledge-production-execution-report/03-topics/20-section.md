---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-20
title: 専門家知識制作・実行報告書：2026-09-28 09:49 UTC A100 qualifier-revision batch
summary: 2026-09-28 09:49 UTC A100 qualifier-revision batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 274
- 281
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 09:49 UTC A100 qualifier-revision batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 09:49 UTC A100 qualifier-revision batch

- Re-ran the two claims held in batch `b20260928t093710` on an NVIDIA A100 80GB using Qwen3-32B-AWQ. Preflight confirmed the A100 and imported Transformers 4.51.3, Tokenizers 0.21.4, and Hugging Face Hub 0.30.2. Both result ZIP hashes matched their Colab status records.
- Reviewed and imported both as unapproved candidate commits. The BERTopic claim preserves the five documented topic-representation stages and marks representation fine-tuning as optional Step 6 ([BERTopic v0.17.4 docs](https://raw.githubusercontent.com/MaartenGr/BERTopic/v0.17.4/docs/algorithm/algorithm.md)). The GiNZA claim distinguishes `ja_ginza_electra` from its underlying transformer model and scopes the more-than-200-million mC4 sentence count to that model's pretraining ([GiNZA v5.2.0 README](https://raw.githubusercontent.com/megagonlabs/ginza/v5.2.0/README.md)). Commit SHA-256 values: job 01 `e1b7b135043c3150e5afb64c589abe4eaa56b4ad20dde217e01e5ddc4cee5adb`; job 02 `4278abec7bfa3d1bfe435dbfa3cbaef9eed45d4851f093a80142f99a7fcaebcf`.
- Inference totaled 1,726 input tokens, 219 output tokens, and 41.696 seconds, excluding setup, package installation, and transfers. The two selected excerpts and source records were hash-bound to the jobs. The A100 session was stopped; Colab reported no active sessions and 0.00 CU/hour, with 88.92 compute units remaining (0.31 CU below the pre-batch balance).
- A read-only primary JobStore audit verified all 78 accepted Commit manifests, 77 Claim artifacts, and 78 Source artifact hashes and evidence-to-Source bindings; it found zero integrity errors and zero Knowledge Packs. No Knowledge Pack has been created or published. The expert inventory remains 17 definitions and 87 literature notes, with zero unresolved references. The Software Vault literature notes and index were not changed in this batch.
