---
note_id: "ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns"
note_type: "research-reference"
title: "Gurumoji の研究作業に使う公式 UI 参照パターン"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji の研究作業に使う公式 UI 参照パターン

調査日: 2026-10-02 UTC（2026-10-03 JST）  
対象: 原音 → 文字起こし → コード／テーマ候補 → 根拠確認 → 出力の往復  
前提資料: [現行監査](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md)、[UX 根拠調査](ux-research.md)  
成果物の性格: 公式マニュアル・ヘルプと公式掲載画像を比較した設計提案。製品の実操作試験、性能比較、利用者テストではない。Gurumoji のアプリソースは変更していない。

## 結論

**参照すべきものは画面全体の外観より、根拠への戻り口、変更前後の境界、処理と保存の区別である。** MAXQDA、ATLAS.ti、Dovetail、Descript の4製品を、役割の異なる参照例として選んだ。

Gurumoji へ先に取り込む候補は次の5点。

1. 結果やコードから原文・原音を開き、元の結果の対象・版・位置へ戻れる契約を作る
2. 原文、既存コード、AI 提案、今回適用する差分を比較できるようにする
3. 文字修正、時間合わせ、原音の編集を別操作として明示する
4. 処理中でも別作業へ移れ、実行対象へ戻れる固定入口を残す
5. 引用だけでなく、入力版・対象範囲・時刻精度・出力の省略項目を持ち運べるようにする

特に重要な反例もある。Dovetail は本文の版履歴を提供する一方、公式資料は復元で highlight の位置が戻らないこと、再文字起こしで既存 highlight が除かれることを説明している [R12, R13]。**「履歴がある」「引用を開ける」だけでは、入力変更後の引用の正しさは保証できない。** Gurumoji の source hash・segment ID・revision・固定 run を弱めず、古い引用と現在本文の区別を維持する。

## 1 調査範囲と根拠の強さ

### 読み分け

- **M（Manual）**: 公式本文が操作や制約を説明している。ここで動作確認したという意味ではない
- **S（Screenshot）**: 公式が掲載した画像を実際に画素で閲覧した。静止状態の配置や表示だけを支持する
- **L（Live）**: 製品を実操作して確認した。本調査は全製品で **L なし**
- **D（Design inference）**: Gurumoji への適用案。効果や実装可否が確認済みではない
- **不明**: 今回の資料に十分な記載がない。「機能がない」という製品評価ではない

各出典の閲覧日は上記調査日。更新日のないページについて、検索結果の crawl 日を公開日や実装日として扱わない。ATLAS.ti はタイトルで Windows 26 と確認できた資料を使用。MAXQDA は `/help/` の現行オンラインマニュアルで、スクリーンショットの個別 build は不明。Dovetail／Descript は現行ヘルプへの redirect 先を採用し、旧ヘルプの検索要約と混在させない。

ログイン、サインアップ、実データ投入、有料機能の利用は行っていない。第三者ブログ、比較サイト、コミュニティ投稿は製品挙動の根拠に採用していない。公式の宣伝的な「高精度」「完全な透明性」も独立した実証として扱わない。

### 4製品を選んだ理由

| 製品 | この比較で担う役割 | 確認範囲 | 主要な境界 |
|---|---|---|---|
| MAXQDA | 原文と coded segment の往復、コード見直し、出典付き出力 | M、S 3枚 | Desktop の高密度作業面を Web／狭い画面へ丸ごと移さない |
| ATLAS.ti Windows 26 | 引用を独立した対象として扱うこと、マルチメディアの範囲・時刻・コメント | M、S 1枚 | 引用番号と不変 ID、推定同期と精密時刻を混同しない |
| Dovetail | highlight から証拠付き知見へ進む Web の軽い導線、AI 候補の承認、版・出力制約 | M | 参照したhero画像は取得不可。外観や実操作の良否は判定しない |
| Descript | 文字修正とメディア編集の分離、音声と語の alignment、処理／sync の区別 | M | 映像編集向け操作を研究原本の修正に転用しない |

NVivo も初期探索したが、今回取得した playback／framework matrix の公式ページは 12／20 系だった [R22, R23]。現在版の同一機能を確認せず並列比較に入れるのを避け、今回は上の4製品に絞った。NVivo が劣る、機能を持たない、という判断ではない。Otter の追加調査は、Descript で必要な文字修正・音声同期の反例が得られたため行っていない。

