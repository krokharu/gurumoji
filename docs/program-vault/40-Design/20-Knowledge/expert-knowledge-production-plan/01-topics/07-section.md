---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-07
title: 配布用専門家の知識・プロンプト制作計画：8. モデルとCodexトークンの使い方
summary: 8. モデルとCodexトークンの使い方。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 332
- 376
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：8. モデルとCodexトークンの使い方

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

## 8. モデルとCodexトークンの使い方

初期のローカル候補は、今回LM Studioで一覧確認できた`qwen/qwen3-8b`とする。日本語ログの分類、JSON出力、待ち時間、VRAMをP0で確認してから採用する。既存の他モデルの読み込みや解除を勝手に変更しない。[LM Studio公式API](https://lmstudio.ai/docs/developer/openai-compat)

A100の現行workerは`Qwen/Qwen3-32B-AWQ`を固定している。次の主候補はQwen公式の`Qwen3-Next-80B-A3B-Instruct-GGUF`のQ4_K_M版とする。公式掲載の配布ファイルは約48.4 GBで、Apache-2.0、総パラメータ80B・稼働パラメータ約3BのMoEである。48.4 GBはファイル容量であり、A100 80 GBでのVRAM使用量・長文context・同時実行可能数を保証しない。[Qwen公式80Bモデルカード](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF)。モデルID・commit・量子化ファイルhash・ライセンス・runtime版を固定して小さいJobから実測する。

| A100候補 | 役割 | 採用前に確認すること |
| --- | --- | --- |
| Qwen3-Next-80B-A3B-Instruct Q4_K_M | 公開資料のClaim生成・prompt候補作成の第一試行候補 | 単一GPUへの全層搭載、8Kから開始する入力長、1並列時のVRAM余裕、JSON適合、根拠支持、Job全所要時間 |
| Qwen3-Next-80B-A3B-Thinking Q4_K_M | 難しい適用判断の比較候補 | thinkingの出力上限と期限、審査独立性の不足。公式掲載ファイルは約48.4 GB [公式Thinkingモデルカード](https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking-GGUF) |
| 現行Qwen3-32B-AWQ | 動作基準・80Bが載らない場合の候補 | 同じ開発用問題・同じ根拠・同じ上限で80Bと比較する |

80Bは大きい重みを持つがMoEの稼働パラメータは約3Bであり、32B dense相当以上の品質をこの数値だけから推定しない。まずA100割当とGPU空き容量、ホストRAM、モデル取得先の空き容量を確認し、単一Job・8K入力・短い出力でロード、CUDA実行、peak VRAM、速度、出力schemaを記録する。次に16K/32Kへ段階的に増やす。CPU/disk offloadが必要、残VRAMが不足、期限内にモデル取得と推論を終えられない場合は80B Jobを投入せず、32B profileへ戻す。実文献の代表ケースで根拠支持・重大誤り・JSON適合・処理件数/分・GPU時間を比較し、第6節の合格基準を下げずに採用する専門家とJob種類を決める。

現行のJob ZIPは32Bのmodel IDとworker source hashを固定している。80Bを使うには別のmodel profile・prompt compiler・worker source版・Job契約を追加し、既存ZIPのモデル名だけを書き換えない。80Bの初回ダウンロードやロードは現行の発行時から55分の期限に含まれるため、事前準備とworker開始leaseを分離してから本番queueに加える。これらが未実装の間、80Bは検証候補であり、現行Notebookの5分pollが処理するモデルは32B-AWQのままである。

### ローカルLLMをA100でも動かす追加経路

RTX 5070のLM Studioで使う`qwen/qwen3-8b`の実体を調べ、同一のQwen3-8B GGUF量子化ファイルをColab A100でも動かす選択肢を追加する。LM Studioのモデル表示名だけで同一と判断せず、GGUFファイルのSHA-256、配布元commit、量子化、chat template、推論実装の版、thinking設定、context長、sampling設定を記録する。A100側の候補実装はCUDA対応の`llama.cpp`で、同じGGUFを指定する。[LM Studio CommunityのGGUFモデルカード](https://huggingface.co/lmstudio-community/Qwen3-8B-GGUF)、[llama.cppのCUDAビルド手順](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)。Hugging Faceの非GGUF `Qwen/Qwen3-8B`を使う案は別の実行profileとして扱い、同じ品質・出力と推定しない。[Qwen公式モデルカード](https://huggingface.co/Qwen/Qwen3-8B)

| 実行場所・モデル | 優先する作業 | データ境界 |
| --- | --- | --- |
| RTX 5070・既存LM Studio 8B | 時間・失敗の監視説明、private資料の候補作成、A100切断時の局所作業 | private原本・抽出物をローカルに保持。期限・採用・再試行の決定はPython |
| Colab A100・同一GGUF 8B（追加予定） | Colab送信許可のある小型Jobの大量処理、ローカル8Bとの品質・速度比較、開発用評価の候補推論 | Driveへ送信可能と審査された入力だけ。Colab側にモデル重みを取得して実行することはローカル限定資料の送信許可にはならない |
| Colab A100・80B Q4候補／現行固定32B-AWQ | 根拠付きClaim候補の生成。80Bが実測の品質・時間gateを通れば優先し、現行32Bは比較基準とする | 現行Jobは32B専用。80B用profileを別実装し、承認済みSourceだけを使用 |

実装は、(1) LM Studioが実際に使用したGGUFのID・ファイルhash・設定を棚卸し、(2) A100で同一GGUFを取得してhash照合し、CUDAで読み込む有限worker profileを追加、(3) 架空入力でRTXとA100のschema適合率、token量、待ち時間、GPU時間、VRAMを測定、(4) Colab送信可のJobだけをローカル管理役が8B/32B/80Bへ割り振る、の順に進める。80Bの適合検証と本番Job profileをA100 8Bの大量運用より優先する。GGUFを手作業でColabへ置いたことだけではJob処理可能とはしない。worker source・モデル・prompt版をJobへ固定し、結果を既存のgeneration/Commit検証へ接続する。モデル再取得時間を含む総所要時間で割当を判断し、A100が空いていても小さい単発Jobのために毎回モデルを読み直す運用は採用しない。

8Bを両GPUで使っても独立した審査役にはならない。同じ入力・同じモデル由来の誤りが相関し得るため、根拠支持と最終評価の合格判定は独立のrubric・原典照合・必要に応じた別モデルまたはSol/人の確認へ渡す。A100を使う場合もColabのGPU割当とランタイム寿命は変動する。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)

審査モデルは別設定にし、P0で生成候補との誤りの相関も確認する。独立した審査を通せない場合は合格扱いせず、該当する部分だけSolまたは人の確認へ回す。

コスト削減は次のルールで実現する。

- 文献抽出・索引・hash・schema・タイマーは通常のコード。文献要約・整理・評価の大量処理はA100、例外分類はローカルLLMを使う。
- Codexに全文PDF、全ログ、全専門家を一括で渡さない。実装チケットは対象ファイル・入出力・受入条件だけに絞る。
- Solには目的、差分、契約、失敗する具体例、必要な根拠、検証結果を渡す。入力は概ね4,000〜8,000 tokens、回答は1,500 tokens以内を目安にし、必要な追加読取は理由付きで行う。
- Luna/Solへの引継ぎにも送信区分を適用する。ローカル限定の本文・派生知識を自動送信せず、実装の再現には架空資料と構造化した失敗情報を優先する。
- サブエージェントへ長い会話履歴を丸ごと複製しない。既知の資料を再検索せず、版付きの短い引継ぎを使う。
- 同じ資料・抽出器・prompt・モデル設定の結果はhashで再利用する。更新した専門家と依存部分だけ再処理する。
- Lunaが同じ問題を2回修正しても受入条件を満たさない、保存・機密・評価の契約が変わる、重大な判断が食い違う場合にSolへ上げる。タイムアウトだけでSolを呼ばない。
- Codexの利用量が取得できる場合は入力・キャッシュ入力・出力を別に記録する。A100時間、ローカル時間、監修回数も記録し、API料金とCodex契約枠を同一扱いしない。

削減率は未計測なので約束しない。「通常制作1ジョブあたりCodex呼出し0回」と「同じ範囲・合格基準の成果物1件を作るための実測Codex使用量」で効果を確認する。プロンプトを評価して改善する考え方はDSPy・GEPAの研究を参考にするが、v1で新しい大型フレームワークの採用を必須にしない。[DSPy](https://arxiv.org/abs/2310.03714)、[GEPA](https://arxiv.org/abs/2507.19457)
