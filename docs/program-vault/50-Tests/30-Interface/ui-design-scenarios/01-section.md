---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: test-ui-design-scenarios-section-01
title: Gurumoji 研究作業シナリオと受入条件：Gurumoji 研究作業シナリオと受入条件
summary: Gurumoji 研究作業シナリオと受入条件。出典ノート「Gurumoji 研究作業シナリオと受入条件」の分割本文。
parent_note_id: test-ui-design-scenarios
source_path: 50-Tests/ui-design-scenarios.md
source_sha256: 9f71d53a14ce91325066d6751cab56455b58336565bdb774708972b1304959db
source_body_lines:
- 1
- 36
split_on: '2026-10-11'
---

# Gurumoji 研究作業シナリオと受入条件：Gurumoji 研究作業シナリオと受入条件

親索引・状態・確認版：[[50-Tests/30-Interface/ui-design-scenarios/00-Index]]。必要な本文だけを取得する。


# Gurumoji 研究作業シナリオと受入条件

第4稿 0.4 · 2026-10-02 UTC · 確認HEAD `88f5e3e`（0.3文書統合）／ソース基準 `ddc23abe`・実装 `59ebd24`  
これは実装と利用者検証に使う歩行仕様。実際の利用者テスト、現行HEADのブラウザー操作、AT音声確認を実施した結果ではない。

[仕様注釈付きv1](../../../40-Design/ui-design-assets/2026-10-02/prototypes/comparison.md)は8図。[clean v2](../../../40-Design/ui-design-assets/2026-10-02/prototypes/v2/index.html)はS02/S04に関係する1280px／390pxの比較8図＋定義変更後の補助2図。密度比較はv2を使い、開発条件は[画面外凡例](../../../40-Design/ui-design-assets/2026-10-02/prototypes/v2/outside-legend.md)へ分ける。[独立批評](../../ui-design-evidence/2026-10-02/mockup-critique.md)の初回／修正後レビューは同じ案の反復で、独立した評価件数として足さない。いずれも全長の静止図で、操作・保存・復帰の合格証拠ではない。規則・根拠数・対象数は各fixtureと照合する。

## 共通の実施条件

合成発話・合成音声・一時DB／Vault・stub providerを使用し、実研究データ／外部AI／追加モデルを必要としない。研究者役のタスク文にはボタン名や正解経路を入れず、操作可能性の自動試験ではrole／labelから通常操作する。初期fixture・遅延・失敗responseの注入は可。測定対象のclick／入力／visibility／navigationを内部state代入で代用しない。

記録はシナリオごとにcommit、環境、ブラウザー、viewport／拡大、合成fixture ID、経路、観測、API・保存結果、画像を結ぶ。V1 contract、V2 component、V3 browser操作、V4 AT、V5利用者理解を分け、passed／failed／not-runを明記する。画像だけ、JS clickだけ、説明できそうというエージェント判断だけで上位層を合格にしない。

まず1440px、390px、境界959/960px。該当箇所は320 CSS px相当、200%文字拡大、400%相当reflowも確認する。キーボードのみ、reduced-motion、Windows日本語font／IMEとATは独立条件。環境がない条件は未実施で残す。

## S01 個別の分析を見つけて実行する

**研究者の仕事:** 保存済みの会話にテーマ分析を追加し、何をどこへ送るか確認して開始する。別ケースでAI見解と発話分類も行う。

**入力:** 保存済み・dirtyなしの会話A、未実行／保存済み旧run／実行中の各fixture。provider未設定、モデル未取得、適格stubの3条件。対応: DG-01、W01、UX:K02/UX:K03。

1. データ一覧で会話Aを開き、画面の通常の案内から分析へ移る
2. 目的に対応する入口を見つけ、対象・処理・送信先・現在の条件を確認する
3. 条件不足なら理由と設定入口を確認し、中止する。適格条件では開始する
4. 連続して開始を押す。処理中に別画面へ移り、同じ分析の状態へ戻る。中止は取消対応のあるTransformer／AI見解で行い、分類の取消能力を装わない。分類Aの応答を遅延させてBへ移る分岐も別に試す
5. 保存済み結果を開く。この閲覧だけでは再実行しない

**受入:** 3入口がproduction CSS適用後に見えて通常pointer／Tabで操作可能。AI見解の案内先が実panel位置と一致。正しいAPI／item／providerが1回、dirty時は適切に止まる。取消対応のあるcontrolは実running状態で可視。分類Aの遅延応答がBのstate／成功通知を変更しないことを照合する。基礎分析のみを実行して個別分析が済んだように表示しない。

**送信内容の照合:** AI見解の合成prompt captureで、発話、話者識別子／名前／役割、研究目的、コードID／label、重要フラグと、expert時の短い説明・許可手順情報を説明文へ対応付ける。除外発話や空本文を省く条件と、単なる画面filterを混同しない。LM Studioを含む実際の設定接続先を示し、閲覧端末内の処理とは断定しない。全文の研究ノート・文献・音声まで送るとは補完しない。[独立契約確認](../../ui-design-evidence/2026-10-02/microcopy-contract-review.md)はcall引数の合成捕捉であり、外部AI接続試験ではない。

**理解の問い:** 「今回実行した処理と送信先は何ですか」「保存済みの結果を見るだけで新しい処理は走りましたか」。正しく説明できたか、どこで迷ったかを記録する。

**失敗時:** 入口が非表示ならV3失敗。JSでbuttonを押せることを代替合格にしない。stub成功を実モデル品質・外部サービス接続成功と呼ばない。
