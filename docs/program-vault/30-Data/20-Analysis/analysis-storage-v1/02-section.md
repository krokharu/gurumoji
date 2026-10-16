---
note_type: reference-section
status: current
feature: analysis-storage
verified: 2026-10-05
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/program
- gurumoji/analysis
- gurumoji/obsidian
note_id: program-analysis-storage-v1-section-02
title: AI仕上げ・文章分析の保存契約 v1：ノートと根拠
summary: ノートと根拠。出典ノート「AI仕上げ・文章分析の保存契約 v1」の分割本文。
parent_note_id: program-analysis-storage-v1
source_path: 30-Data/analysis-storage-v1.md
source_sha256: 31b48be809af0922124aea608b12aec7e8f935b513ca61743fecd5d9e06bc885
source_body_lines:
- 66
- 89
split_on: '2026-10-11'
---

# AI仕上げ・文章分析の保存契約 v1：ノートと根拠

親索引・状態・確認版：[[30-Data/20-Analysis/analysis-storage-v1/00-Index]]。必要な本文だけを取得する。

## ノートと根拠

ResearchVaultの会話は`10-インタビュー/I###-<名前>/`にまとめる。概要は`I###-概要.md`、分析の入口は`I###-分析まとめ.md`、実行結果は同じフォルダーの`履歴/分析/<run-id>/`に保存する（`ObsidianLayout.note_path/analysis_dir`）。実行ノートから各`method-<id>.md`に移動できる。手法別ノートには見解、根拠、主要表の先頭10行・最大8列、分析単位・解析器、全件データ、限界を記録する。KWICの引用表示は先頭50件、AI仕上げの変更リンクは先頭100発話までで、全件はJSON／CSVに残る。旧`20-Conversations`・`40-Analyses`は移行前の配置。

引用は各インタビューフォルダーの`履歴/引用/<source-hash>/part-0001.md`に200発話ごとに保存する（`ObsidianLayout.source_dir`、`AnalysisStore.source_notes`）。旧`25-Sources`は移行前の配置。原文の文字列を維持してMarkdown用にエスケープし、発話IDはUTF-8の16進表現を使った`s-<hex>`ブロックIDに対応付ける。AIの根拠は生成当時の本文を使う。現在の本文・時刻・話者が異なる場合、リンクから現在の音声へ自動で進めず保存済み引用を案内する。

プロパティは単純なYAML値にし、大量のIDや入れ子の結果はJSONに置く。リンクはVault内のノートパスとブロックIDで生成する。[Obsidian公式：プロパティ](https://help.obsidian.md/properties)、[内部リンクとブロック参照](https://help.obsidian.md/links)

各CSV／JSONにはアプリで取得するリンクだけを付ける。端末固有の `file:///` パスは、PCのユーザー名などがVaultに残り、移動で切れるため書かない（OBS-12）。音声リンクとアプリからの取得にはサーバーの起動が必要。「Obsidianで開く」はローカルパスへのアクセスが許可された環境で表示する。[Obsidian公式：URI](https://help.obsidian.md/uri)

## AI仕上げと分析の規約

Whisper原文を先に保存し、Obsidianの専用作業ノートから仕上げを実行する。対象は各インタビューフォルダーの全文・アウトライン・操作ノートで、生成版は`履歴/仕上げ/`に残す。旧`15-Finishing`は移行前の配置。一般的な双方向同期とは分離し、人の既存ノートを自動更新しない。現在の作業版は概要・状態ノートから開く。操作、原文保護、重複実行防止、競合時の扱いは [Obsidianで文字起こしを仕上げる](../../../../OBSIDIAN_FINISHING.md) を参照する。

- 校正はID・発話順・話者・時刻を固定し、明白な誤変換と句読点を直す。要約・解釈・テーマ付与は別工程とする。長い単独発話も分割し、末尾まで処理する。失敗した分割片があれば校正結果全体を採用しない。
- 話者の修復を選んだ場合は校正前の本文を独立した入力に用いる。修復したラベルと原ラベルを変更CSVに残す。
- Jev比較を選んだ場合は、校正前の同じ発話をTypeSafeへ送り「修正が必要／修正不要」の二択だけを判定する。現行AIの変更有無と合わせた4区分、確率、確信度、モデル、使用量を`jev_review`と`ai_jev_comparison.csv`へ固定保存する。音声を判定した結果として扱わず、原音確認を必須の注意事項にする。
- 発話分類は、手動確定値とテンプレート規則・Jev・Transformerの提案を別レイヤーで保持する。発話種別、重要度、要確認度、機密らしさの0〜100値は確認用スコアであり、校正済み確率や法的な機密判定ではない。AI提案を手動注釈へ自動反映しない。
- 議題は各要点の根拠IDをサーバーで検証する。時刻を原文から計算し、`bullet_evidence` と `evidence` に根拠を保存する。既存の根拠IDがない議題には「旧形式」と表示する。
- AI見解は研究質問を優先し、1項目に1つの主張と根拠IDを持たせる。語の一致を合意とみなさず、少数意見・否定を保持する。人のコード・メモへ自動反映しない。
- 空結果、未実行、利用不可、簡易分割、古い対象、工程の一部失敗を `empty / not_run / unavailable / fallback / stale / partial` で区別する。
- 発話・話者・条件・注釈を更新すると旧実行を「更新が必要」にする。話者台帳の更新は保守的に全履歴を更新対象にする。固定JSON／CSV・過去引用は上書きしない。
- 分析準備の追加・更新・削除も、SQLiteトリガーで同じトランザクション中に対象会話の単独実行・比較実行を`stale=1`にする。ロールバック時は更新待ちへの変更も戻す。修正前の古い履歴を一括補正する処理はない。
