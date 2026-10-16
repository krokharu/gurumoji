---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-14
title: '配布用専門家の知識・プロンプト制作計画：P4中断・再開基盤の実装記録: Colab要求ZIPと結果取込adapter'
summary: 'P4中断・再開基盤の実装記録: Colab要求ZIPと結果取込adapter。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。'
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 514
- 531
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：P4中断・再開基盤の実装記録: Colab要求ZIPと結果取込adapter

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### P4中断・再開基盤の実装記録: Colab要求ZIPと結果取込adapter

- `src/gurumoji/knowledge_builder/transport.py`を追加。ローカルJobStoreを正本に保ち、Colabへ送るSource抜粋要求ZIPと返却結果ZIPをcanonical JSON・閉じたmember集合・サイズ・SHA-256・schemaで検証する。DBをDrive上で共有しない。
- export/importの両方で`approved_sources`を要求し、要求内Sourceと全フィールド一致させる。これは呼出API境界での照合であり、信頼は渡し元に依存する。実運用呼出側は要求作成者が編集できない独立したローカル承認台帳からSourceを取得する。ZIP内hashだけではDrive書込者・送り手の真正性を証明しない。
- 抜粋anchor・source版・本文hash・task prompt hashを束ね、private Source、Colab route不許可、answer key/secret、要求外Claimを拒否する。Colabは`candidate` Claimのみ返せ、承認操作はできない。
- Windows/POSIXのプロセス間generation lock、job/generation stageの一時tree、空stageへの一度限りのadopt、stage内容一致による受理前クラッシュ回復、完全一致Commit再送のみの冪等受理を実装。旧generation・期限切れ・部分ZIP・改変結果を拒否する。
- 検証: 専門のknowledge builder一式とinventoryのfocused tests 58件成功。`py_compile`、`git diff --check`成功。Sol read-only再監修で前回指摘の並行import/staging競合、新generation拒否、権利自己申告、approved Claim許可は解消し、新たなブロッカーなし。
- この段階ではZIP transportのみであり、Drive APIアップロード/ダウンロード、Colab上でのモデル推論、独立台帳を使う本番caller、署名付き成果物は未実装だった。後続でColab側のDrive Job pollとモデルadapterを追加したが、ローカル側の自動Drive転送・本番caller・署名は引き続き未実装。

### P4中断・再開基盤の実装記録: 有限Colab workerのオフライン試作

- `src/gurumoji/knowledge_builder/colab_worker.py`に、Colab request ZIPを検証してgenerator関数へ`task`と明示された`excerpts`だけを渡し、候補Claim・台帳由来Source・Commitを含む結果ZIPを返す入口を追加した。workerは状態の採用権限を持たず、最終取込は引き続きローカルtransport adapterが行う。
- Job/generation/deadline/input hash、closed ZIP envelope、Source excerpt/hash/anchor、独立台帳とSource全フィールド一致、Colab route権利、Claim expert/evidence/statusを検査。answer key等の入力・生成出力を拒否する。ClaimからSourceを生成せず、承認台帳のレコードをそのまま成果物にする。
- この段階の`generate(task, excerpts)`は注入可能なcallableで、モデル・依存パッケージ・Drive・ネットワークに接続しなかった。後続で固定Qwen3のprompt compilerとColab側Drive pollを追加した。署名、ローカル側のDrive自動転送、実ランタイムでの中断・再開実証は引き続き未完了。
- ZIP member名はIDから決定的なSHA-256表現で生成し、ID自体はartifact JSONに保つ。契約上有効なコロン入りSource/Claim IDでもworkerからローカル取込まで通る。
- 検証: worker、transport、contracts、Pack builder/reader、inventory一式のfocused tests 63件成功。worker/transportの`py_compile`、`git diff --check`成功。valid mock worker結果をローカル取込するroundtripと、不正ZIP、期限切れ、route権利、secret、承認Claim、excerpt外根拠、台帳Source不一致を検査。
- 既存専門家定義・架空サンプルの回帰テスト36件も`PYTHONPATH=src;src/gurumoji;tests`で成功。後続のDrive確認では共有folder内の接続確認Notebook 1件を確認し、保存済み実行出力はA100 80GBと512x512 CUDA計算成功を示した。最終保存は2026-09-26 20:11 UTCであり、再接続後のlive runtime状態、A100 worker推論、P4 Drive transportは未確認。Colabランタイムの直接操作APIもない。
