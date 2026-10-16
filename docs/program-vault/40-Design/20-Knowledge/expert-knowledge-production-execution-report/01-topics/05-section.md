---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-05
title: 専門家知識制作・実行報告書：2026-09-27 P2 SAGE rights audit
summary: 2026-09-27 P2 SAGE rights audit。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 93
- 104
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-27 P2 SAGE rights audit

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-27 P2 SAGE rights audit

- `LIT-hermann-2024-fg-interaction-coding`の書誌情報にあったCrossref由来のCC BY 4.0表示を、SAGE公式記事ページのRights and permissions欄で確認した。記事ページはCC BY 4.0で任意の利用・複製・頒布を帰属表示付きで許可している。[SAGE article](https://journals.sagepub.com/doi/10.1177/16094069241286848)、[CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en)。
- 文献ノートにlicense ID/URL、LLM processing permission、route allowlist、審査根拠・日時を記録。local、利用者が起動するColab A100、言い換えた出典付きClaimのexportを許可し、remote LLMはプロジェクト方針で拒否。第三者コンテンツと本文・図表の配布は対象外。研究知識の抽出範囲はabstract-onlyのまま。
- `source-audit --all-experts`で17専門家・108参照・未解決0・status/correction status欠落0を再確認。レビュー済みは5 unique papers、12 expert-reference rows。権利未確認または審査pendingは100から96へ減少。

### 2026-09-27 IRSP rights audit

- `LIT-delacre-2017-welch`の掲載誌International Review of Social Psychology公式記事ページにCC BY 4.0表示があることを確認し、ライセンスURL・LLM permission・route allowlist・審査根拠を文献ノートへ記録した。[IRSP article](https://rips-irsp.com/articles/10.5334/irsp.82)、[CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en)。
- 同ページは訂正記事DOI `10.5334/irsp.661`への案内も掲載。権利metadataは原論文のみを対象とし、訂正記事の内容は取り込まず、訂正が関係するClaimは内容照合まで承認しない。
- 全体の権利監査は4 unique sources・11 expert-reference rowsがレビュー済み、97/108 rowsが未確認または審査pending。これは権利metadataの確認であり、知識Claimの内容承認数ではない。
