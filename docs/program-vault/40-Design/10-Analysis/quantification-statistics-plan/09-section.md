---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-09
title: 発話の数値化とjamovi型統計の自動実行計画：11. 実装の順序
summary: 11. 実装の順序。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 248
- 308
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：11. 実装の順序

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 11. 実装の順序

各段階を単独でレビューし、関係する回帰テスト、手法ノート、[[20-Modules/10-Inventory/feature-inventory/00-Index|feature-inventory]]、[[40-Design/50-Governance/decisions/00-Index|decisions]]を同じ変更で更新する。

### 着手の条件

別の作業による未コミットの変更（セットアップ、VisualizationVaultの起動スクリプト、Obsidian安全化で`analysis_store.py`・`obsidian_layout.py`・`obsidian_finishing.py`などを変更中）が確定するまで、同じファイルに触れる実装を始めない。[[40-Design/50-Governance/convergence-plan/00-Index|convergence-plan]]の他の課題（UX-33など）は、ファイルが重ならなければ並行してよい。

### Phase 0：決定の実装と契約

- **範囲：**
  - `config/requirements.txt`にstatsmodels 0.15系を追加し、セットアップのテストとREADMEの依存の記載を更新する。
  - `LICENSE`（MIT。著作権者名は利用者が確認）と`THIRD_PARTY_NOTICES.md`を作る。
  - 保存契約（変数カタログ、分析用データセット、統計解析計画、検証サンプル）を`30-Data`に定義する。抽出確率と検証の状態の列を最初から入れる。
  - 一致テスト用の架空データとgolden値を作る。jamoviかR＋jmvは、このときだけ用意する。
  - 13章の既定値を決める。
- **完了条件：** statsmodelsを入れた環境で既存のテストが通る。ライセンスの一覧が12章と一致する。

### OBS-18：生成Vaultの書き出し失敗を保存APIに集約する

- **理由：** 新しい統計とAI数値化の実行記録も、OrchestratorVaultとVisualizationVaultへ出力する。失敗が見えない状態で手法を増やさない。
- **範囲と完了条件：** [[40-Design/50-Governance/known-issues/00-Index|known-issues]]のOBS-18の受け入れ条件どおり。1レビュー単位を超える場合は、Phase 1aとの並行を再判断する。

### Phase 1a：SciPyの検定・集約・jamovi出力（AIなし）

- **範囲：** `statistical_tests.py`、9.2のうちSciPyで実装する検定、効果量のCI、Holm・BH補正、話者・参加者・インタビュー単位への集約、比較軸の拡張、計画→選択→実行→テンプレート報告、jamovi用CSV・変数カタログ・jmv構文・手順書、「統計を実行」ボタン。既存の感情ラベル、手動コード、相づち、事前アンケートを変数カタログへ登録する。
- **統合：** 既存の分散分析・Kruskal–Wallis・カイ二乗・相関、相づちのカイ二乗、ブラウザー側の相関を`statistical_tests.py`へ移す。
- **完了条件：**
  - golden値と許容誤差内で一致する。
  - `statistical_tests`・`correlations`の列の互換を保つか、版を上げて移行を説明する。
  - 空データ、1群、欠測、全て同じ値、期待度数の不足、最小N未満で`not_computable`と理由を返す。
  - 計画、比較軸、集約の規則をfingerprintに含め、変更すると`stale`になる。
  - 統計の実行・保存・Vault出力がAIを呼ばない。
- **テスト：** `tests/test_research_analysis.py`、`test_analysis_storage.py`、`test_interview_comparison.py`、`test_browser_e2e.py`（計画→結果→保存）。

### Phase 1b：statsmodelsによる分析

- **範囲：** 発話単位の探索的な分析への、話者でクラスター化したGEE（二値・計数）とクラスター頑健標準誤差。線形混合モデル。線形・二項ロジスティック・順序ロジスティック回帰。反復測定・要因の分散分析、共分散分析。
- **完了条件：** golden値と一致する。モデルが収束しない場合を`not_computable`と理由で返す。GEEと混合モデルの入力表を、Phase 5の補正でも使える形で保存する。statsmodelsのimportがWebの起動を遅らせない。

### Phase 2：決定的な数値化（ルール辞書・会話構造）

- **範囲：** 宣言的なコーディングルール、言語マーカーの辞書、モーラ/秒の発話速度、話者別の会話構造変数。利用条件を確認できた場合だけ、J-LIWC2015などの辞書を任意で使う。
- **完了条件：** ルールの版と辞書のhashがfingerprintに入る。ルールごとに該当発話へ戻れる。人手コードと比べられる形で保存する。

### Phase 3：LLMのコード・評定と妥当性ゲート（同時に出す）

- **範囲：** 6章と7章。「AIで数値化」ボタン、試行と全件の2段階、送信前のダイアログ、同意の扱い、キャッシュと上限トークン、失敗したバッチだけの再実行、AIのラベルを隠した検証画面、一致度（信頼区間付き）と群ごとの誤り、ゲートの状態の変数カタログへの反映。
- **完了条件：** モックAIで、schema、引用の一致、未判定、再試行、3回の実行の集約、キャンセル、見積もり、上限での停止、キャッシュの再利用、同意しなかった話者の除外を検証する。ゲート未通過の変数を確認的な計画に選べない。AIのラベルが人のコードに自動で入らない。
- **限界：** 実際のLLMの精度は、研究データごとに検証サンプルで測る。アプリのテストでは保証しない。

### Phase 4：Transformer分類器と能動学習

- **範囲：** E5ベクトル＋ロジスティック回帰（層化交差検証、確率の校正の確認）、低確信の発話とLLM不一致の発話の検証キューへの送付、学習ラベルの出所の記録、TF-IDF＋線形分類器との比較。ゼロショットの類似度は候補の提示だけに使う。
- **完了条件：** seed、分割、モデルのrevision、学習ラベル集合のhashを保存する。交差検証とゲートを通過した分類器だけを変数にする。全会話へ再適用しても同じ結果になる。

### Phase 5：発展（誤分類の補正・音響・外部R）

- **範囲：** 一般化線形混合モデル、話者単位の並べ替え検定、AIラベルの変数へのDSL・PPI型の補正、音響特徴（librosaのpYINなど。ライセンスを確認）、R＋jmvの外部実行、STM。
- **完了条件：** 手法ノート、査読文献、限界を登録してから有効にする。
