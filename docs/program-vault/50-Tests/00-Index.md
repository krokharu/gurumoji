---
note_id: index-50-tests
note_type: retrieval-index
title: 検証
summary: 検証の目的別入口。必要な責務を一つ選び、詳細へ進む。
status: current
updated: '2026-10-11'
tags:
- gurumoji/program
- gurumoji/retrieval
---

# 検証

必要な項目だけを選び、本文は選んだノートで読む。

- [[50-Tests/10-Storage/00-Index|保存・Obsidianの検証]] — この責務の資料と論点別入口
- [[50-Tests/20-Analysis/00-Index|分析・専門家の検証]] — この責務の資料と論点別入口
- [[50-Tests/30-Interface/00-Index|UIシナリオと受入]] — この責務の資料と論点別入口
- [[50-Tests/ui-design-evidence/2026-10-02/README|UI設計の証拠]] — 日付と対象版を固定した記録

## 2026-10-27 main 調査メモ

対象は main e33a91dda2e27a8226190c40c351f243213e20f5。実利用データは未使用。

- ゴミ箱への削除で segment_labels・segment_embeddings は保存されず削除されるが、版2の分析履歴は参照している。一時メモリ DB で参照欠落と復旧対象外を確認。復元後の過去分析の閲覧に影響する。
- 発話開始・終了秒の条件「等しい」は REAL の 1.0 と整数 1 を別型として不一致とする。一時メモリ DB で再現。
- 属性定義の型変更時、既存値の整合性を検証しない。一時メモリ DB で文字列から整数への変更後に不整合を確認。
- スライド設計保存 POST は CSRF ヘッダーを付与しないため、ブラウザーから 403 が予想される。静的調査のみ。
- 同一 data_dir で Knowledge Builder を使う場合、その state.sqlite3 等は通常バックアップに含まれない。一時ディレクトリで検証・復元後の欠落を確認。

画面での実操作、実モデル、全試験、実 Vault は未検証。修正は行っていない。

### ObusSQL 導入との照合

2026-10-27 時点、別 worktree `krokharu/ObusSQL導入` の HEAD 5f113448ef38293995ebee5cb61e3a5c3db97bfc と main の作業ツリーを静的に比較。上記5件の該当処理は変更されていない。ObusSQL は任意の管理ノート読取プレビューで、保存・バックアップ形式を変更せず、PostgreSQL 永続化や同期は未接続。導入だけでは5件の改善は確認できず、各問題の個別修正と試験が必要。ObusSQL 結合実行や実データでの検証はしていない。

### 2026-10-27 改善計画

1. 版2分析が参照するラベル・ベクトルを削除時にゴミ箱へ退避し、復元時にDBへ戻す。旧manifestとの互換、BLOB、競合時の安全停止を一時DBで確認。旧設計はベクトルを復元対象外としていたが、版2の固定分析が参照するため対象を拡張する。既に削除されたデータは自動復元しない。
2. 条件の数値比較を整数・実数間で整合させ、属性定義変更は既存値に矛盾する変更を拒否する。一時DBで境界と既存値の保護を確認。
3. スライド設計保存に既存のCSRFヘッダー方式を適用し、ブラウザー要求の条件を確認。
4. Knowledge Builder のバックアップ範囲と整合性を確認し、既存形式・空ディレクトリ復元との互換を維持する。一時DB・一時ディレクトリで往復検証。
5. 関連の回帰試験と差分を確認し、結果と未実施範囲を記録する。別セッションの変更と実データは変更しない。

### 2026-10-27 改善結果

