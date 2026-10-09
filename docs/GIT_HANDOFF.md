# Dot / Orca の Git 受け渡し

共通リポジトリは https://github.com/krokharu/gurumoji、共有ブランチは `krokharu/dot-orca-git-share`。このブランチは公開済み `main` を基点に選別した候補で、元のローカル作業ブランチの履歴は含まない。コード・合成テスト・必要な設計契約を固定し、[ファイルmanifest](git-handoff-manifest.json)でSHA-256を確認する。長い私有プラン・研究データ・実DB・資格情報・未選別の作業packetは追加しない。

## 更新と受領

1. C0/Orcaは共有ブランチへ対象ファイルを明示してcommitし、通常のpushを行う。Issue #15または対応するPRに、完全なcommit SHA、変更ファイル、確認コマンドと結果、失敗／未実行、残件を短く記載する。元の私有ブランチ全体をpushしない。
2. Dotは通知されたSHAをGitから取得して確認する。自分の既存作業を確認し、変更があるcheckoutでは自動pull／merge／resetしない。必要なら専用のcheckoutを作る。受領はIssue #16またはPRへ `receiver / commit / checked / failed / not_run / next` を返信する。送信やfetchだけでは受領済みにしない。
3. C0/Orcaは同じIssue／PRからDotの受領とレビューを読む。実装ownerはIssue #17、共有ownerは#15、レビューownerは#16。開始前に固定SHAと編集対象を記録し、同じファイルへ重複実装しない。
4. 次回も同じ共有ブランチとPRを更新し、結果は新しい固定SHAへ対応付ける。共有成功と工程合格を分ける。mainへのmerge、force push、履歴書換え、実データ移行はこの受け渡しに含めない。

新しい環境での取得例（Git以外の実行権限やモデル許可は増えない）:

```text
git clone --single-branch --branch krokharu/dot-orca-git-share https://github.com/krokharu/gurumoji.git gurumoji-shared
cd gurumoji-shared
python scripts/check_git_handoff.py --expected-commit <通知された完全SHA>
```

既存の共有checkoutでは `python scripts/check_git_handoff.py --fetch --expected-commit <通知された完全SHA>` を使う。fetchはrefの更新だけで、checkoutを自動更新しない。`received=false` ならcommit・dirty・mismatchesを確認し、成果を退避せずに強制上書きしない。Gitの読取だけ可能なDotはcommitの取得とファイルmanifest照合を報告し、Python未実行を明記する。GitHub Issue/PRが双方の永続的な通知・受領経路であり、ChatGPTの会話は短い通知に使う。バックグラウンドの自動受信や監視は設定していない。

## 2026-10-10: export??????????reader?????

UI?? `ecb9aafadcf90c938bff627afc4383f28d304fda` ?2path?app.js???DOM test?????????????????focus???????????????focus???tablist?????????????????DOM??7???15?22 PASS / FAIL0 / SKIP0????C0??? `ca2614cbd3b45be7d7b5c50c3a6f13b67e97f65d` ???2blob??Edge1440/390?????????32?????8?????????????6???PASS?ERROR/SKIP0?????32????????????1skip????????????receipt SHA256? `14788313c11d0a8cbf5db9d739e43a3f2d0a5e9864e358e550e967967511b893`?native history Back/Forward???????????OS??????shortcut accelerator??AT/screenreader??????DB/Vault???????????AI????0???Dispatch `ctx_882f3ec3393b` ???done????release???

?????????Git object???????????reader?code bytes??? `tests/fixtures/expert_reader_history/6f1d532c5a0ce995b03e3dca191f358eeed6d42f/expert_agents.py` ???????blob `8c86a20ed9cb54e977376afc9f6a90c0176649cd`?45572 bytes?SHA256 `7cccfdd6188cd6b25641c673516c9012d83a7bd90c43b1c5bb0f86e49a74bff8`????????????????????????test?fixture???transcript-preparation pin???Dot???scope?????????????

