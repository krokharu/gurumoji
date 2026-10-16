---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-01
title: Gurumoji UI改善の実装計画：Gurumoji UI改善の実装計画
summary: Gurumoji UI改善の実装計画。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 1
- 33
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：Gurumoji UI改善の実装計画

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。


# Gurumoji UI改善の実装計画

第4稿 0.4 · 2026-10-02 UTC · 実装承認前の計画  
確認HEAD `88f5e3e`（0.3設計文書統合）／ソース基準 `ddc23abe`・実装 `59ebd24`。本0.4更新はSoftware Vault内の文書差分で、コード変更・push・deploy・実データ移行を含まない。

## 1 結論と根拠の扱い

**先に既存の処理を正しく使えるようにし、その後で作業目的に沿った配置を試す。** P1はDG-01の可視入口とDG-02の測定意味・定義版の整合。DG-02はUIだけで完了しない。追加の文言監査で、保存targetと実書出し経路の不一致も確認したため、W03のscope対策をP1候補として先行判定する。IAや外観の改善効果は仮説であり、これらの修正条件にしない。

DG番号は[監査対応表](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md)。UX:S番号は[UX出典台帳](../../ui-design-research/2026-10-02/ux-source-ledger.json)、PR:番号は[プロンプト出典台帳](../../ui-design-research/2026-10-02/prompt-source-ledger.json)。文献は設計理由、ソース／probeは現行事実、実操作は受入を支える。それぞれ代用しない。

原25件の **15 addressed / 10 UI partial / 0 open** は[元受入表](../../../50-Tests/ui-design-evidence/2026-10-02/prior-25-acceptance-matrix.md)で維持する。今回14項目は新規不整合、既知課題、設計提案、旧画像由来の仮説の混在であり、「新規14バグ」と集計しない。

## 2 優先順と依存

工数は対象コードを読んだ概算の実作業量。1人の実装＋局所確認を想定した人日で、モデル取得、環境接続、Windows／AT待ち、利用者募集を含まない。合計を納期約束に使わない。

| 作業 | 根拠／種別 | 優先 | 概算 | 期待する影響 | 依存 |
|---|---|---|---|---|---|
| W00 現行能力・証拠を固定 | DG-13／文書不一致 | 前提 | 0.5日 | 未実装の二重開発と誤案内を防ぐ | なし |
| W01 個別実行入口を戻す | DG-01／確認済み不整合 | P1 | 2〜3日 | 主要分析を通常操作で開始できる | W00の能力表 |
| W02 測定定義を試して採用 | DG-02／確認済み不整合 | P1 | 5〜9日 | 名称・採用版・実計算の不一致を防ぐ | W00、definition／実行境界 |
| W03 状態と保存先を揃える | DG-03/11＋追加契約probe／不整合＋文言 | scope対策P1候補／表示P2 | 表示1〜2日、保存契約は再見積 | 待機・失敗・保存範囲の誤認を防ぐ | W00、publisher契約。W01/02と並行可 |
| W04 版と根拠の往復を示す | DG-06/12／設計提案 | P2 | 2〜4日 | 過去runと現在入力の取り違えを抑える | W03の状態語彙 |
| W05 目的名・contrast・focus | DG-09/10／コード＋指定色 | P2 | 1〜2日 | 中心操作の認識・操作性を改善 | W00。局所箇所は並行可 |
| W06 履歴の上限と全件導線 | DG-04／既知UX-34 | P2 | 表示0.5日、paging1〜3日 | 古いrunを発見できる | W04のrun文脈 |
| W07 タスク別入口を試作 | DG-05／ADR-118未実装 | P2 | 5〜10日 | 次の仕事を予測しやすくする仮説 | W01〜04、W06の一覧契約 |
| W08 日本語密度と狭幅を調整 | DG-07/08/14＋12／混合 | P2/P3 | 2〜4日 | 長文照合・現在地の読み取り改善仮説 | 現行描画取得、W05、対象画面安定 |
| W09 横断受入と記録 | 全体／回帰と引継ぎ | 各段階 | 1〜3日＋環境待ち | 原25件と科学的保護の維持 | 各Wの実装・対象版固定 |

W01→W02の直列固定は不要。template／analysis-execution.jsの同時編集は担当範囲と取り込み順を調整する。W07は低忠実度の構成比較を先に行い、全機能の新UI化を一括発注しない。
