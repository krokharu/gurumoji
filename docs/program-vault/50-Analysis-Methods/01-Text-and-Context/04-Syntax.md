---
note_id: method-syntax
method_id: syntax
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: 係り受け
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# 係り受け（`syntax`）

## 実装契約

GiNZAのUniversal Dependencies出力から、発話ID、文ID、語、lemma、UPOS、依存関係ラベル、係り先トークン／表層形、固有表現を`dependencies`に保存する。GiNZAの構文解析器が使えない場合は`unavailable`であり、Sudachiや正規表現から係り受けを捏造しない。

## オーケストレーターの判断

- `unavailable`を空結果や成功として扱わない。必要なら依存パーサを導入して同じ入力revisionから再実行する。
- 根拠には発話IDだけでなく文ID・トークンID・解析器版を残す。文法関係を集計する場合は、解析誤りを目視監査できる原文と解析行を併置する。
- 日本語UDの語単位と、ユーザーが読む文節・発話の単位を混同しない。

## 言えないこと

依存関係は意味役割、話者の意図、因果、談話関係を直接決めない。音声転記の句読点と断片発話は解析精度を下げる。

## 査読文献

- [Omura & Asahara (2018)](https://aclanthology.org/W18-6014/) は日本語コーパスをUDスキーマへ変換する方法と規模を報告する。
- [Nivre et al. (2020)](https://aclanthology.org/2020.lrec-1.497/) はUDの統語層が述語・項・修飾の関係を対象にすることを示す。これはGiNZAの出力形式の基礎であって、本実装の口語精度の保証ではない。
