---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-02
title: Gurumoji デザイン監査・証拠対応表：項目別の証拠・最小変更・受入
summary: 項目別の証拠・最小変更・受入。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 23
- 51
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：項目別の証拠・最小変更・受入

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。

## 項目別の証拠・最小変更・受入

### DG-01 個別のTransformer・AI見解・発話分類の実行入口がCSSで非表示

- 優先度: P1
- 根拠: `src/gurumoji/templates/index.html:235-236`、`src/gurumoji/static/style.css:2088-2093`、`src/gurumoji/static/analysis-content.js:184-187,561-564`、`src/gurumoji/static/analysis-method-view.js:254-264`、`src/gurumoji/static/analysis-execution.js:560-594`、`src/gurumoji/analysis_core.py:80-100,314-330`、`src/gurumoji/static/app.js:6760-6769`、`artifacts/design-sprint-20261003/adversarial-checks.md:H1`
- 影響: 画面の説明に従って移動しても実行ボタンが見つからず、設定やモデルの問題と誤認する。保存済み結果の表示やAPIの存在と、利用者が新規実行できることは別。
- 最小案: 基礎分析・テーマ分析・AI見解・分類それぞれの入口、実行条件、送信先、取消、現在の状態を能力表にする。まず対応済みの個別入口を明示復帰させるか、同じ確認パネルへ接続。実装していない統合runnerへ誘導しない。
- 受入:
  - 実DOMで通常表示・computed visibility・操作可能領域を確認する。role/nameからマウスとTab/Enterで入口へ到達できる。JS評価によるhidden要素.click()を合格根拠にしない
  - 条件不足では理由と設定入口を表示する。適格fixtureでは個別処理の確認まで進み、未承認の外部送信を行わず取消できる
  - 基礎分析ボタンだけでTransformer等も実行されたと表示しない。API/mock・CPU実モデル・外部API実行の受入を分ける

### DG-02 手動測定の規則・試行採用・固定した定義版の保証が不足

- 優先度: P1
- 根拠: `src/gurumoji/templates/index.html:243-249`、`src/gurumoji/static/analysis-execution.js:50-64,80-92,542-557`、`src/gurumoji/analysis_core.py:151-187`、`artifacts/design-sprint-20261003/static-design-probes.json`、`artifacts/design-sprint-20261003/adversarial-contract-probes.json`、`src/gurumoji/analysis_pipeline.py:45-50,209-280,332-365,494-499,635-644`、`src/gurumoji/analysis_core.py:346-369`、`artifacts/design-sprint-20261003/definition-lifecycle-probe.py`、`artifacts/design-sprint-20261003/definition-lifecycle-probe.json`、`artifacts/design-sprint-20261003/definition-full-pipeline-probe.py`、`artifacts/design-sprint-20261003/definition-full-pipeline-probe.json`、`artifacts/design-sprint-20261003/definition-lifecycle-evidence-manifest.json`
- 影響: 名前・説明を任意に書ける一方、測定対象はtext、規則text_length、数値・比率尺度・記述統計へ固定される。利用者が説明文を実行ルールとして受け取ると研究上の測定内容を誤認し得る。試行件数の表示後に採用へ直行するため、判断の区切りも見えない。 追加確認では、同じIDのdraft保存が旧adopted行を置換し、受付bindingにv1があってもworkerは同ID最新v2を読み得る。実UIの明示採用だけでは固定版保証が成立しない。
- 最小案: 入力列・規則・型・尺度・手法を対応範囲内で選択または読取専用要約として明示。『少数で試す→例と欠測・限界を確認→この定義を採用→全件実行』を分離。説明文は計算規則ではないことを示す。未提供のLLM尺度生成を装わない。 技術依存として、試行個票/欠測理由/定義版、編集中draftと旧adopted版の分離、受付したdefinition version/hashによる厳密な解決を追加する。最小安全策は版不一致時に計算前で停止し、将来のsnapshot/不変版方式を別途設計する。既存SQLの破壊的変更はしない。
- 受入:
  - 4入力だけを変更したときも、実際の規則が文字数であると開始前に読める
  - durationとtext_length、名義尺度+frequency等の対応組合せを正確に送信し、不適合は該当欄へ具体的理由を関連付ける
  - 試行終了時はdraft/trial-reviewed相当の表示に止まる。明示採用前にadopted PUT・pipeline POSTを送らない
  - 採用済み定義のrevisionと画面の測定要約が一致し、変更後の再試行・取消で旧採用版を壊さない
  - 同ID adopted v1→draft v2保存→取消/試行失敗でもv1を引き続き選択・再現でき、v2は未採用のまま分離される
  - 受付binding v1(text_length)→実行前に同ID v2(duration)へ更新する競合fixtureで、v1値3を使うか計算前に明示停止する。v2値60をv1としてcommitしない
  - trial結果にsampleのsegment ID/入力例/測定値/欠測理由/definition versionまたはhash/input hashが揃い、定義か入力の変更後に旧trialを採用根拠として流用しない
  - 採用・固定版のUI受入、API/SQLite競合回帰、全pipeline再開/再試行/公開を別々に検証する。分離manual stepの成功を全pipeline合格へ拡大しない
