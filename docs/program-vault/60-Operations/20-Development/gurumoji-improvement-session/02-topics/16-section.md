---
note_type: reference-section
status: current
updated: 2026-11-12
note_id: ops-gurumoji-improvement-session-20261003-section-16
title: Gurumoji 改善セッション：同日：マーラータン実データで尺度出力・反復を試験
summary: マーラータン実データの尺度・反復試験とObusSQL接続。2026-11-10に配送5候補の比較・混合方式の採用、検索・配送予算の改善、速度未改善と残る品質制約を記録。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 275
- 284
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：マーラータン実データで尺度出力・反復を試験

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：マーラータン実データで尺度出力・反復を試験

- 利用者のテスト依頼に基づき、323発話の原本DBを読取専用でコピーし、各呼び出し48発話/8,000文字/索引48件でLM Studioの実推論を実施。初回の120発話/全索引では65,827 tokensとなり、ロード枠32,768を超えてHTTP 400。48発話の初期版でも2回目Coreで入力32,466/出力302 tokensとなり応答途中終了した。全323発話をAIへ渡した試験とは扱わない。
- 実データで確認した入力の重複、ID誤写、尺度型と値の不一致、欠測の通常値化、空の追加理由を、既存context/adapter/純粋validatorで修正。最終adapterは`core-handler-prompts-10-complete-intents`。全量snapshot/hashは保持し、AIパケットの重複メタデータを省く。尺度設計には既存AIラベルを渡さず、後続は変更可能なラベル欄だけを渡す。実在ID/節/依存taskと型別生成、必須理由の空文字禁止をschemaにも適用し、不正原回答の事後置換は行わない。共有schemaコンテナーの制約が別フィールドへ漏れる問題も新テストで検出し、JSON往復コピーで分離した。
- Qwen3 8Bは順序尺度と分類の混同、category型で数値を出す、欠測をlevelsへ混ぜる等の応答があり、全試行不合格。GPT-OSS 20Bへ切替え、最初の試行は尺度2件を保存したがCoreのwhy_now空欄で停止。失敗記録は`output/malatang-specialist-labels`の各日時ディレクトリーに保持する。モデルはこの試験だけで指定し、アプリ設定は変更しない。試験用にロードしたモデルは終了後にアンロードした。
- 最終run `run_d2de4cc5ac524ed399b8fbf8b9133ba8`（`20261005T064634Z-c6017726`）: ローカルGPT-OSS 20B、32,768 context、実AI6呼び出し、176.33秒。専門エージェントが初回に「辛さの好み」（順序1〜5）と「価格に対する懸念度」（順序1〜3）を作成し、値の意味/判定基準/欠測条件/根拠と共に保存。最初のCore開始より前の終了時刻、作成主体、catalog/原結果/hashの一致を確認した。Core3回の採用判断、批判者1回、追加解釈1回がある。独立verificationはこのrunで未実行。
- **最終の厳格判定はfailed**。3回目は2回目と同じ追加作業を提案し、同じタスクを再発注せず`no_new_tasks`で停止した。原応答hashは3種類だが進展signatureは2種類で、2/3回目の採否は新しいresult IDへdefer/impact=none。Coreの根拠付きclaimsは全3回とも0件で、専門家結果を主張へ統合した十分な分析とは扱わない。採用数3は新しい専門家結果の評価を含む動作記録であり、内容深化/研究上の十分性/正常完了の保証ではない。固定成果物の自動保存・Vault公開はskipped。終了判定を成功に変えない。
- 原本のsource stampは試験前後で一致。保存原結果全件のhash、全量根拠323件、尺度catalog、JSON/Markdownの既存読取ルート、閲覧での再推論なしを照合。尺度は未検証AI下書きで、科学的な尺度妥当性の検証・全量分析・実Vault公開・Git commit/push・Drive更新は未実行。関連9モジュール153 tests成功（31.586秒）、Python compile/git diff --check成功。未コミット変更のコードhashと実試験は同ディレクトリーの`result.json`、`verification.json`、尺度は`initial-labels.json`、全台帳は`analysis-history.json`/`analysis-history.md`へ保持する。

## 2026-11-09 ObusSQL更新・マーラータン入出力実試験

- 利用者は最新版更新とマーラータン実データの分析・入出力試験を許可。作業先は利用者checkout、ブランチ `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の未コミット変更を保持し、commit/pushなし。
- ObusSQLを `e371ae3` からリモートmainの `07128acfe13c1162552f7928b5ab0e7c954fac1b` へff-only更新。Windows/Python 3.12.9でnative wheelとMAF wheelを作成し、アプリと隔離試験venvへ導入。dev版番号は変わらないため、wheelと導入assetのhashを照合した。requirements2件・接続サービス・利用手順の固定commitを更新し、pip check成功。
- 原本SQLiteはURI `mode=ro` とbackupでコピー。試験は一時DB・一時Vault、323発話・5話者・12,074文字で実施。原本行hashは試験前後で一致。runtime/資格情報保護guard違反0、クラウドAI通信0。Pythonは `output/validation/obussql-update-20261109/app-venv`、AIはloopback LM Studioだけを使用した。
- 通常writerのJSONを別プロセスの実importerで再取込し、323発話のID・本文・話者・時刻・順序が一致。JSON/Markdown/CSV/Excel出力、集計結果のInput・Orchestrator・Visualization・Researchの4Vault保存、別プロセスからの再読込、固定JSON/CSV/Excel/ZIP、ObusSQLの管理ノート3件読取を確認。Excelは全セル、ZIPは全memberのhashでも照合した。
- 自律AIは `google/gemma-4-12b-qat`、16,384 context、GPU80%、追加推論off、並列1。323発話の固定根拠をObusSQLで取得し、初回専門分析・尺度設計・独立尺度レビュー・Coreの2反復まで実行。実AI32呼出し、35タスク成功。後続の解釈とCoreの2タスクが `context_budget_exceeded` で停止し、最終状態は `stopped / execution_failure`。必要枠は20,024/18,588 tokens。自律結果の固定保存・公開は未実施であり、通常集計の保存成功と区別する。停止台帳のJSON/Markdown出力は成功。
- 固定Excel/ZIPが表ごとに全packageを再検証していた遅延を修正。`analysis_store.py`・`fixed_exports.py`・`analysis_queries.py` の3件で、検証済みpackageから全表を一括取得する。SQLカラム・保存形式・hash・元参照の検証は維持。内容改変・参照欠落の拒否も隣接試験で確認した。
- 上流関連117件、接続関連68件、固定出力関連96件、計281件成功。Windowsのsymlink権限で1件skip、pyreadstat未導入のSAV1件deselect。初回Janome skip分はoptional依存導入後に再実施して成功。AST・差分検査成功。
- 出力修正前の試験全体558.05秒、fresh 268.20秒。修正後の同じ保存データで全体58.95秒、fresh 24.97秒。初回は保存を含むため厳密な速度倍率とは扱わない。6出力の内容hashが一致し、XLSX/ZIP1要求につき全package検証1回の試験も成功した。
- 試験ハーネスは開発資料ブランチの `scripts/verify_obussql_malatang_io.py`・`scripts/verify_obussql_malatang_post_io.py`。実行結果は利用者checkoutの `output/validation/obussql-update-20261109/verification.json`、`static-fidelity.json`、`context-limit-failures.json`、JUnit、`io-standard/exports/` に保持し、総合判定は `partial_pass`。
- 未実行はブラウザー実操作、音声再文字起こし、PostgreSQL・上流MAF本番host binding、上流全試験、32K以上の再試験、SAV。実Vaultや認証設定は変更していない。
- この節は前回記録時の文字コード不具合で日本語が「?」へ変わっていたため、同日の検証JSONと実行記録に基づいて復元した。過去の他節・タグ・IDは変更していない。

## 2026-11-09 Gurumoji自律分析の可逆入力配送

- 利用者から「グルモジ側を対応させて」と依頼。汎用 `compact_v2` をそのままモデルへ渡すと、停止入力2件は16,312→19,443、14,876→17,117 tokensへ増えた。パッケージ更新だけで入力枠問題が解決するとは扱わない。
- `context_delivery.py` を追加し、ObusSQL `ResponseCodecAdapter(compact_v2)` によるJSONの往復・hash検証後、グルモジの読みやすい表・共通値・共有文字列形式へ投影する。文字列化されたJSONは完全な項目を可逆に構造化し、切断済みの末尾を補完しない。配送候補をローカルで復元し、元のcanonical JSON bytesと再照合する。sourceタグ衝突、未導入、未対応、codec上限は通常形式へ戻し、復元不一致では停止する。
- 通常形式と候補を同一ロード済みモデルのtokenizer・chat templateで測定し、説明文込みで入力が小さくなる場合だけ選ぶ。回答予約3,200と安全余白512は維持。計測途中のモデル設定変更は拒否。budgetへ前後token・削減数・元JSONのhash・往復検証結果を記録し、manifestは実送信user/systemのhashを持つ。adapter版は `core-handler-prompts-45-obussql-context-delivery`。
- 停止済みコピーから再構築した2タスクを同じ16Kモデルで実推論した。解釈は30発話・17,446→12,553 tokens、Coreは7発話・15,229→12,517 tokens。各1回の実送信で4件ずつの主張が返り、既存 `_validate_result` の契約検査に両方成功。原本runtime/資格情報への書込なし、guard違反0。再構築状態での測定であり、新しい分析全体の完了とは区別する。
- 関連8モジュール106件と27 subtests成功。JSON-prefixの全切断位置、Unicode/escape、bool/int/float、条件・例外・ID、改変hash、通常形式への復帰、モデル変更拒否、実adapterの配送・manifestを確認。例外の保護範囲を整理した後、追加17件の再試験も成功。
- 実推論の最初の試行は、応答取得後にハーネスがusage行をmanifestと誤認して停止。ソース不具合とは区別し、ハーネスを修正して別ディレクトリーで実AI2呼出しを再試験した。失敗資料を残し、原応答の改変や成功状態の捏造は行わない。
- 323発話の新しい隔離コピーで全体再試験に成功。run `run_9f8e986b6bcf410fb6d2af33bb237631`、実AI24呼出し、27タスク成功、失敗0。初回の全専門分析・尺度設計・独立尺度レビュー・Core統合3反復を経て `completed / no_more_evidence`。自律結果の固定保存・4Vault公開・別プロセスでの再読込と再出力、JSON/Markdown/CSV/Excel/ZIP出力が成功した。全体1,240.30秒、fresh 3.19秒。研究上の妥当性を承認済みと扱わず、AI下書きの属性を保持する。
- 全体の実送信24件で、同一入力の通常配送計203,129→187,404 tokens、15,725 tokens（約7.74%）を削減。全件でObusSQL往復・投影復元検証が成功。実際の呼出し数削減や前回モデル出力との差を、この同一入力の圧縮率へ混ぜない。
- 原本行hashは前後一致、保護先書込違反0、外部AI通信なし。元DB・実Vault・資格情報の更新やcommit/pushは行っていない。主変更はruntimeサービス3件と既存利用手順で、試験・ハーネス・本記録は開発資料ブランチへ保持。関連回帰試験は重複を除いて165件（106+59）と49 subtestsが成功し、最後の例外保護整理後に追加17件を再実施した。
- 証跡は利用者checkoutの `output/validation/obussql-context-20261109/verification.json`、`real-model-r2/measurement.json`、`full-io/result.json`、`full-io/fresh-result.json`、JUnit、`tested-sources.json`、`full-io/exports/autonomous/`。ブラウザー操作・音声再文字起こし・上流MAF本番host bindingは本試験に含めない。更新後はアプリを再起動し、旧契約のrunを再開せず新しい分析を開始する。

## 2026-11-09 結果ID再分析・必須手法・終了制御

- 利用者から、結果IDのGUI表示・IDと追加プロンプトによる再分析、分析処理の完了、全自動分析の必須手法指定を、それぞれ要件化して並列実装する依頼を受けた。作業先・ブランチ・開始HEADは上記と同じで、既存の未コミット変更を保持した。実装3担当はGPT-6.1 Terra、統合は親担当が実施。
- 要件と受け入れ条件は [[20-Modules/20-Analysis/analysis-orchestration/06-section|結果IDによる再分析・分析処理の完了・必須手法]]。mainにはアプリ本体と既存READMEの手順だけを反映し、試験・設計書は本開発資料ブランチに保持した。
- 同一会話・同一入力版のrun/result IDから、有効性とhashを確認して新runに参照元と人の追加指示を固定する。参照GETはAIを呼ばず、元の履歴・会話本文・固定成果物を変更しない。独立検証には元の結論を配らず、追加指示と出所だけを渡す。元の解釈は参照データ、追加指示は今回の分析指示として区別する。
- 必須指定できる手法は現行の自律経路で実行できる発話量・参加バランス、会話の時間構造、ラベル度数の3種。AIが即時停止を提案してもHandlerが未実行を登録し、担当評価とCore統合まで確認する。未対応手法、未評価、保留、失敗を実行成功と表示しない。
- 終了前レビュー後の改訂で処理が循環する問題を修正し、人の確認が残る分析を処理完了のAI下書きとして固定保存する。元の停止理由と原応答、未レビューの表示を保持し、自動Vault公開を保留する。一般の上限停止、取消、障害、不明実行、同じ判断の繰り返しを正常完了へ変換しない。分割親のblockedは、子孫の全範囲・有効結果・採否が揃った場合だけ処理済みとする。旧runと採否がない旧プロトコルの状態は変更しない。
- 関係Python試験241件、DOM43件、実Edgeの1360／390px試験が成功。一時DB・一時Vaultの結合試験で、固定成果物の再読込と参照元・追加指示の保持、元run・原結果・会話行・固定成果物bytesの不変を確認した。AST・JS構文・差分検査も成功。総合記録は `output/validation/reanalysis-required-20261109/verification.json`、要件ノートに検証範囲と初期失敗を記載。
- 実モデルで停止と追加依頼の併記が続く問題を確認したため、adapter49のnext_stepを追加分析／終了の排他形式に修正した。元next_stepを保持して既存Handlerへ投影し、旧版と初回ルーティングは維持する。最終r7はGemma実呼出し7回・全10タスク成功・必須3手法の採否とCore統合・専用MetricDecoder受理を確認。時間上限前に処理完了し、人手確認待ちで終了した。未解決指摘2件と元のモデル停止理由を保持。別プロセス・読み取り専用DBで原応答／参照元hash・追加指示・Core投影・decoder再実行receiptも一致した。実モデル試験は分析処理まで、固定保存は別の結合試験で確認し、両者を同一試験の成功と混同しない。
- 実利用者DB・実研究者Vault・資格情報を試験に使用していない。commit/pushなし。Pythonの更新はアプリ再起動後の新規実行に有効。

## 2026-11-09 クロス集計の必須指定と実行確認

- 利用者の「クロス集計が出来るように指定して出来るか確認」に対応。作業checkoutは `C:/Users/kurok/Downloads/mojiokosi/mojiokosi`、ブランチは `krokharu/transcription-finish-20261102`、HEADは `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の未コミット変更を維持し、commit/pushなし。
- 自律分析の必須手法に `cross_tabulation`（話者×codes）を追加。件数・行内割合のGUI表と、列内割合・全体割合・各分母・欠測内訳・根拠ID・入力版・ラベル版・コードブック版の原結果を保持する。複数コードの同一発話内重複は除き、複数回答の割合合計が100%を超え得ることを明記する。
- 全件欠測の表を `unavailable` として必須分析完了から除外。GUIで固定したcodes列を生成schemaとHandlerで守り、別列・部分範囲を必須の全件表の代わりにしない。同じ列・対象・版の全件再集計は保存結果を再利用する。既存の初回3手法、SQLカラム、保存先契約は維持する。
- Python回帰274件・92 subtestsと追加の初回処理共存試験1件、DOM33件、実Edge1360／390pxの選択・送信・クロス表表示・横はみ出し確認が成功。GUIは合成API、実モデルは同じrequired_methods指定のサービス実行として区別する。AST・JS構文・対象ファイルの差分検査も成功。
- 最終実モデルr4（Gemma4 12B QAT・ローカル・reasoning off）は `run_488204f681994c4f8c83d576ddffaa4d`、Core2巡・AI7回・集計1回、全8タスク成功、`completed / question_satisfied`。合成6発話の表はAの価格2・味1、Bの価格1・味3、各話者の分母3、欠測はAの1発話。有効5／対象6発話。専門評価adopt・Core統合・MetricDecoder受理を確認した。
- 別PythonプロセスからDBをmode=roで開き、全原結果hash、クロス表の再計算hash、専用decoder receipt1件、必須進捗、固定入力不変を照合。総合証跡は `output/validation/crosstab-20261109/verification.json`、原結果は `real-model/r4/cross-result.json`、新プロセス照合は `fresh-verification.json`、主コード9ファイルのhashは `tested-sources.json`。
- 初期r1は試験transport引数不足、r2は批判回答の状態と指摘本文の矛盾を正しく隔離、r3はAIによるcode/codesの変更と別列欠測を確認。r3の問題を列固定・対象照合・保存結果再利用で修正し、失敗台帳は保持した。モデルの不正応答を成功に書き換える処理は入れていない。
- 実利用者DB・研究者の本文・タグ・別名・実Vault・資格情報は試験対象にしていない。新規ラベル付与の品質、実データの再分析、クロス表の固定成果物変換・Vault公開は今回の実モデル検証に含めない。アプリ再起動後の新規実行で有効。

