---
note_id: "design-ui-knowledge"
note_type: "knowledge-index"
title: "Gurumoji 設計知識の入口"
summary: "Gurumojiの設計契約・研究・prompt・受入へ必要時だけ進む索引。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
review_repository_head: "88f5e3eea245166ee68ed4dc6c3f99c31e149228"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji 設計知識の入口

第4稿 0.4 · 2026-10-02 UTC · 確認HEAD `88f5e3e`（0.3文書統合）／ソース基準 `ddc23abe`・実装 `59ebd24`  
後続の調査・設計・実装で、必要な根拠だけを読むための索引。全資料の常時読込や、この文書だけによる実装判断を求めない。

source_headは調査時のソース基準版を指す。文書だけのcommitでrepoのHEADが進んでも、アプリの新実装やUI再検証を意味しない。実際のHEADと、[統合検証](../50-Tests/ui-design-evidence/2026-10-02/integration-validation.json)のsource／test hash保全を分けて記録する。ブラウザーへ配信された版との一致や実画面の受入は別途確認する。

## 最初に読むもの

1. [AGENTS.md](../../../AGENTS.md)と実際のHEAD・差分。コードが実装の正本
2. [DESIGN案](ui-design-contract.md)。意図、不変条件、提案を把握
3. 対象のW項目だけ[実装計画](ui-design-implementation-plan.md)で選び、DGの[証拠対応表](../50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md)からコードへ進む
4. 必要な[シナリオ](../50-Tests/ui-design-scenarios.md)と[受入方法](../50-Tests/ui-design-acceptance.md)を読む

## 作業から選ぶ詳細資料

| 今の仕事 | 読む箇所 | 対応する根拠と注意 |
|---|---|---|
| 現行画面と能力を理解 | [監査](../50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md)§2、[独立反証](../50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md)H1/H2 | 上部4入口、M0〜M7永続実装済み。基礎pipelineと個別分析は別 |
| 分析の実行入口を直す | DG-01、W01、S01 | CSS非表示は確認済み。API／保存済み表示の削除ではない |
| 手動測定・試行・採用 | DG-02、W02、S02、[prompt](ui-design-research/2026-10-02/prompt-research.md)T11、[定義版probe](../50-Tests/ui-design-evidence/2026-10-02/definition-lifecycle-probe.json) | 説明は測定命令ではない。既採用上書き・実行時の版ずれも対処 |
| 保存・再分析・版 | DG-03/06/11、W03/04、S03/04、prompt T5 | 計算、保存、Vault、研究者確認は別軸 |
| 根拠から原音へ戻る | W04、S04、[UX](ui-design-research/2026-10-02/ux-research.md)K01/K05/K13、prompt T6 | 入力版・引用・filter・focusの往復契約 |
| 履歴と比較 | DG-04/05、W06/07、S05 | 上限はUX-34既知。古い保存物は消えていない |
| 日本語とaccessibility | W05/08、S06/07、UXの基準表、prompt §8 | 現行描画とATが必要。候補font-sizeはWCAG規定値ではない |
| 見た目の方向を比較 | prompt T2/T3/T8、W07/08、[clean v2](ui-design-assets/2026-10-02/prototypes/v2/index.html) | 同じ内容・状態・幅で比較。静かな緑紙色を出発点に。静止全長図を実viewportと見なさない |
| 小さな既存修正を実装 | prompt T7/T9、対象コードと隣接test | Flask/素のJSを維持。新スタック導入を既定にしない |
| 検証結果を引き継ぐ | prompt T10、受入方法、計画§4/5 | V1〜V5とpassed/failed/not-runを分離 |
| 短い日本語・送信／保存の説明 | [文言仕様](ui-microcopy-state-catalog.md)J01〜25、[独立契約確認](../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md)、W01/03 | handlerの実効果と実payloadへ合わせる。25箇所は新規不具合数ではない |

[レビュー済みの3タスクbrief](ui-design-research/2026-10-02/prompt-workflow-task-briefs.md)はW01/W02/W04の短い再利用入口。[公式参照パターン](ui-design-research/2026-10-02/reference-patterns.md)は根拠往復、提案と適用、再生と選択、出力の省略項目を検討するときだけ読む。公式マニュアル／静止画像／設計推論を実操作の証明と混ぜない。

