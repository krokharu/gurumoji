---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit-section-02
title: Gurumoji 現行デザイン監査と実装可能な改善計画：2. 今のアプリを正しく理解する
summary: 2. 今のアプリを正しく理解する。出典ノート「Gurumoji 現行デザイン監査と実装可能な改善計画」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md
source_sha256: 29fdac89e90f723f623c7a6e660b4bd780c77d975d1bfbc6d6ada363dc6aeaff
source_body_lines:
- 28
- 64
split_on: '2026-10-11'
---

# Gurumoji 現行デザイン監査と実装可能な改善計画：2. 今のアプリを正しく理解する

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-audit]]。必要な本文だけを取得する。

## 2. 今のアプリを正しく理解する

### 2.1 現行の情報構造

| 層 | 現在の構造 | デザイン上の扱い |
|---|---|---|
| 全体 | 動画・音声を文字起こし／文字起こし結果／分析・可視化／話者管理 | 上部4入口と互換URLを維持する |
| 一覧・分析の補助ナビ | データ一覧／分析・可視化 | 上部と同じ分析入口を重複表示。移行時は文脈ナビ・戻り口へ役割を限定 |
| 1データ作業 | 発話の確認・編集／会話・話者／議事録・アウトライン／ファイル・管理 | 研究者の編集・確認単位として維持 |
| 分析モード | 自動分析／設定・手動分析／手法別 | 作業目的より実装・処理分類に近い。ADR-118の段階移行対象 |
| 自動分析内 | 全体／話者、概要／内容・文脈検索／会話推移／言語構造／統計／出力・検証 | 結果の主題別閲覧は再利用し、現在位置を見失わない |
| 基礎分析の開始 | 共通dialog、自動実行／手動実行、O01計画候補、Vault書出しoption | 実際はM0〜M7の永続pipeline。現行能力を明示 |
| 複数会話比較 | 分析画面の下部に折りたたみ、基準＋2〜8件、履歴あり | 比較作業の独立した入口へ段階移行できる |

根拠: [index.html](../../../../../../src/gurumoji/templates/index.html#L46)、[analysis.html](../../../../../../src/gurumoji/templates/views/analysis.html#L111)、[app.jsナビ](../../../../../../src/gurumoji/static/app.js#L1156)、[分析ページ](../../../../../../src/gurumoji/static/analysis-visualizations.js#L1014)。

### 2.2 既存の強みと、壊してはいけない条件

- 新規作成はファイル→設定→開始。段階的に詳細を開き、desktop/mobileで同じフォームを使う
- 文字起こしの処理中と編集中データのIDを分離。別データで作業中に処理完了しても勝手に作業を置き換えない
- 未保存の文字起こし、話者、分析設定、準備記録を移動時に守る。保存中に増えた変更も単純に保存済みへしない
- 話者CSVはプレビュー→未保存編集→通常保存。削除undo、失敗通知、競合draft退避、live regionは今回以前の改善に含まれる
- 根拠引用は生成時の本文・時刻・話者と照合。入力変更後の引用を無言で現在音声へつながない
- 分析は欠測、未実行、参照値、更新必要を区別する方向の保護を持つ。参加者名簿がないのに未発言者を0秒と補完しない
- グラフの代替表やCSV、方法の注意、対象集合・分母、保存済みrunの来歴を保持する
- 研究者の本文・タグ・別名・ノートを、見た目の変更のついでに上書きしない

根拠: `app.js:1111–1135,1247–1259`、`analysis-content.js:45–122`、`analysis-storage.js:43–69`、原25件受入表。ここに挙げた対策も現在の実GUI合格を意味しない。

### 2.3 古い設計文書と現行コードの差

`ui-screens.md` は「3つの上部タブ」「6段階」「画面側で順番に実行」「永続pipelineは後続」とする。一方、現在のtemplate/JS/backendは上部4入口とM0〜M7のサーバー永続pipelineを持つ。

新しい `analysis-milestone-visualization-design.md:19` は初回導入範囲を実装済みと明記する。したがって「永続化が未実装だから作る」という計画は誤り。現在の基礎pipelineの手法は発話量・会話の時間構造・手動測定で、47成果物、7つのLLM役割、全推測統計が一斉に提供されたわけでもない。

また、既存の通常分析APIのExcel出力と、pipeline固定packageからのXLSX未提供は別。両方を「Excel対応／非対応」の一語にまとめない。
