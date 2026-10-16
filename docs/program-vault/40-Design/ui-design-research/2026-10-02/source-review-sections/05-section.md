---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review-section-05
title: Gurumoji 設計調査の独立出典監査：URLと出版記録の問題
summary: URLと出版記録の問題。出典ノート「Gurumoji 設計調査の独立出典監査」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review
source_path: 40-Design/ui-design-research/2026-10-02/source-review.md
source_sha256: 444a9f0716d8b24c2d90b4ab5ddd61f1c7727e707a5c9d4bb7b1e547494f42d5
source_body_lines:
- 129
- 152
split_on: '2026-10-11'
---

# Gurumoji 設計調査の独立出典監査：URLと出版記録の問題

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/source-review]]。必要な本文だけを取得する。

## URLと出版記録の問題

**取得失敗と不存在は区別する。** この監査で採用URLの404や不存在を確定したものはない。

| URLまたは項目 | 観測 | 扱い |
|---|---|---|
| S15の著者FAQとeditor-checklist | 直接openはtimeout/502。著者サイトの検索索引に該当内容あり | 「検索抽出確認」を維持し、全文取得済みにしない |
| OpenReviewのR4 forum/PDF | ブラウザー確認画面 | 回避操作はせず、取得可能なICLR公式出版記録で確認 |
| S19 DOIのACM直接取得 | 内部取得エラー | DOI不存在とはしない。Monashの出版記録で補う |
| S32 DOIのPNAS直接取得 | 内部取得エラー | 著者資料に取得経路を限定。今回は数値の格差率を新規採用しない |
| R2およびS18のarXiv HTML内の仮DOI・仮ISBN | テンプレートのプレースホルダーを含む | 仮DOIをリンク・出版証拠として転記しない。論文URL自体は有効 |
| Google DESIGN.mdのmain URL、各社の動的ドキュメント | 将来内容が変わる | 閲覧日・対象モデル・節を残す。厳密な再現性が必要ならcommit permalink/正規リリースを別記 |
| Google DESIGN.mdのStitch側仕様ページ | 元台帳で本文未取得として除外 | GitHub公式仕様への代替は妥当。除外URLを閲覧済み本文に数えない |

## 因果と選定の偏り

- ベンダーの公式ガイドは製品機能と推奨の一次資料として有用だが、各社に宣伝上の利害がある。同じ方向の助言が複数社にあることを、独立した複数実験の再現と数えない
- Design2Code、DesignBench、WebGenは異なる入力・課題・採点であり、数値を横並びにして製品順位を作れない。現状資料はその比較を行っていない
- ASR強調の無効果、説明の悪影響だけを選ぶと偏る。現状UXは、説明が検証費用を下げる条件で有益なS06も載せており、相反する結果の扱いは適切
- CollabCoderの採用率・自己評価や、Figmaの時間短縮だけを「研究の質」へ変換しない。根拠往復、残存誤り、保存の完全性をGurumoji側で測る必要がある
- 小標本の質的研究は仮説と問題発見を支える。研究者全体の需要、初心者・熟練者全体の平均効果を確定しない
- 英語圏・短時間・固定課題から日本語の長時間グループ研究への移植可能性は未確認。既存資料の「体系的レビューではない」という説明を残す
- 独自テンプレート、1440/390px、状態モデル、重大度の運用定義、ペルソナ、優先順位はプロジェクト判断である。論文がそのまま要求する仕様と誤表示しない
