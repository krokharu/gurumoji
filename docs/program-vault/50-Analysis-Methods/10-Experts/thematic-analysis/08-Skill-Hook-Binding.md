---
note_id: expert-thematic-analysis-skill-hook-binding
note_type: expert-skill-hook-binding
title: テーマ分析の段階別スキル・hook対応案
summary: テーマ分析の現行01・07・actor・scopeを固定し、未接続readerと不足を明示する。
status: proposed
schema_version: 1
binding_version: 2
expert_ids: [exp-thematic-analysis]
stage: registration
review_state: draft
runtime_state: planned
required_note_ids: [analysis-common-evidence-and-claims, analysis-common-source-classification, analysis-common-group-interview-data, analysis-common-ai-assistance-boundaries, expert-thematic-analysis-overview, expert-thematic-analysis-definition, expert-thematic-analysis-procedure, expert-thematic-analysis-quality, expert-thematic-analysis-limits, expert-thematic-analysis-cases, expert-thematic-analysis-open-issues, lit-braun-clarke-2006-thematic, lit-braun-clarke-2021-one-size, lit-byrne-2022-reflexive-ta, lit-gilardi-2023-llm-annotation, lit-hermann-2024-fg-interaction-coding, lit-oka-2022-reflexive-ta-ja, expert-thematic-analysis-agent-contract]
optional_note_ids: []
updated: 2026-10-08
tags: [gurumoji/skill, gurumoji/expert]
---

# テーマ分析の段階別スキル・hook対応案

G1b-entry-02の固定提案。専門家IDは `exp-thematic-analysis`。研究質問に関わる意味パターンの候補を、支持・反例と原文IDへ戻して提示する。採用テーマは研究者が決める。
書式は [[90-Templates/skill-hook-binding]]、skill書式は [[90-Templates/skill-definition]]、充足・人の保留は [[50-Analysis-Methods/50-Knowledge-Evaluation/expert-stage-readiness|17専門家の充足・不足表]]。この08の作成は実行登録ではなく、G2/G4の能力登録・汎用reader・callbackは未実装として保持する。

## 目的・取得用途・固定する出典

|対象|ID・版・raw byte SHA-256／用途|
|---|---|
|01|[[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert\|専門家実行定義]] `expert-thematic-analysis-definition` D2 / `26dfcdfe87323ed33fe232c8c36489f24453adb58c2b2feaa48083996147ecdc`。問い・流派・単位・許可step/actor・禁止結論の照合|
|07|[[50-Analysis-Methods/10-Experts/thematic-analysis/07-Agent-Contract\|入出力契約]] `expert-thematic-analysis-agent-contract` S1/C1 / `453adefd17b23e289352affafc4ae85d61afa1a6f094a34e774c806772050a65`。入力・出力型。統計2phaseの必須step契約は追加しない|
|手順|skill-thematic-candidate-evidence skill1/r3 8f7860af502ba9dd6e33da259309284bd53f2fa64c9d91a5d0754c66c82b5527; workflow-group-interview-evidence flow1/r3 1a8ed0b31076f5ade8ddb30ca953ac00debf022a3b08b20b4544221a096a2a32。tce-guards/procedure/output全体|
|実装|root `0fbfb402af9d9bdd18a495565288bf5ed273d5f4`、Registry `obsidian-expert-agents-3`、hook `expert-data-hooks-3`。既存01/07 parserとHandlerを正本とする|
|開始base knowledge|`sha256:5342ff429fa9d3d026898eafdfb01a76ecdd9d4d624ae10b1760e6a76e6c3f98`。個人上書き・実run採用hashではない|
|入口追記後base knowledge|`sha256:8941432f37b57280357ef58725748ce95a9fb872b2ce18a87626f5a2936193df`。Overview入口追加による変更。旧runの固定profileへ後付けしない|
|配信方針|C0 `task_e1044a47e1e6` の `currentPack` 暫定維持。新方式 `notadopted`、b/c未測定で比較優位・実モデルready・品質合格を認定しない|

^ta-sources

必要知識は前付のrequired_note_ids（既存Catalogの選択00〜06・共通・文献と07）に一致する。本文を必要用途で読む範囲は02の手順、03の品質、04の適用/限界、06の未確認、01のprocedure/basisと07。参照文献は以下の用途をまず照合し、Packの省略を全文自由取得で補わない。

