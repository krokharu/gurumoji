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

## dot の Linux CPU 配置

クラウドではプロジェクト単位で `app/`（この Git リポジトリ）、`runtime/`、
`vaults/`（移入ノートの独立した Git）、`artifacts/` に分けます。
`scripts/run_cloud.sh` は既存の `MOJIOKOSI_DATA_DIR`、`MOJIOKOSI_OUTPUT_DIR`、
`MOJIOKOSI_BACKUP_DIR` を `app/` の隣の `runtime/` 配下へ設定します。
一時アップロードだけは既存実装どおり `app/runtime/uploads` に置きます。
パス安全検査を保つため、`app/runtime` は symlink にしません。

Python 3.12 の仮想環境を `app/.venv` に作り、まず公式 CPU wheel を入れます。
その後、検証時の全依存をロックファイルで再現します。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install torch==2.8.0+cpu torchaudio==2.8.0+cpu torchvision==0.23.0+cpu --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r config/requirements-cloud-cpu.lock.txt
.venv/bin/python -m pip check
bash scripts/run_cloud.sh
```

元の要件範囲で更新する場合は `config/requirements.txt` に
`-c config/constraints-cloud-cpu.txt` を併用し、検証後にロックを更新します。
`config/requirements-cloud-core.txt` は UI だけの軽量構成です。

起動先は `127.0.0.1:7860` のみです。公開 URL や常時稼働サービスではなく、
実行環境のセッション寿命・到達性に従います。サーバーと同じセッション内の
HTTP 応答、別セッションからの到達、ブラウザー表示は別々に検証してください。
認証を外す・公開 bind を使う・トンネルを作ることを標準の解決策にしません。

`runtime/models/whisper/tiny.pt` を保存済みなら、
`.venv/bin/python scripts/smoke_cloud_cpu.py` でローカル合成音声による CPU 推論を
確認できます。このスクリプトはモデルをダウンロードせず、アプリの DB や
移入 Vault を更新しません。FFmpeg の `flite` フィルターが必要です。

元 UI の WhisperX ジョブには Hugging Face token と gated pyannote 話者分離モデルが
必要です。CPU Whisper 単体の成功を、UI 全工程・話者分離の成功とは扱いません。
モデル、資格情報、外部 AI、GPU、ローカル LLM は別途の確認・認可対象です。
ランチャーは HF/Transformers のオンライン取得とライブラリ telemetry を無効に
しますが、OpenAI Whisper 独自のモデル取得機構にはそのオフライン設定が効きません。
移入 Vault のスナップショットは空のアプリ runtime と切り離して保持します。
