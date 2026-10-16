---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-18
title: Gurumoji 改善セッション：2026-10-05 Windows モデル別コンテキストと作業記録の計画
summary: 2026-10-05 Windows モデル別コンテキストと作業記録の計画。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 301
- 322
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：2026-10-05 Windows モデル別コンテキストと作業記録の計画

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## 2026-10-05 Windows モデル別コンテキストと作業記録の計画

- 利用者の計画作成依頼に対し、[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]を提案として保存し、AI入口と索引から参照可能にした。基点は`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`、既存未コミット変更を含むコードを調査。Anthropic、Agent Skills、LM Studio、LangGraph、長文評価の一次資料を参照した。
- パラメーター数と実ロード枠・役割別能力を分け、入力予算、段階取得、全発話の分割提示、初回途中の尺度要求、結果採否と差分の保存を5段階で提案。直近のマーラータン試験は48/323発話、Core主張数0/0/0、厳格判定failedのままで、コンテキスト改善だけで統合問題が解決するとは扱わない。
- 設計判断と開発引継ぎはSoftware Vault、分析の再開状態は既存DB、全件結果は既存成果物へ分担。今回は文書のみ変更し、実装・DB変更・再推論・モデルロード・実Vault公開・Drive更新・commit/pushは未実行。原本DB・研究者所有のVaultへ書込みなし。次の実装単位はP0〜P1の計測と実行前予算判定。
- 文書検証は成功。frontmatter、提案ステータス、note_id一意性、ローカル参照9件・Vault参照5件・入口参照3件、UTF-8、空白と対象差分を確認。実装テストは今回未実行。

## 2026-10-05 Windows モデル別コンテキスト計画の実装と専門知識の選択

