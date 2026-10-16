---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-07
title: Gurumoji 改善セッション：作業の進め方
summary: 作業の進め方。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 155
- 172
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：作業の進め方

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 作業の進め方

1. 再現と影響を示し、既存責務を使う小さい修正を選ぶ
2. 主作業treeの実装担当を1つに限定する。独立したテスト整備は別worktree/task branchで行い、調整担当がレビューして明示的に統合する
3. UI/UXと分析担当が独立に検証し、問題があれば同じ修正を閉じるまで戻す
4. 次の高価値課題へ進む。時間消化だけの反復、未検証の成功報告はしない
5. 期限で変更を凍結し、最終HEADに対する試験、未実施範囲、復旧可能な成果物を受け渡す

部門への再利用可能な依頼は[依頼テンプレート](../../gurumoji-department-briefs.md)を使う。既存の詳細契約は複製せず、[設計入口](../../../../../../DESIGN.md)、[運用引継ぎ](../../dot-cloud-development-handoff/00-Index.md)、[受入方法](../../../../50-Tests/30-Interface/ui-design-acceptance.md)へ戻る。

## 2026-10-05 Windowsでのマーラータン保存データ確認

- 利用者の依頼で、`main` / `2f2479ca638c569f6978bec47c509646bd92ff67` の既存分析を実行。対象はローカルDB内の唯一のインタビュー `bb5555800e4248d7a401fc97c85c6882`、入力版1、本文revision 0、分析revision 0。過去のResearchVaultのI001ノートは別conversation IDなので、現DBのIDを根拠とした。
- `.venv/Scripts/python.exe output/malatang-smoke/run.py` は終了コード0。323発話・観測5話者、323/323発話に有効時刻。参加量・会話動態の既存method adapter、GiNZA 5.2.0の形態素／係り受け（7,226 token）、SciPyの統計処理、JSONの非有限値検査、48種のCSV生成／再読込を確認。ゼロ行の表は生成のみの確認で、Transformerや手動コードを実行した証拠ではない。
- 準備状態はdraft、内容確認済み0/323、相互作用分析の準備済み0/323。5話者は観測数であり、確認済み参加者数ではない。研究者の確定解釈や音声との一致を検証したという意味ではない。
- SQLiteを`mode=ro`と`query_only`で読み取り、実DB・研究Vaultへの書き込みなし。処理前後の本文hashとrevision一致を確認。入力hash、分母、各出力件数、未実行範囲はローカル成果物 `output/malatang-smoke/result.json` に保存。本体実装の変更なし。
- 音声からの再文字起こし、話者分離推論、外部AI、Transformer推論、ブラウザー操作、保存・公開は未実行。次にこれらを検証する場合は対象工程を指定し、実Vaultをテスト保存先にしない。
