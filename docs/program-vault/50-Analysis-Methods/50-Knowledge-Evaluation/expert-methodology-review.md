---
note_id: analysis-expert-methodology-review
note_type: knowledge-evaluation
title: 17専門家の方法論レビューと研究者採否票
summary: 固定公開版の17定義と一次資料の実読範囲を照合し、方法論・AI候補・CPU契約・研究者採否を分離する。
status: proposed
schema_version: 1
review_state: draft
runtime_state: not_applicable
stage: methodology-review
expert_ids: [exp-qualitative-content-analysis, exp-thematic-analysis, exp-framework-method, exp-scat, exp-m-gta, exp-kj-method, exp-quantitative-text-analysis, exp-focus-group-interaction, exp-participation-balance, exp-conversation-timing, exp-descriptive-statistics, exp-group-comparison-statistics, exp-correlation, exp-embedding-topic-exploration, exp-speech-emotion-recognition, exp-japanese-text-preprocessing, exp-cross-session-comparison]
case_ids: [M33-01-N, M33-01-X, M33-02-N, M33-02-X, M33-03-N, M33-03-X, M33-04-N, M33-04-X, M33-05-N, M33-05-X, M33-06-N, M33-06-X, M33-07-N, M33-07-X, M33-08-N, M33-08-X, M33-09-N, M33-09-X, M33-10-N, M33-10-X, M33-11-N, M33-11-X, M33-12-N, M33-12-X, M33-13-N, M33-13-X, M33-14-N, M33-14-X, M33-15-N, M33-15-X, M33-16-N, M33-16-X, M33-17-N, M33-17-X]
base_commit: 89aa95844d911ea8e1abee6337cc4f4b229e439d
cpu_probe_base_commit: 4d92d0a45dcede55ebb1c991343fe12a2a8295f3
cpu_probe_state: observed_contract_only
cpu_probe_date: 2026-10-09
updated: 2026-10-09
review_timezone: UTC
tags: [gurumoji/analysis, gurumoji/evaluation]
---

# 17専門家の方法論レビューと研究者採否票

