---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review-section-06
title: Gurumoji 設計調査の独立出典監査：公開資料で検証できないプロジェクト前提
summary: 公開資料で検証できないプロジェクト前提。出典ノート「Gurumoji 設計調査の独立出典監査」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review
source_path: 40-Design/ui-design-research/2026-10-02/source-review.md
source_sha256: 444a9f0716d8b24c2d90b4ab5ddd61f1c7727e707a5c9d4bb7b1e547494f42d5
source_body_lines:
- 153
- 185
split_on: '2026-10-11'
---

# Gurumoji 設計調査の独立出典監査：公開資料で検証できないプロジェクト前提

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/source-review]]。必要な本文だけを取得する。

## 公開資料で検証できないプロジェクト前提

L1のREADME、対象HEAD、既存25改善とWindows受入待ち10項目、画面幅や保存契約はローカル資料に依存する。今回の公開出典監査では独立に再検証していない。別のコード・実画面監査の結果を参照し、文献が裏付けた製品事実という表示にしない。

## 引用量と再配布

検査した本文は主として日本語の要約と製品固有の提案で、英語原文の長い連続転載や論文図表の丸ごとの再配布は見当たらなかった。11個のプロンプトテンプレートもGurumoji固有の契約・状態・受入へ再構成されており、公式プロンプトの全文転載ではない。

公開時は出典を短い書誌情報・確認範囲・原資料リンクで示し、必要な範囲を簡潔に要約する。原文、サンプルプロンプト、図表を追加転載する場合は、目的と利用条件を確認する。この確認は目立つ大量転載を点検したものであり、すべての言い換えに対する権利審査や再配布許可の確認を完了したという意味ではない。

## 追加探索で見つかった日本語研究

既存の「日本語の長時間グループインタビューUIの直接比較研究は不足」という限定に反する資料は見つからなかった。一方、SakaguchiらのJMIR2025論文は、日本語の医療場面の30個別インタビューを比較した関連研究として存在する。

**追加の定量的根拠としては採用しない。** 原文にはMethodsのGPT-4oとLimitationsのGPT-4というモデル名の不一致があり、人側には面識・背景知識、AI側には本文のみという条件差がある。また「agreement」は相対頻度に基づく記述値で、κや単純な正答率ではない。UI比較試験でもない。日本語の文脈保持を考える補助読書にはなるが、報告された割合をGurumojiの性能目標へ転用しない。[著者論文のPMC全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC12062757/)

## 最終反映確認

- C01 WebGen指標名・分母: `prompt-research.md` v1.1への反映を再読確認
- C02 WebGen-Agent出版状況: 同本文とJSON台帳への反映を確認。閲覧版と出版記録を分離
- C03 ASR脱落語: UX本文K04と台帳S03で、信頼度分類からの除外と脱落を含む利用者WERを分離した修正を再読確認。S19のMonash出版記録追加も確認
- C04 Figma内部不整合: 現行本文は一般化を避けており使用可能。数値を短く再引用する際は本監査の条件を省かない

本監査は他担当のファイルを直接変更していない。訂正は担当者へ伝達し、確認した版を記録した。

最終再読時刻 2026-10-02 18:56 UTC。以下は監査終了時点の入力ファイルSHA-256。後続編集があればその版を別に確認する。

- `prompt-research.md`: `82a1764145b4e6ba8b6a0cfd5a8a7a08fd9c7c70f34de01eee91b536d7c516c7`
- `prompt-source-ledger.json`: `bca488d395a3c18ae01338db60c94cb4d7e82f9c36b762beab001401b5e0c41e`
- `prompt-source-ledger.md`: `605e2e737f108114e948cac726740c5ce69674f9f639b2270a0d8bd85813732b`
- `ux-research.md`: `e453d2647c762b230042ecf26bf6907e0b2d5e87a9950b2e93babeb05b0bfb09`
- `ux-source-ledger.json`: `3e174118480fe12d9b85ea01e20f6b85b8738d0feed6bbc3646cb980a2d26180`
