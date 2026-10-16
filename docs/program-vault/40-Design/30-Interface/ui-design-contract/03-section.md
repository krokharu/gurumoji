---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-contract-section-03
title: Gurumoji UI設計指針：5 部品ごとの実装契約案
summary: 5 部品ごとの実装契約案。出典ノート「Gurumoji UI設計指針」の分割本文。
parent_note_id: design-ui-contract
source_path: 40-Design/ui-design-contract.md
source_sha256: 0a2b9fa0a3c575013504d0f1d458a3927e626353dc7f4d65c1f326aea175c974
source_body_lines:
- 61
- 97
split_on: '2026-10-11'
---

# Gurumoji UI設計指針：5 部品ごとの実装契約案

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-contract/00-Index]]。必要な本文だけを取得する。

## 5 部品ごとの実装契約案

### 対象と表示版の帯

対象名、現在データ／保存済みrun、算出日時、対象数と欠測・除外、更新必要を短く示す。hash・設定全文は詳細へ置く。対象数の意味を曖昧にしない。値がないlegacy runは「版不明」。既存レスポンスと固定packageのartifact読取から始め、表示のためだけに新しい保存体系を作らない。artifactのhash一致は、定義版や研究内容の妥当性の証明ではない。pipeline状態取得のGETは読取専用。固定成果物の閲覧と、再起動後の明示的なresumeを分ける。

### 測定定義と試行レビュー

名称・説明・列名は規則の説明であり計算命令ではない。対応する入力列・規則・型・尺度・手法を見える形で選択／確認し、単位は規則から説明する。任意の自然文による新尺度生成を装わない。

提案フローは「編集→少数で試す→個別値・欠測理由・限界を見る→この定義を採用→全件実行」。初期修正は既存draft/adopted APIとrevisionを利用し、画面内の『試行確認待ち』を新しい永続statusに勝手に追加しない。現行は同一IDのdraft保存が旧adopted行を上書きするため、既採用の変更試行は別draft ID等で保護し、取消時の逆PUTを復旧策にしない。定義または入力版が変わればレビューは再確認対象。現行trialは件数・有効値・input_hashのみで個票IDと欠測理由を返さないため、個票レビューには後方互換のresponse拡張が必要。加えて、受付時bindingの版と実行時に再取得する定義が異なる隔離再現がある。固定定義snapshotを使うか、版不一致で安全停止する実行境界対策を必須とする。人がレビューした事実を保証する採用gateのサーバー強化とは分けて計画する。

通常表示にも試行した定義版・入力版、全体→除外→試行の関係、計算の限界を短く残す。定義変更後は試行を失効させ、編集内容とfocusを保って再試行へ導く。欠測の確認入口は発話を特定できる名前を持ち、固定した試行入力と現在の編集を分ける。

### 結果と根拠

結果cardは質問／手法、対象、値または主張、制約、根拠、次操作を持つ。すべてのcardを大型の装飾面にしない。引用は生成時と現在の違いを表示し、元音声、前後発話、反例へ進める。再生中の発話、編集中の選択、保存した引用は別状態にし、再生追従で編集選択を奪わない。文字修正で原音を編集せず、精密な時刻が無い場合は推定を精密な引用として見せない。desktopの開閉paneとmobileの全幅表示は試作候補。採用前は既存details＋音声往復を保つ。

狭幅の根拠画面でも、照合する主張、AI下書き、取得できた確認状態、主張の限界、選択発話IDを残す。「確認記録なし」と記録の読取不能を分け、人が未読とは断定しない。研究者メモを別状態へ移す案は、戻る／展開の負担を含めて比較する。

### 状態と回復

見出し・chip・主操作・通知を同じ状態表から決める。UIから推測した状態でbackendを上書きしない。

| 軸 | 表示する区別 | 混同しないもの |
|---|---|---|
| 編集／確認 | 未保存・保存中・保存済み・競合、別に人の確認 | 保存済み＝確認済み |
| 実行 | accepted/running/waiting/failed/cancelling/cancelled/completed | 中止要求＝中止完了、通信断＝処理失敗 |
| 結果の版 | 現在入力・固定run・更新必要・来歴不明 | 新しい日時＝同じ入力 |
| 成果物の保存先 | 本体保存、Vaultごとの未選択／処理中／成功／失敗／競合／不明 | 計算完了＝全保存先成功 |

waitingは理由と実際のallowed actionを見せる。現行failedでは同じrunの許可操作が空なので、設定を開く操作を「再試行」と呼ばない。保存済み成果を開く入口は残す。中止は送信中・受付済み・完了を分ける。Vault再試行の可否と範囲も実契約に従い、保存先1つだけをやり直せると先取りしない。全体%は工程基準と明記し、処理時間へ換算しない。

2026-10-12、段階2-1：再起動後は`recovery.pending`と許可操作`resume`から「固定入力から分析を再開」を表示する。待機中の反復pollingを止め、クリックでのみ入力・方針・残りattempt上限を再検証する。failed／cancelledは新しい分析を開始し、同じpipelineを復活させない。

「結果を公開」は「設定済みのVaultにも保存」等の実態に合う文言へ改める。**現行APIのtargetはInput／Orchestrator／Visualizationの3種だが、非空ならその3先とResearchVaultへの処理を試みる。** inputだけの指定でも他2先は台帳上not_selectedになりながら処理経路へ入り、ResearchVault conflictでもpipeline completedになることを[合成probe](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-probes.json)で確認した。実Vaultへの書込み検証ではない。対象配列・not_selected・completedから実際の保存範囲や全4先成功を推定しない。選択を実writerへ渡し、Researchを含む結果を照合するW03の契約対策が必要。旧completedは新しい成功条件へ書き換えず、研究者が削除したノートのmissing保護も残す。publishedは全ノート存在の保証ではない。空配列はこのpipelineのVault工程を省略するだけで、他の自動保存の全体OFFではない。詳細は[独立契約確認](../../../50-Tests/ui-design-evidence/2026-10-02/microcopy-contract-review.md)。

Gurumoji実行環境への保存、閲覧端末へのダウンロード、外部AI送信は別。出力前に固定run／現在filter、含む情報と省かれる重要情報を示し、形式を選ぶだけで全来歴が付くと誤認させない。成功・保持・再試行可能の文言は実装で保証できる範囲に限定する。
