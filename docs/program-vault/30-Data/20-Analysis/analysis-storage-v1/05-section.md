---
note_type: reference-section
status: current
feature: analysis-storage
verified: 2026-10-05
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/obsidian
note_id: program-analysis-storage-v1-section-05
title: AI仕上げ・文章分析の保存契約 v1：固定runの保存版表示（2026-10-04）
summary: 固定runの保存版表示（2026-10-04）。出典ノート「AI仕上げ・文章分析の保存契約 v1」の分割本文。
parent_note_id: program-analysis-storage-v1
source_path: 30-Data/analysis-storage-v1.md
source_sha256: 31b48be809af0922124aea608b12aec7e8f935b513ca61743fecd5d9e06bc885
source_body_lines:
- 155
- 179
split_on: '2026-10-11'
---

# AI仕上げ・文章分析の保存契約 v1：固定runの保存版表示（2026-10-04）

親索引・状態・確認版：[[30-Data/20-Analysis/analysis-storage-v1/00-Index]]。必要な本文だけを取得する。

## 固定runの保存版表示（2026-10-04）

read-only要約は保存手法の `engine.version` を「保存した計算版」、`method_version` を「手法registry版」として別々に投影する。`result.algorithms` は独立した「保存した算法一覧」で表示し、手法へ推測で結合しない。保存記録間で値が異なっても両方を残し、現在の定数や別記録で欠落を補完しない。

空・未記録は「記録なし」、bool・複合値等の未対応形式は「表示できない形式」。有限数値の0も保存された版として保持する。要約の共通16 KiB文字budget、最大12手法・20算法、版文字列256文字の上限を使う。元に値がありbudgetで省略された場合は「省略（全ファイルで確認）」とし、未記録へ変換しない。完全な保存JSONとhashは変更しない。


## 固定packageの読取整合境界（2026-10-04）

破損・外部復旧等でcatalogとmanifestの内容が変わったpackageを想定し、ZIP member名も検証する。絶対パス・親/現在ディレクトリ要素・空要素・backslash・drive/ADS colon・制御文字・Windows予約名・末尾dot/space等を拒否する。大文字小文字/Unicode正規化後の衝突と、同名ファイル/ディレクトリの衝突も停止する。安全な入れ子・日本語・単独の正規化前Unicode名は元綴りのまま保持する。名前を安全な文字列へ自動改名する処理ではない。

入力JSONは生成時と同じcanonical化（library_idを含む）からsnapshot digestを再計算し、run/manifestのsnapshot IDと照合する。個別artifactとmanifestのhashだけ整合しても、入力とsnapshot IDが異なる場合は固定run取得・preview・ZIPを409で停止する。元bytes・catalog・manifestを再生成/修復しない。ZIPには検証済みcontent集合を使い、検証後に別catalog名を再取得して混ぜない。通常の生成APIから不正名やこの不整合を作成できるとの確認ではなく、既存packageの読取検証の強化である。


## 時間系出力の残る欠測境界（2026-10-04）

`focus-group-local-7`／registry `text-analysis-store-11` では、timebin用の集合に真の0秒発話を含める。時刻あり発話が0件ならtimelineは空表、0→0の発話は終端0・開始件数1、10→10は終端10・開始件数1を保持する。従来の正duration集合を使う話者遷移・gap・overlapは変えない。旧v6の仮0行は固定snapshot/CSV内では元値のまま保持する。

感情別`seconds`とコード別`speaking_seconds`は全欠測時null、一部欠測時は既知小計とし、`timed_turn_count`/`missing_time_turn_count`を追加する。コード0件は空集合の合計0のまま。`overview.session_duration`は従来同様に除外を含む全発話の最大終了位置であり、時刻あり0件ならnull。`session_timed_turn_count`/`session_missing_time_turn_count`で、分析に含めた集合のcoverageと区別する。録音ファイルの全長を推測する値ではない。

一覧・個別の`library_public.duration`も既存analysis時刻boundsに基づく非破壊の読取projectionへ統一する。無効な時刻値で一覧全体を500にせず、全欠測null・真0・既存Python float互換の数値文字列を維持し、`timed_turn_count`/`missing_time_turn_count`を併記する。原発話・DBは書き換えない。

個別ライブラリのfull応答には、既存Python float互換の数値文字列を画面計測でも使えるよう、表示専用の`segment_timings`を添える。元発話ID・順序・件数・start/end/time_unknownとの一致、有効性の厳密なtrue、正規化値の有限性・順序・上限を確認した場合だけ利用する。ID重複・構造差・局所時刻編集・不正projectionは通常の数値guardへ戻す。原発話と保存本文へ混ぜず、DB永続化や自動保存はしない。音声seekのguardは別契約のまま。開始/終了時刻の編集は話者時間表示も同時に更新する。

数値時刻の計測では、既存Python契約で偽となる`time_unknown`のnull/false/0/空文字/空JSON配列/空JSON objectを限定的に扱う。空containerのprojection結合は同じ型かつ両方空の場合だけ値一致とし、非空化・型変更は旧投影を失効させる。局所時刻編集後は現在の数値boundsと同じmarker規則を使うため、未変更の空markerだけを理由に不明へ戻さない。一般のdeep equal・数値文字列parserは追加せず、原marker、保存本文、音声/evidenceのguardは変更しない。
