---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-05
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-03〜04: 復旧と専用ブランチの改善'
summary: '2026-10-03〜04: 復旧と専用ブランチの改善。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 115
- 129
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-03〜04: 復旧と専用ブランチの改善

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-03〜04: 復旧と専用ブランチの改善

現在の作業は[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]、再利用する分担は[[60-Operations/20-Development/gurumoji-department-briefs|gurumoji-department-briefs]]を参照。旧環境で失われた未公開sourceを復元したと扱わず、ddc23abeと検証済み設計資料から新しく修正している。

Backend区切り9768b80は定義固定/CAS、測定型・欠測、4writerの公開試行台帳、世代/再起動、入力stamp競合を含む。非browser回帰926成功・10skip・24deselect、独立48件と1120定義matrixで受入。UI・実browser・実モデル・実Vault・旧binaryへのdowngradeは別の確認範囲。別途承認された実runtime利用の前には旧workerを停止/drainし、旧成果を保存する。完全履歴のsource bundleを区切りごとに保管し、元PCや公開remoteへの自動反映は行っていない。

## 2026-10-03 固定run viewerの区切り

対象sourceは`ce6e003`（実装`f31da55`、可読要約・CSV/公開証拠補正`5ac07ec`）。既存run/artifactをread-onlyで開き、最新100件外もrun IDで参照する。保存した手法要約・状態・制約・採用定義ID/版・有限表を表示し、JSON/hash/catalogは詳細へ分けた。固定packageを現在データで埋めず、GET/exportで計算・回復・公開・DB更新をしない。公開の最新durable試行と古いpipeline台帳を別表示し、空scopeの同package照合も守る。判断はADR-122追記。

- `5ac07ec`を凍結したcanonical `PYTHONPATH=src:tests ../app/.venv/bin/python -m pytest tests/ -q`: 1012 passed、32 skipped、953 subtests、lokyのCPU数warning1。2026-10-03 23:45:37〜23:47:45 UTC、前後HEAD/clean状態/src+tests集合hashが一致。
- 後続`ce6e003`は空scope証拠guardと保存package入口の局所差分。対象27 tests/39 subtests、viewer合成35ケース、status合成32ケース成功。全体結果をこの後続差分の全体合格として流用しない。統合branchで最終回帰する。
- 実行中に編集が混在した先行全体runは探索用として明記し、固定commitのcanonical証拠から除外。証拠はappから`../artifacts/eight-hour-20261003/fixed-run-viewer/`。
- 実browser/keyboard/focus/ATと視覚的受入は未実施。禁じられたブラウザー起動/localhost迂回を試していない。実研究データ・Vault、外部AI/モデル取得、migration、push/deploy、認証/安全設定へ変更なし。
