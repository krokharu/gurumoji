---
note_id: data-cross-conversation-foundation
note_type: data-contract
title: 会話横断分析の土台（C1〜C4）
summary: 発話ベクトルの保存、固定標準、定義hash、グラフIDと根拠の契約。
status: current
updated: '2026-10-13'
tags:
- gurumoji/program
- gurumoji/analysis
---

# 会話横断分析の土台（C1〜C4）

実装の正本は`analysis_core.py`、`transformer_analysis.py`、`services/segment_embeddings.py`、`services/analysis_jobs.py`。判断は[[40-Design/10-Analysis/analysis-immediate-changes-plan#5. 系列C：会話横断分析の土台|系列C]]のQ6・Q7に従う。

## 発話ベクトル

主DBの`segment_embeddings`に`item_id, segment_id, text_sha256, input_hash, model_name, model_revision, dimensions, encoding, vector, created_at`を保存する。主キーは`item_id, segment_id, model_name, model_revision, text_sha256`。`vector`は既存`_pack_vectors`のbase64を復号したint8 BLOB、`encoding=int8-scale-127`。既存JSONと意味検索は保持する。

Workerは入力hash・発話ID・次元・符号化を検査し、結果JSON・ベクトル・完了状態を同じtransactionで確定する。`text_sha256`は切詰め前の発話本文のUTF-8 SHA-256。`input_hash`は既存`transformer_embedding_fingerprint`で、周辺発話・入力版・モデル版も含む。本文が同じでも文脈が変われば古い。再計算で同じ主キーを更新し、本文hash・モデル版の異なる行は共存する。固定runの不変な成果物の役割は既存JSON・保存パッケージに残す。

版不明の旧結果はJSONだけで保持し、版を推測して取り込まない。旧JSONの一括移行は今回行わない。削除は既存D8のtransactionで行い、ゴミ箱の復元対象から除外する。`read_current`は読取専用で、古い行を`stale=true`と明示する。欠落は空集合であり成功やゼロの分析値を意味しない。

## 埋め込み標準 v1

`analysis_core.EMBEDDING_STANDARD_V1`を`application_metadata.embedding_standard_v1`に記録する。`intfloat/multilingual-e5-small`、版`614241f622f53c4eeff9890bdc4f31cfecc418b3`、384次元、int8 scale 127、検索語`query: `・本文`passage: `。既定モデルのロードをこの版へ固定する。比較はモデル・版・次元・符号化のすべてが一致する場合だけ許可し、不一致・破損は再計算を案内する。将来の標準は別のID・設定として追加する。

既存の単一会話内のキャッシュ再利用はモデル・版を一致させる。異なる座標系のベクトルを混ぜない。任意モデルの結果を標準v1として扱わず、会話横断の読取は標準の行だけを選ぶ。ベクトル索引・会話横断検索・新UIは未実装。

## 定義とグラフ

`definition_identity`は既存実行束縛と同じ`fingerprint(validate_definition(..., require_version=True))`。状態・保存revision・更新日時は除き、定義本体のID・version等は含める。`group_definitions_by_hash`は固定payloadと記録hashを照合し、hashで会話を束ねる。同じIDの異なる定義は別群。対象の重複と改ざんは拒否する。共有コードブック表は追加しない。

節点は`utt:<item_id>:<segment_id>`、台帳に登録された話者は`spk:<participant_code>`、未登録話者は`spk:<item_id>:<speaker>`、語は`term:<lemma>:<pos>`、定義は`def:<definition_hash>`、主張は`clm:<claim_id>`。呼出元が台帳の解決を担い、コアは純粋な生成・検証だけを行う。各要素の`%`・`:`を`%25`・`%3A`へ符号化して衝突を防ぐ。

辺の必須項目は`source, target, relation, weight, provenance, method, method_version, input_hash, evidence_segment_ids`。重みは有限数、出所は`rule / ai_draft / researcher`、hashは小文字SHA-256。根拠は会話付き`utt:`IDで、対象集合を渡すと集合内かも照合する。根拠IDは重複を除き整列する。`edge_id=edge:<fingerprint(必須項目)>`とし、入力・手法版・出所が変われば別ID。AI下書きと研究者の確定解釈を同一の辺にしない。