## 2026-11-09 統計専用codecの設計・実装

- 停止原因の追跡：`full-io-r2` の保存済みDBを読み取り専用で確認。Coreの全6判断が `human_review_required` を提案し、結果版は1から6へ毎回更新された。終了レビュー済み版は `[1,2,3,4,5]`。第2・第5レビューは `no_issues` でも、次のCore判断が新版になり再レビューへ進んだ。現行制御は同じ版がレビュー済みの場合だけ停止提案を確定するため、版更新と再レビューが循環し、第6判断で試験設定の上限に達した。直接停止理由は `iteration_limit`、統計codec失敗・入力トークン超過ではない。さらに全判断が人の確認を求めており、上限を増やすだけでは正常完了を保証しない。自動保存コールバックは `completed` のみが対象なので未起動。終了制御の修正・再試験はこの原因調査では未実施。

- 利用者から、集計用codecが未接続だった理由の確認に続き、統計専用の設計・実装を依頼された。作業checkout・ブランチ・HEADは上記と同じで、既存の未コミット変更を保持した。従来の統計3種はPythonで計算されていたが、汎用JSON配送だけでは `MetricEncoder` / `MetricDecoder` の利用を保証しないため、新しい専用契約を設ける。
- 責務は「既存の固定統計表 → MetricResult → MetricEncoder公開投影 → 既存の統計担当レビューAI1呼出し → 原応答保存 → 元統計再照合 → MetricDecoder → 採用・公開」。AIに集計や算術を委ねず、codecにSQL・認可・研究上の承認を委ねない。既存の原応答を検査前に保存する契約、SQLカラム、Vault保存先は維持する。
- 参加状況は全体・話者別発話数、話者別の発話時間・文字数を変換。会話動態は保存済みgaps/overlaps表の件数・時間合計を扱い、表の外にある区間の不存在を主張しない。ラベル頻度は母数・観測・欠測・分類別件数を扱い、ラベル版・コードブック版を結び付ける。割合・検定値・任意SQL・NumericReaderとの直結は本契約に含めない。
- `metric_delivery.py` の `gurumoji-metrics-v1` は同一run・固定入力・initial・task・ラベル版・元結果hashへ束縛する。元統計の全文が16,000文字を超えても統計レビューのホスト側では取得し、モデルには公開投影だけを渡す。内部stateを `context_manifest.metric_contract` に保存し、入力対応表・query_hash・元結果参照はAIのmetric_contextへ送らない。
- 集計元ごとの `source_1` 等を必須schemaとして、各欄のoperandsをその集計元のrefsだけへ限定する。1欄につき1演算で、同一レビューは最大4集計元、50指標、投影16 KiB。超過・不足を切り捨てて成功にしない。`value` の元値復唱と `diff` / `ratio` / `max` / `min` を専用デコーダーへ渡し、単位・粒度・比較軸・欠測・0除算・未発行参照・元結果改変を検査する。Decimalの集約は独立した精度50のcontextで行い、丸めて受理しない。
- 検証成功のreceiptは結果metadata・採用判断の `metric_validation`、成功イベントは `metric_codec_validated`。統計報告のsummaryはdecoder.answerとし、AIのmodel_summaryと原応答を監査用に保持する。統計レビューの自由なclaims/alternativesはschemaで空に制約する。後続の自由な研究解釈全体の正しさや尺度妥当性をcodecの合格へ読み替えない。
- adapter初版は `core-handler-prompts-46-metric-codec`、演算別生成制約を追加した最終版は `core-handler-prompts-47-metric-operations`。新runではObusSQL有効時に `metric_codec_version=1` を固定し、未導入は開始前に拒否する。上流07128acのharness wheel `obusql_agent-0.1.0` をビルドし、実アプリと隔離venvへ正規依存込みで導入した。requirementsとrun.batへ導入経路を追加。上流のmetric_codec.py・codec_core.py、wheel、隔離環境の導入assetはbytes/hash一致。両venvのpip check成功。
- 単発実モデル試験は原本でなく、前回の許可済み実データの固定コピーから統計3種を読取専用で再構築した。最初の試作ではnot_found、次の試作では最初の集計元だけの選択が返り、成功扱いにせず保持した。集計元ごとに必須schemaを分けた再試験 `replay-r3` は実AI1回・23指標・3集計元を通過。実際の上流メソッドを包んだ計数でencoder成功2回・decoder成功1回を確認。応答の捏造・不足の補完・原文改変なし。
- 関連8モジュール175件・49 subtests、上流Metric codec96件が成功。合成試験は差・比・最大・最小、母数・欠測・空表、型・桁、元結果改変・別run・改変state・値改変・未発行参照・別単位・一部元だけの選択を拒否する経路を含む。資料・試験は開発資料ブランチ、主実装は利用者checkoutへ保持する。
- 初回全体試験 `full-io` は実AI16回の後、`value` に複数参照とnullを入れた統計応答を上流decoderが `METRIC_OPERATION_INVALID` として隔離し、`specialist_review_incomplete` で停止。固定保存・公開は未実施で、原本行hashは前後一致。実メソッド計数はencoder成功2回・decoder拒否1回。失敗を成功へ変えず保持する。
- 改善版47では `value` を参照1件とその元値の組でanyOfへ束縛し、diff/ratioは2件、max/minは2件以上へ制限する。比較演算の候補は同一指標・版・単位・粒度・固定入力・フィルターの非欠測値だけから作り、最終的な比較軸・重複・0除算はdecoderでも再検査する。単発実モデル `replay-r4` は3集計元・23指標を通過し、encoder成功2回・decoder成功1回、実入力5,181/16,384 tokens。参照に対応しない元値とvalueの複数参照を生成schemaで拒否する合成試験も追加した。
- 最終の版47・323発話新規run `full-io-r2` は、実AI33呼出し・36タスク成功、失敗/隔離0。統計レビューで3集計元・23指標を配送し、3件の検証済み値を受理した。実メソッド計数はencoder成功3回・decoder成功2回、拒否0。原AI応答は保存したまま、採用した統計報告のsummaryがdecoder.answerであること、元のmodel_summaryを保持すること、検証イベント1件が残ることを照合した。
- 自律分析全体はCore6反復後に `stopped / iteration_limit` で停止し、自律結果の自動固定保存・公開はnot_started/skipped。統計codecの成功と全体分析の完了を区別し、完了状態へ書き換えない。停止台帳のJSON/Markdown出力と、別種の通常集計の固定保存・4Vault出力・JSON/CSV/Excel/ZIP・別プロセス再読込は実APIで成功。通常集計の保存を自律結果の保存成功と扱わない。
- 新しいPythonプロセスで試験DBを `mode=ro` で開き、保存済みの対応表と統計元から専用decoderを再実行。結果metadataと採用判断のreceipt、summary、元AI応答hashが全て一致した。原本行hashは前後一致、保護先書込・禁止AI/ネットワーク試行0。実Vault・資格情報・原本DBは更新していない。commit/pushなし。
- 最終回帰はホスト9モジュール182件・49 subtests、上流統計codec96件、計278件成功。起動処理の依存確認部分を実Windows cmdで実行して成功。両venvのpip check、上流ソース・wheel・両導入環境のmetric_codec.py/codec_core.pyのbytes/hash、AST・差分検査も確認した。
- 総合証跡は `output/validation/obussql-metric-20261109/verification.json`。`metric_integration_status=passed`、自律分析停止を含めた総合は `partial_pass`。最終単発は `replay-r4/result.json`、新規全体は `full-io-r2/result.json`、実呼出しは同ディレクトリーの `metric-codec-calls.json`、入出力は `post-io-result.json` / `post-io-fresh-result.json`、導入hashは `codec-provenance.json`。新しいハーネス・試験・本記録は開発資料ブランチに保持し、不要な開発資料をmainへ追加していない。ブラウザー操作・音声再文字起こし・実PostgreSQL NumericReader接続は含めない。

