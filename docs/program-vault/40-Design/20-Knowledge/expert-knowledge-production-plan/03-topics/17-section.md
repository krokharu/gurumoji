---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-17
title: 配布用専門家の知識・プロンプト制作計画：A100定期実行とColab停止境界（2026-09-27）
summary: A100定期実行とColab停止境界（2026-09-27）。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 564
- 578
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：A100定期実行とColab停止境界（2026-09-27）

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

### A100定期実行とColab停止境界（2026-09-27）

- 実行中は60分ごとにRuntime/GPU/job queueの状態を確認し、80分ごとにDrive成果物のfile ID・size・SHA-256を照合して監視JSONへ履歴を保存する。ジョブがない場合も毎時の状態確認を続ける。
- 実際の専門家知識ジョブは、権利routeがColabを許可する場合に、P0 Notebookの固定revision Qwen3 workerからA100へ投入する。適格JobがDrive queueに存在しない場合は生成処理を始めず、毎時のRuntime/GPU確認と256x256 FP16の軽量health probeを記録する。
- 監視セルは1回あたり最大24時間で終了する。Colab側のidle timeout、VM寿命、GPU割当、利用枠は動的であり、実行継続を保証できない。Colab Pro+の連続実行も十分なcompute unitsがある場合に最大24時間である。停止後はDriveのmonitor JSONから履歴を引き継ぎ、Notebookを再実行する。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)

### 2026-09-27 07:28 UTC Colab A100 定期監視・本番worker更新

- Colab用Notebookとworker bundleを更新し、既存Drive file IDを維持したまま上書きした。Notebookは118,858 bytes、SHA-256 `eefa76fcef97c84766350962bf85432a0e9018841e4d5be1ab07263d57b233c0`。bundleは37,005 bytes、SHA-256 `7140aa4636c0bb1a680ca3d4b9e7b1e6b0f4aa7231c81192802f3c5ca8a62a7d`。両ファイルをDriveからraw取得し、全byte sizeとSHA-256の一致を確認した。
- Notebookは5分ごとにJob ZIPを確認してA100上で1件ずつ処理し、60分ごとにRuntime/GPU状態を記録する。キューが空でもA100割当中は毎時256x256 FP16 health probeを行う。80分ごとにDrive成果物のID・folder・size・SHA-256を別workerで監査する。長時間のDrive操作で監査が次の周期までに終わらない場合は遅延を記録するため、各間隔はbest-effortである。
- 本番workerはQwen3-32B-AWQのrevisionを固定し、Base専門家定義と1つの承認済み抜粋からdraft candidateを生成する。各Jobは発行時刻から最大55分、worker sourceのSHA-256とDrive上のJob file revision/作成者/最終更新者を検証する。承認Sourceの独立した正本はローカルに保持し、Job実行に必要な照合用レコードはZIPへ同梱する。Colabの返却結果は配布承認ではない。
- 24時間は監視loopの上限であり、実行中threadの強制終了ではない。model download/deserializationやDrive API呼出しは期限・周期を超える可能性がある。ColabのVM寿命・idle timeout・GPU割当も変動するため、接続維持は保証できない。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)
- 2026-09-27 07:40 UTCにDriveを再確認した。フォルダー内はNotebook、bundle、接続確認Notebookの3件のみで、監視JSON・P0結果ZIP・専門家知識Jobは見つからない。NotebookとbundleのDrive更新時刻はそれぞれ07:27:27 UTC、07:27:17 UTC。再接続後のRun allとA100処理は確認できていない。実A100時間・A100 token量・処理件数は0と断定せず「未計測」とする。
- 作業AIはCodex Lunaが実装と生成を担当し、SolがP4経路を読み取り専用で3回再監査した。ローカルLLM・A100推論は本更新では実行していない。Solを含む各モデルのtoken使用量は利用ツールから取得できないため数値を記録しない。確認はsyntax compileと`git diff --check`までで、テストは実行していない。
