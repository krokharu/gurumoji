# フォルダー構成

最上位は日常的に使う入口だけにしています。

```text
mojiokosi/
├─ README.md                 使い方
├─ run.bat                   アプリ起動
├─ setup_gui.bat             初回セットアップ
├─ config/                   設定と依存関係
├─ src/gurumoji/             アプリ本体・画面素材
├─ scripts/                  補助・保守スクリプト
├─ runtime/                  実行データ（Git管理外）
│  ├─ data/                  SQLite、メディア、分析・Obsidian Vault
│  ├─ logs/                  起動・実行ログ
│  ├─ models/                ダウンロード済みモデル
│  ├─ output/                文字起こしの出力
│  └─ uploads/               実行中の一時ファイル
├─ notebooks/                Colab ノートブック
├─ docs/                     設計資料
└─ tests/                    自動テスト
```

`runtime/` は利用者データです。バックアップは、画面の「接続と処理装置」にある「バックアップを作成」か、アプリ停止中に `python scripts/backup_data.py create` で作成します（保存先 `runtime/backups`）。DB・分析結果・Vault・台帳・作業台・単語登録を同じ時点で写し、全ファイルのSHA-256を `manifest.json` に記録します。元の音声・動画は既定で含めません（画面のチェックまたは `--include-media`）。出力ファイルとサムネイルは再生成されるため含めません。確認は `verify <フォルダー>`、復元は `restore <フォルダー>` で、空のデータフォルダーにだけ戻します。`config/tokens.json` には秘密情報が含まれるため、必要に応じて別途安全に保管してください。

開発時のテストは、プロジェクト直下で次を実行します。

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -p 'test_*.py'
```
