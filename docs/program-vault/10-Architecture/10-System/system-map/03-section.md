---
note_type: reference-section
status: current
feature: architecture
verified: 2026-09-14
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/architecture
note_id: program-system-map-section-03
title: システム全体構造・データフロー・設定の所在：保存先
summary: 保存先。出典ノート「システム全体構造・データフロー・設定の所在」の分割本文。
parent_note_id: program-system-map
source_path: 10-Architecture/system-map.md
source_sha256: b51430e47959bba035a47fefde19f5942b7014f183c331b6cecd7d7207d6ea14
source_body_lines:
- 127
- 145
split_on: '2026-10-11'
---

# システム全体構造・データフロー・設定の所在：保存先

親索引・状態・確認版：[[10-Architecture/10-System/system-map/00-Index]]。必要な本文だけを取得する。

## 保存先

| 場所 | 内容 | 決め方 |
| --- | --- | --- |
| `<data>` | `runtime/data`、または `MOJIOKOSI_DATA_DIR` | `app.py`: `DATA_DIRECTORY` |
| `<data>/library.sqlite3` | 会話・話者台帳・分析条件・AI要求・固定保存台帳・Obsidianノート台帳・逐語録の版と準備 | `DATABASE_FILE` |
| `<data>/media`, `thumbnails`, `kushinada_training`, `custom_vocabulary.json` | 元メディア、再生成物、学習データ、単語登録 | `app.py` の定数 |
| `<data>/analysis_store` | 不変の入力スナップショット・結果・表CSV・manifest | `AnalysisStore.root` |
| `<data>/obsidian/ResearchVault` | 研究者が読むノート・仕上げ作業台 | `ObsidianLayout`、`ObsidianWorkbench`、`AnalysisStore` の3か所で個別に算出 |
| `<data>/obsidian/{InputVault,VisualizationVault,OrchestratorVault}` | IDでつなぐ生成Vault。ルートと管理ノートのhashを記録 | `obsidian_layout/vaults.json` |
| `<data>/obsidian_layout` | `interviews.json`（インタビューコード・管理ノートのhash）、`vaults.json`、移行記録・バックアップ | `ObsidianLayout.registry`、`VaultRegistry.catalog_file` |
| `<data>/trash/<日時-ID>/` | 削除した会話のメディア・サムネイルと、削除した行を記録した `manifest.json`（DATA-01） | `app.trash_directory`（DBファイルの隣） |
| `runtime/backups` または `MOJIOKOSI_BACKUP_DIR` | DATA-03のバックアップ一式と各ファイルのSHA-256 manifest。元メディアは任意 | `BACKUP_DIRECTORY`、`services/data_backup.py` |
| `<data>/obsidian_workbench/<key>/` | 仕上げの `state.json`、過去の `state-*.json`、`source-*.json`、`result-*.json` | `ObsidianWorkbench.root` |
| `runtime/output` | 文字起こしの出力。`MOJIOKOSI_OUTPUT_DIR` で変更できる | `DEFAULT_OUTPUT_DIRECTORY` |
| `runtime/uploads`, `models`, `logs` | 一時アップロード・インスタンスロック、モデル、ログ | `app.py`、ランチャー |
| `config/tokens.json` | APIキーと各社の使用モデル（Git管理外） | `TOKEN_FILE` |
| `docs/program-vault` | このVault。アプリは書き込まない | `vault_registry.SOFTWARE_ROOT` と `app.vault_registry()` の2か所 |
