---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns-section-01
title: Gurumoji の研究作業に使う公式 UI 参照パターン：Gurumoji の研究作業に使う公式 UI 参照パターン
summary: Gurumoji の研究作業に使う公式 UI 参照パターン。出典ノート「Gurumoji の研究作業に使う公式 UI 参照パターン」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns
source_path: 40-Design/ui-design-research/2026-10-02/reference-patterns.md
source_sha256: f1334e394b188d0ff4c52216c8a7ff37e52789869513174579c3868d7764a702
source_body_lines:
- 1
- 47
split_on: '2026-10-11'
---

# Gurumoji の研究作業に使う公式 UI 参照パターン：Gurumoji の研究作業に使う公式 UI 参照パターン

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/reference-patterns]]。必要な本文だけを取得する。


# Gurumoji の研究作業に使う公式 UI 参照パターン

調査日: 2026-10-02 UTC（2026-10-03 JST）  
対象: 原音 → 文字起こし → コード／テーマ候補 → 根拠確認 → 出力の往復  
前提資料: [現行監査](../../../../50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md)、[UX 根拠調査](../ux-research.md)  
成果物の性格: 公式マニュアル・ヘルプと公式掲載画像を比較した設計提案。製品の実操作試験、性能比較、利用者テストではない。Gurumoji のアプリソースは変更していない。

## 結論

**参照すべきものは画面全体の外観より、根拠への戻り口、変更前後の境界、処理と保存の区別である。** MAXQDA、ATLAS.ti、Dovetail、Descript の4製品を、役割の異なる参照例として選んだ。

Gurumoji へ先に取り込む候補は次の5点。

1. 結果やコードから原文・原音を開き、元の結果の対象・版・位置へ戻れる契約を作る
2. 原文、既存コード、AI 提案、今回適用する差分を比較できるようにする
3. 文字修正、時間合わせ、原音の編集を別操作として明示する
4. 処理中でも別作業へ移れ、実行対象へ戻れる固定入口を残す
5. 引用だけでなく、入力版・対象範囲・時刻精度・出力の省略項目を持ち運べるようにする

特に重要な反例もある。Dovetail は本文の版履歴を提供する一方、公式資料は復元で highlight の位置が戻らないこと、再文字起こしで既存 highlight が除かれることを説明している [R12, R13]。**「履歴がある」「引用を開ける」だけでは、入力変更後の引用の正しさは保証できない。** Gurumoji の source hash・segment ID・revision・固定 run を弱めず、古い引用と現在本文の区別を維持する。

## 1 調査範囲と根拠の強さ

### 読み分け

- **M（Manual）**: 公式本文が操作や制約を説明している。ここで動作確認したという意味ではない
- **S（Screenshot）**: 公式が掲載した画像を実際に画素で閲覧した。静止状態の配置や表示だけを支持する
- **L（Live）**: 製品を実操作して確認した。本調査は全製品で **L なし**
- **D（Design inference）**: Gurumoji への適用案。効果や実装可否が確認済みではない
- **不明**: 今回の資料に十分な記載がない。「機能がない」という製品評価ではない

各出典の閲覧日は上記調査日。更新日のないページについて、検索結果の crawl 日を公開日や実装日として扱わない。ATLAS.ti はタイトルで Windows 26 と確認できた資料を使用。MAXQDA は `/help/` の現行オンラインマニュアルで、スクリーンショットの個別 build は不明。Dovetail／Descript は現行ヘルプへの redirect 先を採用し、旧ヘルプの検索要約と混在させない。

ログイン、サインアップ、実データ投入、有料機能の利用は行っていない。第三者ブログ、比較サイト、コミュニティ投稿は製品挙動の根拠に採用していない。公式の宣伝的な「高精度」「完全な透明性」も独立した実証として扱わない。

### 4製品を選んだ理由

| 製品 | この比較で担う役割 | 確認範囲 | 主要な境界 |
|---|---|---|---|
| MAXQDA | 原文と coded segment の往復、コード見直し、出典付き出力 | M、S 3枚 | Desktop の高密度作業面を Web／狭い画面へ丸ごと移さない |
| ATLAS.ti Windows 26 | 引用を独立した対象として扱うこと、マルチメディアの範囲・時刻・コメント | M、S 1枚 | 引用番号と不変 ID、推定同期と精密時刻を混同しない |
| Dovetail | highlight から証拠付き知見へ進む Web の軽い導線、AI 候補の承認、版・出力制約 | M | 参照したhero画像は取得不可。外観や実操作の良否は判定しない |
| Descript | 文字修正とメディア編集の分離、音声と語の alignment、処理／sync の区別 | M | 映像編集向け操作を研究原本の修正に転用しない |

NVivo も初期探索したが、今回取得した playback／framework matrix の公式ページは 12／20 系だった [R22, R23]。現在版の同一機能を確認せず並列比較に入れるのを避け、今回は上の4製品に絞った。NVivo が劣る、機能を持たない、という判断ではない。Otter の追加調査は、Descript で必要な文字修正・音声同期の反例が得られたため行っていない。
