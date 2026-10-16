---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks-section-02
title: 'Gurumoji デザイン監査の独立反証チェック：H2: 旧6段階の現行説明'
summary: 'H2: 旧6段階の現行説明。出典ノート「Gurumoji デザイン監査の独立反証チェック」の分割本文。'
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks
source_path: 50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md
source_sha256: fec531750b3b1eeb8616de26b52688a81b740a197d67d9f5682156883db2fd50
source_body_lines:
- 50
- 99
split_on: '2026-10-11'
---

# Gurumoji デザイン監査の独立反証チェック：H2: 旧6段階の現行説明

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/adversarial-checks]]。必要な本文だけを取得する。

## H2: 旧6段階の現行説明

### 確認できた不一致

- `docs/program-vault/20-Modules/ui-screens.md:21`: 6段階、画面側の順次API実行、永続pipelineは後続Phase 3–4
- 同 `:52`: 詳細設定でTransformer・AI実行先・Jev・再利用を指定する説明
- 同 `:86`: 旧入口を非表示にして新画面へ統合したと説明
- 実際の `analysis-execution.js:1–12,439`: M0–M7、サーバー永続ゲート。ブラウザーはpipelineを開始し状態をpollする
- `analysis_pipeline.py:44–93`: 定義、pipeline要求、step attempts、公開先状態、イベントのSQLite台帳と再起動回復
- 同 `:332–377,635–750`: 受付保存、段階実行、完了状態の保存。`analysis_core.py:311–338` に具体的な8段階計画
- `analysis-milestone-visualization-design.md:19` は初回導入範囲のM0–M7実装済みを明記

### 過大解釈しないこと

古い記述があることと実装が非永続であることは逆。M0–M7の存在を否定する根拠にはならない。また大きい設計書には将来の全構想が含まれるため、全機能の実装漏れを無条件で不具合として数えない。現在の初回導入範囲は同文書18.7節およびcapabilitiesに絞る。

## H3: 手動定義と測定意味のずれ

### UI・契約・計算をつないだ根拠

- `templates/index.html:243–249` の手動欄は定義名・ID・説明・出力列の4つ
- `analysis-execution.js:50–64` が参照するsource、rule、type、level、methodの5要素は現行templatesに存在しない。src全体にもこれらを作るコードを確認できない
- 欠落時の値は source=text, rule=text_length, type=number, level=ratio, method=descriptive
- `analysis_core.py:151–198` は構造化された測定ルールを検証するが、説明文を意味解析してルールへ変換しない
- `analysis_pipeline.py:104–126` はtext_lengthなら本文文字数を返す。`:157–168` はその値を数値記述統計として要約する
- backend自体はidentity、text_length、nonempty、duration、boolean_trueとfrequency/descriptiveを持つ。欠けているのはUI選択・伝達と、その意味の説明

### 独立した合成プローブ

`adversarial-contract-probes.py` とJSONで再現。Flask appはimportせず、純粋契約・測定モジュールに合成データだけを渡した。

- 説明「各発話の持続時間を秒数で測る」、出力列 `synthetic_duration`
- 2発話の本文文字数3/10、実時間60秒/2秒
- UI既定の構造化payloadによる算出値: **3 / 10**
- API契約でdurationルール/列を明示した対照: **60.0**

これはユーザーが自然文だけで任意測定できると解釈した場合に、出力名と実際の計算が食い違うことを示す。既定ルールが常に誤りという意味ではない。文字数を意図して入力した場合は整合する。

### 試行と採用

`analysis-execution.js:542–557` はdraft PUT → trial POST → adopted PUTを1回のsubmit内で連続実行する。trial値の個票は表示せず、件数だけを文面へ入れる。利用者が測定値や尺度を見てから採用する待ち状態はない。その後pipeline受付が成功するとdialogを閉じる。

追加のin-memory SQLite対照では `save_definition(..., status='adopted')` はtrial未実行でも成功し、`last_trial_json='{}'` のまま採用できた。これはAPIに人のレビューを保証するゲートがない証拠。ただし、ユーザー操作の意図をAPIが必ず別確認すべきだと単独で断定するものではない。UIの意味を修正する際、どこでレビュー・採用を保証するかを設計上明確にする。

### 妥当な修正方向・受入条件

- 限定文字数機能として提供するなら「文字数測定」とルール・型・尺度・単位を明示し、任意測定のように見せない
- 手動定義として提供するなら実在するsource/rule/type/level/method選択と互換性検査を復元。少数の実測値、欠測理由、要約を見て採用する導線を設ける
- 意図がdurationの合成定義をUIから作って、出力が文字数にならないことを確認。名義尺度の平均を拒否する対照も含める
