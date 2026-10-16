---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-13
title: 分析マイルストーン・可視化プログラム・UI統合設計：16. UIへの反映と導入順
summary: 16. UIへの反映と導入順。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 538
- 580
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：16. UIへの反映と導入順

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 16. UIへの反映と導入順

### 16.1 既存画面へ加えるもの

| 画面 | 追加する表示・操作 |
| --- | --- |
| S02 分析を組む | 詳細設定に「役割と実行モデル」。O01〜O07の使用/不使用、provider/model、必要能力、local_only/cloud_allowed、上限。手動では不要な役割を実行しない |
| S02 手動定義 | 「Obsidianで編集」「変更を確認」。note ID/基準版を保持し、差分を同じ定義エディターへ戻す |
| S03 実行状況 | taskの担当手法、担当役割、実モデル、資源待ちと親待ち。提案・検証・計算・保存・公開を区別 |
| S04 データ・出力 | 「Obsidian連携」。公開先、図の添付、状態、ノートを開く、公開のみ再試行。計算成功と公開失敗を併記 |
| S06 根拠 | 参照した原文版、ノートID、artifact ID、アプリ/Obsidianで開く、旧版の表示 |

新しい管理画面を量産せず、S02/S04の詳細領域に配置する。画面と機械構造は [design-spec.json](../../../analysis-design/design-spec.json) のsystem_extensionsに追記する。今回の追加UIは構造設計であり、既存の4画面生成画像を改変して実装済みと見せない。

### 16.2 実装する場合の順序

1. **境界を固定**：Main→Handlers→Core/Runtimeの参照とポートを1ユースケースで確認。既存計算・保存を再利用。
2. **共通LLM契約**：既存のクラウド1系統とローカル1系統を同じ要求/応答schemaへ接続。手動定義・既定計画も同じ経路へ。
3. **分析コアへ実行を移す**：M0〜M7、段階内並列、再試行・取消・回復。メインと分析で資源枠を共有。
4. **役割別オーケストレーター**：O01/O04から始め、契約・評価済み手法に対してO02/O03/O05/O06/O07を追加。
5. **公開の観測と画像添付**：既存AnalysisStore/Registryの公開失敗をUIへ返し、図を同じVault内で表示。
6. **差分取り込み**：定義ノートから試行・採用・新版保存。研究メモは人所有を保持。同期から自動分析を起動しない。
7. **外部入口の追加判断**：必要ならMCP adapterを同じHandlersへ接続。内部MCPサーバー化を全作業の前提にしない。

### 16.3 追加受入条件

- A01：分析CoreをFlask/app.py/provider SDK/SQLなしで読み込み、計画・尺度・ゲート検証を試験できる。
- A02：同じschemaでクラウド/ローカルのモック応答を検証。未知の手法、架空根拠、循環、異版JOIN、越境送信を拒否。
- A03：手動定義の試行・確定・実行に、LLMによる定義生成が必須でない。
- A04：役割ごとにrequest/usage/modelを追跡。形式エラー・拒否・timeout・部分出力・取消の状態が混ざらない。
- A05：相談上限、資源枠、マイルストーン全件待ちを同時に守る。同じモデルの複数役割でも成立する。
- A06：Vault公開失敗・競合・ノート欠損でも原文と確定結果を保持。公開のみの再試行でAI呼出し0件。
- A07：人の本文、タグ、未知のYAML項目、改行を保持し、両側編集の競合を差分で解決できる。
- A08：図の正本hashと管理添付が一致し、Obsidian内の画像・同一Vaultリンク・ID resolverが解決する。
- A09：Obsidian変更検出だけでは分析/AI/外部送信を開始しない。既存の明示AI仕上げ操作は回帰確認する。
- A10：既存のDB/ノート/旧runを一時環境で移行、dry-run、バックアップ、旧経路への切戻しを確認。移行でAIを再実行しない。

### 16.4 設計成果物の確認範囲

2026-09-21に、共通Schemaの構造検証、要求・応答・計画の正常例4件、不正な役割・hash・状態・確定要求などの拒否例8件を確認した。7役割の担当段階、5つのUI拡張の画面参照、JSONと画面試作の埋め込み定義の一致、文書リンク、6図のSVG/PNG表示を確認した。画面試作は手動定義・段階待ち・再試行表示・画像形式の制約・モバイル幅を確認済み。

これは設計成果物の確認である。実際のLLM接続、手法別payloadの検証、分析の妥当性、Vaultの同期・競合処理は未実装であり、A01〜A10は今後の実装時の受入条件である。アプリコード、DB、実行用Vaultはこの設計作業で変更していない。
