---
note_id: design-obsidian-sync-contract
note_type: interface-design
title: ID・更新・取り込み・APIの契約
status: proposed
updated: 2026-09-13
schema_version: 1
tags:
  - gurumoji/design
  - gurumoji/storage
---

# ID・更新・取り込み・APIの契約

2026-09-13???????????????AI?????????Vault????????????API??????????? [[30-Data/analysis-storage-v1]] ??????????????????????????????????????

本ノートのDB追加、API、保存パッケージは提案仕様であり、まだ実装されていない。現在のAPIは [[20-Modules/module-map]] を参照する。

## 識別子と版

| 識別子 | 規則 |
| --- | --- |
| `library_id` | DBごとに永続化するUUID。別DBで同じ会話IDが現れても混ざらない |
| `conversation_id` | 現在の `library_items.id` を維持 |
| `segment_id` | 保存済みIDを維持。表示順・本文のhashから毎回作り直さない |
| `speaker_id` | 台帳連携があれば台帳ID。未連携なら会話ID＋話者ラベルの組で識別 |
| `input_snapshot_id` | 解析入力の正規化JSONのSHA-256から作る。ファイルは不変 |
| `analysis_id` | 分析実行ごとのUUID。AI再生成・外部結果の新規登録は別ID |
| `method_id`, `method_version` | 手法と計算契約の版。[[method-rules]] に対応 |
| `artifact_id` | 成果物の永続ID。実際の保存パスとは分離 |
| `note_id` | 改名・移動しても変えない。ID重複時は同期を止めて競合として表示 |
| `block_id` | `s-`＋発話IDのUTF-8バイト列をhex化した値。元IDとの対応をmanifestへ記録 |

