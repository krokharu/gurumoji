---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-05
title: コア・ハンドラー・ルーティング再編案：分析同士のつながりは、実行依存と意味上の関連を分ける
summary: 分析同士のつながりは、実行依存と意味上の関連を分ける。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 187
- 299
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：分析同士のつながりは、実行依存と意味上の関連を分ける

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

### 分析同士のつながりは、実行依存と意味上の関連を分ける

| 関係 | 例 | 実行・保存上の扱い |
| --- | --- | --- |
| 実データの入力依存 | 親結果の行をTransformerでまとめる | `data_input`。親run・artifact・hash・行IDと子runを結ぶ |
| 根拠・範囲の依存 | 親の外れ値を選び、元発話へJevをかける | `selection_basis`／`evidence_context`。選択元の結果とRAWの両方を入力参照に残す |
| 条件の依存 | 親結果の候補ラベルを次の分類に使う | `parameter_source`。候補の内容と版を固定し、元結果の変更から切り離す |
| 同じ対象の別手法 | 同じscopeの語彙分析と参加バランス | 共通scopeで結ぶ。片方の完了をもう片方の前提にしない |
| 結果間の意味的関連 | 類似、支持、反証候補、不一致 | relationと根拠・判定者・版を持つ派生結果。意味リンクだけでは自動再実行しない |

追加分析の実行依存は循環しない有向グラフ（DAG）とする。親の確定済みartifactを参照し、子は別runで保存する。再評価が必要なら新しい計画版・子runを作り、過去のrunへ逆向きの依存を追加しない。

最小の関連契約は`pipeline_id`、`plan_version`、`step_id`、`input_bindings[]`、`scope_id`、`input_kind`、親run／artifact ID・hash、根拠IDとする。scope・計画・結果入力は既存保存基盤で扱う版付きJSONに置き、全関係を最初から新しいSQLテーブルへ正規化しない。manifest／payloadの版更新と旧形式の読取をセットで実装する。

現在版から見たstaleは、RAW・scope・条件・知識版の変更を依存する子へ伝える。無関係な枝を再実行せず、固定された過去の入力・結果は保持する。親失敗時は依存する子を待機／実行不可にし、独立した枝の結果を捨てない。削除時も参照先を無言で現在版へ差し替えない。

#### 計画案から確定入力への変換（FLOW-1で追加）

`input_refs`は計画時の参照、`input_bindings`は実行直前に解決・検証した固定入力とする。`scope_ref`は版付きscopeのIDとhashを指し、実行時の`scope_id`・`scope_hash`へ対応付ける。計画JSONは`plan_schema_version`、保存manifestは`schema_version`を持ち、計画内容の更新回数`plan_version`とは区別する。

| 計画時の参照 | 実行時の解決 | 拒否する条件 |
| --- | --- | --- |
| 保存済みの`run_id`・`artifact_id`・`sha256` | 台帳から同じ親runの確定済みartifactを読み、hash・kind・schema・単位を検証 | 親の不一致、未確定、参照欠落、hash不一致、未対応の型 |
| 同じ計画の`from_step`・`output_name` | 登録済み出力名を、その段階が確定したrun・artifact・hashへ置換 | 未知の段階・出力名、循環、親失敗、必要出力の欠落 |
| `row_ids`・選択規則 | 親artifact内のIDへ解決し、重複排除・順序規則を含め固定 | 存在しない行、別artifactのID、表示の上位件数を暗黙に全件扱い |

各参照は一意な`binding_id`と関係の役割（`data_input`／`selection_basis`／`evidence_context`／`parameter_source`）を持つ。同一計画内の`from_step`から必要な依存をコードで導出し、提案の`depends_on`と一致しなければ拒否する。既に確定した過去runは入力として照合するが、現在の計画内の実行待ちには含めない。LLMが渡したパス、現在版への差し替え、型の暗黙変換を解決方法にしない。

以下は、既存の主張集合を新しい1段階の分析へ渡す対応例。IDと`<…>`のhashは説明用で、実行可能な要求ではない。結果文用adapterの実装・能力確認が完了するまで、この計画は利用不可とする。

```yaml
plan:
  plan_schema_version: 1
  pipeline_id: example-pipeline
  plan_version: 1
  steps:
    - step_id: group_claims
      method_id: transformer_topics
      task: cluster_result_text
      scope_ref: {id: scope-a, sha256: "<scopeのhash>"}
      input_refs:
        - binding_id: claims
          role: data_input
          source: {run_id: parent-run, artifact_id: parent-claims, sha256: "<親artifactのhash>"}
          row_ids: [claim-1, claim-2]
      depends_on: []
      parameters: {adapter_id: result_text_transformer, adapter_version: 1}
resolved_step:
  step_id: group_claims
  scope_id: scope-a
  scope_hash: "<scopeのhash>"
  input_bindings:
    - binding_id: claims
      role: data_input
      input_kind: analysis_result
      run_id: parent-run
      artifact_id: parent-claims
      sha256: "<親artifactのhash>"
      artifact_schema_version: 1
      unit_kind: claim
      row_ids: [claim-1, claim-2]
manifest_extension:
  pipeline_id: example-pipeline
  plan_version: 1
  plan_hash: "<確定した計画JSONのhash>"
  pipeline_request_id: pipeline-request-a
  step_id: group_claims
  attempt_id: attempt-a
  request_id: step-request-a
  analysis_id: child-run
  parameters_ref: {artifact_id: child-parameters, sha256: "<parameters.jsonのhash>"}
```

