# Dot / Orca の Git 受け渡し

共通リポジトリは https://github.com/krokharu/gurumoji、共有ブランチは `krokharu/dot-orca-git-share`。このブランチは公開済み `main` を基点に選別した候補で、元のローカル作業ブランチの履歴は含まない。コード・合成テスト・必要な設計契約を固定し、[ファイルmanifest](git-handoff-manifest.json)でSHA-256を確認する。長い私有プラン・研究データ・実DB・資格情報・未選別の作業packetは追加しない。

## 更新と受領

1. C0/Orcaは共有ブランチへ対象ファイルを明示してcommitし、通常のpushを行う。Issue #15または対応するPRに、完全なcommit SHA、変更ファイル、確認コマンドと結果、失敗／未実行、残件を短く記載する。元の私有ブランチ全体をpushしない。
2. Dotは通知されたSHAをGitから取得して確認する。自分の既存作業を確認し、変更があるcheckoutでは自動pull／merge／resetしない。必要なら専用のcheckoutを作る。受領はIssue #16またはPRへ `receiver / commit / checked / failed / not_run / next` を返信する。送信やfetchだけでは受領済みにしない。
3. C0/Orcaは同じIssue／PRからDotの受領とレビューを読む。実装ownerはIssue #17、共有ownerは#15、レビューownerは#16。開始前に固定SHAと編集対象を記録し、同じファイルへ重複実装しない。
4. 次回も同じ共有ブランチとPRを更新し、結果は新しい固定SHAへ対応付ける。共有成功と工程合格を分ける。mainへのmerge、force push、履歴書換え、実データ移行はこの受け渡しに含めない。

新しい環境での取得例（Git以外の実行権限やモデル許可は増えない）:

```text
git clone --single-branch --branch krokharu/dot-orca-git-share https://github.com/krokharu/gurumoji.git gurumoji-shared
cd gurumoji-shared
python scripts/check_git_handoff.py --expected-commit <通知された完全SHA>
```

既存の共有checkoutでは `python scripts/check_git_handoff.py --fetch --expected-commit <通知された完全SHA>` を使う。fetchはrefの更新だけで、checkoutを自動更新しない。`received=false` ならcommit・dirty・mismatchesを確認し、成果を退避せずに強制上書きしない。Gitの読取だけ可能なDotはcommitの取得とファイルmanifest照合を報告し、Python未実行を明記する。GitHub Issue/PRが双方の永続的な通知・受領経路であり、ChatGPTの会話は短い通知に使う。バックグラウンドの自動受信や監視は設定していない。

## この共有候補の限界

初期sourceは `b932fe11adf0881a3d7093c2761fbee930be0e56`。2026-10-09の継続では、#17のゼロ件セル欠落を `59e48b09625f1b4a5dffed993d4c8e920530f21e` で修正した。作者47成功、別担当の関連71成功・symlink1skipと独立68合成ケースで、固定入力から完全な型付き直積を確認して保存前に欠落を拒否することを検証済み。旧独立21 PASS / 1 FAIL / 2 PARTIAL、作者FAILED、工数UNKNOWNは過去の証拠として保持する。

通常Web入口は `1ba673f911034a686ba63661867a8922eead8d54`、画面導線は `855a16553729912f0643f44930760a85b584caa0`、独立検証の3指摘を直した候補は `bd04e601286037026afc0d1830b9c939efe782c5`。固定表選択・5方式・scheduler保存を接続し、consumer一致、初回GETの読取専用性、offsetの閉じた検証を修正した。独立再検証は関連159成功・追加20成功・UI38成功。1440/390pxのEdgeでpointer/keyboardを確認し、実Flask→Handler→合成Store→fresh読込を通した。実app全体のimport、実利用者・AT・実モデルは未実行。旧独立9 PASS / 3 FAILは履歴として保持し、合格は修正版だけに対応する。

Git受領validatorはDot PR #20の修正版 `d2dd0899d5dec394f87abf75fc08347cbd0417ef` のコードとテストを選別統合した。Windowsの別名・末尾dot/space・予約名・case重複等を拒否し、独立23ケース成功、同一ファイル別名9ケースを確認。作者テストはWindowsで7成功・symlink権限1skip、Dot Linuxで8成功。旧manifestは上書きせずC0が最新の公開対象から再生成する。PRの競合を解消するためのmain mergeや強制操作はしない。

図表描画はDot #21 / PR #22の `371bd8986651cbfca42e80a6a4c068855b197f53` を独立検証し、相互辺の数値ラベル重なり・Windows既存日本語フォント選択の2指摘でHOLD。作者18成功・独立10成功だけで解消としない。修正はDot担当、承認済みspec全体と固定保存データの照合・PNG保存／表示はOrca担当。型付き結果・本人記録の来歴修正は別の非公開作業checkoutで実装中で、この共有版には未移入。依存実行・図表保存／表示まで継続し、全体のENGINEERING HOLDを維持する。

Git書込の自動承認拒否が発生した際は、同じ操作の連続再試行をせず理由を確認する。今回は既に公開済みのmanifestと担当2ファイルの差分・hash・bytesを固定SHAで照合してDotが反映し、GitHubから読み戻しを確認した。各担当は次回も公開済みの内容、今回の差分、担当範囲、秘密情報の混入の有無を確認してから送る。

実モデル品質、全323発話、人の採否、実Vault、自然な容量境界などは未完了。文書内の未公開プランや履歴commitへの参照は出典表示であり、この共有版だけでは取得できない。必要な歴史的負例は技術ノートのfixtureとして同梱し、過去履歴を公開せずテストできる。Gitの固定版受領は、これらの工程合格や研究品質を意味しない。

## 受領コメント例

共有準備時の検証（Windows / Python 3.13、合成データのみ）: `PYTHONPATH=src python -m pytest tests/test_expert_skill_bindings.py tests/test_analysis_asset_bindings.py tests/test_statistical_expert_agents.py -q` は68成功・symlink権限による1skip。`node --test tests/test_analysis_fixed_run_ui.cjs tests/test_analysis_ownership_ui.cjs` は2成功。manifest86ファイルが一致し、CRLFを許容したdiff検査は成功。既存`PureWindowsPath.is_reserved()`の非推奨警告が発生。全体テスト・実画面・実モデルは未実行で、既知の#17不具合をこの成功結果で解消扱いにしない。

```text
receiver: Dot または Orca
commit: <完全SHA>
checked: Git取得、manifest <件数>一致、実施した検証
failed: <既知／今回の失敗>
not_run: <未実行>
next: <担当、Issue、編集対象、開始／待機>
```
