# Gurumoji（グルモジ）

<p align="center">
  <img src="docs/assets/gurumoji-animated.svg" alt="グルモジのアニメーションロゴ" width="640">
</p>

<p align="center"><strong>動画・音声を文字に。会話を、読み返せる・分析できるデータに。</strong></p>

Gurumojiは、動画・音声の**文字起こし → 話者・本文の確認と編集 → 会話の分析 → 保存・出力**を行うWebアプリです。WindowsとGoogle Colabに対応しています。現在の**バージョンはβ0.47.0です。**

[Windowsで始める](#windowsで始める) · [使う流れ](#使う流れ) · [できること](#できること) · [操作ガイド](#操作ガイド)

## Windowsで始める

### 1. 初回の準備

フォルダー内の **`setup_gui.bat` をダブルクリック**し、画面の案内に従ってPython・アプリ環境と必要な接続情報を設定します。

話者分離（誰が話したかを分ける機能）には、Hugging Faceの利用条件への同意と **read token** が必要です。セットアップ画面の案内に従って準備してください。外部AIを使わない機能は、外部AIの接続を設定せずに利用できます。

### 2. アプリを開く

**`run.bat` をダブルクリック**し、起動後にブラウザーで **[http://127.0.0.1:7860](http://127.0.0.1:7860)** を開きます。2回目以降はここから始められます。

### 3. 動画・音声を選んで開始

文字起こし画面でファイルを選び、設定を確認して処理を開始します。完了したら、元の音声・動画を再生しながら本文や話者名を確認できます。

<details>
<summary>手動で環境を準備する場合</summary>

Python 3.10〜3.13の64bit版で仮想環境を作り、依存関係を導入します。GPU・FFmpeg・話者分離の準備も必要なため、通常はセットアップ画面を使ってください。

PowerShellで、アプリのフォルダーから実行します。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r config/requirements.txt
.\run.bat
```

</details>

## 使う流れ

| 手順 | 操作 | できあがるもの |
| --- | --- | --- |
| 1. 文字にする | 動画・音声を選び、文字起こしを実行 | 話者・時刻付きの発話 |
| 2. 確認する | 元の音声を聴きながら、本文・時刻・話者名を編集 | 内容を確認した文字起こし |
| 3. 分析する | 発話量や会話の時間構造、単語・テーマなどを確認 | 集計表・図・分析結果 |
| 4. 保存・出力する | 本文や分析結果を書き出し、必要に応じてVaultへ保存 | TXT・JSON・SRT、Excel・SPSS SAV・図など |

## できること

| 目的 | 主な機能 |
| --- | --- |
| 文字起こし・編集 | Whisper / WhisperXによる文字起こし、話者分離、音声・動画の再生、本文・時刻・話者名の編集 |
| 話者・資料の整理 | 話者台帳、追加属性、CSV取込・出力、タグ・分析グループの管理 |
| AIによる仕上げ（任意） | 話者名候補、アウトライン、表記ゆれの確認 |
| 会話の分析 | 発話量、会話の時間構造、日本語形態素、共起、記述統計、意味テーマの分析 |
| 結果の保存・再利用 | 分析結果の固定保存と履歴、Excel・SPSS SAV・図の出力、型付き表の単位・尺度・出所を指定した統計計算 |
| 研究メモ・検索 | 研究メモ・解釈・コード案の差分取込、外部分析結果の登録、会話横断の全文検索、保存済みベクトルによる類似発話検索 |
| Obsidianとの連携 | 研究用・台帳用Vaultへの保存、バックアップ・復元 |

**AIの見解と生成列は下書きです。** 構造・根拠IDの検査と、研究上の正しさ・採用判断は区別してください。高度な会話分析やモデル品質の採用など、未実装・未承認の機能は利用可能として扱っていません。

<details>
<summary>実験的な日本語文字起こし：Haas-ja v1.0</summary>

Third Intelligence公式のHaas-ja v1.0による日本語文字起こしにも実験的に対応しています。**NVIDIA GPUが必要**です。

- **Windows**：WSL2のUbuntu 24.04上で実行します。`scripts\setup_haas_ja.bat` で専用環境とモデルを準備します。
- **Linux**：`bash scripts/setup_haas_ja.sh` で準備します。
- 話者分離にはNemotron 3を使います。

GGUF変換版（sakasegawa）は公式配布ではなく、本アプリでは使いません。

</details>

## 保存先とバックアップ

利用者データの既定の保存先は **`runtime/`** です。APIキーなどの秘密情報は **`config/tokens.json`** に保存します。秘密情報・モデル・利用者データはGitへ追加しないでください。既存の本文・属性・研究ノートをテスト用に転用しないでください。

バックアップは、アプリ画面の **「接続と処理装置」→「バックアップを作成」** から作成できます。秘密情報はバックアップ対象と別に安全に保管してください。

<details>
<summary>コマンドでバックアップを作成・検証する場合</summary>

アプリを停止してから、PowerShellで実行します。

```powershell
.venv\Scripts\python.exe scripts/backup_data.py create
.venv\Scripts\python.exe scripts/backup_data.py verify <バックアップフォルダー>
```

`<バックアップフォルダー>` は、作成されたフォルダーのパスに置き換えてください。

</details>

復元先には空のデータフォルダーを指定してください。保存形式を切り替えた後に古いコードへ戻す場合は、対応するバックアップと履歴の整合を確認してください。

## Google Colab / Linuxで使う

**Google Colab**：[Colabノートブックを開く](https://colab.research.google.com/github/krokharu/gurumoji/blob/main/notebooks/Gurumoji_Colab.ipynb)。ノートブックの認証付きポート表示からアプリを開きます。

**Linux**：環境を作成し、`bash scripts/run_cloud.sh` で起動します。CPUの再現用依存関係は `config/requirements-cloud-cpu.lock.txt`、UI用の軽量構成は `config/requirements-cloud-core.txt` です。

Windowsの仮想環境は転用せず、実行する環境で作り直してください。GPU推論・話者分離・外部AIの利用可否は配置先で別途確認してください。

## 操作ガイド

| 確認したいこと | ガイド |
| --- | --- |
| フォルダー構成・環境変数 | [配置と設定](docs/PROJECT_LAYOUT.md) |
| Obsidianの保存先・Vaultの使い分け | [Obsidian Vault](docs/OBSIDIAN_VAULTS.md) |
| ObusSQLの接続確認・管理ノート検索 | [ObusSQL](docs/OBUSSQL.md) |
| ObsidianでAI仕上げを使う | [ObsidianでのAI仕上げ](docs/OBSIDIAN_FINISHING.md) |
| AI仕上げを設定する | [AI仕上げの設定](docs/AI_EFFORT.md) |
| 音声から感情を分析する | [任意の音声感情分析](docs/EMOTION_ANALYSIS.md) |
| 開発・試験・設計の資料を探す | [開発資料の参照先](docs/DEVELOPMENT.md) |

<details>
<summary>リポジトリの収録範囲・従来の詳細ガイド</summary>

mainにはアプリ本体、起動・保守に必要なプログラム、利用手順、実行時に使う専門家・文献・スライド定義を収録しています。

テストコード・架空データ・開発用プログラム・設計書の全体は[開発資料ブランチ](https://github.com/krokharu/gurumoji/tree/archive/development-assets-20261016)に保存しています。[従来の詳細な操作・設定ガイド](https://github.com/krokharu/gurumoji/blob/archive/development-assets-20261016/README.md)も同ブランチに保持しています。

</details>
