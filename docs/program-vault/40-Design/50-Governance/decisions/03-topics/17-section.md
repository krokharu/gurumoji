---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-17
title: 設計判断の記録（ADR）：ADR-123 保存済み分析の読取専用投影と追記監査、設計記録後のスライド出力
summary: ADR-123 保存済み分析の読取専用投影と追記監査、設計記録後のスライド出力。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 527
- 591
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-123 保存済み分析の読取専用投影と追記監査、設計記録後のスライド出力

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

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
- 詳細: [[40-Design/10-Analysis/analysis-history-viewer|analysis-history-viewer]]、[[40-Design/60-Output/slide-generation-design-and-prompts/00-Index|slide-generation-design-and-prompts]]。検証結果は[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index|dot-cloud-development-handoff]]


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
- 関連: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]、[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]。元DB・研究者Vaultの書換え、移行、Drive送信、commit/pushはない。

### Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）

- 状態: ローカル実装。v22〜24の入力・応答上限での失敗を保存し、Downloads系列の参照文脈のv25で再試験中。基点`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、既存未コミット変更を保持。
- 判断: 新規runは`specialist_orchestration_version=1`を既定にする。専門オーケストレータが解釈・検証・批判・数量・尺度の分野別に採否と追加案を返す。Handlerが予算内の束を選び、保存済み結果・来歴・依存を管理して直接発注する。Coreは初回の担当指示、分野間の統合、終了案を返す。
- 判断: 尺度は会話解釈専門家が作成し、Core統合前に独立した批判者が欠測・方向・尺度水準を検証する。尺度の指摘は尺度自身の対象版に紐付け、Coreの見解更新で旧版扱いにしない。応答した批判を自動的に解決済みとしない。
- 判断: 専門側の分割査定はCoreの反復回数へ加算せず、AIお任せで最低3回を強制しない。新しい報告IDだけを進展とせず、元結果の対象版・範囲・内容hashを比較する。元の問いと同一または文字列の近い追加案を保留し、同じ固定入力の全件集計は再利用する。文字列の類似度は意味同一性の完全な判定ではない。
- 判断: 各AI呼出しはsystem指示・userの対象データ・出力schemaを同じリクエストに送る。モデルがVaultやスキルを自分で読むagent tool経路や、送信済み指示のアプリ側キャッシュを実装したとは扱わない。初期原文はページ分割し、追加分析へ完了済みの全初期報告・過去結果を渡さない。Coreへは追跡可能な分野報告を渡し、未読の原結果を読了扱いにしない。
- 互換性: 新しいrole/phase/prompt版を固定し、旧版の未完runを黙って再開しない。明示的な旧経路`specialist_orchestration_version=0`と保存履歴を保持する。DBは既存JSONを使い、カラムの削除・型変更、元DBや研究者Vaultの書換えはない。
- 詳細と検証: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]、[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]。

### Downloads再構成・最低回数後の追記: 初回のラベル・尺度は専門エージェントが作成する（2026-10-05）

- 利用者指定: 初回でラベル作り（スケール/尺度）を必ず出力し、作成主体はCoreではなく専門エージェントとする。
- 最初のCore実行前に、既存の会話解釈専門担当へ専用`label-design-v1`タスクを必須発注する。空/不正な定義は隔離して停止し、初回を成功扱いにしない。保存結果のhashと作成主体を検証してCoreへ渡し、中断後も同じ生成を繰り返さない。
- 定義は根拠・判定基準・尺度水準・欠測規則付きのAI下書き。既存ラベルやコードブックの確定・統計実行とは分け、Coreは専門家結果の採否/統合を担当する。既存履歴に定義を補作しない。現行契約と出力経路は[[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]。
- 実データ試験で入力枠超過、根拠IDの誤写、型と尺度値の不一致、欠測の通常値化、空の追加理由を確認した。現在は`core-handler-prompts-10-complete-intents`で、AIへ渡す重複メタデータを省き、実在参照と型別生成・空文字禁止をschemaにも適用する。保存の全量根拠/hashと既存採用検証を維持する。初回順序尺度は数値符号と各値の意味を出力し、科学的な妥当性の確定とは分ける。モデルの不正回答を事後書換えして採用しない。

### Downloads再構成・最低回数後の追記: 初回に全担当へ依頼し、尺度要件を集約して担当指示する（2026-10-05）

- 利用者指定: 初回の分析を全分析担当へ依頼し、ラベル/尺度が必要な分析をHandlerへ報告、集約してCoreが担当への指示をHandlerへ返す。
- 判断: 既存の会話解釈・数量統計・独立検証・批判者を初回から起動する。独立な原文確認と既存3コード手法の全6タスクを保存し、AI担当は分析用途・必要概念・理由・根拠を`label_requirements`として報告する。不要な担当は空配列を明示する。全担当の成功・hash・版を確認するまでCoreの担当指示へ進まない。
- 判断: Handlerは原結果の出所を保持した`initial_analysis_report`をCoreへ渡す。Coreの`initial_routing`は発注先と具体的な問い・採用基準を指示し、Handlerが既存の尺度設計専門担当へ正式発注する。Coreは尺度を自作せず、担当指示を1回目の統合や反復成功へ加算しない。尺度のAI下書き保存後に1回目の結果統合へ進む。
- 判断: 保存・再開・予算上限・取消・重複防止は既存台帳を使う。独立検証へ他の担当/Coreの結果を渡さず、初回予備分析で採用ラベルを変更しない。実行可能な新規尺度の自動登録や未実装の統計を追加しない。
- 互換性: prompt版は`core-handler-prompts-11-initial-specialists`。新規実providerでは新契約を固定する。SQL列変更/旧runの後付け変更/実データ移行なし。旧provider版の再開は既存guardで拒否する。検証と実データ上の限界は[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]に記録する。

### Downloads再構成・最低回数後の追記: 同じ回答を最低回数に加算しない（2026-10-05）

- 背景: 実AI成功runのCore3回が完全一致し、独立検証の24主張を後続判断へ反映した根拠もなかった。利用者から同じ内容を繰り返さないよう修正依頼を受けた。
- 判断: 新しいadapter契約`core-handler-prompts-5-progress`は、要約だけの変更・claim ID・配列順で進展を作らず、根拠付き主張・代替説明・未解決点・具体的な作業案と過去の判断を比較する。同じ状態への循環は最低3回より優先して`no_progress`で停止する。試行回数と採用判断数を分け、停止した部分結果を分析完了や自動公開にしない。
- 判断: 独立検証等の未評価結果をCoreへ明示し、各result IDの採否・理由・結論への影響を保存する。結果を無視した応答は隔離し`unreviewed_results`で停止する。同じ役割・入力/ラベル版・対象範囲で原結果hashも同じなら、新result IDだけでは新しい検討根拠としない。結論を保った再検討でも、実際に異なる結果/レビュー対象への採否は進展になり得る。
- 互換性/限界: DB列・封印済み成果物・旧runの条件や成功判定は変更しない。既存のadapter版不一致時の再開拒否を維持する。意味の等しいあらゆる言い換えの検出や、結果への採否理由の研究上の妥当性は保証しない。合成試験/ブラウザーの受入と実AIでの再分析は区別する。検証は[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]へ記録する。
