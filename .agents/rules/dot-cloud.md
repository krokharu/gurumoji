# Gurumoji: dot クラウド CPU 運用

[AGENTS.md](../../AGENTS.md) から、起動・配置・環境間の受け渡しで必要なときに読む。一般的な開発・研究ルールはここに複製しない。

## dot で進め、ローカル開発へ記録を渡す

基本的な調査・編集・検証・進捗確認は利用可能な dot の機能を優先する。Obsidian は開発の継続に必要な記録を共有する場所として使い、操作のたびに書き込む必要はない。配置、設計判断、互換性、検証、未解決事項に重要な変化があった時点で [Software Vault の運用引継ぎ](../../docs/program-vault/60-Operations/dot-cloud-development-handoff.md) を更新する。

ノートには関連 commit、決定理由、再現に必要なコマンド／根拠、成功・失敗・未実行、次の作業を簡潔に残す。詳細ログや大きな結果は `artifacts` を参照し、資格情報・実会話・不要な個人情報を収録しない。Software Vault の記録はアプリ Git で受け渡し、移入した研究 Vault や PC 原本に自動反映しない。

## 実行環境と配置

確認済みの配置は `/workspace/scratch/be1eb353f7eb/projects/gurumoji/app`。以下で `<project>` はその親、`<app>` はチェックアウトを指す。絶対パスは配置の記録であり、ソースへ固定する値ではない。移入元は app commit `4b311df51c7fe2938f1761cb1efbb4cc4906fd10`、準備ブランチは `dot/cloud-cpu-setup`。作業の都度、実際の HEAD と差分を確認する。

| 領域 | 場所・設定 | 境界 |
| --- | --- | --- |
| アプリ／Software Vault | `<app>`／`docs/program-vault` | アプリ Git が版の正本 |
| Python | `<app>/.venv/bin/python`、初期構築版 3.12.14 | Linux 用。Windows venv をコピーしない |
| 実行データ | `<project>/runtime/data` = `MOJIOKOSI_DATA_DIR` | DB、分析結果、実行時 Vault、台帳、作業台 |
| 出力／バックアップ | `runtime/output`／`runtime/backups`（`<project>` 基準） | `MOJIOKOSI_OUTPUT_DIR`／`MOJIOKOSI_BACKUP_DIR` |
| モデル／ログ | `<project>/runtime/models`／`runtime/logs` | Git 対象外。秘密・本文をログへ出さない |
| 一時アップロード | `<app>/runtime/uploads` | 現行コードの実ディレクトリを維持 |
| 移入 Vault repo | `<project>/vaults` | runtime と独立した私有 Git。ノートはさらに `vaults/` 配下 |
| 検証記録 | `<project>/artifacts` | commit・条件・結果を記録。匿名サンプルのみ |

[scripts/run_cloud.sh](../../scripts/run_cloud.sh) は既存の DATA／OUTPUT／BACKUP 環境変数を sibling `runtime` に設定する。任意の外部値や `.env` を自動で読み込むとは仮定しない。`runtime` を symlink にせず、出力・回復処理のパス検証を無効化しない。旧配置 `/workspace/scratch/be1eb353f7eb/gurumoji_cloud` の互換参照は、仮想環境の entry point に関係するため用途を確認せず削除しない。

## 起動・CPU・到達性

`<app>` から実行する。

```bash
.venv/bin/python --version
.venv/bin/python -m pip check
bash scripts/run_cloud.sh
```

- 依存元は [requirements.txt](../../config/requirements.txt)、CPU の整合性は [constraints-cloud-cpu.txt](../../config/constraints-cloud-cpu.txt)、構築時の固定版は [requirements-cloud-cpu.lock.txt](../../config/requirements-cloud-cpu.lock.txt)。最小 UI 構成だけなら [requirements-cloud-core.txt](../../config/requirements-cloud-core.txt)。制約とインストール一覧を混同せず、torch 一式を CUDA 版へ戻さない
- GPU、CUDA、Colab A100、Windows の LM Studio/Ollama は利用可能と仮定しない。CPU torch／torchaudio 2.8.0+cpu、torchvision 0.23.0+cpu が構築時の組み合わせ。再導入後は実際の版と `pip check` を検証する
- ランチャーは `127.0.0.1:7860`（ポートは設定可）、`NO_BROWSER=1`、`ALLOW_REMOTE=0` を使う（各変数は `MOJIOKOSI_` 接頭辞）。公開 bind、トンネル、認証解除、許可ホスト／Origin の拡大を疎通試験の代わりに行わない
- `HF_HUB_OFFLINE=1` と `TRANSFORMERS_OFFLINE=1` は OpenAI Whisper 独自のダウンロードを止めない。キャッシュの tiny 以外のモデルや gated 話者分離を、取得済み・認証済みと扱わない。追加取得は配布元・モデル版・容量・利用条件・認証要否を確認してから行う
- 同一セッションでの HTTP 応答と、利用者のブラウザーからの到達性は別。現在の配置だけで外部利用可能とはいえない。使用しているブラウザーと到達できた範囲を明示する

