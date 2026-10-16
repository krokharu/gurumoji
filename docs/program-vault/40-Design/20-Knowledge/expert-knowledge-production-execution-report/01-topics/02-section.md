---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-02
title: 専門家知識制作・実行報告書：AI と計算資源の担当
summary: AI と計算資源の担当。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 24
- 53
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：AI と計算資源の担当

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

## AI と計算資源の担当

| AI / 資源 | 実施内容 | 使用量の記録 |
| --- | --- | --- |
| Codex Luna | 実装と作業進行を担当。契約、worker、評価・読込基盤、候補生成の改善を実施。 | Codex のトークン量はこの実行環境から取得できないため数値化していない。 |
| Codex Sol | P1 契約の監修、および候補と根拠の独立レビュー。 | トークン量は取得できないため数値化していない。 |
| ローカル Qwen3-8B / RTX 5070 | JSON 分類スモークと候補作成。 | usage を返した9呼出しの小計: 合計 20,994 tokens、計測時間 470.157秒。prompt / completion の総内訳は手元の集計に残っていない。usage のない失敗・timeout は含まない。 |
| Colab A100 | 80B架空入力probeに加え、固定Qwen3-32B-AWQでFreeTxt、会話時間構造、記述統計、cross-corpus SER、オンラインFG、SCAT、相関APIのJobを直近8バッチで22回実行。15件を根拠一致として受理し、7件を保留。 | 直近3バッチはA100-SXM4-80GB High-RAM、最新5バッチはA100-SXM4-40GB Standard。usage記録のある結果は計16,889 input + 2,588 output tokens、推論時間462.322秒。1回は重複防止器が生成文を止め、usage記録なし。Transformers 4.51.3 / Tokenizers 0.21.4 / Hub 0.30.2を確認。11:00 batch開始からの残高差は4.66 CU、最新残高は83.31 CU。 |

Qwen の呼出しは、完全な usage 記録が残る9件の合計である。今回の追加probeは5つの合成障害を一要求で分類し、正答基準との一致は4/5、計測時間は13.1秒だった。送信前にDNSが失敗したケースを`manual_review`と判定した保守的な誤分類があり、例外分類だけで再試行を決める運用には使えない。失敗したschema応答やtimeoutの計算量は分からないため、総利用量とは扱わない。Codex Luna / Sol についてもトークン量を推定していない。

## Colab と定期実行の状態

2026-09-27 05:13 UTC の Google Drive 再確認では、共有フォルダーに接続テストNotebook、P0 roundtrip bundle、P0 A100 Notebookの3件がある。P0 Notebookは同じDrive file ID上で65,145 bytes・SHA-256 `e8894b2f0ca0a7ec58dff4c9a3a879b7c2aa86165b3cf43614b46d412c35e0bf`。raw readbackはローカルの全byteと一致した。Notebookは60分ごとにRuntime/GPU・ジョブ候補を確認し、A100が割り当てられていれば軽量な256x256 FP16健全性確認を実行する。80分ごとに成果物のfile ID・size・SHA-256を照合し、同じ監視JSONへ履歴を保存する。Driveの更新時刻はNotebook資材の更新時刻でありColab実行の証拠ではない。P0 bundleは27,358 bytes。再接続後も結果ZIPと監視JSONは見つからず、Run all後の実行は未確認。この環境からDrive一覧は読めるが、Colabランタイムを直接起動・操作するAPIはない。

実ジョブがある間はA100を候補生成・バッチ評価などに優先使用し、最大55分単位でcheckpointを保存する。キューが空の間も60分ごとにジョブ候補とRuntime/GPU状態を点検し、A100が割り当てられていれば256x256 FP16行列積の軽量な健全性確認を1回実行して同じ監視JSONをDrive上で更新する。この確認は文献処理ではない。80分ごとにbundle・結果ZIPの存在、file ID、size、SHA-256を再照合する。不一致時は受理を止め、最後に確認したgenerationから再開する。P0 Notebookはジョブ候補の検出までで、本番文献処理用のmodel adapterは未実装。再実行時は同一job/generationの監視履歴を引き継ぐ。

Colab FAQはPro+で計算単位残高が十分な場合の連続コード実行を最大24時間と案内する一方、利用枠・idle timeout・GPU割当は変動し、早期終了もあり得る。したがって監視セルは最大24時間で終了し、接続維持は保証しない。常時稼働が必要なら専用VM/Colab Enterprise等を検討する。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)

**Colabでの開始操作は利用者が必要。** 共有Notebookを開いて両コードセルを順に実行し、Driveアクセスを承認すると、P0結果ZIPを直接保存してから定期監視を開始する。現時点では再接続後のA100実行と結果保存は未確認。

### P0 合成A100往復確認

`output/knowledge-p0-colab-roundtrip/` に世代1の合成Jobとローカル単一writer stateを作り、結果を受理する `scripts/accept_p0_colab_roundtrip.py` を追加した。Driveには次の2点をアップロードし、raw downloadのbyte sizeとSHA-256がローカル原本と一致することを確認した。

- [A100確認・定期監視Notebook](https://drive.google.com/file/d/1sN8Qwgt9uZ6liRB_tIc-aWEBydY1x16S/view?usp=drivesdk): 65,145 bytes、SHA-256 `e8894b2f0ca0a7ec58dff4c9a3a879b7c2aa86165b3cf43614b46d412c35e0bf`
- [合成roundtrip bundle](https://drive.google.com/file/d/1WkhBlBxrIKZVMEwQk_Gcm7vTVS0upHWw/view?usp=drivesdk): 27,358 bytes、SHA-256 `ad4041cee5600623ac5e9ca5a6855b3b9653266266e6de429d8626773c7c0415`

bundleは合成Source、1件のJob/request、承認Source registry、worker sourceだけで構成する。Colab Notebookは512×512 CUDA演算でA100を確認し、決定論的なsynthetic generatorで未承認結果ZIPを返す。LLM推論も実文献処理も行わないP0 transport smokeである。ローカルの隔離preflight結果を複製stateへ受け入れ、2 Artifact、generation 1の採用、同一ZIP再送の冪等性を確認した。本番側stateは`accepted_generation=0`を保っている。Notebookの実行・DriveへのNotebook保存・実A100出力の取得・`accept_p0_colab_roundtrip.py`による本番stateへの一度だけの受理は待機中。Job期限は2026-10-04 02:08 UTC。
