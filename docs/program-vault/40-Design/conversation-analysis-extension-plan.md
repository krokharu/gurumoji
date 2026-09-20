---
note_id: design-conversation-analysis-extension
note_type: implementation-plan
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合
status: planned
feature: analysis
updated: 2026-09-16
tags:
  - gurumoji/analysis
  - gurumoji/design
  - gurumoji/conversation
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合

## 結論と対象範囲

目的は、Transformerを増やすことではなく、既存の発話・話者・時間・手動コード・意味クラスタを組み合わせて、次の問いを根拠発話へ戻れる形で扱うことである。

- どの内容が多いかだけでなく、**質問・提案・回答・留保・反論**のどれとして話されたか。
- ある**明示された対象**（提案・論点・条件）に、誰がどの立場を表明したか。
- 質問→回答、提案→反論／補足のような、観測された**発話間の関係候補**。
- 手動コード、話題、感情、話者、時間を分けたまま、どの組合せに偏りがあるか。

今回の調査対象は、意図・発話行為、スタンス／NLI、ゼロショット／教師あり分類、応答関係、BERTopic系、追加学習分類器の6系統である。これは実装承認ではない。現行の`transformer_topics`は多言語E5埋め込み＋K-meansであり、BERTopic、スタンス分析、応答関係推定、汎用分類器はいずれも実装済みではない。

最優先は **M01（発話行為×既存の語彙・共起・手動コード）をA: 結果の結合・絞り込み・クロス集計としてPoCすること**である。自動推論を別の自動推論の入力にするB、複数特徴を共同学習するCは、Aの人手評価で追加利益を確認できた場合だけ進める。最初の実装単位は、`dialogue_act`の版付きラベル定義・人手確認用データ・低コストの規則ベースライン・既存の固定保存／根拠表示への接続である。

## 調査の境界と根拠

### 読んだ入口と保存先

- `AGENTS.md`、[[00-AI-Entry]]、[[50-Analysis-Methods/00-Index]]、[[40-Design/method-rules]]を入口として読んだ。`00-AI-Entry`の「分析手法、専門家定義、AIプロンプトの制約」は、手法索引→登録規約→対象実装を順に読むよう指定する。
- このノートはプログラム仕様を置くSoftware Vault（`docs/program-vault/40-Design/`）に置く。実会話・実行結果は置かない。将来の実行結果は[[30-Data/analysis-storage-v1]]のAnalysisStore／ResearchVault経路に保存する。
- [[40-Design/method-rules]]の「将来手法を保存する場合の追加項目」は登録規約であり、ここは複数手法の採否、統合、評価、段階を決める計画である。実装時は各採用手法について[[90-Templates/method-registration]]を別途作る。

### 現時点で確認した事実

| 区分 | 確認済みの事実 | この計画への影響 |
| --- | --- | --- |
| 安定ID・版 | `app.py:2293-2310`の`ensure_segment_ids`が発話IDを正規化し、[[30-Data/transcript-preparation-v1]]は本文・話者・順序・確認状態の版と古い根拠の扱いを定義する | 新しい出力は`segment_id`を主キーとし、対象発話をまとめる場合も対応表を必須にする |
| 手動分析 | `app.py:4904-5038`は複数コード、相互作用タグ、`source_segment_id → target_segment_id`の手動リンクを検証する。関係は応答・同意・不一致・補足等で、予測器はない | 既存の手動リンクとコードは正解データ・確認UIの候補であり、自動推定で上書きしない |
| 基本分析 | `research_analysis.py:1354`、`analysis_insights.py:61-170`が形態素、TF/DF、共起、特徴語、KWIC、記述統計を発話単位で作る | M01/M02は新しい語彙器を作らず、ラベルで対象発話を絞った既存集計を優先する |
| 現行Transformer | `transformer_analysis.py:654-692`はE5の`query:`／`passage:`接頭辞、512 token上限、L2正規化、CPU/CUDAを実装する。`analyze_transformer_topics`（930行以降）はK-means、候補silhouette、代表発話、話者・時間・相づち集計を出力する | モデル名・revision・接頭辞・本文・前処理が一致しない埋め込みは共有しない。既存クラスタをBERTopicと表示しない |
| 意味検索 | `semantic_search`（`transformer_analysis.py:1286`）と`GET /analysis/semantic-search`（`app.py:14762-14783`）は保存済みE5ベクトルを使う | 応答先候補の一部として再利用できるが、意味近傍だけで応答先・賛否を確定しない |
| 現行の限定的な応答処理 | `transformer_topics`は短い相づちを別集計し、時系列上の近い別話者発話へ暫定リンクする。UIも「賛成とは断定しない」と表示する（`analysis-content.js:456-810`） | 相づちリンクを応答関係の正解・一般的な賛否の根拠として流用しない。別途人手評価する |
| 保存・更新判定 | `analysis_store.py:44-80, 258-361`は入力fingerprint、分析／原本revision、固定`input.json`・`parameters.json`・`result.json`・CSV、staleトリガーを持つ | Phase 1は新テーブルを先に作らず、この手法別runと成果物を使う。既存発話を編集すれば予測をstaleにする |
| 表示・根拠確認 | `static/app.js:6972-8025`はコード／関係リンクの編集、文脈展開、根拠発話への復帰を持ち、`analysis-content.js`はテーマの代表発話と意味検索を表示する | まず既存の発話詳細、音声確認、CSV／JSON出力、手動分析パネルを再利用する。予測値を確定コードのように表示しない |
| 実行環境 | `config/requirements.txt`は`transformers>=4.48,<5`、`scikit-learn>=1.5,<2`。調査時のvenvはTransformers 4.57.6、PyTorch 2.8.0+cu128、sentence-transformers／BERTopic／SetFitは未導入。実機はCPU 20論理コア、RAM 63.46 GiB、RTX 5070（VRAM 12,227 MiB） | 新規依存・モデル重みは導入しない。GPU常駐、速度、VRAMは実測前に前提化しない |