- ゴミ箱manifestに版2分析が参照するラベルとベクトルを追加。新たな削除・復元で固定分析とBLOBを保持し、参照行の競合はロールバックしてゴミ箱を残す。旧manifestと既存SQL列は変更なし。旧削除ですでに失った行は復旧しない。専用一時DBで関連36件、および追加した復元・競合2件を確認。
- 数値の整数・小数を同値として比較し、真偽値と区別。会話属性は型・許容値の実質的変更で既存値と矛盾する場合に拒否。旧不整合は検査に残し、説明や尺度の編集は可能。話者属性は既存の整合検査契約を維持。関連41件を一時DBで確認。
- スライド設計保存を共通 apiFetch に変更。ヘッダーを含むDOM試験11件成功。実ブラウザー・実PowerPoint出力は未検証。
- Knowledge Builder は別プロセスがDB外にも書き込み、既存の共通排他がない。自動収録は未対応とし、画面・manifestの除外表示と停止後の手動フル退避手順を追加。一時ディレクトリの対象2試験成功。自動バックアップでは当該データは復元されない。
- mainと開発資料ブランチの対象差分で git diff --check 成功。実利用DB・実Vault・実モデル・全試験は未使用／未実施。別セッションの未コミット変更は保持。コミットなし。

## 2026-11-02 おすすめ前処理とNemotronLabs RE-USEの仕上げ比較

