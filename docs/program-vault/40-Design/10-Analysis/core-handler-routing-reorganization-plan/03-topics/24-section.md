---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-24
title: コア・ハンドラー・ルーティング再編案：段階的な移行プラン
summary: 段階的な移行プラン。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1381
- 1465
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：段階的な移行プラン

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 段階的な移行プラン

各段階を単独でレビュー・差し戻しできる変更にする。全ルートを先に移してからHandlerを作る順序をやめ、**対象機能のRouting・Handler・必要な依存を一緒に完成させる**。

### Phase 0：対象と比較基準を固定

1. 作業ツリーには未コミット変更があるため、実装開始時の対象ファイルと差分を確定する。既存変更を再編の差分に混ぜず、対象関数が並行して変わった場合は基準を取り直す。
2. 初回対象を`GET /api/analysis/methods`、`GET /api/library/<item_id>/analysis/runs`、`GET /api/analysis/artifacts/<artifact_id>`の3ルートに限定する。
3. importのみでDB初期化・watcher・AIを開始しない条件で、`app.url_map`のURL、methods（自動HEAD／OPTIONSを含む）、endpointを取得する。静的配信も対象に含める。全ルートの詳細なJSON台帳は作らない。
4. 既存の`test_analysis_storage.py`と関連テストを確認し、対象3ルートの正常系、存在しないID、壊れた成果物、ローカル／リモート公開情報に不足するケースだけ補う。
5. 既存テストの失敗は先に記録・切り分ける。今回の移動に関係する失敗を残したまま進めない。

**完了条件：** 対象ルートの依存、既存テストの結果、変更前のHTTP契約が特定され、初回差分の範囲が明確である。

### Phase 1：読み取り3ルートを縦切りで分離

- Blueprintの登録関数へ必要なHandler／依存を渡す。Blueprint／Handlerは`app.py`をimportしない。
- 履歴取得では現行のfingerprint照合とstale表示を保持する。成果物取得ではID参照、hash検証、404／409、MIME、添付名を維持する。
- 初回は大きなEntityや汎用Repositoryを導入せず、既存の`AnalysisStore`の必要な操作を利用する。
- 互換呼び出しは組み立て側で明示する。`app`モジュール全体、`globals()`、Flaskアプリ全体を新Handlerへ渡す方法は使わない。
- 既存テストが差し替える`DATABASE_FILE`等を登録時に固定しない。移行中は呼び出し時に現在の設定から既存storeを作る等の最小限の橋渡しを置き、必要なpatchが実際に使われることを確認する。
- 認証・共通エラー処理・起動構造はこの段階で再設計しない。

**完了条件：** 対象3ルートが互換であり、履歴取得または成果物取得のHandlerをFlask contextなしで検証できる。新設モジュールに逆importがなく、ルート登録は重複していない。

**実装状態（2026-09-20）：完了。** `web/analysis_routes.py`と`handlers/analysis_queries.py`へ分離し、HTTP契約、stale判定、成果物hashエラー、ローカル情報の公開制御、設定差し替え、FlaskなしのHandler、ルート重複なしをテストで確認した。

**継続判断：** 呼び出し経路と依存が明確になり、HTTPなしの検証ができた場合だけ次へ進む。既存関数を何重にも包むだけなら、抽象化を削ってから再評価する。ここで終了しても有効な改善として残せる。

### Phase 2：固定保存・Vault再試行を同じ境界へ移す

対象は`save_analysis_run`、`retry_analysis_vault`。比較の固定保存はこの縦切りが安定してから別変更で扱う。

