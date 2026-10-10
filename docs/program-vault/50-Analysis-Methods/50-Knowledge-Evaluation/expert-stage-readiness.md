---
note_id: analysis-expert-stage-readiness
note_type: knowledge-evaluation
title: 17専門家の段階別充足・不足表
summary: currentPack暫定方式の17定義・責務・参照・adapterを固定し、文書確認と方法論・研究者採否を分ける。
status: proposed
schema_version: 1
expert_ids: [exp-qualitative-content-analysis, exp-thematic-analysis, exp-framework-method, exp-scat, exp-m-gta, exp-kj-method, exp-quantitative-text-analysis, exp-focus-group-interaction, exp-participation-balance, exp-conversation-timing, exp-descriptive-statistics, exp-group-comparison-statistics, exp-correlation, exp-embedding-topic-exploration, exp-speech-emotion-recognition, exp-japanese-text-preprocessing, exp-cross-session-comparison]
stage: registration
review_state: draft
runtime_state: planned
case_ids: [G1B-TA-01, G1B-TA-02, G1B-TA-03, G1B-TA-04, G1B-TA-05, G1B-TA-06, G1B-COR-01, G1B-COR-02, G1B-COR-03, G1B-COR-04, G1B-COR-05, G1B-COR-06, G1B-GRP-01, G1B-GRP-02, G1B-GRP-03, G1B-GRP-04, G1B-GRP-05, G1B-GRP-06]
updated: 2026-10-10
tags: [gurumoji/analysis, gurumoji/evaluation]
---

# 17専門家の段階別充足・不足表

### 2026-10-10 — Coreのrole・物理所属境界を固定受入、実モデル評価は別ゲート

- 公開固定 `a0a2e0dc34c37fa3e1c2bd7cb0142bd37598f95b`（親fb997）の既存service・adapter・新testを選別した。Windows109unique PASS（新26＋既存Core24＋選択59、旧14内包）、role3拒否、物理所属1境界のgetter/execute各roleと正当foreign対照6、欠落参照/ID4、独立来歴17、codec80、型境界4と上限拒否2を確認。証拠583fileを照合した。旧role2FAILと物理所属4観測FAIL、reviewer/fixtureの初回失敗・限定訂正は保持し、再実行を成功件数へ加算しない。
- 合成323件・9scope・31wireと原raw/task/decision/labelを保持し、Store7保存後のfresh全member bytes一致と、生成identityを固定した新旧normal31の同等性を確認した。getterはreadonly、無関係foreign本文は配送しない。schema追加/変更・入力切捨て・予算拡大・新schedulerはない。
- 前固定版の31wire CPU容量は全件24576以内（最大23601、余裕975）、別作者543整合性＋24decoder確認を受入済み。短い合成出力によるCPU計測であり、新sourceでの容量・有限実行票・実Gemma全323本文配送/3安定完了は別受入とする。G0.5実raw比較18件は全品質FAIL、正式比較/cache/currentPack/本人採否の制約を維持する。G5の方法意味品質は型の成功で代替せず、PNG延期も維持する。


### 2026-10-10 08:04 JST — 17専門家CPU境界を固定受入、意味品質と本人採否を分離

- 公開固定 `2b9f07a7ef52ca5aba026fefa1f19cfbe0e491c4`（親4d92）の方法レビュー＋新合成testの2pathを選別。Linux18unique PASS、別作者Windows18＋独立4境界PASS、証拠924file＋固定Git対応894sourceを照合した。反復を成功件数へ加算しない。原410doc行、17定義・入力source hash、AI許可9／禁止8／106段階と既存production／Core testsを保持する。
- 9許可専門家では、不適切な一般化・因果・信頼性主張も構造的には `accepted_unreviewed_draft` となる限界を再現した。テストPASSはその境界確認であり、負例の意味上の合格ではない。禁止8のAI拒否、型付きsource／producer／未読、数値binding改変拒否は別に確認。独立C1は実Handler→隔離SQLite→freshでも未確認draft・採択decision空を保持。archive Store全統合、実モデル出力・方法意味品質・研究者本人の採否はこの票で未受入。
- 別の実G0.5b/c raw比較18件は全plan FAIL、code／explanation0、原応答拒否5、既知235132tokensとして閉鎖。事後CPU再計数の整合成功を実測時配列の保存に置換しない。cache UNKNOWN／正式比較HOLD／currentPack暫定を維持する。Gemma全323件のCore最終入力は合成31wireの1件が24624>24576で容量FAIL、実モデル成功は未確認。Dot同backend ownerが可逆wire修正を継続し、入力上限拡大・本文切捨て・未読の読了化を行わない。PNG延期と人の採否待ちを維持する。


G1b-entry-02（Task `task_04f5c063165c`、Run `run_9bb051ea8c4b`、owner W-knowledge）の一Markdown正本。定義の存在、方法論の適否、実行接続、人の採否を別判定で保持し、17×段階のノートを量産しない。書式は [[90-Templates/knowledge-evaluation]]、表示補助は [[50-Analysis-Methods/50-Knowledge-Evaluation/knowledge-readiness.base]]。

## 固定対象と確認範囲

2026-10-10 07:44 JST追補：DotのCore配送 `95a33e9acb85348f1c94982b6ff75abee090d9ff` をWindows新24／隣接9／独立負例19、実serviceの323件・9scope・Handler／Store保存／fresh、23wireの全ID順序・採択Core参照5・保存raw14の照合後に限定受入した。C0は1429artifact＋Git対応1328sourceを照合した。旧wire前提14methodは別のtest-only固定 `4d92d0a45dcede55ebb1c991343fe12a2a8295f3` へ移行し、Windows関連97unique（初回96成功＋固定資料の抽出不足1件のみ再実行成功）と独立6成功、932artifact＋親／候補892sourceを確認。初回失敗と旧7FAIL／8ERROR、他59method AST、production全体／新Core24不変を保持した。未採択履歴・明示依存・clarification・統計・blindの配送、保存全raw／来歴を維持し、検証を緩和していない。実本文の全wire容量、実Gemma全323件と安定3回、意味品質、研究者本人の採否は別ゲートで未受入。Dotは既存方法レビューの17節にある未実行合成例のCPU検証へ同ownerで継続し、AI許可9／禁止8、下書きと本人確定、未実行を分離する。

