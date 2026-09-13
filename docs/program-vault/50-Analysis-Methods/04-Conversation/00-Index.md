---
note_id: analysis-conversation-index
note_type: method-group
title: 会話構造・参加バランス
status: current
tags: [gurumoji/analysis, gurumoji/conversation]
---

# 会話構造・参加バランス

時間情報と話者ラベルから、参加の量、交替、無音候補、重なり候補、時間帯別集計を作る。いずれも時刻情報の品質と話者分離に依存し、相互作用の意味は人が確認する。

- [[01-Participation|発話量・参加バランス]] — `participation`
- [[02-Conversation-Dynamics|会話の時間構造]] — `conversation_dynamics`

共通文献: [[../99-Peer-Reviewed-References|査読文献一覧]]。実装: `app.py` の `group_analysis_for_row`。
