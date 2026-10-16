---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-14
title: 設計判断の記録（ADR）：ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る
summary: ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 443
- 464
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る

- **状態：** accepted（2026-09-20の設計方針、未実装）
- **背景：** 利用者から、LLM分析専用オーケストレーター、Jev／LLMの手法・結果形式の事前定義、疑似人格どうしの相談による型の作成、クロス集計以外の後続分析への接続を求められた。
- **決定：**
  - 統括・手法・型・後続分析を役割として分け、必要な担当だけが上限付きで相談する。同じローカルLLMを順に使える。Jevは選択肢判定を担当し、型生成や議論のモデルとして扱わない。
  - 入出力schemaに、意味・単位・尺度・欠測・根拠・接続条件を加えた手法別契約を版管理する。先に決めるのは結果の形式であり、分析の結論ではない。
  - 相互指摘と異論を残し、コードの検証・試行・採用を経て実行する。既存テンプレートの設定内では自動採用でき、新しい概念・尺度・コードブックの採用は研究者が決める。合意やschema適合と、科学的妥当性を区別する。
  - 既存レジストリ・登録票・AnalysisStoreを拡張する。観測表と主張集合から始め、関係表・系列・ベクトルへ広げる。後続のrunner／adapterが未実装なら利用不可とする。
  - 相談・型・結果を別のartifact／実行記録として保存し、OrchestratorVaultには既存経路で要約を公開する。採用済み契約では再相談を省く。
- **理由：** 出力の再利用条件を実行前に明確にし、LLMによる相談を実行可能性と妥当性の確認につなげる。表の作成やクロス集計だけに処理を固定しない。
- **結果・影響：** 再編計画の「LLM同士の合議を初期対象外」とする方針を、FLOW-5bの限定的な相談へ変更する。ADR-115の専門家知識の正本とAI補助制約、ADR-114のPersonaVaultを自動読み書きしない境界は維持する。構造再編とは別の版付き機能拡張として実装する。
- **関連：** [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]、[[50-Analysis-Methods/00-Orchestrator-Common-Contract]]、[[40-Design/50-Governance/method-rules/00-Index|method-rules]]、[[40-Design/10-Analysis/quantification-statistics-plan/00-Index|quantification-statistics-plan]]

### ADR-118 分析UIを、結果閲覧・比較・計画・データ出力の作業単位へ整理する

- **状態：** accepted（2026-09-20の設計方針、未実装）
- **背景：** 利用者から、多様な分析を見る現行UIが不親切であり、再編計画にUI設計も含めるよう求められた。現行の自動／手動／手法別切替は、実行版を横断した結果比較や追加分析の入口を十分に表現しない。
- **決定：** 「結果を見る／比較する／分析を組む／データ・出力」を分析画面内の主入口にする。結果は検索・形式・手法・状態で探し、選択したrunの固定結果を中央に表示する。根拠は開閉式のペインで確認し、結果から比較・追加分析へ移る。
- **結果・影響：** ADR-116の手法別UIは既存部品・状態APIとして再利用し、移行後は新入口へ統合する。上部ナビ、既存URL・根拠リンク、未保存確認は互換維持する。旧表示は移行中の戻り口として残し、新旧の全結果を二重描画しない。表示・比較ではAIを実行せず、計画・試行・実行を分ける。UI-0〜4として段階導入し、型・相談・履歴の不足APIは各FLOW段階と接続する。
- **関連：** [[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]、[[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]、[[40-Design/30-Interface/ui-ux-issues/00-Index|ui-ux-issues]]
