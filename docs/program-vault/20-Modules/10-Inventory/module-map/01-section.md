---
note_type: reference-section
status: current
verified: 2026-09-25
updated: 2026-09-26
tags:
- gurumoji/program
note_id: program-module-map-section-01
title: 機能・コード・テストの対応表：機能・コード・テストの対応表
summary: 機能・コード・テストの対応表。出典ノート「機能・コード・テストの対応表」の分割本文。
parent_note_id: program-module-map
source_path: 20-Modules/module-map.md
source_sha256: 9d4be038e5ca8e5f28209be2d481906c976790670a214ce8b9bc595ce249b386
source_body_lines:
- 1
- 32
split_on: '2026-10-11'
---

# 機能・コード・テストの対応表：機能・コード・テストの対応表

親索引・状態・確認版：[[20-Modules/10-Inventory/module-map/00-Index]]。必要な本文だけを取得する。


# 機能・コード・テストの対応表

コードのパスは `src/gurumoji/` から、それ以外（`tests/`、`docs/`、`scripts/`、`run.bat` など）はリポジトリルートからの相対パスです。2026-09-25 の `app.py` 分割で移った関数の一覧は [[70-Changes/10-Compatibility/app-py-phase5|app-py-phase5]] と同じフォルダーの JSON にあります。最新版`2f13f98`で追加されたゴミ箱・バックアップ・ノート履歴・画面別テンプレートも以下に追記しました。資料とコードの関連付けには、行番号より変更に強いファイル名・関数名を使います。

