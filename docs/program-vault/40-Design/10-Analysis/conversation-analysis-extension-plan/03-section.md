---
note_type: reference-section
status: planned
feature: analysis
updated: 2026-09-16
tags:
- gurumoji/analysis
- gurumoji/design
- gurumoji/conversation
note_id: design-conversation-analysis-extension-section-03
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合：既存分析の棚卸しと再利用方針
summary: 既存分析の棚卸しと再利用方針。出典ノート「会話分析の拡張計画：既存分析とTransformer系推論の統合」の分割本文。
parent_note_id: design-conversation-analysis-extension
source_path: 40-Design/conversation-analysis-extension-plan.md
source_sha256: 53dc673b9392c2b03a1b6fd2a103f326b15690c0702376bab2e403dfda7f9bfb
source_body_lines:
- 60
- 72
split_on: '2026-10-11'
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合：既存分析の棚卸しと再利用方針

親索引・状態・確認版：[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index]]。必要な本文だけを取得する。

## 既存分析の棚卸しと再利用方針

| 実際の機能 | 入力・分析単位→処理 | 出力・保存・UI | 再利用できる部分 | 不足点 |
| --- | --- | --- | --- | --- |
| 文字起こし・話者・編集・準備 | `library_items`の発話。`group_analysis_for_row`（`app.py:5511-`）が`id`、話者、役割、時刻、本文、除外、確認状態を構成 | SQLite、入力版、`prepared_turns`、編集／音声確認UI。更新時は関連runをstale | session／speaker／segment ID、時刻、元本文と編集本文、準備状態 | 機能単位の分割、対象ID、予測と人手確定の汎用記録はない |
| 形態素・語彙・共起・KWIC・特徴語 | 1発話を文書として、形態素、TF/DF、Jaccard共起、話者差、KWICを集計 | `research_analysis`、`analysis_insights`、Excel／CSV／JSON、分析UI | M01のラベル絞り込み、M02のコード×話者表、根拠発話への復帰 | 語の共起は発話間の応答・賛否グラフではない |
| 手動コード・相互作用 | 複数コード、重要引用、単発タグ、手動関係リンク。分析単位はturnのみ | `analysis_annotations_json`、`coded_segments`、`interaction_links`、case matrix、文脈展開UI | ラベル定義、確認・修正、関係の正解候補、M02/M05/M09 | 自動予測のスコア・候補順位・モデル版を保存する契約はない。既存JSONを未設計の予測用に転用しない |
| Transformerテーマ・意味検索 | 文脈付き有意味発話→E5 small→K-means／手動テーマ割当、意味検索 | テーマ、割当、話者分布、時間、例外、相づち、CSV、固定run、テーマUI | E5ロード・CPU/CUDA設定・キャッシュ・発話根拠・時間／話者集計 | BERTopic、対象別スタンス、一般応答関係、分類評価はない |
| 音声感情 | 音声セグメント→AISTモデル。テキストとは別のラベル | 発話別感情、分布、UI、CSV。任意依存 | M03の発話ID結合、元音声へ確認 | 感情を賛否・意図・内心へ置換できない |
| 会話構造・参加量 | 発話数、秒数、遷移、無音・重なり候補、時間区間 | automatic分析、グラフ、CSV | M04/M06の話者・時間分母、候補窓 | 遷移・発話量は応答・影響力・人格を意味しない |
| AI見解／アウトライン／会議議事録 | 根拠発話IDを検証するAI見解、議題、規則ベース会議タスク／決定候補 | 固定run、ResearchVault、根拠表示 | M07の比較対象、発話ID付き構造化入力 | 談話関係を要約に入力する機構、少数意見・帰属の測定はない |
| 固定保存・Vault・出力 | `archive_group_analysis`（`app.py:13952-13982`）→`AnalysisStore.save` | `analysis_runs`、成果物CSV/JSON、ResearchVault、method status、CSV／Excel／JSON | 新手法の入力fingerprint、parameters、モデルrevision、stale、根拠と履歴 | 事前に`analysis_method_registry`、CSV schema、検証、UI対応を追加する必要がある |
