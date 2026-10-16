---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-13
title: Gurumoji 改善セッション：同日：通常のColabノートブックを更新
summary: 同日：通常のColabノートブックを更新。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 239
- 248
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：通常のColabノートブックを更新

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：通常のColabノートブックを更新

- 利用者のColab更新依頼により、通常の文字起こし・分析用`notebooks/Gurumoji_Colab.ipynb`とREADME、`tests/test_colab.py`を更新。実装commit `b3768a59232815c58bafaa7619a4b3345214b184`、基点`e69097453ec50551af49a8523690fde437744aa0`。Knowledge Control Centerの別ノートブックは対象外。
- セットアップはmainを明示したfast-forward更新と実HEAD表示を行う。アプリ/Ollamaが実行中、main以外、追跡ファイルに編集がある場合は変更前に停止する。既存ランタイムの利用者には、分析の停止・保存状態を確認し、終了セルを実行して最新ノートブックを開き直す手順を示した。reset/clean・変更破棄・実データ移行は追加しない。
- 旧処理はモデル一覧だけで準備完了としていた。新版は合成入力による短いJSON Schema応答を実行し、正常終了・JSON値、`/api/ps`のロード済みモデルと実入力枠を確認する。JSON不正/途中終了・未ロード・入力枠不足/未取得では停止し、ローカルLLM設定を切り替えない。起動セルも検証未完了のモデルでは開始しない。
- 入力枠の既定を16,384から32,768へ変更し、設定範囲4,096〜32,768を維持。GPU配置はsize_vramをGiBで表示し、0はCPUのみ、欠落は未取得とする。GPU使用率の連続監視や全量分析の成功保証ではない。メモリ負担と、設定値/実ロード値の違いは[Ollama公式の入力枠説明](https://docs.ollama.com/context-length)、[ロード済みモデルAPI](https://docs.ollama.com/api/ps)に基づく。既定モデル名は[公式タグ一覧](https://ollama.com/library/qwen3/tags)で確認し、変更していない。
- 最低3回後のCore判断、新規の型付き全件JSON/共有CSV、Google Drive有効時の`data/analysis_store`保持を説明。分析本体は共有実装を使い、Colab専用の停止制御・保存先・再計算経路を追加しない。
- Windowsの隔離保存先`output/colab-update-test`、`PYTHONPATH=src;tests`で`.venv/Scripts/python.exe -m unittest test_colab -q`を実行し、15件成功、1.278秒。全コードセルのcompileと出力/実行履歴なし、更新前のプロセス/編集保護、合成HTTP応答の不正・切断・入力枠不足、CPU/未取得値の保持、既存Colab用Web/securityの境界を確認。`git diff --check`も成功。
- 実Colab GPU、Ollamaの実モデル推論、apt/pipのインストール、Driveマウント、全量自律分析は未実行。テストのHTTP/Gitはmockで、既存Windowsのモデル・設定・利用者DB/Vaultへ変更なし。配布は既存origin/mainへのsource pushのみで、利用者のColabセッションを直接更新・再起動していない。