2026-10-10 06:55 JST追補：Framework説明 `4310b2eb862854e3f62f636b757be9f6f522f409` はWindows新7＋別作者独立4＝11PASS、208artifact＋198の親／候補source hashをC0が照合し限定統合した。3message以外の全定義、6／5／7段階、actor・AI権限・min2／block・version1は不変、知識hash更新で旧AI文脈をstale拒否する。研究者が定義するケース数と現製品の話者条件を区別する説明の受入であり、Framework一般の適否・方法意味品質・研究者本人の採否は未承認。Core配送の追加修正はDotが隔離3pathで実着手、修正後G0.5b/cの新raw-only固定版は独立CPU71／模擬wire125／実行入口19項目を確認済みだが、新実推論と実品質は別受入とする。

2026-10-10 06:44 JST追補：通常fullapp1440／390から実比較builder／API、Handler／archive／Store保存、fresh画面／Store、ZIP／全14artifactのbytes一致まで別作者が2条件PASS。390pxでは実横wheel0→371で右端列を確認した。固定 `f2462ab5e066679b340c78f2f65208a445cdc942` の261artifact＋168source hashをC0が照合し、対象0／既知0／不明と保存原版を維持する画面・保存経路を限定受入した。初回browser／shell記録失敗と最終sandbox有効／audit exit0を分離する。研究者本人の理解・方法採用の合格ではない。

明示receipt付きM_extended固定 `ab7c674fdab6e9e47aea1b76890b8505066e4530` は別作者Windows54＋独立3＝57PASS、旧legacy／Mの期限・hash・費用不変をCPU限定受入した。推論の再許可ではない。保存本文の最終非実装projectionでもCore29=24648／Core31=25152>24576で容量FAIL、Dotへ既存Core配送境界の追加3path修正を正式割当し、固定版・Windows独立受入・実本文容量の再確認を待つ。Framework説明 `4310b2eb` はLinux作者7＋隣接4／独立7＋1を受領しWindows独立検証中。修正後G0.5b/cは旧18FAILを保持する別IDのraw-only比較としてCPU準備中で、currentPack暫定・strict形式HOLD・方法意味品質・研究者採否を未受入のまま分ける。

2026-10-10 06:23 JST追補：保存比較のHTTP修正 `ed6ca0b59baf740d01806fb9c80b278206fa61c2` は別作者Windows15、実Flask→Handler→archive→Store保存→fresh ZIP／全14artifact取得、破損409・通常欠落404・stale保存原版のbytes維持を限定受入した。通常fullapp画面→実比較builder→保存→freshと390px実横gestureは別担当が追加検証中。配送修正ec85はWindows32＋独立2PASSだが、実保存本文を用いた短い合成reportのCore進行では後半入力が上限を超え、最大36830>24576となった。全323本文配送・実モデル成功・安定3回は未達、上限緩和や無断切捨てを行わず既存Core履歴の重複配送をCPU解析する。

統計注記 `30df9733c1603f39d69eb86efa56dad207c66917` はLinux作者72／別作者11と、C0別作者Windows11＋旧版対照6条件（通常・小標本・同順位・定数・欠測・未計算）を区別して確認した。Kruskal現式 `max(0,(H-k+1)/(N-k))` と互換名称未確定、Spearman小標本漸近p値の注意を新規注記へ追加し、数値・schema・status・nullと保存済み旧hashを維持する限定受入である。Frameworkの話者gate／ケース数説明は後続、効果量名称の方法論的正規化・方法意味品質・研究者本人の採否は未受入。初期18実測の失敗とcurrentPack暫定／strict形式HOLDは維持する。

2026-10-10 06:00 JST追補：以下の時刻付き記述と表は各時点の履歴として保持する。G0.5b/cの初期固定18比較は実Gemmaで実測済みになったが、全18の計画応答が既存Handler検証で隔離され、独立品質判定は18FAIL／0PASS、不必要拒否9だった。正式計算・結果説明は0件、研究者採否は未実行。全18の実入力とusageは確認済みで、合計229284token／試行時間合計2516.650281秒（失敗を含む）。cache／KV再利用はUNKNOWNのまま旧strict形式のvalid=false／HOLDを維持し、currentPack暫定と新方式未採用を変更しない。後保存のpreflight再生成が原formalとCPU完全一致しても、実行前memoryobjectの原本保存証明とはしない。

会話間比較の観測分母はDot固定 `b1c2fc5805f7ef8f2ca2470879dd8be37e874ac3` をWindows関連25＋独立11PASS後に限定統合した。対象0はnot_applicable、妥当な空予測は既知0、欠落・不正来歴はunknownとして、旧率・元scopeを維持する。通常表示は独立DOM／境界／1440・390の限定受入済みだが、修正backendとの通常画面／保存／fresh／HTTP取得の全経路は追加確認中。保存済み比較runのHTTP404は親にもある独立不具合としてDotが別修正中。無関係な過去結果本文の配送修正 `ec85dce2fcbbb5dfd89e67342463ea702c35e1d6` はLinux作者・独立結果を受領し、Windows受入中である。実323本文の配送・安定3回・意味品質の合格証明にはしない。

2026-10-10 05:04 JST追補：下表は作成時の状態を保持する。公開固定 `89aa95844d911ea8e1abee6337cc4f4b229e439d` の17定義について、Dotの [[50-Analysis-Methods/50-Knowledge-Evaluation/expert-methodology-review]]（固定 `2793c91d844331f01c25b1e7fd917a1b47f4175a`）を別作者が照合した。現行の明示07は5（TA・統計3・FGI）、AI許可9／禁止8、既定C1のAI許可は4、08 readerは統計3とTAの4である。下の「07は4」「既定C1は5」や08未接続等の旧記述を、現行版の件数・未実装判定として利用しない。版・raw hash・actor／step・局所参照の一致は文書・契約の整合性であり、方法品質や研究者の採用の証明ではない。

