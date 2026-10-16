---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-knowledge-section-04
title: Gurumoji 設計知識の入口：次のエージェントへ渡す最小brief
summary: 次のエージェントへ渡す最小brief。出典ノート「Gurumoji 設計知識の入口」の分割本文。
parent_note_id: design-ui-knowledge
source_path: 40-Design/ui-design-knowledge.md
source_sha256: 91d434fb547e4d56ecae2bd1c1b0f471f816a06c2e275bfe5735e8440a809428
source_body_lines:
- 80
- 90
split_on: '2026-10-11'
---

# Gurumoji 設計知識の入口：次のエージェントへ渡す最小brief

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-knowledge/00-Index]]。必要な本文だけを取得する。

## 次のエージェントへ渡す最小brief

「対象commit、対象W/DG、改善する研究者の仕事、変更してよいファイル、守る契約、使うシナリオ、必要なV層、成功／失敗／未実施の報告、禁止する実データ・外部送信・公開」を渡す。参考画像は版・状態・幅と参考にする属性を付ける。未確認の能力を成功済みとして補完させない。

記録例: `W02 → DG-02/H3 → definition APIとvalidator → S02のduration対照 → V1成功/V3未実施 → 採用前`。設計が良さそうか、コードがあるか、人が使えるかを別々に追跡できることが目的。

調査・検証はdotで進め、節目だけ既存Software Vaultに決定・commit・証拠・未実施・次の作業を残す。研究者所有ノートを開発記録で上書きしない。

## 保存版と更新先

この索引と設計契約・実装計画はSoftware Vault内を作業用正本とする。日付付き研究・証拠は調査時の保存版。現在の採用版はここから選び、訂正は出典・条件・測定結果を残して新しい日付版へ記録する。図と元検証hashの範囲は[静止案の保存説明](../../ui-design-assets/2026-10-02/README.md)、コード検証の範囲は[証拠の保存説明](../../../50-Tests/ui-design-evidence/2026-10-02/README.md)を必要時だけ読む。
