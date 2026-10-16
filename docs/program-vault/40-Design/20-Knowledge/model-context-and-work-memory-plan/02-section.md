---
note_type: reference-section
status: in_progress
updated: 2026-10-06
feature: analysis-orchestration
tags:
- gurumoji/program
- gurumoji/plan
- gurumoji/ai
- gurumoji/storage
note_id: design-model-context-and-work-memory-section-02
title: モデル別コンテキスト管理と作業記録の保存計画：参考事例と採用する考え方
summary: 参考事例と採用する考え方。出典ノート「モデル別コンテキスト管理と作業記録の保存計画」の分割本文。
parent_note_id: design-model-context-and-work-memory
source_path: 40-Design/model-context-and-work-memory-plan.md
source_sha256: 5deb802e628cb0041fcc9fb6b42ddf5ac43615a40641f4aa9d09e449c34d9323
source_body_lines:
- 25
- 50
split_on: '2026-10-11'
---

# モデル別コンテキスト管理と作業記録の保存計画：参考事例と採用する考え方

親索引・状態・確認版：[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index]]。必要な本文だけを取得する。

## 参考事例と採用する考え方

以下は外部事例からの設計提案。各事例がGurumojiでの効果を実証したものではない。参照確認日は2026-10-05。

| 一次資料 | 示されている考え方 | Gurumojiへの適用案 |
| --- | --- | --- |
| [Anthropicのcontext engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 必要時の情報取得、履歴の圧縮、会話外への構造化メモ | 全履歴を毎回送らず、未処理結果・判断差分・必要な根拠を取得。原結果は保持 |
| [Agent Skills仕様](https://agentskills.io/specification) | 名称・説明から適用スキルを選び、本文と参照資料を段階的に読む | 常時ルールを短くし、手法別の手順・例・契約を必要時に取得 |
| [LM Studioのモデル一覧](https://lmstudio.ai/docs/developer/rest/list)と[トークン計測](https://lmstudio.ai/docs/python/tokenization) | パラメーター数、量子化、実ロード枠、最大対応枠の区別。tokenizerとchat templateの利用 | 名前から枠を推測せず、実instanceと整形済み入力で予算を決定 |
| [LangGraphのpersistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 実行のチェックポイントと、実行をまたぐ記憶を分ける | 既存SQLiteのrun/task状態と、再利用する設計・手法知識を分離。LangGraph導入は不要 |
| [Lost in the Middle](https://arxiv.org/abs/2307.03172)と[RULER](https://arxiv.org/abs/2404.06654) | 長い入力での情報位置や課題による性能差。公称枠と実効能力を評価する必要 | 入力が収まるかに加え、中央・末尾の根拠と集計・統合の品質を検証 |

## モデルの大きさと実効能力による使い分け

モデルの選択は、パラメーター数だけで決めない。既存の役割別モデル設定に、モデル版・量子化・実行エンジン・chat template・ロード枠・reasoning設定・実測時間・課題別評価を結び付ける。MoEは総パラメーターと有効パラメーターを取得できる範囲で区別し、不明値は不明として扱う。

| モデル規模の試験候補 | 任せる仕事の候補 | 採用条件 |
| --- | --- | --- |
| 7〜8B程度 | 少数発話の根拠抽出、定義済みラベルの下書き、範囲を限定した照合 | 根拠ID・出力型・欠測の扱いが課題別試験に合格。未合格の尺度設計や統合は任せない |
| 20B程度 | 専門分析、尺度設計、初期ルーティング、限定した結果の統合 | 役割ごとに評価。直近の尺度出力の成功をCore統合の合格へ流用しない |
| 32B以上や大規模MoE | 複数結果の比較、代替解釈、最終統合の候補 | 利用可能な機器・実ロード枠・時間予算で試験。大きさによる自動合格はしない |

この表は初期候補であり性能保証ではない。同じモデルでも役割別に合否を持ち、小型でも合格した役割は使用できる。計数、分母、task重複判定、hash照合は既存コードが行う。適合するモデルがない場合は理由付きで保留し、設定済み・許可済みの候補以外へ自動送信しない。

能力情報は既存AI設定の取得境界で確認し、評価記録はDB、選び方の理由はSoftware Vaultへ保存する。取得に伴うモデルのダウンロード・ロード・アンロードを行わず、ロード変更時は枠とtokenizerの対応を再確認する。
