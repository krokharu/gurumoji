---
note_type: reference-section
status: current
verified: 2026-09-25
updated: 2026-09-26
tags:
- gurumoji/program
note_id: program-module-map-section-02
title: 機能・コード・テストの対応表：現在の分析API
summary: 現在の分析API。出典ノート「機能・コード・テストの対応表」の分割本文。
parent_note_id: program-module-map
source_path: 20-Modules/module-map.md
source_sha256: 9d4be038e5ca8e5f28209be2d481906c976790670a214ce8b9bc595ce249b386
source_body_lines:
- 33
- 50
split_on: '2026-10-11'
---

# 機能・コード・テストの対応表：現在の分析API

親索引・状態・確認版：[[20-Modules/10-Inventory/module-map/00-Index]]。必要な本文だけを取得する。

| 機能 | 実装・入口 | 主な検証先 |
| --- | --- | --- |
| 保存履歴・Vaultからの発話参照 | `static/analysis-storage.js` | `tests/test_content_browser.py` |
| 分析出力 | `services/group_analysis.py`: `analysis_csv_rows`; `web/export_routes.py`: `export_library_analysis_json` ほか; `research_analysis.py`: `build_analysis_workbook` | `tests/test_analysis.py`, `tests/test_research_analysis.py` |
| 編集差分の学習データ | `services/training_corpus.py`: `training_export_contents`, `write_training_exports`, `refresh_training_exports`; `web/training_routes.py` | `tests/test_backend_safety.py`, `tests/test_outputs.py` |
| UI・分析実行・引用から音声確認（画面構成は [[20-Modules/40-Interface/ui-screens/00-Index\|ui-screens]]） | `templates/index.html`（外枠）と `templates/views/{analysis,create,library,result,speakers}.html`（画面別テンプレート）, `static/app.js`, `static/analysis-visualizations.js`, `static/analysis-method-view.js`, `static/analysis-content.js`, `static/analysis-execution.js`, `static/style.css`, `static/ai-effort.css` | `tests/test_content_browser.py`, `tests/test_browser_e2e.py`, `tests/test_ui_defaults.py` |
| メディアパス・リモートアクセス | `web/security.py`: 認証・CSRF・サイズ上限; `web/library_routes.py`: メディアAPI; `services/media_files.py`; `diagnostics.py`: ローカルパスの非表示 | `tests/test_media_paths.py`, `tests/test_backend_safety.py` |

## 現在の分析API

| 操作 | API |
| --- | --- |
| 分析取得・条件保存 | `GET/PUT /api/library/<id>/analysis` |
| 文脈検索・CSV | `GET /api/library/<id>/analysis/kwic` |
| AI生成・状態 | `POST/GET /api/library/<id>/analysis/insights` |
| AI中止 | `POST /api/library/<id>/analysis/insights/cancel` |
| JSON・Excel・CSV | `GET /api/library/<id>/analysis/export.json`, `export.xlsx`, `export.csv` |

固定保存・履歴・再試行・成果物取得の実装済みAPIは [[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]] に記載します。後続の差分取り込み等の設計は [[40-Design/40-Storage/sync-contract|sync-contract]] を参照してください。
