# 開発・試験・設計書

利用者の指定により、mainは引渡し用、`archive/development-assets-20261016` は開発資料・試験の保存用です。

| main | 開発資料ブランチ |
| --- | --- |
| アプリ本体、起動・保守、利用手順 | テストコード・架空データ・評価プログラム |
| 実行時に必要な専門家・文献・スライド定義 | 完全なSoftware Vault、設計計画、ADR、検証記録 |
| Colabアプリのノートブック | 開発用コンソール、画面試作、エージェント用資料 |

アプリ本体と実行時定義の正本は現在のmainです。保存用ブランチの`src`はmainより古い場合があるため、そのブランチを起動しても現在のアプリの検証にはなりません。設計根拠は[完全なSoftware Vault](https://github.com/krokharu/gurumoji/tree/archive/development-assets-20261016/docs/program-vault)を参照します。

## mainを隔離して検証する

保存用の`prepare_main_validation.py`で、新規の検証cloneを作成します。local mainの追跡ファイルは未コミット変更・削除も含めて現行bytesを保持し、固定した保存資料commitから不足する試験・開発ツール・設計資料を補完します。main由来のファイルと実行時カタログは上書きしません。保存資料の`src`は補完対象外です。

元のmain・branch・worktreeを切り替えず、`.env`、`runtime`、`output`、`config/tokens.json`等の私有ファイルを持ち込みません。未追跡ファイルは自動収集しません。新規実装も検証する場合は、対象を確認して`--include src/gurumoji/対象.py`のように通常ファイル単位で指定します。保護対象は明示指定しても拒否します。

次はlocal mainのrepository rootで実行するPowerShell例です。取得する保存資料SHAを表示して確認し、bootstrapファイルと検証先には未作成の名前を指定してください。

```powershell
git fetch origin
$env:PYTHONUTF8 = '1'
$archiveRef = (git rev-parse origin/archive/development-assets-20261016).Trim()
$archiveRef
python -c "import pathlib,subprocess,sys; p=pathlib.Path('../prepare-main-validation.py'); data=subprocess.check_output(['git','show',sys.argv[1]+':scripts/prepare_main_validation.py']); p.open('xb').write(data)" $archiveRef
python ../prepare-main-validation.py --source . --target ../gurumoji-validation --archive-ref $archiveRef
cd ../gurumoji-validation
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r config/requirements-cloud-core.txt -r config/requirements-dev.txt
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install soundfile jsonschema requests 'lmstudio>=1.5,<2'
$env:MOJIOKOSI_DATA_DIR = "$PWD/output/validation/runtime"
$env:HF_HOME = "$PWD/output/validation/hf-cache"
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.venv\Scripts\python.exe scripts/run_tests.py --scope main --split-module test_developed_analysis_unit_pool_independent --timeout-seconds 600 --output output/validation/tests
```

`output/validation/prepare-manifest.json`にmain HEAD、準備時の追跡変更、保存資料ref/commit、各ファイルの由来とSHA-256、削除・除外を記録します。source/targetの重複、既存target、symlink/junction、未解決のindex競合は拒否します。準備失敗時は半完成の検証cloneを調査用に残すため、再実行には別の未作成targetを指定してください。

検証先には保存資料だけの設計ノートも補完されます。`docs/program-vault/00-Catalog.json`はmain配布資料の索引として維持し、検証先の全設計ノートを含めて再生成しないでください。main資料の完全性はmanifestの`origin: main`または`main-explicit`と、元のmainの実資料を基準に照合します。カタログ更新・`build_program_vault_catalog.py --vault <main>/docs/program-vault --check`は、実行時資料だけを持つmainで行います。

CPU環境の上記導入は試験用Pythonを検証clone内に新設します。利用中アプリのPython、モデルキャッシュ、ポート、DB、Vaultは共有しません。通常試験はモデルをdownloadせず、欠けている任意依存や対象外の試験は理由付きで報告します。音声モデルの実試験に必要なtorchaudioは通常試験の直接依存には含めません。ObusSQL等の任意連携を検証する場合は、専用環境に必要な版を別途導入して明示実行します。

保存用のエージェント資料コピーも確認する場合は、固定した保存資料commitから`.agents`・`.claude`・`AGENTS.md`・`DESIGN.md`・リンク先の`docs`を別フォルダーへ取得し、`GURUMOJI_AGENT_ASSETS_SOURCE`にそのrootを明示して、検証cloneで`.venv\Scripts\python.exe -m pytest tests/test_agent_assets_sync.py::RepositoryCopiesTests`を実行します。未指定のコピー試験2件は`not-run`、明示した空・不正rootはerrorとして報告します。同期処理自体の合成試験は通常試験でも実行します。この保存資料のコピー整合性はmainアプリの検証結果と分けて扱います。

Windows Python 3.12の制約を更新する場合は、検証環境の`.venv\Scripts\python.exe -m pip freeze`から再生成します。`config/constraints-windows-cp312.txt`には`name==version`のみ残し、直接参照・PyTorch 3製品・任意ObusSQL/MAFを除外してください。

DOM試験は`tests/dom/package.json`の`engines`を満たすNode.jsを別途用意し、次のように実行します。通信は合成APIに限定します。

```powershell
$env:GURUMOJI_TEST_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
$env:GURUMOJI_REUSE_SOURCE_ROOT = "$PWD"
npm ci --prefix tests/dom
npm test --prefix tests/dom
```

ブラウザー実操作と実モデルは通常の試験とは別に明示実行します。合成試験の成功、実モデルの契約合格、研究上の品質承認を同一視しません。

mainの整理はファイルの配布範囲だけを変え、利用者DB・研究者ノート・モデル・認証設定を移行しません。未実装・品質未承認の機能の状態も変えません。

GitHub ActionsはPythonのコンパイル、ruff、JavaScriptの構文を検査します。
ローカルのlintは `python -m pip install ruff==0.8.6` の後、`ruff check src scripts --no-cache` で実行します。
開発資料ブランチの試験ジョブは、GitHub上で確認が済むまで手動実行のみです。

## バージョンの付け方

表示は `src/gurumoji/app.py` の `APP_VERSION` が正本です。

- `β`: 画面に「Coming Soon」が残っている間は付ける。なくなったら外す。
- 先頭の数字: 製品版になったら1にする。それ以降はメジャーアップデートで上げる。
- 次の数字(46など): 通常アップデートで上げる。
- 最後の数字(1など): 細かいパッチで上げる。
