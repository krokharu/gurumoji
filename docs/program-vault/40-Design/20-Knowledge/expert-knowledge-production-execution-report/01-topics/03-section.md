---
note_type: reference-section
status: in_progress
updated: 2026-09-28
tags:
- gurumoji/analysis
- gurumoji/expert
note_id: design-expert-knowledge-production-execution-report-section-03
title: 専門家知識制作・実行報告書：検証記録と制約
summary: 検証記録と制約。出典ノート「専門家知識制作・実行報告書」の分割本文。
parent_note_id: design-expert-knowledge-production-execution-report
source_path: 40-Design/expert-knowledge-production-execution-report.md
source_sha256: 778a8e56c9ab0bab5fd3f6f51bcaefe2d93ff24386e8fba9ec4942cf852c1f1c
source_body_lines:
- 54
- 76
split_on: '2026-10-11'
---

# 専門家知識制作・実行報告書：検証記録と制約

親索引・状態・確認版：[[40-Design/20-Knowledge/expert-knowledge-production-execution-report/00-Index]]。必要な本文だけを取得する。

## 検証記録と制約

- 以前の作業で worker / transport を含む focused tests 63件と回帰確認36件が成功した記録がある。今回の更新ではテストを再実行していない。
- 対象モジュールの `py_compile` と `git diff --check` は以前の実装確認で成功。今回の報告書・計画変更については別途差分確認が必要。
- Gale の1候補は出典全体に対する自動承認ではない。人手の出典確認と登録判断が済むまで候補状態を保つ。
- 現在の実装はオフライン worker と ZIP transport を含む基盤であり、Drive upload/download、Colab 実行、17専門家の評価、リリース承認を通した end-to-end の実績はない。

## 次に進める作業

1. Colab UI で接続テスト Notebook を実行・保存し、A100 の割当と再接続後の Drive 保存を確認する。
2. Gale 候補の出典抜粋を人が確認し、承認または棄却を記録する。
3. 利用経路が確認できた資料だけを対象に、候補を小さいバッチで A100 に処理させる。各バッチの結果を検証してから次の世代へ進む。
4. Drive transport と Colab worker の実運用 round-trip を確認後、専門家別の評価 suite と ReleaseApproval を完成させる。

### 2026-09-27 Local Papers overlay検証境界の更新

- P1/P5実装に、Base-only公開loader、Baseを実際に読んだ後だけoverlayを合成するloader、installation/Base rootに結び付いたLocal Papers adoption recordを追加した。
- adoptionはClaim hash、別reviewer identity、引用Sourceのversion・原文hash・Source record hashに結び付く。reviewerによる独立採用、Source一項目の訂正、root変更で古い記録は通らない。`revoked` adoptionを含むPackは受け付けない。
- `render_agent_request()` はmodel payload全体からfile URI、Windows/POSIX/UNC/home-relative pathを検出し、その文字列を丸ごと伏せる。`local_uri`のlocator valueも常に伏せる。これによりSource title/license/Claim/query内へのローカルパス混入にも対処する。
- Solの再監修では、当初のloader・adoption・path漏えいの指摘と追加で見つかったfile URI、drive-relative、root-relative、tilde、引用符付きPOSIX pathを修正した。最終read-only再監修で残存ブロッカーなし。テスト実行はしていない。
- active overlay rootの失効管理と、ローカルPDFの実取込・検索・索引、実資料からのadoption承認UIは未実装。静的overlayを失効させるには、利用側のpinned rootも切り替える必要がある。
- この報告時点でColab notebookはA100の小規模health probeを毎時1回実行し、Drive上のbundle/resultを80分ごとにID・size・SHA-256で再照合する。queueが空ならGPU probeのみで、論文処理ではない。本番job adapterが未実装のため、現段階ではqueued jobsは自動処理しない。
