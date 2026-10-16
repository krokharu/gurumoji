---
note_id: design-program-vault-rules
note_type: documentation-rules
title: プログラム資料のObsidian化と更新ルール
status: proposed
updated: 2026-09-13
schema_version: 1
tags:
- gurumoji/program
- gurumoji/rules
summary: プログラム資料のObsidian化と更新ルール
---

# プログラム資料のObsidian化と更新ルール

研究用Vaultは会話から得られた知識、プログラムVaultは実装と運用の知識を扱う。プログラムのコードは従来どおりGit上で管理し、ノートには役割・理由・参照先を記録する。

## 今回作成した資料

[[00-Home|入口]]、[[10-Architecture/10-System/overview|構成]]、[[20-Modules/10-Inventory/module-map/00-Index|機能とテストの対応]]、[[30-Data/10-Inventory/current-storage|保存形式]]、今回の保存・登録計画、および登録テンプレートを作成した。フォルダー全体をプログラム資料用Vaultとして開ける。

## 今後の構成

| フォルダー | 登録するノート | ひとつのノートの範囲 |
| --- | --- | --- |
| `10-Architecture` | システム全体、データの流れ、起動経路、依存関係 | 一つの仕組み・境界 |
| `20-Modules` | 文字起こし、話者管理、分析、AI、UI、エクスポート、Obsidian連携 | 一つの責務。関数単位の全自動量産はしない |
| `30-Data` | DB、結果schema、保存先、revision、移行・回復 | 一つの保存契約またはデータ群 |
| `35-API` | APIの目的、入力、出力、エラー、関連UI | 一つの機能群。大量のschemaはJSONで参照 |
| `40-Design` | 実装計画、登録規約、設計判断（ADR） | 一つの提案または判断 |
| `45-Methods` | 分析手法の定義・式・前提・限界 | 手法ID＋版 |
| `50-Tests` | 機能とテストの対応、検証手順、再現条件 | 一つの検証責務 |
| `60-Operations` | Windows／Colab、モデル設定、バックアップ、復元、トラブル対応 | 一つの運用手順 |
| `70-Changes` | 変更履歴、互換性、データ移行、廃止予定 | リリースまたは互換性変更 |
| `90-Templates` | モジュール、手法、結果、メモ、ADRのテンプレート | ノート種別 |

## 必須項目

プログラム用ノートには `note_id`, `note_type`, `title`, `status`, `tags` を付ける。実装を説明するノートには `verified`、提案には `updated` を付ける。コードに直接対応するノートは、相対ファイルパス、関数／クラス名、確認した版または作業ツリー、関連テストを本文に記載する。

`status` は `current`／`proposed`／`deprecated` を基本とする。現在の説明と将来案を同じ段落に混在させない。設計判断は `ADR-番号` の固定ID、背景、採用案、理由、影響、関連コード、置き換え先を持つ。

## 変更時の対応

| 変更 | 更新する資料 |
| --- | --- |
| DB列・正本・出力schema | `30-Data`、移行手順、保存分類、復元テスト |
| 分析式・前処理・除外・分母 | 手法定義の版、対応テスト、関連結果schema |
| API | API資料、入力例、競合・エラー処理、関連UI |
| UI導線 | 操作手順、機能ノート、ブラウザーテスト |
| 起動・依存パッケージ・設定 | 運用資料、READMEの該当箇所、起動テスト |
| AI provider・prompt・分割方法 | AIモジュール、手法版、出所記録、モック検証 |
| 廃止 | 旧ノートを `deprecated` にし、置き換え先をリンク |

コード変更と同じレビュー単位で資料を更新する。自動化は、ファイル・関数・API・リンクの存在確認、手法schemaの整合、更新対象候補の列挙を担当する。設計意図や分析の妥当性を自動生成した文章だけで確定しない。

`README.md` は導入の入口、`EMOTION_ANALYSIS.md` は既存の感情分析手順として維持し、詳細ノートから参照する。移設する場合は移設先を決め、二つの独立した手順を並行して保守しない。

## 検証・管理

- Vault内リンク、重複した `note_id`、プロパティ型、参照ファイル・主要関数の存在を検証する。
- schemaと手法定義はプログラム資料側で版管理し、研究用Vaultの `45-Methods` には採用版をコピーする。個人の変更をプログラム側へ自動で逆流させない。
- 研究用Vault内の手法ノートだけで結果の意味を読めるようにする。別Vaultへの相互リンクは任意のObsidian URIとし、必須の根拠リンクにはしない。
- `.obsidian` の個人レイアウト、履歴、コミュニティプラグイン設定は既定でGit管理しない。共有する設定を導入する場合は明示的に選ぶ。
- 実会話、音声、参加者台帳、秘密設定、個人PCの絶対パスをプログラム資料へ自動収録しない。例は架空データを使う。

将来、研究用Vaultで一覧表示を強化する場合は、ノートのプロパティを使ったObsidian標準のBasesを任意で追加できる。DB管理や生データの正本は [[40-Design/40-Storage/storage-policy|storage-policy]] の分類を維持する。[Obsidian公式：Bases](https://help.obsidian.md/bases)


## 2026-10-11 段階取得のための改装

- 領域 → 責務 → 論点・工程で分類し、入口は本文を複製しない。大きい本文は見出し単位で分割する。
- 既存のnote_idは本文または本文索引へ保持する。旧パスはpath-redirectとし、通常検索から除外する。
- 専門家の実行定義、知識7ノート、文献本文、共通知識の固定パスとbytesを維持する。過去の観測JSON・画像・manifestも変更しない。
- source_sha256/source_path/source_body_linesは分割前の出所。改装日は内容の再検証を意味しない。読めない既存本文は推測修復せず保存する。
- 00-Catalog.jsonは再生成可能な取得索引。scripts/build_program_vault_catalog.pyで更新し、本文の正本にはしない。
- scripts/restructure_program_vault.py planは別フォルダーにbefore.zip・staged・plan.jsonを作る。apply/restoreはhashで後続編集を検出して停止する。
- 取得は--scopeで領域、--note-idでIDを選び、--metadata-onlyまたは--sectionで必要量を限定する。全Vaultの本文をコンテキストへ渡さない。


### ?????????Windows?2026-10-11?

- ??HEAD: `47ecd0ae5b0ad2c6dd3b8387f9918c58791eb468` ??????????????????????????
- ??????????: 3,552????900???????????????????0?47???????????????hash????
- 17?????????????????????????????????211????????Markdown 106?????bytes???
- ??56???????????8????29?????15?Git??4????????????pypdf???4???????????????scratch/vault-test-deps??????????????????????????
- ??????????2,500???537???????78,356???7,487????????????????token???????
- ???: Obsidian??????????URL??????????????????????????2???ADR-116?????????????????
- ???: `python scripts/check_program_vault.py` ? `python scripts/build_program_vault_catalog.py --check`????????? `scratch/vault-restructure-20261011-final/`?
