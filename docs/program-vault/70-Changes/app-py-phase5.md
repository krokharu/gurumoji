---
note_id: change-app-py-phase5
note_type: change-record
title: app.py 分割 Phase 5（手順0〜11）
summary: app.py を 8,361 行から約 1,900 行の組み立て役に縮め、ルート・処理・実行時状態を web/・handlers/・services/ へ移した変更の記録。HTTP・DB・Vault の契約は変えていない。
status: current
verified: 2026-09-25
updated: 2026-09-25
feature: architecture
data: 70-Changes/app-py-phase5.data.json
tags:
  - gurumoji/program
  - gurumoji/architecture
  - gurumoji/change
---

# app.py 分割 Phase 5（手順0〜11）

[[40-Design/core-handler-routing-reorganization-plan|コア・ハンドラー・ルーティング再編案]] の Phase 0〜4 の続きとして、`src/gurumoji/app.py` に残っていた処理を機能ごとに移した。機械可読のデータ（旧シンボルの移動先、新モジュールの責務、検証結果）は同じフォルダーの `app-py-phase5.data.json` にある。

- 基準：コミット `594b7a0`（分割前）→ ブランチ `claude/program-evaluation-8l5p0t`
- `app.py`：8,361 行 → 1,895 行
- テスト：580 件中、失敗 0、スキップ 11（Windows PowerShell が必要なもの 10、ffprobe がないもの 1）。Linux・Python 3.11・Chromium と ffmpeg あり・重い機械学習パッケージなしの環境で確認した。

## 変えていないもの

- HTTP の URL・method・endpoint 名。`tests/fixtures/route_map.json` と機械比較する。
- DB の構造、保存形式、stable ID、Vault の配置と所有権のルール。
- ロックの取得順、書き込みの確定順、起動時の回復処理。
- テスト・スクリプト・Colab ノートブックが `app.<名前>` で参照する名前（`gurumoji.app` から引き続き import できる）。

## 新しい配置

| 場所 | 役割 |
| --- | --- |
| `app.py` | 組み立て役。設定とパス、実行時状態の別名、依存の配線、`create_app()`、`main()` |
| `runtime_state.py` | `RuntimeState`：実行中のジョブ、共有ロック、分析の取消イベント |
| `diagnostics.py` | リモート表示時にローカルパスを含む診断を隠す |
| `web/security.py` | 全リクエスト共通の安全対策（Host、リモート認証、CSRF、サイズ上限、応答ヘッダー） |
| `web/*_routes.py`、`web/library_deletion.py` | HTTP の入口（ライブラリ、エクスポート、分析表示、学習データ、AI設定、削除） |
| `handlers/transcription_start.py`、`handlers/speaker_identification.py`、`handlers/segment_classification.py`、`handlers/form_fields.py` | Flask に依存しない操作単位の処理 |
| `services/library_*.py`、`services/output_import.py`、`services/media_files.py` | ライブラリの DB・編集・既存出力の取り込み・メディア |
| `services/analysis_jobs.py`、`services/analysis_archive.py`、`services/analysis_annotations.py`、`services/analysis_pipeline_adapters.py` | AI見解と Transformer のジョブ、固定保存、分析設定の保存、段階分析の接続 |
| `services/ai/settings.py`、`services/speaker_identification.py` | AI の設定・接続先、話者名の推定と台帳への連携 |
| `services/transcription/{options,job_record,diarization,vocabulary}.py` | 文字起こしのオプション、ジョブ記録、話者分離の準備、登録語 |
| `services/machine_profile.py`、`services/instance_lock.py`、`services/subprocesses.py`、`services/word_cloud.py` | PC診断、二重起動の防止、取消可能な外部コマンド、ワードクラウド |

`app.py` に残したもの：依存を渡す組み立て関数（`analysis_commands` など）、AI 仕上げの接続関数、`run_transcription_job`（実行時に依存一式をワーカーへ渡す入口）、Vault 公開の入口、アップロードの上限付き読み込み。

## 移し方の決まり

1. **遅延束縛で依存を渡す。** 移動先は `app.py` を import しない。`app.py` が `lambda *args, **kwargs: 関数(*args, **kwargs)` の形で依存を渡し、呼び出し時に `app` の名前を引く。これにより、テストが `patch.object(app, "名前")` で差し替えた関数が移動後のコードにも届く。
2. **設定値は提供関数で渡す。** `MEDIA_DIRECTORY` などのパスや上限値は `lambda: MEDIA_DIRECTORY` として渡し、差し替えた値を毎回読む。
3. **endpoint 名を保つ。** 安全対策の hook が `create_job` と `import_speaker_registry` の endpoint 名で上限を切り替えるため、ルートは同じ endpoint 名で登録する。
4. **状態の持ち主は一つ。** ジョブとロックは `RuntimeState` が持ち、`app.jobs` などは同じオブジェクトの別名。`_job_admission_id` はテストが再代入するため `app.py` のモジュール変数のまま残した。

## 検証の仕組み（`tests/test_routing_architecture.py`）

| テスト | 守るもの |
| --- | --- |
| `test_route_map_matches_the_committed_snapshot` | URL・method・endpoint の一致 |
| `test_handlers_and_routes_never_import_the_composition_module` | どのモジュールも `gurumoji.app` を import しない |
| `test_adapters_receive_names_that_tests_patch_on_app` | テストが `app` 上で差し替える名前を `web/`・`handlers/` が直接 import しない |
| `test_create_app_builds_independent_apps_without_touching_data` | `create_app()` がデータに触れず、独立したアプリを返す |

安全対策の移動（手順8）は、18 通りのリクエスト（Host 不正、CSRF、Origin・Referer、リモート認証、サイズ上限など）で移動前後の status とセキュリティヘッダーが一致することも確認した。

## 手順ごとの内容

| 手順 | 内容 |
| --- | --- |
| 0 | 失敗していたテスト5件の修正（期待値の更新漏れ1、DB未初期化2、OS依存2。Windows 専用パス判定は OS に依存しない実装に変更）、ルート一覧の比較テスト、テスト用 DB ヘルパー（`tests/support.py`） |
| 1〜3 | 状態を持たない関数、ルートだけの機能、PC診断 |
| 4〜6 | AI 設定（重複していた応答解析を `services/ai/client.py` に一本化）、話者の特定、分析ジョブと固定保存 |
| 7〜10 | ライブラリ DB、安全対策、文字起こしの開始、編集保存・削除・分析設定の保存 |
| 11 | `RuntimeState`、`InstanceLock`、`JobRecord` の分離、`create_app()`、不要 import の整理 |

削除したもの：呼び出し元のなかった `normalize_outline_sections`、`services/ai/client.py` と重複していた応答解析 5 関数。

## 以後の変更で注意すること

- 新しいモジュールから `gurumoji.app` を import しない。必要な関数は `app.py` から渡す。
- テストで `app.<名前>` を差し替える関数を新しいモジュールで使うときは、import せずに引数で受け取る（上記テストが検出する）。
- ルートを追加・変更したら `tests/fixtures/route_map.json` を意図した変更として更新する。

関連：[[20-Modules/module-map]]、[[10-Architecture/system-map]]、[[40-Design/core-handler-routing-reorganization-plan]]。
