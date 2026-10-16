---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit-section-03
title: Gurumoji 現行デザイン監査と実装可能な改善計画：3. 研究の仕事から整理する5フロー
summary: 3. 研究の仕事から整理する5フロー。出典ノート「Gurumoji 現行デザイン監査と実装可能な改善計画」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-audit
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-audit.md
source_sha256: 29fdac89e90f723f623c7a6e660b4bd780c77d975d1bfbc6d6ada363dc6aeaff
source_body_lines:
- 65
- 125
split_on: '2026-10-11'
---

# Gurumoji 現行デザイン監査と実装可能な改善計画：3. 研究の仕事から整理する5フロー

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-audit]]。必要な本文だけを取得する。

## 3. 研究の仕事から整理する5フロー

### F1. 原音を確認し、分析可能な入力版へ整える

現在: 取込→処理→発話編集→明示保存→分析側の準備記録→入力の確認状態を保存。

改善: 対象名・本文版・未保存件数・未確認件数を同じコンテキスト帯に置く。表示上の「編集済み」「本文・区切り確認済み」「分析用に確認済み」を別の状態にする。AI修正案を適用しただけで人の照合済みへしない。

守るもの: 既存の原本保護、source hash、source segment ID、revision、準備記録。確認のために新しい保存体系を作らない。

### F2. 結果から根拠を確認して同じ場所へ戻る

現在: 結果の根拠details→発話本文・話者・時刻→音声で確認→発話編集画面→見解・文脈検索へ戻る。

改善: 現在の結果ページ／run／選択引用とfocus起点を復帰契約にする。desktopでは根拠pane、mobileでは全幅の根拠画面が候補。paneは「引用を見る」目的に留め、常時3カラムへ増やすことを前提にしない。

守るもの: 過去引用と現在の本文の区別、元音声がない時の本文代替、研究者未確定の候補表示、弱い推論を確定表現へ強めないこと。

### F3. 測定の意味を決め、試して採用する

現状の不足はDG-02。提案する順序は「定義→少数試行→研究者確認→採用→全件実行」。

必須の表示: 入力列、計算規則、分析単位、出力名、単位、型、尺度、集計手法、欠測、試行件数、少なくとも数件の入力と出力の対、適用できない場合の理由。自由記述の説明は構造化規則の代わりではない。

既存対応に限定: 入力列 `speaker/speaker_name/role/text/duration/characters/question_candidate`、規則 `identity/text_length/nonempty/duration/boolean_true`、手法 `frequency/descriptive`。未提供のLLMによる新概念・尺度自動生成を画面上で約束しない。IDは必要なら自動候補を出せるが、実保存IDと履歴は明示する。


### F3の技術依存: UIだけでは保証できない部分

| ID | 区分 | 現行契約と証拠 | 必要な設計 |
|---|---|---|---|
| DG-02-T1 / P2 | 試行レビューのAPI拡張依存 | `trial_definition:258–280` はinput_hash、values、件数を返すが、segment ID付きの個票、欠測理由、定義revision/hashを返さない | 少数の入力→出力対と欠測理由、試行時の定義版/入力hashを紐付ける。現在画面から後で推測補完しない |
| DG-02-T2 / P1 | 採用版保全の技術課題 | 台帳の主キーはitem+definition ID。adopted v1へ同IDのdraft v2を保存すると同じ行を置換し、adopted lookupはdefinition_not_adoptedになる | 新しいdraft ID/不変version等で旧adopted版と編集中draftを分ける。取消・試行失敗をしても旧採用版を選択可能にする |
| DG-02-T3 / P1 | 固定版の実行不整合 | bindingはdefinition_version=1を記録するが、worker開始時はIDだけで最新を取得。受付後v2へ変更するとv2を計算してしまう | 固定definition snapshotまたはID+version+hashの厳密取得。最小安全策は版不一致時に計算前で明示停止し、最新へ黙って置き換えない |

**再現の正確な範囲:** [definition-lifecycle-probe.json](../definition-lifecycle-probe.json)は、合成in-memory SQLite、元workerの定義取得prefix、元manual stepで、v1文字数3に対しv2のduration60を`committed`にすることを確認。監査担当も同じprobeを再実行し一致した。

[definition-full-pipeline-probe.json](../definition-full-pipeline-probe.json)は独立担当の補強検証。受付後のscheduleを一時停止して同IDを変更し、**元M0〜M7オーケストレーターを最後まで実行**すると、全段committed・pipeline completedになる。save adapterへ渡されるpackageはbinding v1／definitions v2／測定値60で混在した。method/save/publication adaptersとデータは合成で、SQLiteは一時領域。実手法・実保存ファイル・実Vault・GUIでの再現とはしない。

この追加検証は「既保存runが消えた」「すべてのrunが誤計算する」という主張ではない。**受付からworker読込までに同じ定義IDが変更される競合条件**で成立する。旧adopted payloadの台帳保全と、実行時の固定版解決は関連するが別の失敗モードとして追跡する。

最小の導入順は、(1)固定版不一致で安全停止、(2)draft/採用版の分離、(3)版付き試行レビュー、(4)明示採用と全件実行のUI接続。永続pipeline自体の作り直しは不要。既存SQLを破壊的に変更せず、必要な版付き情報を追加する。UI2〜4日という元概算だけで閉じず、技術契約と競合/再開回帰を含めて再見積りする。

受入は、受付v1→v2編集でもv1値3を使うか計算前で停止、draft取消後も旧採用版を使える、定義/入力が変わったら旧trialを採用根拠へ流用しない、実packageにも定義版/hashが一致する、まで分けて行う。

### F4. 実行・中断・部分成果を理解する

現在: 永続M0〜M7、実行チップ、バックグラウンド移動、中止、再試行、公開のみ再試行がある。

改善: 主見出しは利用者の状態説明、M番号や永続ゲートは補助。8段階のステッパーと3ノードの処理経路を両方常時強調せず、主表示は現在・完了・次の処理、詳細に内部段階を置く。progressが実作業量に比例しないなら「8段階中3完了」など根拠を添える。

次の操作: 待つ／不足入力を直す／失敗だけ再試行／保存済み結果を見る／公開だけ再試行を区別。失敗後も「バックグラウンドで続ける」という完走前提の文言に頼らない。

### F5. 過去の結果を見つけ、再現可能な出力として渡す

現在: run履歴、成果物リンク、Obsidianへのリンク、Vault再試行。既知UX-34として直近100件上限。

改善: 一覧filter、総数・上限、run選択、入力版、算出日時、対象集合、除外、設定版、モデル/版、表示中snapshot、出力内来歴を一連にする。研究者は「当時の結果を読む」と「現在の入力で計算し直す」を明確に選べる。

守るもの: A04/A05で改善されたstale/fingerprint/旧来歴の保持。不明な旧hashを現在値で埋めない。保存とVault公開を二軸で伝える。
