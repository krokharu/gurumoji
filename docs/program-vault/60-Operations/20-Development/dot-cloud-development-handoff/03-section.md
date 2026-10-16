---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-03
title: 'dot クラウド開発とローカルへの引継ぎ：2026-10-02: 25指摘の改善と独立受入'
summary: '2026-10-02: 25指摘の改善と独立受入。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。'
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 67
- 96
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-02: 25指摘の改善と独立受入

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-02: 25指摘の改善と独立受入

改善実装は `59ebd24f88a86415c3cb122c11ece9b03c9111fc` に確定した。UI-01〜10、分析A01〜14、同秒Vault台帳復旧V01の25指摘を対象にした40ファイルについて、検証前後のhash差分は0。コミット前snapshotを記録した `../artifacts/all-improvements-review/final-after-tests.json` の40ファイルと、この commit の Git blob の SHA-256 も一致する。

### 実装と互換性の要点

- UI: キーボード編集、開始条件と外部送信先の明示、削除取消と失敗表示、手動設定保護、CSVの非保存preview、競合時の未保存draft書き出し、環境別の保存先表示、保存フィードバックを改善。旧CSV APIの即保存互換を保ち、画面側はpreview→未保存編集→通常保存に分けた
- 分析: 全件エクスポートと制限理由、明示された参加者役割・参加人数と観測人数の区別、時系列に基づく重なり・無音、完全一致の語集計、DF分母、時間bin配分、極小p値の保持を修正。`participant_count` は実参加人数（不明はnull）、観測人数は `observed_participant_count` 等として区別するため、従来の0/1補完を期待する外部consumerは確認が必要
- 来歴・Transformer: 設定依存fingerprint、stale表示、出力元revision/hash、計測したtoken切詰め、モデルrevision固定、固定テーマ数の成立条件を改善。古い結果は保持し、不明な来歴を現在のhashで補わない。条件変更で再計算が必要になる場合がある
- Vault: `src/gurumoji/vault_registry.py` の `_write` で、同一bytesのノートでも台帳の確定を回復する。不要なノート再書き込み・履歴追加を避け、編集版の履歴保存と削除保護を維持する。台帳消失時の履歴pointer・entity設定・削除知識の一般的な復元まで保証する修正ではない

### 検証結果と未完了の区別

- 独立受入17件、Node合成DOM／関数契約11件、固定時刻Vault検証33件は成功。Vault検証は広範囲回帰にも含まれるので件数を重複加算しない
- 広範囲回帰は **900項目収集、browser名の24項目を除外、876項目選択**。pytest表示は **864 passed / 2 failed / 10 skipped / 24 deselected / 424 subtests passed**。failed2件は旧ブラウザーテストの起動引数を安全ガードが拒否した実行ブロックであり、計算・API・保存のassert失敗ではない。元のfailed表記をpassへ読み替えず、全体を「全成功」と呼ばない
- 10件のskip理由はWindows専用等としてログに保持。安全ガード導入前に中断したブラウザーを含む実行は未完了であり、合格件数へ加算しない。安全制限を緩めて再試行しない
- Python変更28ファイルのcompile、JavaScript変更4ファイルの構文、CRLF対応差分検査、`pip check` は成功
- 受入表は **15 addressed / 10 partial / 0 open**。全25指摘の改善実装は存在するが、UI10件は修正版の実Windowsブラウザー受入待ち。Node合成DOMやAPIの成功は、実画面、実端末のObsidian起動、スクリーンリーダー音声の合格を意味しない

根拠は `../artifacts/all-improvements-review/` の `SUMMARY-ja.md`、`acceptance-matrix.json`、`final-independent-results.json`、`final-node-tests.log`、`vault-independent-tests.log`、`pytest-nonbrowser-tests.log`、`pytest-nonbrowser-results.xml`、`final-static-checks.log`、`final-verification-metadata.json`。これらはローカル検証成果物であり、公開Gitへ生ログを一括追加しない。コード側の再現対象は `tests/test_analysis_metrics_regressions.py`、`test_transformer_provenance.py`、`test_four_vaults.py`、`test_vault_coverage.py`、UIは `test_ui_safety_browser.py`、`test_transformer_content_browser.py` と `tests/ui/` を参照する。

実データ、外部AI、追加モデル取得、認証を試験には使っていない。実E5の精度・クラスタ安定性、日本語の否定等の正解集合評価、AI主張の意味的な裏付け、発話単位の非独立性や多重比較の妥当性は別の検証課題として残る。

### 配置・受け渡しの状態

- **`59ebd24` のクラウド再起動は 2026-10-02 15:58:40 UTC に確認済み**。HTTP6経路が200、設定APIはcloud/Linux、HTMLはクラウド実行環境を表示する。tinyはキャッシュ済み、baseは未取得、Qwenは未準備、Hugging Face認可は未検証。ライブラリ0件、認証情報未設定、公開無効、runtime側のみのVault監視と移入1,398ファイルのhash一致を維持。根拠は `../artifacts/restart-verification-59ebd24.json`。実ブラウザーの描画・操作評価は別途ブロック中で、HTML取得を実画面の合格とはしない
- 長文パッチ経路とWindowsでのファイル転送は、内容の省略および拡張属性処理（`os.setxattr` 未対応）により完了していない。欠けたパッチを適用済みと扱わず、元のローカルcheckoutを保護した
- 受け渡しは **公開アプリrepoの別ブランチへpushし、ローカルでfetch・差分レビューする方法**が承認済み。現接続は対象repoの読取権限のみでpush権限がなく、書込み権限を持つ接続への切替待ち。GitHubへのpushとローカル反映は未完了で、この記録更新自体はpushを行わない
- 公開先の対象はアプリコードとSoftware Vaultの技術・設計記録。5つの研究用移入Vaultは専用remoteを持たない別Gitとして維持し、公開GitHubへ送らない。研究本文、会話データ、資格情報、実runtime、個人の非公開記録は公開用の変更へ含めない
