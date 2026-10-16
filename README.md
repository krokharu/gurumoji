# Gurumoji

動画・音声を文字起こしし、話者と発話を確認・編集して、会話を分析するWebアプリです。WindowsとGoogle Colabに対応しています。バージョンは1.8.0です。

mainにはアプリ本体、起動・保守に必要なプログラム、利用手順、実行時に使う専門家・文献・スライド定義を収録しています。テストコード・架空データ・開発用プログラム・設計書の全体は[開発資料ブランチ](https://github.com/krokharu/gurumoji/tree/archive/development-assets-20261016)に保存しています。

## Windowsで始める

1. 初回は `setup_gui.bat` を開き、Python・アプリ環境と必要な接続情報を設定します。
2. 話者分離にはHugging Faceの利用条件への同意とread tokenが必要です。セットアップ画面の案内に従ってください。
3. `run.bat` を開き、ブラウザーで `http://127.0.0.1:7860` にアクセスします。
4. 動画・音声を選び、文字起こし条件を確認して開始します。

APIキーなどの秘密情報は `config/tokens.json` に保存します。このファイル、モデル、利用者データはGitへ追加しないでください。接続情報が不要な機能は、外部AIを設定せずに使えます。

手動で環境を作る場合は、Python 3.10〜3.13で仮想環境を用意し、依存関係を導入します。GPU・FFmpeg・話者分離の準備も必要なため、通常はセットアップ画面を使ってください。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r config/requirements.txt
run.bat
```

## できること

- Whisper / WhisperXによる文字起こし、話者分離、TXT・JSON・SRTの出力
- 発話・本文・時刻・話者名の確認と編集、元の音声・動画の再生
- 話者台帳、追加属性、CSV取込・出力、タグ・分析グループの管理
- 任意のAI仕上げ、話者名候補、アウトライン、表記ゆれの確認
- 発話量・会話構造・日本語形態素・共起・記述統計・意味テーマの分析
- 分析結果の固定保存、履歴の読み返し、Excel・SPSS SAV・図の出力
- 保存した型付き表から、単位・尺度・出所を指定した統計計算
- 研究メモ・解釈・コード案の差分取込、外部分析結果の登録
- 会話横断の全文検索と、保存済みベクトルによる類似発話検索
- Obsidianの研究用・台帳用Vaultへの保存と、バックアップ・復元

AIの見解と生成列は下書きです。構造・根拠IDの検査と、研究上の正しさ・採用判断は区別してください。高度な会話分析やモデル品質の採用など、未実装・未承認の機能は利用可能として扱っていません。

## 保存先とバックアップ

利用者データは既定で `runtime/` に保存します。既存の本文・属性・研究ノートをテスト用に転用しないでください。

画面の「接続と処理装置」からバックアップを作成できます。CLIを使う場合はアプリを停止してから実行します。

```powershell
.venv\Scripts\python.exe scripts/backup_data.py create
.venv\Scripts\python.exe scripts/backup_data.py verify <バックアップフォルダー>
```

復元先は空のデータフォルダーにしてください。秘密情報はバックアップ対象と別に安全に保管します。保存形式を切り替えた後に古いコードへ戻す場合は、対応するバックアップと履歴の整合を確認してください。

## 操作・配置の資料

- [フォルダー構成・環境変数](docs/PROJECT_LAYOUT.md)
- [Obsidian Vaultの使い分け](docs/OBSIDIAN_VAULTS.md)
- [ObsidianでのAI仕上げ](docs/OBSIDIAN_FINISHING.md)
- [AI仕上げの設定](docs/AI_EFFORT.md)
- [任意の音声感情分析](docs/EMOTION_ANALYSIS.md)
- [開発・試験・設計書の参照先](docs/DEVELOPMENT.md)

[従来の詳細な操作・設定ガイド](https://github.com/krokharu/gurumoji/blob/archive/development-assets-20261016/README.md)も開発資料ブランチに保持しています。

## Google Colab / Linux

[Colabノートブックを開く](https://colab.research.google.com/github/krokharu/gurumoji/blob/main/notebooks/Gurumoji_Colab.ipynb)。ノートブックの認証付きポート表示を使用します。Windowsの仮想環境は転用しません。

Linuxでは環境を作成し、`scripts/run_cloud.sh` で起動します。CPUの再現用依存関係は `config/requirements-cloud-cpu.lock.txt`、UI用の軽量構成は `config/requirements-cloud-core.txt` です。GPU推論・話者分離・外部AIの利用可否は配置先で別途確認してください。
