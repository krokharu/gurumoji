---
note_type: reference-section
status: in_progress
updated: 2026-10-06
feature: analysis-orchestration
tags:
- gurumoji/program
- gurumoji/plan
- gurumoji/ai
- gurumoji/storage
note_id: design-model-context-and-work-memory-section-07
title: モデル別コンテキスト管理と作業記録の保存計画：2026-10-06 Coreへの依存を減らす修正
summary: 2026-10-06 Coreへの依存を減らす修正。出典ノート「モデル別コンテキスト管理と作業記録の保存計画」の分割本文。
parent_note_id: design-model-context-and-work-memory
source_path: 40-Design/model-context-and-work-memory-plan.md
source_sha256: 5deb802e628cb0041fcc9fb6b42ddf5ac43615a40641f4aa9d09e449c34d9323
source_body_lines:
- 175
- 185
split_on: '2026-10-11'
---

# モデル別コンテキスト管理と作業記録の保存計画：2026-10-06 Coreへの依存を減らす修正

親索引・状態・確認版：[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index]]。必要な本文だけを取得する。

## 2026-10-06 Coreへの依存を減らす修正

利用者の「Coreに頼りすぎではないか」「これを修正して」に基づき、個別結果の採否・批判応答・追加分析を専門オーケストレータへ移した。最終候補は`core-handler-prompts-23-specialist-orchestration`、新規resolverの既定は`specialist_orchestration_version=1`。`model_context_version`の既定0は維持し、実モデル試験では1を指定する。Coreの初回担当指示を保ち、全有効結果の分野別査定が終わってから短い`domain_reports`を統合する。専門側の査定ではCoreの見解・版・統合回数を変えない。ADR-126とモジュール契約に責務・互換性を記録した。

尺度は専門家の下書き出力後に独立した批判レビューを入れる。批判への応答は専門側が保存し、未解決状態を保持する。具体的な追加分析をHandlerが直接発注し、同じ入力版の全件統計は既存結果を参照する。元の問いと同一または文字列が近い追加案は理由と共に保留し、その件数をCoreへ伝える。文字列の類似度で任意の意味的な重複を完全に判定したとは扱わない。

各呼出しは指示と対象データとschemaを同一のAPIリクエストへ送る。system/userのメッセージは分けるが、送信済み指示を参照して送信自体を省くアプリ側cacheは未実装。モデルが自分でVaultやskillを取得するtool経路も未実装。Handlerが選んだ知識と原文を渡す現行契約である。初回の各AIは全323発話をページ分割し、後続の新規分析は対象の原文、保存結果の説明は明示された1結果、終了批判は統合案と引用原文を読む。完了済みの全初期報告や過去結果を後続分析へまとめて送らない。

v22の8B/16K試験は全初期担当323発話、尺度下書き、独立尺度レビュー、専門側10件の査定を保存したが、追加分析5件を入力枠の超過で送信前に止め、専門側11件目が1600tokenの出力上限で途中終了した。全体は失敗。v23は入力の責務を絞り、専門報告の長さをschemaで制約し、専門側の出力予約を最低3200tokenへ増やした。追加分析の失敗を無視してCoreへ進む経路も止める。現在の関連Python検証196件、DOM28件、合成データの実ブラウザー3件が成功。実モデルの最終結果は運用ノートに追記する。分析の科学的妥当性と、小型モデルの役割別品質認定はこの形式検証から独立して評価する。

8B/8Kの全体試験は批判者の出力上限で停止した。出力枠を3200へ増やすと元ページは送信前に予算超過と判定し、所有範囲を小さくした子ページの単発試験は契約検証に成功した。これは全323発話の分析完了ではない。原本DB・研究者Vaultへ書き込まず、試験DBのコピーだけを使用した。commit/push・Drive更新・実Vault公開は未実行。