|出典ID／note ID|既存確認範囲・版／raw SHA-256|参照用途と保留|
|---|---|---|
|[[50-Analysis-Methods/20-Literature/LIT-braun-clarke-2006-thematic\|LIT-braun-clarke-2006-thematic]] / lit-braun-clarke-2006-thematic|full_text・2026-09-16 / `3360c43f677b9c772185e85fc670ac1d1b76b7195b3907f50190f6876dec3f3e`|01のbasis/quality/限界へ戻す。今回frontmatter・存在・hashのみ。文献本文の新読了、人の方法論採否、訂正状態の再確認は未実行|
|[[50-Analysis-Methods/20-Literature/LIT-oka-2022-reflexive-ta-ja\|LIT-oka-2022-reflexive-ta-ja]] / lit-oka-2022-reflexive-ta-ja|full_text・2026-09-16 / `ad0fb8453a74f9768883c8762a9664bb19e1e3e17a9d462ba93fb4b0b623a295`|01のbasis/quality/限界へ戻す。今回frontmatter・存在・hashのみ。文献本文の新読了、人の方法論採否、訂正状態の再確認は未実行|
|[[50-Analysis-Methods/20-Literature/LIT-hermann-2024-fg-interaction-coding\|LIT-hermann-2024-fg-interaction-coding]] / lit-hermann-2024-fg-interaction-coding|full_text・2026-09-28 / `ae0e78a022ccb8d5f6a8d46e125c5347705f2923bd8da59a977fc589310543fb`|01のbasis/quality/限界へ戻す。今回frontmatter・存在・hashのみ。文献本文の新読了、人の方法論採否、訂正状態の再確認は未実行|

全必要sourceのmetadataは `../artifacts/obsidian-skill-plan/revision-5/g1b-entry-02/selected-source-manifest.json`（SHA-256 `c99f638317a748a2dc5cf8fb313cc9ec3f385001b6a0d1498126d337114aed67`）と充足表の固定台帳へ戻る。base/local/固定実run、raw note hash/knowledge集合hash/profile hashを分ける。研究者本文・原文・資格情報を08へ複製しない。

currentPackは各note抜粋 `min(1600, 8000 // note数)`、`omitted_characters` を残す。現行CatalogのKNOWLEDGE_NOTESは00〜06固定で08本文は送られない。今回の3 Overview入口はknowledge hashと次runの抜粋候補を変えるが、08専用reader接続にはならない。必要本文の実配信/読了は別receiptと範囲で確認する。

## 段階別の対応表

表示用段階名と実行phaseを分ける。既存に登録された分析skill IDは未作成であり、表の作業名から架空IDを発行しない。必須のskill登録はplanned、必須論理callbackは未登録blocked。今の01/07実行経路は08を利用せず存続する。

|段階|method／scope・単位|actor・許可procedure|必須／任意skill・読む知識|hook・状態|
|---|---|---|---|---|
|計画・準備|`thematic` は分析方針ID。逐語録の全データセット、初期固定会話。区間adapter能力を付けない|R ta-p1（全体を少なくとも1回精読）、研究質問/理論前提を本人が記録。Coreは選択、Handlerは正式発注|必須：問い/流派/全体精読の確認（未登録planned）、01 required_inputs/school、02/04、07 analysis_premises（任意string/null）。任意の資料も選択したら固定参照へ解決|task_prepare、knowledge_requested planned。callback未登録blocked|
|候補生成|元発話IDと前後文脈。テーマは意味パターン、発話件数は重要性の尺度にしない|AI ta-p2/ta-p3のみ。数値計算/人の精読・確定を代行しない|必須：初期code/候補/支持と反例の整理（未登録planned）、01 procedure/禁止、02/03、07の7出力。必要原文は許可IDだけ|read_evidence現行。data_requested論理callback未登録blocked|
|受領・採用|07 string出力＋claim/evidenceを元版/hashへ戻す。論理claim_set候補は汎用kind登録済みではない|Handlerが型/知識ID/AI step/根拠IDを検査。R ta-p4/p5/p6がレビュー/命名/報告・採否|必須：型と参照照合、意味/反例/human_review（後者未実施）。Rの記録なしは人未確認。AI plan/reportは統計phaseに読み替えず準備/候補/報告責務として表示|output_received planned、label_version_committed等未登録blocked。候補受領を採用確定にしない|
|停止・引継ぎ|必須原文未読、入力/knowledge hash変化、未対応区間、actor違い|Handler停止、Coreへ不足/次担当、研究者へ前提・採否。再開は対象版・許可集合・期限/世代を再確認|必須：未読・未処理・旧版保持（planned）。未指定理論前提を生成しない。変化は別計画/要求へ戻す|checkpoint/resuming/failed/stopped planned、callback未登録blocked。通知再送を再生成にしない|

