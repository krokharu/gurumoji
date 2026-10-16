---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-33
title: 専門家知識制作・実行報告書：2026-09-28 15:55 UTC A100 GiNZA preprocessing batch
summary: 2026-09-28 15:55 UTC A100 GiNZA preprocessing batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 391
- 396
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 15:55 UTC A100 GiNZA preprocessing batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 15:55 UTC A100 GiNZA preprocessing batch

- Claim数の少ない日本語テキスト前処理領域を選び、MITライセンスのGiNZA v5.2.0公式READMEからspaCy、SudachiPy、Hugging Face Transformersの役割を区別する短い言い換え根拠を作成した。Colabへの抜粋SHA-256は`feda596de8e7d2cf785330034ba64ce6ad854feb739b0f9700944d1e9e21467b`、元README SHA-256は`71652a6e50e94ee71020d16b38dd7e67a2c679149a2622a83fe9ef8615ec2dc7`。対象はバージョン付き公式READMEのLicense節で、モデル性能の主張は生成対象から外した。
- Qwen3-32B-AWQ generation-1をNVIDIA A100-SXM4-80GB High-RAMで実行し、Transformers 4.51.3、Tokenizers 0.21.4、Hugging Face Hub 0.30.2、AutoAWQ 0.2.9をカーネル再起動後に確認した。GiNZA v5.2.0ではSudachiPyが形態素解析・品詞タグ付けを担い、`ja_ginza_electra`の事前学習モデルのframeworkにHugging Face Transformersを用いるというClaimを根拠照合し、未承認候補として受理した。Commit SHA-256 `1e707a1ccee0b6b597fab866db44743118476a0d36dcca453861ab9e498a1459`、結果ZIP SHA-256 `d127e638be38c1f2cd19c426f8b3b4677839b19ec6a522323f55fb1ed939adb5`。
- 推論は835 input tokens、99 output tokens、21.463秒。Colab残高は81.37から81.15 CUへ0.22 CU減少し、A100停止後のactive sessionは0。Job・抜粋・Source・結果のhash対応は`output/knowledge-colab-batch/b20260928t155500.json`に記録した。Knowledge Packは作成・承認・公開していない。
- 読み取り専用の最終JobStore監査はSQLite integrity `ok`、105 accepted Commit、104 Claim、105 Source、17/17 expert domain、artifact/hash/evidenceエラー0、Knowledge Pack 0を確認した。`exp-thematic-analysis`は9 Claim、`exp-japanese-text-preprocessing`は5 Claim。P6の全領域を対象とする体系的な重複整理・反復評価は未完了。
