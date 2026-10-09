---
note_id: ops-gurumoji-improvement-session-20261003
note_type: development-session
title: Gurumoji 改善セッション
summary: 専用ブランチの復旧根拠、作業分担、課題、検証、受け渡しを管理する。
status: current
updated: 2026-10-05
---

# Gurumoji 改善セッション

## 目的と範囲

2026-10-03 20:50:25 UTC〜2026-10-04 04:50:25 UTC の改善作業。専用ブランチ `dot/gurumoji-eight-hour-20261003` で、UI/UX・分析・プログラミング・全体調整を分担し、根拠のある改善、独立レビュー、回帰試験を繰り返す。

公開、push、deploy、認証変更、有料推論、実Vaultの移行は対象外。合成fixtureを使い、研究者のデータ・原文・所有権、欠測とゼロ、固定runと現入力の区別を守る。

## 復旧の根拠

- 作業環境の置換により、旧checkout・仮想環境・未公開commitの実体が失われた
- 公開リポジトリの `4b311df51c7fe2938f1761cb1efbb4cc4906fd10` を取得し、保管bundleの前提commitと一致を確認
- 保管bundleから `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0` までの実装を復旧
- 設計資料v0.4の95ファイルをmanifestのサイズ・SHA256と照合し、新commit `2d9bb23` で復旧
- 資料に記録された元commit `d4788938536bef4e13b38af77abeb6b962f504fa` は資料の来歴であり、元の全treeやcommitを復旧したという意味ではない
- 旧後続commit `8d0d277`、`336af40`、`55dbd0f`、`7795485` の完全なソース成果物は確認できない。後続修正は新しい変更として再実装・再検証する。旧テスト件数を今回の成功に流用しない

## 部門の責務

| 部門 | 入力 | 成果物と合格条件 |
|---|---|---|
| UI/UX | 現コード、DESIGN、設計契約、対象画面 | 操作状態・値同期・アクセシビリティ・狭幅の具体的受入条件。静的確認と実画面を区別 |
| 分析 | 合成データ、定義・実行・保存契約 | 定義版、分母、欠測、来歴、保存先の再現可能な検証。未測定を成功としない |
| プログラミング | 優先課題、再現fixture、独立レビュー | 小さな対象変更、明示的な対象fileでcommit、関連試験と回帰試験。ソース変更の単一担当 |
| 全体調整 | 各部門の根拠、変更差分、試験結果 | 優先順位・重複回避・統合判定・次の課題。意味のある節目で復旧可能な成果物を保存 |

## 作業ボード

| ID | 優先 | 課題 | 状態 | 完了の証拠 |
|---|---|---|---|---|
| REC-01 | P0 | 確認可能なソースと設計資料の復旧 | 完了 | base／bundle確認、95 hash一致、2d9bb23 |
| REC-02 | P0 | テスト環境の復旧 | 完了 | project-local venv、CPU torchのみ、pip check成功、依存版記録 |
| COR-01 | P0 | 旧後続修正の再構築範囲を確定 | 完了 | 旧担当の仕様と復旧コードを照合。完全な旧sourceの復元ではない |
| ANA-01 | P0 | 定義版・入力版と実測・出力の一致 | backend受入済 | 9768b80、独立48件・1120定義matrixで違反0 |
| ANA-02 | P0 | 欠測・型・保存scope・世代/復旧 | backend受入済 | 4writer台帳、固定package、Barrier試験、restart3境界 |
| UI-02 | P0 | 対象切替・遅延応答の誤適用を遮断 | 統合済 | c1029e4、request ownership、遅延応答とABAの合成検証 |
| UI-03 | P0 | 測定の試行→確認→採用→実行、簡易/詳細 | 統合済 | c1029e4、7904aa1。4presetを元UI→実Flaskの20要求で独立検証 |
| UI-04 | P1 | 不明時刻・旧根拠の再生guard | 統合済 | c1029e4、無効・非有限・逆転・不明時刻を拒否、実0は維持 |
| UI-01 | P1 | 既存4 effort controlの小型グラフィカルカード | 統合済 | 1875020、候補1934ca2で独立20境界成功。実handlerの方式往復も値を保持 |
| QA-02 | P0 | browser testの安全な起動と明示opt-in | 統合済 | 9b1757d、869b843、5fa689f。安全な既定値と標準収集範囲、子process importの修正 |
| QA-01 | P1 | 最終差分への独立レビューと回帰 | code/DOM受入済 | 721c308で1049 pytest・1052 subtests・161 DOM、失敗0。実browser22/Windows10は未実施skip |
| ANA-03 | P0 | 役割の値と登録・準備・既定来歴を一致 | 統合済 | 7904aa1、候補86f82b5で明示・登録・準備・旧曖昧値を独立検証 |
| UI-05 | P1 | 固定run閲覧・履歴の来歴と4writer状態 | 統合済 | c6e5094、保存要約・表・定義版、読取副作用0、台帳snapshot、長いCSV、全download一致 |
| UI-06 | P1 | 旧役割の来歴不明を説明し同値を明示指定 | 統合済 | e8cb4e8、明示button、旧save応答の別会話・同ID再読込への誤適用も遮断 |
| QA-03 | P1 | 実HTMLと全UI scriptのオフラインDOM統合 | 統合済 | 721c308、同HEADで既定npm test 161件成功。jsdom30.1.1はtest専用。実browser・layout・ATは別途未実施 |
| COR-02 | P0 | 特殊な話者名・未知statusの継承key誤認 | 統合済 | a0c7a60を1a7677fへ統合。literal key、保存往復、prototype不変、未知status表示を独立DOM受入 |
| UI-07 | P1 | 話者表のcontrol名と再描画focus | 統合済 | 3df48e5、表示名変更後も話者ID付きの名前を更新、registry再描画で該当controlへfocusを保持 |
| UI-08 | P1 | 旧route応答が新しい会話表示を取り消す | 統合済 | bbd743c、実popstate配線で応答順2通り・別画面・取消・ABAを独立受入 |
| UI-09 | P1 | 分析Saveの別会話／同ID再読込への誤適用 | 統合済 | bc84d85をed7a3f1へ統合。古い成功・409・500、後続編集、新保存のbusy所有権を独立受入 |
| ANA-04 | P1 | speaker集計の全欠測0秒／不完全な割合・集中警告 | 統合済 | 9c92b6b、実API／固定CSV／旧v4 snapshot不変を独立受入。全欠測graph非描画、真0とpartialを維持 |
| UI-10 | P2 | 同item Saveで固定viewerが検証中のまま停止 | 統合済 | e618d38を9c92b6bへ統合。現編集revisionと独立し、入力比較を「取得時点」と明示 |
| UI-11 | P2 | 役割未設定を含む参加者集計の確定風表示 | 統合済 | 7ae080a、仮集計／不明人数を明記し無限定50%断定を抑制。実API→JS独立10条件、source不変 |
| UI-12 | P2 | 測定定義dialog再openのbusy残存／移動後のmodal残存 | 統合済 | 35378a0、Save/Trial再open・移動の回帰反転、測定定義の実DOM9条件成功 |
| UI-13 | P2 | 分析Save完了後の測定dialogが旧入力版のまま無反応 | 統合済 | c3c1662、定義文言保持・旧trial採用失効・保存済ID保護・自動書込なし、実DOM再保存とdirty対照 |
| ANA-05 | P1 | 同じ話者の発話別role混在による配列順依存 | 統合済 | c6abf58、6並替・除外復帰・全観測分母・旧v5保持を独立受入。15592f1の実DOMで全観測分母とnullable役割量も受入 |
| UI-14 | P2 | 固定run要約で保存計算版とregistry版を区別表示 | 統合済 | 7a6f137、保存記録だけのbounded投影。旧版・欠落・非scalar・省略・有限0を区別、DB/固定package不変、独立APIと実DOM受入 |
| ANA-06 | P1 | 固定packageのmember名・snapshot来歴の不整合 | 統合済 | 998ea4b、危険なmember名と正規化衝突を拒否、入力digest照合、同じ検証済bytesからZIP。破損/復旧境界の独立受入 |
| ANA-07 | P1 | 残る時間系の偽0・library不正時刻500 | 統合済 | a383df1/c1d8cfd、v7で全source終端・感情・コードのnullableとcoverage、真0/空集合、旧v6保持。通常JSON import含め独立受入 |
| UI-15 | P1 | legacy数値文字列と時刻編集後の話者表示不一致 | 統合済 | 97847d1/4c31983。binding付き投影と空JSON markerの既存意味を維持。961組合せと実import/編集/Saveの追加10 DOM、raw保持・音声guard不変を受入 |
| QA-04 | P1 | 偽timelineを除いた後の専門家sample契約 | 統合済 | c456795、production変更なし。emptyとnot_run、結果レビューとblocked前提条件、4空表/固定CSV/固定run不変を明示assert |
| EFF-01 | P0 | cleanup OFFと既存effort互換 | 統合済 | f4d692e、OFF時の校正停止、非OFF強度を思考能力と混同しない |
| QA-05 | P1 | 世代保護テストの並列fixture競合とthread残存 | 統合済 | 9e8a326、両adapter同期とfinally解放。本体不変更、旧競合4条件再現、250反復と70隣接、guard無効化を検出 |
| DEL-01 | P0 | 節目のソースbundleと最終引継ぎ | 受渡し準備 | 復元・再構築したGit履歴bundle、独立clone/fsck、空runtime起動/再起動、読みやすいsource ZIPと日本語手順。最新の版/hashはcheckpoint manifest |