[#31](https://github.com/krokharu/gurumoji/issues/31) ?FGI backend?Dot????Windows??QA????????C0???15????PASS??????????????????????PNG Store/Web/Vault???Gemma full323 HOLD?G0.5b/c????currentPack???G5????????????????????manifest?engineering_hold???????

## 2026-10-10: AI向け生データZIPの選別受入

[#29](https://github.com/krokharu/gurumoji/issues/29)／[Draft PR30](https://github.com/krokharu/gurumoji/pull/30)のbackendはDot主担当。公開4e3で旧API作者をfreezeし、Dotの5path候補85b8と修正版 `d87be47feac6c04584a3fd7d8d50047cd263d358` を既存実装へ選別した。Dotは`ai_data_export_bundle.py`／`ai_data_export.py`／`ai_data_export_frames.py`とbundle／API testを所有し、OrcaはUI／独立Windows QA、C0はroute／app登録／共有index／統合を所有する。同じpathの重複実装・main mergeは行わない。

受入sourceは `69e95ebac32957ae9a739d7764afcc7f95b5c23f`、独立testは `f0a552c3c349542ea33e9c0b38ec48ff3d2c3956`。UI作者54aの3path、Dot最終5path、独立test1path、C0のroute／app・route fixture・request guard testを合成し、後続の資料／byte pin／manifest変更でproduction7blobを変えない。manifestは既存114と明示追加12pathの計126を固定し、private docs・raw破損履歴・延期visual・Downloads別WIP系列を混ぜない。

- 既存保存preparation exportをreadonly snapshotで再利用し、原文／現行／全入力版／lineage・時刻nullと0・保存outline／欠落・元snapshotと出力file hashの別domainを保持する。氏名OFF・属性未選択が既定、全入力履歴にも同じ選択を適用する。氏名除外は本文や動画の匿名化を保証しない。
- 動画frameは明示opt-in、item許可mediaだけ。24枚／600秒／間隔1秒以上／長辺1280px／各2MiB／計32MiB／subprocess合計30秒を制限し、部分失敗・timeoutをZIP成功にしない。実PTSと要求時刻を分け、stat identityをcontent hashと呼ばない。ZIP展開64MiB／text32MiB、schema／hash／参照・unsafe path／bombを検証する。
- C0は旧合成64dcでbundle／API／route隣接60methodを実行し、59PASS／FAIL0／Windows symlink権限1SKIP（2.299秒）。pure validatorの大時刻grid不備を別途再現し、Dot最終修正を取り込んだ69e95ebではbundle25methodがPASS／FAIL0／SKIP0（0.067秒）。同じ試験を合算して種類数を水増ししない。
- 別作者のWindows独立受入は旧64dcの累積25PASS（初回23＋保存済み空文字の期待値補正2）、大時刻grid6subcase FAILを保存した上で、新69e95ebの差分6methodがPASS／FAIL0／SKIP0（8.382秒）。重複／逆順／正の1秒未満をpayloadとhash再計算後ZIPの双方で拒否し、正常decimal `(1.3,2.3)` を保持した。通常Edge1440／390は新版で文字ZIP＋氏名／組織／実3frame ZIPの計4実download→HTTP200→hash／参照／PIL decode・readonly・pageerror0・横overflow0まで確認、未解決製品所見0。実Windows Junction escapeは拒否、権限不足の実symlinkは未実行として分ける。
- 実行環境はWindows11／Python3.12.9／Edge154.0.4258.53／Playwright1.63.0／FFmpeg7.1.1／Pillow12.2.0、install／設定変更0。独立receipt SHA256は `04c930c03a77d2fb4ed4673bd2f96a36370ae3697b2971e774b36670fb7e26f7`、Run `run_30240e5eb510`／Task `task_13d75c4de7c3`／Dispatch `ctx_70df24e7118c`。正規doneを照合してworkerをreleaseした。

Dotの[修正版作者報告](https://github.com/krokharu/gurumoji/issues/29#issuecomment-6083739323)はpure25／combined54PASS（0FAIL／ERROR／SKIP、2.341秒）と別review22caseを述べる。これはDot報告として区別し、Orca自身のLinux実行やWindows独立受入へ置換しない。実command／版／exit／cleanの補足確認はLuna窓口が追跡する。再現入口は`PYTHONPATH=src:tests python -B -m unittest test_ai_data_export_bundle test_ai_data_export_api -v`（WindowsではPYTHONPATH区切りを`;`にする）と独立testの対象method。独立全26methodを最終版で一括再実行したとは主張しない。

実利用者DB／研究Vault／実媒体の変更・外部AI自動送信・モデル推論は0。Linux独立試験／全app suite／AT／実研究者の理解と採否は未実行。PNG Store／Web／Vault延期、Gemma full323 HOLD、G0.5b/c未測定・currentPack暫定・G5未評価を維持し、manifestの`engineering_hold`は解除しない。共有SHAの取得とmanifest一致は、この限定機能以外の工程合格を意味しない。

## 2026-10-09: 実複数source接続の選別受入

23:35 JSTのLinux追補：[Dotの固定429 receipt](https://github.com/krokharu/gurumoji/issues/28#issuecomment-6082993355)で、指定2blobと下記の純kernelコマンド、Git2.52.0／Python3.12.14、4 PASS／0 SKIP／0 FAIL（0.769秒）、隔離checkout clean・編集／install 0を確認した。C0は公開本文をreadbackした。以下の旧環境不可／未実行は当時の履歴であり、この限定4件は現在実行済み。legacy Flask suite／full app／モデルや別機能の受入を意味しない。

共有sourceは `3bb09c2ce0b80ee7b6f52d1a39d7f3dfcc662533`。公開bc0基点からbackend `4f4a2903c9ac0e995426b22843d68b8c5b8a6f66` の6path、UI `211587f9400bc87c5204ce51d70716c2e972c1b9` の3path、別作者の独立test `80f148babc424e63c128db53d74ffab886dfa822` の1pathだけを選別した。共有indexはC0のみが所有し、全10pathのGit／index／作業bytesを照合、AST7・diff・統合後の隣接kernel4件が成功した。以下の以前の区切りは履歴であり、現在の接続範囲は本節を使う。

- 既存options GETの`unit_pool`と既存asset-plansの`unit-pool-request-1` explicit POSTを接続した。GETはreadonlyでscopeを生成せず、POSTが2〜16の完全utterance carrierからStoreの閉じたgroup scopeを作る。`pool-source-option-1`は表示用metadataで、互換性・原入力・現在policyのauthorityにはしない。主会話を含む許可済み2会話がない場合は選択を無効にする。
- 実group HumanRecordの明示participant mappingを採択して既存unit_aggregateへ渡す。単一会話HCを多会話へ転用せず、定義の同名だけで互換にしない。snapshot content_hashとinput_hash、元発話／qualified ID対応、元分母／現在除外、全sourceと親policyをprepare・実行・save・freshで照合する。missing／unknown／unprocessed／excludedと観測0を区別し、無発話名簿を観測0にしない。
- 保存はunit_poolだけ`connected-provenance-3`を使う。完全unit_contractと値を含む全receiptを保ち、重複parentsだけを同packageの`receipt.bindings`への閉じたtarget／hash／domain参照にする。freshでは実durable task／raw ledgerとの全体一致と現在の元bytes・権限を再検証する。旧`connected-assets-2`と他methodは保持し、131072／65536上限、SQL、保存先、schedulerは増減しない。
- 別作者の最終4f4境界8件（415.614s）、有効な16source47発話の実SAVE上限拒否1件（74.628s）、receipt実値改変拒否1件、4f4＋211のEdge1440通常操作1件（118.425s）が成功、open製品指摘0。縮小していない16source・5変数・21発話は実GET→POST→Handler→immutable save→fresh成功、全receiptを保った122014 bytesで上限内。実保存2会話`[0,2]`と`[4]`の同参加者HCからsum6／mean2／observed分母3を確認した。390px正常操作とprimaryなし無効化は723＋f042で成功し、UI2 blobは最終211と同じ。初期options／重送／保存サイズの失敗とfixture修正履歴を保持し、最終版の成功で過去を消さない。
- 旧mock5回帰は実ExpertCatalog／Registry選択へ接続し、C0のexact5＋欠落ID拒否／一般互換2が成功。別の2pathで既存UnitKernelTestsを純粋supportへ分離し、fixture・4本体のASTと旧export／discovery4 uniqueを保持した。C0のFlask遮断4と旧入口4は同じ4件の入口別検証であり、8種類の意味品質試験とは数えない。Linux用は`PYTHONPATH=src:tests python -m unittest support_analysis_unit_kernel.UnitKernelTests -v`。Dot [#28](https://github.com/krokharu/gurumoji/issues/28#issuecomment-6074192102)は環境利用不可で未実行、[所有者移管](https://github.com/krokharu/gurumoji/issues/28#issuecomment-6074232023)後にWindowsで完成させた。#27の旧bc0 Linux109照合／helper14成功とは別の受入である。

作者端末のcapacityエラーで完了報告が止まった試行はfailedとして保持し、同じ既定modelの正式retryで固定4f4のreadonly照合・回復receiptだけを完成した。旧試行の未確認overgate結果は不明のまま、上記の合否は別作者の実ログを根拠にする。Run `run_30240e5eb510`、独立Task `task_7f86196b7e4b`／Dispatch `ctx_168b62300154` が技術受入の根拠。

実DB・研究者Vault・認証・実モデル・Downloads原本への書込0。UIは合成loopback appのproduction画面と実scoped API／Handlerを操作し、full scheduler、全初期pipeline、利用者稼働サービス、AT、全suiteは未実行。今回のNode検証は既存24.21.0を使用し通常PATH22.19は変更しない。PNG Store／Web／Vault延期、Gemma323 fullMready=false／HOLD、G0.5b/c未実測・currentPack暫定・G5残14未展開と意味品質未認定を維持する。私有checkpoint／延期visual／raw破損snapshot／実データ・認証・私有Drive資料は共有へ入れず、Downloads別公開branchも自動mergeしない。manifestの`engineering_hold`を維持し、通常forward pushと固定SHA受領を工程全体の合格にしない。

## 2026-10-09 06:58以前の共有固定候補（履歴）

当時の共有sourceは `1949833c1c20e898fe935cbad5df382d2c18fb23`。元の私有作業ブランチをpushせず、公開共通基点から次のcode/testを選別した。当時のmanifestはこの固定sourceのGit bytesと公開受け渡し資料を対象にした。進行中だった未コミット画面実装は含めない。

- 実際に保存された研究者記録を持つTA候補から発話単位・明示対応による参加者単位へ変換し、count/sum/mean、完全な一対一join、探索的相関を既存Handler／Storeで保存してfresh再利用する。無発話の名簿を観測ゼロにしない。現在の実接続は単一会話。複数会話はkernelだけでなく、全保存元／原票／現在の権限を照合する実Store橋を必須後続に残す。
- 同Handlerの資産依存計画を接続し、選択したfrom_stepの実保存receiptを待つ。重送／順序違い／欠落通知／再開は実台帳から照合する。旧世代resumeの計算・保存を0で拒否し、正常completed後の新run再利用を保持する。独立最終関連11件、独立unittest12件、standalone4probesが成功。初期のP1/P2失敗は履歴として保持し、修正版だけで閉鎖した。通信先の不確定な実LLM結果にexactly-onceを主張しない。
- 質的対照のsupport/counter/complement/conflict/incomparableと明示理由、元発話／少数・撤回・除外・時刻欠測のパケットを保存し、B1／Q1／原文から新A2へ再利用する。AI提案は未確認のまま、独立検証とはしない。graph／bundleの実HumanRecordは別に保存され、先に採択したHC revisionを利用したA2の訂正で子孫だけstale、独立枝と旧bytesを保つことを確認した。
- 通常TA判断フォームとreadonly選択GETは実Flask→Handler→Store→freshで確認済み。作者のUI最終46 distinct項目、C0の重送／本人訂正2件が成功、Edge1440／390pxでpointerとTab／Enterを確認した。実app cold root200／missing HumanGET404でDB生成0・通信0を確認した。Node/jsdomの宣言engine差はPARTIAL、AT／利用者理解は未実行。
- Dot #23の固定 `b4436c6f69186dd69c47960522e187d845f080c3` の2fileをbytes／hash／blobで照合して統合した。Windowsのpackage23件、日本語2slotの並列fresh検証／metadata・PNG改変拒否が成功。helperは既存の閉じた14-field specと固定bindingを照合する。科学的なspec承認と保存PNGhashの信頼はStoreの責務であり、helperだけで保証しない。

利用者の最新指示でPNG Store／Web／Vaultの接続は延期した。描画・検証基盤と候補は保持し、未接続を成功stubにしない。図表以外の通常S3–S5選択API／graph・bundle研究者判断画面と、実複数会話の接続を継続する。この固定候補にはそれらの進行中機能の成功を含めない。

C0が管理・割当・受入を担当し、Orca側LunaはDot応答と作業有無だけを読取確認する。作業者は必要時のみ上限6（C0別枠）、同じファイルの編集ownerは1名、共有indexは直列化する。機能候補・レビュー・引継ぎの安全な区切りで新チャットへ移り、編集中／実行中の処理は中断しない。Dotはクラウド実装、C0はWindows確認とGit選別統合を担当する。GitHub Issueが永続的な通知・受領経路であり、Lunaの稼働セッション監視と永続常駐の自動更新設定を混同しない。

実モデル品質・全323発話・研究者採否・実Vault・AT・非図表の残る接続は未完了。図表延期と残件を明示し、全要求や研究品質の合格にはしない。通常共有はdraftで、main merge・強制push・私有履歴／実DB／研究本文／資格情報の公開は行わない。


## 2026-10-09: S6 非図表と通常画面の選別受入

原S6 `178bc53b136394784fd89f982c1f8dd403519ee2`（基点 `2805d9987fe9831058e66385a56c3f2cdef049a9`、明示6ファイル、patch SHA-256 `afafcb2f91e88c1f2d8faf7751c88f52a6aecef9a22a316965930b606dd9084e`）の独立判定は、変更された非図表Web・単一会話native mapping境界で8件と隣接2件成功、open製品指摘0。固定6ファイルを3wayで共有 `213ee596a60a48b18677b5262a233929ef3cc42a` へ統合し、Git bytes/hash、AST6、差分、最小smokeを確認した。作者suiteは再反復していない。

その版の通常UI最終候補を `1949833c1c20e898fe935cbad5df382d2c18fb23` へ選別した。通常8ファイル全体と `analysis-history.css` のfocus hunkだけの9パスで、PNG専用 `analysis-storage.js` / `analysis-visualizations.js` / `test_analysis_visual_ui.cjs` と図表CSS6ルールの作業bytesは保全・非commit。最終stage9のbytes/hashは作者receiptと一致。実Flask→Handler→合成SQLite/Store→fresh経路5件、実Edgeの1テスト内1440/390px操作2シナリオ、変更隣接3件、通常入口1件が成功した。射影→参加者対応HC→平均→保存/fresh、graph/bundleのHC投稿/重複/再読込、取消・権限取消拒否、根拠から戻る際の選択/scroll/focusを確認した。選択欄のラベル不備は修正版で閉鎖し、初回fixture5失敗・応答期待2失敗・Edgeラベル1失敗を履歴として残す。

原checkoutのhelper2は今回不要で追加せず、原source/index/dirty docsには未接触。実複数会話Handler/Store橋・6e8/options複数source seamは次票の未実装、PNG Store/Web/Vault接続は延期。full app起動・full service.run scheduler・実利用者DB/Vault/モデル/認証/main・AT・全suite反復は未実行。Node22.19とjsdom30.1.1宣言engine差はPARTIALのまま。実データ接触0。公開は受入済み完全SHAの通常forward pushをLunaが担当し、共有index/sourceの返却と次票割当はC0へ。manifestはこの固定sourceのGit bytesを使い、未コミット延期差分を含めない。根拠はOrca Run `run_30240e5eb510` / 受入Dispatch `ctx_015ad29dbb33` の単一receipt。

## 2026-10-09: Dot #25 の初回 Windows 受入（当時の区切り）

Dot #25 / Draft PR #26 の固定 `6534303820148b6b679e35e1ccd9ea7dbd4792a7` から `src/gurumoji/services/analysis_unit_groups.py` と `tests/test_analysis_unit_groups.py` だけを選別し、共有 `deaa6751a566c7c22a8f1e205e26165e28b74bb3` へ統合した。Issue #25 の確認済み契約 [6068361583](https://github.com/krokharu/gurumoji/issues/25#issuecomment-6068361583) と公開候補の bytes / SHA-256 / blob を固定 fetch/readback で照合した。

Windows / Python 3.13.7 の `$env:PYTHONPATH='src;tests'; python -m unittest test_analysis_unit_groups -v` は14件成功。別3会話合成例で count / sum / mean、発話加重平均5.25、projection原分母と現在context、qualified対応、異なる変数定義の拒否が成功。helperは原snapshot evidence対応・現在権限・実HC採択を認定しない。実複数会話Handler保存/fresh橋、実DB/Vault/モデル、PNG接続は未実行で、engineering_holdを維持する。

共有frontend14の凍結bytes・未stage・index内容を保護した。最終S6 backend `178bc53b136394784fd89f982c1f8dd403519ee2`（基点 `2805d9987fe9831058e66385a56c3f2cdef049a9`、明示6file、patch SHA-256 `afafcb2f91e88c1f2d8faf7751c88f52a6aecef9a22a316965930b606dd9084e`）は読取り受領済みで独立レビュー待ち。通常合格後の共有統合ownerはWindows担当、画面→保存→fresh/Edge受入はfrontend担当、通常push/Dot通知はLuna。私有履歴・未コミットfrontendは公開候補に含めない。

## 過去の固定候補と検証（当時の状態）

初期sourceは `b932fe11adf0881a3d7093c2761fbee930be0e56`。2026-10-09の継続では、#17のゼロ件セル欠落を `59e48b09625f1b4a5dffed993d4c8e920530f21e` で修正した。作者47成功、別担当の関連71成功・symlink1skipと独立68合成ケースで、固定入力から完全な型付き直積を確認して保存前に欠落を拒否することを検証済み。旧独立21 PASS / 1 FAIL / 2 PARTIAL、作者FAILED、工数UNKNOWNは過去の証拠として保持する。

通常Web入口は `1ba673f911034a686ba63661867a8922eead8d54`、画面導線は `855a16553729912f0643f44930760a85b584caa0`、独立検証の3指摘を直した候補は `bd04e601286037026afc0d1830b9c939efe782c5`。固定表選択・5方式・scheduler保存を接続し、consumer一致、初回GETの読取専用性、offsetの閉じた検証を修正した。独立再検証は関連159成功・追加20成功・UI38成功。1440/390pxのEdgeでpointer/keyboardを確認し、実Flask→Handler→合成Store→fresh読込を通した。実app全体のimport、実利用者・AT・実モデルは未実行。旧独立9 PASS / 3 FAILは履歴として保持し、合格は修正版だけに対応する。

Git受領validatorはDot PR #20の修正版 `d2dd0899d5dec394f87abf75fc08347cbd0417ef` のコードとテストを選別統合した。Windowsの別名・末尾dot/space・予約名・case重複等を拒否し、独立23ケース成功、同一ファイル別名9ケースを確認。作者テストはWindowsで7成功・symlink権限1skip、Dot Linuxで8成功。旧manifestは上書きせずC0が最新の公開対象から再生成する。PRの競合を解消するためのmain mergeや強制操作はしない。

図表描画はDot #21の最終 `2ccd248171a87c4d85d14c84647ac989960a9f45` の2ファイルを選別統合した。相互辺の数値ラベル重なりとWindowsの日本語フォント選択を修正し、日本語Tableセルまで実描画を確認した。中間9e17の28成功・1失敗を保持し、最終版の限定差分について独立6成功と日本語クロス表1成功、glyph警告0、実画像の確認を記録した。通過済みの8方式と負例は中間版の結果を限定差分で引き継ぎ、最終版で全反復したとは記載しない。Dot作者の最終24成功は作者の結果として分ける。PR #22の先頭は旧371bdのままで、Dotブランチ更新の取消を再試行せず、完全SHAから受領したコードだけをC0が統合した。

型付きテーマ候補と信頼された研究者記録APIは、非公開作業履歴を含めず固定実装の15ファイルを選別統合した。4つの研究者工程を別々に記録し、元メモと要求bytesを不変保存、同一対象の版更新・現在の権限・取消・実タスク来歴を保存時とfresh採用時に照合する。旧実装で保存された偽来歴候補も記録追加0で拒否する。独立最終63成功・追加15成功、表API/UIとの統合版42成功、公開済み履歴fixtureを維持した隣接41成功・symlink1skipを確認した。現在のテーマ結果の接続はevidence_contextまでで、数値分析のdata_input・単位変換・依存実行は次の実装対象。承認済みspec全体と固定保存データの照合・PNG保存／Vault／画面表示も継続中で、全体のENGINEERING HOLDを維持する。

共有76a31feのDot受領はGitHubから4資料を読んだ結果で、90件の全hash照合やPython実行はDot未実行。Orcaの新規checkoutでの90件一致・received=trueと混同しない。Orcaは一時環境で実app import・root HTTP200・存在しない表APIの正しい404とDB生成0を追加確認したが、通常画面の実利用者・実モデル成功を意味しない。

Git書込の自動承認拒否が発生した際は、同じ操作の連続再試行をせず理由を確認する。今回は既に公開済みのmanifestと担当2ファイルの差分・hash・bytesを固定SHAで照合してDotが反映し、GitHubから読み戻しを確認した。各担当は次回も公開済みの内容、今回の差分、担当範囲、秘密情報の混入の有無を確認してから送る。

実モデル品質、全323発話、人の採否、実Vault、自然な容量境界などは未完了。文書内の未公開プランや履歴commitへの参照は出典表示であり、この共有版だけでは取得できない。必要な歴史的負例は技術ノートのfixtureとして同梱し、過去履歴を公開せずテストできる。Gitの固定版受領は、これらの工程合格や研究品質を意味しない。

## 受領コメント例

共有準備時の検証（Windows / Python 3.13、合成データのみ）: `PYTHONPATH=src python -m pytest tests/test_expert_skill_bindings.py tests/test_analysis_asset_bindings.py tests/test_statistical_expert_agents.py -q` は68成功・symlink権限による1skip。`node --test tests/test_analysis_fixed_run_ui.cjs tests/test_analysis_ownership_ui.cjs` は2成功。manifest86ファイルが一致し、CRLFを許容したdiff検査は成功。既存`PureWindowsPath.is_reserved()`の非推奨警告が発生。全体テスト・実画面・実モデルは未実行で、既知の#17不具合をこの成功結果で解消扱いにしない。

```text
receiver: Dot または Orca
commit: <完全SHA>
checked: Git取得、manifest <件数>一致、実施した検証
failed: <既知／今回の失敗>
not_run: <未実行>
next: <担当、Issue、編集対象、開始／待機>
```