利用者の再開指示後に実Gemmaの323件試験を1回実行したが、最初のCoreがtransport timeoutで失敗し、専門家へ実送信できた本文は0／323だった。使用量不明と予約は保持し、CPU原因修正・独立検証を継続中。G0.5b/cの実比較は未実行で、currentPack暫定を維持する。17専門家の意味品質・実モデル品質・研究者採否は未受入。方法論票の3群のうち、会話間比較のモデル出力観測分母はDot backend／C0表示の別ownerで実装中であり、保存旧結果の不明を0に補完しない。統計式の呼称・近似条件とFrameworkの製品gate／ケース数の説明は後続の限定修正対象とする。

2026-10-10追補（FGI一専門家・CPU契約のみ）：Dot `de601683175fa2a115f9f256313801a07a4401ae` を統合した固定 `0ff1a84f529e24ee73df8ce476bf9f70eb034523` で、別作者の独立20件（10.614秒）と旧隣接5件（0.729秒）が各PASS、FAIL/ERROR/SKIP0。明示S1の既存Handler→raw保存→実AnalysisStore.save→freshと、実UNKNOWN／単一話者の解釈agent呼出0を確認した。receipt SHA256 `ba1da647dea28956531899db98adbe94cf9b6abf580ac82b26fa60885ea1afe9`。旧18PASS／2FAILは保存し修正版だけを受入。FGI既定C1は維持し、HumanRecord採用・手動リンク変更・新asset登録はない。実モデル／意味品質／方法論の適否／研究者採否／残る専門家のG5評価は未実施で、表全体のdraft/plannedとcurrentPack暫定・G0.5b/c未測定を維持する。

| 対象 | 取得元ID・版・hashと確認範囲 |
| --- | --- |
| 実装 | root `0fbfb402af9d9bdd18a495565288bf5ed273d5f4`。a06 C0 `task_294ab89afad8`、source9 manifest `4bdd59dda62ab66ed3f04448aae83b5de003694278cf46355780adee93458859`。統合301件/142.796秒成功はpacket引用、本票が再実行した結果ではない |
| F02/G1a | `task_2cc8fa88356d`、canonical本文 `msg_ecfa490b44ad`。236 sourcehashの元参照 `msg_499194e7cc84` / `msg_ea3e223ff567` / `msg_0f5376a16614` / `msg_40b6664b4408`。前付/存在/hashであり、新しい文献読了・研究採用ではない |
| 書式・入口 | entry01 `task_cadb2f0361f8`、commit `0ed172bc6a1819c4158f422d9d2672043cb78d47` の3テンプレートと既存indices。hook indexはa06後workingtree更新版を参照 |
| 配信方針 | C0 `task_e1044a47e1e6`、2026-10-07 22:16:55 UTCの `currentPack` 暫定維持。新方式は `notadopted`、b/c未測定。b/c実測を本票の依存へ追加しない |
| 初期票根拠 | 6ID/25リンク/3YAML/Base2viewsの静的確認、Obsidian 1.13.7隔離fixtureの17行表示成功はentry01の根拠。今回の充足/新3binding表示/08 readerの合格証拠ではない |
| 今回の取得 | Windows local・baseのみ。17の01、存在する4の07、必要なCatalog/Registry/adapterと選択依存metadata。個人上書き・実run・モデル/解析器・研究者ノートは未確認 |

review_state=draft、runtime_state=plannedを維持する。未読、人未確認、未実行、unsupported、意味undeterminedを成功や欠測0に変えない。文書レビュー、合成経路、実モデル、研究採否の各証拠を別に扱う。

## 共通のkind・scope・参照役割

D=01 definition_version、C=07 contract_version、S=07 schema_version。AI=ai_draft、R=researcher、K=code。必要段階/actorは01の要求を表示したもので、実施証明ではない。

| 軸 | 必要な照合と確認根拠 |
| --- | --- |
| kind | 5種 observation_table / claim_set / relation_graph / event_sequence / embedding_matrixへの論理対応候補。現行wireのkindや汎用schemaを新設する宣言ではない |
| role | DI=data_input（対象）、SB=selection_basis（選択根拠）、EC=evidence_context（原文/媒体/前後）、PS=parameter_source（問い/採用定義/条件）。実行receiptを観測値/原文根拠にしない |
| scope | autonomous計算は固定初期会話の全対象。統計all_included_initial、pipeline全snapshot。区間/横断の汎用adapterはunsupported。方法論の全体精読を任意scope能力と同一視しない |
| source/use | 01 step/basis、07、00〜06、common_notes、literatureをID/版/raw hashで固定。用途は計画/候補生成/照合/人の採否。送信可否・必要媒体は既存依頼で確認し、文書から権限を増やさない |
| 知識確認 | T/A/B/Oは文献前付のfull_text/abstract/bibliographic/official_pageという既存確認範囲。今回の作業者やモデルの読了ではない。全定義のmethodology adequacyとhuman_reviewの新評価は未実施 |

