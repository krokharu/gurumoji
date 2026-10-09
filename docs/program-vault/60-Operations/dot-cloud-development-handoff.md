---
note_id: ops-dot-cloud-development-handoff
note_type: runbook
title: dot クラウド開発とローカルへの引継ぎ
summary: dot を優先して基本作業を進め、設計判断・変更背景・検証・未解決事項をローカル開発へ引き継ぐためのプロジェクト記録。
status: current
verified: 2026-10-02
updated: 2026-10-09
feature: development-workflow
tags:
  - gurumoji/program
  - gurumoji/operations
---

# dot クラウド開発とローカルへの引継ぎ

## 2026-10-09: 実多会話接続とCPU残件の最新受入

公開選別sourceは`3bb09c2ce0b80ee7b6f52d1a39d7f3dfcc662533`。C0が固定backend4f4／UI211／別作者test80の10pathをbytesで選別し、旧mock実Registry修正3pathと純粋kernel import分離2pathを保持した。閉じたunit_poolの2〜16 source POST、実group HumanRecord、Handler保存／fresh、元発話・入力版・現在権限と元分母／現在除外を接続。GETはreadonly、同名定義や単一会話HCを互換としない。保存v3は全unit_contractと全receipt値を保ち、重複parentsだけを閉じたhash参照にする。

別作者の最終境界8件、有効な47発話のSAVE上限拒否1件、receipt実値改変拒否1件、同固定版の1440通常画面→実API→Handler→group HC→sum6／mean2／分母3→save／freshが成功、open製品指摘0。16source・5変数・21発話の正常保存は122014bytesで131072上限内。390正常画面とprimaryなし無効化は前723版で成功、UI2 blobは最終版と一致する。初期失敗、作者capacity停止と同modelのreadonly回復、未確認の旧試験を分けて保持する。固定SHA・コマンド・対象別検証は[公開引継ぎ正本](../../GIT_HANDOFF.md)とmanifestを参照。

