---
note_type: reference-section
status: planned
feature: analysis
updated: 2026-09-16
tags:
- gurumoji/analysis
- gurumoji/design
- gurumoji/conversation
note_id: design-conversation-analysis-extension-section-01
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合：会話分析の拡張計画：既存分析とTransformer系推論の統合
summary: 会話分析の拡張計画：既存分析とTransformer系推論の統合。出典ノート「会話分析の拡張計画：既存分析とTransformer系推論の統合」の分割本文。
parent_note_id: design-conversation-analysis-extension
source_path: 40-Design/conversation-analysis-extension-plan.md
source_sha256: 53dc673b9392c2b03a1b6fd2a103f326b15690c0702376bab2e403dfda7f9bfb
source_body_lines:
- 1
- 42
split_on: '2026-10-11'
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合：会話分析の拡張計画：既存分析とTransformer系推論の統合

親索引・状態・確認版：[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index]]。必要な本文だけを取得する。


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

- `AGENTS.md`、[[00-AI-Entry]]、[[50-Analysis-Methods/00-Index]]、[[40-Design/50-Governance/method-rules/00-Index|method-rules]]を入口として読んだ。`00-AI-Entry`の「分析手法、専門家定義、AIプロンプトの制約」は、手法索引→登録規約→対象実装を順に読むよう指定する。
- このノートはプログラム仕様を置くSoftware Vault（`docs/program-vault/40-Design/`）に置く。実会話・実行結果は置かない。将来の実行結果は[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]のAnalysisStore／ResearchVault経路に保存する。
- [[40-Design/50-Governance/method-rules/00-Index|method-rules]]の「将来手法を保存する場合の追加項目」は登録規約であり、ここは複数手法の採否、統合、評価、段階を決める計画である。実装時は各採用手法について[[90-Templates/10-Analysis/method-registration|method-registration]]を別途作る。

### 現時点で確認した事実

| 区分 | 確認済みの事実 | この計画への影響 |
| --- | --- | --- |
| 安定ID・版 | `app.py:2293-2310`の`ensure_segment_ids`が発話IDを正規化し、[[30-Data/30-Transcript/transcript-preparation-v1\|transcript-preparation-v1]]は本文・話者・順序・確認状態の版と古い根拠の扱いを定義する | 新しい出力は`segment_id`を主キーとし、対象発話をまとめる場合も対応表を必須にする |
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
