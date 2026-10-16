---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-08
title: 配布用専門家の知識・プロンプト制作計画：9. 実装順と監修の節目
summary: 9. 実装順と監修の節目。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 377
- 414
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：9. 実装順と監修の節目

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

## 9. 実装順と監修の節目

Lunaは1チケットずつ実装する。各段階の受入条件を満たしてから次へ進み、Solは監修時に変更を書き広げず、指摘と修正条件を返す。

| 段階 | Lunaの実装内容 | 受入条件 | Sol監修 |
| --- | --- | --- | --- |
| P0 接続・基準記録 | 専門家・文献の再集計、LM Studio推論、モデル選定、Driveアプリ認証方式の選定、原本ルート設定、利用量記録 | 架空の1要求をローカル＋Colabで受け渡し、入力・結果hashを照合。要求と完了記録にjob/generationを付け、ローカルで一回だけ受理。成果物は接続確認用だけに保存 | 通常は不要 |
| P1 契約 | source/claim/job/evaluation/packageのschema、送信区分、Base固定rootからモデル入力までの経路、追加層の衝突処理、凍結評価のアクセス主体、最小輸送契約 | 架空データで両版の成果物構造・停止条件と、実行世代＋完了hash＋単一採用を実装・確認 | **1回目：契約と評価設計** |
| P2 文献と知識 | 取得・抽出・出典位置・重複・候補生成・構造検証・承認済み知識の管理 | 公開資料とローカル限定資料が混ざらず、主張から原文へ戻れる。生成物はP4まで試作領域に留める | 重大な契約変更時だけ |
| P3 3専門家の試作 | テーマ分析・フレームワーク法・記述統計の知識、prompt、評価を一巡 | 配布時と同じ呼出経路で知識の入力・回答への反映、基準版比較、評価隔離を確認。Packは明示的な内部候補としてP4まで試作領域に保存し、配布readerは拒否 | **2回目：評価結果と実行への反映** |
| P4 中断と再開 | Drive輸送、完了記録、実行世代、生存通知、期限、再試行、ローカル監視 | 模擬切断・遅延・重複・再起動から復旧し、旧結果を採用しない | 解決不能な境界不具合だけ |
| P5 Local Papers版 | PDF取込・検索・ページ読取、private追加層、同名ノートの差分選択、古い索引・資料不足への対応 | 指定資料が検索でき、利用者編集を保持し、private由来の内容がBase配布へ入らない | **3回目：ローカル資料・配布境界** |
| P6 17専門家へ展開 | 残り14専門家の不足を埋め、専門家別の改善周期を実行 | 各専門家が合格、または具体的な未達理由で停止。大量処理はA100で実施 | 異議のある根拠だけ |
| P7 配布 | 両版のZIP、manifest、説明、ライセンス情報、公開サンプル、互換読取 | 全専門家の基準合格とP4復旧gateを確認し、immutable `ReleaseApproval`をPack rootへ紐付けた後にのみ、クリーン環境の読取・根拠照合・旧版へ戻す手順・混入検査を通したZIPを配布可能とする | **4回目：配布候補の総合確認** |

最初の3専門家は、質的分析、表による整理、数値の定義の違いを確認するために選ぶ。難しい手法を避けて完了とする意味ではない。KJ法等のAI補助が許可されていない専門家には、説明と確認の範囲に合う評価・プロンプトを作る。

P0/P1でJobとCommitの最小世代契約を使い、P2/P3も同じものを使う。P4で中断・遅延・再起動まで拡張する。受理操作は`(job_id, generation)`を比較交換し、単一writerが`accepted_generation`を一度だけ単調更新する。受理前に全ArtifactのDrive file ID・size・SHA-256・schemaを再検証し、完了manifest hashを確認する。部分アップロード、古いattempt、遅れて届いた結果、再送の重複を拒否する。Packは受理済みCommitだけを参照する。P3の合格は試作評価の合格とし、P4の復旧・単一採用確認が通るまで配布用の承認済み領域に昇格させない。

実装箇所の予定は以下とし、各チケットの開始時に既存責務を再確認する。

| 箇所 | 変更・追加の責務 |
| --- | --- |
| `src/gurumoji/method_experts.py` | Baseのみの解決、追加知識assetのhash、従来定義との互換、packet接続 |
| `src/gurumoji/expert_knowledge_context.py`（新規）、`analysis_insights.py` | 配布物の読取・claim選択・packet固定・prompt組立て・根拠検証。共通アダプターを配布時にも使用する |
| `src/gurumoji/knowledge_builder/`（新規） | 文献制作に必要なstore、sources、pipeline、evaluation、packaging、transportの小さなモジュール |
| `<data>/knowledge_builder/state.sqlite3`（新規） | 制作ジョブと来歴。単一writerのローカルDB。会話データのDBと責務が異なり、クラウドと同時共有しない |
| `scripts/manage_expert_knowledge.py`（新規） | `inventory/ingest/run/status/resume/evaluate/build/verify`のCLI入口 |
| `notebooks/Gurumoji_Expert_Knowledge.ipynb`（新規） | 版を固定した制作workerを起動し、選択バッチを実行する薄い入口 |
| 専門家フォルダーと文献ノート | 審査済みの内容、追加asset、定義版、未達事項 |
| `.codex/agents/sol-reviewer.toml`（必要時） | 監修モデルと指示を固定。導入時のCodex版に対応する設定形式を確認する |

原本は既定で移動せず、設定されたルートから読んでID・hashを付ける。作業用コピー・抽出物・候補・評価は`<data>`配下にまとめ、Git管理するものを許可リストで限定する。

配布ビルドは新設する明示的な`base_only`解決を使う。現行の`ExpertCatalog`はローカルを優先するため、既定のままビルドしてはいけない。private資料から派生した要約・例・索引もprivateを継承し、派生元をたどる混入検査で止める。

アーカイブの取込ではパスの範囲、ID重複、schema、hash、互換版を検査し、ノート内の命令や実行コードを起動しない。ローカル上書きがある場合は差分を提示し、既存の利用者内容を保持する。新しいreaderを有効化する前の版を残し、失敗時は元のreaderと配布版へ戻す。
