---
note_id: "ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run"
note_type: "design-evidence"
title: "Gurumoji 設計プロンプト運用の質的dry-run"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji 設計プロンプト運用の質的dry-run

2026-10-02 UTC · 実装PLANの作成と文書レビュー · 対象HEAD `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`

## 1 結論

**短いbriefから必要な設計知識と現行コードへ戻り、3件の具体的な実装PLANを作れた。ただし、テンプレートだけで安全な実装が保証されるという結果ではない。** 最も重要な補足は、通常操作での入口確認、定義を採用するUIと実行時の版保証の分離、固定結果の閲覧から自動retryを呼ばないことだった。

W01は既存入口の小さい復元として計画できる。W02は画面修正だけでは完了せず、個票responseと実行境界の修正を要する。W04は既存根拠guardを保ち、固定artifactと復帰文脈を接続する。W02の保存互換、W04の固定viewerのfield対応には後続の契約レビューを残した。

成果物は本稿のレビュー済みPLANと、コピーして使える[3件のタスクbrief](../../../40-Design/ui-design-research/2026-10-02/prompt-workflow-task-briefs.md)。アプリsource、設定、DB、Vaultは変更していない。

## 2 何を実施したか

### 方法と限界

1. 指定されたprompt調査、DESIGN初稿、知識索引、実装計画を読み、W01/W02/W04だけを今回の課題に選んだ
2. 各briefにT1/T11/T6のいずれか1つと共通のT10を適用し、対象コードと隣接テストをread-onlyで照合した
3. 本稿§4〜6に実装PLANを作成した。これは同一の作成者による記述的なdry-runで、別モデルの生成結果を集計したものではない
4. §7の固定した5観点で文書を自己レビューし、§8の反証課題を当てた。第三者による盲検評価、独立した参加者、ランダム割付、反復モデル呼出しはない
5. 合同作業で更新されたW02の隔離probeを読み、実行版の不一致を「潜在」から「合成adapterで再現済み」へ同期した。実ディスク保存/GUI確認済みへは拡大していない

**実行しなかったもの:** アプリ起動、UI操作、テストスイート、probeの再実行、モデル生成比較、実モデル品質評価、利用者調査、AT、Windows GUI、外部API、私有データ/認証へのアクセス、source編集。採点はPLANの記述の充足を示し、ソフトウェアの合格率、モデルの成績、生産性改善率を示さない。

今回のshell操作は対象文書/コードの読取、Git HEAD/差分確認、依頼されたMarkdown成果物の作成/参照検査。既存probeの報告を引用するときは「既存probe」と明記する。列挙した受入ケースはすべて**将来実行する計画**。

### テンプレートの位置付け

