---
note_id: workflow-group-interview-evidence
note_type: workflow-proposal
title: グループインタビューの根拠接続手順（提案）
summary: 目的・準備・内容候補・人の相互作用・比較・反例・報告を結ぶ。
status: proposed
schema_version: 1
workflow_version: 1
review_state: draft
runtime_state: planned
required_note_ids: [data-analysis-asset-connection-v1, skill-thematic-candidate-evidence, transcript-preparation-v1, analysis-common-evidence-and-claims, analysis-common-source-classification, analysis-common-group-interview-data, expert-focus-group-interaction-definition, expert-focus-group-interaction-procedure, expert-focus-group-interaction-quality, expert-focus-group-interaction-limits]
optional_note_ids: [expert-correlation-skill-hook-binding, expert-group-comparison-statistics-skill-hook-binding]
updated: 2026-10-08
tags: [gurumoji/workflow, gurumoji/analysis]
---

# グループインタビューの根拠接続手順（提案）

研究目的に応じて既存手順を組み合わせるworkflow案。新AI expert/persona、parser/reader/callback/executorを登録しない。TA01 D2/07 S1/C1・7string、統計07 S2/C2、現在のactor・phaseを維持する。共通型と固定contentは[[30-Data/analysis-asset-connection-v1]]、TAは[[50-Analysis-Methods/40-Skills/thematic-candidate-evidence]]を再利用しschemaを複製しない。

## 目的から必須・条件・非対応を決める

| 研究目的 | 必須 | 条件付きで選ぶ入力/手順 | 未対応・不足時 |
| --- | --- | --- | --- |
| 語られた意味のまとまり | 問い/流派、本文/区切り確認、入力版、内容根拠、TA候補/支持/反例/代替 | 人による全体精読、媒体、定義/命名 | 本人p1/p4–6未回答は確定保留。頻度を重要性としない |
| どう応答・対立・変化したか | 話者/順序/司会確認、複数発話の連鎖、人のmanual interaction | 音声/観察/fieldnotesが当主張に必要なら必須 | 媒体なしで声色/表情/正確な間はunknown。話者不明は当枝停止 |
| 場面/意見の質的対照 | 定義版・同名異義確認、内容候補＋関係＋原文context、人の比較理由 | 固定scope/episode、原記録再取得、反例検索 | section/episode汎用adapterなしはunsupported、意味を自動対応させない |
| 初期発話の探索的数量・関連/群差 | 対象集合/分母/変数/尺度/除外、01/07の許可method、正式code表 | COR/GRP B2入力、説明phase、研究者p1/p3/p4 | 数量枝は省略可。任意新表・採用後ラベル・独立参加者推論は未対応 |
| 参加者/複数会話/反復データ比較 | 人の対応・設計・単位決定 | 将来G4c projection/aggregate/joinの別step | 現行all_included_initialへ混入不可、paired/nested推論未対応 |
| 確定報告 | 原根拠、反例/限界、定義/命名・本人採否record、確認範囲 | 別下書き・固定正式計算表 | 未読/未処理/意味未判定を確定主張へ昇格しない |

^giew-purpose

## 代表手順と停止

この表は全行・actor・必須・停止を含む取得単位。TA02/FGI02と使用するCOR/GRP02の段階表も全行を読む。部分reader未接続を全文自由取得で補わない。

| 順 | actor・既存step | 固定する入力→出力 | 停止・引継ぎ |
| --- | --- | --- | --- |
| 1 準備 | researcher、TA ta-p1/FGI fgi-p1 | 問い/流派、入力版/hash、本文・区切り・speaker/order、名簿根拠、司会/fieldnotes/媒体→確認状況 | 本人未回答/話者不明は該当枝needs_input/human_pending |
| 2 内容候補 | AI ta-p2/p3のみ＋研究者 | 許可原文/context→固定CandidateContent/ThemeContent、支持/反例/代替・未読・検索状態 | AI候補はdraft。未探索≠反例なし、未配信は未処理 |
| 3 manual interaction | researcherのみ、既存fgi-p1〜p7の人手順 | 保存annotations/interaction_links→両端・順序・間の全context、応答/反論/撤回/司会区分 | missing_target/古い根拠は保留。AI発話組は本人確定ではない |
| 4 比較 | researcher、数量選択時だけ登録code＋COR/GRP許可AI | claim_set＋relation_graph＋原文→質的対照。数量は別正式task/result | 任意表/単位不一致/新採用labelはunsupported、数量枝だけblocked |
| 5 反例・定義 | researcher ta-p4/p5 | 撤回/少数意見/異義/context→split/merge/reject/定義・命名・理由・旧版履歴 | 架空本人recordを作らず未回答維持。AI補助は新ta-p2/p3 |
| 6 報告・受渡し | researcher ta-p6/FGI fgi-p7、AIは許可下書きのみ | 問い/入力版/根拠/比較/反例/限界/採否/未読→draft report・次担当 | 本人採否なしは確定不可。モデル評価/人評価未実行を明示 |