## 2026-11-10: ObusSQLのコンテキスト量・速度・品質の調査

- 対象は利用者checkout `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と既存の未コミット実装。上流は `07128acfe13c1162552f7928b5ab0e7c954fac1b`。アプリ本体・保存契約・実利用者DB・実Vault・認証設定は変更せず、合成データと一時DB/Vaultで調査。調査中にも対象外ファイルの変更が見られたため、再現にはHEADだけでなく `app-source-hashes.json` の対象実装hashを用いる。
- Python 3.12.9、obsipg 0.0.1.dev0、obusql-agent 0.1.0、agent-framework-core 1.22.0。導入済み delivery_codec.py / retrieval.py / metric_codec.py は上流checkoutとbytes/hash一致。pip check成功。LM Studioのロード済み `google/gemma-4-12b-qat`、実枠16,384 tokensを使い、モデルの追加取得・再ロード・クラウド送信は行わない。
- 実用途は管理ノートの読取プレビュー、分析入力の可逆配送、MAF開発接続の固定根拠選択、統計専用codecの4経路。実体はMemoryBackendによる要求単位の処理であり、永続PostgreSQL索引の性能評価ではない。
- 実tokenizer＋テンプレート全体の計測: 小規模3行411→697 tokens（候補は不採用）、繰り返し100行5,171→2,909（43.7%減）、異なる内容100行5,023→4,336（13.7%減）。全ケースの復元後JSONは原入力に一致。説明文を含めて小さい候補だけ採用する実装は妥当。codec作成中央値0.5～5.2 ms、候補の追加token計測331～341 msで、削減がない入力にも候補比較の負担がある。
- 読解の実モデル試験: 出力枠512では通常形式4/4が指定4項目に完全一致、圧縮形式4/4がJSON解析失敗。初回ハーネスは失敗時の原応答を保存していないので、finish_reasonを断定しない。1,600へ広げた繰り返し100行の再試験では両形式2/2一致。圧縮形式の推論量は1,066～1,104 tokens、通常形式334 tokens。アプリの可逆復元保証と、モデルの読解容易性・研究品質は別である。
- 速度比較: 並行推論が重なった初回の再試験時間は比較から除外。別プロセス終了後の単独実行の温まった1対では、通常17.82秒・圧縮48.88秒（約2.74倍）。この単純抽出課題では入力削減が推論増加を相殺しなかった。キャッシュ・モデル・課題依存の単発比較であり、全分析の速度改善率へ一般化しない。
- 根拠選択: 100件・1,024件の末尾に置いた重要発話は短語「副作用」で取得できる一方、自然文「副作用で中止した事例は何か？」と同義語「副反応」では取得できない。1,200件目は短語でも検索対象外。Coreでは引用済み根拠の候補内選択に用いるが、その候補が上限を超えた場合に取りこぼす。省略coverageが残ることは、根拠が十分選べることの代替ではない。
- 上流のスコア順位は `preferred=set(ranked)` と元順序への並べ直しで失われる。英語合成10件・1件上限では8回一致のev-9より、1回一致のev-1を選んだ。これは一致候補内では先頭優先になる制約。100件の選択中央値約6 ms、1,024件約56～59 ms。ASCII合成で2,000/5,000/10,000件は約99/139/215 ms。FixedEvidenceIndexが本文を保持していてもselectごとにbackendを作り直して全候補を登録するため、非検索部分も処理量へ効く。
- 管理ノートの16 KiB枠は根拠本文だけでなく除外一覧を含む。上流読取APIへ1ノートの合成段落を渡した一致なし検索で、100段落は11,108 bytesで成功、200/500/1,024段落はBudgetExceeded。ホストのpreviewはこれをpreview_failedへ変換する。ノートの入力bytes上限以下でも、除外情報だけで検索全体が失敗し得る。
- 隣接5モジュールの検証は108件成功、2 subtests成功、1件スキップ（Windowsの非特権symlink不可）。両有効化flagを外から立てた追加条件では107成功・1失敗・1スキップ。失敗はObusSQL無効／MAF開発有効時にもdev_bridge診断がmetadata.versionを呼ぶ境界。アプリ本体の修正はしていない。
- 試験は利用者checkoutの `.venv/Scripts/python.exe` とsrcで実行。archiveのpytest.iniが古いarchive/srcを優先するため、最初の収集は5 import errorsとなり、`-o "pythonpath=<利用者checkout>/src <開発資料checkout>/tests"` で参照先を明示して解消。再実行対象は test_context_delivery / test_maf_dev_bridge / test_metric_delivery / test_obussql_integration / test_required_methods_metric_context。全体のdiff --checkでは既存の対象外変更に空白警告があり、修正しない。新規評価スクリプトのpy_compileは成功。
- 推奨順: 自然文の検索条件と検索上限・スコア保持を改善、除外一覧の予算管理を改善、モデル別の読解負荷を含めて圧縮採用条件を見直す。可逆性の検証を緩めない。大規模・多様な研究課題の品質、通常アプリ全工程、PostgreSQL性能、ブラウザー、音声処理は今回未評価。
- 証跡は利用者checkoutの `output/validation/obussql-audit-20261110/` に results.json / quality.json / retrieval_extra.json / preview_budget.json / provenance.json / app-source-hashes.json / verification.json。再現用2スクリプトは開発資料ブランチの scripts/audit_obussql_usage_20261110.py と scripts/audit_obussql_quality_20261110.py。既存変更は保持し、commit/pushなし。
- 統計の単発実モデル試験は1,600出力枠でfinish_reason=length、生成1,600中reasoning 1,597となりJSON未生成。アプリ本来の統計レビュー予約は少なくとも3,200であるため、これは狭い出力枠での失敗と区別する。4,096枠の追加確認は `audit_obussql_quality_20261110.py <利用者checkout> --metric-only` を使用し、先行試験を上書きせずmetric_quality.jsonへ保存する。
- 統計の追加結果: 4,096枠でも176.25秒、finish_reason=length、completion 4,096中reasoning 4,093、contentは空でJSON解析失敗。1,600枠と合わせて2回とも専用decoderの実行へ到達しなかった。原モデルのreasoning_contentは元値・演算・schemaを繰り返し検討しており、値の改変やdecoderの受理失敗ではなく、回答生成の未完了と判定する。これは単発の合成統計コンテキスト＋GUIDANCEの試験で、アプリ全体の実行結果とは区別する。ホストcodecの108件試験成功を、現行モデルで統計レビューを安定完了できる保証へ読み替えない。次回は推論設定・指示長・schemaの読解負荷を比較し、完了率も圧縮採用・モデル選択の評価へ含める。
- 最終総合判断: JSONの可逆性と版・出典保護は機能し、繰り返し構造でのコンテキスト削減は実証。一方、検索範囲・自然文検索・順位・除外情報予算に制約があり、Gemmaの推論増加や統計回答の未完了も再現したため、速度・品質まで十分最適化済みとは評価しない。今回は調査として完了し、アプリ修正・研究品質承認・公開・commit/pushは行わない。

## 2026-11-10: 5種類の配送方式を比較して採用する計画

- 利用者の追加依頼により、5種類を実装して同条件で比較し、品質・速度・入力量が良い方式を採用する。候補は通常JSON一括、列形式、共通項目＋差分、共有文字列、構造に応じた混合。通常の分離メッセージと既存v1を対照とする。
- 復元後canonical JSON一致を必須とし、型・条件・例外・出典・切断済み本文を保持する。実モデルは現在ロード済みGemmaを用い、追加モデル取得・再ロード・外部送信・実データ利用はしない。合成課題の正答・完了を先に判定し、その後に総時間・推論量・token数で比較する。勝者候補は別課題と逆順再試験でも確認する。
- 共通修正として固定根拠の検索範囲・順位、自然文の検索語分割、管理ノートの除外情報予算を改善する。保存正本・SQL・Vault同期契約は変更しない。新しい配送形式は過去のv1復元も維持し、既存runの契約を置換しない。
- 評価コードと試験は開発資料ブランチのみ。アプリには採用方式と共通修正だけを残す。未コミットの他領域には触れず、関連回帰を一時DB/Vaultで実行する。

## 2026-11-10: 5候補の比較結果と混合配送の採用

- 利用者の依頼「5種類作成し良かった物を採用」に対応。利用者checkoutは `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の多数の未コミット変更は保持し、対象の配送・検索・利用案内と、開発資料側の評価・関連試験だけを変更した。commit/pushなし。
- 作成した5候補は (1)通常JSONの一括配送 (2)列形式の表 (3)共通項目＋差分行 (4)共有文字列参照 (5)通常JSON・列形式・共通項目を配列ごとに選ぶ混合。対照は従来の分離メッセージと既存readable-v1。候補全てのcanonical JSON往復一致と改変拒否を合成試験で確認し、元本文・型・否定・例外・切断済みJSON文字列は保持する。
- 一次比較は各方式に同じ2課題を提示し、課題ごとに実行順を反転。ロード済みGemma 4 12B QAT、16,384 context、temperature=0、max_tokens=2,048、追加推論は既定のまま、全呼出しを逐次実行した。後続の別課題と採用コード確認を含む3段階の全計測でモデル・load設定hashは同一だった。モデル追加取得・再ロード・設定変更・クラウド送信はしていない。
- 一次の指定8項目の完全一致: 一括JSON2/2、列形式0/2、共通差分1/2（1件出力枠超過）、共有文字列2/2、混合2/2。通常形式は2/2、旧readable-v1は1/2。列形式では数値に0を付け足すモデル出力を観測したが、元JSON・復元データは改変されていない。一括JSONは通常形式より大きく、共有文字列は少ない削減に対して遅かった。
- 上位2案はID・数値・条件・例外を変えた別課題で再試験し、10%以上かつ128 tokens以上減らない候補は通常形式に戻す実際の採用条件も通した。混合2/2、共通差分の条件付き採用1/2、通常形式0/2。通常形式にも整数の桁が増える誤答を再現したため、通常へ戻すだけでは品質問題を解決しない。共通差分の未削減課題は実際にnativeへ戻り、その同じ誤答を観測した。
- 品質（数値・条件・例外の完全一致と回答完了）を必須とした比較に基づき混合を採用。最終のアプリ実装で元の2課題を再確認し2/2一致。混合は一次2・別課題2・最終コード2の計6/6一致、実モデル総呼出し22回。これは限定した合成抽出課題の結果で、研究上の妥当性や他モデル・他課題への一般化を保証しない。
- 最終コードの元課題の入力token: 繰り返し6,596→2,095（68.24%減）、内容が異なる課題4,863→4,081（16.08%減）。一方、同じ元課題の通常形式平均44.62秒に対して、最終コード平均77.56秒。推論量が増え、今回は高速化していない。順序反転・逐次実行を行ったがcache・課題・量子化モデルの影響を含む小標本である。誤答の速さより正答と入力量を優先した採用で、最速方式や総合的な速度最適化済みとは扱わない。
- アプリの配送形式は `obussql-adaptive-context-v2`。配列ごとに通常JSON・列形式・共通項目と差分行からUTF-8 bytesの小さい表現を選び、全体は同じロード済みモデルの実tokenizer・テンプレートで再計測する。通常形式が枠内なら削減10%以上かつ128 tokens以上で採用。枠外ならより小さい候補も許すが、出力予約・安全余白・最終fits判定は緩和しない。採用理由の基準・実測・元hash・復元一致を既存manifestへ記録する。本文の共有文字列参照や埋込JSONの再解釈は新方式では使わない。旧v1の復元と改変拒否は継続する。
- 実行契約を `core-handler-prompts-51-obussql-adaptive-context` へ更新し、旧runを新契約で暗黙に再開しない。新方式はアプリ再起動後の新規runへ適用する。実利用者アプリの停止・再起動は今回行っていない。不採用候補の実装は開発資料側の `scripts/obussql_delivery_candidates.py` へ保持し、アプリは混合方式を使う。
- 共通修正: FixedEvidenceIndexのrun内backend再利用、取得時の固定本文照合の維持、全文優先＋最大8検索文字列の質問分割とja_surface_v1、全候補の256件ずつの検索、バッチをまたぐスコア比較、採用決定後の発話順への復帰。1,200件目の自然文検索と、スコア8回一致が1回一致より優先されることを検証。選択方式は `obussql_keywords_surface_v1`。同義語や意味検索は未対応のまま。
- 管理ノート検索は上流上限の10,000ブロックまで調べ、内部取得8 MiB・返却context16 KiBを分離。除外先頭16件と、理由別件数・総数・完全性・全除外一覧hashを返す `gurumoji-summary-context-v1` を導入した。大きい根拠本文は切断しない。1,200段落の一致なし・末尾一致を実VaultRegistry・実obsipg・一時Vaultで通過。10,000一致ブロックの配送整形は約55 ms、16,346 bytes、104件を配送し残る9,896件の除外総数を保持した。返却context上限と内部の処理上限・入力正本は別である。
- ObusSQL無効／MAF開発有効時の診断が任意依存のmetadataを先に読む問題も修正。両flagを明示して実行した最終8モジュールは163件成功・14 subtests成功・1件スキップ（Windows非特権symlink）。ブラウザー7件成功、合計170件成功。大きなノートの読取後に一時データのbytes/mtimeが変わらないこと、過去v1の復元、共有キーの上書き拒否、小削減時の不採用、通常形式が枠外の候補利用、adapterの実配送・manifestを含む。
- py_compile、JavaScript構文、pip check、対象追跡ファイルのdiff --checkは成功。ブラウザーfixtureのmkdirが共通隔離fixtureと衝突した初回エラーは、開発資料側でexist_ok=Trueへ直し再検証した。実Vault、利用者DB・本文・タグ・別名、資格情報、SQL schema、保存・同期・移行は未変更。
- 証跡: 利用者checkoutの `output/validation/obussql-five-20261110/verification.json`、screening.json、confirmation.json、adopted-recheck.json、screening-summary.json、app-source-hashes.json、retrieval.json、preview-performance.json、browser/。評価入口は開発資料ブランチ `scripts/compare_obussql_five.py`。再現例は `--app-root <利用者checkout> --output <新しい結果JSON>`。別課題は `--profiles native,defaults,adaptive --held-out --production --select-smaller --reverse`、採用後確認は `--profiles native,adaptive --production --select-smaller --skip-native`。任意出力先を使って既存の失敗・成功記録を上書きしない。
- 未評価: 実研究データ、全自律分析の実モデル完了・研究品質、PostgreSQL、音声処理、他モデル、追加推論OFFの比較。統計codecの単発未完了を今回直したとは扱わない。今後の速度改善は推論設定・長い検討の終了・モデル出力の数値束縛を別に検証し、可逆性と今回の正答条件を維持する。

