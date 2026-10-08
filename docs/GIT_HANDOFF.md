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

sourceは `b932fe11adf0881a3d7093c2761fbee930be0e56`。G4c表処理はゼロ件セル欠落（IR-G4CT-01）によりENGINEERING HOLD。#17の修正はこの共有準備で実施していない。旧作者FAILED、独立21 PASS / 1 FAIL / 2 PARTIAL、工数UNKNOWNを成功へ変更しない。実モデル品質、全323発話、人の採否、実Vault、自然な容量境界などは未完了。文書内の未公開プランや履歴commitへの参照は出典表示であり、この共有版だけでは取得できない。必要な歴史的負例は技術ノートのfixtureとして同梱し、過去履歴を公開せずテストできる。

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
