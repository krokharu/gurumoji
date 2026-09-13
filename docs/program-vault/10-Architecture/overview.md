---
note_id: program-architecture
note_type: architecture
title: 処理の流れと構成
status: current
verified: 2026-09-13
tags:
  - gurumoji/program
---

# 処理の流れと構成

Gurumojiは、音声・動画の文字起こし、話者分離、編集、会話分析をFlaskのWeb画面から扱うプログラムです。WindowsとGoogle Colabの起動経路があります。

## 入力から保存まで

1. `templates/index.html` と `static/app.js` が、ファイル・処理条件・話者設定を受け付ける。
2. `app.py` がジョブを管理し、FFmpegによる任意の音声前処理、Whisper／WhisperX、pyannoteを実行する。
3. 任意で音声感情分析、AI校正、話者特定、アウトライン生成を行う。AI通信は `ai_http_worker.py` に分離される。
4. 元メディアを `data/media` に保管し、処理結果をSQLiteと `output` のJSON／TXT等へ保存する。
5. 保存後の本文・話者・時刻の修正は、revisionを確認した編集保存とファイル回復処理を通す。
6. 「分析・可視化」は保存済みデータを入力とし、自動集計と手動コード・メモを組み合わせる。

## 分析の構成

| 担当 | 現在の責務 | 関連資料 |
| --- | --- | --- |
| `app.py` | 会話集計、分析条件・注釈の保存、API、任意AI見解のジョブ管理 | [[20-Modules/module-map]] |
| `research_analysis.py` | 形態素・係り受け・語彙・共起・統計、分析キャッシュ、Excel | [[40-Design/method-rules]] |
| `analysis_insights.py` | ローカル見解、KWIC、特徴語比較、根拠検証、AI見解の分割・統合 | [[40-Design/method-rules]] |
| `static/analysis-content.js` | 見解、検索、引用、音声確認、AI生成状態の表示 | [[20-Modules/module-map]] |
| `ai_finishing.py` | 分割片の完全性確認、校正、発話根拠付き議題、校正前後差分 | [[30-Data/analysis-storage-v1]] |
| `analysis_method_registry.py`, `analysis_store.py` | 手法ごとの保存契約、入力版・結果の固定保存、ノート生成・再試行 | [[30-Data/analysis-storage-v1]] |
| `static/analysis-storage.js` | 保存・履歴・再試行とVaultから音声への移動 | [[30-Data/analysis-storage-v1]] |

自動集計の数値、AIが生成した下書き、研究者が保存したコード・解釈は出所が異なります。Obsidian連携でも出所を各ノートに記録します。

## 今回の拡張位置

保存済みデータと全件分析の後段に、結果の固定保存とVaultへの書き出しを追加しました。AI仕上げにも発話IDを維持する分割・根拠検証・変更記録を組み込みました。研究メモ等の差分取り込みは後続の実装工程です。

読み進める順序：[[30-Data/current-storage]] → [[40-Design/storage-policy]] → [[40-Design/obsidian-plan]]。

2026-09-14追記：モジュールの依存関係、操作から保存までのデータフロー、保存先、外部サービス、設定の所在をまとめた全体図は [[10-Architecture/system-map]] にある。

確認元：リポジトリの `README.md`、`app.py`、`research_analysis.py`、`analysis_insights.py`、`ai_http_worker.py`。ファイル別の検証箇所は [[20-Modules/module-map]] にまとめています。
