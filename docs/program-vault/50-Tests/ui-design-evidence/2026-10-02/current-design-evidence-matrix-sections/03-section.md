---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-03
title: Gurumoji デザイン監査・証拠対応表：DG-03 失敗した分析の主見出しが「分析を実行しています」のまま
summary: DG-03 失敗した分析の主見出しが「分析を実行しています」のまま。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 52
- 84
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：DG-03 失敗した分析の主見出しが「分析を実行しています」のまま

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。

### DG-03 失敗した分析の主見出しが「分析を実行しています」のまま

- 優先度: P2
- 根拠: `src/gurumoji/static/analysis-execution.js:393-476`、`artifacts/design-sprint-20261003/static-design-probes.json`
- 影響: 失敗理由と再試行は存在するが、最大の見出しは継続中を示す。waitingも一律「再開できます」で、利用者の入力が必要な理由と処理回復を区別しにくい。通常結果への背景導線があるため、全結果へ到達不能とは判断しない。
- 最小案: 実行状態の文言表を1つ持ち、見出し・現在段階・チップ・操作・live通知を同じstateから導出。failed=停止/失敗、waiting=必要条件、cancelling=中止要求済み、cancelled=中止済み。完了済み成果と未完成部分を別枠で示す。
- 受入:
  - accepted/running/waiting/failed/cancelling/cancelled/completedをすべてfixtureで表示し、相互に矛盾する見出しや主操作がない
  - 公開だけ失敗なら公開のみ再試行。既存計算・外部AIを再実行しない
  - 停止後の完了済み結果へ到達でき、再試行・設定変更・確認待ち解除の違いを説明できる

### DG-04 保存履歴の直近100件上限がUIに出ず、古いrunへ進めない

- 優先度: P2
- 根拠: `src/gurumoji/analysis_store.py:274-296`、`src/gurumoji/static/analysis-storage.js:27-85`、`docs/program-vault/40-Design/ui-ux-issues.md:127`
- 影響: 100件を全保存数と解釈しやすい。過去の研究結果をUIで探し直せない。成果物削除ではない。
- 最小案: 短期は『直近100件を表示』と明示。次に総件数・次ページ・日付/手法/状態絞込を既存履歴へ追加し、安定したcreated_at+id順序で全runに到達させる。
- 受入:
  - 0/1/100/101件で上限・総数・ページ境界を区別する
  - 同時刻を含む201件でページ間重複/取りこぼしなし。選択したrunのID・入力版・出力が一致する
  - 比較履歴にも同じ上限表示・ページング契約を適用する

### DG-05 分析の入口が作業目的と分類方式を混在させている

- 優先度: P2
- 根拠: `src/gurumoji/templates/index.html:46-50,79-81`、`src/gurumoji/templates/views/analysis.html:111-139`、`src/gurumoji/static/app.js:1156-1206,5920-5959`、`src/gurumoji/static/analysis-visualizations.js:1014-1031`、`docs/program-vault/40-Design/decisions.md:401-407`
- 影響: 上部とサブナビに同じ分析入口があり、その下に自動/手動/手法別、全体/話者、概要〜出力が重なる。『結果を見る』『定義を変える』『比較する』の仕事から入口を予測しにくい。
- 最小案: 上部4入口は当面維持し、処理済みデータの重複サブナビを文脈ナビへ整理。分析内はADR-118の結果/比較/計画/データ・出力へ段階移行し、手法別は結果のfilter、手動コードは解釈作業として配置。
- 受入:
  - 既存#/new,#/data/<id>,#/analysis/<id>,#/speakersとquery形式の根拠リンクを維持
  - 保存済み結果を見るだけで計算/外部送信なし。以前のタブに戻って検索語・選択対象・未保存draftを保持
  - 初見テストで5代表タスクの最初のクリック、戻り回数、完遂/失敗を比較し、提案の優位性を実測する
