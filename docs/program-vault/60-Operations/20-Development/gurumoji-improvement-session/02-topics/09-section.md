---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-09
title: Gurumoji 改善セッション：同日：CSVの保存用途を評価
summary: 同日：CSVの保存用途を評価。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 191
- 204
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：CSVの保存用途を評価

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：CSVの保存用途を評価

- 利用者の依頼により、現行`AnalysisStore.save`/`csv_bytes`と固定結果readerを評価。CSVは全件の表計算・共有用として維持し、AI再分析や統計へ渡す正本は型・欠測・版を検証するJSONを優先する判断。現行もCSV単独保存ではなく、SQLite台帳とinput/parameters/result/manifest JSONを併用している。
- 実データを使わず、現行csv_bytes→csv.DictReaderで合成10値の往復を確認。null/空文字、数値0/文字列0、false/文字列False、数式風=A/元からの'=A、文字列配列/そのJSON風文字列の5組がそれぞれ同じCSVセルになった。前回の48種CSV読取成功は構文と出力件数の確認であり、元の型や欠測を無損失復元できるという確認ではない。長いセルのWindows互換修正も、この区別を解消しない。
- [既存FLOW-1提案](../../../../40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index.md)に沿い、result.jsonで全件を保持できない表だけschema版・列型・安定行ID・欠測理由を持つtables/*.jsonを追加するのが次の候補。JSONにも列の単位・分析対象集合・分母・入力版/発話ID/run ID/hashの契約が必要。[JSON Schemaの型検証](https://json-schema.org/understanding-json-schema/reference/type)を根拠に検証方法を具体化できる。大量表の容量・読取性能が実測で問題になれば、[Parquet](https://parquet.apache.org/docs/overview/)を別途比較する。今回は形式変更・移行・追加実装を行わず、旧成果物のbytes/hashと数式対策を維持する。

### 同日：Software Vaultに記録後、型付き全件表を実装

- 利用者の追加依頼により、[[40-Design/50-Governance/decisions/00-Index|ADR-124]]を先に記録してからAnalysisStoreを修正。基点main/2f2479ca638c569f6978bec47c509646bd92ff67の未コミット作業ツリー。result内の同名配列の全件性を推測する方式は避け、新規runの各CSVにJSON表を対応させた。保存先/DB schemaは変えず、manifestとpendingへ表形式版1を固定する。詳しい契約は[[30-Data/20-Analysis/analysis-storage-v1/00-Index|analysis-storage-v1]]に集約。
- 全行・型・null/空文字/存在しないキー・根拠を保持し、run内行IDと入力snapshot/revisionを記録。read_tableは既存hash/manifest検証に加え、schema、行数/行ID、観測型、CSVとの一致を照合する。未知の版・欠落・改変時は停止する。意味上の単位/欠測理由を創作せず、汎用の後続分析/変数定義までは追加していない。Researchの手法ノートにはJSON全件表と共有CSVを既存所有権保護経路でリンクする。
- 旧CSVのみの完了runは閲覧/ZIPを維持し、JSON表を後付けしない。旧pendingの復旧は旧形式、新pendingの復旧は元データと保存時の形式を維持する。新形式の保存中runを旧writerで再試行するrollbackは未対応で、停止/完了後に切替し未完分は新版で復旧する。
- 検証: 最終関連unittest **160成功・失敗0、115.296秒**。fixed run、storage、queries、自律分析公開、milestones、pipeline regressions、自律分析統合/durable、interview comparison、CSV上限を対象とした。型の衝突5組、221行の全件取得、空表/全null、NumPyのJSON互換float、改変/非有限値/非文字列キーの拒否、新旧保存失敗の復旧、旧形式の安全なUnicodeパス、ノートの編集履歴/削除保護を確認。初回の再試行引数漏れは修正し、WindowsのUTF-8ノート読取をテストで明示した。git diff --checkと対象Python compileも成功。
- 一時DB/Vault・合成値のみ。実DB/実Vaultの移行・公開、音声/実モデル推論、実ブラウザー操作は未実行。検証metadataと変更コードhashは`output/malatang-storage-final/verification.json`。既存のマーラータン試験結果は上書きしない。