- 利用者の「プランを実行して」に基づき、`main / 75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`の既存未コミット変更を維持して実装。設計は[[40-Design/20-Knowledge/model-context-and-work-memory-plan/00-Index|model-context-and-work-memory-plan]]、専門知識は[[40-Design/20-Knowledge/expert-knowledge-production-plan/00-Index|expert-knowledge-production-plan]]、使用契約は[[20-Modules/20-Analysis/analysis-orchestration/00-Index|analysis-orchestration]]。モデルのパラメーター数と実ロード枠を分け、LM Studioのロード済みhandleのtemplate/tokenizer・実枠・設定hashで入力を計測する。出力予約と512tokenの余裕を確保し、超過時は送信前に分割または保留する。SDK探索はモデルを自動ロードしない。
- `model_context_version=1`の新規runで段階別の入力・出力契約を使う。初期全役割の全発話ページ、途中の尺度要求の保存、Handler集約、Coreの担当指示、専門家の尺度下書き、Core統合の順。所有発話と前後の境界を別に記録する。統合は未評価結果の順序付きbatchと、その結果が引用した原文を取得する。未読結果に属する批判は提示しない。入力manifest・提示ID・未読数・評価対象・専門家brief・予算・hashは既存DBのtask JSONと原結果へ保存し、設計理由はSoftware Vaultに保存する。SQL列の削除・改名・型変更はない。
- `expert_step_ids`は既存定義のAI利用を許可した手順だけを選択し、適用範囲・必須入力・未解決事項・禁止結論を残す。選択briefは解釈経路へ接続し、独立検証のblind入力を維持する。Knowledge Pack v2のライブラリAPIは、審査済み選択方針・root・全claim hash・依存関係を検証し、claim全体を取得する。v1と既存の承認・権利検査を維持する。実Packの選択方針の承認や本番の自動選択は未実施。
- 最終v21の関連10モジュールの**159 unittest成功（36.893秒）**。8K/16K/32Kの合成容量境界、未送信時の0推論、323発話の各役割での非重複所有、提示原文とcitationの一致、要件分割、未評価結果保持、再開時の保存結果再利用、専門知識の条件・例外・依存関係の保持を確認。統計schemaを全件専用とラベル集計の枝に分け、部分発話で全件専用コードを再実行する指定を生成させない。旧テストの2枝固定を3枝へ更新した。主張のない批判・尺度要求の根拠取得と、3結果・2批判への4096token出力予約も回帰対象とした。
- Qwen3-8B / Q4_K_M、GPU全配置、parallel 1、reasoning offを試験専用instanceで使用。8K全体試験はcriticの1600token出力上限で途中終了。3200予約では元ページを送信前に拒否し、分割した子ページの単発契約検証は成功した。16Kのv16全体試験は初期AI42ページとコード3件が成功し、各AI役割へ323発話を提示、Core担当指示と尺度下書きも成功したが、Core統合の1600token出力上限で停止した。[v16記録](../../../../../../output/model-context-plan-16k/20261005T110549Z-50921e4b/result.json)。出力予約と未読批判の範囲を修正したv17はCore39回を採用した後、全件専用統計への部分範囲指定を`method_scope_unavailable`として隔離し停止した。[v17記録](../../../../../../output/model-context-plan-16k/20261005T112701Z-c8c96163/result.json)。いずれも原本source stampは一致し、全体合格にはしていない。v17実行時コードは同試験内`code-v17`に保存した。
- 根拠発話を取り直すv18の単発Core契約検証は成功。7発話・評価対象2結果、入力5238＋schema2874＋出力3200＋余裕512で16,384以下。読取専用コピーDBのhashも一致した。[単発記録](../../../../../../output/model-context-plan-16k/core-quote-hydration-v18.json)。引用付きclaimsの構文合格でも、限られた提示から「懸念や否定的な意見は見られません」と述べるsummaryは全資料の研究結論として承認しない。
- 同じ結果batch・原文・現在見解・catalog・schema・systemで、処理済み初期報告を両側から除いて管理情報だけを比較すると、template入力は7,778→5,238token、**32.7%減**。追加推論0、コピーDB不変。[管理情報の計測](../../../../../../output/model-context-plan-16k/metadata-only-count-comparison-v19.json)。初期報告の省略も含む比較は26,003→5,238token、79.9%減だったが、この値を管理情報だけの削減率にしない。[先行比較](../../../../../../output/model-context-plan-16k/metadata-count-comparison-v19.json)。単一packetの比較であり、全runの総token・処理時間が同率で減ったという意味ではない。
- v19の16K全体試験は1358.45秒、AI68回・コード3件、初期42ページで各AI役割へ323/323発話を提示し、専門家の序数尺度2件を出力した。Core23回を採用した後、24回目の3200token出力上限で`recovery_required`となり全体判定はfailed。[全体結果](../../../../../../output/model-context-plan-16k/20261005T121254Z-d141cdaf/result.json)、[回ごとの作業](../../../../../../output/model-context-plan-16k/20261005T121254Z-d141cdaf/rounds.md)、[完全な採否・根拠・予算と整合性検査](../../../../../../output/model-context-plan-16k/20261005T121254Z-d141cdaf/verification.json)。全役割の所有発話は非重複、全packetの入力＋schema＋出力予約＋余裕は実枠以下、結果hash・manifest hash・リンク・元source stamp・SQLite quick_checkは一致、同じ保存結果の二重評価は0だった。実行版のソースは同試験の`code-v19`へ保存し、試験reportの4ファイルhashと一致した。
- 尺度下書き`def_001`/`def_002`は、`missing_rule=null_with_reason`としながらlevel 1に「未読・欠測」を入れ、「マーラタンを食べる理由がない」「根付かない」を高評価として扱っている。この矛盾を研究用尺度として不合格とした。AI下書きの構文合格であり、人が確認した尺度・発話への数値付与・研究上の解釈を確定したものではない。
- v20では主張以外の批判・尺度要求の根拠も取得する修正を追加。停止後の単発packetはまだ3200token出力上限で不合格だった。[v20記録](../../../../../../output/model-context-plan-16k/critic-source-hydration-v20.json)。最終v21は出力予約を結果数・提示批判数に応じて増やし、批判応答・ラベル決定の配列上限も実提示ID数に合わせた。停止した24回目の場面を**読取専用の新規単発packet**として実行すると、9発話・3結果・2批判応答・4主張、入力8921＋schema2840＋出力4096＋余裕512＝16,369 ≤ 16,384で契約検証成功、コピーDB hashも一致した。[v21記録](../../../../../../output/model-context-plan-16k/core-output-reservation-v21.json)。元runは再開していない。v21の全体再試験と研究上の品質合格には読み替えない。
- 最終adapterは`core-handler-prompts-21-context-contracts`。品質合格前なので既定`model_context_version=0`を維持する。P4の役割別品質認定、cloud計測、料金・サイズからの自動モデル割当、一般検索cache、32K実推論比較、UIの新規検証、本番Pack承認・自動選択、v21全体再試験は今回未完了または未実行。次は尺度の欠測・方向・重複水準を専門家レビューで検証し、合格した役割・モデル構成で全体試験する。
- 原本DBと研究者所有Vaultは読取のみ。試験DBを`output`内に分離し、実Vaultへの公開、Drive更新、commit/push、クラウド配置は行っていない。実験で自分がロードした`qwen/qwen3-context-plan-16k-test`だけを終了時にアンロードした。Python compile、対象文書のローカル参照25件、UTF-8、`git diff --check`も成功。最終追記の参照と差分を再確認して受け渡す。
