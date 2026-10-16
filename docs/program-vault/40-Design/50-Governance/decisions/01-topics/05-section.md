---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-05
title: 設計判断の記録（ADR）：採用済み（コードから復元）
summary: 採用済み（コードから復元）。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 90
- 209
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：採用済み（コードから復元）

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

## 採用済み（コードから復元）

### ADR-001 Obsidianとはプラグインではなく、ファイルの直接読み書きで連携する

- **状態：** accepted（復元）
- **背景：** 研究者がObsidianで読み・考察でき、Obsidianを閉じていてもアプリが動く必要があった。
- **決定：** アプリがVaultフォルダー内のMarkdownを直接読み書きする。コミュニティプラグインは必須にしない。
- **理由：** アプリの起動と独立させるため。追加プラグインのインストールを不要にするため（[[40-Design/40-Storage/obsidian-plan|obsidian-plan]]「外部プラグイン：必須にしない」）。
- **代替案：** Obsidianプラグインを作り、Vault APIで書き込む。Local REST API系のプラグインを使う。
- **結果・影響：**
  - `Vault.process`、`processFrontMatter`、ゴミ箱などの公式の安全策が使えない。
  - その代わりに `safe_path`、`write_atomic`、hash台帳を自前で実装した。
  - 安全策が不十分な箇所は [[40-Design/50-Governance/known-issues/00-Index|known-issues]] の OBS-* に記録している。
- **関連コード：** `analysis_store.safe_path`、`write_atomic`、`obsidian_layout.py`、`obsidian_finishing.py`、`vault_registry.py`

### ADR-002 正本はSQLiteと固定成果物で、Vaultは閲覧・考察用とする

- **状態：** accepted（復元）
- **背景：** 同じ内容がDB・JSON・CSV・Markdownに現れるため、復元の基準を決める必要があった。
- **決定：** 逐語録と条件は SQLite、分析の全行は `analysis_store` を正本とする。Vaultには要約・根拠リンク・来歴を置く。
- **理由：** Markdownの手作業による編集で、正本が壊れないようにするため。
- **代替案：** Markdownを正本にし、DBを索引にする。
- **結果・影響：** Vaultへの書き出しに失敗しても、保存自体は成功扱いにする（ADR-009）。DBへの取り込みは、明示的な操作に限る（ADR-006）。
- **関連コード：** [[40-Design/40-Storage/storage-policy|storage-policy]]、`AnalysisStore.save`

### ADR-003 アプリ専用のVaultはデータフォルダー配下に作り、利用者のVaultを探したり推測したりしない

- **状態：** accepted（復元）
- **背景：** 利用者のメインVaultに書き込むと、既存の知識ベースを壊す危険がある。
- **決定：**
  - ResearchVault は `<data>/obsidian/ResearchVault` に置く。
  - 生成Vaultは `<data>/obsidian/<英数字>` に置き、`vaults.json` に登録する。
  - `docs/program-vault` には書き込まない。
  - Documents配下など、既存のVaultは探さない。
- **理由：** 書き込み範囲を、アプリが管理するフォルダーに限定するため。
- **代替案：** 利用者が選んだ既存のVaultに書き込む。
- **結果・影響：**
  - 保存先を変えるUIがない。
  - ルートの算出がコードの複数箇所に分散した（ARCH-03）。
  - 利用者が親フォルダーを保管庫として開くと、Vaultが入れ子になる（OBS-10）。
- **関連コード：** `ObsidianLayout.__init__`、`VaultRegistry.root`、`roots`

### ADR-004 自動生成ノートはhashで所有を確認し、外部で編集されていたら上書きしない

- **状態：** accepted（復元）。実装が統一されていないため、ADR-101で見直す。
- **背景：** 研究者が生成ノートに直接追記する可能性がある。
- **決定：** 書き込み時のhashを台帳に記録し、実際のファイルと一致しない場合は上書きしない。
- **理由：** 人が書いた考察を失わないため。
- **代替案：** 生成ノートは常に上書きし、「編集禁止」と表示する。
- **結果・影響：** 台帳が4つ、競合時の挙動が4通りに分かれた（OBS-04）。
- **関連コード：** `VaultRegistry._write`、`AnalysisStore.write_note`、`ObsidianLayout.managed_note`

### ADR-005 AIの生成物は常に新しいパスへ保存し、人が編集中のノートを置き換えない

