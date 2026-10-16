---
note_type: reference-section
status: current
verified: 2026-10-05
updated: 2026-10-06
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
note_id: module-analysis-orchestration-section-04
title: Core・Handler自律分析と実行状態UI：機密性・限界
summary: 機密性・限界。出典ノート「Core・Handler自律分析と実行状態UI」の分割本文。
parent_note_id: module-analysis-orchestration
source_path: 20-Modules/analysis-orchestration.md
source_sha256: 145ca8522ee906fad2e00812f0dcd27f6c2c4f143f52b9c715fc81da9060e96c
source_body_lines:
- 96
- 127
split_on: '2026-10-11'
---

# Core・Handler自律分析と実行状態UI：機密性・限界

親索引・状態・確認版：[[20-Modules/20-Analysis/analysis-orchestration/00-Index]]。必要な本文だけを取得する。

## 機密性・限界

既定はlocal_only。クラウドAIへ原文・分析結果を送る場合、選択providerと明示同意を必要とする。認証情報は既存設定から都度読み、run設定へ保存しない。会話中の命令は実行指示として扱わない。

この版は探索分析。未使用検証データの隔離を保証する確認的統計ワークフローは実装しないため、confirmatory要求は拒否する。統計手法は実装済み能力に限定し、自由なPython実行・ネット検索・追加インストール・自己権限拡大は許可しない。

ラベル案と採用版は自律分析run内で保持し、元の研究者ラベルを勝手に書き換えない。`label_frequency` は全対象または明示した根拠ID範囲で、現在の固定ラベル版から度数・分母・欠測を実際に再計算する。旧版依存結果はstaleとして残す。既存の参加量・時系列adapterは初期全範囲の参照に限定し、部分範囲やラベル依存の再計算へ転用しない。Obsidian用ノートは完全台帳のダウンロードに加え、新runの明示選択で既存安全経路から公開できる。元データ・研究者所有ノートの保護と既存出版経路を維持する。

## 初回の専門エージェントによるラベル・尺度出力

利用者指定（2026-10-05）により、現行adapterは`core-handler-prompts-12-initial-evidence`。実provider resolverは`initial_specialist_analysis_version=1`、`initial_label_definitions_version=1`、`core_progress_version=1`を固定する。初回は全専門家の予備分析、Handlerによる要件集約、Coreの担当指示、専門家による尺度設計、1回目のCore統合の順に進む。Coreは尺度の作成主体ではない。予備分析と担当指示はCore反復回数へ加算しない。

初期snapshot確定後、Handlerは`initial_analysis`で会話解釈・独立検証・批判者、および数量統計の既存3手法（participation/conversation_dynamics/label_frequency）へ正式タスクを登録する。AI担当は同じ提示範囲の原文を独立に読む。批判者の初回対象は研究の問いと分析計画で、まだ存在しない結論ではない。数量統計は既存の確定入力/保存集計と現行ラベルを使い、任意の新しい尺度を作らない。

各担当は`label_requirements`を初回結果としてHandlerへ報告する。要件は一意ID、label/scale、名称、分析用途、必要な理由、読んだ根拠IDを含み、不要なら空配列を明示する。Handlerは各結果の受領をイベントへ保存し、全6タスクの成功/hash/入力版を照合して`initial_analysis_report`へ集約する。同じ要件は出所を保ってまとめ、担当の失敗・報告欠落は`initial_analysis_incomplete`で停止する。未実行を不要や成功へ置換しない。

予備分析の要約だけを成功扱いにしないため、会話解釈・独立検証には空でない要約と根拠付きclaimsを1件以上要求する。数量統計のlabel_frequencyが対象全件のcodes欠測を返した場合は、分類の定義と発話への付与が必要だと要件へ明示する。数量集計は全対象の分母を使い、AIへ提示した発話数とは区別する。定義が作成されたことだけで発話の欠測が埋まったと扱わない。

