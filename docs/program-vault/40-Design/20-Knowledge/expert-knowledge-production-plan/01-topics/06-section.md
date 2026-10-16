---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-06
title: 配布用専門家の知識・プロンプト制作計画：7. ローカル管理とColabの接続
summary: 7. ローカル管理とColabの接続。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 250
- 331
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：7. ローカル管理とColabの接続

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

## 7. ローカル管理とColabの接続

v1は既存のGoogle Driveフォルダーを受け渡しに使う。フォルダーIDは設定値に置き、共有コードへ個人用IDを埋め込まない。実行するのは利用者が開始した有限のノートブック・バッチとする。

```text
ローカルPC
  Python管理プログラム ─ 状態・予算・取消・再開・採用
  LM Studio            ─ 異常の説明・不足の分類
  ローカルSQLite       ─ ジョブと制作履歴の正本
             │
             │ 確定した要求・成果物・完了記録を受け渡す
             ▼
Google Drive
  requests / events / artifacts / commits
             ▲
             │ 選択されたバッチだけ実行
Colab A100
  取得済み資料 → 知識候補 → 審査 → prompt候補 → 評価
```

Driveはファイル輸送として使い、SQLiteを同時共有して開かない。ローカル管理プロセス1つを状態の書き手にする。アプリ用のDrive API認証はP0で準備し、今回使えたCodexのDriveコネクター認証をプログラムがそのまま使えるとは仮定しない。

各要求には、`job_id`、`attempt_id`、単調増加する実行世代、入力hash、専門家・prompt・モデルの版、出力上限、期限、再試行上限、送信区分を含める。workerが受け取った要求は途中で差し替えない。

成果物は実行世代ごとの新しいファイルとして保存する。最後にファイルID・サイズ・hashを列挙した完了記録を発行し、ローカル側は全件検証後に採用する。Drive上の名前だけで同一性を判断せず、アップロード途中のファイルや古い実行世代の結果は採用しない。

監視の初期設定は次を基準に調整する。

| 管理対象 | 初期設定・動作 |
| --- | --- |
| 生存通知 | 60秒ごと。LLMを呼ばずworkerの状態を記録する |
| 通知が来ない場合 | 3分で`unknown`。通信遅延と計算停止を区別し、直ちに二重実行しない |
| 進捗 | 生存通知と別に完了項目数・最終保存位置を記録する |
| 再試行 | 一時通信障害等の分類済み失敗だけ最大2回。内容の不合格は再試行でなく改善周期へ戻す |
| 時間上限 | 操作別に設定。worker側も期限を確認し、期限前に新しい単位の開始を止める |
| 保存 | 論文・候補・評価バッチの区切りごと。長い処理は途中位置を保存する |
| ローカルGPU競合 | 空きVRAMを確認し、他の処理が使用中ならLLM監視を待機させる。Python監視は継続する |
| PCのスリープ・再起動 | 経過を復元してworkerと再照合する。古い生存通知だけで稼働中としない |

Colabが応答しない場合、ローカルから計算を停止できたと表示しない。期限・取消はworkerが到達できる境界でも確認する。再実行は古い試行の失効と新しい実行世代を記録して行い、遅れて到着した結果は隔離する。

ランタイム切断時は`waiting_for_runtime`として処理位置を残す。利用者が再接続し、環境・入力・モデルを照合した後に再開する。ブラウザーの座標クリックを本番運用の通信方式にせず、今回の画面操作は接続確認に限る。接続維持のための擬似操作を前提にしない。

Colabの最大稼働時間・アイドル時間・GPU割当は変動するので、固定時刻まで必ず使える計画は立てない。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)

### A100の実作業スケジュールとDrive照合