^ta-stages

07出力名は `research_context`、`analysis_form`、`candidate_themes`、`theme_evidence`、`theme_relations`、`quality_record`、`limitations` の7必須string。AIの出力が非空でも支持/反例の意味充足、全体精読、確定解釈は証明しない。TAには統計S2のphase_requirements/numeric_bindingsを追加しない。正式codeはTA固有の数値計算として登録せず、必要な既存補助分析を別タスクの能力として照合する。

## 入力slot・論理kind・roleの照合案

以下は汎用slot能力の固定提案で、現行adapterが任意artifactを受理する宣言ではない。論理kindは5種、roleは4種に限定し、具体的な原文/媒体/parameter参照は型付き表へ潰さない。各参照にID・版・hash・取得用途・送信可否・選択範囲を必要とし、任意slotでも選択した入力は開始前に解決する。

|slot／必須・個数|kind／schema・role|単位・scope・actor／利用目的|現行対応と不足|
|---|---|---|---|
|問い・分析前提／問い1必須、前提0..1任意|パラメータ参照、07 input schema S1・analysis_premises string/null。`parameter_source`|Rが与えた目的/流派/条件、Core選択/Handler固定。未指定はnull|元入力/契約を固定。任意slotの省略は方法論前提が確認済みの意味ではない|
|固定入力・原文／対象1必須、根拠ID1..n|原文は既存evidence schema、論理`event_sequence`対応候補。`data_input`＋別参照`evidence_context`|発話ID/会話ID/入力版、初期固定会話。全体精読と前後文脈、AI候補の支持/反例|既存snapshot/evidenceあり。単位/順序/欠区間は保持。区間/横断の汎用scope adapterはunsupported|
|選択元／0..n任意|論理`claim_set/observation_table/relation_graph`からの固定参照。`selection_basis`|どの主張/表/関係から根拠を選んだかを記録|現行08汎用resolverなし。選択結果だけをRAW全件にしない、未対応は理由付き保留|
|候補report／1候補|論理claim_set候補、07 output schema S1。data_inputとして再利用する能力は未登録|AI ta-p2/p3の下書き、意味パターンの単位|7stringと共通claims/evidenceを検査。candidate_themesを確定テーマ表にしない|
|採用定義・人record／確定に必要、候補では不足保持|人の記録/定義参照（候補分類が表なら論理`observation_table`）。`parameter_source`、原文は`evidence_context`|R本人・確認日時/判断/対象step・入力版/結果hash。未reviewの研究者labelを採用済みにしない|ta-p1/p4/p5/p6の本人判断を保持。架空recordを作らず人未確認/human_pending|
|補助媒体／必要条件時必須、他は0..n|音声/観察等の固定参照。`evidence_context`|前後文脈/非言語の確認、媒体可用性・用途許可を本人が判断|逐語録から音声・表情を推定しない。未提供はneeds_input/未読|

^ta-slots

`embedding_matrix`はこの08で受理するslotを持たない。埋込clusterや異なる単位のreportを暗黙変換しない。実行receiptはkind/観測行として受け取らず、来歴の証拠として別に戻る。登録済み変換adapter・schema・単位/尺度/scopeを照合できなければunsupported。actor不一致、入力/結果/参照hash不一致は拒否・再固定へ戻す。

## hook・callback・上限・停止と再開

