---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-04
title: Gurumoji 設計プロンプト運用の質的dry-run：5 B02にテンプレートを適用したレビュー済みPLAN
summary: 5 B02にテンプレートを適用したレビュー済みPLAN。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 86
- 116
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：5 B02にテンプレートを適用したレビュー済みPLAN

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 5 B02にテンプレートを適用したレビュー済みPLAN

**目的:** 研究者が秒数の測定内容を確認し、試行を見て明示採用し、受付内容と一致する計算だけを確定する。T11の「定義/試行/採用/全件」を使い、C05〜C08の現行制約を具体化する。

### 最小変更と状態

1. 既存validatorに適合する入力列・規則・型・尺度・手法を可視化する。durationはduration列/number/ratio、文字数はtext/text_length等の実契約を説明する。名称/説明は計算規則ではないと明示する
2. 既採用を編集する場合、旧IDをdraft PUTしない。別draft IDへ複製する方式を優先し、元定義との関係を画面で示す。Cancelは未採用draftを残せるが、旧採用payloadの逆PUTやdraft削除を勝手に行わない
3. 編集→試行中→レビュー待ち→明示採用→全件開始を分ける。レビュー待ちはまず画面の状態。新しい永続statusを無断追加しない。Cancel/Close/Backでadopt/pipelineを送らない
4. trialへID付き個票、欠測理由、測定に使った定義revisionを後方互換で追加する計画を別差分にする。既存values/件数/input_hashを保持し、値の配列を現在の発話順へ推測結合しない
5. 定義内容、item、入力版が変われば古いレビューを無効化する。409は入力を保持して再読込/比較を促す。draft版rと同内容adopt版r+1の対応を示し、status変更だけを別内容と混同しない
6. **実行時版保証は必須。** 受付後の定義差替え、再起動/retryでも受付と同じ定義を使う。最小対策は版/内容不一致・不明で安全停止。本対応は受付時に完全payload/版/hashを原子的に固定し、実行/再開/保存でその同一値を使う。単に開始直前に最新revisionを読むだけでは受付後raceを防がない
7. UIで研究者が採用したことと、サーバーがそのレビュー行為を永続的に保証することは別。trial ID/定義revision/input fingerprintを結ぶserver review gateは別契約レビュー。これを後回しにしても⑥は省略しない
8. 390pxでは定義要約→個票→欠測/限界→採用の順。個票の列名/単位/IDは省略しない。長い日本語label、320px/拡大、IME確定Enterで誤採用しない、Tab順、エラー欄へのfocus、Close後のfocusを計画する

### 受入証拠の計画

- B02-A: e1/e2でduration=60/2と文字数=3/10を対照にする。e3欠測理由とe4真の0秒を分離。名義尺度の平均をvalidatorが拒否し、欄へ理由が結び付く
- B02-B: trial responseの個票ID/値/理由/revision/hashを画面と照合。明示採用までadopted PUT=0、pipeline POST=0。Close/Cancel/Back、二重submit、試行後編集/別item/別ID/入力更新を通信記録で確かめる
- B02-C: 採用済みID→修正試行→取消/409の後、元のadopted payloadが同じであることを一時DBで確認する。旧定義が欠けた場合を「キャンセル成功」と表示しない
- B02-D: 受付を一時停止→別タブの定義変更→worker再開、再起動/retryを制御fixtureで再現。binding/definitions/実測値/保存packageが同じ内容か、理由付き安全停止。異なる60をv1文字数の成功結果として保存しない
- B02-E: V3で通常dialog起動から採用/全件まで通す。V1/V2成功だけでGUI合格にしない。V4実AT、Windows IME、V5単位と採用の理解は別記

### データと戻し方

trial responseの追加fieldは旧clientが読める形を保つ。定義snapshotを保存する場合は、既存保存場所と契約versionを先にレビューし、旧reader/旧待機run/rollback後の読取を一時DBでdry-runする。SQLを変えるなら追加のみ、backup/復旧を先に設計する。固定payloadのない旧待機runは一致を証明できなければ安全停止し、現在値で埋めない。完了済みrunを再計算・来歴改変しない。

未決定はsnapshotの具体的な保存field/原子的固定の境界/旧版workerへ戻した時の扱い。安全停止を先行するかsnapshotを同時導入するかで互換試験が変わるため、ここはPLANの部分充足として残す。戻し方はコード差分の撤回であり、新draft・研究者編集・新成果物の削除ではない。

**今回の結果:** コード照合と既存probeの読取のみ。B02-A〜Eは未実行。明示採用buttonを加えるだけの案は却下する。測定と宣言の一致は検証対象だが、研究の科学的妥当性を保証したとはしない。
