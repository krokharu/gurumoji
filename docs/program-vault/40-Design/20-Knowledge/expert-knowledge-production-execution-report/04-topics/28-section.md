---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-28
title: 専門家知識制作・実行報告書：2026-09-28 12:23 UTC A100 online focus groups and participation-balance batch
summary: 2026-09-28 12:23 UTC A100 online focus groups and participation-balance batch。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 341
- 355
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：2026-09-28 12:23 UTC A100 online focus groups and participation-balance batch

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

### 2026-09-28 12:23 UTC A100 online focus groups and participation-balance batch

- Poliandri et al. (2023) のFrontiers公式論文Table 2と§4.2.1から2件を生成し、原文と既存Claimを照合して未承認候補として受理した。(1) 北部エミリア＝ロマーニャの教員グループは参加者あたり平均発話数5.57、標準偏差3.59。(2) この研究の参加者は司会者の「真の傾聴」と「効果的な要約」の役割を認識したと報告された。どちらも単一研究の記述・参加者評価として限定した。[Frontiers publisher article](https://www.frontiersin.org/journals/sociology/articles/10.3389/fsoc.2023.1145264/full)。
- Commit SHA-256はjob 01 `5befad60479c9c6a82462a1a4c0040bac8f54f70ed422e7c796af8f778b16db9`、job 02 `1306a20e824be44d4473b2db5c3d95dec48b4db0f11bf43f24c82851279c659a`。結果ZIP SHA-256は`79ceb3f0c7aaad9e564019a4cb591111c135c8161122c2a4e4541a7cfb90ddb9`と`0d258d48f8b29d372d614c84239717a3bef353617f96a5750ccf0858bdb3991a`。PDF Source SHA-256は`ceff84c3d635dcc5f9ed70218851055e907d97817e13d92250b5a75ffd66058c`、選択した言い換え根拠スナップショットは`d8b3f3f084d41ca2e1de900f9df9a874cac702a83fca94bc7703b2d2511581ea`。
- PreflightでA100-SXM4-40GB StandardとTransformers 4.51.3、Tokenizers 0.21.4、Hub 0.30.2を確認。推論は1,691 input tokens、211 output tokens、39.735秒。残高は86.28から86.21 CUへ減少し、停止後のactive sessionは0。
- primary JobStoreは90 accepted Commit（89 Claim、90 Source）、全17領域、整合性エラー0、Pack 0。P6の体系整理・反復評価・Pack承認は未完了。

### 2026-09-28 13:25 UTC A100 correlation API batch

- SciPy v1.18.0公式`stats.pearsonr` APIページ（SHA-256 `9999856b875cf15abcad22654b16bd3d2801f89eef28b42a048114e93eac68c3`）から`exp-correlation`向けに7回推論した。最終的に3件を根拠照合し、未承認候補Commitとしてprimary JobStoreに登録した。(1) `PermutationMethod`または`MonteCarloMethod`でp値計算の再標本化方式を選べること、(2) `PearsonRResult.confidence_interval`の既定がFisher変換であり、退化した再標本化により非常に小さい標本で信頼限界がNaNになること、(3) `BootstrapMethod`を指定すると`scipy.stats.bootstrap`に計算が委譲されること。[SciPy v1.18.0 API reference](https://docs.scipy.org/doc/scipy-1.18.0/reference/generated/scipy.stats.pearsonr.html)。
- Commit SHA-256はjob 03 `b704029d9d69a6cd5fcf6206e9521cebb5e64c45b8f566bd52dcd1decae346a8`、job 04 `98522e6519704f43b801a10f828f623078fb6bc21a5d3ad61338c728fe1c25f8`、job 07 `fb9f88e8878eecfe59042eb58497bef3620924f5cfd6d4c9ca028a402333e306`。対応する結果ZIP SHA-256は`7ff9467a33973f38ab10e5e0b17d5d9b8f2b5458fcf743ef5daad54befca0f9f`、`213fb1fc513ea0325c42a028ea162e8877ba35381000c2304851170b572af433`、`114c763098dd70e12d591d18659c73e81725b3b858f06b5d6b31b380a646fbbc`。バンドル・Source・抜粋・証拠スナップショットのSHA対応は`output/knowledge-colab-batch/b20260928t132500.json`に記録した。
- 4件は保留した。job 01は生成Claimが抜粋と48文字以上重なり重複防止器に拒否された。job 02は例外欄に編集指示を含めた。job 05は「退化した標本」とし、原資料の「退化した再標本化」とずれた。job 06は`confidence_interval`を`interval`に誤記した。各修正版を同じSourceの新しいハッシュ付き抜粋で再生成した。API機能は研究デザイン上の独立性・交換可能性を保証しないため、その適用を自動的に勧めるClaimにはしていない。
- A100-SXM4-40GB StandardでTransformers 4.51.3、Tokenizers 0.21.4、Hugging Face Hub 0.30.2をインストールし、カーネル再起動後にGPUとimport版を確認した。usage記録のある6結果は4,593 input tokens、783 output tokens、129.206秒。重複防止器が止めた最初の出力にはusage記録がないため、この小計には含めていない。残高は85.07から83.31 CUへ1.76 CU減少。A100セッションは停止し、active sessionは0。
- 読み取り専用監査でprimary JobStoreのSQLite integrity `ok`、95 accepted Commit、94 Claim、95 Source、17/17 expert domain、整合性エラー0、Knowledge Pack 0を確認した。相関のClaim数は7。SciPy文献ノート、相関の事例表・未解決事項を更新した。候補の承認・公開とP6の体系的な重複整理、17領域の評価は未完了。
