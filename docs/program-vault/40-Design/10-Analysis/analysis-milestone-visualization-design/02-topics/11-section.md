---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-11
title: 分析マイルストーン・可視化プログラム・UI統合設計：14. 様々なLLMに対応するオーケストレーター
summary: 14. 様々なLLMに対応するオーケストレーター。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 400
- 466
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：14. 様々なLLMに対応するオーケストレーター

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 14. 様々なLLMに対応するオーケストレーター

### 14.1 役割の分離

| ID | オーケストレーター | 担当段階 | 返すもの |
| --- | --- | --- | --- |
| O01 | 計画担当 | M0 | 利用可能な手法・対象・依存・必要能力を示すPlanProposal |
| O02 | アウトライン担当 | M1 | 論点候補、予定質問対応、発話との対応候補 |
| O03 | 意味分析担当 | M2/M3 | 主張・立場・関心・相互作用の手法別契約と根拠付き候補 |
| O04 | ラベル・測定・尺度担当 | M4 | VariableDefinition案、例・反例、試行条件 |
| O05 | 手法・結果確認担当 | M0/M3/M4/M5 | 前提・尺度・根拠の指摘、反例、解決が必要な事項 |
| O06 | 統合・二次分析担当 | M6 | 共通点、食い違い、追加分析案、終了条件 |
| O07 | 可視化・説明担当 | M3/M7 | 許可された図種・列・説明のChartSpec案。数値は確定dataset参照 |

オーケストレーターは役割であり、常駐する別モデルではない。同じモデルが複数役割を担当してよい。役割数と同数のエージェント/プロセスを常時起動しない。計画担当と実際の文章分析担当のcall ID、プロンプト版、入力、使用量、結果は別管理とする。

現行のO01接続は、基礎分析の実行設定で計画候補を明示生成する範囲に限る。ローカルTransformerは分析目的と実行可能な2手法のカードを意味ベクトルで比較する。指定LLMはLM Studioを既定とし、OpenAI／Googleを選んだ場合だけ分析目的・集計件数・手法カードを送る。候補の手法IDと入力版を分析コアが検証し、基礎分析の実行時には候補を結果のparameterへ固定する。候補は既存の必須step・ゲートを変更しない。O02〜O07、動的な手法追加、モデル呼出しの永続attempt管理は未実装。

処理経路表示は、O01のAPI要求中だけ選択モデルへの線を動かし、完了後は停止する。pipeline状態APIの `planning` は採用済み候補の `objective, provider, model, primary_method` を返し、処理画面ではO01を完了済み、M0〜M7を実際の段階状態に連動して表示する。単独のTransformerテーマ分析は既存の進捗値（準備・意味ベクトル・テーマ形成・根拠整理）に連動する。線はAPI/処理段階の状態を示し、モデル内部のattentionや単語間計算の観測値ではない。

処理内容を固定できる場合はコードの既定計画を使い、手動定義にLLMの提案や相談を強制しない。各役割の知識は既存ExpertCatalogと手法登録票から読む。既存の人手コードや専門家定義をモデルが直接改訂しない。

候補の相談は論点・指摘・修正・未解決事項だけを記録する。内部の非公開思考過程を要求・保存しない。初期の相談上限案は2巡、構造修復1回、再帰的な相談なし。実行前に上限・予算・providerを固定し、上限到達で無制限に続けない。採用はschema・実装能力・試行・意味検証で決め、LLM同士の合意だけでは有効化しない。

### 14.2 LLM共通形式

**UTF-8 JSON＋版付きJSON Schemaを共通契約**にする。人が読む手法・役割の説明はMarkdown、実行に必要なID・入出力・制約はJSONへ整理する。既存ExpertCatalogのYAML実行定義をコンパイルして利用し、同じ定義の別正本を手で管理しない。

