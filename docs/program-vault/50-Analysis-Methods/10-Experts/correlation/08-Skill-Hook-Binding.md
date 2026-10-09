---
note_id: expert-correlation-skill-hook-binding
note_type: expert-skill-hook-binding
title: 相関の段階別スキル・hook対応案
summary: 相関の現行01・07・actor・scopeを固定し、未接続readerと不足を明示する。
status: proposed
schema_version: 1
binding_version: 6
expert_ids: [exp-correlation]
stage: registration
review_state: draft
runtime_state: planned
required_note_ids: [analysis-common-evidence-and-claims, analysis-common-source-classification, analysis-common-group-interview-data, expert-correlation-overview, expert-correlation-definition, expert-correlation-procedure, expert-correlation-quality, expert-correlation-limits, expert-correlation-cases, expert-correlation-open-issues, lit-aarts-2014-nested-data, lit-appelbaum-2018-jars-quant, lit-benjamini-hochberg-1995-fdr, lit-bishara-hittner-2012-correlation, lit-holm-1979-multiple-testing, lit-spearman-1904-rank, res-scipy-pearsonr, expert-correlation-agent-contract]
optional_note_ids: []
updated: 2026-10-08
tags: [gurumoji/skill, gurumoji/expert]
---

# 相関の段階別スキル・hook対応案

G1b-entry-02の固定提案。専門家IDは `exp-correlation`。固定初期発話の変数対と探索的な関連を計画し、正式計算表へ戻れる説明を下書きする。因果や方向を確定しない。
書式は [[90-Templates/skill-hook-binding]]、skill書式は [[90-Templates/skill-definition]]、充足・人の保留は [[50-Analysis-Methods/50-Knowledge-Evaluation/expert-stage-readiness|17専門家の充足・不足表]]。この08の作成は実行登録ではなく、G2/G4の能力登録・汎用reader・callbackは未実装として保持する。

## 目的・取得用途・固定する出典

|対象|ID・版・raw byte SHA-256／用途|
|---|---|
|01|[[50-Analysis-Methods/10-Experts/correlation/01-Expert\|専門家実行定義]] `expert-correlation-definition` D2 / `5a499ea69a38f176a1212ab52d4fe85b8237aaf80ba6fd1b5deed148a14642bb`。問い・流派・単位・許可step/actor・禁止結論の照合|
|07|[[50-Analysis-Methods/10-Experts/correlation/07-Agent-Contract\|入出力契約]] `expert-correlation-agent-contract` S2/C2 / `92c02db1e1db0f68ed2ff0febd3b5d5615149a748bf0b2a7a534dc06478bb3d2`。入力・出力型、必須phase集合・数値9キー|
|固定提案手順|[[50-Analysis-Methods/40-Skills/correlation-exploratory-evidence\|correlation-exploratory-evidence]] `correlation-exploratory-evidence` v1・proposal_revision 3 / `3d29a901c8fc64c7d0822310bb8e97e7137e661431dcd0851e25a766eb7eb2ec`。`^cee-guards` の全条件blockquote、`^cee-procedure` の同一手順（analysis_plan と result_explanation の双方）、`^cee-output` の全出力・停止条件blockquoteを固定参照。status proposed / review_state draft / runtime_state planned。文書IDの存在はruntime登録を意味しない|
|旧08 B2履歴アンカー|`5c40a0d3065f77039bad87a88eac91cbf6020d55`。過去版のbyte参照として保持し、現行固定提案手順の参照に読み替えない|
|workflow|workflow-group-interview-evidence flow1/r3 1a8ed0b31076f5ade8ddb30ca953ac00debf022a3b08b20b4544221a096a2a32|
|実装|root `0fbfb402af9d9bdd18a495565288bf5ed273d5f4`、Registry `obsidian-expert-agents-3`、hook `expert-data-hooks-3`。既存01/07 parserとHandlerを正本とする|
|開始base knowledge|`sha256:1feeff1d3ec657c7033db1aef4c99eb1edd0f9a08b2fa70331091cb2106a85f8`。個人上書き・実run採用hashではない|
|入口追記後base knowledge|`sha256:e0a6b1f867b8b88e0c1e3fb10d700f5e66004b71176ccdadc421e2187cb70fc7`。Overview入口追加による変更。旧runの固定profileへ後付けしない|
|配信方針|C0 `task_e1044a47e1e6` の `currentPack` 暫定維持。新方式 `notadopted`、b/c未測定で比較優位・実モデルready・品質合格を認定しない|


