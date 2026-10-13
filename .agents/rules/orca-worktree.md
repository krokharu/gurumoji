# Gurumoji: Orca worktree 運用

[AGENTS.md](../../AGENTS.md) の判定で Orca の worktree（Windows で、作業場所が `git worktree list` の先頭以外）と分かったときに読む。Windows 共通の事項は [windows-local.md](windows-local.md)。worktree が分けるのは Git 管理下のファイルだけで、Python 環境・ポート・実行データ・stash・`../artifacts` は他の worktree と共有されうる。

## 開始時

- `git status --short --branch` と `git worktree list` で、自分の worktree・ブランチ・未コミット変更を確認する。1 タスク 1 worktree 1 ブランチとし、他の worktree のファイルを編集しない
- 既存の未コミット変更が今回の依頼と無関係なら触らず、コミットにも含めない

## Python とテスト

worktree には `.venv` がない。メイン checkout（`git worktree list` の先頭）の `.venv` を使い、`PYTHONPATH` は自分の worktree の `src;tests` にする。venv に Gurumoji は install されていないため、`PYTHONPATH` が import 先を決める。

```powershell
$main = (git worktree list --porcelain | Select-Object -First 1) -replace '^worktree ', ''
$env:PYTHONPATH = "src;tests"
& "$main/.venv/Scripts/python.exe" -m unittest test_analysis_orchestration -v
```

## 起動と実行データ

- アプリを起動するときは worktree ごとに `MOJIOKOSI_PORT` を変える（7861 以降。`netstat -ano | findstr :<port>` で空きを確認）。`run.bat` の起動表示は常に 7860 と出るが、実際のポートは `MOJIOKOSI_PORT` に従う
- コード内に `http://127.0.0.1:7860` を既定値とする `app_url` が残っている。7860 以外で起動したときの分析結果内リンクは未確認として扱う
- `MOJIOKOSI_DATA_DIR`／`MOJIOKOSI_OUTPUT_DIR`／`MOJIOKOSI_BACKUP_DIR` が未設定なら、worktree 配下の空の `runtime/` が使われる。確認用の保存先は `output/<目的>` などに隔離して明示する。メイン checkout の `runtime/data` を使う場合は利用者に確認し、2 つの worktree から同時に起動・書き込みしない

## Git と共有資源

- bare な `git stash`／`git stash pop` を使わない（stash はすべての worktree で共有される）。作業の退避は WIP commit で行う
- コミットは対象ファイルを明示し、push は利用者の依頼がある場合だけ行う
- 検証記録は `../artifacts/<branch>-<YYYYMMDD>/` に置き、他の worktree の記録を上書きしない
- 共有の運用ノート（`docs/program-vault/60-Operations/`）へは、[AGENTS.md の記録](../../AGENTS.md#記録)に従い統合時にだけ書く
- マージ済み・放置された worktree の削除（`git worktree remove`）は、未コミット変更の有無を示して利用者が判断する。自動で削除しない
