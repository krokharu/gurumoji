---
note_id: design-analysis-method-rules
note_type: registration-rules
title: 分析手法ごとのObsidian登録規約
status: proposed
updated: 2026-09-25
schema_version: 1
tags:
  - gurumoji/analysis
  - gurumoji/rules
---

# 分析手法ごとのObsidian登録規約

2026-09-13更新：組み込み手法の固定保存・AI仕上げの変更記録・Vault生成は実装済みです。現行API・テーブル・登録契約は [[30-Data/analysis-storage-v1]] を参照してください。この文書は差分取り込み・外部手法等の後続計画も含みます。

分析結果を「手法」「実行」「見解」「根拠」に分けて関連付ける。ひとつの会話で複数の手法・条件・実行結果を持てるようにする。表のデータセット名は現行の `ANALYSIS_CSV_FIELDS` と `RESEARCH_CSV_FIELDS` を基にしている。

## 全手法に共通する登録単位

| 種類 | ノート作成単位 | 識別・保存する内容 |
| --- | --- | --- |
| 手法定義 | 手法ID＋手法版ごと | 目的、適用条件、入力、計算法、出力schema、限界、出典 |
| 分析実行 | 分析実行IDごと | 会話、入力版、対象集合、条件、計算環境、結果ファイル、完了状態 |
| 見解 | 保存対象として選んだ見解ごと。短い見解は実行ノート内のブロックでもよい | 出所、主張、根拠、反例・限界、研究者の確認状態 |
| 根拠 | 入力版＋発話ID＋必要なら文字範囲 | 保存時点の原文、話者、時刻、元の会話・分析へのリンク |
| 人の考察 | メモIDごと | 自由記述、研究質問、関連手法、支持・反証・要確認の参照 |

標準ノートは「見解／観察」「条件と対象」「主な結果」「根拠」「限界・代替説明」「全件データ」「関連ノート」の順にする。数値は元表の精度で保存し、表示上の丸めを別扱いにする。空・未実行・実行不能・失敗を同じゼロとして扱わない。

## 現在の分析手法の登録ルール

