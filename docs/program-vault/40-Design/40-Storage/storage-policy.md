---
note_id: design-storage-policy
note_type: storage-policy
title: 保存先と正本の分類
status: current
updated: 2026-10-22
schema_version: 1
tags:
- gurumoji/storage
summary: 現行の保存先・正本・バックアップ対象、実装した系列D〜Fと後続の制約を分類する。型付きpackage版2、Rawと差分、派生DB、利用者承認後の試験DB切替は実施計画を参照。
---

# 保存先と正本の分類

2026-10-12更新：組み込み手法の固定保存・型付き表JSONと共有CSV・AI仕上げの変更記録・Vault生成は実装済みです。現行API・テーブル・登録契約は [[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]] を参照してください。系列D〜Fの後続変更、差分取り込み・外部手法等の計画は実装済みの範囲と区別します。

「正本」は、変更時に優先し、復元時の基準にする保存物を指す。同じ内容が複数の形式に現れる場合も、どれが正本でどれが表示・交換用かを記録する。

## 分類表

| データ | 正本 | Obsidianに置くもの | CSV／JSON等に残すもの | 更新のルール |
| --- | --- | --- | --- | --- |
| 現在の文字起こし本文・時刻・話者割当 | SQLite `library_items` | 版付きの対象発話と根拠ブロック、会話の入口 | 既存文字起こしJSON／TXT／SRT、固定した入力JSON | 本文の修正は既存編集保存を通す |
| 話者台帳・会話プロフィール・データグループ | SQLite `speaker_registry`・`library_items.speaker_profiles_json`・`library_groups` | 設定で選んだ表示項目、研究上必要な属性 | 既存話者CSV、入力時点の実効プロフィールJSON | IDで対応。氏名や表示順で照合しない |
| 分析条件・対象／除外・コードブック・測定定義 | SQLite `library_items.analysis_config_json`・`analysis_annotations_json`・`analysis_definitions` | 条件の説明、確定コードの定義と適用例 | 固定結果の条件JSON、コードブックJSON／CSV、固定定義を含むExecutionBinding | 条件変更で新しい入力識別値を作る |
| アプリで確定したコード付与・重要引用・分析メモ | SQLite `library_items.analysis_annotations_json` | 確定内容の表示、引用リンク | 注釈JSON、コード済み発話CSV | 既存保存APIとrevision確認を使う |
| Obsidianで新規作成した自由メモ・概念・仮説 | 人が編集するMarkdown | 本文、関連ノート、原文リンク | 選択時の移送用JSON。DBにはID・hash・索引 | Markdownを勝手に再生成しない |
| Obsidianから提出するコード案・解釈案 | 元のMarkdown。採用後のアプリ値はSQLite | 提出原文と根拠 | 取り込みイベントJSON | 差分確認後の取り込み。提出原文は保存 |
| 確定保存した分析結果 | 実行ID付きのJSON・CSV | 要約、主要表、図、条件、結果ファイルへの参照 | 全件JSON、表形式CSV、manifest | 固定結果は不変。DBは台帳・最新ポインターを管理 |
| AI見解 | 現行互換の最新値はSQLite。保存履歴は実行ID付きJSON | 「AI見解・下書き」、出所、対象版、根拠 | 結果JSON、入力・prompt版・使用量の記録 | 成功時だけ最新ポインター更新。失敗で旧成功を消さない |
| 形態素・係り受け・語彙・共起・統計の詳細行 | 固定保存した結果JSON・型付き表JSON | 説明・一部の表・結果リンク | 型付き表と同じ値から生成する共有CSV。分割JSONL等は後続計画 | 大量行をMarkdownやDBの重複JSONへ押し込まない |
| KWIC | 保存した検索条件JSON＋一致結果CSV | 検索目的、ヒット数、選択した引用 | 全一致行、位置、対象版 | 通常検索は一時状態。「検索を保存」で固定 |
| 実行中ジョブ・使用量・エラー・同期状態 | SQLite | 完了・失敗等の概要を索引に表示 | 必要な監査用エクスポート | 進捗の更新ごとにノートを書き換えない |
| Vault台帳・書き込みhash・変更履歴 | `<data>/obsidian_layout` のJSON／JSONL | 対応ノートのID・revision・索引 | `vaults.json`、`interviews.json`、`note_changes.jsonl` | 衝突・欠落判定に必要な状態。Vaultと一緒にバックアップする |
| AI仕上げの作業状態・候補結果 | `<data>/obsidian_workbench/<item-key>/` の状態JSON・結果JSON | ResearchVaultの操作ノート・仕上げ結果 | `state.json`、`result-<run_id>.json`等 | 既存Workbench経路を使い、作業状態もバックアップする |
| 議論用人格・パネル・議事録・人格の記憶 | `<data>/obsidian/PersonaVault` のMarkdown | `10-Personas`・`20-Panels`・`30-Deliberations`・`40-Memory` | 必要な手動エクスポート | ADR-114。手作業で作成済み、アプリは読み書き・VaultRegistry登録をしない。記憶・議事録は追記、`obsidian`一式のバックアップに含む |
| 再計算可能な形態素・係り受けの解析行（F1） | 正本ではない。`<data>/analysis-derived.sqlite3` の `segment_parses`・`morphemes`・`dependencies` | 通常は収録しない | 旧形式の固定JSON・CSVは維持。パッケージ版2の参照は後続 | 本文hash・解析器／辞書／モデルの版・設定hashごとに追記。読込時に入力と結果hashを照合し、話者・役割・除外は固定入力から付ける。バックアップ対象外、欠落時は再計算。ベクトルは未導入 |
| 検索キャッシュ・描画用キャッシュ | 再生成可能な一時領域 | 通常は収録しない | 必要なものだけキャッシュ | 正本のバックアップ対象から分離 |
| 原音声・動画 | `data/media` の元ファイル | アプリで該当時刻を確認するリンク | 元形式。配布時は選択して複製 | 自動で全音声をVaultへ複製しない |
| サムネイル・ワードクラウド・分析図 | 再生成物。引用した図は実行成果物 | PNG／SVG等の閲覧用添付 | 元データと生成条件、選択した図 | 図と数値の実行IDを揃える |
| 学習イベント・音声クリップ | 既存DBイベントと保管音声 | 件数・作成方法・場所への参照 | 既存manifest CSV／JSON等 | 研究ノートと学習用レコードを混同しない |
| プログラムの仕様・設計判断・手法規約 | Git管理するプログラムVault | 構成・機能・API・手法・テスト・運用資料 | schema例、架空のサンプル | コードの変更と資料更新を対応させる |
| APIキー・トークン・ローカル秘密設定 | 現行 `tokens.json` 等 | 設定項目の説明のみ | 値を含まないサンプル | 実値を両Vaultへ複製しない |

