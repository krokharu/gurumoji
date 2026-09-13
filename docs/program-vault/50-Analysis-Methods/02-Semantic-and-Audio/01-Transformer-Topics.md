---
note_id: method-transformer-topics
method_id: transformer_topics
method_version: text-analysis-store-2
algorithm_version: transformer-topics-4
execution_kind: builtin
title: Transformerテーマ分析
status: current
tags: [gurumoji/analysis, gurumoji/semantic, gurumoji/orchestrator]
---

# Transformerテーマ分析（`transformer_topics`）

## 実装契約

意味のある発話だけを選び、短い断片には同話者・3秒以内の隣接発話を文脈として加える。`intfloat/multilingual-e5-small`で384次元ベクトルを作り、K-means（`random_state=42`、`n_init=10`）でクラスタリングする。指定テーマ数がなければ、最小クラスタサイズを満たす候補からcosine silhouette最大の数を選ぶ。出力はテーマ、発話割当、話者別分布、時間推移、中心から遠い発話、相づちとその時系列上の応答先である。

## オーケストレーターの判断

- 入力発話の除外数、文脈補完数、モデル名・revision・次元、候補テーマ数、選択理由、seed、silhouetteを保存する。
- `silhouette`はクラスタの内的一貫性の指標であり、テーマの真実性ではない。低値、少数クラスタ、候補間の僅差では人の見出し確認を必須にする。
- テーマ名は内容語からの仮ラベル。各テーマの代表発話と外れ値を読み、テーマの併合・分割・除外を人が承認する。
- 相づちは時刻と短文辞書からの候補である。応答先・賛同・合意として確定しない。

## 言えないこと

埋め込み類似度とクラスタは、話者の合意、不一致、重要性、因果、感情を推論しない。話者偏りや転記断片によるクラスタを実質的テーマと誤認しない。

## 査読文献

- [Reimers & Gurevych (2019)](https://aclanthology.org/D19-1410/) は文の意味類似性に使うSiamese BERT文埋め込みを評価した。
- [Lloyd (1982)](https://doi.org/10.1109/TIT.1982.1056489) は最小二乗量子化の反復手続き（Lloyd型k-means）の査読済みの基礎論文である。本実装は`KMeans`を用いるため、実行時のライブラリ版・アルゴリズム設定も保存する。
- [Rousseeuw (1987)](https://doi.org/10.1016/0377-0427(87)90125-7) はsilhouetteによるクラスタ解釈・検証を提案した。

実装依存メモ: E5の直接資料はプレプリントであり、このノートでは査読済みの上記3文献と混同しない。