### 資料から分かること、設計提案、未検証仮説

資料は手法の意味と候補を示すが、日本語の複数話者会話、転記誤り、当プロジェクトのラベル体系における精度を保証しない。以下で「資料」は出典の記述、「提案」は本計画、「仮説」はPoCで検証する事項を分ける。

## 6系統の調査と採否

| 系統 | 資料から確認したこと | 現プロジェクトへの適用判断 | 採否・次の段階 |
| --- | --- | --- | --- |
| 意図・発話行為分類 | ISO 24617-2関連では発話行為と用途固有の意味注釈を併存させる設計が扱われる [S01] | `dialogue_act`（質問、回答、提案、依頼、確認、同意的フィードバック、留保、反論、自己修正、その他／保留）と、既存コードブックの`content_code`を同じ排他的列に混ぜない。1発話に複数機能がある場合は複数ラベルまたは機能単位の分割を人手で決める | **既存機能を拡張**。M01の規則ベースライン→人手確認から開始。単独発話・前後文脈・話者／役割ありの比較を評価する |
| スタンス／NLI | スタンスは対象への態度、NLIは前提→仮説の含意・矛盾・中立であり同一ではない [S02][S03]。外部情報はLLMのスタンス判定を悪化させ得る報告がある [S19] | `stance`は`target_id`と対象原文・版を必須にし、支持／反対／条件付き・混合／表明なし／対象不明／保留を分ける。NLIは同一対象・条件の主張の整合性や言い換えの補助で、賛否や現実の真偽に置換しない | **PoC後に判断**。明示対象の発話だけでAの結合表示を先行する。省略対象の推定は応答関係の結果を必須入力にしない |
| ゼロショット／教師あり分類 | TransformersのゼロショットはNLI型pipelineで候補ラベルと仮説テンプレートを使う [S04]。疎なTF-IDF＋線形分類器も教師ありベースラインになる [S05] | NLI型、LLM型、規則型のスコアは同じ意味ではない。ラベル定義、否定例、保留規則、テンプレートを版管理する。E5固定ベクトルの線形分類器も比較対象にする | **既存機能を拡張／PoC後に判断**。まず規則型とTF-IDF＋ロジスティック回帰を比較し、ゼロショットは日本語会話の評価セット上でのみ候補化する |
| 応答関係推定 | 候補検索とCross-Encoder再順位付けは検索用の二段階構成であり、候補集合のRecallを失うと再順位付けで回復できない [S08]。談話解析は領域適応が課題 [S06][S07] | 辺は`source=応答側`、`target=参照先`で固定する。リンク推定（候補順位）と関係分類（回答、補足、反論、訂正等）は分ける。直前発話、近傍窓、未回答質問、呼びかけ、既存E5候補を比較する | **新規追加／PoC後に判断**。M05/M06を行うための人手リンク評価を先に作る。短い相づちはルールと時刻を併用し、意味類似度だけに依存しない |
| BERTopic系 | BERTopicは埋め込み、次元削減、クラスタリング、c-TF-IDFによる表現を組み合わせる [S09]。Manual Topic Modelingは既存ラベルを渡し、クラスタリングを飛ばしてそのラベルを語で表現する [S11] | 既存のK-meansテーマ探索とは別手法。Manual Topic Modelingは未知話題の発見ではなく、手動コード・発話行為・既存クラスタを特徴語で説明するBに近い補助である。日本語の意味入力と形態素由来の特徴語入力は分ける | **保留／PoC後に判断**。まず既存ラベルの説明強化（M08）を比較し、発話単位・質問＋回答単位・連続意味単位、外れ値率、安定性を検証してから新規トピック発見を判断する |
| ファインチューニング分類器 | Sequence Classificationの追加学習 [S13] とSetFit [S14] は選択肢だが、必要な件数・性能は当データへ移植できない | 人手確認済みラベルだけを正解にする。規則、TF-IDF、固定E5、軽量encoder追加学習、SetFitを同じセッション分割で比較する。未確認AIラベルは疑似ラベルとして別管理し、評価セットに混ぜない | **PoC後に判断**。低コスト方式を上回る再現可能な利益、ラベル定義の安定、未知セッションへの汎化、運用コストを満たすときだけ採用 |

