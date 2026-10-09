---
note_id: design-decisions
note_type: adr-log
title: 設計判断の記録（ADR）
status: current
updated: 2026-10-08
tags:
  - gurumoji/program
  - gurumoji/design
  - gurumoji/adr
---

# 設計判断の記録（ADR）

> 復旧時の系列確認（2026-10-10）: 以下の既存ADR-126〜129は、`eb46e68793ef78e71fcae5493e6e5fa4c2354335`から保全した別系列の設計履歴です。Downloadsの実装基点`b9ee037e749748e2819e8ffa0e0faf639d6fd9f6`（adapter `core-handler-prompts-25-referenced-context`）の実装済み機能を示すものではありません。現在系列の判断は後掲の「Downloads系列の再構成記録」を参照してください。NUL破損で失われた元の最新bytesとの一致は未証明です。

### ADR-129 Coreの発注内で専門家がデータ取得hookを使う（2026-10-07）

- 状態: Windows作業ツリーで実装。関連177 unittest成功（62件と115件の別バッチ）。実データ・実モデル試験は運用記録を参照する。分析完了は未確認。
- 背景: 利用者の訂正により、分析を決めるのはCore、専門家は受け取った指示をhookで効率化する責務とする。
- 判断: Handlerの既存発注・JSON transportを再利用し、専門家が固定根拠の本文と許可された保存済み計算表を追加取得する2種のread-only hookを追加。Coreによる専門家・分析・対象範囲の判断を維持し、Jevの選択器・任意コード・新規計算経路は追加しない。
- 判断: 最初の文脈を最大12発話・12,000文字に絞り、未読範囲を明示。追加取得は最大2巡・計3モデル呼出しで、停止・総予算・入力版・Core対象範囲・保存結果hashを検査する。追加分析は従来のanalysis_requestsとしてCoreへ提案する。
- 保存/検証: 中間応答と取得receiptをtask台帳へ保存し、最終報告の根拠候補は実際に届けたIDに限定する。不正な最終応答も既存隔離経路へ保存し、修復して成功扱いしない。usageは継続呼出しごとに記録する。
- 互換性/限界: 新規runのexpert_hooks既定true、falseで従来経路。旧runの欠落設定は無効。プロンプト版8とhook版2を固定する。実モデル試験でデータ要求と報告の混在が発生したため、版2はexpert_response内のread/reportを別Schema候補に分ける。SQL列・保存先の変更と実データ移行なし。ローカルLLMでもJSON生成能力・文脈上限・専門判断の品質に依存する。
- 2026-10-08追記: 32,768 token枠で全323発話の索引を渡す再試験から、索引をevidence_idだけにし、専門家入力内の重複索引を除いた。発話本文にはutterance_idを保持し、固定正本は変更しない。独立検証の生成Schemaも実際に渡した根拠IDへ限定し、受信時の既存照合は維持する。最終試験は取得要求IDの1文字欠落で範囲検査が拒否し、recovery_required。索引配信は全文分析の完了を意味しない。
- 関連: [[20-Modules/analysis-orchestration]]、[[60-Operations/gurumoji-improvement-session]]、`tests/test_expert_data_hooks.py`。

### ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）

- 状態: Windows作業ツリーで実装。実モデル試験・制約は運用記録を参照。
- 判断: 記述統計・群間比較・相関の3専門家へ、専用Obsidian知識と入出力契約を渡す。専門家定義版2に分析案・説明のai_draft手順を追加し、既存code／researcher手順は代行しない。他分野のAI補助禁止は維持する。
- 判断: 検定ごとにLLMを増やさず、手法別ツール（記述統計、度数、クロス集計、ANOVA、Kruskal–Wallis、カイ二乗、Pearson、Spearman）をHandlerのallowlistへ接続。共通の既存Python統計エンジンで固定入力から計算し、指定手法の表を返す。任意コード・未実装検定・後から採用したラベル・部分範囲の計算は追加しない。
- 判断: analysis_requestsは提案。Coreが必要性を判断して正式intentを返し、Handlerが発注する。計算前のneeds_calculationを成功した数値結果と扱わず、計算後は同じrun・入力版・許可手法・hashを照合したcalculation_result_ids付き説明を作る。型付き数値表と説明下書きを区別する。
- 保存/互換性: 全計算表・row_id・対象集合・N/欠測/単位・run/task/result/input version/hashは既存SQLite/JSON台帳に保持。Obsidian管理ノートはIDでリンクする。SQL列変更・利用者データ移行なし。プロンプト版6・専門家bundle版2の新規runから適用し、旧runは版ガードで保護する。
- 限界: 形式・参照検査は数値に付けた説明の意味的妥当性を保証しない。人の確認と専門品質評価は必要。結果抜粋の未読行を明示する。
- 関連: [[20-Modules/analysis-orchestration]]、[[50-Analysis-Methods/10-Experts/00-Index]]、[[60-Operations/gurumoji-improvement-session]]。

### ADR-127 専門家ごとの固定知識と宣言的入出力契約（2026-10-06）

