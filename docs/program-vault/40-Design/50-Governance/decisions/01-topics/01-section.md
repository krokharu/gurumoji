---
note_type: reference-section
status: current
updated: 2026-10-08
tags:
- gurumoji/program
- gurumoji/design
- gurumoji/adr
note_id: design-decisions-section-01
title: 設計判断の記録（ADR）：設計判断の記録（ADR）
summary: 設計判断の記録（ADR）。出典ノート「設計判断の記録（ADR）」の分割本文。
parent_note_id: design-decisions
source_path: 40-Design/decisions.md
source_sha256: c2461d8bf240148cf020ce83427691192b3473717f1237fcd33e6e7698601b0b
source_body_lines:
- 1
- 16
split_on: '2026-10-11'
---

# 設計判断の記録（ADR）：設計判断の記録（ADR）

親索引・状態・確認版：[[40-Design/50-Governance/decisions/00-Index]]。必要な本文だけを取得する。


# 設計判断の記録（ADR）

> 復旧時の系列確認（2026-10-10）: 以下の既存ADR-126〜129は、`eb46e68793ef78e71fcae5493e6e5fa4c2354335`から保全した別系列の設計履歴です。Downloadsの実装基点`b9ee037e749748e2819e8ffa0e0faf639d6fd9f6`（adapter `core-handler-prompts-25-referenced-context`）の実装済み機能を示すものではありません。現在系列の判断は後掲の「Downloads系列の再構成記録」を参照してください。NUL破損で失われた元の最新bytesとの一致は未証明です。

### ADR-129 Coreの発注内で専門家がデータ取得hookを使う（2026-10-07）

- 状態: Windows作業ツリーで実装。関連177 unittest成功（62件と115件の別バッチ）。実データ・実モデル試験は運用記録を参照する。分析完了は未確認。
- 背景: 利用者の訂正により、分析を決めるのはCore、専門家は受け取った指示をhookで効率化する責務とする。
- 判断: Handlerの既存発注・JSON transportを再利用し、専門家が固定根拠の本文と許可された保存済み計算表を追加取得する2種のread-only hookを追加。Coreによる専門家・分析・対象範囲の判断を維持し、Jevの選択器・任意コード・新規計算経路は追加しない。
- 判断: 最初の文脈を最大12発話・12,000文字に絞り、未読範囲を明示。追加取得は最大2巡・計3モデル呼出しで、停止・総予算・入力版・Core対象範囲・保存結果hashを検査する。追加分析は従来のanalysis_requestsとしてCoreへ提案する。
- 保存/検証: 中間応答と取得receiptをtask台帳へ保存し、最終報告の根拠候補は実際に届けたIDに限定する。不正な最終応答も既存隔離経路へ保存し、修復して成功扱いしない。usageは継続呼出しごとに記録する。
- 互換性/限界: 新規runのexpert_hooks既定true、falseで従来経路。旧runの欠落設定は無効。プロンプト版8とhook版2を固定する。実モデル試験でデータ要求と報告の混在が発生したため、版2はexpert_response内のread/reportを別Schema候補に分ける。SQL列・保存先の変更と実データ移行なし。ローカルLLMでもJSON生成能力・文脈上限・専門判断の品質に依存する。
- 2026-10-08追記: 32,768 token枠で全323発話の索引を渡す再試験から、索引をevidence_idだけにし、専門家入力内の重複索引を除いた。発話本文にはutterance_idを保持し、固定正本は変更しない。独立検証の生成Schemaも実際に渡した根拠IDへ限定し、受信時の既存照合は維持する。最終試験は取得要求IDの1文字欠落で範囲検査が拒否し、recovery_required。索引配信は全文分析の完了を意味しない。
- 関連: [[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]、[[60-Operations/20-Development/gurumoji-improvement-session/00-Index|gurumoji-improvement-session]]、`tests/test_expert_data_hooks.py`。