| 提案する手法ID／現在の機能 | Obsidianに登録する内容 | 固定保存するデータ／条件 | 根拠・解釈のルール |
| --- | --- | --- | --- |
| `local_insights` ローカル見解 | 会話の入口に最大5項目。実行ノートに生成時点の見解 | `insights` のローカル行、対象集合、入力版、アルゴリズム版 | 各項目に発話ID・話者・件数。語の一致から意見の一致を断定しない |
| `kwic` 文脈検索 | 保存した検索ごとに目的、ヒット数、選択引用 | 検索条件JSON、全一致CSV。`q`, `mode`, `speaker`, 前後幅40文字 | 自由入力と正規化語を区別。同一発話内の複数出現は文字位置で別行。50件の表示ページは保存範囲にしない |
| `speaker_characteristics` 話者別特徴語 | 話者ごとの上位10語、対象・他話者の率と差 | `characteristic_terms`、対象・他話者の件数・分母・割合 | 発話出現率の差。語の延べ回数と混同しない。比較相手なしは算出不能。クリック・リンク先は話者付きKWIC |
| `transformer_topics` Transformerテーマ分析 | ノイズ除外・同一話者の短文文脈補完後の意味クラスタ、参加者／進行役候補を分けた代表発話・話者分布、相づちの話者×対象テーマ対応・応答率・探索的検定、話者別の会議リザルト、時間推移、例外候補 | `transformer_topics`, `transformer_assignments`, `transformer_speakers`, `transformer_timeline`, `transformer_outliers`, `transformer_backchannels`, `transformer_backchannel_speakers`, `transformer_backchannel_rates`, `transformer_backchannel_tests`, `transformer_speaker_results`、反応機会数・応答対象数・応答率・種類別件数・Pearsonカイ二乗・Cramér's V・期待度数診断、リザルト種別・対象テーマ・根拠発話ID・明示表現、相づちの種類・応答先発話ID・時間差、除外／文脈補完件数、話者補正、テーマの決め方（`auto`／`candidate`／`manual`）、候補ごとのsilhouetteと選んだテーマ数、手動テーマの定義（見出し・手がかり語・シード発話）と割り当てのしきい値、未割当・境界例の件数、保存済み意味ベクトルの再利用、モデルrevision、次元、K-means seed、silhouette係数 | テーマ名は汎用語を除いた特徴語による仮ラベル。低いsilhouette係数を警告する。相づち率の反応機会は他者の有意味発話数による代理分母。反復観測の非独立性と疎な期待度数があるため検定は探索用とする。話者別リザルトは本人の明示表現だけを抽出し、表現がなければ未判定とする。会議前調査との比較ではない。相づちの対象は時系列上の推定で、賛同とは断定しない。意味類似度から合意・重要性を断定せず、代表発話を原文と照合する。手動のテーマは研究者の見出しで、割り当ては最近傍の候補である。しきい値と境界例の目安は実装上の判断であり、割り当てを妥当性が確認された分類として示さない |
| `participation` 発話量・参加バランス | 会話全体／話者／属性群の集計、確認候補 | `speakers`, `groups`, `summary`, `observations`、除外・役割・属性・単位・しきい値 | 発話量を影響力や重要性の順位に置き換えない。分母と役割を表示 |
| `conversation_dynamics` 話者遷移・無音・重なり・時間推移 | 遷移表、時間区間、確認対象へのリンク | `transitions`, `gaps`, `overlaps`, `timeline`、各しきい値・時間窓 | タイムスタンプからの候補と明記。発話除外によって存在しない物理的無音を作らない。対象集合と元の時間配置を保存 |
| `segment_classification` 発話種別・確認スコア | 手動確定値とテンプレート・Jev・Transformerの提案比較、クロス集計 | `segment_classifications`, `segment_classification_crosstabs`、入力revision、規則版、Jevモデル・使用量、Transformer版 | 自動提案を人手の正解に置き換えない。重要度・要確認度・機密らしさは0〜100の選別スコアで、確率・法的判定ではない。Transformer話題の近さを発話機能や重要性に読み替えない |
| `morphology` 形態素・品詞 | 解析器、分割単位、代表例、品詞分布 | 全件 `morphemes`, `pos_frequency`、辞書・モデル・版・分割モード・ストップワード | プレビューから保存しない。表層形／原形／正規形／読みを保持。簡易解析は `fallback` とし正式解析と混合しない |
| `syntax` 係り受け | 対象文の構造説明と選択例 | 全件 `dependencies`、形態素入力への参照、解析器・モデル版 | 係り元・係り先・関係ラベル・発話IDを保持。利用不可なら理由を記録し空結果を成功扱いしない |
| `lexical_frequency` 頻出語・TF／DF | 上位語と集計の定義、保存した語へのリンク | `term_frequency` とJSON内の話者別語彙。既存 `keywords` は別系列と明記 | TF＝延べ出現、DF＝語を含む発話数を区別。旧簡易キーワードと正規化語の値を混ぜない |
| `cooccurrence` 共起 | 選択した語の関係図、主要エッジ、確認する文脈 | 全件 `cooccurrence`、語集合、最小共起数、Jaccard等の指標、発話単位 | 図には重みと条件を付ける。Obsidianのリンク関係と統計上の共起を区別し、語ごとの大量ノートは自動作成しない |
| `descriptive_statistics` 記述統計・度数 | 指標の分布、対象数、欠測、単位 | `descriptives`, `frequencies`、対象変数・単位・除外規則 | 要約値の根拠は対象集合と表の行キー。極端な発話を引用する場合は発話根拠も付ける |
| `group_statistics` クロス集計・群間比較 | 比較の目的、群の定義、集計表、結果・限界 | `crosstabs`, `statistical_tests`、変数・群・N・欠測・統計量・p値・効果量・前提条件 | 現在のχ²／Cramér's V、ANOVA／η²、Kruskal–Wallis／ε²を識別。未補正の多重検定と会話内発話の非独立性を表示。p値だけで結論を書かない |
| `correlation` 相関 | 変数対、方向・大きさ、対象数 | `correlations`、Pearson／Spearman、N・係数・p値・欠測処理 | 因果関係と断定しない。変数対・手法ごとに行キーを付ける |
| `qualitative_coding` 手動コード・重要引用・相互作用 | コード定義、採用／除外例、引用、比較表、解釈 | `codes`, `coded_segments`, `case_matrix`, `interactions`, `important_quotes`, `context`、コードブック版、注釈JSON | コードIDを維持。記入者・出所・確認状態を記録。頻度だけでテーマの重要性を順位付けしない。AI候補と確定コードを区別 |
| `ai_insights` 任意AI見解 | 総合見解、テーマ、共通意見、相違・少数意見、追加確認点 | `insights` のAI行、出力JSON、provider・model・prompt版・入力hash・使用量 | 内容の見解には有効な対象発話IDが必須。共通意見は複数話者の根拠。全対象の処理完了後だけ登録し、常に下書きと表示 |
| `audio_emotion` 音声感情推定 | モデル別の分布、対応発話、研究者による確認 | `emotions`、既存感情JSON／CSV、発話レベル値、モデル版・適用範囲 | 自動推定と手修正を区別し、本人の実際の感情とは断定しない。欠測・利用不可を明記 |
| `outline` 議題・アウトライン | 会話の案内、時刻、保存済み見出し | 既存 `outline` JSON／TXT、生成情報が取得できる範囲 | 過去データに発話IDがなければ時刻範囲参照と明記。存在しない根拠IDを補わない |

