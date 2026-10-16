---
note_id: design-storage-policy
note_type: storage-policy
title: 保存先と正本の分類
status: current
updated: 2026-10-16
schema_version: 1
tags:
- gurumoji/storage
summary: 現行の保存先・正本・バックアップ対象、実装した系列D〜Fと後続の制約を分類する。型付きpackage版2、Rawと差分、派生DB、利用者承認後の試験DB切替は実施計画を参照。
---

# 保存先と正本の分類

2026-10-12更新：組み込み手法の固定保存・型付き表JSONと共有CSV・AI仕上げの変更記録・Vault生成は実装済みです。現行API・テーブル・登録契約は [[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]] を参照してください。系列D〜Fの後続変更、差分取り込み・外部手法等の計画は実装済みの範囲と区別します。

「正本」は、変更時に優先し、復元時の基準にする保存物を指す。同じ内容が複数の形式に現れる場合も、どれが正本でどれが表示・交換用かを記録する。

## 分類表

| データ | 正本 | Obsidianに置くもの | CSV／JSON等に残すもの | 更新のルール |
| --- | --- | --- | --- | --- |
| 現在の文字起こし本文・時刻・話者割当 | SQLite `library_items` | 版付きの対象発話と根拠ブロック、会話の入口 | 既存文字起こしJSON／TXT／SRT、固定した入力JSON | 本文の修正は既存編集保存を通す |
| 話者台帳・会話プロフィール・データグループ | SQLite `speaker_registry`・`library_items.speaker_profiles_json`・`library_groups` | 設定で選んだ表示項目、研究上必要な属性 | 既存話者CSV、入力時点の実効プロフィールJSON | IDで対応。氏名や表示順で照合しない |
| 分析条件・対象／除外・コードブック・測定定義 | SQLite `library_items.analysis_config_json`・`analysis_annotations_json`・`analysis_definitions` | 条件の説明、確定コードの定義と適用例 | 固定結果の条件JSON、コードブックJSON／CSV、固定定義を含むExecutionBinding | 条件変更で新しい入力識別値を作る |
| アプリで確定したコード付与・重要引用・分析メモ | SQLite `library_items.analysis_annotations_json` | 確定内容の表示、引用リンク | 注釈JSON、コード済み発話CSV | 既存保存APIとrevision確認を使う |
| Obsidianで新規作成した自由メモ・概念・仮説 | 人が編集するMarkdown | 本文、関連ノート、原文リンク | 選択時の移送用JSON。DBにはID・hash・索引 | Markdownを勝手に再生成しない |
| Obsidianから提出するコード案・解釈案 | 元のMarkdown。採用後のアプリ値はSQLite | 提出原文と根拠 | 取り込みイベントJSON | 差分確認後の取り込み。提出原文は保存 |
| 確定保存した分析結果 | 実行ID付きのJSON・CSV | 要約、主要表、図、条件、結果ファイルへの参照 | 全件JSON、表形式CSV、manifest | 固定結果は不変。DBは台帳・最新ポインターを管理 |
| AI見解 | 現行互換の最新値はSQLite。保存履歴は実行ID付きJSON | 「AI見解・下書き」、出所、対象版、根拠 | 結果JSON、入力・prompt版・使用量の記録 | 成功時だけ最新ポインター更新。失敗で旧成功を消さない |
| 形態素・係り受け・語彙・共起・統計の詳細行 | 固定保存した結果JSON・型付き表JSON | 説明・一部の表・結果リンク | 型付き表と同じ値から生成する共有CSV。分割JSONL等は後続計画 | 大量行をMarkdownやDBの重複JSONへ押し込まない |
| KWIC | 保存した検索条件JSON＋一致結果CSV | 検索目的、ヒット数、選択した引用 | 全一致行、位置、対象版 | 通常検索は一時状態。「検索を保存」で固定 |
| 実行中ジョブ・使用量・エラー・同期状態 | SQLite | 完了・失敗等の概要を索引に表示 | 必要な監査用エクスポート | 進捗の更新ごとにノートを書き換えない |
| Vault台帳・書き込みhash・変更履歴 | `<data>/obsidian_layout` のJSON／JSONL | 対応ノートのID・revision・索引 | `vaults.json`、`interviews.json`、`note_changes.jsonl` | 衝突・欠落判定に必要な状態。Vaultと一緒にバックアップする |
| AI仕上げの作業状態・候補結果 | `<data>/obsidian_workbench/<item-key>/` の状態JSON・結果JSON | ResearchVaultの操作ノート・仕上げ結果 | `state.json`、`result-<run_id>.json`等 | 既存Workbench経路を使い、作業状態もバックアップする |
| 議論用人格・パネル・議事録・人格の記憶 | `<data>/obsidian/PersonaVault` のMarkdown | `10-Personas`・`20-Panels`・`30-Deliberations`・`40-Memory` | 必要な手動エクスポート | ADR-114。手作業で作成済み、アプリは読み書き・VaultRegistry登録をしない。記憶・議事録は追記、`obsidian`一式のバックアップに含む |
| 再計算可能な形態素・係り受けの解析行（F1） | 正本ではない。`<data>/analysis-derived.sqlite3` の `segment_parses`・`morphemes`・`dependencies` | 通常は収録しない | 旧形式の固定JSON・CSVは維持。パッケージ版2の参照は後続 | 本文hash・解析器／辞書／モデルの版・設定hashごとに追記。読込時に入力と結果hashを照合し、話者・役割・除外は固定入力から付ける。バックアップ対象外、欠落時は再計算。ベクトルは未導入 |
| 検索キャッシュ・描画用キャッシュ | 再生成可能な一時領域 | 通常は収録しない | 必要なものだけキャッシュ | 正本のバックアップ対象から分離 |
| 原音声・動画 | `data/media` の元ファイル | アプリで該当時刻を確認するリンク | 元形式。配布時は選択して複製 | 自動で全音声をVaultへ複製しない |
| サムネイル・ワードクラウド・分析図 | 再生成物。引用した図は実行成果物 | PNG／SVG等の閲覧用添付 | 元データと生成条件、選択した図 | 図と数値の実行IDを揃える |
| 学習イベント・音声クリップ | 既存DBイベントと保管音声 | 件数・作成方法・場所への参照 | 既存manifest CSV／JSON等 | 研究ノートと学習用レコードを混同しない |
| プログラムの仕様・設計判断・手法規約 | Git管理するプログラムVault | 構成・機能・API・手法・テスト・運用資料 | schema例、架空のサンプル | コードの変更と資料更新を対応させる |
| APIキー・トークン・ローカル秘密設定 | 現行 `tokens.json` 等 | 設定項目の説明のみ | 値を含まないサンプル | 実値を両Vaultへ複製しない |

