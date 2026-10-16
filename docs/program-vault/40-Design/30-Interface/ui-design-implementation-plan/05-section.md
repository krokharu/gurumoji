---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-05
title: Gurumoji UI改善の実装計画：W04 固定runと根拠への往復を見える契約にする
summary: W04 固定runと根拠への往復を見える契約にする。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 102
- 133
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：W04 固定runと根拠への往復を見える契約にする

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

### W04 固定runと根拠への往復を見える契約にする

- 対象: `app.js:5757–5814`、`analysis-storage.js:43–69`、`analysis-content.js:45–122`、`analysis-execution.js:316–325,651–655`
- 作業: 対象／表示版／対象集合／fresh-stale／作成時刻を共通帯へ。完了から固定runを開く入口を設計し、通常の現在データ集計と区別する。`AnalysisStore.public:315–321`のartifact URL、保存packageのinput.json／result.json／manifest、既存artifact読取APIを先に再利用できるか調べる。不足分だけ最小のread API追加を別契約にする
- 読取境界: 固定成果物の閲覧と実行中jobの状態取得を分ける。現行pipeline statusは再起動でinterruptedになった待機runを自動retryする場合がある（`analysis_pipeline.py:766–770`）。GETという形式だけで副作用なしと仮定せず、固定結果ビューからその回復経路を呼ばない
- 復帰: `{item, run, page, filter, selectedEvidence, scroll, focusOrigin}`相当を既存navigation stateへ対応付ける。新しい永続session storeを先に作らない。根拠panel案は既存detailsを使う案と比較する
- 狭幅の文脈: 主張全文又は意味を保つ要約、AI下書き、取得できた確認状態、解釈の限界、選択発話IDを根拠と一緒に残す。「確認記録なし」と読取不能を分け、人の未読と同一視しない。B mobileで研究者メモを別状態へ置く負担を比較に含める。現在発話の対応元を確定できない場合、その移動buttonも有効にしない（MC-02/06）
- 合格: シナリオS04/S05。入力更新後も旧runの版・引用が変わらず、stale/unknownを保持。根拠から同じ結果・位置へ戻る。出力と画面のrun/hash/revisionが一致
- 出典: DG-06/12、UX:S04/UX:S06/UX:S17/UX:S20、PR:T5/PR:T6
- 移行／rollback: readonly表示を先行。新paneを戻しても既存根拠リンクが使える。hash・結果の再生成や旧runへの情報補完は行わない

#### W04 固定viewerの最小契約案

現行の結果buttonは現在itemを再読込するため固定viewerではない。まず`ai_insights`と`milestone_analysis`の保存済みpackageをread-onlyで扱い、他kindは既存の正しいartifact downloadを残して「画面表示は未対応」とする。current/live workspaceへの無言fallbackを禁止する。

| 表示するもの | 現行の取得元 | 新adapterでの扱い |
|---|---|---|
| run／対象／入力版／日時 | manifest.jsonのanalysis_id/conversation_id/source_revision/analysis_revision/created_at/input_fingerprint | 選択run・一覧metadata・input.jsonの識別子と照合。不一致なら停止、欠落は不明 |
| 生成時の発話・条件 | input.jsonのsegments/config/annotations/preparation、original_source | snapshot内の発話IDへ戻す。現在本文から補完しない。時刻欠測を0秒表示にしない |
| AI見解と引用 | ai_insightsのresult.json内analysis.insights.ai.findings/evidence | AI下書き表示とvalidation_noteを維持。欠けた引用は欠落として示す |
| 基礎pipeline結果 | milestone_analysisのresult.json内methods/chart_specs/parameters、tables/*.csv | 対応したmethodの読み取り表示のみ。schema未知はdownloadへ。全手法rendererやXLSXを装わない |
| 保存byteのhash整合 | 既存artifact API→AnalysisStore.read_artifactのDB hash照合 | 既存読取を維持し、409/404を現在値で埋めない。hash一致を意味・版の整合と同一視しない |

根拠: `services/analysis_archive.py:60–103`、`services/analysis_jobs.py:114–130`、`analysis_pipeline.py:557–603`、`analysis_store.py:304–321,400–423`。`result.analysis`を丸ごとliveの`analysisState.data`へ差し込まず、既存の表示用部品を使うadapterで取得元を分離する。ただしevidenceDetailsは欠落IDをskipし、欠測時刻を0表示するため無変更では使えない。欠落ID・件数を明示し、時刻不明の表示へ修正する。根拠・音声guardはcallback／文脈を明示して再利用し、liveのpoll・再集計・保存handlerを呼ばない。

- 意味の整合: milestone結果のparameters.binding内の定義版とparameters.definitionsの版も照合する。旧runの不一致・確認不能は『定義版の整合を確認できない』と表示し、自動比較・確認済み表現を止める。元artifactを保持し、最新定義で来歴や値を書き直さない
- 読取入口: 一覧由来なら既存artifact URLを使う。現在は任意run IDのJSON lookupがなく一覧は100件で切れるため、再読込／深いリンク用に`GET /api/analysis/runs/<run_id>`相当の小さいread lookupを提案。既存store.get/publicと対象存在確認、runsと同じ現入力fingerprint照合を再利用し、artifact URLを返す。現入力を照合できなければfreshとせず不明。worker/status/retryを呼ばない。全bundleの再構築や任意filesystem pathを受けるAPIは不要
- URL案: `#/analysis/<item>/saved/<run>`。既存`/run`実行画面・旧hash/queryと分け、live routeより先に判定する。現parseRouteHashは後続要素を無視するため、route拡張は必須。lookup完了前に現在データを表示しない
- 復帰範囲: 同tabの根拠往復とBack/Forwardはentryごとのpage/filter/evidence/scroll/focus識別子をhistory.stateへ保持。全文／DOM node／tokenは保存しない。reloadは同じ固定runをURLから復元し、history contextが有効なら復元、欠落なら同じrunの概要・見出しへ戻す。新tab／sessionを越えた完全な位置復元は約束しない。既存syncRouteHashのnull state上書きを調整する必要がある
- 原音と現在編集への移動は明示操作。本文・話者・有効な時刻が照合できない引用は自動seekしない。既存Number差分比較はmissing/NaNを明示拒否しないため、生成時と現在の両方でnull／空値／time_unknownを拒否し、有限・非負・start≤endを確認してから差分を照合する。変更後のreturnは固定readerを呼び、現在itemを開く`returnToAnalysisEvidence/openAnalysisForItem`へ戻して済ませない。未保存確認を保つ
- rollbackは表示adapterを外しても固定URLのguardと正しいrunのdownloadを残す。旧parserへ全面撤回してsaved URLを現在データとして解釈させない。404／hash conflict／未知schema／引用欠落／履歴100件外／reload state欠落のfixtureが通るまでW04は契約レビュー中