^giew-procedure

FGI01にはfgi-p3/p5のAI補助が存在するが、本workflowのmanual interaction枝は研究者操作だけを採用する。コードq1のリンク数確認を人q2〜q5の解釈確認に置き換えない。沈黙/相づちを合意、引用を固定個人意見、similarityを応答と断定しない。fieldnotes/メモの所有者・原版を維持し、研究者本文へAI結果を自動反映しない。

## 準備・単位・分母

名簿の実参加者、観測された会話内speaker、UNKNOWN、無発言参加者、司会を別集合で保持。speakerラベルは人物証明ではない。無発言・未観測≠反対/同意/0。入力version/source_hashと確認revisionを記録し、本文/speaker/order変更後は旧確認を歴史として残す。mediaなしで音声照合済みを作らない。

会話内speaker IDはconversation_idで名前空間を分け、会話横断の人物対応は本人の根拠がある場合だけ。反復参加者を独立人数として重複加算しない。共同発話のparticipant_refsは0..n、episode重複は独立観測行の増殖ではない。分母は対象全発話/有効観測/対象参加者/会話等のどれか、対象集合・除外・条件と一緒に固定し、抽出数を全体数にしない。

value_statusはobserved（有効0を含む）/missing(null)/excluded/unprocessed/unknownを分離。空集合も別。valid_time=falseならstart/end/duration=null、互換placeholder 0秒を計算・順序・確認証拠に使わない。順序は固定配列の付番。時刻の有効小計とtimed/missing数を分ける。集計除外の発話も応答contextとして保持し、欠区間・順序不明を補わない。

将来G4cは承認済み定義/参加者対応→登録projection（行/列）→aggregate（unit/分母/欠測）→join（キー/多重度/件数）を別code stepとする。任意Python式や新scopeをノートから実行しない。現行初期発話adapterへ接続済みとはしない。

^giew-units

## 接続・固定hash・配信と保留

共通契約schema1/proposal_revision2を使い、SourceRef/Scope/Asset/AssetState/Slot/InputRef/Bindingの正本はその各block。5kindはobservation_table/claim_set/relation_graph/event_sequence/embedding_matrix、4roleはdata_input/selection_basis/evidence_context/parameter_source。原文/媒体/本人メモはSourceRef、receiptは研究kind外。kind一致だけでは再利用できずschema/unit/scale/scope/actor/実登録adapter版とconsumer目的/送信policyを照合する。embeddingはTA/本初期経路unsupported。

source raw byte hash、入力source_hashの既存domain、TA content HC、AssetState採否/利用policy、取得/配信/処理receiptを区別する。旧source_hashをrawへ推測変換しない。receipt追記でHCを変えず、内容/定義/入力/根拠/scope変更は新content版/hashにする。候補→テーマ参照は固定TA方式の一方向、自己hash/改訂循環なし。状態adoptedでも用途・人step未充足を迂回しない。

取得receiptはtool返却、配信receiptは実contextへの配信、processing receiptは実処理byte、本人精読は本人record。それぞれ不足集合を別にし、unknown/not_runを空集合や読了へ置き換えない。G3合成台帳は実配信・人読了の証拠ではない。現read_evidenceは2巡×最大3要求/12,000文字、計算packetは各表40行・既定10,000文字、全件hash/件数と抜粋/省略件数は分離。知識部分取得候補3資料×2巡/8,000文字は未接続、全必須表の取得不能は停止。

required slotは解決必須、optionalもselectedなら同じ待機、omittedは理由固定。from_step親は採用/保存待ち、frozenも同じ検証を通す。全親purpose/scope/送信先のintersectionを用い、prohibited/local_onlyを拡大せず、空はblocked。発注前と結果attachment/採用前にhash/state/policy/世代/取消/期限/残予算/能力版を再確認する。通知の再送はreceiptだけ、旧世代/逆順で新発注しない。入力変更は新plan/task/予算、取消/失効は依存子孫のみstale。

本人record、model capability、callback不足は依存枝だけblocked/human_pending。独立に充足した枝のdraftは保持し、全体完了としない。意味未判定はCore採用の確定主張ではない。旧bundleを現行知識で補完/強制resumeせず読取保持。技術問題はHandler/G4、流派/解釈/採否/命名は研究者、独立文書reviewはC0担当へ戻す。

^giew-binding

## case aliasと文書trace