Dotの[#27 Linux受領](https://github.com/krokharu/gurumoji/issues/27#issuecomment-6073765543)は旧bc0の109照合とhelper14成功、純kernel4はFlask未導入でloader BLOCKED。後続[#28](https://github.com/krokharu/gurumoji/issues/28#issuecomment-6074192102)はクラウド環境利用不可・編集0で、C0が2testpathのownerをWindowsへ移管して完成・独立受入した。Linuxでの新固定版試験は未実行であり、環境復旧後もC0が固定SHAと専用scopeを渡すまでDotが同じ2pathを再編集しない。Lunaは受入済み公開版の通常push／readback／通知、C0は割当・共有index・技術受入を所有する。

私有checkpointと延期PNGは別branchでローカル保持、Downloads原本・私有履歴・実DB／Vault／資格情報は共有しない。Node24.21による今回検証は通常PATHの変更ではない。PNG Store／Web／Vault延期、Gemma323 HOLD、G0.5b/c未実測／currentPack暫定、G5残14と意味品質未評価を維持。実データ・モデル・利用者稼働サービス・full scheduler／全初期pipeline・AT・全suiteは未実行で、下記の以前の区切りを現在の未実装判定に流用しない。

## 作業と記録の分担

基本的な調査、整理、編集、実行、検証、進捗確認は利用可能な dot の機能を優先する。ローカル PC でも開発を再開できるよう、意味のある節目で Software Vault の関連ノートへ、設計判断と理由、変更背景、テスト結果と未実行範囲、未解決事項、次の作業、対象 commit と根拠を残す（利用者の方針、2026-10-02）。

全 Vault の事前読み込みや作業ログの逐次複製は不要。既存ノートを対象に絞って更新し、詳細ログ・大きい成果物は参照先を示す。研究者の本文・タグ・別名は所有者のものとして保護し、開発記録のために置換しない。登録規約は [[40-Design/program-vault-rules]]、作業の入口はリポジトリ直下の `AGENTS.md`。

## 初期クラウド配置の根拠

- アプリの移入元: `4b311df51c7fe2938f1761cb1efbb4cc4906fd10`
- CPU 環境と音声 smoke: `5af286d738731a337466e3fb155b3e6f622fd0e7`
- dot 向けルール初版: `36d8895bff0fc53db7ed5e79923de4d003949c44`。以後の方針更新は `AGENTS.md`、`.agents/rules/dot-cloud.md` と本ノートの Git 履歴で追跡する
- 移入 Vault の不変な共通基点: `045d51340b989d934b730b639d45312556596e84` / `gurumoji-vault-base-v1`
- 別 Vault repo の安全な取得・比較ツール: `bd947a4f7e92125cc94fdebcf9518cd7385e43ce`、運用手順は同 repo の `SYNC_OPERATIONS.md`

クラウドでは `projects/gurumoji/app`、`runtime`、`vaults`、`artifacts` を分離する。`scripts/run_cloud.sh` は既存の `MOJIOKOSI_DATA_DIR`・`MOJIOKOSI_OUTPUT_DIR`・`MOJIOKOSI_BACKUP_DIR` を使い、アップロードは `app/runtime/uploads` に残す。`src/gurumoji/app.py` の `DATA_DIRECTORY`・`DEFAULT_OUTPUT_DIRECTORY`・`BACKUP_DIRECTORY` が対応する。symlink で安全なパス検証を回避しない。

Python は Linux の `.venv/bin/python`、初期版は 3.12.14。CPU の依存関係は `config/constraints-cloud-cpu.txt` と `config/requirements-cloud-cpu.lock.txt`、実行手順は `.agents/rules/dot-cloud.md` を参照する。Windows の仮想環境・資格情報を流用せず、ローカル手順は `.agents/rules/windows-local.md` に分けた。

5つの移入 Vault（Research、Input、Visualization、Orchestrator、Persona）は別 Git の `vaults/` 配下に保持し、実行時 Vault の監視先へ接続しない。Software Vault はアプリの `docs/program-vault`。ノートの snapshot は DB・メディア・分析成果物の復元ではない。

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

## 2026-10-02: 25指摘の改善と独立受入

改善実装は `59ebd24f88a86415c3cb122c11ece9b03c9111fc` に確定した。UI-01〜10、分析A01〜14、同秒Vault台帳復旧V01の25指摘を対象にした40ファイルについて、検証前後のhash差分は0。コミット前snapshotを記録した `../artifacts/all-improvements-review/final-after-tests.json` の40ファイルと、この commit の Git blob の SHA-256 も一致する。

### 実装と互換性の要点

- UI: キーボード編集、開始条件と外部送信先の明示、削除取消と失敗表示、手動設定保護、CSVの非保存preview、競合時の未保存draft書き出し、環境別の保存先表示、保存フィードバックを改善。旧CSV APIの即保存互換を保ち、画面側はpreview→未保存編集→通常保存に分けた
- 分析: 全件エクスポートと制限理由、明示された参加者役割・参加人数と観測人数の区別、時系列に基づく重なり・無音、完全一致の語集計、DF分母、時間bin配分、極小p値の保持を修正。`participant_count` は実参加人数（不明はnull）、観測人数は `observed_participant_count` 等として区別するため、従来の0/1補完を期待する外部consumerは確認が必要
- 来歴・Transformer: 設定依存fingerprint、stale表示、出力元revision/hash、計測したtoken切詰め、モデルrevision固定、固定テーマ数の成立条件を改善。古い結果は保持し、不明な来歴を現在のhashで補わない。条件変更で再計算が必要になる場合がある
- Vault: `src/gurumoji/vault_registry.py` の `_write` で、同一bytesのノートでも台帳の確定を回復する。不要なノート再書き込み・履歴追加を避け、編集版の履歴保存と削除保護を維持する。台帳消失時の履歴pointer・entity設定・削除知識の一般的な復元まで保証する修正ではない

### 検証結果と未完了の区別

- 独立受入17件、Node合成DOM／関数契約11件、固定時刻Vault検証33件は成功。Vault検証は広範囲回帰にも含まれるので件数を重複加算しない
- 広範囲回帰は **900項目収集、browser名の24項目を除外、876項目選択**。pytest表示は **864 passed / 2 failed / 10 skipped / 24 deselected / 424 subtests passed**。failed2件は旧ブラウザーテストの起動引数を安全ガードが拒否した実行ブロックであり、計算・API・保存のassert失敗ではない。元のfailed表記をpassへ読み替えず、全体を「全成功」と呼ばない
- 10件のskip理由はWindows専用等としてログに保持。安全ガード導入前に中断したブラウザーを含む実行は未完了であり、合格件数へ加算しない。安全制限を緩めて再試行しない
- Python変更28ファイルのcompile、JavaScript変更4ファイルの構文、CRLF対応差分検査、`pip check` は成功
- 受入表は **15 addressed / 10 partial / 0 open**。全25指摘の改善実装は存在するが、UI10件は修正版の実Windowsブラウザー受入待ち。Node合成DOMやAPIの成功は、実画面、実端末のObsidian起動、スクリーンリーダー音声の合格を意味しない

根拠は `../artifacts/all-improvements-review/` の `SUMMARY-ja.md`、`acceptance-matrix.json`、`final-independent-results.json`、`final-node-tests.log`、`vault-independent-tests.log`、`pytest-nonbrowser-tests.log`、`pytest-nonbrowser-results.xml`、`final-static-checks.log`、`final-verification-metadata.json`。これらはローカル検証成果物であり、公開Gitへ生ログを一括追加しない。コード側の再現対象は `tests/test_analysis_metrics_regressions.py`、`test_transformer_provenance.py`、`test_four_vaults.py`、`test_vault_coverage.py`、UIは `test_ui_safety_browser.py`、`test_transformer_content_browser.py` と `tests/ui/` を参照する。

実データ、外部AI、追加モデル取得、認証を試験には使っていない。実E5の精度・クラスタ安定性、日本語の否定等の正解集合評価、AI主張の意味的な裏付け、発話単位の非独立性や多重比較の妥当性は別の検証課題として残る。

### 配置・受け渡しの状態

- **`59ebd24` のクラウド再起動は 2026-10-02 15:58:40 UTC に確認済み**。HTTP6経路が200、設定APIはcloud/Linux、HTMLはクラウド実行環境を表示する。tinyはキャッシュ済み、baseは未取得、Qwenは未準備、Hugging Face認可は未検証。ライブラリ0件、認証情報未設定、公開無効、runtime側のみのVault監視と移入1,398ファイルのhash一致を維持。根拠は `../artifacts/restart-verification-59ebd24.json`。実ブラウザーの描画・操作評価は別途ブロック中で、HTML取得を実画面の合格とはしない
- 長文パッチ経路とWindowsでのファイル転送は、内容の省略および拡張属性処理（`os.setxattr` 未対応）により完了していない。欠けたパッチを適用済みと扱わず、元のローカルcheckoutを保護した
- 受け渡しは **公開アプリrepoの別ブランチへpushし、ローカルでfetch・差分レビューする方法**が承認済み。現接続は対象repoの読取権限のみでpush権限がなく、書込み権限を持つ接続への切替待ち。GitHubへのpushとローカル反映は未完了で、この記録更新自体はpushを行わない
- 公開先の対象はアプリコードとSoftware Vaultの技術・設計記録。5つの研究用移入Vaultは専用remoteを持たない別Gitとして維持し、公開GitHubへ送らない。研究本文、会話データ、資格情報、実runtime、個人の非公開記録は公開用の変更へ含めない

## 2026-10-02 UI設計知識の文書統合

対象ソースは `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`（直近実装 `59ebd24`）。設計資料v0.3を取り込み、短いroot `DESIGN.md`、条件付きで資料を読む `gurumoji-ui-design` skill、既存UI criticへの参照、Software Vaultの設計契約・知識索引・実装計画・受入資料を整えた。新しい設計提案は未実装・未受入。skillはプロジェクト内の再利用文書で、自動発見・常駐登録・モデル重み学習を完了したという意味ではない。

- 入口は [[40-Design/ui-design-knowledge]]。全研究packの常時読込は求めず、局所修正は対象コードと契約の該当節だけで進める
- [[20-Modules/ui-screens]] の上部3タブ／永続pipeline未実装という古い記述を、現行4入口とM0〜M7にコード照合して更新した。実画面・AT受入日には読み替えない
- 文献・出典台帳・監査・合成probe・静止案を日付付きで保存。v1仕様8図、v2比較8図＋補助2図、初回／修正後レビューを別の利用者実験数へ合算しない。builder、描画ログ、browser profile、私有の研究資料は取り込んでいない
- 対象ファイルとhashは [統合manifest](../50-Tests/ui-design-evidence/2026-10-02/integration-manifest.json)、文書・source保全の確認は [統合検証](../50-Tests/ui-design-evidence/2026-10-02/integration-validation.json)。アプリのUI受入・モデル品質・利用者評価をこの検証で合格にしない
- この区切りはapp内文書の未コミット差分。source／runtime／tests／依存定義／私有5 Vaultの変更、commit、push、PC反映は実施していない。別checkoutのSoftware Vault更新は既存のcheck→対象確認→apply手順を維持する

## 2026-10-02 UI設計知識v0.4の限定追記

v0.3文書はlocal commit `88f5e3eea245166ee68ed4dc6c3f99c31e149228`へ収録済み。v0.4は4つの作業用設計文書を更新し、[[40-Design/ui-microcopy-state-catalog]]と追加の合成契約確認を参照できるようにした。source基準は引き続き`ddc23abe`／直近実装`59ebd24`で、文書commitをruntime修正と扱わない。旧v0.3レビュー・manifest・検証は日付と版を付けて保存し、旧DG14項目は書き換えていない。

- API enum／台帳の3targetと、非空指定でResearchを含む4書出し経路を試みる現行処理を区別。subsetと台帳の不一致、Research conflictでもcompletedになり得る合成確認をW03へ集約した。文言だけで解消済みにせず、scope／outcome契約の改修は未実装
- 保存履歴にある全保存bundleの再試行と、新しいpipeline action／Research-only等の部分再試行を分けた。AI見解の送信説明は役割、コード、重要flag、条件付きexpert情報を含む実call内容に対応付ける
- v0.4の差分は未コミットで独立deltaレビュー待ち。アプリsource・tests・依存定義・runtime・私有5 Vaultの変更、UI修正、外部AI送信、pushは実施していない。検証の詳細は[統合検証](../50-Tests/ui-design-evidence/2026-10-02/integration-validation.json)を参照

## 2026-10-03〜04: 復旧と専用ブランチの改善

現在の作業は[[gurumoji-improvement-session]]、再利用する分担は[[gurumoji-department-briefs]]を参照。旧環境で失われた未公開sourceを復元したと扱わず、ddc23abeと検証済み設計資料から新しく修正している。

Backend区切り9768b80は定義固定/CAS、測定型・欠測、4writerの公開試行台帳、世代/再起動、入力stamp競合を含む。非browser回帰926成功・10skip・24deselect、独立48件と1120定義matrixで受入。UI・実browser・実モデル・実Vault・旧binaryへのdowngradeは別の確認範囲。別途承認された実runtime利用の前には旧workerを停止/drainし、旧成果を保存する。完全履歴のsource bundleを区切りごとに保管し、元PCや公開remoteへの自動反映は行っていない。

## 2026-10-03 固定run viewerの区切り

対象sourceは`ce6e003`（実装`f31da55`、可読要約・CSV/公開証拠補正`5ac07ec`）。既存run/artifactをread-onlyで開き、最新100件外もrun IDで参照する。保存した手法要約・状態・制約・採用定義ID/版・有限表を表示し、JSON/hash/catalogは詳細へ分けた。固定packageを現在データで埋めず、GET/exportで計算・回復・公開・DB更新をしない。公開の最新durable試行と古いpipeline台帳を別表示し、空scopeの同package照合も守る。判断はADR-122追記。

- `5ac07ec`を凍結したcanonical `PYTHONPATH=src:tests ../app/.venv/bin/python -m pytest tests/ -q`: 1012 passed、32 skipped、953 subtests、lokyのCPU数warning1。2026-10-03 23:45:37〜23:47:45 UTC、前後HEAD/clean状態/src+tests集合hashが一致。
- 後続`ce6e003`は空scope証拠guardと保存package入口の局所差分。対象27 tests/39 subtests、viewer合成35ケース、status合成32ケース成功。全体結果をこの後続差分の全体合格として流用しない。統合branchで最終回帰する。
- 実行中に編集が混在した先行全体runは探索用として明記し、固定commitのcanonical証拠から除外。証拠はappから`../artifacts/eight-hour-20261003/fixed-run-viewer/`。
- 実browser/keyboard/focus/ATと視覚的受入は未実施。禁じられたブラウザー起動/localhost迂回を試していない。実研究データ・Vault、外部AI/モデル取得、migration、push/deploy、認証/安全設定へ変更なし。

## 2026-10-04: 時間欠測・固定来歴・編集UIの受入

専用branchの固定source `721c308` で標準pytest **1049成功／32skip／1052 subtests成功／失敗0**、同HEADのオフラインDOM **161成功／失敗0**。browser22・Windows10は未実施。詳細、既知失敗の解消根拠、復元手順は[[gurumoji-improvement-session]]、再利用する4部門の依頼範囲は[[gurumoji-department-briefs]]へ集約する。

通常importの空JSON markerも既存の欠測意味へ合わせ、raw/Save/音声guardを保持した。世代保護の旧fixture競合は両adapter同期と確実な解放へ直し、production guardは不変更。961組合せ・旧版negativeと250反復の詳細はセッション記録へ分ける。

`focus-group-local-7`／registry11までの欠測・役割混在の意味、追加nullableとcoverage、保存計算版、表示専用時刻projection、固定packageの検証境界は[[30-Data/analysis-storage-v1]]の末尾を参照する。外部consumerはnull/空欄を勝手に0へ補完しない。旧v4〜v6の固定snapshotは元の値と版を保持し、現計算へ書き換えない。実runtimeへの適用、旧workerのdrain、データbackup・downgradeの確認は別であり、今回のソース検証やbundle受渡しで完了したと扱わない。

## 2026-10-04 分析オーケストレーター評価4件の修正

基点は `cc19a84f41592238beec8838134ad477d255131f`。完全履歴bundle v14から別checkout `analysis_orchestrator_fixes/app` と専用branch `dot/analysis-orchestrator-fixes-20261004` を作成し、8時間成果物・評価原本は変更していない。実装commitは `2379a450f473829a2d12122739fcb13521b9c672`。最終配布HEADは修正版ZIPの `manifest.json` とGit bundleの同名branchで確認する。

- **対象なしの誤完了:** preview・開始・既受付snapshotの実行で、除外後の発話集合を適用性判定と測定で統一。空入力／全件除外は保存前に拒否する。固定summary行だけでparticipationをcompletedと表示しない。部分除外と通常入力の完了は維持。
- **O01話者不足の見落とし:** `observed_speaker_count`を使い、UNKNOWNを識別済みラベル数へ加算しない。未知話者件数も非除外集合から取り、モデルが省略できない注意を付ける。ラベル数は人手確認済みの実人数と区別。旧summary-only入力では品質サマリーを保守的に利用する。
- **取消後readyが残る:** 一般失敗と取消を分け、既存の合法遷移に従ってworker終了後に現世代を終端化する。終了pipelineにactive stepを残さず、retry可能にする。確定済みstep・artifactは保持し、旧世代・旧attemptの更新は禁止したまま。
- **公開確定と取消の競合:** 追加の副作用を止めるguardと、既に確定した公開結果の読取照合を分離。公開台帳のpublished/conflict/failedを保持し、未確認はunknownにする。取消は公開済みファイルの巻戻しではない。再試行の成功再利用はStore内で固定package検証、scope/hash、世代guard、最新公開attemptの全先成功を確認してから行う。pipelineに限る明示opt-inであり、直接再公開の挙動は変更しない。

### 最終コードの検証

- 対象・隣接Python **126件成功**。新規回帰25件（orchestrator14、advisor11）を含む。元の適用性、定義固定、世代競合、保存直前取消、部分公開失敗、fixed-run、研究protocol、外部送信境界を再確認。
- Node UI回帰 **155件成功**（ownership40、status32、measurement37、fixed-run46）。これは実ブラウザー操作ではない。
- 全体pytest: **1072 passed / 2 failed / 32 skipped / 1073 subtests passed**。subtestは重複を含む別表示のため合算しない。残る2件は `test_transformer_provenance.TransformerTruncationTests` のtorch未導入によるimport失敗で、基点cc19a84でも同じ失敗を再現。32スキップは実ブラウザー22、Windows専用10。全体成功とは扱わない。
- 独立レビュー: F1〜F4と除外UNKNOWN回帰を確認。中間案で見つかった公開済み再利用時のpackage検証回避・新しい公開失敗の見落としは最終版で解消。実並列取消、二重writer防止、manifest欠落／破損、最新台帳、旧世代guardを別担当が再確認し、修正阻止欠陥なし。
- `git diff --check`、対象Python構文確認、`.venv/bin/python -m pip check`成功。検証用venvにFlask/pytest/Google APIテスト依存等を追加したが、本番依存lockは変更していない。追加依存の版は成果物 `verification/test-environment-final-freeze.txt` に記録。

再現コマンド（`app`で実行）:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest test_analysis_orchestrator_regressions test_analysis_plan_advisor test_analysis_milestones test_analysis_definition_safety test_analysis_generation_safety test_analysis_eligibility test_analysis_core_contracts test_analysis_publication_safety test_analysis_snapshot_commit test_analysis_fixed_run test_analysis_recovery test_analysis_research_protocol test_analysis_llm_contracts -v
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src:tests .venv/bin/python -m pytest tests -q --junitxml=../artifacts/full-final-tests.xml
```

証跡は修正版ZIPの `verification/`（`adjacent-final-tests.log`、`full-final-tests.log/xml`、`node-ui-tests.log`、`baseline-environment-check.log`、`independent-review/`）へ同梱。合成・一時データのみを使った。実データ、移入Vault、認証、外部AI、実モデル推論、実ブラウザー、Windows、push/deployは未実行。一般的な自律手法選択は追加しておらず、O01は既存2手法の確認優先順の助言という範囲を維持した。

## 未確認・次の引継ぎ

- gated 話者分離、外部 AI、利用者ブラウザーでの一連操作は初期 CPU smoke の対象外。認証・モデル・到達性を別に確認する
- ローカルとクラウドの同期は自動化しない。共通基点から両側の差分を読み、人が採用する内容を判断する。初期タグは保持し、新しい共通基点は双方の受理後に版付きタグで決める
- PC 原本への変更適用、実データの移行、アプリと移入 Vault の接続は別の作業。承認済みの対象だけを扱う
- アプリ修正・設計変更・追加検証がまとまったら、このノートか該当する既存ノートへ対象 commit、結果、残る問題を追記する。未実行や失敗を成功として記録しない


## 2026-10-04: Core・Handler自律分析と低トークン実行UI

実装commitは `91d827141628dec84f8e1d32301b49f901074584`、基点は `0d9239ac9d041d78d298c68a235738b3fe549a2a`、ブランチは `dot/core-handler-orchestration-20261004`。原本とは別checkoutで実装し、元checkoutのHEAD・未コミット変更なしを確認した。Windows原本、移入研究Vault、main、外部remoteへ反映していない。

### 実装と判断

- [[20-Modules/analysis-orchestration]] に責務・API・追加SQLite形式・停止/復旧・適用範囲を記録
- Coreは問い/見解/不足/次の分析/終了を判断。Handlerだけが正式タスクを登録・発注・保存し、4専門系統へ配分する。数量・統計とHandlerはコード処理として表示する
- 初期全量は入力/設定/テンプレート版で再利用し、全結果・原結果hash・根拠参照・ラベル版を保持。主張変更と終了前の独立検証/批判、Core採否理由、重複抑止を実装した
- 原文を伏せるのではなく期待結論を伏せるblind-firstを維持。保存済みの独立検証結果を説明する対話は当該結果・根拠・説明質問に限定する
- `label_frequency` はrun内の採用ラベル版から対象数/分母/欠測付きで実再集計する。既存参加量/時系列は初期全範囲の参照を維持する。原本ラベルは変更しない
- 時間/回数/重要度/AIお任せと手動停止、プロセス中断、曖昧な外部実行の明示放棄を扱う。期限/取消し後の応答は保存して隔離し、結果不明の呼出しを自動再送しない
- 表示のアニメーションはstatus/event/CSSのみ。再表示・pollingでAI呼出しを追加しない。実測tokenだけを表示し、unknownを0で補完しない
- Obsidian用MarkdownとJSONは全量台帳のダウンロード。研究者所有Vaultへの新しい自動書込み経路を追加していない

### 最終検証

- 対象・境界・adapter・Flask統合の72件成功。ラベル版0集計→Core採用→版1実再計算→旧結果staleを実adapter経由で確認した
- 全JSDOM 172件成功（既存161＋新規11）。終了/復旧/表示再開、遅延応答のlatest-wins、個別確認付きabandon、外部同意、欠測表示、XSSを含む
- 全体pytestの実表示は **1144 passed / 2 failed / 32 skipped / 1085 subtests passed**。2失敗は `test_transformer_provenance.TransformerTruncationTests` のtorch importで、基点でも同じ2失敗を再現した。新機能のassert失敗ではないが、全成功とは呼ばない
- 32skipは実ブラウザー22、Windows専用10。JavaScript構文、Python compile、git diff check、pip check成功。最終全体試験開始から実装commitまでsource/test hashの差分は0
- dotのクラウドブラウザーによるlocalhost表示は `ERR_BLOCKED_BY_CLIENT`。制限を迂回せず実画面画像を未取得と記録。合成状態HTMLは実template/描画関数から生成した静的previewであり、実画面受入や実AI稼働の証拠ではない

証跡は配布source ZIPの `verification/` に収録する。主なファイルは `full-final-tests.log/.xml`、`focused-final-tests.log`、`orchestration-dom-regression.txt`、`baseline-environment-check.log`、`final-tested-tree.json`。UI previewは `ui/orchestration-ui-preview.html`。件数は重複を含むため足し合わせない。

### 未実行・制約と次の確認

実データ、実AI/モデル品質、課金、Windows実機UI、支援技術、Vault自動出版、push/deployは未実行。確認的統計の隔離検証データと金額上限は未対応で、要求を誤って成功扱いしない。運用上限は呼出し数/タスク数、重要度は未校正の仮基準。初期snapshot構築自体の中断は復旧確認で停止する。

ローカルへ採用するときは既存checkoutを保持し、bundleを新しいフォルダーへ復元、共通基点との三者差分を確認する。その後、既存モデル設定を用いた小さな承認済み会話で実動確認し、ブラウザーの表示/動き/キーボード操作を確認する。プログラムVaultと私有研究Vaultを混ぜない。


## 2026-10-04 追補: 初期構築の部分再開と自律runの安全出力

実装commit `0a5a0c4a5c0a0a1ec50e680d6d8aa655251c0dcc`。基点 `f3e16ba9e737bfb9ed29cfaaf11a4ebf57edf340` と旧ブランチ `dot/core-handler-orchestration-20261004` をそのまま残し、後継 `dot/core-handler-durable-output-20261004` に実装した。前節で未実装とした初期部分再開・明示選択Vault出力の2項目をこの版で追加した。

### 初期構築

runを先に永続化し、`base → linguistics → statistics → content → snapshot` の5段階を順番に実行する。各段階の入力hash・前段hash・版・出力hashと実行回数を保存する。完了後に別段階が故障した場合、完成済みの統計を含めた段階を再実行せず、未完了段階だけ再開する。未commit段階は再計算し得るが、完了済み段階を単にラベル付けし直す擬似再開ではない。

開始時row、保存済みAI/Transformer/classification入力、選択済みexpert定義/knowledgeを固定し、後段へ新しい情報を混ぜない。旧ready初期snapshotも再利用する。初期構築の初めから時計を固定し、期限超過後は進行中段階の出力を保持しても次段階/最終採用/Coreを始めない。再開で時計をresetしない。

### 固定成果物と選択公開

全量台帳を一度封印し、`AnalysisStore.save(publish=False)` で固定packageを作る。新runで4先一式を明示選択した場合だけ、既存のInput・Orchestrator・Visualization・Research writerへ渡す。既定OFF、個別選択なし、旧runのscope拡大なし。Researchには発話本文も保存する。原文版を確認して実際に分析した本文を引用へ投影し、全量raw/批判/採否/ラベル版をresult.jsonに残す。

保存・公開の試行、世代、封印hash、元会話の現存・版を専用guardで確認する。汎用publish/retryはこのkindに専用guardを要求し、generic refreshからの迂回を防ぐ。一部失敗/応答喪失/再起動からは同じpackage・scopeで保存/公開だけ再試行し、AI・統計・初期構築を再計算しない。入力変更後は成果物をstaleで保存できるがVault writerは止める。取消/停止/失敗runは自動公開しない。

生成ノートの編集履歴保存・利用者削除の維持を既存policyで保つ。writerの処理がpublishedでも、削除したノートまで復元する意味ではなく、全ノート存在の保証ではない。表示も分析終了・固定保存・4先処理を分離する。

### 検証と残る制約

- 対象128件、全JSDOM187件（既存161＋自律UI26）が成功。実際の5段階adapterで統計計算が再開前後に1回であること、旧snapshotとの完全値/hash一致（warm cache）を確認
- 4先は一時DB/一時Vaultで既存writerを動かした。部分失敗、同時retry、応答喪失、初期/出力改ざん、旧世代、生成ノート編集/削除の逆境試験を含む。実モデルはmockのみ
- 全体pytest **1200 passed / 2 failed / 32 skipped / 1099 subtests passed**。2失敗は前節と同じtorch未導入で、32skipも実ブラウザー22・Windows10。ソース/testは最終全体試験中のhash差分0。CRLF形式を維持し、CRLF対応diff・Python compile・JS syntax・pip checkも成功
- 手動停止後も初期段階やAI呼出しのrunning/cancel_requestedが残る間は読取pollingで完了/後着usageを確認し、新規実行をしない。復旧済みunknownを永遠にrunningとしてpollしない

証跡は更新source ZIPの `verification/`、静的合成previewは `ui/orchestration-ui-preview.html`。実画面画像はクラウドブラウザーの既知制約により未取得で、previewを実画面受入の証拠とはしない。

確認的統計/holdout、金額上限、汎用の数量専門LLM、自由コード/検索は引き続き制限する。実データ・実Vault・実AI・Windows反映・push・merge・deployは行っていない。旧Library版・旧HEADを保全し、受渡し時は新ZIP/bundleから全ソースhashとHEADを復元確認する。


## 2026-10-04 追補: 分析履歴ビューと設計記録後のPPTX

基点 `1dbd54710e281698fedcd19ab4db001c1db11aac` を維持し、専用 `dot/analysis-history-viewer-20261004` に追加。対象HEADと全ソースhashは配布manifestを正本とする。旧source ZIP・bundle・branch、元DB・原ラベル・研究者ノートを保全した。

### 実装と保存境界

- 専用read-only viewerで会話→run→初期/最新/過去ラベル版→タスク/結果/Core判断/採否→固定原文を辿る。SQLページング、担当・種別・操作・状態・UTC日付filter、詳細と根拠の分割取得を提供
- 表示のために実行serviceを初期化しない。appはSQLite `mode=ro`、query_only、固定read transactionの専用経路を注入する。GETでDDL/stale書込/復旧/再計算/モデル呼出し/Vault出力をしない
- `orchestration_label_audit` は追加schemaと追記専用trigger。実変更前後、proposal申告旧値・新値、採否、actor、task/result/decision、版、理由と根拠を保持。deleteはtombstone。未適用proposalのafterを採用結果と表示しない
- 旧履歴の欠落は未記録のまま。保存値の省略を明示し、破損hash・越境参照は拒否。model schemaは `core-handler-prompts-2-label-audit` へ更新。旧prompt版runは閲覧可能だが新promptで再開せず、旧checkoutを保持して復旧する
- スライドは保存された1runから決定的に作る。追加AI・新解析・現在会話からの補完はしない。既知fieldを日本語で表示し、未知/未検証/隔離を採用見解へ混ぜない
- 設計/promptのSoftware Vault記録hashとcatalogを照合。利用時は明示操作でVisualizationVaultのrun別設計ノートを保存し、読戻し確認後だけpreview/PPTXを許可。既存ノート履歴・削除保護を使い、失敗/編集/削除/対象版変更は出力停止。旧4先一括公開の権限は拡大しない
- 重大な未解決指摘を本編から欠く、根拠欠落/除外/別入力版がある場合は要確認としてPPTXを出さない。表示の継続は状態確認用で、成功扱いしない

### スライド設計の先行記録

Webの一次資料比較から独自の8セクション構成を選定した。[[40-Design/slide-generation-design-and-prompts]] v1.0.0は24994bytes、SHA256 `a3ed14a846b0144a8ed5428637fb8ff21a3bc9f0f3f7147988024895348c0ce8`。クラウドSoftware Vault正本とPC上の利用者指定Software Vaultへ同一UTF-8/LFを新規保存し、双方の再読hash確認を終えてから合成deckを生成した。PC側の既存ノートと`.obsidian`は変更していない。これは設計記録の保存確認であり、アプリコードのPC適用やPC実機での機能確認ではない。

### 検証と利用時の制約

匿名fixtureだけを使用。実Flask/SQLiteと実registryで保存run→設計POST→preview→PPTX→再openを確認し、追加AIなし・DB bytes不変・設計ノート削除時409を検証。追記監査のCRUD/競合/再実行、旧schema、213件履歴、135発話、204ラベル版、遅延応答/ABA/XSS/私有推論fieldの非掲載を含む。

最終Python全体は1271 passed / 2 failed / 32 skipped / 1107 subtests passed。全DOMは198/198成功。独立レビューは19件＋生成8件の27/27成功（既存suiteとの重複を含み、加算しない）。コード/test/configは全体試験中のhash差分0。既知2失敗はtorch未導入、32skipはbrowser/Windowsの未実行。成功に置き換えたりテストを削除したりしていない。詳細は配布verificationの `release-metadata.json` とログを参照。

PPTX sampleはネイティブの編集可能text object、JSON/notesにrun・入力/結果/ラベル版・hash・根拠IDを保持。15ページをLibreOfficeDev 26.8でPDF化し全ページ画像を確認、文字領域外0を照合した。NotoSansCJKsc/NotoSansへの代替描画で、Windows PowerPointのYu Gothic表示は未検証。長文・根拠保留の逆境検証とnative XMLの整合も確認する。相対API参照はグルモジ内照合用で、オフラインPPTXだけで開ける公開URLではない。

クラウドブラウザーで実Flaskのlocalhostページと匿名fixtureを開いたが `ERR_BLOCKED_BY_CLIENT`。トンネル・proxy・許可Origin拡張・sandbox解除で迂回しない。`ui/history-viewer-synthetic.html` は匿名fixtureの操作previewで、実画面受入・実AI結果の証拠ではない。

アプリ内原稿編集とPDF出力は初版対象外。PDFは開発QAの参考出力のみ。必要な新runtime依存は`python-pptx>=1.0.2,<2`、cloud lockは導入済み版を記録。未導入時はpreview可能/PPTX不可を明示する。実AI・実会話・実Vaultへの生成出力、課金、Windowsへのコード反映、push/merge/deployは行っていない。

## 2026-10-04 追補: 保存runスライドの視覚構成v2

基点 `e3f002c9d4962769deb1925b8d9859e7f7d2bd73` を保全し、別worktree／`dot/visual-analysis-slides-20261004` で改修。納品manifestのHEADと全ソースhashが実装の正本。元branch、元データ、旧Library版は保全し、push／deploy／Windowsへのアプリコード適用は行っていない。

- 旧15枚の実画像を確認した後、同じ文字列挙の反復と意味の途中での分断を解消。保存runの構造に応じて要旨、分析構成図、根拠と主張の接続図、専門担当、数量棒グラフ、批判とCore応答、統合判断、限界、監査表の9レイアウトへ決定的に投影する。sampleだけの別レンダラーではなくアプリ生成器に実装
- v2設計は31549bytes、SHA256 `9e43d30f386ea99700b5cf009caae1094a2854cf8491eeae9e9303dc05e3775f`。クラウド／PC Software Vaultの保存・再読一致と旧版backupを確認してから新PPTXを生成。採用設計hash・runtimeのrun別設計保存gateを維持
- visualの事前fit検査で、長文、未知の公開field、複合型、値／版の不一致は既存文字投影へ戻す。重大指摘・留保を本体で確認できなければPPTX出力停止。隔離、未実行、未記録、旧版、内容未確認を維持。存在しない一致／対立／ラベル変更履歴を作らない
- 数量は保存count／denominator／proportionが一致する場合のみnative chart。0を保持、多重ラベルを100%へ正規化せず、割合軸は0–100。編集用xlsxを保持。chart軸IDをunsignedへ統一し、embedded workbookの時刻も正規化して同じ保存runからbytes一致を確認
- 匿名合成の日本語見本は11枚、native chart1点、table1点、接続図、画像貼付0。全11枚の実画像と内容／根拠／留保を確認。最終PPTXのSHA256は `1f995f7f75fd8709c2bb60e291b00fd7c28d1b52bba7e555a2694a5f0860f370`。元の英語混在fixtureを日本語の合成fixtureへ改めたため、旧sampleと本文・snapshotが完全同一とは説明しない
- 最終関連テスト59 passed（8 subtests）、新規visual回帰8 passed、全DOM198/198。最終Python全体は1279 passed / 2 failed / 32 skipped / 1107 subtests passed。既知2失敗はtorch未導入のTransformer testsで前版と同じ。成功へ読み替えない。全体試験後に対象code／testのhash差分0を確認
- PPTXはpackage／geometry／EA font指定／native chartとembedded workbook参照／first-party importの検査を通過。描画はartifact-toolであり、Windows PowerPointの実表示と編集操作、実ブラウザー一連操作は未検証。相対API参照は引き続きグルモジ内の照合用

生成器依存は既存python-pptxのまま。追加AI、課金、実会話／実研究Vaultを使う検証は0。source-only ZIP、完全Git bundle、検証資料を別々の20MB未満ファイルにし、別フォルダー復元でsource全hashとbundleのHEAD／tree／fsckを照合する。サンプルのスライド数を固定する契約ではなく、保存内容と安全な分割により実runの枚数は変わる。


## 2026-10-09: Windows 選別受入と次の所有者

共有baseline `f52e95948e4fef3abe8afbe2d0ddd617c69ade3b` 上で、Dot #25 固定 `6534303820148b6b679e35e1ccd9ea7dbd4792a7` のpure pooling helper/test二fileだけを `deaa6751a566c7c22a8f1e205e26165e28b74bb3` に選別した。既存carrierを再利用し、原分母と欠測/観測zeroを保持する。原snapshot evidence対応、現在projection/policy、HC採択、execute/save/fresh権限の確認は既存Store owner責務である（Issue #25 確認6068361583）。

Windows Python3.13関連14件と別3会話合成例が成功。count/sum/mean・発話加重平均5.25・projection原分母と現在context・異なる定義の拒否を確認した。frontend14の凍結bytes/未stage/indexは不変。研究者データと実DB/Vault/モデルへ接触していない。実複数会話Handler保存/fresh橋、PNG接続、利用者Edge経路は未実行で、helper合格をそれらの完了へ拡張しない。

S6最終 `178bc53b136394784fd89f982c1f8dd403519ee2` の明示6fileは基点2805d998とのpatch hashを照合して読取り受領済み。独立レビュー後にWindows ownerがbackend-only shared index leaseで3way統合し、frontendへ固定ready版とleaseを返す。Lunaは受入済み公開SHAの通常push/通知のみ、仕様変更/担当競合はC0へ戻す。公開正本は `docs/GIT_HANDOFF.md` とmanifest、検証receiptはOrca Run `run_30240e5eb510` / Dispatch `ctx_b1d0fd9e06ef` を参照する。


## 2026-10-09: S6 通常受入の完了と延期境界

S6原最終178bc53/base2805d998の明示6fileは独立8＋隣接2件PASSを受領後、共有 `213ee596a60a48b18677b5262a233929ef3cc42a` に3way選別した。固定Git bytes/hash・AST6・diff・最小smokeが成功し、作者suiteの重複実行はしていない。frontend14の凍結を統合前後で保護してから、通常9pathのsource編集/受入を元ownerへ返した。

通常UIは実API5件、Edge1440/390の1テスト内2操作シナリオ、隣接3件、入口1件で成功した。固定原文と現在の対応・版・権限を保った射影→HC→平均→保存/fresh、graph/bundle HC、取消/revoke拒否、根拠往復の選択/scroll/focusを確認。選択欄ラベル不備を修正し、初回fixture5失敗・HTTP期待2失敗・Edge製品ラベル1失敗を消さずに閉鎖した。最終normal8全fileとhistory CSS focusだけを `1949833c1c20e898fe935cbad5df382d2c18fb23` に選別、receiptの9hashとstage一致。PNG専用3fileと図表CSS6rulesは作業bytesを保全し非commit。

実複数会話Store/Handlerと6e8/options複数source seamは未実装、PNG Store/Web/Vault接続は延期。full app/default AI/実利用者DB/Vault/モデル/認証/main/AT/full scheduler・全suite反復は未実行、Node/jsdom engine差はPARTIAL。合成fixtureのみで実データ接触0。原helper2の追加は今回不要で原checkoutへ書き込まなかった。受入source/index leaseは最終receiptでC0へ返却し、Luna新Dispatch `ctx_2496f7f8f44e` が受入済み公開SHAの通常forward push/readback/Dot通知を担当する。割当・仕様/担当競合はC0責務のまま。根拠はRun `run_30240e5eb510` / Dispatch `ctx_015ad29dbb33`、公開正本はGit受渡資料とmanifest。
