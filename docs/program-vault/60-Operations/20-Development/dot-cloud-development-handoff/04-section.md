---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-04
title: dot クラウド開発とローカルへの引継ぎ：2026-10-02 UI設計知識の文書統合
summary: 2026-10-02 UI設計知識の文書統合。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 97
- 114
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：2026-10-02 UI設計知識の文書統合

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 2026-10-02 UI設計知識の文書統合

対象ソースは `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0`（直近実装 `59ebd24`）。設計資料v0.3を取り込み、短いroot `DESIGN.md`、条件付きで資料を読む `gurumoji-ui-design` skill、既存UI criticへの参照、Software Vaultの設計契約・知識索引・実装計画・受入資料を整えた。新しい設計提案は未実装・未受入。skillはプロジェクト内の再利用文書で、自動発見・常駐登録・モデル重み学習を完了したという意味ではない。

- 入口は [[40-Design/30-Interface/ui-design-knowledge/00-Index|ui-design-knowledge]]。全研究packの常時読込は求めず、局所修正は対象コードと契約の該当節だけで進める
- [[20-Modules/40-Interface/ui-screens/00-Index|ui-screens]] の上部3タブ／永続pipeline未実装という古い記述を、現行4入口とM0〜M7にコード照合して更新した。実画面・AT受入日には読み替えない
- 文献・出典台帳・監査・合成probe・静止案を日付付きで保存。v1仕様8図、v2比較8図＋補助2図、初回／修正後レビューを別の利用者実験数へ合算しない。builder、描画ログ、browser profile、私有の研究資料は取り込んでいない
- 対象ファイルとhashは [統合manifest](../../../50-Tests/ui-design-evidence/2026-10-02/integration-manifest.json)、文書・source保全の確認は [統合検証](../../../50-Tests/ui-design-evidence/2026-10-02/integration-validation.json)。アプリのUI受入・モデル品質・利用者評価をこの検証で合格にしない
- この区切りはapp内文書の未コミット差分。source／runtime／tests／依存定義／私有5 Vaultの変更、commit、push、PC反映は実施していない。別checkoutのSoftware Vault更新は既存のcheck→対象確認→apply手順を維持する

## 2026-10-02 UI設計知識v0.4の限定追記

v0.3文書はlocal commit `88f5e3eea245166ee68ed4dc6c3f99c31e149228`へ収録済み。v0.4は4つの作業用設計文書を更新し、[[40-Design/30-Interface/ui-microcopy-state-catalog/00-Index|ui-microcopy-state-catalog]]と追加の合成契約確認を参照できるようにした。source基準は引き続き`ddc23abe`／直近実装`59ebd24`で、文書commitをruntime修正と扱わない。旧v0.3レビュー・manifest・検証は日付と版を付けて保存し、旧DG14項目は書き換えていない。

- API enum／台帳の3targetと、非空指定でResearchを含む4書出し経路を試みる現行処理を区別。subsetと台帳の不一致、Research conflictでもcompletedになり得る合成確認をW03へ集約した。文言だけで解消済みにせず、scope／outcome契約の改修は未実装
- 保存履歴にある全保存bundleの再試行と、新しいpipeline action／Research-only等の部分再試行を分けた。AI見解の送信説明は役割、コード、重要flag、条件付きexpert情報を含む実call内容に対応付ける
- v0.4の差分は未コミットで独立deltaレビュー待ち。アプリsource・tests・依存定義・runtime・私有5 Vaultの変更、UI修正、外部AI送信、pushは実施していない。検証の詳細は[統合検証](../../../50-Tests/ui-design-evidence/2026-10-02/integration-validation.json)を参照
