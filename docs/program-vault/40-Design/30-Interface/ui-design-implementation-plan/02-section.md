---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-02
title: Gurumoji UI改善の実装計画：3 作業単位の実装契約
summary: 3 作業単位の実装契約。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 34
- 59
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：3 作業単位の実装契約

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

## 3 作業単位の実装契約

### W00 現行能力を短く固定する

- 文書同期の進捗（2026-10-02）: `ui-screens.md`の上部4入口、M0〜M7永続pipeline、初回能力の限定をコード照合して更新済み。入口→handler/API→capabilityの対応表と可視入口の受入は残るため、W00全体の完了にはしない。日付付きDG-13の監査snapshotは当時の観測として維持する

- 対象: `analysis_core.py:80–100,311–338`、`analysis_pipeline.py`、`analysis-execution.js`、Software Vaultの`ui-screens.md`とマイルストーン設計
- 作業: 基礎pipeline、個別Transformer／見解／分類、O01計画相談、固定package出力を別行にした能力表を作る。M0〜M7は既存のサーバー永続処理と明記する。旧6段階／client逐次説明を同期する
- 境界: 47成果物・7役割・全推測統計を既に使えるとも、永続化が未実装とも書かない。通常分析のXLSXとpipeline固定packageのXLSX未提供を分ける
- 合格: 各可視入口→handler/API→capability→説明先を一対一で追跡。unsupportedには理由、案内する画面には入口が存在する。コードと文書差分のリンクを確認
- 依存／出典: DG-01/13、ADR-118、PR:T1/PR:T4
- 戻し方: 文書差分のみ戻せる。能力表を新しい実行エンジンにしない

### W01 個別分析の実行と案内を一致させる

- 対象: `style.css:2088–2093`、`analysis-content.js:184–188,561–568`、`analysis-method-view.js:254–264`、`app.js:6760–6769`、`index.html:236`
- 推奨: 既存の個別controlを各結果panelで可視・操作可能に戻し、見解が概要にある現構成なら案内を合わせる。見えなくした全selectorを機械的に復活させず、取消・provider・表示条件を確認する
- 送信表示: AI見解は「発話・話者情報・研究質問・分析用の付与情報」と短く示し、詳細に話者名／役割、コードID・label、重要フラグ、専門家設定時の短い説明・ID／版・手順／根拠IDを含める。本文だけの送信と説明しない。LM Studioも設定された接続先であり、閲覧端末の「このPC」と決めつけない。実prompt captureとの照合を受入に含める（[文言仕様](../ui-microcopy-state-catalog/00-Index.md)J24、[合成probe](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)）
- 代案: 共通確認panelから既存handlerへ送る。将来IAと揃うが、対象版／dirty guard／送信要約／取消／二重送信を再結合するコストがある。対応runnerのない基礎pipelineへ統合したふりはしない
- 合格: シナリオS01。通常一覧からのpointerとkeyboardで3入口へ到達し、visible/enabled・実矩形・production CSSを確認。route spyで正しい対象／provider／APIが1回。dirty、連打、取消対応のある処理の中止、条件不足も検証
- 可視化前のhandler gate: 分類のA要求を保留してBへ移ると、Aの遅い応答がBの表示へ入ることを[隔離probe](../../../50-Tests/ui-design-evidence/2026-10-02/classification-late-response-probe.json)で再現した。要求時item／入力・分析revisionを保持し、応答時の表示対象／版と照合してからstateと通知へ反映する。不一致ではBを変更せず、Aの保存済み結果は後で正規読取する。通信abortだけでserver処理の取消と見なさない。現行はCSS-hiddenのため通常UI発生済みとは呼ばないが、入口復旧の必須回帰に含める
- 能力の限定: 取消を確認できたのはTransformer／AI見解。分類は`analysis-method-view.js:312–347`のPOSTで、同じ取消handlerは確認できていない。3入口一律の中止を提供せず、分類の遅延responseと対象移動の保護も別に試験する
- 既存試験: `test_content_browser.py`、`test_transformer_content_browser.py`等のhandler試験を保ち、可視入口の試験を追加。hidden要素のJS clickを可視受入に数えない
- 出典: DG-01、反証H1、UX:S01/UX:S12/UX:S22、PR:T7/PR:T10
- 移行／rollback: 保存schema不要。入口adapter単位で戻せるようにする。問題時は旧の非表示状態を正当化せず、利用不可の理由と保存済み結果の入口を明示する
