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

分析用Vaultはローカルの `runtime/data/` 配下にあるためGit管理対象外です。復元用には、画面の「バックアップを作成」または `python scripts/backup_data.py create` で、DB・`analysis_store`・`obsidian_workbench`・全Vault・台帳を同じ時点でバックアップしてください（メディアは任意）。手順は `docs/PROJECT_LAYOUT.md` にあります。プログラム用Vaultの資料はGit管理でき、個人の `.obsidian` 設定は除外されます。

## プログラム資料Vaultの更新

プログラム資料Vault（`docs/program-vault`）の正本はGitです。GitHubに届いた資料の更新は、次のスクリプトで確認して取り込みます。AIエージェントに「Obsidianを更新」と頼んだ場合も、同じ手順を実行します。

```powershell
python scripts/update_program_vault.py check   # 取り込まれるノートを一覧（何も変更しない）
python scripts/update_program_vault.py apply   # 取り込む
```

- `docs/program-vault` をそのままObsidianで開いている場合、`apply` は現在のブランチを早送り（fast-forward）で更新します。Obsidianは変更を自動で読み込みます。同じノートをローカルで編集中の場合や、ローカルだけのコミットがある場合は、何も変更せずに中止して対象を表示します。
- 別のフォルダーに作ったVaultへ取り込む場合は、`--target "<フォルダー>"` を付けるか、環境変数 `GURUMOJI_PROGRAM_VAULT_TARGET` を設定します。前回の取り込み以降にローカルで編集したノートは上書きせず、新しい版を `<フォルダー>/.gurumoji-sync/incoming/` に保存します。上流で削除されたノートは `.gurumoji-sync/removed/` へ移します（削除はしません）。
- どちらの方法でも、個人設定の `.obsidian` フォルダーと、分析用の実行時Vault（`runtime/data/obsidian/...`）には触れません。
- 取り込み元は、現在のブランチの追跡先（未設定なら `origin/main`）です。`--remote` と `--branch` で変更できます。