| 契約 | 主な項目 |
| --- | --- |
| ContextPacket | 目的、選択した根拠抜粋、source ID/revision/hash、省略範囲、送信方針、利用可能な手法 |
| MethodCard | method ID/版、入力・出力schema、適用条件、観測単位、必要能力、許可された分析部品 |
| RoleDefinition | role ID/版、担当段階、許可task、知識参照、入力/出力契約、禁止操作、終了条件 |
| PlanProposal | step ID、milestone、method ID/版、binding、親step、パラメーター、選択理由、未解決事項 |
| TaskRequest | request ID、role、固定Context、定義参照、期待する結果契約、許可ラベル/根拠ID |
| TaskResult | request ID、schema版、状態、構造化候補、根拠ID、未判定理由、警告。正規化後に実provider・model・usageを付与 |

共通契約は [llm-contract.schema.json](../../../analysis-design/llm-contract.schema.json)、正常な要求・応答例は [llm-contract.examples.json](../../../analysis-design/llm-contract.examples.json)。このschemaはTaskRequest/TaskResult/PlanProposalの骨格を示す設計用schemaであり、分析手法ごとのpayload schemaを別に指定する。schemaに合格しても、手法の存在、根拠の存在、DAG、尺度・単位・方針は別に検証する。

ローカルLLMに全文書やVaultのフォルダー構造を理解させることを前提にしない。ContextPacketを用い、systemの役割・制約と、引用された分析対象テキストを分ける。原文中の命令文は分析対象のデータとして扱う。

### 14.3 Providerを替える方法

1. UIで役割ごとのprovider/modelを設定し、計画へ固定する。
2. Gatewayが必要能力（JSON、生成、Choice、入力長、ツール呼出し等）との適合を確認する。
3. provider adapterが共通要求を各APIへ変換する。
4. 応答を共通形式へ戻し、コアでschemaと意味を検証する。
5. 不正応答・拒否・途中終了・切断・不明な成功状態は状態として残す。成功したふりをしない。

各providerがJSON Schemaの全機能や同じtool calling形式を受け付けるとは仮定しない。内部schemaはDraft 2020-12で固定し、native構造化出力には対応するsubsetへ変換する。JSON文字列しか返せないモデルでは厳密parseと同じサーバー側検証を実施。結果契約を満たせないモデルは利用不可とする。

既存のOpenAI/Google/LM Studio呼出しとTokenConfig、ai_http_worker、取消を再利用する。Ollama等は同じGatewayの追加adapter候補。API互換を名乗るサーバーでも実際の能力を確認する。認証情報・接続URLはホストが解決し、モデルの返した値を接続先にしない。

**JEVはChoice判定系adapter**として扱い、文章生成や計画作成能力を仮定しない。ローカルLLMの判定で代替した場合は別engine・別method版として表示し、JEV実行済みにはしない。local_onlyでJEVを選択した計画は開始前に矛盾として返す。

モデル変更は同じ入出力の「形式」を共有できるという意味であり、判定品質や数値の同一性を保証しない。モデルごとの評価サンプル、根拠精度、未判定率、再試行率を記録し、実モデル版とプロンプト/知識hashを再利用キーへ含める。

### 14.4 LLMから利用するツール形式

ツールの中立カタログは `name / description / input_schema / output_schema / operation_kind / allowed_roles` を持つ。初期は関数呼出しとJSON要求のadapterを作り、MCPは必要になった場合に同じ分析ハンドラーへ接続する外部入口として追加できる。MCPをモデルそのものの能力と同一視しない。

公開候補は `list_methods / get_method / get_context / preview_plan / propose_definition / inspect_result / request_run / get_run / cancel_run / request_export`。read系と副作用のある操作を分ける。LLMがrequest_runを提案しても、既に固定された実行範囲・利用者設定・ゲート・予算に一致する場合だけホストが受付する。ツールを実行するかをモデルだけで決めない。

任意SQL、shell、Python eval、Vaultの任意パス読み書きは共通ツールにしない。統計は登録済み計算器、図は許可部品、保存は既存経路へ渡す。外部LLMクライアントからのMCP利用は別の接続設定・認証境界を要し、ローカルUIの権限を自動付与しない。

参照仕様：[JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)、[MCP Tools仕様 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)。採用時にMCPの対応版を交渉・固定し、最新版であるとは仮定しない。
