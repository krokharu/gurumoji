---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-07
title: 専門家知識制作・実行報告書：2026-09-27 Springer Nature rights audit
summary: 2026-09-27 Springer Nature rights audit。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 124
- 144
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-27 Springer Nature rights audit

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-27 Springer Nature rights audit

- `LIT-byrne-2022-reflexive-ta`のSpringer Nature公式記事ページはOpen AccessとCC BY 4.0を明記し、適切な帰属・ライセンスリンク・変更表示を条件に利用・共有・改変・配布を許可している。[Springer article](https://link.springer.com/article/10.1007/s11135-021-01182-y)、[CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en)。
- 文献ノートにライセンス、LLM処理許可、route allowlist、審査者・日時・根拠を記録した。abstract-scopeは維持し、本文内容の正確性や査読状態を承認した扱いにはしていない。第三者素材の別クレジットは個別確認が必要。
- `source-audit --all-experts`は17専門家・108参照・未解決0・status/correction欠落0を再確認。レビュー済みは6 unique papers・13 expert-reference rows、権利未確認または審査pendingは96から95へ減少。

### 2026-09-27 05:13 UTC Colab reconnect recheck

- ユーザーの再接続後に共有Driveを再確認したが、追加ファイルはなく、結果ZIPと監視JSONも見つからなかった。DriveのNotebook本体は65,145 bytes・SHA-256 `e8894b2f0ca0a7ec58dff4c9a3a879b7c2aa86165b3cf43614b46d412c35e0bf`で、raw readbackはローカル版と一致した。
- ランタイムの再接続だけではNotebookセルが実行された証跡にならない。Run allの実行・Drive認可・A100割当は未確認。Google Drive接続にはColabランタイムを直接操作するAPIがないため、Notebookを開いてRun allする操作が必要。
- 定期Notebookの仕様は60分ごとのRuntime/GPU確認と、A100割当時の軽量なGPU確認、80分ごとのDrive成果物照合。Colabが終了した場合は処理も止まるため、接続維持を保証しない。実文献のA100ジョブはmodel adapter未実装のためまだ投入されない。

### 2026-09-27 06:06 UTC Colab定期処理・P3境界更新

- ユーザー要望に合わせ、Drive上の既存Notebook ID `1sN8Qwgt9uZ6liRB_tIc-aWEBydY1x16S` を更新した。実行中は60分ごとにRuntime/GPU/queueを確認し、A100割当時は軽量256x256 FP16 health probeを行う。80分ごとにDrive artifactのID・size・SHA-256を検査し、同じmonitor JSONへ履歴を保存する。queueが空でも毎時の運用確認を続ける。
- 現行Notebookにproduction model adapterがないため、今はA100で専門家知識を生成していない。health probeはGPUの稼働状態を記録する軽量診断で、論文・ダミー知識の生成はしない。権利gateを通過した実jobをA100へ優先投入するadapterの実装は未完了。監視セルは最大24時間で自動終了する。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)では実行上限・idle timeout・GPU availabilityは変動し、Pro+の連続実行も十分なcompute unitsがある場合に最大24時間とされる。
- Drive Notebookの更新版は65,711 bytes、SHA-256 `5ef9b866381f1859035e148c81f0e2e6a6904cc1680c8c9b1319d935a1bb1ecb`。raw downloadでsizeとSHA-256をreadback照合した。共有folderにはNotebook、27,358-byte input bundle、接続確認Notebookの3件だけがあり、P0 result ZIPとmonitor JSONはまだない。Run all実行・Drive認可・A100割当は未確認。
- P3ではGale論文のページ4だけからローカルQwen3-8Bがpending候補を1件生成した。今回の成功呼出しは1,787 prompt + 86 completion = 1,873 tokens、1.213秒。ローカル集計は今回分を含め成功10呼出し、22,867 tokens、471.370秒。出力先guardを追加する前に失敗した1呼出しは実行量不明のため集計外。
- P3候補は未承認batch/review bundleとして保留中で、配布Packへは登録していない。Solのコードのみの監修で、Source文を配列・候補間に分割する経路と、推論中の出力先差替えを指摘された。候補全体の本文一致検査・上限付きshingle索引・書込直前の出力先再検証を追加し、最終レビューで高リスク問題なしを確認した。Solは文献・候補内容を読まず、テストも実行していない。こちらもsyntax compileと`git diff --check`のみ実施した。
- AI別作業量: 主担当Codex（Luna運用）はコード・Notebook・計画/報告の実装を担当。Sol（gpt-6-sol）は4回のコード限定レビューを実施したが、レビューtoken量はツールから取得できない。ローカルQwen3-8Bの今回の成功生成は1,873 tokens / 1.213秒。Colab Run allは未実行確認のため、この作業でのA100 GPU時間は未計測。
