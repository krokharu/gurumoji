---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique-section-03
title: Gurumoji 静止モックアップの独立批評：保持したい点と、過剰修正を避ける点
summary: 保持したい点と、過剰修正を避ける点。出典ノート「Gurumoji 静止モックアップの独立批評」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique
source_path: 50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md
source_sha256: a5930f15d27ba0bde495c47e25e7920c6463caf23571b284ea0a61df3c58cbb7
source_body_lines:
- 111
- 131
split_on: '2026-10-11'
---

# Gurumoji 静止モックアップの独立批評：保持したい点と、過剰修正を避ける点

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/mockup-critique]]。必要な本文だけを取得する。

## 保持したい点と、過剰修正を避ける点

- **数値:** 60/2/0を有効3として平均20.7秒と表示する計算はfixtureと一致。S003は「0秒」「計算済みゼロ」、S004は「欠測」「時刻不明」。平均に0を含め、欠測を含めない文章もある。この区別をlegendだけへ戻さない
- **科学的な限界:** 主張は「可能性」と限定され、引用1件から重要性や全体合意を判断しないと説明される。単なるAI免責badgeより作業に即している。mobile Bにも引き継ぐ
- **採用:** チェック→採用button→「全件実行は始まりません」の並びは明瞭。実行開始を同じbuttonへ合体させない。新しい定義・未採用の表示を、採用済み旧版が破壊されないという実装保証へ読み替えない
- **版差:** 保存結果入力12版／現在入力13版、引用本文の変更warning、現在発話への別入口、音声無効理由を色だけに頼らず示す。このfixtureの理由を「音声がありません」へ置き換えない
- **階層:** desktopの見出し・summary・個票・次操作は追える。過剰に大きいdecorative heroや新ブランドは不要。quiet greenを現在地・操作・数値に一貫して使い、warningを文字と淡いamberで区別する方向を維持
- **legibility:** 今回の短い日本語では明白な欠け・重なり・frame外へのはみ出しは見えなかった。これは長い名前、100行、200%/400%拡大、実フォントの可読性を保証しない。13px補助文字をすべてWCAG違反とする根拠もない
- **密度:** 4個票がmobileで各82pxのcardになるため約360pxを使う。ID/時刻と値/状態の2行は理解しやすい。まず可変高・余白調整を比較し、表を全面に詰めたり必須文を消したりしない。高さだけの最適化はしない

## 選好は分解した仮説として扱う

| 仮説 | この静止図から支持できること | まだ判断できないこと |
|---|---|---|
| Aの段階レビューを最初に導入 | 現在地2、定義要約、確認・採用の順序が表示される。既存3モードとdetailsを維持する | 誤測定発見、学習時間、実装費用の実測 |
| Bのdesktop根拠paneを比較候補に残す | claimとquoteを同時に見られる。fixtureではwarningが近い | 長文・多引用・200%での読みやすさ、focus、pane閉鎖時の選択保持 |
| Bの4タスクnavを独立評価 | labelが研究者の仕事に近い可能性がある | 既存利用者が旧3モードより見つけやすいか。このfixture1課題では判断不能 |
| mobileでは文脈を短く保持する | Aは上下移動、Bは現在主張欠落という異なる負担がある | task成功や往復数の優劣。Bへclaim anchorを足してから同条件比較が必要 |

M（定義と試行の配置）、E（根拠inline/pane）、N（nav再編）を一度に変えないという `comparison.md` の方針を支持する。今回はA/Bの人気投票や合計点にはしない。