## Backend区切り（9768b80）

復旧後の新しい修正は2854ad6、8b8a5be、1ccd8b2、5cba079、b394553、19e886e、9768b80。旧の失われたcommitを復元したという意味ではない。

- `pytest tests -q -k 'not browser' --ignore=tests/test_qualitative_visualization.py`: 926成功、10skip、24deselect、467 subtests成功。実browserを合格扱いしない
- 独立48件成功。1120定義のmatrixは106受理/1014明示拒否、106実trial・44代表pipelineで不変条件違反0。非有限JSONを固定入力にできない条件は別計数
- 一時DB・合成fixtureのみ使用。外部AI、実モデル推論、実Vault移行、push/deployは未実施
- 依存・詳細ログ・再現probeは`../artifacts/eight-hour-20261003/`（appからの相対位置）。今後の差分をこの合格結果へ含めない
- 新binding/台帳を実runtimeで使う前には旧workerを停止またはdrainする。旧binaryを新runtimeへ戻す互換性は未検証。UIの撤回とbackend安全修正の撤回を分ける
- cloud browserの通常loopback経路は拒否、standalone Chromiumは起動制約あり。迂回せず、V3/V4/V5は未受入。静的・合成DOM確認と実画面を分ける

## 23:04 UTCの統合区切り

- 主branchは `5fa689f`。分析UIの14対象ファイルは受入元 `3443eae` のmanifest hashと一致して統合した
- 3種類の測定presetは元JavaScriptから実Flaskへ15要求の往復を検証。役割presetは登録来歴の不一致があり、独立受入を保留して修正中。合成DOMだけで実adapterの正しさを代用しない
- `869b843` の全体試験は976成功・32skip・1失敗。失敗は子processのimport経路で、`5fa689f` の対象3試験は成功。修正後の全体成功とはまだ扱わない
- 32skipの内訳は実browser opt-in未実施22、Windows依存10。GUI・支援技術・実音声の評価は別途未実施
- 保管source bundleは主branchに加えて本セッションの専用branchのcommitを含む。未統合branchを主branch受入済みとみなさない。最新の保管版とHEADはcheckpoint manifestに記録する

## 2026-10-04 00:05 UTCの統合区切り

- `c6e5094` のsourceを固定して `PYTHONPATH= .venv/bin/python -m pytest tests/ -q -rs`: 1012成功、32skip、953 subtests成功、失敗0。32skipはbrowser opt-in未実施22、Windows依存10。既存lokyのCPU数warning1
- 固定runは保存した要約・定義版・表を読取り、閲覧時に現入力から再計算しない。独立検証でDB・保存bytes不変、最新100件外のrun指定、破損/欠落停止、null/0/空欄と省略表示を確認
- 公開試行とpipeline台帳を同一DB snapshotから取得。最新の同package完了試行が4writer成功の根拠となり、古いpipeline台帳との不一致は別に表示。空scopeは不明なscopeや別packageと区別する
- source/synthetic受入と全体試験後も、追加監査で特殊keyを話者名やstatusにした不具合を再現したため修正する。既存テストの成功を、未試験条件の正しさへ拡張しない
- 次は実HTML・実handlerのDOM統合試験と、そこで再現した名前処理・control関連の局所改善。DOM libraryは外部resourceを読まず、実ブラウザーの描画・支援技術の評価には代用しない

## 2026-10-04 01:01 UTCの統合区切り

- 固定source `ed7a3f1` で標準pytest **1017成功・32skip・953 subtests成功・失敗0**。同HEADの既定DOM suiteは **72成功・失敗0**。32skipはbrowser22・Windows10で、実画面／ATの合格を意味しない
- 特殊な話者ID、話者controlの名前と再描画focus、履歴リンクの許可境界、話者editorの欠測表示、古いroute応答、分析Saveの所有権を独立レビューして統合。旧sourceを用いたnegative controlは同じ正しい期待値で失敗することも確認した
- 一時的な実行環境切断で旧全体試験が途中終了した。未完了ログを残し、同HEADで全体試験をやり直して成功を確認。作業tree・commitは保持された。途中終了を成功として計数しない
- 復元可能なsourceには専用branchの未統合回帰も含める。未統合のfixedviewer／測定dialog／backend欠測は上の作業ボードのまま追跡する。実データ・外部AI・公開・deployには接触していない
- 根拠は `../artifacts/eight-hour-20261003/integration-dom-recovery/`、独立UIの初期ログは `../artifacts/ui-review/`。source復元手順を本ノートへ追加した

## 2026-10-04 01:22 UTCの統合区切り

- 固定source `9c92b6b` で標準pytest **1026成功・32skip・959 subtests成功・失敗0**、同HEADの既定DOM suite **92成功・失敗0**。browser22・Windows10は未実行のまま
- `focus-group-local-5`／registry9で、時間欠測を実0と分け、対象集合に欠測がある割合・均等度を非算出にした。部分観測は時刻あり小計とcoverageを併記し、未観測の0秒グラフを描かない。巨大JSON整数の時刻も500ではなく欠測扱い
- 旧v4の受付済みsnapshotは旧数値・旧計算版のまま保存され、新v5はnull/空欄を使う。実Flask・保存CSV・固定GETのbytes不変を独立確認。新仕様を過去結果へ遡って適用しない
- fixed runは編集側Saveから独立して読める。保存時入力との比較は取得時点と明示し、同itemの後続編集を現在一致の保証へ取り違えない。測定定義dialogは再open時のbusy解除とnavigation時の同期終了を追加した
- 外部consumerは `speaking_seconds`・`total_speaking_seconds`・割合のJSON null／CSV空欄を受理できるか採用前に確認する。自動的に0へ補完して旧意味へ戻さない。DB schema・原入力・実runtimeの移行は行っていない
- 同itemの分析Save完了による測定dialogの入力版失効、未確定roleの表示、混在roleの順序依存は別課題として継続。根拠は `../artifacts/eight-hour-20261003/integration-timing-dialogs/` と `analysis-recovery-review/`、`ui-recovery-review/`

## 2026-10-04 01:36 UTCの統合区切り

- 固定source `1cf236f` で標準pytest **1027成功・32skip・959 subtests成功・失敗0**、既定DOM suite **95成功・失敗0**。Node/browser/Windowsの範囲は前区切りと同じ
- 来歴未確定の会話役割を含むeditor insightは仮集計と明示し、未確定人数を示す。default／legacy_unknown／未知sourceを勝手に明示役割へ変えない。明示・registryの通常表示は保持
- 分析Saveで入力版が更新された測定dialogは、入力済み文言を保持して旧試行・確認・採用を失効させる。未送信の下書きIDは保持し、保存済み／送信中IDは元を保護する新しい下書きIDへ分ける。理由を表示し、自動の定義送信や採用はしない。主分析の後続未保存変更があれば操作制限を保持
- 混在role backendは候補 `c6abf58` の独立受入まで進んだが、この主branchにはまだ含めていない。v6と旧v5固定値の区別、役割混在による非算出と時刻欠測による非算出の表示を最終確認する。固定runの保存計算版の表示も別の次課題
- 根拠は `../artifacts/eight-hour-20261003/integration-input-role-ui/`、独立roleの `analysis-recovery-review/`、定義文言保持の `ui-recovery-review/`

## 2026-10-04 02:43 UTCの統合区切り

- 固定source `a91eec3` で標準pytest **1048成功・32skip・1025 subtests成功・失敗0**、同HEADの既定DOM suite **151成功・失敗0**。前後HEADとclean状態を確認。32skipは実browser22・Windows10、既存loky warning1。異なる層の件数を合算しない
- 混在roleのv6、保存計算版の表示、固定packageのmember/snapshot検証、v7の残る時間欠測、editorの数値文字列・時刻編集再描画を統合した。全欠測を0にせず、真0と空集合を保持する。役割不確定による非算出と時刻不明を区別する
- `397be30` の全体試験は **1045成功・1失敗・32skip・1017 subtests成功**。失敗は旧専門家sampleが仮の0 timeline行を結果とみなしたassertだった。`c456795` はproductionを変えず、empty／not_run、保存結果レビューなし／現在のblocked前提条件、4空表と固定CSVを明示確認する。旧失敗ログは保持し、最新の合格に置き換えて数えない
- 互換性: JSON null／CSV空欄とcoverageを受理できるか外部consumerで確認する。追加nullableはlibraryの`duration`、分析の`session_duration`、感情の`seconds`、コードの`speaking_seconds`も含む。session終端は除外を含む全発話の最大終了位置で、録音全長やincluded発話合計とは別。旧v4〜v6の固定値と元計算版を保ち、新意味を遡及適用しない
- full GETの`segment_timings`は元ID/原値/順序/件数に結び付いた表示専用値。原入力や保存payloadへ混ぜず、局所変更・不正値で数値guardへ戻す。音声再生guardを緩めない。通常の数値時刻編集で内部20秒なのに画面10秒となる旧不具合も独立DOMで反転確認した
- 根拠は `integration-projection-contract/`、`analysis-recovery-review/`、`ui-timing-review/`（いずれも証跡root配下）。実browser・AT・Windows・実モデル・実Vaultは未実施。手動受入の短い確認表は証跡 `ui-timing-review/final-ui-handoff.md`。次は独立cloneから空runtimeだけで起動/停止/再起動を確認し、最終受け渡しを整える

