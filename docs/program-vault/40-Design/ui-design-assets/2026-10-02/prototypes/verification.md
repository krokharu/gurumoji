---
note_id: "ui-archive-40-design-ui-design-assets-2026-10-02-prototypes-verification"
note_type: "design-evidence"
title: "静止プロトタイプの確認記録"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# 静止プロトタイプの確認記録

2026-10-02 UTC / 基準HEAD `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`

## 成果物と役割

- `index.html`：SVG 8図をdata URIで内包した自己完結の静止レビュー資料。外部依存・JavaScript・通信・保存なし。図ごとのテキスト代替あり
- `{a,b}-{measurement,evidence}-{desktop,390}.svg`：1280px/390px、2案×2フローのネイティブvector図。title/descあり
- `rendered/*.png`：同じSVGをローカルInkscapeで描画した静止図。実アプリのスクリーンショットではない
- `comparison.md`：比較、根拠、点数の意味、実装前提、状態境界、採用候補と評価方法
- `synthetic-fixture.json`：人工の入力・測定・引用例。試験を実行したアプリの出力ではない
- `build-wireframes.py` / `build-index.py`：上記再作成用。アプリ側のファイルを編集しない
- `wireframe-manifest.json` / `validation.json`：寸法、出典HEAD、確認結果、成果物hash

## 実施した確認

| 確認 | 結果 | 何を証明するか |
|---|---|---|
| 現行ソース／CSS／templateの読取 | 実施 | 3モード、緑・紙色、測定・試行・引用契約の提案への対応 |
| Inkscape通常SVG→PNG描画 | 8/8成功 | 合成静止図がローカルrendererで表示できる |
| SVG/PNG寸法 | 8/8一致 | desktop=1280、mobile=390の元幅 |
| 全textの横境界検査 | 8/8成功 | 採用フォントによる文字幅がSVGの左右を超えない。縦や意味は別に目視 |
| 日本語・数値・注記の画素閲覧 | 8図実施、修正版を再確認 | 低忠実度図としてラベル、0/欠測、旧/現在版が読める |
| 独立担当の比較レビュー | 8図確認、修正1件 | 根拠2件表示に対しfixtureが1件だったため1件へ統一。研究上の数を見た目で補完しない |
| HTML構造／自己完結性 | 検査 | imgのdata URI、テキスト代替、重複IDなし、scriptなし |
| 合成fixture算術 | 確認 | 60/2/0の有効3・欠測1・平均20.7秒。除外1は別 |
| アプリGit差分 | 前後ともなし | この作業によるアプリソース変更なし |

初回描画ではInkscapeの通常設定directoryがread-onlyで作成できないという警告があったが、PNG生成は成功した。以後は既存の指定optionでcache/profileの書込み先を許可された`/tmp`内へ設定した。新しい権限付与・sandbox解除・ネットワーク回避はしていない。通常のローカルSVGレンダリングであり、ブラウザーやアプリへ接続していない。

## 未実施・この成果物では証明しないこと

- 現行GurumojiのV3ブラウザー操作、hit testing、focus復帰、Close/Cancel、API呼出し回数
- V4 accessibility tree・実スクリーンリーダー・日本語IME
- V5利用者理解、正しい初手、完遂率、速度、エラー発見の改善
- production CSSによるreflow、320px、200%/400%拡大、Windows実フォント描画
- 新しいtrial response、固定定義実行、採用gate、固定viewer、immutable履歴の実装
- 実モデル推論、録音精度、実データ、Vault保存、環境間配布、push/deploy

390px画像は固定幅の構成案であり、レスポンシブ実装の操作受入ではない。HTMLは構造検査済みだが、ブラウザーでレンダーしたとは記録しない。原25件の受入判定や、現行HEADのGUI合格へ繰り上げない。

## 再作成

Pythonでbuild-wireframes.pyを実行し、各SVGをInkscapeのexport-type=pngでrenderedへ書き出す。その後build-index.pyを実行する。Noto Sans CJKとPillowを使用。新しいフォントやソフトウェアをダウンロードしていない。

生成順序：SVG/manifest → PNG → index.html → 静止画の目視と構造検査。hashは最後の検査時点をvalidation.jsonへ記録する。
