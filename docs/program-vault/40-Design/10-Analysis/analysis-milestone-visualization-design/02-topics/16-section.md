---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-16
title: 分析マイルストーン・可視化プログラム・UI統合設計：18.2 M0とM4の二段階確定
summary: 18.2 M0とM4の二段階確定。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 678
- 708
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：18.2 M0とM4の二段階確定

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

### 18.2 M0とM4の二段階確定

| 確定物 | 固定する内容 | 固定後にできること |
| --- | --- | --- |
| M0：PlanEnvelope | snapshot、目的、M1〜M3の定義、M0〜M7の段階、依存、手法候補、後段binding slot、対象列候補、出力契約、適用外条件、代替候補、予算、送信方針、研究区分 | 値未確定のslotを許容範囲内で埋める。既存値は変更しない |
| M4：ExecutionBinding | PlanEnvelope参照、slot→採用手法/定義版/列/観測単位、試行根拠、研究区分の検証記録 | M5〜M7の実行入力を解決し、確定した組合せを使う |

M4以前に実行するstepはslotに依存してはならない。M5以降のslotには選択可能な手法と入力列契約、出力schemaをM0で記録する。未来の生成列は実データの列名ではなく、上流の出力契約・出力キーで予約する。M4はその実在・型を確認して結び付ける。slotが不要な計画でもM4の整合検査と空のBinding確定は行う。

M4で許容範囲にない手法・尺度・出力・予算が必要になった場合、元のEnvelopeを編集せず、新Envelopeと新pipelineを作る。親pipeline/親計画版を残す。新pipelineはM0から順に検証し、同一の入力・定義・手法・親hashを満たす完了成果だけを再利用して段階を確定する。影響しない分析の再計算は不要だが、段階ゲートの検証は省略しない。

「定義を修正して継続」のUIは、許容slotの未確定値を埋める操作なのか、新pipelineを作る操作なのかを差分付きで示す。研究上の目的や確認的仮説を事後変更して、旧計画の検証結果に見せない。

### 18.3 探索・検証と評価尺度の信頼性

各計画に`ResearchProtocol`を含め、目的、`exploratory / confirmatory`、仮説・分析対象の事前定義、データ閲覧履歴、推論の範囲、検定群と多重比較方針、評価データの参照を固定する。効果量・区間推定・対象数・欠測・前提を結果に保持する。有意なものだけ残さず、実施した分析、除外、変更、失敗も履歴へ残す。透明な報告とp値だけによらない解釈は [ASAの声明](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf) を根拠に採用する。

M1〜M4で同じデータを閲覧して作った尺度・仮説の分析は、原則として探索的と表示する。検証的とする場合は、分析選択前に固定された仮説と規則を使うか、選択に未使用の独立データを用いる条件を記録し、コアが根拠を確認する。M0で名前だけconfirmatoryにしても有効化しない。条件が崩れた場合は検証的出力を停止し、探索への変更は明示的な新計画とする。

LLMのラベル・JEV8軸・尺度については、開発用と最終評価用のデータを分け、同じ話者・会話の情報が評価側へ流れるかを確認する。分割単位とIDを保存し、LLMのプロンプトや例示に最終評価データを使わない。これは学習・選択に使ったデータだけで性能を評価する問題への対策である。[scikit-learnの評価データ分離とグループ分割の説明](https://scikit-learn.org/stable/modules/cross_validation.html)

JEV8軸の運用条件は次とする。

1. 各軸の意味、0〜4の採点例、対象外と判定不能、必要文脈を版付きで固定する。
2. 複数の人手評定を独立に収集し、人同士の一致と、人とモデルの一致を分けて確認する。不一致の扱い・裁定記録も残す。
3. 軸別の一致率、混同行列、判定可能範囲、誤り例を確認する。順序評定では重み付きκを候補とし、尺度・対象数・分布に適合するかを確認する。[重み付きκの公式仕様](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html)
4. 合格基準は指標・評価対象・許容誤差・必要な評価範囲を含めて最終評価前に固定する。根拠のない共通閾値は置かない。基準・評価データが未確定なら`unvalidated`と表示し、研究上の成功/失敗を自動確定しない。
5. model/prompt/rubric/分類規則が変われば評価状態を`revalidation_required`へ移す。過去版の評価を新モデルへ流用しない。人手との一致は尺度の内容妥当性そのものの証明ではない。

多重比較の方針は検定群ID、対象仮説、補正手法と設定を計画へ記録する。追加探索は元の検定群へ黙って継ぎ足さず、新しい分析として履歴・出力に区別する。記述集計のみの場合は検定群を不要と明示できる。
