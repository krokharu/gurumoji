---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-01
title: Gurumoji 改善セッション：Gurumoji 改善セッション
summary: Gurumoji 改善セッション。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 1
- 65
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：Gurumoji 改善セッション

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。


# Gurumoji 改善セッション

## 目的と範囲

2026-10-03 20:50:25 UTC〜2026-10-04 04:50:25 UTC の改善作業。専用ブランチ `dot/gurumoji-eight-hour-20261003` で、UI/UX・分析・プログラミング・全体調整を分担し、根拠のある改善、独立レビュー、回帰試験を繰り返す。

公開、push、deploy、認証変更、有料推論、実Vaultの移行は対象外。合成fixtureを使い、研究者のデータ・原文・所有権、欠測とゼロ、固定runと現入力の区別を守る。

## 復旧の根拠

- 作業環境の置換により、旧checkout・仮想環境・未公開commitの実体が失われた
- 公開リポジトリの `4b311df51c7fe2938f1761cb1efbb4cc4906fd10` を取得し、保管bundleの前提commitと一致を確認
- 保管bundleから `ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0` までの実装を復旧
- 設計資料v0.4の95ファイルをmanifestのサイズ・SHA256と照合し、新commit `2d9bb23` で復旧
- 資料に記録された元commit `d4788938536bef4e13b38af77abeb6b962f504fa` は資料の来歴であり、元の全treeやcommitを復旧したという意味ではない
- 旧後続commit `8d0d277`、`336af40`、`55dbd0f`、`7795485` の完全なソース成果物は確認できない。後続修正は新しい変更として再実装・再検証する。旧テスト件数を今回の成功に流用しない

## 部門の責務

| 部門 | 入力 | 成果物と合格条件 |
|---|---|---|
| UI/UX | 現コード、DESIGN、設計契約、対象画面 | 操作状態・値同期・アクセシビリティ・狭幅の具体的受入条件。静的確認と実画面を区別 |
| 分析 | 合成データ、定義・実行・保存契約 | 定義版、分母、欠測、来歴、保存先の再現可能な検証。未測定を成功としない |
| プログラミング | 優先課題、再現fixture、独立レビュー | 小さな対象変更、明示的な対象fileでcommit、関連試験と回帰試験。ソース変更の単一担当 |
| 全体調整 | 各部門の根拠、変更差分、試験結果 | 優先順位・重複回避・統合判定・次の課題。意味のある節目で復旧可能な成果物を保存 |

## 作業ボード

