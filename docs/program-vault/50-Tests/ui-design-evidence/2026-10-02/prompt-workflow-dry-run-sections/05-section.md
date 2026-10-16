---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run-section-05
title: Gurumoji 設計プロンプト運用の質的dry-run：6 B03にテンプレートを適用したレビュー済みPLAN
summary: 6 B03にテンプレートを適用したレビュー済みPLAN。出典ノート「Gurumoji 設計プロンプト運用の質的dry-run」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-prompt-workflow-dry-run
source_path: 50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run.md
source_sha256: 8821edb6ba72ea01b9284bf1c462724ece9f7752a338ea42958a75d995bf76c3
source_body_lines:
- 117
- 145
split_on: '2026-10-11'
---

# Gurumoji 設計プロンプト運用の質的dry-run：6 B03にテンプレートを適用したレビュー済みPLAN

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/prompt-workflow-dry-run]]。必要な本文だけを取得する。

## 6 B03にテンプレートを適用したレビュー済みPLAN

**目的:** 固定runのAI見解を根拠で確かめ、入力修正後も同じ結果の同じ文脈へ戻る。T6の往復条件とT10の証拠分離を使う。

### 最小変更と状態

1. C09の既存details、生成時snapshot、stale表示、音声前の同一性guardを出発点にする。今ある音声代替本文を保ち、全機構の作り直しを避ける
2. C10のrun/artifact URL→input.json/result.json/manifestを先に調べ、固定viewerの表示field対応を作る。run ID/入力版/生成時引用を確定できないlegacyは「来歴不明」。現在itemを開く既存処理を固定run閲覧と呼ばない
3. 固定閲覧からC11のpipeline status自動retry経路を呼ばない。既存artifact読取を優先し、不足分だけread APIの追加契約にする。GET/POSTの形式より実際のside effectを確認する
4. 既存navigationへitem/run/page/filter/selectedEvidence/scroll/focusOriginを対応付ける。使える既存stateを確認して不足だけ追加し、新しい永続session storeを先に作らない。desktop details＋mobile全幅の軽い案から始める
5. 根拠を閉じる/戻ると同じ固定runと表示文脈を復元する。focus起点が再描画で消えた場合は同じ根拠の操作名へ、存在しなければ結果見出しへ移し、その理由を仕様にする。Back/Forward、再読込、幅変更時の復帰範囲も明示する
6. 入力の本文/話者/時刻が違う引用は現在音声に黙って接続しない。生成時本文と変更理由を示す。音声なし、引用欠落でも確認可能な原文を示し、復元できないものは明示する
7. 入力修正の保存成功/失敗、旧run stale/unknown、新しい分析要求を別状態にする。保存だけで旧runを再計算しない。AI見解「全員が賛成」は主張候補であり、反対/伝聞/質問の根拠へ同じ操作で戻れるようにする
8. 1440/390/320pxで対象run、引用、戻るを常に識別できる。keyboardで開閉、focus復帰、必要なlive通知、固定要素の遮蔽、IME入力/保存を計画する。paneの広さだけを改善根拠にしない

### 受入証拠の計画

- B03-A: R1/revision1の引用を開き、現在revision2と照合。古い本文/話者/時刻を保持し、staleまたはunknownが残る。引用がないとき現在値で補完しない
- B03-B: page/filter/引用/scroll/focus起点を記録→原音/本文→入力修正/保存→戻る。通常pointer/keyboard双方で同じ結果へ戻る。保存失敗はdraftが保持され、旧runと保存済み入力の版が混ざらない
- B03-C: 固定結果を開く/閉じる/Back/Forward/再読込の通信とworker callを監視し、新規推論/retry/外部送信0回。APIがGETでも無条件に合格としない
- B03-D: 表示と既存exportのrun/hash/revision/対象集合・分母を照合。欠測/除外/未実行と0を分ける。固定packageに未提供のXLSXを追加済みと見せない
- B03-E: 合成の反対根拠を見つけられるかはV5で評価する計画。エージェントが答えを知る本稿では誤り発見率/理解向上を測定したことにしない

### データと戻し方

固定成果物はread-onlyから始め、hash検証を保つ。旧hash/引用/runに現在来歴を書き足さず、研究者メモを再生成しない。新しい復帰adapterを戻しても既存details・deep link・音声guardが働き、編集draftや履歴を消さない。固定viewerのpayload対応と再読込時にどこまで復帰するかはまだ確定しておらず、APIを増やす前に契約レビューが必要。

**今回の結果:** C09〜C11のコード照合のみ。B03-A〜Eは未実行。固定run閲覧の新規依存を隠して完成画面として扱わない。
