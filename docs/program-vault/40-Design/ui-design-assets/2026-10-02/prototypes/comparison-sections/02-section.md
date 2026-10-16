---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-comparison-section-02
title: Gurumoji：2案の低忠実度フロー比較：2 共通データと算術
summary: 2 共通データと算術。出典ノート「Gurumoji：2案の低忠実度フロー比較」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-comparison
source_path: 40-Design/ui-design-assets/2026-10-02/prototypes/comparison.md
source_sha256: e1e1cb01403af93a48b0bcef230d4b0336546f52a6ba6173e48ca7a30c9887a9
source_body_lines:
- 34
- 66
split_on: '2026-10-11'
---

# Gurumoji：2案の低忠実度フロー比較：2 共通データと算術

親索引・状態・確認版：[[40-Design/ui-design-assets/2026-10-02/prototypes/comparison]]。必要な本文だけを取得する。

## 2 共通データと算術

全例はこのレビュー用に作成した架空の内容である。実録音・実本文を使わない。

- 対象：相談会サンプル、全5発話、除外1。試行は**除外後の先頭4発話**。任意の代表サンプル選択機能を暗黙に追加しない
- 定義：duration列／duration規則／number／ratio／descriptive、出力speech_seconds、単位は秒、分析単位segment
- S001：00:00–01:00 → 60秒。S002：01:00–01:02 → 2秒
- S003：01:02–01:02 → 0秒。現在のvalid_timeはstart <= endを許す。これは有効な計算済みゼロであり、未発言者を補ったゼロではない
- S004：時刻不明 → null、missing_reason=invalid_source_value。画面では欠測。詳細原因は現行の一般reasonより細かく推定しない
- 有効3、欠測1。平均は(60+2+0)/3=20.666…秒を20.7秒と表示。欠測を0として15.5秒にはしない
- 除外S005は試行対象外。除外数は全体5発話と明確に対応し、試行の欠測数に含めない
- 根拠例：固定run R-demo-07、生成時入力rev12、現在rev13、引用E-002→発話S002。本文が変わった合成状態なので現在音声への再生は無効

## 3 画面への注釈と根拠

| 注釈 | 設計判断 | 根拠 | 現行／提案の区別 |
|---|---|---|---|
| 対象と表示版の帯 | 入力rev、run、対象集合、更新ありを同じ場所に置く | draft-DESIGN §3–5、監査DG-06/12、W04 | 固定viewerと全復帰契約は未実装の提案 |
| 入力列→規則を明示 | 名前と説明で任意の尺度を生成できると見せない | index.html:243–249、analysis-execution.js:50–64、analysis_core.py:151–198、DG-02 | rule等を読むJSはあるが、現行templateの対応欄は不足 |
| 個票の入力と値を対照 | 0と欠測を別表示し、入力との対応を検査する | analysis_pipeline.py:103–148,258–280、W02 | 現行trialには個票ID・理由・定義revisionがないためAPI拡張が必要 |
| 旧採用定義の保護 | 既採用を別draft IDへ複製し、取消で逆PUTしない | analysis_pipeline.py:245–253、definition-lifecycle-probe、W02 | immutable履歴schemaが現行であるとは主張しない |
| 明示採用 | 試行完了と研究者採用を別操作にする | analysis-execution.js:542–557、DG-02、reference-patterns A02 | 画面上レビューgateだけを永続保証にしない |
| 受理版を固定 | snapshot使用または版不一致停止を前提にする | W02、definition-full-pipeline-probe、analysis_pipeline.py:_run | レイアウト変更だけでは解消しない実行境界 |
| source/AI/研究者 | 原資料、AI下書き、研究者メモを色以外の文字で区別 | draft-DESIGN §3、reference-patterns A01/A02、B02 | 合成AI見解を新しく生成した結果として見せない |
| 根拠への往復 | 同じrun・filter・選択引用・scroll・focusへ戻す | analysis-content.js:45–122、W04、reference-patterns A01/B02 | 現行return stateは完全な提案契約を満たすと断定しない |
| 元の緑と紙色 | 既存のquietな作業面を継承し新しいブランドを作らない | style.css:12–52、draft-DESIGN §6 | SVGはNoto Sans CJKを代替使用。Windows実フォントの描画証拠ではない |

### 個票表示に必要な追加の境界

trialへrowsを追加するだけでは、この図の「入力時刻」と値を確実に照合できない。現在のmeasure_segmentsのrowsはID・話者・値・欠測理由を持つが、時刻・本文は持たない。試行に使ったsnapshotの入力値を応答に含めるか、その固定snapshotへIDで解決できる必要がある。最新の本文・時刻をjoinして試行時入力と表示しない。

これは「新しい入力保管システムを作る」という決定ではない。既存snapshot/input_hashを再利用できる範囲、固定入力に到達できない場合の表示、後方互換のresponse契約を先に確認する。入力照合ができない状態は採用前の未確認事項として表示し、個票を補完したふりをしない。
