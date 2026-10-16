---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-06
title: Gurumoji 改善セッション：保存したソースから安全に再開する
summary: 保存したソースから安全に再開する。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 136
- 154
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：保存したソースから安全に再開する

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 保存したソースから安全に再開する

`Gurumoji_session_source_20261003.bundle` は Git の完全履歴で、アプリ／Software Vault と本セッションの専用branchを含む。仮想環境、node_modules、実runtime、媒体、研究Vault、資格情報を含めない。固定成果物やDBのバックアップではない。実データの復元は [[60-Operations/10-Data/backup-restore|backup-restore]] を別途使う。

1. 既存checkoutへ上書きせず、空の新しい場所へcloneする。bundleのdefault HEADに依存しないようbranchを明示する

   ```sh
   git clone --branch dot/gurumoji-eight-hour-20261003 Gurumoji_session_source_20261003.bundle gurumoji-review
   git -C gurumoji-review fsck --full
   git -C gurumoji-review status --short --branch
   git -C gurumoji-review rev-parse HEAD
   ```

2. `Gurumoji_session_evidence_20261003.zip` 内のcheckpoint manifestで、主branch HEAD・全体試験対象HEAD・未統合branchを照合する。最新のbranchが存在することと、主branchへ受入済みであることは別。source bundleのSHA-256もmanifestに記録する
3. 元のPC・別環境の未公開差分を先に保全し、共通基点から両側の差分を比較する。既存repoへreset／clean／強制上書きはしない。統合先や公開先をこのcloneだけで変更しない
4. Python環境は実行OSの手順で再作成する。WindowsのvenvをLinuxへ流用せず、認証やモデルを復旧済みと仮定しない。設定とCPU手順は `.agents/rules/dot-cloud.md`、Windowsは `.agents/rules/windows-local.md` を参照する
5. Pythonの標準試験は `python -m pytest tests/ -q -rs`。Nodeの局所probeは標準試験のwrapperから実行する。オフラインDOM統合は `tests/dom/README.md` の別コマンドで実行し、対象source rootを固定する。browser／Windows固有のskipを合格件数へ加算しない
6. 実runtimeに適用する場合は、旧workerの停止またはdrain・対応するdataバックアップ・保存形式の互換確認を先に行う。新台帳を旧binaryで読み書きするrollbackは未検証。今回のsource受け渡しはアプリ起動・deploy・実データ移行を自動で行わない
