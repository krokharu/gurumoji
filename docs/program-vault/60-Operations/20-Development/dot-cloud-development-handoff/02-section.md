---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-02
title: dot クラウド開発とローカルへの引継ぎ：確認できたこと
summary: 確認できたこと。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 24
- 66
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：確認できたこと

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 確認できたこと

初期構築版 `5af286d` とルール初版を対象にした記録。後続のアプリ修正の合格判定には流用しない。

- 環境の主要モジュール import と `pip check` は成功。構築時の関連テストは 92 件成功
- `scripts/smoke_cloud_cpu.py` の `main()` は hash 検証済み Whisper tiny と匿名合成音声を CPU で認識。根拠は `../artifacts/whisper-cpu-smoke.json`。話者分離や UI のジョブ実行を通した検証ではない
- 同一セッション内の Web 応答は確認済み。利用者のブラウザーからの到達性とは別に扱う
- 移入 Vault の 1,398 ファイルは manifest の SHA-256 と一致。比較ツールは元の版との比較で `NO_CHANGES`。ツールの検証とノートの内容検証を区別する
- ルールの相対リンク、コマンド例、専用スキルの形式を確認。詳細は `../artifacts/rule-validation.json`

関連テストは `tests/test_application_lifecycle.py`、`test_machine_profile.py`、`test_backend_safety.py`、Vault 関連では `test_four_vaults.py`、`test_vault_note_policy.py`、`test_update_program_vault.py`、`test_data_backup.py`。実データを使わず、変更対象に合ったテストを再実行する。

## 2026-10-02: 6件の修正と最終対象の検証

修正 commit は `1cbe1561454403618f39aaa2b786dfb61b90b799`。ソース11ファイル・テスト5ファイルの計16ファイルを対象にした。独立検証の `../artifacts/integration-review/release-tested-tree.json` はコミット前の HEAD を記録しているが、記載された16ファイルの SHA-256 とこの commit の Git blob はすべて一致することを確認した。

| 修正 | 主な実装・確認範囲 |
| --- | --- |
| trash 処理失敗時の録音保護 | `src/gurumoji/services/library_trash.py` の `finish`・`recover_pending`・`purge_expired`。不明な asset kind、破損した manifest、未完了処理で原音声を失わず安全停止する境界も確認 |
| JSON の往復でプロフィール・議事録・session を保持 | `services/output_import.py` の `make_output_import`、`services/outputs.py`、編集・ジョブ出力経路（いずれも `src/gurumoji/` 配下） |
| 不正 JSON で起動を妨げない | 取込時の形状・型を検証し、壊れた入力を拒否して起動を継続。配列の language／不正 source を含む境界を確認 |
| 話者の短文平滑化の連続性 | `services/transcription/segments.py` の `make_display_segments` と単語単位の話者分割 |
| 話者 ID による集計 | `services/group_analysis.py` の `_tally_speaker_turn`・`group_analysis_for_row` |
| 欠測の表示・CSV・統計 | `research_analysis.py`、`services/group_analysis_exports.py`、`static/app.js`。欠測と真の0秒を区別し、中央値・最長表示と4種CSVの空欄／`valid_time`を確認 |

### 検証の対象版を分ける

- **最終16ファイル:** 対象・隣接テスト243件が成功（失敗0、エラー0、スキップ0）。`release-focused-tests.log` / `release-focused-results.json` が根拠。Node構文、`pip check`、CRLF対応の差分検査も成功し、`release-static-checks.log` に記録した
- **追加境界修正前の全体実行:** 849項目を収集し、pytestの表示は `827 passed / 16 failed / 10 skipped / 388 subtests passed`。subtestを含む表示をそのまま記録し、件数を単純合計しない。対象版は `broad-tested-tree.json`、結果は `pytest-final-tests.log` / `pytest-final-results.xml`
- 全体実行の16失敗は Chromium の `socket() failed: Operation not permitted` によるブラウザーテストの制限。10スキップは Windows PowerShell/Git 専用。最終の trash schema と欠測 UI/CSV の追加差分後は243件で再確認しており、**最終 commit で全体試験を再実行したとは扱わない**

上記の根拠ファイルは `../artifacts/integration-review/` 配下。関連する新規・変更テストは `tests/test_data_integrity_recovery.py`、`test_backend_safety.py`、`test_pipeline_regressions.py`、`test_analysis.py`、`test_research_analysis.py`。再現runnerは同成果物フォルダーの `run_isolated_tests.py`、対象モジュールと実行条件は `SUMMARY.md` と各ログを参照する。

### 検証用の追加依存

検証のために追加したトップレベル依存は `pytest==9.1.1`、`google-api-python-client==2.201.0`、`google-auth-oauthlib==1.5.0`。推移依存を含む18パッケージの版は `../artifacts/integration-review/test-dependencies.txt`、導入ログは `pytest-install.log` と `kcc-test-dependencies-install.log` に分けて記録した。本番用 `config/requirements-cloud-cpu.lock.txt` は変更していない。これらをアプリ実行に必須の依存として自動追加しない。

### 6件修正時点の問題と、その後の状態

- 6件修正の検証時点では、Vault の同秒再保存による台帳欠損が未修正だった。`test_vault_coverage.LegacyRunVaultTests.test_resaving_a_run_from_before_the_four_vaults_mirrors_it` は元版 `4b311df` でも再現し、同秒に固定すると元版・当時の版とも失敗した。既存ノートの bytes が同じ場合に `write_generated_note` が unchanged を返し、台帳を作らないまま `VaultRegistry._write` が `KeyError` になる経路。**後述の `59ebd24` で同一bytes時の台帳確定を修正し、固定時刻33件で確認済み**。過去の再現証拠は `baseline-vault-fixed-tests.log` / `current-vault-fixed-tests.log` に保持する
- テストは匿名・一時データを使い、実メディアや移入 Vault を fixture にしていない。外部 AI、OAuth、gated モデルや実録音の一連推論は未検証
- `1cbe156` のクラウド再起動は完了し、その後の欠測時間補正 `c85202b` でも再起動とHTTP6経路の200応答を確認した。ライブラリ0件、認証情報未設定、remote無効、監視対象はruntime側のみ、移入1,398ファイルのhash一致を維持。根拠は `../artifacts/restart-verification-c85202b.json` と `deployment-status.json` の版付き記録。これを後続版の再起動・実画面評価の合格へ流用しない