### モデル候補に関する限定的な確認

- `intfloat/multilingual-e5-base`のモデルカードはMIT、768次元、最大512 token、`query:`／`passage:`接頭辞を案内する。既存smallは384次元であるため、名前が似ていてもベクトルを混在できない。カードの検索ベンチマークは日本語グループ会話の発話行為・応答関係精度ではない [S15]。
- `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`のモデルカードはMIT、XNLI/MNLIで学習した多言語NLI・ゼロショット候補とする。ただしモデルカードの多言語性は、日本語の省略・相づち・会話上のスタンスを検証済みにしない [S16]。
- 現在導入済みのTransformers 4.57.6には`zero-shot-classification` pipelineが存在する。しかし候補モデル、ラベルテンプレート、revision、CPU/GPUメモリ、ライセンスの実装時再確認は必須であり、本調査ではダウンロード・推論をしていない [S04]。

## 既存分析の棚卸しと再利用方針

| 実際の機能 | 入力・分析単位→処理 | 出力・保存・UI | 再利用できる部分 | 不足点 |
| --- | --- | --- | --- | --- |
| 文字起こし・話者・編集・準備 | `library_items`の発話。`group_analysis_for_row`（`app.py:5511-`）が`id`、話者、役割、時刻、本文、除外、確認状態を構成 | SQLite、入力版、`prepared_turns`、編集／音声確認UI。更新時は関連runをstale | session／speaker／segment ID、時刻、元本文と編集本文、準備状態 | 機能単位の分割、対象ID、予測と人手確定の汎用記録はない |
| 形態素・語彙・共起・KWIC・特徴語 | 1発話を文書として、形態素、TF/DF、Jaccard共起、話者差、KWICを集計 | `research_analysis`、`analysis_insights`、Excel／CSV／JSON、分析UI | M01のラベル絞り込み、M02のコード×話者表、根拠発話への復帰 | 語の共起は発話間の応答・賛否グラフではない |
| 手動コード・相互作用 | 複数コード、重要引用、単発タグ、手動関係リンク。分析単位はturnのみ | `analysis_annotations_json`、`coded_segments`、`interaction_links`、case matrix、文脈展開UI | ラベル定義、確認・修正、関係の正解候補、M02/M05/M09 | 自動予測のスコア・候補順位・モデル版を保存する契約はない。既存JSONを未設計の予測用に転用しない |
| Transformerテーマ・意味検索 | 文脈付き有意味発話→E5 small→K-means／手動テーマ割当、意味検索 | テーマ、割当、話者分布、時間、例外、相づち、CSV、固定run、テーマUI | E5ロード・CPU/CUDA設定・キャッシュ・発話根拠・時間／話者集計 | BERTopic、対象別スタンス、一般応答関係、分類評価はない |
| 音声感情 | 音声セグメント→AISTモデル。テキストとは別のラベル | 発話別感情、分布、UI、CSV。任意依存 | M03の発話ID結合、元音声へ確認 | 感情を賛否・意図・内心へ置換できない |
| 会話構造・参加量 | 発話数、秒数、遷移、無音・重なり候補、時間区間 | automatic分析、グラフ、CSV | M04/M06の話者・時間分母、候補窓 | 遷移・発話量は応答・影響力・人格を意味しない |
| AI見解／アウトライン／会議議事録 | 根拠発話IDを検証するAI見解、議題、規則ベース会議タスク／決定候補 | 固定run、ResearchVault、根拠表示 | M07の比較対象、発話ID付き構造化入力 | 談話関係を要約に入力する機構、少数意見・帰属の測定はない |
| 固定保存・Vault・出力 | `archive_group_analysis`（`app.py:13952-13982`）→`AnalysisStore.save` | `analysis_runs`、成果物CSV/JSON、ResearchVault、method status、CSV／Excel／JSON | 新手法の入力fingerprint、parameters、モデルrevision、stale、根拠と履歴 | 事前に`analysis_method_registry`、CSV schema、検証、UI対応を追加する必要がある |

