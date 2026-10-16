---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit-section-06
title: Gurumoji 現行デザイン監査と実装可能な改善計画：9. DESIGN.mdの実用的な構成案
summary: 9. DESIGN.mdの実用的な構成案。出典ノート「Gurumoji 現行デザイン監査と実装可能な改善計画」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md
source_sha256: 29fdac89e90f723f623c7a6e660b4bd780c77d975d1bfbc6d6ada363dc6aeaff
source_body_lines:
- 236
- 269
split_on: '2026-10-11'
---

# Gurumoji 現行デザイン監査と実装可能な改善計画：9. DESIGN.mdの実用的な構成案

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-audit]]。必要な本文だけを取得する。

## 9. DESIGN.mdの実用的な構成案

巨大な既存設計書を複写するのではなく、普段の実装時に参照できる短い正面入口にする。詳細は今回の監査・一次資料・既存契約へリンクする。

1. **目的・範囲・現在版**: Gurumojiが支援する研究作業、対象commit、初回実装能力、未提供、受入待ち。DG-13
2. **守る設計原則**: 入力所有権、候補と確定、根拠・分母・版、閲覧で実行しない、現実の保存先。原25件、AGENTS、ADR-118
3. **代表フロー**: F1〜F5。各フローに入口→情報→主操作→例外→復帰→完了を記載。DG-01/02/03/06
4. **情報構造と語彙**: 現行画面map＋段階移行map、互換URL、手動測定と手動解釈の違い。DG-05
5. **視覚token**: semantic color、type roles、spacing、radius、density、focus、motion。既存値/提案値/検証済みを別欄に。DG-08/09/12
6. **部品の契約**: 対象コンテキスト帯、結果card、根拠、測定定義form、試行レビュー、run状態、保存/競合、履歴、出力。DG-02/03/04/06/10/11
7. **状態と文言**: 4軸state matrix、empty/error/retry、外部送信、保存先、未提供の表示。DG-01/03/11
8. **アクセシビリティ/レスポンシブ**: label、keyboard、focus、live、selected navigation、表、拡大、motion、実AT受入。DG-07/09/10/12
9. **変更の安全境界**: 既存ID/API/SQL/ノート契約、無断外部送信なし、CSSだけで存在する操作を消さない、mock成功と実受入の区別
10. **実装順・受入・追跡**: DG ID→source→decision→component→test→result。未実施を未実施のまま残し、画像とHEADを紐付ける

### 追跡行の形

`DG-02 → definition/trial/adopt API → ManualDefinition + TrialReview → duration/character対照fixture → keyboard + API + revision検証 → 状態: 提案/実装/静的合格/GUI合格`

Design原則の例: 「測定の自然文説明と実行規則を区別する」。具体例: 「説明が『秒数を測る』でもtext_lengthなら文字数と表示」。受入: 「duration選択で60秒/2秒、text_length選択で3文字/10文字」。抽象的な『直感的にする』だけで終わらせない。

## 10. この監査の成果物

- [current-design-evidence-matrix.md](../current-design-evidence-matrix.md): 14項目の分類、根拠、優先度、概算、受入
- [current-design-evidence-matrix.json](../current-design-evidence-matrix.json): 追跡用の構造化版
- [audit-source-manifest.json](../audit-source-manifest.json): 監査対象19ファイルのSHA-256とHEAD
- [static-design-probes.js](../static-design-probes.js) / [結果JSON](../static-design-probes.json): 手動定義/採用順/失敗見出しの分離検証
- [definition-lifecycle-evidence-manifest.json](../definition-lifecycle-evidence-manifest.json): 定義lifecycle追加調査のsource/probe hash・検証範囲
- [definition-lifecycle-probe.json](../definition-lifecycle-probe.json) / [definition-full-pipeline-probe.json](../definition-full-pipeline-probe.json): 採用版置換と固定版実行の独立再現
- [specified-color-contrast.json](../specified-color-contrast.json): CSS指定色対の計算
- [adversarial-checks.md](../adversarial-checks.md): 別担当の反証チェックと独立プローブ
- [ux-research.md](../../../../40-Design/ui-design-research/2026-10-02/ux-research.md)、[prompt-research.md](../../../../40-Design/ui-design-research/2026-10-02/prompt-research.md): 並行して整理された一次資料・プロンプト研究。外部研究の一般知見とGurumojiで検証した事実は別扱い

アプリコード・実runtime・移入Vaultは変更していない。研究の内容や私有データを外部AIへ送信していない。現行GUI受入、正式な利用者テスト、実モデル精度は未実施として引き継ぐ。
