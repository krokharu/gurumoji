---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-14
title: 専門家知識制作・実行報告書：2026-09-28 05:49 UTC A100 three-domain evidence expansion batch
summary: 2026-09-28 05:49 UTC A100 three-domain evidence expansion batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 222
- 229
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 05:49 UTC A100 three-domain evidence expansion batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 05:49 UTC A100 three-domain evidence expansion batch

- Ran six hash-bound jobs on an NVIDIA A100 80GB with pinned Qwen3-32B-AWQ. The sources covered conversation timing (Levinson & Torreira 2015), focus-group interaction coding (Hermann et al. 2024), and M-GTA in a clinical application (Iseki 2023). All six result ZIP hashes matched their Colab status records. Recorded inference totaled 139.426 seconds, 5,799 input tokens, and 781 output tokens; runtime setup and transfers are excluded.
- Imported all six reviewed outputs into the primary JobStore as unapproved candidate commits. The claims cover the 348-conversation Switchboard subset and overlap denominators; Hermann's eight interaction codes and transcript-quality/applicability limits; and Iseki's M-GTA description, case-specific analysis workflow, and analysis review trail. The per-job commit SHA-256 values are recorded in `output/knowledge-colab-batch/b20260928t051400.json` and its progress file. No candidate was approved or published to a Knowledge Pack.
- Source snapshots were licensed CC BY 4.0: Hermann's full-text PDF from Uppsala University DiVA (SHA-256 `a80d7ec05530f1d6e34bdad1d6a3840cd498dd8fc5764533c032280434b8f32b`), Iseki's PubMed Central full-text HTML (`2c9f4fc3dbf2ff8c051f7b4dbe68d9599f659ceb9b907207b3e8ff1a573c69cc`), and Levinson & Torreira's Frontiers full-text HTML (`2bee897da2f719cc1ef4ed45346744a78dcacc4db5f73063da755269de3fd43d`). Each input excerpt and result was bound to its source, bundle, and job hashes in the batch manifest.
- The first worker start found an outdated Tokenizers package; installing the pinned 0.21.4 version and restarting the kernel allowed inference to proceed. The first acceptance call also used the wrong companion registry filename; correcting it allowed all six commits to be accepted. The A100 session was stopped after import.
- Updated the Software Vault literature index and source notes, added Iseki's application note, and revised the M-GTA, focus-group interaction, and thematic-analysis case references. These notes distinguish the single clinical application from general M-GTA method authority and record the source-supported scope of Hermann's coding scheme.
