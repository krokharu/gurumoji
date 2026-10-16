---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-01
title: Gurumoji デザイン監査・証拠対応表：Gurumoji デザイン監査・証拠対応表
summary: Gurumoji デザイン監査・証拠対応表。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 1
- 22
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：Gurumoji デザイン監査・証拠対応表

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。


# Gurumoji デザイン監査・証拠対応表

対象: `ddc23abe` / code `59ebd24`。原25件の受入表は変更しない。S=局所、M=複数部品、L=段階導入。日数は概算であり約束ではない。

| ID | 優先度 | 分類 | 結論 | 確度・規模 | 既存指摘との関係 |
|---|---|---|---|---|---|
| DG-01 | P1 | 現行コードで確認した導線不整合 | 個別のTransformer・AI見解・発話分類の実行入口がCSSで非表示 | 高（ソース。現行実ブラウザー未確認）／S〜M：1〜2日＋既存送信確認・取消の回帰 | 原25件とは別。旧統合実行UIと新しい基礎pipelineの境界 |
| DG-02 | P1 | 現行コード＋分離関数再現 | 手動測定の規則・試行採用・固定した定義版の保証が不足 | 高（Node合成DOM。実UI未確認）／M〜L：UI 2〜4日＋定義版/試行契約/競合回帰3〜5日の再見積り候補。単純な前面改修だけでは閉じない | 原25件とは別。M0〜M7の手入力定義フロー |
| DG-03 | P2 | 現行コード＋分離関数再現 | 失敗した分析の主見出しが「分析を実行しています」のまま | 高（Node合成DOM。実UI未確認）／S：半日〜1日＋状態別回帰 | 原25件とは別。新pipelineの状態表現 |
| DG-04 | P2 | 既知未対応の再確認 | 保存履歴の直近100件上限がUIに出ず、古いrunへ進めない | 高（ソース。今回のDB再実行なし）／S：上限説明／M：1〜3日でcursor付き履歴 | 既存UX-34。新しい発見として数えない |
| DG-05 | P2 | 既存設計の段階導入提案 | 分析の入口が作業目的と分類方式を混在させている | 高（現行構造）／改善効果は要利用者検証／M〜L：1〜2週、互換維持し段階導入 | ADR-118 accepted未実装。旧UI課題の再命名ではなく実装計画へ接続 |
| DG-06 | P2 | 表示設計の改善提案 | 現在データと固定runの由来を主画面で継続表示する | 高（表示場所）／誤認発生率は未測定／M：2〜4日。既存revision/run情報を利用 | A04/A05/A11/A12は修正済み。来歴欠落/誤出力の再指摘ではない |
| DG-07 | P2 | 旧版視覚所見＋現行コードの確認候補 | 狭い画面で選択中の分析ページ名が横スクロール域外に残り得る | 中。旧4b311df画像では確認、現行実画面は未確認／S：半日〜1日＋幅/拡大回帰 | 旧UI評価のS5改善候補。原UI-01〜10に追加していなかった項目 |
| DG-08 | P2 | 既知可読性課題の残存範囲整理 | 作成・分析以外の文字サイズと密度を共通役割へ揃える | 高（CSS指定値）。現行描画の可読性は未測定／M：2〜4日、画面単位で検証 | UX-17/41の改善を維持。全て小さい/未修正とはしない |
| DG-09 | P2 | CSS指定値の数値検証 | 補助文字・未保存色・共通focusのコントラストを用途別に補正する | 高（指定色の計算）／適合判定はcomputed styleと実画面待ち／S：半日〜1日＋全state回帰 | UX-19は既知未対応。UX-24のfocus有無修正は維持 |
| DG-10 | P2 | 現行ソースで確認したaccessible name不足 | 相互作用リンクの対象・関係selectに名称がない | 高（生成コード）。支援技術実測は未実施／S：半日＋名前/キーボード回帰 | 原UI-10（保存通知/tabpanel）とは別の部品 |
| DG-11 | P2 | 現行UI文言の境界不足 | 「結果を公開する」の保存先と含むデータを明示する | 高（template/payload）／S：半日〜1日＋公開OFF/競合回帰 | 原UI-09のOS/保存先修正は維持。新pipeline公開optionの補足 |
| DG-12 | P3 | 設計整備と回帰基準 | motion低減とfocus/scroll復元を共通の操作契約にする | 高（呼出混在）。体感/支援技術は未測定／S〜M：1〜2日＋入力/ナビ横断回帰 | 既存reduced-motion、focus-visible、根拠位置復元は実装済み |
| DG-13 | P2 | 設計文書の現行差分 | 6段階/client説明とM0〜M7/server実装を同期する | 高（文書・コードの直接比較）／S：半日。実装変更なし | DESIGN.md作成の前提。設計書のcurrentラベルを実装の証明にしない |
| DG-14 | P3 | 旧画像からの改善仮説 | 空状態・概要・詳細の縦方向密度を主作業に合わせる | 中。旧4b311df画像の所見。現行比較待ち／S〜M：1〜2日で試作・現行比較 | UX-07/35〜42の既存改善を保護。全面レイアウト不良とはしない |
