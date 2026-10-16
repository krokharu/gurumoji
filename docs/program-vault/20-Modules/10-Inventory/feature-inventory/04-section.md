---
note_type: reference-section
status: current
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/features
note_id: program-feature-inventory-section-04
title: 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Duplicate：目的が重なる機能と、併存の理由
summary: Duplicate：目的が重なる機能と、併存の理由。出典ノート「機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）」の分割本文。
parent_note_id: program-feature-inventory
source_path: 20-Modules/feature-inventory.md
source_sha256: 452c464c3fa60e7f2a4cc230a48433daf715bc2dd5508dc9ea8a77ac12a373e4
source_body_lines:
- 74
- 89
split_on: '2026-10-11'
---

# 機能一覧と分類（Core／Supporting／Optional／Duplicate／Legacy／Experimental／Unknown）：Duplicate：目的が重なる機能と、併存の理由

親索引・状態・確認版：[[20-Modules/10-Inventory/feature-inventory/00-Index]]。必要な本文だけを取得する。

## Duplicate：目的が重なる機能と、併存の理由

| 重複 | 併存している理由（推定を含む） | 収束の方向 |
| --- | --- | --- |
| AI仕上げ：アプリ内ジョブ／Obsidian作業台 | Obsidian方式を既定にした後も、API互換（`finish_in_obsidian=0`）とテストのためにジョブ内の経路が残った | Obsidian方式を正にする。ジョブ内の経路は「おすすめ」「高度」モードが使うため残す。校正の手順（全体アウトライン → 全文校正 → Jev比較）は `services/ai/transcript_finishing.run_full_cleanup` に共通化済み（2026-09-25、ARCH-07） |
| 話者特定：ジョブ／作業画面の再特定／仕上げのオプション | 機能を追加するたびに入口が増えた | 実装は `detect_speaker_names_with_ai` の1つ。UIの入口を整理する |
| 議事録Markdown：`format_meeting_minutes_markdown`（出力・API）／`meeting_minutes_note`（Obsidian） | Obsidian用にリンク付きの形式を別途作った | 同じ中間データからレンダラーを2つ作る形に整理する |
| 議事録のVault出力：作業台の会議ノート（`I###-会議議事録-*.md`）／固定保存の実行（`meeting_minutes` run） | 閲覧用と、再現用の固定保存を分けた | ノートの役割をドキュメントに明記し、ナビでは一方へ誘導する |
| 文字起こし保存API：`PUT /api/jobs/<id>/transcript`／`PUT /api/library/<id>` | ジョブ完了直後の保存と、ライブラリからの保存 | 内部の実装は共通。APIは互換として残す |
| ダウンロードAPI：`/api/jobs/<id>/files/…`／`/api/library/<id>/files/…` | 同上 | 同上 |
| 分析のCSV：都度エクスポート／固定保存の成果物 | 「今の値」と「再現用に固定した値」 | UIの文言で区別する |
| Vaultノートの台帳：SQLite `obsidian_notes`／`interviews.json`／`vaults.json`／`state.json` | モジュールごとに段階的に追加された | 書き込みの判定を共通化する（OBS-04） |
| Frontmatterの生成・解析 | 同上 | 1組に統合する（OBS-06） |
| 原子的書き込み関数 | `analysis_store` と `app.py` で個別に実装した | 1つに統合する（ARCH-04） |
| AI入力の分割：`analysis_insights.bounded_batches`／`ai_finishing.fragments` | 用途ごとに実装した | 未使用だった `chunk_segments` は2026-09-26に削除（ARCH-06） |
