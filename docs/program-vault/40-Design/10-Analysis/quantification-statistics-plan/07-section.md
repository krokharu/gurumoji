---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-07
title: 発話の数値化とjamovi型統計の自動実行計画：9. 統計解析計画と検定の自動選択
summary: 9. 統計解析計画と検定の自動選択。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 162
- 217
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：9. 統計解析計画と検定の自動選択

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 9. 統計解析計画と検定の自動選択

### 9.1 計画

`app.build_focus_group_analysis_plan`が作る`analysis_plan`を拡張し、研究者が確定する。

- 研究質問のID、確認的か探索的か、分析単位、目的変数、群または説明変数、対応の有無、有意水準、補正の族、除外規則、最小N。
- 確定した日時とfingerprintを保存する。結果を見た後に変えた計画は、自動的に探索的として扱う。
- 実行した検定の総数を結果に記録し、画面に出していない検定を隠さない。

### 9.2 選択表（jamoviとの対応）

jmvの関数名と引数は、2026-09-15にCRANのjmvリファレンスで確認した。

| 目的変数とデザイン | 既定の検定 | 併記する検定 | 効果量 | jamovi（jmv） | 実装 | 現状 |
| --- | --- | --- | --- | --- | --- | --- |
| 連続・独立2群 | Welchのt検定 | Mann–Whitney U、Studentのt検定 | Cohenのd（CI）、順位双列相関 | Independent Samples T-Test（`ttestIS`：`welchs`、`mann`、`norm`、`eqv`） | SciPy（1a） | 未実装 |
| 連続・対応2条件 | 対応のあるt検定 | Wilcoxonの符号付順位検定 | d_z（CI） | Paired Samples T-Test（`ttestPS`） | SciPy（1a） | 未実装 |
| 連続・基準値との比較 | 1標本t検定 | Wilcoxonの符号付順位検定 | d（CI） | One Sample T-Test（`ttestOneS`） | SciPy（1a） | 未実装 |
| 連続・独立3群以上 | Welchの一元配置分散分析＋Games–Howell | Kruskal–Wallis＋DSCF対比較 | ω²・η²、ε² | One-Way ANOVA（`anovaOneW`：`welchs`、`phMethod`）、非パラメトリック（`anovaNP`：`pairs`） | SciPy（1a。DSCFは自前） | 発話単位の分散分析（等分散）とKruskal–Wallisだけ |
| 連続・反復3条件以上 | 反復測定分散分析（球面性の補正） | Friedman | 偏η² | `anovaRM`、`anovaRMNP` | statsmodels（1b）、SciPy | 未実装 |
| 連続・2要因または共変量 | 要因分散分析、共分散分析 | — | 偏η² | `ANOVA`、`ancova` | statsmodels（1b） | 未実装 |
| 名義×名義・独立 | Pearsonのカイ二乗 | Fisherの正確検定（2×2）、R×Cのモンテカルロ正確検定、調整済み標準化残差 | Cramér's V、φ、オッズ比（2×2、CI） | Contingency Tables（`contTables`：`chiSq`、`fisher`、`odds`、`phiCra`、`exp`） | SciPy（1a） | 発話単位のカイ二乗とCramér's Vだけ |
| 2値・対応2条件 | McNemar検定 | 正確検定（不一致ペアの二項検定） | 不一致ペアの比 | Paired Samples Contingency Tables（`contTablesPaired`：`chiSq`、`exact`） | SciPy＋自前（1a） | 未実装 |
| 名義・期待比率との比較 | カイ二乗適合度検定、二項検定 | — | — | `propTestN`、`propTest2` | SciPy（1a） | 未実装 |
| 連続・順序どうし | Pearson（連続）、Spearman・Kendallのτb（順序） | 残りの係数 | 係数（CI） | Correlation Matrix（`corrMatrix`：`pearson`、`spearman`、`kendall`、`ci`）、`corrPart` | SciPy（1a） | 発話単位のPearson・Spearman（CIなし） |
| 連続・2値・順序と複数の説明変数 | 線形・二項ロジスティック・順序ロジスティック回帰 | — | 係数（CI） | `linReg`、`logRegBin`、`logRegOrd` | statsmodels（1b） | 未実装 |
| 尺度の項目（事前アンケート） | 信頼性（α） | ω（因子分析が必要） | — | Reliability Analysis（`reliability`） | 自前（1a） | 未実装 |
| 話者・会話に入れ子の発話 | 話者でクラスター化したGEE（二値・計数）、クラスター頑健標準誤差、線形混合モデル | 話者単位への集約、話者単位の並べ替え検定 | — | 基本機能にはない（GAMLjなどの追加モジュール） | statsmodels（1b。一般化線形混合モデルはPhase 5） | 未実装 |

