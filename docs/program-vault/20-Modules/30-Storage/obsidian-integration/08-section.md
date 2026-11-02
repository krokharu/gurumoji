---
note_type: reference-section
status: current
feature: obsidian-storage
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/obsidian
note_id: program-obsidian-integration-section-08
title: Obsidian連携の現状構造と安全性：今後変更するときの注意事項
summary: 今後変更するときの注意事項。出典ノート「Obsidian連携の現状構造と安全性」の分割本文。
parent_note_id: program-obsidian-integration
source_path: 20-Modules/obsidian-integration.md
source_sha256: 3248688d4a6945a66bfa38de6b5a2475dcf5fb88a5a3f52b16573263e0e86f19
source_body_lines:
- 216
- 237
split_on: '2026-10-11'
---

# Obsidian連携の現状構造と安全性：今後変更するときの注意事項

親索引・状態・確認版：[[20-Modules/30-Storage/obsidian-integration/00-Index]]。必要な本文だけを取得する。

## 今後変更するときの注意事項

1. 新しい書き込み処理を作らない。まず [[40-Design/50-Governance/decisions/00-Index|decisions]] ADR-101 の方針（1つの書き込み関数、書き込み前の予定hash、conflict・missingの表示）に合わせる。
2. 人が所有するノートの全体を再生成して上書きしない。テーマと仕上げノートにはADR-109を適用し、関連情報・現在の参照を別の生成ノートへ書く。hash再確認だけを外部編集に対する排他保証と扱わない。`.obsidian`は新規Vaultの初回だけ書く（OBS-03、ADR-103）。
3. Vaultのパスは既存の算出元から得る。新しくパスを組み立てない。ユーザーのVaultを推測しない。
4. 判断できない状態では書かずに止め、理由を状態ノート・索引・ログに残す。対象は、Vaultが特定できない、同じ名前がある、YAMLを解析できない、`note_id` が重複している、revisionが一致しない、など。
5. 削除・移動・一括変換を追加する場合は、バックアップ、変更予定の一覧を出すDry Run、再開可能な記録を先に設計する。
6. 変更したら、このノートの該当箇所、[[40-Design/50-Governance/known-issues/00-Index|known-issues]]、[[50-Tests/10-Storage/obsidian-safety-test-plan/00-Index|obsidian-safety-test-plan]]、利用者向けの `docs/OBSIDIAN_*.md` を同じレビュー単位で更新する。

## 危険箇所の要約（G）

| ID | 重要度 | 内容 |
| --- | --- | --- |
| OBS-01 | 高 | テーマ同期が、研究者のテーマノートを所有確認なしで10秒ごとに再シリアライズ・上書きする |
| OBS-04 | 高 | 書き込み主体が5つあり、台帳が4つ、競合時の挙動も4通り |
| OBS-02 | 中高 | 仕上げノートのプロパティ更新に、読み込みから書き込みまでの間の変更検出がない |
| OBS-05 | 中 | `state.json` を失ったり片側だけ復元したりすると、作業台の初期ノートが上書きされうる |
| OBS-03 | 中 | `.obsidian` の設定をアプリが変更する（対応済み 2026-09-25：新規Vaultの初回だけ） |
| OBS-10 | 中 | Vaultの入れ子の痕跡があるのに、検出していない（対応済み 2026-09-26：`vault_registry.nesting_warnings` で警告。保存は継続） |
| OBS-06／07 | 中 | frontmatterの実装が複数あり、全体を再シリアライズする |
| OBS-09／15 | 中 | 監視の停止とスキップが見えない（OBS-09対応済み、OBS-15はスキップのログのみ。2026-09-25） |
| OBS-11／12／13／14 | 低〜中 | 削除後の表示、`file:///` 絶対パス、移行時の空フォルダー削除、パス長（OBS-11・12は2026-09-25、OBS-13・14は2026-09-26に対応済み） |

## 公開版からの解析実装の削除（2026-11-03）

利用者の「Gurumoji-publicの開発用設計・解析機能を削除」という依頼により、公開版だけを変更した。基点は `8f0fc49`、実装コミットは `3efefd653256981acae73b01b83d670298c01f6a`。[公開版PR #1](https://github.com/krokharu/Gurumoji-public/pull/1) は `public/develop` に、[PR #2](https://github.com/krokharu/Gurumoji-public/pull/2) は `public/release` に統合済み。配布版は自動更新後の `f96e815ce5bb307bc2a466f4110a1b8a1e3b1807`、`β0.47.1`（`public/v0.47.1-beta`）。実装版からの追加差分はREADMEと表示版だけで、配布版そのものでも公開範囲855 blobと版整合の検査成功を確認した。この開発資料側の解析実装や、利用中のアプリの未コミット変更は削除していない。

- 画面だけの無効化を解消し、解析・統計・テーマ分析・自律分析・スライド生成・音声感情モデル・事前アンケート集計と専用API／UIを削除した。公開版で未提供のObsidian連携・Knowledge Builderと関連ツールも除去した。解析配布コード105ファイルを削除し、変更全体は170ファイル、496行追加・48,426行削除。
- 文字起こしの編集APIは `web/transcript_routes.py`、入力分割・CSV安全化・時刻検証は `services/transcript_shared.py` に移した。既存SQLカラムは削除・改名・型変更せず、新規DBに解析専用テーブルを作らない。旧DBの表と履歴は保持し、存在する場合だけ既存の失効トリガーを維持する。旧感情メタデータは表示と文字起こしJSON出力で保持する。
- `analysis_store`、Vault、台帳、作業台の既存ファイルは削除せず、従来の整合バックアップ対象に残した。公開版にはそれらを再実行・同期するコードを含めない。`docs/program-vault` の保持指定216ファイルは基点と同じbytes。公開CIには現在版への解析実装の再混入検査を追加した。既に公開済みのGit履歴は書き換えていない。
- 公開版専用venvと一時DB・一時Vaultだけで7件の統合検証が成功。旧版で作ったDBの全既存カラムと保存済みrunの不変、編集競合、TXT／JSON／SRT等の出力、タグ・台帳、整合バックアップ、ゴミ箱復元、旧メタデータの出力、削除済みモデル指定を受けても実行しない受付を確認した。音声受付のモデル部分はテストダブルであり、実音声推論の成功を意味しない。
- Edgeの1365pxと390pxで画面遷移・保存済み文字起こし表示を確認し、JavaScriptエラー0件、解析APIへの通信0件。Python／JavaScript構文、版表記、差分整合、公開範囲853 blobの検査が成功。PR #1 の公開範囲CI・版管理CIも成功。実音声モデル・実LLM・全体試験は未実行。実利用者のDB・Vault・本文・タグ・別名・認証設定には触れていない。検証用ポート17864とサーバーは終了した。

再検証用資産はこの開発資料ブランチの `tests/public/test_analysis_removal.py` と `tests/public/analysis_removal_browser.cjs` に保持する。Python試験には `GURUMOJI_APP_ROOT` を公開版、`GURUMOJI_BASELINE_ROOT` を変更前公開版の隔離コピーに設定し、公開版専用venvで `pytest <開発資料>/tests/public/test_analysis_removal.py --confcutdir=<開発資料>/tests/public -o pythonpath=<公開版>/src -q -p no:cacheprovider` を使う。試験・検証記録を公開版へ追加しない。
