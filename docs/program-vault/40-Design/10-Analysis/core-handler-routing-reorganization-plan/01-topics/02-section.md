---
note_type: reference-section
status: complete
verified: 2026-09-20
updated: 2026-10-05
feature: architecture
tags:
- gurumoji/program
- gurumoji/architecture
- gurumoji/plan
note_id: design-core-handler-routing-reorganization-section-02
title: コア・ハンドラー・ルーティング再編案：結論
summary: 結論。出典ノート「コア・ハンドラー・ルーティング再編案」の分割本文。
parent_note_id: design-core-handler-routing-reorganization
source_path: 40-Design/core-handler-routing-reorganization-plan.md
source_sha256: 98cc334bf8a1cd5d991da28ffd9b394da6b7dd173080079385ff9fb473eca535
source_body_lines:
- 33
- 71
split_on: '2026-10-11'
---

# コア・ハンドラー・ルーティング再編案：結論

親索引・状態・確認版：[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index]]。必要な本文だけを取得する。

## 結論

**段階的な分離は採用する。ただし、7層の一括整備ではなく、分析履歴・成果物取得の小さな縦切りを先に完成させ、効果を確認して対象を広げる。** 2026-09-20にPhase 0〜4の構造再編を完了した。後述のAI管理・追加分析・統計・UIは、それぞれの導入条件に従う別の機能拡張である。

次の7項目は責務を見分ける観点であり、7つのパッケージや基盤を最初から作る要求ではない。

1. **Core**：会話、発話、版、分析実行、根拠、stale判定などの業務ルール
2. **Handlers**：1操作を完了させるユースケースの調整役
3. **Routing**：HTTPとHandlerの変換だけを行うFlask Blueprint
4. **Input**：アップロード、既存JSON取り込み、Obsidianからの操作、検証と正規化
5. **Output**：SQLite、成果物、エクスポート、Vault公開、外部AI・FFmpegへの接続
6. **Runtime State**：実行中ジョブ、キャンセル、一時作業領域、再開可能な保留パッケージ
7. **Analysis**：既存レジストリ・保存用結果契約を利用する分析プログラム群

挙動を維持する構造再編では、DB、`analysis_store`、Vault配置、stable ID、Markdownの競合処理を維持する。Obsidianの物理構成はSoftware、Input、Visualization、Orchestrator、Researchの5 Vaultを維持する。追加分析の依存関係・派生入力・出力区分は、後述のFLOW段階で保存契約の版付き拡張として導入し、単なるコード移動とは別変更にする。

AI管理は横断する責務としてこの計画に含める。**分析手法・専門家の定義、実行役割、実行場所、データ送信許可を別々に管理する。** クラウド／ローカルの生成AIとJevを役割で使い分け、ローカルにある専門家知識と実行記録を既存の正本から参照する。まず挙動を維持してAI接続の境界を抽出し、送信方針や実行来歴の拡張は、後述のAI管理段階で別変更として導入する。

目標の分析フローは、**文字起こしの固定版 → アウトラインと分析箇所 → LLMを含む手法別の分析 → 結果を使う追加分析・カラム生成 → 型付きデータセットの統計分析 → 閲覧・共有出力**。LLMは計画担当と分析担当の両方に使え、役割ごとに入力・設定・結果を分ける。分析用RAW、結果から作る派生入力、機械用の分析出力、閲覧・共有出力を区別する。

2026-09-20の追加方針：**LLM分析専用オーケストレーターを用意し、手法・型・後続分析の疑似人格と相談して、入力・分析手順・結果の型・接続条件を先に定める。** 定めるのは結果の項目・意味・形式であり、得られる値や結論ではない。表以外の主張・関係・時系列・ベクトルも扱い、クロス集計を経由せず別の分析へ渡せるようにする。詳細は図6、設計判断はADR-117。

### 評価と修正判断

| 指摘 | 根拠・問題 | 修正方針 |
| --- | --- | --- |
| 最優先：Blueprint化だけでも動作が変わる | `enforce_request_security`は`request.endpoint`の`create_job`／`import_speaker_registry`を参照し、入力上限とジョブ受付を制御する | URLだけでなくendpointとhookの対応を検証。認証・受付処理の再設計を同じ変更に混ぜない |
| 最優先：移行時の依存注入が未定義 | Blueprintから`app.py`をimportすると循環する。テストは`import app`と`patch.object(app, ...)`、設定の差し替えに依存 | 組み立て側から必要な関数を明示的に渡す。旧importとpatchの実効性を確認する |
| 高：先行する基盤作成が多い | commands／queries、全Entity、7種のPort、Catalog、Workspaceを先に作っても、最初の機能分離に必要とは限らない | 機能別Handlerと必要な依存だけを作る。空のディレクトリ・全テーブルのRepository化を行わない |
| 高：異なる状態を1モデルへ統一している | ジョブ進捗、分析結果の有無、入力のstale、Vault同期、保留保存は寿命と回復条件が異なる | 各状態の正本と所有者を維持する。統合状態APIと共通status enumは対象外 |
| 高：分析レジストリと結果契約が重複する | `analysis_method_registry`に21手法、`REGISTRY_VERSION`、`method_results`が既にある。手法とrunnerも1対1ではない | 第2のCatalogと全手法共通DTOを作らず、既存契約を再利用する |
| 高：障害修正と構造整理が混在する | OBS-18はAPI/UIの振る舞いを変える優先課題。後半のOutput統合待ちにする理由がない | 既存経路で独立して修正できる課題として扱い、再編の完了条件に含めない |
| 高：副作用の境界が曖昧 | 保存のlock、DB・ファイルの確定順、再試行、起動回復を別々に移すと回復保証を失う | 既存の操作単位で移し、lock順・確定順・回復情報を維持する |
| 中：検証が大きすぎる | 全69ルートの詳細な手書き台帳と巨大な結果snapshotは保守対象を増やす | ルート構造は機械比較し、詳細検証は変更ルートと隣接境界に限定する |
| 中：構成図と契約に不整合 | Obsidian watcherまでHTTPを経由する図、Portから具象への依存矢印、外部キーの説明漏れがある | 呼び出しとimport依存を区別し、現行コードに合わせて修正する |
| 高：AIの実行先・役割・知識の責務が不足 | 生成AIは3 provider、Jevは別の通信経路。専門家定義とOrchestratorの実行ノートも別の役割を持つ | 段階ごとに実行先・送信方針・入力来歴を確定し、既存の知識と記録を利用する |

採用するのは、機能単位の分離、既存契約の維持、HTTPなしでのHandler検証である。ファイル数や`app.py`の目標行数を成果指標にしない。既存の不具合修正・機能追加を阻害する場合は、完成した縦切りで再編を止められる計画にする。
