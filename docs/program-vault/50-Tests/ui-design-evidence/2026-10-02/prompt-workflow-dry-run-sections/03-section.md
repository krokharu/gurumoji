---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-03
title: Gurumoji 設計プロンプト運用の質的dry-run：4 B01にテンプレートを適用したレビュー済みPLAN
summary: 4 B01にテンプレートを適用したレビュー済みPLAN。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 61
- 85
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：4 B01にテンプレートを適用したレビュー済みPLAN

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 4 B01にテンプレートを適用したレビュー済みPLAN

**目的:** 保存済み会話から目的の個別分析を見つけ、正しい対象と接続先で開始し、既存対応のある処理を中止し、旧結果を閲覧できる。T1で現行事実/仮説/未確認を分け、T10で証拠層を固定する。

### 最小変更と状態

1. 3種類の可視入口→既存handler→API→能力を対応付ける。テーマは`POST .../analysis/transformer`、見解は`POST .../analysis/insights`、分類は`runSegmentClassification`→`POST .../analysis/classifications`。分類payloadの`use_jev`とrevision/request_idを確認し、基礎pipelineへ転送しない
2. C01の一括非表示のうち対象controlとtoolbarを局所修正する。既存refresh関数が持つdisabled/取消条件を保ち、全selectorを無条件に表示しない
3. 見解の案内を実際のoverviewへ合わせる。処理/対象/接続先の短い説明を実能力に合わせる。実行環境のLM Studioを常に利用者PCと呼ぶ等の説明は設定と照合する
4. ready、dirty、provider/モデル不足、starting/running、cancel requested、失敗、旧結果の各状態を既存判定元から表示する。取消はTransformer/見解の既存対応を利用する。分類に同じcancel handlerは今回の読取で確認していないため、存在しない取消を表示せず、追加が必要なら別依存にする。失敗/取消を完了扱いせず、旧結果閲覧の入口を残す
5. 1440/390pxでは同じ3作業へ到達できる配置を保つ。表示順は対象と接続先→主操作→状態→結果。Tab/Enterで通常操作、visible focus、取消後focus復帰。320px/拡大では操作と説明が隠れない

### 受入証拠の計画

- B01-A: 一覧→会話A→各分析。production CSSでpointerとkeyboardの別走行、3入口の可視矩形/名前/disabled状態、画面記録。直接click/force/hidden解除は不許可
- B01-B: 合成stub・通信spyでitem/provider/source_revision/analysis_revision/request_idと正しいrouteを照合。連打時の実行要求1回、dirty/条件不足は開始0回、保存済み閲覧は新規実行0回
- B01-C: 開始後に会話Bへ移る、遅いA response、戻る、中止/完了競合。Bのdraftと対象を保持し、取消対応のある処理の実running中のcontrolが通常操作で届く。分類も対象移動後の遅いresponseを別検査し、既存の保護が十分だと推定しない
- 隣接handler試験は残しV1/V2として活用。V3は上記の通常経路を追加。V4/Windows/V5は実施環境が得られるまでnot-run。stub成功を実モデルの品質/接続成功にしない

### データと戻し方

保存schema変更なし。既存URL/DOM data属性、revision/request_id、run履歴、ノート所有境界を維持する。CSS/案内/小さいadapterに差分を限定し、戻すときも研究者の入力/生成済みrunを削除しない。入口を戻すと再び操作不能になる場合は、その制限と旧結果閲覧を明示し「問題解決済み」を撤回する。

**今回の結果:** C01〜C04/C12の文書・コード照合のみ。B01-A/B/Cは未実行。W01計画は局所修正のレビューに進めるが、UI受入済みではない。
