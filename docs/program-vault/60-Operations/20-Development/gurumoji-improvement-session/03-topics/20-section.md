---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-20
title: Gurumoji 改善セッション：2026-10-11 Windows 現行版の品質評価
summary: 2026-10-11 Windows 現行版の品質評価。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 339
- 356
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：2026-10-11 Windows 現行版の品質評価

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 2026-10-11 Windows 現行版の品質評価

- 対象は `krokharu/downloads-latest-reconstruction-private-20261010` / `47ecd0ae5b0ad2c6dd3b8387f9918c58791eb468`。主要な HTTP 境界、画面の非同期操作、保存・復旧、テストをレビューした。既存の未コミット文書・出力を維持し、アプリのソースは変更しない。
- 総評: 保存の版競合検知、署名付き編集 journal、内容 hash、rollback／再開、固定成果物の検証は丁寧。一方、以下の製品不具合と検証の再現性の問題があり、安定性の受入完了とは扱わない。保守性では `static/app.js` 8,656行、`services/transcription/job_runner.py:18` の実行関数1,085行に責務が集中している。

| 優先度 | 確認済みの製品不具合 | 再現条件・次の修正 |
| --- | --- | --- |
| P1 | 話者再特定の遅延応答が未保存編集を破棄する (`static/app.js:5723`) | 再特定待ち中に本文を編集すると、古い応答の `renderResult` が本文を戻し dirty を解除する。別会話へ移動した後も元の会話へ強制復帰。対象・画面・編集世代の照合が必要 |
| P2 | リモート設定で JSON ダウンロードが失敗する (`web/security.py:215`) | remote 有効／remote local paths 無効で `send_file` の JSON を共通フックが `get_json` し、direct passthrough 例外。ローカル200とリモート例外を実 export route で比較。ダウンロード応答と秘匿処理の境界修正が必要 |
| P2 | 追加属性が CSV 固定列を上書きする (`web/export_routes.py:276`, `services/speaker_registry.py:510`) | 通常の追加属性入力で `発話数=999` を保存すると、実発話1件の CSV に同名2列・両方999。氏名にも同じ問題。固定列との名前衝突防止が必要 |

- Python: 標準の `python -m unittest discover -s tests -p 'test_*.py' -v` は `tests` / `scripts` の同名モジュール衝突で収集停止。`test_local_expert_knowledge` と `test_saved_autonomous_analysis` を tests の実ファイルから明示ロードしてから同じ discover を行う補助ランナーでは **1,426件、成功1,365・失敗2・エラー31・skip28（492.012秒）**。データ／出力／バックアップを一時フォルダーへ隔離し、browser opt-in は無効。これは正式 pytest 全件の受入結果ではない。
- エラー31件は未導入依存10件（python-pptx 3、pypdf 4、googleapiclient 2、pytest import 1）と、一時 DB の終了漏れによる Windows cleanup エラー21件。失敗2件は `test_history_slide_review.py:242` の旧 adapter 版固定と、Drive依存不足が `drive_not_authorized` ではなく `unreachable` になる期待値不一致。本番の DB 接続は finally close を備え、今回の21件を本番の接続リークと同一視しない。代表 fixture の close 補正、版期待だけの一時 mock、Drive認可境界の一時 mock で各対象1件の成功を確認したが、元 suite の失敗結果は保持する。
- `pytest` 未導入で正式 pytest suite は未実行。関数形式の candidate pipeline 7件と runtime scheduler 3件は unittest の成功件数に含めない。`pip check` は成功したが、`config/requirements.txt` と照合すると `pypdf` と `python-pptx` が不足しており、全宣言依存の充足を意味しない。
- JavaScript: `node --test` で既存の `tests/test_*.cjs` と `tests/ui/*.test.cjs` **45件成功**。オフライン DOM は project Python と `PYTHONUTF8=1` を指定して **200件成功**。UTF-8指定なしは `tests/dom/render_fixture.py:8` の cp932 出力エラーで17ファイル起動失敗。Node 22.19.0 は DOM package の要求最低22.22.2未満のため、この成功は現環境での参考結果とする。既存200件が成功しても上記の再特定競合は別 probe で再現する。
- バックアップの別パス復元は、メディア同梱・検証成功でも DB の元の絶対パス参照を保持し、音声 URL が得られないことを一時データで確認。ただし [[60-Operations/10-Data/backup-restore|backup-restore]] は元パス復元を契約としており、新規不具合ではなく移設の制約とする。
- 検証は合成データ・一時 DB/Vault・Flask test client・オフライン DOM の範囲。利用者の原本DB・個人Vault・秘密値を評価入力にせず、実推論、外部API、実ブラウザー操作、音声認識／話者分離／AI分析の内容精度、公開・移行・commit/pushは未実行。次は P1 の操作競合、2件の書き出し、テストの import／close／版期待・依存の順に整備する。
- 一時証跡: `%TEMP%/gurumoji-quality-704a3a4a7d4a4a10bcf0c64ee7e69627` の Python／JSログ、`%TEMP%/gurumoji-quality-js-20261011` の再特定競合 probe、`%TEMP%/gurumoji-quality-backend-d5fcd85c035645b6946ec6d188032a34` の書き出し probe と原因分類。これらは一時成果物であり恒久保存や別環境共有はしていない。
