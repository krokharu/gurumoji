---
note_type: reference-section
status: current
verified: 2026-10-02
updated: 2026-10-11
feature: development-workflow
tags:
- gurumoji/program
- gurumoji/operations
note_id: ops-dot-cloud-development-handoff-section-07
title: dot クラウド開発とローカルへの引継ぎ：未確認・次の引継ぎ
summary: 未確認・次の引継ぎ。出典ノート「dot クラウド開発とローカルへの引継ぎ」の分割本文。
parent_note_id: ops-dot-cloud-development-handoff
source_path: 60-Operations/dot-cloud-development-handoff.md
source_sha256: 8a7d7ab890d3b62cf5023a3580ce42201dfea43900174fe98a80e6db8f0c2c7d
source_body_lines:
- 164
- 203
split_on: '2026-10-11'
---

# dot クラウド開発とローカルへの引継ぎ：未確認・次の引継ぎ

親索引・状態・確認版：[[60-Operations/20-Development/dot-cloud-development-handoff/00-Index]]。必要な本文だけを取得する。

## 未確認・次の引継ぎ

- gated 話者分離、外部 AI、利用者ブラウザーでの一連操作は初期 CPU smoke の対象外。認証・モデル・到達性を別に確認する
- ローカルとクラウドの同期は自動化しない。共通基点から両側の差分を読み、人が採用する内容を判断する。初期タグは保持し、新しい共通基点は双方の受理後に版付きタグで決める
- PC 原本への変更適用、実データの移行、アプリと移入 Vault の接続は別の作業。承認済みの対象だけを扱う
- アプリ修正・設計変更・追加検証がまとまったら、このノートか該当する既存ノートへ対象 commit、結果、残る問題を追記する。未実行や失敗を成功として記録しない


## 2026-10-04: Core・Handler自律分析と低トークン実行UI

実装commitは `91d827141628dec84f8e1d32301b49f901074584`、基点は `0d9239ac9d041d78d298c68a235738b3fe549a2a`、ブランチは `dot/core-handler-orchestration-20261004`。原本とは別checkoutで実装し、元checkoutのHEAD・未コミット変更なしを確認した。Windows原本、移入研究Vault、main、外部remoteへ反映していない。

### 実装と判断

- [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]] に責務・API・追加SQLite形式・停止/復旧・適用範囲を記録
- Coreは問い/見解/不足/次の分析/終了を判断。Handlerだけが正式タスクを登録・発注・保存し、4専門系統へ配分する。数量・統計とHandlerはコード処理として表示する
- 初期全量は入力/設定/テンプレート版で再利用し、全結果・原結果hash・根拠参照・ラベル版を保持。主張変更と終了前の独立検証/批判、Core採否理由、重複抑止を実装した
- 原文を伏せるのではなく期待結論を伏せるblind-firstを維持。保存済みの独立検証結果を説明する対話は当該結果・根拠・説明質問に限定する
- `label_frequency` はrun内の採用ラベル版から対象数/分母/欠測付きで実再集計する。既存参加量/時系列は初期全範囲の参照を維持する。原本ラベルは変更しない
- 時間/回数/重要度/AIお任せと手動停止、プロセス中断、曖昧な外部実行の明示放棄を扱う。期限/取消し後の応答は保存して隔離し、結果不明の呼出しを自動再送しない
- 表示のアニメーションはstatus/event/CSSのみ。再表示・pollingでAI呼出しを追加しない。実測tokenだけを表示し、unknownを0で補完しない
- Obsidian用MarkdownとJSONは全量台帳のダウンロード。研究者所有Vaultへの新しい自動書込み経路を追加していない

### 最終検証

- 対象・境界・adapter・Flask統合の72件成功。ラベル版0集計→Core採用→版1実再計算→旧結果staleを実adapter経由で確認した
- 全JSDOM 172件成功（既存161＋新規11）。終了/復旧/表示再開、遅延応答のlatest-wins、個別確認付きabandon、外部同意、欠測表示、XSSを含む
- 全体pytestの実表示は **1144 passed / 2 failed / 32 skipped / 1085 subtests passed**。2失敗は `test_transformer_provenance.TransformerTruncationTests` のtorch importで、基点でも同じ2失敗を再現した。新機能のassert失敗ではないが、全成功とは呼ばない
- 32skipは実ブラウザー22、Windows専用10。JavaScript構文、Python compile、git diff check、pip check成功。最終全体試験開始から実装commitまでsource/test hashの差分は0
- dotのクラウドブラウザーによるlocalhost表示は `ERR_BLOCKED_BY_CLIENT`。制限を迂回せず実画面画像を未取得と記録。合成状態HTMLは実template/描画関数から生成した静的previewであり、実画面受入や実AI稼働の証拠ではない

証跡は配布source ZIPの `verification/` に収録する。主なファイルは `full-final-tests.log/.xml`、`focused-final-tests.log`、`orchestration-dom-regression.txt`、`baseline-environment-check.log`、`final-tested-tree.json`。UI previewは `ui/orchestration-ui-preview.html`。件数は重複を含むため足し合わせない。

### 未実行・制約と次の確認

実データ、実AI/モデル品質、課金、Windows実機UI、支援技術、Vault自動出版、push/deployは未実行。確認的統計の隔離検証データと金額上限は未対応で、要求を誤って成功扱いしない。運用上限は呼出し数/タスク数、重要度は未校正の仮基準。初期snapshot構築自体の中断は復旧確認で停止する。

ローカルへ採用するときは既存checkoutを保持し、bundleを新しいフォルダーへ復元、共通基点との三者差分を確認する。その後、既存モデル設定を用いた小さな承認済み会話で実動確認し、ブラウザーの表示/動き/キーボード操作を確認する。プログラムVaultと私有研究Vaultを混ぜない。
