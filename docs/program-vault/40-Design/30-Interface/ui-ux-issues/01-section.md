---
note_type: reference-section
status: current
verified: 2026-09-16
updated: 2026-09-26
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/ui
note_id: design-ui-ux-issues-section-01
title: Web UI デザイン・UX 問題点一覧：Web UI デザイン・UX 問題点一覧
summary: Web UI デザイン・UX 問題点一覧。出典ノート「Web UI デザイン・UX 問題点一覧」の分割本文。
parent_note_id: design-ui-ux-issues
source_path: 40-Design/ui-ux-issues.md
source_sha256: c6f0bc30d41c6d90a9c75e220f625e969a0b285260197965f43858ce5d0a0c54
source_body_lines:
- 1
- 23
split_on: '2026-10-11'
---

# Web UI デザイン・UX 問題点一覧：Web UI デザイン・UX 問題点一覧

親索引・状態・確認版：[[40-Design/30-Interface/ui-ux-issues/00-Index]]。必要な本文だけを取得する。


# Web UI デザイン・UX 問題点一覧

**2026-09-20の追加設計（一部実装）：** 利用者の「多種多様な分析を見るには不親切」という指摘を受け、[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]の図7で、結果の検索・型別表示・根拠・実行比較・追加分析・相談と計画・RAWと出力をまとめたUI案を作成した。UX-33の比較履歴導線は実装済み。UX-34の取得範囲と、それ以外の画面再編は導入条件に従う未実装範囲として残る。過去の対応件数は当時の集計であり、この設計追加だけで解消済みに変更しない。

**現在の状態（2026-09-26）：** 42件中、対応済み32件・一部対応3件・未対応7件。UI再設計でUX-01／02／03／05／09／16／18／20／27を対応済みに更新した。状態欄は実装状況、選別欄は当初の優先度。問題・根拠・改善案は調査時点の記録として残す。2026-09-15時点のプッシュ済みコミットの集計は [[40-Design/50-Governance/convergence-plan/01-section#プッシュ済みの対応状況（2026-09-15）|convergence-plan#プッシュ済みの対応状況（2026-09-15）]]。

**動画処理画面の追加調査（2026-09-22）：** 利用者からの「動画処理画面のUIが非常に見づらい」という指摘を受け、動画処理・確認画面の課題8件（UX-35〜UX-42）を追記した。詳細は [[40-Design/30-Interface/video-ui-redesign-plan|video-ui-redesign-plan]]。登録は計42件。

**UI全面再設計（実装2026-09-16、2026-09-25に最新版`2f13f98`へ収録）：** 利用者の許可を受けて画面構造を作り直し、UX-01／02／03／05／09／16／18／20／27を対応済み、UX-21／28を一部対応にした。画面とURL、旧機能の移動先は [[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]]、判断は [[40-Design/50-Governance/decisions/02-topics/13-section#ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する|decisions#ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する]]。ヘッドレスEdgeで幅1440pxと、幅585px（CSS上）の狭い画面を撮影して確認した。実機スマホは未確認。

**優先修正の追記（2026-09-14）：** UX-30／31／32を実装し、実ブラウザーの回帰テストで確認した。既存のAI応答モックを現行仕様に合わせた後、プロジェクトの仮想環境で全393件が成功。下記の先行UI修正記録にある385件中3件失敗は当時の結果で、現在は解消している。[[40-Design/50-Governance/convergence-plan/02-section#優先修正の実装（2026-09-14）|convergence-plan#優先修正の実装（2026-09-14）]]。

**追加調査：** [[40-Design/30-Interface/ui-ux-issues/07-section#追加調査：UI・UX（2026-09-14）|未記載だった5件]] を追記し、登録は計34件。プログラム全体の追加4件は [[40-Design/50-Governance/known-issues/07-section#追加調査：プログラム全体（2026-09-14）|known-issues#追加調査：プログラム全体（2026-09-14）]]。前回29件の選別は履歴として維持する。

Web UIのデザインとUXの問題点を、改善の順番を決めるために記録する。対応が決まった項目は、ADRや実装計画として別ノートに分け、この一覧には対応先へのリンクを追記する。

**2026-09-14の選別：** 全29件に選別欄を追加した。理由とアプリ全体での対応順は [[40-Design/50-Governance/convergence-plan/04-section#今回の取捨選択（2026-09-14）|convergence-plan#今回の取捨選択（2026-09-14）]] を正本とする。今回の追加確認はコードの読解のみで、画面の再撮影・モバイル実機確認は行っていない。元の問題・改善案を残し、選別は実装状況と区別する。

**先行UI改善（実装2026-09-14、プッシュ済み）：** P1のUX-11／12／14／17／23／24と、P2のUX-04／06／07／08／10をコミット`1b8fe41`に収録した。UX-03は540px以下だけ対応、UX-01は未着手。検証先は`tests/test_ui_defaults.py:test_registered_ui_ux_fixes_stay_in_place`。初回の全385件中3件の失敗は、AI応答モックを現行仕様へ合わせた後の全393件で解消した。これは`1b8fe41`収録版の過去の検証結果であり、2026-09-16の全面再設計後の表示・動作を検証した結果ではない。実機モバイルの表示確認は未実施。

**記述の補正：** UX-15の開始ボタンには既に `.launch-button.primary-button:disabled { cursor: not-allowed; }` がある。他のボタンと無効理由の表示は別途判断する。UX-25の `.visually-hidden` は現在、`#speaker-csv-input` と `#input-file` の非表示file入力に使われている。読み上げ用テキストが消える実例は確認できず、クラスの意味を一括で変える案は採用しない。