## 2 作業を横断した比較

表内は特記がなければ **M**。製品間の優劣や使いやすさの得点ではない。

| 観点 | MAXQDA | ATLAS.ti | Dovetail | Descript |
|---|---|---|---|---|
| 選択を作業対象として残す | coded segment を取得一覧で扱う [R03] | quotation に ID・位置・名称・comment [R08, R10] | 選択から highlight、後から tag を付与 [R11] | script の選択がメディア編集範囲にもなる [R20] |
| 原文・原音への移動 | 出典を選ぶと元文書と該当範囲、時刻から再生 [R01, R03] | quotation の文脈再生、timestamp による同期 [R08, R09] | sidebar の highlight から本文へ移動、回答内の出典 preview [R11, R14] | 語と波形の alignment を wordbar で調整 [R18] |
| confidence と来歴 | 生成設定 memo、既存／提案／一致を区別 [R04, R06] | 時刻精度と推定同期の制約を明記 [R09] | AI 提案の承認／却下、AI 編集者の版帰属 [R11, R12] | 灰点線は再alignment中、赤下線はalignment問題の例 [R16, R17] |
| 長時間処理 | ジョブ数の入口と完了通知。別作業を続けられる [R04] | AI Coding 中に別作業が可能 [R07] | 処理中に離脱可能。clip出力準備の進捗を別表示 [R12, R15] | upload／処理の後に文字起こし。別途sync表示 [R17, R19] |
| コードとレビュー | 原文＋既存＋提案、適用前の追加／削除件数 [R06] | 候補の分類と引用を確認して Apply [R07] | AI highlight の Suggest／On／Off と承認・却下 [R11] | この資料集合では研究コードブックの review は不明 |
| 空・失敗・復旧 | 失敗時に既成 transcript の backup を確認する案内 [R05] | 今回の資料で失敗画面・空状態は不明 | codec不適合／音声trackなし等を切り分け [R12] | 未開始／stuck／misalignment／部分欠落を分けて案内 [R17] |
| 初学者と反復操作 | 文字だけの編集／聞きながら編集、基本再生＋詳細設定 [R02] | ボタンとshortcutの範囲作成、一覧の列／表示切替 [R08, R10] | 文脈actionからhighlight、後から整理 [R11] | 単語修正と継続Correct modeを併用 [R16] |
| 証拠を外へ渡す | 出典付きcopy、出力する属性を選択 [R21] | quotation reportの内容を選べる [R10] | VTT／CSV／PDF／clipで保存情報が異なる [R15] | 本文注記の出力とalignment付き字幕を扱う [R18, R20] |

### 「選択が残る」の4段階を混同しない

1. **一時選択**: マウスやキーボードで今選んだ範囲
2. **保存された抜粋**: quotation／highlight／coded segment として後で開ける範囲
3. **閲覧位置の復帰**: 根拠を開いて戻ると、同じ filter・並び・scroll・focus が戻ること
4. **版を越えた整合性**: 本文修正や再生成後も、元の版の引用と現在版を正しく識別すること

今回、2の公式記述は複数製品で得たが、3の完全な復帰契約や4の全条件を実証してはいない。Gurumoji の監査 F2/F5 に必要なのは2だけでなく3と4であり、ここを競合画面の見た目から補完しない。

## 3 採用する原則

以下の「採用」は設計原則の候補であり、実装済み・利用者検証済みという意味ではない。

### A01 根拠を開くときに対象と戻り先を保つ

**観察**: MAXQDA の取得一覧には segment の出典があり、原文の該当範囲へ移る。公式画像でも抜粋と出典位置が近い [R03, S01]。Dovetail の回答には展開式の出典 preview があると説明される [R14]。

**Gurumoji の案 D**: 結果の直近に「引用を見る」を置く。開いた根拠には dataset、表示 run、入力 revision、segment ID、話者、時刻を添える。閉じる／戻る際は結果内の位置と focus を戻す。音声確認の後も選択引用を保持する。

**理由**: 監査 F2 が求める往復を、文書名の暗記やタブ再探索に依存させない。来歴が違う場合に、現在本文へ無言で移動しない。