## 現行の物理配置と後続計画

```text
<data-root>/
  library.sqlite3
  analysis-derived.sqlite3  F1の再計算可能な形態素・係り受け行（バックアップ対象外）
  media/...
  analysis_store/
    inputs/<snapshot-id>/input.json
    runs/<analysis-id>/
      manifest.json
      parameters.json
      result.json
      tables/*.json        型付き表の正本
      tables/*.csv         同じ値から作る共有用表
  obsidian/
    ResearchVault/         研究者のMarkdownと閲覧用添付
    InputVault/            入力台帳・固定スナップショットの説明
    VisualizationVault/    図表仕様と成果物の来歴
    OrchestratorVault/     手法カード・実行記録
    PersonaVault/          手作業で作成する議論用ノート（アプリ未登録）
  obsidian_layout/         Vault台帳・書き込みhash・変更履歴
  obsidian_workbench/      AI仕上げの作業状態・候補結果

<repo>/
  runtime/output/          既存の文字起こし・字幕・互換成果物（既定）
  runtime/backups/         明示的な整合バックアップ（既定、データ外）
  docs/program-vault/      プログラム資料のVault
```

`<data-root>`はDBの親ディレクトリ（既定`runtime/data`、`MOJIOKOSI_DATA_DIR`で変更）。出力・バックアップ先はそれぞれ既存の`MOJIOKOSI_OUTPUT_DIR`・`MOJIOKOSI_BACKUP_DIR`で解決する。外部結果の`incoming/`は後続実装の対象。F1の派生SQLiteはDBの親ディレクトリに配置する。新規のVault移行バックアップは`MOJIOKOSI_BACKUP_DIR`（既定`runtime/backups`）の`backup-<id>/`へ作り、旧配置の既存バックアップとpending記録は移動しない。

