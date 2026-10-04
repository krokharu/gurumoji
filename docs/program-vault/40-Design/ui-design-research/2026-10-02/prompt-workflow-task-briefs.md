---
note_id: "ui-archive-40-design-ui-design-research-2026-10-02-prompt-workflow-task-briefs"
note_type: "research-reference"
title: "Gurumoji 設計依頼に再利用する小さいタスクbrief"
summary: "2026-10-02の研究・設計・検証記録の保存版。提案や静止図を実装・操作合格へ置き換えない。"
status: "current"
updated: "2026-10-02"
source_head: "ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0"
tags: ["gurumoji/design", "gurumoji/ui"]
---

# Gurumoji 設計依頼に再利用する小さいタスクbrief

2026-10-02 UTC · 基準HEAD `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0` · 計画作成用

この3件は[質的dry-run](../../../50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md)で使用した依頼文。テンプレートは[prompt-research.md](prompt-research.md)のT番号を指す。同資料のオリジナル文面であり、ベンダー公式テンプレートの転載ではない。**共通条件＋対象briefを1件だけ**渡す。将来の実装依頼へ転用するときも、別途実装範囲の承認が必要。

## 共通条件

> Gurumojiの既存実装を前提に、レビュー可能な実装PLANだけを作る。アプリ・設定・DB・Vault・認証・モデルを変更せず、外部API、実データ、push/deployを使わない。まずAGENTS.md、HEAD/差分、知識索引の対象W/DG、関連コードと隣接テストを確認する。DESIGN初稿は意図、コードは実装の正本。Flask/素のJS、URL/DOM ID、revision/run、研究者所有ノートを維持する。出力は現行根拠、最小変更、状態/失敗/復帰、受入証拠、データ/戻し方、未確認。T10に従い、コード確認・既存probe・今回実行・未実行を分ける。V1〜V5を混ぜず、通常pointer/keyboard、1440/390pxと該当320px・拡大・IMEを計画に含める。

参照入口: [設計知識索引](../../ui-design-knowledge.md)、[設計契約](../../ui-design-contract.md)、[実装計画](../../ui-design-implementation-plan.md)。全資料を無条件に連結しない。

## B01 個別分析を普通に開始できる入口

使用: T1＋T10 · W01/DG-01/S01

> 保存済み会話Aからテーマ分析、AI見解、発話分類を通常操作で開始し、保存済み結果へ戻れる計画を作る。中止は既存の取消対応がある処理で確認し、分類の取消能力を装わない。基礎pipelineへ個別分析が統合済みと仮定しない。現行の非表示selector、生成・取消control、provider/dirty/実行中guard、案内先と実panel位置を照合し、全hidden解除ではなく最小の可視入口復元を提案する。送信対象・接続先の説明と実payloadを合わせる。
>
> 合成fixtureは未実行/旧結果/実行中、dirty、provider不足、遅延/失敗。受入証拠はproduction CSSで一覧から通常pointer/Tab/Enterで3入口へ到達する記録、visible/enabled/実矩形、正しいitem/provider/revisionの要求が1回のroute spy。連打・中止・別item・戻る、閲覧だけの再実行0回も確認する。JS clickやCSSなしfixtureを可視操作の合格にしない。保存schemaを変えず、入口adapterを戻しても履歴/入力を失わない案と、V3ができない場合のnot-runを示す。

詳しい合格条件: [S01](../../../50-Tests/ui-design-scenarios.md#s01-個別の分析を見つけて実行する)

## B02 手動測定を試して明示採用する

使用: T11＋T10 · W02/DG-02/S02

> 「発話の長さを秒で測り、少数例を見てから採用する」フローのPLANを作る。説明文が計算命令にならない現行default、validator、trial response、同一IDのdraft保存、受付から実行までの版を照合する。個票/revisionの不足をUIで推測補完せず、必要なAPI拡張と実行境界対策を分ける。既採用IDの修正試行は別draft等で保護し、取消の逆PUTを復旧にしない。
>
> fixtureはe1「あいう」3文字/60秒、e2「abcdefghij」10文字/2秒、e3時刻欠測、e4真の0秒。証拠はduration=60/2/欠測/0、文字数=3/10、名義尺度の平均拒否、個票ID/欠測理由、採用前adopted PUT/pipeline POST=0、明示採用と実結果の版一致。試行後変更、409、閉じる/戻る、受付後の定義変更・再起動/retryも計画に入れる。受付内容で計算するか安全停止し、別版の値を成功確定しない。レビューUIとサーバーの人のレビュー保証を区別する。旧run互換とrollback未決定点を隠さない。

詳しい合格条件: [S02](../../../50-Tests/ui-design-scenarios.md#s02-定義したつもりの測定と実際の値を照合する)

## B03 結果の根拠を確かめ同じ場所へ戻る

使用: T6＋T10 · W04/DG-06・DG-12/S04

> 固定runR1の見解から根拠発話/原音を確認し、必要なら現在入力を編集・保存してR1へ戻るPLANを作る。現行details、音声前の同一性guard、復帰state、固定artifact URLを確認する。desktopは既存detailsを基準とし、390pxでも根拠と戻る操作を失わない。大きいpaneや新しい永続storeは前提にしない。
>
> fixtureは合成の賛成/反対/伝聞/質問、R1の入力revision1、現在revision2、音声なし、引用欠落、legacy来歴不明。証拠はrun/入力版/引用の対応、変更済み時刻や本文から現在音声へ黙って移らないこと、同じ結果page/filter/引用/scroll/focusへの復帰、保存失敗時draft保持、表示とexportのrun/hash一致。固定閲覧では推論・retry・外部送信0回。pipeline status GETの自動回復経路を使わず、既存artifact読取を先に検討する。古い来歴を現在値で補わず、AI見解と研究者の判断を分ける。互換linkと研究者ノートを保つrollback、未実装の固定viewer依存、V3/V4/V5未実行を示す。

詳しい合格条件: [S04](../../../50-Tests/ui-design-scenarios.md#s04-根拠を確認して編集し同じ結果へ戻る)

## 渡す前の確認

- HEADが違えばW/DGの行番号を再確認し、古いprobeを現行成功へ転用しない
- brief中の受入値は**期待値**。実行結果を埋めるまではpassedではない
- 実装者には関連コードを読む権限だけで変更権限まであると解釈させない
- 外部送信0回は今回の検証条件。個別AI分析の本番能力を外部送信なしと説明する根拠ではない
