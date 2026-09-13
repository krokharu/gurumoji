# 2つのObsidian Vault

分析内容用とプログラム資料用を、それぞれ独立したフォルダーに作成しました。

| 用途 | リポジトリルートからの場所 | 最初に開くノート |
| --- | --- | --- |
| 分析・研究内容 | `runtime/data/obsidian/ResearchVault` | Vault内の `00-ホーム.md`、ブックマークの `Gurumoji` |
| プログラムの解説・設計 | `docs/program-vault` | [プログラム資料の入口](program-vault/00-Home.md) |

## 開き方

Obsidianの保管庫管理で「保管庫としてフォルダーを開く」を選び、上記のフォルダーをそれぞれ開きます。研究用は `ResearchVault` 自体を指定し、その親の `obsidian` フォルダーは選びません。[Obsidian公式：既存フォルダーから開く](https://help.obsidian.md/manage-vaults)

両Vaultには独立した `.obsidian` フォルダーを用意しています。Obsidianアプリの保管庫一覧への登録は、初めて各フォルダーを開いたときに行われます。

## 分析用に用意したもの

全文・アウトライン・仕上げ操作・分析まとめをインタビュー単位にまとめました。ブックマークから研究全体のグラフと1件に絞ったグラフを開けます。[グラフと一覧の操作手順](OBSIDIAN_GRAPH.md)を参照してください。

文字起こしの仕上げは、Whisper原文を保存した後にObsidianの専用操作ノートから実行できます。録音1件の会話全文を1ノートで編集し、全体アウトラインの作成・調整、AI仕上げ、結果のアプリへの反映をチェック欄で進めます。[操作手順](OBSIDIAN_FINISHING.md)を参照してください。追加のObsidianプラグインは不要です。

- 研究、会話、原文、話者、分析結果、コード、研究メモ、概念、添付の保存先
- AI仕上げとTransformerテーマ分析を含む18手法の登録ガイドと共通規約
- 研究計画、会話の入口、分析結果、研究メモの記入用テンプレート
- Obsidian・DB・CSV／JSONの保存分類と、研究メモ・解釈・コード案の差分取り込み方針

「分析・可視化」の冒頭にある「分析結果をObsidianに保存」で、対象会話・分析結果・根拠を登録できます。KWICは「この検索をObsidianに保存」で全一致を保存します。AI仕上げの工程結果とAI見解は処理時に自動で記録します。保存履歴からObsidian・JSON・CSVへ進めます。

全件データは `runtime/data/analysis_store`、実行・同期状態はSQLite、読むための見解・引用は研究Vaultに保存します。[実装済みの保存仕様と使い方](program-vault/30-Data/analysis-storage-v1.md)を参照してください。研究メモ・解釈・コード案の差分取り込みは後続の実装対象です。

分析用Vaultはローカルの `runtime/data/` 配下にあるためGit管理対象外です。復元用にはアプリを停止してDB・`analysis_store`・`obsidian_workbench`・研究Vault・必要なメディアを一緒にバックアップしてください。プログラム用Vaultの資料はGit管理でき、個人の `.obsidian` 設定は除外されます。
