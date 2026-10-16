---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-03
title: Gurumoji UI改善の実装計画：W02 手動測定を意味の確認から採用へつなぐ
summary: W02 手動測定を意味の確認から採用へつなぐ。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 60
- 88
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：W02 手動測定を意味の確認から採用へつなぐ

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

### W02 手動測定を意味の確認から採用へつなぐ

- 対象: `index.html:243–249`、`analysis-execution.js:50–64,542–557`、`analysis_core.py:151–198`、`analysis_pipeline.py`の定義保存／試行
- 推奨: backendが対応する入力列・規則・型・尺度・手法をUIへ接続する。まず文字数、duration、カテゴリの度数等の検証済み組合せを説明付きで提示し、詳細選択は実validatorの制約と合わせる。独自の許可組合せを推測しない
- 必須の小さいAPI拡張: 現行`trial_definition:258–280`は`values[:20]`と件数・`input_hash`を返すが、発話ID・欠測行／理由・定義revisionを落としている。既存values／件数を保ち、`measure_segments`が持つrowsと欠測理由、試行した定義revisionをresponseへ追加する。現在の本文から有効値の発話対応を推測しない。入力hashは既存値を利用し、新しいfingerprint体系を作らない。rowsだけにも元の本文／時刻はないため、同じtrial snapshotから測定に用いた入力値を上限付きsampleとして返すか、その固定入力への参照を返す。現在本文とのjoinは禁止。保存するsampleの範囲・サイズ制限は契約レビュー事項で、再open時に固定入力を復元できない古いtrialは再試行を案内する
- 採用の区切り: 試行の個票・要約・欠測理由→明示採用→全件実行。定義revisionと入力版が試行時から変われば再試行を要求するか、確認無効を明示する。Close／Cancelで意図せずadopt/pipelineを送らない
- 表示と失効: 試行した定義版・入力版、全体／除外／試行数、欠測と真の0、測定の限界を採用前に短く示す。編集後は古い試行を履歴扱いに下げ、確認と採用を無効にして再試行を主操作へ。変更field・未保存内容・focusは保ち、補助storyboardのために編集面全体を置換しない。欠測行の確認linkは発話IDを含む名前を持ち、固定試行入力を開く。採用応答不明では成功を推測せず正式状態を再確認する（[静止批評](../../../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)MC-01/03/04/05。描画上の補強であり動作は未検証）
- 既採用版の保護: `analysis_definitions`はitem＋definition IDごとの1行で、draft PUTも旧adopted payloadを上書きする。第1段階は既採用を直接編集せず別draft IDに複製し、採用時に新IDを選択する案を推奨。旧IDとの関係表示を設計し、将来の版履歴schemaへ暗黙に広げない。取消時は未採用draftとして残す範囲を示し、旧payloadへの逆PUTで並行更新を巻き戻さない
- 小さい代案: 現行を「文字数測定」と明示し、text／text_length／number／ratio／descriptiveを読み取り専用表示に限定する。即時の誤認抑制には有効だが、既存APIのduration等はUIから使えない。採用確認は省略しない
- API判断: 第1段階は既存draft/adoptedを利用。採用PUTでもrevisionが増えるため、試行した内容の版rと、同内容を採用した版r+1の対応を示す。画面変更があれば内容を比較し直し、単なるstatus更新を別の測定内容と混同しない。クライアントの『試行レビュー済み』を永続保証と呼ばない。サーバーでレビューgateを保証するなら、definition revision＋入力fingerprint＋trial IDを結ぶ追加契約を別レビューし、既存client互換と旧adopted定義の扱いを決める。上記5〜9日は画面2〜4日＋backend契約／競合回帰3〜5日の概算。人のレビューを永続保証するserver gateは含めず、契約設計後に追加見積りする
- 合格: シナリオS02。受付後に定義を変えても固定内容で実行するか、理由付きで安全停止し、異なる値を正常確定しない。本文3/10文字・実時間60/2秒の対照で、選んだdurationは60/2、文字数は3/10。名義尺度への平均は拒否。明示採用前はadopted PUT/pipeline POSTが0回。編集／対象変更／revision競合後の古い試行を採用しない
- 出典: DG-02、反証H3＋[定義lifecycle probe](../../../50-Tests/ui-design-evidence/2026-10-02/definition-lifecycle-probe.json)／[全pipeline合成probe](../../../50-Tests/ui-design-evidence/2026-10-02/definition-full-pipeline-probe.json)、UX:S01/UX:S05/UX:S15/UX:S17、PR:T11。採用UIが研究の妥当性を保証するとの主張はしない
- 必須の実行境界対策: `_run:635–643`はbinding記載versionでなく現行IDを再読する。`definition-lifecycle-probe.json`は受付binding v1→同IDのduration v2→実測定60秒（v1なら3文字）を隔離再現。`definition-full-pipeline-probe.json`は元の_runをM0〜M7 completedまで実行し、保存adapterにbinding v1／definitions v2／値60が混在することも確認した。合成adapterによる試験で、実ディスク保存・GUIは未試験。最小修正は版／内容不一致で安全停止し、最新定義へ自動置換しないこと。推奨の本対応は、受付時に採用定義の完全なpayload・版・hashを固定して実行／再開／保存で同じ内容を使うこと。人のレビュー確認gateとは別に必須とし、UIの完了条件から外さない
- 旧runの扱い: 固定payloadのない既存待機runは一致を証明できる場合だけ進め、不一致・不明を現行定義で埋めない。安全停止案は変更後の継続性が下がるが誤計算を止められる。snapshot案は元定義で再開できる一方、契約version・旧run互換・原子的な固定の追加試験が必要。完了済み成果物は再計算・来歴の書換えをしない
- 移行／rollback: 旧定義やrunの再計算・自動改名なし。既存adoptedは『過去の定義・確認記録不明』等、取得できる来歴だけ表示。追加metadataを入れた場合は旧reader互換を試し、rollbackで新定義を削除しない

