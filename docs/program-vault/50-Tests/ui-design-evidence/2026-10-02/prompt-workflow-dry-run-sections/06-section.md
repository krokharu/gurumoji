---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-06
title: Gurumoji 設計プロンプト運用の質的dry-run：7 PLANの採点とレビュー結果
summary: 7 PLANの採点とレビュー結果。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 146
- 177
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：7 PLANの採点とレビュー結果

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 7 PLANの採点とレビュー結果

### 事前の判定基準

0＝記載がない/契約違反、1＝言及はあるが対象や証拠/未決定の契約が残る、2＝具体的な対象・根拠・将来の受入証拠まで記載。これは本稿を作成したエージェントによる順序尺度の自己レビュー。点数差の統計的意味はなく、合計/平均/改善率は計算しない。

| 観点 | 2に必要な記載 | B01 | B02 | B03 |
|---|---|---:|---:|---:|
| 実repo契約 | source/能力/既存機構と変更境界、未実装依存の具体化 | 2 | 2 | 1 |
| 科学的保護 | 入力/定義/run/欠測/人の判断の該当する境界と反証fixture | 2 | 2 | 2 |
| mobile/keyboard | viewportだけでなく通常経路/狭幅/IME/復帰と証拠 | 2 | 2 | 2 |
| データ/rollback | 保存・並行更新・旧版互換・研究者編集を失わない戻し方 | 2 | 1 | 2 |
| not-runの限界 | source/probe/V1〜V5の区別と今回未実施の明示 | 2 | 2 | 2 |

- B01の2は3入口の操作/別routeと取消能力の境界を計画に含めた評価で、UIの現在の可視性が合格した意味ではない
- B02のdata=1は固定payloadの保存契約/旧worker互換の未決定による。名称と値が一致するUIだけではこの条件を解決できない
- B03のrepo=1は固定artifactからのviewer field対応と再読込復帰仕様の未確定による。既存入口へ無条件に差し込む実装承認には足りない

**相殺できない停止条件:** 別定義の値を正常確定、古い引用の現在来歴化、閲覧で推論/retryを開始、既採用/研究者編集の喪失、非表示controlの直接clickでV3合格。このいずれかが残れば他の2点で相殺しない。

### レビューで具体化したこと

| テンプレートだけでは決まらない点 | 最終PLANの扱い |
|---|---|
| T1の「現行画面とテスト」は通常の到達性まで自動で含まない | B01-Aのproduction CSS/一覧始点/通常pointer・Tab・Enter/実矩形、C12の偽合格防止 |
| T11の「定義版を確認」からtrial response不足の解決策は出ない | B02④に後方互換の個票/revision拡張。現在の発話順による推測禁止 |
| T11の採用確認だけでは同ID上書き/worker再読を止めない | B02②⑥、旧定義保護と受付後raceの別受入 |
| T6の「既存深いリンク」だけでは固定artifactと現在データを分けられない | B03②③、固定viewer依存とside-effect検査 |
| T10は報告分類を与えるがrollbackの仕様は与えない | 各PLANに保存/旧版互換/取消/戻し方を独立記載 |

これはテンプレートの失敗率を計測した表ではない。選択した指示を実repoへ適用すると追加確認が必要だった箇所の記録である。
