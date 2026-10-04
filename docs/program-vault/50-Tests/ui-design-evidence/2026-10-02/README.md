---
note_id: test-ui-design-evidence-2026-10-02
note_type: evidence-index
title: "UI設計調査の証拠保存範囲（2026-10-02）"
summary: "対象HEADに固定したコード監査・合成probe・静止図レビューの索引と限界。"
status: current
updated: 2026-10-02
tags: [gurumoji/design, gurumoji/tests]
---

# 証拠の保存範囲

[現行監査](current-design-audit.md)と[DG対応表](current-design-evidence-matrix.md)は基準HEAD ddc23abeの記録。[独立反証](adversarial-checks.md)と[静止図批評](mockup-critique.md)も観測の種類・対象版を維持して読む。保存日のstatus: currentは「この日付の記録を維持する」という意味で、現在の実装に全指摘が残ることやUI受入済みを示さない。

- JSONは当時の観測結果、Markdown表はその表示用view。ファイル名のcurrentを将来の最新結果と読まない
- 原25件の状態は[元の受入表の保存版](prior-25-acceptance-matrix.md)。新DG／静止案MCと別に扱い、指摘件数や評価件数を重複加算しない
- probeのPython／JavaScriptは合成データで行った当時の検証を説明する保存資料。元環境のpathや出力設定を含むため、このfolderからの再実行を検証・指示したものではない。appの自動テスト・実行経路には登録していない
- 元manifestのsource pathはrepo相対のコード、出力pathは当時の検証環境を表す。元hashを、移設時のMarkdown属性・リンク調整後のhashと混同しない
- [統合manifest](integration-manifest.json)は同梱対象・入力hash・取り込み後hashを記録する。新しい評価は日付・実行版・記録版を区別して保存し、過去の成功／失敗／未実行を書き換えない

実画面、production CSSでの操作、AT、利用者評価の不足は[受入方法](../../ui-design-acceptance.md)で扱う。資料の存在、構文合格、静止図の見やすさからこれらを合格にしない。

## v0.3の保存とv0.4の追加確認

[旧manifest](integration-v0.3-manifest.json)、[旧検証](integration-v0.3-validation.json)、[旧独立レビュー](integration-v0.3-independent-review.md)は20:34:31 UTCのv0.3記録。対象の文書bytesはdocs commit `88f5e3eea245166ee68ed4dc6c3f99c31e149228`で確認する。そこに列挙されたhashを、更新後の作業用文書へそのまま照合しない。現在の取り込み一覧は従来の統合manifestを使う。

v0.4では[文言・保存・送信契約の独立確認](microcopy-contract-review.md)とcontract/action probeを追加した。元コード＋合成入力／adapter／DOMの確認であり、実Vault書込み、外部AI、実GUIの試験ではない。3 API targetに対してResearchを含む4経路が動く条件、subsetと台帳の不一致、completedの限定、既存履歴の全保存bundle再試行を区別する。修正の実装・受入や、新しいtarget enumの追加は行っていない。

旧DG14項目と原25件は当時のまま保持する。J01〜J25は文言の対象箇所であり、25件の追加不具合を示さない。対応する案は[文言仕様](../../../40-Design/ui-microcopy-state-catalog.md)と[実装計画](../../../40-Design/ui-design-implementation-plan.md)のW03を必要時だけ読む。