## 2026-10-04 03:47 UTCの統合・受け渡し区切り

- 固定source `721c308` で標準pytest **1049成功・32skip・1052 subtests成功・失敗0**、同HEADの既定DOM suite **161成功・失敗0**。2 suiteを同時実行し、前後HEAD/clean状態を確認。browser22・Windows10は未実施、warningは既存CPU数検出1件のみ
- 通常JSON importが保持する空配列/空objectの`time_unknown`は、既存Python契約では偽だが旧editorでは不明になっていた。`4c31983`は計測内だけを一致させ、元marker・保存payload・backend版・音声/evidence guardを維持。961組合せのうち旧版で不一致だった6条件をすべて解消し、17452 assertions、実renderResult57条件が成功。追加実DOM10件はimport→実時刻編集→Saveと旧binding失効を確認し、旧版は8件失敗する
- `e11e3ce`の全体試験は **1048成功・1失敗・32skip・1052 subtests成功**。世代保護fixtureがM2の最初のadapterだけを待ち、もう一方のchecking/readyを残していたため、productionのretry guardが正しく拒否した。`9e8a326`は対象テストだけを両adapter同期＋finally解放へ変更。本体の安全条件を弱めず、旧競合4条件の決定的再現、250反復/残存thread0、隣接70 tests、generation guardを外したnegative controlを確認した。失敗ログも保持する
- 03:10〜03:29 UTCに環境起動障害があり、依存する実行を止めた。復旧後に残っていたHEAD/clean状態/未commit差分を確認し、未回収の試験結果は既存logとsource hashを照合してから受入した。障害中の未確認結果を成功へ読み替えていない
- `5d5c594`のbundleから新しいclone/空runtimeを起こす確認は成功。8 JS/2 CSSのbytes一致、空一覧/話者、通常security guard、二重起動拒否、正常停止/再起動、SQLite整合性を検証した。同版のsource ZIPも857 filesがGit blobと一致し、Gitなしの新規展開先で1048 pytest/151 DOMを再現した。これは当該版の検証であり、最終配布版のhash/追加確認はcheckpoint manifestと同梱の短い検証要約に記録する
- ソースの変更はここで凍結し、以後はこの内容の復元・梱包・最終照合を進める。実browser/AT/Windows/モデル/利用者データ・実runtimeへの配備は未実施。新たな未検証機能へ範囲を広げない。4部門の再利用手順は[依頼テンプレート](gurumoji-department-briefs.md)を参照し、常駐daemonの導入とは扱わない

## 保存したソースから安全に再開する

`Gurumoji_session_source_20261003.bundle` は Git の完全履歴で、アプリ／Software Vault と本セッションの専用branchを含む。仮想環境、node_modules、実runtime、媒体、研究Vault、資格情報を含めない。固定成果物やDBのバックアップではない。実データの復元は [[60-Operations/backup-restore]] を別途使う。

1. 既存checkoutへ上書きせず、空の新しい場所へcloneする。bundleのdefault HEADに依存しないようbranchを明示する

   ```sh
   git clone --branch dot/gurumoji-eight-hour-20261003 Gurumoji_session_source_20261003.bundle gurumoji-review
   git -C gurumoji-review fsck --full
   git -C gurumoji-review status --short --branch
   git -C gurumoji-review rev-parse HEAD
   ```

2. `Gurumoji_session_evidence_20261003.zip` 内のcheckpoint manifestで、主branch HEAD・全体試験対象HEAD・未統合branchを照合する。最新のbranchが存在することと、主branchへ受入済みであることは別。source bundleのSHA-256もmanifestに記録する
3. 元のPC・別環境の未公開差分を先に保全し、共通基点から両側の差分を比較する。既存repoへreset／clean／強制上書きはしない。統合先や公開先をこのcloneだけで変更しない
4. Python環境は実行OSの手順で再作成する。WindowsのvenvをLinuxへ流用せず、認証やモデルを復旧済みと仮定しない。設定とCPU手順は `.agents/rules/dot-cloud.md`、Windowsは `.agents/rules/windows-local.md` を参照する
5. Pythonの標準試験は `python -m pytest tests/ -q -rs`。Nodeの局所probeは標準試験のwrapperから実行する。オフラインDOM統合は `tests/dom/README.md` の別コマンドで実行し、対象source rootを固定する。browser／Windows固有のskipを合格件数へ加算しない
6. 実runtimeに適用する場合は、旧workerの停止またはdrain・対応するdataバックアップ・保存形式の互換確認を先に行う。新台帳を旧binaryで読み書きするrollbackは未検証。今回のsource受け渡しはアプリ起動・deploy・実データ移行を自動で行わない

## 作業の進め方

1. 再現と影響を示し、既存責務を使う小さい修正を選ぶ
2. 主作業treeの実装担当を1つに限定する。独立したテスト整備は別worktree/task branchで行い、調整担当がレビューして明示的に統合する
3. UI/UXと分析担当が独立に検証し、問題があれば同じ修正を閉じるまで戻す
4. 次の高価値課題へ進む。時間消化だけの反復、未検証の成功報告はしない
5. 期限で変更を凍結し、最終HEADに対する試験、未実施範囲、復旧可能な成果物を受け渡す

部門への再利用可能な依頼は[依頼テンプレート](gurumoji-department-briefs.md)を使う。既存の詳細契約は複製せず、[設計入口](../../../DESIGN.md)、[運用引継ぎ](dot-cloud-development-handoff.md)、[受入方法](../50-Tests/ui-design-acceptance.md)へ戻る。

## 2026-10-05 Windowsでのマーラータン保存データ確認

- 利用者の依頼で、`main` / `2f2479ca638c569f6978bec47c509646bd92ff67` の既存分析を実行。対象はローカルDB内の唯一のインタビュー `bb5555800e4248d7a401fc97c85c6882`、入力版1、本文revision 0、分析revision 0。過去のResearchVaultのI001ノートは別conversation IDなので、現DBのIDを根拠とした。
- `.venv/Scripts/python.exe output/malatang-smoke/run.py` は終了コード0。323発話・観測5話者、323/323発話に有効時刻。参加量・会話動態の既存method adapter、GiNZA 5.2.0の形態素／係り受け（7,226 token）、SciPyの統計処理、JSONの非有限値検査、48種のCSV生成／再読込を確認。ゼロ行の表は生成のみの確認で、Transformerや手動コードを実行した証拠ではない。
- 準備状態はdraft、内容確認済み0/323、相互作用分析の準備済み0/323。5話者は観測数であり、確認済み参加者数ではない。研究者の確定解釈や音声との一致を検証したという意味ではない。
- SQLiteを`mode=ro`と`query_only`で読み取り、実DB・研究Vaultへの書き込みなし。処理前後の本文hashとrevision一致を確認。入力hash、分母、各出力件数、未実行範囲はローカル成果物 `output/malatang-smoke/result.json` に保存。本体実装の変更なし。
- 音声からの再文字起こし、話者分離推論、外部AI、Transformer推論、ブラウザー操作、保存・公開は未実行。次にこれらを検証する場合は対象工程を指定し、実Vaultをテスト保存先にしない。

### 同日：AI反復が0回だった理由

- 前回のテスト範囲を基本分析に絞ったため、自律分析は未開始だった。`output/malatang-smoke/run.py` は `group_analysis_for_row` と参加量／会話動態のmethod adapterを呼ぶが、`AnalysisOrchestrationService.start`、`run`、AI runnerは呼ばない。method adapterは既存集計とCSVを結果形式へ変換するだけで、Coreの反復処理ではない。
- 現行の開始経路は `POST /api/library/<item_id>/analysis/orchestration` → `service.start` → 保存・schedule → `_run_analysis`。Coreタスク登録直前に `iteration` を加算する。通常の基本分析から自動でこの経路へ入る実装ではない。`max_iterations` は指定する場合に1以上を要求し、前回はその設定検証自体を通っていない。
- 前回と同じローカルDBをSQLite読取専用で照合し、`orchestration_*` テーブルなし、対象itemの旧AI見解request 0件を確認。既存pipeline requestは2件あるが、別の台帳であり自律反復の回数には換算しない。この調査から別DB・別環境の実行履歴までは断定しない。
- 前回の「AIループ0回」はテストでAI開始処理を呼ばなかったことの説明であり、保存runのiterationを測定した数値ではなかった。接続障害、準備状態draft、回数制限で停止したという根拠はない。調査中もAI推論・実行開始・実DB/Vaultの書き込みは行っていない。本体変更なし。

### 同日：実AI開始・反復試験とWindows修正