| 系列 | 現行の保存 | 後続計画との境界 |
| --- | --- | --- |
| D：話者・属性・グループ | `speaker_registry`、`library_groups`、`library_items`の正本と追加の投影・属性・タグ表 | 現行カラムを維持。研究者の確定値と差分履歴をバックアップし、検索用FTSとベクトル索引は現在版・除外条件で検証する |
| E：エージェント用コンテキスト | 固定入力・計画・binding、step証跡、区間所有権、短い参照IDと配送manifest | コンテキスト縮小・区間処理・確定step再利用は実装済み。契約成功と実モデルの研究品質・採用は別ゲート |
| F：分析結果と派生データ | `analysis_runs`・成果物台帳、固定入力・型付き表、版2の固定参照 | package版2とF1〜F3は実装済み。同内容はQ23の条件で既存runを再利用。異なる推論結果・版は別runを保持し、欠落を別実行で代用しない。派生DBは再計算用・バックアップ対象外 |

`analysis_store` は既存の `output/*_話者分離.json` の自動取込先から分離し、固定入力を誤って新しい会話として再取込しない。既存ファイル名やダウンロード形式は維持する。

CSV／JSONの大量データは `analysis_store` に一度保存し、通常のVault同期では複製しない。ノートには `artifact_id`、相対的な保管場所の説明、アプリ経由の取得リンクを付ける。Obsidian自体がCSV／JSONを表として表示することは前提にしない。

## 自動保存と容量

- ライブラリの保存では、会話の入口と更新状態を更新キューへ入れる。
- 明示した分析保存、再集計完了、AI生成成功、外部結果登録で固定結果を作る。分析GETやページ閲覧では履歴を増やさない。
- 同じ入力スナップショット・手法版・条件・エンジンで同じ成果物を再利用できる。AIを明示的に再生成した場合は、同じ入力でも別の実行として保存する。
- 保存済みの成功結果は自動削除しない。キャッシュと放棄されたstagingには別の保持期限を設ける。
- 引用・メモ・別分析から参照される実行は保持する。容量整理では参照関係と削除予定を表示する。
- 「Vault登録解除」「アプリ上の会話削除」「保存履歴・音声の完全削除」を別操作とし、全コピーの所在をmanifestで追跡する。

## 端末間の移送・復元

研究用Vaultだけをコピーした場合は、保存済みノートと添付図が読める。元音声・外部のCSV／JSON・実行中のアプリへの接続は含まれない。すべてを持ち出す場合は、選択した結果を `PortableData/` へ収め、参照を相対リンクにした「可搬パッケージ」を作る。CSV／JSONは元形式のまま同梱する。

現行の`services/data_backup.py`はSQLiteのbackup APIで`library.sqlite3`の整合コピーを作り、`analysis_store`・`obsidian`（PersonaVaultも含む）・`obsidian_layout`・`obsidian_workbench`・`custom_vocabulary.json`を必須対象として保存する。メディア・学習用音声は選択式。台帳・hash・作業状態は表示用キャッシュではなく、履歴保持・競合検知・再開に必要な保存物である。派生データ用SQLiteはこの必須対象に追加しない。Vaultをクラウド等で運ぶ方法は別設定とし、稼働中DBをVault同期の対象にしない。

研究用Vaultの表示名は既定で参加者コード／仮名を優先する。これは本文中の個人情報を匿名化する処理とは別である。配布パッケージは、対象会話・属性・原文・音声の範囲を指定して作成する。プログラムVaultに実際の参加者情報や原文を載せない。

関連：[[40-Design/40-Storage/sync-contract|sync-contract]]、[[40-Design/50-Governance/method-rules/00-Index|method-rules]]。

## ObusSQL接続準備（2026-10-22）

