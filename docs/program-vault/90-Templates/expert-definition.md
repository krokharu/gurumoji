---
note_id: template-expert-definition
note_type: template
title: 分析手法の専門家定義のテンプレート
status: current
updated: 2026-09-16
tags:
  - gurumoji/template
  - gurumoji/expert
---

# 分析手法の専門家定義のテンプレート

専門家は `50-Analysis-Methods/10-Experts/<slug>/` に次の7ノートで登録する。アプリが実行時に読むのは `01-Expert.md` の「実行定義」ブロックと、そこで参照したノート・文献だけである。登録手順は [[40-Design/method-rules]] の「専門家定義の登録」。

| ファイル | note_type | 役割 |
| --- | --- | --- |
| `00-Overview.md` | expert-overview | 答えられる問い／答えられない問い、流派の違い、関連する実装ノート |
| `01-Expert.md` | expert-definition | 専門家定義（人向けの説明と、機械可読の実行定義） |
| `02-Procedure.md` | expert-procedure | 手順、各段階の確認事項、迷いやすい点、典型的な失敗と修正、結果のまとめ方 |
| `03-Quality.md` | expert-quality | 判断基準と品質確認、流派ごとの違い |
| `04-Applicability-and-Limits.md` | expert-limits | 入力データの条件、適用できない条件、言えないこと、グループインタビューへの注意 |
| `05-Cases.md` | expert-cases | 文献で確認できた適用事例 |
| `06-Open-Issues.md` | expert-open-issues | 知識が不足している点、未確認事項、文献間で意見が分かれる点 |

本文では、次の3種類を見出しまたは行頭の記号で区別する。

- `[文献]` 文献に書かれていること（文献IDを付ける）
- `[整理]` 複数の文献から整理したこと（文献IDを並べる）
- `[実装判断]` Gurumojiでの採用・しきい値・画面上の扱い

## `01-Expert.md` のひな形

プロパティは単純な値だけにし、手順や判定は本文の「実行定義」ブロック（YAML）に置く。ブロックの `check:` はコードに登録済みの判定名だけを使う（一覧は [[40-Design/method-rules]]）。判定できない項目は `check: human_review` にする。

````markdown
---
note_id: expert-<slug>-definition
note_type: expert-definition
expert_id: exp-<slug>
title: <手法名>の専門家
role: methodology | computational | preprocessing | comparison
status: current
definition_version: 1
knowledge_verified: YYYY-MM-DD
analysis_method_ids: []
registry_method_ids: []
tags:
  - gurumoji/analysis
  - gurumoji/expert
---

# <手法名>の専門家（exp-<slug>）

## 担当範囲と担当外
## 理論的背景と採用する流派
## 適した研究目的・問い・データ
## 必要な入力と前処理、分析単位
## 手順の要約（詳細は02-Procedure）
## 判断基準と品質確認の要約（詳細は03-Quality）
## よくある誤用と禁止事項
## 出力形式
## 説明できる範囲と限界
## 参照ノートと主要文献
## 知識の確認日と未解決事項

## 実行定義

```yaml
expert_id: exp-<slug>
definition_version: 1
knowledge_verified: YYYY-MM-DD
title: <手法名>の専門家
role: methodology | computational | preprocessing | comparison
analysis_method_ids: []
registry_method_ids: []
school:
  default: <流派ID>
  alternatives: []
scope: []
out_of_scope:
  - text: <担当外の内容>
    handoff: exp-<別の専門家>
analysis_unit: <分析単位>
required_inputs: []
applicability_checks:
  - id: <slug>-a1
    check: <判定名>
    severity: block | warn
    params: {}
    message: <満たさない場合の説明>
    basis: []
procedure:
  - id: <slug>-p1
    title: <段階名>
    actor: researcher | code | ai_draft
    checks: []
    basis: []
quality_checks:
  - id: <slug>-q1
    check: human_review
    text: <確認内容>
    basis: []
prohibited_conclusions: []
output_sections: []
ai_assist:
  allowed: false
  steps: []
  reason: <AI補助を許可しない理由（allowed が false のとき必須）>
  brief: <AIに渡す1500文字以内の指示（allowed が true のとき必須）>
literature: []
common_notes:
  - 01-Evidence-and-Claims
open_issues: []
readiness:
  literature_checked: false
  procedure_documented: false
  integrated: false
  sample_verified: false
```
````
