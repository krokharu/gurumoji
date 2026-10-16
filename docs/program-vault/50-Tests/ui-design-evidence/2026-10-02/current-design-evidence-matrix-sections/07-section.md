---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-07
title: Gurumoji デザイン監査・証拠対応表：DG-14 空状態・概要・詳細の縦方向密度を主作業に合わせる
summary: DG-14 空状態・概要・詳細の縦方向密度を主作業に合わせる。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 173
- 222
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：DG-14 空状態・概要・詳細の縦方向密度を主作業に合わせる

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。

### DG-14 空状態・概要・詳細の縦方向密度を主作業に合わせる

- 優先度: P3
- 根拠: `artifacts/ui-review/local-evidence/extracted/screenshots/speakers-390.png`、`artifacts/ui-review/local-evidence/extracted/screenshots/analysis-statistics-390.png`、`src/gurumoji/templates/views/speakers.html:16-34`、`src/gurumoji/static/style.css:938-958,2337-2346`
- 影響: 旧390px画像では話者の入力カードより前に概要・案内・検索が並び、統計はデータ不足の大きなカードが連続する。重要な安全説明を削らず、作業開始までの距離を減らす余地がある。
- 最小案: 話者の追加後は追加カードを表示域/focusへ。概要は必要な件数と未保存状態を短くまとめる。空の分析は理由・必要条件・次の行動を1つのコンパクトな状態部品で表現し、空カードを単純羅列しない。
- 受入:
  - 0件/1件/多数件、検索0件、全データ欠測を別fixtureにし、次操作が具体的
  - 警告と分母・欠測条件を折りたたみ過ぎて隠さない
  - 同一viewportのbefore/afterで主作業到達スクロール量・行動数を比較し、改善を測定する

## DG-02の内訳と数え方

上位監査IDは14件のまま。DG-02-U1/U2は元のUI指摘を分解したもの、T1は必要な試行契約、T2/T3は独立に再現したP1技術課題。原25件へ合算せず、T2/T3をUI文言問題だけに埋めて過小報告もしない。

### DG-02-U1 / P1 / 既存DG-02のUI意味不整合

構造化規則の5selectorがなくtext_length/number/ratio/descriptiveへ暗黙固定

根拠: `static-design-probes.json`, `adversarial-contract-probes.json`

### DG-02-U2 / P1 / 既存DG-02の採用操作不足

少数試行後に研究者の値レビュー待ちなしでadoptedへ進む

根拠: `src/gurumoji/static/analysis-execution.js:542-557`, `static-design-probes.json`

### DG-02-T1 / P2 / 試行レビュー実装に必要なAPI契約拡張

trialはinput_hash/values/件数のみ。segment ID付き個票・欠測理由・定義revision/hashがなく、根拠付き試行レビューを現APIだけで完全には作れない

根拠: `src/gurumoji/analysis_pipeline.py:258-280`

検証範囲: ソース確認。豊かなレビュー表示の依存であり、個票UIが既に存在するという主張ではない

### DG-02-T2 / P1 / 独立再現した採用版保全の技術課題

同IDのadopted v1→draft v2で同じDB行のpayload/statusを置換。旧adopted版をこの定義台帳から選べなくなる

根拠: `src/gurumoji/analysis_pipeline.py:45-50,227-256`, `definition-lifecycle-probe.json:existing_adoption_after_draft_save`

検証範囲: 合成in-memory SQLite。row count1、status draft、adopted lookup definition_not_adopted。既存出力や全履歴が消失したとは判断しない

### DG-02-T3 / P1 / 独立再現した固定定義版の実行不整合

binding v1受付後に同IDをv2へ更新するとworkerは最新v2を読み、v1の3文字ではなくv2の60秒を算出。合成adapters付き元M0〜M7でもcompletedとなり、save adapterへbinding v1とdefinitions v2が混在したpackageを渡す

根拠: `src/gurumoji/analysis_pipeline.py:209-225,332-365,494-499,635-644`, `src/gurumoji/analysis_core.py:346-369`, `definition-lifecycle-probe.json:definition_version_race`, `definition-full-pipeline-probe.json`

検証範囲: 第1証拠は元worker prefix+manual stepの分離実行。第2証拠は受付後scheduleを停止して定義を更新し、元M0〜M7オーケストレーター全体を実行。全段committed・pipeline completed、save adapterへbinding v1/definition v2/値60のpackage。method/save/publication adaptersは合成、SQLiteは一時領域。実保存ファイル/Vault/実手法/GUIは未実施
