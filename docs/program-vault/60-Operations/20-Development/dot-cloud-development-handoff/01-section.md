---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-01
title: dot クラウド開発とローカルへの引継ぎ：dot クラウド開発とローカルへの引継ぎ
summary: dot クラウド開発とローカルへの引継ぎ。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 1
- 23
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：dot クラウド開発とローカルへの引継ぎ

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。


# dot クラウド開発とローカルへの引継ぎ

## 作業と記録の分担

基本的な調査、整理、編集、実行、検証、進捗確認は利用可能な dot の機能を優先する。ローカル PC でも開発を再開できるよう、意味のある節目で Software Vault の関連ノートへ、設計判断と理由、変更背景、テスト結果と未実行範囲、未解決事項、次の作業、対象 commit と根拠を残す（利用者の方針、2026-10-02）。

全 Vault の事前読み込みや作業ログの逐次複製は不要。既存ノートを対象に絞って更新し、詳細ログ・大きい成果物は参照先を示す。研究者の本文・タグ・別名は所有者のものとして保護し、開発記録のために置換しない。登録規約は [[40-Design/50-Governance/program-vault-rules|program-vault-rules]]、作業の入口はリポジトリ直下の `AGENTS.md`。

## 初期クラウド配置の根拠

- アプリの移入元: `4b311df51c7fe2938f1761cb1efbb4cc4906fd10`
- CPU 環境と音声 smoke: `5af286d738731a337466e3fb155b3e6f622fd0e7`
- dot 向けルール初版: `36d8895bff0fc53db7ed5e79923de4d003949c44`。以後の方針更新は `AGENTS.md`、`.agents/rules/dot-cloud.md` と本ノートの Git 履歴で追跡する
- 移入 Vault の不変な共通基点: `045d51340b989d934b730b639d45312556596e84` / `gurumoji-vault-base-v1`
- 別 Vault repo の安全な取得・比較ツール: `bd947a4f7e92125cc94fdebcf9518cd7385e43ce`、運用手順は同 repo の `SYNC_OPERATIONS.md`

クラウドでは `projects/gurumoji/app`、`runtime`、`vaults`、`artifacts` を分離する。`scripts/run_cloud.sh` は既存の `MOJIOKOSI_DATA_DIR`・`MOJIOKOSI_OUTPUT_DIR`・`MOJIOKOSI_BACKUP_DIR` を使い、アップロードは `app/runtime/uploads` に残す。`src/gurumoji/app.py` の `DATA_DIRECTORY`・`DEFAULT_OUTPUT_DIRECTORY`・`BACKUP_DIRECTORY` が対応する。symlink で安全なパス検証を回避しない。

Python は Linux の `.venv/bin/python`、初期版は 3.12.14。CPU の依存関係は `config/constraints-cloud-cpu.txt` と `config/requirements-cloud-cpu.lock.txt`、実行手順は `.agents/rules/dot-cloud.md` を参照する。Windows の仮想環境・資格情報を流用せず、ローカル手順は `.agents/rules/windows-local.md` に分けた。

5つの移入 Vault（Research、Input、Visualization、Orchestrator、Persona）は別 Git の `vaults/` 配下に保持し、実行時 Vault の監視先へ接続しない。Software Vault はアプリの `docs/program-vault`。ノートの snapshot は DB・メディア・分析成果物の復元ではない。
