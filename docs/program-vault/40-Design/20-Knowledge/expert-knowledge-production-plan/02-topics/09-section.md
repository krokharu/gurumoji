---
note_type: reference-section
status: in_progress
updated: 2026-10-05
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/expert
- gurumoji/plan
note_id: design-expert-knowledge-production-plan-section-09
title: 配布用専門家の知識・プロンプト制作計画：10. 必要な検証
summary: 10. 必要な検証。出典ノート「配布用専門家の知識・プロンプト制作計画」の分割本文。
parent_note_id: design-expert-knowledge-production-plan
source_path: 40-Design/expert-knowledge-production-plan.md
source_sha256: b29b4dc13e95d8747582dc2a88d3383cf7a74b637860e105d1a12f5969cca005
source_body_lines:
- 415
- 453
split_on: '2026-10-11'
---

# 配布用専門家の知識・プロンプト制作計画：10. 必要な検証

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index]]。必要な本文だけを取得する。

## 10. 必要な検証

実装段階では、既存の`tests/test_method_experts.py`、`tests/test_method_expert_samples.py`、`tests/test_ai_http_worker.py`の関連範囲を起点にする。テスト対象は一時ディレクトリと架空資料にする。

- 追加知識assetがない場合の旧読取、ある場合のhash変化、未選択専門家を読まないこと。
- AI補助不可、根拠欠落、定義変更、private送信不可をpromptが回避できないこと。
- PDFのページ、段落、出典hash、検索結果、回答中の根拠IDが対応すること。
- 同一資料の再取込、原本更新、OCR失敗、空の索引、資料削除を正しく扱うこと。
- 生成役に最終評価の問題・正答を渡さないこと。評価モデルの自己申告点をそのまま集計しないこと。
- 完了記録欠落、途中アップロード、古い実行世代、同名ファイル、重複完了、PC再起動で二重採用しないこと。
- runtime・APIの使用量が取れない場合は不明とし、予算・状態を偽って成功にしないこと。
- Baseビルドにローカル論文、抽出本文、個人パス、秘密値、private派生知識が入らないこと。
- 配布ZIPのクリーン環境での読取と、以前の配布版への切替。

最終のA100実測は小さな代表バッチから行い、性能測定と内容の品質検証を混同しない。今回の512×512行列積の成功は接続確認であり、専門知識の品質確認ではない。

## 11. Lunaへの開始指示

次の指示とこのファイルのパスを渡して実装を始める。進行に必要なのは本計画・現在のチケット・対象コードだけとし、過去の会話全文を渡さない。

```text
この計画に従い、配布用17専門家の知識とプロンプトの制作機能を実装する。
計画: docs/program-vault/40-Design/expert-knowledge-production-plan.md
あなたの担当モデルはgpt-6-luna。P0から、受入条件を満たした段階を順に進める。
既存の専門家ID、適用条件、AI補助ゲート、利用者のローカル知識を保持する。
文献の大量処理・候補生成・通常評価はColab A100、例外分類はローカルLLMへ渡す。
Codexを常駐監視や文献全文の読解ループに入れない。
P1/P3/P5/P7ではgpt-6-solの監修エージェントを1つ呼び、必要な差分と根拠だけを渡す。
Solは重大な欠陥、修正条件、検証不足を簡潔に返す。修正実装はLunaが担当する。
同じ問題の修正が2回失敗した場合や保存・評価・機密の契約が変わる場合もSolへ相談する。
単に点数を上げるために評価基準を変更しない。未達なら理由と再開条件を記録する。
通常の可逆的な実装は継続し、必要な入力が不足する作業だけ保留して独立した作業を進める。
未完了チケット、変更、検証、必要な判断、使用量を短い引継ぎに残す。
```

P0で決める利用者固有の設定は、ローカル論文のルート、Colabと共有可能な資料の区分、1バッチのA100時間・費用上限。未設定でも架空資料による契約と実装を先に進められる。

関連：[[40-Design/50-Governance/method-rules/00-Index|method-rules]]、[[40-Design/50-Governance/decisions/00-Index|decisions]]のADR-115・ADR-120、[[50-Analysis-Methods/10-Experts/00-Index]]、[[40-Design/10-Analysis/core-handler-routing-reorganization-plan/00-Index|core-handler-routing-reorganization-plan]]のAI入力・来歴契約。変更を実装するときに、影響する既存の契約資料を更新する。