研究目的に応じた任意参照：[[50-Analysis-Methods/40-Skills/group-interview-evidence-workflow|workflow-group-interview-evidence]] `workflow-group-interview-evidence` v1/r3 / `1a8ed0b31076f5ade8ddb30ca953ac00debf022a3b08b20b4544221a096a2a32`。条件付きworkflowであり必須knowledgeではない。選択時は `^giew-procedure` 表と `^giew-procedure-guards` 注意段落を同時に必須取得し、不足はneeds_input/blocked。選択した目的で必要な枝が未充足なら当該枝のみ停止する。

^cor-sources

必要知識は前付のrequired_note_ids（既存Catalogの選択00〜06・共通・文献と07）に一致する。本文を必要用途で読む範囲は02の手順、03の品質、04の適用/限界、06の未確認、01のprocedure/basisと07。参照文献は以下の用途をまず照合し、Packの省略を全文自由取得で補わない。

|出典ID／note ID|既存確認範囲・版／raw SHA-256|参照用途と保留|
|---|---|---|
|[[50-Analysis-Methods/20-Literature/LIT-bishara-hittner-2012-correlation\|LIT-bishara-hittner-2012-correlation]] / lit-bishara-hittner-2012-correlation|abstract・2026-09-16 / `3ad59314da799d802abecf82c46f54e6ce87b8c6fd81004f635fcbf170172015`|01のbasis/quality/限界へ戻す。今回frontmatter・存在・hashのみ。文献本文の新読了、人の方法論採否、訂正状態の再確認は未実行|
|[[50-Analysis-Methods/20-Literature/LIT-appelbaum-2018-jars-quant\|LIT-appelbaum-2018-jars-quant]] / lit-appelbaum-2018-jars-quant|abstract・2026-09-16 / `d1586a3926a56887963cc2ed7778f71cd90ac0529753b067fff817e909f1dea8`|01のbasis/quality/限界へ戻す。今回frontmatter・存在・hashのみ。文献本文の新読了、人の方法論採否、訂正状態の再確認は未実行|
|[[50-Analysis-Methods/20-Literature/LIT-aarts-2014-nested-data\|LIT-aarts-2014-nested-data]] / lit-aarts-2014-nested-data|abstract・2026-09-16 / `57fa087bf420ba73fbda0e6f259731f659f5687c4229ada819dac7d4ad227702`|01のbasis/quality/限界へ戻す。今回frontmatter・存在・hashのみ。文献本文の新読了、人の方法論採否、訂正状態の再確認は未実行|

全必要sourceのmetadataは `../artifacts/obsidian-skill-plan/revision-5/g1b-entry-02/selected-source-manifest.json`（SHA-256 `c99f638317a748a2dc5cf8fb313cc9ec3f385001b6a0d1498126d337114aed67`）と充足表の固定台帳へ戻る。base/local/固定実run、raw note hash/knowledge集合hash/profile hashを分ける。研究者本文・原文・資格情報を08へ複製しない。

currentPackは各note抜粋 `min(1600, 8000 // note数)`、`omitted_characters` を残す。現行CatalogのKNOWLEDGE_NOTESは00〜06固定で08本文は送られない。今回の3 Overview入口はknowledge hashと次runの抜粋候補を変えるが、08専用reader接続にはならない。必要本文の実配信/読了は別receiptと範囲で確認する。

統計07冒頭の「schema1のみ受理」の本文はa03時点の旧説明で、指定現行Registryのschema2受理を優先する。07本文だけの狭い修正はF04と独立レビュー後のC0後続票で保留し、そこで07 raw hashが変われば08参照を別票で再束縛する。ここでは01/07 byteを変更しない。

