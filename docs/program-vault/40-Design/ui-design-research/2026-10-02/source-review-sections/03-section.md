---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review-section-03
title: Gurumoji 設計調査の独立出典監査：UI生成研究の照合
summary: UI生成研究の照合。出典ノート「Gurumoji 設計調査の独立出典監査」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-source-review
source_path: 40-Design/ui-design-research/2026-10-02/source-review.md
source_sha256: 444a9f0716d8b24c2d90b4ab5ddd61f1c7727e707a5c9d4bb7b1e547494f42d5
source_body_lines:
- 71
- 108
split_on: '2026-10-11'
---

# Gurumoji 設計調査の独立出典監査：UI生成研究の照合

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/source-review]]。必要な本文だけを取得する。

## UI生成研究の照合

| ID | 主張と確認箇所 | 判定と具体的な再利用条件 |
|---|---|---|
| R1 | Design2Codeの484実Webページ、視覚要素・レイアウト評価。ACLの抄録とNAACL2025書誌 | 確認。査読会議の最終論文。静的画像再現と研究作業の保存・再分析は別の評価対象。[論文](https://aclanthology.org/2025.naacl-long.199/) |
| R2 | DesignBenchの900サンプル。Table2は生成430・編集359・修復111、React/Vue/Angular/vanilla。§6.4はコード文脈の有用性 | 確認。「900ページ全てで全課題を試す」という意味ではない。コードのみが画像のみを上回る結果は当該実験の文脈に限定。v3は2026-03-15。会議欄・DOIにプレースホルダーがあり、採録は確認できず。現在のリポジトリ例の新しいモデル名を、この論文の比較結果に混ぜない。[v3](https://arxiv.org/html/2506.06251v3) |
| R3 | WebGen-Bench v2は2025-08-11、生成指示・GUIケース・外観を分ける | 確認。指標はC01参照。採録の一次記録はこの監査では確認できなかったため、読んだarXiv版として表記。自動GUI評価を実利用者テストと呼ばない |
| R4 | 複数階層フィードバックと選択による改善、ネットワーク・速度の検証限界 | C01・C02の訂正後に採用可能。論文タイトルの強化学習部分と、Claudeの推論時システム比較を混同しない。学習対象の小型モデル実験は別 |
| R5 | 100名・3課題・約20% | C04の条件を伴ってのみ採用可能。arXiv掲載そのものは査読通過の証明にならず、独立した追試でもない |

## UX研究の主張ごとの照合

| ID | 主張 | 判定と条件 | 一次資料 |
|---|---|---|---|
| S01 | 49実務家・20製品で評価したHuman–AI指針 | 確認。18指針の適用可能性を検討する研究。各UI要素の効果量ではない | [Microsoft研究記録](https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/) |
| S02 | キーボード併用の修正・テキストからの音声再生が有用 | 大学リポジトリの抄録で確認。2008年。本文未確認という既存の限定を残す。UI技法の組合せの報告を単独機能の現行効果量に分解しない | [Waikato](https://researchcommons.waikato.ac.nz/entities/publication/f81aef87-b420-488c-b70d-77abbb76938c) |
| S03 | 信頼度強調と修正結果、標本数・録音長 | C03参照。効果が検出されなかったという表現は適切。ASR以外のLLM自己申告信頼度への直接実験ではない | [著者公開v1](https://arxiv.org/html/2503.15124v1) |
| S04 | 説明でAI受容が増えてもconfidence-only以上のチーム精度にならない | 研究結果と一致。三データセットの比較を全説明・全タスクへ一般化しない。公開初版2020、CHI2021としての年表記は妥当 | [著者公開書誌・抄録](https://arxiv.org/abs/2006.14779) |
| S05 | 199人、cognitive forcingの過信低減と主観評価のトレードオフ | 確認。個人差も報告。全操作の確認ダイアログを増やす根拠ではない | [著者公開記録](https://arxiv.org/abs/2102.09692) |
| S06 | 5研究・731人、検証の費用と利益、模擬AI・迷路 | 抄録・方法の概説と一致。研究別Nを単純加算しない。唯一の正解がない解釈作業の効率改善率には使わない | [大学公開PDF](https://cicl.stanford.edu/papers/vasconcelos2023explanations.pdf) |
| S07 | 2020年1月〜2023年6月の106実験・370効果量 | 確認。74論文から106実験であり106論文ではない。人単独を上回るaugmentationと、最良単独主体を上回るsynergyを区別。全協働が悪いという結論にしない | [Nature論文](https://www.nature.com/articles/s41562-024-02024-1) |
| S08 | overview/filter/detail/history/extractによる探索整理 | 概念分類として確認。1996年の分類を強制的な一方向フローの実験則にしない | [著者大学](https://drum.lib.umd.edu/items/155a868e-fb83-4115-9899-9187ea8c0498) |
| S09 | 視覚符号化が比例判断精度に関係する | 位置・長さ等の実験として確認。グラフの意味や研究上の妥当性を自動保証しないという限定は適切 | [大学公開PDF](https://hci.stanford.edu/publications/2010/crowd-perception/heer-chi2010.pdf) |
| S10 | 不確実性を見せない実務上の理由を調査。台帳90人・13人 | 確認。便宜標本で選択バイアスの可能性あり。不確実性表示を省くことの有効性試験ではない | [著者大学PDF](https://users.eecs.northwestern.edu/~jhullman/Value_of_Uncertainty_Vis_CR.pdf) |
| S11 | 認知負荷研究は学習・問題解決を扱う | 出版社抄録・書誌で確認。余白量、タブ上限、画面密度の直接根拠にしないという限定は適切 | [Sweller1988](https://onlinelibrary.wiley.com/doi/10.1207/s15516709cog1202_4) |
| S12 | 状態可視化、利用者制御、認識、エラー等 | 原著者の指針として確認。レビュー更新日と初出を区別。因果効果量ではない | [10ヒューリスティック](https://www.nngroup.com/articles/ten-usability-heuristics/) |
| S13 | 重要・頻回操作を優先し二次機能を段階開示 | 指針として確認。重要な送信先や保存失敗を隠すことを正当化しない | [Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) |
| S14 | 頻度・影響・持続性による重大度 | 確認。独自のS0〜S4はGurumojiの運用定義と明示されている。著者の原尺度の逐語的定義として引用しない | [Severity Ratings](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/) |
| S15 | reflexive TA、codebook、coding reliabilityを区別 | 著者サイトの検索抽出で確認。直接取得はtimeout/502のため全文閲覧としない。特定の方法論上の立場であり、全質的研究で一致度を禁止する主張ではない | [著者FAQ](https://www.thematicanalysis.net/faqs/)・[著者評価ガイド](https://www.thematicanalysis.net/editor-checklist/) |
| S16 | Focus groupでは参加者間の相互作用を扱う | 出版社抄録で確認。K01/K07の前後文脈を残す設計は妥当な推論だが直接UI実験ではない | [Kitzinger1994](https://doi.org/10.1111/1467-9566.ep11347023) |
| S17 | 分析過程と根拠・解釈の対応を報告。21項目 | PDFで確認。報告指針であり、特定のUI部品や来歴スキーマを必須化する技術仕様ではない | [SRQR PDF](https://med.stanford.edu/content/dam/sm/chri2/documents/O%27Brien%20et%20al.%20-%202014%20-%20Standards%20for%20Reporting%20Qualitative%20Research%20A%20Sy.pdf) |
| S18 | CollabCoder16人・8組、短い書評、AI提案への影響 | §6.1–6.3で確認。各データセット15書評、二者協働。経験者への影響も観察されるが専門家は少数で、専門家一般の効果率ではない。著者サイトの書誌はCHI2024、DOI 10.1145/3613904.3642002。arXivの仮DOIを出版証拠にしない | [v4本文](https://arxiv.org/html/2304.07366v4)・[著者サイト](https://gaojie058.github.io/CollabCoder/) |
| S19 | 10人の質的研究者、利点と文脈・一貫性への懸念 | 著者抄録で確認。CHI EA2024の出版情報は正確。Monashの一次機関記録で査読会議出版・Article191を追加確認。効率の客観的因果効果試験として扱わない | [抄録](https://arxiv.org/abs/2311.03999)・[Monash出版記録](https://research.monash.edu/en/publications/human-ai-collaboration-in-thematic-analysis-using-chatgpt-a-user-/) |
| S20 | PROV-DMはentity/activity/agent等のデータモデル | W3C仕様で確認。2013-04-30 Recommendation。採用のみでUIが改善するという主張はない | [PROV-DM](https://www.w3.org/TR/prov-dm/) |
| S21 | NASA-TLXは6次元の主観負担 | 公式資料で確認。Performanceも自己評価。重み付き正式版とRaw TLX等を区別し、実成績と同一視しない | [NASA公式](https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/) |
| S31 | Loadingパターンの更新2026-08-11、処理表示の区分 | フッターでなく本文上部に更新日あり、確認。秒数の万能法則にはしない | [Carbon](https://www.carbondesignsystem.com/building-blocks/core/patterns/loading) |
| S32 | 2020年の5商用ASR・米国英語話者の格差研究 | 著者再現リポジトリを確認。出版社DOI直接取得は失敗。現行日本語モデルの格差率に移植しないという本文の限定は適切 | [著者再現資料](https://github.com/stanford-policylab/asr-disparities) |
