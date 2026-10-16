---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks-section-05
title: 'Gurumoji デザイン監査の独立反証チェック：第4巡: 固定定義snapshotの旧worker互換（19:20–19:22 UTC、追加probeなし）'
summary: '第4巡: 固定定義snapshotの旧worker互換（19:20–19:22 UTC、追加probeなし）。出典ノート「Gurumoji デザイン監査の独立反証チェック」の分割本文。'
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks
source_path: 50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md
source_sha256: fec531750b3b1eeb8616de26b52688a81b740a197d67d9f5682156883db2fd50
source_body_lines:
- 217
- 237
split_on: '2026-10-11'
---

# Gurumoji デザイン監査の独立反証チェック：第4巡: 固定定義snapshotの旧worker互換（19:20–19:22 UTC、追加probeなし）

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/adversarial-checks]]。必要な本文だけを取得する。

## 第4巡: 固定定義snapshotの旧worker互換（19:20–19:22 UTC、追加probeなし）

統合担当の「version付き完全definition payload＋canonical hashをbinding JSONに保存し、旧binaryへ無条件rollbackしない」という方向は現コードと整合する。ただし次を追加要件として送った。

1. **pendingゼロだけでは旧worker安全性を判定できない。** `analysis_pipeline.retry:847–861`はfailed/interrupted/cancelled stepも再実行候補にする。新形式の非completed runと再開可能attempt全体を互換確認対象にする。完了済みartifactの読取互換は実行互換と分ける
2. **互換guardはDB初期化・回復より前。** `handlers/application_lifecycle.py:43–49`はinstance lock取得後にlibraryを初期化し、`services/library_schema.py:387`が`initialize_pipeline_store`を呼ぶ。同`:79–90`はactive stepをinterrupted、active pipelineをwaitingへ更新する。旧binaryを一度起動してから互換性を判定する運用では、すでにstateが変わり得る。launcher/互換hotfix側の起動前guardが必要
3. **単一process≠単一request。** `services/instance_lock.py:17–30,57–80`と`app.py:445–453`のOS file lockは同data/uploadsへの第二app processを防ぐ。`analysis_pipeline.py:37,402–413`のRUNTIME_LOCKはprocess内のworker二重起動を防ぐ。一方でHTTP要求や独立stepは同process内で並行できる。snapshot、plan、bindingの書込みを1transactionにするだけでなく、対象定義の読取・expected revisionの再検証・内容固定を同じ受理境界で行う

これらは現コードの静的確認で、旧binary起動・データ移行・rollback実行を行った結果ではない。新しい保存契約の採用前に一時データで互換／停止／再開を検証する必要がある。

## 第5巡: W01復旧時の分類late-response境界（19:22–19:24 UTC）

統合担当の指摘を `classification-late-response-probe.js/.json` で独立検証した。元 `runSegmentClassification` 関数とsynthetic deferred fetchを使い、AへのPOSTを保留→表示対象をBへ変更→Aの成功responseを返すと、**Bの`analysisState.data.segment_classification`がAの結果に置き換わり、成功通知もB上へ出る**。

- `analysis-method-view.js:312–347`は送信時のitem/revisionをPOSTに入れるが、await後`:335`で現在のglobal stateへ直接代入する。復帰時item/revision/sequence照合はない
- `app.js:356–364`のapiFetchはheaderを付けてfetchするだけ。`:5878–5892`のAbortControllerはanalysis GETに渡され、分類POSTには渡されていない
- `segmentClassificationInProgress`は分類開始buttonのdisabledに用いられるが、dirtyなしの対象変更をロックする条件ではない（全src参照、`:1072–1073,1113–1135,5868–5917`）
- 比較上の反例: TransformerとAI見解はitem別content stateを保持し、開始responseのfinallyでもitem IDを照合する（`analysis-content.js:933–944,1171–1191`）。したがって3入口すべてが同じlate-response問題だと一般化しない

**制限:** 現在の分類開始buttonはDG-01のCSSで非表示。今回の結果はhandler境界の確定した隔離再現であり、現行通常UIから起きた観測ではない。サーバー側保存の取り違え・実データ損失・実ブラウザーの表示は検証していない。W01で入口を復旧する前のitem/revision/要求世代guard、target-switch/late response受入へ接続する。原25件の完了評価は変更しない。