2026-09-14の優先修正：`obsidian_layout.sync_themes/sync_finishing`による人のノート保護、`obsidian_finishing.prepare/save_note`と`analysis_store.write_atomic(create_only=True)`による既存ノート保護、比較APIの`input_fingerprints`照合、`transcript_preparation.initialize`の更新待ち伝播トリガー、`static/app.js`の未保存・応答順序制御。詳細と検証先は[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）|convergence-plan#優先修正の実装（2026-09-14）]]。

| 機能 | 実装・入口 | 主な検証先 |
| --- | --- | --- |
| 起動・更新 | `run.bat`, `run_launcher.ps1` | `tests/test_launcher.py`, `tests/test_ui_defaults.py` |
| 初期セットアップ | `setup_gui.bat`, `setup_gui.ps1` | `tests/test_setup_gui.py` |
| Colab | `notebooks/Gurumoji_Colab.ipynb` | `tests/test_colab.py` |
| マシン診断 | `services/machine_profile.py`: `get_machine_profile`, `detect_machine_profile`, `system_activity_snapshot` | `tests/test_machine_profile.py` |
| 音声前処理・小声対策・空白補完 | `services/transcription/job_runner.py`: `run_transcription_job`; `services/transcription/audio.py`: 話者分離用の小声補強; `services/transcription/segments.py`: 3秒以上の空白抽出 | `tests/test_audio_preprocess.py`, `tests/test_gap_supplement.py`, `tests/test_pipeline_regressions.py` |
| 文字起こし整形・確認レポート | `services/transcription/formatting.py`: `transcript_formatting_result`, `normalize_transcript_punctuation`。`app.py` は既存の呼び出し名と依存の接続を保持 | `tests/test_transcript_formatting.py`, `tests/test_pipeline_regressions.py` |
| 音声感情分析 | `services/emotion.py`: `run_aist_emotion_analysis`, `build_emotion_analysis_summary`（`app.py` は依存を渡す入口）; `docs/EMOTION_ANALYSIS.md`, `scripts/setup_emotion.bat`, `scripts/bootstrap_s3prl.py` | `tests/test_emotion_batch.py`, `tests/test_pipeline_regressions.py` |
| ライブラリ・DB初期化 | `services/library_schema.py`: `initialize_library`; `services/library_store.py`: `library_row`, `library_public`, `upsert_library_item`; `services/library_rows.py`: `row_segments`, `ensure_segment_ids`; `services/output_import.py`: 既存出力の取り込み | `tests/test_backend_safety.py`, `tests/test_analysis.py` |
| 話者管理 | `handlers/speaker_registry.py`: `SpeakerRegistryHandler`; `web/speaker_routes.py`; `web/export_routes.py`: `export_speaker_registry`; 話者名の推定は `services/speaker_identification.py`、再推定は `handlers/speaker_identification.py` | `tests/test_speaker_registry.py` |
| 編集保存と回復 | `services/library_edits.py`: `normalize_edited_segments`, `_update_library_from_payload_locked`; `services/edit_transactions.py`: マニフェスト・回復 | `tests/test_edit_recovery.py`, `tests/test_outputs.py` |
| 会話削除・ゴミ箱・復元 | `web/library_deletion.py`; `services/library_trash.py`: 削除行とメディアのmanifest、復元、完全削除、期限切れ処理; `web/library_routes.py`: trash API | `tests/test_backend_safety.py`, `tests/test_application_lifecycle.py` |
| データバックアップ・検証・復元 | `services/data_backup.py`: `create_backup`, `verify_backup`, `restore_backup`; `scripts/backup_data.py`; `web/system_routes.py`: `POST /api/system/backup` | `tests/test_data_backup.py`, `tests/test_application_lifecycle.py` |
| 会話集計・手動分析 | `services/group_analysis.py`: `group_analysis_for_row`, `normalize_analysis_config`, `normalize_analysis_annotations`; `services/group_analysis_exports.py`: レポート・CSV; `services/analysis_annotations.py`: 分析設定・注釈の保存 | `tests/test_analysis.py`, `tests/test_method_expert_samples.py` |
| 日本語解析・統計 | `research_analysis.py`: `build_research_analysis`, `_linguistic_analysis`, `_statistics_analysis` | `tests/test_research_analysis.py` |
| 見解・KWIC・特徴語 | `analysis_insights.py`: `build_content_analysis`, `search_kwic`, `create_ai_insights`, `validate_findings` | `tests/test_content_analysis.py` |
| AI見解の実行と保存 | `services/analysis_jobs.py`: `run_analysis_insight_job`, `start_analysis_insights_command`, `cancel_analysis_insights_command`; HTTPは `web/analysis_routes.py` | `tests/test_content_analysis.py`, `tests/test_content_browser.py` |
| 手法ごとの専門家定義 | `method_experts.py`: `ExpertCatalog`, `review_for_analysis`, `ai_context`, `attach_method_reviews`, `report_lines`; `app.py`: `group_analysis_for_row`; `services/analysis_jobs.py`: `start_analysis_insights_command`; `web/analysis_view_routes.py`: `get_analysis_experts`。定義はSoftware Vaultの `50-Analysis-Methods/10-Experts`（ADR-115）。実行環境ごとの `<data>/local_knowledge/…` があれば同じ相対パスで上書き・追加する（ADR-120） | `tests/test_method_experts.py`, `tests/test_method_expert_samples.py` |
| 手法別の分析画面 | `web/analysis_view_routes.py`: `get_analysis_method_overview`; `method_experts.py`: `method_overview`; `static/app.js`: `renderMethodAnalysis`, `buildExpertDetails`, `methodResultPanels`（パネルは `data-analysis-method` で対応付け、ADR-116） | `tests/test_analysis_method_view.py` |
| AI通信・モデル設定・応答判定 | `ai_http_worker.py`; `services/ai/client.py`: `call_ai_json`, `ensure_complete_response`, HTTP 429／一時的な5xxの最大2回再試行; `services/ai/settings.py`: `TokenConfig`, `configured_ai_credentials`, `available_ai_models` | `tests/test_ai_client_responses.py`, `tests/test_ai_http_worker.py`, `tests/test_ai_model_settings.py`, `tests/test_ai_scaling.py` |
| 根拠付きAI仕上げ | `ai_finishing.py`: `clean_transcript`, `create_outline`, `finishing_changes` | `tests/test_ai_finishing.py`, `tests/test_pipeline_regressions.py` |
| 手法別の固定保存・Vault | `analysis_method_registry.py`, `analysis_store.py`; `services/analysis_archive.py`: `archive_group_analysis`, `archive_ai_finishing` | `tests/test_analysis_storage.py` |
| 4 Vaultへの書き出し・生成ノート保護 | `vault_registry.py`: `VaultRegistry.publish_input`, `retire_input`, `publish_analysis`; `vault_note_policy.py`: 共通hash判定と履歴コピー; `analysis_store.py`: `AnalysisStore.publish_vaults`, `refresh_vaults`; `app.py`: `publish_input_vault`, `retire_input_vault`, `whisper_vault_settings` | `tests/test_four_vaults.py`, `tests/test_vault_coverage.py`, `tests/test_vault_note_policy.py` |
| 会議議事録・インタビュー比較の独立保存 | `services/interview_comparison.py`: `build_interview_comparison`; `services/analysis_archive.py`: `archive_meeting_minutes`, `archive_interview_comparison`, `interview_comparison_datasets`; `analysis_store.py`: `analysis_run_members`, `list_comparisons`; `static/interview-comparison.js` | `tests/test_vault_coverage.py`, `tests/test_meeting_minutes.py`, `tests/test_interview_comparison.py` |


## 2026-11-02 Haas-jaのWindows／WSL実行

- 対象：`krokharu/transcription-finish-20261102`、基点 `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` 上の未コミット差分。開始時から多数の別作業差分があり、それらは保持。コミット・公開は未実行。
- 利用者の「Haasモデルを利用できるようにして」に対応。公式版がLinux＋CUDA専用のため、WindowsからWSL2 Ubuntu 24.04へASRとNemotronの実行を渡す。GGUF等の変換版へは切り替えていない。
- `services/transcription/haas_stack.py`、`wsl_stack.py`、`scripts/wsl_stack_worker.py` がWindows／Linuxのパス変換と実行を担当。共通の `qwen_stack.run_worker` にコマンド・中止フック、話者割当へ実行関数の差し替えを追加。Linuxのプロセスグループを中止し、起動直後の中止もマーカーで伝える。別worktreeの準備マーカーは無効とする。
- 導入は `scripts/setup_haas_ja.bat`／`.ps1`／`.sh`。公式Haas-ASR `acc614f68769dcbfae9dba96b48439c4a66295af` とそのuv.lockを使用。専用環境はLinux利用者領域のworkspaceハッシュ別ディレクトリ。HaasとNemotronは専用のtorch／transformersを共用して別プロセスで順に実行し、WindowsのWhisperX環境は変更しない。準備情報はGit対象外 `.venv-haas/wsl-runtime.json` に保存。
- UIでHaas選択時にGPUと日本語を選び、CPUを無効化。サーバーもHaas＋CPUを受付時に拒否する。READMEと画面の導入案内を更新。
- 導入途中でCドライブの空き容量不足によりWSLがI/Oエラーとなった。利用者はCの空きを確保して継続する方針を選択。Ubuntuの再起動、今回追加した重複のNemotron/CUDA環境と再取得可能なインストールキャッシュの整理後に復旧し、Cの空き容量回復を確認して続行。WSLへbuild-essential、python3-dev、ffmpegを導入した。
- 検証：Windows Python 3.12.9、WSL Ubuntu 24.04／Python 3.12.3、RTX 5070 12GB。公式lockのtorch 2.14.0+cu130とtransformers 5.20.2で公式Haas／Nemotronの取得・GPU実推論に成功。Microsoft Harukaによる約15.42秒の合成日本語音声から日本語本文と `SPEAKER_00` を取得。入力・成果物は主作業フォルダーのGit対象外 `scratch/haas-validation`。利用者の音声・DB・Vaultは試験入力にしていない。
- 自動試験：開発資料ブランチ `tests/test_haas_stack.py` 6件成功（workspace混同防止、不正設定、CPU拒否、中止フック、日本語／空白パスの実WSL往復、実WSLプロセスグループの終了）。`tests/dom/haas.test.cjs` 2件成功（GPU／日本語選択、WhisperXへ戻した際のCPU再選択）。主作業フォルダーを `PYTHONPATH` と `GURUMOJI_HAAS_SOURCE_ROOT` に明示して実行。
- 追加確認：JavaScript構文、bash構文、`git -c core.whitespace=cr-at-eol diff --check` 成功。処理中ジョブがないことを確認して起動中アプリを再起動。実アプリの `/` は200でHaas選択肢とWSL案内あり、`/api/config` のHaas blockersは空、CUDA利用可能。
- 未実行・制約：全体回帰試験、実利用者音声での品質評価、多人数／長時間の精度評価、Linuxネイティブ新規導入、別GPU、実ブラウザーのフォーム送信は未実行。話者割当の時刻は既存の無音分割による概算であり、Haasの認識精度や研究上の品質承認を本検証で保証しない。
