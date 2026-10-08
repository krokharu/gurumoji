# Obsidian Vaultの構成

Gurumojiは、役割の異なる独立したObsidian Vaultを使います。人が読んで書くのは主に **ResearchVault** と **Software Vault** です。残りの3つはアプリが台帳として書き出します。Vault同士は内部リンクでつながず、会話ID・実行IDなどで対応付けます。

| Vault | 場所（リポジトリルートから） | 誰が書くか | 用途・最初に開くノート |
| --- | --- | --- | --- |
| ResearchVault | `runtime/data/obsidian/ResearchVault` | 研究者とアプリ | 分析・研究内容。全文、アウトライン、仕上げ操作、分析まとめ、研究メモ。Vault内の `00-ホーム.md`、ブックマークの `Gurumoji` |
| Software | `docs/program-vault` | 開発者（Git管理） | プログラムの解説・設計。[プログラム資料の入口](program-vault/00-Home.md) |
| Input | `runtime/data/obsidian/InputVault` | アプリ | 文字起こしの取り込み台帳と分析入力のスナップショット（本文は含まない） |
| Visualization | `runtime/data/obsidian/VisualizationVault` | アプリ | 分析結果の図表仕様（`run.bat` の横の「可視化用Obsidianを開く」から開く） |
| Orchestrator | `runtime/data/obsidian/OrchestratorVault` | アプリ | 分析手法カードと実行記録 |

「4 Vault」はSoftware・Input・Visualization・Orchestratorの役割分担を指し、ResearchVaultはそれとは別に併用します（物理的には計5つ）。保存の契約は [4 Vaultの保存契約](program-vault/30-Data/four-vaults-v1.md) を参照してください。`runtime/data` は `MOJIOKOSI_DATA_DIR` で変更できます。

## 開き方

Obsidianの保管庫管理で「保管庫としてフォルダーを開く」を選び、上記のフォルダーをそれぞれ開きます。研究用は `ResearchVault` 自体を指定し、その親の `obsidian` フォルダーは選びません。[Obsidian公式：既存フォルダーから開く](https://help.obsidian.md/manage-vaults)

各Vaultは独立した `.obsidian` フォルダーを持ちます。アプリが新しく作ったVaultにだけ、初回に推奨の表示設定（グラフ、ブックマーク、ワークスペースなど）を書きます。既に `.obsidian` があるVaultの設定は変更しません。Obsidianアプリの保管庫一覧への登録は、初めて各フォルダーを開いたときに行われます。

### Obsidianの版と図表・添付の扱い

`obsidian://open` などURI操作の確認ダイアログは、Obsidian 1.13.6で撤去されています。常に確認が出ることを前提にせず、対象Vaultとノートを確かめて開いてください。[公式1.13.6更新内容](https://obsidian.md/changelog/2026-08-10-desktop-v1.13.6/)

1.12以降には、ノートの削除に伴う添付削除を「Always」「Ask every time」「Never」から選ぶ設定があります。アプリが図表や固定成果物を記録するVaultでは「Ask every time」を推奨します。削除候補に出た添付は、他の固定run・ノートからも参照されていないか確認してください。アプリは既存Vaultの設定を自動変更しません。[公式1.12更新内容](https://obsidian.md/changelog/2026-02-27-desktop-v1.12.4/)

CLIとBases表示は閲覧・参照検査の補助です。CLIには対応installer（1.12.7以降）、Obsidian内の有効化と登録が必要で、初回コマンドは未起動のアプリを起動することがあります。使う際は `vault=<対象名>` を先頭に指定し、対象のないコマンドで研究者の現在のVaultへ操作を送らないでください。Python側のID・hash・必須参照検査と、Obsidianでの表示確認は別に記録します。[公式CLIヘルプ](https://obsidian.md/help/cli)

2026-10-08のこのPCでは、既設Obsidian実行ファイルのProductVersionは `1.13.7.0`、`Obsidian.com` は存在し、PATH上の `obsidian` コマンドは未登録でした。実行中アプリの版・CLI有効化・Bases表示は未確認です。バージョンや設定を変更せず、CLI未確認を分析runtimeの停止条件にはしません。1.14のkanban表示をこの確認結果へ含めません。

## 分析用に用意したもの

全文・アウトライン・仕上げ操作・分析まとめをインタビュー単位にまとめました。ブックマークから研究全体のグラフと1件に絞ったグラフを開けます。[グラフと一覧の操作手順](OBSIDIAN_GRAPH.md)を参照してください。

文字起こしの仕上げは、Whisper原文を保存した後にObsidianの専用操作ノートから実行できます。録音1件の会話全文を1ノートで編集し、全体アウトラインの作成・調整、AI仕上げ、結果のアプリへの反映をチェック欄で進めます。[操作手順](OBSIDIAN_FINISHING.md)を参照してください。追加のObsidianプラグインは不要です。

- 研究、会話、原文、話者、分析結果、コード、研究メモ、概念、添付の保存先
- AI仕上げとTransformerテーマ分析を含む18手法の登録ガイドと共通規約
- 研究計画、会話の入口、分析結果、研究メモの記入用テンプレート
- Obsidian・DB・CSV／JSONの保存分類と、研究メモ・解釈・コード案の差分取り込み方針

「分析・可視化」の冒頭にある「分析結果をObsidianに保存」で、対象会話・分析結果・根拠を登録できます。KWICは「この検索をObsidianに保存」で全一致を保存します。AI仕上げの工程結果とAI見解は処理時に自動で記録します。保存履歴からObsidian・JSON・CSVへ進めます。

全件データは `runtime/data/analysis_store`、実行・同期状態はSQLite、読むための見解・引用は研究Vaultに保存します。[実装済みの保存仕様と使い方](program-vault/30-Data/analysis-storage-v1.md)を参照してください。研究メモ・解釈・コード案の差分取り込みは後続の実装対象です。

分析用のVaultはローカルの `runtime/data/` 配下にあるためGit管理対象外です。画面の「バックアップを作成」または `python scripts/backup_data.py create` は、DB・固定成果物・各Vault・台帳を同じ時点で保存します（メディアは任意）。このデータバックアップにはゴミ箱と `runtime/output` は含まれません。削除済み会話も復元できる完全退避では、アプリを停止して `<data>` と `<output>` を一組でコピーしてください。手順は[バックアップと復元の手順](program-vault/60-Operations/backup-restore.md)にあります。プログラム用Vaultの資料はGit管理でき、個人の `.obsidian` 設定は除外されます。

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