利用者の依頼「作成中のObusSQLをグルモジへ入れる基盤を用意」に対応。アプリ変更は `krokharu/ObusSQL導入` の `175018992f6d92466444c54e50a2a2811a248be5`（基点 `e33a91d`）。参照した上流は [krokharu/ObusSQL の 5be3212](https://github.com/krokharu/ObusSQL/tree/5be32120d17a7f07eac7a2c41b0bab1372ae4cdb)、内部パッケージは `obsipg 0.0.1.dev0`。上流README・CLOUD_IMPLEMENTATION_PLANの本接続前の実装／検証順序を維持する。

- `services/obussql.py` と `web/obussql_routes.py` に既定OFFの読取プレビューを追加。通常のrequirementsと分離した固定commitの任意依存、状態診断、利用手順はアプリ側の `config/requirements-obussql.txt`・`docs/OBUSSQL.md` に置く。Python 3.12以上が必要なのはこの任意接続だけ。
- `VaultRegistry` のID・path・revision・source_hash・sha256を再利用する。scopeは既存SQLiteの `application_metadata.library_id`、sourceはVault種別、resourceはnote_id。DB接続は `mode=ro`、欠けたIDの作成や補修をしない。既存カラム・正本・書込経路・バックアップの変更はゼロ。
- 明示した最大16ノート（各256 KiB、合計1 MiB）だけを読み、原UTF-8 bytes・BOM・改行を維持。同期済みかつcurrentのInput／Visualization／Orchestratorの管理ノートに限定し、本文編集、stale、欠落、pending、曖昧なID、Vault外参照・reparseを拒否する。全選択の事前確認と返却前のhash・台帳・library ID再確認を行う。hash再確認は外部編集に対するOSレベルの排他保証ではない。
- 上流のMemoryBackendは要求ごとに破棄するプレビュー用。権限・actor・scope・任意パスはHTTP入力から受け取らず、既存認証／Host／CSRF／ローカルパス制限を通す。検索結果はAIへ送らず、永続索引・DSN・SQL実行口・同期・復旧ジョブを追加しない。無効化は `MOJIOKOSI_OBUSSQL_ENABLED=0` で、移行／ロールバック不要。

検証は当該worktree専用 `.venv`（Windows CPython 3.12）と一時DB・一時Vaultで実行。待受ポートは開かず、実runtime・実Vault・tokens.json・.envは変更していない。追加の `tests/test_obussql_integration.py`、既存 `test_four_vaults.py`、`test_vault_note_policy.py` は **59 PASS / 2 SKIP**（29.04秒）。追加分は35 PASS。skipは実シンボリックリンク作成権限不足と、ネイティブObusSQLパッケージ未導入。プレビューの依存側はテストダブルで接続契約を確認しており、実パッケージ結合の合格ではない。

実行時はアプリcheckoutのsrcを使う。開発資料ブランチのpytest設定がsrcを上書きするため、`PYTHONPATH` に加えて `-o pythonpath` を指定する。

```powershell
$env:PYTHONPATH = "$appRoot/src;$devRoot/tests"
& "$appRoot/.venv/Scripts/python.exe" -m pytest "$devRoot/tests/test_obussql_integration.py" "$devRoot/tests/test_four_vaults.py" "$devRoot/tests/test_vault_note_policy.py" -o "pythonpath=$appRoot/src" -q -rs -p no:cacheprovider
```

別途、隔離したアプリ本体importと無効時GET=200／POST=503、Python 3.10文法との互換、`git diff --check` を確認。Python 3.10実機、実ObusSQL wheel・PostgreSQL・MCP・実LLM・双方向同期・復旧・性能・ブラウザーUI・全体試験は未実行。本接続時は上流の固定版の完成範囲を再確認し、実パッケージ試験と保存／移行契約の検証を進める。

### MAF拡張の確認と接続準備の補完（2026-10-22）

利用者の指摘で開発ブランチも確認し、ObusSQLの `packages/obussql-maf` が既に実装済みと判明。最初に参照したmainの `5be3212` には含まれず、mainだけの確認では不足していた。`dot/af2-provenance-activation-20261021` の固定版 [228a864](https://github.com/krokharu/ObusSQL/tree/228a86477aa5cee7e651b9fd661b4f4e8c6d2fdc/packages/obussql-maf)を追加の参照先とした。実装本体は `dot/maf-execution-package-20261020` の `77b68fe` と同じblob。`obussql-maf 0.1.0.dev0` は `agent-framework-core==1.22.0` に依存する独立配布物で、Pythonは3.12限定。

アプリ側 `5f113448ef38293995ebee5cb61e3a5c3db97bfc` で固定commit・subdirectory指定の任意requirementsと、既存診断APIの `maf` 項目を追加。上流の `RuntimeConfig/create_runtime/readiness` を使い、MAFを再実装しない。既定OFFは依存の調査・importを行わない。ON時も本番用 `obus.maf.pipeline.v1` のreadinessだけを確認し、workflow.run・callback・モデル・DB操作を起動しない。拡張の確認と `execution_ready` を区別し、上流の現在の `NOT_READY / HOST_BINDING_UNAVAILABLE` を維持する。未知の版・契約変更は拒否し、試験用プロファイルへ自動切替しない。MAF未導入でも既存の読取プレビューは利用できる。

同じ専用venv・一時データで `test_obussql_integration.py` **47 PASS / 2 SKIP**（4.07秒、今回12件追加）。Python版・依存欠落／不一致、readiness確認時の実行禁止、上流の状態変更の拒否、例外内容の非公開、読取機能との独立を確認。HTTP応答とPython 3.10文法も確認。実MAF・実ObusSQLのインストール／実行と本番host接続は未実施。既存Vault側24件は直前変更の成功記録を維持し、今回そのコードは変更していない。実利用者データ・認証設定の変更なし。


### ?????????????2026-10-27?

???????????????main????????? `krokharu/ObusSQL??` ????????????????????????????????Input?Visualization?Orchestrator ? current ?????????????????????????hash???????????????100??????16??Windows `run.bat` ???????????????????? `0` ????????SQLite?Vault????????????????????????

ObusSQL?????? `5be32120d17a7f07eac7a2c41b0bab1372ae4cdb` ????????MSVC?CPython 3.12?Windows wheel???????????venv????wheel SHA-256 `2823798425eb067f0384bddd3db5b713fcdb88c6c9a98d8b3adf5c519b6a1c2e`???????checkout?HEAD `69728a6` ???????????????????commit???????????????????

??DB?Vault??wheel???? `test_obussql_integration.py`?`test_four_vaults.py`?`test_vault_note_policy.py` ?72 PASS?1 SKIP?2 subtests PASS?SKIP?Windows????????????????????2??pytest??????pythonpath?Windows???????collection error???????????????DB??wheel?????????????????????????????????JS?????????????????PostgreSQL???????MAF???????????????????

## 2026-11-02 Claude計画に基づく開発版MAF分析接続

Claude Code 2.1.310に読み取り専用で実装計画を依頼した。上流obussql-mafの本番プロファイルはHOST_BINDING_UNAVAILABLEであり、そのガードを解除したりsyntheticプロファイルで実利用を偽装したりしない。Microsoft Agent Framework 1.22.0の公開Workflow/Executor APIを使うGurumoji開発版ブリッジを別に構成する方針を採用した。

採用した実装は、初期分析、固定根拠索引、自律分析の3段階をMAFで接続し、既存AnalysisOrchestrationServiceへ実行ドライバーを注入する。既存の開始・停止・再開API、台帳、世代番号による失効、原応答の保存と隔離、終了判定、完了後の成果物保存・公開を使う。新たな実行APIやSQLカラムの変更は不要と判断した。MAFのメッセージはrun IDだけとし、本文・モデル応答は渡さない。

ObusSQLは当該runの固定済み・除外されていない発話だけをMemoryBackendに登録する。モデルへ配送する本文を版付きで取得し、元の根拠IDと本文を検証する。Coreの参照根拠の選択は指定済みの部分集合だけで行い、省略と実配送範囲を既存manifestへ残す。Vaultの自動探索、同期、研究者ノートの変更、新規の永続索引は行わない。日本語のUnicode行区切りとMarkdownフェンスも損失なく復元する。

MOJIOKOSI_MAF_DEV_ENABLEDとMOJIOKOSI_OBUSSQL_ENABLEDを明示的な有効化条件とし、Windowsの開発版run.batでは未指定時に有効化する。無効時は従来ドライバーを使い、依存不足時はモデル送信前に停止する。通常版と開発版ではadapter_versionを分け、既存runを異なる指示で再開しない。

実モデルの合成会話試験から、8,192トークンのロード済みモデルでは初回批判と尺度設計の指示重複が停止原因となることを確認した。安全余白と必須の尺度条件を維持して段階別の指示を整理し、1概念の尺度タスクには1定義用の出力枠を使う。名義尺度に2値以上を要求する受理契約と生成用JSONスキーマの差も修正した。最終の実行結果・検証件数は後続の検証記録に追記する。
### 実機検証から追加した判断（2026-11-02、adapter 42）

返却済みで来歴が一致する尺度案が受理条件に違反した場合だけ、開発版はlabel_repair_limit=1として修正タスクを1回登録する。不正案は隔離したまま、別task/attempt/resultとし、元の呼出し・時間・登録数上限を継承する。通信不明、途中終了、停止後の応答、来歴不一致はこの修正の対象にしない。通常版の設定は0であり、既存の無再送契約を維持する。1回で有効にならなければ停止する。

追加推論はlocal_reasoning=off/autoとして実行設定に保存する。LM StudioがOFFを広告するモデルだけ、該当要求のreasoning_effort=noneへ変換する。モデル全体の推論既定値や他の文字起こし・仕上げジョブの設定は変更しない。実機Gemmaの短い合成応答でreasoning_tokens=0を確認した。画面にも分析単位の選択を追加した。

LM Studioの構造化応答は生成制約を使う（公式: https://lmstudio.ai/docs/developer/openai-compat/structured-output ）。当日の実API記録では、入力usageはSDKテンプレート計測値+約12〜16であり、338〜1058 tokensのJSONスキーマは入力へ加算されていなかった。従来のconservative_additionは枠を二重計上するため、schema_tokensを診断記録として残しつつ、grammar_outside_contextとして計算する。安全余白512は保持し、生成上限は実測した残り枠内で決める。

制御文とデータは分離し、開発版のhandler_preloaded_compact_v1では完全な参照のパス・版・本文hashを制御側へ保持し、データ側はresource_idと参照全体のhashで結合する。パス・版の差し替え、resource_idの差し替え、本文の差し替えは検出する。単一尺度だけ他分野へ全文再送される投影の不整合も修正した。専門家の必須知識本文と適用条件は削らない。

標準プロファイルの固定区間分析を有効にし、一時DB・一時Vault・価格と操作性に関する合成会話で実モデルを手動実行している。質問は食事選択であり、原文では裏付けられない対象を含む限界条件である。Gemma追加推論OFFでは議題・全初回担当・尺度設計・尺度レビュー・最初の専門側評価まで実行できた。8K枠では同分野の過去報告を含む次の評価が予算不足となり、実モデルの全体完了・成果物保存・4Vault公開はまだ合格していない。合成応答による実MAF/実ObusSQLの完了・保存・公開と、実モデルの全体完了を区別する。

GPUはRTX 5070 12GBで空き約350MB、RAM空き約4GB。既存のGemma/Qwenはいずれも8Kで、新しいモデルインスタンスを同時に追加する余裕がない。共有Gemmaの16K/GPU比率0.8への再ロードは他のGemma処理を中断するため利用者へ確認中で、承認前の再ロードは行っていない。

### 専門側の批判応答の取りこぼし（2026-11-02、adapter 43）

その後RAM空きが約18GBへ回復したため、共有モデルの再ロードを行わず、Gemma 4 12B QATを専用の16,384 context / GPU比率0 / KVキャッシュCPUの別インスタンスで検証した。1呼出し360秒、全体3,600秒、追加推論OFF、並列1、呼出し160、タスク400、区間300秒の構成である。専用モデルは試験のfinallyで解放し、共有モデルの設定は変更していない。

最初の16K実機run_05e2d2f9a94843b485f1adbbf0927c5cは21呼出し・23タスクが全件成功し、入力予算不足を解消できた。ただし最終状態はhuman_review_requiredで、成果物保存・公開は未実施。原文で裏付けられない食事選択の質問を使った限界ケースである。この結果を分析完了・公開成功とは扱わない。出力はoutput/validation/maf-dev-real-model-20261102-gurumoji-maf-validation-20261102.jsonと同名の合成DBバックアップへ保持した。

取りこぼしは、専門orchestratorのcritique_responsesが任意件数で、提示された指摘に応答しない結果も受理された一方、Coreは個別応答を禁止される責務分離にあった。ラベルの2指摘にはdefer応答があったが、初回の指摘と古い見解への指摘は未回答のまま残った。終了時の未回答検査は維持する。

adapter 43では専門側のJSONスキーマに提示issue_id数と同じminItems/maxItemsを指定し、採否・理由・影響を各指摘へ1件ずつ返す。受理時も配送manifestのprovided_issue_idsと応答ID集合の一致・重複を検査し、省略や重複はcritique_response_missingで隔離する。deferは未解決点として保持し、合意や解決への変換はしない。上限24件を超える指摘は、既存reduce_contextで結果単位を分割し、指摘本文を切り詰めず後続バッチへ残す。原応答の自動再送や終了条件の緩和は追加していない。

初回の根拠IDなしの指摘でも専門側が明示的にdeferを返して完了できること、省略・重複を隔離すること、30指摘を結果単位で15件ずつ処理することを追加検証した。関連2ファイルは32 PASS / 12 subtests PASS。UIの既存DOM 28件もPASS。起動時ObusSQL診断の合成応答が従来harnessに不足していたため、外部接続せずdisabledを返すfixtureを補完した。入力枠不足の案内、追加推論OFF、1呼出し120/360秒の設定を画面で確認した。通常のAPI既定値は120秒を維持する。

原文に沿う比較・改善基準の質問を既定とし、実モデルの通常ケースを再実行する。実行ごとのJSON名にはrun IDを加え、失敗記録を上書きしない。全orchestration系とMAF・ObusSQL・入力計測・AI transportを含めた拡大回帰は293 PASS / 1 SKIP / 75 subtests PASS（154.31秒）。SKIPはWindowsの非特権シンボリックリンク作成制約。最終実機結果は後続へ記録する。

### 実モデルでの完了・保存・公開の確認（2026-11-02）

run_bd5638a58bf94ab2bcf86bba6562244a、adapter core-handler-prompts-43-required-critique-responses:gurumoji-maf-dev-v1で、合成の価格・操作性の会話に対し「この会話で比較や改善の基準として何が述べられているか、原文の根拠付きで比較する。」を実行した。実MAF 1.22.0と実obsipgの固定版を使い、実モデルGemma 4 12B QATの専用CPU/16K/追加推論OFFで、19呼出し・21タスクすべてsucceeded、2回のCore判断を経てstatus=completed / stop_reason=question_satisfiedとなった。所要2,341秒（約39分）。最大の実測テンプレート入力は11,520 tokensで、8Kでは出力予約と安全余白を確保できない。

completion_callback_status=completed、save_status=saved、publication_status=publishedを個別に照合した。Input・Research・Orchestrator・Visualizationの4 outcomesがすべてpublishedであり、保存だけ・一部公開・人の確認待ちを完了へ読み替えた結果ではない。出力はoutput/validation/maf-dev-real-model-20261102-gurumoji-maf-validation-20261102-run_bd5638a58bf94ab2bcf86bba6562244a.jsonに保持する。一時DB・一時Vaultの内容を既存AnalysisStoreと4writerが実際に作成し、検証終了後に一時領域を解放した。実利用者の本文・タグ・別名、runtime、.env、tokens.jsonには反映していない。

この通常ケースでは6回の専門レビューに提示された指摘はすべて0件だった。manifestと応答ID集合の一致は全件確認したが、非空の批判応答を実モデルが生成する分岐の確認ではない。非空の初回指摘、未解決deferでの完了、応答省略・重複の隔離、件数上限の分割は前記の合成回帰試験で確認している。実研究データ、大規模データ、研究結論の妥当性、実ブラウザーの視覚・キーボード操作、上流の本番用obussql-maf host、PostgreSQL・双方向同期は未検証／未接続のままである。

最後に依存整合性pip check、2つの変更JSの構文、対象差分の空白を再確認した。DOMは28 PASSで、入力枠不足の案内が完了後には残らないこと、追加推論OFF、呼出し上限120/360秒と不正値拒否を別途確認した。run.batの未指定=両方ON、ObusSQL=0かつMAF未指定=両方OFF、明示的なMAF指定の優先を4組合せで確認した。共有Gemmaの8K設定は変更しておらず、専用CPUモデルはfinallyでunloadし、共有モデルが残ることを確認した。共有モデルの再読込は本検証には不要となり、承認待ちの操作は実行していない。

作業元はkrokharu/transcription-finish-20261102 / d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486。既存の未コミット変更を保持し、コミット・push・ブランチ切替は行っていない。利用手順はmain側docs/OBUSSQL.mdに追記し、通常利用では16Kでロードしたモデルを選択して新しい分析を開始する。

### 利用者承認後の共有Gemma再ロードと再検証（2026-11-02、adapter 44）

利用者が共有Gemmaの「16K・GPU使用率80%」への再ロードを明示的に承認したため実施した。実際に設定した値はLM StudioのGPUオフロード率gpu.ratio=0.8とcontextLength=16384であり、ハードウェアの演算使用率を80%へ制限する操作ではない。元の8K/gpu.ratio=1.0/flashAttention=trueはoutput/validation/maf-shared-model-before-20261102.jsonへ保持し、ロード失敗時には元の設定へ戻す処理を先に用意した。対象モデルIDだけをunload/loadし、flashAttention=trueを維持して指定値で読み込めた。Qwenは確認時点でロードされておらず操作していない。保存済みのモデルファイル・利用者データ・認証設定を変更する操作は行わない。

adapter 43の最初のGPU試験run_3868ca051ffe4cbcb215960c90764c61では、追加分析後の最後のCore入力が12,894 tokensとなり、出力予約3,200と安全余白512を加えると16Kを222 tokens超過した。既存の根拠部分集合への縮小後も12,859で不足し、context_budget_exceededで送信前に停止した。この失敗結果・合成DBを同run ID付きのJSON/SQLiteとして保持する。停止済みrunを改変して完了扱いにしたり、予約・安全余白を削ったりしない。

adapter 44では、専門側へ個別尺度判断を委譲済みのCoreへ、未読の尺度定義の空の配送オブジェクトではなく、AI下書きであること・全体hash・result IDs・定義数・競合・read_scope=index_onlyを持つ索引を渡す。実際の尺度定義・判断条件・全専門家報告・専門家の必須知識は保存し、個別尺度を読了扱いにしない。全体欄と完全に同じタスク内の問いの重複も除いた。索引の可変リストを変更しても元カタログへ波及しないこと、異なるタスクの問いは残ること、問い・intentがない入力でも壊れないことを検証した。既存の空配列を読むconsumer契約は維持する。旧失敗DBの複製を現行モデルで推論せず再計測し、既存の根拠部分集合の配送後に12,661 + 3,200 + 512で予算内となることを確認した。保存形式・SQLカラムやソース定義の変更はない。

共有Gemmaの同じ16K/gpu.ratio=0.8で、新しいrun_3bb692dcbd914292a41e821db998c269を実行した。1呼出し120秒、追加推論OFF、並列1、区間300秒、呼出し160・タスク400の構成で、20呼出し・23タスクすべてsucceeded、status=completed / question_satisfied、completion_callback_status=completed、save_status=saved、publication_status=publishedとなった。Input・Research・Orchestrator・Visualizationの4 outcomesを個別に照合し全件published。所要782秒（約13分）。今回は実モデルで指摘1件と対応する応答1件も発生し、7回の専門レビューすべてでprovided_issue_idsと応答ID集合の一致・重複なしを照合した。前のCPU通常ケースで未実行だった非空の批判応答も、今回の実機で確認できた。

結果はoutput/validation/maf-dev-real-model-20261102-google_gemma-4-12b-qat-run_3bb692dcbd914292a41e821db998c269.jsonへ保持する。拡大回帰は295 PASS / 1 SKIP / 75 subtests PASS（141.96秒）。共有Gemmaを16K/gpu.ratio=0.8でロード済みのままとし、最終のSDK照合でも指定値を確認した。GPUメモリ使用9,666 MiB、空き2,278 MiB。Qwenや実runtime・研究者ノートへの変更はなく、公開は引き続き一時Vaultだけで検証している。アプリは新しいadapter版を読み込むため再起動し、新しい分析を開始する。

### ObusSQL main e371ae3への追従（2026-11-05）

上流 `krokharu/ObusSQL` の `origin/main` を2026-11-05に取得し、最新HEAD `e371ae3cab2b07cb527bc960a650502692982b63`（2026-10-29）を確認した。手元の同梱checkout `69728a6` は未変更を確認してからfast-forwardした。11月4日の `prepare/external-context-clean-20261104` は未統合の別ブランチなので、本接続の固定対象には含めない。

アプリの `config/requirements-obussql.txt`、`config/requirements-obussql-maf.txt` と `services/obussql.py` の両参照commitを `e371ae3` に統一した。上流の `obsipg` は `0.0.1.dev0`、`obussql-maf` は `0.1.0.dev0` のまま。上流mainにはMAF拡張が統合済みであり、読取の `MemoryBackend`、`retrieve_context`、`ReadLimits`、`PayloadBudget` と本番MAFの `NOT_READY / HOST_BINDING_UNAVAILABLE` 契約をソースで照合した。版番号だけでは旧コミットを検出できないため、利用手順に強制再導入を明記した。SQLiteカラム、Vault正本・台帳、研究者本文・タグ・別名、保存・同期・移行形式は変更していない。

隔離したWindows CPython 3.12の一時venvで同HEADのネイティブ `obsipg` wheelをビルド・導入した。一時DBと一時InputVaultの1管理ノートで候補一覧1件、検索一致1件、出典IDと読取量を確認した。開発資料ブランチの `tests/test_obussql_integration.py` を現行アプリの `src` を指定して実行し、48 PASS / 1 SKIP（3.81秒）。SKIPはWindowsのシンボリックリンク制限。MAF拡張と `agent-framework-core==1.22.0` も同じ一時venvへ導入し、診断が `available_for_preview`、MAFが `host_binding_unavailable`、`package_available=true`、`execution_ready=false` と返ることを確認した。PostgreSQL、MCP、実モデル、研究データ、本番hostでの実行は未実施。実runtime、実Vault、認証設定、待受ポートは使用していない。
現行アプリの `.venv`（CPython 3.12.9）にも同じcheckoutから `obsipg` と `obussql-maf` をwheelとして再導入した。診断は `available_for_preview` と `host_binding_unavailable`、`pip check` は依存不整合なし。起動中プロセスがあれば新コードの反映にはアプリの再起動が必要。pipの旧版退避フォルダー `.venv/Lib/site-packages/~bsipg` が残った。安全なパス確認を付けて削除を試みたが、自動承認レビューが再帰削除コマンドを拒否したため、退避フォルダーは保持している。新しいwheelの導入と診断は成功している。