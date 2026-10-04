---
note_id: "ui-archive-40-design-ui-design-research-2026-10-02-source-review"
note_type: "research-reference"
title: "Gurumoji 設計調査の独立出典監査"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

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

## 最新モデルガイドと仕様の照合

以下は製品の公式助言としての確認であり、独立した効果測定や最良モデル認定ではない。

| ID | 監査した主張 | 判定と条件 | 原資料 |
|---|---|---|---|
| O1 | フロントエンド指示の対象は GPT-5.5。既存設計・用途に合う業務画面を重視 | 確認。本文冒頭と Build with empathy に一致。「全現行モデルの共通最適解」にはしない | [OpenAI frontend](https://developers.openai.com/api/docs/guides/frontend-prompt) |
| O2 | GPT-5.4 記事は2026-03-20。参照と描画後検証を推奨 | 日付・方針を確認。低い推論設定に関する助言を他モデルや複雑な仕様作業へ移植しないという限定は適切 | [GPT-5.4 記事](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4) |
| O3 | Astra 記事は2026-09-11。常設文脈を整理し、完了と境界を明確化 | 日付・方針を確認。UIの比較実験ではない。「仕様不要」への読み替え不可 | [Astra 記事](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) |
| A1 | 一般指針に旧世代の美観プロンプト例がある | 確認。モデル一覧は更新されるが、Frontend例にはOpus4.5/4.6の記述が残る。段落ごとの対象世代を読む | [Claude 一般指針](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) |
| A2 | Opus4.8 は具体的代案・複数方向案を推奨 | 確認。書体や背景色の禁止はモデルの既定スタイルを変える例であり、普遍的UX則ではない | [Opus4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8) |
| A3 | Opus5.5 は抽象的なAI感の回避より、実出力の特定パターンを見て反復する | 確認。公開日不明の扱いも妥当 | [Opus5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5) |
| A4 | テスト・ビルド・画像で結果を確認可能にする | 確認。確認手段の推奨であり、利用者受入の代替ではない | [Claude Code](https://code.claude.com/docs/en/best-practices) |
| G1 | 明確な指示、区分した文脈、例、反復 | 確認。長く書くこと自体の推奨ではない | [Gemini 一般指針](https://ai.google.dev/gemini-api/docs/prompting-strategies) |
| G2 | Gemini3.5 Flash ページの更新日は2026-09-23。簡潔さと長文後の依頼を推奨 | フッターと Prompting best practices を確認。該当助言はGemini3.x向けと書かれている | [Gemini3.5](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5) |
| G3 | Googleが2026-04-21にDESIGN.md draft仕様を公開 | 日付・draftの表現を確認 | [Google発表](https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-design-md/) |
| G4 | 任意YAML frontmatterとMarkdown本文、alpha、標準節、省略可 | 確認。トークン値と説明文の役割は区別される。存在する標準節の順序も仕様の一部。単にファイルを置けば全製品が自動で読むという主張はしない | [Google仕様](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md) |
| G5 | lint・diff・exportがあり、alphaで変更され得る | READMEで確認。CLI未実行の明示は適切。lintの形式・限定的色対検査をアプリのWCAG適合へ広げない | [公式リポジトリ](https://github.com/google-labs-code/design.md) |
| D1 | DTCG2025.10は安定したトークン交換仕様だがW3C Recommendationではない | 2025-10-28のFinal Community Group Report表記を確認。Status節はW3C Standards Track外と明示。GoogleのYAMLと同一形式ではない | [DTCG2025.10](https://www.designtokens.org/tr/2025.10/format/) |
| F1 | task/context/constraints、画像と構造化Figmaフレームの差、対象を絞る編集 | 公式本文で確認。フレームの情報量と操作契約の正しさは別 | [Figma Make作成](https://help.figma.com/hc/en-us/articles/31304485164695-Create-a-Figma-Make-file) |
| F2 | Guidelines.mdで継続的指針を渡せる | 確認。ファイル名の大文字小文字は公式ページ内でも混在するため、実環境のファイルと読込みを確認する | [Figma guidelines](https://help.figma.com/hc/en-us/articles/33665861260823-Add-guidelines-to-Figma-Make) |
| F3 | 短い入口から用途別の細かい資料へ案内 | 確認。サンプルの数値・美的嗜好はGurumoji要件ではない | [Make kits指針](https://help.figma.com/hc/en-us/articles/43602393097239-Write-design-system-guidelines-for-Make-kits) |
| V1 | 高解像度画像・対象切抜き・挙動や例外の補足 | 確認。画像から推測する機能は実システムの保存契約を検証しない | [v0 Screenshots](https://v0.app/docs/screenshots) |
| V2 | 局所的な外観調整と自然言語の構造変更を使い分ける | 確認。既存Flaskアプリをv0推奨スタックへ変える因果的根拠にはならない | [v0 Design mode](https://v0.app/docs/design-mode) |
| P1 | 比較画像のOS・ブラウザー・フォント等の環境を揃える | 確認。公式の環境差警告と一致 | [Playwright画像比較](https://playwright.dev/docs/test-snapshots) |
| P2 | 自動アクセシビリティ検査と手動・利用者評価を併用 | 確認。サンプルのWCAG2.1タグだけをコピーして2.2全体を検査済みとはしない | [Playwright accessibility](https://playwright.dev/docs/accessibility-testing) |

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

## アクセシビリティの数値と規範の照合

WCAG本文、Understanding、ARIA APGを分ける両調査の説明は適切。これらは同じ強さの規範ではなく、いずれもGurumoji現行画面の合格を証明しない。

| ID | 判定 | 重要な境界 | 一次資料 |
|---|---|---|---|
| W1/S22 | 2024-12-12版WCAG2.2 Recommendationを確認 | 抜粋の通過だけでAA適合を宣言しない | [WCAG2.2](https://www.w3.org/TR/WCAG22/) |
| W2/S24 | 2.5.8の24×24 CSS pxと例外を確認 | 見えるアイコン寸法だけでなく操作対象。44×44を全AA要求にしない。解説ページの2026-05-11更新も確認。仕様発行日とは別 | [Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) |
| S25 | 2.4.11でフォーカス対象が完全に隠れないことを確認 | 外側のフォーカス枠ではなく対象部品の隠れ方。枠の可視性は2.4.7等も別に評価。2pxを2.4.11の数値要求としない | [Focus Not Obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) |
| S26 | 状態メッセージのプログラムによる識別を確認 | 毎秒の読み上げが義務ではない。通知頻度の設計はD | [Status Messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) |
| S27 | 320 CSS px相当のreflowと二次元例外を確認 | 390pxだけの画面確認では不足。200%文字拡大は別基準1.4.4 | [Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) |
| S28 | 通常文字4.5:1、大きい文字3:1を確認 | 例外・大きい文字の定義・表示状態を考慮。全文字を無条件に同じ閾値で分類しない | [Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) |
| S29 | 必要な非テキスト情報の3:1を確認 | 隣接色と必要な識別情報が対象。装飾全てに3:1を要求する意味ではない | [Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) |
| S30a | キーボード操作の要求を確認 | native要素の採用だけで複合UI全体の動作は保証されない | [Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html) |
| S30b | 一文字等のショートカットに停止・再割当・フォーカス時限定の代替を確認 | IME中に発火させない条件は製品の追加設計推論 | [Character Shortcuts](https://www.w3.org/WAI/WCAG22/Understanding/character-key-shortcuts.html) |
| S30c | ドラッグの単一ポインター代替を確認 | キーボード代替だけで2.5.7達成とは限らない | [Dragging](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html) |
| S23a | タブの役割・状態・矢印キーを確認 | 遅延がある場合の手動activationはAPGの推奨。すべてのナビゲーションをtabへ変える指示ではない | [APG Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) |
| S23b | モーダルのフォーカス・内部移動・閉じる操作を確認 | 起動元が消える等の復帰先例外あり。本文の「通常は」は適切 | [APG Dialog](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) |
| S23c | 複合UIのキーボード設計を確認 | ARIAを付けただけでは操作実装は増えない | [APG Keyboard](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) |

## URLと出版記録の問題

**取得失敗と不存在は区別する。** この監査で採用URLの404や不存在を確定したものはない。

| URLまたは項目 | 観測 | 扱い |
|---|---|---|
| S15の著者FAQとeditor-checklist | 直接openはtimeout/502。著者サイトの検索索引に該当内容あり | 「検索抽出確認」を維持し、全文取得済みにしない |
| OpenReviewのR4 forum/PDF | ブラウザー確認画面 | 回避操作はせず、取得可能なICLR公式出版記録で確認 |
| S19 DOIのACM直接取得 | 内部取得エラー | DOI不存在とはしない。Monashの出版記録で補う |
| S32 DOIのPNAS直接取得 | 内部取得エラー | 著者資料に取得経路を限定。今回は数値の格差率を新規採用しない |
| R2およびS18のarXiv HTML内の仮DOI・仮ISBN | テンプレートのプレースホルダーを含む | 仮DOIをリンク・出版証拠として転記しない。論文URL自体は有効 |
| Google DESIGN.mdのmain URL、各社の動的ドキュメント | 将来内容が変わる | 閲覧日・対象モデル・節を残す。厳密な再現性が必要ならcommit permalink/正規リリースを別記 |
| Google DESIGN.mdのStitch側仕様ページ | 元台帳で本文未取得として除外 | GitHub公式仕様への代替は妥当。除外URLを閲覧済み本文に数えない |

## 因果と選定の偏り

- ベンダーの公式ガイドは製品機能と推奨の一次資料として有用だが、各社に宣伝上の利害がある。同じ方向の助言が複数社にあることを、独立した複数実験の再現と数えない
- Design2Code、DesignBench、WebGenは異なる入力・課題・採点であり、数値を横並びにして製品順位を作れない。現状資料はその比較を行っていない
- ASR強調の無効果、説明の悪影響だけを選ぶと偏る。現状UXは、説明が検証費用を下げる条件で有益なS06も載せており、相反する結果の扱いは適切
- CollabCoderの採用率・自己評価や、Figmaの時間短縮だけを「研究の質」へ変換しない。根拠往復、残存誤り、保存の完全性をGurumoji側で測る必要がある
- 小標本の質的研究は仮説と問題発見を支える。研究者全体の需要、初心者・熟練者全体の平均効果を確定しない
- 英語圏・短時間・固定課題から日本語の長時間グループ研究への移植可能性は未確認。既存資料の「体系的レビューではない」という説明を残す
- 独自テンプレート、1440/390px、状態モデル、重大度の運用定義、ペルソナ、優先順位はプロジェクト判断である。論文がそのまま要求する仕様と誤表示しない

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

## 統合初稿の追加点検

2026-10-02 18:58 UTCに `agent-design-knowledge.md` と `draft-DESIGN.md` の文献表現も再読した。draft-DESIGNは設計仮説、既存契約、規範、受入未確認を分けており、追加の効果保証は見当たらない。知識索引のASR条件に「再生なし」とあった点は「音声は一度再生してリプレイ不可」へ訂正されたことを19:00 UTCに再読確認した。実験では音声を聞きながら修正するため、ここは意味のある差である。24pxの略記を24×24 CSS pxへ、文献のS番号をUX名前空間へ揃える修正も確認した。

追加確認した統合資料のSHA-256:

- `agent-design-knowledge.md`: `226d8a0c5ed641030b6b4faec86f717553dab30aae14b20f39f99e524344434d`
- `draft-DESIGN.md`: `3296426feee85fde4e3a85a5f9de802a4bf69cb7dd49e6ed9619801d45abf444`
