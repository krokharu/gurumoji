---
note_id: template-literature-note
note_type: template
title: 文献ノートのテンプレート
status: current
updated: 2026-09-15
tags:
  - gurumoji/template
  - gurumoji/literature
---

# 文献ノートのテンプレート

文献ノートは `50-Analysis-Methods/20-Literature/<literature_id>.md` に1文献1ノートで作る。同じ文献を複数の手法で使う場合も1ノートにし、`related_experts` に並べる。区分の定義は [[50-Analysis-Methods/08-Common-Knowledge/02-Source-Classification]]。

- 学術文献は `LIT-<第一著者>-<年>-<主題>`、公式ページ・モデルカード等は `RES-<主体>-<主題>` とする。
- 査読状態は、掲載誌・会議の方針を確認できた場合だけ `confirmed` にする。DOIがあることは根拠にしない。
- 確認範囲（`access_scope`）を超える内容を書かない。要旨だけの文献から手順の詳細・数値を推測しない。ページ番号は本文で確認できた場合だけ書く。
- 本文は自分の言葉で要約し、全文や長い引用を保存しない。

````markdown
---
note_id: lit-<id>
note_type: literature
literature_id: LIT-<id>
title: "<原題>"
authors:
  - <著者>
year: <発表年>
venue: "<掲載誌・会議・媒体、巻号、ページ>"
source_type: journal_article | review_article | conference_paper | bulletin_paper | serial_article | interview_article | book | book_chapter | preprint | official_resource | model_card | report
peer_review: confirmed | not_peer_reviewed | unconfirmed
peer_review_basis: "<確認した根拠と確認日>"
doi: <DOI または空>
url: <URL>
accessed: YYYY-MM-DD
access_scope: full_text | abstract | bibliographic | official_page
access_detail: "<どの版を、どの経路で確認したか>"
correction_status: none_found | correction_published | not_checked
related_experts: []
status: current
updated: YYYY-MM-DD
tags:
  - gurumoji/literature
---

# <著者（年）>：<原題>

## 研究目的
## 対象データと研究条件
## 分析手順の要約
## 主要な知見
## 適用上の注意と限界
## 専門家の判断・手順に反映する内容
## 根拠の位置情報
## 未確認事項
## 関連ノート
````
