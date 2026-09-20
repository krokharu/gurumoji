---
note_id: method-transformer-topics
note_type: analysis-method
method_id: transformer_topics
method_version: text-analysis-store-2
algorithm_version: transformer-topics-8
execution_kind: builtin
title: Transformerテーマ分析
status: current
tags: [gurumoji/analysis, gurumoji/semantic, gurumoji/orchestrator]
---

# Transformerテーマ分析（`transformer_topics`）

## 実装契約

意味のある発話だけを選び、短い断片には同話者・3秒以内の隣接発話を文脈として加える。`intfloat/multilingual-e5-small`で384次元ベクトルを作る。テーマの決め方は3つで、実行ごとに`parameters.mode`へ記録する。

| mode | 決め方 | 主な記録 |
| --- | --- | --- |
| `auto` | K-means（`random_state=42`、`n_init=10`、話者量の重み`1/√件数`）で、最小クラスタサイズを満たす候補からcosine silhouette最大の数を選ぶ | 候補ごとのsilhouette、選択したテーマ数 |
| `candidate` | 研究者が候補一覧から選んだテーマ数でクラスタリングする。候補一覧は毎回すべて評価して残す | 指定したテーマ数、候補ごとのsilhouette |
| `manual` | 研究者が定義したテーマ（見出し・手がかり語・シード発話）のベクトルへ、コサイン類似度が最大のテーマに割り当てる。しきい値未満は未割当にする | テーマ定義、しきい値、未割当件数、上位2テーマの差が小さい件数 |

テーマ定義は分析設定（`config.transformer_topics`）に研究者が保存し、実行時に固定保存の`parameters`へ写す。`candidate`と`manual`では、入力の指紋が一致する保存済み意味ベクトル（int8）を再利用し、埋め込みを計算し直さない。出力はテーマ、発話割当、話者別分布、時間推移、中心から遠い発話、相づちとその時系列上の応答先である。

## オーケストレーターの判断

- 入力発話の除外数、文脈補完数、モデル名・revision・次元、候補テーマ数、選択理由、seed、silhouette、テーマの決め方、ベクトル再利用の有無を保存する。
- `silhouette`はクラスタの内的一貫性の指標であり、テーマの真実性ではない。低値、少数クラスタ、候補間の僅差では人の見出し確認を必須にする。`manual`のsilhouetteは割り当て後の記述であり、研究者のテーマの妥当性ではない。
- `auto`と`candidate`のテーマ名は内容語からの仮ラベル。各テーマの代表発話と外れ値を読み、テーマの併合・分割・除外を人が承認する。
- `manual`の割り当ては最近傍の候補である。しきい値と上位2テーマの差は実装上の目安で、テーマの妥当性を検証した値ではない。未割当と境界例を人が読み、手がかり語・シード発話・しきい値を見直す。
- 相づちは時刻と短文辞書からの候補である。応答先・賛同・合意として確定しない。

## 言えないこと

埋め込み類似度とクラスタは、話者の合意、不一致、重要性、因果、感情を推論しない。話者偏りや転記断片によるクラスタを実質的テーマと誤認しない。

## 査読文献

- [Reimers & Gurevych (2019)](https://aclanthology.org/D19-1410/) は文の意味類似性に使うSiamese BERT文埋め込みを評価した。
- [Lloyd (1982)](https://doi.org/10.1109/TIT.1982.1056489) は最小二乗量子化の反復手続き（Lloyd型k-means）の査読済みの基礎論文である。本実装は`KMeans`を用いるため、実行時のライブラリ版・アルゴリズム設定も保存する。
- [Rousseeuw (1987)](https://doi.org/10.1016/0377-0427(87)90125-7) はsilhouetteによるクラスタ解釈・検証を提案した。

実装依存メモ: E5の直接資料はプレプリントであり、このノートでは査読済みの上記3文献と混同しない。

## 担当専門家

[[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert|埋め込みによるテーマ探索の専門家]]。名前が似ている [[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert|テーマ分析の専門家]] とは別の手法として扱う。
