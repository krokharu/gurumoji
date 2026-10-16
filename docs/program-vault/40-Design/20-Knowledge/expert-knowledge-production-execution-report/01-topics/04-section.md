---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-04
title: 専門家知識制作・実行報告書：2026-09-27 follow-up verification
summary: 2026-09-27 follow-up verification。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 77
- 92
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-27 follow-up verification

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-27 follow-up verification

- Google DriveのNotebookをraw downloadで全byte再取得した。63,515 bytesとSHA-256 `8c60210dae43d0cd812ff64a31338f5c74fe186edff0df7ac6610ecdb06b9c0c`がローカルNotebookと一致した。
- 再取得した共有Driveフォルダーには、A100 Notebook、P0 bundle、接続確認Notebookだけがあり、結果ZIPと監視JSONはない。ユーザーのColab再接続後も、P0 runtime実行とDriveへの成果物保存は未確認である。
- knowledge-builder対象8ファイルのfocused suiteは76件成功。追加したreaderテストは引用符付き・colon-prefixed POSIX、absolute/drive-relative/root-relative Windows、UNC、tilde/home path、`file:` URIを確認し、HTTPS URLは保持する。
- この時点ではcandidate_pipeline単体suiteが未整備だった。下段の追加確認でfocused testsを加え、最終suiteは88件成功した。

### 2026-09-27 Colabスケジュール更新

- Sol監修で、Python文字列へのID直挿し、既存Drive resultのhash取り違え、LM Studioリクエストのproxy通過、`file:` locator漏れを指摘された。各項目をliteral化・永続hash pin・ProxyHandler無効化・file URI全形拒否で修正し、再監修で全指摘が閉じていることを確認した。

- Colab公式FAQの現行説明では、利用枠・idle timeout・GPU割当・VM最大寿命は変動し、実行継続を保証しない。Pro+でも十分なcompute unitsがある場合に連続実行は最大24時間まで。接続維持だけを目的にGPUを空回しする構成を避け、実処理があるときだけA100を使うスケジュールへ変更した。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
- 共有Drive上の同じNotebook file IDを更新した。60分ごとのRuntime/GPU・ジョブ待ち行列確認と、A100割当時の軽量な256x256 FP16健全性確認、80分ごとのDrive bundle/result ID・size・SHA-256照合、同一監視JSONへの履歴保存・再開を行う。健全性確認は重いダミー処理ではない。Drive共有フォルダーを再確認したが、実行結果ZIPと監視JSONはまだなく、Colab上のRun allは未確認。
- 最終更新Notebookは63,012 bytes、SHA-256 `0fb5fc36801633cb97e9434b6a793ed890657da7143accaf4ab7bb2004304684`。Driveからraw bytesを取り直してsize/hash一致を確認。Drive更新時刻は2026-09-27 04:06:06 UTC、フォルダー再確認時刻は04:07 UTC。結果ZIPと監視JSONはまだなく、Colab上のRun allは未確認。P0でA100上に流せるのは現在の合成transport smokeのみ。本番モデルadapterがまだないため、承認済み文献からの知識生成ジョブはまだA100へ定期投入できない。
- 関連する10モジュールのfocused suiteは88件成功。candidate_pipelineはloopback/proxy無効化・local path拒否・source rights/provenanceを含む7件、Colab schedulerは文字列literal・Drive result hash pinを含む3件。Solの読み取り専用監修では重大/高リスク指摘なし。Notebook code cell 2件の構文確認、対象Python modulesの`py_compile`、metadata hash確認、`git diff --check`も成功。
