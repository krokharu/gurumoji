---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-08
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-04 追補: 初期構築の部分再開と自律runの安全出力'
summary: '2026-10-04 追補: 初期構築の部分再開と自律runの安全出力。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 204
- 233
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-04 追補: 初期構築の部分再開と自律runの安全出力

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-04 追補: 初期構築の部分再開と自律runの安全出力

実装commit `0a5a0c4a5c0a0a1ec50e680d6d8aa655251c0dcc`。基点 `f3e16ba9e737bfb9ed29cfaaf11a4ebf57edf340` と旧ブランチ `dot/core-handler-orchestration-20261004` をそのまま残し、後継 `dot/core-handler-durable-output-20261004` に実装した。前節で未実装とした初期部分再開・明示選択Vault出力の2項目をこの版で追加した。

### 初期構築

runを先に永続化し、`base → linguistics → statistics → content → snapshot` の5段階を順番に実行する。各段階の入力hash・前段hash・版・出力hashと実行回数を保存する。完了後に別段階が故障した場合、完成済みの統計を含めた段階を再実行せず、未完了段階だけ再開する。未commit段階は再計算し得るが、完了済み段階を単にラベル付けし直す擬似再開ではない。

開始時row、保存済みAI/Transformer/classification入力、選択済みexpert定義/knowledgeを固定し、後段へ新しい情報を混ぜない。旧ready初期snapshotも再利用する。初期構築の初めから時計を固定し、期限超過後は進行中段階の出力を保持しても次段階/最終採用/Coreを始めない。再開で時計をresetしない。

### 固定成果物と選択公開

全量台帳を一度封印し、`AnalysisStore.save(publish=False)` で固定packageを作る。新runで4先一式を明示選択した場合だけ、既存のInput・Orchestrator・Visualization・Research writerへ渡す。既定OFF、個別選択なし、旧runのscope拡大なし。Researchには発話本文も保存する。原文版を確認して実際に分析した本文を引用へ投影し、全量raw/批判/採否/ラベル版をresult.jsonに残す。

保存・公開の試行、世代、封印hash、元会話の現存・版を専用guardで確認する。汎用publish/retryはこのkindに専用guardを要求し、generic refreshからの迂回を防ぐ。一部失敗/応答喪失/再起動からは同じpackage・scopeで保存/公開だけ再試行し、AI・統計・初期構築を再計算しない。入力変更後は成果物をstaleで保存できるがVault writerは止める。取消/停止/失敗runは自動公開しない。

生成ノートの編集履歴保存・利用者削除の維持を既存policyで保つ。writerの処理がpublishedでも、削除したノートまで復元する意味ではなく、全ノート存在の保証ではない。表示も分析終了・固定保存・4先処理を分離する。

### 検証と残る制約

- 対象128件、全JSDOM187件（既存161＋自律UI26）が成功。実際の5段階adapterで統計計算が再開前後に1回であること、旧snapshotとの完全値/hash一致（warm cache）を確認
- 4先は一時DB/一時Vaultで既存writerを動かした。部分失敗、同時retry、応答喪失、初期/出力改ざん、旧世代、生成ノート編集/削除の逆境試験を含む。実モデルはmockのみ
- 全体pytest **1200 passed / 2 failed / 32 skipped / 1099 subtests passed**。2失敗は前節と同じtorch未導入で、32skipも実ブラウザー22・Windows10。ソース/testは最終全体試験中のhash差分0。CRLF形式を維持し、CRLF対応diff・Python compile・JS syntax・pip checkも成功
- 手動停止後も初期段階やAI呼出しのrunning/cancel_requestedが残る間は読取pollingで完了/後着usageを確認し、新規実行をしない。復旧済みunknownを永遠にrunningとしてpollしない

証跡は更新source ZIPの `verification/`、静的合成previewは `ui/orchestration-ui-preview.html`。実画面画像はクラウドブラウザーの既知制約により未取得で、previewを実画面受入の証拠とはしない。

確認的統計/holdout、金額上限、汎用の数量専門LLM、自由コード/検索は引き続き制限する。実データ・実Vault・実AI・Windows反映・push・merge・deployは行っていない。旧Library版・旧HEADを保全し、受渡し時は新ZIP/bundleから全ソースhashとHEADを復元確認する。