## 移入 Vault と環境間の版管理

5 Vault の確認済みルートは `<project>/vaults/vaults/{ResearchVault,InputVault,VisualizationVault,OrchestratorVault,PersonaVault}`。Software Vault は `<app>/docs/program-vault` に別途存在する。PersonaVault をアプリの新しい生成 Vault と見なさず、4+1 の保存契約へ勝手に追加しない。

移入 repo の基点は `045d51340b989d934b730b639d45312556596e84`、タグは `gurumoji-vault-base-v1`、クラウド作業ブランチは `cloud/work`。最初の移入は 1,398 ファイルの hash で検証済み。外部 remote は未設定。実行時の `<data>/obsidian/...` とは切り離し、アプリの監視・同期先に接続しない。ノートだけの snapshot であり、DB・メディア・analysis_store を復元したものではない。

```bash
# snapshot の manifest と実ファイルを照合する（read-only）
python3 ../vaults/verify_snapshot.py
# 版と未コミット変更を確認する
git -C ../vaults status --short
git -C ../vaults diff gurumoji-vault-base-v1..HEAD -- vaults
```

- アプリの Git と Vault の Git を分ける。アプリは確認済みの既存 remote を使い、非公開性と送信対象を確認してから受け渡す。origin があるだけで私有データの push を許可されたと扱わない。Vault は Git bundle による受け渡しが基本で、remote を追加したり別サービスへ push したりしない
- 受け取った版は別のレビュー用 ref／作業場所で確認する。共通基点からローカル側・クラウド側をそれぞれ比較する三者比較を使う。両側変更、改名／削除、生成ノートの編集は人の判断が必要。元の両版を残し、自動 merge・双方向自動同期・force push・reset／clean・削除付きミラーで解消しない
- 受け渡しの手順は移入 repo の [SYNC_OPERATIONS.md](../../../vaults/SYNC_OPERATIONS.md) を正本とする。`compare_vault_refs.py` は clean な repo と共通基点の子孫である両側 ref を要求する read-only 比較で、差分を適用しない。`snapshot_update.py` は元 Vault からの取得用であり、双方向同期や元ノートの更新に使わない。STOP を `--initial` や強制コピーで回避しない
- 原本へ採用する差分は、所有権・ID・hash・既存アプリの履歴保存経路を確認してから反映する。初期タグ `gurumoji-vault-base-v1` は不変とし、移動・置換しない。双方で受理した bytes と manifest が一致してから新しい版付きタグで次の共通基点を合意し、取得ツールの基点設定も別途レビューする
- `endpoint-map.json` のクラウド URL／パスは現在値を確認する。元ノート内の Windows パスや localhost 参照を一括置換しない。アプリとの接続、DB の整合、双方向反映は別途未設定・未検証として扱う
- コミットは対象ファイルだけを列挙し、他の担当と順番を合わせる。push 前後の commit を確認する。ローカル PC の未追跡ルールは受領元と相対パスを確認し、Windows 固有手順をクラウド共通規約へ混ぜない

## プライバシーと対象外

ローカル PC の `.env`、`config/tokens.json`、OAuth、ブラウザー認証、SSH/API キーをコピーしない。Git 用の認証をアプリの AI／Hugging Face 認証に流用しない。秘密値は表示・記録せず、必要な認証がなければ該当機能を未設定と報告する。私有 Git でも生メディア、DB、モデル、秘密、不要な個人情報を追加しない。

配置作業だけを理由に実データや研究ノートを外部 AI へ送信しない。ADC08 は将来用の予約領域として維持し、Gurumoji の Vault クラスやルールを適用しない。

## 検証コマンド

現行テストが一時領域を使うことを確認し、`<app>` から変更に応じて選ぶ。Linux の `PYTHONPATH` は `:` 区切り。

```bash
# 起動・CPU 診断・安全性
PYTHONPATH=src:tests .venv/bin/python -m unittest test_application_lifecycle test_machine_profile test_backend_safety -v
# Vault／更新／保存契約
PYTHONPATH=src:tests .venv/bin/python -m unittest test_four_vaults test_vault_note_policy test_update_program_vault test_data_backup -v
# 広範囲の変更
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
# キャッシュ済み tiny + 合成音声のみ。Vault や UI ジョブは変更しない
.venv/bin/python scripts/smoke_cloud_cpu.py
```

CPU 音声 smoke は hash 検証済み `runtime/models/whisper/tiny.pt` と FFmpeg の flite を使い、結果を `artifacts/whisper-cpu-smoke.json` に保存する。これは話者分離・AI API・UI 一連操作の検証ではない。依存不足やモデル未取得で失敗したテストを、安全条件の緩和や削除で通さない。
