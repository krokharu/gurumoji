---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-16
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-11
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-11: Windows 現行版のコード監査（未修正）'
summary: '2026-10-11の監査履歴と2026-10-16の実装・検証・承認後のローカルDB切替。26項目の到達範囲、品質/採用の未完了、バックアップと復旧制約、別コミット方針を記録。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 278
- 298
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-11: Windows 現行版のコード監査（未修正）

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-11: Windows 現行版のコード監査（未修正）

対象は利用者PCの `C:\Users\kurok\Downloads\mojiokosi\mojiokosi`、branch `krokharu/downloads-latest-reconstruction-private-20261010`、HEAD `47ecd0ae5b0ad2c6dd3b8387f9918c58791eb468`。厳しい問題探索の依頼に対する調査であり、アプリコードの修正・commit・配布・実データ移行は行っていない。既存の未コミット文書と未追跡出力は保持した。

確定7件。優先して直す境界は、同送信IDの永続的な重複検査、バックアップ復元時の保存参照、補正前話者データの保持。

| ID | 優先度 | 合成再現で確認した問題 | 根拠 |
| --- | --- | --- | --- |
| R1 | P1 | TTL/再起動後の同送信ID再送で手編集を上書きし、revisionも増えない。通常UI復帰の保護とは別のAPI条件 | `app.py:381`、`services/library_store.py:217` |
| R2 | P1 | 別dirへのbackup復元後、媒体APIが404。復元側の編集が元環境のJSONへ書き込む | `services/data_backup.py:170`、`services/library_edits.py:239` |
| R3 | P1 | A→B→Aの短い「いいえ」「反対です」等をAへ統合。原文保存にもBが残らない | `services/transcription/segments.py:477`、`job_runner.py:615` |
| R4 | P1 | 同一基点の別発話への独立ラベルpatchを一括採用すると、1件目以外が競合。runはcompleted | `analysis_orchestration.py:1921`、`:1932` |
| R5 | P1 | B読込待ち中にAへ加えた未保存編集が、B応答適用で確認なしに消える | `static/app.js:4193`、`:4879` |
| R6 | P2 | 会話話者CSVが時刻欠測を0秒、片端欠測やtime_unknownを12秒などの値にする | `web/export_routes.py:225`、`:274` |
| R7 | P2 | 任意属性と固定CSV列が同名だとヘッダーが重複し、正式値が属性値に置換される | `services/speaker_registry.py:495`、`:510` |

ソース参照はすべて `src/gurumoji/` 配下。再現条件・期待結果・実際・最小修正案・受入条件は、チェックアウト外の `../artifacts/ui-review/gurumoji-code-review-20261011.json` に保持。古い設計資料のdefinition binding・公開失敗に関する既知2件は現行対策を確認し、所見から除外した。

関連既存試験はPython 66件、DOM 32件成功。独立担当のRuntimeTests 35件、backup 8件、job局所17件も成功（最後の17件は重複を含み単純加算しない）。既存試験の成功は上記の逆境ケースをカバーする証明ではない。pytest未導入はunittestで代替し、DOMはWindows cp932出力失敗後に `PYTHONUTF8=1` で再実行した。Node v22.19.0はDOM packageの宣言対応範囲より古く、正式環境認定ではない。

実runtime・実研究Vault・資格情報・外部APIは不使用。実Whisper/diarization推論、実ブラウザー描画・ネイティブ操作、全体試験は未実行。UIのR5は実HTML/JSとオフラインDOMイベントの再現であり、実画面検証と区別する。初回backup合成検証のTemp1件は削除が自動承認レビューで拒否されて残存（上記JSONに絶対パスと理由、利用者データなし）。次はR1〜R5の保全境界とR6/R7の出力往復を回帰試験にし、個別修正後に隣接統合試験を行う。

## 2026-10-16: 残作業の実装とローカル切替

対象は同じWindowsチェックアウト、基点 `47ecd0ae5b0ad2c6dd3b8387f9918c58791eb468` と段階0〜5の既存編集。今回の26項目の実装済み・部分実装・未完了は [[40-Design/10-Analysis/analysis-immediate-changes-plan|実施計画]] を正本とする。コード・試験と、作業前からのSoftware Vault再編は利用者指示で別コミットに保存する。クラウド反映・push・認証設定変更は行わない。

コード・試験・設定194ファイルのcommitは `86a70d9b6af0828838280a005f8e55927d60a9be`。Software Vault602ファイルと検索/再編/カタログ補助4ファイルは、本ノートを含む別コミットとして組で使用する。コードcommitだけのcheckoutでは移動先の設計文書が揃わないため、両コミットを受け渡す。検証manifestの基点HEADと作業ツリーhashは保持し、commit後も対象ソースhash不変を照合する。

主な追加は遅延話者応答の編集保護、remote JSONのパス除去、CSV属性の可逆化、Q23の内容一致run再利用、型付き保存表の統計とXLSX/SAV/画像、保存履歴と一覧のページング、研究者ノートの原本を保持した差分取込、Vaultルートのcopy-first変更/復旧、外部固定結果の登録、会話横断の全文/既存ベクトル検索。試験基盤を収集前から隔離し、pytest、UTF-8、並列実行、class付き失敗ID、異常終了・未収集・source変更・SQLite直接書込の検出を導入した。

全体証跡は `output/validation/final-current-2/summary.json`（1,781収集、1,748成功・33 skip・失敗0、未収集/runtime変更/source変更0）。同条件の基点1,435件・失敗ID24件と比較した。独立担当の境界点検・復旧/受入ゲート/実行器の点検で指摘を修正し、関連試験を再実行。追加のブラウザー試験とDOM試験は計画の証跡節を参照し、全体件数へ重複加算しない。