原44=REUSE-01〜12、CONN-01〜06、QA-01〜07、ASSET-01〜08、GI-01〜11。TA追加6=G2-TA-01〜06。G3先行50はこの44+6だけ、本票/COR/GRP新手順のruntime検査分母を増やさない。

| 元ID | 本workflowでの対照/不足（alias維持） |
| --- | --- |
| GI-01/02/03 | 準備不足/名簿≠観測話者/司会context |
| GI-04/05 | 撤回・反論再取得、媒体unknown/invalid time/抜粋≠全読了 |
| GI-06/07 | 別kind再利用、同label異義/対応未確認→未比較 |
| GI-08/09 | 本人memo/旧解釈、共同発話/episode重複/反復/欠測/分母 |
| GI-10/11 | 目的/未読/誤数値/禁止結論/actor、人/モデル/技術評価分離 |
| G2-TA-01/02/03 | 正常候補/偽hash・actor/未配信・未探索・本人未回答 |
| G2-TA-04/05/06 | split/merge履歴、wrongunit/section、optional待機・再送・取消 |
| G1B-COR-01〜06 | 正常/非許可/単位scope/新表/9キーactor/未配信未計算。相関票の同ID |
| G1B-GRP-01〜06 | 正常/非許可/単位scope/新label/9キーactor/未配信未計算。比較票の同ID |

^giew-cases

新手順の規範確認：W-P01=目的に応じ必須/条件/省略を固定、W-P02=内容候補→人手interaction→質的比較、W-P03=反例→定義/命名→draft handoff。正常文書traceは1会話の固定本文/順序・許可→ta-p2/p3固定候補→人link/context→質的対照→反例/未読→本人未回答のdraft受渡し。隔離負例は同traceでlink先を削除→missing_target、その相互作用主張だけ保留、旧引用・候補・原版保持。W-P04=未登録quant/本人record不足で依存枝のみ停止、W-P05=取消をattachment直前に検出→子昇格禁止。

これらは提案上の期待行。新runtime fixture実行0、成功とラベルしない。actual code/parserの限定接続、sourceノートの規範、G2提案、合成fixture、実モデル、人評価を別記録にする。文書readiness=draft/planned、方法採用/人精読/モデル品質/full G2〜G4は未完。

## 固定source manifest・読取範囲

共通固定commit=2907391b55989579935134403f2d12010f73514e、C0のR02限定文書受入はこの固定2票に限る。新3票は対象外。下記raw SHA-256は正規化前実byte。01/07の定義・段階/出力、02全段階表、03判断、04限界を必要範囲で読む。文献原文は今回未取得。既存abstract/full_text/書誌の区分を持つノートの説明をその範囲で再利用し、code decisionとsynthesisを分ける。

Shared manifest: data-analysis-asset-connection-v1 S1/rev2, raw 438fd973660016ee1ab1c4150ee6c914792bbf3ce3f3f77f88cd49ebfe09e986, commit 2907391b55989579935134403f2d12010f73514e. Inherit its source-table E/SC/GI/PR/T note IDs and raw hashes. Read scope: E evidence/human review; SC access scope; GI all cautions; PR preparation/version; T mandatory fields. E/SC/GI version 2026-09-15, PR v1, T 2026-10-08. Read ^asset-types/hash/binding/measures; note sections only, no original literature read.

Read scope: 01 D2 input/procedure; 02 whole stage table; 03 quality; 04 limits (2026-09-16; GRP02 corrected); 07 S2/C2 phases/cells/status; 08 B2 stages/slots/hooks. 07/08 commit 5c40a0d3065f77039bad87a88eac91cbf6020d55.

FGI read scope: 01 D2 procedure/allowed AI/prohibitions; 02 whole stage table/records; 03 quality/actors; 04 input/limits. 02/03/04 version 2026-09-16. Raw note hashes below; original literature unread.

| note_id | raw SHA-256 |
| --- | --- |
| expert-focus-group-interaction-definition | 502131e409de7b141a166658ee63a5935e0e1aca95efd7112f99bd9b316dde82 |
| expert-focus-group-interaction-procedure | e8a2e4681379ce6fd8c0919b6328b7cf0347057a9944e081627135a9aa3d2178 |
| expert-focus-group-interaction-quality | a08de475a427660f1d0d90d76d2d0401b137567f8ee464648776f736e3d28c52 |
| expert-focus-group-interaction-limits | 1ae6ecc9e2de687e4fd6c4934c300932cc03ddb3395d3d0dd5c0b8e8318e4ddd |

Optional COR08/GRP08: B2, commit 5c40a0d3065f77039bad87a88eac91cbf6020d55; raw hashes in fixed common source table. Read cor/grp-stages/slots/hooks only when quant selected. Future B3 wrapper hashes excluded. New3 hashes fixed in coordinator manifest; no mutual wrapper-hash links.
