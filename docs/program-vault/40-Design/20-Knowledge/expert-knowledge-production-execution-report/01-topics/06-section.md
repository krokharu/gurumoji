---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-06
title: 専門家知識制作・実行報告書：2026-09-27 FQS rights audit
summary: 2026-09-27 FQS rights audit。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 105
- 123
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-27 FQS rights audit

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-27 FQS rights audit

- `LIT-mayring-2000-qca`のForum Qualitative Social Research公式記事ページにCC BY 4.0表示があることを確認し、ライセンスURL・LLM permission・route allowlist・審査根拠をノートへ記録した。[FQS article](https://www.qualitative-research.net/index.php/fqs/article/view/1089)、[CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en)。
- `correction_status: not_checked`はそのまま維持。今回の権利確認は内容の妥当性や訂正履歴の確認を含まず、それらはClaim承認前に別途確認する。
- 最新監査は5 unique sources・12 expert-reference rowsがレビュー済み、96/108 rowsが未確認または審査pending。

### 2026-09-27 04:15 UTC Colab Drive status

- 共有フォルダーにはA100用P0 Notebook、合成roundtrip bundle、接続確認Notebookの3件があり、実行結果ZIPと監視JSONはまだなかった。
- 04:15時点でNotebookのRun allとA100実行は確認できていない。Colabランタイムをこの接続から直接起動・操作するAPIはない。

### 2026-09-27 04:54 UTC A100 hourly check update

- Drive上の既存Notebookは60分ごとの状態確認と80分ごとのDrive監査を持っていたが、実際のコードではA100演算は起動時の一度だけだった。60分ごとの確認でA100が割り当たっていれば、256x256 FP16行列積を1回実行し、成否を監視JSONに記録するよう修正した。重いダミー生成はしない。
- 同じDrive file ID `1sN8Qwgt9uZ6liRB_tIc-aWEBydY1x16S`を更新し、65,145 bytes・SHA-256 `e8894b2f0ca0a7ec58dff4c9a3a879b7c2aa86165b3cf43614b46d412c35e0bf`をraw readbackで照合した。
- フォルダー再確認ではNotebook、27,358-byte入力bundle、接続確認Notebookの3件のみで、結果ZIP・監視JSONはまだない。Colabの再接続は聞いているが、Run all後の出力は未確認。
- 本番モデルadapterが未実装のため、現段階でA100が行う実作業はP0合成transport smokeと毎時の軽量GPU健全性確認まで。実ジョブbundleは要手動確認として記録する。
- Colabは利用枠・idle timeout・VM寿命・GPU割当が変動するため、このループは接続維持を保証しない。1回の実行は最大24時間で停止する。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