`segments_all` は全手法で参照する発話データセットとして入力スナップショットに対応付け、除外フラグを保持する。研究用Vaultの発話表示は登録時に選んだ範囲に限定し、解析対象外の発話が集計や見解に混入しないようにする。

`analysis_methods` は手法定義・計算法・出典の基礎データとして保存する。各固定結果の `result.json` に手法別詳細を含め、`analysis_methods.csv` とmanifestで手法版を照合できるようにする。

## 根拠の種類

発話に基づく主張は、原文へ戻るための参照を必須にする。統計集計の主張は、対象集合のスナップショット・対象数・結果表の行キーを根拠にする。集計値の説明のために恣意的な1発話を「全体の根拠」として付けない。

関係は `supports`（支持）、`contradicts`（反証）、`context`（文脈）、`follow_up`（追加確認）、`derived_from`（導出元）から選ぶ。ノートには関係名の見出しとリンクを書く。機械向けの複雑な関係・大量の発話IDはJSONに保存し、YAMLプロパティへ深く入れ子にしない。[Obsidian公式：プロパティ](https://help.obsidian.md/Editing+and+formatting/Properties)

## 新しい分析手法の登録手順

1. [[90-Templates/method-registration|手法登録票]] を作り、英小文字・数字・アンダースコアの `method_id` と版を割り当てる。
2. 研究上の目的、入力単位、必須列、ID、対象・除外、パラメーター、利用条件を記載する。
3. 出力JSON schema、CSV列、必須成果物、図の形式、根拠の規則を定義する。
4. `execution_kind` を `builtin`／`external`／`manual` として、計算を担当するアダプターまたは外部ツールを登録する。
5. 正常、空、1話者、対象外ID、欠測、古い入力、重複実行の架空サンプルを用意する。
6. サーバーでschema・ID・hash・対象版を検証し、登録プレビューでノート・表・リンクを確認する。
7. 条件・根拠・原文へ戻れることを確認して手法を有効化する。式や対象単位が変わったら手法版を上げる。

追加の完了条件（2026-09-20設計）：新設・拡張する手法は、登録票にUI入口・設定、結果と根拠、比較・再利用、状態と操作検証も記入する。計算・保存/APIと対応するUIを一組として公開し、画面がモックだけの段階で「利用可能」にしない。詳細は[[40-Design/core-handler-routing-reorganization-plan]]の「分析手法とUIの対応確認」。共通部品の利用や既存編集画面への往復は認め、手法ごとに専用画面を量産しない。

登録票やJSONは宣言的なデータとして読む。ファイル内の任意Python・JavaScript・シェルコマンドを自動実行する仕組みにはしない。

2026-09-20追加設計（未実装）：[[40-Design/core-handler-routing-reorganization-plan]]の図6では、LLM分析専用オーケストレーターと疑似人格の相談で、この登録票に沿う手法別契約の原案を作る。入出力の型に単位・尺度・欠測・キー・根拠と後続手法の要件を含め、既存の登録・検証経路へ渡す。相談の合意だけでは有効化せず、schema・実装能力の確認と試行を行い、採用した版を固定する。結果の形は表だけに限定せず、主張集合・関係表・系列・ベクトルを必要に応じて追加する。生成案が既存の専門家定義や人の確定コードを直接上書きすることはない。

## 専門家定義の登録

分析手法ごとの専門家定義は `50-Analysis-Methods/10-Experts/<専門家>/` に置く（ADR-115）。書式は [[90-Templates/expert-definition]]、一覧は [[50-Analysis-Methods/10-Experts/00-Index]]、実装は `src/gurumoji/method_experts.py`。

1. `01-Expert.md` のプロパティ（`expert_id`、`definition_version`、`knowledge_verified`、`title`、`role`、`analysis_method_ids`、`registry_method_ids`）と、本文の「実行定義」（YAML）の同じ項目を一致させる。
2. `applicability_checks` と `quality_checks` の `check` には、下表の判定名か `human_review` だけを書く。ノートに書いたコードを実行させない。`human_review` の項目は、アプリが確認済みと表示しない。
3. `basis` には、`literature` に並べた文献ID（`LIT-`／`RES-`）か、実装上の判断を示す `implementation` を書く。書誌のみの文献を、手順や基準の唯一の根拠にしない（[[50-Analysis-Methods/08-Common-Knowledge/02-Source-Classification]]）。
4. AI補助を許可する場合は、`actor: ai_draft` の段階を `ai_assist.steps` に並べ、各段階に文献の根拠を付け、1500文字以内の `brief` を書く。許可しない場合は `steps` を空にして `reason` を書く。
5. 手順・判定・禁止事項を変えたら `definition_version` を上げ、文献を再確認したら `knowledge_verified` を更新する。知識hash（同じフォルダーの7ノート、`common_notes`、`literature` の文献ノート）は自動で計算され、変わると保存済みの専門家モードのAI見解は「更新が必要」になる。
6. `readiness` の `literature_checked`、`procedure_documented`、`integrated`、`sample_verified` は、確認できた場合だけ `true` にする。文献ノートの解決と未解決事項の有無は、アプリが計算して表示する。
7. `tests/test_method_experts.py` で、定義の検証、文献の解決、手法との対応を確認する。

### ローカル限定の知識（ADR-120）

Git管理下の `50-Analysis-Methods` は実行環境間で共有する「ベース」である。実行環境ごとに知識を追加・変更したい場合は、`<data>/local_knowledge/50-Analysis-Methods/…`（`<data>` は `MOJIOKOSI_DATA_DIR`、既定は `runtime/data`）に、上記と同じ相対パスでノートを置く。`runtime/` はGit管理対象外（`.gitignore`）なので、このディレクトリはコミットされず環境ごとに内容を変えられる。

- 新しい専門家フォルダーをそこに置けば、ベースに存在しない専門家として追加される（`source: local`）。
- 既存の専門家フォルダーと同じ相対パスのノート（例：`10-Experts/thematic-analysis/02-Procedure.md`）を置けば、そのノートだけがベースを上書きする（`source: local_override`）。知識hashは上書き後の内容から計算され直す。
- `local_knowledge` が存在しない環境では、すべてベースから解決され、挙動は変わらない。
- 論文原本などの資料そのものはここにもGitにも置かない。研究者が内容を理解したうえで書いた要約ノート（本ノートの形式）だけを置く。

| 判定名 | 読む値 | パラメーター |
| --- | --- | --- |
| `research_question_present` | 研究質問（`allow_objective: false` でなければ研究目的でも可） | `allow_objective` |
| `method_rationale_present` | 手法の選定理由 | — |
| `moderator_guide_present` | インタビューのテーマ・質問項目 | — |
| `min_included_segments`／`max_included_segments` | 対象の発話数 | `min`／`max` |
| `min_speakers`／`min_participants` | 話者数／参加者数 | `min` |
| `preparation_confirmed` | 逐語録の準備状態が `confirmed` | — |
| `analysis_basis_current` | 準備記録と分析の根拠が一致（`analysis_needs_review` でない） | — |
| `speaker_order_confirmed` | 順序の確認済みで、未確認の話者の発話が0 | — |
| `valid_time_ratio_min` | 有効な時刻を持つ発話の割合 | `min`（0〜1） |
| `unknown_speaker_ratio_max` | 不明な話者の発話の割合 | `max`（0〜1） |
| `codebook_min_codes`／`codebook_definitions_complete` | コードブックの件数／定義の有無 | `min` |
| `coded_segments_min` | コードを付けた発話数 | `min` |
| `interaction_links_min` | 有効な発話間リンクの数 | `min` |
| `comparison_axis_present` | 比較軸または比較グループ | — |
| `statistics_engine_ready`／`statistics_min_groups` | SciPyの状態／群の数 | `min` |
| `chi_square_expected_cells` | 期待度数5未満のセルの割合（最悪の表） | `max_low_ratio` |
| `morphology_engine_ready`／`syntax_available` | 形態素解析が簡易解析でない／係り受けが利用できる | — |
| `transformer_result_current`／`transformer_silhouette_min` | Transformerテーマ分析の結果が最新／シルエット係数 | `min` |
| `emotion_coverage_min` | 感情推定のカバー率（%） | `min` |
| `comparison_sessions_min` | 保存する比較の会話数 | `min` |

## 将来手法を保存する場合の追加項目

以下は登録形式を用意する候補であり、現在このプログラムが計算する機能ではない。

| 候補 | 追加して保持するもの |
| --- | --- |
| テーマ分析・SCAT等の質的分析 | 採用した方法の版・工程、概念化前後の記述、理論記述、研究者、反例、原文への対応 |
| 複数会話の比較 | 会話IDと入力版の集合、包含基準、分析単位、比較条件。1会話の結果と混在させない |
| 外部R／Python等の統計結果 | スクリプト識別値、環境、入力hash、結果表、未確認の再現条件。再計算済みと表示しない |

外部結果を元の入力版に結び付けられない場合は `unverified` として保管し、現行の分析結果や確定した根拠として扱わない。

関連：[[storage-policy]]、[[sync-contract]]、[[90-Templates/research-result]]。
