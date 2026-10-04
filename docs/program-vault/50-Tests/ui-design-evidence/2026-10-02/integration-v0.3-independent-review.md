---
note_id: "test-ui-design-integration-v03-review"
note_type: "design-evidence"
title: "v0.3設計知識統合の独立レビュー"
summary: "20:34:31 UTCのv0.3 snapshotとdocs commit88f5e3eに対する独立レビュー保存版。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
review_repository_head: "88f5e3eea245166ee68ed4dc6c3f99c31e149228"
tags: ["gurumoji/design", "gurumoji/ui"]
---

保存範囲: 2026-10-02 20:34:31 UTCのv0.3文書snapshotに対するレビュー。対象の内容はGit commit `88f5e3eea245166ee68ed4dc6c3f99c31e149228`に収録されている。以下の件数・行番号・hashは当時の記録であり、v0.4差分の合格を示さない。

# Gurumoji 設計知識統合の独立レビュー

レビュー日: 2026-10-02 UTC  
対象: `/workspace/scratch/be1eb353f7eb/projects/gurumoji/app` の文書・skill差分  
ソース基準: `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`（実装 `59ebd24f88a86415c3cb122c11ece9b03c9111fc`）  
方法: アプリ内はread-only。差分・実ファイル・コード・PNGを独立に点検。app実行、実runtime、私有Vault、外部AI、commit/pushは実施していない。

## 結論

**文書のみの統合として受入可能。独立レビューで挙げた4点は修正・再検証済み。未解決blockerは0件。**

UI修正、現行GUI操作、AT、利用者比較、モデル品質を合格にしたレビューではない。既存アプリのP1課題を修正済みにする記述は見つからなかった。公開・commit・PC反映の許可をこのレビューが与えることもない。

## 1 変更範囲と保存性

- 変更は86ファイル。root `DESIGN.md`、既存`AGENTS.md`の1行追加、既存criticの参照追加、project skill、`docs/program-vault`の設計・研究・受入・画像に限定
- 既存tracked変更は6ファイル。これら以外のtracked **692ファイルをHEADのGit blobとbyte照合し、想定外の差分0件**
- 新規ファイルを含む変更一覧で、source、tests、実行設定、依存定義、runtime、資格情報、私有Vaultを対象とするファイル0件。symlink 0件
- 配布予定ファイルだけを秘密鍵・一般的なAPI key形・認証情報入りURL・email形で点検し、該当0件。これは内容を見た範囲の確認で、未知の秘密を機械的に完全否定するものではない
- 私有Vault/runtimeの内容・変更状況は読んでいない。確認できるのは「今回の統合差分に含まれない」「このレビューが触れていない」ことで、外部領域全体のbyte不変は主張しない
- 既存の原25件表は実数で **15 addressed / 10 partial / 0 open**。UI10件を未実装に戻していない

## 2 入口と3つの再利用シナリオ

`DESIGN.md`は20行、skillは33行。AGENTSの追加は条件付きの1行。skill descriptionにはGurumoji固有の適用条件と、別プロジェクト・一般相談・非UI修正・単純な文書編集の除外がある。全研究packの常時読込、事前Vault更新、モデル学習、自動登録・自動発見を要求／主張しない。

以下は**文書ルーティングの独立walkthrough**であり、新しいエージェント実験や実装試験ではない。

| 具体的な依頼 | 選ぶ資料と到達先 | 判定 |
|---|---|---|
| 「Gurumojiの分析がfailedなのに実行中と見える。最小修正を考える」 | skillの局所修正 → DESIGN → 設計契約§5状態 → W03 → `analysis-execution.js:434–437`と隣接test → S03/V1–V3。全文献や全画面案は不要 | 適切に限定できる。現行のfailed分岐欠落と、将来の受入を分けられる |
| 「Gurumojiの390px画面で、固定結果から根拠を確認して戻る2案を比較したい」 | 知識索引の根拠往復・比較行 → W04/S04、必要なUX:K01/K05/K13・T2/T8、clean v2と画面外凡例。入力版・原音・復帰契約を先に確認 | 適切。静止案と実操作を混ぜず、選好・効果は利用者検証待ちとして扱える |
| 「READMEの誤字修正」または「ADC08のサーバー処理を直す」 | Gurumojiの設計判断・出典更新を伴わないためskill対象外。対象文書／実装だけから始める | 負例も適切。Gurumojiの設計packを他作業へ強制しない |

