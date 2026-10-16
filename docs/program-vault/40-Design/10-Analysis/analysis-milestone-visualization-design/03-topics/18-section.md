---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-18
title: 分析マイルストーン・可視化プログラム・UI統合設計：18.6 計算可否と結論の制約を分ける
summary: 18.6 計算可否と結論の制約を分ける。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 745
- 773
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：18.6 計算可否と結論の制約を分ける

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

### 18.6 計算可否と結論の制約を分ける

| 判定次元 | hardの例 | warningの例 | unknown時の扱い |
| --- | --- | --- | --- |
| computability | 必須列不存在、値域違反、有効入力なし | 任意列の欠損 | 必須条件なら対象task停止 |
| inference_validity | 指定推測手法の成立条件・独立単位・検証的計画条件を満たさない | 許容済みの推測上の制約 | 当該推測を止める。記述統計は別の許可taskとして継続可 |
| precision | 計画で必須とした精度基準を満たさない | 精度不明・区間が広いなど、記述結果の提示を妨げない制約 | warningならunknownを保持して実行。必須目標なら停止 |
| qualitative_coverage | 指定論点に根拠がなく、要求された解釈を生成できない | 視点や文脈の限定、未確認の反例 | 許容範囲だけを分析し、不足範囲を表示。網羅性や飽和を自動宣言しない |

severityは結果を見て変更せず、MethodCardと研究計画で固定する。Assessmentには`execution = allowed / blocked`と`inference_scope = none / descriptive / exploratory / confirmatory`を別に持たせる。hardにfail/unknownがあればexecutionはblocked。warningだけならeligible_with_warningsで実行できるが、警告をpassへ変更しない。

例えば記述統計の計算条件が満たされ、精度の評価が未設定なら「記述統計は実行可能、精度は未評価」と返す。検定に必要な条件が未確認なら「当該検定は停止」と返す。停止した検定を、実施済みの記述統計で置換して成功扱いにはしない。

### 18.7 導入範囲と修正の受入条件

初回の実装対象は、既存の記述集計を核にした一本の経路と、同段階で並列に動くもう一つの独立した既存処理とする。必要なM0〜M7を計画に残し、選択外の分析はM0で明示する。既存の確定アウトライン等を入力として再利用できる場合はID/hashを検証し、ない場合は未実装機能を成功扱いせず開始前に不足を返す。LLM7役割・47成果物の全実装を初回の完了条件にしない。

最初に契約・検査・指示・部分結果・保存まで成立させ、次にM7出力/公開、最後に追加手法とUIを増やす。第10節のP1〜P7は全体ロードマップであり、P1は初回対象の契約を実装可能に確定する段階、残りのカタログは設計上の予約とする。

- R01：Schemaで未定義状態、必須stepの適用外許可、失敗報告のエラー欠落、hard不合格なのにallowed、公開未完了なのにpipeline completedを拒否する。
- R02：M0のEnvelope不変、M4での全slot解決、範囲外変更の新pipeline化を確認。旧成果再利用でも全ゲートを順に検証する。
- R03：探索データの事後仮説を検証的と表示しない。仮説・検定群・多重比較・閲覧履歴を出力にも含める。
- R04：JEV8軸の人手評定・採点規則・評価データ・事前基準を版付きで固定。モデル変更で再評価状態となる。
- R05：遅い計算中に独立taskと通常の読取が進み、書込ロックに計算・LLM待機を含めない。取消・並行編集・重複確定も確認する。
- R06：result_run completedかつ公開失敗でも結果を保持し、pipelineは未完了。公開のみの再試行でM7まで回復する。
- R07：必須検査unknownは停止、精度warning unknownは記述処理を許可。両者が同じ「分析不可」表示にならない。

初回導入範囲についてR01、R02、R05、R06、R07を専用試験で確認した。R03は探索／検証区分と検証的計画の事前固定まで、R04は未選択機能として能力一覧で利用不可に固定した。未選択の推測統計、JEV評価、外部provider接続を検証済みとは扱わない。