採用したT1/T6/T10/T11は[prompt-research.md §6](../../../40-Design/ui-design-research/2026-10-02/prompt-research.md#6-再利用できる依頼テンプレート)で公開した本スプリント独自のテンプレート。公式ベンダーの文面ではない。資料に記録されたOpenAI/Claude Code/Figma等の一次資料から「対象を絞る、現行を読む、検証可能な条件を渡す」を採用した。今回は外部サイトを再取得していない。T7は実装権限を要求するため使わず、実装手順のPLANを出すに留めた。

### 読取入口

- [知識索引](../../../40-Design/ui-design-knowledge.md): 対象W/DG/Sと根拠への案内
- [DESIGN初稿](../../../40-Design/ui-design-contract.md)§3/5/7: 守る契約、定義/根拠/状態、検証層
- [実装計画](../../../40-Design/ui-design-implementation-plan.md)W01/W02/W04/W09: 対象、依存、rollback
- [シナリオ](../../ui-design-scenarios.md)S01/S02/S04と[受入方法](../../ui-design-acceptance.md): 操作単位と証拠の限界
- appの[AGENTS.md](../../../../../AGENTS.md)、関連source/隣接test: 現行実装の正本。runtimeや移入研究Vaultは参照しない

## 3 コード照合で固定した事実

以下のpathは`app/`からの相対パス。行番号は上記HEAD時点での読取位置。

| ID | 確認した契約/不整合 | 読取根拠 |
|---|---|---|
| C01 | 個別実行/取消controlをCSSが隠す。API廃止を意味しない | `src/gurumoji/static/style.css:2088–2093`、`analysis-content.js:184–188,561–568`、`analysis-method-view.js:254–264` |
| C02 | 見解はoverview、Transformer/分類はcontent。説明は両者をcontentへ案内する | `static/app.js:6760–6769`、`templates/index.html:236` |
| C03 | Transformer/見解はdirty/実行中guardとrevision/request_idを持つ。分類は別handlerとPOST | `analysis-content.js:910–944,1156–1192`、`analysis-method-view.js:312–347`。分類に同じ取消能力があると推定しない |
| C04 | 基礎pipelineの能力と個別分析は同一でない | `analysis_core.py:80–105,311–338`。基礎pipelineのM0〜M7は存在し、全LLM役割/全手法ではない |
| C05 | 表示されない測定fieldのfallbackはtext/text_length/number/ratio/descriptive。試行後に自動adoptする | `templates/index.html:243–249`、`analysis-execution.js:50–64,542–557` |
| C06 | 定義PUTは同IDの行を更新しrevisionを増やす。trialはinput_hash/件数/有効valuesを返すが個票と定義revisionを落とす | `analysis_pipeline.py:229–280`。取消時の逆PUTは履歴復旧にならない |
| C07 | 名義/順序のdescriptive、durationの列/型などをvalidatorが制約する | `analysis_core.py:151–198`。自然文から任意の尺度を作る能力ではない |
| C08 | startはplan/binding/input snapshotを保存するが、workerはdefinition IDから現行payloadを再読する | `analysis_pipeline.py:332–389,635–644`、[既存lifecycle probe](definition-lifecycle-probe.json)、[既存M0〜M7 probe](definition-full-pipeline-probe.json) |
| C09 | 根拠detailsと音声前の本文/話者/時刻比較は既にある。戻りstateはmode/scope/speaker/scroll等で、完全な固定run/page/filter/focus一式の保証はない | `analysis-content.js:45–127`。機構全体を新規未実装と扱わない |
| C10 | run履歴にartifact URLがあり、artifact読取はhash照合を行う。現行「結果」buttonは現在itemの読込へつながる | `analysis_store.py:304–321`、`analysis-storage.js:43–69`、`analysis-execution.js:651–655` |
| C11 | pipeline status取得はinterrupted/waiting条件でretryを起こし得る | `analysis_pipeline.py:752–770`。GETであることだけをread-onlyの証明にしない |
| C12 | content試験にはDOMの直接clickがあり、Transformer fixtureにはproduction CSSがない | `tests/test_content_browser.py:72,147–148,184–189`、`tests/test_transformer_content_browser.py`のfixture。既存試験の価値とV3到達証拠は別 |

C08の既存M0〜M7 probeはbinding v1に対してdefinitions v2、文字数なら3の入力がdurationで60となり、save adapterへ渡った記録を持つ。合成adapter・一時SQLiteでの記録であり、実ファイルに誤結果が保存された/利用者が遭遇したとまでは述べない。

## 4 B01にテンプレートを適用したレビュー済みPLAN

**目的:** 保存済み会話から目的の個別分析を見つけ、正しい対象と接続先で開始し、既存対応のある処理を中止し、旧結果を閲覧できる。T1で現行事実/仮説/未確認を分け、T10で証拠層を固定する。

### 最小変更と状態

1. 3種類の可視入口→既存handler→API→能力を対応付ける。テーマは`POST .../analysis/transformer`、見解は`POST .../analysis/insights`、分類は`runSegmentClassification`→`POST .../analysis/classifications`。分類payloadの`use_jev`とrevision/request_idを確認し、基礎pipelineへ転送しない
2. C01の一括非表示のうち対象controlとtoolbarを局所修正する。既存refresh関数が持つdisabled/取消条件を保ち、全selectorを無条件に表示しない
3. 見解の案内を実際のoverviewへ合わせる。処理/対象/接続先の短い説明を実能力に合わせる。実行環境のLM Studioを常に利用者PCと呼ぶ等の説明は設定と照合する
4. ready、dirty、provider/モデル不足、starting/running、cancel requested、失敗、旧結果の各状態を既存判定元から表示する。取消はTransformer/見解の既存対応を利用する。分類に同じcancel handlerは今回の読取で確認していないため、存在しない取消を表示せず、追加が必要なら別依存にする。失敗/取消を完了扱いせず、旧結果閲覧の入口を残す
5. 1440/390pxでは同じ3作業へ到達できる配置を保つ。表示順は対象と接続先→主操作→状態→結果。Tab/Enterで通常操作、visible focus、取消後focus復帰。320px/拡大では操作と説明が隠れない

### 受入証拠の計画

- B01-A: 一覧→会話A→各分析。production CSSでpointerとkeyboardの別走行、3入口の可視矩形/名前/disabled状態、画面記録。直接click/force/hidden解除は不許可
- B01-B: 合成stub・通信spyでitem/provider/source_revision/analysis_revision/request_idと正しいrouteを照合。連打時の実行要求1回、dirty/条件不足は開始0回、保存済み閲覧は新規実行0回
- B01-C: 開始後に会話Bへ移る、遅いA response、戻る、中止/完了競合。Bのdraftと対象を保持し、取消対応のある処理の実running中のcontrolが通常操作で届く。分類も対象移動後の遅いresponseを別検査し、既存の保護が十分だと推定しない
- 隣接handler試験は残しV1/V2として活用。V3は上記の通常経路を追加。V4/Windows/V5は実施環境が得られるまでnot-run。stub成功を実モデルの品質/接続成功にしない

### データと戻し方

保存schema変更なし。既存URL/DOM data属性、revision/request_id、run履歴、ノート所有境界を維持する。CSS/案内/小さいadapterに差分を限定し、戻すときも研究者の入力/生成済みrunを削除しない。入口を戻すと再び操作不能になる場合は、その制限と旧結果閲覧を明示し「問題解決済み」を撤回する。

**今回の結果:** C01〜C04/C12の文書・コード照合のみ。B01-A/B/Cは未実行。W01計画は局所修正のレビューに進めるが、UI受入済みではない。

## 5 B02にテンプレートを適用したレビュー済みPLAN

**目的:** 研究者が秒数の測定内容を確認し、試行を見て明示採用し、受付内容と一致する計算だけを確定する。T11の「定義/試行/採用/全件」を使い、C05〜C08の現行制約を具体化する。

### 最小変更と状態

1. 既存validatorに適合する入力列・規則・型・尺度・手法を可視化する。durationはduration列/number/ratio、文字数はtext/text_length等の実契約を説明する。名称/説明は計算規則ではないと明示する
2. 既採用を編集する場合、旧IDをdraft PUTしない。別draft IDへ複製する方式を優先し、元定義との関係を画面で示す。Cancelは未採用draftを残せるが、旧採用payloadの逆PUTやdraft削除を勝手に行わない
3. 編集→試行中→レビュー待ち→明示採用→全件開始を分ける。レビュー待ちはまず画面の状態。新しい永続statusを無断追加しない。Cancel/Close/Backでadopt/pipelineを送らない
4. trialへID付き個票、欠測理由、測定に使った定義revisionを後方互換で追加する計画を別差分にする。既存values/件数/input_hashを保持し、値の配列を現在の発話順へ推測結合しない
5. 定義内容、item、入力版が変われば古いレビューを無効化する。409は入力を保持して再読込/比較を促す。draft版rと同内容adopt版r+1の対応を示し、status変更だけを別内容と混同しない
6. **実行時版保証は必須。** 受付後の定義差替え、再起動/retryでも受付と同じ定義を使う。最小対策は版/内容不一致・不明で安全停止。本対応は受付時に完全payload/版/hashを原子的に固定し、実行/再開/保存でその同一値を使う。単に開始直前に最新revisionを読むだけでは受付後raceを防がない
7. UIで研究者が採用したことと、サーバーがそのレビュー行為を永続的に保証することは別。trial ID/定義revision/input fingerprintを結ぶserver review gateは別契約レビュー。これを後回しにしても⑥は省略しない
8. 390pxでは定義要約→個票→欠測/限界→採用の順。個票の列名/単位/IDは省略しない。長い日本語label、320px/拡大、IME確定Enterで誤採用しない、Tab順、エラー欄へのfocus、Close後のfocusを計画する

### 受入証拠の計画

- B02-A: e1/e2でduration=60/2と文字数=3/10を対照にする。e3欠測理由とe4真の0秒を分離。名義尺度の平均をvalidatorが拒否し、欄へ理由が結び付く
- B02-B: trial responseの個票ID/値/理由/revision/hashを画面と照合。明示採用までadopted PUT=0、pipeline POST=0。Close/Cancel/Back、二重submit、試行後編集/別item/別ID/入力更新を通信記録で確かめる
- B02-C: 採用済みID→修正試行→取消/409の後、元のadopted payloadが同じであることを一時DBで確認する。旧定義が欠けた場合を「キャンセル成功」と表示しない
- B02-D: 受付を一時停止→別タブの定義変更→worker再開、再起動/retryを制御fixtureで再現。binding/definitions/実測値/保存packageが同じ内容か、理由付き安全停止。異なる60をv1文字数の成功結果として保存しない
- B02-E: V3で通常dialog起動から採用/全件まで通す。V1/V2成功だけでGUI合格にしない。V4実AT、Windows IME、V5単位と採用の理解は別記

### データと戻し方

trial responseの追加fieldは旧clientが読める形を保つ。定義snapshotを保存する場合は、既存保存場所と契約versionを先にレビューし、旧reader/旧待機run/rollback後の読取を一時DBでdry-runする。SQLを変えるなら追加のみ、backup/復旧を先に設計する。固定payloadのない旧待機runは一致を証明できなければ安全停止し、現在値で埋めない。完了済みrunを再計算・来歴改変しない。

未決定はsnapshotの具体的な保存field/原子的固定の境界/旧版workerへ戻した時の扱い。安全停止を先行するかsnapshotを同時導入するかで互換試験が変わるため、ここはPLANの部分充足として残す。戻し方はコード差分の撤回であり、新draft・研究者編集・新成果物の削除ではない。

**今回の結果:** コード照合と既存probeの読取のみ。B02-A〜Eは未実行。明示採用buttonを加えるだけの案は却下する。測定と宣言の一致は検証対象だが、研究の科学的妥当性を保証したとはしない。

## 6 B03にテンプレートを適用したレビュー済みPLAN

**目的:** 固定runのAI見解を根拠で確かめ、入力修正後も同じ結果の同じ文脈へ戻る。T6の往復条件とT10の証拠分離を使う。

### 最小変更と状態

1. C09の既存details、生成時snapshot、stale表示、音声前の同一性guardを出発点にする。今ある音声代替本文を保ち、全機構の作り直しを避ける
2. C10のrun/artifact URL→input.json/result.json/manifestを先に調べ、固定viewerの表示field対応を作る。run ID/入力版/生成時引用を確定できないlegacyは「来歴不明」。現在itemを開く既存処理を固定run閲覧と呼ばない
3. 固定閲覧からC11のpipeline status自動retry経路を呼ばない。既存artifact読取を優先し、不足分だけread APIの追加契約にする。GET/POSTの形式より実際のside effectを確認する
4. 既存navigationへitem/run/page/filter/selectedEvidence/scroll/focusOriginを対応付ける。使える既存stateを確認して不足だけ追加し、新しい永続session storeを先に作らない。desktop details＋mobile全幅の軽い案から始める
5. 根拠を閉じる/戻ると同じ固定runと表示文脈を復元する。focus起点が再描画で消えた場合は同じ根拠の操作名へ、存在しなければ結果見出しへ移し、その理由を仕様にする。Back/Forward、再読込、幅変更時の復帰範囲も明示する
6. 入力の本文/話者/時刻が違う引用は現在音声に黙って接続しない。生成時本文と変更理由を示す。音声なし、引用欠落でも確認可能な原文を示し、復元できないものは明示する
7. 入力修正の保存成功/失敗、旧run stale/unknown、新しい分析要求を別状態にする。保存だけで旧runを再計算しない。AI見解「全員が賛成」は主張候補であり、反対/伝聞/質問の根拠へ同じ操作で戻れるようにする
8. 1440/390/320pxで対象run、引用、戻るを常に識別できる。keyboardで開閉、focus復帰、必要なlive通知、固定要素の遮蔽、IME入力/保存を計画する。paneの広さだけを改善根拠にしない

### 受入証拠の計画

- B03-A: R1/revision1の引用を開き、現在revision2と照合。古い本文/話者/時刻を保持し、staleまたはunknownが残る。引用がないとき現在値で補完しない
- B03-B: page/filter/引用/scroll/focus起点を記録→原音/本文→入力修正/保存→戻る。通常pointer/keyboard双方で同じ結果へ戻る。保存失敗はdraftが保持され、旧runと保存済み入力の版が混ざらない
- B03-C: 固定結果を開く/閉じる/Back/Forward/再読込の通信とworker callを監視し、新規推論/retry/外部送信0回。APIがGETでも無条件に合格としない
- B03-D: 表示と既存exportのrun/hash/revision/対象集合・分母を照合。欠測/除外/未実行と0を分ける。固定packageに未提供のXLSXを追加済みと見せない
- B03-E: 合成の反対根拠を見つけられるかはV5で評価する計画。エージェントが答えを知る本稿では誤り発見率/理解向上を測定したことにしない

### データと戻し方

固定成果物はread-onlyから始め、hash検証を保つ。旧hash/引用/runに現在来歴を書き足さず、研究者メモを再生成しない。新しい復帰adapterを戻しても既存details・deep link・音声guardが働き、編集draftや履歴を消さない。固定viewerのpayload対応と再読込時にどこまで復帰するかはまだ確定しておらず、APIを増やす前に契約レビューが必要。

**今回の結果:** C09〜C11のコード照合のみ。B03-A〜Eは未実行。固定run閲覧の新規依存を隠して完成画面として扱わない。

## 7 PLANの採点とレビュー結果

### 事前の判定基準

0＝記載がない/契約違反、1＝言及はあるが対象や証拠/未決定の契約が残る、2＝具体的な対象・根拠・将来の受入証拠まで記載。これは本稿を作成したエージェントによる順序尺度の自己レビュー。点数差の統計的意味はなく、合計/平均/改善率は計算しない。

| 観点 | 2に必要な記載 | B01 | B02 | B03 |
|---|---|---:|---:|---:|
| 実repo契約 | source/能力/既存機構と変更境界、未実装依存の具体化 | 2 | 2 | 1 |
| 科学的保護 | 入力/定義/run/欠測/人の判断の該当する境界と反証fixture | 2 | 2 | 2 |
| mobile/keyboard | viewportだけでなく通常経路/狭幅/IME/復帰と証拠 | 2 | 2 | 2 |
| データ/rollback | 保存・並行更新・旧版互換・研究者編集を失わない戻し方 | 2 | 1 | 2 |
| not-runの限界 | source/probe/V1〜V5の区別と今回未実施の明示 | 2 | 2 | 2 |

- B01の2は3入口の操作/別routeと取消能力の境界を計画に含めた評価で、UIの現在の可視性が合格した意味ではない
- B02のdata=1は固定payloadの保存契約/旧worker互換の未決定による。名称と値が一致するUIだけではこの条件を解決できない
- B03のrepo=1は固定artifactからのviewer field対応と再読込復帰仕様の未確定による。既存入口へ無条件に差し込む実装承認には足りない

**相殺できない停止条件:** 別定義の値を正常確定、古い引用の現在来歴化、閲覧で推論/retryを開始、既採用/研究者編集の喪失、非表示controlの直接clickでV3合格。このいずれかが残れば他の2点で相殺しない。

### レビューで具体化したこと

| テンプレートだけでは決まらない点 | 最終PLANの扱い |
|---|---|
| T1の「現行画面とテスト」は通常の到達性まで自動で含まない | B01-Aのproduction CSS/一覧始点/通常pointer・Tab・Enter/実矩形、C12の偽合格防止 |
| T11の「定義版を確認」からtrial response不足の解決策は出ない | B02④に後方互換の個票/revision拡張。現在の発話順による推測禁止 |
| T11の採用確認だけでは同ID上書き/worker再読を止めない | B02②⑥、旧定義保護と受付後raceの別受入 |
| T6の「既存深いリンク」だけでは固定artifactと現在データを分けられない | B03②③、固定viewer依存とside-effect検査 |
| T10は報告分類を与えるがrollbackの仕様は与えない | 各PLANに保存/旧版互換/取消/戻し方を独立記載 |

これはテンプレートの失敗率を計測した表ではない。選択した指示を実repoへ適用すると追加確認が必要だった箇所の記録である。

## 8 反証と曖昧さへの応答

各行は**文書への挑戦条件**であり、アプリやモデルへ複数回入力した実験結果ではない。最終PLANが何を要求するかを静的に照合した。

| 挑戦条件 | 危険な解釈 | 本稿の応答/残る限界 |
|---|---|---|
| 「ボタンはある。既存testもpassだから完了」 | handler試験を可視性へ繰り上げ | C01/C12、B01-Aで棄却。production CSSと通常経路が未実行ならV3 not-run |
| 「全部のhiddenを外すだけ」 | 取消や条件不足controlの状態を壊す | B01②で局所selectorとrefresh条件を確認 |
| 「説明を秒数へ直して」 | text_lengthのまま名称だけ変える | B02-Aの60/2対3/10が区別する。UI説明変更だけでは未完了 |
| 「試行が成功したら自動採用」 | 成功を人の判断と同一視 | B02③/Bで明示操作までadopt/pipeline 0回 |
| 「取消時に以前の定義をPUTし直す」 | 別タブの更新を巻き戻す | B02②/Cで別draftと旧採用保護。逆PUTを採用しない |
| 「bindingにv1があるので再開も安全」 | workerは最新IDを読む事実を見落とす | C08とB02-Dで受付後変更・retryを必須化。安全停止か固定内容の保証を求める |
| 「GETだけなら閲覧は安全」 | status GETの自動retry | C11とB03-Cで実side effectを検査 |
| 「根拠paneを出せば戻りやすい」 | page/filter/focus、引用版が欠ける | B03④⑤/A/Bで検査。理解向上はV5未実施 |
| 「390pxの画像があるからWCAG適合」 | reflow/keyboard/AT/実背景を省略 | 共通条件とT10で320px/拡大、V3/V4を分ける。適合宣言しない |
| 「資料には潜在不整合とある」 | 同時更新前の文書を絶対視 | codeと新probeに戻り、基準hashを記録。文書差分だけでコード修正済みとしない |
| 「T7も付けたので実装してよい」 | 再利用テンプレートを権限と読む | 今回PLAN限定を優先しT7を選ばない。source編集なし |
| 全11テンプレート＋全設計資料を毎回連結 | 対象外の保存/IA/ブランド刷新を混在させる | 共通条件＋1 brief＋主template＋T10→対象W/DG/S/sourceの順で取得 |

### 長い文脈の扱い

今回の監査では指定4文書をすべて読んだが、日常の依頼に毎回同じ全量を渡すことを勧めない。文書には実装事実、提案、古い画像由来の仮説が混在するため、長さだけでなく**どの主張がどの版を示すか**が問題となる。

最小の読込順は「共通条件＋1件のbrief→DESIGNの不変条件→該当W/DG/S→関連source/test」。文献は設計理由が争点になったときだけ該当IDへ進む。T1の事実/推定/未確認は最終PLANの各主張に残す。これで読込量を減らせるという運用上の提案であり、注意低下の減少や生成品質の向上を測定した結果ではない。

最終版の単純文字数では指定4文書が合計38,813文字、共通条件とB01/B02/B03各本文はそれぞれ1,127/1,087/1,129文字。後者に必要なsource/仕様の追加読取が続くため、最終context全量の比較ではない。Unicode文字数でありtoken数・時間・品質の測定値ではない。

### 故意に曖昧な依頼

入力例: 「GurumojiをAIっぽくなくして」

このままでは対象画面、困っている操作、維持する機能、変更範囲が決まらない。具体的な確認は1問でよい。

> どの画面で、どんなところを変えたいですか。たとえば「主操作が分かりにくい」「長い日本語が読みにくい」など、困る場面を1つ教えてください

返答前に進めてよいのはread-onlyの現行確認と**仮定付きの設計案**まで。「今回は分析結果から根拠へ戻る画面を対象、緑/紙色と情報・操作を維持し、主操作の優先度と本文/補助情報の階層を検討する。コードは変更しない」と明記する。勝手に巨大heroの撤去、新フォント、React化、画面全面生成を選ばない。

T2で案を比べるなら同一内容・状態・viewportを固定し、density/一覧と詳細/根拠位置を変える。T8で「同じ強さの主操作が3つあり次の行動が不明」等の観察へ直す。ただし、その画面で実際に見ていない現象を観察事実と書かない。本稿には新規スクリーンショットがないため、具体的な見た目の欠点は未確認の仮説に留める。

## 9 テンプレートへの最小修正案

元のprompt調査は直接編集していない。以下は次版へ取り込む候補。全契約を常設文書に複製せず、短い補足と対象へのリンクにする。

### 共通の出力条件へ追加する3行

```text
実装PLANには、変えてよい責務、API/保存に必要な追加、旧版互換と入力を消さない戻し方を分けて書く。
受入ごとに開始経路/fixture/操作/期待値/証拠層を付け、未実行はnot-runとする。
関連するW/DG/Sとsourceを確認し、資料更新や未決定の契約があれば実装前gateとして残す。
```

### T1またはB01へ追加する1行

```text
入口改善はproduction CSSの通常画面からpointer/keyboardで到達を確認する計画とし、handler呼出しだけを可視操作の合格にしない。
```

### T11またはB02へ追加する2行

```text
既採用定義を修正して取消しても旧採用を失わないこと、試行個票/欠測/版が実responseで取得できることを確認する。
受付後の定義変更と再起動/retryでも採用内容と実計算を照合する。UI採用確認とサーバーの実行版保証を別条件にする。
```

### T6またはB03へ追加する1行

```text
固定run閲覧に使う読取経路の副作用を確認する。GETでもretryを起こす経路は分離し、旧来歴を現在値で補完しない。
```

足す場所は主templateまたはbriefのどちらかに決め、両方へ重複させない。T10に全実装仕様を詰め込まない。知識索引は本稿/briefへの1リンクとW02の版保証への案内で足りる。

## 10 次に必要な確認

1. B01の入口adapter案を承認した後、合成fixtureで実装しV1/V2/V3を実行する
2. B02は最小safe-stopかsnapshot導入かを決め、原子的固定と旧run/rollback契約をレビューしてから実装する
3. B03は固定artifact→viewerのfield対応表をread-onlyで完成させ、復帰範囲を明文化する

モデル比較/利用者実験を行うなら別計画と権限で実施する。今回の3件の自己レビューを、その比較の結果へ置き換えない。

## 11 文書検証記録

2026-10-02 UTCの最終read-only確認。

- 文書検査: 3 briefと3 PLANの対応を確認。ローカルMarkdownリンクはbrief 8件/本稿10件、存在しない参照0件。リンク先のS01/S02/S04見出しも確認
- source照合: C01〜C12の記載箇所を読み、HEADは記載の`ddc23abe…`、branchは`dot/cloud-cpu-setup`。appの`git status --short`は読取開始時/成果物作成後とも空
- 別担当による文書レビュー: 分類の中止能力を3分析共通に読める文言を指摘。B01 brief/PLANを修正し、既存取消対応と分類の未確認/別依存を分離。これは文書校閲で、別モデル比較や利用者評価ではない
- アプリ受入: 今回のV1/V2/V3/V4/V5はすべてnot-run。既存probe報告の読取を今回の再実行へ数えていない
- 作成範囲: 本稿と`prompt-workflow-task-briefs.md`のみ。アプリsource、Software Vault、runtime、移入Vaultへ変更なし

参照した4文書の最終検査時SHA-256。合同作業で後から文書が変わった場合、この記録より新しい版を使ったことにはならない。

| 文書 | Unicode文字数 | SHA-256 |
|---|---:|---|
| prompt-research.md | 16,633 | `82a1764145b4e6ba8b6a0cfd5a8a7a08fd9c7c70f34de01eee91b536d7c516c7` |
| draft-DESIGN.md | 6,458 | `fe0e576b6cc33f5e3fc041a290e60d2ada5397b2fdf6dc76c71c2444e33ce308` |
| agent-design-knowledge.md | 4,123 | `8672d525c12a7f988620a4ae183c1e52209dc6449a5279fd5bba6c5ba935e83d` |
| design-implementation-plan.md | 11,599 | `2a6448fa1c4b05944c7848e589610431d646e75736a49b764ac2b20ee25ebd6e` |
