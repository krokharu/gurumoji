---
note_id: method-audio-emotion
note_type: analysis-method
method_id: audio_emotion
method_version: text-analysis-store-2
algorithm_version: per-model-repository-and-fold
execution_kind: builtin
title: 音声感情推定
status: current
tags: [gurumoji/analysis, gurumoji/audio, gurumoji/orchestrator]
---

# 音声感情推定（`audio_emotion`）

## 実装契約

話者分離後の各発話音声を切り出し、AIST公開モデルの`くしなだ`（HuBERT）または`いざなみ`（wav2vec 2.0）、あるいは両方で推定する。JTES由来の`ang`、`hap`、`sad`、`neu`主ラベルを発話へ保存し、話者・モデル・ラベル別に件数と発話秒数を集計する。確信度は取得できる場合のみ保持し、無い場合は`null`である。

## オーケストレーターの判断

- モデル名、Hugging Faceリポジトリ、fold、主ラベルのみ／確信度の有無、対象発話数、カバー率を出力する。
- 音声区間の切り出し・話者分離・ノイズが上流誤差源である。短い区間、重なり、音質不良、未推定を可視化し、欠測をゼロ件へ混ぜない。
- 両モデルを使った場合は一致／不一致を独立に表示し、片方のラベルで上書きしない。人の聴取確認へ戻るリンクを保持する。

## 言えないこと

ラベルは音声モデルの分類であり、本人が経験した感情、感情の強さ、話者の意図、発話内容の真偽を確定しない。学習データと異なる場面・話者・マイクでは性能が変わり得る。

## 査読文献

- [Baevski et al. (2020)](https://proceedings.neurips.cc/paper/2020/hash/92d1e1eb1cd6f9fba3227870bb6d7f07-Abstract.html) はwav2vec 2.0の自己教師あり音声表現を示す。
- [Hsu et al. (2021)](https://doi.org/10.1109/TASLP.2021.3122291) はHuBERTの隠れ音声単位を用いる自己教師あり表現を示す。
- [Kosaka et al. (2023)](https://doi.org/10.1587/transinf.2023HCP0010) はJTESを用いた日本語感情音声認識を報告する。

モデル配布とセットアップは[[../../../EMOTION_ANALYSIS|音声感情分析の設定]]を参照。

## 担当専門家

[[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert|音声感情推定の専門家]]。上のKosaka et al.の年と位置づけは2026-09-16の調査で確認できていない（[[50-Analysis-Methods/20-Literature/LIT-kosaka-2024-emotional-speech-recognition]]）。
