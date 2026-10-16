---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit-section-01
title: Gurumoji 現行デザイン監査と実装可能な改善計画：Gurumoji 現行デザイン監査と実装可能な改善計画
summary: Gurumoji 現行デザイン監査と実装可能な改善計画。出典ノート「Gurumoji 現行デザイン監査と実装可能な改善計画」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md
source_sha256: 29fdac89e90f723f623c7a6e660b4bd780c77d975d1bfbc6d6ada363dc6aeaff
source_body_lines:
- 1
- 27
split_on: '2026-10-11'
---

# Gurumoji 現行デザイン監査と実装可能な改善計画：Gurumoji 現行デザイン監査と実装可能な改善計画

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-audit]]。必要な本文だけを取得する。


# Gurumoji 現行デザイン監査と実装可能な改善計画

監査基準日時: 2026-10-02 18:20–19:06 UTC（2026-10-03 JST）  
対象: `dot/cloud-cpu-setup` / `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`、実装差分の直近 `59ebd24`  
作業: 現行コード・関連Software Vault・既存受入記録の読取、旧スクリーンショット5枚の画素閲覧、ソース分離Nodeプローブ。アプリコード変更・実データ操作・push・ローカルPC操作なし。

## 1. 結論

**見た目の全面刷新より、研究者が「何を実行したか／どの版を読んでいるか／次に何を確認するか」を理解して進められる設計を優先する。** 現行の紙色＋濃緑、3段階の新規作成、発話のコンパクト表示、4つの作業タブ、引用から音声へ戻る導線は継承できる。

先に解決すべき3点は以下。

1. **実行の入口と実態を一致させる（DG-01）**。画面はTransformer・AI見解の個別実行を案内するが、現在のCSSがその実行ボタンと分類ボタンを非表示にする。AI見解panel自体も案内された「内容・文脈検索」ではなく「概要」にある。新しい基礎pipelineはこの代替にはならない。APIがあることは人が使えるUIの証明にならない。
2. **手動測定を、意味を確認して採用するフローへする（DG-02）**。現行4入力欄は名前などだけで、実際の測定は本文文字数・数値・比率尺度・記述統計へ暗黙に固定される。少数試行後も研究者の確認を待たず採用される。さらに同ID編集で旧採用版が置換され、受付した定義v1と実行するv2が食い違う技術課題を再現した。測定規則の明示だけでなく、採用版の保全と固定版解決が必要。
3. **状態・表示版・保存先を一貫して見せる（DG-03/06/11）**。失敗中の大見出しが実行中を示す箇所がある。現在データ、固定run、計算完了、Vault書出し、研究者確認を1つの「完了」に潰さない。

### 判定の境界

- **原25件は再計上しない。** 既存レビューは15 addressed / 10 UI partial / 0 open。UI partialは実装がないという意味ではなく、修正版Windows実画面の受入待ち。原UI-01〜10、A01〜14、V01の完了状況を本監査で下げたり、ブラウザー未実施のまま上げたりしない。
- 今回の14項目は同じ性質ではない。新しいコード不整合、既知未対応UX-34の再確認、既存ADRの導入計画、旧画像からの改善仮説を区別した。**「14件の新規確定バグ」と数えない。**
- **現行HEADの実画面はこの監査では未確認。** 画素を見た5枚は元版 `4b311df` のWindows合成fixture。現在の余白・色・focus・文字潰れを測定したことにはならない。
- Nodeプローブは実ソース関数＋合成DOMであり、ブラウザー操作ではない。追加のPython検証は一時/メモリー内SQLiteを使った定義lifecycleと、合成adapters付きの元M0〜M7全体であり、実データや実出力ファイル/Vaultの受入ではない。独立担当の通常sandbox Chromiumも起動前のsocket制約で停止した。安全条件を緩めて再実行していない。
- P0に該当する新しい根拠は得ていない。上位のP1テーマはDG-01/02。追加調査でDG-02の内部に、別々に再現したP1技術課題T2（採用版保全）とT3（固定版と実行版の不整合）を明記した。「新規UI指摘を水増し」せず、「P1は2つだけ」と技術欠陥を過小報告もしない。原25件の判定とは別である。

証拠は[対応表](../current-design-evidence-matrix.md)、機械可読版は[JSON](../current-design-evidence-matrix.json)。独立反証は[adversarial-checks.md](../adversarial-checks.md)。原受入は[25件受入表](../prior-25-acceptance-matrix.md)。
