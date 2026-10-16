---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-06
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-04: 時間欠測・固定来歴・編集UIの受入'
summary: '2026-10-04: 時間欠測・固定来歴・編集UIの受入。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 130
- 163
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-04: 時間欠測・固定来歴・編集UIの受入

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-04: 時間欠測・固定来歴・編集UIの受入

専用branchの固定source `721c308` で標準pytest **1049成功／32skip／1052 subtests成功／失敗0**、同HEADのオフラインDOM **161成功／失敗0**。browser22・Windows10は未実施。詳細、既知失敗の解消根拠、復元手順は[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]、再利用する4部門の依頼範囲は[[60-Operations/20-Development/gurumoji-department-briefs|gurumoji-department-briefs]]へ集約する。

通常importの空JSON markerも既存の欠測意味へ合わせ、raw/Save/音声guardを保持した。世代保護の旧fixture競合は両adapter同期と確実な解放へ直し、production guardは不変更。961組合せ・旧版negativeと250反復の詳細はセッション記録へ分ける。

`focus-group-local-7`／registry11までの欠測・役割混在の意味、追加nullableとcoverage、保存計算版、表示専用時刻projection、固定packageの検証境界は[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]の末尾を参照する。外部consumerはnull/空欄を勝手に0へ補完しない。旧v4〜v6の固定snapshotは元の値と版を保持し、現計算へ書き換えない。実runtimeへの適用、旧workerのdrain、データbackup・downgradeの確認は別であり、今回のソース検証やbundle受渡しで完了したと扱わない。

## 2026-10-04 分析オーケストレーター評価4件の修正

基点は `cc19a84f41592238beec8838134ad477d255131f`。完全履歴bundle v14から別checkout `analysis_orchestrator_fixes/app` と専用branch `dot/analysis-orchestrator-fixes-20261004` を作成し、8時間成果物・評価原本は変更していない。実装commitは `2379a450f473829a2d12122739fcb13521b9c672`。最終配布HEADは修正版ZIPの `manifest.json` とGit bundleの同名branchで確認する。

- **対象なしの誤完了:** preview・開始・既受付snapshotの実行で、除外後の発話集合を適用性判定と測定で統一。空入力／全件除外は保存前に拒否する。固定summary行だけでparticipationをcompletedと表示しない。部分除外と通常入力の完了は維持。
- **O01話者不足の見落とし:** `observed_speaker_count`を使い、UNKNOWNを識別済みラベル数へ加算しない。未知話者件数も非除外集合から取り、モデルが省略できない注意を付ける。ラベル数は人手確認済みの実人数と区別。旧summary-only入力では品質サマリーを保守的に利用する。
- **取消後readyが残る:** 一般失敗と取消を分け、既存の合法遷移に従ってworker終了後に現世代を終端化する。終了pipelineにactive stepを残さず、retry可能にする。確定済みstep・artifactは保持し、旧世代・旧attemptの更新は禁止したまま。
- **公開確定と取消の競合:** 追加の副作用を止めるguardと、既に確定した公開結果の読取照合を分離。公開台帳のpublished/conflict/failedを保持し、未確認はunknownにする。取消は公開済みファイルの巻戻しではない。再試行の成功再利用はStore内で固定package検証、scope/hash、世代guard、最新公開attemptの全先成功を確認してから行う。pipelineに限る明示opt-inであり、直接再公開の挙動は変更しない。

### 最終コードの検証

- 対象・隣接Python **126件成功**。新規回帰25件（orchestrator14、advisor11）を含む。元の適用性、定義固定、世代競合、保存直前取消、部分公開失敗、fixed-run、研究protocol、外部送信境界を再確認。
- Node UI回帰 **155件成功**（ownership40、status32、measurement37、fixed-run46）。これは実ブラウザー操作ではない。
- 全体pytest: **1072 passed / 2 failed / 32 skipped / 1073 subtests passed**。subtestは重複を含む別表示のため合算しない。残る2件は `test_transformer_provenance.TransformerTruncationTests` のtorch未導入によるimport失敗で、基点cc19a84でも同じ失敗を再現。32スキップは実ブラウザー22、Windows専用10。全体成功とは扱わない。
- 独立レビュー: F1〜F4と除外UNKNOWN回帰を確認。中間案で見つかった公開済み再利用時のpackage検証回避・新しい公開失敗の見落としは最終版で解消。実並列取消、二重writer防止、manifest欠落／破損、最新台帳、旧世代guardを別担当が再確認し、修正阻止欠陥なし。
- `git diff --check`、対象Python構文確認、`.venv/bin/python -m pip check`成功。検証用venvにFlask/pytest/Google APIテスト依存等を追加したが、本番依存lockは変更していない。追加依存の版は成果物 `verification/test-environment-final-freeze.txt` に記録。

再現コマンド（`app`で実行）:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest test_analysis_orchestrator_regressions test_analysis_plan_advisor test_analysis_milestones test_analysis_definition_safety test_analysis_generation_safety test_analysis_eligibility test_analysis_core_contracts test_analysis_publication_safety test_analysis_snapshot_commit test_analysis_fixed_run test_analysis_recovery test_analysis_research_protocol test_analysis_llm_contracts -v
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src:tests .venv/bin/python -m pytest tests -q --junitxml=../artifacts/full-final-tests.xml
```

証跡は修正版ZIPの `verification/`（`adjacent-final-tests.log`、`full-final-tests.log/xml`、`node-ui-tests.log`、`baseline-environment-check.log`、`independent-review/`）へ同梱。合成・一時データのみを使った。実データ、移入Vault、認証、外部AI、実モデル推論、実ブラウザー、Windows、push/deployは未実行。一般的な自律手法選択は追加しておらず、O01は既存2手法の確認優先順の助言という範囲を維持した。
