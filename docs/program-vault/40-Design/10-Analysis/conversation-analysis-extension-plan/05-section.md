---
note_type: reference-section
status: planned
feature: analysis
updated: 2026-09-16
tags:
- gurumoji/analysis
- gurumoji/design
- gurumoji/conversation
note_id: design-conversation-analysis-extension-section-05
title: 会話分析の拡張計画：既存分析とTransformer系推論の統合：推奨アーキテクチャとデータ契約
summary: 推奨アーキテクチャとデータ契約。出典ノート「会話分析の拡張計画：既存分析とTransformer系推論の統合」の分割本文。
parent_note_id: design-conversation-analysis-extension
source_path: 40-Design/conversation-analysis-extension-plan.md
source_sha256: 53dc673b9392c2b03a1b6fd2a103f326b15690c0702376bab2e403dfda7f9bfb
source_body_lines:
- 90
- 116
split_on: '2026-10-11'
---

# 会話分析の拡張計画：既存分析とTransformer系推論の統合：推奨アーキテクチャとデータ契約

親索引・状態・確認版：[[40-Design/10-Analysis/conversation-analysis-extension-plan/00-Index]]。必要な本文だけを取得する。

## 推奨アーキテクチャとデータ契約

### 分析単位と依存関係

```text
保存済み発話（segment_id, session, speaker, role, start/end, 本文版, 除外, 準備状態）
  ├─ A: 発話行為／内容コード／感情／既存topic を発話単位で結合 → 表・既存UI・CSV
  ├─ A: 明示対象の stance を (segment_id, target_id) 単位で結合 → 表・時間／話者比較
  ├─ B: 時間・話者・質問候補・E5近傍で relation の候補集合 → 人手確認 → 確定リンク
  └─ B: 確定リンク／明示対象を必要な場合だけ次の推論・要約候補へ渡す
       └─ C: 複数特徴や追加学習は、独立評価でA/Bを上回る場合だけ
```

- `dialogue_act`、`content_code`、感情、topic、stanceは同じものではない。多面ラベルとして別の結果表に置く。
- `stance`の行キーは`(segment_id, target_id)`である。1発話が複数対象に異なる態度を持てるため、発話ごとに1件へ潰さない。
- `nli`の行キーは`(premise_id, hypothesis_id又は仮説本文hash, direction)`である。前提→仮説の向き、文脈発話ID、三値ラベル、判定保留を保存する。
- `relation`の行キーは`(source_segment_id, target_segment_id, relation_type, candidate_rank)`である。応答先なし、自己補足、複数候補／複数辺を表せる。既存の手動リンクとの方向を一致させる。
- topic用に発話をまとめた文書は`document_id → segment_id[]`の対応を残す。重複窓は集計に二重計上しない。topic IDはrun/model/文書化条件に属し、別run間で同名IDを同一視しない。

### 保存・キャッシュ・UIの方針

1. Phase 1は既存`analysis_runs`と`AnalysisStore`の固定`input.json`、`parameters.json`、`result.json`、CSVを利用する。各手法を`analysis_method_registry.METHODS`へ登録し、結果ごとにモデル名・commit revision・ライブラリ版・入力本文hash・前処理・接頭辞・最大長・seed・ラベル定義／テンプレート版・判定状態を`parameters`へ入れる。
2. 最初から新しい汎用DBテーブルや既存`analysis_annotations_json`の転用を決めない。人手確認を永続的に運用する段階で、予測・確定ラベル・保留理由・確認履歴を安全に保持できる既存契約との差分を設計し、移行と回帰テストを含む別判断にする。
3. E5キャッシュ再利用は、モデル、revision、入力本文、文脈追加、`query:`／`passage:`、512 token制限、正規化、対象発話IDがすべて一致する場合だけにする。分類用に追加学習した埋め込みを既存検索・テーマへ無検証で置換しない。
4. UIは既存の分析パネル、発話フィルター、根拠発話の文脈展開、音声確認、CSV／Excel／JSON出力を使う。`未実行`、`利用不可`、`失敗`、`予測`、`人手確認済み`、`判定保留`、`stale`を区別し、スコアを校正済み確率や確定結果として表示しない。
5. 既存のローカル／外部AI設定を超えて、原文や個人情報を新しい外部検索・APIへ送らない。技術資料のWeb検索と、参加者のスタンス推定に外部事実を注入することは分離する。
