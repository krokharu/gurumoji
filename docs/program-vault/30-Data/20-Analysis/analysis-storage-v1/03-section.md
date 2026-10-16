---
note_type: reference-section
status: current
feature: analysis-storage
verified: 2026-10-13
updated: 2026-10-13
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/obsidian
note_id: program-analysis-storage-v1-section-03
title: AI仕上げ・文章分析の保存契約 v1：書き出しと回復
summary: 書き出しと回復。出典ノート「AI仕上げ・文章分析の保存契約 v1」の分割本文。
parent_note_id: program-analysis-storage-v1
source_path: 30-Data/analysis-storage-v1.md
source_sha256: 31b48be809af0922124aea608b12aec7e8f935b513ca61743fecd5d9e06bc885
source_body_lines:
- 90
- 136
split_on: '2026-10-11'
---

# AI仕上げ・文章分析の保存契約 v1：書き出しと回復

親索引・状態・確認版：[[30-Data/20-Analysis/analysis-storage-v1/00-Index]]。必要な本文だけを取得する。

## 書き出しと回復

版2の保存・取得・参照復旧は[[30-Data/20-Analysis/analysis-storage-v1/01-section#保存パッケージ版2（2026-10-13、段階4-2）|版2の保存契約]]に従う。版2の推論を含むrunは要求IDごとに固定し、入力・設定・モデル・結果の不一致を拒否する。CSVはその場で生成し、F1だけhash照合後にbackground復旧する。以下の再利用・JSON／CSV同時保存の説明は版1の記録であり、旧pendingの復旧にも適用する。

入力識別値・手法版・条件・AI生成IDから同一結果を判定する。同じリクエストIDの重複は再利用し、別入力への流用は409にする。`ai_finishing`・`ai_insights`では要求IDも識別に入り、明示的な再生成は別の履歴になる。それ以外のkindでは同じfingerprintの完了runを再利用する。provider・model・結果本文は、それだけでは識別に含まれないため、新しい実行種類へこの再利用規則を無条件に適用しない。追加分析の再送・再利用・明示再実行は再編計画のFLOW-1で別途定義する。

DBに再試行用パッケージを登録 → 一時ファイルから各JSON／CSVを置換 → hashと件数をDBに確定 → Markdownを生成、の順に保存する。起動時に中断中の書き出しを検出する。「保存済み結果から再試行」は当時のパッケージを使うので、後から本文を編集しても過去版を現在の内容に置き換えない。

`analysis_pending_packages`は計算後の保存回復だけを担当する。統合実行の受付・計画・step試行は別のpipeline台帳へ保存し、起動時に実行中attemptを`interrupted`へ移してpipelineを再試行待ちにする。再試行は世代を更新し、失敗したstepから新しいattemptを作る。確定済みの親成果物と結果runは再利用し、公開再試行で分析やAIを繰り返さない。

分析の生成ノートが人に編集されていたら、編集版を各インタビューの `履歴/ノート変更/` に写してから最新版で上書きする。削除されていたら作り直さず、保存結果の `vault_notes` と `90-運用/同期状況.md` で知らせる（2026-09-25、OBS-04）。保存済みのJSON／CSVは変更しない。考察は各インタビューの`I###-研究メモ.md`に書く。旧`60-ResearchNotes`は移行前の配置。ノートの自動マージは行わない。書き込み主体ごとの差異は[[20-Modules/30-Storage/obsidian-integration/00-Index|obsidian-integration]]を参照する。

会話をアプリで削除しても、固定結果とVaultの履歴は自動削除しない。削除済み会話のアプリAPI・音声リンクは使用できなくなる。完全に消去する場合はバックアップを含め、保存した実行・入力・ノートを別途整理する。バックアップと復元は [[60-Operations/10-Data/backup-restore|backup-restore]] の手順で、DB・メディア・`analysis_store`・各Vault・台帳を一組で扱う。

## APIと拡張手順

| 操作 | API |
| --- | --- |
| 組み込み手法一覧 | `GET /api/analysis/methods` |
| 統合実行の能力一覧 | `GET /api/analysis/pipeline-capabilities`。提供中と未提供の手法・形式・provider役割を区別する |
| 手動定義の保存 | `PUT /api/library/<id>/analysis/definitions/<definition-id>`。`expected_revision`を検証する |
| 手動定義の少数試行 | `POST /api/library/<id>/analysis/definitions/<definition-id>/trials`。固定入力の最大20件を既定にし外部通信しない |
| 計画プレビュー | `POST /api/library/<id>/analysis/plans/preview`。副作用なくPlanEnvelopeとExecutionBindingを返す |
| 統合実行の開始 | `POST /api/library/<id>/analysis/pipelines`。`request_id`、入力版、local-only方針、定義ID、公開先を固定する |
| 統合実行の状態 | `GET /api/library/<id>/analysis/pipelines/<pipeline-id>`。milestone、step attempt、event、公開先別状態を返す |
| 統合実行の取消・再試行 | `POST .../<pipeline-id>/cancel` / `retry`。取消は世代単位、再試行は失敗箇所から行う |
| インタビュー比較 | `POST /api/library/interview-comparison`。応答に対象会話ごとの`input_fingerprints`を含む |
| 比較の固定保存 | `POST /api/library/interview-comparison/runs`。集計時の`item_ids`・`allow_different_content`・`input_fingerprints`と`request_id`を送る。入力版の欠落は400、現在版との不一致は409で再集計が必要 |
| 全件分析／KWICの固定保存 | `POST /api/library/<id>/analysis/runs`。`request_id`, `source_revision`, `analysis_revision` と任意の `kwic: {q, mode, speaker}` |
| Transformerテーマ分析の実行 | `POST /api/library/<id>/analysis/transformer`。`request_id`, `source_revision`, `analysis_revision`, `mode`（`auto`／`candidate`／`manual`）、`max_topics`／`min_topic_size`（自動）、`topic_count`（候補）、`min_similarity`（手動）。手動のテーマ定義は保存済みの分析設定 `config.transformer_topics` から読む |
| 発話分類の実行 | `POST /api/library/<id>/analysis/classifications`。`request_id`, `source_revision`, `analysis_revision`, `use_jev`を送る。テンプレートは常に実行し、最新のTransformer結果があれば話題提案として併記する。結果は`segment_classifications.csv`と`segment_classification_crosstabs.csv`へ固定保存する |
| 保存履歴 | `GET /api/library/<id>/analysis/runs`。直近100件。古い成果物は保持 |
| 保存・Vault生成の再試行 | `POST /api/analysis/runs/<run-id>/vault` |
| 成果物取得 | `GET /api/analysis/artifacts/<artifact-id>`。hashを検証して返す |
| 固定runのZIP取得 | `GET /api/analysis/runs/<run-id>/export.zip`。manifest、parameters、result、表CSVを同じ固定成果物から束ねる |

保存結果（`run`）の `vault_status` はResearchVaultへの書き出しだけを表す。Input／Orchestrator／Visualizationへの書き出しは `vault_outputs`（Vaultごとの `status`：`published`／`failed`／`conflict`／`unknown` と `error`）と `vault_outputs_complete` で返す。正本（固定成果物とResearchVault）の保存が成功していれば、生成Vaultが失敗しても保存は成功扱いのまま（ADR-009）。「保存履歴」は未完了のVaultと理由を示し、上の再試行で書き直せる（OBS-18）。

新しい組み込み手法は [[40-Design/50-Governance/method-rules/00-Index|登録規約]] を満たし、`analysis_method_registry.METHODS` にID・表示名・CSVデータセットを追加する。計算は既存の分析層へ、詳細と状態・単位・解析器の対応付けは `method_results` へ加える。CSVの列定義、根拠IDの検証、空・除外・更新時の検証を追加し、計算が変わった版を更新する。ファイルから任意コードを実行する登録方式にはしない。登録手法の一覧・件数は現行の`METHODS`を正本とする。

複数会話のインタビュー比較と固定保存は実装済み。ResearchVaultでは`40-研究/インタビュー比較/comparison-<run-id>.md`に保存する。比較画面から保存履歴、成果物、Obsidianノートを開き、固定済み成果物からVault保存を再試行できる（UX-33）。研究メモ・解釈・コード案の差分取り込み、外部R／Python等の結果登録、図の自動添付、保存先変更UI、バックアップ専用UIも後続工程。

検証先：`tests/test_analysis_core_contracts.py`、`tests/test_analysis_plan_binding.py`、`tests/test_analysis_snapshot_commit.py`、`tests/test_analysis_milestones.py`、`tests/test_analysis_recovery.py`、`tests/test_analysis_research_protocol.py`、`tests/test_analysis_exports.py`、`tests/test_analysis_publication.py`、`tests/test_analysis_storage.py`、`tests/test_content_browser.py`。AI通信はモックを用い、実Vaultは使わない。

2026-09-21のWindows作業ツリーで `PYTHONPATH=src;tests` を設定し、`.venv\Scripts\python.exe -m unittest discover -s tests` の550件が成功した。手動定義の少数試行からM0〜M7完了までをChromiumでも確認した。実APIによる生成品質・料金の検証は行っていない。

関連：[[30-Data/10-Inventory/current-storage|current-storage]]、[[40-Design/40-Storage/storage-policy|storage-policy]]、[[20-Modules/10-Inventory/module-map/00-Index|module-map]]。