## 既存分析との組み合わせマトリクス

各案はA（結合／絞り込み／クロス集計）を先に評価し、B（後段推論の文脈・候補選別）、C（統合特徴・共同学習）は前段を越えた利益がある場合だけ許可する。

| ID | 答えたい問いと既存根拠 | A: 最初に行う結合 | B/Cを検討する条件 | 結合キー・表示・比較評価 | 判定 |
| --- | --- | --- | --- | --- | --- |
| M01 | 「提案／問題提起／質問で、どの語・コードが異なるか」。既存の語彙・共起・特徴語、質問候補、手動コード | `segment_id`で`dialogue_act`を結び、ラベル別TF/DF、特徴語、共起、コード表を再集計 | B: 前後発話で曖昧な質問候補を再判定。Cは不要 | 発話単位・除外規則を共有。既存のみ／規則のみ／規則＋人手確認でMacro F1とラベル別根拠の正しさを比較 | **最優先・拡張** |
| M02 | 「コード体系と自動ラベルはどこで一致／不一致か」。コードブック、case matrix、クロス集計 | コード×予測ラベル、話者／役割×ラベルを表示。予測と確定コードを別列にする | B: 確定コード定義をゼロショット候補へ渡す。Cは教師データが十分な後のみ | `segment_id`、コードブック版、ラベル定義版。発話数と参加者数を別表示。混同行列・人手不一致理由を比較 | **拡張** |
| M03 | 「感情と賛否は一致しないか」。音声感情と対象別スタンス | 同一`segment_id`で感情×stance×targetを閲覧・クロス集計 | B: 感情特徴を入力するのは、テキストのみより対象別stanceが改善し、誤帰属を増やさない場合だけ | 音声ラベルの欠測を別扱い。感情単独／stance単独／結合で対象特定・stance F1・誤集計を比較 | **PoC後に判断** |
| M04 | 「話題・対象ごとの賛否、話者差、時間変化」。既存テーマ、話者、時間bin | `segment_id`でtopic／stance／speaker／timeを結合し、対象を発言した人、発話数、秒数を別集計 | B: 明示的なtopicを対象候補に使う。Cは不要 | topic run IDとtopic IDを固定し、別runの`T01`を同一視しない。対象明示例で既存のみ／新規のみ／結合を比較 | **PoC後に判断** |
| M05 | 「質問に回答候補があるか、提案に反論・補足が続くか」。手動リンク、質問候補、手動タグ | 質問／提案ラベルで手動リンクを絞り、未リンクを確認候補として表示 | B: 時刻・話者・質問候補・E5近傍でTop-K候補を作り、再順位付けする。Cは不採用 | `source_segment_id → target_segment_id`。直前発話ベースライン、候補Recall@K、最終link P/R/F1、関係F1を分ける | **新規PoC** |
| M06 | 「誰のどの発言に、どの種類の応答が付いたか」。話者集計、遷移、手動リンク | 確定リンクのみで話者×関係の記述表を作る | B: 自動リンク候補を人手確認へ送る。Cは不要 | 両端・間の文脈を既存UIで表示。リンク数／中心性を人格、能力、支配性に読まない | **手動で対応済み／自動化はPoC** |
| M07 | 「要約で論点、根拠、反論、留保、修正を追えるか」。AI見解／アウトライン／議事録 | 既存要約の各項目に、確定済みの関係・発話行為・根拠IDを併記する | B: 確定または高品質に確認された構造だけを要約入力に渡す。Cは不採用 | 根拠追跡、話者帰属、少数意見保持、誤った賛否集計を、既存要約対構造付き要約で人手評価 | **保留** |
| M08 | 「既存コード／クラスタはどの語で特徴付くか」。手動コード、現行テーマ、形態素 | 既存の特徴語・話者別語彙で説明を強化する | B: BERTopic Manual Topic Modelingで既存ラベルをc-TF-IDF表現する。未知話題の発見とは分離 | 文書と発話IDの対応を保存。語の説明可能性、外れ値率、前処理・単位変更への安定性を比較 | **保留／BERTopic PoC後** |
| M09 | 「人手修正を将来の分類改善に使えるか」。コード／リンク編集UI、版、CSV | 人手確定ラベルを予測と並べ、低確信・モデル不一致・無作為例を確認キューにする | B: 確定ラベルだけで軽量教師ありを学習。C: encoder追加学習は軽量ベースラインを越えた後 | session単位でTrain/Validation/Testを分離。元予測、確認者、確認時刻、ラベル版、本文版を保存 | **PoC後に判断** |
| M10 | 「文字起こし・整文の差が後段推論をどれだけ変えるか」。原本、編集本文、準備状態、音声 | 同じ発話IDで原本／分析本文のラベル差、否定・条件・相づち・話者帰属の変更を比較 | B/Cは不要 | 原本条件・整文条件・人手正解を分け、下流のstance／relationへの誤り伝播を測る | **拡張（全PoCの品質条件）** |

