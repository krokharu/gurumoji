---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-03
title: Gurumoji 改善セッション：2026-10-04 01:01 UTCの統合区切り
summary: 2026-10-04 01:01 UTCの統合区切り。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 93
- 109
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：2026-10-04 01:01 UTCの統合区切り

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 2026-10-04 01:01 UTCの統合区切り

- 固定source `ed7a3f1` で標準pytest **1017成功・32skip・953 subtests成功・失敗0**。同HEADの既定DOM suiteは **72成功・失敗0**。32skipはbrowser22・Windows10で、実画面／ATの合格を意味しない
- 特殊な話者ID、話者controlの名前と再描画focus、履歴リンクの許可境界、話者editorの欠測表示、古いroute応答、分析Saveの所有権を独立レビューして統合。旧sourceを用いたnegative controlは同じ正しい期待値で失敗することも確認した
- 一時的な実行環境切断で旧全体試験が途中終了した。未完了ログを残し、同HEADで全体試験をやり直して成功を確認。作業tree・commitは保持された。途中終了を成功として計数しない
- 復元可能なsourceには専用branchの未統合回帰も含める。未統合のfixedviewer／測定dialog／backend欠測は上の作業ボードのまま追跡する。実データ・外部AI・公開・deployには接触していない
- 根拠は `../artifacts/eight-hour-20261003/integration-dom-recovery/`、独立UIの初期ログは `../artifacts/ui-review/`。source復元手順を本ノートへ追加した

## 2026-10-04 01:22 UTCの統合区切り

- 固定source `9c92b6b` で標準pytest **1026成功・32skip・959 subtests成功・失敗0**、同HEADの既定DOM suite **92成功・失敗0**。browser22・Windows10は未実行のまま
- `focus-group-local-5`／registry9で、時間欠測を実0と分け、対象集合に欠測がある割合・均等度を非算出にした。部分観測は時刻あり小計とcoverageを併記し、未観測の0秒グラフを描かない。巨大JSON整数の時刻も500ではなく欠測扱い
- 旧v4の受付済みsnapshotは旧数値・旧計算版のまま保存され、新v5はnull/空欄を使う。実Flask・保存CSV・固定GETのbytes不変を独立確認。新仕様を過去結果へ遡って適用しない
- fixed runは編集側Saveから独立して読める。保存時入力との比較は取得時点と明示し、同itemの後続編集を現在一致の保証へ取り違えない。測定定義dialogは再open時のbusy解除とnavigation時の同期終了を追加した
- 外部consumerは `speaking_seconds`・`total_speaking_seconds`・割合のJSON null／CSV空欄を受理できるか採用前に確認する。自動的に0へ補完して旧意味へ戻さない。DB schema・原入力・実runtimeの移行は行っていない
- 同itemの分析Save完了による測定dialogの入力版失効、未確定roleの表示、混在roleの順序依存は別課題として継続。根拠は `../artifacts/eight-hour-20261003/integration-timing-dialogs/` と `analysis-recovery-review/`、`ui-recovery-review/`