- A100は権利確認済み文献のClaim候補生成を優先する。現行workerは固定版Qwen3-32B-AWQで、Base専門家1人と抜粋1件から未承認候補を最大1件作る。文献選定、意味審査、prompt改善、評価のA100自動実行はまだ対応していない。
- 現行Notebookは5分ごとにJob ZIPを確認し、1件ずつ実行する。60分ごとにRuntime/GPUとキューを記録し、JobがないときA100なら256x256 FP16の軽量健全性確認を記録する。監視セルは利用者が起動する有限処理であり、キューが空でも新しい知識は生成しない。
- 現行Notebookの80分監査は、Colab内で追跡中のDriveファイルについてfile ID・名前・フォルダー・size・SHA-256を照合し、異常を監視eventへ記録する。ローカル台帳、schema、job/generationとの照合と、監査異常時の後続Job自動停止は未実装。ローカル側は結果受理時にJob世代・schema・hashを検査し、監査異常が見つかったキューの追加投入は人が止める。後続Jobを自動停止するfail-closed制御を継続運用前の実装条件にする。
- 監視セルは最大24時間で終了する有限処理とする。Colab Pro+は十分な計算単位残高がある場合、最大24時間の連続コード実行を案内しているが、他プラン・資源枠・バックエンドの都合で早期終了する可能性がある。接続維持は保証されない。常時稼働が必須なら、Googleが案内する専用VM/Colab Enterprise等へ移す。[Google Colab FAQ](https://research.google.com/colaboratory/faq.html)

### A100へ適切な指示を渡す実行計画

指示の単位は**1 Job ZIP = 1 Base専門家 × 1承認済みSourceの1抜粋 × 1実行世代**とする。ローカル管理プログラムがJobを作成し、Colabは渡された入力だけを処理する。個人のローカル論文・private由来の抜粋はDriveへ送らない。現行の自動監視だけではJobは生成されない。

| 順番 | 担当と指示 | 開始・完了の証拠 |
| --- | --- | --- |
| 1. 対象決定 | ローカル管理役が17専門家の開発用評価失敗・不足項目から、影響の大きい専門家と承認済み資料を選ぶ。最初は1専門家・1抜粋だけにする | expert ID、改善対象、Source ID、選択理由、開発用評価版をローカル台帳に記録 |
| 2. 送信前確認 | 出典と選択箇所を開き、版・anchor・訂正状態・route権を照合する。原本ファイルを取得できる場合は原本SHA-256を固定する。ブラウザ表示だけ取得できる場合は選択箇所の保持スナップショットをhash-boundにし、hashが原本バイト列ではないことと取得方法を記録する。どちらも確認できない主張は送信しない | 審査済みSource JSON、保持スナップショットに結び付いたexcerpt JSON、独立したapproved Source registry。最終評価の正答・秘密値・private派生内容を含めない |
| 3. Job発行 | LunaまたはローカルPythonが`prepare_colab_claim_job.py`で固定Base定義を読み、Job・世代・モデル/prompt/worker版・期限・入力hashを確定する。Job ZIPと独立したapproved Source registryのローカルコピーを別保存する | CLIが`ready_for_user_started_colab`とjob/generation、bundle SHA-256、deadlineを返す。CLIの`--output`は任意名を許すため、発行者が必ず`Gurumoji_Job_<job_id>_g<generation>.zip`を指定する |
| 4. A100投入 | Job ZIPを共有DriveのNotebookと同じフォルダーへ、ColabでDrive認可したGoogleアカウント自身で作成・最終更新する。利用者が[Colab Notebook](https://drive.google.com/file/d/1sN8Qwgt9uZ6liRB_tIc-aWEBydY1x16S/view)を開き、A100 High RAMを確認して初回は`Run all`し、Drive認可を完了する | Runtime monitor JSONにA100割当、job開始・終了、失敗理由を記録。キュー確認は5分ごと、状態確認は60分ごと、Drive照合は80分ごと（遅延あり） |
| 5. 結果受理 | `Gurumoji_Result_<job_id>_g<generation>.zip`をDriveから取得し、ローカルに保存したregistryを使って`accept_colab_claim_job.py`で検査・一度だけ受理する | job/generation、入力・成果物hash、Source/anchor、期限、schemaが一致したCommit。返却Claimは`candidate`であり承認済み知識ではない |
| 6. 審査と改善 | 根拠箇所への意味的支持、適用条件・例外、重複・矛盾・権利を独立に審査する。不足なら失敗を分類し、別の抜粋またはprompt改善へ戻す | Claim採否の根拠、開発用評価差分、A100時間・token実測または`未計測`、次のJob判断を台帳に残す |

現在の`--ttl-minutes`は**Jobをローカルで発行した時刻から最大55分**であり、Colabでの実行時間だけを数える値ではない。初回モデル取得・Drive手動アップロードがこの時間内に収まらなければ期限切れになる。発行はNotebook起動・Drive認可・モデル準備の見込み確認後に行い、期限切れJobを編集・再アップロードして使わない。継続運用の前に、ローカルqueueからの安全な発行・Drive転送、workerの開始lease、モデル準備時間と推論時間の分離を実装する。現行の最大55分はJobごとの上限であり、途中checkpointを持つ長時間バッチではない。

本番指示を出す前の最小実行順は、P0合成roundtripの結果ZIPをDriveから取得して`accept_p0_colab_roundtrip.py`で一度受理すること、次にColab送信可で原本・抜粋・registryが揃った公開資料1件で実Jobを作ること、最後にその候補を独立に審査することとする。DriveにNotebookとP0 bundleだけがある状態では知識生成は始まらない。公開資料でも原本本文を未取得なら、要旨を本文確認済みとしてJob化しない。

ローカル管理役は各Jobの前に、`expert_id`、不足項目、`source_id`、`anchor_id`、抽出・権利審査版、期待する成果物、拒否条件、評価版、予定A100時間を短い作業チケットに固定する。A100へ渡す本文はこのチケットで指定された抜粋だけとし、別の論文を任意に探索・追加しない。返却後は次のように振り分ける。

| 発見した問題 | 次の指示 |
| --- | --- |
| 根拠の支持不足・Source訂正 | 候補を採用せず、原典・anchorを再確認する。別抜粋が必要なら新Job |
| 抽出失敗・古いhash・権利不明 | ローカル側で抽出・権利記録を修正するまでA100へ送らない |
| 適用判断の失敗 | 同じ資料の無条件な再生成を避け、開発用評価で知識欠落かprompt欠陥かを分ける |
| timeout・Drive障害 | 旧世代の結果を採用せず、入力と状態を照合して新しい実行世代を作る |

P6の大量展開では、Job優先度を「配布停止につながる誤り > 必須知識の欠落 > 開発用評価での頻出失敗 > 重複整理」の順にする。各専門家の開発用評価版・未達項目・既存Claim hashを固定し、同じ入力hashの再生成を避ける。Job完了後にローカル管理役が次の1件を選び、期限切れ・通信障害は同一世代の二重採用を避けて新しい世代で再開する。1専門家あたり最大5改善周期・1周期あたり追加資料最大5件という第6節の上限を守る。

後続のA100指示型は`claim_generation`、`evidence_review`、`prompt_proposal`、`development_evaluation`を別契約で実装する。審査役には生成履歴を渡さず、最終評価の正答をDriveの生成Jobへ含めない。各型に入力schema、出力schema、モデル/prompt版、採用gate、失敗時の処理を定め、単独で実行・検証できるまで「A100審査済み」「17専門家評価済み」と報告しない。
