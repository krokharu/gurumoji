---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-10
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-04 追補: 保存runスライドの視覚構成v2'
summary: '2026-10-04 追補: 保存runスライドの視覚構成v2。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 264
- 277
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-04 追補: 保存runスライドの視覚構成v2

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-04 追補: 保存runスライドの視覚構成v2

基点 `e3f002c9d4962769deb1925b8d9859e7f7d2bd73` を保全し、別worktree／`dot/visual-analysis-slides-20261004` で改修。納品manifestのHEADと全ソースhashが実装の正本。元branch、元データ、旧Library版は保全し、push／deploy／Windowsへのアプリコード適用は行っていない。

- 旧15枚の実画像を確認した後、同じ文字列挙の反復と意味の途中での分断を解消。保存runの構造に応じて要旨、分析構成図、根拠と主張の接続図、専門担当、数量棒グラフ、批判とCore応答、統合判断、限界、監査表の9レイアウトへ決定的に投影する。sampleだけの別レンダラーではなくアプリ生成器に実装
- v2設計は31549bytes、SHA256 `9e43d30f386ea99700b5cf009caae1094a2854cf8491eeae9e9303dc05e3775f`。クラウド／PC Software Vaultの保存・再読一致と旧版backupを確認してから新PPTXを生成。採用設計hash・runtimeのrun別設計保存gateを維持
- visualの事前fit検査で、長文、未知の公開field、複合型、値／版の不一致は既存文字投影へ戻す。重大指摘・留保を本体で確認できなければPPTX出力停止。隔離、未実行、未記録、旧版、内容未確認を維持。存在しない一致／対立／ラベル変更履歴を作らない
- 数量は保存count／denominator／proportionが一致する場合のみnative chart。0を保持、多重ラベルを100%へ正規化せず、割合軸は0–100。編集用xlsxを保持。chart軸IDをunsignedへ統一し、embedded workbookの時刻も正規化して同じ保存runからbytes一致を確認
- 匿名合成の日本語見本は11枚、native chart1点、table1点、接続図、画像貼付0。全11枚の実画像と内容／根拠／留保を確認。最終PPTXのSHA256は `1f995f7f75fd8709c2bb60e291b00fd7c28d1b52bba7e555a2694a5f0860f370`。元の英語混在fixtureを日本語の合成fixtureへ改めたため、旧sampleと本文・snapshotが完全同一とは説明しない
- 最終関連テスト59 passed（8 subtests）、新規visual回帰8 passed、全DOM198/198。最終Python全体は1279 passed / 2 failed / 32 skipped / 1107 subtests passed。既知2失敗はtorch未導入のTransformer testsで前版と同じ。成功へ読み替えない。全体試験後に対象code／testのhash差分0を確認
- PPTXはpackage／geometry／EA font指定／native chartとembedded workbook参照／first-party importの検査を通過。描画はartifact-toolであり、Windows PowerPointの実表示と編集操作、実ブラウザー一連操作は未検証。相対API参照は引き続きグルモジ内の照合用

生成器依存は既存python-pptxのまま。追加AI、課金、実会話／実研究Vaultを使う検証は0。source-only ZIP、完全Git bundle、検証資料を別々の20MB未満ファイルにし、別フォルダー復元でsource全hashとbundleのHEAD／tree／fsckを照合する。サンプルのスライド数を固定する契約ではなく、保存内容と安全な分割により実runの枚数は変わる。