|要求／接続点|登録ID・版・実在範囲|上限・失敗・停止条件|
|---|---|---|
|read_evidence|既存 `services/expert_data_hooks.py`、内部版3。要求名は既存プロトコルであり、汎用callback登録IDではない。今回の許可根拠IDだけ読む|2巡×各最大3要求・総取得上限12,000文字。ID/版・result/table/rowを推測修復しない。read receiptとモデル実配信receiptを分離し、未読/未配信は未処理|
|task_prepare / knowledge_requested / data_requested|論理名planned、callback ID・版は未登録|必須依存はblocked。08 readerと知識部分取得の汎用callbackを既存read_evidenceへ読み替えない|
|output_received / label_version_committed / dataset_committed|論理名planned、callback ID・版は未登録|受領、候補保存、研究者採否、固定保存、consumer別receiptを分ける|
|checkpoint / resuming / failed / stopped / memory_projection_requested|論理名planned、callback ID・版は未登録|現行永続状態・停止/世代・残予算/期限・許可集合/入力版を再確認。投影失敗と分析成否を分ける。通知再送だけで再計算しない|

^ta-hooks

hook仕様は [[50-Analysis-Methods/40-Skills/80-Hooks/00-Index]] を再利用する。旧hook版2のrunは凍結読取を維持し、版3へ書替えて再開せず既存停止理由を返す。期限/版/許可集合の変化は旧成果物を履歴保持して、新しい計画/要求と予算へ戻す。同一固定版の受領再通知は生成を重複させない。能力未登録はG2/G4担当へ、前提・意味未判定・採否は研究者へ渡す。ノートのコード/式/YAMLを動的実行するreaderは作らない。

## G3へ渡す正常・負例（仮書式の評価）

全例は文書上の能力照合期待値。G3に合成fixtureと独立した元表/原文期待値を置くとき、このIDと対象hashを戻り先にする。ここでruntime試験・実モデル品質・人の採用を合格にしない。

|case ID|固定する入力対と変更点|期待状態・理由／責務|
|---|---|---|
|G1B-TA-01|正常対：D2/C1、初期会話/原文ID、ta-p2/p3のみ、7stringと支持・反例候補、R recordは未回答|既存候補型/参照の検査対象。08はplanned、人未確認。テーマ意味充足はG3独立期待値待ち|
|G1B-TA-02|正常対のmethodをunknown、新AI手順ta-p4、またはAI禁止exp-kj-methodへ替える|unknown/nonallowed。未登録能力や研究者stepのAI代行を拒否。既存実装のエラー名と文書分類を混同しない|
|G1B-TA-03|同じ根拠を未対応section scope、テーマ候補数を参加者数へ替える|unsupported/wrongscope/wrongunit。一般区間adapterなし、テーマ数を人数/重要性に置換しない|
|G1B-TA-04|AI候補theme labelを人recordなしで採用済みobservation_tableとして後段へ渡す|unreviewed researcher label。人未確認/採用保留、汎用入力adapter未対応|
|G1B-TA-05|knowledge/profileまたは入力参照hashを旧版へ替える／performed_step_idsにR ta-p1/p4を入れる|参照不一致/actor mismatchを拒否。AIの「全体精読済み」自由文は未検証下書きに保持|
|G1B-TA-06|支持候補の原文未配信/反例文脈なし、または理論前提nullを確認済み扱いする|needs_input/未読または意味undetermined。参照存在や7string非空を読了/採用の成功にしない|

^ta-g3-cases

上の06例の実行は未実行。後続G3は正常/異常対、入力版/対象集合・分母・kind/単位/role・原表hash・期待理由を固定する。自由文だけのactor自己申告を機械検査の実施証拠にせず、未知と既知禁止断定、意味判定不能、研究者確認不足を別に記録する。

## 採否・独立レビューの保留

作者による前付/リンク/ID/版・actor/step・sourcehashの静的確認、現行01/07 loader受理は文書技術確認に限定する。独立文書レビューとObsidian 1.13.7隔離fixtureの新3binding表示はC0後続、実モデル・個人上書き・研究者資料の方法論採否は未実行/未評価。対象hashに対する本人/独立担当の記録が揃うまでreviewed/connectedへ変更しない。

この08を以て全G1b・全知識充足・G2/G4能力接続の完成としない。人判断の保留と次担当は [[50-Analysis-Methods/50-Knowledge-Evaluation/expert-stage-readiness#保留・人の判断と次工程]] へ戻る。
