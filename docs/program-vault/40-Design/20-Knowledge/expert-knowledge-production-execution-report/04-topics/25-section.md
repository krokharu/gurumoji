---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-25
title: 専門家知識制作・実行報告書：2026-09-28 11:33 UTC A100 descriptive-statistics API batch
summary: 2026-09-28 11:33 UTC A100 descriptive-statistics API batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 315
- 321
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 11:33 UTC A100 descriptive-statistics API batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 11:33 UTC A100 descriptive-statistics API batch

- Ran two hash-bound Qwen3-32B-AWQ jobs against the SciPy v1.18.0 official `stats.describe` API page. Both Claims were reviewed and accepted as unapproved candidates for `exp-descriptive-statistics`: default `axis=0` versus `axis=None` over the whole array; and `bias=False` applying bias correction to skewness and kurtosis, separate from `ddof` for variance. [Official SciPy API reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.describe.html).
- Commit SHA-256 values: job 01 `258add30cfab3825e63a61970044dc2781750e871825794c08204a04b752576a`; job 02 `5e487b0af2a1289d5c2adbf3eabea8fb2fdd58348a747eac104235ff47066e22`. Official documentation SHA-256 recorded in the Source is `66566c9dfdc18383000a0badfd29d550f8073edfd85c2686f8162d299e84960a`; separate paraphrased evidence snapshot SHA-256 is `9b9b1508df40e349a1a015e74692500010938b4662cdd3ab905bc481efc9c26e`.
- The first `colab new` call returned Service Unavailable, but server-side status showed the named A100 assignment had actually been created. Reused that single session; did not create a duplicate. Preflight verified A100-SXM4-80GB and Transformers 4.51.3, Tokenizers 0.21.4, and Hub 0.30.2. Inference totaled 1,463 input tokens, 215 output tokens, and 40.702 seconds. The session was stopped with 87.33 compute units remaining (0.22 CU below pre-session balance).
- A read-only primary JobStore audit verified 86 accepted Commit manifests, 85 Claim artifacts, 86 Source artifacts, coverage of all 17 expert domains, zero integrity errors, and zero Knowledge Packs. Updated the SciPy describe note, descriptive-statistics case table, and P6 progress. No candidate was approved or published.
