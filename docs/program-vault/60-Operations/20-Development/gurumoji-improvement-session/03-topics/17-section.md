---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-17
title: Gurumoji 改善セッション：2026-10-05 Windows 専門知識の入力調整を具体化
summary: 2026-10-05 Windows 専門知識の入力調整を具体化。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 285
- 300
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：2026-10-05 Windows 専門知識の入力調整を具体化

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 2026-10-05 Windows 専門知識の入力調整を具体化

- 利用者の「エージェント専門知識などでも調整出来るか」に対し、既存コードを確認して[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index|expert-knowledge-production-plan]]の「小型モデルに合わせた専門知識の調整案」へ追記した。担当専門家・手法・段階・対象条件で選択し、必須契約、作業別の知識、具体例、詳細資料を段階取得する提案。現在の短いbrief経路と全件Pack経路を区別し、反復Coreへの未接続も明記した。
- 現行`method_experts.ai_context()`は1500文字以内のbriefと許可段階・文献IDを通常AI見解へ渡す。Pack readerは承認済みclaimを全件渡し、問い合わせ別の順位付けは未実装。部分取得では必須の例外・禁止事項・対立知識を審査済みの選択条件で保持し、根拠ID/hash・送信条件を再検証する。Coreの入力枠超過は別経路なので、まずCore報告の縮約と送信前予算を整える。
- 検証は既存Pack readerの9 tests成功、専門家定義・適用・AI補助の28 tests成功、対象文書の差分確認成功。専門家テストの直接discoverは旧`import app`で読込失敗し、現行`gurumoji`モジュールのaliasを設定した隔離起動で28件を実行した。一時data/output/backupsを使い、実AI・原本DB・研究者Vaultへ書込みなし。今回は計画のみを変更し、知識パケットの部分取得、本番prompt、モデル別予算制御、DB変更、実AIによる効果測定は未実行。

## 2026-10-05 Windows 小型モデルの資料処理と分析を実測

- 利用者のテスト依頼に基づき、既存未コミット変更を含む`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`で実施。既存ローカルQwen3 8B / Q4_K_Mを試験専用IDでロードし、実ロード枠8,192、parallel 1、GPU全配置、reasoning offで使用。設定モデルは変更せず、試験後は自分がロードしたinstanceだけをアンロードした。
- [資料試験スクリプト](../../../../../../scripts/test_small_model_documents.py)を追加。Software Vaultの計画1文書に対し、保存先3問と尺度・blind・予算3問を、節選択・行選択・全文の4ケースで確認した。対象と原文範囲は試験コードが明示選択しており、アプリの自動検索・モデル別予算制御を実装した試験ではない。
- 最終資料試験は**2ケース合格、2ケース不合格**。保存先の問いは全文7,094 tokensと該当節1,364 tokensで同じ内容上の回答となり、入力は80.8%減。SQLite/Software Vault等の別名は内容評価で照合し、指定表記に一致しないことは別項目に保持した。手順の節選択1,680 tokensでは尺度作成者の引用が報告者の説明にとどまり、行選択884 tokensではblindの引用が「契約を維持する」にとどまった。値は正答でも、回答を直接支える引用として不合格。全資料を理解した保証や幅広い品質評価にはしない。
- 初回試験の別名を不正解にする判定を修正し、内容と表記を分離した。また原文一致だけでなく、引用が回答を支える条件を追加した。初回と中間の試行・原応答は残し、最終判定へ上書きしていない。最終資料記録（ローカル記録・Git未同梱：`../../../../../../output/small-model-documents/20261005T101227Z-61970bc1/result.json`）にはprompt、応答、元文書hashと範囲、script版、usage、判定を保持。HTTPエラー本文の保存は秘密値保護のため除去し、最後の変更はcompileで確認した。実呼出時のscript hashは記録に残り、この最後のエラー分岐変更後の再推論は行っていない。
- マーラータンは原本を読取専用でSQLite backupし、AI各回24/323発話、未提示299発話で既存フローを実行。run `run_f8e0567391874d5b846cffa1fc1a4d5e`は初期AI3役とコード統計3手法が保存されたが、Core初期ルーティングでHTTP 400となり`recovery_required`。Core統合0回、尺度0件、厳格判定failed。保存入力から再構成した1token出力の容量確認でも8K枠超過を確認した。この確認は台帳のtask再試行や分析の完了とは扱わない。
- 分析結果（ローカル記録・Git未同梱：`../../../../../../output/small-model-analysis-8k/20261005T100713Z-dc99b41c/result.json`）、容量確認（ローカル記録・Git未同梱：`../../../../../../output/small-model-analysis-8k/20261005T100713Z-dc99b41c/core-capacity-probe.json`）、検証記録（ローカル記録・Git未同梱：`../../../../../../output/small-model-analysis-8k/20261005T100713Z-dc99b41c/verification.json`）を保持。コピーDBのquick_check、保存結果6件のhash、元のsource stamp一致、資料入力と文書hash、対象分析コードhash、容量確認によるコピーDB変更なしを確認。`output`はローカルの未追跡成果物であり共有先への配置は未実行。
- 結論は「限定した資料の設問には答えられるが、根拠引用の安定性と既存分析フローは未合格」。本番の入力調整・自動モデル切替は依然未実装。次は[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]のP1の送信前予算判定と、P2のCore初期ルーティング専用契約・報告縮約を優先する。全323発話のAI分析、32K/他モデルとの比較、研究上の妥当性、実Vault公開、Drive更新、commit/push、全体unit/DOM/browser suiteは未実行。原本DB・研究者所有のVaultへ書込みなし。
