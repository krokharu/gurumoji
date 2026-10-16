---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-21
title: 専門家知識制作・実行報告書：2026-09-28 10:10 UTC A100 FreeTxt scope batch
summary: 2026-09-28 10:10 UTC A100 FreeTxt scope batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 282
- 289
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 10:10 UTC A100 FreeTxt scope batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 10:10 UTC A100 FreeTxt scope batch

- Ran one hash-bound Qwen3-32B-AWQ job on the NVIDIA A100 80GB using the verified Transformers 4.51.3, Tokenizers 0.21.4, and Hugging Face Hub 0.30.2 runtime. The claim was reviewed against Knight et al.'s CC BY abstract: it describes FreeTxt as a corpus-based tool for Welsh and/or English free-text analysis and user-led analyses of small and larger datasets. It does not claim Japanese-language performance. [Publisher article](https://www.sciencedirect.com/science/article/pii/S2666799124000200).
- Imported the claim as an unapproved candidate commit, SHA-256 `c84bcf999f354dce68248199476ff4f8b706fba2d5cfd146d17d3575f3f6e1b6`. Inference totaled 858 input tokens, 106 output tokens, and 22.413 seconds, excluding setup and transfers. The result ZIP matched the Colab status record; job, source, excerpt, and bundle bindings are preserved in `output/knowledge-colab-batch/b20260928t100700.json`.
- The first local packaging attempt created generation 1 but stopped before upload because the local Source registry output path was also used as input. Generation 2 superseded it through the JobStore retry API and completed; no generation-1 bundle was uploaded or inferred. The A100 session was stopped; Colab reported no active sessions and 0.00 CU/hour, with 88.70 compute units remaining (0.22 CU below the pre-batch balance).
- A final read-only audit verified all 79 accepted Commit manifests, 78 Claim artifacts, and 79 Source artifact hashes and evidence-to-Source bindings; it found zero integrity errors and zero Knowledge Packs. The expert inventory remains 17 definitions, 87 literature notes, and 115 resolved references. Separately, 36 JobStore rows remain in `running` status (34 beyond their recorded deadlines); this is local job state, not active Colab sessions. No Software Vault literature notes or index entries were changed.
