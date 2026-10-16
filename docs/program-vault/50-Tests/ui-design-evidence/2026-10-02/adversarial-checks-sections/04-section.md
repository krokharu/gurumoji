---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks-section-04
title: 'Gurumoji デザイン監査の独立反証チェック：第3巡: DESIGN初稿と実装計画の契約レビュー（18:57–19:06 UTC）'
summary: '第3巡: DESIGN初稿と実装計画の契約レビュー（18:57–19:06 UTC）。出典ノート「Gurumoji デザイン監査の独立反証チェック」の分割本文。'
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks
source_path: 50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md
source_sha256: fec531750b3b1eeb8616de26b52688a81b740a197d67d9f5682156883db2fd50
source_body_lines:
- 164
- 216
split_on: '2026-10-11'
---

# Gurumoji デザイン監査の独立反証チェック：第3巡: DESIGN初稿と実装計画の契約レビュー（18:57–19:06 UTC）

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/adversarial-checks]]。必要な本文だけを取得する。

## 第3巡: DESIGN初稿と実装計画の契約レビュー（18:57–19:06 UTC）

対象: `draft-DESIGN.md`、`design-implementation-plan.md` W00–W09、`agent-design-knowledge.md`、`user-scenario-walkthroughs.md` 初稿0.1。本文は編集せず統合担当へ修正要求を送った。

### 1. W02の個票レビューにはtrial response拡張が必要

現行 `analysis_pipeline.py:258–280` は `input_hash`、definition ID、sample/valid/missing件数、**欠測を除いたvalues配列（最大20個）**を返す。元の `measure_segments:129–146` はsegment IDと欠測理由を持つがtrial返却時に落としている。したがって、S02の「e3は欠測理由付き、e4は0」という個別確認をUIだけで作れない。

要求した修正: 既存fieldsを保持してrows（segment ID/value/missing reason）と測定したdefinition revisionを追加する小さなresponse契約変更を、永続review gateの強化と分ける。現在の本文とvaluesをUIが順番で推測して対応付けてはならない。input_hashは既存なので重複導入しない。

### 2. W02の既採用保護と固定版実行は、現行APIの無料の保証ではない

**同じIDのdraft保存で旧採用を置換する:** `analysis_definitions`は(item_id, definition_id)を主キーとする1行の現行状態。`:227–256`はdraft PUTでもpayload/status/revisionを上書きする。adopted v1→draft v2を行うと旧adoptedは定義表から取得できなくなり、`:221–224`は `definition_not_adopted`を返す。既存runのsnapshotまで削除するという意味ではない。

**bindingの版とworkerの定義がずれ得る:** `start:358–365`はversion付きbindingを保存するが、`_run:640–643`はIDだけで現在の定義を読み直す。`_execute_step:496–499`はその現在定義で測り、`_save_package:569–572`は古いbindingと現在definitionsを同じpackageに入れる。

独立再現:

- `definition-lifecycle-probe.py/.json`: in-memory SQLite。draft上書きで1行だけ残り旧adopted lookup失敗。別例でaccepted binding v1→現行adopted v2更新→元worker定義ロードprefix＋元manual stepを実行。v1文字数3のはずがv2duration60秒をcommittedにする
- `definition-full-pipeline-probe.py/.json`: 一時合成SQLite、元M0–M7 `_run`。受付後の `_schedule`だけをpauseして定義更新を挟み、実orchestratorを実行。全M0–M7はcommitted、pipeline completed。**save adapterへ渡されたpackageはbinding version1、definitions version2、測定値60.0**。元v1なら3文字
- 後者のmethod_runner・save/publication adaptersはstub。実モデル、実成果物ファイル保存、Vault公開、HTTP UI、通常schedulerでの発生頻度は試していない。保存adapterへの不整合payloadと元pipelineの状態確定を証明する。これを「実ファイル破損を観測」とは書かない

