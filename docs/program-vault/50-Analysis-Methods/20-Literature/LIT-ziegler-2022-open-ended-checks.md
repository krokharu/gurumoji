---
note_id: lit-ziegler-2022-open-ended-checks
note_type: literature
literature_id: LIT-ziegler-2022-open-ended-checks
title: "A Text-As-Data Approach for Using Open-Ended Responses as Manipulation Checks"
authors:
  - "Jeffrey Ziegler"
year: 2022
venue: "Political Analysis"
source_type: "method_article"
peer_review: "unconfirmed"
peer_review_basis: "The source note does not record evidence confirming this article's peer-review status."
doi: 10.1017/pan.2021.2
url: https://doi.org/10.1017/pan.2021.2
accessed: 2026-09-28
access_scope: full_text
access_detail: "Publisher HTML article captured locally; selected paragraph text normalized for whitespace. Full capture digest is recorded in Source.sha256."
document_version: "publisher-html-captured-2026-09-28-sha256-09ad66c0ad0f86a3"
document_url: https://doi.org/10.1017/pan.2021.2
document_sha256: 09ad66c0ad0f86a3bc8f28dbe151f5323bfd05814c2eed43473da85971805e9c
license_id: CC-BY-4.0
license_url: https://creativecommons.org/licenses/by/4.0/
llm_processing_permission: explicitly_permitted
llm_allowed_routes:
  - local
  - colab
  - export
rights_review_status: approved
rights_reviewed_by: "Codex GPT-6 (read-only)"
rights_reviewed_at: 2026-09-28T04:25:58Z
rights_review_basis: >-
  The Cambridge article page identifies this as open access under CC BY 4.0 and links to the license. The full publisher HTML was captured; only selected paragraphs are sent to Colab. The claims must remain scoped to open-ended manipulation checks and the paper?s design conditions. No participant responses are included.
correction_status: not_checked
related_experts:
  - exp-quantitative-text-analysis
status: current
updated: 2026-09-28
tags:
  - gurumoji/literature
  - gurumoji/analysis
---


# オープンエンド回答をマニピュレーションチェックに使うテキスト分析法

## 研究の問いと設計条件

参加者に文章の指示や物語を提示し、その内容を短く言い換えて回答させる実験を対象とする。提示文と回答の文書類似度を計算し、回答者が課題に注意を向けた程度を連続量として測る方法を提案する。これは自由回答一般の質や、会話参加者の注意・理解を測る方法として検証されたものではない。

## 類似度の表現方法

著者は、入力や転記に含まれる綴り・文法の揺れへの対処として文字n-gramを使い、小規模文書では3-gramを推奨する。例では、各回答と対応する提示文を文字3-gramの頻度ベクトルにし、その類似度を計算する。

## 適用上の注意と限界

- 方法は文章のプロンプトを前提とし、画像や動画だけのプロンプトには適用できない。
- 著者は、文章を処置として提示する実験では、内的妥当性を保つため対照条件にも文章を使う設計を推奨している。
- ここでの類似度は、特定の実験設計における注意の指標案であり、回答内容の質や真偽を示さない。別の言語、会話逐語録、一般的な自由回答への適用は別途検証が必要。

## 根拠の位置情報

出版社HTMLの「Open-Ended Manipulation Checks as Data」「Selecting Similarity Metrics to Measure Attention」。全文HTMLを取得し、該当節の選択箇所を確認。
