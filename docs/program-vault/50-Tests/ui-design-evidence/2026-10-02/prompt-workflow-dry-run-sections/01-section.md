---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-01
title: Gurumoji 設計プロンプト運用の質的dry-run：Gurumoji 設計プロンプト運用の質的dry-run
summary: Gurumoji 設計プロンプト運用の質的dry-run。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 1
- 39
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：Gurumoji 設計プロンプト運用の質的dry-run

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。


# Gurumoji 設計プロンプト運用の質的dry-run

2026-10-02 UTC · 実装PLANの作成と文書レビュー · 対象HEAD `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`

## 1 結論

**短いbriefから必要な設計知識と現行コードへ戻り、3件の具体的な実装PLANを作れた。ただし、テンプレートだけで安全な実装が保証されるという結果ではない。** 最も重要な補足は、通常操作での入口確認、定義を採用するUIと実行時の版保証の分離、固定結果の閲覧から自動retryを呼ばないことだった。

W01は既存入口の小さい復元として計画できる。W02は画面修正だけでは完了せず、個票responseと実行境界の修正を要する。W04は既存根拠guardを保ち、固定artifactと復帰文脈を接続する。W02の保存互換、W04の固定viewerのfield対応には後続の契約レビューを残した。

成果物は本稿のレビュー済みPLANと、コピーして使える[3件のタスクbrief](../../../../40-Design/ui-design-research/2026-10-02/prompt-workflow-task-briefs.md)。アプリsource、設定、DB、Vaultは変更していない。

## 2 何を実施したか

### 方法と限界

1. 指定されたprompt調査、DESIGN初稿、知識索引、実装計画を読み、W01/W02/W04だけを今回の課題に選んだ
2. 各briefにT1/T11/T6のいずれか1つと共通のT10を適用し、対象コードと隣接テストをread-onlyで照合した
3. 本稿§4〜6に実装PLANを作成した。これは同一の作成者による記述的なdry-runで、別モデルの生成結果を集計したものではない
4. §7の固定した5観点で文書を自己レビューし、§8の反証課題を当てた。第三者による盲検評価、独立した参加者、ランダム割付、反復モデル呼出しはない
5. 合同作業で更新されたW02の隔離probeを読み、実行版の不一致を「潜在」から「合成adapterで再現済み」へ同期した。実ディスク保存/GUI確認済みへは拡大していない

**実行しなかったもの:** アプリ起動、UI操作、テストスイート、probeの再実行、モデル生成比較、実モデル品質評価、利用者調査、AT、Windows GUI、外部API、私有データ/認証へのアクセス、source編集。採点はPLANの記述の充足を示し、ソフトウェアの合格率、モデルの成績、生産性改善率を示さない。

今回のshell操作は対象文書/コードの読取、Git HEAD/差分確認、依頼されたMarkdown成果物の作成/参照検査。既存probeの報告を引用するときは「既存probe」と明記する。列挙した受入ケースはすべて**将来実行する計画**。

### テンプレートの位置付け

採用したT1/T6/T10/T11は[prompt-research.md §6](../../../../40-Design/ui-design-research/2026-10-02/prompt-research-sections/05-section.md#6-再利用できる依頼テンプレート)で公開した本スプリント独自のテンプレート。公式ベンダーの文面ではない。資料に記録されたOpenAI/Claude Code/Figma等の一次資料から「対象を絞る、現行を読む、検証可能な条件を渡す」を採用した。今回は外部サイトを再取得していない。T7は実装権限を要求するため使わず、実装手順のPLANを出すに留めた。

### 読取入口

- [知識索引](../../../../40-Design/30-Interface/ui-design-knowledge/00-Index.md): 対象W/DG/Sと根拠への案内
- [DESIGN初稿](../../../../40-Design/30-Interface/ui-design-contract/00-Index.md)§3/5/7: 守る契約、定義/根拠/状態、検証層
- [実装計画](../../../../40-Design/30-Interface/ui-design-implementation-plan/00-Index.md)W01/W02/W04/W09: 対象、依存、rollback
- [シナリオ](../../../30-Interface/ui-design-scenarios/00-Index.md)S01/S02/S04と[受入方法](../../../30-Interface/ui-design-acceptance.md): 操作単位と証拠の限界
- appの[AGENTS.md](../../../../../../AGENTS.md)、関連source/隣接test: 現行実装の正本。runtimeや移入研究Vaultは参照しない
