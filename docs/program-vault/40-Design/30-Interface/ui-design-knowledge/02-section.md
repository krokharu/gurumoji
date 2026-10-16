---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-knowledge-section-02
title: Gurumoji 設計知識の入口：再利用する判断と出典
summary: 再利用する判断と出典。出典ノート「Gurumoji 設計知識の入口」の分割本文。
parent_note_id: design-ui-knowledge
source_path: 40-Design/ui-design-knowledge.md
source_sha256: 91d434fb547e4d56ecae2bd1c1b0f471f816a06c2e275bfe5735e8440a809428
source_body_lines:
- 38
- 61
split_on: '2026-10-11'
---

# Gurumoji 設計知識の入口：再利用する判断と出典

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-knowledge/00-Index]]。必要な本文だけを取得する。

## 再利用する判断と出典

出典IDは名前空間付きで書く。`UX:S22`は[UX台帳](../../ui-design-research/2026-10-02/ux-source-ledger.json)、`PR:R4`は[prompt台帳](../../ui-design-research/2026-10-02/prompt-source-ledger.json)。`DG-02`は現行コードの問題、`W02`は計画、`S02`はシナリオ。優先度P1とPR:P1を混同しない。

- **根拠へ戻るコストを小さくする:** UX:K01/UX:K05/UX:K13、UX:S04/UX:S06/UX:S17/UX:S20。説明量・採用率・主観的信頼だけを成功指標にしない
- **AI案と人の判断を分ける:** UX:K03/UX:K08、UX:S01/UX:S15/UX:S18/UX:S19。コードブック型とreflexive thematic analysisを同じ品質スコアへ押し込まない
- **意味・単位・分母を先に確かめる:** UX:K09、UX:S09/UX:S10/UX:S17。観測量から参加態度や合意を自動断定しない
- **必要な情報は消さず段階化する:** UX:K02/UX:K10、UX:S11/UX:S13。認知負荷理論は「余白を増やせ」「7個まで」の証明ではない
- **中止・待機・失敗・保存先を区別する:** UX:K11/UX:K12、UX:S12/UX:S26/UX:S31。残り時間や保存保証を根拠なく作らない
- **評価を分けて反復する:** PR:A4/PR:P1/PR:P2/PR:R1〜R4。静的画像一致、通常操作、保存契約、実モデル品質は異なる
- **短い入口と条件付き詳細を持つ:** PR:O3/PR:F2/PR:F3/PR:G4/PR:D1。形式・交換仕様・CSS実値・自動読み込みは別物

## 文献を使うときの重要な限定

訂正の原資料・確認範囲は[独立出典監査](../../ui-design-research/2026-10-02/source-review.md)を参照。

1. 本調査は体系的レビューでもモデルランキングでもない。公式ベンダーの推奨は製品の使い方の根拠であり、独立した効果量ではない
2. PR:R4のWebGen-Agentは、部分点付きGUIテスト精度26.4%→51.9%を報告。完成サイトの割合ではない。full YESは22.6%→45.6%。改善は評価・選択を含むシステム全体であり、1行のプロンプトの効果ではない。閲覧版はarXiv v1、発表は[ICLR 2026 poster](https://iclr.cc/virtual/2026/poster/10008256)と分ける
3. PR:R5の約20%短縮は成功完了した課題に条件付けた結果。デザイナー群の有意性の記述にも不整合があり、一般的な速度保証へ転用しない
4. UX:S03の信頼度強調は、36名・ドイツ語・短い音声・音声は一度再生してリプレイ不可という利用実験条件でWER改善を検出しなかった。無効果の証明ではない。欠落語除外は信頼度classifier評価に関する制約であり、利用者修正後WERから欠落誤りを除いたという意味ではない
5. UX:S18のCollabCoderは16名・8組、短い書評。日本語の長いグループインタビュー全体へ効果を一般化しない。UX:S02は今回抄録確認まで
6. WCAG本文は規範、Understanding／ARIA APGは解説／パターン。通常文字4.5:1、操作対象は原則24×24 CSS px、例外あり、focus非遮蔽等は個別条件を読む。44pxやFocus AppearanceのAAA面積要件をAAに混ぜない
7. Google DESIGN.mdは取得時alpha、DTCG 2025.10はCommunity Group Report。いずれもこのアプリが自動で従うことや、WCAG適合を保証しない
