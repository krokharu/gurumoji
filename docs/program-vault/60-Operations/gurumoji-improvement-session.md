---
note_id: ops-gurumoji-improvement-session-20261003
note_type: development-session
title: Gurumoji 改善セッション
summary: 専用ブランチの復旧根拠、作業分担、課題、検証、受け渡しを管理する。
status: current
updated: 2026-10-04
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
