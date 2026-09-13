---
note_id: analysis-text-context-index
note_type: method-group
title: テキスト・文脈分析
status: current
tags: [gurumoji/analysis, gurumoji/text]
---

# テキスト・文脈分析

発話を基本単位に、GiNZA／Sudachi由来の形態情報、頻度、同一発話内共起、文脈検索を出力する。GiNZAが使えない場合、形態素・語彙・共起・話者別特徴語は簡易解析へ切り替わるが、係り受けは`unavailable`であり推測しない。

- [[01-Local-Insights|ローカル見解]] — `local_insights`
- [[02-Speaker-Characteristics|話者別特徴語]] — `speaker_characteristics`
- [[03-Morphology|形態素・品詞]] — `morphology`
- [[04-Syntax|係り受け]] — `syntax`
- [[05-Lexical-Frequency|語彙頻度]] — `lexical_frequency`
- [[06-Cooccurrence|共起]] — `cooccurrence`
- [[07-KWIC|文脈検索]] — `kwic`

共通文献: [[../99-Peer-Reviewed-References|査読文献一覧]]。実装: `research_analysis.py`、`analysis_insights.py`。
