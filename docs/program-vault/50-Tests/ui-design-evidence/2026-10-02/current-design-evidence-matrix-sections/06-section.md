---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-06
title: Gurumoji デザイン監査・証拠対応表：DG-11 「結果を公開する」の保存先と含むデータを明示する
summary: DG-11 「結果を公開する」の保存先と含むデータを明示する。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 140
- 172
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：DG-11 「結果を公開する」の保存先と含むデータを明示する

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。

### DG-11 「結果を公開する」の保存先と含むデータを明示する

- 優先度: P2
- 根拠: `src/gurumoji/templates/index.html:267-268`、`src/gurumoji/static/analysis-execution.js:569-578`、`src/gurumoji/analysis_core.py:290-292,321-328`
- 影響: 利用者はWeb公開、外部AI送信、設定済みVaultへの書出しのいずれかを短いラベルから判断できない。実際のpayloadはinput/orchestrator/visualizationの3生成Vaultを対象とする。
- 最小案: 『設定済みの3つのVaultにも保存する』のような実態に即すラベルと、Vault名/実行環境/含む成果物/失敗時の回復を表示。保存先が未確認なら不明・未設定を明示する。
- 受入:
  - OFFではpublication_targets=[]、ONでは選択された実際の保存先が画面とpayloadで一致
  - 外部AI送信とVault書出しを別の確認として理解できる
  - 本体保存成功+Vault conflict/failed時に二軸の状態を出し、公開のみ再試行できる

### DG-12 motion低減とfocus/scroll復元を共通の操作契約にする

- 優先度: P3
- 根拠: `src/gurumoji/static/style.css:41-43,2079-2085`、`src/gurumoji/static/app.js:2212,5562,5579,8155-8156`、`src/gurumoji/static/analysis-content.js:76-122`
- 影響: CSS htmlのsmoothと直接smooth指定、motion-aware helperが混在する。画面再描画・根拠復帰でscrollとfocusを別々に扱っており、視点の復元品質を一括確認する必要がある。
- 最小案: 位置復元は対象ID+選択ページ+scroll+focus起点を記録し、reduced-motion下はscrollも即時。focusが消えたときは同じ項目/節の意味ある位置へ戻す。
- 受入:
  - motion低減ONでもナビ・削除undo・根拠遷移・発話追加に必要な位置移動は行うが、smoothなスクロールanimationは行わない
  - 根拠を開いて閉じると同じrun/ページ/引用とfocus起点へ戻る
  - 320px・200%拡大・ソフトキーボード表示中に入力focusや保存feedbackを固定バーが完全に覆わない

### DG-13 6段階/client説明とM0〜M7/server実装を同期する

- 優先度: P2
- 根拠: `docs/program-vault/20-Modules/ui-screens.md:20,28-43`、`docs/program-vault/40-Design/analysis-execution-ux-plan.md`、`docs/program-vault/40-Design/analysis-milestone-visualization-design.md:19-34`、`src/gurumoji/static/analysis-execution.js:1-12,439`、`src/gurumoji/analysis_core.py:80-101`
- 影響: 後続開発で既存pipelineを再実装したり、基礎pipelineがTransformer/推測統計まで扱うと誤解する危険。現行URL/入口の説明も3タブと4タブで差がある。
- 最小案: DESIGN.md冒頭にcommit付き現行能力・実装済み・未提供・受入待ちを置く。古い計画は経緯として残し、現行節へリンク。UI-10件partialを未実装へ戻さない。
- 受入:
  - M0–M7、基礎2手法+手動測定、JSON/CSV/ZIP、3生成Vaultと未提供出力の境界がコードと一致
  - 既存APIからのXLSXとpipeline固定packageのXLSX未提供を区別する
  - 旧25件と新DG項目が重複計上されず、各提案にsource/decision/testのリンクがある