[Issue #33](https://github.com/krokharu/gurumoji/issues/33)、C0 R9 `task_4de195d99437` の文書レビュー。基点は公開 `89aa95844d911ea8e1abee6337cc4f4b229e439d`。**AIレビューは候補支援の適合性と不足の指摘であり、研究者による方法の採用・精読・確定解釈ではない。** 17専門家すべての研究者採否は未回答のままとする。


> **G5追加の読分け（2026-10-09 UTC）**: 元の17節と「今回の読了範囲」「本作業の検証」は公開R9文書の履歴を保持する。下記の「G5 CPU局所観測」と末尾のG5追加だけが `task_76c0456ec081` の新実測で、コード・定義の基点は `4d92d0a45dcede55ebb1c991343fe12a2a8295f3`。今回は一次資料を新たに読んでおらず、以前の部分読了・未読を引き継ぐ。構造受理、方法論的に不適切な合成負例、実モデルの意味品質、研究者採否を別々に記録する。

## 結論と判定の境界

- 定義のAI補助許可は**9、禁止は8**を維持する。原典がAI支援を推奨・検証したという意味ではない。禁止8分野でも既存コードの計算や埋め込み・音声モデルはあり得るが、専門家LLMへの新しい許可にはならない。
- 説明・候補生成に使える方法の骨格はある。しかし全17の方法妥当性、実モデルの意味品質、研究者採否を合格にはしない。各節は方法の主張、実装上の範囲、反例、未読を分ける。
- 優先して確認する差分は、感情推定の**件数と百分率の条件・欠測分母**、統計の**非独立性と効果量の名称・式**、Frameworkの**原典の適用範囲と製品制約の混同**。後段に最大3群の狭い実装候補を置く。今回は修正しない。

### 読み方と確認した資料

本ノートの現行実装とは上記89aaを指す。後続の公開技術候補や限定環境での計数受入は、この固定版のコード評価へ混ぜず、17専門家の意味品質・方法採用を認定する根拠にしない。

各専門家の `00-Overview`〜`06-Open-Issues` 計119ノート、存在する07計5ノート・08計4ノート、[現行readiness](expert-stage-readiness.md)を照合した。以下の定義hashは01の**raw bytes SHA-256**で、知識集合hash・profile hash・原文hashとは別。個人上書き、実runの知識、実研究データは見ていない。一次資料の「今回読んだ範囲」は各節に記録し、既存文献ノートの「本文確認」を今回の読了として転記しない。公開Webの著者原稿・出版社本文・公式仕様を2026-10-09 UTCに確認した。公式API・モデルカードの読了は研究上の妥当性の検証ではない。

「対象集合」は入力として固定した集合であり、一般化先の母集団ではない。除外・欠測・未配送・未読・未推定はそれぞれ分ける。通常の自律runの初期scopeは一会話の固定datasetで、会話間比較は別run。以下の正常例と負例は**公開用に作った合成設計例で、統合受入試験としては未実行**。別記したSER・会話間比較・参加指標の純関数確認だけは実施した。設計例は期待する停止・表示・人の判断を示すもので、現在の実装が全例を自動拒否できるという主張ではない。

段階記号はAI=候補の下書き、K=既存コードの計算、R=研究者本人の判断。AIの自己申告・Core採用・型検査・数値一致はRの代行にならない。

### 旧readinessとの差分を現行コードで限定して読む

[method_experts.py](../../../../src/gurumoji/method_experts.py) の `KNOWLEDGE_NOTES` は00〜06、`SKILL_EXPERTS` はTA・相関・群比較・FGIの4分野。[expert_agents.py](../../../../src/gurumoji/services/expert_agents.py) の `freeze/_profile` は9分野の許可を守り、currentPackを既定とし、任意の固定skill contextやtyped contractを明示選択する。

- 物理的な07ファイルは**5件**。通常currentPackで07を読むのはTAと統計3の4件。FGIは既定C1を維持し、明示typedで専用07/08を使う。AI許可で07なしはQCA・Framework・SCAT・M-GTAの4件。**07の数、9許可、17定義、22保存method、方法品質受入数は別の分母**。
- readinessに残る「07は4」「AI許可で07なし5」「08 reader未接続」は古い段階の記録。現在は4分野の固定readerがあり、TAの候補parser/callbackとFGIのreport-only候補は接続済み。相関・群比較の汎用接続callbackは別の計画状態。reader接続だけで全kindの実行adapterが揃ったとはしない。
- TA07の現raw hashは `09f3742811e56c187427ec5b7899d8f7fb9cc576f6ec36ffb26f538069aa3beb`。readiness台帳の古い `453adefd17b23e289352affafc4ae85d61afa1a6f094a34e774c806772050a65` は現bytesではない。01の17hashは各節の値へ固定した。
- [analysis_core.py](../../../../src/gurumoji/analysis_core.py) のHumanRecord検証に加え、[AnalysisStore](../../../../src/gurumoji/analysis_store.py) の `human_asset_choices/_human_contract/submit_human_record`、[HTTP経路](../../../../src/gurumoji/web/analysis_orchestration_routes.py) とUIに、TA等の保存対象に対する別の本人記録経路が実在する。AIが作るTA/FGI候補自体は `human_pending`・`not_entered`・空の本人記録を維持する。FGI report-onlyはこのTA asset採否へ自動接続せず、統計エージェントの本人記録取得は `unsupported; human_pending`。入力経路の存在と、今回の研究者採用済みを混同しない。
- [Git受け渡し記録](../../../GIT_HANDOFF.md)にあるFGIのCPU契約受入は継承する。本作業で再実行した結果ではなく、意味品質・実モデル・G5・方法採用の証明でもない。currentPack暫定、G0.5b/c未測定、Gemma full323 HOLD、PNG Store/Web/Vault延期、engineering_holdは解除しない。

## 01. 質的内容分析

- **固定定義**: `exp-qualitative-content-analysis`／`expert-qualitative-content-analysis-definition`／D1／[01-Expert](../10-Experts/qualitative-content-analysis/01-Expert.md) raw SHA-256 `6d38aa212b3379ce667e31d7379a3a4c3d815917b61a385f337d942e902c01ec`
- **許可・実行段階**: AI下書き許可。AI: `qca-p3`（定義の基準に沿って素材を読み、暫定的なカテゴリーの候補を作る）、`qca-p5`（カテゴリーを発話に割り当てる候補を作る（確定は研究者がコードブックで行う））／K: なし／R: `qca-p1`（研究質問と分析の目的を定め、分析単位と、顕在的・潜在的内容のどちらを扱うかを決める）、`qca-p2`（流派を選ぶ（先行研究がない・断片的なら帰納的、既存理論の検証や時期の比較なら演繹的））、`qca-p4`（演繹的な場合は、カテゴリーごとの定義・典型例・コーディング規則をコーディング・アジェンダにまとめる）、`qca-p6`（フィードバックでカテゴリーを見直し、主カテゴリーにまとめる）、`qca-p7`（採用した流派に応じて信頼性・信用性を確認し、その手順を記録する）、`qca-p8`（準備・組織化・報告の各段階を記述して報告する（要約的アプローチでは数えた後に文脈を解釈する））
- **分析単位**: 発話（turn）。意味単位が発話と一致しない場合は研究者が注釈で扱う
- **必要入力**: 研究質問（カテゴリーの定義の基準を決めるため）；帰納的な場合はカテゴリーの定義の基準、演繹的な場合はカテゴリーの定義・典型例・コーディング規則；本文・区切り・話者を確認した逐語録
- **現行契約**:
  - 専用07/08なし。既定C1の汎用候補出力のみ

- **対象集合・方法**: 固定した資料集合のうち研究質問に関係する側面を、帰納的なカテゴリー形成または演繹的な規則適用で整理する。現行runは一会話の固定全対象発話。turnは製品上の単位であり、方法論上の意味単位とは限らない。複数発話をまたぐ意味や一発話内の複数内容は、研究者が範囲を決める。
- **研究者だけの判断**: 流派、顕在／潜在水準、単位、カテゴリーの定義・典型例・境界規則、信頼性／信用性の評価。研究者採否は未回答。適切な計数そのものを禁止せず、件数を重要性や支持人数と同一視しない。
- **一次資料と今回の読了範囲**: [Mayring 2000公式本文](https://www.qualitative-research.net/index.php/fqs/article/download/1089/2385?inline=1) §1–7、特にpara4–7・9–18・26–28とHTMLのFig.3 coding agendaを実読。画像Fig.1・2、ドイツ語書籍、Hsieh・Elo・Graneheimの各本文は今回未読。para12・26は研究質問に沿ったカテゴリー頻度等との接続も扱う。
- **AIレビュー判定・具体的差分**: カテゴリー候補・割当候補に限定する方針は整合する。[method_experts.py](../../../../src/gurumoji/method_experts.py) の `_codebook_definitions` はdescriptionの非空だけを判定し、演繹型の典型例・境界・割当規則の充足までは検査しない。[group_analysis_exports.py](../../../../src/gurumoji/services/group_analysis_exports.py) のanalysis_unitsはsegmentの対応表で、研究者が意味単位を検討した証拠ではない。専用07なしの既定C1は任意のanalysis_premisesと必須文字列で、流派・単位・演繹規則の構造化が不足する。
- **正常例 M33-01-N（合成設計）**: u1「聞きたいが先輩が接客中」を、研究者定義「相手の業務状況による相談機会の制約」に照らして候補とし、u1と前後を根拠に付ける。
- **負例 M33-01-X（禁止・不適合）**: 「12発話あるので12人の最重要課題」「κ未計算だが信頼性確認済み」とする。
- **代替説明**: 相談の遅れは心理的な不安でなく、勤務配置や単純な多忙による可能性もある。


- **G5 CPU局所観測（4d92d0a）**: M33-01-N/Xを下記G5一覧の条件で確認。両文ともaccepted_unreviewed_draft。外部根拠ID／別profile hash／研究者stepは拒否。意味品質・本人採否は別判定で、負例の意味は不適切（FAIL）。頻度=人数・重要性、未実施信頼性の主張は禁止。

## 02. テーマ分析

- **固定定義**: `exp-thematic-analysis`／`expert-thematic-analysis-definition`／D2／[01-Expert](../10-Experts/thematic-analysis/01-Expert.md) raw SHA-256 `26dfcdfe87323ed33fe232c8c36489f24453adb58c2b2feaa48083996147ecdc`
- **許可・実行段階**: AI下書き許可。AI: `ta-p2`（コーディング（研究質問に関わる特徴に初期コードを付ける））、`ta-p3`（初期テーマの生成（コードから潜在的なテーマの候補を作る））／K: なし／R: `ta-p1`（データに精通する（コーディングの前にデータセット全体を少なくとも1回読む））、`ta-p4`（テーマの開発とレビュー（コード化したデータとデータセット全体に照らして見直す））、`ta-p5`（テーマの磨き上げ、定義と命名）、`ta-p6`（報告書の作成（分析の語りとデータの抜粋を織り合わせる））
- **分析単位**: データセット全体（テーマは発話ごとの値ではない）。根拠として発話IDを参照する
- **必要入力**: 研究質問；分析前の判断の記録（本質主義か構築主義か、経験的か批判的か、帰納的か演繹的か、意味的か潜在的か）；聞こえたとおりに書き起こした逐語録
- **現行契約**:
  - [07-Agent-Contract.md](../10-Experts/thematic-analysis/07-Agent-Contract.md): schema_version=1 / 既定contract_version=1 / 明示typedのcontract_version=2; raw SHA-256 `09f3742811e56c187427ec5b7899d8f7fb9cc576f6ec36ffb26f538069aa3beb`
  - [08-Skill-Hook-Binding.md](../10-Experts/thematic-analysis/08-Skill-Hook-Binding.md): schema_version=1 / binding_version=2; raw SHA-256 `e4677c2271ff95ccdbd053119420d20c44ac1049b3c372e30c24b747037816ef`

- **対象集合・方法**: 選定したデータセット全体を繰り返し読み、研究質問に関係する共有意味のパターンを研究者が構成する。既定は再帰的TA。現行自律runの全体は固定した一会話であり、別会話や未配送資料まで読んだことにしない。発話は根拠で、テーマを測る独立した観測単位ではない。
- **研究者だけの判断**: 理論的・認識論的立場、経験的／批判的、帰納／演繹、意味的／潜在的、データへの習熟、全体照合、定義・命名・報告。研究者採否は未回答。AIは初期コードと初期テーマの候補だけを作る。
- **一次資料と今回の読了範囲**: [Braun & Clarke 2006著者所属大学PDF](https://www2.uwe.ac.uk/services/Marketing/students/Newstudents/HAS/PG%20Psychology%20Thematic%20Analysis%20Paper.pdf) 掲載pp.81–85の事前選択、pp.86–88の導入・Table 1・習熟と転記、pp.94–96の落とし穴・Table 2を実読。25頁全体の通読ではない。[著者公式6フェーズ](https://www.thematicanalysis.net/doing-reflexive-ta/) は検索が返した本文キャッシュの6段階と前後説明、[公式Reviewer Guide](https://www.thematicanalysis.net/editor-checklist/) は同キャッシュの項目8–20等を確認。両ページの直接取得は502、2021論文本体は未読。2006の頻度の扱いと後年の再帰的TAを区別する。
- **AIレビュー判定・具体的差分**: [analysis_core.py](../../../../src/gurumoji/analysis_core.py) に定義・根拠・反例・代替説明・履歴・coverageを持つtyped候補と検証がある。固定reader・callback、[AnalysisStore](../../../../src/gurumoji/analysis_store.py) の本人記録経路も実在し、旧06の「専用欄なし」や08の未接続記述を現状としない。AI候補内の空HumanRecordと別経路の本人採否は両立する。残る不足は中心概念の一貫性、反例・代替の意味的妥当性、抜粋外を含む習熟、実モデル品質。コードブック型・信頼性型は選択肢だけで、その手順まで実装済みとしない。Hermann読了範囲の01/06と04/05にも不整合がある。
- **正常例 M33-02-N（合成設計）**: u1「質問すると無能と思われそう」、u2「一度助けてもらうと次は聞けた」から「能力評価への警戒と相談の許可感」を候補とし、全体・反例による再検討へ渡す。
- **負例 M33-02-X（禁止・不適合）**: 質問項目「相談の困りごと」をそのままテーマ、最多クラスタを重要テーマ、AI候補を本人の確定テーマとする。
- **代替説明**: 個人の評価不安だけでなく、先輩の多忙や組織の相談規範が語りを組織しているかもしれない。


- **G5 CPU局所観測（4d92d0a）**: M33-02-N/Xを下記G5一覧の条件で確認。両文ともaccepted_unreviewed_draft。型/根拠/step拒否境界は維持。意味品質・本人採否は別判定で、負例FAIL。質問項目や最多クラスタはテーマ確定・重要性の証拠ではない。

## 03. フレームワーク法

- **固定定義**: `exp-framework-method`／`expert-framework-method-definition`／D1／[01-Expert](../10-Experts/framework-method/01-Expert.md) raw SHA-256 `4d8fb1c4d26acd84d9f9486c52aa0b6e2b4f6f5427571a5b6b1289508a651d2f`
- **許可・実行段階**: AI下書き許可。AI: `fw-p3`（コーディング（1行ずつ読み、重要と解釈した箇所にコードを付ける））、`fw-p6`（行列にチャート化する（ケースごと・カテゴリーごとにデータを要約する））／K: なし／R: `fw-p1`（書き起こし（逐語録の準備））、`fw-p2`（面接に慣れ親しみ、分析的なメモを残す）、`fw-p4`（作業用の分析枠組みを作る（コードを比べて合意し、カテゴリーにまとめて定義する））、`fw-p5`（分析枠組みを以後の逐語録に適用する）、`fw-p7`（データを解釈する（分析メモを書き、ケース間・カテゴリー間の特徴と違いを検討する））
- **分析単位**: ケース（話者、属性、グループ）×カテゴリーの行列のセル。根拠は発話ID
- **必要入力**: 研究質問；インタビューのテーマ・質問項目（データが共通のトピックを含むことの確認）；比較するケースの定義；作業用の分析枠組み（コードとカテゴリーの定義）
- **現行契約**:
  - 専用07/08なし。既定C1の汎用候補出力のみ

- **対象集合・方法**: 共通のトピックを含む選定資料を、ケース×カテゴリーのセルに文脈付きで要約し、ケース内・ケース間を比較する。現行runは一会話の固定発話集合。ケースは研究者が個人・組織・グループ等として定義し、話者数と同一視しない。帰納・演繹・併用があり、最終的な解釈的テーマも生成できる。
- **研究者だけの判断**: ケースと比較範囲、枠組みの合意・適用、欠落と不在の区別、最終解釈。研究者採否は未回答。コード候補を作る段階と、確定枠組みに沿ってセル要約を作る段階では必要入力が違う。
- **一次資料と今回の読了範囲**: [Gale et al. 2013出版社PDF](https://link.springer.com/content/pdf/10.1186/1471-2288-13-117.pdf) PDF pp.1–3の用語・Background、pp.4–5のStage 1–7、pp.5–7のDiscussion・Conclusion・Summaryを実読。出版社HTMLは要旨中心の表示だったためPDFを使用。Additional File 1、図表の視覚詳細、Ritchie & Spencer原典・Goldsmith本文は未読。
- **AIレビュー判定・具体的差分**: 現01の「解釈的テーマ生成」「文書分析」を一律担当外にする説明は方法の適用範囲より狭い。Galeは議事録・日誌等も扱え、問いにより別手法が適する場合と区別する。`fw-a3` の話者2人以上は製品上の制約で、文献上の必要条件としない。[method_experts.py](../../../../src/gurumoji/method_experts.py) はケース数でなくoverview.speaker_countを検査する。[group_analysis.py](../../../../src/gurumoji/services/group_analysis.py) の `_case_code_matrix` はcode_id/label/count中心で、出典付きセル要約のチャート化を満たさない。必要なのは製品制約の明記と段階別のケース／枠組み入力である。
- **正常例 M33-03-N（合成設計）**: 同じ質問で聞いた新人A/Bを行、相談機会・支援相手を列にし、セルへ要約と発話IDを置く。「語られない」は「支援なし」にせず保留する。
- **負例 M33-03-X（禁止・不適合）**: 件数ヒートマップだけをチャート化済み、空セルを不在の証拠、13/20を母集団の支持率とする。
- **代替説明**: ケース差は職場差でなく、面接者の追問・語りの長さ・経験期間の差かもしれない。


- **G5 CPU局所観測（4d92d0a）**: M33-03-N/Xを下記G5一覧の条件で確認。両文ともaccepted_unreviewed_draft。実製品gateは話者数のまま。意味品質・本人採否は別判定で、負例FAIL。要約・文脈・ケース定義と件数は別、一般化は不可。

## 04. SCAT

- **固定定義**: `exp-scat`／`expert-scat-definition`／D1／[01-Expert](../10-Experts/scat/01-Expert.md) raw SHA-256 `6b24e90408a23a1bca376b697cac313f639c663558f6b68b27f9c07b561b5122`
- **許可・実行段階**: AI下書き許可。AI: `scat-p2`（〈1〉テクスト中の注目すべき語句を書き出す（全体を見て先にすべて書き出すのがよい））、`scat-p6`（〈5〉分析の過程で得た疑問・課題を書く）／K: なし／R: `scat-p1`（テクストをセグメント化してマトリクスに書き込む）、`scat-p3`（〈2〉〈1〉を言いかえるテクスト外の語句を書く）、`scat-p4`（〈3〉〈2〉を説明するテクスト外の概念を書く（背景・条件・原因・結果・影響・比較・特性・次元・変化など））、`scat-p5`（〈4〉前後や全体の文脈を考慮したテーマ・構成概念を書く（文ではなく名詞・名詞句））、`scat-p7`（〈4〉を紡いでストーリーラインを書く（使った〈4〉に下線を引いて漏れを確認する））、`scat-p8`（ストーリーラインを断片化して理論記述を書く（このデータから言えること））、`scat-p9`（さらに追究すべき点・課題をまとめる）
- **分析単位**: セグメント（一つのセグメントに大きく一つのトピック）。Gurumojiでは発話を目安とし、区切りは研究者が確認する
- **必要入力**: 研究質問；分析の根拠となる概念的枠組みと関連文献；セグメント化したテクスト
- **現行契約**:
  - 専用07/08なし。既定C1の汎用候補出力のみ

- **対象集合・方法**: 選定した小規模資料にも適用できるが、「小規模のみ」が方法条件ではない。現行runは一会話の固定発話集合を入口にし、研究者が意味上のセグメントを確認する。〈1〉注目語句→〈2〉言い換え→〈3〉説明概念→〈4〉構成概念、〈5〉疑問を記録し、構成概念をストーリーラインとデータに根ざした理論記述へ結ぶ。
- **研究者だけの判断**: セグメント化、〈2〉〜〈4〉、ストーリーライン・理論記述・最終課題。研究者採否は未回答。AIは原文語句〈1〉と疑問〈5〉の候補だけ。手続きの監査可能性を保ちつつ、途中へ戻る分析を禁止しない。
- **一次資料と今回の読了範囲**: [大谷2011公式PDF](https://www.jstage.jst.go.jp/article/kansei/10/3/10_155/_pdf/-char/ja) p.155 §1–3、pp.156–157の分析例の抽出テキスト、pp.158–160 §4.1–4.10・5.1–5.2を実読。表の紙面・下線の視覚確認はしていない。[開発者公式ページ](https://www.educa.nagoya-u.ac.jp/~otani/scat/index.html) のニュース内の〈4〉記法と2011チュートリアル推奨を実読。2008本文、FAQ/tips全項目、福士・名郷原典は未読。
- **AIレビュー判定・具体的差分**: [expert_agents.py](../../../../src/gurumoji/services/expert_agents.py) の既定C1は01のoutput_sectionsを必須文字列にし、SCATではストーリーライン・理論記述も欄になる一方、AI briefはそれらの生成を禁止する。人待ちとAI候補を型で分ける余地がある。300発話は作業量warnで、方法の上限ではない。原典p.160は〈4〉を先に思いついてから〈2〉〈3〉を埋めて検討することも認める。05の包丁事例は、p.158 §4.1では複数の調理師・店主への面接を再構成した教材であり、実在単一面接の分析と誤認させない説明が必要。
- **正常例 M33-04-N（合成設計）**: u1「忙しそうで声をかけられなかった」から〈1〉候補と〈5〉「忙しさは観察か推測か」を返し、〈2〉〜〈4〉は研究者に残す。
- **負例 M33-04-X（禁止・不適合）**: AIが〈2〉〜〈4〉と完成理論を生成してSCAT実施済みとする、〈4〉を長い説明文にする。
- **代替説明**: 声をかけない理由は遠慮ではなく、別の相談経路が既にあるためかもしれない。


- **G5 CPU局所観測（4d92d0a）**: M33-04-N/Xを下記G5一覧の条件で確認。両文ともaccepted_unreviewed_draft。研究者stepをperformedに入れると拒否。意味品質・本人採否は別判定で、負例FAIL。許可段階はscat-p2/p6、欄の存在は理論生成の許可ではない。

## 05. M-GTA

- **固定定義**: `exp-m-gta`／`expert-m-gta-definition`／D1／[01-Expert](../10-Experts/m-gta/01-Expert.md) raw SHA-256 `fbeae854b1726cd8cdb5a63b02b0b636fe8f7a4db53c6795466ca7ab2a614b40`
- **許可・実行段階**: AI下書き許可。AI: `mgta-p4`（分析ワークシート（概念名、定義、ヴァリエーション、理論的メモ）に記入し、ヴァリエーション（具体例）の候補を集める）、`mgta-p5`（反対例・類似例の候補を探し、複数の概念を同時並行で比較する）／K: なし／R: `mgta-p1`（研究テーマから分析テーマを設定し、分析焦点者を決める）、`mgta-p2`（1人分の記録の全体に目を通し、分析テーマと分析焦点者に照らして着目する箇所を選ぶ（切片化しない））、`mgta-p3`（着目した箇所の意味を幾通りか検討し、定義として採用する解釈を決めて概念を生成する）、`mgta-p6`（採用しなかった解釈案や疑問を理論的メモに残す）、`mgta-p7`（概念間の関係からカテゴリーを生成する）、`mgta-p8`（理論的サンプリングで確認し、理論的飽和化を判断する）、`mgta-p9`（結果図と、概念とカテゴリーだけで書くストーリーラインをまとめる）
- **分析単位**: 分析テーマと分析焦点者に沿って着目したデータの箇所（切片化しない）。発話IDはヴァリエーションの根拠として参照する
- **必要入力**: 研究テーマと、プロセスを捉える形の分析テーマ（研究質問として登録）；分析焦点者（分析メモに記録）；1人分ずつ全体として読める面接記録
- **現行契約**:
  - 専用07/08なし。既定C1の汎用候補出力のみ

- **対象集合・方法**: 分析テーマと分析焦点者を定め、文脈を切り離さず概念と関係を構成して動態的な過程を説明する。分析焦点者は特定の一人でなく、条件で定めた集合的な他者。現行runの固定会話だけで、理論的サンプリングや限定的一般化の範囲が満たされたとはしない。
- **研究者だけの判断**: テーマ・焦点者、概念名・定義、理論的メモ、カテゴリー、飽和化、結果図・ストーリーライン。研究者採否は未回答。AIの担当は研究者定義の概念に対する具体例・類似例・反対例候補で、概念生成や飽和判断ではない。
- **一次資料と今回の読了範囲**: [M-GTA研究会公式](https://www.m-gta.jp/mgta.html) の「修正版の意味」「分析テーマ・分析焦点者」両Q&A全文を実読。担当が木下康仁、2009年HP開設時と明記され、既存RESの著者未確認は更新候補。[木下2007機関リポジトリ](https://toyama.repo.nii.ac.jp/records/2605) は429等で本文未取得。書籍・2007本文・追加応用研究は未読で、ワークシート詳細と飽和化の頁指定を今回再検証済みとはしない。
- **AIレビュー判定・具体的差分**: 文脈付き例の探索という補助に限定すれば整合する。現01の焦点者確認はhuman_review/warn、登録概念の存在・定義の機械的gateがない。既定C1の任意analysis_premisesだけでは必要前提を保証しない。`mgta-p4` の題名はワークシート記入全体にも読めるがbriefは具体例候補だけで、名前・定義・メモの人の権限を明瞭にする必要がある。専用07/08がないことは実行不可ではなく、構造化の不足である。
- **正常例 M33-05-N（合成設計）**: 焦点者を入職1年未満の新人、テーマを相談相手獲得の過程とし、研究者定義「相談の許可感」に対する具体例と「歓迎されても相談しない」という反対例候補を前後付きで返す。
- **負例 M33-05-X（禁止・不適合）**: 焦点者なしに語句を細切れ自動コード化してM-GTAと呼ぶ、検索結果が増えないことを理論的飽和とする。
- **代替説明**: 相談増加は心理的安心よりも、担当変更・勤務時間の重なりで説明できるかもしれない。


- **G5 CPU局所観測（4d92d0a）**: M33-05-N/Xを下記G5一覧の条件で確認。両文ともaccepted_unreviewed_draft。分析前提の意味充足は未検査。意味品質・本人採否は別判定で、負例FAIL。概念/焦点者・理論的サンプリング/飽和は研究者責務。

## 06. KJ法

- **固定定義**: `exp-kj-method`／`expert-kj-method-definition`／D1／[01-Expert](../10-Experts/kj-method/01-Expert.md) raw SHA-256 `6da09be94b025adb2c5e60d3420a1d5f0640239a9d207c2273d8d22bd2d52c70`
- **許可・実行段階**: AI補助禁止。AI: なし／K: なし／R: `kj-p0`（下準備（音声データの文字起こし、道具の準備））、`kj-p1`（ラベルづくり（1ラベル1メッセージ、通し番号を元データと対応させる））、`kj-p2`（ラベル拡げ（ランダムな順に並べる））、`kj-p3`（ラベル集め（内容からボトムアップに小グループを作る。事前にカテゴリーを想定せず、入らないラベルはそのままにする））、`kj-p4`（表札づくり（文章で書き、理論や専門用語に無理に当てはめない））、`kj-p5`（第2段・第3段のグループ編成（解釈可能なグループ数になるまで繰り返す））、`kj-p6`（空間配置（大グループから、解釈しやすい順に並べる））、`kj-p7`（図解化（グループを囲み、関係線は大きいグループから研究目的に合わせて最小限に結ぶ））、`kj-p8`（文章化（論理的な矛盾とデータからの解釈の逸脱に注意する））、`kj-p9`（図解と文章化を他者に説明し、衆目評価の結果を記録する）
- **分析単位**: ラベル（1つのメッセージ）。発話IDをラベルの通し番号に対応させる
- **必要入力**: 研究目的（関係線を最小限にする基準）；文字起こし；ラベル化の方針（発話の区切りとメッセージの単位が合わない場合の扱い）
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 選定資料の意味構造を扱い、一ラベル一メッセージを保持して、既成カテゴリーを置かず小群・表札・階層・図解・文章へ進む。現製品の発話集合を使う場合も、複数メッセージの分割と元IDとの対応は研究者が決める。ラベル数を母集団の支持率にしない。
- **研究者だけの判断**: `kj-p0`〜`kj-p9`の全段階。異質なラベルを無理に編入せず、図解と文章の意味・衆目評価を本人が記録する。研究者採否は未回答。AI禁止は本製品の役割契約で、古典文献が現代AI一般を禁止したという意味ではない。
- **一次資料と今回の読了範囲**: [田中「KJ法クイックマニュアル」](https://www.mizumot.com/method/2012-08_Tanaka.pdf) 印刷pp.102–106、特に図2の手順pp.103–105と専門書も必要という結語を実読。[川喜田ほか2003](https://www.jstage.jst.go.jp/article/jaqp/2/1/2_6/_pdf) p.6要約、pp.23–24の衆目評価・異なる意見、pp.26–27の解説を選択読解。後者全体を通読しておらず、1967/1986/1997の原典書籍は未読。インタビュー・実務手引きの確認を原典書籍の精読に置換しない。
- **AIレビュー判定・具体的差分**: ラベルからのボトムアップ整理という骨格は支持されるが、現00/06とreadinessが示すとおり、ラベル・表札・編成履歴・図解の専用機能がない。旧01のintegrated/sample_verified=trueはKJ全工程の実行可能性ではない。埋め込みクラスタで代替せず、400発話は便宜的な作業量の目安とする。
- **正常例 M33-06-N（合成設計）**: u1「価格はよいが予約が難しい」を二ラベルにし、研究者が他のラベルと小群・文章の表札を作り、孤立ラベルを残して元資料との関係を説明する。
- **負例 M33-06-X（禁止・不適合）**: 自動クラスタをKJ完成品、最大の島を最重要意見とする。
- **代替説明**: 類似ラベルの多さは独立した支持でなく、同調、質問の反復、ラベルの切り方でも生じる。


- **G5 CPU局所観測（4d92d0a）**: M33-06-N/Xを下記G5一覧の条件で確認。入力あり非blocked/0件blocked、全10手順researcher、expert_ai_unavailable。意味品質・本人採否は別判定で、二ラベル化・表札/孤立ラベル・KJ完成の意味判断NOTRUN。

## 07. 計量テキスト分析

- **固定定義**: `exp-quantitative-text-analysis`／`expert-quantitative-text-analysis-definition`／D1／[01-Expert](../10-Experts/quantitative-text-analysis/01-Expert.md) raw SHA-256 `9258b86f28c19ba88c338591a3e8802ef8d1bb6255a959ec0d18d14d3c453fcb`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `qta-p2`（形態素解析の条件（解析器、分割単位、ストップ語）を固定する）、`qta-p3`（語彙頻度・共起・話者別特徴語を計算してデータ全体を要約する（語を手作業で逐一選ばない））／R: `qta-p1`（研究質問、比較の枠組み、注目する概念を分析の前に設定する）、`qta-p4`（比較の枠組みで、明確に区別できる対象の間の語の違いを見る）、`qta-p5`（注目した語を文脈検索（KWIC）で原文に戻って読み、質的に解釈する）、`qta-p6`（概念を語で操作化する場合は、コーディングの規則を公開できる形で記録する）
- **分析単位**: 発話（文書）。語はGiNZA／SudachiPyの内容語
- **必要入力**: 研究質問；比較の枠組み（明確に区別できる比較対象）；注目する概念；形態素解析の結果（解析器・分割単位・ストップ語を固定）
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 固定会話の非除外発話を文書集合とする。TFは延べ語数、DFは出現した発話数で、参加者数ではない。機械的に全体を要約し、KWICで原文へ往復する。理論的概念を辞書規則で操作化する分析は、単なる語彙探索と別工程。
- **研究者だけの判断**: 比較軸・概念の操作化・原文の意味・質問語や否定の扱い。研究者採否は未回答。
- **一次資料と今回の読了範囲**: [樋口2004](https://www.jstage.jst.go.jp/article/ojjams/19/1/19_1_101/_pdf) §3.1–3.2、掲載pp.105–106の抽出と規則を実読。[樋口2017](https://www.jstage.jst.go.jp/article/jsr/68/3/68_334/_pdf) §2.1–2.2、§3.2.2、p.344のインタビュー事例、§4 pp.346–348を実読。両論文全体・引用先の個別研究・2014年書籍は未読。
- **AIレビュー判定・具体的差分**: 語の探索と原文確認という用途は整合するが、Gurumoji独自の頻度・共起・率差をKH Coder全機能と呼べない。[research_analysis.py](../../../../src/gurumoji/research_analysis.py) の既存集計には辞書規則による自動コーディング・特徴語の有意差検定がない。20発話の注意基準は必要標本数の保証ではない。AI禁止を維持する。
- **正常例 M33-07-N（合成設計）**: Aのu1に「費用」が3回、Bのu2に1回あるときTF=4、DF=2を分け、両IDの原文で否定・引用を確認する。
- **負例 M33-07-X（禁止・不適合）**: 「4回だから4人の懸念」「最頻語が最重要」「共起が原因」を出す。4回を支持人数へ変換しない。
- **代替説明**: 司会の質問語の反復、引用、長い発話、分割・ストップ語の差でも頻度は変わる。


- **G5 CPU局所観測（4d92d0a）**: M33-07-N/Xを下記G5一覧の条件で確認。4/2/2を実計数、fallback/研究利用不可を明示、状態needs_attention。意味品質・本人採否は別判定で、人数・重要性・因果の意味検出NOTRUN。TF4≠観測話者2を確認。

## 08. フォーカスグループ相互作用

- **固定定義**: `exp-focus-group-interaction`／`expert-focus-group-interaction-definition`／D1／[01-Expert](../10-Experts/focus-group-interaction/01-Expert.md) raw SHA-256 `502131e409de7b141a166658ee63a5935e0e1aca95efd7112f99bd9b316dde82`
- **許可・実行段階**: AI下書き許可。AI: `fgi-p3`（隣接する発話の組（提案と同意・不同意、質問と答え、補足、言い直し）の候補を見つける）、`fgi-p5`（不同意・少数意見・意見の変化の候補を、分析の資源として記録する）／K: なし／R: `fgi-p1`（話者と順序、司会者の役割を確認する）、`fgi-p2`（内容の分析とは別の表で相互作用を扱う方針を決める）、`fgi-p4`（選好構造（好まれる応答・好まれない応答）、説明、修復の観点で応答を検討する）、`fgi-p6`（司会者の働きかけとグループの構成が相互作用に与えた影響を検討する）、`fgi-p7`（相互作用の所見を、根拠となる発話の連鎖と一緒に報告する）
- **分析単位**: 発話の連鎖（隣接する発話の組と前後の文脈）。根拠は複数の発話ID
- **必要入力**: 話者と発話の順序を確認した逐語録；司会者の役割の登録；研究質問
- **現行契約**:
  - [07-Agent-Contract.md](../10-Experts/focus-group-interaction/07-Agent-Contract.md): schema_version=1 / 既定contract_version=1 / 明示typedのcontract_version=2; raw SHA-256 `18e3f05b356806c9fe2bb625c7e7ae7d5fb20f7cf4ab002926aefe891f5f2942`
  - [08-Skill-Hook-Binding.md](../10-Experts/focus-group-interaction/08-Skill-Hook-Binding.md): schema_version=1 / binding_version=1; raw SHA-256 `1eb5e6ef2fe06f4a264ace022b53ec44522f9abfba68f4798ad177bbff998c37`

- **対象集合・方法**: 固定一会話の発話連鎖と前後文脈を対象に、誰が何に応答し、同意・不同意・修復・説明がどう働いたかを見る。内容コードとは分け、司会と構成も検討する。明示S1の各候補は2〜16個の異なる発話ID/hashを順序付きで持つが、2〜16は方法論上の連鎖長の限界ではない。
- **研究者だけの判断**: 話者・順序・役割確認、内容との分離方針、応答の機能、司会影響、連鎖を伴う報告。研究者採否は未回答。AIは `fgi-p3/p5` の候補だけ。
- **一次資料と今回の読了範囲**: [Grønkjær et al. 2011](https://tidsskrift.dk/qual/article/download/4273/3706) 印刷pp.16–20の対象・方法・連鎖例、pp.24–27の行き詰まり・司会・考察を実読。デンマークの飲酒に関する5グループ27人の研究で、完全な会話分析を製品で再現した証拠ではない。[Hermann et al. 2024公式PDF](https://journals.sagepub.com/doi/pdf/10.1177/16094069241286848?download=true) pp.2–5のMethods/Table 1/適用、pp.10–12の別資料試行・修正・品質条件を実読。DOI直通は403だったが公式PDFは取得できた。全13ページの精読ではない。
- **AIレビュー判定・具体的差分**: 現07/08の閉鎖候補、固定scope・実配送・原文hash・実actorと人未確認の分離は適切なCPU契約範囲。受入を撤回する根拠はない。一方、既定hookは12発話/12000文字、明示無効時の既存経路も120発話/60000文字までで、全文の初期配送不足はneeds_input。長いFGIの意味分析に成功したとはしない。Hermannの8コードと現7relation種は同じ分類でなく、対応づけは未検証。非言語・日本語の意味品質・本人採否は未評価。00/03/06のHermann要旨のみと01/05の本文確認が不整合。手動interaction_linksとTAのasset採否経路へ自動昇格しない。
- **正常例 M33-08-N（合成設計）**: u1 A「毎週対面にしたい」、u2 B「毎週は難しい。月1回なら」、u3 A「では月1回に変えます」、u4 B「それなら参加できます」。不同意u1–u2、意見変更u1–u3の候補を前後付きで返す。
- **負例 M33-08-X（禁止・不適合）**: 「そうですね」だけで合意、沈黙から同意、単発引用から集団合意、AI出力から人確認済みを確定する。
- **代替説明**: 相づちは継続促進、不同意を和らげる前置き、司会への儀礼的応答でもあり得る。


- **G5 CPU局所観測（4d92d0a）**: M33-08-N/Xを下記G5一覧の条件で確認。両文ともaccepted_unreviewed_draft。typed FGIの意味拒否結果とは別。意味品質・本人採否は別判定で、負例FAIL。連鎖と機能・司会影響の研究者確認は未実施。

## 09. 発話量・参加バランス

- **固定定義**: `exp-participation-balance`／`expert-participation-balance-definition`／D1／[01-Expert](../10-Experts/participation-balance/01-Expert.md) raw SHA-256 `3b01cd0aff930a6cada9b26dd0075daa4bbd59d777f6a39be13eb6e1081e0bb6`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `part-p2`（話者・属性群ごとに発話数・発話時間・割合を集計する）、`part-p3`（同じ話者の集合から、偏りの指標（Gini係数、正規化evenness、HHI、最大参加者比）を計算する）／R: `part-p1`（役割と分母（参加者のみ、または全話者）を決める）、`part-p4`（低参加や発話時間の集中の候補を、司会者の働きかけとグループ構成と合わせて読む）
- **分析単位**: 話者（司会者・運営役を分母から除く設定あり）と属性群。値は発話の集計
- **必要入力**: 話者ラベルと役割の登録；有効な時刻；分母の設定（参加者のみ、または全話者）
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 一会話で役割と除外方針を固定した観測話者集合を分母にし、発話数・時間・偏りを記述する。確認済み全参加名簿とは異なる。参加の公平性、関与、発言価値を直接測る尺度ではない。
- **研究者だけの判断**: 分母、司会除外、欠測の意味、発言機会と役割を踏まえた解釈。研究者採否は未回答。LLM見解は許可されていない。
- **一次資料と今回の読了範囲**: [Woolley et al. 2010著者要旨](https://pubmed.ncbi.nlm.nih.gov/20929725/) はAbstractのみ。699人・2〜5人の課題遂行集団での関連で、FGIにGini/evenness/HHIを用いる妥当性を検証した資料ではない。本文・補足の測定詳細は未読。[Grønkjær et al. 2011](https://tidsskrift.dk/qual/article/download/4273/3706) p.25の司会と発言機会を実読。Stephan & Mishler原著は今回本文未読。
- **AIレビュー判定・具体的差分**: [group_analysis.py](../../../../src/gurumoji/services/group_analysis.py) の `_participation_balance` は名簿なし・未観測人数nullを明示し、未発言者を補完しない点は適切。ただし `part-a1` は全話者2人以上で、司会除外後の対象2人以上とは違う。complete条件にも人数条件がなく、司会＋参加者1人なら単独Gini=0/evenness=1をcomputedにし得るという静的差分がある。局所helperの単独値0/1だけは確認したが、役割除外からの全経路は未実行。数値定義と単独対象の解釈不能を分離する必要がある。
- **正常例 M33-09-N（合成設計）**: 司会を除く観測A/Bが各30秒ならGini=0、evenness=1、HHI=0.5とし、「観測2人の時間が等しい」とだけ報告する。
- **負例 M33-09-X（禁止・不適合）**: 名簿なしで「参加者全員が均等」、低発話から無関心、司会除外後1人の指標から公平性を結論する。
- **代替説明**: 指名の偏り、通訳、説明担当の役割、話者分離の誤りでも分布は変わる。


- **G5 CPU局所観測（4d92d0a）**: M33-09-N/Xを下記G5一覧の条件で確認。計算された観測分布と名簿未確認を保持。単独指標の既知制約を再現。意味品質・本人採否は別判定で、公平性・全員均等・低発話=無関心の意味判断NOTRUN。

## 10. 会話の時間構造

- **固定定義**: `exp-conversation-timing`／`expert-conversation-timing-definition`／D1／[01-Expert](../10-Experts/conversation-timing/01-Expert.md) raw SHA-256 `07d53d607a10acf1c5df8b4d6f257e77a295de673f5df933eacbd5cc552b56b0`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `time-p2`（話者遷移・無音の候補・重なりの候補・時間区間の集計を計算する）／R: `time-p1`（しきい値（無音、重なり、時間区間）を決めて記録する）、`time-p3`（候補の区間を音声と前後の発話で確認する）、`time-p4`（遷移の件数と、遷移の社会的な意味を分けて報告する）
- **分析単位**: 文字起こしのセグメントの開始・終了時刻
- **必要入力**: 有効な開始・終了時刻；話者ラベル；しきい値（無音、重なり、時間区間）
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 固定会話の有効な開始終了と話者を持つ区間を対象に、欠測区間を別記し、閾値付きの無音・重なり・遷移候補を記述する。ASR等のsegment、実際のturn、発言権の移動は同一ではない。件数比率と時間比率の分母も区別する。
- **研究者だけの判断**: 閾値と許容時刻誤差、音声・前後の聴取、社会的な意味。研究者採否は未回答。候補の検出をLLMによる合意・対立判定へ広げない。
- **一次資料と今回の読了範囲**: [Levinson & Torreira 2015](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.00731/full) §5.1、§5.2.1–5.2.2、Table 2を実読。348件・約38時間の英語電話二者会話と180ms以上の無音で区切るIPU等を扱う。原コーパス・音声・個別注釈は未確認で、日本語FGIのsegment測定と直接同じにはできない。Heldner & Edlund原著の今回全文確認はしていない。
- **AIレビュー判定・具体的差分**: 候補算出と聴取・意味を分離する骨格は整合する。製品の3秒/0.2秒・50%/95%等は普遍的な文献基準ではなく、時刻誤差への感度や日本語・多人数での評価が不足。[group_analysis.py](../../../../src/gurumoji/services/group_analysis.py) の `_long_gaps` は前後の名前と時刻を返すが発話IDを持たず、01の出力要件との来歴差がある。重なり候補にはIDがあり、同じように原資料へ戻れる設計が必要。候補算出自体の誤りと断定したものではない。
- **正常例 M33-10-N（合成設計）**: u1 A[0,2]、u2 B[5.5,7]、u3 A[6.5,8]から、3.5秒の無音候補と0.5秒の重なり候補を提示し音声へ戻る。
- **負例 M33-10-X（禁止・不適合）**: 重なりから遮り・対立、無音から熟考・同意、0.2秒差から文化差を断定する。
- **代替説明**: 相づち、同時開始、録音欠落、segment境界誤差が同じ時間値を作り得る。


- **G5 CPU局所観測（4d92d0a）**: M33-10-N/Xを下記G5一覧の条件で確認。gap/overlap候補を算出。欠測から不存在へ昇格せず、gap出力は発話IDなし。意味品質・本人採否は別判定で、重なり=対立・無音=熟考/同意の意味判断NOTRUN。

## 11. 記述統計・度数

- **固定定義**: `exp-descriptive-statistics`／`expert-descriptive-statistics-definition`／D2／[01-Expert](../10-Experts/descriptive-statistics/01-Expert.md) raw SHA-256 `08c12a57476204ac9dad8520427a4268ad67ed8eec6a35d319334f61890cbdc7`
- **許可・実行段階**: AI下書き許可。AI: `desc-ai-plan`（専用知識から集計案・前提確認事項を下書きし、Handlerへ計算を提案する）、`desc-ai-report`（Handlerが検証した記述統計・度数の結果を参照して説明を下書きする）／K: `desc-p2`（N、欠測、平均、標準偏差、中央値、四分位、最小・最大、度数を計算する）／R: `desc-p1`（対象の発話、比較軸、欠測の扱いを決める）、`desc-p3`（分布の歪みと極端な発話を、発話IDで確認する）、`desc-p4`（分析を探索的な記述として報告する）
- **分析単位**: 発話（比較軸は話者または役割）
- **必要入力**: 除外していない発話；比較軸（話者または役割）；欠測の扱い；形態素解析の結果（形態素数・内容語数・語彙多様性のため）
- **現行契約**:
  - [07-Agent-Contract.md](../10-Experts/descriptive-statistics/07-Agent-Contract.md): schema_version=2 / contract_version=2; raw SHA-256 `97a8dfc961a2c469bd22f76897b790e1bd4a5de0fcf2b6df5a4743b10412ad4a`

- **対象集合・方法**: 一会話の固定 `all_included_initial` を対象とし、変数ごとの有効N・欠測を分ける。発話加重平均と話者ごとの平均の等重み集計は異なる。計算結果の転記だけでは何を要約したかを決められない。
- **研究者だけの判断**: 対象・比較軸・欠測方針、極端値の扱い、分布の意味。研究者採否は未回答。
- **一次資料と今回の読了範囲**: [Appelbaum et al. 2018 原論文PDF](https://www.unlv.edu/sites/default/files/page_files/27/APA-JournalArticle-ReportingStandards.pdf) の要旨、Table 1の対象・除外・欠測・分析、掲載pp.6–8の該当部分と末尾の訂正を実読。全24 PDFページの通読ではない。訂正は臨床試験登録に関するヘルシンキ宣言の引用版で、この記述統計の区分を撤回するものではない。[SciPy describe](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.describe.html) Parameters/Returns/Raises/Examplesを実読。公式APIは実装仕様の一次資料で、独立した方法妥当性試験ではない。
- **AIレビュー判定・具体的差分**: 固定入力の記述とAI説明の分離は妥当。`desc-ai-plan/report`、正式tool2種、S2/C2、セル9キーの束縛は実装済み。ただし[research_analysis.py](../../../../src/gurumoji/research_analysis.py) は `stats.describe` そのものではなくPythonの標本SDと独自の線形補間四分位を使用する。発話／話者の単位切替はこの専門家のnative統計経路にない。[expert_agents.py](../../../../src/gurumoji/services/expert_agents.py) の統計本人recordは依然unsupportedで、数値一致を本人採用へ昇格しない。
- **正常例 M33-11-N（合成設計）**: 5発話の文字数は全件有効、時間は1件欠測。時間N=4・欠測1、文字数N=5として、それぞれの固定セルから説明する。
- **負例 M33-11-X（禁止・不適合）**: 欠測時間を0秒、1人の100発話を100人、文字/分を理解度とする。欠測は変数ごとの状態を保持する。
- **代替説明**: 質問形式、長い説明1件、話者分離誤り、欠測が特定話者に偏ることでも要約値は変わる。


- **G5 CPU局所観測（4d92d0a）**: M33-11-N/Xを下記G5一覧の条件で確認。固定セル受理＋負例散文accepted_unreviewed_draft。hash改変/行改変は拒否。意味品質・本人採否は別判定で、負例FAIL。発話単位と人単位の混同。数値一致は独立性保証でない。

## 12. クロス集計・群間比較

- **固定定義**: `exp-group-comparison-statistics`／`expert-group-comparison-statistics-definition`／D2／[01-Expert](../10-Experts/group-comparison-statistics/01-Expert.md) raw SHA-256 `15ac2cd8ffd7c02a9ffd8d99215a6a2a31fc1b776d3702da23e73b05f3fc9906`
- **許可・実行段階**: AI下書き許可。AI: `grp-ai-plan`（専用知識から比較案・前提確認事項を下書きし、Handlerへ計算を提案する）、`grp-ai-report`（Handlerが検証したクロス集計・検定の結果を参照して説明を下書きする）／K: `grp-p2`（クロス集計と検定（N、群数、統計量、p値、効果量、仮定の注記）を計算する）／R: `grp-p1`（比較の目的、群の定義、対象の変数を決める）、`grp-p3`（期待度数、群の大きさ、分散の違いを確認する）、`grp-p4`（入れ子と多重比較を踏まえて、結果を探索的に報告する）
- **分析単位**: 発話（群は話者または役割）
- **必要入力**: 比較の目的；比較軸（話者または役割）；対象の変数（質問候補、手動コード、選択した語）；SciPyの利用
- **現行契約**:
  - [07-Agent-Contract.md](../10-Experts/group-comparison-statistics/07-Agent-Contract.md): schema_version=2 / contract_version=2; raw SHA-256 `a1ed398b0e6f759448fd4b327eccb1d672f5bada923a4f377e82f98a16ed0c5a`
  - [08-Skill-Hook-Binding.md](../10-Experts/group-comparison-statistics/08-Skill-Hook-Binding.md): schema_version=1 / binding_version=6; raw SHA-256 `5080fbf445fc4668ca803ffa0cfe4ef5ad00f302786dc3644bb1d9c24f903be4`

- **対象集合・方法**: 一会話の固定全対象発話を、既存の話者／役割で群分けする。群別の分布・クロス表・効果量と検定前提を先に読む。発話の入れ子は「探索的」と書くだけでは解消せず、KruskalやWelchへの置換でも独立性は回復しない。
- **研究者だけの判断**: 群の意味、独立単位、期待度数・分散・多重検定、どこまで推論するか。研究者採否は未回答。
- **一次資料と今回の読了範囲**: [SciPy f_oneway](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html) Parameters/Warnings/Notesと、[kruskal](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html) 本文/Returns/Notesを実読。[Delacre et al. 2019](https://pure.tue.nl/ws/portalfiles/portal/143487258/198_2046_1_PB.pdf) 要旨、掲載pp.1–4の前提・式、pp.9–10のRecommendations該当部分のみ。全シミュレーション・コードは未読。[rstatix公式効果量API](https://rpkgs.datanovia.com/rstatix/reference/kruskal_effsize.html) の式・method引数、[effectsize公式](https://easystats.github.io/effectsize/reference/rank_epsilon_squared.html) のrank eta/epsilon・Detailsを実読。Cochran原著、Delacre2017/2022訂正は今回本文未確認。
- **AIレビュー判定・具体的差分**: [analysis_orchestration_methods.py](../../../../src/gurumoji/services/analysis_orchestration_methods.py) に許可tool4種、S2/C2と固定セル説明はある。一般化の妥当性はない。[research_analysis.py](../../../../src/gurumoji/research_analysis.py) のKruskal部分は `effect_name="epsilon_squared"` に `max(0,(H-k+1)/(N-k))` を入れる。公式rstatixではこれをeta²[H]とし、rank epsilon²=H/(N−1)と区別する。数値が直ちに誤りと断定せず、用語の揺れも含め名称・式・採用根拠を揃える必要がある。標準 `f_oneway` はWelchではない。各群2件で計算できる条件は近似の十分性を保証せず、公式の各群5件という目安も万能ではない。補正・入れ子モデル未実装、08 readerあり・汎用callbackはplanned。
- **正常例 M33-12-N（合成設計）**: A/Bの質問候補の有無を固定クロス表から示し、N・群・百分率・期待度数警告と未補正を併記。本人記録がなければhuman_pending。
- **負例 M33-12-X（禁止・不適合）**: 100発話を独立100人として最小pだけを採用、標準ANOVAをWelchと表示、違う方式の効果量名と式を混ぜる。
- **代替説明**: 発言機会、司会の役割、同一人の反復、群サイズ・分散の偏りが群差を作る。


- **G5 CPU局所観測（4d92d0a）**: M33-12-N/Xを下記G5一覧の条件で確認。固定count/分母受理＋負例散文accepted_unreviewed_draft。実行したのはcrosstabsのみ。意味品質・本人採否は別判定で、負例FAIL。未実行のANOVA/Welch/補正を主張、方法名と計算の不一致。

## 13. 相関

- **固定定義**: `exp-correlation`／`expert-correlation-definition`／D2／[01-Expert](../10-Experts/correlation/01-Expert.md) raw SHA-256 `5a499ea69a38f176a1212ab52d4fe85b8237aaf80ba6fd1b5deed148a14642bb`
- **許可・実行段階**: AI下書き許可。AI: `cor-ai-plan`（専用知識から相関の分析案・前提確認事項を下書きし、Handlerへ計算を提案する）、`cor-ai-report`（Handlerが検証したPearson・Spearmanの結果を参照して説明を下書きする）／K: `cor-p2`（係数、N、p値、計算できない状態を計算する）／R: `cor-p1`（変数の対と、相関の種類（Pearson・Spearman）を確認する）、`cor-p3`（分布の歪み・外れ値・同順位を確認し、発話IDに戻る）、`cor-p4`（探索的な関連として報告する）
- **分析単位**: 発話
- **必要入力**: 発話単位の数値変数；欠測の扱い；SciPyの利用；形態素解析の結果（形態素に基づく変数のため）
- **現行契約**:
  - [07-Agent-Contract.md](../10-Experts/correlation/07-Agent-Contract.md): schema_version=2 / contract_version=2; raw SHA-256 `92c02db1e1db0f68ed2ff0febd3b5d5615149a748bf0b2a7a534dc06478bb3d2`
  - [08-Skill-Hook-Binding.md](../10-Experts/correlation/08-Skill-Hook-Binding.md): schema_version=1 / binding_version=6; raw SHA-256 `4834067229ad482d05316df8d504a6cfdc17e8c652b58318801675e9560ffe66`

- **対象集合・方法**: 一会話の固定全対象発話から、変数対ごとの完全ペアを対象にする。Pearsonは線形、Spearmanは単調な関連の要約。係数・p値の条件・原因は別問題で、話者内と話者間の関連を混ぜない。
- **研究者だけの判断**: 変数対、散布・外れ値・同順位、欠測機構、独立単位と解釈。研究者採否は未回答。
- **一次資料と今回の読了範囲**: [SciPy pearsonr](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html) Parameters/Returns/Warnings/Notesと再標本化Examplesの該当部分、[spearmanr](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html) 冒頭のp値精度注意、Parameters/Warnings、小標本の置換例を実読。[Bishara & Hittner 2012](https://cpb-us-w2.wpmucdn.com/blogs.cofc.edu/dist/7/881/files/2021/06/Bishara-Hittner-2012.pdf) 掲載pp.404–405の再標本化、p.411のGeneral Discussion該当部分のみ。全条件・表・コード、Spearman1904・Holm1979原著は未読。
- **AIレビュー判定・具体的差分**: 正式Pearson/SpearmanとS2/C2セル束縛は実装済み。[research_analysis.py](../../../../src/gurumoji/research_analysis.py) は両関数を直接呼び、置換・変換・多重比較補正はない。公式はSpearman漸近p値の小標本精度に注意し、大標本（>500）を目安にしている。`cor-a2` の10発話は精度保証ではなく、>500も独立性の保証ではない。行シャッフルの単純追加も話者内依存を解決しない。08 readerの未接続という旧記述は現行コードと分け、統計本人recordの保留は維持する。
- **正常例 M33-13-N（合成設計）**: 発話時間×文字数を先に指定し、完全ペアN・欠測と両係数を、それぞれ同じ検証済み行から説明する。
- **負例 M33-13-X（禁止・不適合）**: 定数列の未計算をr=0とする、別変数対のNを結合する、正の相関から「長く話すと理解が深まる」と因果を確定する。
- **代替説明**: 時間と文字数の定義的な関係、役割の混合、外れ値1件、時刻誤差。


- **G5 CPU局所観測（4d92d0a）**: M33-13-N/Xを下記G5一覧の条件で確認。固定係数/N受理＋負例散文accepted_unreviewed_draft。実行したのはPearsonのみ。意味品質・本人採否は別判定で、負例FAIL。別手法・小標本精度の保証・因果断定は束縛セルから導けない。

## 14. 埋め込みによるテーマ探索

- **固定定義**: `exp-embedding-topic-exploration`／`expert-embedding-topic-exploration-definition`／D2／[01-Expert](../10-Experts/embedding-topic-exploration/01-Expert.md) raw SHA-256 `82198ae33868ccbc96773fbd087359be63b1aaee3ead1375765e8779a111bf02`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `emb-p1`（対象の発話の選択と、短い断片の文脈補完の条件を確認する）、`emb-p2`（文埋め込みを作り、K-meansでクラスタリングし、シルエット係数でテーマ数を選ぶ）、`emb-p6`（定義したテーマのベクトルへ最近傍で割り当て、未割当と境界例を研究者が原文で確認する）／R: `emb-p3`（各クラスタの代表発話と外れ値を原文で読み、仮ラベルを見直す）、`emb-p4`（クラスタの併合・分割・除外を研究者が判断し、探索の結果として報告する）、`emb-p5`（手動で割り当てる場合は、研究者がテーマの見出しと手がかり語・シード発話を定義して保存する）
- **分析単位**: 文脈付き発話（短い断片は同じ話者の3秒以内の隣接発話で補う）
- **必要入力**: 入力変更後に更新されたTransformerテーマ分析の結果；モデル名・リビジョン・次元・seed・候補テーマ数の記録；手動で割り当てる場合は、テーマの見出しと、手がかり語またはシード発話
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 固定会話の対象発話と明示された文脈補完範囲を扱う。ベクトルのまとまりは読む箇所の候補で、解釈的テーマ・支持・合意ではない。シルエットは配置の分離度で、研究上の意味の妥当性ではない。
- **研究者だけの判断**: 原文と境界例、仮ラベル、併合・分割・除外、手動テーマ定義。研究者採否は未回答。Transformer計算があることは、この専門家のLLM見解許可ではない。
- **一次資料と今回の読了範囲**: [Wang et al. 2024 v1](https://arxiv.org/html/2402.05672v1) Abstract・§1–3の本文と表の該当範囲。全言語Appendixは未読。[multilingual-e5-small公式card](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md) Usage/Supported Languages/FAQ1–3/Limitationsを実読、benchmark metadata全件は未読。[Chang et al. 2009](https://papers.nips.cc/paper_files/paper/2009/file/f92586a25bb3145facd64ab20fd554ff-Paper.pdf) Abstract、§3.1–3.2、§4.1・4.3の該当部分を実読。同論文は確率的topic modelの人評価であり、E5＋K-meansを直接検証していない。
- **AIレビュー判定・具体的差分**: [transformer_analysis.py](../../../../src/gurumoji/transformer_analysis.py) はrevision固定・正規化・切詰診断がある。クラスタ用発話は `kind="passage"` だが公式cardはclustering/feature用途に `query:` を推奨する。検索との共用判断もあり得るため即不良とはせず、prefix選択理由と感度試験・人評価が不足とする。`emb-p6` はactor=codeなのに題名に研究者の原文確認を含み、自動割当の終了と人確認を区別しにくい。日本語会話での妥当性、20件・0.1等の注意基準は未確立。
- **正常例 M33-14-N（合成設計）**: 「駅まで歩く」「バスの本数」と食事の発話を探索し、代表例と境界例の原文IDへ戻る。意味テーマの採用は研究者が別に行う。
- **負例 M33-14-X（禁止・不適合）**: 「バスは便利」「便利ではない」が近いから合意とする、高silhouetteをTAの成功とする。
- **代替説明**: 共通語、話者の言い回し、司会の反復、文脈補完、切詰めがクラスタを作った可能性。


- **G5 CPU局所観測（4d92d0a）**: M33-14-N/Xを下記G5一覧の条件で確認。入力文脈の境界だけ実確認、embedding/clusterは未起動。意味品質・本人採否は別判定で、近さ=同意・silhouette=TA成功の意味判断NOTRUN。

## 15. 音声感情推定

- **固定定義**: `exp-speech-emotion-recognition`／`expert-speech-emotion-recognition-definition`／D1／[01-Expert](../10-Experts/speech-emotion-recognition/01-Expert.md) raw SHA-256 `fe5853d9461963f504b329f7d6956c03c882e9fbf955c2a03b620a767164a1b9`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `ser-p1`（モデル（くしなだ・いざなみ）、リポジトリ、fold、学習データを記録する）、`ser-p2`（発話音声を切り出して推定し、話者・モデル・ラベル別に集計する）／R: `ser-p3`（短い区間、重なり、音質の不良、未推定の発話を確認する）、`ser-p4`（必要な箇所を聴取で確認し、推定と手修正を区別して報告する）
- **分析単位**: 話者分離後の発話音声の区間
- **必要入力**: 音声ファイル；話者分離と発話区間；感情推定の結果（モデル名、リポジトリ、fold）
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 固定会話から切り出した音声区間を対象に、モデル別の推定済み・未推定・除外を分ける。分類ラベル、聴取者に知覚された感情、本人が経験した感情は別。既存音声モデル推論と専門家LLM補助の許可は別で、後者は禁止を維持する。
- **研究者だけの判断**: 音質・分離・短区間・重なりの適否、聴取との照合、参照ラベルと評価者間の不一致、解釈の限界。研究者採否は未回答。聴取だけで本人の感情の真値が得られるとはしない。
- **一次資料と今回の読了範囲**: [くしなだ公式card](https://huggingface.co/imprt/kushinada-hubert-large-jtes-er) と[いざなみ公式card](https://huggingface.co/imprt/izanami-wav2vec2-large-jtes-er) のModel description、Demo、RESULTS/Accuracy、JTES citation、License/access条件を実読。JTES v1.1での掲載平均accuracyは各0.8477/0.8012で、この会話の精度ではない。重み・評価データ・学習は取得／実行せず、JTES原論文本文と実会議性能は未確認。
- **AIレビュー判定・具体的差分**: 推定出力の補助指標に限定する方針は適切。現01 `ser-a1` のmin:1は [method_experts.py](../../../../src/gurumoji/method_experts.py) でcoverage_percent>=1と判定され、0.5%ならfailになる。説明は「推定済み発話がありません」なので、1件以上を意図するなら条件の齟齬、1%以上を意図するなら判定は意図通りで説明が不正確という**仕様確認待ち**。局所関数で0.5%のfailだけを確認し、UI表示は未実行。80%も製品上の目安。いざなみcard未読という06の欠落は今回補えたが、自然会話への妥当性は未解決。
- **正常例 M33-15-N（合成設計）**: 10区間中8推定、ang3/hap2/sad1/neu2、未推定2を分け、モデルとカバー率80%を併記する。実音声を推論した例ではない。
- **負例 M33-15-X（禁止・不適合）**: angから本人が怒っている・攻撃的、neuから平静、cardのaccuracyから当該会話の正解率を断定する。
- **代替説明**: 雑音、他話者混入、短い音声、学習領域との差でも分類は変わる。


- **G5 CPU局所観測（4d92d0a）**: M33-15-N/Xを下記G5一覧の条件で確認。推定済み形式8/欠如2とモデルID維持。実音声推論ではない。意味品質・本人採否は別判定で、ang=本人感情・card精度=会話精度の意味判断NOTRUN。

## 16. 日本語テキスト前処理

- **固定定義**: `exp-japanese-text-preprocessing`／`expert-japanese-text-preprocessing-definition`／D1／[01-Expert](../10-Experts/japanese-text-preprocessing/01-Expert.md) raw SHA-256 `8576c0202b84e1f4eccee6d99d2ef33452e68e15155f8cc223a6e769f7c16bc3`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `pre-p1`（解析器・辞書・分割モード・ストップ語を固定し、版を記録する）、`pre-p2`（形態素と係り受けを解析し、発話ID・文ID・トークンIDと一緒に保存する）、`pre-p3`（簡易解析や利用不可の状態を、後段の分析の結果に伝える）／R: `pre-p4`（解析の誤りをサンプルで監査し、必要なら辞書やストップ語を明示的に追加する）
- **分析単位**: 形態素（トークン）と形態素間の係り受け。発話ID・文ID・トークンIDで対応させる
- **必要入力**: 除外していない本文；解析器・辞書・分割モード（既定C）・ストップ語の設定
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 固定会話の非除外本文に、解析器・辞書・実効pipeline・分割・ストップ語を適用する。トークンや依存辺は推定値で、原文ID・文字位置との対応と利用不能の伝達が必要。
- **研究者だけの判断**: フィラー・固有名詞・専門語・誤変換の監査と辞書修正の適否。研究者採否は未回答。言語モデル利用と専門家LLMの許可は別で、AI補助禁止を維持する。
- **一次資料と今回の読了範囲**: [GiNZA v5.2.0 README](https://github.com/megagonlabs/ginza/blob/v5.2.0/README.md) License、依存、Training Datasets、モデル・分割の該当記述、[公式日本語ページ](https://megagonlabs.github.io/ginza/) のモデル評価表・注記、モデル指定、訓練コーパス、互換情報を実読。現ページにはv5.3情報もあるので固定v5.2の根拠へ混ぜない。BCCWJ系の評価を、当該会話の精度としない。日本語会話の独立評価データは未確認。
- **AIレビュー判定・具体的差分**: [research_analysis.py](../../../../src/gurumoji/research_analysis.py) は `ja_ginza` を明示するため、06の「読み込むモデル未確認」は静的に解消できる。ただし今回のロード成功・実モデル版は未確認。結果engineのginzaパッケージ版だけではモデル版・辞書版・実効pipelineを再現できない。GiNZA互換fallbackはcompound_splitter/bunsetu_recognizerを除外し、Sudachi単独の利用者指定split_modeとGiNZAのモデル設定も異なる。これらを同一条件として比較しない。
- **正常例 M33-16-N（合成設計）**: 「ええと、予約は、取り直しました」の表層・原形・正規形と原文を突合する。Sudachi単独なら形態素利用可・構文利用不可を別に報告。
- **負例 M33-16-X（禁止・不適合）**: 正規表現fallbackを正式形態素と混ぜる、構文の空配列を依存関係不存在とする、書き言葉の精度を会話の正解率とする。
- **代替説明**: ASR誤変換、句読点、辞書不足、分割mode・モデル・実効pipelineの差。


- **G5 CPU局所観測（4d92d0a）**: M33-16-N/Xを下記G5一覧の条件で確認。簡易文字種分割/fallback/構文利用不可を保持、正式形態素と混同しない。意味品質・本人採否は別判定で、構文空=不存在・書き言葉精度=会話精度の意味判断NOTRUN。

## 17. 会話間比較

- **固定定義**: `exp-cross-session-comparison`／`expert-cross-session-comparison-definition`／D1／[01-Expert](../10-Experts/cross-session-comparison/01-Expert.md) raw SHA-256 `8f19105b11a2d3c208b892ad12285a648620e0e6083fcb39ced85d77119c837a`
- **許可・実行段階**: AI補助禁止。AI: なし／K: `cmp-p2`（会話ごとの集計（発話量、共通語、特徴語、手動コード、感情ラベル）を並べる）／R: `cmp-p1`（比較の目的と、含める会話の基準を決める）、`cmp-p3`（違いを、会話ごとの元の発話に戻って確認する）、`cmp-p4`（会話を独立な単位として扱い、会話の数が少ない比較で一般化しない）
- **分析単位**: インタビュー（会話・グループ）。値の根拠は各会話の集計
- **必要入力**: 比較する会話（2回以上）；比較グループと質問設計の同一性の確認；各会話の逐語録の準備状態と話者の確認
- **現行契約**:
  - 専用07/08なし。既定契約でAI実行可とは扱わない

- **対象集合・方法**: 選定した2会話以上の別runを比較し、問い・質問設計・準備・前処理・コード定義・モデル・分母の同一性を確認して原発話へ戻る。集計単位は会話だが、同一参加者の反復セッションまで独立とは限らない。母集団への推論ではなく、選定会話内の記述比較に留める。
- **研究者だけの判断**: 会話の選択と比較可能性、反復参加の扱い、差の解釈、元資料の確認。研究者採否は未回答。LLM補助は禁止。
- **一次資料と今回の読了範囲**: [樋口2017](https://www.jstage.jst.go.jp/article/jsr/68/3/68_334/_pdf) §3.4.2周辺p.344・§4 pp.346–348、[Gale et al. 2013](https://link.springer.com/content/pdf/10.1186/1471-2288-13-117.pdf) PDF pp.5–6のStages 5–7/Discussionを実読。[Aartsの著者大学公開章](https://research.vu.nl/ws/portalfiles/portal/42165179/chapter%202.%20A%20solution%20to%20dependency%20-%20Using%20multilevel%20analysis%20to%20accommodate%20nested%20data.pdf) は2014原著の2016学位論文収録版、印刷pp.14–18のAbstract/§2.1.1/Box 2.1を実読。全31ページ・補足シミュレーションは未読。これらは比較・依存・文脈保持の根拠で、当該製品の会話数閾値を検証したものではない。
- **AIレビュー判定・具体的差分**: 記述比較に限定し推測統計をしない現実装は維持する。[interview_comparison.py](../../../../src/gurumoji/services/interview_comparison.py) の `categorical_rows` は感情ラベル欠如を0とし、全included_segment_countで割る。合成メタデータA=100件・coverage100%・sad20、B=100件・coverage5%・sad1を比較関数へ注入すると20%対1%を返し、interviewsに感情coverageを引き継がないことを局所確認した。上流の推定処理を再現した試験ではない。未推定と観測されたゼロを区別して説明できず、推定済み内の分母なら両者20%という違いを隠す。全発話あたりのラベル出現率自体は定義可能だが、感情差として比較するにはcoverage併記が必要。コード名が同じでも定義同一とは限らず、01/02の会話の独立性も設計条件付きにする。
- **正常例 M33-17-N（合成設計）**: 同じ質問設計の2グループを同じ前処理・観測分母で比較し、特徴語差の元発話IDへ戻る。結論はこの2会話に限定する。
- **負例 M33-17-X（禁止・不適合）**: 発話を独立標本として検定、質問の違いを属性差と断定、反復参加者の会話を自動的に独立とする。
- **代替説明**: 司会語彙、会話長、コード定義、モデルや推定カバー率の差でも比較値は変わる。

- **G5 CPU局所観測（4d92d0a）**: M33-17-N/Xを下記G5一覧の条件で確認。既知の分母/coverage差を再現。会話数1はcmp-a1 blocked。意味品質・本人採否は別判定で、観測差から感情差・反復参加の独立性を結論する意味判断NOTRUN。

## 次の実装候補：最大3群、いずれも未着手

下記はC0と研究者が範囲・仕様を決めるための候補。ここにpathを挙げても編集許可・採用・新しいAI権限は生じない。既存の保存・Handler・検証責務を再利用し、新method・別DB・一括専門家展開を作らない。

### 群A：観測分母と「未推定」を一致させる

- **専門家／用途**: `exp-speech-emotion-recognition`、`exp-participation-balance`、`exp-cross-session-comparison`。観測件数・対象人数・推定カバー率を取り違えず、記述比較の不足を表示する
- **契約**: 3定義のAI禁止を維持。全対象N・推定済みN・未推定N・モデル別Nを区別し、比率には分子と分母の型を付ける。SERの「1件以上」と「1%以上」のどちらを意図するか人が決める。参加均衡の単独参加者は解釈不能を明示。未推定全件を観測ゼロへ変換しない
- **候補path**: `src/gurumoji/method_experts.py`、`src/gurumoji/services/group_analysis.py`、`src/gurumoji/services/interview_comparison.py`、対応する3専門家の `01-Expert.md`、`tests/test_method_experts.py`、`tests/test_interview_comparison.py`。定義変更時は版/hashと登録pinの影響をC0が別途確認
- **正常例**: 2会話とも100件を推定してラベル20件なら、20/100とカバー率100%を同じ条件で表示
- **負例**: 100件中5件だけを推定してラベル1件を、別会話の20/100と無注記で比較。司会を除くと1人しか残らない集合で「参加が均等」と表示
- **技術的解除条件**: count・percentage・未実行・ゼロ・複数モデル・役割除外の合成境界試験が分母を追跡でき、旧データのunknownを補完しないこと。独立レビューで定義と表示を照合し、既存表/export互換を確認。解除するのはこの計算・表示差分だけで、感情の真値・参加の公平性・一般化は認定しない

### 群B：統計の名称・近似条件・独立単位を明示する

- **専門家／用途**: `exp-descriptive-statistics`、`exp-group-comparison-statistics`、`exp-correlation`。既存S2/C2の結果説明で、数値の正しい出所と推論可能範囲を揃える
- **契約**: `statistical-tools-1` と `statistical-cells-v1` の同run・対象集合・9キーのセル束縛を維持。Kruskal効果量の式・名称・出典を一つに固定し、小標本Spearmanの近似と発話の非独立性を結果状態へ明示する。未実装の置換・Welch・多重比較補正・入れ子モデルを行ったことにしない
- **候補path**: `src/gurumoji/research_analysis.py`、`src/gurumoji/services/analysis_orchestration_methods.py`、`src/gurumoji/services/expert_agents.py`、統計3の `07-Agent-Contract.md`、`tests/test_research_analysis.py`、`tests/test_statistical_expert_agents.py`。既存01〜06の説明・版/hashの整合は同一の承認範囲で扱う
- **正常例**: 固定表のN・欠測・係数とセルhashが一致し、効果量の式を明示した探索的説明。p値の計算成功と独立性の未確認を別欄にする
- **負例**: 発話100件を独立した100人と説明、N=10だけでSpearman p値の精度を保証、別結果の同じ数値だけを流用、効果量の名称と式を別方式から混合
- **技術的解除条件**: 名称と式の固定fixture、N/欠測/同順位/定数/小標本、異なるresult・rows_hash、本人未回答の対照例が合格。AI説明の自由文は引き続き人の意味評価対象。統計モデル追加や「有意」を認定する仕様拡張は別依頼

### 群C：Frameworkの「ケース」と製品範囲を分ける

- **専門家／用途**: `exp-framework-method`。同一話題を持つ資料をケース×カテゴリーへ戻れる形で整理し、方法そのものの不適合とアプリの未対応を区別する
- **契約**: D1のAI許可 `fw-p3/fw-p6` とRの枠組み確定・解釈を維持。ケースの定義と構成員は研究者入力に束縛し、単純な話者数からケース数を推定しない。文書を扱える方法論と現在の逐語録用入力を分離し、製品非対応は `unsupported/needs_input` として説明する
- **候補path**: `docs/program-vault/50-Analysis-Methods/10-Experts/framework-method/01-Expert.md`、同 `02-Procedure.md`・`04-Applicability-and-Limits.md`、`src/gurumoji/method_experts.py`、`tests/test_method_experts.py`、`tests/test_method_expert_samples.py`。既存手動case matrixを使える範囲から始め、専用07の追加や汎用ケースエンジンはこの群の前提にしない
- **正常例**: 研究者がケースを1つと定めた共通話題の資料では、within-caseの記述比較と、ケース間比較をしないことを区別できる
- **負例**: 司会＋参加者1人の話者数2を独立2ケースとする、異質な資料を共通カテゴリーへ無理に押し込む、現UIで未対応という理由だけで「Framework法は文書を扱えない」と断定
- **技術的解除条件**: 話者数とケース数が一致／不一致の合成対で、原典要件・製品条件・本人確認が別の理由コード／表示となる。1ケースを許可しただけで未対応資料を実行・保存しない。引用元セルへの来歴を保ち、方法の最終採否は本人に残す

他専門家をこの3群へ便乗して実装しない。TA/FGIの既存候補契約を広げる前に実際の意味評価・研究者判断を行う。KJの原典、M-GTAの詳細、日本語会話でのモデル妥当性などはコードの通過条件では解決しない。

## 本作業の検証・未実行

- **成功**: 17定義のfrontmatterと実行YAMLのexpert ID・版・AI可否を照合し、01のraw SHA-256を再計算。9許可／8禁止、07=5、08=4を確認
- **成功**: Python 3.12.14でfrontmatterをYAML解析し、note IDの一意性、17自己完結節、正常／負例／代替説明各17件、106段階のID・題名、ローカル参照52件（39種類）の存在を照合。strict UTF-8・NFC・BOM/置換文字/双方向制御文字なし・末尾改行を確認。`git diff --cached --check` はexit 0、`git diff --cached --name-status` はこの1pathの追加だけ
- **局所確認**: Python 3.12.14の `python -B` で公開コードの純関数だけをASTからメモリ内ロードし、合成入力を確認。SERはcoverage=0.5・min=1でfail、会話間比較は100発話ずつ・sad20/1を20%/1%として返しcoverage欄なし、単独参加のGini/evenness helperは0/1。局所確認スクリプトはexit 0。比較のcoverageは注入メタデータで、上流モデル推定・役割除外の全経路を検証したものではない
- **実施範囲の別記**: 公開一次資料の実読範囲は各節に限定。コード読解をもとにした差分と、合成の局所関数確認を区別する。文書のレビュー結果は、アプリや各手法の合格件数へ加算しない
- **失敗・制約**: 全原典の全文を取得・精読したわけではない。KJの書籍等、未入手・部分確認の範囲は各節に残す。アクセスできなかった資料を読了としない
- **未実行**: 本ノートの正常／負例を用いたHandler/Store/UI統合試験、全app suite、実DB・実研究Vault・実媒体、外部AI呼出し、モデル取得・実推論、認証／環境変更、実研究の意味品質・方法妥当性・本人採否、G5全体評価。既存CPU受入を今回再実行したことにしない
- **変更範囲**: この新規Markdown1pathだけ。既存01〜08・readiness・index・manifest・production source・testsは変更しない。公開技術情報と合成例のみを収録

## 研究者への短い採否票

まず主に使う専門家1つについて、下記を埋める。未回答は保留であり、AIが採用を補わない。残る専門家を一括承認する必要はない。

1. 対象expert／D版・hash：＿＿＿＿　採否：方法・既存補助を採用／条件付き／保留
2. 研究質問・流派、分析単位と対象集合、一般化しない範囲：＿＿＿＿
3. 正常例・負例・代替説明を踏まえた採用理由、まだ読む原典／追加条件：＿＿＿＿
4. 研究者名・判断日：＿＿＿＿

この票は方法選択の記録案であり、01のAI許可段階を広げたり禁止8分野を解除したりしない。実runの対象hashに束縛した本人記録や、各研究者段階の実施記録を代行しない。技術的な解除と方法論の採用は別々に判断する。

## G5追加：17専門家の合成CPU受付と限界（2026-10-09 UTC）

### 範囲・出典・判定語

正式票 [6090396377](https://github.com/krokharu/gurumoji/issues/33#issuecomment-6090396377)、文書取込許可 [6090472933](https://github.com/krokharu/gurumoji/issues/33#issuecomment-6090472933)、受領 [6090501327](https://github.com/krokharu/gurumoji/issues/33#issuecomment-6090501327) に対応する。コード/test基点は `4d92d0a45dcede55ebb1c991343fe12a2a8295f3`、parent `95a33e9acb85348f1c94982b6ff75abee090d9ff`、tree `1fbb7a35b2826dbdb77e9faf817e43373ca08ba9`。文書だけを公開 `2793c91d844331f01c25b1e7fd917a1b47f4175a` の同pathから取り込み、初期blob `5f293a4f586e853943b2196f7da66fc54a70c395`／81,183 bytes／raw SHA-256 `8a82aadb1c827d15eb931327307c0bcd0a1de129d6676bf59e525f9671059c7d` を照合後に今回の追記を行った。merge/cherry-pickや別branchの修正の取込はない。G5-A/B/Cの後続修正版をこの4d92コードへ混ぜず、本文に残る古いSER閾値・参加分母・統計注記・Framework説明の観測を修正版の再受入と区別する。

- **試験PASS**は、具体的入力に対する現在の受付・拒否・既知限界がassertionと一致したことだけ。既知不適切散文が通ることをPASSとして検出しても、その散文の意味は**不適切（FAIL）**であり、意味品質の合格ではない。
- **accepted_unreviewed_draft**は今回の観測分類。製品に新しい保存statusを足していない。手書きの合成応答を既存validatorへ渡し、モデル呼出しは0。正常案も研究者が採用した結果ではない。実モデルの意味品質は全17でNOTRUN、研究者採否は未回答・HumanRecord入力0。
- AI許可9／禁止8は実Catalogからassertする。禁止8分野はCatalogの条件・code/human契約と必要最小の純関数だけを通し、Registryも `expert_ai_unavailable` を返す。これはLLMを起動した試験ではない。
- C1は渡した根拠ID・profile/knowledge hash・許可stepの一致を検査する。`actor_id`、散文とstepの意味対応、入力本文hashとの意味束縛は直接検証しない。今回のsource ID/version/hash・合成実行主体はfixture/receiptに固定し、この外側の保持と製品内の検証を混同しない。入力packetの本文・data_version不変は別にassertした。
- 統計は実既存Python計算、全対象/除外、変数ごとの欠測、manifest/rows hash、9キーセルbindingを確認した。計算済み値からの説明と未実行手法を散文で主張する負例を分離する。同run DB台帳、実配送receipt、Store保存後の再読込はNOTRUNで、保存来歴を検証済みとは記載しない。
- 過去のregistry・CPU件数は歴史資料であり、今回18件へ加算しない。一次資料は新しく閲覧していない。各行の「R9読了」は上の元17節の読了範囲を指し、未読原典を読了へ変更しない。PNG延期、G0.5/M/G5/研究者採否の独立HOLDは維持する。

### 17分野の具体的normal/negative入力と結果

N/Xは同番号のM33ケース。各専門家1行で、局所試験名は `tests/test_expert_methodology_acceptance.py::ExpertMethodologyAcceptanceTests.test_NN_*`。共通test18は17定義と9/8権限、知識note ID/raw hash、profile/bundle hashを照合する。Catalogのreadyは人の確認を含まず、human_reviewはhumanのまま。

| No./専門家 | normal入力 | negative入力 | 実行経路 | 実観測 | 意味判断 | 権限根拠・一次資料の読了状態 | NOTRUN・次owner/解除条件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 質的内容分析 | u1「聞きたいが先輩が接客中」→研究者定義の相談機会制約の候補 | 「12発話=12人の最重要課題、κ未計算だが確認済み」 | C1 request_packet→validate_report | 両文ともaccepted_unreviewed_draft。外部根拠ID／別profile hash／研究者stepは拒否 | 負例の意味は不適切（FAIL）。頻度=人数・重要性、未実施信頼性の主張は禁止 | §01 Mayring §1–7等はR9部分読了、他原典は未読。01の単位/AI brief/研究者step | 研究者: 単位・カテゴリー規則・前後文脈・信頼性を確認 |
| 02 テーマ分析 | u1評価不安/u2援助経験→「能力評価への警戒と相談の許可感」の候補 | 質問項目をそのまま最重要・研究者確定テーマとする | C1 request_packet→validate_report | 両文ともaccepted_unreviewed_draft。型/根拠/step拒否境界は維持 | 負例FAIL。質問項目や最多クラスタはテーマ確定・重要性の証拠ではない | §02 Braun/Clarke掲載pp.81–88,94–96等はR9部分読了、2021本文未読。01研究者ta-p4以降 | 研究者: 全体・反例照合。typed TA/保存採否は別試験までNOTRUN |
| 03 Framework | A/B×相談機会/支援相手セルにu1/u2要約、語られない支援は保留 | 件数だけでcharting完了、空セル=不在、13/20=母集団支持率 | C1 request_packet→validate_report | 両文ともaccepted_unreviewed_draft。実製品gateは話者数のまま | 負例FAIL。要約・文脈・ケース定義と件数は別、一般化は不可 | §03 Gale PDF pp.1–7の記載範囲はR9部分読了、Ritchie/Goldsmith本文未読。01 fw-p6/研究者解釈 | 研究者: ケース・枠組みを確定。別branchのG5-Cを今回へ取込まず |
| 04 SCAT | u1「忙しそう」〈1〉と観察/推測の疑問〈5〉候補のみ | AIで〈2〉〜〈4〉と完成理論を生成し実施済みとする | C1 request_packet→validate_report | 両文ともaccepted_unreviewed_draft。研究者stepをperformedに入れると拒否 | 負例FAIL。許可段階はscat-p2/p6、欄の存在は理論生成の許可ではない | §04 大谷2011 pp.155–160記載範囲はR9部分読了、表視覚/2008本文未読。01 actor/brief | 研究者: 〈2〉〜〈4〉・ストーリーライン・理論。専用型は今回追加なし |
| 05 M-GTA | 新人の相談過程、定義「相談の許可感」の具体例/反対例u1/u2 | 焦点者なしの細切れ自動コード化、検索増加なし=理論的飽和 | C1 request_packet→validate_report | 両文ともaccepted_unreviewed_draft。分析前提の意味充足は未検査 | 負例FAIL。概念/焦点者・理論的サンプリング/飽和は研究者責務 | §05 公式Q&A2項目はR9実読、2007本文/書籍未読。01 mgta-p4/p5とhuman steps | 研究者: 焦点者・概念定義・採らない解釈・飽和根拠 |
| 06 KJ | u1「価格はよいが予約が難しい」の入力条件をCatalogへ | 対象0件→kj-a2 fail。自動cluster=KJ完成の意味検証器はない | Catalog.review→Registry禁止確認 | 入力あり非blocked/0件blocked、全10手順researcher、expert_ai_unavailable | 二ラベル化・表札/孤立ラベル・KJ完成の意味判断NOTRUN | §06 手引pp.102–106/2003論文選択頁はR9部分読了、原典書籍未読。01全step researcher | 研究者の実ラベル/編成記録が必要。専用機能なし、AI代行禁止 |
| 07 計量テキスト | u1「費用」3回＋u2 1回→TF4/DF2/観測話者2 | 同じ4回を4人・最重要・原因にする推論は実行しない。fallback入力でqta-a3 fail | _linguistic_analysisを明示fallback＋Catalog | 4/2/2を実計数、fallback/研究利用不可を明示、状態needs_attention | 人数・重要性・因果の意味検出NOTRUN。TF4≠観測話者2を確認 | §07 樋口2004/2017の列挙節はR9部分読了、全論文/書籍未読。01コード/研究者分離 | 正式解析器の別受入、研究者による否定/引用/KWIC確認 |
| 08 FGI | u1毎週対面→u2月1提案→u3変更→u4応答を不同意/変更候補へ | 相づちだけで全員合意、沈黙=同意、人確認済みと断定 | 既定C1 request_packet→validate_report | 両文ともaccepted_unreviewed_draft。typed FGIの意味拒否結果とは別 | 負例FAIL。連鎖と機能・司会影響の研究者確認は未実施 | §08 Grønkjær/Hermann列挙頁はR9部分読了、全原典精読でない。01 fgi-p3/p5 | 研究者: 連鎖/儀礼応答/意味。typed S1・Handler/StoreはNOTRUN |
| 09 参加バランス | 観測A/B各30秒→Gini0/evenness1/HHI.5、名簿なし | singleton helper→0/1/1かつcomputed。Catalog話者1はpart-a1 blocked | _participation_balance＋Catalog | 計算された観測分布と名簿未確認を保持。単独指標の既知制約を再現 | 公平性・全員均等・低発話=無関心の意味判断NOTRUN | §09 WoolleyはR9 Abstractのみ、測定詳細未読。Grønkjær p.25部分。01 denominator制約 | C0: 基点のsingleton境界を別票で判断。研究者: 名簿/役割/発言機会 |
| 10 会話時間 | u1[0,2],u2[5.5,7],u3[6.5,8]→gap3.5/overlap.5 | 全time_unknown→候補空、20中11時刻不正→time-a1/a2 fail | _long_gaps/_overlap_candidates＋Catalog | gap/overlap候補を算出。欠測から不存在へ昇格せず、gap出力は発話IDなし | 重なり=対立・無音=熟考/同意の意味判断NOTRUN | §10 Levinson/Torreira列挙節/Table2はR9部分読了、音声/原コーパス未確認。01 code/human分離 | 研究者: 音声/境界/相づち。C0: gap出典IDの不足は別票 |
| 11 記述統計 | 5発話＋除外1、時間有効N4/欠測1/平均4.25、文字N5/欠測0 | 同じ話者の各発話をそれぞれ別人として集計した | 実descriptive_statistics→manifest→9キーbinding→validate_report | 固定セル受理＋負例散文accepted_unreviewed_draft。hash改変/行改変は拒否 | 負例FAIL。発話単位と人単位の混同。数値一致は独立性保証でない | §11 JARS列挙頁/SciPy APIはR9部分読了。01 desc-p2/codeとhuman target/missing | 研究者: 対象・欠測・独立単位。保存/本人記録はNOTRUN |
| 12 群比較 | 同じ5発話の話者×質問候補crosstab、total分母5、除外1 | 標準ANOVAの結果はWelch法による群間比較であり、多重比較補正済みである | 実crosstabs→manifest→9キーbinding→validate_report | 固定count/分母受理＋負例散文accepted_unreviewed_draft。実行したのはcrosstabsのみ | 負例FAIL。未実行のANOVA/Welch/補正を主張、方法名と計算の不一致 | §12 SciPy/rstatix等とDelacre列挙頁はR9部分読了、全simulation/原著未読。07計算binding | 研究者/C0: 前提・独立性・方式の意味照合。追加計算/保存はNOTRUN |
| 13 相関 | 同じ5発話の時間×文字数Pearson、完全ペアN4/欠測1 | Spearman近似はこの小標本でも必ず正確、説明変数が結果を引き起こした | 実pearson→manifest→9キーbinding→validate_report | 固定係数/N受理＋負例散文accepted_unreviewed_draft。実行したのはPearsonのみ | 負例FAIL。別手法・小標本精度の保証・因果断定は束縛セルから導けない | §13 SciPy API/Bishara列挙頁はR9部分読了、全条件/原著未読。01 cor-p2/codeと研究者解釈 | 研究者: 散布/外れ値/独立性。Spearmanや定数列の追加probeはNOTRUN |
| 14 埋め込み探索 | 同一話者「駅まで歩く」「バスの本数」を文脈連結、元ID維持 | 別話者なら連結しない、保存結果stale=True→emb-a1 blocked | _contextual_texts＋Catalog | 入力文脈の境界だけ実確認、embedding/clusterは未起動 | 近さ=同意・silhouette=TA成功の意味判断NOTRUN | §14 E5論文/card/Chang列挙範囲はR9部分読了、全appendix未読。01モデル計算と研究者命名 | モデル実行の別許可・固定版と代表/境界例の研究者評価が必要 |
| 15 音声感情 | 合成10区間中ang3/hap2/sad1/neu2、空2をparserへ | 空labelは欠如。coverage .5%→現ser-a1 min1/a2 min80 fail | analysis_emotion_entries＋Catalog | 推定済み形式8/欠如2とモデルID維持。実音声推論ではない | ang=本人感情・card精度=会話精度の意味判断NOTRUN | §15公式model card記載部はR9実読、JTES本文/実会議性能未確認。01 ser-p3/p4 researcher | C0: .5%説明差は別票。研究者: 音質/参照ラベル。実推論別許可 |
| 16 日本語前処理 | 「ええと、予約は、取り直しました」の表層offsetとu1を保持 | 強制regex fallback→pre-a1/pre-a2 fail、構文edges=[] | _analyze_with_fallback/_linguistic_analysis＋Catalog | 簡易文字種分割/fallback/構文利用不可を保持、正式形態素と混同しない | 構文空=不存在・書き言葉精度=会話精度の意味判断NOTRUN | §16 GiNZA固定v5.2 README等はR9列挙範囲読了、会話独立評価なし。01 pre-p3伝達 | 固定モデル/辞書の別試験、研究者による表層・原形・正規形監査が必要 |
| 17 会話間比較 | 同質問identityのA/B各100、coverage100/100,sad20/20→20/20 | Bだけcoverage5,sad1→全発話比20/1、coverageが出力へ継承されない | build_interview_comparison注入集計＋Catalog | 既知の分母/coverage差を再現。会話数1はcmp-a1 blocked | 観測差から感情差・反復参加の独立性を結論する意味判断NOTRUN | §17 樋口/Gale/Aarts列挙頁はR9部分読了、全章/補足未読。01会話単位/文脈 | C0: coverage伝達は別票。研究者: 設計/反復参加/モデル同一性。上流推論NOTRUN |

### 今回fixtureのsource固定と保存未実行

各sourceは `synthetic-M33-NN`。source versionは合成入力のcanonical JSON fingerprint、source hashも同じ完全入力から算出する。これは実研究データ・実runの入力版ではない。01のraw hash/定義版は上の各固定定義と一致し、現profile/knowledge hash、許可step、計算raw hashとセルbindingは外部検証receiptにも記録した。既存の過去hash・履歴は書き換えない。

| No. | 合成source version / content hash |
| --- | --- |
| 01 | `sha256:b45b51a5258aff9a06ca48d312853418f083fcc8b60b89d3ba3dec55a23cba49` |
| 02 | `sha256:af8d8ced53d0ada3d8a60ca40661d7183ea12b6be09ccc43577fb90ab68772b2` |
| 03 | `sha256:273803efab49fa8ad4f780ab78d3f55c4470dace2dda1bec068d9c19402b5409` |
| 04 | `sha256:87d8717f853fc9fead975efe2d81028ea5af7f0d520ee33c66957e8e44988a15` |
| 05 | `sha256:4645d711966040fc05d47c005cc8504735c21e17f3203a3839ebde0c11ea01e6` |
| 06 | `sha256:16c76ff984304db7a658d184a62ce16d84b4a139f9e9e990ed5c79a8e93827b7` |
| 07 | `sha256:8cc65d66da88daa3da8f50d4feab787e8a5481effe4ef097166fe986a98d9eb2` |
| 08 | `sha256:4d9fe0d06514287b53e470eecdf69242779815684ca92282ab5e5531b1e3c8ad` |
| 09 | `sha256:5388abc7d52368b6bfe8eeafebb3fed78296d75e02ce4dea7ef09a649b162cb2` |
| 10 | `sha256:db1890a5f9dcd810595f97e1dfa5a7632c20224264e7b51e5ea432ad546557c8` |
| 11 | `sha256:a50cd47999e139672d9f00441316322e71c6e4e08fbcb608140774386f635e9d` |
| 12 | `sha256:a50cd47999e139672d9f00441316322e71c6e4e08fbcb608140774386f635e9d` |
| 13 | `sha256:a50cd47999e139672d9f00441316322e71c6e4e08fbcb608140774386f635e9d` |
| 14 | `sha256:8d7342846a0ed73c7a8a9518e3aaaa9aaa875e29082894ae40ab6fcd0eeeca3c` |
| 15 | `sha256:ab0d1fe6cac81ae6a3d98c3cef18df6f5a13301511168c88d3833693ce5105f3` |
| 16 | `sha256:a4dccabffbd41b972a8051a23a78065bb913a7a53deed982811bcd17d92e2250` |
| 17 | `sha256:1107db716ee2b08c68cc2381d082a209b8a3cf6e05a7e6a5445c374da8a6744b` |

### Linux実行記録と未実行

実行先はLinux 6.18.44 x86_64/glibc2.41、Python 3.12.14、既存SciPy 1.17.0。installなし。作者は隔離branch `dot/g5-methodology-acceptance` で実行した。初回は18 tests / PASS18 / FAIL0 / ERROR0 / SKIP0、unittest 1.323秒、wrapper全体1.662610秒、exit0。初回から失敗がなかったため途中FAILの隠蔽はない。最終test bytesの再実行も18 PASS / FAIL0 / ERROR0 / SKIP0、wrapper全体1.570130秒、exit0。途中の再確認も全件PASSで、これらを別の方法受入件数へ加算しない。

再現コマンド（Linux、repo root、既存Pythonを指定）:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /workspace/scratch/be1eb353f7eb/analysis_orchestrator_fixes/app/.venv/bin/python -B -m unittest test_expert_methodology_acceptance -v
```

初回・最終作者実行では同じsuiteをunittest runnerで実行し、socket/SQLite接続とtorch/transformers/sentence_transformers/openai/anthropic/whisper importをaudit guardで拒否した。tests自身もsocket接続を拒否し、言語解析のfallback試験では既存モデルloaderを無効にした。テストによる実モデル/SDK/GPU/外部AI/実DB/実Vault/媒体/auth/settingsの使用は0。計算用の合成dictと空の一時local override directoryだけを使う。

未実行: 全app suite、TA/FGI明示typedの深い統合、Handler/Store/UI経路、実runの同run配送/永続化/再読込、実言語/embedding/音声モデル、実研究の方法妥当性・意味品質・全研究者手順と採否。実装がないKJ整理や意味検出器は未実装/人待ちとして残す。追加実行には表の条件に沿う別scopeと必要な許可が必要。別作者LinuxレビューとC0 Windows独立受入はこの作者記録と別枠で、未実施のまま返す。

変更対象はこの文書と新規testの2pathのみ。production、01/07/08、API/Store/schema/SQL、研究者記録、既存tests、readiness/index/manifestは変更していない。