利用者依頼による実モデルの小規模比較。対象は `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と未コミットの現行コード。実行中に前処理・仕上げ関連4ファイルのSHA-256が変わっていないことを確認した。アプリのコード・設定は変更していない。

- 入力は公開JSUTの `BASIC5000_4501`〜`4508`。配布元 `FluidInference/JSUT-basic5000` の版 `cd13cc9c9fe70d8d4f62ffe6fbbb872aef79835c` に固定。8発話へ固定シードの白色ガウス雑音を0・10・20dB SNRで加え、24組を両方式へ渡した。16kHz mono、クリッピングなし、同じ正解発話境界で切り出した。
- おすすめは現行 `audio.py` のstandardフィルター。RE-USEはNVIDIA公式Hugging Face Spaceで帯域拡張なし。推論後に確認したSpace版は `f5218aea6b8cd29147e79a2532eb62a98167aff2`。匿名呼出しの途中失敗後、既存Hugging Face認証による正規呼出しで全6本が完了。ローカルとの速度比較はしていない。
- ASRは全48音声ともfaster-whisper 1.2.1 / base / CPU int8 / ja / beam 5 / VADなし / 前文脈なし。現行アプリ全体の実行ではなく、前処理の比較を目的に認識器と発話境界を固定した独立試験。
- 仕上げは現行Jev候補判定と `repair_recommended_segments` の中。Google設定モデルは個別応答の途中でReadTimeoutとなり、集計に含めていない。全条件をLM Studioの既存 `qwen3-vl-8b-instruct` に統一して実施。候補を4件ずつ処理し、中のモデル入力が通常の逐次処理と一致することを確認した。設定ファイルの書換えなし。

| 指標（24条件発話ずつ） | おすすめ | RE-USE |
| --- | ---: | ---: |
| 変更された発話の割合（句読点も含む） | 4/24 = 16.7% | 4/24 = 16.7% |
| 内容の文字列が変わった発話の割合 | 3/24 = 12.5% | 3/24 = 12.5% |
| 正規化後の文字変更率 | 0.72% | 1.91% |
| 仕上げ前CER | 48.77% | 54.78% |
| 仕上げ後CER | 49.07% | 56.79% |
| 仕上げでCERが改善／悪化した発話 | 0／2 | 0／3 |
| 全文認識欠落 | 0 | 0 |

変更発話率は0dBで0%対12.5%、10dBで25%対12.5%、20dBで25%対25%。補正率の一律低下は確認できず、10dBで変更発話率が低くてもRE-USEの仕上げ後CERは50.0%、おすすめは40.7%だった。変更が少ないことを精度改善と解釈しない。

CERは正解文に対するLevenshtein距離／正解文字数。NFKC正規化と句読点・空白除去を行い、かな・漢字・英字などの表記差は残している。文字変更率は仕上げ前後の距離／仕上げ前文字数で、正しく直った割合ではない。8つの同じ発話を雑音3条件で繰り返しており、独立した24録音の試験ではない。単独話者の朗読と合成雑音の1回測定で、会議・同時発話・残響・別ASR・Google仕上げ・反復変動・研究上の採用判断は未検証。

実験専用Pythonを `output/validation/reuse-finishing-20261102/.venv` に作成。アプリ・DB・Vaultは起動せず、実利用者の録音・本文・タグ・別名は未使用。APIの秘密値はメモリだけで使用し、生成物に含まれないことを確認。既存の未コミット変更を保持し、コミット・公開なし。

再実行スクリプト: [benchmark_reuse_finishing.py](../../../scripts/benchmark_reuse_finishing.py)。Git対象外のローカル実測資料: [条件とhash](../../../output/validation/reuse-finishing-20261102/manifest.json)、[条件別集計](../../../output/validation/reuse-finishing-20261102/summary.json)、[全体集計](../../../output/validation/reuse-finishing-20261102/aggregate.json)、[補正前後の本文](../../../output/validation/reuse-finishing-20261102/finishing.json)、[比較図](../../../output/validation/reuse-finishing-20261102/comparison.png)。全6条件・48行・24組の対応、分母、同一モデル、音声長、編集距離の既知例、資格情報の非混入を確認。通常の全試験は対象外。

### 2026-11-02 RE-USE選択と「高」への統合

利用者の追加依頼により、同じHEADと未コミットの現行実装へ `audio_preprocess=reuse` を追加。詳細選択欄と音声処理タイルの高から選択できる。強めも高として残し、メニューの選択値を実プリセット値に統一して強めとRE-USEの選択を混同しない。既定はstandardを保持。仕上げの高設定は音声強調と別責務のため変更していない。

- 研究音声を公式デモへ自動送信せず、専用WSL/LinuxのNVIDIA GPUでローカル推論する。モデル版は上記の公式重みと同じ `31f82f2efad1095034492f236e8dac9239ba713b`。公式ネットワーク・STFT関数を読み込み、公式長時間処理と同様の5秒・50%重複・Hann重み付き合成を行う。処理音声はASRにだけ使い、話者分離には原音系統を維持。
- 準備状態を画面と開始ハンドラーの両方で検査。未準備・推論失敗・中止時にstandardへ置換しない。区間前処理にも接続し、一時入力を削除。出力は16kHz mono PCM16と入力フレーム数を照合してから返す。既存WSLブリッジのパス変換・プロセスグループ中止を再利用。
- `setup_reuse.bat` / `.ps1` / `.sh` を追加。Linuxユーザー領域の作業フォルダーhash別venv・モデルと、Git対象外の `.venv-reuse/wsl-runtime.json` を使用。WindowsのWhisper環境・Haas環境を変更しない。モデル読込みと0.1秒のGPU実推論が成功してからreadyを書き込む。
- Mamba最新版2.3.2.post1はtriton>=3.5等を要求して対応wheelのPyTorch 2.8と一致しない依存解決を誘発したため、導入を止めた。公式torch2.8 ABI対応wheelがあるmamba-ssm 2.2.5へ固定。torch 2.8.0+cu128、triton 3.4.0、transformers 4.57.6、huggingface_hub 0.36.2で導入・GPU推論・pip check成功。以降の導入でもtorch/triton/transformersの条件を明示し、意図しない更新を防ぐ。

検証: 新規Python試験7件（未準備、変換・区間接続、失敗・中止伝播、出力長照合、別workspace拒否、短音声・末尾・重複合成）、既存audio_preprocess 7件、DOM 2件（高のRE-USE/強めの区別、未準備・準備済み時の開始可否）の計16件成功。実アプリのHTML生成、フォーム受付、準備状態API、Python/JS/Bash/PowerShell構文も確認。公開JSUT BASIC5000_4508を実アプリの関数から処理し、全体29,600フレームと区間9,600フレームのGPU実推論・有音出力・音声長一致を確認。出力hashはローカルの [real-inference.json](../../../output/validation/reuse-integration-20261102/real-inference.json) に保存。

実利用者の録音・DB・Vaultは未使用。アプリ起動・HTML検査は専用の一時データ領域で行い、利用中サーバーは再起動していない。今回のローカル分割推論を用いた認識品質の再比較、実会議・同時発話・長時間実録音、全試験は未実施。コード・ノート以外の未コミット変更を保持し、コミット・公開なし。


## 2026-11-02 配布用mainの混入監査

利用者依頼による静的監査。作業ブランチは `krokharu/transcription-finish-20261102`、HEADは `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486`。既存の未コミット変更を保持した。ローカルmainは `e33a91dda2e27a8226190c40c351f243213e20f5`、公開mainは `31f21c3e2574339659fc322caf6d8f535f21df16`。後者は `git ls-remote origin refs/heads/main` で一致を確認した。

- 公開mainの437ファイル、ローカルmainの435ファイル、作業HEADの442ファイルをGitオブジェクトから走査。現行mainに実利用者DB・録音・モデル・実認証ファイルはなく、資格情報パターンの検出は `config/tokens.example.json` の伏せ字見本のみ。Colabノートブックは出力0・実行番号0。実行用Software Vaultは216ファイル中、入口4ファイルを除く212ファイルが開発資料ブランチと同一blobだった。
- **配布前の除外候補**: `src/gurumoji/templates/index.html.recovered` は公開mainにも残る76,056 bytesの旧HTML。コードからの参照は検出されず、復旧用資産として開発資料側へ保全して配布対象から外す候補。今回の依頼はチェックのため削除していない。
- **ローカル認証設定の混入リスク**: 未追跡 `.codex/config.toml` の5行目にStitch用 `X-Goog-Api-Key` の直書きがある。環境変数参照・伏せ字ではない。現在のmain・HEADでは追跡されていないが、`.codex/` は `.gitignore` で除外されないため一括追加時の混入を防ぐ必要がある。秘密値は出力・記録せず、有効性の外部照会もしていない。
- 未追跡の `docs/program-vault/**/.obsidian/` には開いたノートの履歴等のローカル状態があり、除外されていない。未追跡 `ObusSQL/` は別Gitリポジトリで、追跡2,299ファイルにtests 464件、reports 722件、experiments 33件、harness 118件、obsidian 262件を含む。別リポジトリの指示は非公開を指定しており、丸ごと配布へ入れる対象ではない。Gurumoji側にはまだ追跡されていない。
- `runtime/`、`config/tokens.json`、`.env`、`.venv/` はローカルに存在する。存在とGit除外だけを確認し、本文や実利用者データは読んでいない。`.gitignore` はフォルダー全体をZIP化する際の除外を保証しないため、配布は公開mainの追跡ファイルを基準にする。
- mainから到達する全履歴の1,831 blob（約76.2 MB）のうち、テキスト1,773 blobを資格情報・認証URL・メール・個人パスのパターンで走査。認証候補は設定見本・試験用で、実キーは検出しなかった。ただし、旧tests・devtools・設計資料は履歴から取得可能であり、削除前の `docs/QWEN3_REPAIR.md` には実ローカルアカウントの絶対パスが残る。最新コミットのソース配布とGit履歴付き配布を区別する必要がある。履歴書換えはしていない。

作業中のGit対象候補はテキスト470件・バイナリ128件を確認し、テキストを走査した。入れ子のObusSQL本体・履歴、Git対象外の実データ・秘密ファイル内容、履歴中の58バイナリの画像内容、既公開Releaseの追加添付ファイルは未監査。パターン照合による検出なしは未知形式の秘密値の不存在保証ではない。アプリ起動・モデル実行・全体試験は対象外。

記録先ノートには監査前から4か所の末尾空白があり、`git diff --check` はその既存差分で失敗していた。今回の追記前後で同じ検出内容であることを比較し、新しい空白エラーがないことを確認した。アプリ・除外設定・認証設定は変更せず、コミット・push・公開なし。


## 2026-11-02 公開用release・developの分離

利用者は、過去データを継承しない新しい履歴で `public/release`（公開・配布用）と `public/develop`（公開版の開発用）を作り、既存main・開発資料を保持する案を選択した。両ブランチをGitHubへ新規push済み。共通初期コミットは `6fd6f890b532ea574791a9c45b77b16c19f8fafe`、treeは `2dbe90f6392900226c28e1aab186d4841806f2db`。GitHub Git Data APIでも `parents: []` を確認した。

- 基点は公開済みmain `31f21c3e2574339659fc322caf6d8f535f21df16` の追跡ファイル。作業ブランチの未コミット機能は取り込んでいない。隔離したGitリポジトリへ監査済みファイルだけを展開し、旧履歴・旧タグ・ローカル設定・実データをコピーしていない。
- 復旧用 `src/gurumoji/templates/index.html.recovered` を公開対象から除外。設定見本の認証値は空欄に統一し、`.codex/`・`.obsidian/`・別Gitの `ObusSQL/`・DB・秘密鍵・復旧ファイル等をGit除外へ追加した。元の認証設定や実利用者データは変更していない。
- 公開ブランチのREADME、開発手順、作業指示、Colab取得先を新ブランチに合わせた。実行用Vaultの入口3件とカタログのhashを更新し、内部開発資料へのリンクを公開用手順へ置き換えた。アプリ本体と実行用専門家・文献・スライド定義212ファイルは基点と同一bytes。カタログ215項目のhashと文字数が一致した。
- 両公開ブランチのCIで到達可能な履歴の秘密値・個人パス・禁止パス・ノートブック出力を検査。版更新・Release作成は `public/release` のみ、タグは `public/` 接頭辞で旧タグと分離した。公開用開発ブランチも内部試験資産を収録せず、必要な試験は従来の開発資料側で行う。
- `.gitattributes` でGitHub管理設定とエージェント用指示をソース配布から除外した。公開Gitは438ファイル、検証済み配布ZIPは433ファイル。ZIPには認証ファイル・ローカル設定・runtime・復旧HTML・入れ子の別Gitがないことを確認した。ローカル配布物は `output/validation/public-split-20261102/gurumoji-public-release.zip`。
- 秘密値を含まない8件の合成Gitリポジトリで、正常入力、ローカル設定、認証ヘッダー直書き、プロバイダー形式、個人パス、秘密鍵ヘッダー、削除済み開発資産、削除済みノートブック出力を確認し、すべて期待どおり許可・拒否された。Colabの取得関数はローカルGitでclone・pull・未コミット編集保持・別ブランチ拒否・実行中プロセス拒否を確認した。
- Python構文、ノートブック取得セルの構文、Workflow YAML、版整合検査を確認。既存のCRLFは定義のhash保持のため変更せず、`git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check` が成功した。既存のβ版にComing Soonがないという版検査の警告は保持し、製品版への変更はしていない。
- GitHub Actionsは [public/release](https://github.com/krokharu/gurumoji/actions/runs/41370200790)、[public/develop](https://github.com/krokharu/gurumoji/actions/runs/41370200939) とも成功。公開ブランチは [配布用](https://github.com/krokharu/gurumoji/tree/public/release)、[開発用](https://github.com/krokharu/gurumoji/tree/public/develop)。元リポジトリにも同名ローカル参照とupstreamを登録し、作業ブランチのHEAD・未コミット状態は変更していない。

既存リポジトリは公開設定であることを確認した。今回保全したmain・旧開発資料・旧履歴は引き続き他ブランチから取得できる。新2ブランチの履歴分離は、リポジトリ全体から旧資料の公開を取り消すものではない。この点は利用者へ明示した。既存ブランチの履歴書換え・削除・公開範囲変更はしていない。

アプリ起動、GPU・実モデル、実Colabブラウザー、全体試験、研究上の品質承認は未実施。実利用者DB・録音・本文・タグ・別名・秘密ファイル内容は使用していない。公開用2ブランチの作成以外に、既存mainや開発資料をpushしていない。既存の開発資料ノートの編集を保持して末尾だけ追記し、追記による新たな空白エラーがないことを確認した。


## 2026-11-02 公開専用リポジトリへの配置と説明整備

利用者が作成した [krokharu/Gurumoji-public](https://github.com/krokharu/Gurumoji-public) へ、監査済みコードと公開向け説明を配置した。作業開始時は空の公開リポジトリで、既存コードの上書きはない。配布用 `public/release` と開発用 `public/develop` を作成し、既定ブランチは `public/release`、About欄はアプリの日本語説明に設定した。

公開した最終コミットは `29ad6b8685ebef7d5741f6cb3bd7528224f99f65`。親なし初期コミットは `1f8061e54863689c553d85c5f88fd9fac569417d` で、旧履歴を継承せず、公開専用の3コミットだけを持つ。初期コミットの `parents: []` はGitHub APIでも確認した。基点は前回公開用に監査した `6fd6f890b532ea574791a9c45b77b16c19f8fafe` のファイルで、作業ブランチの未コミット機能や実データは取り込んでいない。

- READMEを公開利用者向けに書き直し、機能、対応環境、Windowsの導入、Colab、データとAI、設定資料、ブランチ、報告先を説明した。新たに `docs/GETTING_STARTED.md` と `docs/DATA_AND_PRIVACY.md` を追加し、更新・起動時の通信・保存先・バックアップの実対象と除外を実装に照合した。
- 開発・配布手順を新リポジトリへ合わせ、旧リポジトリの取得URLを残していない。Colabの取得先も新リポジトリに変更した。既存の音声感情分析ガイドで、セットアップコマンドを実在する `scripts/setup_emotion.bat` に修正した。
- `src/`・`config/`・`docs/program-vault/` の403ファイルは基点と同一bytes。専門家・文献・スライド定義212件を保持し、カタログ215項目のhashと文字数を確認した。公開Gitは441ファイル、ソースZIPは435ファイルで、ローカル認証設定・実runtime・個人設定・復旧用HTML・別GitのObusSQLを含まない。
- 公開前に資格情報・個人パス・禁止パス・ノートブック出力を履歴全体で検査し、最終履歴443 blobが成功した。Python構文、Workflow YAML、版整合、説明内の相対リンク21件を確認した。元からあるβ版とComing Soonの不一致警告は保持し、製品版への変更はしていない。
- Colabの取得関数で、実際の新公開リポジトリからcloneと更新ができることを確認した。外部AI・GPU推論・実Colabブラウザー・アプリ全体・研究上の品質は未検証。実利用者DB・録音・本文・タグ・別名は未使用。
- GitHubの設定変更には、連携ツールが既定ブランチとAboutの変更に対応しないためCLIを使用した。所有者krokharuの保存済み認証をこの操作のメモリ内だけに指定し、CLIの既定ログイン先・資格情報ファイルは変更していない。秘密値はログや成果物へ出していない。
- 版管理Workflowをβ維持指定で手動実行する案は、自動承認審査が版更新・タグ・Release等の副作用を理由に拒否し、実行されなかった。安全な代替として `contents: read`、資格情報保持なし、検査2コマンドだけの `public-check.yml` を追加した。版・コミット・タグ・Releaseの作成権限を持たないことを公開先ファイルで照合した上で、その検査だけを手動実行した。
- GitHub上の読取専用検査は [配布用](https://github.com/krokharu/Gurumoji-public/actions/runs/41371508577)、[開発用](https://github.com/krokharu/Gurumoji-public/actions/runs/41371510791) とも成功。開発用へのpushによる [公開範囲検査](https://github.com/krokharu/Gurumoji-public/actions/runs/41371463076) と [版管理Workflowの検査](https://github.com/krokharu/Gurumoji-public/actions/runs/41371463047) も成功した。版更新・タグ・Release作成の実行確認はしていない。

配布ZIPは `output/validation/gurumoji-public-20261102/Gurumoji-public-source.zip`、SHA-256は `7e9db502b1d1ea0374d80f0f44a62915f2cc0fba50c11dc4dbb555fcf4cc5d2d`。公開コピーの作業ツリーはclean。元の `krokharu/transcription-finish-20261102` はHEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と未コミット状態を保持した。旧リポジトリのブランチ・公開範囲・実利用者データは変更していない。開発資料側の既存ノートのbytesを保って末尾だけ追記し、新しい空白エラーがないことを確認した。


## 2026-11-02 手元開発版のObusSQL操作と機能停止表示の解除

利用者に反映先と範囲を確認し、「手元の開発版（現在の作業フォルダー）」と「全画面」の指定を受けた。対象は `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と未コミットの現行コード。公開専用リポジトリには反映していない。