**受入**: 過去run→根拠→前後の音声→戻るで同じ結果へ復帰する。元segment削除・音声なし・現在版変更も含め、誤った再生リンクを作らない。

### A02 計算結果と採用する変更を別にする

**観察**: MAXQDA は既存コードと AI 提案を同じ行で示し、選んだ追加／削除の数を Apply に表示する [R06, S03]。ATLAS.ti も AI Coding の候補と引用を確認した後に Apply と説明する [R07]。

**Gurumoji の案 D**: 「処理が完了」と「研究者が採用」を別状態にする。測定は DG-02 の「定義→少数試行→確認→採用→全件実行」を守る。コード提案を実装する場合は原文・既存・提案・保留・選択差分を読み比べられるようにし、「追加3件／削除1件」など対象を示す。

**理由**: 試行が成功しただけで測定の意味まで採用されたことにしない。件数には「発話数」「コード付与数」など単位を必ず付ける。

**受入**: 全件選択→個別解除→適用前取消で研究者の既存編集が変わらない。表示filterだけなのか全候補なのか、一括対象を誤認しない。

### A03 処理の居場所を残す

**観察**: MAXQDA は実行数の入口と完了通知、Descript は別のsync進行表示を説明している [R04, R19]。

**Gurumoji の案 D**: 既存M0〜M7の永続pipelineを使い、job IDと対象を持つ短い状態入口を残す。本文編集を続けていても、完了通知で編集対象を置き換えない。実行、結果の保存、Vaultへの書出し、研究者確認を別々に示す。

**理由**: 監査 DG-03/11 と F4 に直結する。8段階の完了数を実処理時間の百分率と誤認させない。

**受入**: 実行中に別datasetへ移動し、元jobへ戻れる。計算完了＋公開失敗では保存済み成果を開け、公開だけを再試行できる。通信断を処理失敗と断定しない。

### A04 出力の範囲と失われる情報を先に見せる

**観察**: MAXQDA は出典や付加情報を出力設定に持つ [R21]。Dovetail は形式ごとに保持できる情報と制約が異なることを明記する [R15]。

**Gurumoji の案 D**: 現在filterか固定runかを出力前に表示する。「本文・時刻・話者・コード・ノート・来歴」のうち含まれるものを要約し、含まれない重要情報を示す。出力packageに入力版、対象集合、除外、設定、算出時刻を残す。

**理由**: ファイルを作れたことと、研究結果を再現可能に渡せたことは異なる。現行通常分析のExcel出力とpipeline固定packageの形式制約も区別する。

**受入**: filter後の件数、引用、分母がpreviewと出力で一致する。生成失敗をdownload済みと表示しない。

## 4 条件を変えて取り込むパターン

### B01 コード付け前の重要箇所の保留

**参照 M**: ATLAS.ti は引用範囲を先に作って後からコードを付けることを説明し、Dovetail はtagを必須にしないhighlightを扱う [R08, R11]。

**適応 D**: Gurumoji の既存メモ・確認状態で重要箇所を保留できるかを先に確認する。新しい保存対象を増やす場合は「重要箇所」「コード候補」「根拠として採用」を区別する。すべての選択を自動的に根拠として保存しない。

**未検証仮説**: 分類が未定のまま読み進める負担を減らす一方、保留項目が増えすぎる可能性がある。保留から定義・コードへ戻るタスクで評価する。

### B02 本文を中心に必要時だけ根拠paneを開く

**参照 M/S**: MAXQDA は取得segmentと補助column、ATLAS.ti は引用一覧・codes・commentという分担を持つ [R03, R10, S01]。

**適応 D**: 常時3〜4paneを再現しない。まず結果と根拠の2面で試し、狭い画面では根拠の全幅画面へ切り替える。開いた際に親の対象・版の要約と戻り操作を残す。熟練者の固定pane化は比較検証後に判断する。

**未検証仮説**: 文脈保持と本文可読性を両立できるかは、長い日本語・多数話者・200%拡大で確かめる。競合のdesktop画像は最適な列数の実験証拠ではない。

### B03 再生位置と編集選択を区別する

**参照 M**: ATLAS.ti は再生に同期した範囲強調とカーソル移動によるseekを説明する [R09]。MAXQDA は時刻columnとplaybarを近接させる [R01, S02]。