## 現行の物理配置と後続計画

```text
<data-root>/
  library.sqlite3
  analysis-derived.sqlite3  F1の再計算可能な形態素・係り受け行（バックアップ対象外）
  media/...
  analysis_store/
    inputs/<snapshot-id>/input.json
    runs/<analysis-id>/
      manifest.json
      parameters.json
      result.json
      tables/*.json        型付き表の正本
      tables/*.csv         同じ値から作る共有用表
  obsidian/
    ResearchVault/         研究者のMarkdownと閲覧用添付
    InputVault/            入力台帳・固定スナップショットの説明
    VisualizationVault/    図表仕様と成果物の来歴
    OrchestratorVault/     手法カード・実行記録
    PersonaVault/          手作業で作成する議論用ノート（アプリ未登録）
  obsidian_layout/         Vault台帳・書き込みhash・変更履歴
  obsidian_workbench/      AI仕上げの作業状態・候補結果

<repo>/
  runtime/output/          既存の文字起こし・字幕・互換成果物（既定）
  runtime/backups/         明示的な整合バックアップ（既定、データ外）
  docs/program-vault/      プログラム資料のVault
```

`<data-root>`はDBの親ディレクトリ（既定`runtime/data`、`MOJIOKOSI_DATA_DIR`で変更）。出力・バックアップ先はそれぞれ既存の`MOJIOKOSI_OUTPUT_DIR`・`MOJIOKOSI_BACKUP_DIR`で解決する。外部結果の`incoming/`は後続実装の対象。F1の派生SQLiteはDBの親ディレクトリに配置する。新規のVault移行バックアップは`MOJIOKOSI_BACKUP_DIR`（既定`runtime/backups`）の`backup-<id>/`へ作り、旧配置の既存バックアップとpending記録は移動しない。