## 段階別の対応表

表示用段階名と実行phaseを分ける。提案skill IDは固定版として存在するが、実行runtimeには未登録である。必須のskill登録はplanned、必須論理callbackは未登録blocked。今の01/07実行経路は08を利用せず存続する。

|段階|method／scope・単位|actor・許可procedure|必須／任意skill・読む知識|hook・状態|
|---|---|---|---|---|
|計画|正式tool `pearson/spearman`。固定初期発話 `all_included_initial`、初期群/変数、用途を固定|`analysis_plan`：AI cor-ai-plan。R cor-p1。K必須stepなし、未計算|必須：変数対、Pearson/Spearman種類、欠測・外れ値・同順位、因果/方向・探索性の計画/適用条件確認（未登録planned）、01/02/04、07 phase_requirements。analysis_premisesは任意string/null|task_prepare/knowledge_requested planned。callback未登録blocked。AI提案とHandler発注を分ける|
|正式計算|上のallowlistのみ、`statistical-tools-1`。任意表・後から採用したラベル・部分scope・任意式は使わない|Coreが提案を判断しHandlerが正式codeタスクを発注。K cor-p2。AI performed_step_idsでcode完了を申告しない|必須：正式task/result、原manifest/table/row/hash・computed/partial/not_computedの照合。slot能力の汎用登録は未実装|data_requested/dataset_committedは論理名、callback未登録blocked。計算の成功はセルごとの状態で示す|
|説明・受領|同runの検証済み・実配信表。modelに未提供の行やセルへ束縛しない|`result_explanation`：AI cor-ai-report、K cor-p2、R cor-p1/p3/p4。Rの本人record取得は現行unsupported|必須：07の5string、calculation_result_ids/9キーnumeric_bindings、statistical-cells-v1。AI自由文は未検証下書き、数量主張はコード描画のみ|read_calculation_table/read_evidence現行。output_receivedは論理callback未登録blocked。受領と研究採用を分離|
|採否・停止・引継ぎ|stale/未読/欠測・単位違い・別群/変数・未知tool・hash不一致・重大意味未判定|Handlerの保留、研究者の変数対、Pearson/Spearman種類、欠測・外れ値・同順位、因果/方向・探索性の判断。AI自己申告/Core採用はR recordの代用にしない|必須：human_pending、semantic undetermined、理由/未処理/旧版/次担当。本人recordが対象input/result/hashへ束縛できるまで未確認|checkpoint/resuming/failed/stopped/label_version_committed planned、callback未登録blocked。再通知と再計算を区別|

^cor-stages

AI許可集合は `cor-ai-plan/cor-ai-report` だけ。必要AI集合は07の当該phaseの集合、許可集合の部分集合。実phaseは固定response_phaseと計算結果から決め、モデルの申告で切替えない。計算前 `needs_calculation` は未実行提案、不足 `needs_input`、不適用 `not_applicable` は理由付きで成功/欠測0へ変えない。R required集合は計画p1、説明p1/p3/p4で、人の記録なしは `human_pending`。

07の5必須stringは `analysis_plan`、`prerequisite_review`、`result_explanation`、`quality_record`、`limitations`。数値9キーは `result_id/dataset/row_id/column/variables/target/dataset_version/computation_input_hash/rows_hash`。value/表示文/丸め桁をモデルへ追加許可しない。raw表・対象集合・N/欠測・分母・単位・状態を同じ行/manifestへ戻す。原全行hashを抜粋から再作成しない。自由文の数値/既知禁止断定の検査は意味妥当性や研究採否の合格を保証しない。

分野固有：dataset `correlations`、variables=[variable_a, variable_b]は原順序、target.selectors={method}。Pearson/Spearman、coefficient/p_value/N/missing/unit_a/unit_b/status/p_value_adjustmentは同一行。因果/方向・話者内/間・多数ペアの選択は人判断、変換/並替/CI/補正は未実装・未提供のまま。

