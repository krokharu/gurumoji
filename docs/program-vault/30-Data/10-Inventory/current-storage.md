---
note_id: program-current-storage
note_type: data-model
title: 現在の保存形式と拡張点
status: current
verified: 2026-09-13
updated: 2026-10-13
tags:
- gurumoji/program
- gurumoji/storage
summary: 現在の保存形式と拡張点
---

# 現在の保存形式と拡張点

確認元は `services/library_schema.py` の `initialize_library`、`app.py` の `group_analysis_for_row`、`services/output_import.py` の出力・再取込処理、および `research_analysis.py` です。個々の研究データの内容はこの資料に含めません。

## SQLite：`data/library.sqlite3`

| テーブル | 保存しているもの |
| --- | --- |
| `library_items` | 発話JSON、話者名、会話・話者プロフィール、アウトライン、感情推定、成果物パス、元データrevision |
| 同テーブルの分析列 | `analysis_config_json`, `analysis_annotations_json`, `analysis_revision`, `analysis_updated_at` |
| 同テーブルのAI列 | 最新成功結果の `analysis_insights_json`、AI使用量 |
| `analysis_insight_requests` | AI見解のリクエストID、対象revision、fingerprint、モデル、進捗、中止・失敗・完了、使用量 |
| `analysis_runs`, `analysis_artifacts` | 固定結果の実行台帳、成果物のhash・行数・保存先 |
| `obsidian_notes` | アプリが書いたノートのID・hash・同期状態 |
| `analysis_pending_packages` | ファイル保存の中断・失敗から復旧するための一時記録。成功後に削除 |
| `speaker_registry` | 話者の共通プロフィール、属性、同意状態等 |
| `attribute_definitions`, `conversation_attributes` | 対象別の属性キー・型・尺度・許容値・定義版と、会話の自由属性の正本。会話属性の未定義キー・型不一致は保存APIで拒否 |
| `speaker_attributes` | 台帳の `attributes_json` からトリガー展開する問合せ用の写し。既存キー・CSVの未知列は `discovered` 定義として自動登録 |
| `data_groups`, `data_group_members` | 手動／条件グループと複数所属。手動所属の変更も版を進め、条件所属は現在の表・属性・タグから評価 |
| `tags`, `conversation_tags` | 会話のタグと複数付与。NFKC・前後空白除去・casefoldで名称の重複を防ぐ |
| `analysis_run_members`, `analysis_run_groups` | 会話横断の固定所属とグループ参照。属性・タグ・所属の変更は会話1件の入力hashを変えず、該当する保存結果を更新必要にする |
| `application_metadata` | 話者台帳revision、移行状態等 |
| `training_events` | 編集に由来する学習イベント |
| `output_import_provenance` | 出力ファイル取込の出所 |
| `output_import_tombstones` | 削除済み出力の再取込防止情報 |

`MOJIOKOSI_DATA_DIR` で保存先を変更できます。既存IDは会話ID・発話ID・話者台帳IDとして維持します。発話IDは英数字・アンダースコア・ハイフンを許容するため、ObsidianブロックIDへは別途変換が必要です。

## ファイル

会話横断比較の `parameters.target_snapshot` に、グループID／版、評価済み所属／hash、属性定義／版、会話属性、タグ、参照した話者台帳の値を固定する。元の所属や属性が変わってもpackageと分母は書き換えない。条件グループは対象外の会話の変化でも所属が変わり得るため、そのグループを使うrunを保守的に更新必要にする。

会話の属性・タグ付与・手動所属は派生コピーではなく正本なので、削除時に既存ゴミ箱manifestへ保存して復元する。参照先タグ／グループが削除済みなら復元を停止する。旧 `library_groups` は保存形式とAPIを維持し、画面では「フォルダー」と区別する。実データ移行・Vault反映・I3bの変更履歴はこの段階に含めない。

| 場所・形式 | 現在の用途 |
| --- | --- |
| `data/media` | 原音声・動画 |
| `data/thumbnails` | 再生成可能なサムネイル |
| `data/kushinada_training` | 学習用音声クリップ・派生ファイル |
| `output/*_話者分離.json` | 機械可読な文字起こし結果。既存データの復旧・取込にも利用 |
| `output/*_話者分離.txt`, `.srt` | 閲覧用文字起こし・字幕 |
| `output/*_アウトライン.txt`, `*_感情分析.json`, `*_感情分析.csv` | 任意処理の結果 |
| `output` のSVG・MP4 | ワードクラウド・字幕焼き込み動画 |
| 分析出力APIのJSON／CSV／Excel | 保存済み入力から必要時に生成してダウンロード |
| `tokens.json` | 秘密情報を含むローカル設定。Vaultへ出力しない |

通常の分析GETには形態素・係り受け等のプレビュー上限があります。固定保存APIは全件を再取得し、`data/analysis_store` のCSV／JSONと `ResearchVault` のノートへ保存します。AI仕上げの校正前後・議題の根拠も同じ保存層を使います。

## 今回補った点と後続工程

1. 全件出力を使い、入力スナップショット・実行条件・結果を実行IDで固定保存する。
2. DB上の最新版と、引用された過去版を区別する。
3. 見解・研究メモ・手法・根拠をMarkdownで関連付ける。
4. 組み込み手法の共通契約を設ける。外部分析結果の取り込みは後続工程とする。
5. ファイルとDBの同期途中で失敗しても、既存の編集保存と復旧動作を維持する。

現在の詳細：[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]。全体設計：[[40-Design/40-Storage/storage-policy|storage-policy]]、[[40-Design/40-Storage/sync-contract|sync-contract]]。
