---
note_type: reference-section
status: in-progress
updated: 2026-09-15
tags:
- gurumoji/program
- gurumoji/design
note_id: design-convergence-plan-section-01
title: アプリ収束計画（整理・統合・安全化）：アプリ収束計画（整理・統合・安全化）
summary: アプリ収束計画（整理・統合・安全化）。出典ノート「アプリ収束計画（整理・統合・安全化）」の分割本文。
parent_note_id: design-convergence-plan
source_path: 40-Design/convergence-plan.md
source_sha256: b60640ba092a802e2735beeefa7dc160b6c69c609f7930b46554a0d1751d92d6
source_body_lines:
- 1
- 28
split_on: '2026-10-11'
---

# アプリ収束計画（整理・統合・安全化）：アプリ収束計画（整理・統合・安全化）

親索引・状態・確認版：[[40-Design/50-Governance/convergence-plan/00-Index]]。必要な本文だけを取得する。


# アプリ収束計画（整理・統合・安全化）

新機能を無計画に追加する段階を終え、既存の機能を整理・統合して1つのアプリとして完成させるための計画。

- **位置づけ：** 優先課題を実装中。最新の実装状態は次節、以降の調査・選別は実装前の記録。
- **根拠：** [[10-Architecture/10-System/system-map/00-Index|system-map]]、[[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]]、[[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]、[[40-Design/50-Governance/known-issues/00-Index|known-issues]]。

## プッシュ済みの対応状況（2026-09-15）

実装の基準は`agent/expand-analysis-ai-workflows`のコミット`1b8fe41`（originへプッシュ済み）。2026-09-15は資料を現状に合わせて更新した。初回の選別・追加調査は履歴として保持し、以下を現在の状態として読む。

| 課題一覧 | 登録数 | 対応済み | 一部対応 | 未対応・保留 |
| --- | --- | --- | --- | --- |
| プログラム全体（known-issues） | 43 | 8 | 1 | 34 |
| UI・UX（ui-ux-issues） | 34 | 14 | 2 | 18 |
| 合計 | 77 | 22 | 3 | 52 |

対応済み22件は、下記の優先修正11件（統合2件を含む）と、先行UI改善11件。課題IDの行数で数え、実装単位の数とは区別する。P0の5件はすべて対応済み。P1／P2／統合／保留は当初の選別で、完了状態ではない。

- プログラム全体の対応済み：BUG-01／02、ARCH-05、OBS-01／02／05／07、DATA-04。
- UI・UXの対応済み：UX-04／06／07／08／10／11／12／14／17／23／24／30／31／32。UX-17は最小`.7rem`の採用範囲で対応済みとし、全利用者の読みやすさを保証する意味ではない。
- 一部対応：UX-03は540px以下の重複ナビを整理。UX-15は開始ボタンのカーソルを修正。残る画面・状態は完了扱いにしない。
- 一部対応だったDOC-03は、この集計後の2026-09-16にルート `AGENTS.md` を追加して対応済みとした。この行の2026-09-15集計には含めない。
- 次のプログラム課題：OBS-18（生成Vaultの失敗通知）、UX-33（比較履歴と再試行）、OBS-09／15（監視停止・操作状態の通知）。OBS-03、DATA-01〜03など、ほかの未対応項目も各一覧に保持する。

全393件成功は`1b8fe41`へ収録した実装の前回検証結果。今回の資料更新ではアプリのテストを再実行していない。作業ツリーに別作業の`tests/test_browser_e2e.py`変更があるため、その変更後のテスト成功を示すものではない。今回は課題77件のID重複・状態集計、追加／変更した内部リンク10件、Vault内のYAMLと54件のnote_id、保存先・API・テスト名を照合した。資料の空白検査も成功。別作業のテストファイルは変更前後のSHA-256が一致している。