ObsidianのブロックIDは英字・数字・ハイフンの制約があるため、アンダースコア等を単に削除して衝突させない。リンクは `[[25-Sources/<snapshot-id>/part-0001#^s-...]]` とする。[Obsidian公式：ブロックへのリンク](https://help.obsidian.md/links)

入力スナップショットには、保存済み本文・ID・時刻・実効話者情報・会話目的・研究質問・条件・注釈・対象と除外理由・元データrevision・分析revisionを含める。手法のfingerprintは、入力スナップショットID、手法版、パラメーター、解析器・辞書・モデル・promptの版を含めて計算する。生成時刻や画面の表示順は含めない。

古いAI結果に生成情報がない場合は `unknown` を記録し、現在のモデル設定を過去の実行に補記しない。元データの完全な過去版が残っていなければ、保存された引用スナップショットのみを旧結果の根拠にする。

## ノートの所有権と命名

- 自動生成ノートには `managed_by: gurumoji`、人が編集するノートには `managed_by: researcher` を付ける。
- ファイル名は `conversation-<uuid>.md`、`analysis-<uuid>.md` 等の安全なASCII IDを基準とする。日本語名は `title` と `aliases` で表示する。
- 会話タイトルの変更で毎回ファイルを改名しない。外部の改名・移動は `note_id` と内容hashで検出する。
- 全ノート共通のプロパティは `note_id`, `note_type`, `title`, `schema_version`, `managed_by`, `created`, `updated`, `tags`。分析ノートは入力・手法・実行ID、実行状態、確認状態、更新要否を追加する。
- `run_status`（計算の完了）と `review_status`（研究者の確認）は別属性とする。AIは計算が成功しても研究上の確定結果にはしない。
- プロパティ名ごとの型を統一する。短い属性はYAMLに、パラメーターの構造や大量のIDはJSONに保存する。[Obsidian公式：プロパティ](https://help.obsidian.md/Editing+and+formatting/Properties)
- 自動ノートに直接加えられた変更を検出した場合は上書きを保留する。人の考察は専用ノートへ移す案を差分画面で示す。

## 原文とリンク

原文の文字列は入力JSONを正本とする。Markdownに出す際は文中の `[[...]]`、HTML、コードフェンス等が意図しないリンク・埋め込みにならないよう表示をエスケープし、原文自体は書き換えない。表の中へ発話全文を詰め込まず、発話ごとの引用ブロックを使う。

長い文字起こしは、初期値200発話を目安にページ分割する。ひとつの極端に長い発話は段落を分けて表示し、元発話への代表ブロックと文字範囲の対応を保持する。スナップショットのページ分割と対応表は一度確定したら変えない。

見解・引用のリンク先は生成時点の入力版に固定する。会話の入口だけが最新成功結果を指す。元データの分割・統合で発話IDが失われても、旧根拠を別の発話へ勝手に付け替えない。

音声確認用のアプリリンクは `conversation_id`, `segment_id`, `input_snapshot_id` を指定する新しい画面導線として実装する。最新本文との違いを表示してから再生位置を確認できるようにし、URIやリンクにAPIキーを含めない。PCの `127.0.0.1` URLはスマホから同じサーバーを指さないため、アクセス可能なアプリURLの端末別設定を用意する。

## 分析結果のmanifest

```json
{
  "schema_version": 1,
  "analysis_id": "example-analysis-id",
  "library_id": "example-library-id",
  "conversation_ids": ["example-conversation-id"],
  "input_snapshot_id": "sha256:example",
  "method_id": "speaker_characteristics",
  "method_version": "1",
  "execution_kind": "builtin",
  "run_status": "completed",
  "fingerprint": "sha256:example",
  "source_revision": 12,
  "analysis_revision": 4,
  "parameters_file": "parameters.json",
  "artifacts": [
    {
      "artifact_id": "example-artifact-id",
      "path": "tables/characteristic_terms.csv",
      "media_type": "text/csv",
      "schema_version": 1,
      "rows": 20,
      "bytes": 4096,
      "sha256": "example"
    }
  ],
  "evidence_file": "result.json"
}
```

これは値を省略した形の例である。実装schemaでは作成時刻、エンジン版、使用量、対象件数、入力・手法への参照を加える。hash・件数・ファイルサイズを検証する。CSVは既存互換のUTF-8 BOM付き・数式対策を継承し、配列などの完全な型はJSONで保持する。

## DBに追加する台帳（案）

| テーブル | 保存するもの |
| --- | --- |
| `analysis_method_definitions` | 手法ID・版・schema hash・実行種別・定義ファイルへの参照 |
| `analysis_runs` | 実行ID・会話集合・入力版・手法・状態・更新要否・最新採用情報 |
| `analysis_artifacts` | 成果物ID・実行ID・相対パス・hash・行数・サイズ・形式 |
| `obsidian_vaults` | Vault ID・用途・設定したルート・同期対象。秘密情報は持たせない |
| `obsidian_notes` | ノートID・Vault内相対パス・対象実体・生成hash・観測hash・入力版 |
| `obsidian_sync_jobs` | outbox、処理状態、進捗、再開点、対象版、失敗理由 |
| `research_note_imports` | メモID・提出hash・差分・適用先revision・採否・適用日時 |

`library_items` の既存JSON列や `analysis_insight_requests` は互換のため維持し、新台帳との対応を付ける。大きな結果本文を新台帳へ重複保存しない。スキーマ追加はmigrationの版とバックアップを伴い、旧データのIDを変えない。

## 書き込み・中断・競合

1. DBの保存トランザクションで、対象版を指定した同期outboxを記録する。
2. バックグラウンド処理が同一Vaultの書き込みを直列化し、入力版を取得する。
3. 新しい実行フォルダーをstagingへ書き、全ファイルのschema・hash・根拠リンクを検証する。
4. 新規の固定成果物と固定ノートを確定し、manifestと実行状態を記録する。
5. 現在の元データ版を再確認し、一致する場合だけ会話入口・最新結果ポインターを更新する。不一致なら過去版として保持する。
6. 索引は最後に更新する。書き込み済みhash・再開点から失敗を再試行する。

DBと複数Markdownファイルを単一トランザクションで同時更新できるとは扱わない。固定版を先に揃え、入口を最後に切り替える方式と回復journalで、不完全な結果へのリンクを避ける。処理の中止・失敗で直前の成功版を消さない。

利用者が変えたファイルは生成時hashとの比較で検出する。競合は別の生成候補として提示し、片方を黙って採用しない。ノート削除はDBデータの削除と解釈せず、登録解除／復元の選択状態として記録する。外部リンクやシンボリックリンク／ジャンクションを経由して設定ルート外へ書き出さない。

## Obsidianからの取り込み（範囲確定）

2026-09-13の利用者の指定により、対象は人が編集するノートの研究メモ・解釈・コード案とし、差分確認後に取り込む方式で確定した。任意のMarkdown本文を全文解析して確定注釈へ変換せず、テンプレートの明示的な項目と根拠参照を読む。

`プレビュー → 差分を選択 → 最新revisionを再確認 → 既存保存処理で適用 → 取り込み履歴を記録` の順で処理する。本文と話者情報の変更はこの取り込みの対象にしない。元のノートは保持し、DBは採用された値とその出所を管理する。

同じメモID＋内容hashの取り込みは一度だけ。変更後は別の提出版として扱う。承認待ちに本文・コードブック等が変わった場合はプレビューを更新する。存在しない発話・対象外発話・不正なYAML・重複キーは、理由を表示して適用しない。

## API案

| 用途 | 提案するAPI |
| --- | --- |
| Vault設定 | `GET/PUT /api/obsidian/settings` |
| 登録プレビュー | `POST /api/library/<id>/obsidian/preview` |
| 登録・同期開始／状態 | `POST/GET /api/library/<id>/obsidian/sync` |
| 同期中止 | `POST /api/obsidian/jobs/<job_id>/cancel` |
| 分析結果の固定保存／履歴 | `POST/GET /api/library/<id>/analysis/runs` |
| 固定結果・成果物取得 | `GET /api/analysis/runs/<analysis_id>`、`GET /api/analysis/artifacts/<artifact_id>` |
| 手法一覧・外部結果登録 | `GET /api/analysis/methods`、`POST /api/library/<id>/analysis/import` |
| ノート差分確認・適用 | `POST /api/obsidian/import/preview`、`POST /api/obsidian/import/apply` |

変更系APIにはリクエストIDと期待revisionを渡す。外部結果はバイト数・行数・schema・根拠・ファイル形式を検証する。保存先は登録済みルートから解決し、成果物APIに任意のOSパスを渡せる形にしない。既存の認証・ローカルパスアクセス制限を継承する。
