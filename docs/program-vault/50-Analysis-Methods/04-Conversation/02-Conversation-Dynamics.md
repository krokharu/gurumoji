---
note_id: method-conversation-dynamics
method_id: conversation_dynamics
method_version: text-analysis-store-2
algorithm_version: focus-group-local-1
execution_kind: builtin
title: 会話の時間構造
status: current
tags: [gurumoji/analysis, gurumoji/conversation, gurumoji/orchestrator]
---

# 会話の時間構造（`conversation_dynamics`）

## 実装契約

時刻順に、異話者の連続発話から遷移表、平均間隔、司会→参加者・参加者→参加者遷移を作る。全発話の物理タイムラインから`long_gap_seconds`（既定3秒）以上の無音候補と、異話者間で`overlap_seconds`（既定0.2秒）以上の重なり候補を抽出する。さらに発話秒数・ターン数・話者別秒数を時間bin（既定300秒）へ集計する。

## オーケストレーターの判断

- 文字起こしのタイムスタンプ精度、発話分割、音声前処理、話者分離を前提として表示する。無効時刻、0秒発話、候補の上限打切りを警告する。
- 無音・重なりは閾値を記録し、候補区間の音声再生と周辺発話へ戻す。遷移カウントと遷移の社会的意味を分ける。
- 時間bin幅は会話長により上方調整され得るため、要求値と有効値を両方保存する。

## 言えないこと

無音は同意・熟考・不参加を、重なりは遮り・対立を、話者遷移は影響関係を意味しない。発話間の正負の間隔も、転記セグメントの境界で変わる。

## 査読文献

- [Sacks, Schegloff & Jefferson (1974)](https://doi.org/10.2307/412243) は会話のターン交替の組織を定式化した。
- [Heldner & Edlund (2010)](https://doi.org/10.1016/j.wocn.2010.08.002) は複数コーパスのポーズ、間、重なりの分布と、閾値・統計処理の方法論的問題を報告した。現行の0.2秒／3秒は実装上の確認用しきい値で、普遍的な意味境界ではない。