- 目的は基本分析だけの確認から、既存POST開始・Core・批判レビュー・次のCoreという実経路を検証すること。基点は引き続き`main / 2f2479ca638c569f6978bec47c509646bd92ff67`、変更は未コミット。再現用に`scripts/test_saved_autonomous_analysis.py`を追加し、元DBは読取専用、SQLite backup先だけに追加台帳を作る。媒体参照をコピーで外し、Vault公開を禁止する。AI応答のmock置換・クラウド送信なし。
- WindowsでCSVのsys.maxsizeがC long幅を超えてimport失敗したため、受理される幅へ下げる。raw SQLite factoryのconnectionもcommit/rollback後に閉じ、Windowsの一時DB削除失敗を修正した。Handlerのcall_timeout_secondsを実通信workerへ渡す。Coreの空要約・解釈担当へのlabel_frequency指定は登録前に隔離する。モデル用プロンプト・schemaで次の作業/終了判断、終了理由コード、発話IDと根拠IDの使い分けを明示した。
- 実モデルの初期失敗も保持する。GPT-OSS 20Bの既存8192枠では要求拒否、65536枠/部分GPUでは通信timeout、32768枠では全項目が空のCore応答を得た。空応答を分析成功としない。Qwen3 8Bは推論ONや文字列だけの/no_thinkで長時間生成/timeoutになり、実capabilityのoff設定からreasoning_effort=noneを送る試験へ切り替えた。停止した試験は取消し・timeoutのまま保存する。
- 原文24件にしても全323件の根拠ID索引が残り、後続criticで入力枠超過のHTTP 400が発生した。context_index_limitを追加し、原文と索引の省略を別々に記録する。既定0は従来の全索引。全量固定snapshotは323件を保持する。索引の外を順次読む処理は追加していない。
- **反復動作は確認済み、分析完了は未達**。最終の実試験は`output/malatang-autonomous/20261005T003035Z-4120cd7e/result.json`、run `run_cd826f0356f34003993b0e24d7c3c177`。Qwen3 8B、実ロード32768枠、並列1、原文/索引各48件。Core成功2回、critic成功1回、実測AI呼出し3回、input 72,651/output 1,802 token、約67秒。不正/失敗タスク0。criticが根拠不足を指摘し、Coreがその指摘への採否を返さなかったためhuman_review_requiredで停止した。厳格なpassed=falseを保持し、全323発話の解釈完了や固定成果物保存成功とは扱わない。24件の前試験もCore2/critic1が成功し、人の確認待ちで停止した。
- 元入力hashは前後とも`7dc5067452160de02239ef10a9ee7c2861ccbe49b00c96f197085bea9775d7ef`、revisionも維持。実利用者データは読取りだけ、書込みは試験コピーのみ。config/tokens.jsonを変更せず、試験モデルのロード設定は一時変更とする。GPU実測は生成中99%/VRAM約11GBで、コード調査・unittest・待機時の低使用率と区別する。
- 最終の関連unittestは128件成功・失敗0（24.415秒）。対象はCSV、実試験の判定、analysis_queries、fixed_run、orchestration本体/adapter/route/integration、review、durable integration。git diff --checkと対象Python compileも成功。保存台帳からの再判定、変更コードhash、試験module一覧は同試験ディレクトリのverification.jsonに記録。厳格な元result.jsonは書き換えない。終了時にGPT-OSS 20B・8192枠・並列4・TTL3600秒を再ロードし、idle/queued 0を確認した。
- 音声文字起こし、話者分離推論、ブラウザーUI、実Vault公開、研究者による確定解釈は未実行。次の課題は未提示範囲の参照と、モデルの批判応答欠落への対処。反復回数を増やすだけで研究上の根拠不足は解消しない。

### 同日：CSVの保存用途を評価

