---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks-section-01
title: Gurumoji デザイン監査の独立反証チェック：Gurumoji デザイン監査の独立反証チェック
summary: Gurumoji デザイン監査の独立反証チェック。出典ノート「Gurumoji デザイン監査の独立反証チェック」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-adversarial-checks
source_path: 50-Tests/ui-design-evidence/2026-10-02/adversarial-checks.md
source_sha256: fec531750b3b1eeb8616de26b52688a81b740a197d67d9f5682156883db2fd50
source_body_lines:
- 1
- 49
split_on: '2026-10-11'
---

# Gurumoji デザイン監査の独立反証チェック：Gurumoji デザイン監査の独立反証チェック

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/adversarial-checks]]。必要な本文だけを取得する。


# Gurumoji デザイン監査の独立反証チェック

対象: `ddc23ab`（実装差分の直近 `59ebd24`）／初回検証 2026-10-02 18:26–18:33 UTC

## 結論

- **H1: 採用（P1候補）**。Transformer・AI見解・発話分類の個別実行入口は現行ソース上、通常のUI操作から到達できない。APIと保存済み結果の表示は残っている。「機能そのものを削除した」「保存済み結果も読めない」は不正確
- **H2: 採用（P2）**。`ui-screens.md`の「6段階・ブラウザーが順次API実行・永続pipelineは後続」という現行説明は実装と不一致。サーバーはM0–M7と永続台帳を持つ。ただし、より広い設計書の47成果物や7 LLM役割がすべて実装済みという意味ではない
- **H3: 採用（P1候補）**。手動測定の4入力欄は名称等のみ。実行規則は非表示の選択肢ではなく、存在しない5要素から `text / text_length / number / ratio / descriptive` にフォールバックする。自然文の説明は測定ルールへ変換されない。試行から採用へ確認待ちなしで進む
- **H4: 部分採用（P2）**。失敗状態の主見出しが「分析を実行しています」になる。結果ボタンが `completed` 限定なのも事実。ただし画面を抜ける導線があり、「失敗すると全結果へのアクセスを失う」は反証された

この判定は**ソース検証と隔離した実行プローブ**に基づく。実ブラウザーの画面操作・スクリーンリーダー・実際のレスポンシブ表示は未検証。Chromiumをsandbox維持で起動したが `socket() failed: Operation not permitted` で起動前停止した。制約の解除・別経路での回避は行っていない。

## H1: 個別実行の入口消失

### 成立する最小の主張

通常ロードされるスタイルシートを適用したUIでは、Transformerテーマの新規/再実行、AI見解生成、分類実行の対象ボタンは `display:none!important` になる。現行の「基礎分析」pipelineにはこれらの代替実行stepがない。

### 根拠

1. `templates/index.html:8–9` は `style.css` と `ai-effort.css` を通常読み込み。`style.css:2088–2093` はmedia queryの外にあり、次を非表示にする
   - `[data-transformer-run]`, `[data-transformer-cancel]`
   - `[data-insight-generate]`, `[data-insight-cancel]`
   - `[data-run-segment-classification]`
   - AI見解providerを含む `.content-ai-section .content-ai-toolbar`
2. 対象ボタンは実際に作成される
   - `analysis-content.js:184–188`: `startContentInsights` に結び付く生成・中止ボタン
   - `analysis-content.js:561–568`: `startTransformerAnalysis` に結び付く実行・中止ボタン
   - `analysis-method-view.js:254–264`: 分類実行ボタン。`app.js:8116–8120` がイベントを受ける
3. `analysis-content.js:839–845,1113–1119` の状態更新はdisabled、ラベル、cancelのhiddenを変更する。属性削除、重要度付きdisplay解除、別表示ボタンの生成はない
4. `analysis-execution.js:560–594` の統合開始はplan previewとpipelineのPOST。`analysis_core.py:80–100,311–338` の実行計画は participation、conversation_dynamics、manual_measurement。AIを使うO01計画相談も既存2手法の優先順位付けであり、見解生成/Transformerテーマ/分類実行の代替ではない
5. `templates/index.html:236` は「Transformerテーマ分析とAI見解は『内容・文脈検索』から個別に実行」と案内。`analysis-content.js:1126` にもAI見解の同じ案内が残る

### 代替・反例を調べた結果

- **desktop/mobile別入口:** 対象selectorに対するトップレベル重要宣言のため、同じ属性を持つどちらのレイアウトにも適用。mobile用 `.content-ai-toolbar` のgrid指定は `style.css:2008` にあるが、後続の非表示規則を打ち消さない。実画面の幅別テストは未実施
- **feature flag / 後続CSS:** src全体の該当selector、実行関数呼出し、style変更を検索。後続の解除規則や属性削除、条件付きの別入口は確認できなかった
- **別の表示ページ:** `app.js:6760–6769` ではAI見解を作る `buildInsightSummary()` は「概要」に入り、「内容・文脈検索」にはKWIC・分類・Transformerが入る。つまりAI見解は非表示問題に加えて案内先も不一致
- **API:** `web/analysis_routes.py:205–305` にinsights、transformer、classificationsのPOSTが存在し、`handlers/analysis_commands.py:180–199` が実サービスへ委譲する。APIやコンソールから呼べることは、人向けUIの代替入口にはならない。一方「backendも未提供」と断定してはならない
- **保存済み結果:** 読み込み・結果表示・出力経路は存続。分析を「新規実行できない」と「過去の結果を閲覧できない」に分ける

### テストが見逃す理由

`tests/test_content_browser.py:146–148` はDOMの対象ボタンをJavaScript `.click()`で直接押す。非表示要素でもプログラム的イベントは発火するため、テストが成功しても人が見つけてクリックできる保証はない。

受入条件は、保存済み合成データを開く → 案内されたtabへ移動 → 可視・enabledなbuttonへポインター/キーボードで到達 → 正しいAPIだけ1回送信、まで確認すること。provider、送信対象、保存前ブロック、実行中中止も同じ表示状態で確認する。
