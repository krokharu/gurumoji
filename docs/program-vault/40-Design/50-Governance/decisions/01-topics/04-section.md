---
note_type: reference-section
status: current
updated: 2026-10-16
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-04
title: 設計判断の記録（ADR）：ADR-125 自律分析は最低3回後にCoreが終了を判断（2026-10-05）
summary: ADR-125の最低3回とADR-124の型付き保存。2026-10-16追補にpackage版2、Q23の内容一致run再利用、固定表統計/出力、試験用DB切替と検証制約を記録。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 49
- 89
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：ADR-125 自律分析は最低3回後にCoreが終了を判断（2026-10-05）

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。

### ADR-125 自律分析は最低3回後にCoreが終了を判断（2026-10-05）

- 状態: 採用・実装。利用者の「最低三回はループし、その後はエージェント判断」の指定をAIお任せの既定へ反映。
- 判断: 新規AIお任せrunへmin_iterations=3を固定。採用済みCore判断を永続台帳から数え、最低回数未満の通常終了は保留し、次のCoreで根拠・代替説明・批判・未解決を再検討する。以降はCoreの提案と既存レビュー契約に従う。追加タスクなしの停止を成功へ読み替えない。
- 判断: 画面/APIの既定はauto、時間/回数上限は既定なし。autoの任意回数上限は3以上。呼出し/タスク上限、手動停止、実行障害、不正応答、レビュー失敗は優先する。明示的な他モードと保存済み条件は保持する。
- 互換性: SQLite列変更・実データ移行なし。最低回数のない旧条件を後から変更しない。プロンプト版はcore-handler-prompts-4-minimum-iterations、版不一致時の復旧停止を維持する。
- 検証/限界: 関連129 unittest、DOM操作26件、隔離した実ブラウザー操作1件成功。実AIの初期試験はCore2回/批判者の旧対象版転記でreview_incomplete、3回達成/分析完了ではない。再試験の最終結果は[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]へ記録する。最低3回は分析品質や全原文の読了を保証しない。
- 関連: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、src/gurumoji/analysis_orchestration.py、services/analysis_orchestration_adapters.py。基点main/2f2479ca638c569f6978bec47c509646bd92ff67の未コミット作業ツリー。
- 追検証: 同日の実AI再試験で採用済みCore3回、最低回数による2回目の終了保留と3回目のquestion_satisfiedを確認。48/323発話の限定範囲と短文question条件。試験用DBの初期化漏れを修正した後、同じ保存済みrunのHTTP200/固定成果物も確認した。全発話の読了や製品の既定questionでの安定性を保証しない。詳細は運用ノートの再試験節。

### ADR-124 分析表の型付きJSON保存とCSV共有出力（2026-10-05）

- 状態: 採用、実装・一時DB/Vaultでの関連160 tests成功。利用者の「オブシディアンに記録したうえで修正して」に基づき、実装前に記録した判断を検証後に更新。実データ移行・実Vault公開・実ブラウザー確認は未実施。
- 背景: 現行CSVはnull/空文字、数値/文字列、配列/文字列、数式対策前後の文字列を一意に読戻せない。全行のCSVが読めることは再分析の再現性を保証しない。
- 判断: 既存AnalysisStoreの新規固定runに、各datasetのtables/<name>.jsonを追加する。table_format_version=1をmanifestと再試行用pending packageへ固定する。CSVは同じ型付き値から従来通り生成し、数式対策と既存bytesを維持する。
- 判断: 表にはrun/input snapshot/revision、列順、列ごとの観測型、全行、run内の安定行IDを保存する。nullと存在しないキーを区別し、元の欠測理由・根拠ID・対象集合/分母/単位の列を保持する。入力にない意味や理由、空表の型を推測しない。
- 判断: 全表を明示的に対応付ける。result.json内の同名/類似配列を推測して重複排除すると全件性を保証できないため、今回の修正は各CSVに必ず1件の型付きJSONを対応させる。新しい独立保存庫や任意ファイル読取APIは作らない。
- 検証: 読戻し時にschema、run/snapshot/revision、行数・行ID、観測型、CSVとの一致を既存hash/manifest検証へ加える。旧CSVのみのrunは閲覧できるが、型付き表への自動復元は拒否する。検証は一時DB/一時Vaultと合成値のみ。
- 互換性/復旧: STORE_VERSION=1と旧readerを維持した版付き追加。完了済み旧run、既存hash、旧pending packageの再試行形式は変更しない。DB schema変更・実データ移行なし。rollback前には保存中runを停止/完了させ、未完の新形式pendingは対応する新版で復旧する。旧writerが新pendingを再試行できるとは扱わない。
- 代替案: CSVへの型推測・欠測補完は不採用。Parquetは容量/性能の実測上の必要が出るまで保留。
- 2026-10-16追補（基点47ecd0aの作業ツリー）: package版2は型付きJSONを正本とし、互換CSVは検証済み表から必要時に生成する。既存の完了run/hashは書き換えず、版1 readerとpending復旧を維持する。固定表からXLSX、native SAVと型保存sidecar、SVG/PNGを生成し、入力・欠測・単位・列の出所を固定する。保存表の推論統計は元run/table hashと計画を参照する別runへ保存し、未検証列を研究者確認済みへ補完しない。
- 2026-10-16追補（Q23利用者決定）: 同内容の別保存要求は既存の検証済みrunを再利用し、要求IDをaliasへ追記する。同一性は入力・revision・手法/モデル/版・条件・結果/表を含み、時刻など生成付随値だけを除く。同じ要求IDの内容変更は拒否し、異なる推論結果を統合しない。既存カラムの削除・変更はなく、追加表/列のみ。
- 2026-10-16検証/限界: 全体1,781件収集・1,748成功・33 skip・失敗0、独立境界レビューの指摘を修正。同一の架空入力9保存で版2は基点より27.9%省容量、保存中央値は31.84→44.90msで増加。ユーザー承認後に試験用DB1会話の履歴切替・WAL・派生生成を実行し、現在の既存値hash不変を確認。実研究Vaultの移動/公開は未実施。詳細・実画面の追加検証は [[40-Design/10-Analysis/analysis-immediate-changes-plan|実施計画の26項目と証跡]]。
- 関連: src/gurumoji/analysis_store.py、handlers/analysis_queries.py、tests/test_analysis_storage.py、tests/test_analysis_fixed_run.py、[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]。基点main/2f2479ca638c569f6978bec47c509646bd92ff67の作業ツリー。

後からAIや人がコードを読んだときに、「なぜこの構造なのか」が分かるように残す。

**ADRの番号**

| 番号 | 意味 |
| --- | --- |
| ADR-001〜099 | 既存コードとノートから復元した、採用済みの判断（`accepted`） |
| ADR-101〜 | 収束フェーズの提案・判断。各項目の状態と採用範囲を参照 |

**運用ルール**

- IDは変えない。
- 判断を置き換える場合は、旧ADRの状態を `superseded` にして、置き換え先へリンクする。
- 実装で判断が変わったら、コードと同じレビュー単位でここを更新する（[[40-Design/50-Governance/program-vault-rules|program-vault-rules]]）。

**各ADRの項目：** 状態、背景（Problem）、決定（Decision）、理由、代替案、結果・影響、関連コード。

---