- JSONの構文検証・HTTP変換をRoutingに残し、revision照合から保存・再試行までの調整をHandlerへ移す。
- `library_write_lock`と`analysis_store.STORE_LOCK`は、それぞれ既存の共有インスタンスを使い、取得順・解放条件を保持する。別のlockを新設して同じデータを守ったつもりにしない。
- 現行の読み取り→revision照合→計算→確定の保護範囲を維持する。lock外への計算移動や並行化は別の最適化として扱う。
- `request_id`の冪等性、保存途中の保留パッケージ、正本確定後のVault失敗を維持する。DB／ファイル／Vaultをまとめた新しいrollback機構は導入しない。
- **初回の固定保存は現行どおり集計を行う。** 「保存は一切計算しない」とは定義しない。Vault再試行・中断保存の回復は保存済みパッケージを使い、分析やAIを再実行しない。
- fingerprintやstaleの純粋部分を抽出する場合も既存関数を優先し、SQLite triggerが担う無効化を削除・二重実装しない。

**完了条件：** 初回保存、同じ要求の再送、revision競合、中断保存後の原文変更、Vault失敗・再試行が現行と同じ結果になる。`test_analysis_storage.py`の該当ケースと比較・準備変更に隣接するテストが通る。

**実装状態（2026-09-20）：完了。** `handlers/analysis_commands.py`へrevision照合から固定保存・再試行までを移し、RoutingにはJSON検証とHTTP変換を残した。共有lockの取得順、保存途中のパッケージ、stale更新、Vault競合時の人のノート保護を変えず、FlaskなしのHandlerテストと既存の保存・回復テストで確認した。

### Phase 3：効果のある機能だけ同じ手順で拡張

以下は別々の変更とし、対象外の機能は既存位置に残してよい。

AIを使う機能の移行では「AI管理の導入順序」のAI-0〜AI-2と接続する。生成・判定・知識参照の責務をHandlerへ渡し、各ルートにprovider選択や送信方針を重複実装しない。挙動維持の移動と、送信方針・payload版の拡張は同じ変更に混ぜない。

| 順序 | 対象 | 移行前に固定する境界 |
| --- | --- | --- |
| 1 | 比較保存、編集、分析準備・話者変更 | 複数会話のstale伝播、入力版、編集manifest、学習用出力、削除回復 |
| 2 | AI見解・Transformer・分類 | 同期／非同期の違い、要求の冪等性、revision変化、取消、thread開始失敗 |
| 3 | 文字起こし・アップロード | endpoint依存の受付、上限、二重送信、取消不可の確定段階、作業ファイルの所有 |
| 4 | Obsidian watcher、起動・終了 | 二重起動防止、回復順序、watcherの起動・停止、共有設定とlock |

対象機能を移す際に必要なら小さなCore関数、ジョブ所有オブジェクト、依存契約を追加する。機能別Handler内の操作が増えたという理由だけでcommands／queriesを階層化しない。

**完了条件：** 移行した機能について、正常・失敗・取消・再起動の該当経路が維持される。未移行機能の分離はその変更の合否条件にしない。

**実装状態（2026-09-20）：完了。** 順序1のうち比較の固定保存、分析準備の保存、通常の会話編集（話者名・会話内話者プロファイルを含む）を`AnalysisCommands`と共通Blueprintへ移した。比較は表示時の複数入力fingerprint照合、サーバー側の再集計、専用run・member保存、stale伝播、Vault公開を確認した。分析準備は`BEGIN IMMEDIATE`からrevision・本文版更新・stale伝播までの単一トランザクション、commit後の索引更新、InputVaultへ本文を出さない契約を確認した。通常編集は共有lock内の確定、revision競合、編集manifest・回復、学習用差分、索引とInputVaultの更新を既存テストで確認した。グローバル話者台帳のGET／PUTとCSV取込から共用する保存処理も`SpeakerRegistryHandler`と専用Blueprintへ移し、台帳revision競合、削除、保存後の分析索引更新を確認した。AI話者再同定は送信内容・provider規則を変えず、資格情報解決、同期AI実行、実行後revision照合、利用量保存、話者修復とInputVault更新をFlask非依存のユースケースとHandlerへ分離した。

