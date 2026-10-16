---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-02
title: Gurumoji 設計プロンプト運用の質的dry-run：3 コード照合で固定した事実
summary: 3 コード照合で固定した事実。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 40
- 60
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：3 コード照合で固定した事実

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 3 コード照合で固定した事実

以下のpathは`app/`からの相対パス。行番号は上記HEAD時点での読取位置。

| ID | 確認した契約/不整合 | 読取根拠 |
|---|---|---|
| C01 | 個別実行/取消controlをCSSが隠す。API廃止を意味しない | `src/gurumoji/static/style.css:2088–2093`、`analysis-content.js:184–188,561–568`、`analysis-method-view.js:254–264` |
| C02 | 見解はoverview、Transformer/分類はcontent。説明は両者をcontentへ案内する | `static/app.js:6760–6769`、`templates/index.html:236` |
| C03 | Transformer/見解はdirty/実行中guardとrevision/request_idを持つ。分類は別handlerとPOST | `analysis-content.js:910–944,1156–1192`、`analysis-method-view.js:312–347`。分類に同じ取消能力があると推定しない |
| C04 | 基礎pipelineの能力と個別分析は同一でない | `analysis_core.py:80–105,311–338`。基礎pipelineのM0〜M7は存在し、全LLM役割/全手法ではない |
| C05 | 表示されない測定fieldのfallbackはtext/text_length/number/ratio/descriptive。試行後に自動adoptする | `templates/index.html:243–249`、`analysis-execution.js:50–64,542–557` |
| C06 | 定義PUTは同IDの行を更新しrevisionを増やす。trialはinput_hash/件数/有効valuesを返すが個票と定義revisionを落とす | `analysis_pipeline.py:229–280`。取消時の逆PUTは履歴復旧にならない |
| C07 | 名義/順序のdescriptive、durationの列/型などをvalidatorが制約する | `analysis_core.py:151–198`。自然文から任意の尺度を作る能力ではない |
| C08 | startはplan/binding/input snapshotを保存するが、workerはdefinition IDから現行payloadを再読する | `analysis_pipeline.py:332–389,635–644`、[既存lifecycle probe](../definition-lifecycle-probe.json)、[既存M0〜M7 probe](../definition-full-pipeline-probe.json) |
| C09 | 根拠detailsと音声前の本文/話者/時刻比較は既にある。戻りstateはmode/scope/speaker/scroll等で、完全な固定run/page/filter/focus一式の保証はない | `analysis-content.js:45–127`。機構全体を新規未実装と扱わない |
| C10 | run履歴にartifact URLがあり、artifact読取はhash照合を行う。現行「結果」buttonは現在itemの読込へつながる | `analysis_store.py:304–321`、`analysis-storage.js:43–69`、`analysis-execution.js:651–655` |
| C11 | pipeline status取得はinterrupted/waiting条件でretryを起こし得る | `analysis_pipeline.py:752–770`。GETであることだけをread-onlyの証明にしない |
| C12 | content試験にはDOMの直接clickがあり、Transformer fixtureにはproduction CSSがない | `tests/test_content_browser.py:72,147–148,184–189`、`tests/test_transformer_content_browser.py`のfixture。既存試験の価値とV3到達証拠は別 |

C08の既存M0〜M7 probeはbinding v1に対してdefinitions v2、文字数なら3の入力がdurationで60となり、save adapterへ渡った記録を持つ。合成adapter・一時SQLiteでの記録であり、実ファイルに誤結果が保存された/利用者が遭遇したとまでは述べない。
