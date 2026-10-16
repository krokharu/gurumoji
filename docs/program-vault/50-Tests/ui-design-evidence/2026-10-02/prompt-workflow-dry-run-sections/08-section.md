---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-08
title: Gurumoji 設計プロンプト運用の質的dry-run：9 テンプレートへの最小修正案
summary: 9 テンプレートへの最小修正案。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 217
- 275
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：9 テンプレートへの最小修正案

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 9 テンプレートへの最小修正案

元のprompt調査は直接編集していない。以下は次版へ取り込む候補。全契約を常設文書に複製せず、短い補足と対象へのリンクにする。

### 共通の出力条件へ追加する3行

```text
実装PLANには、変えてよい責務、API/保存に必要な追加、旧版互換と入力を消さない戻し方を分けて書く。
受入ごとに開始経路/fixture/操作/期待値/証拠層を付け、未実行はnot-runとする。
関連するW/DG/Sとsourceを確認し、資料更新や未決定の契約があれば実装前gateとして残す。
```

### T1またはB01へ追加する1行

```text
入口改善はproduction CSSの通常画面からpointer/keyboardで到達を確認する計画とし、handler呼出しだけを可視操作の合格にしない。
```

### T11またはB02へ追加する2行

```text
既採用定義を修正して取消しても旧採用を失わないこと、試行個票/欠測/版が実responseで取得できることを確認する。
受付後の定義変更と再起動/retryでも採用内容と実計算を照合する。UI採用確認とサーバーの実行版保証を別条件にする。
```

### T6またはB03へ追加する1行

```text
固定run閲覧に使う読取経路の副作用を確認する。GETでもretryを起こす経路は分離し、旧来歴を現在値で補完しない。
```

足す場所は主templateまたはbriefのどちらかに決め、両方へ重複させない。T10に全実装仕様を詰め込まない。知識索引は本稿/briefへの1リンクとW02の版保証への案内で足りる。

## 10 次に必要な確認

1. B01の入口adapter案を承認した後、合成fixtureで実装しV1/V2/V3を実行する
2. B02は最小safe-stopかsnapshot導入かを決め、原子的固定と旧run/rollback契約をレビューしてから実装する
3. B03は固定artifact→viewerのfield対応表をread-onlyで完成させ、復帰範囲を明文化する

モデル比較/利用者実験を行うなら別計画と権限で実施する。今回の3件の自己レビューを、その比較の結果へ置き換えない。

## 11 文書検証記録

2026-10-02 UTCの最終read-only確認。

- 文書検査: 3 briefと3 PLANの対応を確認。ローカルMarkdownリンクはbrief 8件/本稿10件、存在しない参照0件。リンク先のS01/S02/S04見出しも確認
- source照合: C01〜C12の記載箇所を読み、HEADは記載の`ddc23abe…`、branchは`dot/cloud-cpu-setup`。appの`git status --short`は読取開始時/成果物作成後とも空
- 別担当による文書レビュー: 分類の中止能力を3分析共通に読める文言を指摘。B01 brief/PLANを修正し、既存取消対応と分類の未確認/別依存を分離。これは文書校閲で、別モデル比較や利用者評価ではない
- アプリ受入: 今回のV1/V2/V3/V4/V5はすべてnot-run。既存probe報告の読取を今回の再実行へ数えていない
- 作成範囲: 本稿と`prompt-workflow-task-briefs.md`のみ。アプリsource、Software Vault、runtime、移入Vaultへ変更なし

参照した4文書の最終検査時SHA-256。合同作業で後から文書が変わった場合、この記録より新しい版を使ったことにはならない。

| 文書 | Unicode文字数 | SHA-256 |
|---|---:|---|
| prompt-research.md | 16,633 | `82a1764145b4e6ba8b6a0cfd5a8a7a08fd9c7c70f34de01eee91b536d7c516c7` |
| draft-DESIGN.md | 6,458 | `fe0e576b6cc33f5e3fc041a290e60d2ada5397b2fdf6dc76c71c2444e33ce308` |
| agent-design-knowledge.md | 4,123 | `8672d525c12a7f988620a4ae183c1e52209dc6449a5279fd5bba6c5ba935e83d` |
| design-implementation-plan.md | 11,599 | `2a6448fa1c4b05944c7848e589610431d646e75736a49b764ac2b20ee25ebd6e` |