#### W02 保存とrollbackの提案契約

以下は**新設する契約案で、現行実装ではない**。最小の版不一致停止を先行し、本対応はこの境界を満たしてから有効にする。

- 保存先は既存`analysis_pipeline_requests.binding_json`を拡張する。`resolved`を残し、`definition_snapshots`にIDごとの採用payload／version／canonical hashを保持する案。別DBやmutableな定義参照を正本にしない。新contract versionとbinding hashの対象へsnapshotも含め、入力snapshotと区別する
- 受理境界は単にJSONを同時INSERTすることではない。同じ受理transactionでdefinitionを読取り、expected version／採用状態を再確認し、payloadとhashを固定してplan／binding／input snapshotと保存する。previewと受付の間の更新は409。別connectionを開く現`_definitions`をそのまま呼んで原子的とみなさない。workerは確定payloadのみを検証・計算・再開・保存へ渡す
- 旧manual runに固定payloadがない場合は、現在値から旧版を復元したふりをしない。再開は既定で止め、旧成果を保持し、現在の定義から別runを作る判断へつなぐ。定義を持たない旧automatic runは別の互換fixtureで検証する。completed成果物は変更しない
- 旧workerは未知のbinding field/versionを安全に拒否せず、最新IDを読み直す。したがって**新形式を保存した同じruntimeへ旧binaryを直接戻すrollbackは未承認・未検証**。通常の戻し方は安全性修正を残すhotfix版へのUI撤回。旧binaryが必要なら別途互換計画と一時DBでの試験を完了するまで起動しない
- compat guardはDB初期化／回復より前に必要。現`handlers/application_lifecycle.py:43–49`はOS lock後にinitialize、`services/library_schema.py:387`からpipeline初期化がactiveをwaiting/interruptedへ更新する。OS lockは複数processを防ぐが、同processのHTTP／worker並行実行まで直列化しない
- 互換検査はpending数だけで判定しない。`retry:847–899`が扱うfailed/interrupted/cancelledを含む全非completed新形式runと再開可能attempt、definition row、新artifactを対象にする。backup取得・guard・全対象の分類・復元dry runが揃うまで全アプリdowngradeは停止条件。復元で後続の研究者編集を消さない

必要な追加受入は、受理直前／直後の並行編集、複数HTTP、restart/retry、旧manual／旧automatic／新形式の3種読取、旧worker起動前guard、artifactのbyte/hash保持。保存field名とcontract versionの最終採用、実DB dry run、実worker互換は未実施であり、この文書の追記では解決済みにならない。
