---
note_id: expert-focus-group-interaction-skill-hook-binding
note_type: expert-skill-hook-binding
expert_id: exp-focus-group-interaction
title: FGI候補の固定skillとHandler接続
status: draft
schema_version: 1
binding_version: 1
updated: 2026-10-09
---

# FGI候補の固定skillとHandler接続

## 既存readerでの選択

Issue31の7path範囲で07と本08を追加する。既存SKILL_EXPERTSの(folder, selected_note_id)選択は登録noteのsectionを読む仕組みであり、新実行methodではない。FGIでは本08のexpert-focus-group-interaction-skill-hook-bindingをselected_note_idとし、07/08と既存FGI01〜04・analysis-common-*・data-analysis-asset-connection-v1・analysis-skills-indexを取得する。別skillファイルやsemantic roleを新設しない。

全raw SHA-256、note_id、版、相対path、section hashはmethod_experts.SKILL_NOTE_REFSに固定する。読取ごとに実bytesを検証し、stale pin・旧版・別path・root escape・欠落は停止する。新規07/08の追加で共通index/manifestを書き換えず、共有統合はC0所有。登録17expertのうちskill opt-in対応4、他13はunsupported、未知IDはrejected。

workflow=trueは既存group-interview-evidence-workflowを追加する。同workflowのmanual interaction枝は研究者専用のまま。本S1のfgi-p3/p5候補とは別で、01のAI許可・研究者段階を変更しない。文献本文を新規取得したことにはしない。

## Handlerと配信の境界

07の明示typed opt-inがあるときだけ同じHandler/Storeのlibrary authorityからimmutable initialを読み、既存thematic_source_packetを渡す。request_packetは既存applicabilityを評価し、report_schema/validate_reportへ閉鎖FGI fieldを追加する。

初期実contextの全文配送証拠はbounds/hook初期抜粋の後で固定する。source indexと実配送を混同せず、途中が欠けたcontext・部分scope・除外contextを完全読了としない。既定hook初期配送は最大12発話/12000文字であり、hookを明示無効にした既存経路の上限は最大120発話/60000文字。full sourceがこれら既存配送上限に入らない場合も、上限を緩めずneeds_input。本S1ではread_evidenceによる後続取得を全量初期配送へ補完しない。researcherの読了・同意・採否を生成しない。

fgi-p3/p5の実task actor/model/providerだけをproducerに採用し、revisionはunverified。modelのproducer自己申告だけを信頼しない。raw resultは元の失敗/隔離記録も保持し、成功扱いへの改変やutility試験だけの受入をしない。

## 検証と保留

新規test_focus_group_interaction_contractと既存expert_agents/expert_skill_bindings、関連Handler fixtureのみを比例して実行する。source/配送/actor/pin負例、legacy currentPack不変、original raw JSON・manual links不変を確認する。既存Store/publicationを編集せずfresh packageのraw_resultsで検証する。新規Registry method、モデル実行、ネットワーク呼出し、実利用者データは不要。

作者CPU結果はengineering範囲。C0受入・Orca Windows独立QA、人による意味評価と方法評価は別工程。G5 full合格・他expert評価済み・Gemma323解除・PNG完了とは記録しない。
