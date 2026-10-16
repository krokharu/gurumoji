---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-11
title: Gurumoji 改善セッション：同日：利用者指定の再試験で実AIの3回採用を確認
summary: 同日：利用者指定の再試験で実AIの3回採用を確認。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 216
- 225
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：利用者指定の再試験で実AIの3回採用を確認

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：利用者指定の再試験で実AIの3回採用を確認

- 実run `run_008cbf3502d7400e94876c47734b1325`、出力`output/minimum-loops-retest/20261005T013659Z-d11dbe3d`。Qwen3-8b/実context32768/GPU全配置/parallel1/reasoning_effort=none。試験用questionに「1回分のJSON、alternatives/unresolved各3件以内、異なる内容、未提供発話は未読」を追加した。製品の既定prompt・停止制御は変更していない。
- **実AIの有効なCore判断3回、critic1回、verification1回、失敗タスク0**。2回目の終了案をmin_iterations=3により保留したイベントを確認し、3回目でCoreがquestion_satisfiedを選びcompletedとなった。実通信5回、報告された入力125,529/output6,540/total132,069 tokens、試験159.47秒。表示・結果再取得にAIを呼ばないことも確認。
- 初回の結果collectorはKeyErrorで失敗した。テストスクリプトが通常起動時のinitialize_libraryを省いたため、完成した固定runのstatus取得でanalysis_publication_attemptsテーブル不足/HTTP503になった。スクリプトだけを修正し、コピーDBのパス一致を確認してrepair_provenance=Falseで通常schema初期化を行う。HTTP失敗を未確認のrunとして扱う診断も追加。原本に初期化処理を実行しない。
- 同じ保存済みrunを正常初期化後に再検証し、status HTTP200、assess_runの全条件成功、固定成果物save_status=saved、6 artifactsのhash/manifest/型付き表検証に成功。再推論や保存の再計算は行わず、元の失敗result.jsonを保持した。最終確認は`output/minimum-loops-retest/verification.json`。通常終了・3回以降続行・上限/障害・旧条件と初期化先の保護の関連15 tests成功、0.664秒。
- 最初のCPU併用試験（013029Z-8efc9fda）はCore1回採用後、実行時間のため通常cancel経路で停止し、その結果を残した。CLIは65536を指定したがLM Studioの実contextは32768で、64kで成功したとは扱わない。
- 固定snapshotは323発話を保持するが、各呼出しの原文/索引は48発話。**これは限定範囲の動作試験であり、全323発話の読了・科学的解釈の妥当性を保証しない**。原本のsource hashは`7dc5067452160de02239ef10a9ee7c2861ccbe49b00c96f197085bea9775d7ef`のまま。実Vault公開・音声処理・今回の実ブラウザー操作は未実施。
- 試験後にGPT-OSS20B/8192枠/parallel4/TTL3600秒へ戻しIDLEを確認。アプリ本体・設定ファイルはこの再試験で変更せず、試験スクリプトと回帰テスト、Software Vaultの検証記録だけを更新。基点はmain/2f2479ca638c569f6978bec47c509646bd92ff67の作業ツリー。
