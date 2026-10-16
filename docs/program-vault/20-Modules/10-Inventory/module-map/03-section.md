---
note_type: reference-section
status: current
verified: 2026-09-25
updated: 2026-09-26
tags:
- gurumoji/program
note_id: program-module-map-section-03
title: 機能・コード・テストの対応表：検証の実行
summary: 検証の実行。出典ノート「機能・コード・テストの対応表」の分割本文。
parent_note_id: program-module-map
source_path: 20-Modules/module-map.md
source_sha256: 9d4be038e5ca8e5f28209be2d481906c976790670a214ce8b9bc595ce249b386
source_body_lines:
- 51
- 57
split_on: '2026-10-11'
---

# 機能・コード・テストの対応表：検証の実行

親索引・状態・確認版：[[20-Modules/10-Inventory/module-map/00-Index]]。必要な本文だけを取得する。

## 検証の実行

リポジトリルートで `python -m unittest discover -s tests -q` を実行します。ブラウザーテストはEdge／Chrome／Chromium、メディアテストの一部はFFmpegを利用します。テスト結果の記録には実行日・対象commitまたは作業ツリー識別値・成功／失敗／スキップ理由を付けます。

このノートはテストの対応表であり、現在の環境での全テスト合格を自動保証するものではありません。

機能の分類（Core／Duplicate／Legacyなど）は [[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]]、Obsidian連携の書き込み主体と競合処理は [[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]] を参照してください。
