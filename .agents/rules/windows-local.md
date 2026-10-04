# Gurumoji: Windows ローカル実行プロファイル

このプロファイルは利用者の Windows チェックアウトでコマンドを実行するときだけ適用する。共通規約は [AGENTS.md](../../AGENTS.md)。Linux クラウドでは [dot-cloud.md](dot-cloud.md) を使う。

- ローカルの実パス、ブランチ、未コミット編集、仮想環境をその PC で確認する。クラウドの `/workspace/...` や sibling `runtime` をローカルへそのまま設定しない。
- 起動・初回セットアップは既存の [README.md](../../README.md)、`run.bat`、`setup_gui.bat` と、対象の PowerShell スクリプトに従う。Windows／Colab 向け説明は引き続き有効であり、クラウド対応を理由に削除しない。
- `run.bat` には Git／ライブラリの更新処理がある。クラウドと比較する際は、起動前後の版と更新の有無を確認する。CPU 専用のクラウド制約を Windows の GPU 環境へ適用しない。
- GPU／CUDA、LM Studio、Ollama、Obsidian 本体、接続トークンの利用可否はローカルで確認する。これらがローカルにあってもクラウドで利用できるとは限らない。
- 保存先は現行コードと `MOJIOKOSI_DATA_DIR`、`MOJIOKOSI_OUTPUT_DIR`、`MOJIOKOSI_BACKUP_DIR` から解決する。未設定時の既定は [PROJECT_LAYOUT.md](../../docs/PROJECT_LAYOUT.md) のアプリ配下 `runtime`。個人の Vault パスをソースへ埋め込まない。
- 設定ファイルと環境変数の読み込み方は実際のランチャーで確認する。`.env`、`config/tokens.json` 等の秘密値は Git に追加せず、クラウドとの受け渡しにも含めない。
- Software Vault 更新、Vault の所有権・競合処理、データベースの既存カラム保護、比例した検証は `AGENTS.md` と既存の対象別契約に従う。ローカル／クラウドのやり取りは私有 Git の版と差分を確認し、ローカル編集を一方的に置換しない。

既存の Windows 向けテスト例（リポジトリ直下、PowerShell）:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
```

これはローカル PC に変更を加える許可や、クラウド側からローカルのルール・設定・Vault を書き換える許可を与える文書ではない。ローカルにのみ存在する追加ルールは、内容が確認されるまで未反映として扱う。