- **状態：** accepted（復元）
- **背景：** AI仕上げの結果で、研究者が編集した全文やアウトラインを消してはならない。
- **決定：** アウトライン・仕上げ結果・仕上げ後のアウトラインは `履歴/仕上げ/…-<run>.md` として毎回新しく作る。現在の版はリンクで切り替える。
- **理由：** 人の編集とAI出力の競合を、構造的に避けるため。
- **代替案：** 既存ノートに差分を適用する。
- **結果・影響：** 履歴ノートが増える。状態ノートだけは毎回上書きされる（アプリ所有）。
- **関連コード：** `ObsidianWorkbench.execute`、`save_note`

### ADR-006 Obsidianの内容をアプリへ反映するのは「結果をアプリへ反映」の明示操作だけとする

- **状態：** accepted（復元）
- **背景：** 双方向同期では、ループや意図しない上書きが起きる。
- **決定：**
  - 反映は、操作ノートでチェックしたときだけ行う。
  - 反映の前に、次の3点を再確認する。
    - revision が一致すること
    - 元ノートの内容fingerprintが一致すること
    - 反映中に結果ノートが変わっていないこと
  - 研究メモなどの自動取り込みはしない。
- **理由：** データ保全を優先し、同期ループを防ぐため。
- **代替案：** ファイル監視で自動的に取り込む。
- **結果・影響：** テーマ同期はDBへ取り込まないが、テーマノートへの書き込みはある（OBS-01）。研究メモの差分取り込みは Planned。
- **関連コード：** `ObsidianWorkbench.poll_once`、`execute`、`check_sources`、`run_obsidian_finishing`

### ADR-007 4つのVaultは相互にリンクせず、IDで対応付ける

- **状態：** accepted（復元。最新版`2f13f98`に実装を収録）
- **背景：** 役割の異なるVaultを、独立して開けるようにしたい。
- **決定：** Vaultをまたぐ `[[…]]` は書かない。`conversation_id`・`input_snapshot_id`・`run_id`・`artifact_id`・`note_id` で対応付ける。
- **理由：** Vaultをまたぐリンクは、Obsidianでは未解決リンクになるため。
- **代替案：** 1つのVaultにフォルダーを分けて置く。
- **結果・影響：** 詳細は [[30-Data/40-Vaults/four-vaults-v1|four-vaults-v1]]。
- **関連コード：** `vault_registry.py`

### ADR-008 Software Vault（このVault）はGitで管理し、アプリからは書き込まない

- **状態：** accepted（復元）
- **背景：** プログラムの資料と、研究データを混ぜない必要がある。
- **決定：** `docs/program-vault` は `VaultRegistry._write` で書き込みを拒否する。`.obsidian/` は `.gitignore` で除外する。
- **理由：** 資料をコードと同じレビュー単位で管理するため。個人の設定を共有しないため。
- **代替案：** 資料もアプリが生成する。
- **結果・影響：** 資料の更新は、人またはAIが手作業で行う（[[40-Design/50-Governance/ai-development-rules|ai-development-rules]]）。
- **関連コード：** `vault_registry.GENERATED`、`docs/program-vault/.gitignore`

### ADR-009 Vaultへの書き出しに失敗しても、文字起こしや編集の保存は失敗させない

- **状態：** accepted（復元）
- **背景：** Vaultのロックや競合で、正本の保存が止まると困る。
- **決定：** Vaultへの書き出しの失敗は、警告ログまたは `vault_status` に記録し、保存は成功として返す。後から再試行できるようにする。
- **理由：** ADR-002 により、正本はDBと成果物だから。
- **代替案：** DBとVaultをまとめてロールバックする。
- **結果・影響：** 失敗が画面から見えにくい（OBS-09、OBS-15）。
- **関連コード：** `publish_input_vault`、`AnalysisStore.publish_vaults`、`refresh_archive_index`、`POST /api/analysis/runs/<id>/vault`

### ADR-010 新規の文字起こしは「Obsidianで仕上げる」を既定とする

- **状態：** accepted（復元）
- **背景：** AI校正の前に、研究者が原文を確認・編集できるようにしたかった。
- **決定：** `finish_in_obsidian` の既定をTrueにする。ジョブ内のAI仕上げはAPI互換のために残し、UIでは校正のチェックを非表示にする。
- **理由：** AIによる変更を、人が確認したうえで反映するため。
- **代替案：** ジョブ内で自動校正する。
- **結果・影響：** AI仕上げが2経路になった（ARCH-07）。既定値が3か所に書かれている（CFG-03）。
- **関連コード：** `JobOptions.finish_in_obsidian`、`create_job`、`run_transcription_job`、`index.html`

---