| 系列 | 現行の保存 | 後続計画との境界 |
| --- | --- | --- |
| D：話者・属性・グループ | `speaker_registry`、`library_groups`、`library_items`の正本と追加の投影・属性・タグ表 | 現行カラムを維持。研究者の確定値と差分履歴をバックアップし、検索用FTSとベクトル索引は現在版・除外条件で検証する |
| E：エージェント用コンテキスト | 固定入力・計画・binding、step証跡、区間所有権、短い参照IDと配送manifest | コンテキスト縮小・区間処理・確定step再利用は実装済み。契約成功と実モデルの研究品質・採用は別ゲート |
| F：分析結果と派生データ | `analysis_runs`・成果物台帳、固定入力・型付き表、版2の固定参照 | package版2とF1〜F3は実装済み。同内容はQ23の条件で既存runを再利用。異なる推論結果・版は別runを保持し、欠落を別実行で代用しない。派生DBは再計算用・バックアップ対象外 |

`analysis_store` は既存の `output/*_話者分離.json` の自動取込先から分離し、固定入力を誤って新しい会話として再取込しない。既存ファイル名やダウンロード形式は維持する。

CSV／JSONの大量データは `analysis_store` に一度保存し、通常のVault同期では複製しない。ノートには `artifact_id`、相対的な保管場所の説明、アプリ経由の取得リンクを付ける。Obsidian自体がCSV／JSONを表として表示することは前提にしない。

## 自動保存と容量

- ライブラリの保存では、会話の入口と更新状態を更新キューへ入れる。
- 明示した分析保存、再集計完了、AI生成成功、外部結果登録で固定結果を作る。分析GETやページ閲覧では履歴を増やさない。
- 同じ入力スナップショット・手法版・条件・エンジンで同じ成果物を再利用できる。AIを明示的に再生成した場合は、同じ入力でも別の実行として保存する。
- 保存済みの成功結果は自動削除しない。キャッシュと放棄されたstagingには別の保持期限を設ける。
- 引用・メモ・別分析から参照される実行は保持する。容量整理では参照関係と削除予定を表示する。
- 「Vault登録解除」「アプリ上の会話削除」「保存履歴・音声の完全削除」を別操作とし、全コピーの所在をmanifestで追跡する。

## 端末間の移送・復元

研究用Vaultだけをコピーした場合は、保存済みノートと添付図が読める。元音声・外部のCSV／JSON・実行中のアプリへの接続は含まれない。すべてを持ち出す場合は、選択した結果を `PortableData/` へ収め、参照を相対リンクにした「可搬パッケージ」を作る。CSV／JSONは元形式のまま同梱する。

現行の`services/data_backup.py`はSQLiteのbackup APIで`library.sqlite3`の整合コピーを作り、`analysis_store`・`obsidian`（PersonaVaultも含む）・`obsidian_layout`・`obsidian_workbench`・`custom_vocabulary.json`を必須対象として保存する。メディア・学習用音声は選択式。台帳・hash・作業状態は表示用キャッシュではなく、履歴保持・競合検知・再開に必要な保存物である。派生データ用SQLiteはこの必須対象に追加しない。Vaultをクラウド等で運ぶ方法は別設定とし、稼働中DBをVault同期の対象にしない。

研究用Vaultの表示名は既定で参加者コード／仮名を優先する。これは本文中の個人情報を匿名化する処理とは別である。配布パッケージは、対象会話・属性・原文・音声の範囲を指定して作成する。プログラムVaultに実際の参加者情報や原文を載せない。

関連：[[40-Design/40-Storage/sync-contract|sync-contract]]、[[40-Design/50-Governance/method-rules/00-Index|method-rules]]。