- 開発版の `features.py` で既存Obsidian機能を有効化。分析画面の停止分岐・覆い・CSSバッジ、既定言語の停止分岐とdisabled、Obsidian監視の固定表示を除き、既存の実機能・実状態表示へ戻した。`src/gurumoji` の実行用HTML・JS・CSS・PythonでComing Soonは0件。既定言語の保存・再読込、分析画面の表示を実ブラウザーで確認した。
- 新しい `dialogs/obussql.html`、`static/obussql.js`、`static/obussql.css` を追加。「接続と処理装置」と「内部データ」から、接続診断、管理ノート一覧、最大16件の明示選択、検索を行える。結果は原ノート本文・行番号・版としてテキスト表示し、HTMLとして挿入しない。内部データの停止表示はこの実操作への入口にした。「表示」の無効ボタンは既存の通常設定へつないだ。
- 既存の `/api/obsidian/obussql`・`/notes`・`/preview` をそのまま使用。既存のHost・ローカルアクセス・CSRF・ID/hash・読取上限・原本再確認を維持した。DBスキーマ・保存形式・同期契約・認証設定を変更していない。取得結果をAIへ送信しない。MAF実行、PostgreSQL保存、永続索引、双方向同期は実装済みと扱っておらず、MAFの実診断結果は読取接続とは分けて表示する。
- 実行環境は当該作業フォルダーの `.venv/Scripts/python.exe`（CPython 3.12.9）と導入済み `obsipg 0.0.1.dev0`。試験ソースには当該作業フォルダーのsrcを明示し、テスト設定で開発資料側の古いsrcを優先しないようにした。一時DB・一時Vault、専用の自動割当ポート、独立したheadless Chromeだけで検証した。実runtime・実Vault・実録音・本文・タグ・別名・tokens.json・.envは使っていない。
- 既存 `test_obussql_integration.py` と追加の `test_development_connections_browser.py` は最終実行で **55 PASS / 1 SKIP**（32.27秒）。skipはWindowsの実シンボリックリンク作成権限不足。実パッケージ読取、HTTPのCSRFヘッダー、原本非変更、無効時に一覧を読まないこと、16件上限、HTML風タイトルの非実行、検索語変更やダイアログ再オープン後の古い応答破棄、失敗時の旧結果消去、既定言語の永続化と分析画面を確認した。試験中に対象12ファイルのSHA-256が変わらないことを確認した。
- 接続ダイアログのデスクトップ表示と幅390pxを画像で確認し、内側余白を調整。最終の実接続・非変更・狭い画面試験1件も成功した。ブラウザー試験は対象srcとブラウザーを明示したときだけ実行し、通常の試験へ暗黙にブラウザー起動を加えない。
- NodeによるJS構文確認とCRLFを許容した `git diff --check` が成功。READMEの版の強調記法が既存の版管理正規表現と合わなかったため、値と強調を保ちつつ正規表現が読める書式にした。版整合検査は成功し、Coming Soonがないβ版という警告は残る。開発版の有効化を製品版宣言と混同せず、版はβ0.46.1のままにした。
- `docs/OBUSSQL.md` とREADMEの導線を更新。Windows `run.bat` は未指定時に読取接続を有効化し、無効化には `MOJIOKOSI_OBUSSQL_ENABLED=0` を明示する。直接Python・Linuxから起動する場合は明示的な有効化が必要。現在の実アプリは再起動していないため、Python側の機能スイッチ反映には利用者によるアプリの再起動が必要。

検証資料は作業フォルダーの `output/validation/dev-obussql-20261102/` にある `verification.json`、`results.xml`、`tested-sources.json`、`task.diff`、`screenshots/obussql-connected.png`、`screenshots/obussql-connected-mobile.png`。試験コードは開発資料ブランチの `tests/test_development_connections_browser.py` に保存し、mainへ追加していない。既存の未コミット変更を保ち、対象箇所だけを変更した。実アプリ起動・研究上の品質・実モデル・全体試験・MAF/実PostgreSQL接続は未実施。コミット・push・公開なし。
