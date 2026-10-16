---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-16
title: 配布用専門家の知識・プロンプト制作計画：検証結果
summary: 検証結果。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 543
- 563
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：検証結果

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### 検証結果

- `tests/test_knowledge_builder_contracts.py`: 15件成功。
- `tests/test_manage_expert_knowledge.py`: 5件成功。
- 対象モジュールの`py_compile`成功。
- `git diff --check`成功。
- `tests/test_method_experts.py`は`PYTHONPATH=src`を設定して`python -m unittest discover -s tests -p test_method_experts.py -v`で実行し、28件成功。以前のcollection失敗はテスト起動時のimport path不足だった。

### 未完了の実装境界

上記は最終配布物の完成ではない。Colab側のJob処理・固定Qwen3 workerとローカルZIP受理は追加済みだが、ローカルからDriveへの自動転送、監査異常時の自動停止、実ランタイムでの往復確認、正式pinの承認・出所証明、Local Papersの実行時統合、回答を作って採点する隔離評価runnerと意味審査suite、17専門家への知識・評価展開、ReleaseApprovalは後続工程で実装する。P1契約コアのhashは改ざん検知用であり、それ単独では配布物の署名や出所証明にならない。

### Local Papers overlay contract実装境界（2026-09-27）

- 公開 `ExpertKnowledgeContext.load()` / `load_expert_pack()` はBase Packのみを受け付ける。Local Papers overlayは実PackのBase rootとinstallation IDを検証した後、`load_local_papers_pack()` でのみ合成する。
- Local PapersのSource/Claim IDは `local:<installation_id>:source:<id>` / `local:<installation_id>:claim:<id>` に分け、Base Packでは `local:` namespaceとprivate/local-only Sourceを拒否する。overlayはlocal routeに限る。
- overlay内の各Claimには独立した採用記録を1件要求する。記録はClaim全体のcanonical hash、installation ID、Base Pack root、引用Sourceごとのversion・原文SHA-256・Source record全体のcanonical SHA-256に束縛する。出典の書誌・権利・locator等が訂正された場合も再採用が必要。
- 採用記録の `revoked` 状態は新しいPackの作成・読込を拒否する。一方、旧overlayのrootを実行側が引き続き指定している場合に自動失効させるactive-root registryは未実装である。取消時は旧rootを利用対象から外す運用・統合が必要。
- モデル要求を作る前に、query・Claim・Source metadata・evidenceを含む全文字列を再帰的に検査し、file URI、Windows/POSIX/UNC/home-relative pathを含む文字列全体を伏せる。`local_uri` locatorのvalueは常に伏せる。
- これはBase/overlayの検証境界である。後続でprivate PDF/TXT取込・簡易検索・根拠読取の試作を追加したが、OCR、利用者別overlayの有効root管理、既存分析への組込、実資料を使う評価と配布承認は別工程で残る。
