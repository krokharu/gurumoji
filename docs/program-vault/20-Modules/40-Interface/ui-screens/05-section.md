---
note_type: reference-section
status: current
feature: web-ui
verified: 2026-10-03
verification_scope: source-and-synthetic-handler-tests
updated: 2026-10-06
tags:
- gurumoji/program
- gurumoji/ui
note_id: program-ui-screens-section-05
title: Web UIの画面構成と既存機能の対応：保存済み自律分析の履歴・スライド（2026-10-04追加）
summary: 保存済み自律分析の履歴・スライド（2026-10-04追加）。出典ノート「Web UIの画面構成と既存機能の対応」の分割本文。
parent_note_id: program-ui-screens
source_path: 20-Modules/ui-screens.md
source_sha256: 848211ee88b8d60b2d3753a083c1936dd3ec29cdcf0f077c6bb1ea295598d8d9
source_body_lines:
- 98
- 115
split_on: '2026-10-11'
---

# Web UIの画面構成と既存機能の対応：保存済み自律分析の履歴・スライド（2026-10-04追加）

親索引・状態・確認版：[[20-Modules/40-Interface/ui-screens/00-Index]]。必要な本文だけを取得する。

## 保存済み自律分析の履歴・スライド（2026-10-04追加）

分析画面と自律分析dialogの「分析の履歴と根拠」が専用read-only viewerを開く。会話内run、初期/最新/過去のラベル版、時系列フィルター、保存結果・Core判断・採否・固定原文を同じ文脈で表示する。`static/analysis-history.js/.css`、`templates/views/analysis-history.html`、`services/analysis_history.py`が担当する。

「スライド」は別の明示保存操作を持つ。設計確認→VisualizationVaultへの設計/prompt保存→固定版プレビュー→編集可能PPTXの順。閲覧では保存・AI呼出しを行わない。`services/analysis_slides.py`、`analysis_slide_templates.py`、`web/analysis_slides_routes.py`へ接続する。詳しい境界は[[40-Design/10-Analysis/analysis-history-viewer|analysis-history-viewer]]。

## 2026-10-06 文字起こし原文・AI修正・手動修正の履歴確認

確認対象はWindowsの`main`、HEAD `75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`と既存の未コミット変更を含む作業ツリー。実データ・実Vaultを編集せず、一時DB・合成発話で確認した。今回アプリコードの修正は行っていない。

- **原文:** `job_runner.py`がAI前の`imported_transcript`を保存へ渡し、`library_store.py`は`original_segments_json`を更新時に置換しない。旧データの`migrated_current_snapshot`は移行時点の本文であり、AI前原文を復元したものではない。
- **保存版:** `transcript_preparation.capture`が本文・話者・会話設定の変更前後を`transcript_versions`へ蓄積する。同一hashは新しい版を作らない。合成API試験で「原文（別保存）→AI修正を想定した初回本文→手動修正1→手動修正2」を確認し、手動保存ごとの学習差分も各1件残った。未保存の入力操作の全履歴ではない。
- **AI:** 通常処理の最終本文と修正情報は保存され、Obsidian仕上げではrun別の結果JSON・結果ノートと反映後の`ai_finishing`固定保存がある。ただし通常処理の全中間版を個別に保存する仕組みではない。保存版の`origin`は`initial_import`／`saved`等で、AI／手動・編集者の統一した分類はない。
- **画面:** 現在本文、`ai_review.fragments`がある発話の「修正理由と原文」、分析の準備欄の取込本文、原本・全入力版・確認履歴JSON、固定保存欄のAI仕上げrunと成果物リンクは実装済み。原文・AI・手動の全版を発話単位で時系列比較する統合履歴UIは未実装。
- **検証:** `test_transcript_preparation`／`test_ai_finishing`／`test_obsidian_finishing`は68件中67成功・ブラウザー1件未実施。そのブラウザー試験を別途有効化すると1360×900・390×844とも準備記録の保存・再表示は成功したが、共通の初期化例外により全体は失敗。編集・保存のNode DOM試験27件も同例外で失敗した。
- **現在のUI障害:** `templates/views/analysis-orchestration.html`の13,689 bytesがすべてNULで、`bindAnalysisOrchestration`が欠落した`orchestration-role-overrides`に対して`append`し、`analysis-orchestration.js:441`で例外になる。既存変更の破損を確認した段階で、復元・上書きは未実施。現在版のUI全体を正常とは判定しない。

検証証拠はローカル`output/transcript-history-audit-20261006/{summary,browser-diagnostics}.json`。次の作業は、破損テンプレートの復旧、保存版の修正種別・編集者の来歴設計、既存履歴を使う統合比較UIの実装と実ブラウザー受入。実AI・音声認識の再実行、利用者の既存DBの全件監査は未実施。