## 2026-11-10: インターネット調査で見つけた別プラン

- 利用者の追加依頼「ネットを検索して別のプランが無いか検索」に対応し、公式資料・一次資料を検索。実行場所・ブランチ・HEADは前節と同じ。採用済みアプリコード・モデル設定はこの調査では変更せず、新しい実モデル試験はしていない。
- 最優先候補はGemmaの思考制御。Google公式はGemma 4の思考ON/OFF、LOW相当のシステム指示、12B等のOFF時のghost thoughtを抑える空thoughtチャネルのテンプレートを説明する。単に自然文で思考しないと指示することと、正しいテンプレートでOFFにすることを区別し、実際のreasoning出力数を測る。GoogleのGemmaはON/OFFが基本で、LOWは指示による調整である。LM StudioのネイティブAPIにはreasoning指定とreasoning_output_tokens・TTFT等の統計があるが、現在のOpenAI互換経路でどう適用されるかは別確認が必要。
- 第2候補はSQL/Python側での抽出・集計・定型報告。現行でも算術はアプリ側にあるが、追加案では数値の転記・表示もモデルから外し、モデルは出典IDや必要な解釈を返し、元値をホストが参照する。Anthropicのcode execution with MCPは、データをモデルへ全量渡す前にfilter・join・aggregateする構成を紹介する。MCP導入自体を必須とせず、既存のObusSQL/Gurumoji境界へ原則を適用する案である。
- 第3候補はBM25＋意味検索＋reranker。AnthropicのContextual Retrievalはチャンクごとの文脈情報とBM25・embedding検索を組み合わせる。発話の索引へ会話・議題・話者・版の短いメタデータを付け、根拠本文は元の発話と隣接範囲を保持する案。同義語を扱える可能性があるが、日本語・実データでの検索漏れと再順位付け時間は未計測である。
- 第4候補は固定接頭部のKVキャッシュ。llama.cppは共通prefixの再評価を避けるcache_promptを公式に説明している。固定指示・専門家定義・同じ版の資料を前へ、可変の問いやIDを後ろへ置く案。ただし現在のLM Studio実機での有効化・cache命中は未確認で、思考token自体やコンテキスト枠の消費を減らす方法ではない。
- 第5候補はspeculative decoding。LM Studio公式は小さいdraftモデルの候補を本体が検証する方式を説明する。同じvocabularyと対応する組合せ、追加の計算・メモリーが必要。現在のGemma 4 12Bと使えるdraftがあるとは未確認で、今回追加取得・再ロードしていない。
- 形式変更の候補としてTOONも確認。JSONデータモデルの可逆表現で、均一な表に向く。一方、公式README自体が深い不均一データにはcompact JSONが有利、ローカル・量子化環境ではJSONの方が速い場合がある、と記載する。AAIFの2026-10-30公開のApify開発者の報告でも、本番30日と2回のA/Bで一貫した利益がなくTOONを撤回した事例がある。TOONを現行混合の自動上位互換とは評価しない。
- LLMLingua-2はMicrosoftの学習済みtoken分類器による抽出的なプロンプト圧縮。元JSONと完全一致する可逆配送とは別の方式なので、試す場合も検索用要約や過去のAI報告などに限定し、発話正本・数値・条件・否定の完全保持を保証済みとは扱わない。
- 推奨は、まず通常JSON／現行混合と、思考ON／正しくOFF／短い思考指示を交差させた6条件の比較。その後にSQL側の定型処理、検索強化を評価する。総時間・TTFT・入力tokens・reasoning tokens・実出力tokens・数値/否定/例外の一致・未完了率を別々に測り、以前の6/6を一般的な研究品質保証にしない。以上は資料からの適用判断で、導入効果の実証ではない。
- 一次資料: https://ai.google.dev/gemma/docs/capabilities/thinking 、https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4 、https://lmstudio.ai/docs/developer/rest/chat 、https://www.anthropic.com/research/code-execution-with-mcp 、https://www.anthropic.com/research/contextual-retrieval 、https://www.anthropic.com/research/effective-context-engineering-for-ai-agents 、https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md 、https://lmstudio.ai/docs/app/advanced/speculative-decoding 、https://github.com/toon-format/toon 、https://www.microsoft.com/en-us/research/project/llmlingua/llmlingua-2/ 、https://aaif.io/blog/we-added-toon-to-our-mcp-server-then-removed-it 。


## 2026-11-10: 公開代替案の実測比較

