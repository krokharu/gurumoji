---
note_id: index-40-design-10-analysis
note_type: retrieval-index
title: 分析コア・実行設計
summary: 分析コア・実行設計の目的別入口。必要な責務を一つ選び、詳細へ進む。
status: current
updated: '2026-10-12'
tags:
- gurumoji/program
- gurumoji/retrieval
---

# 分析コア・実行設計

必要な項目だけを選び、本文は選んだノートで読む。

- [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|コア・ハンドラー・ルーティング再編案]] — 冒頭で着手範囲・作業手順・完了条件を定め、分析UI、追加分析の入力・保存・再開、LLMの手法別契約と知識固定を段階的な再編へ結ぶ。
- [[40-Design/10-Analysis/quantification-statistics-plan/00-Index|発話の数値化とjamovi型統計の自動実行計画]] — 発話の数値化とjamovi型統計の自動実行計画
- [[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index|分析マイルストーン・可視化プログラム・UI統合設計]] — 段階分析、手入力定義、47種の可視化、統計出力に、分析コア分離・LLM共通契約・Obsidian連携を統合する。
- [[40-Design/10-Analysis/analysis-execution-ux-plan/00-Index|分析実行UX統合・段階分析設計]] — 分散した分析実行ボタンを一つの入口へ統合し、自動／手動、依存段階、実行中画面、再開・再試行を一貫して扱う設計。
- [[40-Design/10-Analysis/analysis-history-viewer|保存済み分析・判断・ラベル履歴の閲覧]] — 保存済み分析・判断・ラベル履歴の閲覧
- [[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index|会話分析の拡張計画：既存分析とTransformer系推論の統合]] — 会話分析の拡張計画：既存分析とTransformer系推論の統合
- [[40-Design/10-Analysis/analysis-immediate-changes-plan|分析基盤の今やる変更の実施計画]] — 分析コアの整合、SQLiteの読み書き、会話横断分析の土台、話者・属性・グループのDB管理、コンテキストの整形、分析データの保存形式、運用上の課題、新しい分析手法、Raw（AI仕上げ前の文字起こし）と差分による管理、AI仕上げでの表記ゆれの統一を、一つの実施順にまとめる。旧「分析コア判断・状態遷移の整合計画」は系列Aとして統合済み。Q19で差分の切替・現在版の共通読取・実行別参照、Q20で辞書のDB化を補足。Q21・E5〜E8でアウトライン単位入力・細分化・時間分割と全発話の処理範囲の追跡を追加。Q22・E9〜E12は案Aの手法別入力契約を採用。各専門オーケストレータの利用/不使用/保留判断を維持し、先行所見1件の反例点検から導入する。実装順A0〜A5、自動試験T01〜T12、実モデルの比較評価と合格条件を定義。段階0〜5・保存表統計・横断検索等を実装し、全体試験は失敗0。2026-10-16の26項目表を参照。実モデルは5契約合格、108試行の人手品質判定と採用は未完了。
- [[40-Design/10-Analysis/analysis-reuse-snapshot-package-plan|確定済みstepの再利用・入力スナップショット版2・保存パッケージ版2の計画]] — 上の計画の点検で分けた3件。新しいpipelineでの確定済みstepの再利用、固定入力を保ったスナップショットの縮小、保存パッケージ版2での既存の読み手と検証の対応。本体Q19に合わせ、推論結果の参照を実行別に固定する検証を補足。3件とも実装・全体検証済み。版1互換と型付き表の検証を維持し、版2の容量/保存時間は実施計画の計測を参照。
