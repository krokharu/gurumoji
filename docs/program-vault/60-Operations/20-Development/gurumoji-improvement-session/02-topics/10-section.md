---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-10
title: Gurumoji 改善セッション：同日：最低3回後にCore判断で継続・終了
summary: 同日：最低3回後にCore判断で継続・終了。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 205
- 215
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：最低3回後にCore判断で継続・終了

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：最低3回後にCore判断で継続・終了

- 利用者の追加指定を[[40-Design/50-Governance/decisions/00-Index|ADR-125]]へ記録。新規API/画面の既定はAIお任せ、通常の自動終了を最低3回の採用済みCore判断まで保留する。3回を超えて続行するかはCoreが選ぶ。呼出し/タスク/時間上限、手動停止、障害・レビュー失敗は優先する。明示した別モード、保存済みrunの条件・履歴、adapter版不一致時の復旧停止は維持する。SQL列変更・実データ移行なし。
- 回数は永続判断台帳から数え、失敗/隔離/未採用を成功へ含めない。contextに最低回数と採用済み回数を渡し、終了保留イベントを記録する。画面の時間/回数上限は既定で空欄、autoの上限1/2はAPIと画面で拒否する。プロンプト版はcore-handler-prompts-4-minimum-iterations。
- 合成検証は関連unittest **129件成功、23.365秒**、DOM操作26件成功、隔離した実ブラウザー操作1件成功（1.556秒）。通常停止を3回まで保留、3回以降の続行（5回で終了）、上限3での正常終了、3回目の不正応答の拒否、旧条件の保持、停止/予算/復旧/公開を確認。ブラウザーの通信は合成応答だけで実Vaultへ書き込まない。DOMのNode22.19.0は宣言engineより古い警告あり、テストは成功。UTF-8のfixture出力を環境変数で指定した。
- 実AIはマーラータンの読取専用SQLite backupでQwen3-8b/32768枠/parallel1/GPU全配置/reasoning_effort=noneを使用。5試験の採用済みCore回数は順に **2, 2, 2, 0, 1**。3回成功は未確認、分析完了も未達。失敗結果を保存し、合成検証の成功と混同しない。
- 初回（20261005T010818Z-2e90555b）は批判者が旧対象版を転記して隔離。次（011044Z-804798dd）は3回目の出力がtoken上限で途中終了。24/323発話へ減らした次（011444Z-9edddeda）はno_issuesと非空issuesの矛盾で隔離。次（011745Z-ceb2b177）はCoreが存在しない批判IDへの応答を生成して隔離。批判者の現在対象ID/版とCoreの実在issue/proposal IDを生成用schemaでも固定し、状態/指摘一覧の整合性をプロンプトで明確化した。採用前検証を弱めず、原応答を補正して成功にしない。
- 最終（012137Z-3211def1、run_6309cb32393047418bc01f66681ff506）はCore1回を採用したが、alternatives/unresolved各24件の重複を含む20,123文字の応答で、後続criticがHTTP400。依然として局所モデルの出力量/履歴context増大の制約が残る。次の対象は全量原結果を保持したうえでの重複・要約投影とcontext/出力予算。最低回数の制御を品質保証や全323発話の読了へ読み替えない。
- 元DBのsource hashは全試験で`7dc5067452160de02239ef10a9ee7c2861ccbe49b00c96f197085bea9775d7ef`のまま。コピー以外のruntime台帳・研究Vaultへ書き込まず、音声処理・実Vault公開・移行は未実施。終了後はGPT-OSS20B/8192枠/parallel4/TTL3600秒へ戻し、IDLEを確認。設定ファイルは変更しない。
- 基点main/2f2479ca638c569f6978bec47c509646bd92ff67の未コミット作業ツリー。各resultは`output/minimum-loops-real/<上記ID>/result.json`、コマンド・コードhash・各台帳の採用回数は`output/minimum-loops-test/verification.json`に保持。Python compile、JS構文、git diff --check成功。