## 入力slot・論理kind・roleの照合案

以下は汎用slot能力の固定提案で、現行adapterが任意artifactを受理する宣言ではない。論理kindは5種、roleは4種に限定し、具体的な原文/媒体/parameter参照は型付き表へ潰さない。各参照にID・版・hash・取得用途・送信可否・選択範囲を必要とし、任意slotでも選択した入力は開始前に解決する。

|slot／必須・個数|kind／schema・role|単位・scope・actor／利用目的|現行対応と不足|
|---|---|---|---|
|問い・分析前提／問い1必須、前提0..1任意|パラメータ参照、07 input schema S2・analysis_premises string/null。`parameter_source`|Rが与えた目的/流派/条件、Core選択/Handler固定。未指定はnull|元入力/契約を固定。任意slotの省略は方法論前提が確認済みの意味ではない|
|固定入力・原文／対象1必須、根拠ID1..n|原文は既存evidence schema、論理`event_sequence`対応候補。`data_input`＋別参照`evidence_context`|発話ID/会話ID/入力版、初期固定会話。発話数値/群・変数対、原文に戻る文脈|既存snapshot/evidenceあり。単位/順序/欠区間は保持。区間/横断の汎用scope adapterはunsupported|
|選択元／0..n任意|論理`claim_set/observation_table/relation_graph`からの固定参照。`selection_basis`|どの主張/表/関係から根拠を選んだかを記録|現行08汎用resolverなし。選択結果だけをRAW全件にしない、未対応は理由付き保留|
|正式計算表／計画0、説明1..n必須|論理observation_table、既存型付きdatasets/manifest・9キーセル束縛。data_input|K cor-p2、all_included_initial、発話単位。初期群/変数を変えない|同runの正式task/result/row/hashあり。任意のobservation_table/採用後ラベル入力はunsupported|
|採用定義・人record／確定に必要、候補では不足保持|人の記録/定義参照（候補分類が表なら論理`observation_table`）。`parameter_source`、原文は`evidence_context`|R本人・確認日時/判断/対象step・入力版/結果hash。未reviewの研究者labelを採用済みにしない|cor-p1/p3/p4 record取得はunsupported。架空recordを作らず人未確認/human_pending|
|補助媒体／必要条件時必須、他は0..n|音声/観察等の固定参照。`evidence_context`|前後文脈/非言語の確認、媒体可用性・用途許可を本人が判断|逐語録から音声・表情を推定しない。未提供はneeds_input/未読|

^cor-slots

`embedding_matrix`はこの08で受理するslotを持たない。埋込clusterや異なる単位のreportを暗黙変換しない。実行receiptはkind/観測行として受け取らず、来歴の証拠として別に戻る。登録済み変換adapter・schema・単位/尺度/scopeを照合できなければunsupported。actor不一致、入力/結果/参照hash不一致は拒否・再固定へ戻す。

## hook・callback・上限・停止と再開

|要求／接続点|登録ID・版・実在範囲|上限・失敗・停止条件|
|---|---|---|
|read_evidence / read_calculation_table|既存 `services/expert_data_hooks.py`、内部版3。要求名は既存プロトコルであり、汎用callback登録IDではない。同runの許可根拠と提供計算表を読む|2巡×各最大3要求・総取得上限12,000文字。ID/版・result/table/rowを推測修復しない。read receiptとモデル実配信receiptを分離し、未読/未配信は未処理|
|task_prepare / knowledge_requested / data_requested|論理名planned、callback ID・版は未登録|必須依存はblocked。08 readerと知識部分取得の汎用callbackを既存read_evidenceへ読み替えない|
|output_received / label_version_committed / dataset_committed|論理名planned、callback ID・版は未登録|受領、候補保存、研究者採否、固定保存、consumer別receiptを分ける|
|checkpoint / resuming / failed / stopped / memory_projection_requested|論理名planned、callback ID・版は未登録|現行永続状態・停止/世代・残予算/期限・許可集合/入力版を再確認。投影失敗と分析成否を分ける。通知再送だけで再計算しない|

