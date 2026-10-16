---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-10
title: 設計判断の記録（ADR）：ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る
summary: ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 348
- 376
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る

- **状態：** accepted（利用者の方針「使っているライブラリに即した配布条件」に基づき、人格パネルで決定、2026-09-15。`LICENSE`・`THIRD_PARTY_NOTICES.md`の作成と著作権者名の確認はPhase 0）
- **背景：** リポジトリにLICENSEファイルがなく、配布条件が決まっていない。
- **決定：**
  - 本体のコードをMITライセンスにし、第三者ライセンスの一覧を付ける。
  - プロセス内でimportする依存は、許容型のライセンス、改変しないMPL-2.0、動的リンクのLGPLに限る。GPL・AGPLのライブラリはimportしない。
  - モデルの重みと参加者データは、配布物に含めない。
  - `.venv`やインストーラーを配布する場合は、imageio-ffmpegが同梱するFFmpeg（`--enable-gpl --enable-version3`のGPLv3ビルド）のライセンス文と、対応するソースの入手方法を付ける。
- **理由：** 直接の依存はすべてBSD・MIT・Apache-2.0で、Whisper、faster-whisper、CTranslate2、GiNZA、spaCyなど主要な依存がMIT。MITはこれらすべてと両立し、GPLの外部ツールと組み合わせる余地も残す。
- **代替案：** Apache-2.0（特許の条項はあるが、GPL-2.0だけのソフトと結合できない）。GPL-3.0（現状の依存からは必要ない）。
- **結果・影響：** 依存を追加・更新するときは、ライセンスの確認と一覧の更新を同じ変更で行う。`.venv`にあるPySide6（LGPL-3.0／GPL）は、どのパッケージにも必要とされず、コードでも使っていないため、配布物に含めない。確認した一覧は[[40-Design/10-Analysis/quantification-statistics-plan/00-Index|quantification-statistics-plan]]の12章。

### ADR-114 議論用の人格をPersonaVaultに置き、OrchestratorVaultと用途を分ける

- **状態：** accepted、作成済み（2026-09-15。アプリには未登録）
- **背景：** 利用者が、この手段を議論する人格用のObsidianを求めた。設計上のOrchestratorVaultは、分析手法カードと実行記録を保存する場所で、人格のプロフィールや長期記憶を置く場所ではない。実データでもOrchestratorVaultは未生成だった。
- **決定：**
  - `<data>/obsidian/PersonaVault`を手作業で初期化する。人格のプロフィール（`10-Personas`）、パネル（`20-Panels`）、議事録（`30-Deliberations`）、人格ごとの記憶（`40-Memory`）を置く。
  - アプリは読み書きせず、`VaultRegistry`にも登録しない。記憶と議事録は追記だけにする。
  - 研究データ、発話本文、参加者の情報、秘密情報、個人PCの絶対パスは書かない。
- **理由：** 手法カードと実行記録（アプリが管理）と、人格の定義と議論（人とAIが手作業で更新）では、書き込む主体と更新の規則が異なる。
- **代替案：** OrchestratorVaultに人格を置く。Software Vaultのフォルダーに置く。Git管理の独立したVaultを`docs/`に置く。
- **結果・影響：**
  - `runtime/`はGit管理外のため、人格の定義と議論はGitに残らない。バックアップは`<data>`一式と同じ扱いにする。
  - `<data>/obsidian`自体がVaultとして開かれた痕跡があり（OBS-10）、PersonaVaultもその内側になる。Obsidianでは`PersonaVault`フォルダーを直接開く。
  - [[30-Data/40-Vaults/four-vaults-v1|four-vaults-v1]]への追記は、同じ資料を変更中の作業が確定した後に行う。アプリから参照する場合は、別のADRで決める。
- **関連：** PersonaVaultの`PNL-quantification-statistics`、`DLB-20260915-quantification-statistics`（IDで参照）
