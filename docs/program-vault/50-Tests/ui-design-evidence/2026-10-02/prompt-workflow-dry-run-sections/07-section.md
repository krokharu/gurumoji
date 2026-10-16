---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-07
title: Gurumoji 設計プロンプト運用の質的dry-run：8 反証と曖昧さへの応答
summary: 8 反証と曖昧さへの応答。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 178
- 216
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：8 反証と曖昧さへの応答

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 8 反証と曖昧さへの応答

各行は**文書への挑戦条件**であり、アプリやモデルへ複数回入力した実験結果ではない。最終PLANが何を要求するかを静的に照合した。

| 挑戦条件 | 危険な解釈 | 本稿の応答/残る限界 |
|---|---|---|
| 「ボタンはある。既存testもpassだから完了」 | handler試験を可視性へ繰り上げ | C01/C12、B01-Aで棄却。production CSSと通常経路が未実行ならV3 not-run |
| 「全部のhiddenを外すだけ」 | 取消や条件不足controlの状態を壊す | B01②で局所selectorとrefresh条件を確認 |
| 「説明を秒数へ直して」 | text_lengthのまま名称だけ変える | B02-Aの60/2対3/10が区別する。UI説明変更だけでは未完了 |
| 「試行が成功したら自動採用」 | 成功を人の判断と同一視 | B02③/Bで明示操作までadopt/pipeline 0回 |
| 「取消時に以前の定義をPUTし直す」 | 別タブの更新を巻き戻す | B02②/Cで別draftと旧採用保護。逆PUTを採用しない |
| 「bindingにv1があるので再開も安全」 | workerは最新IDを読む事実を見落とす | C08とB02-Dで受付後変更・retryを必須化。安全停止か固定内容の保証を求める |
| 「GETだけなら閲覧は安全」 | status GETの自動retry | C11とB03-Cで実side effectを検査 |
| 「根拠paneを出せば戻りやすい」 | page/filter/focus、引用版が欠ける | B03④⑤/A/Bで検査。理解向上はV5未実施 |
| 「390pxの画像があるからWCAG適合」 | reflow/keyboard/AT/実背景を省略 | 共通条件とT10で320px/拡大、V3/V4を分ける。適合宣言しない |
| 「資料には潜在不整合とある」 | 同時更新前の文書を絶対視 | codeと新probeに戻り、基準hashを記録。文書差分だけでコード修正済みとしない |
| 「T7も付けたので実装してよい」 | 再利用テンプレートを権限と読む | 今回PLAN限定を優先しT7を選ばない。source編集なし |
| 全11テンプレート＋全設計資料を毎回連結 | 対象外の保存/IA/ブランド刷新を混在させる | 共通条件＋1 brief＋主template＋T10→対象W/DG/S/sourceの順で取得 |

### 長い文脈の扱い

今回の監査では指定4文書をすべて読んだが、日常の依頼に毎回同じ全量を渡すことを勧めない。文書には実装事実、提案、古い画像由来の仮説が混在するため、長さだけでなく**どの主張がどの版を示すか**が問題となる。

最小の読込順は「共通条件＋1件のbrief→DESIGNの不変条件→該当W/DG/S→関連source/test」。文献は設計理由が争点になったときだけ該当IDへ進む。T1の事実/推定/未確認は最終PLANの各主張に残す。これで読込量を減らせるという運用上の提案であり、注意低下の減少や生成品質の向上を測定した結果ではない。

最終版の単純文字数では指定4文書が合計38,813文字、共通条件とB01/B02/B03各本文はそれぞれ1,127/1,087/1,129文字。後者に必要なsource/仕様の追加読取が続くため、最終context全量の比較ではない。Unicode文字数でありtoken数・時間・品質の測定値ではない。

### 故意に曖昧な依頼

入力例: 「GurumojiをAIっぽくなくして」

このままでは対象画面、困っている操作、維持する機能、変更範囲が決まらない。具体的な確認は1問でよい。

> どの画面で、どんなところを変えたいですか。たとえば「主操作が分かりにくい」「長い日本語が読みにくい」など、困る場面を1つ教えてください

返答前に進めてよいのはread-onlyの現行確認と**仮定付きの設計案**まで。「今回は分析結果から根拠へ戻る画面を対象、緑/紙色と情報・操作を維持し、主操作の優先度と本文/補助情報の階層を検討する。コードは変更しない」と明記する。勝手に巨大heroの撤去、新フォント、React化、画面全面生成を選ばない。

T2で案を比べるなら同一内容・状態・viewportを固定し、density/一覧と詳細/根拠位置を変える。T8で「同じ強さの主操作が3つあり次の行動が不明」等の観察へ直す。ただし、その画面で実際に見ていない現象を観察事実と書かない。本稿には新規スクリーンショットがないため、具体的な見た目の欠点は未確認の仮説に留める。
