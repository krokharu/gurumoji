---
note_id: expert-descriptive-statistics-agent-contract
note_type: expert-agent-contract
title: 記述統計・度数専門家の入出力契約
status: proposed
updated: 2026-10-08
---

# 記述統計・度数専門家の入出力契約

**契約版2の限定runtime接続はa04で実装し、a06でCPU工程受入済み。** `ExpertAgentRegistry._profile` は統計3専門家の `schema_version: 2`・契約版2と、段階必須step・数値セル束縛を受理する。固定候補 `0fbfb402af9d9bdd18a495565288bf5ed273d5f4` の関連301件／142.796秒を確認した。実モデル品質、一般の自由文意味検出、研究者の採否は未認定で、人record取得は未対応／human_pendingを維持する。

専門家は分析案・確認事項・結果説明を下書きする。数値計算はHandlerが既存Python統計エンジンへ発注し、研究者の確定判断は本人の記録だけを証拠にする。01の `definition_version: 2`、procedureのID・actor・AI許可集合は変更しない。根拠は本分野の01〜06と、[[40-Design/obsidian-skill-knowledge-work-plan#13. 目標と進行順序|依頼版5第13節]]のQA-01〜03。

## 段階と採用状態

| 段階／状態 | 必須条件と扱い |
| --- | --- |
| `analysis_plan / needs_calculation` | 当該段階のAI必須step、空でない分析案・前提確認、許可methodの `analysis_requests`。 `calculation_result_ids=[]`、`numeric_bindings=[]`、`claims=[]`。計算は提案であり未実行 |
| `result_explanation / draft` | 当該段階のAI必須step、Handlerが照合した計算result参照、実際に提供された行の説明。数値は下記セル束縛からコード描画する。AI下書きの成立と研究者の確定を別に保持 |
| `needs_input` | `missing_inputs` に具体的な不足を記録。未充足step・未計算セルを補完せず、計画／説明の完了に数えない |
| `not_applicable` | `missing_inputs` に適用条件IDと不足内容、`limitations` に不適用理由を記録し、`numeric_bindings=[]` とする版2契約。現行統計response schemaで受理し、不適用理由を保持する。不適用を成功・ゼロ・手順完了へ変換しない |
| `human_pending` | Handler側の採用状態。研究者stepの記録欠落、重大な意味・因果・一般化・多重検定の未判定を保持し、後続の確定根拠へ昇格させない。モデルが自己指定して解除できる状態ではない |

段階はHandlerの固定packetにある `response_phase` と渡した計算結果から決め、モデルの申告で切り替えない。完了するAI下書きには `required_ai_steps <= performed_step_ids <= allowed_ai_steps` を要求し、重複、空step、説明段階の計画stepだけ、他分野step、code／researcherの代行申告を不完全または拒否とする。AIの `performed_step_ids` は申告にすぎず、対応する版・知識hashの応答と出力検査が必要。これも統計的品質の証明にはならない。

Coreが提案を判断し、Handlerが正式タスクを登録する。計算後の説明は同じ専門家へ固定結果を渡す。比較軸・対象は初期版の `all_included_initial` に固定し、後から採用したラベル・部分範囲・任意Python式は実行しない。計算の `partial`／`not_computed`、null、未読の行・発話・知識は理由とともに保持する。タスクの実行成功だけでは計算成功や研究上の確認完了を示さない。

## 段階×required step×actor×根拠

| 段階 | 必須step ID | actor | 必要な証拠・内容 | 根拠 |
| --- | --- | --- | --- | --- |
| analysis_plan | desc-ai-plan | ai_draft | 固定profile/input/knowledge hashに結ぶ計画応答、前提確認、許可計算の提案 | 01 desc-ai-plan、02、LIT-appelbaum-2018-jars-quant |
| analysis_plan | desc-p1 | researcher | 対象発話・比較軸・欠測・除外と分母を決めた本人のrecord | 01 desc-p1、02、implementation |
| analysis_plan | （なし） | code | 計算は未実行。計算stepの完了を要求・申告しない | 01の計画／計算責務 |
| result_explanation | desc-ai-report | ai_draft | 検証済み結果を参照した説明応答、未読・欠落・限界 | 01 desc-ai-report、03、LIT-appelbaum-2018-jars-quant / LIT-aarts-2014-nested-data |
| result_explanation | desc-p2 | code | Handlerの正式タスク・保存結果（descriptive_statistics / frequency_statistics）とセル状態 | 01 desc-p2、02、implementation |
| result_explanation | desc-p1 | researcher | 同じ入力版・対象に対する計画recordの再照合 | 01 desc-p1、02、implementation |
| result_explanation | desc-p3 | researcher | 分布の歪み・極端な発話と発話IDを確認した本人のrecord | 01 desc-p3、02・03、implementation |
| result_explanation | desc-p4 | researcher | 探索的な記述、N・欠測・中央値・四分位と入れ子の限界を判断した本人のrecord | 01 desc-p4、03・04、LIT-appelbaum-2018-jars-quant |

## 版2の最小schema案

```yaml
schema_version: 2
expert_id: exp-descriptive-statistics
contract_version: 2
phase_requirements:
  analysis_plan:
    ai_draft: [desc-ai-plan]
    code: []
    researcher: [desc-p1]
  result_explanation:
    ai_draft: [desc-ai-report]
    code: [desc-p2]
    researcher: [desc-p1, desc-p3, desc-p4]
numeric_binding:
  required_fields:
    - result_id
    - dataset
    - row_id
    - column
    - variables
    - target
    - dataset_version
    - computation_input_hash
    - rows_hash
  render_policy: statistical-cells-v1
input_fields:
  - id: analysis_premises
    title: 研究者が指定した分析目的・前提。未指定はnull。
    type: string
    required: false
output_fields:
  - id: analysis_plan
    title: 分野内の分析案と選択理由。未実装手法は実行済みとしない。
    type: string
    required: true
  - id: prerequisite_review
    title: 適用条件・欠測・対象と分母・研究者が確認すべき事項。
    type: string
    required: true
  - id: result_explanation
    title: 検証済み計算結果の説明。計算前は未実行と明記。
    type: string
    required: true
  - id: quality_record
    title: 結果の参照IDと読み込み範囲、未確認事項。
    type: string
    required: true
  - id: limitations
    title: 入れ子・独立性・多重比較・探索的扱い・AI下書きの限界。
    type: string
    required: true
```

根拠と手順は [[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert]]。共通実行契約は [[20-Modules/analysis-orchestration]]。

## 必須集合の証拠と数値セル（QA-01・02）

YAMLの `phase_requirements` は直前のactor表と同じ必須集合。AI集合は当該01の `ai_assist.steps` の部分集合で、全項目が `ai_draft`。code／researcher集合は01の当該actorに限定する。研究者記録がなくてもAI下書きや計算提案は保存できるが、研究者の手順を完了にせず `human_pending` を保持する。説明時は計画時の研究者記録も同じ入力版・対象へ束縛する。

codeの証拠は同一runの正式Handlerタスクと保存結果だけ。許可method、task/result ID、`dataset_version`、`raw_hash`、manifest、`rows_hash` を原表に照合し、stale・隔離・別run・別版の結果を拒否する。計算不能セルを成功とせず、検査済みの計算試行と各セルの `computed`／未計算状態を区別する。研究者の証拠は本人のrecord ID、確認者、確認日時、対象step、入力版/hash、対象result/hash、判断内容へ戻れる記録のみ。AIの「確認済み」、Coreの採用、自動品質フラグは研究者recordの代わりにならない。既存の記録経路で取得できなければ保留し、架空recordを作らない。

版2応答では `expert_report.numeric_bindings` を構造化配列として追加する最小案をa04へ渡す。各要素の必須キーはYAMLの `numeric_binding.required_fields` と次表で一致させる。モデルからの任意の `value`・表示文・丸め桁の追加は許可しない。

| キー | 型と照合先 |
| --- | --- |
| `result_id` | string。今回渡した検証済み `calculation_result_ids` 内の保存結果 |
| `dataset`、`row_id`、`column` | string。原表 `datasets[dataset].rows` の一意行・存在する数値列。行番号で代用しない |
| `variables` | string配列。行の変数ID／変数対の順序まで一致。ラベルだけで代用しない |
| `target` | object。固定キー `scope`（string）と `selectors`（object）。scopeはmanifest、selectorsは下記分野別行キーの全組に一致。対象発話集合・除外・分母は原manifest／行から復元して照合 |
| `dataset_version` | string。Handlerの固定入力hashとしてtask・run・result・manifestに一致 |
| `computation_input_hash`、`rows_hash` | string。原manifestの固定計算入力と結果行hash。全原行から照合し、上限付き抜粋からhashを作り直さない |

原セルのN、欠測、単位、分母、状態、補正の有無も同じ行／manifestからコードで添付する。モデルに渡していない行は束縛できない。Handlerは抜粋の省略件数と原表の全量を区別する。正しいresult IDでも変数対・群・行・列・対象・版・hashが違えば拒否し、存在しないCIや補正済みp値は生成しない。

`statistical-cells-v1` は表示だけの固定規則案。原セルの値は変更せず保存する。

| セル | コードでの表示規則 |
| --- | --- |
| N、欠測、度数、群数 | 整数の十進表記。欠測や未実行を0にしない |
| 係数、統計量、効果量、要約値、自由度 | `Decimal(str(value))`、小数3桁、`ROUND_HALF_EVEN`。丸め後の負のゼロは `0.000` |
| p値 | 同じ規則で小数4桁。丸め表示 `0.0000` を厳密なp=0と解釈しない。原値は併記可能な正本として保持 |
| 百分率 | 既存の `percent`／`*_percent` は百分率値のまま小数2桁＋%（二重に100倍しない）。率から変換する場合だけ、登録された分母・尺度から100倍する |
| null、非有限、列欠落、未計算 | 数値を描画せず、欠測・未計算・未提供などの実際の理由を表示 |

数値入りの報告部分は束縛セルだけからコード描画し、AIの自由文（summary、outputs、limitationsなど）中の数値を検証済み主張として採用しない。自由文の値・符号・Nの改変を黙って補正しない。数量主張として検証表示できる経路はセル束縛だけとし、自由文は未検証のAI下書きとして分離・保留する。表の計算一致は説明の意味・因果・一般化の妥当性を保証しない。01の禁止結論に抵触する既知の断定は拒否／隔離し、人の確認で禁止を解除しない。入力・結果が変わった場合は旧研究者recordを履歴として保持し、新対象への確認済みに転用しない。

## 分野固有の束縛と保留（QA-03）

`descriptives` は `variables=[variable]`、`target.selectors={scope, group_variable, group}` を原行と照合する。`frequencies` は `variables=[variable]`、`target.selectors={value, value_id}` を照合する。上位の `target.scope` は両方ともmanifestの `all_included_initial`。同名ラベルでも変数・群・カテゴリを混ぜない。N・missing・unit・平均・標準偏差・中央値・Q1/Q3、度数・percentを実在セルから描画する。

意味レビューはdesc-a4、desc-q2〜q4と禁止結論を対象にする。記述量を影響力・理解度・関与の質とする、数値差へ因果を足す、文字／分を音響的速度とする、未読範囲や母集団へ一般化する判断の重大未判定はhuman_pending。形態素のfallbackや時刻欠測（desc-a2/a3、desc-q1）はHandlerの実状態を示して確認を待つ。人単位の要約へ発話単位の表を読み替えず、検定や相関は担当外へ引き継ぐ。

## 限定runtime接続と互換性（a04実装・a06受入）

1. `services/expert_agents.py` のstrict-key parserを版別に分岐し、版2では `phase_requirements` と `numeric_binding` だけを追加許可する。未知キーは引き続き拒否。上の型、actor、実stepの存在とAI許可、重複なしを検査し、固定profileへ反映する。
2. 同じmoduleのrequest／report schema／`validate_report` でHandler由来の段階とAI必須集合を検査し、`numeric_bindings` の型・参照を制約する。`not_applicable` の不適用理由を扱う最小経路を決め、`needs_input` を完了にしない。code／researcherの証拠をモデルのstep欄で受理しない。
3. `analysis_orchestration.py` と既存統計結果adapterで原表・同run・入力版/hash・行/列/変数/対象を照合し、固定表示規則で描画する。既存task/result/decision/issue/eventを再利用してhuman_pendingと研究者record参照を保持し、未判定の確定採用・後続昇格を防ぐ。記録経路が未対応なら保留する。新しい実行能力や汎用責務は追加しない。
4. 版1の凍結済みbundle・結果は元hashと未判定のまま読み取る。新版で自動再採用・成功化・再計算せず、新規版2だけを新検査へ接続する。既存adapter版の復旧停止を維持し、非互換の再開は既存停止経路へ返す。他14定義やSQL既存列、研究者Vaultの移行・上書きは行わない。

上記はa04の実装対象と互換条件。a05の独立確認とa06の同byte統合検証により、構造step・原表セル・コード描画・人待ちの昇格制御を限定受入した。一般の自由文actor申告6件と旧Core mock5件は既知残件として保持し、全アプリ回帰の合格や実モデル・研究者判断の検証済みを意味しない。以下の確認記録はa03作成時の結果であり、当時のloader拒否を現在の状態へ読み替えない。

確認記録（2026-10-08、Windows local、Python 3.13.7）：基準commit `ac4bc6cef2e806a2bf52f503625fb7a1363c20e3`、依頼版5plan SHA-256 `2ab048079d75ed55d5b737cf4d8a6735e52fa2728daec6dbe7f44d8deb9cf86d`。3契約のYAML解析、実step/actorと人向け表の一致、参照先、01〜06の元byte保持、変更allowlist、`git diff --check` は成功。合成Handler結果の行キーも確認し、全3契約の現行loader拒否（`expert_contract_invalid`）を個別確認した。

`PYTHONPATH=src;tests`、`PYTHONDONTWRITEBYTECODE=1` で `python -m unittest test_statistical_expert_agents.StatisticalExpertTests.test_each_domain_plan_calculation_then_explanation_has_fixed_result_reference -v` を実行し、1テスト・1エラー（最初の相関run構築時の版2 loader拒否）。他分野のこの統合テストと新版採用検査・広い回帰は未実行。テストは一時DB/ローカル上書き先だけを使い、研究者DB/Vault/原文/資格情報は未読・変更なし。アプリの実モデル呼出し・外部APIは未実施。次ownerはG0.5a-04 W-runtime。


| 受入ケース | 期待する状態 |
| --- | --- |
| 正常な計画 | desc-ai-plan、許可集計の提案、結果参照なし。desc-p1記録なしならAI計画下書きのままhuman_pending |
| 正常な説明 | desc-ai-report＋Handlerのdesc-p2結果。対象・群・分母・欠測と中央値／四分位を結ぶ記述をAI下書きとして保持 |
| 手順不整合 | 空step、説明にdesc-ai-planだけ、desc-p2／desc-p3をAIが申告した場合は不完全／拒否 |
| 入力／セル不足 | 対象なしはneeds_inputまたは理由付きnot_applicable。欠測・未提供四分位を0にせず、fallbackは正式解析成功にしない |
| 人の確認待ち | desc-p1/p3/p4、desc-q2〜q4の重大未判定、影響力・因果・一般化の意味判断はhuman_pending |
