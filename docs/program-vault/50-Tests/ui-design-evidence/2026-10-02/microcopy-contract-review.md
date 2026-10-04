---
note_id: "test-ui-microcopy-contract-review"
note_type: "design-evidence"
title: "マイクロコピーに関係する実行・送信・保存契約の独立確認"
summary: "v0.4の送信・保存・状態文言と実契約の対応。修正の実装・実GUI受入は未実施。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
review_repository_head: "88f5e3eea245166ee68ed4dc6c3f99c31e149228"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# マイクロコピーに関係する実行・送信・保存契約の独立確認

2026-10-02 21:00–21:08 UTC。対象HEAD `88f5e3eea245166ee68ed4dc6c3f99c31e149228`。これはdocs統合commitで、`ddc23ab..HEAD -- src tests`の差分は0。実装は引き続き`59ebd24`を含む既監査コード。アプリ編集、実runtime/私有Vault読取、モデル、外部AI、実GUI操作なし。

## 結論

1. **AI見解の送信説明は現在のpayloadより狭い。** 発話・話者名・研究質問に加え、話者の識別子/役割、付与コードID/label、重要flagが入る。専門家modeでは短いbriefと許可手順情報も入る。全文の研究ノートや文献を送る実装ではない
2. **pipelineの3つのAPI targetは実際の保存先の全てではない。** ONの通常経路はInput/Orchestrator/Visualizationの3生成Vaultに加えResearchVaultも試みる。ResearchVault conflictでも3先成功ならpipeline completedになり得ることを元コードの合成実行で確認した
3. **failedの「失敗した処理を再試行」は実際には設定を開く。** backendのfailed allowed_actionsは空で、UI handlerはretryせず設定dialogへ進む。retry endpoint自体が常に不可能という意味ではない

## 1 AI見解: 実際にcallへ渡る情報

### 確認したデータ

- `analysis_insights.py:307–309`: research_question。未指定なら会話session_profile.objective、さらに既定目的へfallback
- `:336–349`: invocation限定参照ID（E0001等）、speaker ID/name、role、offset、text、codes（ID＋label）、important boolean
- `:33–35`: excludedまたは空本文の発話は除く。現在UIで単に表示filterしている部分だけを送ると解釈しない
- `:324–334`: expert指定時のみexpert ID/definition version、短いbrief、許可段階のID/title/basis IDsをsystem文へ追加
- `:397–403`: このrecord batchと目的を実callへ渡す。長文は1500文字単位に分割し、参照IDとoffsetを持つ。`:408–423`の統合処理では部分見解と根拠参照・話者の対応も再送する

### config/modeによる限定

- `services/analysis_jobs.py:99–105`: provider/model/base_urlを使うcallbackへ、`method_experts.ai_context(...)`で得たexpertを渡す
- `method_experts.py:646–690`: 主手法が暫定ならgeneric。研究者が選んだ主手法に適格な定義/知識/許可手順がある場合にexpert。未提供/不適格ならblocked
- `method_experts.py:700–721`: expert mode以外はNone。definition version/knowledge hashを再確認し、解決済み根拠IDだけを付けた短いcontextを作る。研究ノート本文・文献全文はこのcontextへ含めない
- `services/analysis_jobs.py:212–230`: blockedを拒否し、configured provider/modelを読む。LM Studioもconfigのbase_urlを使用するため、閲覧者の「このPC」で必ず処理するとは断定できない。実接続先は今回読んでいない
- 基礎pipelineやO01相談と、このAI見解payloadを混同しない。今回確認したのはAI見解の経路

### 合成確認

`microcopy-contract-probes.py/.json`は元`create_ai_insights`へ合成会話とexpert contextを渡し、call引数だけを捕捉。role/codes/important/brief/stepを確認し、除外発話・生source ID・置いたnote全文/文献全文markerがcallへ入らないことも確認した。外部callは0。

### 文言案の境界

短い要約は「発話、話者情報、研究目的、付与した分析情報を送ります」。展開部分に役割、コード、重要flag、条件付きの専門家brief/許可手順を具体化する。providerと設定された接続先、モデルを表示する。全文コードブック、自由メモ、文献全文、音声など、確認できていない項目まで送信内容へ追加しない。

## 2 Vault: requested target、実副作用、完了判定を分ける

### 通常runtimeでの結線

- `app.py:1514–1515`: archive storeは`AnalysisStore(DATABASE_FILE, database_connection)`
- `app.py:1562–1582`: pipeline serviceは毎回`save_result=store.save`、`publish_result=store.publish`、`publication_outcomes=store.publication_outcomes`をbind。このfactoryにmode/configによるResearchVault除外分岐はない
- `analysis_pipeline.py:583–588`: 結果package保存は`publish=False`
- `:476–482`: publication_targetsが空ならpublish_result stepはnot_applicable。通常UIのcheckbox OFFはこのpipelineのVault工程を実行しない
- `:607–632`: targetsが非空なら`publish_result(run_id)`を呼び、戻り値を使わず、3生成Vaultのoutcomesを読む

### 実writerの範囲

- `AnalysisStore.publish:588–697`: 先に`:594`で3生成Vaultの`publish_vaults`、続いてResearchVaultのsource/method/result/index等を扱う
- `publish_vaults:175–207`→`VaultRegistry.publish_analysis:451–513`は3生成先を対象とし、pipelineのselected targetsを引数として受け取らない
- `AnalysisStore:169`のResearchVaultは同じDB親の`obsidian/ResearchVault`。3生成先のrootは`VaultRegistry.root:205–218`のregistryに従い、`<data>/obsidian`直下の独立rootとして検証される。実際のruntime設定値は今回見ていない
- Software Vaultは`vault_registry.py:31–37`で読み取り責務。今回のpublish対象ではない。移入Vault、利用者PC、外部共有やWeb公開と同一視しない