- 利用者の「それぞれテストして比較した結果を」に基づく実試験。対象は `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と既存未コミット実装。生成API56応答、投機的デコードの拒否1回、日本語検索25問を検査した。アプリコード、実利用者DB/Vault、認証、共有モデルのロード設定は今回変更していない。モデル一覧とロード設定は取得前後一致。再起動・commit/pushなし。
- 全入力は合成資料。80件の反復表と60件の異種表、ID・数値・否定・例外を変えたholdoutを合わせ4課題。各課題で指定ID2件の条件・例外・整数を完全一致で検査。意味解釈や一般的な研究品質は保証しない。Gemma4 12B QAT、context16384、temperature0、最大出力2048。モデル生成・CPU検索・圧縮の測定は逐次実行し、初期の生成測定中だけ公開重みを取得した。
- 推論6条件はoriginal2課題ずつ。原形式はON32.327秒/推論543.5tokens、短い推論指示32.339秒/557tokens、OFF8.848秒/0tokens。現行混合はON35.697秒/691.5tokens、短い推論29.795秒/575.5tokens、OFF6.325秒/0tokens。すべて2/2一致。native APIでON/OFFを明示し実推論tokensを照合。「短く考える」はOFFの代わりにならない。現行アプリには既にOFF指定の経路があり、以前の既定ONの速度をアプリ通常速度とは扱わない。
- OpenAI互換APIでJSONスキーマを強制した再試験は、原形式が平均入力5942.75tokens/9.488秒/4/4一致、現行混合3454.25/7.173秒/4/4、TOON4746.75/8.409秒/4/4、Python側でIDを照合して資料を絞る方式751.25/6.728秒/4/4。native APIのJSON指示だけの別試験でも4形式とも4/4。2経路は別集計で保持する。現行混合は原形式比で入力41.88%減、スキーマ測定の時間24.40%減。TOONの往復復元も一致したが、現行混合を上回らなかった。
- SQL/Python移管は、モデルにIDだけを返させ、条件・例外・整数は一時SQLiteから原文を復元する方式が712tokens/2.547秒、4/4一致。明示IDだけの定型取得ならAIを呼ばないSQLite照合も4/4で、各課題100回の中央値を平均して0.005825ms。DB作成時間は除く。意味解釈や自由な分析の代替とは扱わない。host.jsonとgeneration.jsonに生結果を保持。
- 検索は合成132文書、文字一致寄り12問・言い換え12問・ID1問の25問で、正解が上位3件に入るかを評価。現行ObusSQL13/25（中央値11.379ms）、文字2gram BM2516/25（0.229ms）、multilingual-e5-small25/25（8.998ms）、BM25+denseのRRF22/25（9.365ms）、RRF+日本語xsmall reranker23/25（32.859ms）、同方式にID優先を足すと24/25（32.862ms）。意味検索+ID優先は25/25、top1は24/25、9.002ms。現行は最後に時系列へ戻すのでtop1を比較せずtop3集合で評価した。複雑な混合・再順位付けが常に良いとは判断しない。
- 検索はCPU4threads。denseロード1.723秒・文書索引0.442秒、rerankerロード0.434秒を検索時間とは別掲。初回6方式の結果はretrieval-initial.jsonへ残し、ID優先のdense候補を追加して7方式を再測定した。小規模の合成コーパスであり、実運用規模・隣接会話・否定の意味解釈・更新時の索引失効は未検証。
- prefix再利用は固定資料を先頭、可変質問を末尾に置いた4組。入力は各6130tokensのまま、TTFT中央値3.836秒から0.423秒、総時間中央値4.037秒から0.489秒。8応答すべてOK。APIにcache命中件数がなく完全coldも保証できないので、応答開始時間の観測結果とする。コンテキスト枠や推論量の削減ではない。
- LLMLingua-2は公開XLM-RoBERTa-large重みをCPUで使用し、rate0.5、数字・否定等のforce保持も指定。平均入力3641tokens、圧縮9.944秒を含め17.753秒（ロード1.017秒は別）。完全一致0/4、対象原文の完全保持0/4。例外が「再検査が陰性ない。」へ欠け、ev-0019のvalue133を19として返した。原文・条件・数値を扱う配送には採用不可。初回accelerate不足は検証用depsへ1.12.0を追加して解消し、4応答を再測定した。初回suite.jsonの失敗を残したままverification.jsonへ復旧を記録。
- 投機的デコードはSDKの予測時draft指定を現行engine protocolが「must be configured at load time, not prediction time」と拒否。共有モデルは再ロードしていない。対応する小型draftも未導入だが、今回の直接原因はロード時設定の要求。速度・品質は未測定で、拒否までの0.312秒を生成性能へ数えない。
- 依存は検証用output配下のdepsだけに固定版を追加し、アプリvenvの依存を更新していない。TOON1.2.0、LLMLingua0.2.2、rank-bm250.2.2、accelerate1.12.0。取得hashはpip-report.json/accelerate-report.json、公開重みのrepo/revisionはmodels.jsonへ保持。rerankerは8547ac84ae5aee35387aad7000b379bd1b968dc6、compressorはebaba9b0e874dadd3003ffcff828e4397e568089。各公開モデルはMIT。e5は既存重みキャッシュを利用し、研究者の本文は使っていない。
- 判断は現行可逆混合と推論OFFを維持し、定型原文・数値取得をSQL/Pythonへ移す案を優先する。検索の次候補はID優先+意味検索。prefix配置も有望だがアプリ全体の実行経路は未実装・未測定。TOONへの置換、LLMLingua-2による原文圧縮、未測定の投機的デコードは採用しない。今回、新案をアプリへ反映していない。
- 各形式・課題は1回ずつで、順序・内部キャッシュの影響が残る。統計的有意差や研究解釈品質は主張しない。証跡は利用者checkoutの `output/validation/obussql-alternatives-20261110/summary.json` とverification.json。生応答はgeneration/structured/host/cache/compression/speculative.json、検索順位はretrieval.json、実装hash・環境版はsummary.json、設定前後はmodels-before/models-after.json。新規評価・記録スクリプト6本のASTと空白を確認した。今回アプリコードを変更していないので、既に完了した170件の回帰試験は再実行していない。


## 2026-11-10: Gemma QATの投機的デコードを実動比較

- 利用者の「投機的デコードをしっかり試して」に基づき、前回の予測時API拒否から踏み込み、ロード時MTPと実生成を試験。利用者checkoutのHEADはd8707f2e02e4e1a74a5d3cb4d6c728e3f5691486、ブランチはkrokharu/transcription-finish-20261102。評価コード・本記録は開発資料ブランチへ保持し、アプリコード・実利用者DB/Vault・認証・接続先は変更していない。
- LM Studio CLIのCPU専用インスタンスで `--speculative-draft-mtp` を実行すると、現行GGUFは「bundled supported MTP head」がないためロード拒否。試験専用インスタンスだけを扱い、この時点で元の設定は不変。公式issue2244にも外部Gemma assistantの制約が報告されている。外部assistantを内蔵型扱い・単独モデル扱いで強制せず、公式llama.cppの外部MTP経路へ切り替えた。
- 固定エンジンb9553/9e3b928fd8c9d14dbf15a8768b9fdd7e5c721d66、Windows CUDA13.3の配布zip2本を公式GitHubから取得し、公式asset digestとSHA256一致を確認。RTX5070/12GB、driver610.88。元のQAT本体は読み取りだけで使用し、対応assistantはensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant、revision e9aaf2d12229b0b11d7e8b2c8821c5648c48334e、322915136bytes、SHA256 25f143b4c15b20cd04216e35e99bd7a56afc6f65e7a4e090a3e20091bb590cbb。GoogleのQAT対応assistantを変換したApache-2.0の公開重み。取得物は検証output内だけに置いた。
- 利用中のGemmaがidle/queued0であることをCLIで確認し、ロード状態をAPIとSDKで保存。GPU比較中だけ元インスタンスをunloadし、専用localhost:19841のサーバーを起動した。終了処理finallyで試験プロセスを停止し、元のID・GPU比0.8・context16384・parallel4を復元。probe・本試験・推論ON追加試験の各段階で、全モデル一覧とロード設定が試験前後で完全一致した。APIサーバーやアプリ設定ファイルを切り替えず、実利用者の本文を入力していない。
- 予備GPU実動は原文抽出に完全一致し、draft75件中68件を採用、生成145.8tokens/sec。動いていない指定や通常生成へのfallbackを成功とせず、以後すべてのMTP測定でもdraft_n/acceptedが正であることを検査した。
- 本比較は同一エンジン・本体・テンプレート・schema・全GPU層・context8192・並列1、batch2048/ubatch512、temperature0/seed42、推論OFF、cache_prompt=false、cache-ram0/checkpoints0。反復表・異種表と各holdoutの4課題、および8件の長い原文出力の計5課題を各条件2回。通常生成を最初と最後に置いた計50測定と、各条件warmup5回を実行した。warmupは速度集計から除く。入力tokensは課題内で全条件同じで、全50回のcache_nは0。
- 通常生成（前後20回）は平均3.899秒、重み付き生成速度62.92tokens/sec、20/20完全一致。MTP2は平均2.404秒/131.55tokens/sec、採用1066/1156。MTP3は2.277秒/148.12tokens/sec、採用1202/1344。MTP5は2.116秒/170.67tokens/sec、採用1332/1580。MTP各10/10完全一致で、先読み5がこの範囲では最速。生成速度2.71倍、入力処理を含む総時間は45.74%減。
- 本試験50回すべて、ID・条件・例外の原文字列・整数を期待値と一致で確認し、finish=stop。通常とMTPでJSON空白や出力tokensが異なる例はあるが、元の内容は変わっていない。長い8件出力では全条件400出力tokensで、JSON本文のbytes一致もTrue。単なる出力短縮だけで速度差を説明する結果ではない。
- 推論ONも通常/MTP5で、撤回・未提出・検査不明・否定の例外判定と整数合計の2課題を各2回、計8測定。期待ID集合と合計は一時SQLiteでも独立照合した。通常は4/4一致、平均28.377秒、61.60tokens/sec。MTP5は4/4一致、平均7.860秒、172.69tokens/sec。各応答で思考内容が非空であり、ONを確認。warmup2回は除く。
- 推論ONの初期採点に変数名衝突があり、一致を不一致と表示した。モデル要求・生応答・時間は影響なし。採点処理を修正し、生textを再parseして、別SQLite計算による期待値と独立再照合。初期値を消さずreasoning.jsonに保持し、修正値とinitial_exactはreasoning-scored.jsonに保存した。成功に見せるための期待値変更やモデル再生成はしていない。
- 検証済みは合成58測定、全件完全一致・完了。MTPは全34測定で提案・採用を実測。実研究データ・画像/音声・並列処理・高温度の分布同一性は未検証。元のLM Studio設定（GPU0.8/parallel4/context16384）と専用サーバー（全GPU/parallel1/context8192）は違うため、過去のアプリ時間との差をMTP単独効果とは扱わない。生成速度は実出力tokens合計/生成時間合計、総時間は呼出し平均で比較した。
- 判断: この機械・資料では先読み5のMTPは採用価値がある。ただし現行LM Studioの外部headロード制約は残り、今回の有効化は検証用llama.cppだけ。アプリの本番接続変更や恒久常駐は行っていない。最終的には元のモデルを復元した。モデル容量・補助重みのhashと実装hashはsummary.json、配布hashはengine-manifest.json。証跡は利用者checkoutのoutput/validation/obussql-speculative-20261110/にbenchmark.json（50件）/reasoning.json（8件、生採点）/reasoning-scored.json/summary.json、原設定・復元はoriginal-models/restored-models.json。専用サーバーログには合成入力だけを保持。
- 一次資料: https://github.com/ggml-org/llama.cpp/releases/tag/b9553 、https://github.com/ggml-org/llama.cpp/blob/b9553/docs/speculative.md 、https://ai.google.dev/gemma/docs/mtp/mtp 、https://huggingface.co/ensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant 、https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/2244 。


## 2026-11-10: SQL・投機的デコード・ハイブリッドの同条件比較

- 利用者の「投機的デコード SQL ハイブリット 比較して」に基づき、過去の異なる条件の値を並べるだけでなく、新しい同条件試験を実施。利用者checkoutはkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486と既存未コミット実装。コード・本記録は開発資料worktreeへ保持し、アプリ・実利用者DB/Vault・認証・本番接続は変更していない。
- 比較は、全文をAIが返す方式、AIがIDだけ選んでSQL/ホストが原文・数値・合計を確定する方式、それぞれの通常生成/MTP5、およびAIを呼ばないSQL/ホスト処理。MTPはモデルの高速生成、SQLはデータ処理なので併用可能である。元の通常処理との比較も対照として保持した。
- 5つの原文抽出と2つの条件判定・整数合計、計7合成課題。AI方式は各課題2回、4方式で計56測定とwarmup4回。SQL側は各課題200回、計1400回。通常/MTPとも同じGemma4 12B QAT、本体/assistantは前回と同じhashの固定重み、公式llama.cpp b9553、RTX5070全GPU、context8192/parallel1、batch2048/ubatch512、temperature0/seed42、推論OFF、cache_prompt=false。モデル・DBの作成時間は除外し別掲し、SQLは照合・復元・JSON化・整数合計、AI側は入力準備・生成・復元・JSON化を含めた。
- SQLは平均0.017036ms（課題別中央値の平均）、1400/1400一致、7/7課題、モデル入力0/呼出し0。SQL側の合計はPythonによる整数合計を含む決定的なホスト処理で、SQL SUMでも別照合した。既知の2条件を事前クエリ化しているため、自由文からSQLを生成する時間・品質を含まない。未知条件にもSQLだけで答えられるという評価ではない。
- 通常AI全文は平均3.150429秒、入力2705.00tokens、12/14一致。通常AI+SQLは1.035456秒/572.00tokens/14/14一致。MTP5全文は1.711824秒/2705.00tokens/12/14一致。MTP5+SQLは0.519854秒/572.00tokens/14/14一致。
- MTP5+SQLはMTP5全文に比べ総時間69.63%減、AI入力78.85%減。生成は全応答finish=stop、思考内容なし、cache_n=0を確認。MTPの全28測定で実draft/採用が正であることを確認し、通常生成へのfallbackを成功扱いしていない。
- 不正答はsummary.jsonのfailuresへ期待値・実応答ごと保持。例外のある条件課題でID集合が合っていても、AI全文方式が合計228を188と返す例を確認。AIが選んだIDからホストが元値を取得・計算する方式ではこの転記・算術の責務をAIへ持たせない。試験は推論OFFであり、以前の推論ONで8/8正答した結果と混同しない。今回の小さな課題集合の正答率を一般的な研究品質とは扱わない。
- 判断: 明示ID・既知条件の定型処理はSQL/ホスト単独が最速で、不要なAIを追加する意義は小さい。自然文の条件判断をAIへ任せ、出典本文・整数を元データへ戻す用途では、MTP5+SQLがAI全文より有望。自由な意味検索、未知の条件、研究上の解釈、並列動作は未検証である。今回の7課題で優位なことと、全分析工程の最適構成を区別する。
- 一時SQLiteと合成資料だけを使用。元のモデルidle/queued0を確認してから一時unloadし、測定後は専用サーバーを停止、元のID/GPU0.8/context16384/parallel4を復元。全モデル一覧とロード設定の前後一致を確認した。commit/pushなし。証跡は利用者checkoutのoutput/validation/obussql-sql-hybrid-mtp-20261110/にcomparison.json（56測定・1400SQL照合・warmup・ロード時間）/cases.json/summary.jsonと原設定・復元JSON。2本の新規スクリプトと利用helperのAST・空白・hashを検査した。アプリを変更していないため既存回帰試験を再実行していない。


## 2026-11-10: LM Studio本体で外部MTPを有効化・速度比較

- 利用者の「LM Studio版使えるようにして、そのバージョンで速度を検証」に対応。利用者checkoutはkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486。実験コードは開発資料worktreeだけへ追加。既存の未コミット変更、実利用者DB/Vault、Gurumoji runtime、認証設定、本番API接続は変更していない。commit/pushなし。
- 前回の「現行LM Studioは外部Gemma MTP非対応」という判断を訂正。内蔵ヘッド用CLIフラグ --speculative-draft-mtp の拒否は実際に再現したが、外部用のllm.load.llama.speculativeDecoding.draftMtpSidecar経路を見落としていた。公式0.4.22変更履歴にはMTP assistant対応の記載がある。インストール済み0.4.25+1、公式CUDA12 2.71.0のままで動作し、アプリ更新・実行ファイルのパッチ・代理API・外部常駐サーバーは不要だった。
- 専用assistantをlms import --hard-linkでLM Studioのmodelsへ登録。本体は既存google/gemma-4-12b-qatの同じQAT Q4_0。SDK 1.5は新しいロード項目を無視するため、実験プロセス内だけの通信変換でKV load層を追加した。SDK本体やアプリの配布コードは変更していない。実行エンジンの親PIDはLM Studio.exeで、同アプリの1234番API経由で生成したことを資格情報を伏せたprocess証跡に保持した。
- 原設定のGPU0.8/context16384/parallel4を揃え、checkpoint0、temperature0、逐次要求、同じGemma/assistantで比較。通常→MTP3→MTP5→通常の前後対照を取った。ロード時間は除外し別掲。合成7課題×全文/AI選択+一時SQL復元×各2測定×3方式=84測定、条件判定2課題×推論ON×通常/MTP5=4測定、計88測定。warmupとロード証明は別。JSON schema制約のないnative chat APIを使用した。
- 各課題の資料と指示は同じだが、長いprefix再利用を減らすためsystem先頭へ識別子を付与。通常の前後は反復番号0、MTPの反復は0/1。完全なcold cacheは保証しない。全方式で課題別input tokensは一致。過去のb9553/全GPU/context8192/parallel1/構造化出力とは設定・APIが異なるため数値や正答率を直接混ぜない。

|方式|本文生成/復元|推論|一致|平均秒|生成tokens/秒|平均入力tokens|
|---|---|---|---:|---:|---:|---:|
|normal|full|OFF|10/14|7.901627|21.415|2713.6|
|normal|full|ON|2/2|71.087325|22.279|410.0|
|normal|hybrid|OFF|12/14|2.297979|22.315|580.6|
|mtp3|full|OFF|10/14|4.406394|48.553|2713.6|
|mtp3|hybrid|OFF|12/14|1.238083|51.932|580.6|
|mtp5|full|OFF|10/14|4.189291|52.396|2713.6|
|mtp5|full|ON|2/2|29.792641|53.295|410.0|
|mtp5|hybrid|OFF|12/14|1.158956|56.857|580.6|

- 原文抽出5課題だけの本文生成は、通常9.959884秒/21.165tokens毎秒、MTP3は5.614602秒/47.903tokens毎秒、MTP5は5.370159秒/51.281tokens毎秒。各10/10一致。MTP5のSQL復元方式は1.241888秒/10/10一致だが、これは実験用経路でGurumoji全工程へ組み込んだという意味ではない。
- 原文抽出5課題は3方式それぞれ全文10/10、SQL復元10/10一致。条件判定・整数合計では推論OFFの通常/MTP双方に同じ誤答があり、MTPを品質改善として扱わない。推論ONの全文は通常2/2、MTP5も2/2一致したが小標本。独立採点で生JSONを再parseし、原文と指定ID、および別の一時SQLite WHERE/SUMで期待値を照合した。失敗応答も保存した。
- 先読み5を今回の速度結果から採用。LM Studioのモデル固有既定値 user-concrete-model-default-config/google/gemma-4-12b-qat.json に外部MTPと同じcontext/GPU/parallel設定を保存。原設定の有無/bytesをdefaults-backup.jsonへ保持。追加ロード引数なしのlms loadで再ロードし、実draft提案・採用を再確認してMTP有効のまま引き渡した。元のモデルID・APIポートは継続。rollbackは同スクリプトのrollbackで既定値を元bytesへ戻し、元ロード設定へ復帰する。
- /api/v1/modelsの旧形式speculative_draft_mtp=false/draft_model空欄はsidecar項目を表現しない。MTPの動作判定にはロード層のdraftMtpSidecarと、SDK/OpenAI応答のusedDraftModelKey・totalDraftTokensCount・acceptedDraftTokensCountを使う。各MTPロードと最終再ロードで提案/採用を確認したが、native chat APIの88測定個別のdraft数は取得できない。
- 最終保存後にも原文抽出2件・SQL復元1件の計3応答を追加確認し3/3一致。短い本文抽出3.143980秒、8件の本文抽出11.925359秒、8件のSQL復元3.352947秒で、統制測定より遅い回もあった。初回モデル復帰時のwarmupも38.674tokens毎秒と変動した。同じ実行引数（GPU39層、context16384、parallel4、MTP5）をinstalled-runtime-process.jsonに確認し、再ロード後も同じ速度を常時保証するとは扱わない。
- 実研究の品質・画像/音声・同時4要求・Gurumoji分析全工程は未検証。設定上のparallel4と実同時要求の検証を区別する。アプリ本体コードは今回変更していないため、既存回帰試験は再実行していない。新規2スクリプトの構文確認と生応答の独立再採点を実施した。
- 証跡: 利用者checkoutのoutput/validation/obussql-lmstudio-mtp-20261110/benchmark.json（88測定）、independent-scoring.json、summary.json、install.json、installed-defaults.json、defaults-backup.json、lmstudio-runtime-process.json。実行/復帰: 開発資料scripts/lmstudio_mtp.pyのbenchmark / install --draft-tokens 5 / rollback。
- 一次資料: https://lmstudio.ai/changelog/lmstudio 、https://lmstudio.ai/docs/app/advanced/per-model 、https://lmstudio.ai/docs/app/advanced/speculative-decoding 、https://huggingface.co/ensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant 。


## 2026-11-10: SQLを標準にしてハイブリッドを選択可能にする

- 利用者の「SQLを基本として、ハイブリット方式を選択肢として使えるようにして」に対応。利用者checkoutはkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486と既存未コミット変更。対象以外の編集を保持し、commit/pushなし。
- 対象は自律分析の根拠取得・引用原文の復元。解釈には両方式で既存AIを使い、数量・統計は既存の決定的処理を維持する。自由な研究質問への全分析をSQLだけで完結する機能ではない。MTPは生成エンジンの設定として両方式と独立に併用できる。
- 新規runのevidence_modeはsqlが既定。hybridも明示選択でき、不正値は開始前に拒否する。分析設定の「根拠の取得方式」、POST開始payload、保存config、履歴表示まで接続。再開時に別方式へ暗黙に変えない。adapter契約はcore-handler-prompts-52-sql-evidence-hybridへ更新し、旧runを新方式として再開しない。
- SQL索引はrun単位の一時SQLite。固定発話をJSONとhash付きで登録し、256件ずつ全候補をparameter bindingで取得する。指定ID、全文一致、最大8検索文字列で順位付けし、完全な発話単位で上限内に選んで発話順に戻す。本文だけでなく呼出し側の投影項目（ID・話者・時刻等）と型を照合する。MAFではrun中に索引を再利用し、終了時にclose。通常adapterでもSQL取得を使う。管理ノートの読取プレビューとcodecは従来のObusSQL接続を維持する。
- ハイブリッドは追加の検索AIを呼ばず、既存分析AIのclaims/issues/label_patches/label_definitions/label_requirements/claim_verdictsの引用IDを使用する。将来読むintents/analysis_requestsの対象IDは引用と区別する。原応答を従来のraw_jsonへ保存して既存検証を通した後、SQLで復元した原文・話者・時刻・入力版・hashを既存result metadataのevidence_resolutionへ追加する。AI原応答を書き換えず、未提示・不存在の引用IDと件数/文字数上限超過は隔離する。SQLへの自動fallbackはしない。引用原文は保存結果ビューへtextContentで表示する。
- 既存SQLカラム・保存先・Vault同期を変更しない。追加は既存configとresult metadataの任意JSON項目で、旧結果の閲覧は継続する。原文・数値の照合は引用の同一性の確認であり、意味の妥当性を証明しない。実利用者アプリの再起動は行っておらず、反映後は再起動して新規runで選択する。
- 合成の一時DB/VaultだけでPython関連10モジュール140件成功。SQL注入文字列、1,220件目の一致、指定ID優先、本文/話者/時刻差替え、hash破損、重複/未提示/不存在のID、上限、4スレッド読取、将来の依頼IDの分離、両モードの開始→結果保存→HTTP書き出し、原応答保持、AI呼出し数が増えないことを検証。初期の旧Flask結合fixtureは、以前のCore応答形式を現行next_step契約に返して失敗していたため、旧形式fixtureの設定をcore_control_version=0と明示した。製品のCore制御は1のまま、専用Core契約試験も同時に成功。MAFフラグ有効時に旧provider stubが追加kwargsを受け取れない点も切り分け、通常Flask試験は通常プロファイル、MAF試験は試験内で有効化した。
- DOM操作30件成功（新規2件を含む）。SQL既定、選択したhybridの送信、履歴、原文表示、HTML注入拒否、閲覧による追加AIなしを確認。Edgeで実テンプレートのPC幅1100×900とモバイル幅412×915を開き、既定と選択操作・横にはみ出さないことを確認。スクリーンショットを目視確認した。ブラウザーは合成画面で、実利用者データへ接続していない。
- LM Studioの同じgoogle/gemma-4-12b-qatへ実AI境界の要求を各方式1回、計2回。いずれも指定した2件目の発話IDを返し、SQLから取得した条件・例外・数値を含む原文が完全一致。SQL側4.735秒、hybrid側5.016秒の小規模確認で、追加の分析AI呼出しは各1回。これは以前のID専用応答による高速化ベンチマークとは異なるため、その速度効果を製品へ転用しない。LM Studioのモデル設定・接続先・認証設定は変更していない。
- 構文確認、JavaScript検査、対象差分の空白検査は成功。実研究データでの意味の正答率、全アプリ全試験、実稼働アプリの反映後確認は未実行。証跡は利用者checkoutのoutput/validation/sql-hybrid-selection-20261110/summary.json、unittest.log、model.json、desktop.png、mobile.png。実装hashはsummary.json。再現用verify_sql_hybrid.pyと新規試験は開発資料worktreeだけに保存した。


## 2026-11-11 ローカル最新版の確定と開発ブランチ整理

- 利用者は11月11日20:16までのローカル内容を最新版とし、開発用ブランチ・作業ツリーの統合削除を依頼した。GitHub上の開発用ブランチも整理することを明示確認済み。main、公開版、開発資料の保存用ブランチを残す。
- 正本は利用者checkoutの未コミット状態。開始時ブランチは `krokharu/transcription-finish-20261102`、HEADは `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。最終コミット日時とローカルの更新日時を区別する。表示版 `β0.46.1` は今回変更しない。
- mainは既存 `origin/main` の履歴を継承して現行ファイルを保存する。過去の試作コードを最新版に再適用せず、旧履歴を公開用mainへ再接続しない。開発資料・試験の未コミット更新は本ブランチへ保存する。
- 整理前の全Git参照を `all-refs.bundle` へ保存し、独立した履歴として復旧可能なことを `git bundle verify` で確認した。13作業ツリーのファイルをローカルの復旧先へ退避し、全ファイルのSHA-256をアーカイブから読み戻して照合した。旧試作固有の未保存変更・除外ファイルも補助作業ツリーの退避に含め、Gitには追加しない。復旧先は利用者checkoutの兄弟ディレクトリ `gurumoji-consolidation-backup-20261111`。
- 個人設定、別管理のObusSQL、Obsidian設定、復旧用コピーの除外規則はリモートmainの既存規則を継承した。runtime、認証設定、研究者の本文・タグ・別名に変更なし。新規・変更ファイルを対象とした資格情報パターン検査で該当なし。
- 独立したPython仮想環境とアプリの分離コピーで、Python compileall、ruff 0.8.6、JavaScript 25件の構文検査、スライド関連10試験が成功。スライドカタログと6定義ファイルのSHA-256、版 `2.1.0` を照合した。バージョン書式・README一致の検査は成功し、Coming Soonの残存なしによる案内のみ。
- 実利用者DB・実Vault・モデル推論・GUI動作・全回帰試験は実行していない。今回は現行内容の保存とブランチ整理を対象とする。
- main・開発資料の反映とGitHubブランチ削除は、push前の参照再照合後に実施する。公開版のファイル・タグ・Releaseは更新しない。

