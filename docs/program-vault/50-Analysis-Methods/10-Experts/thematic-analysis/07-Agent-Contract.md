---
note_id: expert-thematic-analysis-agent-contract
note_type: expert-agent-contract
expert_id: exp-thematic-analysis
title: テーマ分析エージェントの入出力契約
summary: Handlerが渡す分野別入力と、テーマ分析のAI下書きが返すJSON項目・型を指定する。
status: current
updated: 2026-10-06
tags:
  - gurumoji/expert
  - gurumoji/analysis
---

# テーマ分析エージェントの入出力契約

専門知識・適用条件・許可されたAI手順は [[01-Expert]] と関連ノートを正とする。この契約は手法の許可範囲を拡大せず、研究者の確定解釈をAIへ移管しない。

`services/expert_agents.py` がこのノートのYAMLを読み、run開始時に知識と一緒に固定する。`<data>/local_knowledge/50-Analysis-Methods/10-Experts/thematic-analysis/07-Agent-Contract.md` の同一パスで個人の契約を上書きできる。共有ノート・個人ノートの変更は次のrunから適用する。

```yaml
schema_version: 1
expert_id: exp-thematic-analysis
contract_version: 1
input_fields:
  - id: analysis_premises
    title: 研究者が選んだ理論的前提・帰納／演繹・意味的／潜在的水準。未指定はnullとして保留する。
    type: string
    required: false
output_fields:
  - id: research_context
    title: 研究質問と分析前の判断。未指定の前提を作らず、研究者の確認事項を記す。
    type: string
    required: true
  - id: analysis_form
    title: テーマ分析の形と適用限界。研究者の未確定の選択を確定扱いしない。
    type: string
    required: true
  - id: candidate_themes
    title: 初期コードとテーマ候補の名前・定義。研究者が確定したテーマと区別する。
    type: string
    required: true
  - id: theme_evidence
    title: 候補に対応する語りと原文の根拠ID、反例・対応しない発話。
    type: string
    required: true
  - id: theme_relations
    title: 候補間の関係と重なり。根拠不足の場合はその理由。
    type: string
    required: true
  - id: quality_record
    title: 適用した品質確認と未確認事項。人の確認を実施済みと書かない。
    type: string
    required: true
  - id: limitations
    title: 未読範囲、不足する前提・データ、一般化できない範囲。
    type: string
    required: true
```

`input_fields` はAPI開始設定の `expert_inputs[expert_id]` に対応する。`required: false` の未指定値は明示的なnull、trueの欠落や異なる型・未定義項目は開始前に拒否する。型は `string`、`number`、`integer`、`boolean`、`string_array`。機械向けJSON Schemaはこの定義から生成する。

共通入力はHandlerが `expert_request` に配置する専門家ID、契約版、profile／knowledge hash、問い、入力版、注釈版、原文根拠、取得知識、範囲・欠落であり、モデルがファイルを直接開く仕組みではない。

共通出力の `summary`、`claims`、`analysis_requests`、`label_patches` に `expert_report` を加える。`expert_report.outputs` は上記項目・型に厳密一致させる。ほかに専門家ID、profile／knowledge hash、draft／needs_input／not_applicable、利用ノートID、実施した許可手順ID、根拠ID、不足入力、限界を返す。必須出力を埋められない場合も理由を記し、不足や未実行を成功としない。

手法や出力の意味を変更した場合は `contract_version` を上げる。任意コード・シェル・外部URLの実行は定義できない。実装と検証は [[20-Modules/analysis-orchestration]] の専門家接続節を参照する。

型付き候補は `expert_inputs[exp-thematic-analysis].typed_contract: thematic_candidates_v1` を明示したrunだけ契約版2として有効になる。既定の契約版1と上記7文字列は読み取り互換を維持し、文字列から候補や採否を抽出しない。版2は `expert_report.thematic_candidates_v1` に [[50-Analysis-Methods/40-Skills/thematic-candidate-evidence#^tce-output|閉鎖候補schema]] を追加し、draft以外ではnullとする。Handlerの固定SourceRef・Scope・発話hashと照合し、保存先は `result.orchestration.thematic_candidates_v1` と固定された候補添付である。原expert_reportのbytes相当のJSON記録は変更しない。

```yaml thematic_candidates_v1
version: thematic_candidates_v1
contract_version: 2
schema_id: gurumoji.thematic-candidate
schema_version: 1
```

内容hashは `HC(domain,content)=SHA256(canonical({domain,content}))` とし、候補のtheme_refsおよびThemeContentは不変とする。検索状態・メモ参照・受領記録・未読・変更理由の履歴は内容hash外、固定保存のraw_byte_hash内に置く。変更した内容は新IDまたは新版で保存し、旧版を上書きしない。支持・反例・代替・コード定義・統合／分割理由は閉鎖schemaで検査するが、その妥当性を人の確定解釈と扱わない。

S1では `human_status: human_pending`、`human_record_state: not_entered`、`human_records: []` のみを受け入れる。本人の実要求・権限・対象内容hash・scope・原記録bytesを検証する将来の信頼された入力経路以外からHumanRecordを作らない。実bytes未解決の受領記録は成功としない。未読のunknown/not_runはids:null、measuredは固定集合との差集合を要求し、配信・処理を人の精読と同一視しない。
