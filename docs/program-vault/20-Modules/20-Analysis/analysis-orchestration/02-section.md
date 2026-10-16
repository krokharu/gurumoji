---
note_type: reference-section
status: current
verified: 2026-10-05
updated: 2026-10-06
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
note_id: module-analysis-orchestration-section-02
title: Core・Handler自律分析と実行状態UI：停止設定
summary: 停止設定。出典ノート「Core・Handler自律分析と実行状態UI」の分割本文。
parent_note_id: module-analysis-orchestration
source_path: 20-Modules/analysis-orchestration.md
source_sha256: 145ca8522ee906fad2e00812f0dcd27f6c2c4f143f52b9c715fc81da9060e96c
source_body_lines:
- 50
- 69
split_on: '2026-10-11'
---

# Core・Handler自律分析と実行状態UI：停止設定

親索引・状態・確認版：[[20-Modules/20-Analysis/analysis-orchestration/00-Index]]。必要な本文だけを取得する。

## 停止設定

2026-10-06の現行版は`core-handler-prompts-25-referenced-context`。実provider resolverは新規runの`specialist_orchestration_version=1`を既定にする。通常のAIお任せは`min_iterations=0`で固定回数を強制せず、専門側の分割評価をCoreの反復回数に含めない。Core統合前に全ての有効な未評価結果を分野別に査定し、Coreへは原結果ID・hashを保持した短い`domain_reports`を渡す。Coreの個別採否・批判応答・ラベル採否は拒否する。下記の最低3回・Core個別査定は明示的な旧経路`specialist_orchestration_version=0`の契約で、旧runの条件と履歴は変更しない。任意の上限1巡も受け付けるが、終了前レビューを完了できず上限停止する可能性を保つ。

2026-10-05の利用者指定により、新規run/APIと画面の既定はAIお任せ。`config.min_iterations=3`を固定し、採用済みのCore判断が最低3回になるまで通常の自動終了を保留する。3回目以降はCoreが続行または終了を判断し、終了前レビューと批判応答の契約を維持する。プロンプト版は`core-handler-prompts-4-minimum-iterations`。最低回数は「十分な分析品質」の保証ではない。

回数は永続化済み`orchestration_decisions`から数え、登録・通信試行・隔離結果を含めない。Core contextのbudgetへmin_iterations/completed_core_iterationsを渡し、原文の根拠対応・代替説明・未読範囲・批判応答を再検討させる。終了を保留したイベントと元の終了理由も保存する。同じ版のレビューを不要に繰り返さない。版が更新されたレビューは今回の`review_target`を使い、古い版を転記した応答は引き続き隔離する。

AIお任せの時間/回数上限は既定で空欄。任意の回数上限は3以上を要求する。手動停止、時間/呼出し/タスク上限、障害・不正応答・レビュー失敗は最低回数より優先するため、これらの停止時に3回を達成したと扱わない。明示的な時間/回数/重要度モードには最低回数を追加しない。既存runの条件・履歴は書き換えず、min_iterationsがない保存条件は最低回数なしとして扱う。既存のadapter版不一致による復旧停止も維持する。

同日の内容点検で、旧版の実AI成功runはCore3回の回答が完全一致していた。新しい実行契約`core-handler-prompts-5-progress`は`core_progress_version=1`を固定し、同じ回答の再送を採用済み判断へ加算しない。主張本文/区分/根拠集合、代替説明、未解決点、具体的な作業案を既存判断と比較し、同じ状態への循環も検出する。要約だけの変更、claim_id、配列順、重複要素、NFKC/空白/文末句読点の違いは進展にしない。数値の符号・小数点・語の境界は保持する。意味が等しい任意の言い換えをすべて検出する意味判定器ではない。

Coreへ`iteration_review`で未評価の専門家結果IDを最大20件渡し、`result_assessments`に各結果の採否・理由・結論への影響を要求する。未提示の未評価結果を直近20件で落とさず、必要なら次のCoreで評価する。独立検証は引き続きCoreの期待結論を見ない。新しい結果への採否、初回の批判応答/ラベル判断は、結論を変えない再検討の根拠にもなる。ただし同じ役割・入力/ラベル版・対象範囲・原結果hashの再生成は新IDでも新しい根拠にしない。存在しない結果、Core自身の結果、既評価結果、同一IDの重複、空の採否理由/影響は採用しない。

新しい検討の根拠がなく既存判断と同じなら`no_progress`で停止し、最低3回未満でも完了・自動公開にしない。未評価の専門家結果を無視した応答は隔離し、`unreviewed_results`で停止する。原応答とhash、重複元decision ID、停止イベントを保持する。APIの`completed_core_iterations`と画面は採用済み判断数を示し、実呼出し回数と区別する。旧runの条件・完了状態・封印済み成果物は変更せず、旧adapter版の実行再開は従来通り拒否する。

時間、Core巡回数、重要度、AIお任せの4モード。AIお任せでは時間・巡回数を無上限にできるが、呼出し数・タスク数等の運用上限と手動停止は残る。重要度の高/中/低は未校正の暫定基準であり、確率・LLM自信・p値ではない。実費用を確実に取得できないため金額上限は受理せず、呼出し数・タスク数の上限で制御する。

ブラウザーを閉じても取消しにはしない。再表示は台帳を読み、実行を再発注しない。プロセス中断や応答不明は、完了済み結果を残して復旧判断を待つ。時間上限到達後の外部処理の物理的停止はproviderにも依存する。
