---
note_type: reference-section
status: in-progress
updated: 2026-09-15
tags:
- gurumoji/program
- gurumoji/design
note_id: design-convergence-plan-section-07
title: アプリ収束計画（整理・統合・安全化）：K. テスト方法
summary: K. テスト方法。出典ノート「アプリ収束計画（整理・統合・安全化）」の分割本文。
parent_note_id: design-convergence-plan
source_path: 40-Design/convergence-plan.md
source_sha256: b60640ba092a802e2735beeefa7dc160b6c69c609f7930b46554a0d1751d92d6
source_body_lines:
- 279
- 308
split_on: '2026-10-11'
---

# アプリ収束計画（整理・統合・安全化）：K. テスト方法

親索引・状態・確認版：[[40-Design/50-Governance/convergence-plan/00-Index]]。必要な本文だけを取得する。

## K. テスト方法

- **自動テスト：** `PYTHONPATH=src` を設定し、`python -m unittest discover -s tests -p "test_*.py"` を実行する（`docs/PROJECT_LAYOUT.md`）。
- **Obsidianの安全性：** テスト用Vault（fixture）で [[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index|obsidian-safety-test-plan]] のケースを実行する。実際のVault（`runtime/data/obsidian`）は使わない。
- **実機確認：** `MOJIOKOSI_DATA_DIR` を一時フォルダーに向けてアプリを起動する。テスト用Vaultのコピーを Obsidian で開き、編集中の保存・移動・改名・削除を手で確認する。
- **ブラウザー：** `tests/test_browser_e2e.py`（Edge／Chrome）に、比較・保存・削除の導線を追加する。

## 目標とする層構造（書き換えずに寄せる）

| 層 | 責務 | 寄せ先（既存） |
| --- | --- | --- |
| Core | 会話・発話・版・確認状態のルールと、正本の保存 | `app.py` の保存・編集トランザクション、`transcript_preparation.py` |
| Service | 文字起こしパイプライン、分析、AI仕上げ、議事録、比較 | `research_analysis`、`analysis_insights`、`transformer_analysis`、`ai_finishing`、（`app.py` から移す関数） |
| Data | SQLite台帳、固定成果物、出力ファイル | `analysis_store`（成果物）、`app.py` のDB関数 |
| External Integration | Obsidian（全Vault）、AI HTTP、FFmpeg、モデル | `vault_registry`・`obsidian_layout`・`obsidian_finishing`（Obsidian）、`ai_http_worker` |
| UI | 表示と入力。API呼び出しは `apiFetch` だけ | `static/*.js`、`templates/index.html` |

ルール：上の層は下の層を呼ぶが、逆方向には呼ばない。Obsidian層は正本（DB・成果物）を読むだけで、DBを変更するのは Core の保存関数を通す場合（仕上げの反映）だけにする。

## 実施フェーズ

元のPhase 0〜6を順番にすべて実施する計画から、採用した課題に絞る計画へ更新した。保留項目を自動的に後続フェーズへ戻さない。

1. **P0：** BUG-01、OBS-01、OBS-02、OBS-05を小さな変更に分ける。上表の完了条件と [[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index|obsidian-safety-test-plan]] の該当ケースを満たす。
2. **P1：** 既存設定の保全と失敗理由の表示、誤操作対策、削除・復元と削除後の表示、絶対パスと資料の整合、読める・操作できるUIを順に扱う。異なる責務は別変更にする。
3. **P2：** 用語・配置・起動・モバイル設定を局所改善し、URLと履歴は別変更で実装する。OBS-13は次の移行より前に対応する。
4. **再選別：** 実害が再現した項目、利用者の困りごと、移行に必要な項目に限って保留から戻す。全体リファクタリングを完了条件にしない。

コードを変更する際は、関係する回帰テストと必要なブラウザー確認を行い、各問題の実装状態を更新する。下の最終確認は変更範囲に該当する項目を確認し、無関係な項目は理由付きで対象外とする。「削除行数が追加行数を上回る」は完了条件から外す。