### 同日：統合・削除の完了確認

- ローカル正本を `main` の `8df5fb4994c78187e892efa4301f8d2ec2b45692` として保存し、GitHubへ通常pushした。アプリ本体は退避時の全ファイルSHA-256と一致し、差分は既存の保護規則を継承した `.gitignore` のみ。作業場所は同じ利用者checkoutで、ブランチはmain、未コミット変更なし。
- 試験・設計記録の最新版は開発資料ブランチの `9cfe8fbd7399d378ff6dda0932cf124c7673d833` としてGitHubへ保存した。
- 整理前のSHAと復旧bundle内の参照を照合し、GitHub上の開発用45ブランチをatomic pushで削除した。残存リモートブランチはmain・archive/development-assets-20261016・public/developの3本。public/releaseは元からリモートには存在せず、ローカルの保存用参照を維持した。
- ローカルの開発用19ブランチと補助作業ツリー12個を削除した。ローカルにはmain・archive/development-assets-20261016・public/develop・public/releaseの4本、作業ツリーは利用者checkoutの1個を残す。旧ブランチの全内容をコードへ再適用したものではなく、利用者指定で現行ソースを最新版として確定し、旧試作の固有履歴・未保存変更を復旧用bundleとtarへ保持した。
- Orca管理の補助作業ツリーはWindowsのジャンクションを介した配置であり、Orca CLIの削除が登録パス照合で失敗した。Git所属・実体の絶対パス・退避hashを確認してGitで削除し、残った空の実体ディレクトリだけを削除した。Orcaの一覧でもmainのみになったことを確認した。
- GitHub Actionsの `checks` は成功（run 43024287303）。`version` は意図どおりスキップされ、タグ・Release・公開版の内容には変更なし。全履歴の復旧bundleは独立した完全履歴として検証済みで、補助作業ツリーのファイルは削除直前にも再照合した。

## 2026-11-11：開発済み機能を現行mainへ統合

