---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-comparison-section-01
title: Gurumoji：2案の低忠実度フロー比較：Gurumoji：2案の低忠実度フロー比較
summary: Gurumoji：2案の低忠実度フロー比較。出典ノート「Gurumoji：2案の低忠実度フロー比較」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-comparison
source_path: 40-Design/ui-design-assets/2026-10-02/prototypes/comparison.md
source_sha256: e1e1cb01403af93a48b0bcef230d4b0336546f52a6ba6173e48ca7a30c9887a9
source_body_lines:
- 1
- 33
split_on: '2026-10-11'
---

# Gurumoji：2案の低忠実度フロー比較：Gurumoji：2案の低忠実度フロー比較

親索引・状態・確認版：[[40-Design/ui-design-assets/2026-10-02/prototypes/comparison]]。必要な本文だけを取得する。


# Gurumoji：2案の低忠実度フロー比較

2026-10-02 UTC / レビュー用、未採用・未実装  
対象HEAD：`ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`  
この資料は合成例の静止設計案であり、現行アプリのスクリーンショット、操作可能な試作品、利用者テスト結果ではない。アプリ・runtime・Vault・資格情報には変更を加えていない。

## 判断の要約

**Aを段階導入の初期候補にし、Bの対照面と根拠paneを独立して比較する。** Aは既存の入口とdetailsを残しやすい。Bは定義と個票、主張と引用を同時に見比べられるが、nav移動と狭幅の復帰実装の費用が増える。この優劣はソースと構造に基づく設計判断であり、使いやすさを実証したものではない。

測定の意味、既採用版の保護、試行と採用の分離、実行時の定義固定は両案の必須条件。レイアウトの選択を待たずW02へ進められる。W01の実行入口修正も4タスク化を条件にしない。

- [静止図とテキスト代替を開く](../index.html)
- [共通fixture](../synthetic-fixture.json)
- [表示検査と未実施範囲](../verification.md)

## 1 同じ作業を異なる構造で見せる

| 観点 | A：既存モード＋段階レビュー | B：タスク入口＋対照面 |
|---|---|---|
| 分析内の入口 | 自動分析／設定・手動分析／手法別を保持 | 結果を見る／比較する／分析を組む／データ・出力へ再編案 |
| 測定定義 | 既存dialogの流れに沿う編集→試行→確認。図の左側は試行時の読み取り要約 | desktopでは定義編集を左、試行を右。編集と試行が同じ作業面にある |
| 採用 | 試行個票を確認した次の操作。採用と全件実行を分ける | 対照面の下で同じ採用操作。入力を変えたら右の試行は失効 |
| 根拠 | 結果card直下のdetailsを開く | 必要時だけ右pane。閉じると結果の幅を戻す |
| 390px | 定義・試行・採用を1段階ずつ、根拠は同じ結果内 | 定義／試行を同一draftの切替で表示。根拠は全幅の別状態 |
| 必要な復帰 | detailsの起点focusと展開位置、原音確認からの復帰 | 左の選択・filterを保持したpane開閉。mobileではrun等の復帰状態も必要 |
| 主なリスク | 長い引用の展開で結果が遠くなる。段階間で測定内容を記憶し直す | 同時に見せる情報が増える。モード再編による入口の学び直し、狭幅切替の状態管理 |

上部4入口、既存hash/query、対象ID、保存revisionは両案で維持する。Bの4タスクは上部navの置換ではなく「分析内」の再編。manual codeとmanual measurementを同じ意味の「手動」として統合しない。

図は設計注釈を同じ面に載せたストーリーボード。mobileの測定図は複数の状態を縦に並べており、実製品で全段階を1本の長いページにする提案ではない。desktopのAも定義編集と確認を同時に有効にするものではなく、左は保存した試行対象の要約である。
