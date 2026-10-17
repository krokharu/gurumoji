# 開発・試験・設計書

利用者の指定により、mainは引渡し用、`archive/development-assets-20261016` は開発資料・試験の保存用です。

| main | 開発資料ブランチ |
| --- | --- |
| アプリ本体、起動・保守、利用手順 | テストコード・架空データ・評価プログラム |
| 実行時に必要な専門家・文献・スライド定義 | 完全なSoftware Vault、設計計画、ADR、検証記録 |
| Colabアプリのノートブック | 開発用コンソール、画面試作、エージェント用資料 |

アプリの実行定義は同じbytesを維持しています。古い設計ノートへの参照が必要な場合は[完全なSoftware Vault](https://github.com/krokharu/gurumoji/tree/archive/development-assets-20261016/docs/program-vault)を開いてください。

別の作業フォルダーに開発資料ブランチを取得して検証します。利用中のアプリのフォルダーでブランチを切り替えたり、利用者DBを試験先に設定したりしないでください。

```powershell
git fetch origin
git worktree add ../gurumoji-development archive/development-assets-20261016
cd ../gurumoji-development
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r config/requirements.txt -r config/requirements-dev.txt
.venv\Scripts\python.exe scripts/run_tests.py --output output/validation/tests
```

ブラウザー実操作と実モデルは通常の試験とは別に明示実行します。合成試験の成功、実モデルの契約合格、研究上の品質承認を同一視しません。

mainの整理はファイルの配布範囲だけを変え、利用者DB・研究者ノート・モデル・認証設定を移行しません。未実装・品質未承認の機能の状態も変えません。

応答・利用量・初期cacheの防御修正では、OpenAI `completed`、Google `STOP`、LM Studio `stop` を正常終端として確認します。欠落は `response_completion_unknown`、未知の値は `response_completion_unsupported` として採用を止めます。JSONとして読めることだけでは完了を証明しません。未対応providerの正常値は、実行契約を確認してから明示的に追加します。

利用量の欠測はnull、実測zeroは0です。未報告のtotalは作らず、集計の一部計測を明示します。同usage IDの同payloadは冪等、異payloadは `usage_conflict` で元の記録を保持します。既存のpayload hashがない記録も、同一性を証明できない場合は照合が必要です。ready cacheのbuilder／段階版が不一致または不明なら `initial_revalidation_required` を返し、保存済みcacheを更新・再計算せず保持します。過去成果物の閲覧と、現在条件での再利用を区別します。
