---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review-section-01
title: Gurumoji 設計調査の独立出典監査：Gurumoji 設計調査の独立出典監査
summary: Gurumoji 設計調査の独立出典監査。出典ノート「Gurumoji 設計調査の独立出典監査」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review
source_path: 40-Design/ui-design-research/2026-10-02/source-review.md
source_sha256: 444a9f0716d8b24c2d90b4ab5ddd61f1c7727e707a5c9d4bb7b1e547494f42d5
source_body_lines:
- 1
- 43
split_on: '2026-10-11'
---

# Gurumoji 設計調査の独立出典監査：Gurumoji 設計調査の独立出典監査

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/source-review]]。必要な本文だけを取得する。


# Gurumoji 設計調査の独立出典監査

監査基準日 2026-10-02 UTC  
対象 `prompt-research.md`、`prompt-source-ledger.json`、`prompt-source-ledger.md`、`ux-research.md`、`ux-source-ledger.json`  
方法 原資料の再取得、論文の方法・結果・限界と出版記録の照合。研究担当者の確認済みラベルだけでは採用しない  
範囲 公開資料に基づく主張の監査。アプリの実装・実画面・実利用者の受入は対象外

## 結論

**主要な出典、標本数、日付、設計上の限定は概ね正確。虚構の論文・モデルガイドは確認しなかった。** ただし、初稿には WebGen の指標名・出版状況と ASR 脱落語の除外範囲に修正すべき点があった。Figma RCT の著者側の記述不整合も、数値を再利用するときに明示する必要がある。

- WebGen の二点は担当者が `prompt-research.md` v1.1 と台帳に修正し、本監査でも再読した
- ASR の除外範囲は UX 担当者が本文・台帳へ修正し、本監査でも再読した
- 研究結果を Gurumoji の改善率へ移植しないという両本文の方針は維持する
- 古い研究を現行モデルの性能ランキングとして読まない。公式ガイドの最新版と、実験されたモデル世代を分ける

「確認」は記載された範囲で一次資料と合うこと、「限定」は主張の適用範囲を維持すべきことを表す。全ての研究の再現実験、網羅的な出版状況調査、引用ネットワーク監査を行ったという意味ではない。

## 重要な訂正と再利用条件

### C01 WebGen の分母と部分点

**初稿要修正、v1.1 反映確認。** R3 の §4.2 Table 3 は、YES に1、PARTIAL に0.5を与えるテストケース単位の加重指標を定義する。R4 の §3.1 は101指示・647ケース、Table 1 は Claude 3.5 Sonnet の Bolt.diy と WebGen-Agent を比較している。26.4%→51.9%はサイト全体が完全に完成した割合ではない。「部分点込みのテストケース加重スコア」が適切。反復、実行、フィードバック、巻戻し、最良ステップ選択を含むシステム比較であり、スクリーンショットを見る指示一つの因果効果ではない。[WebGen-Bench v2](https://arxiv.org/html/2505.03733v2)、[WebGen-Agent v1](https://arxiv.org/html/2509.22644v1)

### C02 WebGen-Agent の出版状況

**初稿要修正、v1.1 反映確認。** R4 は ICLR 2026 の公式会議ポスター記録で確認できる。台帳の `research_preprint` だけという分類は古かった。現在の台帳は会議論文とし、数値・方法を読んだ arXiv v1 と出版記録を別にしている。これは妥当。OpenReview の直接取得はブラウザー確認画面になったため、会議公式記録で照合した。[ICLR 2026 WebGen-Agent](https://iclr.cc/virtual/2026/poster/10008256)

### C03 ASR の脱落語が除外された評価

**初稿の曖昧さを修正済み。** S03 の §3.2 で脱落語を除外したのは、信頼度が存在しない語についての confidence-score による誤り分類評価である。利用者の修正課題は置換・挿入・脱落を含む原稿を用いている。「脱落語は評価から除外」だけでは利用者実験の WER からも除かれたように読める。

推奨文：「脱落語は信頼度値を持たないため、信頼度による誤り分類評価から除外された。別の利用者実験では、置換・挿入・脱落を含む原稿の修正後 WER を評価した」

主要な照合値は9モデル、英語90録音による評価、ドイツ語母語話者36名、3本の各3分の Whisper 原稿、音声再生のやり直しなし。WER 改善差は検出されなかった（§4.2.1、p=.767）。これは同等性の証明でも、任意再生できる日本語環境での無効性の証明でもない。CHI EA 2025 の研究であり、長期実務試験とは区別する。[ASR confidence 研究](https://arxiv.org/html/2503.15124v1)

### C04 Figma RCT の20%と内部不整合

**数値と日付は確認、再利用には限定。** R5 の arXiv 提出日は2026-09-22。50デザイナー・50 PMを職種内で各条件25人に割り付け、固定順の3課題を実施した。約20%は成功裡に完了した課題についての推定で、完了自体が処置の影響を受けるため、無条件の全参加者平均へ読み替えられない。著者はFigma所属、募集・進行はMeasuringUが協力。品質評価は自己申告中心で、完成確認はモデレーターによる参照画像との比較である。

§4.3 はデザイナーの累積時間について p=.049 を記すが、§5.1 は有意な短縮を認めなかったと記す。**出典内部で記述が一致しない**ので、「全デザイナーに有意な17%改善」も「全員20%改善」も採用しない。現行本文の慎重な扱いは妥当。論文自身の約20%という報告、条件付き解析、未確定な一般化を一緒に引用する。[本文 §3–5](https://arxiv.org/html/2609.26725v1)、[提出履歴](https://arxiv.org/abs/2609.26725)
