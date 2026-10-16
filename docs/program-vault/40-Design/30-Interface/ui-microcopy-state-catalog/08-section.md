---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-microcopy-state-catalog-section-08
title: Gurumoji 日本語UI文言と状態の仕様案：9 根拠と今回の検証範囲
summary: 9 根拠と今回の検証範囲。出典ノート「Gurumoji 日本語UI文言と状態の仕様案」の分割本文。
parent_note_id: design-ui-microcopy-state-catalog
source_path: 40-Design/ui-microcopy-state-catalog.md
source_sha256: a380e655813a51346e817cb6f36f5fea46e2e56045e8019aa10d9ef5c0b64d29
source_body_lines:
- 233
- 248
split_on: '2026-10-11'
---

# Gurumoji 日本語UI文言と状態の仕様案：9 根拠と今回の検証範囲

親索引・状態・確認版：[[40-Design/30-Interface/ui-microcopy-state-catalog/00-Index]]。必要な本文だけを取得する。

## 9 根拠と今回の検証範囲

広い文献調査は繰り返さず、既存の[UX出典台帳](../../ui-design-research/2026-10-02/ux-source-ledger.json)、[出典監査](../../ui-design-research/2026-10-02/source-review.md)、[UX知見](../../ui-design-research/2026-10-02/ux-research.md)の確認範囲を再利用した。今回の日本語の語句、色の役割、通知間隔はGurumojiへの設計推論であり、一次資料がこの文言の効果を保証するものではない。

| 根拠IDと一次資料 | この仕様で支える判断 | 限界 |
|---|---|---|
| UX:S12 [原著者のUsability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) | 状態を見せる、利用者の言葉にする、エラーからの回復を示す | 一般指針。日本語案の比較効果ではない |
| UX:S13 [Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | 通常表示と技術詳細を分ける | 必要な限界や保存先まで隠してよい根拠ではない |
| UX:S01 [Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/) | AIの能力・限界・制御・修正を明示する | 個別の日本語表現や現在の生成AIの効果量ではない |
| UX:S22 [WCAG 2.2](https://www.w3.org/TR/WCAG22/)／UX:S26 [Status Messages解説](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) | 状態をフォーカス移動なしで支援技術が提示できるようにする | 規範はS22。秒ごとの読み上げや特定の間引き秒数を要求していない |
| UX:S31 [Carbon Loading](https://www.carbondesignsystem.com/building-blocks/core/patterns/loading) | 処理範囲と確かめられる進捗に合う表示を選ぶ | 製品指針。残り時間の推測や進捗の捏造を認めない |
| UX:S17 [SRQRの原論文](https://med.stanford.edu/content/dam/sm/chri2/documents/O%27Brien%20et%20al.%20-%202014%20-%20Standards%20for%20Reporting%20Qualitative%20Research%20A%20Sy.pdf) | 解釈と根拠の関係を追えるようにする | 報告の完全性は研究の妥当性そのものではない |

実施したこと: 上記HEADの関連コード・設計資料の読取、25箇所の現行文字列照合、状態・handler・backend応答の静的突合、指定したv2の3PNGの画素確認、参照先と文書構造の確認。追加根拠は独立した[合成契約probe](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)で、AI見解のpayload範囲と、保存先・完了状態の経路を確認している。AI captureの対照では除外発話、専門家note全文、文献全文は送られていない。該当する付与情報と短い専門家説明を送ることから、全文送信へ拡大解釈しない。[操作分岐probe](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-action-probes.json)では元JSのrenderer／handlerを合成DOMへ適用し、failed／retry actionなしの操作が設定を開くことも再現した。詳細とconfig上の限定は[独立契約確認](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md)にまとめられている。

実施していないこと: source変更、コードcommit/push、実アプリ起動・通常操作、実API送信、実モデル、外部AI、実データ、実Vault、実AT、利用者評価。したがって文言の実装完了、アクセシビリティ適合、使いやすさの改善は未確認。