最終画面検証は `output/validation/final-browser-confirmed/summary.json` の関連19件（実操作13・API6）、DOMは `dom-final-clean-2.log` の202件が成功。D0〜D7を現行証跡に更新し、研究品質のEVALは未実行のまま。Vaultは834ノート・3,575リンク・907 anchorを確認し、到達不能/エラー0。旧パス2件の移動先anchorを訂正した。runtimeとローカル検証出力はコミットに含めず、記録されたファイルをこのPCで参照する。

実モデルはLM Studioの既存Qwen3-8Bを架空入力のみで起動し、区間・verification・critic・finding_review・notationの5契約が合格。終了後は試験でロードしたモデルを解放した。A5の108試行/人手盲検判定、役割別モデルの研究品質承認、承認済みknowledge packの本番配布、高度会話分析の採用は未実施。stance/JEV8等を利用可能に偽装しない。

実DB切替は最初の自動承認審査で明示承認不足として拒否されたため、その時点では未実行。利用者の「バックアップ後に適用する」の返信後、アプリのロックと差分plan hashを照合し、`runtime/backups/gurumoji-backup-20261016T113625Z`（2,253ファイル、270,191,576B）の検証後に1会話・初期履歴14対象へ適用した。既存列・本文・属性のhash不変、WAL、再dry runで切替残0。派生SQLiteに形態素/係り受け各7,226件を生成し、現在値不変を再確認。証跡は `cutover-{preview,applied,after}.json` と `derived-initialization.json`。

復旧は既存のバックアップ復元経路を使用する。アプリを停止し、指定バックアップの検証を再実行してから復元する。旧コードで差分版へ追記すると履歴不整合を起こし得るため、コードだけを戻して運用せず、計画第16節の接続照合を守る。派生DBは再生成可能。実研究Vault原本は未変更、モデルへ利用者本文は未送信。runtime/出力/資格情報をGitへ追加しない。

同一架空入力の保存比較では版2の総容量571,989B（基点793,106Bより27.9%減）と保存中央値44.90ms（基点31.84msより41.0%増）。容量削減と速度向上を同一視しない。Colab、クラウドCPUでの実推論、Whisper再推論、実研究Vault移動/公開は未実行。

## 2026-10-16: mainへのアプリ統合と開発資料の分離

利用者の「メインに統合」と追加回答「テストコード・データ一式を別ブランチへ」に基づく。統合元は `384759c898fb318c68caaf1156170f98c2024c2f`、mainの基点は `110d4dca5b058a304d733a8b4b2019e96aa5108c`。両者の共通基点は `75ebbb6`。main側の更新はエージェント運用資料・同期プログラムで、アプリ本体の競合はなかった。完全版を `archive/development-assets-20261016` に保存し、既存の私有作業ブランチも保持する。

mainへの統合commitは `e33a91dda2e27a8226190c40c351f243213e20f5`。435ファイル・約5.5MBへ整理し、アプリ本体181ファイルは統合元と同じbytesを維持。mainは起動・保守、Colab、利用手順と実行時資料を収録する。テスト一式、架空データ、開発用コンソール、画面試作、設計計画、ADR、検証記録、エージェント用資料はこの開発資料ブランチへ集約した。ソース履歴の強制書換え・force pushは行わない。

Software Vaultを全削除すると実行時の専門家やスライドが欠けるため、実際のreaderが使う17専門家・206知識/文献ファイルと6スライド定義をmainへ残した。各専門家のknowledge hash、文献・共通知識の欠落0、スライドの全part hashとテンプレート同値を確認。mainのVaultは入口3ノートを含む215ノートの実行用部分集合で、完全な設計・古いリンクの参照先はこのブランチとする。研究者の実Vaultの配置・ID・本文・タグ・別名は変更しない。

検証は統合元の全体1,786件（33 skip）を実行し、新しくmainから入ったエージェント資料同期の1失敗を発見。読み取りスクリプトのコピーを同期し、試験で生成したPython bytecodeを同期元と誤認する問題を除外・回帰試験追加で修正。関連6件成功。他のアプリ試験の失敗は0。新規 `tests/test_main_delivery.py` は別のmain checkoutを明示して7件成功。専門家・統計・固定保存・スライド・Vault等の隣接試験も実行し、最後に残った利用資料の設計リンク1件を別ブランチへ付け替えて引渡し7件を再確認した。

main構成の実ブラウザー関連19件（実操作13・API6）は失敗0。外部に置いたテスト設定がimport先を上書きすることを検出したため、main用設定を別に用意し、実際の `PROJECT_DIRECTORY` がmain checkoutであることを試験で検査した。mainへテスト・試験データをコピーせずに、HTTP応答、型付き表の統計保存、研究ノート取込、履歴・画面操作を確認した。

ローカル証跡は作業元 `output/validation/main-split-manifest.json`、`main-pristine-boundary.xml`、`main-pristine-delivery-final.xml`、`main-pristine-browser.xml` と、開発資料worktreeの `output/validation/main-integration-full/`・`main-integration-agent-assets-final/`。小さな受渡し記録は `../artifacts/main-integration-20261016/summary.json`。mainと開発資料ブランチのpush後はリモートHEADを照合する。

この作業はGit上の引渡し範囲の整理であり、利用者DB・研究者Vault・モデル・認証設定の変更や追加移行は行っていない。前節の研究品質、人手評価、knowledge packの本番採用、高度会話分析の未完了範囲を採用済みへ変更していない。
