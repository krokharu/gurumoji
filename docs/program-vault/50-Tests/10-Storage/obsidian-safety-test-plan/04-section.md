---
note_type: reference-section
status: in-progress
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/tests
- gurumoji/obsidian
note_id: tests-obsidian-safety-plan-section-04
title: Obsidian連携の安全性テスト計画：実行方法
summary: 実行方法。出典ノート「Obsidian連携の安全性テスト計画」の分割本文。
parent_note_id: tests-obsidian-safety-plan
source_path: 50-Tests/obsidian-safety-test-plan.md
source_sha256: 5244a19b68353e0baee8e78523afc1299e1d0d9188c030b57c1153b7afb63f7b
source_body_lines:
- 107
- 118
split_on: '2026-10-11'
---

# Obsidian連携の安全性テスト計画：実行方法

親索引・状態・確認版：[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index]]。必要な本文だけを取得する。

## 実行方法

リポジトリルートで、プロジェクトの仮想環境を使う。`src`と`tests`は子プロセスにも渡す。

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + (Join-Path (Get-Location) 'tests')
& .\.venv\Scripts\python.exe -X utf8 -m unittest test_obsidian_layout test_obsidian_finishing test_analysis_storage test_four_vaults test_vault_coverage -v
```

全体の実行は`& .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py"`。ブラウザーテストにはEdge／Chromeが必要。テストは一時DB・一時Vaultを使用する。アプリの起動を併用する場合は、原則に従い`MOJIOKOSI_DATA_DIR`・`MOJIOKOSI_OUTPUT_DIR`も一時フォルダーへ向ける。

結果を記録するときは、実行日、対象のcommit（または作業ツリー）、成功・失敗・スキップの理由を書く（[[20-Modules/10-Inventory/module-map/00-Index|module-map]]）。
