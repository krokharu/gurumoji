---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-18
title: 専門家知識制作・実行報告書：2026-09-28 09:15 UTC A100 precision and scope follow-up batch
summary: 2026-09-28 09:15 UTC A100 precision and scope follow-up batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 258
- 266
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 09:15 UTC A100 precision and scope follow-up batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 09:15 UTC A100 precision and scope follow-up batch

- Prepared and ran four hash-bound Qwen3-32B-AWQ jobs on an NVIDIA A100 80GB using CC BY sources already approved for Colab processing. All four candidate results were reviewed against their selected source excerpts; result ZIP, bundle, Source, and excerpt hashes matched their manifests and Colab status records.
- Imported all four as unapproved candidate commits. The claims distinguish the approximately 200 ms mode of floor-transfer offsets in Heldner and Edlund's reviewed corpora from average FTOs; record that CAQDAS stores, organizes, and retrieves Framework Method data but does not itself analyze it; scope Hermann et al.'s interaction coding scheme to its five adolescent focus groups and separate try-out data; and record the seven categories and 21 concepts reported in Iseki's single clinical M-GTA application. Commit SHA-256 values: job 01 `52d364fd434706bfebda6e243770d140baa0f767010c12ebc860a0a040113f70`; job 02 `2b3ded773a4ef201bac0d790e37f566ddb3fa1cdecb5b2b00181f91735d3a6be`; job 03 `92ad5e35e250f59f2b3cd88ce1a9bf5c0edb9709f3facb6e3a46ea25cd74231d`; job 04 `53f2771d321ab6ff1e486fa520b331782ff506c5300cccceedeafe9949af8fd5`. Full result, bundle, excerpt, and Source hashes are in `output/knowledge-colab-batch/b20260928t091530.json`.
- Inference totaled 3,262 input tokens, 436 output tokens, and 76.185 seconds, excluding runtime setup, package installation, and transfers. The first execution pass failed all four jobs because the runtime exposed Tokenizers 0.23.1. After installing Transformers 4.51.3, Tokenizers 0.21.4, and Hugging Face Hub 0.30.2, restarting the kernel, and verifying the imported module and distribution versions on the A100, all four jobs completed on the same generation. The session was stopped; Colab reported zero active sessions, 0.00 CU/hour, and an 89.64 compute-unit balance (0.67 CU below the pre-batch balance).
- No candidate was approved or published to a Knowledge Pack. The Software Vault literature notes and index were not changed in this batch.
- A read-only primary JobStore audit found 73 accepted Commits containing 72 Claim and 73 Source artifacts, with all artifact hashes and cross-record evidence checks valid; there are zero Knowledge Packs. All 17 expert domains have at least one source-backed Claim. The expert inventory remains at 17 definitions and 87 literature notes with zero unresolved references.