Coreは`initial_routing`（iteration=0）で集約報告を読み、専門家への問い・理由・採用基準を含む1件の`interpretation/label-design-v1`をintentsとしてHandlerに指示する。Handlerが依存関係を付けて`initial_labels`へ正式発注する。現在、尺度設計を実行できる担当は会話解釈専門エージェントであり、別のオーケストレータサービスや任意のプログラム実行は追加しない。担当指示の原結果とdecisionは保存するが、採用済みCore統合回数から除外する。終了案・尺度の自作・発話ラベル変更を含む不正な担当指示は隔離し、`initial_routing_invalid`で停止する。

尺度設計タスクは原文と問いに加え、集約された各担当の要件とCoreの依頼を受け取る。出力を保存・検証してから1回目の統合へ進み、Coreが予備分析全件と尺度結果の採否・根拠付き主張・限界を評価する。専門家の追加分析案はCoreが既存の各担当へのintentsに変換し、Handlerが発注する。独立検証は引き続き他担当/Coreの結論を受け取らない。保存済みの旧runは従来の段階契約を保持し、現行adapterへ自動移行しない。

`label_definitions`は1〜12件必須。安定ID/版、名前、測定対象、発話単位、型、尺度水準とその理由、値の意味・判定基準、判定規則、欠測条件、推奨集計方法、提示された根拠IDを検証する。名義/順序尺度は異なる値を2件以上。初回の順序尺度はnumber型の数値符号を昇順で出力し、category/booleanは名義尺度へ限定する。生成schemaの型別分岐でlevels.valueも同じ型に固定する。名義/順序尺度に平均を適用せず、欠測は`null_with_reason`としゼロにしない。「欠測」「未読」「missing」「null」「none」「n/a」を通常値へ混ぜた案を拒否する。空配列・形式不正・未提示の発話根拠は原回答を隔離し、Core実行前に`initial_labels_missing`で停止する。Provider障害・取消・予算上限は出力成功として扱わない。

保存した専門家原結果のhash・入力版・task/attempt/作成主体を再確認して、`initial_label_catalog`をCoreと後続解釈/批判へ渡す。独立検証のblind packetには渡さない。初回Coreにも専門家結果の採否・理由・影響を要求する。中断後は保存済み専門家結果を再利用し、同じ作成タスクを再発注しない。

実データ試験で入力枠超過とID誤写を確認したため、AIパケットでは各発話の重複したdataset_version/source_hash/idを省き、根拠ID・発話ID・原文・話者・時刻とルートの入力版を渡す。全量の固定根拠とhashは保存台帳で維持する。尺度設計は原文と問いだけの専用パケットとし既存AIラベルを渡さない。後続のlabelsは既存の変更可能フィールドへ限定し、catalogの重複送信も避ける。

生成schemaは主張/批判の根拠IDを提示済み原文と保存済み主張に、追加タスクの根拠IDを提示索引に限定する。依存task ID・保存result ID・initial ID/節も実在値へ固定し、statisticsの計算とAIの解釈を型別分岐する。主張と尺度の中心根拠は各8件以内にする。schemaコピーはJSON往復で共有コンテナーを分離し、依存taskの制約を根拠IDへ誤適用しない。採用時の既存実在参照/hash検証を省かず、AIが生成した不正なIDを事後に置換しない。指示強化だけで意味上の尺度妥当性を保証したとは扱わない。

定義は`ai_draft`であり研究者が確定したコードブックではない。発話ラベル・既存codebook_version・研究者ノートを書き換えず、実行可能なmanual測定定義へ自動登録しない。原結果、runのcatalogとCore判断の参照IDを既存台帳/固定`result.json`へ保存し、画面の「ラベル・尺度の定義を読む」とJSON/Markdown書き出しから閲覧できる。以前のrunへ定義を捏造して補完しない。旧adapter版のrunの履歴閲覧は維持し、再開には既存の版一致guardが適用される。