順序2はAI見解、Transformer、発話分類の取得・実行境界を`AnalysisQueries`／`AnalysisCommands`と共通Blueprintへ移した。状態取得は保存済み結果と最新requestをSQLite snapshotから読み、取得操作でAI・Transformer・Jevを再実行しない。AI見解とTransformerの開始・取消はrequest ID再送、同時実行拒否、revision照合、AI見解の専門家ゲート、Transformerの自動／候補／手動条件、thread開始失敗時の後始末、取消eventを既存の共有lockとDB状態のまま保持した。発話分類は同期実行のまま、Jev利用指定、実行前後のrevision照合、手動・ルール・Jev・Transformer値の分離、SQLite確定後の固定履歴作成とVault失敗時の警告を維持した。非同期workerは既存のFlask非依存関数を継続利用する。

順序3は文字起こしジョブの受付、状態取得、取消、完了後編集、ジョブ所有ファイル取得を`JobHandler`と専用Routingへ移した。話者台帳のCSV取込も既存の`SpeakerRegistryHandler`保存処理を使うRoutingへ統合した。`create_job`と`import_speaker_registry`を含むendpoint名は共通security hookと互換入口のため維持し、submission IDの再送、同時受付予約、メディア／CSVのmultipart上限、`after_request`での予約解放を既存hookへ残した。文字起こしフォーム検証から作業・出力ディレクトリ確保、worker開始、開始失敗時のジョブ登録・upload・出力の後始末は1つのFlask非依存コマンドとして維持し、`committing`以降を取消不可とする状態境界も変えていない。

順序4はinstance lock取得からライブラリ初期化、編集回復、取込来歴修復、削除回復、学習成果物修復、孤立upload掃除、既存出力取込までを`ApplicationLifecycle`の明示的な順序へ移した。途中失敗時はlockを解放し、Obsidian watcherは同じLifecycleが単一instanceとして所有して二重起動を避け、停止event・thread join後にinstance lockを解放する。watcher内の作業状態回復、Vault移行、操作ノートpoll、theme同期と例外時の停止条件は変更していない。

### Phase 4：互換入口と不要な橋渡しを整理

- 移行済み機能の一時的な橋渡しだけを削除し、設定・依存を組み立て側で明示する。`src/app.py`による`import app`と`gurumoji.app`の同一モジュール性を保つ。
- 関数をre-exportするだけでは、その関数が参照するglobalや既存patch先は移らない。公開されている互換入口と内部関数へのテスト依存を区別し、テストは実際の依存先を差し替える形へ移す。
- 起動責務の独立が有効になった場合に限り`bootstrap.py`／app factoryを導入する。factory生成とデータ初期化・thread開始を分ける。
- `initialize_application`のinstance lock取得、編集回復、来歴修復、削除回復、学習成果物修復、upload掃除、既存出力取り込みの順序を維持する。`main`終了時のlock解放、watcherの停止も維持する。
- `app.py`を薄くすること自体を完了条件にしない。移行対象の入口から実処理まで追跡でき、不要な二重登録・二重状態・逆importが消えたことを確認する。

**完了条件：** 既存の起動・import・HTTP契約が保たれ、移行済み機能が単一の実装を参照する。全体起動や共通hookに触れた変更では、局所テストに加えて広い回帰確認を行う。

**実装状態（2026-09-20）：完了。** 移行対象の旧ルート実装を削除し、組み立て側から各Handler／Routingへ依存を渡す単一経路にした。`src/app.py`の互換importは`gurumoji.app`と同一モジュールを返し、`create_job`／`import_speaker_registry`のendpoint名は共通security hookとの契約として維持する。一時的な再exportや旧新二重登録はなく、移行済みHTTP操作の一意性と`handlers`／`web`からcomposition moduleへの逆import不在を機械検証する。

### Phase 5：app.py に残った処理の移動（2026-09-25）

**実装状態：完了。** Phase 0〜4 と同じ方針（機能ごとの縦切り、`app.py` への逆import禁止、HTTP・DB・Vault契約の維持）で、残っていた処理を手順0〜11に分けて移した。`app.py` は 8,361 行から 1,895 行になった。移動先・検証・注意点は [[70-Changes/10-Compatibility/app-py-phase5|app-py-phase5]]、旧シンボルの移動先は `70-Changes/app-py-phase5.data.json` に記録した。