**適応 D**: Gurumoji では再生中の発話、編集している発話、保存した引用を別の表示にする。追従スクロールを止めたことが分かり、再生位置へ戻れる操作を置く案を試す。再生によって研究者の範囲選択を奪わない。

**未検証仮説**: 自動追従を常時有効にするより、長い修正中の位置喪失が減るか。正しい原音への到達と編集誤りを測り、単なるクリック数の減少で決めない。

### B04 詳細な時間合わせを必要時に開く

**参照 M**: Descript は語の境界を波形上で修正する操作を示すが、通常の語のdragにはメディアの長さを変える意味もある [R18]。

**適応 D**: Gurumoji の通常操作は発話単位の再生・巻戻し・時刻確認に絞る。詳細alignment編集が実装可能な場合だけ別の編集状態で開き、原音を変える操作と分ける。現在発話粒度しかないなら、語単位の精密さをUIで装わない。

**未検証仮説**: 時間境界を調整する必要頻度は不明。観察した研究者の困難がないまま、波形エディターを主要画面へ追加しない。

### B05 ショートカットと見える操作の併存

**参照 M**: MAXQDA、ATLAS.ti、Descript は再生・範囲作成・修正のボタンとshortcutを示す [R02, R08, R16]。

**適応 D**: 初学者には文字付きの主要操作、反復利用者には同じ処理を呼ぶshortcutを用意する。IME変換中や本文入力中は文字キーshortcutが編集を奪わないようにする。主要な理由・エラーをhoverだけに置かない。

**未検証仮説**: 英語環境のkeybindingの移植可能性は不明。日本語IME、JIS配列、キーボードのみで代表タスクを行う。

## 5 そのまま採用しないもの

| 参照・誤解しやすい点 | 不採用とする理由 | Gurumoji の代案 |
|---|---|---|
| Descript の文字削除がcompositionのメディア削除にもなる操作 [R20] | 研究原本の校正と編集動画作成は目的が違う。Descript は非破壊編集と説明しており、元ファイル永久削除だとは主張しない | 通常の文字修正では原音を変えない。除外は明示的な分析操作にする |
| ATLAS.ti のtimestampなしの推定同期 [R09] を精密な引用時刻として見せる | 文書長からの推定では正確な発話範囲を保証できない | 推定・未検証を表示し、必要なら原音全体への入口だけ残す |
| MAXQDA の緑のmatching表示 [R06, S03] を人の確認済みと読む | 既存コードとの一致は解釈の正しさを検証したものではない | 「既存と一致」と「研究者確認済み」を別ラベルにする |
| Dovetail の再生成／版復元を安全な引用移行の雛形にする [R12, R13] | highlightの削除・位置collapseという明示された境界がある | 旧runを保持し、引用版を提示。移行が不確実なら要再確認にする |
| 競合のクラウド離脱可能性 [R04, R12] をローカル処理にも約束する | 実行場所とサーバーの寿命が違う | 実行先別に「タブを閉じても継続」「端末終了で停止」等を検証して表示 |
| 競合の生成理由やconfidence風の色を正しさの根拠にする | 説明と独立した証拠は別。今回、校正済みの確率表示を採用できる証拠は得ていない | 原音・原文・反例へ戻る導線を優先。候補・人の確認・機械状態を分ける |
| 任意の範囲選択を直ちに保存する既定 [R08] | 再生箇所確認と分析引用作成が混ざり、意図しない項目が増え得る | 「この範囲を再生」「引用として保持」「コードを付ける」の意味を分ける |

confidenceを各製品が「持っていない」とは結論しない。今回読んだ特定のページは、そのUIでの校正済み信頼度を比較するための十分な証拠を提供していない、という限定的な判断である。

## 6 空状態と復旧を作業別に定義する

公式ヘルプの復旧案内は、実際のエラー画面の文言・入力保持・focus管理を証明しない。以下は競合の故障分類 [R05, R12, R17] と現行監査を踏まえた **Gurumoji独自の仕様候補 D**。

