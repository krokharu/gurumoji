# 公開版の開発と配布

| ブランチ | 用途 |
| --- | --- |
| `public/release` | 利用者へ配布する版 |
| `public/develop` | 公開可能なアプリ変更の開発・レビュー |

両ブランチは、監査した公開ソースから作った同じ初期コミットを起点とします。旧main・開発資料のコミットを親に持たず、利用者データ・認証情報・内部資料を履歴へ含めません。既存mainと開発資料は別管理で保全しています。同一リポジトリの他ブランチには独立したアクセス制限がないため、ブランチ分離で他ブランチの資料が非公開になるわけではありません。

## 開発する

```powershell
git clone --single-branch --branch public/develop https://github.com/krokharu/gurumoji.git gurumoji-public-development
cd gurumoji-public-development
python .github/scripts/check_public_boundary.py
python scripts/bump_version.py check
```

テスト・架空データ・開発専用コンソール・詳細設計書は既存の開発資料側で扱います。試験は一時DB・一時Vaultへ隔離し、公開するアプリ変更を検証します。実利用者の録音・本文・属性・研究ノートを転用しません。公開ブランチには内部の試験資産を追加しません。

公開可能な変更を `public/develop` でレビューし、確認後に `public/release` へ反映します。旧main・旧開発資料の履歴をmergeすると、削除済みの資料も公開履歴へ戻ります。必要な変更だけを監査して移してください。GitHub Actionsは両公開ブランチの到達可能な履歴とファイルを検査します。

## 配布する

```powershell
git archive --format=zip --output=../gurumoji-public.zip public/release
```

Gitの追跡ファイルだけから配布物を作ります。`.gitattributes` によりGitHub管理設定とエージェント用指示はソースZIPから除外します。実行中のフォルダー全体をZIP化すると、Git対象外の `runtime/`、`.env`、`config/tokens.json` などが混入します。

認証情報、実行データ、モデル、個人の `.codex/`・`.obsidian/` 設定、別リポジトリの `ObusSQL/` は配布しません。`docs/program-vault` の専門家・文献・スライド定義は実行に必要なため残します。

## バージョンの付け方

表示は `src/gurumoji/app.py` の `APP_VERSION` が正本です。

- `β`: 画面に「Coming Soon」が残っている間は付ける。なくなったら外す。
- 先頭の数字: 製品版になったら1にする。それ以降はメジャーアップデートで上げる。
- 次の数字(46など): 通常アップデートで上げる。
- 最後の数字(1など): 細かいパッチで上げる。

版はmainへのpushで自動更新されます（`.github/workflows/version.yml`）。`feat:` を含めば通常アップデート、`docs/chore/ci/test/style` だけなら据え置き、それ以外はパッチです。上がった版にはタグ（例: `v0.46.1-beta`）とGitHub Release（βは先行リリース）が作られます。βの付け外しとメジャーアップデートは、Actionsの手動実行（`release` / `major` / `beta-on` / `beta-off`）でだけ行います。画面に「Coming Soon」が残るのにβが付いていなければ検査が失敗します。

公開版のGitタグは `public/v0.46.1-beta` のように `public/` を先頭に付け、旧履歴のタグと区別します。版の自動更新とGitHub Release作成は `public/release` だけで行い、`public/develop` では検査のみ実行します。
