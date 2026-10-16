---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-microcopy-state-catalog-section-04
title: Gurumoji 日本語UI文言と状態の仕様案：可視入口の別ゲート
summary: 可視入口の別ゲート。出典ノート「Gurumoji 日本語UI文言と状態の仕様案」の分割本文。
parent_note_id: design-ui-microcopy-state-catalog
source_path: 40-Design/ui-microcopy-state-catalog.md
source_sha256: a380e655813a51346e817cb6f36f5fea46e2e56045e8019aa10d9ef5c0b64d29
source_body_lines:
- 107
- 142
split_on: '2026-10-11'
---

# Gurumoji 日本語UI文言と状態の仕様案：可視入口の別ゲート

親索引・状態・確認版：[[40-Design/30-Interface/ui-microcopy-state-catalog/00-Index]]。必要な本文だけを取得する。

### 可視入口の別ゲート

現行`templates/index.html:236`は「Transformerテーマ分析とAI見解は『内容・文脈検索』から個別に実行」と案内するが、`static/style.css:2088–2093`は該当controlを隠している。W01で通常pointer・keyboardから到達できるまで、この文は「実行可能」の案内として受け入れない。暫定表示は「この画面の基礎集計には、Transformerテーマ分析・AI見解は含まれません」。個別入口の場所は実際の可視導線を確認してから足す。能力不足・モデル未準備・画面の入口不足は別の理由として表示する。

## 5 保存と確認を過剰に保証しない

### 採用とレビュー

採用状態は現行DBに保存されるが、**誰かが個票を読んだ事実の永続保証ではない**。`analysis_pipeline.py:227–256`はstatusとrevisionを保存し、`trial_definition:258–280`は件数・値・入力hashを返す。試行IDと定義版と確認者を結んだgateはない。画面のチェックを付けたことだけで「研究者確認済み」と表示しない。

当面、確認操作が実装された後でも「この画面で試行値を確認」に限定する。確認を保存する機能がなければ再読込後の確認済み表示を出さない。記録がないと確かめた場合だけ「確認記録なし」、読取失敗なら「確認記録を確認できません」とする。既存の発話準備記録にある本文・音声確認（`static/app.js:7509,7586–7595`）は別の対象の記録であり、測定定義レビューへ流用しない。生成Vaultノートに付く`review_status="unreviewed"`（`analysis_store.py:613,624`）も初期ラベルであり、人がこの試行を確認した記録とは異なる。

### 版と固定結果

`analysis_store.py:400–426`は固定ファイルの上書きを拒否し、`304–312`は読取時のhashを照合する。一方、同IDの定義はdraft保存でも更新され、`analysis_pipeline.py:640–643`は実行時に現行定義を読み直す。従って次を分ける。

- 言える範囲: 「この実行で保存した結果」「保存時の入力{版}」など、取得できた実際のmetadata
- 条件付き: 「この定義で実行」には受付内容の固定、または不一致時の安全停止が必要。提案の採用後も対応fixtureで確認する
- 言えない範囲: 「採用版は永久に変わりません」「確認済み定義で必ず実行」「記録は改ざんできません」「いつでも同じ画面に戻れます」

変更防止と変更検知、保存byteの一致と計算意味の一致を混同しない。旧runで版の対応を確かめられない場合は「測定定義の版を確認できません」と表示し、現在の定義で来歴を補完しない。

### 保存先ごとの書式

1つの総合成功色で処理を終わらせず、取得できた対象ごとに「結果ファイル：保存済み」「ResearchVault：保存済み」「InputVault：未完了」のように名詞を付ける。pipelineの`publication_targets`と`publications`はInput／Orchestrator／Visualizationの3先だが、実処理の`publish_result`は`store.publish`へ結ばれ、ResearchVaultも書き出す。archiveの`vault_status`はResearchVaultを表す。3先の配列を全保存先一覧とみなさない。

現行はResearchVaultの例外を`vault_status=conflict`として返し、pipelineは3先のoutcomesを判定する（`app.py:1578`、`analysis_pipeline.py:504–508,620–631,737–750`、`analysis_store.py:588–697`）。独立した[合成契約probe](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)は元のM0〜M7処理と元の`store.publish`を合成adapterで使い、3先published／ResearchVault conflictでも全体completedになる組合せを再現した。これは実Vault・GUIの成功や障害発生を検証したものではない。W03で全体完了を4先成功へ読み替えない。

同probeではinputだけを指定しても4保存経路のattemptがあり、管理表上は残る2先がnot_selectedになる。現UIのcheckboxは3先一括のため、これは狭い保存先選択を追加する際の契約上の留保。現在のpublisherを変えずに「選んだVaultだけに保存」「失敗したVaultだけ再試行」と約束しない。

checkbox OFFは`publish=False`で本体を保存し、Vault工程を対象外にする（`analysis_pipeline.py:476–482,583–588`）。probeのこのケースはpublication記録が3先not_selected、ResearchVaultの`vault_status`はpending、保存経路attemptは0だった。したがってこの実行に対するResearchVaultは「対象外」と表示し、pendingだけで未完了の警告を出さない。既存のVaultファイルを削除する操作ではない。このcheckboxは基礎pipelineの設定で、AI見解成功時の自動archive等を含むアプリ全体のVault保存停止ではない。

結果ファイルが保存済みで再試行可能と分かる場合だけ「結果ファイルは保存済みです。Vaultへの保存を再試行できます」。どのVaultが失敗したかは別行に出し、操作の対象がそこだけとは示さない。不明なら「{Vault名}への保存結果を確認できません」。保存先フォルダー、実行環境、閲覧端末のダウンロードを必要時に示す。利用者の手元のObsidianへ到達できることまで保証しない。

生成ノートの`published`は「すべてのノートが存在する」という保証でもない。研究者が削除したノートを再作成しない所有権保護があり、missingを尊重した結果でも保存先全体がpublishedになり得る（[独立契約確認](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md) §2）。現行`vaultNotesMessage`の「削除されていたノート{n}件は作り直していません」（`static/analysis-storage.js:122–129`）を完了要約から落とさない。例は「保存処理が完了しました。削除済みのノート2件は再作成していません」。この注意を新たな失敗や無断復旧の要求へ変えない。
