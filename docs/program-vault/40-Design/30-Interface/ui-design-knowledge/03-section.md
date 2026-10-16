---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-knowledge-section-03
title: Gurumoji 設計知識の入口：現行実装の読み違いを防ぐ
summary: 現行実装の読み違いを防ぐ。出典ノート「Gurumoji 設計知識の入口」の分割本文。
parent_note_id: design-ui-knowledge
source_path: 40-Design/ui-design-knowledge.md
source_sha256: 91d434fb547e4d56ecae2bd1c1b0f471f816a06c2e275bfe5735e8440a809428
source_body_lines:
- 62
- 79
split_on: '2026-10-11'
---

# Gurumoji 設計知識の入口：現行実装の読み違いを防ぐ

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-knowledge/00-Index]]。必要な本文だけを取得する。

## 現行実装の読み違いを防ぐ

- 原25件は15 addressed／10 UI partial。UI partialは実装なしの意味ではない
- 新監査14項目を14新規bugと数えない。DG-04は既知、DG-05/06/12/14等は提案・仮説を含む
- M0〜M7はサーバー永続実装済み。大きい設計書の47成果物／全役割／全統計が実装済みという意味ではない
- 分類はTransformer／見解と同じ取消能力を確認できていない。可視入口の復旧前に、Aの遅延応答がBへ入らないitem／revisionのgateが必要。固定viewerと定義snapshotの保存／旧worker互換は[計画](../ui-design-implementation-plan/00-Index.md)W02/W04の提案契約を読む
- 個別分析のhidden buttonをJS clickできても、人の実行入口がある証拠ではない。production CSSなしのfixtureはCSS非表示を発見できない
- 手動定義は同じIDのdraft保存でも旧採用行を置換する。受付bindingのversionがあるだけでは実計算の版固定を証明できず、現行_runは最新IDを再読する。UIレビューと実行境界の版保証は別課題
- 失敗pipelineから通常workspaceへ戻れる。『完全に閉じ込められる』『全結果消失』は確認できていない
- failedのallowed_actionsは空で、現行の「再試行」reviewは設定を開く。retry endpointに一切能力がないという意味ではない。文言をhandlerと一致させる
- VaultのAPI target／台帳は3先だが、非空ならResearch込み4経路を試みる。inputのみでも他2先をnot_selectedと記録しながら処理へ入り、Research conflictでもcompletedになる[合成確認](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)がある。実Vault書込み／GUI再現ではない。W03のscope／outcome対策が必要で、旧completedの意味は書き換えない。publishedもmissing保護による未再作成を含み得る
- publication OFFはそのpipelineのVault工程だけを止める。個別AI見解の自動archive等も止まる全体設定ではない。AI見解の送信説明は役割・コード・重要フラグ、expert時の短い説明／許可手順まで含める。閲覧端末と実接続先は同一とは限らない
- 履歴は直近100件の発見性の問題。元DBや既知IDの成果物が削除されたわけではない
- 低contrastの指定色は用途とcascadeで評価する。dropは白背景3.128:1、registry未保存は約2.63〜2.76、sidebar未保存は約5.99の反例
- 相互作用select2つのname不足は確認。memoはplaceholder fallbackがあり得るため『AT名が必ず空』とは書かない
- 旧4b311df画像、現行ソース、隔離probe、現行GUI、利用者評価を同じ証拠欄に混ぜない
- clean v2のMC-02〜06は可視情報を補い、MC-01は試行版／失効表示を補強した段階。状態遷移とserver保証は未検証。MC-07のdisabled／mobile現在地も実UIで確認する。静止図の文字欠けなしをV1〜V5合格へ繰り上げない