| 状態 | 表示すべき意味 | 次の操作 | 保持するもの |
|---|---|---|---|
| 取込前 | まだ原資料がない | ファイルを選ぶ | 設定の下書き |
| 未実行 | 原資料はあるが対象処理をしていない | 実行内容・実行先を確認 | 原文と手動編集 |
| filter 0件 | 条件に合う保存済み項目がない | 条件を緩める／解除する | 現在の条件を可視で残す |
| mediaはあるが音声trackなし | transcriptを生成する入力が不足 | 入力確認／別ファイル | 元ファイル情報、診断結果 |
| 処理受付／待機 | 実行は要求済み、処理開始とは別 | 状態を見る／対応可能なら取消 | job ID、対象、要求時刻 |
| 接続が不明 | 最終観測以降の進行が分からない | 再接続／状態再取得 | 最終確認時刻と保存済み成果 |
| 部分完了 | 利用可能な成果と失敗箇所がある | 成果を見る／失敗だけ再試行 | 既成成果、手動追記 |
| alignment不整合 | 本文と音声位置が一致しない可能性 | 原音確認／境界修正 | 元本文・元の時刻、変更差分 |
| 入力変更後 | 旧版には根拠があるが現在版との対応未確認 | 旧版を見る／照合する | 古い引用とrunの来歴 |
| 公開失敗 | 計算・保存と外部書出しの結果が異なる | 保存成果を開く／公開だけ再試行 | 固定runと成果物 |

画面を空にして「もう一度実行」だけを置かない。原因が異なる状態を同じ赤エラーへまとめず、逆に未確認を緑の成功へ含めない。

## 7 最小の試作単位と未検証仮説

この調査によるアプリ改修は行っていない。次に試すなら、機能追加や全面レイアウト変更より、現在の保護を使った狭い比較を優先する。

| ID | 変更する一点 | 成功を判断する観察 | 失敗・撤回条件 |
|---|---|---|---|
| H01 | 根拠pane＋復帰情報 | 結果→原音→戻るを正しいrunで完了、位置喪失が減る | paneが本文やfocusを隠す、旧版と現在版を混同 |
| H02 | 提案と適用差分の分離 | 意図的な誤提案を採用前に発見、既存編集を保持 | checkbox操作だけ増え、誤採用が減らない |
| H03 | 処理・保存・確認の短い別表示 | 公開だけ失敗した状態を正しく説明し復旧できる | 状態ラベルが多すぎて次の操作を選べない |
| H04 | 選択と再生追従の分離 | 長文修正中に選択が保たれ、再生位置へ戻れる | 現在どこが再生されているか分からなくなる |
| H05 | 原文近くの限定再生・巻戻し | 誤変換／話者誤りの検出と修正が改善 | 再生制限で前後文脈を聞かず誤解する |
| H06 | 出力範囲と来歴の要約 | previewとファイルの対象・引用元を照合できる | 形式選択時だけ説明し、実ファイルが欠ける |

合成fixtureは、同名話者・短い相槌・重なり・音声なし・古い引用・本文再編集・filter 0件・部分失敗・公開だけ失敗を含める。初学者と経験者は別に観察し、時間短縮だけでなく誤りの残存・取り消し・根拠確認・日本語IME・focus復帰を確認する。手法上の解釈の妥当性を「AIと一致した件数」では測らない。

## 8 公式画像の画素確認記録

画像は比較研究のため一時取得して閲覧した。アプリ、mockup、出力画面へ画像・ロゴ・UI部品を取り込んでいない。下記は原掲載先と原画像へのリンクであり、競合の視覚資産をGurumojiに複製する指示ではない。

