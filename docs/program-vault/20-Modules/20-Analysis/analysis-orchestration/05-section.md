---
note_type: reference-section
status: current
verified: 2026-10-05
updated: 2026-10-06
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
note_id: module-analysis-orchestration-section-05
title: Core・Handler自律分析と実行状態UI：固定成果物と4先一式の公開
summary: 固定成果物と4先一式の公開。出典ノート「Core・Handler自律分析と実行状態UI」の分割本文。
parent_note_id: module-analysis-orchestration
source_path: 20-Modules/analysis-orchestration.md
source_sha256: 145ca8522ee906fad2e00812f0dcd27f6c2c4f143f52b9c715fc81da9060e96c
source_body_lines:
- 128
- 160
split_on: '2026-10-11'
---

# Core・Handler自律分析と実行状態UI：固定成果物と4先一式の公開

親索引・状態・確認版：[[20-Modules/20-Analysis/analysis-orchestration/00-Index]]。必要な本文だけを取得する。

## 固定成果物と4先一式の公開

正常に分析完了したrunは、台帳全量を一度封印し、既存 `AnalysisStore.save(publish=False)` で固定packageへ保存する。原結果、初期版、批判/採否、ラベル各版は `result.json` の `orchestration` に完全保存し、可読ノートには要約/根拠/未解決批判を投影する。封印後のイベントや遅延結果を再試行時に取り込まない。

Vault公開は新runの既定OFF。選択できる単位は **Input・Orchestrator・Visualization・Researchの4先一式**。内部requested_targetsは既存の3先配列、effective_writersはResearchを含む4先。個別Vault選択ではない。Researchには発話本文も複製する。旧runの公開範囲を後から拡張しない。

追加テーブルは `orchestration_publications`、`orchestration_publication_attempts`。公開先/封印hash/世代/試行主体をguardし、`AnalysisStore.publish(reuse_completed=True)` と既存生成ノートpolicyを使用する。汎用の直接再公開/refreshから専用guardを迂回させない。保存成功、分析完了、公開処理完了を別々に表示する。

一部失敗は同じpackageとscopeで公開だけ再試行し、AI・統計・初期構築を再実行しない。既存契約に合わせ4writer一式を再確認するため、失敗先だけの再試行ではない。編集済み生成ノートの履歴を保存し、削除済み生成ノートを勝手に復元しない。writerがpublishedでも全ノート存在の保証ではない。

入力変更後も固定成果物は保持してstaleを示し、Vaultへの公開は競合として止める。取消/停止/失敗runを自動公開しない。実際の私有Vaultや移入研究Vaultに接続した検証は行っていない。

## 検証

### モデル予算と段階別入力の試験経路

`model_context_version=1`を指定した新規runで現行adapterと`services/model_context.py`を使用する。APIの未指定時は0を維持し、全担当がローカルのUI起動では1とする。旧runはadapter版を照合し、新契約で自動再実行しない。現在はLM Studioだけを予算計測の対象とし、ロード済みhandleのtemplate/tokenizer・実枠・設定hashで確認する。schemaは保守的に加算し、結果数・提示した批判の応答数に応じた出力予約と512tokenの余裕を残す。初期分析も3200token以上を予約する。予測予算は課金usageへ加算しない。

`context_reference_version=1`は実測経路で既定有効。`task_instruction`にDBの論理パスとObsidian参照を置き、Handlerが解決した内容を別の`resource_data`メッセージへ分離する。パスはモデルの任意filesystem権限ではない。必要な原文・結果・専門報告だけを固定snapshot/resultから選び、既存`ExpertCatalog`が共通知識2ノートの指定節と許可済みbriefを読む。知識の適用条件・禁止事項は維持し、全Vault・他専門家・研究者所有ノートは読まない。参照path・ID・版・hash、メッセージ群hash、実提示範囲は既存manifestに保存する。system/user/dataとschemaを合計して実測するため、メッセージ分離だけでトークンを節約したとは扱わない。詳細はADR-127。

統合では未評価の結果だけを順序付きで取得し、その主張・批判・尺度要求が引用した原文を入力版から取り直す。過去の批判の引用を現在batchより優先して取り直さない。未提示の結果や批判を読了扱いにせず、提示ID・評価対象・残数をmanifestに記録する。全件専用のコード統計は、部分範囲を指定できない出力schemaにする。

初期全役割へ全発話の分割タスクを発注し、所有範囲と前後1発話の境界を区別する。予算不足の未送信ページはDBで親を保持して再分割する。Core報告と尺度設計の要件も、本文と適用条件を落とさず別タスクへ分割する。すべての専門家の読了、全要件の担当指示、専門家の尺度下書きが揃ってから統合へ進む。尺度名の衝突は保存し、自動的に確定・上書きしない。

Coreは未評価結果の順序付きbatchだけを読み、残りを次の判断へ保持する。尺度定義も今回の評価対象の結果から取得し、未取得数と完全catalogのhashを残す。DBのtask JSONへ入力manifestとhashを保存し、原結果は同じmanifest hashを参照する。発話・結果・prompt・schema・専門家知識・モデル設定へ追跡できる。

会話解釈へ既存の手法別briefを接続し、`expert_step_ids`では許可済み手順だけを選べる。適用条件・範囲外・禁止結論を保持し、古い定義/hash・AI補助不可は送信前に拒否する。独立検証は他担当の結果・期待結論を含まない。詳細と未実装範囲は[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]と[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index|expert-knowledge-production-plan]]を参照する。

合成試験は`tests/test_model_context.py`と`tests/test_selected_expert_context.py`。実試験は従来CLIの`--model-context --max-calls N --max-tasks N`を使う。`scripts/test_model_context_packet.py`は試験コピーの単発packetを読取専用で検証し、元runを再開しない。これらの合格を研究上の内容品質や全体分析の完了へ読み替えない。

合成会話・一時DB・mock providerによる回帰対象は `tests/test_analysis_orchestration*.py`、`tests/test_orchestration_review.py` とUI回帰。Windowsの保存データ確認は `scripts/test_saved_autonomous_analysis.py` を使い、元DBを読取専用でコピーして既存POST開始・実AI・保存台帳の経路を実行する。Vault公開を禁止し、初期分析だけの成功や空結果では合格させない。具体的な成功/失敗/未実行、モデルの実入力枠、実データ検証の限界は [[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]] に記録する。外部クラウドAIの品質・費用や実Vault公開を確認したという意味ではない。

試験の`--no-think`は対応するQwen3の実capabilityを確認し、既存の推論設定変換からreasoning_effort=noneを実通信へ渡す。応答を代用しない。`loop_execution_verified`は2回以上の有効Core結果・実usage・不正タスクなしと、安全な終状態を確認する。人の確認待ちでも反復動作は確認できるが、`analysis_completed`と厳格な`passed`は成功に変えない。
