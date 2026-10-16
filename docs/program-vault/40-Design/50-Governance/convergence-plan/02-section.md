---
note_type: reference-section
status: in-progress
updated: 2026-09-15
tags:
- gurumoji/program
- gurumoji/design
note_id: design-convergence-plan-section-02
title: アプリ収束計画（整理・統合・安全化）：優先修正の実装（2026-09-14）
summary: 優先修正の実装（2026-09-14）。出典ノート「アプリ収束計画（整理・統合・安全化）」の分割本文。
parent_note_id: design-convergence-plan
source_path: 40-Design/convergence-plan.md
source_sha256: b60640ba092a802e2735beeefa7dc160b6c69c609f7930b46554a0d1751d92d6
source_body_lines:
- 29
- 59
split_on: '2026-10-11'
---

# アプリ収束計画（整理・統合・安全化）：優先修正の実装（2026-09-14）

親索引・状態・確認版：[[40-Design/50-Governance/convergence-plan/00-Index]]。必要な本文だけを取得する。

## 優先修正の実装（2026-09-14）

「プログラム関連を修正していって」の依頼に基づき、P0の5件すべてと、同じ経路に関係するP1の4件を修正した。統合扱いのARCH-05、OBS-07も含め、この変更で11行を対応済みにした。ほかの作業によるUI変更とは分けて数える。既存の問題記述・選別記録は履歴として残す。

| 問題ID | 実装した動作 | 検証先 |
| --- | --- | --- |
| BUG-01、ARCH-05 | 比較一覧・集計・保存を既存の`apiFetch`へ統一し、ブラウザーのCSRFヘッダーを送信 | `test_interview_comparison.py`、`test_browser_e2e.py` |
| OBS-01、OBS-07 | 人のテーマノートは読み書きせず、関連一覧を`40-研究/テーマ関連/<hash>.md`へ生成。コメント・独自タグ・改行を保持 | `test_obsidian_layout.py` |
| OBS-02 | 仕上げ同期で全文・アウトライン・操作ノートを再生成しない。最新の参照は概要と状態ノートへ掲載 | `test_obsidian_layout.py`、`test_obsidian_finishing.py` |
| OBS-05 | 管理状態がなく既存の作業ノートがあれば停止。状態ノート以外は完成済み一時ファイルから排他的に新規作成し、同名ファイルの競合でも上書きしない | `test_obsidian_finishing.py` |
| UX-30 | 分析設定・手動コードと準備記録の未保存状態を共通判定し、画面移動・対象変更・再集計の前に確認 | `test_browser_e2e.py` |
| UX-31 | 結果取得の要求番号を照合し、対象変更・画面移動後に届いた古い応答は描画しない | `test_browser_e2e.py` |
| UX-32、BUG-02 | 集計中は比較条件を固定。結果の列と保存条件を送信時の入力へ固定し、保存時に入力版が変わっていれば409で再集計を案内 | `test_interview_comparison.py`、`test_browser_e2e.py` |
| DATA-04 | 準備の追加・更新・削除と同じSQLiteトランザクションで、単独分析と比較履歴を更新待ちにする | `test_vault_coverage.py` |

### 互換性・残っている制約

- 比較保存APIは、集計応答の`input_fingerprints`を必須にした。欠落は400、現在の本文・分析条件・準備・話者台帳との版不一致は409。開きっぱなしの旧画面は再読み込みし、再集計して保存する。
- 人のノートに付けたタグは作成時点のまま保持する。古い全文を自動で`graph/history`へ付け替えない。現在の作業版は概要・状態ノートで確認する。テーマノート内に従来生成した関連欄は自動削除しない。
- 排他的作成には同一ファイルシステムのハードリンクを使う。非対応の保存先では上書きへ切り替えず、エラーで停止する。生成ノート一般のhash確認と置換の間の競合（OBS-04）は別課題として残る。
- 準備の更新待ち伝播は今後の変更から有効。すでに誤った状態で保存された過去履歴の一括補正、実Vaultの移行・削除は実施していない。
- 次のプログラム課題は、生成Vaultの失敗通知（OBS-18）と比較履歴・再試行（UX-33）、watcherの停止表示（OBS-09）。一覧性能（PERF-01）は計測後に扱う。

### 実装の検証

プロジェクトの`.venv/Scripts/python.exe`（Python 3.12.9）で`unittest discover -s tests`相当の全393件が成功（失敗0、エラー0、スキップ0）。`MOJIOKOSI_DATA_DIR`・`MOJIOKOSI_OUTPUT_DIR`を一時フォルダーへ向け、子プロセスにも`PYTHONPATH=src;tests`相当の絶対パスを渡して実行した。一時DB・一時Vaultによる回帰テストと、Headless Edgeで比較の実集計・保存、未保存時の取消、逆順応答を検証した。変更した2つのJSは`node --check`も成功。

初回のシステムPythonでは依存不足、仮想環境の初回では子プロセスへの検索パスの渡し忘れがあったため、上記環境で全件を再実行した。既存の`test_content_browser.py`のAI応答モック2か所は、現在のプロンプトが要求する根拠別名`E0001`に合わせた。実装側の根拠検証は緩めていない。AI呼び出しはモック。実APIの生成品質、GPU認識精度、Obsidian実機表示、モバイル実機、大規模負荷は未検証。

設計判断：[[40-Design/50-Governance/decisions/01-topics/07-section#ADR-109 人のノートを自動更新せず、生成情報の保存先を分ける|decisions#ADR-109 人のノートを自動更新せず、生成情報の保存先を分ける]]。テスト仕様：[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index|obsidian-safety-test-plan]]。
