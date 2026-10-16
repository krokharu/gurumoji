---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-25
title: コア・ハンドラー・ルーティング再編案：移行時の必須確認
summary: 移行時の必須確認。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 1466
- 1494
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：移行時の必須確認

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 移行時の必須確認

### Blueprint、HTTP、配信

`app.url_map`のURL一致だけでは不十分。Blueprint移行でendpointに接頭辞が付く場合は、旧名→新名の対応を明示し、参照するhook・`url_for`・テンプレート等を同じ変更で更新する。endpoint変更自体を一律禁止せず、その利用先が正しく動くことを検証する。

特に`create_job`／`import_speaker_registry`を移す際は、次を必須とする。

- CSV・メディア・JSONのサイズ上限と413応答。
- 同じsubmission IDの再送と別要求の同時受付、受付中の202／409。
- 失敗時の受付予約・一時ファイル解放とthread開始失敗時の後始末。
- Host、Origin、CSRF、リモート認証、ローカルパス制限、応答の機密パス除去。
- `after_request`の予約解除、cache制御、セキュリティheader。

共通hookは維持し、ルート移動を理由に各Blueprintへ複製しない。static／templateの基準パス、ダウンロードのMIME・filename、メディア配信を移す場合のRange応答も確認する。

### 保存・同時実行・回復

- 書き込み経路は1つに切り替える。旧入口を残す場合も同じ実装へ委譲し、旧新の二重書き込み・影実行は行わない。
- UUID・現在時刻を含む結果全体を無条件にsnapshot比較しない。必要なら時刻・ID生成を固定し、決定的な入力のcanonical bytes／hash、重要なschema・状態・副作用を比較する。
- fixtureは一時ディレクトリ・架空データを使う。複数接続・再起動・ファイル回復の試験には一時ファイルSQLiteを使い、`:memory:`だけで代用しない。
- 既存コードの潜在不具合を現状維持の名目で追加固定しない。発見した不具合は再編と切り分け、意図した契約を決めてから後続の基準へ反映する。

### 差し戻しと中断

構造再編の各変更はDB schema・永続payload・ID生成規則を変えず、前のコードでも成果物を読めることを維持する。AI／FLOWの版付き拡張は別変更とし、新コードが旧runを読めることと、未対応種別の実行・再保存を拒否することを検証する。拡張前にreader／writerの対応版検査と差し戻し先を定め、検査のない旧版で新形式を含むDBを開かない。新形式が読めない差し戻し先しかなければ運用を停止して成果物を保持し、旧形式への破壊的変換はしない。失敗した段階はそのコード変更だけを戻せる大きさにする。実行中ジョブを新旧コード間で引き継ぐ仕組みは追加せず、更新・差し戻しは処理停止後に行う。

差し戻しにデータ移行が必要になった時点で、この再編の範囲を超えているため変更を分割する。既存の未コミット変更に対する一括resetや、Vault・DBを消す復旧は行わない。
