---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-07
title: Web UI デザイン・UX 問題点一覧：推奨する対応順
summary: 推奨する対応順。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 90
- 116
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：推奨する対応順

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。

## 推奨する対応順

追加調査では未保存変更の消失につながるUX-30をP0に追加した。最新の順序は [[40-Design/50-Governance/convergence-plan/03-section#追加調査と対応順（2026-09-14）|convergence-plan#追加調査と対応順（2026-09-14）]]。以下は前回29件に対する選別。

1. P1：誤操作・設定消失の防止（UX-11、UX-12、UX-14）と、読める・キーボードで操作できる状態（UX-17、UX-23、UX-24）。
2. P2：用語・重複ナビ・主作業の配置（UX-04、UX-03、UX-06、UX-07）、起動待ちの短縮（UX-08）、モバイル設定導線（UX-10）、URLへの反映（UX-01）。UX-01は未保存確認と履歴の整合も含むため独立した変更にする。
3. その他16件は保留。結果画面全体のタブ分割やCSS全体の共通化を、上記の修正の前提にしない。再開条件は選別欄と [[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]] に従う。

## 更新ルール

- 項目に対応したら、表の該当行に「対応：commit／ADR／ノートへのリンク」を追記する。削除せず、`~~打ち消し~~` で残す。
- UIの導線を変えたときは、[[40-Design/50-Governance/program-vault-rules|program-vault-rules]] の「UI導線」の行に従い、[[20-Modules/10-Inventory/module-map/00-Index|module-map]] のUIの行と、ブラウザーテストも更新する。
- スマホ実機での確認結果（特に横はみ出しの有無）が得られたら、「確認範囲と方法」を更新する。
- 画面をまたぐ入口の重複（UI-01〜03）とアプリ全体の問題は [[40-Design/50-Governance/known-issues/00-Index|known-issues]]、実施順は [[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]] の最新の選別で管理する。

## 追加調査：UI・UX（2026-09-14）

見た目の好みではなく、未保存データの保護、表示対象の一致、保存後に読み返す操作を追加確認した。Node.jsで実際の関数・イベントハンドラーを読み込み、通信・画面部品をスタブ化して分離実行した。追加調査時点では実ブラウザーの描画・フォーカス・スマホ表示は未確認だった。UX-30／31／32はその後、修正時にHeadless Edgeで検証済み。DB境界の確認も含め、調査時点の詳細は [[40-Design/50-Governance/convergence-plan/03-section#追加調査と対応順（2026-09-14）|convergence-plan#追加調査と対応順（2026-09-14）]]。

| ID | 重要度 | 問題 | 根拠・再現状況 | 影響 | 改善案・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-30 | 高 | 移動・再集計の一部で、未保存の分析設定や準備記録の確認を飛ばす | `static/app.js:showView`は処理済みデータ内の移動を確認対象から外し、`showProcessedDataSection`を`force:true`で呼ぶ。再集計ボタンは`analysisState.dirty`だけを確認し、`preparationDirty`を見ずに`discardDirty:true`で再読込する。`loadAnalysisItem`成功時は準備draftとdirtyを初期化。分離実行で、未保存A→Bへの強制移動と準備のみ未保存→再集計が確認0回で進むことを再現 | 操作経路によって、確認した本文・区切り・役割などの未保存記録や分析設定が失われる。会話モードの設定上書き（UX-14）とは別 | 分析設定と準備記録のdirtyを共通の移動・再読込条件に含め、確認済みの操作だけを強制実行する。再集計・上部ナビ・一覧から別会話への移動それぞれで、取消時にdraftが保持されるブラウザーテストを追加 | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P0：最優先 |
| UX-31 | 中 | 一覧でA→Bと続けて開くと、遅いAの応答で表示が戻る | `static/app.js:openLibraryItem`には要求番号・中断・現在の表示意図の照合がなく、応答ごとに`renderResult(data)`を呼ぶ。一覧検索`loadLibrary`と分析取得`loadAnalysisItem`には要求番号がある。通信を遅延させ、B→Aの順で描画関数が呼ばれることを再現 | 最後に選んだ会話と表示中の会話が一致せず、別のデータを編集するきっかけになる。読込待ち中の別画面への移動でも古い応答に注意が必要 | 最後の要求・画面遷移に属する応答だけを反映する。A→Bの逆順応答、および読込待ち中に別画面へ移動したケースで、古い応答が画面を置き換えないことを確認 | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P1：優先 |
| UX-32 | 中 | 比較の集計中に選択を変えると、表示・保存条件が送信時と混ざる | `interview-comparison.js:runComparison`は送信前に会話IDを取るが、応答後の`lastRequest`にはその時点の`allowDifferent.checked`を入れる。`addCategoricalTable`は応答ではなく現在の`selectedInOrder()`で列を作る。`updateSelectionUi`は処理中フラグを見ずに実行ボタンを有効化する。分離実行で送信false→待機中true→保存条件trueと、待機中のボタン再有効化を再現 | 古い結果を新しい選択の列・条件で読む、同時要求で古い結果に戻る、意図しない条件で保存する可能性がある。BUG-02は元データの版変更、本項目はブラウザー内の選択状態が原因 | 送信条件を固定し、結果の列も応答の会話IDから作る。処理中の選択変更を止めるか、選択・要求世代が変わった応答を捨てる。遅延応答と連続操作のテストで表示・保存条件の一致を確認 | 対応済み（[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）\|convergence-plan#優先修正の実装（2026-09-14）]]） | P1：優先 |
| UX-33 | 中 | 比較結果を保存した後の履歴・成果物・Vault再試行への導線がない | `interview-comparison.js:saveComparison`は成功文だけを出し、返ったrun ID・artifacts・Obsidian URIを表示に使わない。比較履歴GET `/api/library/interview-comparison/runs`を呼ぶJSがない。HTTP成功かつ`vault_status=conflict`の応答でも保存ボタンが無効のままになることを分離実行で再現 | 再読み込み後にWeb画面から保存済み比較へ戻れない。「再試行が必要です」と表示されても、同じ画面から実行できない。VaultやAPIを直接使えば保存物は残っているため、データ消失とは区別する | 既存の比較履歴API・成果物URL・Vault再試行APIを比較パネルに接続する。再読み込み後の履歴表示と、正本保存成功／Vault失敗からの再試行を確認。入口の全面集約（UI-01）は不要 | 対応済み（2026-09-20。保存履歴・成果物・Obsidian URI・Vault再試行を比較パネルへ接続し、実ブラウザ回帰を追加） | P1：優先 |
| UX-34 | 低中 | 保存履歴が直近100件に限られることを画面で示さず、古い履歴へ進めない | `AnalysisStore.list/list_comparisons`は`LIMIT 100`固定。`static/analysis-storage.js:refreshAnalysisStorage`は取得件数を「N件の保存履歴」と表示し、ページ切替を持たない。メモリー内SQLiteで101件登録し、両メソッドが100件だけを返すことを確認。直近100件という仕様自体は既存の保存仕様に記載済み | 件数を全保存数と受け取りやすく、101件目以降をWeb履歴から探せない。成果物ファイルは削除されていない。UX-33の比較履歴入口不足とは別の件数境界の問題 | まず「直近100件」と明示。必要に応じて総件数・次ページを返し、過去の実行へ到達できるようにする。101件以上のfixtureで境界と並び順を確認 | 未対応（取得境界再現、ブラウザー未確認） | P2：後続 |