`parameters.json`には`resolved_step`、実際のengine・モデル・契約版・知識packetの参照を保存し、manifestからhash付きで辿る。同計画内の親を選ぶ例では`source`を`{from_step: extract_claims, output_name: claims}`、`depends_on`を`[extract_claims]`に替え、親の確定後に同じ`input_bindings`形式へ解決する。計画案は書き換えず、解決済み入力を別の記録として固定する。

#### 再送・再利用・新規実行の識別（FLOW-1で追加）

現行の`AnalysisStore.save`は`ai_finishing`・`ai_insights`以外でfingerprintが一致する完了runを再利用する。provider・model・結果本文は単独ではこの識別に入らない。新しい実行種類をそのまま追加すると別の結果を過去runへまとめるため、拡張時に以下の規則を導入する。構造再編だけでは既存種類の識別を変更しない。

| 操作 | IDと保存の規則 | AI・分析の扱い |
| --- | --- | --- |
| 同じ要求の再送 | 同じ`request_id`と同じ固定入力は同じ試行・run。同じIDを別入力へ使えば競合 | 受付・実行前にも重複を排除し、保存時の重複排除だけに頼らない |
| 保存・Vault公開の再試行 | 同じrunと保存済みパッケージを使う | 追加呼び出しなし |
| 既存結果の利用 | `reuse_run_id`とartifact・hashを明示して参照する。新しく計算した結果として記録しない | 追加呼び出しなし。入力・契約・能力の適合を検証 |
| 明示的な再分析・モデル変更 | 新しい`request_id`・`attempt_id`・run。同じ入力条件でも別実行 | 新しい結果を計算し、内容が同じでも履歴を統合しない |
| 失敗段階の推論再試行 | 新しい試行を作り、元の試行と理由を結ぶ。確定済み親runは保持 | 失敗段階だけ実行。結果の再利用と区別 |

入力の同一性を表すfingerprintと実行の同一性を分ける。拡張のfingerprintにはschema版、scopeのhash、全bindingの役割・親ID／hash・行集合、手法／契約／adapter版、実行engine・要求model／取得可能なrevision、seed等の実効設定、固定した知識packetのhashを含める。canonical化と行集合の順序規則も版付きで定める。応答で初めて判明するmodel・usageは結果来歴であり、受付済み要求の識別を後から変えない。

新しい実行種類には明示的な再利用規則を与え、未知のkindに既存のfingerprint再利用を自動適用しない。旧runのID・hashは再生成せず、新旧の識別方式をmanifest版で区別する。受け入れ条件は、同一要求の重複実行0件、別要求の再分析は別run、モデル・親artifact・契約の違いを識別、保存再試行の推論0件である。

#### 段階実行の状態と再開（FLOW-1〜2で追加）

`analysis_pending_packages`は計算済み結果の保存回復専用とする。計画の実行待ち・推論中・取消をここへ混ぜない。追加分析の受付・状態は既存`library.sqlite3`へ必要な2種類の記録を追加し、既存ジョブを統合する汎用ジョブ基盤にはしない。

| 正本 | 最小の記録 | 所有者 |
| --- | --- | --- |
| `analysis_pipeline_requests`（提案） | 要求ID、pipeline ID・計画版・固定計画JSON／hash、送信方針・予算、状態、取消要求、更新版 | 計画を実行するHandler。計画・設定は受付後に不変 |
| `analysis_step_attempts`（提案） | pipeline要求ID、step ID、試行ID・番号、一意なrequest ID、固定binding／設定、状態、結果run、実試行数・usage・失敗理由 | 段階の実行Handler。`pipeline要求ID＋step ID＋試行番号`も一意 |
| 既存のrun・artifact・保留パッケージ | 確定結果と保存途中の回復情報 | `AnalysisStore`。計画完了まで保存を遅らせない |

FLOW-1は受付・固定入力・重複防止・結果runとの対応まで、FLOW-2は非同期実行・取消・回復まで同じ記録を拡張する。DB追加は版付き拡張の変更で行い、既存テーブル・旧runの意味を変更しない。変更可能な状態はSQLiteに置き、確定済みmanifestを進捗更新のたびに書き換えない。

各試行は`waiting → ready → running → completed / failed / cancelled / interrupted`を基本とする。親が失敗・取消になった子は理由付き`blocked`とし、独立した枝の確定結果は保持する。`completed`は結果runの保存確定後とし、Vault公開失敗、結果のpartial、現在版から見たstaleは別軸で扱う。状態更新は期待状態・更新版を照合する条件付き更新で行い、同じ試行を複数のworkerが取得しない。

- 取消は永続の取消要求とプロセス内eventへ伝え、新しい段階・バッチの開始を止める。既に確定した結果を削除せず、戻ってきた応答を別要求へ適用しない。
- 再起動後の自動推論再開は初期対象外。起動時は残った`running`を`interrupted`として確認し、利用者が再開する場合だけ、親hash・入力・能力・送信方針・残り予算を検証する。設定変更を再開中の要求へ混入させない。
- 結果保存後・試行完了記録前に停止した場合は、試行のrequest IDに対応する完了runへ結び直す。保留パッケージがあれば保存だけを回復する。再計算しない。
- providerへ到達したか不明なタイムアウト、応答取得後・保存前の停止は、その事実を残す。同じ試行を成功と推測したり自動再送したりせず、明示的な再実行で新試行を作る。使用量不明を0として予算をリセットしない。
- 回数・時間・tokensの予算は試行をまたいで計画要求へ集約し、再開・JSON修復・相談にも適用する。固定入力や方針を変える場合は新しい計画要求とする。

検証には二重受付、同一段階の同時取得、親失敗と独立枝、取消と完了の競合、保存確定直後の停止、応答不明、再起動後の明示再開を含める。一時ファイルSQLiteとスタブを使い、プロセス再起動を含む回復は`:memory:`だけで代用しない。
