---
note_type: reference-section
status: current
feature: web-ui
verified: 2026-10-03
verification_scope: source-and-synthetic-handler-tests
updated: 2026-10-06
tags:
- gurumoji/program
- gurumoji/ui
note_id: program-ui-screens-section-01
title: Web UIの画面構成と既存機能の対応：Web UIの画面構成と既存機能の対応
summary: Web UIの画面構成と既存機能の対応。出典ノート「Web UIの画面構成と既存機能の対応」の分割本文。
parent_note_id: program-ui-screens
source_path: 20-Modules/ui-screens.md
source_sha256: 848211ee88b8d60b2d3753a083c1936dd3ec29cdcf0f077c6bb1ea295598d8d9
source_body_lines:
- 1
- 21
split_on: '2026-10-11'
---

# Web UIの画面構成と既存機能の対応：Web UIの画面構成と既存機能の対応

親索引・状態・確認版：[[20-Modules/40-Interface/ui-screens/00-Index]]。必要な本文だけを取得する。


# Web UIの画面構成と既存機能の対応

2026-09-16にWeb UIの画面構造を作り直し、当時の版`2f13f98`に収録した。画面は同じAPI・保存形式を使う。2026-09-25にはHTMLを`templates/views/`の画面別テンプレートへ分けた。判断の背景は [[40-Design/50-Governance/decisions/02-topics/13-section#ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する|decisions#ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する]]、解消した問題は [[40-Design/30-Interface/ui-ux-issues/00-Index|ui-ux-issues]]。

2026-09-20の後続設計：多様な手法・実行結果を探す、比較する、追加分析へ渡すUI案を[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]の図7に追加した。比較の保存履歴・成果物・Vault再試行（UX-33）は先行実装済みで、分析画面を「結果を見る／比較する／分析を組む／データ・出力」へ全面整理する部分は未実装（ADR-118）。以下は現行UIの説明として維持する。

**導入履歴（2026-09-20）:** [[40-Design/10-Analysis/analysis-execution-ux-plan/00-Index|analysis-execution-ux-plan]]のPhase 1〜2で、自動／手動の計画パネル、当時の6段階実行画面、分析チップ、バックグラウンド継続、中止を追加した。当時のブラウザー逐次実行の説明は、以下の現行M0〜M7実装とは区別する。

**現行コードの照合（2026-10-02、HEAD `ddc23abe`／直近実装 `59ebd24`）:** `analysis_core.py`と`analysis_pipeline.py`はM0〜M7の要求・段階・状態をサーバー側で永続化し、`static/analysis-execution.js`はpipelineの作成・状態取得・中止・再試行APIへ接続する。分析内の表示モードは「自動分析／設定・手動分析／手法別」。初回範囲は参加・会話時間構造の記述集計、手動測定、固定JSON/CSV/ZIPなどで、47成果物・全LLM役割・推測統計・静止画像・SAV等の提供を意味しない。詳しい導入範囲は[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index|analysis-milestone-visualization-design]]の第18.7節と現行`CAPABILITIES`を照合する。基礎pipelineとTransformer・AI見解等の個別分析、外部AIを使う計画相談は別の入口・能力として扱う。

この照合はコードと既存の隔離検証に基づく。現行版の実画面・AT受入を済ませた意味ではない。手動定義の版整合や個別分析入口の不整合は[[40-Design/30-Interface/ui-design-implementation-plan/00-Index|ui-design-implementation-plan]]のW01/W02と証拠表を参照し、永続化の存在だけから版保証・操作可能性を合格にしない。

統計セクションは数値表だけでなく、記述統計の最小値・四分位・中央値・平均・最大値を示す分布図、カテゴリ別割合バー、統計検定の効果量バー、クロス集計の100%積み上げグラフを先に表示する。正確な値と前提条件を確認できるよう、従来の表は各グラフ直下の詳細表示に残す。

2026-09-22に[[40-Design/30-Interface/video-ui-redesign-plan|video-ui-redesign-plan]]（UX-35〜UX-42）を実装した。動画確認画面（`#/data/<id>`）の動画プレビュー幅を380〜480pxに拡大、動画枠の配色をライトカードに統一、発話リストを通常時コンパクト（チャット風タイムライン）・選択時フル展開に変更、再生中のハイライトと自動追従トグルを追加した。新規処理中画面（`#/new`）の進捗表示から計器・ログをアコーディオンに格納し、視覚的ノイズを削減した。

- **実装：** `src/gurumoji/templates/views/result.html`・`views/create.html`（処理中カード）、`static/app.js`（`renderMedia`、`syncMediaPlayback`、`renderSegments`、`playSegment`）、`static/style.css`（`.transcript-layout`、`.media-review`、`.segment`、`.progress-details-accordion`）
- **検証：** `tests/test_ui_defaults.py`、`tests/test_session_outline.py`、`tests/test_meeting_minutes.py`、`tests/test_speaker_registry.py`、`tests/test_transcript_formatting.py`、`tests/test_launcher.py`、`tests/test_application_lifecycle.py`