共通接続は [[40-Design/obsidian-skill-knowledge-blueprint#15. 任意の登録済み分析を結ぶ共通接続（実装対象）]] と [[40-Design/core-handler-routing-reorganization-plan]]。以下の各行にもこの共通条件を必要とする。

## 17定義の必要段階・責務・不足

| 専門家・D/C/S・AI許可・method | 必要段階・actor | kind・単位・scope／参照role | 知識の確認根拠と不足 | 現行adapter・不適合理由／次工程 |
| --- | --- | --- | --- | --- |
| [[50-Analysis-Methods/10-Experts/qualitative-content-analysis/01-Expert\|exp-qualitative-content-analysis]] D1/既定C1/07なし・可。qualitative_content | 問い/流派→カテゴリ候補→定義規則→割当候補→見直し/品質/報告。AI=qca-p3,qca-p5；R=qca-p1,qca-p2,qca-p4,qca-p6,qca-p7,qca-p8 | claim_set／採用コードobservation_table候補。発話（turn）。意味単位が発話と一致しない場合は研究者が注釈で扱う。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 8参照 T1/A5/B2/O0。前付/存在/hashのみ。質的内容分析の日本語の方法論文献を今回の検索では見つけていない；Mayringの手順図（Fig.1, 2）と、本文が参照するドイツ語の教科書を読んでいない。人の適否未評価 | 既存AI汎用下書き/手動codebook。意味単位設定の専用支援なし。流派/規則/信頼性の人判断→G2 |
| [[50-Analysis-Methods/10-Experts/thematic-analysis/01-Expert\|exp-thematic-analysis]] D2/C1/S1・可。thematic | 全体精読→code→候補→レビュー→定義命名→報告。AI=ta-p2,ta-p3；R=ta-p1,ta-p4,ta-p5,ta-p6 | claim_set候補。データセット全体（テーマは発話ごとの値ではない）。根拠として発話IDを参照する。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 6参照 T4/A2/B0/O0。前付/存在/hashのみ。Braun & Clarkeの書籍を読んでおらず、最新の6フェーズの記述と2006年の論文との差を本文で確認していない；岡ほか 2022で、フェーズ2とフェーズ4の具体的な問いの記述位置を特定していない。人の適否未評価 | 7string＋claim/evidence。テーマID・支持/反例・履歴の専用構造未完→3試行/G2/G3 |
| [[50-Analysis-Methods/10-Experts/framework-method/01-Expert\|exp-framework-method]] D1/既定C1/07なし・可。framework | 精通/逐語録→coding候補→枠組み→適用→chart候補→解釈。AI=fw-p3,fw-p6；R=fw-p1,fw-p2,fw-p4,fw-p5,fw-p7 | observation_table／claim_set候補。ケース（話者、属性、グループ）×カテゴリーの行列のセル。根拠は発話ID。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 5参照 T2/A2/B1/O0。前付/存在/hashのみ。Ritchie & Spencerの原典（書籍の章）を読んでおらず、出版年も確認していない；フレームワーク法の日本語の方法論文献を見つけていない。人の適否未評価 | 既存AI候補。case_code_matrixは発話件数で、chart要約保存は未対応→G2 |
| [[50-Analysis-Methods/10-Experts/scat/01-Expert\|exp-scat]] D1/既定C1/07なし・可。scat | 準備→注目語句候補→言換え/概念/テーマ→追加例候補→story/理論/疑問。AI=scat-p2,scat-p6；R=scat-p1,scat-p3,scat-p4,scat-p5,scat-p7,scat-p8,scat-p9 | observation_table／claim_set候補。セグメント（一つのセグメントに大きく一つのトピック）。Gurumojiでは発話を目安とし、区切りは研究者が確認する。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 4参照 T1/A1/B1/O1。前付/存在/hashのみ。原典論文（大谷 2008）の本文を読めていない（画像のPDF）；福士・名郷 2011の短い回答への活用法を読んでいない。人の適否未評価 | 既存汎用候補。〈1〉〜〈5〉matrix専用画面なし。原典/短回答は人判断→G2 |
| [[50-Analysis-Methods/10-Experts/m-gta/01-Expert\|exp-m-gta]] D1/既定C1/07なし・可。mgta | テーマ/焦点者/精読→具体例/反対例候補→memo/カテゴリー/飽和/図。AI=mgta-p4,mgta-p5；R=mgta-p1,mgta-p2,mgta-p3,mgta-p6,mgta-p7,mgta-p8,mgta-p9 | claim_set／relation_graph候補。分析テーマと分析焦点者に沿って着目したデータの箇所（切片化しない）。発話IDはヴァリエーションの根拠として参照する。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 4参照 T2/A1/B0/O1。前付/存在/hashのみ。木下の書籍の手順の詳細（結果図の描き方、カテゴリーの生成の具体例）を読んでいない；M-GTAの査読付きの方法論文献を確認していない（読んだのは講演に基づく紀要論文と研究会のページ）。人の適否未評価 | 既存汎用候補。テーマ/焦点者/worksheet専用入力なし。追加収集は範囲外→人/G2 |
| [[50-Analysis-Methods/10-Experts/kj-method/01-Expert\|exp-kj-method]] D1/契約なし・禁止。kj | 準備→ラベル→編成→表札→配置→図解/文章→衆目評価。R=kj-p0,kj-p1,kj-p2,kj-p3,kj-p4,kj-p5,kj-p6,kj-p7,kj-p8,kj-p9 | claim_set／relation_graph候補。ラベル（1つのメッセージ）。発話IDをラベルの通し番号に対応させる。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 4参照 T2/A0/B2/O0。前付/存在/hashのみ。川喜田の書籍（1967、1986、1997）の本文を読んでいない；KJ法の査読付きの方法論文献を確認していない（読んだのはインタビュー記事と研究会の報告論集）。人の適否未評価 | AI禁止。ラベル編成/図解の専用機能なし。類似clusterで代替不可→研究者/G2 |
| [[50-Analysis-Methods/10-Experts/quantitative-text-analysis/01-Expert\|exp-quantitative-text-analysis]] D1/契約なし・禁止。quantitative_text,lexical_frequency,cooccurrence,speaker_characteristics,kwic | 問い/概念→解析固定→計算→KWIC往復→規則/報告。K=qta-p2,qta-p3；R=qta-p1,qta-p4,qta-p5,qta-p6 | observation_table／relation_graph候補。発話（文書）。語はGiNZA／SudachiPyの内容語。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 11参照 T2/A5/B2/O2。前付/存在/hashのみ。樋口の書籍（2014）を読んでいない；Gurumojiには辞書・コーディング規則による自動コーディングの機能がない。人の適否未評価 | 既存語彙/共起/KWIC表示。autonomous再発注adapterなし、辞書coding/特徴語検定なし→G2/G4 |
| [[50-Analysis-Methods/10-Experts/focus-group-interaction/01-Expert\|exp-focus-group-interaction]] D1/既定C1維持・明示S1/C2/S1・07あり。interaction | 話者/順序/役割→内容と分離→応答候補→人確認→少数意見候補→比較/報告。AI=fgi-p3,fgi-p5；R=fgi-p1,fgi-p2,fgi-p4,fgi-p6,fgi-p7 | relation_graph／event_sequenceは論理候補。明示S1はreport-onlyの閉鎖候補でasset登録なし。snapshot順の2〜16異なる発話IDと原文hash、1会話dataset全体の実配送を照合／DI,EC,PS（対象選択時SB） | 12参照 T4/A8/B0/O0。前付/存在/hashのみ。Kitzinger 1994の本文を読めていない（出版社サイトが403）；Onwuegbuzie et al. 2009の枠組みの項目を確認していない（要旨のみ）。人の適否未評価 | 既定C1/手動interaction_links維持。明示typedのHandler・保存・freshを限定CPU受入、human_pending。実話者/役割/順序不足はモデル前拒否、本文配送不足は成功draft不可。非言語・意味品質・人採否は未検証→G2/G3 |
| [[50-Analysis-Methods/10-Experts/participation-balance/01-Expert\|exp-participation-balance]] D1/契約なし・禁止。participation | 役割/分母→数/時間→偏り計算→解釈。K=part-p2,part-p3；R=part-p1,part-p4 | observation_table。話者（司会者・運営役を分母から除く設定あり）と属性群。値は発話の集計。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 7参照 T3/A3/B1/O0。前付/存在/hashのみ。Gini係数・evenness・HHIを会話の参加の偏りに使うことの妥当性を検討した文献を確認していない；Stephan & Mishler 1952は書誌のみの確認。人の適否未評価 | 固定snapshot participation adapterあり。名簿不明はnull、無発言者の個人一覧なし。会話妥当性は人→G2 |
| [[50-Analysis-Methods/10-Experts/conversation-timing/01-Expert\|exp-conversation-timing]] D1/契約なし・禁止。conversation_dynamics | 閾値→遷移/間/重なり→音声と前後→意味/件数を分離。K=time-p2；R=time-p1,time-p3,time-p4 | event_sequence／observation_table候補。文字起こしのセグメントの開始・終了時刻。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 6参照 T2/A4/B0/O0。前付/存在/hashのみ。Heldner & Edlund 2010は要旨の一部だけを確認し、既存ノートの記述（閾値・統計処理の問題）を裏付けていない；日本語の会話のターン間の間や相づちの研究を確認していない。人の適否未評価 | 固定snapshot conversation_dynamics adapterあり。無効/欠測時刻を補完しない。意味は音声/文脈待ち→人/G3 |
| [[50-Analysis-Methods/10-Experts/descriptive-statistics/01-Expert\|exp-descriptive-statistics]] D2/C2/S2・可。descriptive_statistics | 研究者の変数/欠測→AI計画→正式計算→AI説明→人の分母/意味確認。AI=desc-ai-plan,desc-ai-report；K=desc-p2；R=desc-p1,desc-p3,desc-p4 | observation_table／説明候補。発話（比較軸は話者または役割）。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 3参照 T0/A2/B0/O1。前付/存在/hashのみ。記述統計そのものの方法論文献は置いておらず、公式API定義と実装が主な一次資料になっている；Appelbaum et al. 2018は要旨だけを確認し、訂正記事の内容を読んでいない。人の適否未評価 | Handler descriptive_statistics/frequency_statistics、S2/C2/必須step/セル束縛あり。人record取得unsupported、human_pending。任意表/新label未対応→G2/G4 |
| [[50-Analysis-Methods/10-Experts/group-comparison-statistics/01-Expert\|exp-group-comparison-statistics]] D2/C2/S2・可。group_statistics | 研究者の群/変数→AI計画→正式計算→AI説明→期待度数/入れ子/探索判断。AI=grp-ai-plan,grp-ai-report；K=grp-p2；R=grp-p1,grp-p3,grp-p4 | observation_table／説明候補。発話（群は話者または役割）。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 12参照 T3/A4/B5/O0。前付/存在/hashのみ。カイ二乗検定の期待度数の基準の文献（Cochran 1952、1954）は書誌のみの確認で、20%の目安は実装上の判断；Welch型の検定、多重比較の補正、入れ子を考慮したモデルは未実装（計画：quantification-statistics-plan）。人の適否未評価 | Handler crosstabs/anova/kruskal_wallis/chi_square、S2/C2あり。Welch/補正/入れ子モデルなし。人未確認→3試行/G2/G4 |
| [[50-Analysis-Methods/10-Experts/correlation/01-Expert\|exp-correlation]] D2/C2/S2・可。correlation | 研究者の変数対/種類→AI計画→正式計算→AI説明→外れ値/探索/因果判断。AI=cor-ai-plan,cor-ai-report；K=cor-p2；R=cor-p1,cor-p3,cor-p4 | observation_table／説明候補。発話。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 7参照 T0/A4/B2/O1。前付/存在/hashのみ。変換や並べ替え検定による相関の検定は未実装；Spearman 1904とHolm 1979は書誌のみの確認。人の適否未評価 | Handler pearson/spearman、S2/C2あり。変換/並替/補正なし。因果/一般化undeterminedはhuman_pending→3試行/G2/G4 |
| [[50-Analysis-Methods/10-Experts/embedding-topic-exploration/01-Expert\|exp-embedding-topic-exploration]] D2/契約なし・禁止。transformer_topics | モデル固定→埋込/cluster→原文/名/反例/適合→検索/割当。K=emb-p1,emb-p2,emb-p6；R=emb-p3,emb-p4,emb-p5 | embedding_matrix／observation_table候補。文脈付き発話（短い断片は同じ話者の3秒以内の隣接発話で補う）。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 9参照 T1/A5/B2/O1。前付/存在/hashのみ。multilingual-e5の技術報告はプレプリントで、日本語の会話の逐語録での評価を確認していない；トピックの人による解釈を扱ったChang et al. 2009の内容を読んでいない（書誌のみ）。人の適否未評価 | 既存Transformer保存/検索。autonomous再発注adapterなし、今回推論未実行。clusterは確定TAではない→人/G2/G4 |
| [[50-Analysis-Methods/10-Experts/speech-emotion-recognition/01-Expert\|exp-speech-emotion-recognition]] D1/契約なし・禁止。audio_emotion | 音声/モデル固定→推定/集計→短区間/未推定→聴取/限界。K=ser-p1,ser-p2；R=ser-p3,ser-p4 | observation_table候補。話者分離後の発話音声の区間。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 7参照 T1/A2/B3/O1。前付/存在/hashのみ。JTESの論文本文と収録条件（演技か自然な発話かなど）を確認していない；いざなみのモデルカードを確認していない。人の適否未評価 | 既存音声モデル。autonomous再発注adapterなし、今回推論未実行。本人感情確定ではない→人/G2 |
| [[50-Analysis-Methods/10-Experts/japanese-text-preprocessing/01-Expert\|exp-japanese-text-preprocessing]] D1/契約なし・禁止。morphology,syntax | 解析器/設定/版→ID付き解析→fallback区別→人の監査。K=pre-p1,pre-p2,pre-p3；R=pre-p4 | observation_table／relation_graph候補。形態素（トークン）と形態素間の係り受け。発話ID・文ID・トークンIDで対応させる。固定初期会話の全体（汎用区間なし）／DI,EC,PS（対象選択時SB） | 6参照 T0/A0/B5/O1。前付/存在/hashのみ。話し言葉の逐語録での形態素解析・係り受け解析の精度を扱った文献を確認していない；Gurumojiが実際に読み込むGiNZAのモデル（ja_ginza か ja_ginza_electra か）をこの定義では確認していない。人の適否未評価 | 既存GiNZA/Sudachi/簡易fallback。簡易syntax不可。実モデル可用性未測定、autonomous再発注adapterなし→G2/G4 |
| [[50-Analysis-Methods/10-Experts/cross-session-comparison/01-Expert\|exp-cross-session-comparison]] D1/契約なし・禁止。interview_comparison | 2会話以上/同一設計→集計比較→原発話→比較限界。K=cmp-p2；R=cmp-p1,cmp-p3,cmp-p4 | observation_table候補。インタビュー（会話・グループ）。値の根拠は各会話の集計。2会話以上の別run／DI,EC,PS（対象選択時SB） | 5参照 T2/A3/B0/O0。前付/存在/hashのみ。複数のフォーカスグループを比較する分析の方法論文献を確認していない；比較に必要な会話の数の基準を扱った文献を確認していない。人の適否未評価 | 既存interview_comparison別run。個人仮説検定や共通bindingの自動再利用ではない→人/G4 |

^readiness-17-stages

定義17、AI許可9/禁止8、明示07は4（TAと統計3）、AI許可で07なしの既定C1は5。AI禁止8の07不在を「既定契約で実行可」と数えない。保存出力registryの正本は22 method（担当専門家あり14/なし8）。分析方針ID・保存method・正式toolは別集合で、17定義と22 methodの一対一対応を要求しない。旧入口の「19手法」は古い局所記述として正本22と区別する。

## F02の修正対象3行と継承範囲

| 行 | F02基準 | 現行commitによる補正 | 継続する保留 |
| --- | --- | --- | --- |
| exp-descriptive-statistics | D2/C1、a修正待ち | D2/C2/S2。計画AI desc-ai-plan/R desc-p1、説明AI desc-ai-report/K desc-p2/R desc-p1,p3,p4。必須phase集合・数値9キー/statistical-cells-v1 | 人record取得unsupported/human_pending。方法論本文・自由文の意味・実モデル・採否未評価 |
| exp-group-comparison-statistics | D2/C1、a修正待ち | D2/C2/S2。計画AI grp-ai-plan/R grp-p1、説明AI grp-ai-report/K grp-p2/R grp-p1,p3,p4。同じphase/セル検査 | Welch/補正/入れ子モデルなし。因果/一般化/有意行の選択の未判定を解除しない |
| exp-correlation | D2/C1、a修正待ち | D2/C2/S2。計画AI cor-ai-plan/R cor-p1、説明AI cor-ai-report/K cor-p2/R cor-p1,p3,p4。同じphase/セル検査 | 変換/並替/補正なし。因果/方向/話者内と間/探索的選択は人判断待ち |

^readiness-f02-three-corrections

他14行の方法論・不足はF02を継承し、新しい文献適否調査や実モデル評価を宣言しない。TAはD2/C1/S1の既存契約で統計2phaseを追加しない。統計07はa04実装・a06限定CPU受入を現行説明として反映し、a03時点のloader拒否は作成時の確認記録として保持する。C0がF04独立・文書レビュー後に本文を狭く修正し、08のraw参照hashを再束縛した。01と07の実行YAMLは変更せず、一般意味検出と研究者recordの未対応を維持する。

現行obsidian-expert-agents-3/statistical-tools-1はAI必須集合・step/actor・型/重複、同runの正式code結果と提供セル、既知禁止断定を検査する。自由文の意味判定は完成していない。AI自己申告/Core採用/数値一致は本人recordの代用にならず、構造成功をmethodology adequacyやhuman_reviewの合格にしない。

## ID・版・hashの固定台帳

01/07のraw byte SHA-256はbaseから取得し、今回変更しない。knowledgeは既存Catalogの00〜06＋共通＋文献の集合hashで07 raw hashとは別。F02当時/今回開始/入口追記後/実run固定profile・個人上書きを混同しない。

| expert／01 note ID・版 | 01 raw SHA-256 | 07 note ID・S/C／raw SHA-256 | 今回開始base knowledge hash |
| --- | --- | --- | --- |
| exp-qualitative-content-analysis / expert-qualitative-content-analysis-definition D1 | `6d38aa212b3379ce667e31d7379a3a4c3d815917b61a385f337d942e902c01ec` | なし（AI既定C1） | `sha256:1e13914bd7c07a27da35e36ecc64448903be6de1b074568942cb77b39bb195c5` |
| exp-thematic-analysis / expert-thematic-analysis-definition D2 | `26dfcdfe87323ed33fe232c8c36489f24453adb58c2b2feaa48083996147ecdc` | expert-thematic-analysis-agent-contract S1/C1 / `453adefd17b23e289352affafc4ae85d61afa1a6f094a34e774c806772050a65` | `sha256:5342ff429fa9d3d026898eafdfb01a76ecdd9d4d624ae10b1760e6a76e6c3f98` |
| exp-framework-method / expert-framework-method-definition D1 | `4d8fb1c4d26acd84d9f9486c52aa0b6e2b4f6f5427571a5b6b1289508a651d2f` | なし（AI既定C1） | `sha256:ef541971b5b9a097db76c54829eabef7c30c8d94e45bca9d8f8cda25a5f01551` |
| exp-scat / expert-scat-definition D1 | `6b24e90408a23a1bca376b697cac313f639c663558f6b68b27f9c07b561b5122` | なし（AI既定C1） | `sha256:e94dcd0dddd36ac405c4d367036d693193a2ef0c157626d625450ded831e37b5` |
| exp-m-gta / expert-m-gta-definition D1 | `fbeae854b1726cd8cdb5a63b02b0b636fe8f7a4db53c6795466ca7ab2a614b40` | なし（AI既定C1） | `sha256:3c9026a4d0f7fe9fd2510d25f72d396b8466a6e05d7c899de7aaa15fb0cddbc9` |
| exp-kj-method / expert-kj-method-definition D1 | `6da09be94b025adb2c5e60d3420a1d5f0640239a9d207c2273d8d22bd2d52c70` | なし（AI禁止） | `sha256:6a24830de165aaa76c9f159de9eff7b8dadb476b4215213ea6ce67aeb244a885` |
| exp-quantitative-text-analysis / expert-quantitative-text-analysis-definition D1 | `9258b86f28c19ba88c338591a3e8802ef8d1bb6255a959ec0d18d14d3c453fcb` | なし（AI禁止） | `sha256:ed25113abff22073239bf8c61ddb5b6777f59d749a81cdf2e7371031a1b499d4` |
| exp-focus-group-interaction / expert-focus-group-interaction-definition D1 | `502131e409de7b141a166658ee63a5935e0e1aca95efd7112f99bd9b316dde82` | 明示S1のみ expert-focus-group-interaction-agent-contract C2/S1 / `18e3f05b356806c9fe2bb625c7e7ae7d5fb20f7cf4ab002926aefe891f5f2942` | 既定C1 `sha256:aa8c00184fca3067339ef2b5999fada5a5fd7ab6bbfb41f38cd686860bbe42c6`。明示S1は固定run.profile_hashを参照 |
| exp-participation-balance / expert-participation-balance-definition D1 | `3b01cd0aff930a6cada9b26dd0075daa4bbd59d777f6a39be13eb6e1081e0bb6` | なし（AI禁止） | `sha256:767e562dcb83040515badc74223ae3014bff41ad4a430f4415259324c23c8e28` |
| exp-conversation-timing / expert-conversation-timing-definition D1 | `07d53d607a10acf1c5df8b4d6f257e77a295de673f5df933eacbd5cc552b56b0` | なし（AI禁止） | `sha256:8971a8388fb758cc6ffbb1a0d61c45fd65071b96fd7e7e7168ec5de5a9fc7858` |
| exp-descriptive-statistics / expert-descriptive-statistics-definition D2 | `08c12a57476204ac9dad8520427a4268ad67ed8eec6a35d319334f61890cbdc7` | expert-descriptive-statistics-agent-contract S2/C2 / `97a8dfc961a2c469bd22f76897b790e1bd4a5de0fcf2b6df5a4743b10412ad4a` | `sha256:3176b988abe502977875a0991f10f957005423620a5e0ccfbc0f4a255472cd18` |
| exp-group-comparison-statistics / expert-group-comparison-statistics-definition D2 | `15ac2cd8ffd7c02a9ffd8d99215a6a2a31fc1b776d3702da23e73b05f3fc9906` | expert-group-comparison-statistics-agent-contract S2/C2 / `a1ed398b0e6f759448fd4b327eccb1d672f5bada923a4f377e82f98a16ed0c5a` | `sha256:1cc6a35faefb3886ae9b5a9c39afa1d7a4afcaccc081e00f0a5911f6d565a6fc` |
| exp-correlation / expert-correlation-definition D2 | `5a499ea69a38f176a1212ab52d4fe85b8237aaf80ba6fd1b5deed148a14642bb` | expert-correlation-agent-contract S2/C2 / `92c02db1e1db0f68ed2ff0febd3b5d5615149a748bf0b2a7a534dc06478bb3d2` | `sha256:1feeff1d3ec657c7033db1aef4c99eb1edd0f9a08b2fa70331091cb2106a85f8` |
| exp-embedding-topic-exploration / expert-embedding-topic-exploration-definition D2 | `82198ae33868ccbc96773fbd087359be63b1aaee3ead1375765e8779a111bf02` | なし（AI禁止） | `sha256:6c0b90cd63ca41b747e0f8b05452c965cee1dc8a8171b57cdeaa2be954d83b0c` |
| exp-speech-emotion-recognition / expert-speech-emotion-recognition-definition D1 | `fe5853d9461963f504b329f7d6956c03c882e9fbf955c2a03b620a767164a1b9` | なし（AI禁止） | `sha256:002120f25532741a6103d337d8e424e00d473bc260c34e2112810045965e7520` |
| exp-japanese-text-preprocessing / expert-japanese-text-preprocessing-definition D1 | `8576c0202b84e1f4eccee6d99d2ef33452e68e15155f8cc223a6e769f7c16bc3` | なし（AI禁止） | `sha256:9fd6de2eabd63ab67053f9c93b139af0a687022a73cca5d66974c00926355a12` |
| exp-cross-session-comparison / expert-cross-session-comparison-definition D1 | `8f19105b11a2d3c208b892ad12285a648620e0e6083fcb39ced85d77119c837a` | なし（AI禁止） | `sha256:7d42626d5accf115abc36036f4cf25a6c0f990fbfc05eae4b2212093d9269a97` |

^readiness-source-hashes

入口追記後の3 trial base knowledge hash（旧runへ後付けしない）:

- exp-thematic-analysis: `sha256:8941432f37b57280357ef58725748ce95a9fb872b2ce18a87626f5a2936193df`
- exp-correlation: `sha256:e0a6b1f867b8b88e0c1e3fb10d700f5e66004b71176ccdadc421e2187cb70fc7`
- exp-group-comparison-statistics: `sha256:ed9cc1cf8869f8cae06c4e251936c8f63dd6ecb2a5ba9521495686a4beb4f2af`

CatalogのKNOWLEDGE_NOTESは00〜06固定で08本文・この充足表・専門家indexを自動送信しない。3 Overviewへの狭い入口追記だけが3 knowledge hashを変え、他14は維持する。currentPackは各note抜粋min(1600, 8000 // note数)とomitted_charactersを保持する。存在/hashや全ID索引は本文の実配信/読了ではない。

取得metadataは本Taskの `../artifacts/obsidian-skill-plan/revision-5/g1b-entry-02/selected-source-manifest.json`（224必要source、01/07/依存のnote ID/版は保存profileと対応定義/前付へ戻る）、SHA-256 `c99f638317a748a2dc5cf8fb313cc9ec3f385001b6a0d1498126d337114aed67`。入口追記後は `knowledge-after-entry-links.json`。F02元sourcehashメッセージを置換せず、今回のbase再取得として対応する。

## 3試行とG3へ渡す仮書式評価

| 対応票 | case ID／blockの戻り先 | 今回の範囲 |
| --- | --- | --- |
| [[50-Analysis-Methods/10-Experts/thematic-analysis/08-Skill-Hook-Binding#^ta-g3-cases\|TA登録案]] | G1B-TA-01〜06 | 正常、unknown/nonallowed、wrongscope/unit、未採用label、hash/actor違い、入力不足の期待値 |
| [[50-Analysis-Methods/10-Experts/correlation/08-Skill-Hook-Binding#^cor-g3-cases\|相関登録案]] | G1B-COR-01〜06 | 正式計算/説明、tool許可集合、発話単位、人の採否と参照の負例 |
| [[50-Analysis-Methods/10-Experts/group-comparison-statistics/08-Skill-Hook-Binding#^grp-g3-cases\|群比較登録案]] | G1B-GRP-01〜06 | 初期群/変数・原表、未対応手法、単位/scope、未採用label・actor/hashの負例 |

caseはG3の期待fixture設計へ戻すIDでruntime試験は未実行。正常例も08 reader未接続を越えてconnectedにしない。登録静的検査、既存01/07 loader、引用301 CPU回帰、今回の独立文書レビュー、新3binding GUI、実モデル、人の採否を別々に記録する。

## 保留・人の判断と次工程

| 保留対象 | 理由 | 次担当／再開条件 |
| --- | --- | --- |
| 方法論・human_review | 各行の未読原典・本文位置・日本語会話適否・流派選択に本人の記録なし。仮承認しない | 研究者が定義/入力版/根拠を固定して判断。静的成功で解除しない |
| TAの確定解釈 | ta-p1/p4/p5/p6の精読/レビュー/命名/報告、支持/反例の意味充足は未確認 | 研究者・F04/G3。AI候補と採用テーマを分ける |
| 統計の意味/確定 | 人record取得unsupported、因果/一般化/多重比較等undetermined。構造/セル照合だけでは不足 | 本人recordを既存経路で対象input/result/hashへ束縛できるまでhuman_pending |
| 08 reader/skill/callback | G1b案のみ、必須論理callback未登録blocked | G2不足整理、G3期待値、G4信頼登録ID/版・adapter/resolverの実装検証 |
| 任意成果物/新label/区間 | 任意observation_table・採用後label・区間/横断を現toolへ渡すadapterなし | G4能力検査/登録済み変換。未確定ならneeds_input/unsupported |
| 配信/実モデル/表示 | b/c未測定、Pack省略あり。独立文書レビュー/新3binding GUIは後続 | C0別票。新方式変更は別依頼版。個人Vault/実データへ拡張しない |

^readiness-holds

今回上限1.5担当h（G1b波4担当h内）。phasebudget・newbytesmanifest・所要・許可外保持・成功/失敗/未実行をOrca statusで返す。共有packet/plan/opsはC0所有のまま維持し、全G1bや知識充足全体の完成としない。


C0本文訂正（2026-10-08）：独立文書レビュー `msg_79ef761f4808` とF04独立 `msg_b1d33bd65fa4` の終了後、統計07の現行説明だけをa04実装・a06限定受入へ訂正した。実行YAMLはbyte同一。対応するraw参照hashを上表へ再束縛し、旧／新hashの対応は `../artifacts/obsidian-skill-plan/revision-5/g1b-doc-correction.json` に保持する。初回のselected-source-manifestは作者時点の履歴として維持し、現在の07はこの差分metadataで解決する。08 reader・人record・実モデルは未接続／未評価のまま。