| ID | 優先 | 課題 | 状態 | 完了の証拠 |
|---|---|---|---|---|
| REC-01 | P0 | 確認可能なソースと設計資料の復旧 | 完了 | base／bundle確認、95 hash一致、2d9bb23 |
| REC-02 | P0 | テスト環境の復旧 | 完了 | project-local venv、CPU torchのみ、pip check成功、依存版記録 |
| COR-01 | P0 | 旧後続修正の再構築範囲を確定 | 完了 | 旧担当の仕様と復旧コードを照合。完全な旧sourceの復元ではない |
| ANA-01 | P0 | 定義版・入力版と実測・出力の一致 | backend受入済 | 9768b80、独立48件・1120定義matrixで違反0 |
| ANA-02 | P0 | 欠測・型・保存scope・世代/復旧 | backend受入済 | 4writer台帳、固定package、Barrier試験、restart3境界 |
| UI-02 | P0 | 対象切替・遅延応答の誤適用を遮断 | 統合済 | c1029e4、request ownership、遅延応答とABAの合成検証 |
| UI-03 | P0 | 測定の試行→確認→採用→実行、簡易/詳細 | 統合済 | c1029e4、7904aa1。4presetを元UI→実Flaskの20要求で独立検証 |
| UI-04 | P1 | 不明時刻・旧根拠の再生guard | 統合済 | c1029e4、無効・非有限・逆転・不明時刻を拒否、実0は維持 |
| UI-01 | P1 | 既存4 effort controlの小型グラフィカルカード | 統合済 | 1875020、候補1934ca2で独立20境界成功。実handlerの方式往復も値を保持 |
| QA-02 | P0 | browser testの安全な起動と明示opt-in | 統合済 | 9b1757d、869b843、5fa689f。安全な既定値と標準収集範囲、子process importの修正 |
| QA-01 | P1 | 最終差分への独立レビューと回帰 | code/DOM受入済 | 721c308で1049 pytest・1052 subtests・161 DOM、失敗0。実browser22/Windows10は未実施skip |
| ANA-03 | P0 | 役割の値と登録・準備・既定来歴を一致 | 統合済 | 7904aa1、候補86f82b5で明示・登録・準備・旧曖昧値を独立検証 |
| UI-05 | P1 | 固定run閲覧・履歴の来歴と4writer状態 | 統合済 | c6e5094、保存要約・表・定義版、読取副作用0、台帳snapshot、長いCSV、全download一致 |
| UI-06 | P1 | 旧役割の来歴不明を説明し同値を明示指定 | 統合済 | e8cb4e8、明示button、旧save応答の別会話・同ID再読込への誤適用も遮断 |
| QA-03 | P1 | 実HTMLと全UI scriptのオフラインDOM統合 | 統合済 | 721c308、同HEADで既定npm test 161件成功。jsdom30.1.1はtest専用。実browser・layout・ATは別途未実施 |
| COR-02 | P0 | 特殊な話者名・未知statusの継承key誤認 | 統合済 | a0c7a60を1a7677fへ統合。literal key、保存往復、prototype不変、未知status表示を独立DOM受入 |
| UI-07 | P1 | 話者表のcontrol名と再描画focus | 統合済 | 3df48e5、表示名変更後も話者ID付きの名前を更新、registry再描画で該当controlへfocusを保持 |
| UI-08 | P1 | 旧route応答が新しい会話表示を取り消す | 統合済 | bbd743c、実popstate配線で応答順2通り・別画面・取消・ABAを独立受入 |
| UI-09 | P1 | 分析Saveの別会話／同ID再読込への誤適用 | 統合済 | bc84d85をed7a3f1へ統合。古い成功・409・500、後続編集、新保存のbusy所有権を独立受入 |
| ANA-04 | P1 | speaker集計の全欠測0秒／不完全な割合・集中警告 | 統合済 | 9c92b6b、実API／固定CSV／旧v4 snapshot不変を独立受入。全欠測graph非描画、真0とpartialを維持 |
| UI-10 | P2 | 同item Saveで固定viewerが検証中のまま停止 | 統合済 | e618d38を9c92b6bへ統合。現編集revisionと独立し、入力比較を「取得時点」と明示 |
| UI-11 | P2 | 役割未設定を含む参加者集計の確定風表示 | 統合済 | 7ae080a、仮集計／不明人数を明記し無限定50%断定を抑制。実API→JS独立10条件、source不変 |
| UI-12 | P2 | 測定定義dialog再openのbusy残存／移動後のmodal残存 | 統合済 | 35378a0、Save/Trial再open・移動の回帰反転、測定定義の実DOM9条件成功 |
| UI-13 | P2 | 分析Save完了後の測定dialogが旧入力版のまま無反応 | 統合済 | c3c1662、定義文言保持・旧trial採用失効・保存済ID保護・自動書込なし、実DOM再保存とdirty対照 |
| ANA-05 | P1 | 同じ話者の発話別role混在による配列順依存 | 統合済 | c6abf58、6並替・除外復帰・全観測分母・旧v5保持を独立受入。15592f1の実DOMで全観測分母とnullable役割量も受入 |
| UI-14 | P2 | 固定run要約で保存計算版とregistry版を区別表示 | 統合済 | 7a6f137、保存記録だけのbounded投影。旧版・欠落・非scalar・省略・有限0を区別、DB/固定package不変、独立APIと実DOM受入 |
| ANA-06 | P1 | 固定packageのmember名・snapshot来歴の不整合 | 統合済 | 998ea4b、危険なmember名と正規化衝突を拒否、入力digest照合、同じ検証済bytesからZIP。破損/復旧境界の独立受入 |
| ANA-07 | P1 | 残る時間系の偽0・library不正時刻500 | 統合済 | a383df1/c1d8cfd、v7で全source終端・感情・コードのnullableとcoverage、真0/空集合、旧v6保持。通常JSON import含め独立受入 |
| UI-15 | P1 | legacy数値文字列と時刻編集後の話者表示不一致 | 統合済 | 97847d1/4c31983。binding付き投影と空JSON markerの既存意味を維持。961組合せと実import/編集/Saveの追加10 DOM、raw保持・音声guard不変を受入 |
| QA-04 | P1 | 偽timelineを除いた後の専門家sample契約 | 統合済 | c456795、production変更なし。emptyとnot_run、結果レビューとblocked前提条件、4空表/固定CSV/固定run不変を明示assert |
| EFF-01 | P0 | cleanup OFFと既存effort互換 | 統合済 | f4d692e、OFF時の校正停止、非OFF強度を思考能力と混同しない |
| QA-05 | P1 | 世代保護テストの並列fixture競合とthread残存 | 統合済 | 9e8a326、両adapter同期とfinally解放。本体不変更、旧競合4条件再現、250反復と70隣接、guard無効化を検出 |
| DEL-01 | P0 | 節目のソースbundleと最終引継ぎ | 受渡し準備 | 復元・再構築したGit履歴bundle、独立clone/fsck、空runtime起動/再起動、読みやすいsource ZIPと日本語手順。最新の版/hashはcheckpoint manifest |
