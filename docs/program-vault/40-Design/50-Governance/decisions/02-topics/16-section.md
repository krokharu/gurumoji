---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-16
title: 設計判断の記録（ADR）：ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る
summary: ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 494
- 526
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る

- **状態：** accepted、実装済み（2026-09-30）
- **背景：** 利用者が、Obsidian利用者の実践も踏まえた「整理・深さ・インデックス」と成果物品質の方針を承認した。ノート数や圧縮率だけでは成果物に役立つ知識か判断できない。
- **決定：** 利用者が必要な対象ノートを選び、整理と深さは根拠付きの確認記録、検索到達率は固定したローカル検索ケース、成果物は実際のプロンプト・出力・根拠抜粋に基づく固定基準のLLM採点で測る。LLMの新規タスク提案には不足と評価の改善点を渡す。削減率は補助指標とする。
- **結果・影響：** 確認記録・履歴を既存ConsoleのSQLiteに追加し、内容hashや設定revisionが変わった古い評価は無効とする。ノートは自動で上書きしない。比較条件が変わった履歴は分け、未評価を仮の点数で補わない。旧目標・タスクは保持する。
- **関連：** [[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index|a100-knowledge-control-plane-plan]]。評価方法は今回のアプリ独自の基準であり、Obsidian公式の評価規格ではない。


### ADR-122 分析要求を表示contextから分離し、固定試行の明示採用を全件実行の前提にする

- 日付: 2026-10-03 UTC
- 状態: 専用branch実装・V1/V2検証。V3実画面／AT／利用者理解は未受入
- 対象: W01〜W04、実装checkpoint `d3694b8`、backend契約 `9768b80`
- 判断: async要求はitem、data identity、入力revision、navigation／編集世代、要求tokenを固定する。遅いA応答でBの編集表示を変更しない。同itemの利用者入力と、旧要求の結果・busy状態を分ける。音声は最新の選択要求だけが保存／現在の有効時刻・本文・話者照合後に再生できる。
- 判断: 測定を4つの実装済みpresetへ限定し、保存→固定20件試行→明示チェック→採用→全件実行を分ける。単なる表示切替・試行・dialog表示では採用しない。完全なtrial CAS、採用版map、input hashでbackendの固定定義に接続する。採用版は編集せず新draftへ分岐。失われた採用応答はGETで確認してから次の書込みを許す。
- 判断: 簡単／詳細はnative radioの表示専用状態とする。明示入力を値の一致で「未編集」と推測しない。fixed trial rowへ現在の引用や時刻をjoinしない。
- 判断: statusとallowed_actions、recovery、4writerのpublication_attemptsを別々に表示する。failedを実行中、waitingを再開可能、legacy記録欠落を成功と呼ばない。固定packageの欠落・不整合を再計算で埋めない。
- 理由: DG-01/02/03/06の誤対象送信・暗黙採用・保存成功の誤認を避け、既存API／保存物bytes／研究者ノートの所有権を保つ。新frameworkやDB schemaは不要。
- 検証: 合成DOM・deferred fetch、4presetの実measure_segments、既存Python/API回帰。実データ・外部AI・モデル推論・移行・deployなし。通常ブラウザー到達がblockedのためV3以降を合格にしない。
- 戻し方: UI adapterを戻す場合もbackendの定義固定・CAS・4writer範囲・package検証を維持する。旧の暗黙採用や再計算fallbackを復活させない。


#### ADR-122 追記: 固定run閲覧と公開証拠の分離（2026-10-03）

- 対象source: `f31da55`、`5ac07ec`、`ce6e003`。既存query/storeを使う読取専用run-ID入口を追加し、実行結果から現在データを再計算する旧導線を廃止した。保存済みpackageのある待機／失敗からも閲覧できる。
- 保存要約・定義ID/版・測定表は固定JSON/CSVからのみ表示し、現在の本文・話者・役割・時刻で補完しない。表previewは20行/24列/セル256文字/本文16 KiB、JSONと保存要約も有限抜粋。省略を明記し、全件downloadのbytesを変えない。CSV空欄をnull・ゼロ・空文字へ推定変換しない。
- 本体の保存、hash/manifest整合、writerの実書出し、pipelineの進行台帳、科学的妥当性を分離する。公開応答のattempt/records/outcomesは単一read snapshotで読む。最新same-packageのfull-scope/full-executed/completed attemptだけを4writer成功の証拠とし、古いpipeline台帳の不一致は別表示する。閲覧で台帳を修復せず、成功済み公開の再試行を促さない。
- 保存条件の明示的な空配列、同run/hashの4台帳not_selected、記録不明を区別する。hash不一致・欠落、部分台帳、attempt欠落だけで対象外や成功を推定しない。旧保存scopeを拡張しない。
- GET、preview、ZIPは固定packageを検証するだけで、計算、復旧、公開、DB更新を行わない。欠落・破損・未対応形式は停止し、fallback再計算をしない。手法の追加、保存migration、実Vaultの変更はない。
- 検証は一時SQLite/filesと元JSの合成DOMのみ。`5ac07ec`固定tree全体で1012 passed/32 skipped/953 subtests、後続`ce6e003`の局所27 passed/39 subtests。GUI/AT/利用者理解は未受入。詳細はクラウド作業証拠 `eight-hour-20261003/fixed-run-viewer`。