### 完了と失敗

- ResearchVault処理中の例外は`analysis_store.py:693–697`でrun.vault_status='conflict'とerrorへ記録され、例外としてpipelineへ戻らない
- `publication_outcomes:209–248`はInput/Orchestrator/Visualizationだけを返す
- pipelineの`:504–508,737–750`はこの3先を完了判定し、ResearchVaultのvault_statusをgateに含めない
- public result_runにはResearchVaultのvault_statusが見える経路は残る。問題は結果が存在しないことではなく、pipeline completedが4先成功を表さないこと

### 合成再現

元M0–M7 engineと元`AnalysisStore.publish`を使い、3生成writer成功とResearchVault書込境界のStoreConflictを合成した。SQLiteは一時領域。実Vault、実artifact書込はstub。

| API publication_targets | publisherのattempt | publication台帳 | pipeline | ResearchVault |
|---|---|---|---|---|
| 全3先 | 3生成先＋Research | 3先published | completed | conflict |
| inputだけ | **同じ4経路** | input published、他2先not_selected | completed | conflict |
| 空配列 | 0経路 | 3先not_selected | completed | pending（今回対象外） |

成果物: `microcopy-contract-probes.py/.json`。現行GUIでの再現、実Vault権限障害、実ネットワーク接続は未試験。

### 所有権保護の重要な例外

- `AnalysisStore.write_note:476–501`と`VaultRegistry._write:269–289`は共通note policyを使う。研究者が削除した非navigation noteはmissingとして再作成しない
- `VaultRegistry.aggregate:504–511`はconflict/failedがなければpublishedへ集約するため、missingを尊重した結果でもpublishedになる場合がある
- したがって「published＝すべてのノートが存在する/ユーザー編集を上書きした」ではない。note_events/missing説明は保持する

### 訂正・後続契約の推奨

- 文書の「targetは3」は**API enum/ゲート対象が3**という説明へ限定し、実際はResearchVaultも含むことを明記する。現行enumはresearchを受理しないので、文言修正だけでpayloadへresearchを足さない
- 短期案として空配列か全3のみを受理し、ONは4先のbundleと明示、subsetはwriter起動前に明示拒否する設計は整合する。ただし現在subset APIが受理されるため、互換変更のversion/4xx/既存client試験が要る
- 本対応は受理時にrequested/effective destinationsを固定し、各writerへ実scopeを渡し、Researchを含む実outcomeをrunと結び付ける。not_selectedならwriter callも0という受入が必要
- 失敗した1先だけの再試行は現callbackがscopeを受け取らないため、契約対応前に保証しない。単にpipeline publish stepをretryすると全bundleが再訪され得る
- 旧completedを新しい4先成功の意味へ遡及変更しない。本体、3生成先、ResearchVault、missing保護を別軸で表示する
- **再試行の既存経路という反例:** pipeline completedのallowed_actionsはview_resultsのみだが、`analysis-storage.js:55–56,143–156`はResearchVault conflict等に保存履歴の再試行buttonを出す。`POST /api/analysis/runs/<run_id>/vault`（`web/analysis_routes.py:347–354`）→`AnalysisCommands.retry_vault`→`AnalysisStore.retry:447–451`→publishは既にある。範囲は全保存bundleでありResearchだけではない。『ResearchVault失敗に再試行手段がない』とは書かず、既存archive再試行とpipelineのallowed action/対象別retryを区別する
- OFFはその基礎pipelineのpublish工程の話。AI見解成功時の自動archive（`analysis_jobs.py:127–130`→`archive_group_analysis`→store.save既定publish=True）等を止める全体設定ではない。OFF時ResearchVault pendingを「今回未完了」と誤表示しない

## 3 failed: ラベルと実際の動作

- `analysis_pipeline.py:823–831`: failedならallowed_actions=[]。waitingならcancelに加え、step失敗等があればretry_failed、公開待ちならretry_publication
- `analysis-execution.js:463–466`: failed/waitingはreview button表示。retry_publicationがなければ一律「失敗した処理を再試行」
- `:620–625`: retryで始まるallowedActionがなければhide execution→open settings。`:628–632`だけがretry POST
- `retry:847–861`のendpoint自体はfailed/interrupted/cancelled stepがあれば受理し得る。能力が存在しないという主張にはしない

`microcopy-action-probes.js/.json`で元renderer/handlerを合成DOM実行し、failed/[]、waiting/[cancel]は再試行labelのままsettingsへ、retry_failed/retry_publicationありはretry POSTへ進むことを確認。backendのfailed []も純粋static methodで確認済み。実browser未実施。

推奨: action labelをstatusだけで決めずallowedActionsとhandlerの実効果へ結び付ける。retry_failedなら再試行、retry_publicationならVault保存工程の再試行、それ以外は設定を見直す。部分target限定の再試行は上記scope契約が整うまで言わない。

## 適用と未実施

統合担当・microcopy担当へ、検証できた条件だけを送った。既存ソース/テスト/原25件の評価は変更しない。追加probeは本番データやVaultへ触れず、artifact directoryと一時合成SQLiteのみ。新しいwriter scope、ResearchVault gate、文言、実GUIの実装修正はこのレビューでは行っていない。
