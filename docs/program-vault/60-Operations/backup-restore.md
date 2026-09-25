---
note_id: ops-backup-restore
note_type: runbook
title: バックアップと復元（1組で保存する単位）
summary: 同じ会話の情報が分散する保存先を1組としてバックアップ・復元する手順。部分復元をしない理由を示す。
status: current
verified: 2026-09-25
feature: storage
tags:
  - gurumoji/program
  - gurumoji/operations
---

# バックアップと復元（1組で保存する単位）

同じ会話の情報は、SQLite、メディア、固定成果物、5つのObsidian Vault、それらの台帳に分かれて保存されている（DATA-03）。各場所は互いのIDとhashを記録しているため、**一部だけを戻すと台帳とファイルが食い違う**。バックアップも復元も、次の一覧を1組として同じ時点で扱う。正本の分類は [[40-Design/storage-policy]]、Vaultの役割は [[30-Data/four-vaults-v1]] を参照する。

確認元：`src/gurumoji/app.py` の `DATA_DIRECTORY`・`DEFAULT_OUTPUT_DIRECTORY` ほかの定数、`analysis_store.AnalysisStore.root`、`vault_registry.VaultRegistry.catalog_file`、`obsidian_layout.ObsidianLayout.registry`（2026-09-25の作業ツリー）。

## 1組として扱う場所

`<data>` は `MOJIOKOSI_DATA_DIR`（未設定なら `runtime/data`）。`<output>` は `MOJIOKOSI_OUTPUT_DIR`（未設定なら `runtime/output`）。

| 場所 | 内容 | 扱い |
| --- | --- | --- |
| `<data>/library.sqlite3` | 会話・本文・話者台帳・分析設定・保存実行の台帳・準備記録・再取り込み防止のtombstone | 必須。正本 |
| `<data>/media/` | 取り込んだ元メディアの管理コピー | 必須。アプリ上の削除で完全に消える（DATA-01） |
| `<data>/analysis_store/` | 分析の固定成果物（JSON／CSV）。hashはDBに記録 | 必須 |
| `<data>/obsidian/ResearchVault/` | 研究者が書いた研究メモ・テーマ・仕上げノートを含む | 必須。人の記述はここにしかない |
| `<data>/obsidian/InputVault/`、`VisualizationVault/`、`OrchestratorVault/` | アプリが書く台帳・図表仕様・実行記録 | 必須。人が編集した場合もあるため再生成で代用しない |
| `<data>/obsidian_layout/` | `interviews.json`（ResearchVaultの所有・削除状態・設定の初期化記録）、`vaults.json`（生成ノートのhash） | 必須。Vaultと必ず同時に扱う |
| `<data>/obsidian_workbench/` | Obsidian仕上げの作業状態 | 必須 |
| `<data>/kushinada_training/`、`<data>/custom_vocabulary.json` | 修正履歴（学習用）、単語登録 | 必須 |
| `<data>/thumbnails/` | 一覧のサムネイル | 任意。再生成される |
| `<output>` | 文字起こしの出力ファイル。DBの `output_dir` は絶対パスで記録される | 必須。同じパスに戻す |
| `config/tokens.json` | APIキー | 別に保管する。共有するバックアップへ入れない |
| `docs/program-vault` | Software Vault | Gitで管理する。このバックアップの対象外 |

`<data>/media/` などの `.delete-staging-*`、`<output>` の `.edit-staging-*`・`.edit-preparing-*`・`.edit-cleanup-*` は削除・編集の途中状態で、起動時の復旧が使う。見つけても消さずにそのまま含める。

## バックアップ

1. アプリのコンソールウィンドウを閉じ、プロセスが終了したことを確認する。`<data>/.gurumoji.instance.lock` はOSのファイルロックで、終了後もファイルは残るため、その有無では判断しない。Obsidianも閉じる。
2. `<data>` フォルダーと `<output>` フォルダーを、それぞれ丸ごと同じ日時のバックアップ先へコピーする。Windowsの例：

   ```bat
   robocopy runtime\data D:\Backup\gurumoji-2026-09-25\data /E /COPY:DAT /R:1 /W:1
   robocopy runtime\output D:\Backup\gurumoji-2026-09-25\output /E /COPY:DAT /R:1 /W:1
   ```

3. DBが読めることを確認する：

   ```bat
   .venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.connect(r'D:\Backup\gurumoji-2026-09-25\data\library.sqlite3').execute('PRAGMA integrity_check').fetchone()[0])"
   ```

   `ok` と表示されればよい。

## 復元

1. アプリとObsidianを終了する。
2. 現在の `<data>` と `<output>` を削除せず、名前を変えて退避する（例：`data.before-restore`）。復元がうまくいかなかったときに戻せる。
3. バックアップの `data` と `output` を、元と同じパスへコピーする。`<output>` の場所を変えると、DBに記録された出力ファイルの絶対パスと食い違う。場所を変える場合は `MOJIOKOSI_OUTPUT_DIR` を元のパスに合わせる。
4. アプリを起動する。起動時に中断した編集・削除の復旧が走る。「接続と処理装置」の「Obsidian監視」が稼働中であることを確認する（停止していれば理由が表示される。OBS-09）。
5. Obsidianで各Vaultを開き直す。

## 部分復元をしない理由

- ResearchVaultだけを戻すと、`interviews.json` と `vaults.json` のhashがファイルと合わない。アプリは人の編集とみなして生成ノートの更新を止める（`conflict`）。
- DBだけを戻すと、`analysis_store` にない成果物IDをDBが参照し、成果物の取得や再保存が失敗する。
- 削除した会話を戻したい場合も、削除前のバックアップを1組として復元する。アプリ上の削除は元メディアを完全に消すため、メディアだけを取り出して戻す操作はない（DATA-01、未対応）。
