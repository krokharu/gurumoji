---
note_id: design-analysis-history-viewer
note_type: design-contract
title: 保存済み分析・判断・ラベル履歴の閲覧
status: implemented-offline-verified
updated: 2026-10-04
source_head: 1dbd54710e281698fedcd19ab4db001c1db11aac
tags: [gurumoji/design, gurumoji/analysis]
---

# 保存済み分析・判断・ラベル履歴の閲覧

## 目的と境界

会話→自律分析run→初期入力・結果・Core判断・ラベル変更→固定発話を往復する。表示は保存済みの要約、短い判断理由と根拠IDに限定する。非公開の推論過程やprovider内部traceを抽出しない。AI下書き、提案、採用、棄却、保留、競合、失敗を区別する。

既存の編集用注釈は変更しない。自律run内のラベル版だけを管理し、初期版0と過去の版は残す。欠落した過去の担当・時刻・理由を推測して補わず「未記録」とする。監査記録が完全でも研究結果の正しさや研究者の確認を保証しない。

## 読取経路

`AnalysisHistoryService`は実行serviceを起動せず、SQLiteの読取snapshotから投影する。appは`mode=ro`と`query_only`の専用接続を注入し、空DBの作成、schema更新、stale書込み、再計算、モデル呼出し、Vault出力を行わない。

- `GET /api/library/<item>/analysis/orchestration/viewer`: 会話内のrun一覧
- `GET .../<run>/viewer`: 絞込みとページング付き時系列、初期・選択・最新のラベル版
- `GET .../<run>/viewer/entries/<entry>`: 保存された詳細、前後値、関連task/result/decision、根拠
- `GET .../<run>/viewer/sources/<utterance>`: 同じrunの固定原文と選択版のラベル

会話・run・初期snapshot・結果・根拠の所有権と保存hashを照合する。現在の会話本文を古いrunへjoinしない。原音再生は今回の履歴画面には追加せず、固定本文を表示する。ページや長文の上限と省略は表示で明示する。

## ラベル監査

`orchestration_label_audit`を追加する。既存カラムは変更しない。proposalと各dispositionを個別行として追記し、UPDATE/DELETEを拒否する。元のproposal・全ラベル版も保全する。

記録する内容は会話/run、発話ID、項目、操作、提案/採否/競合、実行task/result/decision、提案者のtask/result、担当role/model/provider、UTC時刻、適用前後の版・値・存在有無、保存済み短理由・根拠ID。削除はtombstoneで残し、空値と項目不存在を分ける。

`add`は未設定項目、`update`は既存項目、`delete`は項目自体の除去。codes配列の一要素だけを除く操作は`update`として前後の配列を保存する。モデルは変更を提案するだけで、Coreの採用と元値・版の照合を経てHandlerが適用する。未適用提案を適用済みとして表示しない。

旧proposalは既存の保存状態から読取投影する。監査tableがあるだけで旧runを完全履歴にしない。保存されなかった途中過程・採否時刻・担当は復元できない。旧runの読取は維持し、既存DBへ一括補完や元データ移行は行わない。

## UI

既存分析画面と自律分析の進捗dialogから専用閲覧dialogを開く。run一覧と時系列、詳細を分離する。担当・記録種別・操作・状態・UTC日付、初期/最新/過去の版を選ぶ。根拠・関連結果・判断を同じdialog内で辿る。

会話/run切替、閉じる、再取得、根拠の選び直しでは要求世代を更新し、遅れた応答で別対象の画面や出力リンクを更新しない。本文はtextContentで描画し、HTMLとして解釈しない。会話・結果本文をブラウザー保存やconsoleへ記録しない。

## スライドへの接続

履歴閲覧とスライド設計の保存は別操作。選択runの「スライド」で採用テンプレートと保存先を確認し、明示操作でVisualizationVaultに設計・プロンプト・対象版だけを保存する。その後のpreview/PPTXは保存済みrunから決定的に作り、追加AIを呼ばない。設計・promptの一次資料、選定理由、生成順序は[[40-Design/slide-generation-design-and-prompts]]に記録する。

Software Vaultは開発設計のGit正本で、runtimeからは書かない。生成設計ノートは既存VaultRegistryとノート履歴・削除保護を通す。保存の失敗、ノート削除・編集、snapshot不一致では生成を止める。設計保存が、旧runの4先一括公開権限を拡大することはない。

PPTXのノートには対象run・入力hash・ラベル/結果版・根拠IDとアプリ内参照パスを保存する。相対APIパスはグルモジ内で照合するための参照であり、アプリから離れたPPTXだけで開ける外部URLではない。原発話・結果の省略があれば抜粋として示し、元記録は保持する。PPTX v2は保存データの意味構造に応じ、ネイティブの編集可能テキスト・接続図・棒グラフ・表を使う。認識できない公開field、長文、fit不足は既存の文字投影へ戻し、重大留保の欠落は出力を止める。元の値・参照・完全hashはノートにも保持する。アプリ内原稿編集、PDF出力、複数run混合は初版の対象外。

## 復旧・互換性

新監査schemaは追加のみ。旧ソースへ戻す場合もDBと監査行を消さず、既存のバックアップ・別フォルダー復元の手順を使う。providerへのラベル操作schemaは新adapter版で、旧adapter版の実行中runを新しいpromptで黙って再開しない。旧runの閲覧・固定結果は残る。再開が必要なら元版のcheckoutを保持して使う。

実データ移行、Windows側への自動適用、実AI、実Vault、push/deployは本開発検証に含まない。検証の成功・失敗・未実施は[[60-Operations/dot-cloud-development-handoff]]の対象版を参照する。
