---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns-section-03
title: Gurumoji の研究作業に使う公式 UI 参照パターン：3 採用する原則
summary: 3 採用する原則。出典ノート「Gurumoji の研究作業に使う公式 UI 参照パターン」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns
source_path: 40-Design/ui-design-research/2026-10-02/reference-patterns.md
source_sha256: f1334e394b188d0ff4c52216c8a7ff37e52789869513174579c3868d7764a702
source_body_lines:
- 72
- 115
split_on: '2026-10-11'
---

# Gurumoji の研究作業に使う公式 UI 参照パターン：3 採用する原則

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/reference-patterns]]。必要な本文だけを取得する。

## 3 採用する原則

以下の「採用」は設計原則の候補であり、実装済み・利用者検証済みという意味ではない。

### A01 根拠を開くときに対象と戻り先を保つ

**観察**: MAXQDA の取得一覧には segment の出典があり、原文の該当範囲へ移る。公式画像でも抜粋と出典位置が近い [R03, S01]。Dovetail の回答には展開式の出典 preview があると説明される [R14]。

**Gurumoji の案 D**: 結果の直近に「引用を見る」を置く。開いた根拠には dataset、表示 run、入力 revision、segment ID、話者、時刻を添える。閉じる／戻る際は結果内の位置と focus を戻す。音声確認の後も選択引用を保持する。

**理由**: 監査 F2 が求める往復を、文書名の暗記やタブ再探索に依存させない。来歴が違う場合に、現在本文へ無言で移動しない。

**受入**: 過去run→根拠→前後の音声→戻るで同じ結果へ復帰する。元segment削除・音声なし・現在版変更も含め、誤った再生リンクを作らない。

### A02 計算結果と採用する変更を別にする

**観察**: MAXQDA は既存コードと AI 提案を同じ行で示し、選んだ追加／削除の数を Apply に表示する [R06, S03]。ATLAS.ti も AI Coding の候補と引用を確認した後に Apply と説明する [R07]。

**Gurumoji の案 D**: 「処理が完了」と「研究者が採用」を別状態にする。測定は DG-02 の「定義→少数試行→確認→採用→全件実行」を守る。コード提案を実装する場合は原文・既存・提案・保留・選択差分を読み比べられるようにし、「追加3件／削除1件」など対象を示す。

**理由**: 試行が成功しただけで測定の意味まで採用されたことにしない。件数には「発話数」「コード付与数」など単位を必ず付ける。

**受入**: 全件選択→個別解除→適用前取消で研究者の既存編集が変わらない。表示filterだけなのか全候補なのか、一括対象を誤認しない。

### A03 処理の居場所を残す

**観察**: MAXQDA は実行数の入口と完了通知、Descript は別のsync進行表示を説明している [R04, R19]。

**Gurumoji の案 D**: 既存M0〜M7の永続pipelineを使い、job IDと対象を持つ短い状態入口を残す。本文編集を続けていても、完了通知で編集対象を置き換えない。実行、結果の保存、Vaultへの書出し、研究者確認を別々に示す。

**理由**: 監査 DG-03/11 と F4 に直結する。8段階の完了数を実処理時間の百分率と誤認させない。

**受入**: 実行中に別datasetへ移動し、元jobへ戻れる。計算完了＋公開失敗では保存済み成果を開け、公開だけを再試行できる。通信断を処理失敗と断定しない。

### A04 出力の範囲と失われる情報を先に見せる

**観察**: MAXQDA は出典や付加情報を出力設定に持つ [R21]。Dovetail は形式ごとに保持できる情報と制約が異なることを明記する [R15]。

**Gurumoji の案 D**: 現在filterか固定runかを出力前に表示する。「本文・時刻・話者・コード・ノート・来歴」のうち含まれるものを要約し、含まれない重要情報を示す。出力packageに入力版、対象集合、除外、設定、算出時刻を残す。

**理由**: ファイルを作れたことと、研究結果を再現可能に渡せたことは異なる。現行通常分析のExcel出力とpipeline固定packageの形式制約も区別する。

**受入**: filter後の件数、引用、分母がpreviewと出力で一致する。生成失敗をdownload済みと表示しない。
