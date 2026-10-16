---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-contract-section-01
title: Gurumoji UI設計指針：Gurumoji UI設計指針
summary: Gurumoji UI設計指針。出典ノート「Gurumoji UI設計指針」の分割本文。
parent_note_id: design-ui-contract
source_path: 40-Design/ui-design-contract.md
source_sha256: 0a2b9fa0a3c575013504d0f1d458a3927e626353dc7f4d65c1f326aea175c974
source_body_lines:
- 1
- 32
split_on: '2026-10-11'
---

# Gurumoji UI設計指針：Gurumoji UI設計指針

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-contract/00-Index]]。必要な本文だけを取得する。


# Gurumoji UI設計指針

第4稿 0.4 · 2026-10-02 UTC · レビュー用、提案機能は未実装  
確認HEAD: `88f5e3e`（0.3設計文書の統合）。ソース基準 `ddc23abe`、直近の実装 `59ebd24`

## 1 この文書の役割

日本語の録音を確認し、発話を直し、分析から根拠へ戻り、研究結果を保存する作業を支える。まず**実行入口と実際の処理、測定の説明と計算規則、表示結果と入力版を一致させる**。濃緑と紙色の静かな既存UIを土台にする。

この文書は設計意図と実装時の不変条件への入口。API・状態遷移・CSS値の正本は現行コード、判断の背景はSoftware Vaultとする。ここだけを読んで機能を実装済みと見なさない。Google DESIGN.md alpha互換や自動読み込みは主張せず、既存CSSと別のトークン正本を作らない。

- 実装順・受入・戻し方: [実装計画](../ui-design-implementation-plan/00-Index.md)
- 人の操作単位の仕様: [シナリオ](../../../50-Tests/30-Interface/ui-design-scenarios/00-Index.md)
- 必要な知識だけ読む入口: [知識索引](../ui-design-knowledge/00-Index.md)
- 参照製品から採る操作と避ける誤解: [公式参照パターン](../../ui-design-research/2026-10-02/reference-patterns.md)（実操作の比較試験ではない）
- 文献の訂正と適用範囲: [独立出典監査](../../ui-design-research/2026-10-02/source-review.md)
- 短い日本語と使える条件: [状態・文言仕様](../ui-microcopy-state-catalog/00-Index.md)（25箇所の案。新規不具合数ではない）
- 現行事実と詳細なコード位置: [監査](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md) / [DG対応表](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md)

## 2 現行事実と今回の判断を分ける

| 種別 | この案が扱うもの |
|---|---|
| 現行実装 | Flask＋HTML template＋素のJavaScript/CSS。上部4入口、作成3段階、1データの4作業タブ、M0〜M7サーバー永続pipeline |
| 確認した不整合 | DG-01: 個別実行入口のCSS非表示と案内先。DG-02: 手動定義の暗黙text_length、即採用、同ID上書き、受付版と実行版のずれ。DG-03: failed時の実行中見出し。いずれもソース／隔離プローブによる確認 |
| 既知の継続課題 | DG-04はUX-34の履歴100件上限。保存物の削除ではない |
| 今回の設計提案 | 版を示す共通帯、測定のレビュー段階、状態別の操作、用途別の色・文字役割 |
| 検証する仮説 | ADR-118のタスク別入口、根拠ペイン、密度調整が完遂率・理解・往復負担を改善するか |

原25件は**15 addressed / 10 UI partial / 0 open**を維持。UI10件は実装修正済み・修正版Windows GUI受入待ちであり、今回の新規バグ数へ加算しない。現行HEADの実画面／ATは未検証。旧 `4b311df` の画像やNode合成DOMを現行GUI合格の証拠にしない。
