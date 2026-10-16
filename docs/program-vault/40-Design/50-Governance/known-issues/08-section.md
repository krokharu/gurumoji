---
note_type: reference-section
status: current
feature: project-status
verified: 2026-09-26
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/issues
note_id: design-known-issues-section-08
title: 既知の問題点と改善方法（収束フェーズ）：追加調査：プログラム全体（2026-09-25）
summary: 追加調査：プログラム全体（2026-09-25）。出典ノート「既知の問題点と改善方法（収束フェーズ）」の分割本文。
parent_note_id: design-known-issues
source_path: 40-Design/known-issues.md
source_sha256: 93c0e1b715181e4d753e26636d16aa88dd9cf9b8c21d45e1ea6a76fb54c75414
source_body_lines:
- 135
- 156
split_on: '2026-10-11'
---

# 既知の問題点と改善方法（収束フェーズ）：追加調査：プログラム全体（2026-09-25）

親索引・状態・確認版：[[40-Design/50-Governance/known-issues/00-Index]]。必要な本文だけを取得する。

## 追加調査：プログラム全体（2026-09-25）

分析プログラムのリファクタリング後に、壊れた入力（終了時刻0、NaN、文字列の時刻、ID欠落・重複、`null`・数値の本文、巨大・負の時刻、300件の重なり）を分析APIと各エクスポートへ与えて確認した。落ちたのは次の1件だけだった。

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BUG-03 | 中 | 発話の本文が`null`や数値だと、その会話の分析とエクスポートがすべて500になる | `transcript_preparation.view`が`segment.get("text", "").strip()`を呼ぶ。キーがあって値が`null`なら`None.strip()`。既存の`*_話者分離.json`を取り込む`services/output_import.py`は発話を検証せずに保存する | 取り込んだJSONに1件あるだけで、その会話の分析画面・JSON・CSV・Excelが開けない | 本文を文字列として読む`segment_text`を準備画面・行データ・確定検証で使う。分析・3種のエクスポート・確定の回帰テスト | 対応済み（`8cdd22f`） | P1：優先 |

## 追加調査：Obsidian連携（2026-09-15）

- **確認元：** コードと、実環境の `runtime/data/obsidian/ResearchVault` を確認した。OBS-19は実環境のノート、OBS-20〜23とOBS-24の①は一時Vaultで再現した。
- **テスト：** 修正に合わせて回帰テストを追加した（`tests/test_obsidian_layout.py`、`tests/test_obsidian_finishing.py`、`tests/test_analysis_storage.py`）。
- **未確認：** OBS-24の④は、Obsidianが独自キーを消すかどうかを確かめていない。

| ID | 重要度 | 問題 | 根拠 | 影響 | 改善方法・受け入れ条件 | 状態 | 選別（追加調査） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OBS-19 | 中 | 手法別の表の中で、リンクの別名の区切り（縦棒）をエスケープしていない | `obsidian_layout.method_table`。実環境の `40-研究/分析手法/ai.md`・`I001-分析まとめ.md` に出ている | Obsidianで表の列がずれる | 表の中では縦棒をバックスラッシュでエスケープする（`vault_registry` と同じ書き方） | 対応済み（最新版`2f13f98`に収録） | P0：最優先 |
| OBS-20 | 中高 | 作業ノートを削除すると、2秒ごとに状態ノート・`state.json`・`interviews.json`・ナビゲーションを書き直す | `ObsidianWorkbench.poll_once` は、ラッチ前の `refresh_paths` で例外が出た場合も毎回、公開処理を行う。一時Vaultで、状態ノートのhashが毎回変わることを再現 | 同期ソフトの負荷が上がる。メッセージは「一意に確認できません」で、削除が原因だと分からない | ラッチ前の同じエラーは1回だけ公開する。ノートが戻れば `ready` に戻す。見つからない場合と重複の場合で文言を分ける | 対応済み（最新版`2f13f98`に収録） | P0：最優先 |
| OBS-21 | 中 | Obsidianのゴミ箱（`.trash`）にあるノートを、移動先として使う | `locate_note` がVault全体を `rglob` し、隠しフォルダーを除外していない。一時Vaultで、`work` が `.trash/…` に変わり、状態が `ready` のままになることを再現 | 削除したノートを入力にして、AI仕上げ・反映が進む | `.obsidian`・`.trash` などの隠しフォルダーを除外する（`obsidian_layout.find_notes` に集約） | 対応済み（最新版`2f13f98`に収録） | P0：最優先 |
| OBS-22 | 中 | インタビューのフォルダーをObsidianで移動・改名すると、元の場所に概要と研究メモを作り直す | `ObsidianLayout.register` はパスを固定で記録する。`update` は研究メモを作成し、`managed_note` は概要を作り直す。テーマ同期も元のフォルダーだけを読む。一時Vaultで再現 | フォルダーが二重になる。移動した研究メモのテーマリンクが無視される。分析の保存で、`obsidian_notes` のパスと食い違って競合になる | 概要ノートの `note_id` で移動先を探し、`interviews.json` の folder・hub・links・managed を更新して `moved_from` を記録する。`AnalysisStore.follow_moves` が `obsidian_notes`・`analysis_runs.note_path` の接頭辞を同じように書き換える。見つからない（削除された）場合は従来どおり作り直し、再探索は60秒に1回までにする | 対応済み（最新版`2f13f98`に収録） | P1：優先 |
| OBS-23 | 中 | 短い形式のテーマリンク（例：`[[働き方]]`）を認識しない | `sync_themes` の正規表現は `20-テーマ/` から始まるリンクだけを拾う。Obsidianの既定の新規リンク形式は「最短パス」。一時Vaultで再現 | 入力補完でリンクした研究メモが、テーマ関連に反映されない | Obsidianと同じく、Vault内（隠しフォルダーを除く）で名前が1つに決まり、`20-テーマ` 配下にある場合だけ解決する | 対応済み（最新版`2f13f98`に収録） | P1：優先 |
| OBS-24 | 低 | 監視処理の小さな問題：①変化がなくても `interviews.json` を保存する ②テーマ関連の警告が10秒ごとに出る ③`.obsidian` のJSONが壊れているか型が違うと、例外でナビゲーションの生成全体が止まる ④ブックマークの独自キー `gurumoji` が消えると、グループが重複しうる | `managed_note`、`sync_themes`、`configure` | 不要な書き込み、ログの肥大、設定の重複 | ①hashが変わったときだけ保存する ②同じ警告は1回だけ出す ③読めない・型が違う設定は書き換えずに警告する ④キーがなくても、先頭がホームの「Gurumoji」グループなら置き換える | 対応済み（最新版`2f13f98`に収録） | P2：後続 |
