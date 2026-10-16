---
note_type: reference-section
status: current
feature: web-ui
verified: 2026-10-03
verification_scope: source-and-synthetic-handler-tests
updated: 2026-10-06
tags:
- gurumoji/program
- gurumoji/ui
note_id: program-ui-screens-section-04
title: Web UIの画面構成と既存機能の対応：互換性として維持したもの
summary: 互換性として維持したもの。出典ノート「Web UIの画面構成と既存機能の対応」の分割本文。
parent_note_id: program-ui-screens
source_path: 20-Modules/ui-screens.md
source_sha256: 848211ee88b8d60b2d3753a083c1936dd3ec29cdcf0f077c6bb1ea295598d8d9
source_body_lines:
- 74
- 97
split_on: '2026-10-11'
---

# Web UIの画面構成と既存機能の対応：互換性として維持したもの

親索引・状態・確認版：[[20-Modules/40-Interface/ui-screens/00-Index]]。必要な本文だけを取得する。

## 互換性として維持したもの

- APIの呼び出し、送信するフォーム項目名（`name` 属性）、保存・編集・分析のリビジョン確認は変更していない。
- `processed-data-hub`、`show-library-list-button`、`show-library-analysis-button`は処理済みデータ内の補助ナビ。基礎pipelineは`analysis-execution.js`、個別Transformer／AI見解は`analysis-content.js`、発話分類は`analysis-method-view.js`。個別入口は可視化し、aria-hiddenの旧再集計buttonだけ非表示を維持する。
- ブラウザー保存：`sessionStorage` の `gurumoji.activeJobId`、`gurumoji.pendingSubmission`、`gurumoji.bootSplashSeen`、`localStorage` の `gurumoji.ai-efforts` は同じキーで読む。
- 未保存の確認（文字起こし、話者管理、分析設定・準備記録）は、タブ・戻る操作・作業画面からの移動のすべてで `confirmLeave` を通る。

## 実装上の注意

- 実行中ジョブのID（`activeJobId`）と表示中のデータのID（`currentJobId`）を分けた。処理中に別のデータを開いて保存しても、ジョブの進捗・中止と混ざらない。
- スマホの固定バーが画面下に付くよう、`.app-main` の登場アニメーションは不透明度だけにしている。`transform` を使うと固定バーの基準がカードになる。
- 上部バーの高さは `--app-bar-height` で管理し、分析の固定ナビ・スクロール位置はこの値から計算する。


## 2026-10-03 分析UIの安全境界（V1/V2実装、V3以降は未受入）

- 実装checkpoint: `d3694b8`（基点`b02275b`、backend契約`9768b80`）。失われた旧ソースの復元ではなく新規修正。
- 分類・検索・相談・開始・取消・poll・再試行はitem/data/navigation/入力revision/編集世代とrequest所有者を照合。同itemの検索語・送信先・Transformer条件は保持するが、古い結果・loading・errorは新contextへ持ち込まない。
- 試行表は返された固定行をそのまま表示し、現在の本文・音声時刻を補完しない。採用には完全な`expected_trial`、全件実行には採用版mapと試行input hashを送る。採用版の編集は別IDの下書き。応答不明の採用はGET確認より前に再PUTしない。
- 4保存先はResearch/Input/Orchestrator/Visualization。非空API targetsは従来の3target集合で、Researchを含む4writerの実行証拠を別に表示する。legacyの証拠欠落は不明。package欠落・不整合／blocked recoveryでは再計算や不可用なretryを案内しない。
- `tests/test_analysis_ui_safety.py`はNode合成DOM・遅延fetch試験と実backendの4preset計算を束ねる。実データ、外部AI、モデル推論、ブラウザー、音声再生は使わない。固定checkpointの詳細証拠はクラウド作業領域`artifacts/eight-hour-20261003/analysis-ui`、独立確認は同`ui-review`。
- V3実画面・pointer/keyboard、AT、利用者理解・見た目の評価はブラウザー制約で未実施。非表示解除と合成DOM成功を通常操作のUI受入に読み替えない。
