---
note_id: method-morphology
method_id: morphology
method_version: text-analysis-store-2
algorithm_version: research-ja-3
execution_kind: builtin
title: 形態素・品詞
status: current
tags: [gurumoji/analysis, gurumoji/text, gurumoji/orchestrator]
---

# 形態素・品詞（`morphology`）

## 実装契約

GiNZAが利用可能ならSudachi由来の表層形、lemma、正規形、読み、UPOS、詳細品詞、活用、文字位置を`morphemes`に保存する。利用できない場合はSudachiPy単独、さらに不可能なら正規表現の簡易分割へ切り替える。出力には`is_content`、`is_stop`、発話ID、文ID、トークンIDがある。

## オーケストレーターの判断

- エンジン名・版・分割モード`C`、辞書、ストップ語を固定して出力と一緒に保存する。
- `fallback`のとき、品詞や原形の精度を前提にした後段（内容語頻度、特徴語、共起）へ警告を伝播する。
- 固有名詞、口語、フィラー、誤変換、専門語はサンプル監査し、必要ならユーザーのストップ語／辞書を明示的に追加する。

## 言えないこと

形態素境界、品詞、原形は解析器の推定であり、特に日本語の口語音声文字起こしに対する正解ラベルではない。

## 査読文献

- [Kudo, Yamamoto & Matsumoto (2004)](https://aclanthology.org/W04-3230/) は、日本語で語境界が自明でないことを前提に形態素解析を評価したEMNLP論文。
- [Nivre et al. (2020)](https://aclanthology.org/2020.lrec-1.497/) は、lemma・UPOS・形態特徴を含むUDの形態層を説明する。
