---
note_type: reference-section
status: proposed
updated: 2026-09-25
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/rules
note_id: design-analysis-method-rules-section-03
title: 分析手法ごとのObsidian登録規約：専門家定義の登録
summary: 専門家定義の登録。出典ノート「分析手法ごとのObsidian登録規約」の分割本文。
parent_note_id: design-analysis-method-rules
source_path: 40-Design/method-rules.md
source_sha256: b12c64c4bba7906a0e26cb253b7c8e6d2b1eca2ff8b8342118d27ab8c2cdc9a4
source_body_lines:
- 69
- 112
split_on: '2026-10-11'
---

# 分析手法ごとのObsidian登録規約：専門家定義の登録

親索引・状態・確認版：[[40-Design/50-Governance/method-rules/00-Index]]。必要な本文だけを取得する。

## 専門家定義の登録

分析手法ごとの専門家定義は `50-Analysis-Methods/10-Experts/<専門家>/` に置く（ADR-115）。書式は [[90-Templates/30-Knowledge/expert-definition|expert-definition]]、一覧は [[50-Analysis-Methods/10-Experts/00-Index]]、実装は `src/gurumoji/method_experts.py`。

1. `01-Expert.md` のプロパティ（`expert_id`、`definition_version`、`knowledge_verified`、`title`、`role`、`analysis_method_ids`、`registry_method_ids`）と、本文の「実行定義」（YAML）の同じ項目を一致させる。
2. `applicability_checks` と `quality_checks` の `check` には、下表の判定名か `human_review` だけを書く。ノートに書いたコードを実行させない。`human_review` の項目は、アプリが確認済みと表示しない。
3. `basis` には、`literature` に並べた文献ID（`LIT-`／`RES-`）か、実装上の判断を示す `implementation` を書く。書誌のみの文献を、手順や基準の唯一の根拠にしない（[[50-Analysis-Methods/08-Common-Knowledge/02-Source-Classification]]）。
4. AI補助を許可する場合は、`actor: ai_draft` の段階を `ai_assist.steps` に並べ、各段階に文献の根拠を付け、1500文字以内の `brief` を書く。許可しない場合は `steps` を空にして `reason` を書く。
5. 手順・判定・禁止事項を変えたら `definition_version` を上げ、文献を再確認したら `knowledge_verified` を更新する。知識hash（同じフォルダーの7ノート、`common_notes`、`literature` の文献ノート）は自動で計算され、変わると保存済みの専門家モードのAI見解は「更新が必要」になる。
6. `readiness` の `literature_checked`、`procedure_documented`、`integrated`、`sample_verified` は、確認できた場合だけ `true` にする。文献ノートの解決と未解決事項の有無は、アプリが計算して表示する。
7. `tests/test_method_experts.py` で、定義の検証、文献の解決、手法との対応を確認する。

### ローカル限定の知識（ADR-120）

Git管理下の `50-Analysis-Methods` は実行環境間で共有する「ベース」である。実行環境ごとに知識を追加・変更したい場合は、`<data>/local_knowledge/50-Analysis-Methods/…`（`<data>` は `MOJIOKOSI_DATA_DIR`、既定は `runtime/data`）に、上記と同じ相対パスでノートを置く。`runtime/` はGit管理対象外（`.gitignore`）なので、このディレクトリはコミットされず環境ごとに内容を変えられる。

- 新しい専門家フォルダーをそこに置けば、ベースに存在しない専門家として追加される（`source: local`）。
- 既存の専門家フォルダーと同じ相対パスのノート（例：`10-Experts/thematic-analysis/02-Procedure.md`）を置けば、そのノートだけがベースを上書きする（`source: local_override`）。知識hashは上書き後の内容から計算され直す。
- `local_knowledge` が存在しない環境では、すべてベースから解決され、挙動は変わらない。
- 論文原本などの資料そのものはここにもGitにも置かない。研究者が内容を理解したうえで書いた要約ノート（本ノートの形式）だけを置く。

| 判定名 | 読む値 | パラメーター |
| --- | --- | --- |
| `research_question_present` | 研究質問（`allow_objective: false` でなければ研究目的でも可） | `allow_objective` |
| `method_rationale_present` | 手法の選定理由 | — |
| `moderator_guide_present` | インタビューのテーマ・質問項目 | — |
| `min_included_segments`／`max_included_segments` | 対象の発話数 | `min`／`max` |
| `min_speakers`／`min_participants` | 話者数／参加者数 | `min` |
| `preparation_confirmed` | 逐語録の準備状態が `confirmed` | — |
| `analysis_basis_current` | 準備記録と分析の根拠が一致（`analysis_needs_review` でない） | — |
| `speaker_order_confirmed` | 順序の確認済みで、未確認の話者の発話が0 | — |
| `valid_time_ratio_min` | 有効な時刻を持つ発話の割合 | `min`（0〜1） |
| `unknown_speaker_ratio_max` | 不明な話者の発話の割合 | `max`（0〜1） |
| `codebook_min_codes`／`codebook_definitions_complete` | コードブックの件数／定義の有無 | `min` |
| `coded_segments_min` | コードを付けた発話数 | `min` |
| `interaction_links_min` | 有効な発話間リンクの数 | `min` |
| `comparison_axis_present` | 比較軸または比較グループ | — |
| `statistics_engine_ready`／`statistics_min_groups` | SciPyの状態／群の数 | `min` |
| `chi_square_expected_cells` | 期待度数5未満のセルの割合（最悪の表） | `max_low_ratio` |
| `morphology_engine_ready`／`syntax_available` | 形態素解析が簡易解析でない／係り受けが利用できる | — |
| `transformer_result_current`／`transformer_silhouette_min` | Transformerテーマ分析の結果が最新／シルエット係数 | `min` |
| `emotion_coverage_min` | 感情推定のカバー率（%） | `min` |
| `comparison_sessions_min` | 保存する比較の会話数 | `min` |
