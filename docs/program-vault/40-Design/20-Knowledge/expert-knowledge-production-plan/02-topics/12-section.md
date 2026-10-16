---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-12
title: 配布用専門家の知識・プロンプト制作計画：P3 Base Pack候補ビルダーの中核
summary: P3 Base Pack候補ビルダーの中核。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 486
- 503
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：P3 Base Pack候補ビルダーの中核

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### P3 Base Pack候補ビルダーの中核

- `src/gurumoji/knowledge_builder/pack_builder.py`を追加。公開APIは正式Software Vaultの`SOFTWARE_ROOT`をBase-only `ExpertCatalog`で読む。17件全ての`01-Expert.md`原本hashと、既存validatorを通った実行定義hashからBase rootを作り、明示release pinと一致しなければstaging前に停止する。
- Packは受理済みCommitだけから作り、approved Claim、Source整合性、expert ID、distribution rights、private/local Source除外を再検証。Job ID・Source・Claim・定義出力を正規順序にし、再生成時のrootを決定的にする。
- manifestに`stage: internal_candidate`を追加し、root hashに含める。`register_pack/get_pack`成功は候補の記録であり、公開承認・ZIP配布ではない。P7でPack rootに結びつく別のimmutable ReleaseApprovalを導入し、17人の評価とP4復旧gateを通った場合のみ配布する。
- 通常の書込例外では作成済みstagingをrollback。プロセス強制終了では部分stagingが残り得るため、同Pack IDをfail-closedし、将来孤立stagingの運用清掃を加える。
- 検証: `tests/test_knowledge_builder_pack_builder.py` 7件、`tests/test_knowledge_builder_contracts.py` 15件、`tests/test_method_experts.py` 28件、`tests/test_method_expert_samples.py` 8件成功。対象3モジュールの`py_compile`と`git diff --check`成功。Sol read-only再監修でP3 builder / candidate-stageにブロッカーなし。
- 実文献のClaim・Colab実行・release pin承認は未実施。権利許可が確認できた文献は1件のみで、実Pack生成はまだ架空fixtureの境界検証のみ。

### P3 Base Pack候補のruntime reader

- `src/gurumoji/knowledge_builder/expert_knowledge_context.py`を追加。Directory/ZIPから候補PackをDB非依存で読み、外部root pin・manifest・全file hash・Source/Claim schema・専門家定義hash・ID照合を再検証する。候補Packは明示opt-inかつlocal route以外で拒否する。
- ZIPは展開せず、traversal、symlink、重複member、件数・単体/合計byte上限を検証する。Directoryにも件数・byte上限とread前のstat検査を適用する。
- 承認済みClaimをID順にpacket化し、Sourceとの根拠ID/hash/routeを検証する。最大256 Claims・512 KiBを超えるpacketはfail-closed。現在は関連度retrievalをせず全件を渡す仕様で、将来query-aware retrievalを別途実装する。
- Sourceにoptionalな`authors`、`publication_year`、`adaptation_notice`を追加し、著者・年・題名・DOI/URL・license・改変表示をpacketとpromptへ保持。未記録の著者や年は推測しない。Gale fixtureでPackからpromptまで保持されることを検証する。
- 検証: context 8件、contracts/JobStore 16件、Pack builder 7件成功。対象moduleの`py_compile`と`git diff --check`成功。Sol再監修でreaderの容量上限、Source ID/Claim一意性、候補限定のブロッカーなし。
- 候補Packはまだ一般配布不可。公開配布には別のReleaseApprovalとP7 gateが必要。原典の意味的groundingを評価するspan snapshotも未整備。
