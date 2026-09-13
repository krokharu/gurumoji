---
note_id: analysis-semantic-audio-index
note_type: method-group
title: 意味・音声分析
status: current
tags: [gurumoji/analysis, gurumoji/semantic, gurumoji/audio]
---

# 意味・音声分析

ローカルの文埋め込みによるテーマ探索と、音声特徴に基づく感情ラベル推定。どちらも外部APIに会話本文を送らずに実行できるが、ラベルは人の解釈を置き換えない。

- [[01-Transformer-Topics|Transformerテーマ分析]] — `transformer_topics`
- [[02-Audio-Emotion|音声感情推定]] — `audio_emotion`

共通文献: [[../99-Peer-Reviewed-References|査読文献一覧]]。実装: `transformer_analysis.py`、`app.py`。