## 推奨アーキテクチャとデータ契約

### 分析単位と依存関係

```text
保存済み発話（segment_id, session, speaker, role, start/end, 本文版, 除外, 準備状態）
  ├─ A: 発話行為／内容コード／感情／既存topic を発話単位で結合 → 表・既存UI・CSV
  ├─ A: 明示対象の stance を (segment_id, target_id) 単位で結合 → 表・時間／話者比較
  ├─ B: 時間・話者・質問候補・E5近傍で relation の候補集合 → 人手確認 → 確定リンク
  └─ B: 確定リンク／明示対象を必要な場合だけ次の推論・要約候補へ渡す
       └─ C: 複数特徴や追加学習は、独立評価でA/Bを上回る場合だけ
```

- `dialogue_act`、`content_code`、感情、topic、stanceは同じものではない。多面ラベルとして別の結果表に置く。
- `stance`の行キーは`(segment_id, target_id)`である。1発話が複数対象に異なる態度を持てるため、発話ごとに1件へ潰さない。
- `nli`の行キーは`(premise_id, hypothesis_id又は仮説本文hash, direction)`である。前提→仮説の向き、文脈発話ID、三値ラベル、判定保留を保存する。
- `relation`の行キーは`(source_segment_id, target_segment_id, relation_type, candidate_rank)`である。応答先なし、自己補足、複数候補／複数辺を表せる。既存の手動リンクとの方向を一致させる。
- topic用に発話をまとめた文書は`document_id → segment_id[]`の対応を残す。重複窓は集計に二重計上しない。topic IDはrun/model/文書化条件に属し、別run間で同名IDを同一視しない。

### 保存・キャッシュ・UIの方針

1. Phase 1は既存`analysis_runs`と`AnalysisStore`の固定`input.json`、`parameters.json`、`result.json`、CSVを利用する。各手法を`analysis_method_registry.METHODS`へ登録し、結果ごとにモデル名・commit revision・ライブラリ版・入力本文hash・前処理・接頭辞・最大長・seed・ラベル定義／テンプレート版・判定状態を`parameters`へ入れる。
2. 最初から新しい汎用DBテーブルや既存`analysis_annotations_json`の転用を決めない。人手確認を永続的に運用する段階で、予測・確定ラベル・保留理由・確認履歴を安全に保持できる既存契約との差分を設計し、移行と回帰テストを含む別判断にする。
3. E5キャッシュ再利用は、モデル、revision、入力本文、文脈追加、`query:`／`passage:`、512 token制限、正規化、対象発話IDがすべて一致する場合だけにする。分類用に追加学習した埋め込みを既存検索・テーマへ無検証で置換しない。
4. UIは既存の分析パネル、発話フィルター、根拠発話の文脈展開、音声確認、CSV／Excel／JSON出力を使う。`未実行`、`利用不可`、`失敗`、`予測`、`人手確認済み`、`判定保留`、`stale`を区別し、スコアを校正済み確率や確定結果として表示しない。
5. 既存のローカル／外部AI設定を超えて、原文や個人情報を新しい外部検索・APIへ送らない。技術資料のWeb検索と、参加者のスタンス推定に外部事実を注入することは分離する。