入口の取得は文書設計として確認した。実行環境によるskillの自動発見／常駐登録は検証していないし、文書もそれを保証していない。

## 3 参照と現行説明

独自のread-only checker: `integration-independent-checks.py`。結果: `integration-independent-checks.json`。

初回20:24:06 snapshotでは、ローカルMarkdownリンク177、Wikilink69、HTML内リンク・fragment47、明示的な`src/`・`tests/`・`docs/`行参照52を点検し、欠落・範囲外0件。Markdownの9 fragmentも一致。最終件数は末尾の再検証を参照。

- ソース行参照52件は実在と行範囲を機械確認。主要な意味は別途コードを読んだ。すべての記述の意味を機械的に証明したという表示にはしない
- 上部4入口は`templates/index.html:46–50`と一致。互換の結果領域subnavも`:79–81`に残る
- M0〜M7のserver永続処理、capability、JSON/CSV/ZIPと未提供機能の限定は`analysis_core.py:80–104,311–369`、`analysis_pipeline.py`と一致。個別Transformer/AI見解/分類やO01を基礎pipelineと同一視しない
- DG-01のCSS非表示は`style.css:2088–2093`、DG-02の暗黙規則・即採用は`analysis-execution.js:50–64,542–557`で確認
- 同IDdraftによる旧adopted置換とworkerの最新ID再読は`analysis_pipeline.py:227–256,635–644`で確認。合成probeを実保存・本番データ・GUI証拠に繰り上げていない
- 分類の遅延responseは`analysis-method-view.js:312–347`の応答時照合不足として記載され、通常UIでの既発生や保存破損へ膨らませていない
- 履歴100件は`analysis_store.py:274–278,294–297`の一覧上限であり、既知IDの保存物削除を主張しない
- `ui-screens.md:8–9,22–26,38–46`はsource-only確認、導入履歴、現在能力、未実施GUIを区別
- `audit-source-manifest.json`の19ファイルと`definition-lifecycle-evidence-manifest.json`の4ファイルは、すべて**固定されたddc23abeのGit blob**とhash一致。前者の`ui-screens.md`は今回意図的に文書更新され、現working treeのhashとは異なる。これはbaseline記録の破損ではない
- 原artifact名や旧画像への裸のコード表記は、当時の検証環境ラベルとして残る。READMEがその境界を説明しており、持ち運べる相対リンクに偽装していない。将来再実行する場合は別の新しい検証記録が必要

## 4 版・件数・未実施の境界

- 日付付き研究・証拠は過去snapshot、知識索引／設計契約／計画は作業用正本として分離
- DG-02-U1/U2、T1、独立再現したT2/T3を区別。T2/T3を単なるUI文言へ埋めず、14 top-level DGや原25件へ無根拠に合算しない
- DG14件には既知課題、設計提案、旧画像由来仮説もある。「新規14バグ」としていない
- GUI/AT/利用者評価の未実施は契約・受入資料で一貫。Node/合成DOM、静止画像、既存テスト結果をV3/V4/V5合格へ繰り上げない
- 自動発見、モデル重み学習、全機能自動導入、UI修正済みの宣言はない
- 旧v1とclean v2は入口が分かれ、比較はv2優先。v1 8図、v2比較8図＋補助2図、初回／再レビューを独立利用者実験数に加算しない
- 原25件の過去864 passed等を、この文書差分で新実行した全体テスト結果としていない

## 5 公開技術資料・著作物・画像