画面案は、[仕様注釈付きv1](ui-design-assets/2026-10-02/prototypes/comparison.md)の8図と、clean v2の比較8図＋補助状態2図を区別する。開発条件は[画面外凡例](ui-design-assets/2026-10-02/prototypes/v2/outside-legend.md)、可視情報の修正と残留条件は[独立批評](../50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md)の末尾を読む。初回と再レビューの図数を足して評価件数にしない。MCは静止設計案の指摘IDでありDGの現行欠陥数とは別。Aは暫定候補、Bの各要素は利用者検証待ち。着手時の事実／技術gate／選好の区別は実装計画§6に集約する。

prompt T1は現行理解、T4はDESIGN抽出。11テンプレートすべてを一度に付けず、対象フローの1〜2個と必要なコード・受入だけを使う。

## 再利用する判断と出典

出典IDは名前空間付きで書く。`UX:S22`は[UX台帳](ui-design-research/2026-10-02/ux-source-ledger.json)、`PR:R4`は[prompt台帳](ui-design-research/2026-10-02/prompt-source-ledger.json)。`DG-02`は現行コードの問題、`W02`は計画、`S02`はシナリオ。優先度P1とPR:P1を混同しない。

- **根拠へ戻るコストを小さくする:** UX:K01/UX:K05/UX:K13、UX:S04/UX:S06/UX:S17/UX:S20。説明量・採用率・主観的信頼だけを成功指標にしない
- **AI案と人の判断を分ける:** UX:K03/UX:K08、UX:S01/UX:S15/UX:S18/UX:S19。コードブック型とreflexive thematic analysisを同じ品質スコアへ押し込まない
- **意味・単位・分母を先に確かめる:** UX:K09、UX:S09/UX:S10/UX:S17。観測量から参加態度や合意を自動断定しない
- **必要な情報は消さず段階化する:** UX:K02/UX:K10、UX:S11/UX:S13。認知負荷理論は「余白を増やせ」「7個まで」の証明ではない
- **中止・待機・失敗・保存先を区別する:** UX:K11/UX:K12、UX:S12/UX:S26/UX:S31。残り時間や保存保証を根拠なく作らない
- **評価を分けて反復する:** PR:A4/PR:P1/PR:P2/PR:R1〜R4。静的画像一致、通常操作、保存契約、実モデル品質は異なる
- **短い入口と条件付き詳細を持つ:** PR:O3/PR:F2/PR:F3/PR:G4/PR:D1。形式・交換仕様・CSS実値・自動読み込みは別物

## 文献を使うときの重要な限定

訂正の原資料・確認範囲は[独立出典監査](ui-design-research/2026-10-02/source-review.md)を参照。