要求した修正: W02をUIレビューだけで完了としない。既採用の編集を別draft ID/不変版/非保存trialのどれで保持するか決める。Cancel時の逆PUTによる巻戻しは他clientの更新を壊し得るので避ける。workerでは受理時の定義実体を保持して使うか、bindingと現在版の不一致を実行前に拒否する保証が要る。再試行・再起動でも同じ保証を確認する。元25件の計数は変更せず、DG-02に対応する追加技術依存として記録する。

### 3. W04は既存artifact読取を先に検証する

`AnalysisStore.public:315–321` はartifact URLを返し、保存物には `input.json`、`parameters.json`、`result.json`、`manifest.json`がある（`:400–430`）。manifestにrun ID、snapshot ID、入力fingerprint、revision、artifact hashが入る。`AnalysisQueries.artifact:81–92`と`run_bundle:95–107`が読取を提供する。

要求した修正: 固定run画面のための新read APIを必須と決めず、これらのsnapshot/result/manifestを安全に再利用できるか先に調べる。public runの要約だけにはhashが出ないため、取得していないhashを表示へ補完しない。未取得・legacy欠落はunknownとする。

注意: `AnalysisPipelineService.status:766–770` は再起動由来のinterrupted待ちをstatus GETから自動retryする条件を持つ。**GETだからすべて副作用なし**とは扱わない。固定成果物の閲覧と、既に承認された実行の復旧を区別し、閲覧APIへpipeline statusの自動回復を無条件に混ぜない。

### 4. W06のcursor受入は対象集合を定義する

`created_at + id`のkeysetは固定行の安定順序には適切。しかしページ途中の新規runがcursorより前に挿入されれば、進行中scanには入らない。これを「新規も全部含めて欠落なし」と呼ぶのは過剰。単なる最大key cutoffも、後から同時刻・より小さいIDの行が入る場合の厳密なsnapshot membershipを自動では保証しない。

要求した修正: 初回時点の集合を固定する方式か、新規はrefresh後に表示するlive方式かを選び、受入の集合を明示。cursorにfilter/sort/集合条件を結び、別条件への使い回しを拒否する。旧clientの既定100件応答と既知artifactリンクを保つ。厳密snapshotの追加sequence/tokenが必要なら「schema変更なし」を絶対条件にしない。

### 5. S02の真の0秒は現行契約に整合する

`transcript_preparation.valid_time:105–113`は0<=start<=endを許す。`analysis_pipeline.py:114–123`はvalidな非負durationを受け入れる。e4をstart=end=80、duration=0、time_unknown=falseと明記すれば0は正しい。e3は時刻欠測、またはtime_unknown=true/valid_time=falseでdurationの数値placeholderが0でも欠測とする。既存 `test_analysis_research_protocol.py:34–49` に同じ対照がある。

要求した修正: fixtureの真の0と「時刻が不明なので内部値だけ0」を明示。現在のtrial APIには欠測の個票返却がない点は上記1へ戻る。

### 6. 状態不明とdirty navigationの安全な表現

- W03の「未知stateは停止／詳細確認」はbackend停止を保証できない。未知状態・最終確認時刻・再取得/詳細確認とし、実行中/停止/成功を推測しないよう修正要求
- S03でBを未保存編集してAへ移るときは既存confirmLeaveの分岐を含める。移動を取り消してBを保つ、または保存してから移るのも成功経路。未保存guardを迂回して複数item draftを保持できることを既実装契約としない。Aの完了がBの編集画面を自動置換しない条件は維持

### 7. 受入とrollback全体の判定

初稿のV1〜V5分離、source/GUI/ATの未確認表示、原25件の維持、実データと外部AIの除外、局所adapterから戻す方針は妥当。上記W02の定義版保護は、見た目のrollbackだけでは解決しないため別の保存・互換性条件にする。安全な既存readerは新定義を消さず、取得不能な版を現在版で置換せず、停止理由を説明する。
