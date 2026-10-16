---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research-section-06
title: GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：7 スクリーンショットと操作検証のループ
summary: 7 スクリーンショットと操作検証のループ。出典ノート「GurumojiのUI設計をAIに依頼するための調査と実践テンプレート」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-prompt-research
source_path: 40-Design/ui-design-research/2026-10-02/prompt-research.md
source_sha256: 7f17ce12573593c6bdc2e07d39f5f4251c5749bb84459f9eb17cde77cae80c66
source_body_lines:
- 360
- 414
split_on: '2026-10-11'
---

# GurumojiのUI設計をAIに依頼するための調査と実践テンプレート：7 スクリーンショットと操作検証のループ

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/prompt-research]]。必要な本文だけを取得する。

## 7 スクリーンショットと操作検証のループ

### 7.1 何を固定するか

比較ごとに、対象commit、ルート、入力fixture、ブラウザーと版、OS、viewport、device pixel ratio、ズーム、フォント、テーマ、アプリ状態を記録する。撮影直前にフォント、画像、状態遷移の安定を待つ。アニメーション、時計、ランダムデータは比較目的に応じて制御し、何を制御したかを残す。

Playwright公式も、OSやブラウザー等の違いで描画が変わるため、基準画像と同じ環境での比較を勧める。Windowsの日本語フォント・改行をLinuxの基準画像だけで保証しない。[P1](https://playwright.dev/docs/test-snapshots)

参考manifestの最小例。値は例示であり、本調査でこの撮影を実施した記録ではない。

```json
{
  "capture_id": "edit-unsaved-desktop-example",
  "status": "planned",
  "commit": "<verified full hash>",
  "route": "<actual route>",
  "fixture": "<synthetic fixture id>",
  "viewport_css_px": {"width": 1440, "height": 900},
  "dpr": 1,
  "zoom_percent": 100,
  "os": "<actual OS>",
  "browser": "<name and version>",
  "state": "unsaved edit",
  "fonts_ready": null,
  "reference_mode": "current baseline",
  "privacy_review": "synthetic content only",
  "captured_at": null
}
```

### 7.2 反復の順序

1. 合格条件と不変条件を先に固定する
2. 現行基準を撮影し、対象フローを操作する
3. 変更を小さく適用する
4. 構文・起動・関連テストを確認する
5. 同じ条件で描画し、重大な視覚差分を確認する
6. 状態遷移、戻る、再読込、保存の結果を操作で確かめる
7. 失敗の原因と影響範囲を絞り、修正する
8. 証拠が揃った条件だけ合格とし、残りを未確認として渡す

固定回数の反復を成功の代わりにしない。一方、同じ指示を変えずに繰り返して時間だけ使わない。原因を特定できない、実行環境が足りない、仕様の競合に人の判断が必要な場合は、確認できた範囲と依存を示す。

### 7.3 3種類の評価を混ぜない

|評価|証拠|失敗例|
|---|---|---|
|視覚|基準・変更後画像、実際のCSS値|重なり、階層不明、長文の切れ|
|操作|クリック・キー・戻る・再読込の記録|フォーカス消失、フィルター消失、動かないボタン|
|意味とデータ|表示とrevision/run/保存結果の照合|古い分析を現在の結果に見せる、失敗を完了扱い|

DOM要素へのJavaScriptの直接clickやイベント発火は、ハンドラーの検査には使えても、利用者が画面上で到達できる証拠にはならない。主要操作は見える要素への通常のマウス操作とキーボード操作で確認する。不可視要素への強制操作で受入テストを通さない。

同じモデルによる自己採点は、観察漏れや自己正当化があり得る。AI批評は問題候補の抽出に使い、仕様とテストで確かめる。異なるモデルを使っても独立性や正解が保証されるわけではない。
