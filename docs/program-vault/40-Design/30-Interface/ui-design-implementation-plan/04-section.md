---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-04
title: Gurumoji UI改善の実装計画：W03 実行状態と実際のVault書出しを一致させる
summary: W03 実行状態と実際のVault書出しを一致させる。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 89
- 101
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：W03 実行状態と実際のVault書出しを一致させる

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

### W03 実行状態と実際のVault書出しを一致させる

- 対象: `analysis-execution.js:393–476,602–636`、`index.html:267–268`、`analysis_pipeline.py:476–482,583–588,607–632,737–750,823–831`、`analysis_store.py:175–209,588–697`、`app.py:1562–1582`
- 表示: accepted／running／waiting／failed／cancelling／cancelled／completedを同じ表示mapから出す。failedのallowed_actionsは現行で空なので、設定画面を開くreviewを「再試行」と呼ばない。中止の送信中・受付済み・完了と、通信取得失敗を別にする。同状態pollでは通知を重ねず、保存成功後の追加編集は未保存のまま示す
- 確認した保存境界: API enumと台帳は3生成先だが、非空targetsは`store.publish(run_id)`へ渡り、選択を渡さず3生成先＋ResearchVaultを試みる。inputだけの指定でも他2先はnot_selectedと記録され、Research conflictでもcompletedになった。元M0〜M7＋元store.publishと合成adapterによる[probe](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)であり、実Vault書込みやGUIでの発生確認ではない。通常UIは全3先ON／空OFFのcheckboxで、部分指定はAPI条件として区別する
- 直近のguard案: 当面は空配列、または正確な全3先集合だけを許し、ONはResearch込み4経路の一括保存と説明する。部分集合はwriter前に明示4xxで拒否し、Researchをenumへ無断追加しない。現APIは部分指定を受理するため、contract versionと既存client／再試行の互換試験が必要。全4先成功は各結果の照合まで表示しない
- 完全対応のgate: requested targetsと実際の保存先集合を受理時に固定し、各writerへscopeを渡す。Researchの選択規則も明示し、対象外writerは呼ばない。run／attemptごとに各先のrequested・実行有無・成否／競合／不明を記録し、取得不能を成功やnot_selectedへ変換しない。3先台帳だけで4先の完了を判定しない。旧completedは3先gateの履歴として保ち、新しい4先成功へ遡及変換しない。本体・各先の結果とnote policy上のmissingを別表示し、publishedを全ノート存在の保証にしない。研究者の削除を再作成して見かけの成功にしない
- 再試行のgate: 表示した範囲だけのwriterを再度呼び、保存済み固定packageを使う。計算・外部AIや未対象先を起動しない。Research conflictでも既存保存履歴の「保存済み結果から再試行」→`POST /api/analysis/runs/<run>/vault`→`AnalysisStore.retry:447–451`は全保存工程を再訪できるので、範囲を示して再利用する。OFFで未実行のrunもpendingからこの入口が出るため、その場合は「Vaultにも保存」と新たな保存範囲を明示し、失敗した処理の再試行とは説明しない。pipeline completedの新しい再試行action、Researchのみ等の部分再試行は別契約。Researchのみ失敗・generated先のみ失敗・再起動後の不明を分けて試験する
- 合格: S03で空・全3・部分集合、各先の成功／競合／失敗／不明をstubに注入。空はこのpipelineの全Vault callbackが0回、未対象writerも0回。要求→有効保存先→writer trace→返却outcome→台帳→画面が一致する。全3成功＋Research conflictを全保存成功にしない。OFFは他のAI見解自動archive等を止める全体設定ではない
- 文言: 「設定済みのVaultにも保存」と実際の4経路・場所・実行環境を対応付ける。本体ファイル／Research／各生成先を分け、閲覧端末へのダウンロードと混同しない。計画相談の「発話本文を自動では含めない」は入力目的文に貼った本文まで送らない保証ではない。具体文は[文言仕様](../ui-microcopy-state-catalog/00-Index.md)J06〜18/J25を条件付きで再利用する
- 出典: DG-03/11、反証H4、文言仕様、[独立契約確認](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md)と追加probe、UX:S12/UX:S26/UX:S31、PR:T5。旧14項目の監査を上書きせず、追加の契約所見として追跡する
- 移行／rollback: 表示adapterは単独で戻せるが、scope guardを外して広い副作用へ戻さない。新しい保存先／outcome fieldは後方互換・旧run／旧client・再開のfixtureを先に用意する。新契約と実Vault dry runは未実施。未知stateは最終確認時刻と再取得／詳細を示し、実行中／停止／成功を推測しない