### 9.3 選択と実行の規則

- **前提の検定で使う検定を切り替えない。** Shapiro–WilkやLeveneの結果で、t検定と非パラメトリック検定を自動で入れ替えない。平均の比較の既定はWelch型とし、非パラメトリック検定を感度分析として並べる（Rasch et al. 2011、Delacre et al. 2017）。前提の確認は、jamoviの出力と照合できるよう表示だけ行う。
- **期待度数：** 期待度数5未満のセルが20%を超えるか、1未満のセルがある場合は、カイ二乗のp値を採用せず、Fisherの正確検定（2×2）またはモンテカルロ正確検定に切り替える（Cochran 1954の目安を既定案とする）。切り替えた理由を行に残す。
- **最小N：** 群のNが計画の最小Nに届かない場合は`not_computable`とし、理由を残す。
- **多重比較：** 補正の族は研究質問ごとに計画で決める。確認的な検定はHolm、多数のコード×群をふるい分ける探索的な検定はBenjamini–Hochberg。補正前と補正後のp値を両方保存する。
- **分析単位の既定：** 群比較は`stat_speakers`で行う。発話単位の検定は「探索的・非独立」の警告を付け、話者でクラスター化したGEEまたはクラスター頑健標準誤差を併記する（Aarts et al. 2014、Jaeger 2008）。
- **効果量の定義：** jamoviと同じ定義（dの分母など）を、golden値との照合で確定する。定義を変えたら手法の版を上げる。
- **画面：** 推奨の検定を主に表示し、併記する検定は折りたたむ。jamoviのメニュー名を併記する。
- **AIを呼ばない：** 統計の実行、保存、Vault出力はLLMを呼ばない。テストで確かめる。
- **報告：** 検定名、統計量、自由度、補正前後のp値、効果量と95%CI、群ごとのNと平均または中央値、前提の注記、変数の出所と妥当性の状態。結果の文章は、コードが数値を埋める日本語テンプレートで作り、LLMで生成しない。

### 9.4 jamoviとRでの再現

| 出力 | 内容 |
| --- | --- |
| `jamovi_<単位>.csv` | UTF-8、ASCIIの列名。名義変数は文字のラベルにし、jamoviが名義として読み込めるようにする |
| `variable_catalog.csv` | 日本語の表示名、尺度、出所、妥当性の状態 |
| `jmv_syntax.R` | 例：`jmv::ttestIS(data = speakers, vars = "code_c01_rate", group = "gender", welchs = TRUE, mann = TRUE, norm = TRUE, eqv = TRUE)`。効果量などの引数は実装時にjmvリファレンスで確認する |
| `jamovi_steps.md` | メニューの手順と設定。1〜5の評定は読み込み後に「Ordinal」へ変更する、などの注意 |

- jamoviの`.omv`は自前で書き出さない。公開された仕様に基づかず、形式の変更に弱いため。
- jamovi本体、R、jmvは利用者が別に導入するソフトとして扱い、アプリに同梱もimportもしない。
- **一致テスト：** 架空データをjamovi（またはR＋jmv）で一度計算し、統計量・自由度・p値・効果量をgolden値としてテストに保存する。自動テストはRなしで照合する。
- CSVをjamoviで開いたときの文字化けと型の推定は、実機で確認する。