- 利用者の依頼により、現行`AnalysisStore.save`/`csv_bytes`と固定結果readerを評価。CSVは全件の表計算・共有用として維持し、AI再分析や統計へ渡す正本は型・欠測・版を検証するJSONを優先する判断。現行もCSV単独保存ではなく、SQLite台帳とinput/parameters/result/manifest JSONを併用している。
- 実データを使わず、現行csv_bytes→csv.DictReaderで合成10値の往復を確認。null/空文字、数値0/文字列0、false/文字列False、数式風=A/元からの'=A、文字列配列/そのJSON風文字列の5組がそれぞれ同じCSVセルになった。前回の48種CSV読取成功は構文と出力件数の確認であり、元の型や欠測を無損失復元できるという確認ではない。長いセルのWindows互換修正も、この区別を解消しない。
- [既存FLOW-1提案](../40-Design/core-handler-routing-reorganization-plan.md)に沿い、result.jsonで全件を保持できない表だけschema版・列型・安定行ID・欠測理由を持つtables/*.jsonを追加するのが次の候補。JSONにも列の単位・分析対象集合・分母・入力版/発話ID/run ID/hashの契約が必要。[JSON Schemaの型検証](https://json-schema.org/understanding-json-schema/reference/type)を根拠に検証方法を具体化できる。大量表の容量・読取性能が実測で問題になれば、[Parquet](https://parquet.apache.org/docs/overview/)を別途比較する。今回は形式変更・移行・追加実装を行わず、旧成果物のbytes/hashと数式対策を維持する。

### 同日：Software Vaultに記録後、型付き全件表を実装

- 利用者の追加依頼により、[[40-Design/decisions|ADR-124]]を先に記録してからAnalysisStoreを修正。基点main/2f2479ca638c569f6978bec47c509646bd92ff67の未コミット作業ツリー。result内の同名配列の全件性を推測する方式は避け、新規runの各CSVにJSON表を対応させた。保存先/DB schemaは変えず、manifestとpendingへ表形式版1を固定する。詳しい契約は[[30-Data/analysis-storage-v1]]に集約。
- 全行・型・null/空文字/存在しないキー・根拠を保持し、run内行IDと入力snapshot/revisionを記録。read_tableは既存hash/manifest検証に加え、schema、行数/行ID、観測型、CSVとの一致を照合する。未知の版・欠落・改変時は停止する。意味上の単位/欠測理由を創作せず、汎用の後続分析/変数定義までは追加していない。Researchの手法ノートにはJSON全件表と共有CSVを既存所有権保護経路でリンクする。
- 旧CSVのみの完了runは閲覧/ZIPを維持し、JSON表を後付けしない。旧pendingの復旧は旧形式、新pendingの復旧は元データと保存時の形式を維持する。新形式の保存中runを旧writerで再試行するrollbackは未対応で、停止/完了後に切替し未完分は新版で復旧する。
- 検証: 最終関連unittest **160成功・失敗0、115.296秒**。fixed run、storage、queries、自律分析公開、milestones、pipeline regressions、自律分析統合/durable、interview comparison、CSV上限を対象とした。型の衝突5組、221行の全件取得、空表/全null、NumPyのJSON互換float、改変/非有限値/非文字列キーの拒否、新旧保存失敗の復旧、旧形式の安全なUnicodeパス、ノートの編集履歴/削除保護を確認。初回の再試行引数漏れは修正し、WindowsのUTF-8ノート読取をテストで明示した。git diff --checkと対象Python compileも成功。
- 一時DB/Vault・合成値のみ。実DB/実Vaultの移行・公開、音声/実モデル推論、実ブラウザー操作は未実行。検証metadataと変更コードhashは`output/malatang-storage-final/verification.json`。既存のマーラータン試験結果は上書きしない。

### 同日：最低3回後にCore判断で継続・終了

- 利用者の追加指定を[[40-Design/decisions|ADR-125]]へ記録。新規API/画面の既定はAIお任せ、通常の自動終了を最低3回の採用済みCore判断まで保留する。3回を超えて続行するかはCoreが選ぶ。呼出し/タスク/時間上限、手動停止、障害・レビュー失敗は優先する。明示した別モード、保存済みrunの条件・履歴、adapter版不一致時の復旧停止は維持する。SQL列変更・実データ移行なし。
- 回数は永続判断台帳から数え、失敗/隔離/未採用を成功へ含めない。contextに最低回数と採用済み回数を渡し、終了保留イベントを記録する。画面の時間/回数上限は既定で空欄、autoの上限1/2はAPIと画面で拒否する。プロンプト版はcore-handler-prompts-4-minimum-iterations。
- 合成検証は関連unittest **129件成功、23.365秒**、DOM操作26件成功、隔離した実ブラウザー操作1件成功（1.556秒）。通常停止を3回まで保留、3回以降の続行（5回で終了）、上限3での正常終了、3回目の不正応答の拒否、旧条件の保持、停止/予算/復旧/公開を確認。ブラウザーの通信は合成応答だけで実Vaultへ書き込まない。DOMのNode22.19.0は宣言engineより古い警告あり、テストは成功。UTF-8のfixture出力を環境変数で指定した。
- 実AIはマーラータンの読取専用SQLite backupでQwen3-8b/32768枠/parallel1/GPU全配置/reasoning_effort=noneを使用。5試験の採用済みCore回数は順に **2, 2, 2, 0, 1**。3回成功は未確認、分析完了も未達。失敗結果を保存し、合成検証の成功と混同しない。
- 初回（20261005T010818Z-2e90555b）は批判者が旧対象版を転記して隔離。次（011044Z-804798dd）は3回目の出力がtoken上限で途中終了。24/323発話へ減らした次（011444Z-9edddeda）はno_issuesと非空issuesの矛盾で隔離。次（011745Z-ceb2b177）はCoreが存在しない批判IDへの応答を生成して隔離。批判者の現在対象ID/版とCoreの実在issue/proposal IDを生成用schemaでも固定し、状態/指摘一覧の整合性をプロンプトで明確化した。採用前検証を弱めず、原応答を補正して成功にしない。
- 最終（012137Z-3211def1、run_6309cb32393047418bc01f66681ff506）はCore1回を採用したが、alternatives/unresolved各24件の重複を含む20,123文字の応答で、後続criticがHTTP400。依然として局所モデルの出力量/履歴context増大の制約が残る。次の対象は全量原結果を保持したうえでの重複・要約投影とcontext/出力予算。最低回数の制御を品質保証や全323発話の読了へ読み替えない。
- 元DBのsource hashは全試験で`7dc5067452160de02239ef10a9ee7c2861ccbe49b00c96f197085bea9775d7ef`のまま。コピー以外のruntime台帳・研究Vaultへ書き込まず、音声処理・実Vault公開・移行は未実施。終了後はGPT-OSS20B/8192枠/parallel4/TTL3600秒へ戻し、IDLEを確認。設定ファイルは変更しない。
- 基点main/2f2479ca638c569f6978bec47c509646bd92ff67の未コミット作業ツリー。各resultは`output/minimum-loops-real/<上記ID>/result.json`、コマンド・コードhash・各台帳の採用回数は`output/minimum-loops-test/verification.json`に保持。Python compile、JS構文、git diff --check成功。

### 同日：利用者指定の再試験で実AIの3回採用を確認

- 実run `run_008cbf3502d7400e94876c47734b1325`、出力`output/minimum-loops-retest/20261005T013659Z-d11dbe3d`。Qwen3-8b/実context32768/GPU全配置/parallel1/reasoning_effort=none。試験用questionに「1回分のJSON、alternatives/unresolved各3件以内、異なる内容、未提供発話は未読」を追加した。製品の既定prompt・停止制御は変更していない。
- **実AIの有効なCore判断3回、critic1回、verification1回、失敗タスク0**。2回目の終了案をmin_iterations=3により保留したイベントを確認し、3回目でCoreがquestion_satisfiedを選びcompletedとなった。実通信5回、報告された入力125,529/output6,540/total132,069 tokens、試験159.47秒。表示・結果再取得にAIを呼ばないことも確認。
- 初回の結果collectorはKeyErrorで失敗した。テストスクリプトが通常起動時のinitialize_libraryを省いたため、完成した固定runのstatus取得でanalysis_publication_attemptsテーブル不足/HTTP503になった。スクリプトだけを修正し、コピーDBのパス一致を確認してrepair_provenance=Falseで通常schema初期化を行う。HTTP失敗を未確認のrunとして扱う診断も追加。原本に初期化処理を実行しない。
- 同じ保存済みrunを正常初期化後に再検証し、status HTTP200、assess_runの全条件成功、固定成果物save_status=saved、6 artifactsのhash/manifest/型付き表検証に成功。再推論や保存の再計算は行わず、元の失敗result.jsonを保持した。最終確認は`output/minimum-loops-retest/verification.json`。通常終了・3回以降続行・上限/障害・旧条件と初期化先の保護の関連15 tests成功、0.664秒。
- 最初のCPU併用試験（013029Z-8efc9fda）はCore1回採用後、実行時間のため通常cancel経路で停止し、その結果を残した。CLIは65536を指定したがLM Studioの実contextは32768で、64kで成功したとは扱わない。
- 固定snapshotは323発話を保持するが、各呼出しの原文/索引は48発話。**これは限定範囲の動作試験であり、全323発話の読了・科学的解釈の妥当性を保証しない**。原本のsource hashは`7dc5067452160de02239ef10a9ee7c2861ccbe49b00c96f197085bea9775d7ef`のまま。実Vault公開・音声処理・今回の実ブラウザー操作は未実施。
- 試験後にGPT-OSS20B/8192枠/parallel4/TTL3600秒へ戻しIDLEを確認。アプリ本体・設定ファイルはこの再試験で変更せず、試験スクリプトと回帰テスト、Software Vaultの検証記録だけを更新。基点はmain/2f2479ca638c569f6978bec47c509646bd92ff67の作業ツリー。

### 同日：最終レビュー・修正・Git受け渡し

- 利用者の修正・push指示により、実装とテストをcommit `55baa9d7ec83f643c871c6680017893924093ef3`へ確定。基点は`2f2479ca638c569f6978bec47c509646bd92ff67`。送信先は既存の`origin/main`で、fetch時に基点との乖離なし。設計判断・各試験の成功/失敗を含むSoftware Vaultの変更は、この実装commitを参照して別commitにまとめる。
- 部分保存の再試行で呼出し側のrevision/provider/modelが変わると、元のJSON表と異なるbytesを作ろうとして再保存が失敗する問題を合成値で再現。保存開始時のpendingにあるrevision、provider/model、app_urlを使うよう修正した。固定成果物の直接上書き・移行は追加しない。回帰テストは修正前に失敗し、修正後に成功した。
- 隣接試験の初回38件は、一時SQLiteの接続未closeによりWindowsのcleanupで12件エラー。共有fixtureのcontext managerでcommit/rollback後にcloseするよう修正した。失敗をskipやignoreへ変更せず、当該試験とfixture利用側を再実行した。
- Windows `.venv/Scripts/python.exe`、`PYTHONPATH=src;tests`、`PYTHONIOENCODING=utf-8`で検証。appの保存先は`output/final-review`配下へ隔離。下記は重複を含む別バッチの結果で、件数を合算した独立テスト数ではない。
  - 最終レビュー前: `python -m unittest test_analysis_fixed_run test_analysis_storage test_analysis_queries test_analysis_milestones test_pipeline_regressions test_interview_comparison test_csv_field_limit test_analysis_orchestration test_analysis_orchestration_adapters test_analysis_orchestration_integration test_orchestration_review test_orchestration_durable_integration test_orchestration_publication test_orchestration_initial_recovery test_analysis_orchestration_routes test_saved_autonomous_analysis -q` — 264件成功、115.441秒。
  - 再試行修正後: `python -m unittest test_analysis_fixed_run test_analysis_storage test_analysis_snapshot_commit test_analysis_plan_binding test_orchestration_publication test_analysis_orchestration_integration -q` — 84件成功、97.265秒。
  - fixture修正後: `python -m unittest test_analysis_definition_safety test_analysis_orchestration_methods test_analysis_orchestrator_regressions test_analysis_publication test_analysis_publication_safety test_analysis_recovery test_analysis_exports test_analysis_research_protocol -q` — 68件成功、27.397秒。`python -m unittest test_analysis_generation_safety -q` — 15件成功、2.437秒。
  - UI: `GURUMOJI_TEST_PYTHON`を同じvenvへ向け、`node --test tests/dom/orchestration.test.cjs` — 26件成功。`GURUMOJI_RUN_UI_BROWSER=1`で`python -m unittest test_ui_safety_browser.UiSafetyBrowser.test_autonomous_defaults_minimum_three_and_optional_caps -v` — 実ブラウザー1件成功、1.539秒。通信は合成fixtureのみ。
- Python compile、JS構文、`git diff --check`も成功。全体suite、追加の実AI推論、音声処理、実Vault公開/移行、別環境への反映は未実行。実AI3回採用の証拠と限定範囲は直前の節を参照し、今回の保存再試行修正後に再推論したとは扱わない。
- commit対象は実装・テスト・再現スクリプトと設計記録だけ。`runtime`、`config/tokens.json`、個人Vault、実DBコピーや`output`の推論成果物は含めない。利用者データへの新たな書込みなし。

### 同日：通常のColabノートブックを更新

- 利用者のColab更新依頼により、通常の文字起こし・分析用`notebooks/Gurumoji_Colab.ipynb`とREADME、`tests/test_colab.py`を更新。実装commit `b3768a59232815c58bafaa7619a4b3345214b184`、基点`e69097453ec50551af49a8523690fde437744aa0`。Knowledge Control Centerの別ノートブックは対象外。
- セットアップはmainを明示したfast-forward更新と実HEAD表示を行う。アプリ/Ollamaが実行中、main以外、追跡ファイルに編集がある場合は変更前に停止する。既存ランタイムの利用者には、分析の停止・保存状態を確認し、終了セルを実行して最新ノートブックを開き直す手順を示した。reset/clean・変更破棄・実データ移行は追加しない。
- 旧処理はモデル一覧だけで準備完了としていた。新版は合成入力による短いJSON Schema応答を実行し、正常終了・JSON値、`/api/ps`のロード済みモデルと実入力枠を確認する。JSON不正/途中終了・未ロード・入力枠不足/未取得では停止し、ローカルLLM設定を切り替えない。起動セルも検証未完了のモデルでは開始しない。
- 入力枠の既定を16,384から32,768へ変更し、設定範囲4,096〜32,768を維持。GPU配置はsize_vramをGiBで表示し、0はCPUのみ、欠落は未取得とする。GPU使用率の連続監視や全量分析の成功保証ではない。メモリ負担と、設定値/実ロード値の違いは[Ollama公式の入力枠説明](https://docs.ollama.com/context-length)、[ロード済みモデルAPI](https://docs.ollama.com/api/ps)に基づく。既定モデル名は[公式タグ一覧](https://ollama.com/library/qwen3/tags)で確認し、変更していない。
- 最低3回後のCore判断、新規の型付き全件JSON/共有CSV、Google Drive有効時の`data/analysis_store`保持を説明。分析本体は共有実装を使い、Colab専用の停止制御・保存先・再計算経路を追加しない。
- Windowsの隔離保存先`output/colab-update-test`、`PYTHONPATH=src;tests`で`.venv/Scripts/python.exe -m unittest test_colab -q`を実行し、15件成功、1.278秒。全コードセルのcompileと出力/実行履歴なし、更新前のプロセス/編集保護、合成HTTP応答の不正・切断・入力枠不足、CPU/未取得値の保持、既存Colab用Web/securityの境界を確認。`git diff --check`も成功。
- 実Colab GPU、Ollamaの実モデル推論、apt/pipのインストール、Driveマウント、全量自律分析は未実行。テストのHTTP/Gitはmockで、既存Windowsのモデル・設定・利用者DB/Vaultへ変更なし。配布は既存origin/mainへのsource pushのみで、利用者のColabセッションを直接更新・再起動していない。

### 同日：プログラムとマーラータン分析データをDriveへ保存

- 利用者指定の[Driveフォルダー](https://drive.google.com/drive/folders/1TeCym1pulQdMUIrg0HxlU0XCaMo0RTlq)へ、[プログラム＋分析データZIP](https://drive.google.com/file/d/1pwGblwEnTyfXPqUz6XSOxnq3miVJu6wg/view?usp=drivesdk)を新規アップロードした。プログラムは`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`のGit追跡ファイル907件を`program/`へ、成功したrun `run_008cbf3502d7400e94876c47734b1325`の試験用DB、固定入力・結果・JSON表/CSV・検証記録を`analysis-data/`へまとめた。既存Driveファイルの上書き・共有設定変更なし。
- 元の試験DBは読取専用でSQLite backupし、1インタビュー・正常終了・Core判断3回を照合。DB quick_check、保存artifactのhash、ZIP全922ファイルのCRC/manifest hashを確認した。アップロード後のDriveメタデータで指定親フォルダー・ファイル名・26,716,952 bytesの一致を確認。Drive応答にはchecksumが返らず、遠隔bytesのhash比較は未実施。ローカルSHA-256は`ee9c3ee5d3e1d62f788317dce80dcb8536a8c2af7366d430132e8537afcaa903`。確認記録は`output/drive-export/bundle-verification.json`と`drive-upload-verification.json`。
- 設定の秘密値、モデル、仮想環境、媒体、個人Vault、Git履歴は含めない。323発話を保持するがAI各回の入力は48発話、成功試験には回答量の制限指示がある。元のcollector失敗報告と最終再検証を両方保持し、READMEで区別した。利用者の原本DB/Vaultへの書込み、別環境への展開・自動取込・再推論は未実行。DB内の試験当時の絶対パスは保持し、可搬なアプリ復元を検証済みとは扱わない。

### 同日：3回反復の保存内容を点検

- 利用者への内容説明のため、上記成功runの試験DBを読取専用で照合。Core3回の原応答hashは全て`sha256:1807e2c811a0ed49a671df26d18f4fac6336ce05d5efa7b361f997b7d276079a`で一致し、要約・主張3件・代替説明3件・未解決点3件・作業案・終了案が同じ。view_versionも全て1。独立verificationの24主張が後続Coreの見解へ反映されたという根拠はない。3回目でも情報不足を記載しつつquestion_satisfiedで停止している。
- 既存のpassedは通信・採用回数・正常終了・保存の動作判定で、回答の新規性や研究上の十分性を判定していない。最低回数の制御は確認できるが、分析内容が深化するループを確認済みとは扱わない。次の調査対象は同一応答の検知、独立検証の採否、情報不足と終了判断の整合性。今回コード変更・再推論・原本DB/Vault書込み・Drive成果物更新は行っていない。

### 同日：反復の進展検知と専門家結果の採否を実装

- 利用者の修正依頼を受け、`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`を基点としたローカル未コミット変更。既存Handler/adapterへ進展比較と`result_assessments`を追加し、新しい実provider契約を`core-handler-prompts-5-progress`/`core_progress_version=1`へ更新した。API側でprogress=0を指定してもresolverが1へ固定する。SQL列・旧run・封印済み成果物は変更しない。
- 同じ主張・根拠・代替説明・未解決・作業案、過去の状態への循環、要約/ID/順序だけの変更は採用判断へ加算せず`no_progress`で停止する。別IDで生成された同じ役割/範囲/版/hashの専門家結果も新しい根拠にしない。新しい専門家結果は実在IDへの採否・理由・影響を必須にし、無視した応答を隔離して`unreviewed_results`で停止。未評価の21件以上の結果を20件ずつ提示し、古い未評価結果を落とさない。原応答・重複元decision・停止イベントは保存する。
- 画面と実試験スクリプトの判定は採用判断数を使用し、実通信回数と区別する。重複停止で固定成果物のfinalize/公開が呼ばれないこと、読取で再推論されないこと、デスクトップ/スマホ幅で停止理由・採用数・停止後の操作を確認した。設計判断はADR-125追記、現行契約は[[20-Modules/analysis-orchestration]]。
- 検証: 関連9モジュールのunittest 142件成功（27.945秒）。追加した実app組立ての重複停止/公開抑止1件も成功（1.068秒）。DOM 27件成功、隔離した実ブラウザー1件成功（1440/390px、1.197秒）。Python compile、JS構文、git diff --check成功。初回の化粧変更テストはview更新による不要レビューの再生成でcall_budget_limitとなり失敗し、view版の比較も正規化して再検証した。
- すべて合成入力/一時DB・Vault/合成APIで検証。実AI再分析、全体suite、実Vault公開、Git commit/push、Driveの修正版ZIP更新は未実行。利用者の原本DB/Vault・既存分析記録には書き込まない。新しい採否理由の内容妥当性と、意味が等しい任意の言い換えの検出は未保証。最終コードhashとコマンド・成功/未実行範囲は`output/orchestration-progress-fix/verification.json`へ記録する。

### 同日：初回のラベル・尺度作成を専門エージェントへ必須発注

- 利用者の「初回に必ずラベル/尺度を出力」「Coreではなく専門エージェントが作成」の指定を反映。基点は同じ`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、ローカル未コミット。現行adapterを`core-handler-prompts-6-initial-labels`へ変更し、実provider resolverが`initial_label_definitions_version=1`を固定する。初期保存後、会話解釈専門エージェントの専用`label-design-v1`タスクを最初のCore実行前に発注する。
- 1〜12件の尺度候補について名称/安定ID/版、測定対象、型と尺度水準、その理由、値の意味/判定基準、判定規則、欠測条件、推奨集計、提示された発話根拠を検証。空/不正な定義なら原応答を隔離し`initial_labels_missing`で停止してCoreを実行しない。名義/順序尺度の平均指定、値の重複、数値順序の逆転、未提示根拠も拒否。保存hashと作成主体をCore実行前に再確認し、中断後は保存済み結果を再利用する。
- 定義はAI下書きとして台帳と固定JSONに保存し、Coreは結果の採否/統合を担当。画面に専用の読取ボタンを追加し、Markdown書き出しにも定義節を追加した。発話の既存ラベル/コードブック版/研究者本文は変更せず、候補尺度を実行可能な手動測定へ自動登録しない。独立検証のblind packetにも渡さない。契約と判断を[[20-Modules/analysis-orchestration]]、ADR-125追記へ記録。
- 検証: 関連9モジュール150 tests成功（29.795秒）。最後の作成主体/所有権guard追加後、初回尺度と実app保存の11 testsも成功（5.466秒）。DOM 28件成功（18.206秒）、実ブラウザーで尺度閲覧1件成功（1440/390px、1.347秒）、Python compile/JS構文/git diff --check成功。すべて合成データ・一時DB/Vault/合成API。実AI再分析、全体suite、実Vault公開、Git commit/push、Driveの修正版ZIP更新は未実行。利用者の原本DB/Vault・既存の分析結果へ書込みなし。出力内容の研究上の妥当性は別途研究者が確認する。検証記録は同じ`output/orchestration-progress-fix/verification.json`の`initial_label_specialist_revision`に保持する。

### 同日：マーラータン実データで尺度出力・反復を試験

- 利用者のテスト依頼に基づき、323発話の原本DBを読取専用でコピーし、各呼び出し48発話/8,000文字/索引48件でLM Studioの実推論を実施。初回の120発話/全索引では65,827 tokensとなり、ロード枠32,768を超えてHTTP 400。48発話の初期版でも2回目Coreで入力32,466/出力302 tokensとなり応答途中終了した。全323発話をAIへ渡した試験とは扱わない。
- 実データで確認した入力の重複、ID誤写、尺度型と値の不一致、欠測の通常値化、空の追加理由を、既存context/adapter/純粋validatorで修正。最終adapterは`core-handler-prompts-10-complete-intents`。全量snapshot/hashは保持し、AIパケットの重複メタデータを省く。尺度設計には既存AIラベルを渡さず、後続は変更可能なラベル欄だけを渡す。実在ID/節/依存taskと型別生成、必須理由の空文字禁止をschemaにも適用し、不正原回答の事後置換は行わない。共有schemaコンテナーの制約が別フィールドへ漏れる問題も新テストで検出し、JSON往復コピーで分離した。
- Qwen3 8Bは順序尺度と分類の混同、category型で数値を出す、欠測をlevelsへ混ぜる等の応答があり、全試行不合格。GPT-OSS 20Bへ切替え、最初の試行は尺度2件を保存したがCoreのwhy_now空欄で停止。失敗記録は`output/malatang-specialist-labels`の各日時ディレクトリーに保持する。モデルはこの試験だけで指定し、アプリ設定は変更しない。試験用にロードしたモデルは終了後にアンロードした。
- 最終run `run_d2de4cc5ac524ed399b8fbf8b9133ba8`（`20261005T064634Z-c6017726`）: ローカルGPT-OSS 20B、32,768 context、実AI6呼び出し、176.33秒。専門エージェントが初回に「辛さの好み」（順序1〜5）と「価格に対する懸念度」（順序1〜3）を作成し、値の意味/判定基準/欠測条件/根拠と共に保存。最初のCore開始より前の終了時刻、作成主体、catalog/原結果/hashの一致を確認した。Core3回の採用判断、批判者1回、追加解釈1回がある。独立verificationはこのrunで未実行。
- **最終の厳格判定はfailed**。3回目は2回目と同じ追加作業を提案し、同じタスクを再発注せず`no_new_tasks`で停止した。原応答hashは3種類だが進展signatureは2種類で、2/3回目の採否は新しいresult IDへdefer/impact=none。Coreの根拠付きclaimsは全3回とも0件で、専門家結果を主張へ統合した十分な分析とは扱わない。採用数3は新しい専門家結果の評価を含む動作記録であり、内容深化/研究上の十分性/正常完了の保証ではない。固定成果物の自動保存・Vault公開はskipped。終了判定を成功に変えない。
- 原本のsource stampは試験前後で一致。保存原結果全件のhash、全量根拠323件、尺度catalog、JSON/Markdownの既存読取ルート、閲覧での再推論なしを照合。尺度は未検証AI下書きで、科学的な尺度妥当性の検証・全量分析・実Vault公開・Git commit/push・Drive更新は未実行。関連9モジュール153 tests成功（31.586秒）、Python compile/git diff --check成功。未コミット変更のコードhashと実試験は同ディレクトリーの`result.json`、`verification.json`、尺度は`initial-labels.json`、全台帳は`analysis-history.json`/`analysis-history.md`へ保持する。


## 2026-10-05 Windows 専門知識の入力調整を具体化

- 利用者の「エージェント専門知識などでも調整出来るか」に対し、既存コードを確認して[[40-Design/expert-knowledge-production-plan]]の「小型モデルに合わせた専門知識の調整案」へ追記した。担当専門家・手法・段階・対象条件で選択し、必須契約、作業別の知識、具体例、詳細資料を段階取得する提案。現在の短いbrief経路と全件Pack経路を区別し、反復Coreへの未接続も明記した。
- 現行`method_experts.ai_context()`は1500文字以内のbriefと許可段階・文献IDを通常AI見解へ渡す。Pack readerは承認済みclaimを全件渡し、問い合わせ別の順位付けは未実装。部分取得では必須の例外・禁止事項・対立知識を審査済みの選択条件で保持し、根拠ID/hash・送信条件を再検証する。Coreの入力枠超過は別経路なので、まずCore報告の縮約と送信前予算を整える。
- 検証は既存Pack readerの9 tests成功、専門家定義・適用・AI補助の28 tests成功、対象文書の差分確認成功。専門家テストの直接discoverは旧`import app`で読込失敗し、現行`gurumoji`モジュールのaliasを設定した隔離起動で28件を実行した。一時data/output/backupsを使い、実AI・原本DB・研究者Vaultへ書込みなし。今回は計画のみを変更し、知識パケットの部分取得、本番prompt、モデル別予算制御、DB変更、実AIによる効果測定は未実行。

## 2026-10-05 Windows 小型モデルの資料処理と分析を実測

- 利用者のテスト依頼に基づき、既存未コミット変更を含む`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`で実施。既存ローカルQwen3 8B / Q4_K_Mを試験専用IDでロードし、実ロード枠8,192、parallel 1、GPU全配置、reasoning offで使用。設定モデルは変更せず、試験後は自分がロードしたinstanceだけをアンロードした。
- [資料試験スクリプト](../../../scripts/test_small_model_documents.py)を追加。Software Vaultの計画1文書に対し、保存先3問と尺度・blind・予算3問を、節選択・行選択・全文の4ケースで確認した。対象と原文範囲は試験コードが明示選択しており、アプリの自動検索・モデル別予算制御を実装した試験ではない。
- 最終資料試験は**2ケース合格、2ケース不合格**。保存先の問いは全文7,094 tokensと該当節1,364 tokensで同じ内容上の回答となり、入力は80.8%減。SQLite/Software Vault等の別名は内容評価で照合し、指定表記に一致しないことは別項目に保持した。手順の節選択1,680 tokensでは尺度作成者の引用が報告者の説明にとどまり、行選択884 tokensではblindの引用が「契約を維持する」にとどまった。値は正答でも、回答を直接支える引用として不合格。全資料を理解した保証や幅広い品質評価にはしない。
- 初回試験の別名を不正解にする判定を修正し、内容と表記を分離した。また原文一致だけでなく、引用が回答を支える条件を追加した。初回と中間の試行・原応答は残し、最終判定へ上書きしていない。[最終資料記録](../../../output/small-model-documents/20261005T101227Z-61970bc1/result.json)にはprompt、応答、元文書hashと範囲、script版、usage、判定を保持。HTTPエラー本文の保存は秘密値保護のため除去し、最後の変更はcompileで確認した。実呼出時のscript hashは記録に残り、この最後のエラー分岐変更後の再推論は行っていない。
- マーラータンは原本を読取専用でSQLite backupし、AI各回24/323発話、未提示299発話で既存フローを実行。run `run_f8e0567391874d5b846cffa1fc1a4d5e`は初期AI3役とコード統計3手法が保存されたが、Core初期ルーティングでHTTP 400となり`recovery_required`。Core統合0回、尺度0件、厳格判定failed。保存入力から再構成した1token出力の容量確認でも8K枠超過を確認した。この確認は台帳のtask再試行や分析の完了とは扱わない。
- [分析結果](../../../output/small-model-analysis-8k/20261005T100713Z-dc99b41c/result.json)、[容量確認](../../../output/small-model-analysis-8k/20261005T100713Z-dc99b41c/core-capacity-probe.json)、[検証記録](../../../output/small-model-analysis-8k/20261005T100713Z-dc99b41c/verification.json)を保持。コピーDBのquick_check、保存結果6件のhash、元のsource stamp一致、資料入力と文書hash、対象分析コードhash、容量確認によるコピーDB変更なしを確認。`output`はローカルの未追跡成果物であり共有先への配置は未実行。
- 結論は「限定した資料の設問には答えられるが、根拠引用の安定性と既存分析フローは未合格」。本番の入力調整・自動モデル切替は依然未実装。次は[[40-Design/model-context-and-work-memory-plan]]のP1の送信前予算判定と、P2のCore初期ルーティング専用契約・報告縮約を優先する。全323発話のAI分析、32K/他モデルとの比較、研究上の妥当性、実Vault公開、Drive更新、commit/push、全体unit/DOM/browser suiteは未実行。原本DB・研究者所有のVaultへ書込みなし。

## 2026-10-05 Windows モデル別コンテキストと作業記録の計画

- 利用者の計画作成依頼に対し、[[40-Design/model-context-and-work-memory-plan]]を提案として保存し、AI入口と索引から参照可能にした。基点は`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、既存未コミット変更を含むコードを調査。Anthropic、Agent Skills、LM Studio、LangGraph、長文評価の一次資料を参照した。
- パラメーター数と実ロード枠・役割別能力を分け、入力予算、段階取得、全発話の分割提示、初回途中の尺度要求、結果採否と差分の保存を5段階で提案。直近のマーラータン試験は48/323発話、Core主張数0/0/0、厳格判定failedのままで、コンテキスト改善だけで統合問題が解決するとは扱わない。
- 設計判断と開発引継ぎはSoftware Vault、分析の再開状態は既存DB、全件結果は既存成果物へ分担。今回は文書のみ変更し、実装・DB変更・再推論・モデルロード・実Vault公開・Drive更新・commit/pushは未実行。原本DB・研究者所有のVaultへ書込みなし。次の実装単位はP0〜P1の計測と実行前予算判定。
- 文書検証は成功。frontmatter、提案ステータス、note_id一意性、ローカル参照9件・Vault参照5件・入口参照3件、UTF-8、空白と対象差分を確認。実装テストは今回未実行。

## 2026-10-05 Windows モデル別コンテキスト計画の実装と専門知識の選択

- 利用者の「プランを実行して」に基づき、`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`の既存未コミット変更を維持して実装。設計は[[40-Design/model-context-and-work-memory-plan]]、専門知識は[[40-Design/expert-knowledge-production-plan]]、使用契約は[[20-Modules/analysis-orchestration]]。モデルのパラメーター数と実ロード枠を分け、LM Studioのロード済みhandleのtemplate/tokenizer・実枠・設定hashで入力を計測する。出力予約と512tokenの余裕を確保し、超過時は送信前に分割または保留する。SDK探索はモデルを自動ロードしない。
- `model_context_version=1`の新規runで段階別の入力・出力契約を使う。初期全役割の全発話ページ、途中の尺度要求の保存、Handler集約、Coreの担当指示、専門家の尺度下書き、Core統合の順。所有発話と前後の境界を別に記録する。統合は未評価結果の順序付きbatchと、その結果が引用した原文を取得する。未読結果に属する批判は提示しない。入力manifest・提示ID・未読数・評価対象・専門家brief・予算・hashは既存DBのtask JSONと原結果へ保存し、設計理由はSoftware Vaultに保存する。SQL列の削除・改名・型変更はない。
- `expert_step_ids`は既存定義のAI利用を許可した手順だけを選択し、適用範囲・必須入力・未解決事項・禁止結論を残す。選択briefは解釈経路へ接続し、独立検証のblind入力を維持する。Knowledge Pack v2のライブラリAPIは、審査済み選択方針・root・全claim hash・依存関係を検証し、claim全体を取得する。v1と既存の承認・権利検査を維持する。実Packの選択方針の承認や本番の自動選択は未実施。
- 最終v21の関連10モジュールの**159 unittest成功（36.893秒）**。8K/16K/32Kの合成容量境界、未送信時の0推論、323発話の各役割での非重複所有、提示原文とcitationの一致、要件分割、未評価結果保持、再開時の保存結果再利用、専門知識の条件・例外・依存関係の保持を確認。統計schemaを全件専用とラベル集計の枝に分け、部分発話で全件専用コードを再実行する指定を生成させない。旧テストの2枝固定を3枝へ更新した。主張のない批判・尺度要求の根拠取得と、3結果・2批判への4096token出力予約も回帰対象とした。
- Qwen3-8B / Q4_K_M、GPU全配置、parallel 1、reasoning offを試験専用instanceで使用。8K全体試験はcriticの1600token出力上限で途中終了。3200予約では元ページを送信前に拒否し、分割した子ページの単発契約検証は成功した。16Kのv16全体試験は初期AI42ページとコード3件が成功し、各AI役割へ323発話を提示、Core担当指示と尺度下書きも成功したが、Core統合の1600token出力上限で停止した。[v16記録](../../../output/model-context-plan-16k/20261005T110549Z-50921e4b/result.json)。出力予約と未読批判の範囲を修正したv17はCore39回を採用した後、全件専用統計への部分範囲指定を`method_scope_unavailable`として隔離し停止した。[v17記録](../../../output/model-context-plan-16k/20261005T112701Z-c8c96163/result.json)。いずれも原本source stampは一致し、全体合格にはしていない。v17実行時コードは同試験内`code-v17`に保存した。
- 根拠発話を取り直すv18の単発Core契約検証は成功。7発話・評価対象2結果、入力5238＋schema2874＋出力3200＋余裕512で16,384以下。読取専用コピーDBのhashも一致した。[単発記録](../../../output/model-context-plan-16k/core-quote-hydration-v18.json)。引用付きclaimsの構文合格でも、限られた提示から「懸念や否定的な意見は見られません」と述べるsummaryは全資料の研究結論として承認しない。
- 同じ結果batch・原文・現在見解・catalog・schema・systemで、処理済み初期報告を両側から除いて管理情報だけを比較すると、template入力は7,778→5,238token、**32.7%減**。追加推論0、コピーDB不変。[管理情報の計測](../../../output/model-context-plan-16k/metadata-only-count-comparison-v19.json)。初期報告の省略も含む比較は26,003→5,238token、79.9%減だったが、この値を管理情報だけの削減率にしない。[先行比較](../../../output/model-context-plan-16k/metadata-count-comparison-v19.json)。単一packetの比較であり、全runの総token・処理時間が同率で減ったという意味ではない。
- v19の16K全体試験は1358.45秒、AI68回・コード3件、初期42ページで各AI役割へ323/323発話を提示し、専門家の序数尺度2件を出力した。Core23回を採用した後、24回目の3200token出力上限で`recovery_required`となり全体判定はfailed。[全体結果](../../../output/model-context-plan-16k/20261005T121254Z-d141cdaf/result.json)、[回ごとの作業](../../../output/model-context-plan-16k/20261005T121254Z-d141cdaf/rounds.md)、[完全な採否・根拠・予算と整合性検査](../../../output/model-context-plan-16k/20261005T121254Z-d141cdaf/verification.json)。全役割の所有発話は非重複、全packetの入力＋schema＋出力予約＋余裕は実枠以下、結果hash・manifest hash・リンク・元source stamp・SQLite quick_checkは一致、同じ保存結果の二重評価は0だった。実行版のソースは同試験の`code-v19`へ保存し、試験reportの4ファイルhashと一致した。
- 尺度下書き`def_001`/`def_002`は、`missing_rule=null_with_reason`としながらlevel 1に「未読・欠測」を入れ、「マーラタンを食べる理由がない」「根付かない」を高評価として扱っている。この矛盾を研究用尺度として不合格とした。AI下書きの構文合格であり、人が確認した尺度・発話への数値付与・研究上の解釈を確定したものではない。
- v20では主張以外の批判・尺度要求の根拠も取得する修正を追加。停止後の単発packetはまだ3200token出力上限で不合格だった。[v20記録](../../../output/model-context-plan-16k/critic-source-hydration-v20.json)。最終v21は出力予約を結果数・提示批判数に応じて増やし、批判応答・ラベル決定の配列上限も実提示ID数に合わせた。停止した24回目の場面を**読取専用の新規単発packet**として実行すると、9発話・3結果・2批判応答・4主張、入力8921＋schema2840＋出力4096＋余裕512＝16,369 ≤ 16,384で契約検証成功、コピーDB hashも一致した。[v21記録](../../../output/model-context-plan-16k/core-output-reservation-v21.json)。元runは再開していない。v21の全体再試験と研究上の品質合格には読み替えない。
- 最終adapterは`core-handler-prompts-21-context-contracts`。品質合格前なので既定`model_context_version=0`を維持する。P4の役割別品質認定、cloud計測、料金・サイズからの自動モデル割当、一般検索cache、32K実推論比較、UIの新規検証、本番Pack承認・自動選択、v21全体再試験は今回未完了または未実行。次は尺度の欠測・方向・重複水準を専門家レビューで検証し、合格した役割・モデル構成で全体試験する。
- 原本DBと研究者所有Vaultは読取のみ。試験DBを`output`内に分離し、実Vaultへの公開、Drive更新、commit/push、クラウド配置は行っていない。実験で自分がロードした`qwen/qwen3-context-plan-16k-test`だけを終了時にアンロードした。Python compile、対象文書のローカル参照25件、UTF-8、`git diff --check`も成功。最終追記の参照と差分を再確認して受け渡す。

## 2026-10-05 Windows: ???????????????

- ???????????????????????????????Handler????????Core??????Handler?????????????main/75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b???????????4?????/????/????/????3????????????6??? ? initial_analysis_report ? Core?initial_routing ? ????label-design-v1 ? ??Core???????????iteration=0???????????Core???????????SQL?????run????????
- ??v11??AI???????????????????/???claims?????????codes???????????????????????????v12???/???????claims???????????????????????????????????????????????????????????????????????????????
- ??adapter?core-handler-prompts-12-initial-evidence???9?????162 unittest???37.891???DOM28?????????/????????????1????2.257???Python compile/JS syntax/git diff --check????????????????????????????????????????????????????????????????????
- ?????: output/malatang-initial-specialists/20261005T091842Z-70c6bdb6?run_f6eb195fce2f47e0bee69b6bf397ad39?????GPT-OSS-20B/32K??323???????AI???48???275??????????????323???????????3??/????5????????????codes??323????????????1???????????/hash/??????Core???????????????????????????????????????5????AI?????????????1??????????????????7???????????????????
- ???????????????????????failed??AI10???/???3?/????Core3??590.84??Core???claims=0????result_assessments?7/1/1??????????????????????3????????????????????1?????no_new_tasks??????????????????????????????????????????????????????????/????/??????????????
- ??source stamp???????????hash????????hash????????????/??/????JSON?Markdown/verification.json????????????????????AI??????Vault???skipped????????????????????????????????????????????/?Vault??????AI???Git commit/push?Drive????????????ADR-125???20-Modules/analysis-orchestration?
