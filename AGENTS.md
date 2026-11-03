# Gurumoji main 作業ガイド

mainはアプリの引渡し用ブランチ。テストコード・架空データ・開発用ツール・設計書の全体は `archive/development-assets-20261016` に保持する。今回の利用者指定による分離であり、mainにそれらを再追加しない。

- 日本語で簡潔に報告する。最初に実行場所・ブランチ・HEAD・未コミット変更を確認する。
- 現行コードと設定を実装の正本とする。利用手順はREADMEとdocs、設計根拠・試験は[開発資料ブランチ](https://github.com/krokharu/gurumoji/tree/archive/development-assets-20261016)を参照する。
- `docs/program-vault` には実行に必要な専門家・文献・スライド定義だけを残す。不要な設計書として削除しない。これらの変更はhash・版・隣接試験を照合する。
- SQLの既存カラムを削除・改名・型変更しない。保存形式・同期・移行を変える前に、開発資料ブランチの該当契約を確認する。
- `runtime`、`.env`、`config/tokens.json`、研究者の本文・タグ・別名を保護する。資格情報をGit・ログ・fixtureへ残さない。
- 試験は一時DB・一時Vaultで実行する。実利用者データを使わない。別worktreeのPython・ポート・runtimeが共有されないよう明示する。
- コミットは対象ファイルを明示する。無関係な変更を含めず、force push・reset・cleanで競合を消さない。
- 重要な判断・検証結果・未実行範囲は開発資料ブランチの既存Software Vaultノートへ記録する。不要な報告書をmainへ追加しない。

開発と検証の入口は [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。アプリや実Vaultへの反映、公開、認証設定は依頼された範囲で行う。