- 状態: Windows作業ツリーで実装。実モデル・未実行範囲は運用記録を参照する
- 背景: Coreから担当への発注は存在したが、専門家のObsidian知識を担当へ渡す経路がなく、保存成功だけでは専門知識の活用を確認できなかった
- 判断: 既存ExpertCatalogとAI補助許可を再利用し、run開始時に選択知識・抜粋・適用条件・入出力契約を固定する。Coreは専門家IDを選び、Handlerがその専門家の知識を渡して正式実行する
- 判断: 分野別の入力・出力項目と型は `07-Agent-Contract.md` の宣言的YAMLで指定する。生成時のJSON Schemaと受信検査を対応させ、知識・発話・許可手順の参照を照合する。人・コードの手順をAIが実施したと扱わない
- 判断: モデルの重みへ知識を学習させず、固定された知識packetを呼出し文脈として渡す。全文profileは台帳へ保存し、モデル入力は重複を省き、未読範囲を明示する。独立検証へCoreの期待結論を渡さない
- 互換性: 既存カラム・初期結果・成果物・Vault所有権を維持する。プロンプト版を更新し、旧未完runを新しい契約へ自動移行しない。個人知識は既存local_knowledge配置で解決する
- 根拠: [[20-Modules/analysis-orchestration]]、`50-Analysis-Methods/10-Experts/thematic-analysis/07-Agent-Contract.md`（別系列の歴史参照。`ac4bc6cef2e806a2bf52f503625fb7a1363c20e3`に存在するが、Downloads基点には文書・受信実装`services/expert_agents.py`とも存在しない。現在系列は[[40-Design/decisions#Downloads再構成・参照文脈（元系列ADR-127／2026-10-06）]]を参照）。検証: [[60-Operations/gurumoji-improvement-session]]

### ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）

- 状態: 採用・実装。基点 `75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、branch `krokharu/エージェント設計図改善` の未コミット変更。実データ移行・別環境反映は未実施。
- 背景: 利用者の「オブシディアン管理用エージェントを追加し、CoreやHandlerから情報を受け取り管理、基本的にデータをObsidianとリンクして配置」の依頼。
- 決定: Pythonの `ObsidianManagementAgent` を共通Handlerへ依存注入する。Coreの採用判断とHandlerの実行記録はSQLiteへ確定後に渡し、管理ノート・既存catalog/indexを `VaultRegistry` の安全な生成ノート経路で更新する。追加のLLM・自由なファイル操作・新しい分析タスクは導入しない。
- 決定: 説明・短いAI要約・索引はOrchestrator Markdown、全量台帳/表/発話はSQLite/AnalysisStoreを正本に維持し、ID・版・hash・API/artifactリンクで結ぶ。索引は各直近40件と総件数、要約1200文字までで省略を明示。完成済み固定packageのみartifact参照を載せ、未保存を保存成功へ変えない。
- 保存範囲: 新規 `obsidian_management` は既定trueで開始前にOFF可能。旧runの設定欠落はfalse、再開/管理再試行で範囲を変更しない。原文を含む4 Vault一式公開の既定OFFは維持し、管理設定と画面で分ける。管理ノートもrestricted。SQL schema追加・移行は不要。
- 所有権/復旧: 研究者所有ノートを更新しない。生成ノートの編集は既存履歴へ保存、削除は自動復元しない。status/downloadのGETは読取りだけ。管理更新失敗は独立した状態で示し、明示再試行は分析を再実行しない。封印exportは保存receiptに固定し、閲覧時のファイル状態でpackageを変えない。
- 理由/代替案: 整理のための追加AIや全データのノート複製は、再現性・保存主体・原文公開範囲を曖昧にするため不採用。アプリの保存正本とObsidianの索引を既存責務で結ぶ。開発用役割Markdownだけを置く案では実行時の受渡しが成立しないため、実コードへの接続も行う。
- 検証/影響: 自律分析129件、Vault/保存/閲覧72件、最終管理/自律分析/HTTP/公開75件、DOM29件、実Edge操作2件が成功（別バッチ・重複あり）。一時DB/Vaultと合成入力のみ、実AI・実Vault・Linuxクラウドは未実施。詳しいコマンド・文字コードによる初回失敗・既存警告は [[60-Operations/gurumoji-improvement-session]]。
- 関連: [[20-Modules/analysis-orchestration]]、[[20-Modules/obsidian-integration]]、`src/gurumoji/services/obsidian_management.py`、`vault_registry.py`、`analysis_orchestration.py`、`.agents/agents/gurumoji-obsidian-manager.md`（別系列の歴史参照。`eb46e68793ef78e71fcae5493e6e5fa4c2354335`に存在するが、Downloads基点には役割文書・実装`services/obsidian_management.py`とも存在しない。現在系列の責務は[[40-Design/decisions#Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）]]を参照）。Windows/クラウドともOS別分岐を足さず共通実装を使う。

### ADR-125 自律分析は最低3回後にCoreが終了を判断（2026-10-05）

- 状態: 採用・実装。利用者の「最低三回はループし、その後はエージェント判断」の指定をAIお任せの既定へ反映。
- 判断: 新規AIお任せrunへmin_iterations=3を固定。採用済みCore判断を永続台帳から数え、最低回数未満の通常終了は保留し、次のCoreで根拠・代替説明・批判・未解決を再検討する。以降はCoreの提案と既存レビュー契約に従う。追加タスクなしの停止を成功へ読み替えない。
- 判断: 画面/APIの既定はauto、時間/回数上限は既定なし。autoの任意回数上限は3以上。呼出し/タスク上限、手動停止、実行障害、不正応答、レビュー失敗は優先する。明示的な他モードと保存済み条件は保持する。
- 互換性: SQLite列変更・実データ移行なし。最低回数のない旧条件を後から変更しない。プロンプト版はcore-handler-prompts-4-minimum-iterations、版不一致時の復旧停止を維持する。
- 検証/限界: 関連129 unittest、DOM操作26件、隔離した実ブラウザー操作1件成功。実AIの初期試験はCore2回/批判者の旧対象版転記でreview_incomplete、3回達成/分析完了ではない。再試験の最終結果は[[60-Operations/gurumoji-improvement-session]]へ記録する。最低3回は分析品質や全原文の読了を保証しない。
- 関連: [[20-Modules/analysis-orchestration]]、src/gurumoji/analysis_orchestration.py、services/analysis_orchestration_adapters.py。基点main/2f2479ca638c569f6978bec47c509646bd92ff67の未コミット作業ツリー。
- 追検証: 同日の実AI再試験で採用済みCore3回、最低回数による2回目の終了保留と3回目のquestion_satisfiedを確認。48/323発話の限定範囲と短文question条件。試験用DBの初期化漏れを修正した後、同じ保存済みrunのHTTP200/固定成果物も確認した。全発話の読了や製品の既定questionでの安定性を保証しない。詳細は運用ノートの再試験節。

### ADR-124 分析表の型付きJSON保存とCSV共有出力（2026-10-05）

- 状態: 採用、実装・一時DB/Vaultでの関連160 tests成功。利用者の「オブシディアンに記録したうえで修正して」に基づき、実装前に記録した判断を検証後に更新。実データ移行・実Vault公開・実ブラウザー確認は未実施。
- 背景: 現行CSVはnull/空文字、数値/文字列、配列/文字列、数式対策前後の文字列を一意に読戻せない。全行のCSVが読めることは再分析の再現性を保証しない。
- 判断: 既存AnalysisStoreの新規固定runに、各datasetのtables/<name>.jsonを追加する。table_format_version=1をmanifestと再試行用pending packageへ固定する。CSVは同じ型付き値から従来通り生成し、数式対策と既存bytesを維持する。
- 判断: 表にはrun/input snapshot/revision、列順、列ごとの観測型、全行、run内の安定行IDを保存する。nullと存在しないキーを区別し、元の欠測理由・根拠ID・対象集合/分母/単位の列を保持する。入力にない意味や理由、空表の型を推測しない。
- 判断: 全表を明示的に対応付ける。result.json内の同名/類似配列を推測して重複排除すると全件性を保証できないため、今回の修正は各CSVに必ず1件の型付きJSONを対応させる。新しい独立保存庫や任意ファイル読取APIは作らない。
- 検証: 読戻し時にschema、run/snapshot/revision、行数・行ID、観測型、CSVとの一致を既存hash/manifest検証へ加える。旧CSVのみのrunは閲覧できるが、型付き表への自動復元は拒否する。検証は一時DB/一時Vaultと合成値のみ。
- 互換性/復旧: STORE_VERSION=1と旧readerを維持した版付き追加。完了済み旧run、既存hash、旧pending packageの再試行形式は変更しない。DB schema変更・実データ移行なし。rollback前には保存中runを停止/完了させ、未完の新形式pendingは対応する新版で復旧する。旧writerが新pendingを再試行できるとは扱わない。
- 代替案: CSVへの型推測・欠測補完は不採用。Parquetは容量/性能の実測上の必要が出るまで保留。
- 関連: src/gurumoji/analysis_store.py、handlers/analysis_queries.py、tests/test_analysis_storage.py、tests/test_analysis_fixed_run.py、[[30-Data/analysis-storage-v1]]。基点main/2f2479ca638c569f6978bec47c509646bd92ff67の作業ツリー。

後からAIや人がコードを読んだときに、「なぜこの構造なのか」が分かるように残す。

**ADRの番号**

| 番号 | 意味 |
| --- | --- |
| ADR-001〜099 | 既存コードとノートから復元した、採用済みの判断（`accepted`） |
| ADR-101〜 | 収束フェーズの提案・判断。各項目の状態と採用範囲を参照 |

**運用ルール**

- IDは変えない。
- 判断を置き換える場合は、旧ADRの状態を `superseded` にして、置き換え先へリンクする。
- 実装で判断が変わったら、コードと同じレビュー単位でここを更新する（[[40-Design/program-vault-rules]]）。

**各ADRの項目：** 状態、背景（Problem）、決定（Decision）、理由、代替案、結果・影響、関連コード。

---

## 採用済み（コードから復元）

### ADR-001 Obsidianとはプラグインではなく、ファイルの直接読み書きで連携する

- **状態：** accepted（復元）
- **背景：** 研究者がObsidianで読み・考察でき、Obsidianを閉じていてもアプリが動く必要があった。
- **決定：** アプリがVaultフォルダー内のMarkdownを直接読み書きする。コミュニティプラグインは必須にしない。
- **理由：** アプリの起動と独立させるため。追加プラグインのインストールを不要にするため（[[40-Design/obsidian-plan]]「外部プラグイン：必須にしない」）。
- **代替案：** Obsidianプラグインを作り、Vault APIで書き込む。Local REST API系のプラグインを使う。
- **結果・影響：**
  - `Vault.process`、`processFrontMatter`、ゴミ箱などの公式の安全策が使えない。
  - その代わりに `safe_path`、`write_atomic`、hash台帳を自前で実装した。
  - 安全策が不十分な箇所は [[40-Design/known-issues]] の OBS-* に記録している。
- **関連コード：** `analysis_store.safe_path`、`write_atomic`、`obsidian_layout.py`、`obsidian_finishing.py`、`vault_registry.py`

### ADR-002 正本はSQLiteと固定成果物で、Vaultは閲覧・考察用とする

- **状態：** accepted（復元）
- **背景：** 同じ内容がDB・JSON・CSV・Markdownに現れるため、復元の基準を決める必要があった。
- **決定：** 逐語録と条件は SQLite、分析の全行は `analysis_store` を正本とする。Vaultには要約・根拠リンク・来歴を置く。
- **理由：** Markdownの手作業による編集で、正本が壊れないようにするため。
- **代替案：** Markdownを正本にし、DBを索引にする。
- **結果・影響：** Vaultへの書き出しに失敗しても、保存自体は成功扱いにする（ADR-009）。DBへの取り込みは、明示的な操作に限る（ADR-006）。
- **関連コード：** [[40-Design/storage-policy]]、`AnalysisStore.save`

### ADR-003 アプリ専用のVaultはデータフォルダー配下に作り、利用者のVaultを探したり推測したりしない

- **状態：** accepted（復元）
- **背景：** 利用者のメインVaultに書き込むと、既存の知識ベースを壊す危険がある。
- **決定：**
  - ResearchVault は `<data>/obsidian/ResearchVault` に置く。
  - 生成Vaultは `<data>/obsidian/<英数字>` に置き、`vaults.json` に登録する。
  - `docs/program-vault` には書き込まない。
  - Documents配下など、既存のVaultは探さない。
- **理由：** 書き込み範囲を、アプリが管理するフォルダーに限定するため。
- **代替案：** 利用者が選んだ既存のVaultに書き込む。
- **結果・影響：**
  - 保存先を変えるUIがない。
  - ルートの算出がコードの複数箇所に分散した（ARCH-03）。
  - 利用者が親フォルダーを保管庫として開くと、Vaultが入れ子になる（OBS-10）。
- **関連コード：** `ObsidianLayout.__init__`、`VaultRegistry.root`、`roots`

### ADR-004 自動生成ノートはhashで所有を確認し、外部で編集されていたら上書きしない

- **状態：** accepted（復元）。実装が統一されていないため、ADR-101で見直す。
- **背景：** 研究者が生成ノートに直接追記する可能性がある。
- **決定：** 書き込み時のhashを台帳に記録し、実際のファイルと一致しない場合は上書きしない。
- **理由：** 人が書いた考察を失わないため。
- **代替案：** 生成ノートは常に上書きし、「編集禁止」と表示する。
- **結果・影響：** 台帳が4つ、競合時の挙動が4通りに分かれた（OBS-04）。
- **関連コード：** `VaultRegistry._write`、`AnalysisStore.write_note`、`ObsidianLayout.managed_note`

### ADR-005 AIの生成物は常に新しいパスへ保存し、人が編集中のノートを置き換えない

- **状態：** accepted（復元）
- **背景：** AI仕上げの結果で、研究者が編集した全文やアウトラインを消してはならない。
- **決定：** アウトライン・仕上げ結果・仕上げ後のアウトラインは `履歴/仕上げ/…-<run>.md` として毎回新しく作る。現在の版はリンクで切り替える。
- **理由：** 人の編集とAI出力の競合を、構造的に避けるため。
- **代替案：** 既存ノートに差分を適用する。
- **結果・影響：** 履歴ノートが増える。状態ノートだけは毎回上書きされる（アプリ所有）。
- **関連コード：** `ObsidianWorkbench.execute`、`save_note`

### ADR-006 Obsidianの内容をアプリへ反映するのは「結果をアプリへ反映」の明示操作だけとする

- **状態：** accepted（復元）
- **背景：** 双方向同期では、ループや意図しない上書きが起きる。
- **決定：**
  - 反映は、操作ノートでチェックしたときだけ行う。
  - 反映の前に、次の3点を再確認する。
    - revision が一致すること
    - 元ノートの内容fingerprintが一致すること
    - 反映中に結果ノートが変わっていないこと
  - 研究メモなどの自動取り込みはしない。
- **理由：** データ保全を優先し、同期ループを防ぐため。
- **代替案：** ファイル監視で自動的に取り込む。
- **結果・影響：** テーマ同期はDBへ取り込まないが、テーマノートへの書き込みはある（OBS-01）。研究メモの差分取り込みは Planned。
- **関連コード：** `ObsidianWorkbench.poll_once`、`execute`、`check_sources`、`run_obsidian_finishing`

### ADR-007 4つのVaultは相互にリンクせず、IDで対応付ける

- **状態：** accepted（復元。最新版`2f13f98`に実装を収録）
- **背景：** 役割の異なるVaultを、独立して開けるようにしたい。
- **決定：** Vaultをまたぐ `[[…]]` は書かない。`conversation_id`・`input_snapshot_id`・`run_id`・`artifact_id`・`note_id` で対応付ける。
- **理由：** Vaultをまたぐリンクは、Obsidianでは未解決リンクになるため。
- **代替案：** 1つのVaultにフォルダーを分けて置く。
- **結果・影響：** 詳細は [[30-Data/four-vaults-v1]]。
- **関連コード：** `vault_registry.py`

### ADR-008 Software Vault（このVault）はGitで管理し、アプリからは書き込まない

- **状態：** accepted（復元）
- **背景：** プログラムの資料と、研究データを混ぜない必要がある。
- **決定：** `docs/program-vault` は `VaultRegistry._write` で書き込みを拒否する。`.obsidian/` は `.gitignore` で除外する。
- **理由：** 資料をコードと同じレビュー単位で管理するため。個人の設定を共有しないため。
- **代替案：** 資料もアプリが生成する。
- **結果・影響：** 資料の更新は、人またはAIが手作業で行う（[[40-Design/ai-development-rules]]）。
- **関連コード：** `vault_registry.GENERATED`、`docs/program-vault/.gitignore`

### ADR-009 Vaultへの書き出しに失敗しても、文字起こしや編集の保存は失敗させない

- **状態：** accepted（復元）
- **背景：** Vaultのロックや競合で、正本の保存が止まると困る。
- **決定：** Vaultへの書き出しの失敗は、警告ログまたは `vault_status` に記録し、保存は成功として返す。後から再試行できるようにする。
- **理由：** ADR-002 により、正本はDBと成果物だから。
- **代替案：** DBとVaultをまとめてロールバックする。
- **結果・影響：** 失敗が画面から見えにくい（OBS-09、OBS-15）。
- **関連コード：** `publish_input_vault`、`AnalysisStore.publish_vaults`、`refresh_archive_index`、`POST /api/analysis/runs/<id>/vault`

### ADR-010 新規の文字起こしは「Obsidianで仕上げる」を既定とする

- **状態：** accepted（復元）
- **背景：** AI校正の前に、研究者が原文を確認・編集できるようにしたかった。
- **決定：** `finish_in_obsidian` の既定をTrueにする。ジョブ内のAI仕上げはAPI互換のために残し、UIでは校正のチェックを非表示にする。
- **理由：** AIによる変更を、人が確認したうえで反映するため。
- **代替案：** ジョブ内で自動校正する。
- **結果・影響：** AI仕上げが2経路になった（ARCH-07）。既定値が3か所に書かれている（CFG-03）。
- **関連コード：** `JobOptions.finish_in_obsidian`、`create_job`、`run_transcription_job`、`index.html`

---

## 提案（収束フェーズ）

### ADR-101 Vaultへの書き込み判定を1つの関数に統合する

- **状態：** proposed
- **背景：** 書き込み主体が5つあり、競合時の挙動がそれぞれ異なる（OBS-04）。
- **決定（案）：**
  - `VaultRegistry._write` の方式を、全ての書き込みに適用する。
    - 予定hashを記録してから書く。
    - 外部で編集されていれば `conflict` にする。
    - 削除・移動されていれば `missing` にし、再作成しない。
    - 結果を索引とログに出す。
  - `managed_note`・`AnalysisStore.write_note`・`ObsidianWorkbench.save_note` は、この関数を呼ぶだけにする。
- **理由：** 「人の編集を上書きしない」ことを、ノートの種類によらず保証するため。
- **代替案：** 各書き込み主体を個別に修正する（重複が残る）。
- **結果・影響（予定）：**
  - ナビゲーションノートが削除されたとき、再作成しない方針に変わる（`missing` を表示し、ボタンで再作成）。
  - 台帳の統合は別のADRで決める。
- **関連コード：** 上記の関数群

### ADR-102 人が所有するノートは、変更するキーと管理区間だけを更新し、書く直前に再確認する

- **状態：** proposed
- **背景：** テーマ同期と仕上げノートの装飾が、ノート全体を再生成して上書きしている（OBS-01、02、07）。
- **決定（案）：**
  - 変えるのは、プロパティのうち必要なキーの行と、`<!-- gurumoji:… -->` で囲んだ区間だけにする。
  - 書き込む直前に、読み込んだときのhash（とmtime）が変わっていないか確認し、変わっていれば書かずに `SKIP_CONFLICT` を記録する。
  - YAMLを解析できない場合や、未対応の形式の場合は書かない。
- **理由：** Obsidianの `processFrontMatter` や `Vault.process` に相当する安全性を、外部アプリで確保するため。
- **代替案：** YAMLのround-trip対応ライブラリを追加する（依存が増えるため、別途判断する）。
- **結果・影響（予定）：** アプリのタグ名前空間を移行する必要がある（例：`graph/*` → `gurumoji/graph/*`。移行は別ADR）。

### ADR-103 既存のVaultの `.obsidian` は、初回作成時と明示操作のとき以外は書かない

- **状態：** accepted（2026-09-25。明示操作の画面は未実装）
- **背景：** `configure` が、利用者の表示設定を繰り返し変更している（OBS-03）。
- **決定：** `.obsidian/` がまだないVaultを初めて整えるときだけ、既定の設定（コアプラグイン、CSSスニペットの有効化、グラフ、ブックマーク、ワークスペース）を書く。判定結果は `interviews.json` の `obsidian_settings`（`initialized`／`existing`）に1回だけ記録し、以後の同期では書かない。例外はアプリ自身のブックマークグループで、利用者が残している間だけ、内容が変わったときに更新する。削除されたグループは戻さない。既存のVaultに推奨設定を適用する「推奨表示設定を適用」操作は、収束計画どおり必須にせず後続とする。
- **理由：** 利用者の設定と、Obsidianが起動中に持っている設定を尊重するため。

### ADR-104 ファイル名とパスの生成規則を1つにする

- **状態：** proposed
- **背景：** 名前を安全にする正規表現が複数あり、長さの確認もない（OBS-14）。
- **決定（案）：** 次をまとめて扱う1つの関数を、既存の `obsidian_layout` に置く。
  - Windowsの禁止文字 `\ / : * ? " < > |` と制御文字
  - 末尾のドット・空白
  - 予約名
  - フルパス長の上限
  - 同名ファイルの回避（上書きせず、別名にする）
  - 日本語の保持
- **理由：** 保存に失敗したり、別のノートを上書きしたりすることを防ぐため。

### ADR-105 Obsidianの操作を監査ログに残す（本文は残さない）

- **状態：** proposed
- **背景：** スキップや書き換えを後から追跡できない（OBS-15）。
- **決定（案）：** `<data>/obsidian_layout/` にJSON Lines形式で記録する。
  - 記録する項目：日時、Vault、相対パス、操作、前後のhash、理由
  - 操作の種類：`CREATE`、`UPDATE`、`SKIP`、`CONFLICT`、`MISSING`、`MIGRATE`、`ARCHIVE`
  - 本文・話者名・APIキーは書かない。

### ADR-106 新機能を凍結し、「追加より統合」を開発ルールにする

- **状態：** proposed（本ノート作成時点から運用する）
- **背景：** 機能を順番に追加してきた結果、同じ目的の実装や入口が重複した（ARCH-07、UI-01）。
- **決定（案）：** [[40-Design/ai-development-rules]] に従う。次の優先順に選ぶ。
  1. 既存機能を拡張する
  2. 既存機能に統合する
  3. 小規模に新しく実装する
  4. 新しいシステムを作る

### ADR-107 フロントエンドのAPI呼び出しは `apiFetch` に限定する

- **状態：** proposed
- **背景：** 生の `fetch` によってCSRFヘッダーが漏れた（BUG-01）。
- **決定（案）：** 全てのJSで `apiFetch` を使う。テストで生の `fetch(` が使われていないことを検査する。

### ADR-109 人のノートを自動更新せず、生成情報の保存先を分ける

- **状態：** accepted、実装済み（2026-09-14）
- **背景：** 優先課題の修正依頼を受け、テーマ同期・仕上げ同期による人の編集の消失と、管理状態を失った後の既存ノート上書きを防ぐ。
- **決定：** テーマ本文・プロパティと既存の仕上げノートを自動更新しない。テーマの関連情報はアプリ管理の`40-研究/テーマ関連/<hash>.md`へ生成し、仕上げの最新参照は概要・状態ノートで示す。既存の`write_atomic`に排他的作成を追加し、状態以外の仕上げノート作成に適用する。管理状態がなく初期パスにノートがある場合は停止する。
- **理由：** 書き込み直前のhash再確認だけでは、外部エディターによる直後の編集を保護できない。人のノートへ書き込まなければ、コメント・独自タグ・YAML表現・改行をそのまま保持できる。既存モジュールを拡張し、新しい保存基盤は作らない。
- **代替案：** ADR-102の管理区間だけの更新、YAMLのround-trip化、既存ノートを読み直して上書き。今回の人のノート保護には採用しない。ADR-102の該当部分に対して本判断を優先する。
- **結果・制約：** 人のノートのタグは作成時点のまま。過去に生成したテーマ内の関連欄は消さない。ハードリンク非対応の保存先では安全に停止し、上書きへ切り替えない。全生成ノートの競合処理統一や状態表示は未完了。
- **検証：** CRLF・YAMLコメント・アンカー・独自タグのバイト一致、不正YAMLを持つ人のノートの保持、状態消失後の再実行、排他的作成直前の同名ファイル発生を一時Vaultで確認。[[40-Design/convergence-plan#優先修正の実装（2026-09-14）]]。

### ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない

- **状態：** accepted（2026-09-14、課題の選別のみ。コード変更・設定移行・ファイル削除の採用ではない）
- **背景：** 利用者から、プログラム用Obsidianに格納した問題点の取捨選択を依頼された。39件の既知の問題と29件のUI/UX項目には、重複、未計測のリスク、用途の違う機能の統合案が混在していた。
- **決定：** [[40-Design/convergence-plan#今回の取捨選択（2026-09-14）]] を対応順の正本とし、最優先4件、優先13件、後続8件、統合7件、保留36件に分ける。問題ID・元の記述を残して選別欄を追加し、実装状態とは分けて管理する。
- **理由：** テーマノートのコメント・独自タグ消失と、管理状態のない既存全文の上書きを一時Vaultで再現した。比較POSTのCSRFヘッダー欠落もコードに残るため、実害に近い経路を先に扱う。全体移設やデザイン統一を先に行う必要はない。
- **代替案：** 全項目を旧Phase 0〜6の順に実装する、低優先の項目を削除する、一覧の重要度だけで並べる。いずれも採用しない。未計測項目と元の指摘は再検討できるよう保つ。
- **結果・影響：** ADR-101〜107は引き続き提案であり、一括採用しない。ADR-102の書き込み直前hash確認を排他制御と同等とは扱わない。ADR-107はまず比較機能の修正に絞り、`apiFetch` 本体まで禁止するような一律の文字列検査は採用しない。全保存停止、一律の保存パネル集約、削除行数を基準にした完了条件も採用しない。
- **関連コード・検証：** `static/interview-comparison.js:runComparison/saveComparison`、`app.py:enforce_request_security`、`obsidian_layout.py:sync_themes/sync_finishing/decorate`、`obsidian_finishing.py:prepare/save_note`。再現確認は一時フォルダーで実施。実ブラウザー・同時編集の競合は未確認。コードと実データは変更していない。

### ADR-110 発話の数値化とjamovi型統計の自動実行を、既存の分析層の拡張として段階的に実装する

- **状態：** proposed（計画第2版の方針、2026-09-15。着手の順序は利用者の委任により人格パネルで決定。実装は未着手）
- **背景：** 逐語録をLLMやTransformerなどで数値化し、jamoviで実行できる検定を自動で行いたい。現在の統計は発話単位の4種類の検定だけで、AI由来の変数を検証して検定に使う仕組みがない。
- **決定（案）：**
  - [[40-Design/quantification-statistics-plan]]に従う。検定の選択、統計量、報告文の数値はコードが作り、LLMは数値化の候補だけを作る。AI由来の変数は、妥当性ゲートを通してから確認的な検定に使う。
  - 順序は、進行中の作業の確定 → Phase 0 → OBS-18 → Phase 1a → 1b → 2 → 3 → 4 → 5。
  - 検定の計算は、新しいモジュール`statistical_tests.py`にまとめる。
  - 複数会話の推測統計は、別の実行種別`study_statistics`にする。
- **理由：**
  - 検定の計算は`research_analysis`、`transformer_analysis`、`app`（事前アンケート、複数会話）の3か所から使う。1つのモジュールにまとめると、カイ二乗の2実装とブラウザー側の相関計算を置き換えられる（ADR-106の統合の条件）。
  - 新しい実行記録も生成Vaultへ出力するため、書き出し失敗の集約（OBS-18）を先に直す。
  - `interview_comparison`は2〜8件の記述的な比較という契約を持つため、多数の会話の推測統計と混ぜない。
- **代替案：** LLMに検定まで任せる。LLMの機能から始める。検定を`research_analysis.py`の中に置く。`interview_comparison`を拡張する。
- **結果・影響：** Phase 0で保存契約、golden値、依存、ライセンスを先に固める。議論の記録はPersonaVaultの`DLB-20260915-quantification-statistics`（IDで参照）。
- **関連コード：** `research_analysis._statistics_analysis`、`transformer_analysis._backchannel_test`、`static/app.js:speakerSurveyCorrelation`、`app.build_interview_comparison`、`analysis_method_registry.SEPARATE_RUN_METHODS`

### ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする

- **状態：** accepted（利用者の決定、2026-09-15。ボタンと送信条件の詳細は人格パネルで具体化。実装はPhase 3）
- **背景：** AI数値化はトークンを多く使う。文字起こしなどの操作と一緒に実行すると、利用者が意図しない費用が発生する。
- **決定：**
  - クラウドLLM（OpenAI、Gemini）への逐語録の送信を認める。
  - 「文字起こし」「AIで数値化」「統計を実行」を別のボタンにし、トークンを使うのは「AIで数値化」だけにする。
  - AI数値化は試行と全件の2段階にし、送信前に送信先、発話数、推定トークン、上限、同意の状態を表示する。
  - 同意しなかった話者の発話は送らず、除外した件数を結果に記録する。同意が未確認の話者を含む場合は警告し、確認を記録する。
  - 話者の氏名・仮名・所属は送らない。同じ判定はキャッシュから再利用し、失敗したバッチだけ再実行する。
- **理由：** 費用を事前に予測でき、統計は何度でも無料で再実行できる。送信の判断を、利用者の明示の操作に限る。
- **代替案：** 文字起こしジョブの中でAI数値化まで実行する。1つのボタンで数値化と統計をまとめて実行する。
- **結果・影響：** 統計の実行・保存・Vault出力がAIを呼ばないことをテストで確かめる。既存のAI見解は話者名（`speaker_name`）を送っており、この決定に揃えるかは別の課題として残す。
- **関連コード：** `templates/index.html`の新規作成フォーム（`finish_in_obsidian`、`ai_provider`）、`app.call_ai_json`、`analysis_insights.create_ai_insights`

### ADR-112 統計の依存にstatsmodelsを追加する

- **状態：** accepted（利用者の決定、2026-09-15。`config/requirements.txt`への追加はPhase 0）
- **背景：** SciPyだけでは、回帰、反復測定・要因の分散分析、GEE、混合モデルを実装できない。
- **決定：** statsmodels 0.15系を依存に追加する。importは関数内で行い、Webの起動を遅らせない。
- **理由：** BSD-3-Clauseで、配布条件（ADR-113）に合う。2026-09-15の`pip install --dry-run`で、0.15.0はnumpy 2.2.6、SciPy 1.18.1、pandas 3.0.3を変更せずに入り、追加されるのはpatsy 1.0.3（BSD-2-Clause）、formulaic 1.2.2（MIT）、interface-meta 2.0.1（MIT）だけと確認した。
- **代替案：** pingouin（GPL-3.0で、ADR-113の依存の方針に反する）。検定をすべて自前で実装する。
- **結果・影響：** セットアップのテストと、READMEの依存の記載を同じ変更で更新する。

### ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る

- **状態：** accepted（利用者の方針「使っているライブラリに即した配布条件」に基づき、人格パネルで決定、2026-09-15。`LICENSE`・`THIRD_PARTY_NOTICES.md`の作成と著作権者名の確認はPhase 0）
- **背景：** リポジトリにLICENSEファイルがなく、配布条件が決まっていない。
- **決定：**
  - 本体のコードをMITライセンスにし、第三者ライセンスの一覧を付ける。
  - プロセス内でimportする依存は、許容型のライセンス、改変しないMPL-2.0、動的リンクのLGPLに限る。GPL・AGPLのライブラリはimportしない。
  - モデルの重みと参加者データは、配布物に含めない。
  - `.venv`やインストーラーを配布する場合は、imageio-ffmpegが同梱するFFmpeg（`--enable-gpl --enable-version3`のGPLv3ビルド）のライセンス文と、対応するソースの入手方法を付ける。
- **理由：** 直接の依存はすべてBSD・MIT・Apache-2.0で、Whisper、faster-whisper、CTranslate2、GiNZA、spaCyなど主要な依存がMIT。MITはこれらすべてと両立し、GPLの外部ツールと組み合わせる余地も残す。
- **代替案：** Apache-2.0（特許の条項はあるが、GPL-2.0だけのソフトと結合できない）。GPL-3.0（現状の依存からは必要ない）。
- **結果・影響：** 依存を追加・更新するときは、ライセンスの確認と一覧の更新を同じ変更で行う。`.venv`にあるPySide6（LGPL-3.0／GPL）は、どのパッケージにも必要とされず、コードでも使っていないため、配布物に含めない。確認した一覧は[[40-Design/quantification-statistics-plan]]の12章。

### ADR-114 議論用の人格をPersonaVaultに置き、OrchestratorVaultと用途を分ける

- **状態：** accepted、作成済み（2026-09-15。アプリには未登録）
- **背景：** 利用者が、この手段を議論する人格用のObsidianを求めた。設計上のOrchestratorVaultは、分析手法カードと実行記録を保存する場所で、人格のプロフィールや長期記憶を置く場所ではない。実データでもOrchestratorVaultは未生成だった。
- **決定：**
  - `<data>/obsidian/PersonaVault`を手作業で初期化する。人格のプロフィール（`10-Personas`）、パネル（`20-Panels`）、議事録（`30-Deliberations`）、人格ごとの記憶（`40-Memory`）を置く。
  - アプリは読み書きせず、`VaultRegistry`にも登録しない。記憶と議事録は追記だけにする。
  - 研究データ、発話本文、参加者の情報、秘密情報、個人PCの絶対パスは書かない。
- **理由：** 手法カードと実行記録（アプリが管理）と、人格の定義と議論（人とAIが手作業で更新）では、書き込む主体と更新の規則が異なる。
- **代替案：** OrchestratorVaultに人格を置く。Software Vaultのフォルダーに置く。Git管理の独立したVaultを`docs/`に置く。
- **結果・影響：**
  - `runtime/`はGit管理外のため、人格の定義と議論はGitに残らない。バックアップは`<data>`一式と同じ扱いにする。
  - `<data>/obsidian`自体がVaultとして開かれた痕跡があり（OBS-10）、PersonaVaultもその内側になる。Obsidianでは`PersonaVault`フォルダーを直接開く。
  - [[30-Data/four-vaults-v1]]への追記は、同じ資料を変更中の作業が確定した後に行う。アプリから参照する場合は、別のADRで決める。
- **関連：** PersonaVaultの`PNL-quantification-statistics`、`DLB-20260915-quantification-statistics`（IDで参照）

### ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む

- **状態：** accepted、実装済み（2026-09-16）
- **背景：** 分析方針（`build_focus_group_analysis_plan`）は、どの手法を選んでも同じ汎用の手順を示し、手法ごとの前提・適用条件・禁止事項・品質基準を持っていなかった。手法の知識は `50-Analysis-Methods` の手法ノートに実装の観点でまとめられていたが、方法論の文献の確認範囲と査読状態は記録されていなかった。
- **決定：**
  - 分析手法ごとの専門家定義（17人）を `docs/program-vault/50-Analysis-Methods/10-Experts/<専門家>/` に置き、`01-Expert.md` の「実行定義」（YAML）を正本にする。文献ノートは `20-Literature`、全専門家に共通する規則は `08-Common-Knowledge`、調査の記録は `30-Research-Logs` に置く。
  - `src/gurumoji/method_experts.py` を新設する。分析設定の主手法と、分析方針の補助手法の専門家だけを読み込み、実行定義の適用条件を登録済みの判定でコード評価する。専門家のノートと参照文献のノートから知識hashを計算する。
  - 分析データ（`group_analysis_for_row`）に `experts` を加え、分析方針の手順を主の専門家の手順に置き換える。分析レポートに専門家の確認の節を加える。保存記録（`archive_group_analysis`、`archive_interview_comparison`）では、結果を出した手法の結果に担当専門家の確認を付け、`algorithms.experts` に知識hashを残す。保存する手法ノートの「限界と追加確認」には、担当専門家の判定、満たさない条件、示してはいけない結論、文献IDを加える。
  - AI見解は、研究者が主手法を選び、その専門家定義がAI補助を許可し、分析を始めない条件がない場合だけ専門家モードで生成する。出力には許可された手順の段階IDと、その段階の文献IDを必須にし、サーバーで検証する。使える文献IDは、文献ノートが存在するものに限る。KJ法・計量テキスト分析を主手法にした場合、主の専門家の分析を始めない条件がある場合、AI下書きの段階の根拠となる文献ノートがすべて見つからない場合は生成しない（409）。主手法が未選択（`auto`）の場合は従来どおり手法に依存しない下書きとする。
  - 専門家モードの入力fingerprintには専門家の知識hashを含める。未選択（`auto`）の場合のfingerprintは変えない。
  - 実行時にWeb検索や文献の再取得は行わず、AIには専門家の短い指示（`brief`）と段階ID・文献IDだけを渡す。
  - 一覧と詳細のAPI：`GET /api/analysis/experts`、`GET /api/analysis/experts/<expert_id>`。画面は既存の「対象データの確認と分析方針」パネルに専門家の確認を表示する。
- **理由：**
  - 手法の知識の既存の置き場所がSoftware Vaultの `50-Analysis-Methods` で、Gitで版を管理でき、アプリが読み取れる。
  - PersonaVault（ADR-114）は議論用でアプリは読み書きしない。OrchestratorVaultは生成物の保存先で、人が書く知識の正本に向かない。
  - 新しい依存を加えない（PyYAMLと `obsidian_layout.unpack` を再利用）。
  - 判定を登録済みの名前だけに限り、ノートに書かれたコードを実行しない（[[40-Design/method-rules]] の宣言的な登録の方針）。
- **代替案：** 専門家の知識をコードの定数にする（研究者が読めず、文献との対応を追えない）。Vault全体や文献本文をAIに渡す（トークンが増え、未確認の内容が混ざる）。実行ごとにWeb検索する（再現性がなく、外部送信が増える）。
- **結果・影響：**
  - 研究者が主手法を選んで生成した既存のAI見解は、この変更後に一度「更新が必要」になる。
  - 専門家定義を変えたら `definition_version` を上げ、知識の確認日を更新する。登録の規則は [[40-Design/method-rules]] の「専門家定義の登録」。
  - `docs/program-vault` がない配布形態では、専門家の確認は「利用不可」になり、AI見解は手法に依存しない下書きとして動く。
  - 同じ入力の保存は既存の記録を返すが、専門家の知識hashは保存記録の同一性（`algorithms`）に含まれるため、ノートを更新した後の保存は新しい記録になる。
  - テスト：`tests/test_method_experts.py`、`tests/test_method_expert_samples.py`（架空のサンプルによる検証。記録は [[50-Tests/method-expert-sample-verification]]）。
- **関連：** [[50-Analysis-Methods/10-Experts/00-Index]]、[[50-Analysis-Methods/08-Common-Knowledge/04-AI-Assistance-Boundaries]]、[[50-Analysis-Methods/30-Research-Logs/00-Index]]

### ADR-116 分析手法ごとの画面（手法別タブ）と、手法別の状態API

- **状態：** accepted、実装済み（2026-09-16）
- **背景：** 分析画面は「自動分析」「設定・手動分析」の2モードで、手法の結果がパネルとして長く並ぶ。どの手法が結果を出せたのか、担当専門家（ADR-115）の判定がどうかを手法ごとに見る場所がなかった。計算系の専門家の判定は保存記録にしか出ていなかった。
- **決定：**
  - 分析画面に3つ目のモード「手法別」を追加する。既存2モードの内容と並びは変えない。
  - 手法別モードは、手法の一覧（[[40-Design/method-rules|登録済みの手法]]の分類 `METHOD_GROUPS`）と、選んだ手法の詳細（結果の状態、担当専門家の確認、結果パネル、限界、CSV）を表示する。一覧には手法ごとの判定（結果あり・条件を満たす／要確認／この条件では使わない／結果なし／担当専門家なし）と理由の先頭を出し、上部に件数をまとめる。
  - 結果パネルは作り直さない。既存の描画が作るパネルに `data-analysis-method` を付け、手法別ビューはその手法のパネルだけを取り出す。
  - 状態は `GET /api/library/<id>/analysis/methods` が返す。`method_results` の結果に `method_experts.method_overview` の確認を付け、専門家の定義は手法ごとに重複させず `experts` にまとめる。
  - 結果のない手法には「結果への判定」ではなく「実行前に満たす条件」を示す（`expert_scope`）。専門家を置かない機能には、その理由を返す。
  - 文脈検索とAI仕上げは、その画面に結果がないため、状態と実行場所だけを示す。
- **理由：**
  - 既存の2モードを壊さずに、手法ごとの確認を1画面にまとめられる。既存のUIテストにも影響しない。
  - パネルにタグを付ける方式なら、表示の二重実装を避けられる。
  - 「結果があるときだけ結果への判定を出す」というADR-115の規則を、画面でも守れる。
- **代替案：** 自動分析の並びを手法別に組み替える（既存の見え方が大きく変わる）。分析画面全体を手法別に置き換える（設定・手動の作業動線が壊れる）。手法別の判定を分析データに常に含める（全専門家を毎回読み込むことになり、ADR-115の「必要な専門家だけ読む」方針に反する）。
- **結果・影響：**
  - 手法別モードを開いたときだけ、一覧に出る手法の担当専門家を読み込む。AIへ渡す知識は従来どおり主手法の専門家だけ。
  - 分析条件を保存すると手法別の状態は取り直す。画面に再取得ボタンもある。
  - テスト：`tests/test_analysis_method_view.py`（APIと、実ブラウザーでの表示）。
- **関連：** ADR-115、[[50-Analysis-Methods/10-Experts/00-Index]]、[[20-Modules/module-map]]

### ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する

- **状態：** accepted、実装済み（2026-09-16、2026-09-25に最新版`2f13f98`へ収録）
- **背景：** 新規作成の詳細設定（単語登録、AIエフォートなど）が常に開いており、手順表示がデスクトップ4段階・左ナビ6項目・スマホ4ステップの3種類あった（UX-05）。結果画面は1ページに議事録から発話編集までが縦に並び（UX-02）、移動ボタンが2か所にあり（UX-03）、表示中の画面がURLに残らなかった（UX-01）。処理中の進捗カードは画面をまたいで表示され（UX-16）、CPU/GPU表示は3か所にあった（UX-09）。部分修正を重ねても導線の問題が残るため、利用者から画面構造の全面的な見直しを許可された。
- **決定：**
  - 上部バーの4タブ（新規作成・処理済みデータ・分析・可視化・話者管理）と、1件の作業画面を画面の単位にする。各画面にハッシュのURL（`#/new`、`#/data`、`#/data/<id>`、`#/analysis/<id>`、`#/speakers`）を持たせ、`popstate` で戻る操作に対応する。旧 `?view=`／`?item=` は初回表示で置き換える。
  - 新規作成は「ファイル → 設定 → 開始」の3ステップにし、デスクトップとスマホで同じ手順表示を使う。設定は要約と「変更」ボタンで示し、詳細パネルは閉じた状態で置く。
  - 作業画面は「発話の確認・編集」「会話・話者」「議事録・アウトライン」「ファイル・管理」のタブに分け、保存バーは保存とObsidianでの仕上げの2つだけにする。
  - トークン・モデル・マシン診断は「接続と処理装置」ダイアログにまとめ、処理中の状況は上部バーのチップで示す。
  - 実行中ジョブのIDを表示中データのIDと分け、別画面で作業中に完了しても作業中のデータを置き換えない。
- **理由：** API・保存形式・フォーム項目名・既存の要素IDを保つことで、バックエンドと4つの補助スクリプト（分析内容、保存履歴、比較、AIエフォート）を変更せずに再利用できる。新しい依存やフレームワークを加えない。
- **代替案：** 既存画面のCSS調整と並べ替えだけで済ませる（常時表示の設定と重複導線が残る）。SPAフレームワークへ移行する（依存追加と全面的な書き換えが必要）。デスクトップとスマホに別フォームを持つ（手順表示の不一致が再発する）。
- **結果・影響：**
  - 画面から外した部品のID（`processed-data-hub`、`show-library-list-button`、`show-library-analysis-button`、`result-context-name`）を参照する外部スクリプトは動かない。リポジトリ内に参照は残していない。
  - 画面構成と旧機能の移動先は [[20-Modules/ui-screens]]。解消した問題は [[40-Design/ui-ux-issues]] の状態欄。
  - テスト：`tests/test_ui_defaults.py`（`test_redesigned_navigation_routes_and_item_workspace` ほか）、`tests/test_browser_e2e.py`。
- **関連：** [[40-Design/ui-ux-issues]]、[[20-Modules/ui-screens]]

### ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る

- **状態：** accepted（2026-09-20の設計方針、未実装）
- **背景：** 利用者から、LLM分析専用オーケストレーター、Jev／LLMの手法・結果形式の事前定義、疑似人格どうしの相談による型の作成、クロス集計以外の後続分析への接続を求められた。
- **決定：**
  - 統括・手法・型・後続分析を役割として分け、必要な担当だけが上限付きで相談する。同じローカルLLMを順に使える。Jevは選択肢判定を担当し、型生成や議論のモデルとして扱わない。
  - 入出力schemaに、意味・単位・尺度・欠測・根拠・接続条件を加えた手法別契約を版管理する。先に決めるのは結果の形式であり、分析の結論ではない。
  - 相互指摘と異論を残し、コードの検証・試行・採用を経て実行する。既存テンプレートの設定内では自動採用でき、新しい概念・尺度・コードブックの採用は研究者が決める。合意やschema適合と、科学的妥当性を区別する。
  - 既存レジストリ・登録票・AnalysisStoreを拡張する。観測表と主張集合から始め、関係表・系列・ベクトルへ広げる。後続のrunner／adapterが未実装なら利用不可とする。
  - 相談・型・結果を別のartifact／実行記録として保存し、OrchestratorVaultには既存経路で要約を公開する。採用済み契約では再相談を省く。
- **理由：** 出力の再利用条件を実行前に明確にし、LLMによる相談を実行可能性と妥当性の確認につなげる。表の作成やクロス集計だけに処理を固定しない。
- **結果・影響：** 再編計画の「LLM同士の合議を初期対象外」とする方針を、FLOW-5bの限定的な相談へ変更する。ADR-115の専門家知識の正本とAI補助制約、ADR-114のPersonaVaultを自動読み書きしない境界は維持する。構造再編とは別の版付き機能拡張として実装する。
- **関連：** [[40-Design/core-handler-routing-reorganization-plan]]、[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]、[[40-Design/method-rules]]、[[40-Design/quantification-statistics-plan]]

### ADR-118 分析UIを、結果閲覧・比較・計画・データ出力の作業単位へ整理する

- **状態：** accepted（2026-09-20の設計方針、未実装）
- **背景：** 利用者から、多様な分析を見る現行UIが不親切であり、再編計画にUI設計も含めるよう求められた。現行の自動／手動／手法別切替は、実行版を横断した結果比較や追加分析の入口を十分に表現しない。
- **決定：** 「結果を見る／比較する／分析を組む／データ・出力」を分析画面内の主入口にする。結果は検索・形式・手法・状態で探し、選択したrunの固定結果を中央に表示する。根拠は開閉式のペインで確認し、結果から比較・追加分析へ移る。
- **結果・影響：** ADR-116の手法別UIは既存部品・状態APIとして再利用し、移行後は新入口へ統合する。上部ナビ、既存URL・根拠リンク、未保存確認は互換維持する。旧表示は移行中の戻り口として残し、新旧の全結果を二重描画しない。表示・比較ではAIを実行せず、計画・試行・実行を分ける。UI-0〜4として段階導入し、型・相談・履歴の不足APIは各FLOW段階と接続する。
- **関連：** [[40-Design/core-handler-routing-reorganization-plan]]、[[20-Modules/ui-screens]]、[[40-Design/ui-ux-issues]]

### ADR-119 文字起こしの外部連携を `app.py` から分離する

- **状態：** accepted、着手済み（2026-09-22）
- **背景：** `app.py` にAI通信、AI仕上げ、音声前処理、ASRの発話整形、出力生成が同居し、単一ファイルが肥大化していた。今回の目的は互換層を増やすことではなく、`app.py` の実装行を減らすことである。
- **決定：** AI通信は `services/ai/client.py`、AI整文・Jev・アウトラインは `services/ai/transcript_finishing.py`、ffmpeg音声前処理は `services/transcription/audio.py` へ置く。アプリ側は設定値と実行時依存を組み立てるだけにし、移設済みの旧実装を残さない。残る発話整形、議事録、字幕・出力、感情推論、文字起こしrunnerも同じ規則で段階的に移す。
- **理由：** Flask、SQLite、外部AI、ffmpeg、ジョブ状態の依存を一つのモジュールへ固定せず、個別にテスト・再利用できるようにするため。
- **結果・影響：** 既存のHTTP endpoint、ジョブ取消、SQLite・Vaultの確定順序は変更しない。テストの差し替えは移設先の依存注入へ移し、`app.py` の再export・互換ラッパーを恒久的なAPIにしない。
- **関連：** [[40-Design/core-handler-routing-reorganization-plan]]、[[20-Modules/module-map]]

### ADR-120 実行環境ごとのローカル知識を、Gitで共有するSoftware Vaultとは別の階層に置く

- **状態：** accepted、実装済み（2026-09-25）
- **背景：** 利用者から、専門家定義・文献ノートなどAI実行時の知識（ADR-115）はGitで共有する「ベース」だけにし、各実行環境（研究者の端末ごと）でローカルに知識を拡張・変更できるようにしたいという依頼があった。論文原本などの資料はローカルにのみ保持し、Gitには研究者が内容を理解したうえで書いた要約ノートだけを載せる方針も含む。
- **決定：**
  - `src/gurumoji/method_experts.py` の `ExpertCatalog` に、Git管理外の第2の読み込み元 `local_root`（既定は `<data>/local_knowledge`、`MOJIOKOSI_DATA_DIR` 配下）を追加する。`<data>` はVaultと同じく `runtime/` 配下でGit管理対象外（`.gitignore`）。
  - `local_root` の内部構造は `SOFTWARE_ROOT` と同じ相対パス（`50-Analysis-Methods/10-Experts/<専門家>/`、`20-Literature/`、`08-Common-Knowledge/`）にする。既存の相対パス定数（`EXPERTS_DIR`・`LITERATURE_DIR`・`COMMON_DIR`）をそのまま再利用できるようにするため。
  - ノート単位で解決する：同じ相対パスのファイルが `local_root` にあればそれを使い、なければ `SOFTWARE_ROOT` を使う（`ExpertCatalog._resolve`）。専門家フォルダーの一覧は両方の和集合とし、`index()` の各項目に `source`（`base`／`local`／`local_override`）を付けて、どの専門家・どのファイルがローカル限定かを常に判別できるようにする。
  - 知識hash（`ExpertCatalog.knowledge`）は実際に解決された（ローカル優先の）ファイル内容から計算するため、ローカルの追記・上書きは既存のhash機構でそのまま検知される。ローカル知識は原本文献の全文ではなく、ADR-115と同じ「専門家定義・文献ノート」の形式で書く。
  - `local_root` が存在しない・空の環境では、全ノートが `SOFTWARE_ROOT` から解決され、既存の17専門家・挙動と完全に一致する（後方互換）。
- **理由：**
  - 既存の `ExpertCatalog(root=...)` の差し替え可能な設計と、`<data>` がすでにGit管理外である慣習を再利用でき、新しい依存や別の同期機構を増やさない。
  - Vault側のVaultRegistry（所有hash・conflict判定）とは別領域とする。ローカル知識はVaultの利用者ノートではなく、実行時にだけ読むアプリ内部の設定に近いため、Obsidianの競合処理を流用する必要がない。
  - 相対パスをそのまま流用することで、ローカル追加・上書きの両方を同じ仕組みで表現できる（新規専門家フォルダーの追加＝`local`、既存フォルダー内の一部ノート差し替え＝`local_override`）。
- **結果・影響：**
  - `catalog_summary()`（`GET /api/analysis/experts`）に `source` が乗るため、画面側でローカル限定の専門家・上書きを表示する余地ができる（今回は表示側の変更は行わない）。
  - テスト：`tests/test_method_experts.py` の `LocalKnowledgeTests`（ローカル無し＝既存互換、ローカル専用フォルダーの追加、既存ノートのローカル上書きとhash変化）。
  - 原本資料（論文PDF等）自体はこの階層にもGitにも置かない前提は変わらない。研究者が要約・咀嚼した文章だけをノートとして置く運用は、[[40-Design/method-rules]] の登録手順に従う。
- **関連：** ADR-115、[[40-Design/method-rules]]、[[50-Analysis-Methods/10-Experts/00-Index]]

### ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る

- **状態：** accepted、実装済み（2026-09-30）
- **背景：** 利用者が、Obsidian利用者の実践も踏まえた「整理・深さ・インデックス」と成果物品質の方針を承認した。ノート数や圧縮率だけでは成果物に役立つ知識か判断できない。
- **決定：** 利用者が必要な対象ノートを選び、整理と深さは根拠付きの確認記録、検索到達率は固定したローカル検索ケース、成果物は実際のプロンプト・出力・根拠抜粋に基づく固定基準のLLM採点で測る。LLMの新規タスク提案には不足と評価の改善点を渡す。削減率は補助指標とする。
- **結果・影響：** 確認記録・履歴を既存ConsoleのSQLiteに追加し、内容hashや設定revisionが変わった古い評価は無効とする。ノートは自動で上書きしない。比較条件が変わった履歴は分け、未評価を仮の点数で補わない。旧目標・タスクは保持する。
- **関連：** [[40-Design/a100-knowledge-control-plane-plan]]。評価方法は今回のアプリ独自の基準であり、Obsidian公式の評価規格ではない。


### ADR-122 分析要求を表示contextから分離し、固定試行の明示採用を全件実行の前提にする

- 日付: 2026-10-03 UTC
- 状態: 専用branch実装・V1/V2検証。V3実画面／AT／利用者理解は未受入
- 対象: W01〜W04、実装checkpoint `d3694b8`、backend契約 `9768b80`
- 判断: async要求はitem、data identity、入力revision、navigation／編集世代、要求tokenを固定する。遅いA応答でBの編集表示を変更しない。同itemの利用者入力と、旧要求の結果・busy状態を分ける。音声は最新の選択要求だけが保存／現在の有効時刻・本文・話者照合後に再生できる。
- 判断: 測定を4つの実装済みpresetへ限定し、保存→固定20件試行→明示チェック→採用→全件実行を分ける。単なる表示切替・試行・dialog表示では採用しない。完全なtrial CAS、採用版map、input hashでbackendの固定定義に接続する。採用版は編集せず新draftへ分岐。失われた採用応答はGETで確認してから次の書込みを許す。
- 判断: 簡単／詳細はnative radioの表示専用状態とする。明示入力を値の一致で「未編集」と推測しない。fixed trial rowへ現在の引用や時刻をjoinしない。
- 判断: statusとallowed_actions、recovery、4writerのpublication_attemptsを別々に表示する。failedを実行中、waitingを再開可能、legacy記録欠落を成功と呼ばない。固定packageの欠落・不整合を再計算で埋めない。
- 理由: DG-01/02/03/06の誤対象送信・暗黙採用・保存成功の誤認を避け、既存API／保存物bytes／研究者ノートの所有権を保つ。新frameworkやDB schemaは不要。
- 検証: 合成DOM・deferred fetch、4presetの実measure_segments、既存Python/API回帰。実データ・外部AI・モデル推論・移行・deployなし。通常ブラウザー到達がblockedのためV3以降を合格にしない。
- 戻し方: UI adapterを戻す場合もbackendの定義固定・CAS・4writer範囲・package検証を維持する。旧の暗黙採用や再計算fallbackを復活させない。


#### ADR-122 追記: 固定run閲覧と公開証拠の分離（2026-10-03）

- 対象source: `f31da55`、`5ac07ec`、`ce6e003`。既存query/storeを使う読取専用run-ID入口を追加し、実行結果から現在データを再計算する旧導線を廃止した。保存済みpackageのある待機／失敗からも閲覧できる。
- 保存要約・定義ID/版・測定表は固定JSON/CSVからのみ表示し、現在の本文・話者・役割・時刻で補完しない。表previewは20行/24列/セル256文字/本文16 KiB、JSONと保存要約も有限抜粋。省略を明記し、全件downloadのbytesを変えない。CSV空欄をnull・ゼロ・空文字へ推定変換しない。
- 本体の保存、hash/manifest整合、writerの実書出し、pipelineの進行台帳、科学的妥当性を分離する。公開応答のattempt/records/outcomesは単一read snapshotで読む。最新same-packageのfull-scope/full-executed/completed attemptだけを4writer成功の証拠とし、古いpipeline台帳の不一致は別表示する。閲覧で台帳を修復せず、成功済み公開の再試行を促さない。
- 保存条件の明示的な空配列、同run/hashの4台帳not_selected、記録不明を区別する。hash不一致・欠落、部分台帳、attempt欠落だけで対象外や成功を推定しない。旧保存scopeを拡張しない。
- GET、preview、ZIPは固定packageを検証するだけで、計算、復旧、公開、DB更新を行わない。欠落・破損・未対応形式は停止し、fallback再計算をしない。手法の追加、保存migration、実Vaultの変更はない。
- 検証は一時SQLite/filesと元JSの合成DOMのみ。`5ac07ec`固定tree全体で1012 passed/32 skipped/953 subtests、後続`ce6e003`の局所27 passed/39 subtests。GUI/AT/利用者理解は未受入。詳細はクラウド作業証拠 `eight-hour-20261003/fixed-run-viewer`。


### ADR-123 保存済み分析の読取専用投影と追記監査、設計記録後のスライド出力

- 日付: 2026-10-04 UTC
- 状態: 専用branchで実装、API/DOM/合成PPTX検証。実画面・Windows受入は未実施
- 基点: `1dbd54710e281698fedcd19ab4db001c1db11aac`。旧branchと成果物を保持し、`dot/analysis-history-viewer-20261004`に追加
- 判断: 履歴UIは実行serviceから分離したread-only SQLite投影を使い、初回読取でもDDL・stale更新・復旧・モデル呼出しを発生させない。会話・run・初期入力・結果の所有権/hashと版を照合する
- 判断: ラベルproposal・採否・競合・削除は追記専用監査へ保存する。実値の変更前後、提案申告旧値、提案新値を分け、削除はtombstoneとして残す。旧履歴の未記録項目を推測で補わない。元注釈・初期版は維持する
- 判断: スライドは保存runから決定的に生成し、実装の設計・promptは先にSoftware Vaultへ記録する。利用時は明示操作でrun版に結び付いた設計をVisualizationVaultへ保存し、読戻し/hash照合後だけpreview/PPTXを許す。削除・編集・保存失敗時は自動回復せず停止する。4先公開設定は変更しない
- 判断: 開発設計のWeb資料と分析の根拠を分ける。生成は追加AIなし、編集可能なPPTXテキストを使う。未知・未検証・隔離結果は結論へ混ぜない。重大未解決批判を上限で欠く場合は要確認としてPPTX出力を停止する
- 理由: 誰が何を提案し、どの版で何を採用・除去したかを辿り、AI下書き・形式検証・研究者の判断・保存成功の混同を避けるため
- 互換性: DBは追加のみ。新しいラベル操作schemaはprompt版を更新し、旧promptの未完runを黙って再開しない。旧run読取と旧checkoutを保持する。元DBの一括変換・元VaultやPCへの自動反映を行わない
- 詳細: [[40-Design/analysis-history-viewer]]、[[40-Design/slide-generation-design-and-prompts]]。検証結果は[[60-Operations/dot-cloud-development-handoff]]


## Downloads系列の再構成記録（2026-10-10）

以下は元bytesの回収ではなく、基点`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`と同一bytesの指定ZIP、およびCodexセッション`01a1098c-e967-7560-a93f-9a4d3d9998ac`の2026-10-05T05:43〜17:21Zに記録された成功FileChangeと明示置換を照合した再構成です。既存の上掲ADRと同番号でも別系列であり、実装済み・検証済みの記述は当時の記録です。今回実行した検証とは区別します。

HTML13,689 bytes・DOMテスト31,641 bytesは破損ファイルの残存長と一致しましたが、元hashがなくbyte identityは未証明です。ADR全体の再構成候補は71,885 bytes、破損ファイルは71,882 bytesで3bytes異なります。ZIPにBOMはなく、LF正規化・現在のpatchエンジンによる混在改行保持も比較しましたが差の由来は特定できず、欠落bytesを推測補完していません。既存ADR本文と候補全体はprivate Git／receipt側に保全します。

今回の変更はこのADRの系列・参照注記と根拠のある追記、HTML・DOMテストの再構成、前回追加したJavaScript最低3回の2hunkを既存b9の専門側契約へ戻す処理です。通常auto（専門側を明示無効）の最低3回と既存runの条件は維持します。検証は合成fixtureの関連DOM78件と境界5件が成功し、実DB・実Vault・認証・実モデルには接触していません。元bytes完全回収、実ブラウザー操作、全体suite、実AI・全発話品質評価は未実施です。PNG延期、Gemma323 HOLD、G0.5未測定、G5未評価を維持します。

固定証拠はprivate receipt `gurumoji-missing-latest-ctx_0a74dcfad136/recovery-receipt.json`（C0管理）に記録します。private履歴・原スナップショット・リンクを公開共有しません。

### Downloads再構成・参照文脈（元系列ADR-127／2026-10-06）

- 状態: ローカル実装。`core-handler-prompts-25-referenced-context`、関連220 unittest成功。マーラータンのコピーDBによる実モデル全体試験は継続中。基点と未コミット状態はDownloads系列の専門側責務と同じ。
- 判断: `model_context_version=1`では新規resolverの`context_reference_version=1`を既定にする。全担当がローカルのUI起動も両方1とし、発話24件・文字6000を分割の初期値とする。UIの呼出し/登録タスク上限は160/400（利用者が変更可）。323発話では初期3担当だけで42ページとなり旧上限24/48では不足するため。APIの既定上限・明示0と保存済み旧条件は保持する。クラウドを含むUIでは従来経路を維持し、未対応の実測を成功扱いにしない。
- 判断: タスク指示には固定DBの論理参照パスと、Obsidianの相対パス・note ID・版・hashを置く。Handlerが取得済みの発話範囲と知識を別の`resource_data`メッセージで渡す。モデルがファイルを自律読取したという表示はしない。メッセージ分離は同一APIリクエスト内で行い、SDKの自動反復や隠れた追加AI呼出しを使わない。
- 判断: 既存`ExpertCatalog`で共通知識の指定節2ノートと、利用許可・版が一致する手法briefを取得する。全Vault・原論文・他専門家・研究者所有ノートは渡さない。必須入力・適用条件・禁止結論・未解決事項は省略せず、8000文字を超える必須知識は保留する。知識は方法の根拠であり発話の証拠とは区別する。
- 判断: 指示・データ・知識・schemaを含む実テンプレートで予算確認する。参照ごとのhash、データメッセージ群hash、実提示IDと未読範囲を既存task/result JSONへ記録する。知識は取得時に原bytesを再hashし、更新日時だけに依存しない。任意パス・Vault外へのリンク・非currentノート・必須節欠落を拒否する。
- 限界: メッセージ分離だけでトークンが消えるわけではない。モデル側の永続記憶・送信済み指示のキャッシュ・自由な全文検索・モデルが選ぶfilesystem toolは追加していない。研究上の品質認定は別に必要。
- 関連: [[20-Modules/analysis-orchestration]]、[[40-Design/model-context-and-work-memory-plan]]、[[60-Operations/gurumoji-improvement-session]]。元DB・研究者Vaultの書換え、移行、Drive送信、commit/pushはない。

### Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）

- 状態: ローカル実装。v22〜24の入力・応答上限での失敗を保存し、Downloads系列の参照文脈のv25で再試験中。基点`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、既存未コミット変更を保持。
- 判断: 新規runは`specialist_orchestration_version=1`を既定にする。専門オーケストレータが解釈・検証・批判・数量・尺度の分野別に採否と追加案を返す。Handlerが予算内の束を選び、保存済み結果・来歴・依存を管理して直接発注する。Coreは初回の担当指示、分野間の統合、終了案を返す。
- 判断: 尺度は会話解釈専門家が作成し、Core統合前に独立した批判者が欠測・方向・尺度水準を検証する。尺度の指摘は尺度自身の対象版に紐付け、Coreの見解更新で旧版扱いにしない。応答した批判を自動的に解決済みとしない。
- 判断: 専門側の分割査定はCoreの反復回数へ加算せず、AIお任せで最低3回を強制しない。新しい報告IDだけを進展とせず、元結果の対象版・範囲・内容hashを比較する。元の問いと同一または文字列の近い追加案を保留し、同じ固定入力の全件集計は再利用する。文字列の類似度は意味同一性の完全な判定ではない。
- 判断: 各AI呼出しはsystem指示・userの対象データ・出力schemaを同じリクエストに送る。モデルがVaultやスキルを自分で読むagent tool経路や、送信済み指示のアプリ側キャッシュを実装したとは扱わない。初期原文はページ分割し、追加分析へ完了済みの全初期報告・過去結果を渡さない。Coreへは追跡可能な分野報告を渡し、未読の原結果を読了扱いにしない。
- 互換性: 新しいrole/phase/prompt版を固定し、旧版の未完runを黙って再開しない。明示的な旧経路`specialist_orchestration_version=0`と保存履歴を保持する。DBは既存JSONを使い、カラムの削除・型変更、元DBや研究者Vaultの書換えはない。
- 詳細と検証: [[20-Modules/analysis-orchestration]]、[[40-Design/model-context-and-work-memory-plan]]、[[60-Operations/gurumoji-improvement-session]]。

### Downloads再構成・最低回数後の追記: 初回のラベル・尺度は専門エージェントが作成する（2026-10-05）

- 利用者指定: 初回でラベル作り（スケール/尺度）を必ず出力し、作成主体はCoreではなく専門エージェントとする。
- 最初のCore実行前に、既存の会話解釈専門担当へ専用`label-design-v1`タスクを必須発注する。空/不正な定義は隔離して停止し、初回を成功扱いにしない。保存結果のhashと作成主体を検証してCoreへ渡し、中断後も同じ生成を繰り返さない。
- 定義は根拠・判定基準・尺度水準・欠測規則付きのAI下書き。既存ラベルやコードブックの確定・統計実行とは分け、Coreは専門家結果の採否/統合を担当する。既存履歴に定義を補作しない。現行契約と出力経路は[[20-Modules/analysis-orchestration]]。
- 実データ試験で入力枠超過、根拠IDの誤写、型と尺度値の不一致、欠測の通常値化、空の追加理由を確認した。現在は`core-handler-prompts-10-complete-intents`で、AIへ渡す重複メタデータを省き、実在参照と型別生成・空文字禁止をschemaにも適用する。保存の全量根拠/hashと既存採用検証を維持する。初回順序尺度は数値符号と各値の意味を出力し、科学的な妥当性の確定とは分ける。モデルの不正回答を事後書換えして採用しない。

### Downloads再構成・最低回数後の追記: 初回に全担当へ依頼し、尺度要件を集約して担当指示する（2026-10-05）

- 利用者指定: 初回の分析を全分析担当へ依頼し、ラベル/尺度が必要な分析をHandlerへ報告、集約してCoreが担当への指示をHandlerへ返す。
- 判断: 既存の会話解釈・数量統計・独立検証・批判者を初回から起動する。独立な原文確認と既存3コード手法の全6タスクを保存し、AI担当は分析用途・必要概念・理由・根拠を`label_requirements`として報告する。不要な担当は空配列を明示する。全担当の成功・hash・版を確認するまでCoreの担当指示へ進まない。
- 判断: Handlerは原結果の出所を保持した`initial_analysis_report`をCoreへ渡す。Coreの`initial_routing`は発注先と具体的な問い・採用基準を指示し、Handlerが既存の尺度設計専門担当へ正式発注する。Coreは尺度を自作せず、担当指示を1回目の統合や反復成功へ加算しない。尺度のAI下書き保存後に1回目の結果統合へ進む。
- 判断: 保存・再開・予算上限・取消・重複防止は既存台帳を使う。独立検証へ他の担当/Coreの結果を渡さず、初回予備分析で採用ラベルを変更しない。実行可能な新規尺度の自動登録や未実装の統計を追加しない。
- 互換性: prompt版は`core-handler-prompts-11-initial-specialists`。新規実providerでは新契約を固定する。SQL列変更/旧runの後付け変更/実データ移行なし。旧provider版の再開は既存guardで拒否する。検証と実データ上の限界は[[60-Operations/gurumoji-improvement-session]]に記録する。

### Downloads再構成・最低回数後の追記: 同じ回答を最低回数に加算しない（2026-10-05）

- 背景: 実AI成功runのCore3回が完全一致し、独立検証の24主張を後続判断へ反映した根拠もなかった。利用者から同じ内容を繰り返さないよう修正依頼を受けた。
- 判断: 新しいadapter契約`core-handler-prompts-5-progress`は、要約だけの変更・claim ID・配列順で進展を作らず、根拠付き主張・代替説明・未解決点・具体的な作業案と過去の判断を比較する。同じ状態への循環は最低3回より優先して`no_progress`で停止する。試行回数と採用判断数を分け、停止した部分結果を分析完了や自動公開にしない。
- 判断: 独立検証等の未評価結果をCoreへ明示し、各result IDの採否・理由・結論への影響を保存する。結果を無視した応答は隔離し`unreviewed_results`で停止する。同じ役割・入力/ラベル版・対象範囲で原結果hashも同じなら、新result IDだけでは新しい検討根拠としない。結論を保った再検討でも、実際に異なる結果/レビュー対象への採否は進展になり得る。
- 互換性/限界: DB列・封印済み成果物・旧runの条件や成功判定は変更しない。既存のadapter版不一致時の再開拒否を維持する。意味の等しいあらゆる言い換えの検出や、結果への採否理由の研究上の妥当性は保証しない。合成試験/ブラウザーの受入と実AIでの再分析は区別する。検証は[[60-Operations/gurumoji-improvement-session]]へ記録する。
