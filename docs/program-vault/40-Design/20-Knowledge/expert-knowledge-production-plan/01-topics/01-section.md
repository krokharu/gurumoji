---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-01
title: 配布用専門家の知識・プロンプト制作計画：配布用専門家の知識・プロンプト制作計画
summary: 配布用専門家の知識・プロンプト制作計画。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 1
- 32
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：配布用専門家の知識・プロンプト制作計画

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。


# 配布用専門家の知識・プロンプト制作計画

この文書は最終方針と実装順を定める。既存の専門家参照とローカル知識の上書き、Colab接続・GPU計算確認に加え、制作・審査・配布パイプラインの契約、候補Pack reader/builder、評価gate、Colab送受信adapterまで実装中である。実文献の作成バッチ、実回答を採点するrunner、既存分析への接続、Local Papers版、配布承認は未完了。

最新の工程別結果・AI担当範囲・使用量の記録は[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index|expert-knowledge-production-execution-report]]を参照。

## 1. 目標と完成条件

**利用者が受け取って使える、17種類の分析専門家の知識・プロンプト・出典・評価結果を作る。各専門家は、担当範囲内で根拠を示し、条件を満たさない場合には判断を保留できるものとする。**

成果物を次の2種類にする。

| 配布物 | 利用者ができること | 含めるもの |
| --- | --- | --- |
| Base版 | 収録済み知識を使い、専門家の説明・確認・許可された分析補助を実行する | 承認済み知識、プロンプト、出典一覧、出力schema、公開サンプル、対応モデル別の評価結果 |
| Local Papers版 | Base版に加え、指定した端末内の論文を検索して該当ページを確認する | Base版、論文取込・検索機能、追加プロンプト、設定ひな形。利用者のPDFや個人索引は同梱しない |

Local Papers版の個別知識は、利用者の端末で作成する追加層とする。配布用Base版の品質と、特定利用者の論文を加えた状態の品質を別々に評価する。

完成の判定は次の全項目による。

1. 既存17専門家すべてに、ID・担当範囲・適用条件・禁止事項・知識・プロンプト・出典・評価結果が揃う。
2. 各専門家が第6節の基準を満たす。失敗した専門家を平均点で合格にしない。合格済みだけの先行版は可能だが、17専門家版の完成とは区別する。
3. 配布ZIPをクリーンな環境で読み込み、既存の専門家IDと手法IDで利用できる。ObsidianやCodexへの加入を配布物の読取条件にしない。
4. Local Papers版は、指定フォルダー内のPDFを取り込み、ページ付き根拠を返し、論文がない場合は不足を示す。Baseの内容を黙って変えない。
5. 制作処理の中断・再開で成果物の重複採用や途中ファイルの採用が起きない。
6. 制作時のモデル・知識・プロンプト・評価データの版を追跡でき、前の配布版へ戻せる。
7. 文献処理・通常評価・監視の通常経路ではCodexを呼ばない。Codex利用量とA100稼働時間を記録し、費用の未取得値を0扱いしない。

ここでの「学習」は、文献を読んで知識レコードと指示を更新し、その効果を評価すること。モデルの重みの追加学習はv1の完成条件に含めない。追加学習を行う場合は、知識検索とプロンプト改善で残る失敗を確認した後の別工程とする。
