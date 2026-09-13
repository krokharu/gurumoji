# LM Studio実機検証（2026-09-14）

> 更新：Qwen3-8Bの失敗原因は、保存されたGGUFの重み領域8KBの破損でした。配布元のSHA-256と一致するモデルに交換後、GPU全使用・Flash Attention ONで7チェックが成功しました。現在の使用モデルはQwen3-8Bです。[修復と再検証の詳細](QWEN3_REPAIR.md)。以下は交換前の比較検証記録です。

## 結果

ローカルのGPT-OSS-20Bで、エフォート指定4パターンとアウトライン・再校正・話者特定の7チェックが成功しました。アプリの使用モデルを`openai/gpt-oss-20b`に設定しました。`openai/`はLM Studio内のモデル名で、今回の処理はすべて`http://127.0.0.1:1234`で実行しています。

検証条件はRTX 5070（12 GB）、LM StudioのCUDA12ランタイム2.37.0、GPUオフロード70%、コンテキスト16384、並列数1です。モデルはダウンロード済みのMXFP4版です。

| チェック | 結果 | 所要時間 |
| --- | --- | --- |
| 自動でJSON応答 | 成功 | 1.18秒 |
| lowでJSON応答 | 成功 | 0.63秒 |
| mediumでJSON応答 | 成功 | 2.96秒 |
| highでJSON応答 | 成功 | 4.63秒 |
| 根拠付きアウトライン | 成功 | 18.04秒 |
| 再校正 | 成功・発話ID、順序、本文保持 | 43.25秒 |
| 話者候補抽出＋リンク再確認 | A＝田中、B＝佐藤 | 26.04秒 |

架空の日本語会話4発話を使用しました。実際の録音・保存済み会話は使用していません。長時間録音の性能や全内容の正確性を保証する検証ではありません。アウトラインには提案を「合意・決定事項」と強めて表現した箇所があり、内容の確認は必要です。

詳細は`runtime/lmstudio-gptoss-finishing-check.json`、再実行用スクリプトは`scripts/check_lmstudio_finishing.py`です。`PYTHONPATH=src`として実行します。

## Qwen3-8Bで判明した問題

- このモデルが公開する思考設定はON/OFFのみ。low/medium/highの直接指定はサーバーが無視し、既定値ONに戻していました。
- アプリを修正し、対応値を`/api/v1/models`から取得するようにしました。GUIは「思考モード ON／OFF」と「低／中／高／ultra」を表示します。このモデルではON時に既定の思考量を使い、GPT-OSSでは低・中・高をそのまま使用します。
- GPU実行では`Unexpected empty grammar stack after accepting piece: / (14)`が発生。Flash Attention OFFでは短い算数のJSON応答が通りましたが、実際の仕上げはエラーが残りました。ランタイム1.104.2との比較やバッチサイズ128への変更でも解消しませんでした。
- CPUでは算数の応答が成功しましたが、アウトラインは240秒でタイムアウトし、話者名も取得できませんでした。
- したがって、この環境のQwen3-8Bを「仕上げ正常動作確認済み」とは扱いません。比較用に変更したランタイム選択は元の2.37.0に戻しています。

モデル別の対応値取得は[LM Studio公式API](https://lmstudio.ai/docs/developer/rest/list)に従っています。

## 起動時の確認

LM Studioのサーバーが停止していたため起動しました。この作業環境には`ELECTRON_RUN_AS_NODE=1`があり、LM Studioの起動時だけ子プロセスから除いて起動しました。OS全体の環境変数は変更していません。

再ロードが必要な場合の検証済みコマンド：

```powershell
lms load openai/gpt-oss-20b --gpu 0.7 --context-length 16384 --parallel 1 --identifier openai/gpt-oss-20b --yes
```
