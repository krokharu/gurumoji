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

`runtime/` は利用者データです。バックアップ時は、アプリを停止してこのフォルダー全体をコピーしてください。`config/tokens.json` には秘密情報が含まれるため、必要に応じて別途安全に保管してください。

開発時のテストは、プロジェクト直下で次を実行します。

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -p 'test_*.py'
```