- 研究台帳のUX36項目、prompt28項目を点検。研究・規範・製品資料は公開URL、唯一のlocal project source PR:L1はapp README。私有研究Vault本文を新しい設計知識へ取り込んだ形跡なし
- 公式製品の説明、掲載画像の静止観察、Gurumojiへの設計推論、Live操作なしを分離。論文の標本条件・分母・版・適用限界も保持
- 長い英語原文、ベンダー公式prompt全文、論文図表の再配布は見当たらない。11テンプレートと3 task briefはGurumoji向けに書いたものと明記。多数の文書へ同じ外部文章を追加複製する必要はない
- 収録PNG10枚をすべて実際に画素閲覧。各図の上端に「提案モックアップ／非機能／合成データ」が可視表示されている。実アプリのスクリーンショットというラベルはない
- SVG18個はXMLとして正常で、外部画像・外部font等の読込やscriptなし。HTML2個もscriptなし。収録図は第三者製品の原画像ではなく、合成内容のGurumoji案
- 一般的な出典・転載配慮を確認した範囲に限る。全素材の権利審査・再配布許可を完了したという認定はしない。既存repoに新しいライセンスを勝手に追加することは勧めない
- 外部URLの全件live疎通や文献の再研究は、この統合レビューでは再実施していない。版付きarXivリンクは参照版として意図的に固定。旧NVivo12は現在版比較に未採用と明記

## 6 今回指摘し、修正確認した点

1. **公開向けの出典監査の記述:** `40-Design/ui-design-research/2026-10-02/source-review.md:171`。調査ツール固有の運用細目を除き、短い出典表示・原資料リンク・転載時の確認・権利審査未完了の一般的説明へ修正済み
2. **文書commitとソース基準版:** `40-Design/ui-design-knowledge.md:17`。source_headは調査baselineで、文書のみの新HEADが新実装・配信版一致・UI再検証を意味しないことを追記済み
3. **既に進んだ文書同期の記録:** `40-Design/ui-design-implementation-plan.md:48`。`ui-screens.md`同期済み、能力対応表と可視入口受入は未完了、W00全体は未完了と明示。歴史DG-13は改変していない
4. **旧ファイル名の参照label:** `40-Design/ui-design-research/2026-10-02/prompt-workflow-task-briefs.md:22`。存在する新しい移設先に合う「設計知識索引／設計契約」へ変更済み

以上のpathは`docs/program-vault/`を基点とする。修正は統合担当が行い、このレビュー担当はappファイルを編集していない。

## 7 持続可能な保存量

初回snapshotは86ファイル／2,712,478 bytes（約2.59 MiB）。約1.47MBがPNG10枚、約0.30MBが自己完結HTML、0.18MBがSVG。入口を小さく保ち、資料は選択参照するため常時context負担にはならない。

- v1 PNG、builder/validator、描画ログ、browser profileを除外した判断は妥当
- 6個のprobeソースは合計23,242 bytesで、隔離証拠の具体的な検証内容を説明する価値がある。現状の保存資料として残すことは許容。移設後の相対pathは実行用に修正されていないため、再実行できるsuiteとして売らない。README:17が明記している
- HTMLはSVGの重複を持つが、offlineで比較可能な自己完結閲覧物という役割がある。今後は日付snapshotを凍結し、同じ図を複数の「現行版」として並行保守しない
- 研究台帳のJSON/Markdown、証拠JSON/表示表は用途が異なる。入口へ内容を再複製しない現在方針を維持する

## 8 最終再検証

20:34:31.858020 UTCの最終統合snapshotを、20:37 UTCに独立再照合した。

- 86ファイル／2,714,407 bytes。manifest84項目はすべて実ファイルとhash一致。manifestとvalidation自身の2ファイルは明示的な自己除外
- ローカルMarkdownリンク178、Wikilink69、HTMLリンク／fragment47、ソース行参照52は欠落・範囲外0件。Markdown fragment9件（コード行fragment4件を含む）とWiki見出しfragment1件も一致
- `git diff --check`はexit 0。HEADは基準ddc23abeのまま。commit・push・app起動なし
- 最終manifest SHA-256: `02d63bed9560ca687907e42cda3439b9f9f9c7302e1dfea60c5da6f842ad4bba`
- 最終validation SHA-256: `27833058b89e1f28d4cec56aae441fec2476ed15026bae942ae79b5b1c6d485c`
- 詳細: `integration-independent-final-snapshot.json`

この後にapp差分を変える場合はmanifestとリンク検査を再実行する。後日文書のみcommitしてHEADが進んだ場合も、ソース基準・実配信版・新実装／再試験の有無を別に記録する。
