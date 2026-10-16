---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-08
title: Gurumoji UI改善の実装計画：W08 日本語の読みやすさと狭幅を調整する
summary: W08 日本語の読みやすさと狭幅を調整する。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 164
- 202
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：W08 日本語の読みやすさと狭幅を調整する

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

### W08 日本語の読みやすさと狭幅を調整する

- 対象: DG-07/08/12/14の指定selector、作成以外の表、話者・履歴・分析nav
- 作業: 現行HEADの画像を取得して旧画像の仮説を再確認。本文16px相当・label14〜15px相当・補助13px相当、本文行間1.6〜1.8は比較候補。表の列優先順位、長文折返し、要約／詳細の分離を先に検討する
- 比較条件: v1の開発注釈による密度を評価対象へ持ち込まない。v2は全長の静止図で、first viewportや実reflowではない。B mobileが短い分には研究者メモを別状態へ移した差もあるため、画像高を効率点へ換算しない。短い日本語、版・欠測・限界の可視性を維持して比較する
- nav: selected項目をnav内でnearest表示、または狭幅で選択メニューを比較。本文のスクロールや編集中focusを不用意に動かさない。reduced-motion時の直接smooth呼出しも確認する
- 合格: S06/S07。日本語IME、長い氏名・ファイル名・発話、320/390/959/960/1440px、200%拡大、必要な400%相当、Windows font環境。主作業到達までの操作／スクロールを比較し、警告・欠測説明を隠して見かけだけ短縮しない
- 出典: DG-07/08/12/14、UX:S11/UX:S13/UX:S22/UX:S27、PR:T3/PR:T8/PR:T9
- 移行／rollback: 画面単位でCSSを変更し、既存breakpointを理由なく全面変更しない。style差分を戻しても状態・保存契約は維持

## 4 W09 受入のゲート

詳細は[受入方法](../../../50-Tests/30-Interface/ui-design-acceptance.md)。表の各列を独立記録する。

| 層 | 証明するもの | 合格へ含めないもの |
|---|---|---|
| V1 contract/unit | 計算値、validator、payload、revision、保存状態 | 可視性、hit testing、人の理解 |
| V2 component | 合成DOM、属性、文言、指定CSS | 通常の開始入口、実AT音声 |
| V3 browser operability | production CSS＋通常pointer/keyboard＋画面遷移 | forced click、hidden解除、操作の代わりの直接state設定 |
| V4 assistive technology | 実accessibility treeと実AT発話 | ARIA属性だけによる音声合格 |
| V5利用者理解 | 対象版・測定意味・送信先の理解、タスク成績 | エージェントの模擬ペルソナ、見た目の好みだけ |

V1/V2で失敗原因を早く特定し、V3で通常到達性、V4で中心作業を確認する。W07の採用判断はV5の形成的比較を含める。参加者を確保できない場合は未実施として戻せる試作に留め、効果を断定しない。

v2の10図は静止表示レビューとして別記する。生成側の寸法／文字境界検査と独立した画素批評は、アプリのV1〜V5合格へ転記しない。修正版の明白な欠け・重なりが見つからなかったことも、実font／pointer／focus／AT／利用者理解の成功を意味しない。

既存test_ui_safety_browserのlocator＋実Tabは良い土台。初期render直接呼出しがあるため、一覧→対象を開く外側の導線も追加する。test_content_browserのDOM click、Transformer fixtureのproduction CSS欠如、閉じたadvisor dialogへの値代入は別層と記録する。

全試験は合成録音・一時DB／Vault・stub providerを原則にする。これはUI/APIの検証であり実モデル精度ではない。外部AI・実録音・追加モデルはこの計画だけでは使用しない。sandbox拒否やsocket制限は安全条件を緩めず、利用可能な正規環境で確認する。

### リリース判断の最低条件

- 対象commitと変更ファイルhashを固定し、該当シナリオ、隣接unit/integration、影響に応じた全体試験を最終差分で実行
- W01/02の可視入口・測定対照がV3で成功。V1/V2だけならUI受入済みとしない
- 原25件の関連回帰を再確認。Windows UI10件は該当環境での実受入が揃ったときだけ元表を更新
- 失敗／未実施／skipを分ける。過去の864 passed等を新commitの証拠へ流用しない
- 研究者データ保護・引用版・欠測・対象集合・出力整合に退行なし。発見した差分は既存issue IDと結ぶ
- 配置・push・Windows反映は別の承認・実施結果を持つ。試験成功だけで公開済みとしない