| ID | 実際に確認した静止表示 | 原掲載ページと原画像 | 画像から判断できないこと |
|---|---|---|---|
| S01 | 抜粋の下に文書名・位置・コード、上に対象件数 | [R03本文](https://www.maxqda.com/help/segment-retrieval/the-retrieved-segments-window)／[原PNG](https://www.maxqda.com/wp/wp-content/uploads/sites/2/13-EN-ListRetrievedSegments.png) | クリック後のfocus、戻る操作、狭幅 |
| S02 | 本文左の時刻column、下部playbar、code範囲のmargin | [R01本文](https://www.maxqda.com/help/transcription-audio-video/timestamps-to-link-transcripts-with-sound)／[原PNG](https://www.maxqda.com/wp/wp-content/uploads/sites/2/09-EN-Timestamps-In-Document-Browser.png) | 再生中の追従、編集との競合。青い大きな矢印はマニュアル注釈 |
| S03 | 原文・既存・AI提案の4列、未選択checkbox、緑の一致、理由tooltip、無効に見える適用button | [R06本文](https://www.maxqda.com/help/ai-assist/ai-coding/ai-coding-segments)／[原PNG](https://www.maxqda.com/wp/wp-content/uploads/sites/2/31-EN-Survey-AICoding-Suggestions.png) | 適用の実挙動。英語ページ内だが画像UIはドイツ語。色の意味は本文と照合した |
| S04 | 動画、波形、時間に対応する複数の引用帯とcode label | [R08本文](https://manuals.atlasti.com/Win/en/manual/Multimedia/MultimediaWorkingWith.html)／[原PNG](https://manuals.atlasti.com/Win/en/manual/Multimedia/Images/W_CodedVideo.png) | 本文編集、時間調整の精度、keyboard代替 |

取得bytesのSHA-256（再取得時の比較用。製品のbuild識別子ではない）:

- S01: `ad189c4e810cd5c3609c9c4209d4bf51ff874bce144b710a42adcd191f4b5230`
- S02: `fe8a73876ba55a35c7dd4aa9765523f9d19689bdca21be5936dc7e167be1c544`
- S03: `dd52115bc7cb35e6950d0cd9439eef95c791f6d2708532b0d0201944d4d8ce0c`
- S04: `7ee5ea74ed924ae85a07fe50917356f44dd45ea356d04eaff5a1152f21364205`

Dovetail highlightsのhero画像、Descriptのalignmentエラー画像は、公式ヘルプから辿った画像取得が403で終わった。別経路で回避していない。alt textだけから配色・密度・操作性を評価していない。MAXQDA／ATLAS.tiの画像取得で一部検索ツールのcache errorがあったが、公開の同一原画像を通常HTTPで取得して上記4枚を画素閲覧した。これらは製品のライブ画面ではない。

## 9 出典台帳

全件閲覧日: **2026-10-02 UTC**。以下は公式の原資料。Mの「更新日不明」はページ本文で明確な完全日付を確認できなかったことを表す。

| ID | 公式原資料 | 版・日付と閲覧範囲 |
|---|---|---|
| R01 | [MAXQDA Linking Transcripts with Timestamps](https://www.maxqda.com/help/transcription-audio-video/timestamps-to-link-transcripts-with-sound) | 現行オンラインマニュアル、更新日不明。時刻column、再生、時刻の順序制約。S02も確認 |
| R02 | [MAXQDA Editing and Finalizing AI-Generated Transcripts](https://www.maxqda.com/help/transcription-audio-video/automatic-transcription/edit-ai-generated-transcripts) | 更新日不明。編集mode、聞きながら修正、巻戻し、shortcut |
| R03 | [MAXQDA Retrieved Segments](https://www.maxqda.com/help/segment-retrieval/the-retrieved-segments-window) | 更新日不明。出典、範囲強調、件数、補助column。S01も確認 |
| R04 | [MAXQDA Automatic Transcription](https://www.maxqda.com/help/transcription-audio-video/automatic-transcription/transcribe-in-maxqda) | 更新日不明。ジョブ管理、完了通知、継続、生成設定memo |
| R05 | [MAXQDA The transcription process failed](https://help.maxqda.com/en/support/solutions/articles/80001150574-the-transcription-process-failed-where-can-i-find-my-transcript-) | 表示更新情報は「Fri, 11 Sep at 3:35 PM」で年は示されず。失敗時のbackup確認 |
| R06 | [MAXQDA AI Coding Segments and Survey Responses](https://www.maxqda.com/help/ai-assist/ai-coding/ai-coding-segments) | 更新日不明。既存／提案／一致、適用前選択、追加削除件数、取消。S03も確認 |
| R07 | [ATLAS.ti AI Coding](https://manuals.atlasti.com/Win/en/manual/SearchAndCode/AICoding.html) | Windows 26 manual、個別更新日不明。対象選択、送信確認、処理中継続、結果preview後Apply |
| R08 | [ATLAS.ti Working with Multimedia Data](https://manuals.atlasti.com/Win/en/manual/Multimedia/MultimediaWorkingWith.html) | Windows 26 manual。引用範囲の作成、再生、名称・comment、shortcut。S04も確認 |
| R09 | [ATLAS.ti Working with Multimedia Transcripts](https://manuals.atlasti.com/Win/en/manual/Transcription/WorkingWithMultimediaTranscripts.html) | Windows 26 manual。同期、timestamp精度、timestampなしの推定、大きな削除への注意 |
| R10 | [ATLAS.ti Quotation Manager](https://manuals.atlasti.com/Win/en/manual/Managers/ManagerForQuotations.html) | Windows 26 manual。引用ID・位置、管理pane、filter、report。IDは作成順で、renumber機能もあるため不変IDと断定しない |
| R11 | [Dovetail Highlights](https://docs.dovetail.com/help/projects/highlights) | 現行docs、更新日不明。highlight、tags、AI承認、sidebar移動。画像は未確認 |
| R12 | [Dovetail Import data to projects](https://docs.dovetail.com/help/projects/import-data-to-projects) | 現行docs、更新日不明。処理継続、失敗分類、版履歴とrestore境界。検索で得た[旧URL](https://dovetail.com/help/take-notes-and-upload-data/)からredirect |
| R13 | [Dovetail Transcribe and translate](https://docs.dovetail.com/help/projects/transcribe-and-translate) | 現行docs、更新日不明。再文字起こし時のhighlight削除、話者の修正 |
| R14 | [Dovetail Read and verify answers](https://docs.dovetail.com/help/chat/verify-answers) | 現行docs、更新日不明。出典preview、回答中のmedia、処理中表示。全回答の正しさを検証した資料ではない |
| R15 | [Dovetail Download project data](https://docs.dovetail.com/help/projects/download-project-data) | 現行docs、更新日不明。clip生成進捗、形式別保持内容、CSV・PDF・独自projectの制約 |
| R16 | [Descript Correct your transcript](https://help.descript.com/script-editing/correct-your-transcript) | 現行help、更新日不明。文字だけの訂正、単独／全件、再alignment。検索元[旧URL](https://help.descript.com/hc/en-us/articles/10119613609229-Correct-your-transcript)からredirect |
| R17 | [Descript Automatic transcription](https://help.descript.com/script-editing/automatic-transcription) | 現行help、更新日不明。upload後のtranscription、状態・欠落・alignmentの診断。検索元[旧URL](https://help.descript.com/hc/en-us/articles/10249424286477-Automatic-transcription)からredirect |
| R18 | [Descript The wordbar](https://help.descript.com/script-editing/the-wordbar) | 現行help、更新日不明。語の境界調整と語の移動の違い。画像ファイル名の日付は公開日とみなさない。検索元[旧URL](https://help.descript.com/hc/en-us/articles/10249346632717-The-wordbar)からredirect |
| R19 | [Descript Save your work to the cloud](https://help.descript.com/working-in-projects/save) | 現行help、更新日不明。sync表示、編集継続、offline編集非対応という説明 |
| R20 | [Descript Edit like a doc](https://help.descript.com/getting-started/edit-like-a-doc) | 現行help、更新日不明。scriptとcompositionの関係、非破壊性、inline note |
| R21 | [MAXQDA Export and Print Retrieved Segments](https://www.maxqda.com/help/segment-retrieval/print-export-retrieved-segments) | 更新日不明。出典付きcopy、付加情報選択、時刻／durationの推定についての注意 |
| R22 | [NVivo Play audio and video](https://help-nv.qsrinternational.com/12/win/v12.1.115-d3ea61/Content/files/play-audio-video.htm) | Windows 12系。初期探索のみ。現在版比較には未採用 |
| R23 | [NVivo Framework matrices](https://help-nv.qsrinternational.com/20/win/Content/notes/framework-matrices.htm) | Windows 20系。初期探索のみ。現在版比較には未採用 |

## 10 この比較から言えないこと

- 日本語の長時間グループインタビューで、4製品のどれが最も速い・正確・使いやすいか
- 本番製品でfilter・scroll・focus・選択が正確に復帰するか
- 競合のkeyboard／スクリーンリーダー対応、WCAG適合、狭幅での使いやすさ
- 競合のconfidenceの校正、AI説明の正しさ、出力された引用の完全性
- Gurumojiの現行HEADがこの提案の受入条件を満たすか

したがってこの成果物は、[現行監査](../../../50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md)の不具合件数を増やす根拠や、原25件の実GUI受入を通過させる証拠には使わない。プロトタイプの判断候補と、後続の実操作・利用者検証で確かめる問いとして利用する。