## 教師データ・評価・誤り伝播

### 評価セットの作り方

- 実装前に、研究質問・対象・ラベル定義・判断不能・境界例・複数ラベルを記した短い注釈ガイドを版管理する。質問、相づち、婉曲な反対、条件付き意見、複数対象、自己訂正、同時発話、文字起こし誤りを含める。
- Train／Validation／Testは先に`session_id`等のグループで分ける。同じ会話の前後文脈、応答ペア、重複文書が分割をまたがないようにする。GroupKFold等は候補だが、分割可能な会話数を実測してから採用する [S17]。
- 正解は人手確認済みのラベルとリンクだけにする。AIの未確認予測は疑似ラベルとして明示し、独立評価データに混ぜない。可能なら複数人で不一致理由を記録する。

### 比較実験

| 対象 | 必須ベースライン | 主指標 | 失敗を隠さない指標 |
| --- | --- | --- | --- |
| 発話行為／内容分類 | 既存質問正規表現、手動コード、規則、TF-IDF＋線形分類器、必要時NLIゼロショット | Macro F1、クラス別F1、混同行列。多ラベルはMicro F1も | 保留率、誤りの種類、ラベル定義／文脈条件別の差 |
| stance／NLI | 明示対象だけの規則、対象未解決の保留 | 対象特定の正しさ、stance F1、NLIの方向別／三値精度 | 対象不明、条件付き・混合、neutralと低確信の混同、外部情報あり／なしの差 |
| 応答関係 | 直前発話、時間近傍、手動リンク | 候補Recall@K、最終link Precision/Recall/F1、関係分類F1 | 応答先なし、複数応答、相づち、自己補足、候補外正解の割合 |
| BERTopic／既存ラベル説明 | 現行K-meansテーマ、既存の特徴語・手動コード | 代表例の人手解釈可能性、必要時Coherence／Diversityの計算法を明示 | 外れ値率、文書単位・前処理・seed変更への安定性、話者横断文書の誤帰属 |
| 統合／要約 | 既存のみ、新規単体、Aの結合 | 根拠発話の正確さ、意見帰属、少数意見保持、元発話への到達手間 | 誤った賛否集計、上流が人手正解の場合とAI推定の場合の差 |
| 運用 | CPU／GPUの既存実行経路 | 処理時間、RAM/VRAM、追加API費用、再実行時間、キャッシュ再利用率 | モデル未導入／CPUのみ／メモリ不足／中断／staleの挙動 |

効果は同じ評価データで「既存のみ／新規のみ／組合せ」を比較して初めて判断する。閾値、必要ラベル数、速度、VRAM、精度の数値は本計画では仮定しない。採用閾値を置く場合は、研究目的に対する許容誤りとベースライン比較から事前に決め、探索中のTestで調整しない。

## 実装フェーズとチケット案

