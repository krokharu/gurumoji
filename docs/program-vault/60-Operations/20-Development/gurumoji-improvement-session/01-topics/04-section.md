---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-04
title: Gurumoji 改善セッション：2026-10-04 01:36 UTCの統合区切り
summary: 2026-10-04 01:36 UTCの統合区切り。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 110
- 126
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：2026-10-04 01:36 UTCの統合区切り

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 2026-10-04 01:36 UTCの統合区切り

- 固定source `1cf236f` で標準pytest **1027成功・32skip・959 subtests成功・失敗0**、既定DOM suite **95成功・失敗0**。Node/browser/Windowsの範囲は前区切りと同じ
- 来歴未確定の会話役割を含むeditor insightは仮集計と明示し、未確定人数を示す。default／legacy_unknown／未知sourceを勝手に明示役割へ変えない。明示・registryの通常表示は保持
- 分析Saveで入力版が更新された測定dialogは、入力済み文言を保持して旧試行・確認・採用を失効させる。未送信の下書きIDは保持し、保存済み／送信中IDは元を保護する新しい下書きIDへ分ける。理由を表示し、自動の定義送信や採用はしない。主分析の後続未保存変更があれば操作制限を保持
- 混在role backendは候補 `c6abf58` の独立受入まで進んだが、この主branchにはまだ含めていない。v6と旧v5固定値の区別、役割混在による非算出と時刻欠測による非算出の表示を最終確認する。固定runの保存計算版の表示も別の次課題
- 根拠は `../artifacts/eight-hour-20261003/integration-input-role-ui/`、独立roleの `analysis-recovery-review/`、定義文言保持の `ui-recovery-review/`

## 2026-10-04 02:43 UTCの統合区切り

- 固定source `a91eec3` で標準pytest **1048成功・32skip・1025 subtests成功・失敗0**、同HEADの既定DOM suite **151成功・失敗0**。前後HEADとclean状態を確認。32skipは実browser22・Windows10、既存loky warning1。異なる層の件数を合算しない
- 混在roleのv6、保存計算版の表示、固定packageのmember/snapshot検証、v7の残る時間欠測、editorの数値文字列・時刻編集再描画を統合した。全欠測を0にせず、真0と空集合を保持する。役割不確定による非算出と時刻不明を区別する
- `397be30` の全体試験は **1045成功・1失敗・32skip・1017 subtests成功**。失敗は旧専門家sampleが仮の0 timeline行を結果とみなしたassertだった。`c456795` はproductionを変えず、empty／not_run、保存結果レビューなし／現在のblocked前提条件、4空表と固定CSVを明示確認する。旧失敗ログは保持し、最新の合格に置き換えて数えない
- 互換性: JSON null／CSV空欄とcoverageを受理できるか外部consumerで確認する。追加nullableはlibraryの`duration`、分析の`session_duration`、感情の`seconds`、コードの`speaking_seconds`も含む。session終端は除外を含む全発話の最大終了位置で、録音全長やincluded発話合計とは別。旧v4〜v6の固定値と元計算版を保ち、新意味を遡及適用しない
- full GETの`segment_timings`は元ID/原値/順序/件数に結び付いた表示専用値。原入力や保存payloadへ混ぜず、局所変更・不正値で数値guardへ戻す。音声再生guardを緩めない。通常の数値時刻編集で内部20秒なのに画面10秒となる旧不具合も独立DOMで反転確認した
- 根拠は `integration-projection-contract/`、`analysis-recovery-review/`、`ui-timing-review/`（いずれも証跡root配下）。実browser・AT・Windows・実モデル・実Vaultは未実施。手動受入の短い確認表は証跡 `ui-timing-review/final-ui-handoff.md`。次は独立cloneから空runtimeだけで起動/停止/再起動を確認し、最終受け渡しを整える
