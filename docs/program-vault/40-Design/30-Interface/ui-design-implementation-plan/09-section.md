---
note_type: reference-section
status: proposed
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
review_repository_head: 88f5e3eea245166ee68ed4dc6c3f99c31e149228
tags:
- gurumoji/design
- gurumoji/ui
note_id: design-ui-implementation-plan-section-09
title: Gurumoji UI改善の実装計画：5 移行と記録の共通方針
summary: 5 移行と記録の共通方針。出典ノート「Gurumoji UI改善の実装計画」の分割本文。
parent_note_id: design-ui-implementation-plan
source_path: 40-Design/ui-design-implementation-plan.md
source_sha256: 6521f18593584f6fc5ac64f5d4918b2ec5a9d29c9644cae72ab010ef731f00c2
source_body_lines:
- 203
- 232
split_on: '2026-10-11'
---

# Gurumoji UI改善の実装計画：5 移行と記録の共通方針

親索引・状態・確認版：[[40-Design/30-Interface/ui-design-implementation-plan/00-Index]]。必要な本文だけを取得する。

## 5 移行と記録の共通方針

保存済みrun／定義／研究者メモの一括変換を前提にしない。UI adapter、文言、readonly文脈表示から始める。保存契約を広げる段階では旧reader互換、一時データのdry run、backup、前版へ戻したときの読取、再開方法を先に用意する。rollbackはコードを戻しても新しい研究者編集を消さない方法にする。

dotで調査・実装・検証を進め、節目に既存Software Vaultを更新する。0.3文書は`88f5e3e`で統合済み。本0.4更新をSoftware Vaultの文書へ反映した。以下のruntime修正・受入は未実施であり、文書の統合を実装完了にしない。

- `20-Modules/ui-screens.md`: 現行map、入口、操作・状態の説明
- `40-Design/decisions.md`: 採用した代案、互換性、採用しなかった案の理由。局所CSS変更ごとにADRを量産しない
- `60-Operations/dot-cloud-development-handoff.md`: commit、成功／失敗／未実施、成果物参照、残る環境・受け渡し課題

節目の記録形式: 「対象commit／W・DG ID／採用した変更と理由／守った契約／実行した検証と対象版／未実施／次の担当が判断する点」。研究者所有ノート、runtime、移入Vaultには開発記録を書き込まない。

## 6 開発着手チェックリスト

**確認済み事実・既存契約として引き継ぐ**
- [ ] 対象HEADでDG-01の入口、DG-02の暗黙規則／採用／版ずれを再確認する。修正をレイアウト選好の決定待ちにしない
- [ ] 原25件の区分、既存API／URL／ID、研究者編集、固定run、欠測と0、AI下書きと人の採用を保護する
- [ ] 仕様v1は8図、clean v2は比較8図＋補助2図と識別する。MCの静止改善を実行・保存・GUI・ATの合格に数えない

**技術判断と実装のgateが残る**
- [ ] W02はルール復元を推奨し、文字数限定の短期案も明示する。不一致安全停止／固定snapshot、trial固定入力、旧worker互換を決めて試験する。永続レビューgateは別判断
- [ ] W04は固定viewerのlookup／field／route／復帰／legacy停止条件を満たす。利用不能な原音や現在発話への入口を成功状態として描かない
- [ ] W03は3種のAPI targetと実際の4書出し経路を区別し、scope guard・各先outcome・再試行範囲を試験する。送信説明はAI見解の付与情報まで含める
- [ ] V3／Windows／ATの正規実行環境と未実施の記録先を確保する。sandbox Chromium起動失敗は未解決として引き継ぐ

**将来の利用者検証で選ぶ**
- [ ] Aを暫定導入候補に留め、M＝定義配置、E＝根拠表示、N＝入口再編を分けて比較する。B mobileのメモ往復も課題へ含める
- [ ] 密度・文字・狭幅は同じ必須情報で比較する。主指標は正しい版での完遂と誤認発見、時間・好みは補助。重大な保存／研究誤認があれば採用を止める

チェックは着手担当の確認用で、現時点の実装完了を表さない。W00とfixture設計は独立に進められ、今すぐ利用者へ全選択の回答を求める必要はない。
