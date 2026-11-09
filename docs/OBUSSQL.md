# ObusSQLの接続とノート検索

[ObusSQL](https://github.com/krokharu/ObusSQL)は開発中です。グルモジには、任意依存の診断と、明示した管理ノートを読むプレビュー接続を用意しています。手元の開発版では、Windowsの `run.bat` が接続を有効にします。直接PythonやLinuxから起動する場合は `MOJIOKOSI_OBUSSQL_ENABLED=1` を指定します。SQLite・Vaultの保存先、既存カラム、正本、バックアップ形式は変わりません。

接続対象は内部パッケージ `obsipg` の `0.0.1.dev0`、2026-11-09に取得した最新ソースは [07128ac](https://github.com/krokharu/ObusSQL/tree/07128acfe13c1162552f7928b5ab0e7c954fac1b) です。パッケージの読込成功は、実アプリ連携・研究品質・本番運用の検証完了を意味しません。同じ開発版番号でも内容が変わるため、試用には固定したcommitの成果物を使ってください。

MAF（Microsoft Agent Framework）の実行拡張 `packages/obussql-maf` は、ObusSQLの上記 `main` コミットに含まれています。読取用の `obsipg` と同じ固定コミットを参照します。

## 試用環境

Python 3.12以上の専用環境と、一時DB・一時Vaultを用意します。既存のPython 3.10／3.11環境では通常のグルモジを引き続き利用できますが、ObusSQLの試用はできません。

任意依存は `config/requirements-obussql.txt` に分離しています。上流の配布・ビルド手順に従って固定commitのwheelを導入するか、ビルド可能な環境で次を実行します。非公開リポジトリへの既存のアクセス権が必要です。URLや設定ファイルへトークンを記入しないでください。

```powershell
.venv\Scripts\python.exe -m pip install -r config/requirements-obussql.txt
$env:MOJIOKOSI_OBUSSQL_ENABLED = "1"
```

同じ `0.0.1.dev0` を旧コミットから導入済みの場合は、試用環境で `pip install --upgrade --force-reinstall -r config/requirements-obussql.txt` を実行してください。版番号だけではコミットの違いを検出できません。

`MOJIOKOSI_DATA_DIR`・`MOJIOKOSI_OUTPUT_DIR`・`MOJIOKOSI_BACKUP_DIR` は試用先へ指定し、別worktreeのPython・データ・待受ポートを共有しないでください。既定のセットアップはObusSQL、PostgreSQL、MCPを追加インストールしません。

## 既存のMAF拡張

ObusSQL内の `packages/obussql-maf` は、独立して導入する `obussql-maf==0.1.0.dev0` です。`agent-framework-core==1.22.0` の公開Executor／Workflow APIを使います。上流拡張の診断には、この拡張の `RuntimeConfig`・`create_runtime`・`readiness` を使います。後述の開発版分析ドライバーとは別の接続です。

任意依存は `config/requirements-obussql-maf.txt` に分離しました。対象Pythonは **3.12のみ**（3.13以降も対象外）です。読取用の `obsipg` とMAF拡張は別の配布物なので、`requirements-obussql.txt` の導入だけではMAFは入りません。両者の実行連携も未構成です。

上流の配布物を試用環境に導入する際は、`requirements-obussql-maf.txt` を追加で指定します。旧コミットの同じ `0.1.0.dev0` を導入済みなら、こちらも `pip install --upgrade --force-reinstall -r config/requirements-obussql-maf.txt` で更新します。依存全体の再現には、固定commit内の `packages/obussql-maf/requirements-linux-cp312.lock` を `--require-hashes` で先に導入してください。このlockはLinux x86_64 CPython 3.12用で、Windowsでの動作確認は別途必要です。通常のrequirements指定だけでは推移的な依存のhashは固定されません。

`GET /api/obsidian/obussql` の `maf` 項目で、無効・Python非対応・未導入・版不一致・読込失敗・実行接続未構成を区別します。診断は `MOJIOKOSI_OBUSSQL_ENABLED=1` のときだけ行い、既定OFFでは拡張もフレームワークもimportしません。MAF未導入でも、読取用obsipgのプレビューは独立して使えます。

導入済みなら上流の本番用プロファイル `obus.maf.pipeline.v1` のreadinessだけを確認します。現在は `NOT_READY / HOST_BINDING_UNAVAILABLE` で、グルモジの診断も `execution_ready: false` を返します。`package_available: true` は拡張の確認結果であり、ワークフローやモデルの実行許可ではありません。試験用の `obus.maf.synthetic.v1` への自動切替はしません。

上流ではMAF実行拡張と限定した結合試験が実装済みです。[AF2の検証記録](https://github.com/krokharu/ObusSQL/blob/07128acfe13c1162552f7928b5ab0e7c954fac1b/docs/AF2_LOCAL_POSTGRES_ACCEPTANCE.md)でも本番接続はNOT_READYとされています。これを「MAF未実装」と扱わず、実装済みの拡張・グルモジでの未導入・本番の未接続を区別します。

## 診断と読取プレビュー

既存の認証・Host・CSRF・ローカルパスアクセス制限を継承します。操作は保存PCから行います。遠隔のローカルパス操作を明示的に許可している構成では、その既存設定に従います。

- `GET /api/obsidian/obussql`：`disabled`、`python_unsupported`、`not_installed`、`incompatible`、`import_failed`、`available_for_preview` を返します。無効時にはobsipgをimportせず、DB・Vaultを読みません。
- `GET /api/obsidian/obussql/notes?offset=0`：台帳上の候補を最大100件ずつ返します。実ファイルの確認は検索時に行います。
- `POST /api/obsidian/obussql/preview`：JSONの `notes` に `{ "note_id": "…", "sha256": "…" }` の配列、`query` に検索語を渡します。ブラウザーからは既存APIと同様に `X-Gurumoji-Request: 1` を送ります。

## 画面で操作する

1. `run.bat` で開発版を起動し、「接続と処理装置」の「ObusSQL」を確認します。
2. 「接続・ノート検索」を開きます。「事前設定」の「内部データ」からも開けます。
3. 接続済みの場合は管理ノートの候補を表示します。未導入・無効・Python非対応などは、実際の診断結果を表示します。
4. 読みたいノートを最大16件選び、検索語を入力して検索します。結果は元ノートの本文・行番号・版とともに表示します。
5. ノートや検索語を変更すると、前の結果は消えます。接続の再確認は「接続を再確認」で行います。

候補は台帳に基づき、検索時に原本・台帳・版を再確認します。結果は読取量の上限により一部に限られる場合があります。原本への書き込みやAIへの自動送信は行いません。MAFのワークフロー実行は別の接続として診断し、未導入・未接続の状態を隠しません。

IDとhashは、指定データ領域の `obsidian_layout/vaults.json` にある `notes` のキーと `sha256` を使います。これはノート原bytesのhashです。元データの `source_hash` やSQLiteのrevisionとは区別します。要求からOSパス、actor、agent、scope、SQL、接続先は受け取りません。

対象はVaultRegistryに登録されたInput・Visualization・Orchestratorの管理ノートで、`status` と `sync` が `current`、書込途中でないものに限ります。研究者が編集したノート、削除・stale・履歴・曖昧なID対応、Vault外へのリンクはエラーにし、修復や書き戻しは行いません。ResearchVault・PersonaVault・Software Vault・生の発話・メディア・分析表の自動探索はありません。

最大16ノート、1ノート256 KiB、合計1 MiB、検索語512文字です。ObusSQLの検索コンテキストは最大16 KiB、候補は先頭1024ブロックです。検索は上流の限定的な文字列一致で、全件検索や意味検索を保証しません。返却する `context` に選択・除外範囲、`sources` にID・元データ版・元データhash・ノートhash、`measurement` にコンテキストのUTF-8バイト数を含めます。token数は未計測なら `null` です。

scopeの `app_id` は `gurumoji`、`project_id` は既存SQLiteの `application_metadata.library_id`、sourceはVault種別、resourceは `note_id` です。ファイル名や個人の絶対パスからIDを生成しません。既存のlibrary IDがないDBは作成・補修せず拒否します。検索中のノート・台帳・library IDの変更も返却前に再確認します。

## 無効化と本接続までの範囲

### 自律分析の入力圧縮

`MOJIOKOSI_OBUSSQL_ENABLED=1` と参照入力・実測コンテキスト制御が有効なローカル自律分析では、ObusSQLの `ResponseCodecAdapter(compact_v2)` でJSONの往復一致を確認し、グルモジが表・共有値として読める配送候補を作ります。同じ値が並ぶラベル、同じ列を持つ報告、繰り返し文字列、文字列化されたJSONを可逆に整理します。切断済みのJSON抜粋は元の切断位置を維持します。

通常形式と配送候補を、同じロード済みモデルのtokenizerとチャットテンプレートで計測します。説明文も含めて候補の入力トークンが小さくなる場合だけ採用し、回答予約と安全余白を含む上限判定を続けます。圧縮前後・削減数・元JSONのhash・往復検証結果はタスクの `context_manifest.budget.context_delivery` に残ります。本文や必須条件を要約して削る処理ではありません。

任意依存の未導入・未対応・codec上限超過では通常形式を使い、復元不一致では送信を停止します。入力契約の版が変わるため、更新後はアプリを再起動して新しい分析を開始してください。保存済みの旧runを新契約として再開しません。

### 統計専用encoder・decoder

ObusSQL有効時の新しい自律分析では、`metric_codec_version=1` を保存し、統計担当レビューに `obusql_agent.metric_codec.MetricEncoder` と `MetricDecoder` を使います。追加の固定依存は `config/requirements-obussql-metric.txt` です。Windowsの `run.bat` は開発版MAFの起動時に専用codecの導入を確認します。直接起動する場合は次を実行します。

```powershell
.venv\Scripts\python.exe -m pip install -r config/requirements-obussql-metric.txt
```

既存の参加状況・会話動態・ラベル頻度の計算結果から、発話数、文字数、発話時間、記録済み無音・重複区間の件数と時間、ラベルの母数・観測・欠測・分類別度数を変換します。単位・粒度・母数・欠測・固定入力版・ラベル版・元結果hashを結び付け、元の統計表は保持します。割合や検定値を専用codec向けに推測して補う処理はありません。

AIには公開投影と集計元ごとに必須の選択欄を渡します。モデルはその欄の参照と `value` / `diff` / `ratio` / `max` / `min` を選びます。`value` は参照1件とその元値を生成schemaへ組で束縛し、差・比は参照2件、最大・最小は2件以上、計算結果の値は `null` です。原応答を既存台帳へ保存した後、元統計と対応表を再構築・照合してデコーダーが検証・計算します。統計担当の報告本文はデコーダーが生成し、モデルの自由文は監査用に保持します。数値は発話の根拠付き主張とは区別します。

未発行・別集計元の参照、値の改変、単位・粒度・版の不一致、不正演算、0除算、集計元の回答漏れは受理しません。空・全欠測は `null` と母数・欠測数のまま扱い、暗黙の丸め・単位換算はしません。1レビューは最大4集計元、50指標、公開投影16 KiBまでで、超過時は切り捨てず停止します。

入力対応表は `context_manifest.metric_contract`、受理結果は結果metadataと判断記録の `metric_validation`、検証成功は `metric_codec_validated` イベントに残ります。未導入なら新規分析の事前確認で停止します。既存DBカラムとVault保存先は変更せず、旧runを新契約として再開しません。研究上の尺度妥当性や自由な分析文全体の承認を、数値の検証成功と同一視しません。

### 開発版のMAF分析

返却済みの尺度案が受理条件を満たさない場合は、案を隔離し、検査の指摘を付けた修正タスクを最大1回だけ登録します。元の案と修正版は別のtask・attempt・resultとして保存し、呼出し数・時間・タスク数の上限を継承します。通信の結果不明・途中終了・停止後の応答を自動再送する機能ではありません。通常版ではこの修正タスクを追加しません。

開発版では、通常の自律分析画面からMAFとObusSQLを使って分析を実行できます。Python 3.12と固定版のobsipgを使い、追加の依存は次で導入します。

```powershell
.venv\Scripts\python.exe -m pip install -r config/requirements-gurumoji-maf-dev.txt
$env:MOJIOKOSI_OBUSSQL_ENABLED = "1"
$env:MOJIOKOSI_MAF_DEV_ENABLED = "1"
```

Windowsの `run.bat` は両方を未指定時に有効化し、MAF固定版がなければプロジェクトの `.venv` へ導入します。「接続・ノート検索」の開発版MAFの状態が利用可能になったら、自律分析画面でモデル・研究質問・終了条件を設定して開始してください。停止・再開・履歴・書き出しは既存の操作を使います。成果物のVault公開は分析開始時に選択した対象だけへ行います。

「ローカルAIの追加推論」は分析単位で選択できます。「使わない」は、その切替に対応するモデルへの要求だけで追加推論を無効にします。「モデルの既定を使う」は従来の設定を使います。モデル全体や他の処理の設定は変更しません。入力枠はロード済みモデルの実際の値を計測し、出力用の予約と安全余白を確保できない場合は送信前に停止します。

手元のGemma 4 12B QATでは、8Kのロード設定で専門家レビューの入力枠が不足しました。LM Studioでコンテキスト長を16,384にして読み込んだモデルを選び、追加推論「使わない」・同時実行上限1で開始します。CPUで実行する場合の検証用設定は「1回のAI呼出し上限」360秒です。このCPU構成での小規模合成会話の全工程は約39分でした。入力枠や時間は実際のデータ量に応じて確保してください。

同じ合成会話はGPUオフロード率80%・16Kでも、1呼出し上限120秒で保存・4Vault公開まで完了しました（約13分）。モデルのロード設定を変えた後も、追加推論の指定は分析単位で行います。

`gurumoji-maf-dev-v1` Workflowは「初期分析 → 固定根拠索引 → 自律分析」の順で動きます。固定済み発話だけをObusSQLのMemoryBackendへ登録し、モデルへ渡す根拠本文を版照合付きで取得します。Coreの参照根拠が入力上限を超える場合はタスクの問いによる文字列一致を優先し、残りを元の発話順で補充します。配送した根拠と省略範囲は既存のコンテキスト記録へ残します。

MAFへ流すメッセージはrun IDだけです。モデル呼出し、時間・回数制限、キャンセル、結果の検証・隔離、終了判定、成果物保存は既存の分析台帳が管理します。完了後は既存の成果物保存を呼び出し、保存や公開の失敗は分析完了と分けて履歴に残します。再起動後の不明な呼出しを自動再送しません。

専門家レビューは、提示された全指摘へ採否・理由・影響を1件ずつ返します。応答漏れや重複は受理せず、未解決点は未解決のまま記録します。指摘が多い場合は結果のまとまりごとに分割して処理します。

この開発版接続はMicrosoft Agent Frameworkの公開Workflow APIを使います。上流 `obussql-maf` の本番用 `obus.maf.pipeline.v1`、合成プロファイル、観測専用プロファイルは呼びません。`GET /api/obsidian/obussql` の `dev_bridge` が開発版の状態で、`maf` は引き続き上流拡張の診断です。SQLite・Vaultの保存形式、既存カラム、公開先の権限は変更しません。`MOJIOKOSI_MAF_DEV_ENABLED=0` で従来の分析実行に戻せます。実行方式の版が変わるため、切替後は新しい分析を開始してください。

`MOJIOKOSI_OBUSSQL_ENABLED=0` にして再起動すると読取接続を無効にできます。Windowsの `run.bat` は未指定時に有効化するため、無効にする場合は明示的に `0` を指定します。このときMAF開発版の指定がなければ、従来の分析実行を使います。プレビューは要求ごとのMemoryBackendだけを使い、新しい永続保存物を作らないため、DB移行やロールバックは不要です。プレビューの取得結果はAIへ自動送信しません。

上流拡張を使ったPostgreSQL保存、永続索引、双方向同期、自動取込、モデル連携、ジョブ復旧は未接続です。開発版分析は既存グルモジのモデル呼出し・保存・復旧判定を使います。上流の本接続は実装・検証が揃ってから、固定版の実パッケージ、一時データでの結合試験、保存・移行契約を確認して進めます。グルモジ側の試験と設計判断は[開発資料ブランチ](https://github.com/krokharu/gurumoji/tree/archive/development-assets-20261016)に保持します。
