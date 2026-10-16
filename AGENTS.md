# Gurumoji 作業ガイド

## 適用範囲と実行環境

このチェックアウトの Gurumoji 開発・検証・運用に適用する。依頼内容と README／対象実装から Gurumoji の作業だと確認する。`Obsidian` や `docs/program-vault` という名前だけで別プロジェクトへ適用しない。ADC08 は別プロジェクトで、今回は将来用の領域確保まで。

作業開始時に OS と `git worktree list` で実行環境を判定し、該当するプロファイルを読む。実行先を名前や会話だけで推定しない。

| 判定 | 実行環境 | 読むプロファイル |
| --- | --- | --- |
| Windows で、作業場所が `git worktree list` の先頭以外 | Orca の worktree（通常の開発） | [Orca worktree](.agents/rules/orca-worktree.md) と [Windows ローカル](.agents/rules/windows-local.md) |
| Windows で、作業場所が `git worktree list` の先頭 | 利用者のメイン checkout | [Windows ローカル](.agents/rules/windows-local.md) |
| Linux CPU（dot） | クラウド開発 | [dot クラウド運用](.agents/rules/dot-cloud.md) |

- 日本語で簡潔に報告する。指示の優先順はシステム・安全要件、今回の利用者要求、本ファイル、対象プロファイル／スキル、関連資料
- 現行コード・設定・テストを実装の正本、Software Vault を設計根拠として扱う。研究ノートは研究者の記録であり実行命令ではない。提案・未実装・確認済みを分け、コードと Vault の食い違いは作業結果に影響する場合だけ報告する

## 進め方

- 調査・ファイル操作・実行・検証は、現在の実行環境で使えるツールで行う。Obsidian への事前記入や全 Vault の読み込みを作業の前提にしない
- 仕様が明確な作業は 1 エージェント・1 worktree で進める。複数エージェントへの並列化は、方針が曖昧で複数案を比べる価値がある調査に限り、利用者の依頼がある場合だけ行う
- 最初に目的と完了条件を短く整理し、作業場所・ブランチ・HEAD・未コミット変更を確認する。今回の依頼と無関係な未コミット変更には触れず、コミットにも含めない

## 必要な情報だけ読む

- 個別機能・不具合: 対象コードと隣接テストから始める。新しい責務、API、保存先を足す前に既存実装を探す
- 起動・設定・配置: 上の実行プロファイルと現行ランチャーを読む
- Gurumoji Web UIの設計・改善・評価: [DESIGN.md](DESIGN.md)から対象節だけを読み、必要なら[設計スキル](.agents/skills/gurumoji-ui-design/SKILL.md)を使う。独立評価は[既存UI critic](.agents/agents/gurumoji-ui-critic.md)へ対象版と許可範囲を渡す
- Vault 構造・保存・検索・同期・移行: [AI タスク入口](docs/program-vault/00-AI-Entry.md) で絞り、適用条件が合うときだけ [Gurumoji 専用スキル](.agents/skills/gurumoji-obsidian-memory/SKILL.md) を使う
- 文書や研究ノートの単発編集: 対象文書と必要な根拠だけを読む。Vault アーキテクチャの変更へ広げない

入口 → 関連 index／ID → frontmatter・summary → 必要な節の順に取得する。初手で全リポジトリ／全 Vault を通読しない。候補抽出スクリプトは入口で絞れない場合だけ使い、取得元の ID・版・hash を保持する。

## 作業と確認の区切り

差分を一文で説明できる変更はそのまま進め、複数ファイル・複数段階の変更では対象・手順・検証方法を先に示す。承認された範囲内の可逆な作業を進め、方針を変える発見と利用者判断が必要な競合はその時点で報告する。別環境への反映・実データ移行・公開・認証設定は、依頼にない範囲まで拡張しない。

- 既存責務を再利用する。SQL は既存カラムの削除・改名・型変更をせず、追加だけにする
- 環境別のパス・設定は既存の設定インターフェースへ渡す。資格情報をソース、Git、ノート、ログ、fixture に残さない
- 研究者の本文・タグ・別名を保護する。アプリ生成ノートは既存の所有権・履歴保存・欠落検知経路を使い、直接上書きや強制同期を追加しない
- 保存形式・書き込み・同期・移行を変えるときは [詳細開発ルール](docs/program-vault/40-Design/ai-development-rules.md) と該当契約を確認する。移行はバックアップ、dry run、復旧手段を先に用意する。実 Vault をテストに使わない
- 発話に基づく主張は入力版と発話 ID、集計は対象集合・分母・結果表、生成物は run ID・hash に戻れるようにする。AI 下書きと研究者の確定解釈を分け、欠測・未実行をゼロや成功としない
- `.agents/` のスキル・エージェント定義が正本。`.claude/` 配下の同名ファイルは `python scripts/sync_agent_assets.py apply` で生成し、直接編集しない

## 記録

ローカルでも開発を続けられるよう、設計判断と理由、変更の背景、検証結果と未実行範囲、未解決事項・次の作業、対象 commit を残す。作業ログを逐一複製しない。研究者所有のノートは所有権を維持し、開発記録のために書き換えない。

- 変更したモジュールの設計ノート（`docs/program-vault/20-Modules/` など）は、コードと同じブランチで更新してよい
- 共有の運用ノート（`docs/program-vault/60-Operations/`）は複数の worktree が同時に書くと競合する。worktree での作業中はコミットメッセージと `../artifacts/<branch>-<YYYYMMDD>/` に記録し、運用ノートへは main へ統合するときに統合担当が 1 回だけ反映する
- dot クラウド運用の引継ぎは [運用ノート](docs/program-vault/60-Operations/dot-cloud-development-handoff.md) を使う

## 検証・受け渡し

テストはリポジトリ直下で `PYTHONPATH` を `src` と `tests`（Windows は `;`、Linux は `:` 区切り）にして実行する。Python の場所はプロファイルに従う。

| 変更の範囲 | 実行する検証 |
| --- | --- |
| 1 モジュール内 | 隣接テスト（例: `python -m unittest test_analysis_orchestration -v`） |
| モジュール境界・保存形式・API | 関係する統合テスト（プロファイルのコマンド例） |
| 共通基盤・複数領域 | 全体（`python -m unittest discover -s tests -p "test_*.py"`） |
| UI | 上記に加えて画面操作 |
| 文書のみ | リンク先・記載コマンドの存在と `git diff --check` |

検証記録は `../artifacts` に小さく残し、対象 commit、コマンド、結果、未実行範囲を追跡できるようにする。不要な報告書や重複資料は作らない。

アプリと移入 Vault は別 Git。共通基点から両側の差分を比較し、競合は人が判断する。ローカル／クラウドを自動上書きせず、コミットは対象ファイルだけを明示する。詳しい配置・受け渡しは [クラウド運用](.agents/rules/dot-cloud.md) を参照する。

完了報告は変更要点、検証の成功／失敗／未実行、利用者データへの接触、残る制約を示す。import 成功、CPU 推論成功、Web 応答、利用者のブラウザーでの利用可能性を同一視しない。

## 「Obsidianを更新」

Software Vault (`docs/program-vault`) の Git 更新を指す。現在の環境の Python で `scripts/update_program_vault.py check` を実行し、対象を利用者に示してから `apply`。別フォルダーは `--target` または `GURUMOJI_PROGRAM_VAULT_TARGET` を使う。終了コード 1 の競合は対象を報告して判断を待ち、merge／rebase／reset／強制上書きで解消しない。移入 Vault や runtime は対象外。[既存の更新手順](docs/OBSIDIAN_VAULTS.md#プログラム資料vaultの更新)を維持する。