| Phase | 目的・優先度 | 想定変更対象と再利用 | 入出力・評価・完了条件 | 取りやめ条件 |
| --- | --- | --- | --- | --- |
| 0 | **最優先**。研究質問、対象、注釈ガイド、session分割、既存データ品質を確定 | `transcript_preparation`、手動コード／リンクUI、`prepared_turns`を読む。コード変更なしでも開始可能 | ラベル・保留・境界例・正解作成手順、評価用会話の分割、原本／整文条件を記録。手法ごとの適用条件を満たす | 話者・順序・本文確認が必要水準に達せず、正解作成者も確保できない |
| 1 | **最優先**。最小共通契約と固定保存の設計 | `analysis_store.py`、`analysis_method_registry.py`、`app.py:archive_group_analysis`、[[40-Design/method-rules]] | `utterance_labels`、`stance`、`nli`、`relations`、`documents`のCSV／JSON schema、fingerprint、stale、予測／確認状態、根拠IDの検証を定義。架空データの空・削除先・本文変更を検証 | 既存AnalysisStoreだけで版・確認履歴を安全に保持できないと判明し、保存契約の追加設計が未承認 |
| 2 | **最高の最初の実装単位**。M01の低コスト分類とA結合 | 新しい手法アダプター、既存`research_analysis`、`analysis-content.js`／`app.js`の発話・CSV表示。規則型と既存質問候補を再利用 | `dialogue_act`の規則ベースライン、保留、手動確認、ラベル別語彙／コード表。既存のみ／規則のみ／確認後の評価を完了 | 人手評価で既存質問候補／手動コードより使える根拠表示・分類利益がない |
| 3 | M05、明示対象のstance、NLIの限定PoC | `transformer_analysis.semantic_search`、手動relation、話者・時刻・質問候補、既存テーマ | Top-K候補生成と手動確認を分離。明示対象stanceはrelationなしで評価し、NLIは方向と三値を保存 | 候補Recall@Kが低い、対象特定の誤りで賛否表示が危険、またはNLIが人手判断を上回らない |
| 4 | M08/M04。既存分類を説明するBERTopicと未知話題探索を分けて比較 | 現行E5、形態素、コード、topic結果。BERTopicは新規任意依存として隔離 | Manual Topic Modeling対既存特徴語、次に文書単位別の発見的PoC。発話ID対応、外れ値、安定性、解釈可能性を評価 | 既存K-means／特徴語より説明可能性が上がらない、少量会話で不安定、依存・実行コストが利益を上回る |
| 5 | M09。教師あり／追加学習を比較 | scikit-learn、固定E5、必要時Transformers／SetFit。既存編集・確認UIを再利用 | session分割で線形・固定embedding・追加学習を同条件比較。人手確定ラベルの来歴とモデルrevisionを保存 | 軽量方式を越えない、ラベル定義が不安定、未知セッションに汎化しない、運用負荷が大きい |
| 6 | M06/M07を含む統合表示・要約・回帰 | method overview、根拠表示、CSV／Excel、ResearchVault、ブラウザーテスト | 予測／確定・stale・失敗表示、根拠追跡、少数意見・帰属の回帰評価、保存／再試行／exportを確認 | 確定していない構造を要約の事実として表示するリスクを解消できない |

独立に進められるのは、Phase 0の注釈設計、Phase 1の保存schema設計、Phase 2の規則ベースライン、Phase 4の既存ラベル説明の机上比較である。Phase 3の一般的な応答リンク、Phase 5の学習、Phase 6の要約入力は、それぞれの人手評価を通った結果だけに依存する。

## 採否一覧

| 区分 | 対象 | 根拠 |
| --- | --- | --- |
| 既存機能で対応 | 手動コード、手動相互作用リンク、質問候補、話者・時間集計、E5検索、感情の発話ID結合、固定保存 | 既に発話ID、根拠表示、CSV、stale、編集UIを持つ。ただし自動分類／一般応答推定ではない |
| 既存機能を拡張 | M01、M02、M09の確認表示、M10の原本／整文比較 | 手動分析・形態素・保存・UIを再利用でき、まずAの結合で価値を測れる |
| 新規追加 | 自動発話行為、対象別stance/NLI、一般応答リンク候補・関係分類、予測の版付き結果schema | いずれも現在の`METHODS`、API、CSV、UIには存在しない |
| PoC後に判断 | ゼロショットNLI、stance、Cross-Encoder再順位付け、教師あり／SetFit／追加学習 | 日本語会話・既存ラベル・実機コストでの利益が未測定 |
| 保留 | BERTopicによる未知話題発見、談話構造をAI要約の入力にするB、共同学習C | 既存テーマ／特徴語で足りる可能性があり、上流誤りの伝播を未測定 |
| 不採用（現段階） | 感情＝賛否、NLI＝同意／反対、相づち＝賛成、共起ネットワーク＝応答グラフ、外部検索情報をstance入力へ混入、全過去発話の総当たり、未確認AI予測を正解扱い | 各々がタスク定義、根拠、計算コスト、または評価の境界を壊す |

## 未確認事項

1. 実際に利用する日本語グループ会話の件数、話者・順序・本文の確認率、研究質問、対象の粒度、個人情報・外部送信の許可範囲。
2. 人手注釈者数、注釈ガイドの妥当性、クラス別件数、session単位の十分な分割数、不一致理由。
3. 日本語の発話行為、stance、応答関係に対する候補モデルの性能、否定・婉曲・相づち・省略への頑健性、閾値・校正、CPU/GPU実測。
4. E5-base／mDeBERTa／BERTopic／Sentence Transformers／SetFitの実装時の正確なrevision、ライセンス、依存競合、モデル容量、Windows／Colabでのメモリと中断・解放の挙動。
5. AnalysisStore成果物だけで人手確認履歴を十分に表現できるか。新DB契約が必要なら、[[40-Design/ai-development-rules]]と保存契約を読み、移行・後方互換・テストを別計画にする。

## 出典（2026-09-16確認）

### 事前調査の一次資料・公式資料

