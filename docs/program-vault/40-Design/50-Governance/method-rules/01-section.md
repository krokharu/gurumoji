---
note_type: reference-section
status: proposed
updated: 2026-09-25
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/rules
note_id: design-analysis-method-rules-section-01
title: 分析手法ごとのObsidian登録規約：分析手法ごとのObsidian登録規約
summary: 分析手法ごとのObsidian登録規約。出典ノート「分析手法ごとのObsidian登録規約」の分割本文。
parent_note_id: design-analysis-method-rules
source_path: 40-Design/method-rules.md
source_sha256: b12c64c4bba7906a0e26cb253b7c8e6d2b1eca2ff8b8342118d27ab8c2cdc9a4
source_body_lines:
- 1
- 46
split_on: '2026-10-11'
---

# 分析手法ごとのObsidian登録規約：分析手法ごとのObsidian登録規約

親索引・状態・確認版：[[40-Design/50-Governance/method-rules/00-Index]]。必要な本文だけを取得する。


# 分析手法ごとのObsidian登録規約

2026-09-13更新：組み込み手法の固定保存・AI仕上げの変更記録・Vault生成は実装済みです。現行API・テーブル・登録契約は [[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]] を参照してください。この文書は差分取り込み・外部手法等の後続計画も含みます。

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
