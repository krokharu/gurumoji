---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: test-ui-design-scenarios-section-03
title: Gurumoji 研究作業シナリオと受入条件：S03 長時間処理の失敗と保存先の競合から戻る
summary: S03 長時間処理の失敗と保存先の競合から戻る。出典ノート「Gurumoji 研究作業シナリオと受入条件」の分割本文。
parent_note_id: test-ui-design-scenarios
source_path: 50-Tests/ui-design-scenarios.md
source_sha256: 9f71d53a14ce91325066d6751cab56455b58336565bdb774708972b1304959db
source_body_lines:
- 64
- 85
split_on: '2026-10-11'
---

# Gurumoji 研究作業シナリオと受入条件：S03 長時間処理の失敗と保存先の競合から戻る

親索引・状態・確認版：[[50-Tests/30-Interface/ui-design-scenarios/00-Index]]。必要な本文だけを取得する。

## S03 長時間処理の失敗と保存先の競合から戻る

**研究者の仕事:** 会話Aの分析を開始し、待つ間に会話Bの編集を行う。失敗した場所だけ回復して保存済み結果を見る。

**入力:** AとB、Aのpipeline、Bの未保存編集。accepted→running→waiting、failed、中止送信中→cancelling→cancelled、completedの各分岐。計算・本体保存済み＋VisualizationVault conflict、および3生成先成功＋ResearchVault conflictの条件。対応: DG-03/11と追加契約確認、W03、UX:K11/UX:K12。

1. 開始前に対象A、基礎pipelineの処理、計画相談の有無、Vault保存先を確認する
2. 実行中にBを開いて1発話を編集し、Aのchipへ戻ろうとする。confirmLeaveで移動を中止してBのdraftを保つ分岐と、Bを保存してからAへ移る分岐を確認する。未保存確認を無視した複数対象draft保持を前提にしない
3. waiting理由を見る。条件を直す操作と再試行の違いを確認する
4. failed時に見出し・現在工程・保存済み成果・次操作を読む。通常workspaceへ戻る
5. 別ケースで中止要求直後と中止確定後を観察する。完了との競合も試す
6. Vaultだけ失敗したケースで本体結果を開く。Research conflictでも既存保存履歴の「保存済み結果から再試行」は全保存工程を再訪できるため、その範囲を確認する。OFFだった未実行runのpendingから同経路を使う場合は、初回の「Vaultにも保存」と範囲を確認し、再試行と混同しない。pipeline completedに新たな再試行actionを置く場合や、Researchのみ等の部分再試行はW03の別契約後に試す
7. 画面更新・Back/Forward・通信取得失敗を試し、最後に確認した状態と新しい状態の区別を見る

**受入:** A完了でBの作業対象・draftを自動置換しない。明示的な移動は既存の未保存確認を通り、移動中止時のdraftと保存後の本文をそれぞれ保持する。failedを実行中、中止送信中／cancellingを中止済みとしない。failedのreviewが設定を開くなら再試行と呼ばない。通信断をbackend failedと決めつけない。retryは表示範囲と実writerが一致し、計算／外部AIを再実行しない。閉じても続く範囲の説明が実際のserverライフサイクルと一致する。

**保存scopeのgate:** 空／全3先／inputのみを別fixtureにする。現行の[合成probe](../../ui-design-evidence/2026-10-02/microcopy-contract-probes.json)では空のVault callbackは0、非空の両ケースはResearch込み4経路attemptで、Research conflictでもcompletedだった。改修受入では、部分集合を明示4xxでwriter前に拒否する暫定案、又は実対象だけを呼ぶ完全案に従い、要求→有効保存先→writer trace→outcome→台帳→画面を照合する。対象外writerは0回。OFFはこのpipeline限定で、Research pendingを今回の保存失敗と表示しない。旧completedやpublishedを全4先／全ノート存在へ読み替えず、削除されたノートのmissing保護と競合・不明を残す。部分再試行と再起動後のscopeも同じ境界で確認する。

**理解の問い:** 「計算は終わっていますか」「今回、どこへの保存を試みましたか」「どの保存結果が未完了・不明ですか」「この再試行で何がもう一度走りますか」。『完了』一語だけで全保存先や研究者確認まで済んだと受け取られないかを観察する。

**証拠:** 各stateの見出し・操作・live通知、API spy、B draft、run／publicationレコード。現行でもworkspaceへ戻れるため『失敗時に全結果を失う』を前提にしない。