- [S01: ISO 24617-2 dialogue acts and application-specific annotations (2024)](https://aclanthology.org/2024.isa-1.15/)／[ISO standard, second edition (2020)](https://aclanthology.org/2020.lrec-1.69/) — 発話行為と用途固有注釈を分ける出発点。日本語会話での本計画ラベルの性能は未確認。
- [S02: Multi-Task Stance Detection with Sentiment and Stance Lexicons (2019)](https://aclanthology.org/D19-1657/) — 感情とstanceを別タスクとして扱う出発点。
- [S03: JGLUE / JNLI](https://github.com/yahoojapan/JGLUE#jnli) — 日本語NLIの形式確認用。会話・応答関係の正解データではない。
- [S04: Transformers ZeroShotClassificationPipeline](https://huggingface.co/docs/transformers/en/main_classes/pipelines#transformers.ZeroShotClassificationPipeline) — NLI型候補ラベル・テンプレートの公式API。実装時の版はrequirementsと照合する。
- [S05: scikit-learn sparse text classification example](https://scikit-learn.org/stable/auto_examples/text/plot_document_classification_20newsgroups.html) — TF-IDF＋線形分類器を比較に含める根拠。
- [S06: Dialogue Discourse Parsing as Generation (2024)](https://aclanthology.org/2024.sigdial-1.1/)／[S07: Domain Integration for Multi-Party Dialogue Discourse Parsing (2021)](https://aclanthology.org/2021.codi-main.11/) — 談話構造と領域適応の調査入口。
- [S08: Sentence Transformers Retrieve & Re-Rank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) — bi-encoder候補検索とCross-Encoder再順位付けを分ける根拠。応答先判定器そのものではない。
- [S09: BERTopic Algorithm](https://maartengr.github.io/BERTopic/algorithm/algorithm.html)、[Embeddings](https://maartengr.github.io/BERTopic/getting_started/embeddings/embeddings.html)、[Vectorizers](https://maartengr.github.io/BERTopic/getting_started/vectorizers/vectorizers.html) — 構成要素の公式資料。
- [S10: Topics per Class](https://maartengr.github.io/BERTopic/getting_started/topicsperclass/topicsperclass.html)／[Topics over Time](https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html) — 共通topicのクラス／時間比較の候補。
- [S11: BERTopic Manual Topic Modeling](https://maartengr.github.io/BERTopic/getting_started/manual/manual.html) — 既存ラベルを渡し、埋め込み・次元削減・クラスタリングを飛ばしてc-TF-IDF表現を作る公式資料。未知話題発見と区別する。
- [S12: BERTopic Topic Distributions](https://maartengr.github.io/BERTopic/getting_started/distribution/distribution.html) — 文書内の複数topic分布の候補。集計単位の二重計上に注意。
- [S13: Transformers Text Classification](https://huggingface.co/docs/transformers/en/tasks/sequence_classification)／[S14: SetFit conceptual guide](https://huggingface.co/docs/setfit/en/conceptual_guides/setfit) — 追加学習候補。必要件数・性能は未計測。
- [S15: multilingual-e5-base model card](https://huggingface.co/intfloat/multilingual-e5-base) — MIT、768次元、接頭辞、512 token上限を確認。検索ベンチマークを会話分析へ一般化しない。
- [S16: mDeBERTa-v3-base-mnli-xnli model card](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) — MIT、XNLI/MNLI由来の多言語NLI候補を確認。日本語会話の直接評価は未確認。
- [S17: scikit-learn Cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html)／[Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) — group分割と未校正スコアを確率扱いしないための公式資料。
- [S18: Leveraging Discourse Structure for Extractive Meeting Summarization (2024)](https://arxiv.org/abs/2405.11055) — 談話構造と会議要約の調査入口。英語研究を本システムの効果保証としない。
- [S19: Is External Information Useful for Stance Detection with LLMs? (2025)](https://aclanthology.org/2025.findings-acl.764/) — 外部情報のstance入力を既定にしない根拠。

### プロジェクト内の関連資料

- [[50-Analysis-Methods/02-Semantic-and-Audio/01-Transformer-Topics]] — 現行E5＋K-meansの契約、限界、テーマ分析との区別。
- [[30-Data/analysis-storage-v1]]、[[30-Data/transcript-preparation-v1]]、[[40-Design/method-rules]] — 保存、版、根拠、登録の現行契約。
- [[20-Modules/module-map]]、[[20-Modules/ui-screens]] — 実装・UIの入口。
