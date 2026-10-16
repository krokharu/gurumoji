---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-11
title: 配布用専門家の知識・プロンプト制作計画：P2 文献権利監査の先行部分
summary: P2 文献権利監査の先行部分。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 470
- 485
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：P2 文献権利監査の先行部分

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### P2 文献権利監査の先行部分

- `source-audit`は既定の試行3専門家を維持しつつ、`--all-experts`と複数指定できる`--expert-id`で対象を選べる。Base-only Catalogの17専門家・108参照をmetadata-onlyで再監査し、定義エラー0、未解決参照0、status/correction status欠落0を確認。専門家ごとの参照・未解決・欠落・権利状態を集計する。
- LLM routeを許可するにはlicense IDとHTTPS license URL、明示的LLM処理許可、送信先allowlist、承認状態・審査者・日時・根拠を要求し、route別に判定する。許可文言の自己申告だけなら`review_pending`。OA表示・`full_text`・CC表記だけでは許可しない。
- 文献ノートはfrontmatterの閉じ・YAML解析・`note_type`・`literature_id`を照合し、欠落/不正/不一致を別状態で記録する。CLI出力は本文・絶対パスを含めず、locatorをDOIまたはHTTPS URLに制限し、各ノートのSHA-256でmetadataの版を識別する。
- DOI形式を検査して制御文字・バックスラッシュを拒否し、HTTPS locatorのquery/fragmentは出力しない。
- Sol再監修で、route別権利、参照frontmatter照合、locator出力制限の3指摘が解消し、確認範囲でブロッカーなし。
- `LIT-gale-2013-framework`は出版社の権利表示と[CC BY 2.0](https://creativecommons.org/licenses/by/2.0/)をSolがread-only確認。本文・図表を配布せず、出典付きの言い換えClaimに限定する条件で`local`・指定Colab・`export`を許可、一般`remote_llm`はプロジェクト方針で拒否する審査記録をノートに追加。
- `LIT-gilardi-2023-llm-annotation`はPNASの著作権表示でCC BY 4.0を確認し、同じroute制限・帰属・変更表示条件で許可metadataを追加。公式ページは第三者コンテンツの別権利を含み得るため、別許諾の図表・補足資料を除外し、本文アクセス範囲は従来のabstract記録のままにした。
- 検証: `python -m unittest discover -s tests -p test_manage_expert_knowledge.py -v` 9件成功。17専門家fixture、未知/不正/重複expert IDを確認し、`py_compile`と`git diff --check`成功。CLI全17件の結果は17専門家・108参照・未解決0・status/correction欠落0。metadata audit直後は権利未確認または審査pending 106だった。既定3件は13参照・未解決0・権利未確認または審査pending 12。監査はメタデータ照合であり、権利許可を推定・付与しない。
- `LIT-byrne-2022-reflexive-ta`はSpringer Nature公式記事ページのRights and permissions欄でCC BY 4.0を確認。知識ノートはabstract-scopeのまま、local・指定Colab・出典付き言い換えClaimのexportのみを許可し、remote_llmと本文・図表の再配布を除外。本文主張の審査やpeer-review状態の更新はしていない。
- 最新metadataの再集計は17専門家・108参照・未解決0・status/correction欠落0・権利未確認または審査pending 95。CC BY論文6件が専門家ごとの記録13件に現れる。
- `LIT-hermann-2024-fg-interaction-coding`はSAGE公式記事ページのRights and permissions欄でCC BY 4.0を確認。要旨のみを知識抽出対象とし、local・指定Colab・export routeを許可、remote_llmと本文・図表の再配布はプロジェクト方針で除外。Source noteにライセンスURL、確認者・日時・根拠を追記した。
- `LIT-delacre-2017-welch`は掲載誌IRSPの公式記事ページでCC BY 4.0を確認し、local・指定Colab・出典付き言い換えClaimのexportを許可。出版社が訂正記事DOI `10.5334/irsp.661`を案内しているため、権利承認とは別に、訂正内容の照合が終わるまでその資料に依存するClaimを承認しない。
- `LIT-mayring-2000-qca`はFQS公式記事ページにCC BY 4.0の表示があることを確認し、同じ3 routeを許可。`correction_status: not_checked`は維持し、権利承認と内容の正確性・訂正履歴の確認を分離した。
