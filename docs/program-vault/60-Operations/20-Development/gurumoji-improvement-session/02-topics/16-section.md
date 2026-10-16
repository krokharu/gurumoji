---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-16
title: Gurumoji 改善セッション：同日：マーラータン実データで尺度出力・反復を試験
summary: 同日：マーラータン実データで尺度出力・反復を試験。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 275
- 284
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：マーラータン実データで尺度出力・反復を試験

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：マーラータン実データで尺度出力・反復を試験

- 利用者のテスト依頼に基づき、323発話の原本DBを読取専用でコピーし、各呼び出し48発話/8,000文字/索引48件でLM Studioの実推論を実施。初回の120発話/全索引では65,827 tokensとなり、ロード枠32,768を超えてHTTP 400。48発話の初期版でも2回目Coreで入力32,466/出力302 tokensとなり応答途中終了した。全323発話をAIへ渡した試験とは扱わない。
- 実データで確認した入力の重複、ID誤写、尺度型と値の不一致、欠測の通常値化、空の追加理由を、既存context/adapter/純粋validatorで修正。最終adapterは`core-handler-prompts-10-complete-intents`。全量snapshot/hashは保持し、AIパケットの重複メタデータを省く。尺度設計には既存AIラベルを渡さず、後続は変更可能なラベル欄だけを渡す。実在ID/節/依存taskと型別生成、必須理由の空文字禁止をschemaにも適用し、不正原回答の事後置換は行わない。共有schemaコンテナーの制約が別フィールドへ漏れる問題も新テストで検出し、JSON往復コピーで分離した。
- Qwen3 8Bは順序尺度と分類の混同、category型で数値を出す、欠測をlevelsへ混ぜる等の応答があり、全試行不合格。GPT-OSS 20Bへ切替え、最初の試行は尺度2件を保存したがCoreのwhy_now空欄で停止。失敗記録は`output/malatang-specialist-labels`の各日時ディレクトリーに保持する。モデルはこの試験だけで指定し、アプリ設定は変更しない。試験用にロードしたモデルは終了後にアンロードした。
- 最終run `run_d2de4cc5ac524ed399b8fbf8b9133ba8`（`20261005T064634Z-c6017726`）: ローカルGPT-OSS 20B、32,768 context、実AI6呼び出し、176.33秒。専門エージェントが初回に「辛さの好み」（順序1〜5）と「価格に対する懸念度」（順序1〜3）を作成し、値の意味/判定基準/欠測条件/根拠と共に保存。最初のCore開始より前の終了時刻、作成主体、catalog/原結果/hashの一致を確認した。Core3回の採用判断、批判者1回、追加解釈1回がある。独立verificationはこのrunで未実行。
- **最終の厳格判定はfailed**。3回目は2回目と同じ追加作業を提案し、同じタスクを再発注せず`no_new_tasks`で停止した。原応答hashは3種類だが進展signatureは2種類で、2/3回目の採否は新しいresult IDへdefer/impact=none。Coreの根拠付きclaimsは全3回とも0件で、専門家結果を主張へ統合した十分な分析とは扱わない。採用数3は新しい専門家結果の評価を含む動作記録であり、内容深化/研究上の十分性/正常完了の保証ではない。固定成果物の自動保存・Vault公開はskipped。終了判定を成功に変えない。
- 原本のsource stampは試験前後で一致。保存原結果全件のhash、全量根拠323件、尺度catalog、JSON/Markdownの既存読取ルート、閲覧での再推論なしを照合。尺度は未検証AI下書きで、科学的な尺度妥当性の検証・全量分析・実Vault公開・Git commit/push・Drive更新は未実行。関連9モジュール153 tests成功（31.586秒）、Python compile/git diff --check成功。未コミット変更のコードhashと実試験は同ディレクトリーの`result.json`、`verification.json`、尺度は`initial-labels.json`、全台帳は`analysis-history.json`/`analysis-history.md`へ保持する。
