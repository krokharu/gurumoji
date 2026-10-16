---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-15
title: Gurumoji 改善セッション：同日：反復の進展検知と専門家結果の採否を実装
summary: 同日：反復の進展検知と専門家結果の採否を実装。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 260
- 274
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：反復の進展検知と専門家結果の採否を実装

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：反復の進展検知と専門家結果の採否を実装

- 利用者の修正依頼を受け、`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`を基点としたローカル未コミット変更。既存Handler/adapterへ進展比較と`result_assessments`を追加し、新しい実provider契約を`core-handler-prompts-5-progress`/`core_progress_version=1`へ更新した。API側でprogress=0を指定してもresolverが1へ固定する。SQL列・旧run・封印済み成果物は変更しない。
- 同じ主張・根拠・代替説明・未解決・作業案、過去の状態への循環、要約/ID/順序だけの変更は採用判断へ加算せず`no_progress`で停止する。別IDで生成された同じ役割/範囲/版/hashの専門家結果も新しい根拠にしない。新しい専門家結果は実在IDへの採否・理由・影響を必須にし、無視した応答を隔離して`unreviewed_results`で停止。未評価の21件以上の結果を20件ずつ提示し、古い未評価結果を落とさない。原応答・重複元decision・停止イベントは保存する。
- 画面と実試験スクリプトの判定は採用判断数を使用し、実通信回数と区別する。重複停止で固定成果物のfinalize/公開が呼ばれないこと、読取で再推論されないこと、デスクトップ/スマホ幅で停止理由・採用数・停止後の操作を確認した。設計判断はADR-125追記、現行契約は[[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]。
- 検証: 関連9モジュールのunittest 142件成功（27.945秒）。追加した実app組立ての重複停止/公開抑止1件も成功（1.068秒）。DOM 27件成功、隔離した実ブラウザー1件成功（1440/390px、1.197秒）。Python compile、JS構文、git diff --check成功。初回の化粧変更テストはview更新による不要レビューの再生成でcall_budget_limitとなり失敗し、view版の比較も正規化して再検証した。
- すべて合成入力/一時DB・Vault/合成APIで検証。実AI再分析、全体suite、実Vault公開、Git commit/push、Driveの修正版ZIP更新は未実行。利用者の原本DB/Vault・既存分析記録には書き込まない。新しい採否理由の内容妥当性と、意味が等しい任意の言い換えの検出は未保証。最終コードhashとコマンド・成功/未実行範囲は`output/orchestration-progress-fix/verification.json`へ記録する。

### 同日：初回のラベル・尺度作成を専門エージェントへ必須発注

- 利用者の「初回に必ずラベル/尺度を出力」「Coreではなく専門エージェントが作成」の指定を反映。基点は同じ`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、ローカル未コミット。現行adapterを`core-handler-prompts-6-initial-labels`へ変更し、実provider resolverが`initial_label_definitions_version=1`を固定する。初期保存後、会話解釈専門エージェントの専用`label-design-v1`タスクを最初のCore実行前に発注する。
- 1〜12件の尺度候補について名称/安定ID/版、測定対象、型と尺度水準、その理由、値の意味/判定基準、判定規則、欠測条件、推奨集計、提示された発話根拠を検証。空/不正な定義なら原応答を隔離し`initial_labels_missing`で停止してCoreを実行しない。名義/順序尺度の平均指定、値の重複、数値順序の逆転、未提示根拠も拒否。保存hashと作成主体をCore実行前に再確認し、中断後は保存済み結果を再利用する。
- 定義はAI下書きとして台帳と固定JSONに保存し、Coreは結果の採否/統合を担当。画面に専用の読取ボタンを追加し、Markdown書き出しにも定義節を追加した。発話の既存ラベル/コードブック版/研究者本文は変更せず、候補尺度を実行可能な手動測定へ自動登録しない。独立検証のblind packetにも渡さない。契約と判断を[[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、ADR-125追記へ記録。
- 検証: 関連9モジュール150 tests成功（29.795秒）。最後の作成主体/所有権guard追加後、初回尺度と実app保存の11 testsも成功（5.466秒）。DOM 28件成功（18.206秒）、実ブラウザーで尺度閲覧1件成功（1440/390px、1.347秒）、Python compile/JS構文/git diff --check成功。すべて合成データ・一時DB/Vault/合成API。実AI再分析、全体suite、実Vault公開、Git commit/push、Driveの修正版ZIP更新は未実行。利用者の原本DB/Vault・既存の分析結果へ書込みなし。出力内容の研究上の妥当性は別途研究者が確認する。検証記録は同じ`output/orchestration-progress-fix/verification.json`の`initial_label_specialist_revision`に保持する。