利用者の「開発済みでmainにないものと未開発を分け、開発済みのものをmainへ統合」に対応した。mainの正本 `8df5fb4994c78187e892efa4301f8d2ec2b45692` に対して、復旧bundleに保持した `8118022a8e4453795b92ea054c62310d04df8e9d` と `ceae4e56912c325dcb16a4f82318f655cea48249` の実装を選択して移植した。旧ブランチの全体マージは行わず、現行の再分析・必須手法・保存形式v2を保持した。統合先は `main` の `3abd719697c137755c5f3f7b9f373b43f0a8bf02`、変更対象90ファイルである。

### 統合した実装と利用境界

- AI応答の終端状態を検証し、不完全な応答の採用を停止する。未計測トークンを0で補わず、同一usage IDの同じ通知は冪等、異なる通知は競合として拒否する。既存分析と全文分析の両方に適用した。
- 保存済み初期分析のbuilder・段階版を検証する。版を確認できない旧結果と保存地点は保持し、再開・自動再計算を許可しない。初期版の同一性には新旧エンジンの境界を設けた。
- 全文分割・観察・主張・根拠検証・批判・研究質問の終了判断を行う `core-pipeline-1` を別の選択肢として接続した。画面の「全文を段階的に分析」、API `/analysis/core-pipeline`、独立した履歴で利用する。通常の自律分析と履歴・ブラウザー状態を混同しない。新エンジンの履歴は専用の読取APIへ接続し、未接続のスライド操作は表示しない。
- 専門家の固定知識・入出力契約、保存済み表・質的結果を接続する計画、研究者の原文確認記録、複数会話の単位表と参加者対応を統合した。原票・固定artifact・親参照・入力版・権限・採用記録を照合し、AI下書きを研究者の採用として扱わない。AnalysisStore v2の外枠とproducerの原結果形式を区別し、実質データは台帳と全体照合する。通知は欠落分を復旧し、実行・保存前の二段階の再検証を維持した。子グループの検証範囲は呼出元から分離した。
- 分析準備パネルのAI向けデータZIPと任意の動画フレームを接続した。氏名・属性・動画は初期OFF。入力版を固定し、取消・対象変更・版変更後の応答はダウンロードしない。本文や動画を外部AIへ自動送信しない。現行の差分保存方式から原本・編集履歴を読み出すように適合した。
- PNG・描画specの検証／同梱、厳密な要求・トークン予算、LM Studioのテンプレートに基づく計測の開発済み部品を統合した。PNGはプログラム用のAPI部品で、専用の作成メニューを新設したものではない。厳密な予算は明示的なbudget factoryを渡す接続部品であり、通常のGUI開始で自動有効化したとは扱わない。通常開始には既存の時間・呼出し・タスク上限を適用する。
- 大小見出しの分割処理・節タグ・章の解釈を保持し、LM Studio配置の既存opt-in `GURUMOJI_LMSTUDIO_AUTO_PLACEMENT=1` を接続した。既定ではモデルの配置を変更しない。現行の通常アウトライン処理は保持した。

実行に必要な専門家・技能・保存契約22ファイルだけをmainに置き、開発試験・fixture・全体設計書をmainへ追加していない。既存SQLカラムの削除・改名・型変更はない。実利用者のruntime、本文・タグ・別名、認証設定を変更していない。選択した90ファイルの資格情報パターン検査で該当なし。ObusSQL質問ライフサイクル書込みのNOT_READY、金額による停止、確認的推論、通常分析の未接続の部分集合・ラベル再計算は未開発／未接続のままとし、完成機能として扱わない。

### 検証と残っている制約

検証は兄弟復旧ディレクトリ内の独立コピー `developed-merge`、専用Python 3.12仮想環境、一時DB・一時Vault・合成データで実施した。実利用者のPython・ポート・runtime・モデルを共有していない。本体コピーとmainの対象ファイルをSHA-256で照合した。Python compileall、ruff 0.8.6、全JavaScript構文検査が成功した。

対象を絞った試験では、既存分析59件・adapter18件・統合7件・保存形式v2の20件・初期復旧18件・既存保存公開24件・再分析11件以上・必須手法7件・履歴39件、全文分割11件・状態24件・パイプライン31件、厳密な予算42件＋12件・実行予算45件、応答整合20件、ZIPの25／29／26／6件、描画24件＋23件、専門家・技能の契約試験が成功した（環境依存の一部skipを含む）。追加のアプリ接続・利用量・初期版・配置の4件、大小見出し8件、Obsidian管理12件も成功した。

保存結果の接続41件・実行9件・単位表8件・質的結果の実scheduler連鎖2件・研究者記録12件・型付き候補14件・HTTP接続16件を確認した。複数会話は準備8件、実Handler/APIの29件を実行し、16会話の固定保存・読戻し、取消、古い版、二重要求、権限失効、実行前後・保存後の改変拒否を確認した。初回の3不一致は、同一内容の再利用で別の原票を要求していた旧fixture2件と、候補の第1ページだけを探していたfixture1件だった。合成のproducer条件を区別し、正確な保存IDをページ送りで探すように直した。該当6件と発言のない参加者を含む一連の集計を個別に再実行し成功した。研究者記録候補の初回2不一致も、冷えたDBの読み取りと新しいpacketのfixtureを適合し再試験成功した。これらのために本体の原票照合・上限を緩和していない。

実ブラウザーでは合成APIと本番テンプレート／スクリプトを使い、Edgeの1440px・390pxで複数会話選択、確認、保存、参加者対応、集約を確認した。最終の履歴接続を含むDOM16件、再分析DOM5件、利用量UI2件が成功した。広いDOM試験219件で判明した環境設定・旧events_after応答fixtureの差は対象55件等を再試験した。Orcaの埋込みブラウザーはhelper所有状態のエラーでsnapshotできなかったため、そのタブは閉じた。実操作の証跡はEdge試験による。

統合前のmainでも再現する不一致を4件残す。Pythonは `test_repeated_core_results_never_finalize_or_publish_and_progress_cannot_be_disabled`（旧期待stoppedに対し現行completion protocolはcompleted）と `test_speaker_identity_uses_unedited_transcript_independently`（旧fixtureのidentity_inputsが空）。DOMはエフォート値・旧thinking mode要素の2件で、統合前ソースを指定した比較でも同じ不一致が出た。無関係な機能を戻して試験を合わせていない。全既存試験を網羅したものではなく、実モデルの出力品質・実GPU配置変更・実利用者DB／Vaultでの試験は未実行である。

