---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-09
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-04 追補: 分析履歴ビューと設計記録後のPPTX'
summary: '2026-10-04 追補: 分析履歴ビューと設計記録後のPPTX。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 234
- 263
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-04 追補: 分析履歴ビューと設計記録後のPPTX

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-04 追補: 分析履歴ビューと設計記録後のPPTX

基点 `1dbd54710e281698fedcd19ab4db001c1db11aac` を維持し、専用 `dot/analysis-history-viewer-20261004` に追加。対象HEADと全ソースhashは配布manifestを正本とする。旧source ZIP・bundle・branch、元DB・原ラベル・研究者ノートを保全した。

### 実装と保存境界

- 専用read-only viewerで会話→run→初期/最新/過去ラベル版→タスク/結果/Core判断/採否→固定原文を辿る。SQLページング、担当・種別・操作・状態・UTC日付filter、詳細と根拠の分割取得を提供
- 表示のために実行serviceを初期化しない。appはSQLite `mode=ro`、query_only、固定read transactionの専用経路を注入する。GETでDDL/stale書込/復旧/再計算/モデル呼出し/Vault出力をしない
- `orchestration_label_audit` は追加schemaと追記専用trigger。実変更前後、proposal申告旧値・新値、採否、actor、task/result/decision、版、理由と根拠を保持。deleteはtombstone。未適用proposalのafterを採用結果と表示しない
- 旧履歴の欠落は未記録のまま。保存値の省略を明示し、破損hash・越境参照は拒否。model schemaは `core-handler-prompts-2-label-audit` へ更新。旧prompt版runは閲覧可能だが新promptで再開せず、旧checkoutを保持して復旧する
- スライドは保存された1runから決定的に作る。追加AI・新解析・現在会話からの補完はしない。既知fieldを日本語で表示し、未知/未検証/隔離を採用見解へ混ぜない
- 設計/promptのSoftware Vault記録hashとcatalogを照合。利用時は明示操作でVisualizationVaultのrun別設計ノートを保存し、読戻し確認後だけpreview/PPTXを許可。既存ノート履歴・削除保護を使い、失敗/編集/削除/対象版変更は出力停止。旧4先一括公開の権限は拡大しない
- 重大な未解決指摘を本編から欠く、根拠欠落/除外/別入力版がある場合は要確認としてPPTXを出さない。表示の継続は状態確認用で、成功扱いしない

### スライド設計の先行記録

Webの一次資料比較から独自の8セクション構成を選定した。[[40-Design/60-Output/slide-generation-design-and-prompts/00-Index|slide-generation-design-and-prompts]] v1.0.0は24994bytes、SHA256 `a3ed14a846b0144a8ed5428637fb8ff21a3bc9f0f3f7147988024895348c0ce8`。クラウドSoftware Vault正本とPC上の利用者指定Software Vaultへ同一UTF-8/LFを新規保存し、双方の再読hash確認を終えてから合成deckを生成した。PC側の既存ノートと`.obsidian`は変更していない。これは設計記録の保存確認であり、アプリコードのPC適用やPC実機での機能確認ではない。

### 検証と利用時の制約

匿名fixtureだけを使用。実Flask/SQLiteと実registryで保存run→設計POST→preview→PPTX→再openを確認し、追加AIなし・DB bytes不変・設計ノート削除時409を検証。追記監査のCRUD/競合/再実行、旧schema、213件履歴、135発話、204ラベル版、遅延応答/ABA/XSS/私有推論fieldの非掲載を含む。

最終Python全体は1271 passed / 2 failed / 32 skipped / 1107 subtests passed。全DOMは198/198成功。独立レビューは19件＋生成8件の27/27成功（既存suiteとの重複を含み、加算しない）。コード/test/configは全体試験中のhash差分0。既知2失敗はtorch未導入、32skipはbrowser/Windowsの未実行。成功に置き換えたりテストを削除したりしていない。詳細は配布verificationの `release-metadata.json` とログを参照。

PPTX sampleはネイティブの編集可能text object、JSON/notesにrun・入力/結果/ラベル版・hash・根拠IDを保持。15ページをLibreOfficeDev 26.8でPDF化し全ページ画像を確認、文字領域外0を照合した。NotoSansCJKsc/NotoSansへの代替描画で、Windows PowerPointのYu Gothic表示は未検証。長文・根拠保留の逆境検証とnative XMLの整合も確認する。相対API参照はグルモジ内照合用で、オフラインPPTXだけで開ける公開URLではない。

クラウドブラウザーで実Flaskのlocalhostページと匿名fixtureを開いたが `ERR_BLOCKED_BY_CLIENT`。トンネル・proxy・許可Origin拡張・sandbox解除で迂回しない。`ui/history-viewer-synthetic.html` は匿名fixtureの操作previewで、実画面受入・実AI結果の証拠ではない。

アプリ内原稿編集とPDF出力は初版対象外。PDFは開発QAの参考出力のみ。必要な新runtime依存は`python-pptx>=1.0.2,<2`、cloud lockは導入済み版を記録。未導入時はpreview可能/PPTX不可を明示する。実AI・実会話・実Vaultへの生成出力、課金、Windowsへのコード反映、push/merge/deployは行っていない。