1. 本調査は体系的レビューでもモデルランキングでもない。公式ベンダーの推奨は製品の使い方の根拠であり、独立した効果量ではない
2. PR:R4のWebGen-Agentは、部分点付きGUIテスト精度26.4%→51.9%を報告。完成サイトの割合ではない。full YESは22.6%→45.6%。改善は評価・選択を含むシステム全体であり、1行のプロンプトの効果ではない。閲覧版はarXiv v1、発表は[ICLR 2026 poster](https://iclr.cc/virtual/2026/poster/10008256)と分ける
3. PR:R5の約20%短縮は成功完了した課題に条件付けた結果。デザイナー群の有意性の記述にも不整合があり、一般的な速度保証へ転用しない
4. UX:S03の信頼度強調は、36名・ドイツ語・短い音声・音声は一度再生してリプレイ不可という利用実験条件でWER改善を検出しなかった。無効果の証明ではない。欠落語除外は信頼度classifier評価に関する制約であり、利用者修正後WERから欠落誤りを除いたという意味ではない
5. UX:S18のCollabCoderは16名・8組、短い書評。日本語の長いグループインタビュー全体へ効果を一般化しない。UX:S02は今回抄録確認まで
6. WCAG本文は規範、Understanding／ARIA APGは解説／パターン。通常文字4.5:1、操作対象は原則24×24 CSS px、例外あり、focus非遮蔽等は個別条件を読む。44pxやFocus AppearanceのAAA面積要件をAAに混ぜない
7. Google DESIGN.mdは取得時alpha、DTCG 2025.10はCommunity Group Report。いずれもこのアプリが自動で従うことや、WCAG適合を保証しない

## 現行実装の読み違いを防ぐ

- 原25件は15 addressed／10 UI partial。UI partialは実装なしの意味ではない
- 新監査14項目を14新規bugと数えない。DG-04は既知、DG-05/06/12/14等は提案・仮説を含む
- M0〜M7はサーバー永続実装済み。大きい設計書の47成果物／全役割／全統計が実装済みという意味ではない
- 分類はTransformer／見解と同じ取消能力を確認できていない。可視入口の復旧前に、Aの遅延応答がBへ入らないitem／revisionのgateが必要。固定viewerと定義snapshotの保存／旧worker互換は[計画](ui-design-implementation-plan.md)W02/W04の提案契約を読む
- 個別分析のhidden buttonをJS clickできても、人の実行入口がある証拠ではない。production CSSなしのfixtureはCSS非表示を発見できない
- 手動定義は同じIDのdraft保存でも旧採用行を置換する。受付bindingのversionがあるだけでは実計算の版固定を証明できず、現行_runは最新IDを再読する。UIレビューと実行境界の版保証は別課題
- 失敗pipelineから通常workspaceへ戻れる。『完全に閉じ込められる』『全結果消失』は確認できていない
- failedのallowed_actionsは空で、現行の「再試行」reviewは設定を開く。retry endpointに一切能力がないという意味ではない。文言をhandlerと一致させる
- VaultのAPI target／台帳は3先だが、非空ならResearch込み4経路を試みる。inputのみでも他2先をnot_selectedと記録しながら処理へ入り、Research conflictでもcompletedになる[合成確認](../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)がある。実Vault書込み／GUI再現ではない。W03のscope／outcome対策が必要で、旧completedの意味は書き換えない。publishedもmissing保護による未再作成を含み得る
- publication OFFはそのpipelineのVault工程だけを止める。個別AI見解の自動archive等も止まる全体設定ではない。AI見解の送信説明は役割・コード・重要フラグ、expert時の短い説明／許可手順まで含める。閲覧端末と実接続先は同一とは限らない
- 履歴は直近100件の発見性の問題。元DBや既知IDの成果物が削除されたわけではない
- 低contrastの指定色は用途とcascadeで評価する。dropは白背景3.128:1、registry未保存は約2.63〜2.76、sidebar未保存は約5.99の反例
- 相互作用select2つのname不足は確認。memoはplaceholder fallbackがあり得るため『AT名が必ず空』とは書かない
- 旧4b311df画像、現行ソース、隔離probe、現行GUI、利用者評価を同じ証拠欄に混ぜない
- clean v2のMC-02〜06は可視情報を補い、MC-01は試行版／失効表示を補強した段階。状態遷移とserver保証は未検証。MC-07のdisabled／mobile現在地も実UIで確認する。静止図の文字欠けなしをV1〜V5合格へ繰り上げない

## 次のエージェントへ渡す最小brief

「対象commit、対象W/DG、改善する研究者の仕事、変更してよいファイル、守る契約、使うシナリオ、必要なV層、成功／失敗／未実施の報告、禁止する実データ・外部送信・公開」を渡す。参考画像は版・状態・幅と参考にする属性を付ける。未確認の能力を成功済みとして補完させない。

記録例: `W02 → DG-02/H3 → definition APIとvalidator → S02のduration対照 → V1成功/V3未実施 → 採用前`。設計が良さそうか、コードがあるか、人が使えるかを別々に追跡できることが目的。

調査・検証はdotで進め、節目だけ既存Software Vaultに決定・commit・証拠・未実施・次の作業を残す。研究者所有ノートを開発記録で上書きしない。

## 保存版と更新先

この索引と設計契約・実装計画はSoftware Vault内を作業用正本とする。日付付き研究・証拠は調査時の保存版。現在の採用版はここから選び、訂正は出典・条件・測定結果を残して新しい日付版へ記録する。図と元検証hashの範囲は[静止案の保存説明](ui-design-assets/2026-10-02/README.md)、コード検証の範囲は[証拠の保存説明](../50-Tests/ui-design-evidence/2026-10-02/README.md)を必要時だけ読む。