GitHubへmainを通常pushし、[checks run 43042588460](https://github.com/krokharu/gurumoji/actions/runs/43042588460) のlint（Python compileall、ruff、全JavaScript構文検査）が成功した。手動起動専用のtests jobはスキップ。version run 43042588397も意図どおりスキップされ、表示版β0.46.1、公開用ブランチ、タグ・Releaseは変更していない。アプリの再起動・実Vaultへの反映は実行していない。

試験の出力、既存mainとの比較、DOM XML、操作画像、対象ファイルとSHA-256はローカル復旧先の `developed-checks`、`browser-evidence`、`integration-files.json`、`integration-main-hashes.json` に保持する。旧履歴の `all-refs.bundle` と13作業ツリーの元の退避も維持する。開発用ブランチや補助worktreeを作り直していない。


## 2026-11-12：統合後mainの追加検証と引渡し判断

利用者の「テスト・検証を行って」に対応し、main `3abd719697c137755c5f3f7b9f373b43f0a8bf02` を固定した別cloneで検証した。開始時と終了時のmainは同じHEADで未コミット変更なし。検証コピーと利用中mainの全追跡ファイルのbytes差は0件だった。Python環境は前回から独立した検証専用venvを再利用し、各試験のDB・Vault・出力先は一時ディレクトリへ隔離した。利用者の本文・タグ・別名・資格情報・実DB・実Vaultは試験に使用していない。検証用cloneはGit worktreeとして登録していない。

### 自動試験・画面試験

- Pythonの227モジュールを選択した初回はJUnit testcase要素2,555件、skip67件、不一致・収集エラー要素61件で、全体は不合格だった。開発資料・ツールがないことによる収集失敗、任意依存不足、別ソースを要求する公開版試験、旧fixtureの差を区別した。初回のsource_changesとruntime_changesはともに空だった。
- mainの既存ファイルを上書きせず、保存用ブランチの開発資材を別の検証コピーへ補充し、不足したjsonschemaとrequirements-devの依存を検証venvへ追加した。実行途中で追加した依存は後続の再試験結果に区別し、環境一覧を保持した。アプリ側の検査を緩和せず、旧AI通信fixture5ファイルに正常終了状態だけを追加した。応答整合性の拒否試験も成功した。ルート一覧は削除0・追加29件を照合してfixtureを更新した（新規Core/ZIP以外の既存追加も含む）。これらの試験資材だけを本記録と同時に保存用ブランチへ記録する。
- 再試験を優先した集計はJUnit等の要素2736件、成功2652件、skip63件、失敗・収集エラー要素21件。公開版4ファイルの収集エラーも要素に含むため、全件を実行済みとは数えない。残る内訳は統合前にも再現した11件、torch/soundfile不足4件、公開版の別ソース未指定4件、全体収集の安全性試験1件、実行時カタログ照合1件。サブテストの内部件数はこの要素数と別である。browser markerだけで全件除外されたモジュールも成功へ読み替えていない。
- 複数会話の一括受入モジュールは600秒で打切りになった。原試験を変更せず、一時領域を分けたケース単位のプロセスへ分割し、準備8件・Handler/API29件の合計37件中37件が成功した。16会話の実POST・保存・fresh読戻しは265.375秒、代表の対応表・sum/mean・読戻しは251.031秒だった。これらは並行した合成試験での所要時間で、単独実運用のベンチマークではない。10秒の標本ではアプリのsafe_pathを含むサンプル42.8%、試験のruntime監査を含むサンプル12.0%を観測した。containmentやhash照合を緩和していない。
- 実Edge 157.0.4341.42で1440px・390pxの確認、2件が360.03秒で成功した。複数会話の選択・確認、研究者による参加者対応、mean/sum、保存・fresh読戻し、元会話の許可失効による無効化を本番テンプレートと実APIで確認した。試験ドライバーがHandlerを明示実行し、モデルは合成応答、schedulerは無効の範囲である。Orcaの埋込ブラウザーでも固定runの復元、2件選択の境界、計画確認まで操作し、console errorは0件だった。操作用タブと隔離サーバーは終了した。
- DOMは環境不足2ファイルを再試験し、重複を除いた238件中236件成功・2件不一致。残るeffort設定と旧thinking要素の2件は、統合前 `8df5fb4` でも再現した。Python compileall・ruff 0.8.6・全JavaScript構文検査は成功した。

### 今回確認した問題と未承認範囲

実行時の `00-Catalog.json` は更新が漏れている。登録215資料のhashは12件不一致で、6件は統合前のスライド資料から、6件は今回変更した専門家資料からの差だった。追加した実行時資料16件は未登録である。これは本体のデータ破損とは区別するが、mainの実行定義と索引の整合性を満たしていない。今回の検証ではカタログやmainのコードを修正していない。

起動済みLM Studioの `google/gemma-4-12b-qat`（読み取ったcontext 16,384）へ合成の2発話だけを送信した。単独の構造化JSON・終了状態・トークン利用量の取得は成功した。既定の全文分析は本文抽出48.281秒の後、Core呼出しが120秒でtimeoutとなり、runはstopped/call_timeout、固定成果物の保存はnot_startedだった。停止後の未完了workerがいる間に初回の試験fixtureを破棄したため、試験側でunable to open database fileも記録された。これを実DB破損とは扱わず、診断用の次回fixtureでは終了待ちを追加した。

呼出し単位の追加推論をoffにした診断では抽出とCoreの応答契約を通過したが、モデルがhuman_review_requiredを選択し停止した。これも自動完了・公開・保存の成功とは数えない。モデルの再ロード・GPU配置変更は実行していない。クラウド実AI、実音声の認識品質、実利用者DB/Vaultの移行、研究上の結論の品質承認は未実行である。

主要な合成契約・互換性・保存・ブラウザー経路には合格が増えた一方、カタログの整合性と既定条件の実モデル完了は未解決である。この記録を引渡し承認には使用しない。mainや公開版の変更・ロールバック・新規Releaseは実施していない。

### 証跡

ローカルの `../gurumoji-validation-20261112/output/validation/20261112/` に `verification-summary.json`、初回Python XML/log、DOM XML、`pool-split/results.json`、`browser/` の幅別receipt/画像、カタログ比較、実モデル結果、環境一覧を保存した。再試験の証跡は `../gurumoji-validation-complete-20261112/output/validation/20261112/`、統合前との比較は `../gurumoji-validation-baseline-20261112/output/validation/20261112/` に保存した。これらのcloneでは検証用資材が未追跡で存在する。利用中mainの作業ツリーはクリーンのままである。

## 2026-11-12：修正計画の並列実装と再検証

利用者の「修正案を作成しタスク化・並列で修正」に対応した。開始時はmain `3abd719697c137755c5f3f7b9f373b43f0a8bf02`、未コミット変更なし。3担当と統合担当に分け、独立cloneと専用Python、一時DB・一時Vaultで作業した。mainには本体・実行設定・開発入口・CI入口の16ファイルだけを反映し、試験と開発ツールは保存用ブランチに分離する。

### 修正計画と実装

- 資料索引担当：runtimeのMarkdown 231件を列挙し、未登録16件とhash不一致12件をカタログへ反映した。frontmatter・文字数・一意ID・技能定義参照も照合した。Markdown本文・ID・版・保存ポリシーの変更は0件。古い215固定の試験を実資料集合に基づく完全性試験へ更新し、欠落・重複・hash・metadata・文字数の改変を検出する負例も確認した。
- 全文分析担当：新規実行のローカル追加推論OFF・出力上限4096を明示して保存し、実際のLM Studio呼出しへ転送する。画面でモデル既定への切替と128〜16384の上限指定、保存済み条件の確認ができる。120秒の呼出し上限、不完全応答の拒否、人確認停止、原文検証・批判・固定保存の安全条件は維持した。旧runの生成条件を上書きせず、更新前の応答不明POSTを同一request_idで再照合できる互換処理も追加した。終了理由の共通プロンプト説明は旧runの再開時にも適用される。旧指示のbytes完全固定は今回の対象ではない。
- 回帰担当：AI応答から復元する型付き根拠IDのnullを拒否し、送信時の未対応発話や一般metadataのnullableは維持した。進捗のstage_labelを既存の診断公開ポリシーへ統一し、公開側ではWindows・UNC・POSIXパスを秘匿、明示したローカル表示は保持した。旧outline/Core応答、speaker identity引数、現行8タブ・作者・版、正当な終了と無進捗停止、無効操作・Obsidian無効時のDOM fixtureを現行契約へ合わせた。停止・原票照合等の本体検査を緩和していない。
- 統合担当：Windowsのpipが日本語をcp932で復号して失敗する問題を再現し、mainのrequirements 6ファイルにUTF-8宣言を追加した。実pipの復号器と宣言除去の負例を検証した。実ブラウザーを明示opt-in・共通sandboxランチャーへ統一し、通常試験で自動起動しないことを検査した。公開版専用4試験は明示ソースを要求し、main packageと別名で読み込む。保存資料のコピー試験2件も別rootを明示する。未指定・全skip・marker除外を成功へ読み替えず、収集失敗・timeoutと区別して記録する。baselineの解消は実行したcase IDだけで判定する。

保存用のprepare_main_validationは、local mainの追跡中の現行bytes・削除・明示した新規ファイルを保持し、固定したarchive commitから不足資材だけを補う。archiveのsrcを重ねず、runtime・output・.env・tokensを持ち込まない。既存target、sourceとの重複、symlink/junction、未解決index等を拒否する。検証に必要なretrieve_memory.pyはexact pathだけ補完する。mainの開発入口と手動CIをこの準備方式へ更新した。DOM用undiciのlockを8.12.4へ更新し、npm auditは0件だった。

### 検証結果

最終集計はローカルの `../gurumoji-fix-integration-20261112/output/validation/repair-20261112/repair-summary.json` を正本とする。全体走行中に更新した保存用試験2ファイルと、配布用構成7試験は再試験を優先し、同一ケースを重複加算しない。全体の元ログと再試験は別に保持する。実行対象外の公開版・実ブラウザー・実モデル等は別記録とする。

最終の重複なし集計は2,805件、成功2,741件、skip64件、失敗0件。収集失敗・timeout・runtime変更は0件。公開版4モジュールのnot_runは実行済みケースへ加算していない。DOM 241件中241件、実Edgeの2件中2件（423.89秒、1440px/390px）、配布用構成7件と880 subtestsが成功した。分割した複数会話の通常37ケースも全件成功し、16会話の実POST・Handler・固定保存・fresh読戻しは311.05秒だった。別rootの保存資料コピー試験は9件成功。検証を手順から作り直したcloneは全2,089ファイルのSHA一致、srcへのarchive混入0件、71件中成功68件・skip3件で、source/runtime変更と依存関係の破損は0件だった。

元の全体走行は2,802件、skip69件、保存資料コピー2件の失敗を記録した。初期の手動補完で.agentsだけを持ち込み、.claudeを補わなかった試験準備の差が原因だった。保存資料を明示した別rootで照合する方式へ修正してから、対象の全9試験を再実行した。全体走行中に更新したtest_agent_assets_sync.pyとtest_test_runner.pyの2ファイルはsource_changesにも記録されたため、元コマンドの終了値は1であり、これを0へ書き換えていない。main本体の変更は全体走行中0件。修正した2ファイルはsource_changes/runtime_changesが空の最終再試験で合格し、配布構成7試験も専用Pythonで再実行した。最終集計はこれらの新しい証跡を優先し、元ログを残したままcaseの二重計上を避けている。

起動済みLM Studioのgoogle/gemma-4-12b-qatは再ロードせず、合成2発話で実登録APIから抽出、Core反復5回、原文検証2件・批判2件、completed/question_satisfied/reviewed、AnalysisStore v2への固定保存・検証読戻しまで成功した。分析のAI呼出し10回、input 8,820 / output 2,689 / total 11,509 tokens。別のtransport確認1回も成功した。各呼出しは約2.3〜16.3秒で、時間上限を増やしていない。最終主張に批判が残っており、研究上の内容品質・研究者承認を保証する結果ではない。

実利用者の本文・タグ・別名・実DB・実Vault・資格情報、公開版branch・タグ・Releaseは変更しない。実音声の認識品質、クラウド実AI、GPU再配置、実MAF連携は未検証。統合試験環境のobusql-agentは統計codecだけをno-depsで導入し、4つの任意MAF依存不足をenvironment-check.txtへ記録した。別に作り直した通常環境のpip checkは成功した。

mainは`8da841f99eaad70a65e29f9b5e4ff91c8cec80e5`、保存用試験資材は`568987fe10e50bcab2d1b8db1b16a632cfb57450`としてatomic pushした。GitHub [checks run 43059488015](https://github.com/krokharu/gurumoji/actions/runs/43059488015)のlint（Python compileall、ruff、全JavaScript構文）が成功した。手動専用tests jobは今回GitHub上では未実行で、Linux上の全体試験を通過したという意味ではない。version run 43059488265は意図どおりskipし、表示版β0.46.1・タグ・Releaseを変更していない。ローカルには従来の4branchとmain worktree 1個だけを維持し、独立cloneは検証証跡として残す。

Python XML/log、split収集メタ、defaultのnot_run理由、ブラウザー幅別receipt・画像、カタログ負例、main対象SHA、prepareの2,089ファイル照合、専用Pythonの環境一覧、集計と元走行のsource/runtime差分を上記repair-20261112へ保持する。実モデル証跡は `../gurumoji-fix-pipeline-20261112/output/validation/pipeline-fix/`、再現用cloneの71試験は `../gurumoji-fix-reproduction-20261112/output/validation/reproduction-smoke/` に保持する。アプリの再起動と実Vaultへの反映は実行していない。

## 2026-11-12：通常アプリによる実音声・実モデル・実画面の試験

利用者の「実テストを実行」に対応し、main `8da841f99eaad70a65e29f9b5e4ff91c8cec80e5` と保存資料 `c4ada24a2dc2631a1afb0cd2d42d83d00601402b` を固定した `../gurumoji-live-validation-20261112` を準備した。mainの追跡929ファイルは試験前後とも正本とbytes差0件。本体の修正・表示版変更はしていない。

### 音声認識

Windowsの日本語Haruka音声で13.6369375秒の試験WAVを生成した。参照文は「今日は朝に公園を散歩しました。歩くと気分が良くなります。雨の日には散歩を休みます。明日は晴れたら、もう一度歩きたいです。」。文字誤り率はNFKC後に句読点・空白を除いた55文字に対するLevenshtein距離で計算した。

- OpenAI Whisper tiny / CPU：認識0.984秒、13文字の誤り、CER 23.636％。「散歩→参考」等の誤認識があった。
- faster-whisper large-v3 / CPU int8：既存モデルの独立コピー、CTranslate2 4.8.1・NumPy 2.2.6・PyAV 18.0.0で12.453秒、CER 0％。この13.6秒の生成音声だけの結果であり、自然会話・長時間音声・話者分離の一般品質は未評価。
- 追加環境で無制約に入ったPyAV 19.0.2は、faster-whisper 1.2.1のmetadata_errors引数を受け付けず失敗した。ソースにある既存Windows制約の18.0.0へ合わせて認識成功を確認した。最初のlarge認識はCTranslate2 4.9.0・NumPy 2.5.4で13.172秒/CER0％、既存制約に合わせた再試験でもテキスト・時間区間は同じだった。アプリ取込みには最初に得たlargeの実認識結果を使い、元の結果も残した。

音声認識は専用Pythonで実モジュールを推論し、アプリの通常write_outputs/import_existing_outputsで取り込んだ。話者分離付きアップロードジョブ全体、Hugging Face認証、クラウド音声サービスは実行していない。利用者の音声・実DB・実Vault・認証設定は使っていない。

### 通常アプリ経路の結果：自動完了・固定保存は未達

本番のapp.appを127.0.0.1の専用ポートで起動し、実Edge 157で「分析→分析を実行→全文を段階的に分析→自律分析を開始」を操作した。通常の初期分析builder、専門家取得、scheduler、Obsidian管理ON、4 Vault出力の明示指定を通し、AI・DB・保存サービスをMockへ置換していない。起動時のLM Studioはロード中モデル0件だったため、google/gemma-4-12b-qatを試験専用ID・context16,384・GPU全offload・parallel1で一時ロードした。新しいモデルをdownloadせず、ASRのcheckpointも既存cacheから専用環境へコピーした。

- tiny認識のrun：5巡・AI9回、input11,866/output2,371/total14,237 tokens。Coreが開いた問いを残してaction:noneを繰り返し、Handlerのno_progress判定でstopped/human_review_required。固定保存はnot_started、完了後4 Vault出力はskipped。
- large認識のrun：7巡・AI12回、input11,691/output2,702/total14,393 tokens。原文検証2件・批判2件はsucceededとなったが、主張の根拠と因果関係を問う4つの未解決問いについてCoreが次の操作・終了提案を選べず、no_progressから人確認停止した。review_statusはnot_requested、固定保存はnot_started、完了後4 Vault出力はskipped。自動完了試験は不合格として扱う。

Handlerの安全停止は作動している。短い入力の不確実性と未解決問いを整理して終了提案へ進むCoreの判断を調査対象として残す。停止判定を無効化したり、reviewed/completedへ試験側で書き換えたりしていない。前回の限定的な実モデル接続・保存確認を、今回の通常アプリ全体の完了保証へ転用しない。

### 停止後の実画面・履歴

停止したlarge runの全履歴JSONとMarkdownは実HTTPで200を返し、ダウンロードできた。390pxの実画面で「人の確認待ち」を表示し、reload後も同じrunを復元した。ページJavaScriptエラー0件、HTTP500以上0件。閲覧・export・reload前後でAI利用量とgenerationは不変、管理VaultのMarkdown16ファイルのhash変更は0件だった。部分台帳の出力は固定成果物の正常保存とは別に記録する。

最初のUIドライバーは閉じた設定dialog内のボタンを直接押そうとして120秒timeoutとなった。設定を開く通常の操作へ直して再実行し、その後の開始POSTは2試行とも202だった。この準備失敗と、実モデルが人確認停止した2 runを分けて保持する。

試験サーバー2個とブラウザーは終了し、試験専用LM Studioモデルだけをunloadしてロード中0件へ戻した。専用環境2個のpip checkは成功。mainはクリーンのままで、重要結果は本保存資料ノートだけへ追記する。

証跡は `../gurumoji-live-validation-20261112/output/validation/live/live-summary.json`、`audio-result.json`、`audio-large-before-constraints.json`、`audio-large-result.json`、`browser-result.json`、`large/browser-result.json`、`large/stopped-check.json`、画面PNG、実ダウンロードしたJSON/Markdown、各環境一覧、専用DB/Vaultへ保存した。元のUI timeoutとPyAV19の失敗ログも保持する。