^cor-hooks

hook仕様は [[50-Analysis-Methods/40-Skills/80-Hooks/00-Index]] を再利用する。旧hook版2のrunは凍結読取を維持し、版3へ書替えて再開せず既存停止理由を返す。期限/版/許可集合の変化は旧成果物を履歴保持して、新しい計画/要求と予算へ戻す。同一固定版の受領再通知は生成を重複させない。能力未登録はG2/G4担当へ、前提・意味未判定・採否は研究者へ渡す。ノートのコード/式/YAMLを動的実行するreaderは作らない。

## G3へ渡す正常・負例（仮書式の評価）

全例は文書上の能力照合期待値。G3に合成fixtureと独立した元表/原文期待値を置くとき、このIDと対象hashを戻り先にする。ここでruntime試験・実モデル品質・人の採用を合格にしない。

|case ID|固定する入力対と変更点|期待状態・理由／責務|
|---|---|---|
|G1B-COR-01|正常対：D2/C2/S2、初期発話、pearson/spearmanの正式同run表、計画cor-ai-plan→説明cor-ai-report、正しい9キー、R record未回答|既存構造/セル束縛の検査対象。数値は原セルからコード描画、human_pending/意味undetermined維持、08はplanned|
|G1B-COR-02|正常対のtoolをunknown/非許可anova、またはAI禁止expertへ替える|unknown/nonallowedを拒否。method名が索引にあることを正式executor存在の証拠にしない|
|G1B-COR-03|scopeをsection、または発話行を参加者独立標本/テーマ候補数へ替える|unsupported/wrongscope/wrongunit。all_included_initialと発話単位のadapterだけ、暗黙集約/一般化なし|
|G1B-COR-04|未reviewの研究者labelまたは採用後の新変数表を初期固定表の代わりに渡す|unreviewed researcher label/unsupported。研究者recordなしは保留、現toolは採用後任意表を受理しない|
|G1B-COR-05|正常対のresult/row/variables/hashを別版へ替える／AI performed_step_idsへcor-p2/p3を追加する|参照/hash不一致・code/researcher actor mismatchを拒否。本人確認の自由文は未検証下書きに保持|
|G1B-COR-06|必須行未配信、not_computed/nullを0へ替える、または因果/一般化の未判定を完了とする|needs_input/未読/未計算を保持。既知禁止断定は拒否/隔離、意味未判定はhuman_pending。成功にしない|

^cor-g3-cases

上の06例の実行は未実行。後続G3は正常/異常対、入力版/対象集合・分母・kind/単位/role・原表hash・期待理由を固定する。自由文だけのactor自己申告を機械検査の実施証拠にせず、未知と既知禁止断定、意味判定不能、研究者確認不足を別に記録する。

## 採否・独立レビューの保留

作者による前付/リンク/ID/版・actor/step・sourcehashの静的確認、現行01/07 loader受理は文書技術確認に限定する。独立文書レビューとObsidian 1.13.7隔離fixtureの新3binding表示はC0後続、実モデル・個人上書き・研究者資料の方法論採否は未実行/未評価。対象hashに対する本人/独立担当の記録が揃うまでreviewed/connectedへ変更しない。

この08を以て全G1b・全知識充足・G2/G4能力接続の完成としない。人判断の保留と次担当は [[50-Analysis-Methods/50-Knowledge-Evaluation/expert-stage-readiness#保留・人の判断と次工程]] へ戻る。


C0本文訂正（2026-10-08）：独立文書レビュー `msg_79ef761f4808` とF04独立 `msg_b1d33bd65fa4` の終了後、統計07の現行説明だけをa04実装・a06限定受入へ訂正した。実行YAMLはbyte同一。対応するraw参照hashを上表へ再束縛し、旧／新hashの対応は `../artifacts/obsidian-skill-plan/revision-5/g1b-doc-correction.json` に保持する。初回のselected-source-manifestは作者時点の履歴として維持し、現在の07はこの差分metadataで解決する。08 reader・人record・実モデルは未接続／未評価のまま。
