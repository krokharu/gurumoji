---
note_type: reference-section
status: current
updated: 2026-09-21
feature: analysis
tags:
- gurumoji/design
- gurumoji/analysis
- gurumoji/ui
note_id: design-analysis-milestone-visualization-section-19
title: 分析マイルストーン・可視化プログラム・UI統合設計：19. Terra / Lunaで検証してから進む実装工程
summary: 19. Terra / Lunaで検証してから進む実装工程。出典ノート「分析マイルストーン・可視化プログラム・UI統合設計」の分割本文。
parent_note_id: design-analysis-milestone-visualization
source_path: 40-Design/analysis-milestone-visualization-design.md
source_sha256: 7a424d0d4410733e1878eef03fd5bb56027cdae115520e26575598244393721b
source_body_lines:
- 774
- 838
split_on: '2026-10-11'
---

# 分析マイルストーン・可視化プログラム・UI統合設計：19. Terra / Lunaで検証してから進む実装工程

親索引・状態・確認版：[[40-Design/10-Analysis/analysis-milestone-visualization-design/00-Index]]。必要な本文だけを取得する。

## 19. Terra / Lunaで検証してから進む実装工程

### 19.1 実行時のMと開発時のDを分ける

M0〜M7はアプリ内で実行する分析の段階。以下のD0〜D7は、開発者が実装を進める順序とテストのゲートである。**D[n]に定めた必須テストがすべて合格し、変更範囲に対する受入条件を確認するまで、D[n+1]の実装を開始しない。** 設計を読むことはできるが、後段の実装を先に書いて積み上げない。

図は [実装とテストの進行図](../../../analysis-design/implementation-gates.svg)、機械可読の指示と受入記録は [implementation-gates.json](../../../analysis-design/implementation-gates.json)。第18.7節の初回導入範囲はD0〜D7を順に通過した。利用可能な実行環境の制約によりTerra/Lunaへの委任は行わず、主担当が実装・試験・受入を行ったことを記録する。

### 19.2 担当と引継ぎ

利用者指定のモデル名に従い、**Terra（gpt-5.6-terra）を実装・原因調査・受入確認、Luna（gpt-5.6-luna）を範囲の明確なテスト実行と事実報告**へ割り当てる。これは役割分担であり、料金やモデル精度の保証ではない。実装セッションで利用可否を確認し、使えない場合はその事実を示す。別モデルで実行した結果をTerra/Lunaの結果と表記しない。

- Terraは一つのD工程の指定ファイルと契約だけを変更する。新しい意味検証・故障注入・期待値の設計はTerraが担当する。
- Lunaは渡されたコマンド・テスト対象を実行し、終了コード、件数、失敗名、ログ参照を返す。テストを通すための実装変更・assert削除・skip追加はしない。
- 失敗時はTerraへ最小の再現情報を返し、修正後に影響したテストを再実行する。曖昧な期待値、競合・再開、統計解釈の判断はTerraが確認する。
- テスト結果が揃ったらTerraまたは主担当が契約との対応を確認し、同じ差分に対するGateResultをacceptedにする。毎回利用者に形式的な承認を求めない。
- テスト中に検査対象ファイルを変更しない。同工程内の独立テストは隔離したDB・出力先で並列実行できるが、同じファイルを複数エージェントが同時編集しない。

### 19.3 工程別の必須テスト

| 工程 | 今回の工程で実装する範囲 | 次へ進む前に確認すること | 担当・既存テストの接続点 |
| --- | --- | --- | --- |
| D0 基準と契約 | 選択した初回機能、8契約、状態・規則、対象ファイルを固定 | Schema正常/異常例、既存対象テストの基準、テスト収集0件でないこと | Terraが期待値を確認、Lunaが実行。analysis_queries / analysis_storageの対象ケース |
| D1 コア窓口と計画 | メイン→コア→実行ハンドラー→報告、M0/M4、純粋な可否・対処規則 | 逆importなし、手動定義でLLM生成不要、未解決slotでM5開始不可、範囲外は新計画、hard/warningの差 | Terra＋Luna。新規test_analysis_core_contracts / test_analysis_plan_binding / test_analysis_eligibility、既存analysis_queries |
| D2 固定入力と保存 | snapshot、attempt成果物、短い確定ロック、保存runとpipeline IDの関連 | 同一版で検査・計算、計算中の別処理進行、取消と保存競合、二重保存、旧run互換、孤立成果物の回復 | Terraが競合を確認、Lunaが実行。既存analysis_storage、追加test_analysis_snapshot_commit |
| D3 段階・並列・回復 | 同段階並列、永続指示、ゲート、再試行、取消、再起動 | 次段階の先行0件、親待ち、順不同・重複・旧世代応答、上限、外部完了不明、再起動後の回復 | Terraが故障注入を設計、Lunaが実行。新規test_analysis_milestones / test_analysis_recovery。既存pipeline_regressionsは隣接回帰のみ |
| D4 手法と研究規則 | 選択した既存手法2つのadapter、尺度・列・単位、研究区分 | 既存数値一致、欠測後N、独立単位、適用不可、未知条件、探索/検証の誤表示なし、全分析履歴 | Terraが分析上の期待値を確認、Lunaが実行。research_analysis / content_analysis、追加test_analysis_research_protocol |
| D5 LLM境界 | 既存provider adapterへの接続と、選択した役割だけ。手動経路も維持 | 同じ契約でクラウド/ローカルのモック応答、拒否・不正JSON・根拠不正・timeout・取消、予算、local_only外部通信0件 | Terra＋Luna。ai_http_worker / ai_model_settings / method_experts、追加test_analysis_llm_contracts |
| D6 出力と公開 | 選択した形式、ChartSpec、既存Store/Registryの公開Outcome | 再読込値・尺度・欠測一致、日本語画像、公開先別失敗、計算済みでも全体未完了、公開再試行でAI呼出し0件 | Terra＋Luna。analysis_storage / four_vaults / obsidian_layout / vault_coverage、追加test_analysis_exports / test_analysis_publication |
| D7 UIと統合 | 選択機能をS01〜S06へ接続、履歴、部分結果、互換経路 | 手入力→試行→段階実行→不足/再開→出力、状態整合、キーボード・画面幅、旧URL、対象範囲の最終回帰 | Lunaがブラウザー/回帰を実行、Terraが結果確認。content_browser / browser_e2e / analysis_method_view、追加の操作ケース |

表の`test_analysis_core_contracts`等は初回導入で追加済み。既存`test_pipeline_regressions.py`は新しい分析schedulerの試験そのものではないため、schedulerの不変条件は専用試験で確認する。

初回に選択しないLLM役割・画像形式・47成果物の機能は、D0で能力一覧に未提供として固定する。D5等でも、未提供であることと既存機能の互換・手動経路を確認して通過する。選択済みの必須機能を後から未提供に変更してテストを省略しない。拡張時は該当D工程から同じゲートを適用し、依存境界が変わる後続工程を再検証する。

JEV8軸の妥当性は通常のモックテストとは別のEVALゲートを設ける。人手評定、評価データ分離、事前基準の達成を確認するまでは未検証として表示し、自動の成功/失敗判定を有効化しない。Terra/Lunaがテストに合格したことを人手との評価一致の代用にしない。

### 19.4 合格判定とテスト記録

工程状態は`planned → implementing → testing → accepted`。失敗・実行不能は`fix_required / blocked`とし、次工程を開始しない。必須ケースの未収集、unexpected skip、timeout、環境不備、未解決の既存失敗は合格ではない。既存の無関係な失敗を除外する場合は、再現・非関連の根拠と対象範囲を主担当が記録する。関連する失敗は修正してから進む。

GateResultには `gate_id, scope_id, code_fingerprint, test_fingerprint, environment_ref, commands, required_cases, executed_cases, failures, unexpected_skips, exit_codes, log_refs, reviewer, decision` を残す。未コミット変更を含む対象ファイル・テスト・依存設定のhashを使い、commit IDだけで同じ状態とみなさない。記録は一つの小さな進捗JSONとログ参照に集約し、工程ごとに長い報告書を作らない。

工程途中で対象ファイルや依存契約を変更したら、その影響を受ける合格証跡を無効にする。最後の差分に対して必要なテストが通っていることを確認し、古い合格結果で次へ進まない。

既存の実行形式はunittestを利用する。Windowsでは既存READMEに従い`PYTHONPATH`へsrcを設定し、`.venv/Scripts/python.exe -m unittest discover -s tests -p test_analysis_storage.py`のように対象を絞る。コマンドは実装時の環境で検証し、新規テストがない状態で「0件成功」を合格にしない。

### 19.5 トークン節約の実装指示

1. 各担当へ渡すのは「工程ID・目的・必読ファイル/節・編集可ファイル・不変条件・コマンド・合格条件・直前の失敗」のTaskPacketだけ。会話全文、設計書全文、Vault全文は渡さない。
2. 初回読取は対象の関数・契約・テストに限定する。読み取り済みの内容は短い版付き要約と参照で引き継ぎ、変更のない大きなファイルを毎回再読しない。
3. Lunaの通常報告は`PASS/FAIL/BLOCKED、対象hash、件数、失敗名、最小ログ、次の担当`に限定する。全ログは一時ファイルへ保存し、正常ログを会話へ大量出力しない。
4. 修正後は失敗したテストと影響する境界から確認する。無関係な全テストの反復を避け、D7または広範な契約変更時に全体回帰をまとめる。
5. 独立テストの並列実行は一時DB・ポート・保存先を分離できる場合だけ。同じ原因の失敗を複数担当に重複調査させない。
6. 1工程1担当を基本とし、短い単純テストのために大量のエージェントを起動しない。委任が使える環境では新規担当へ会話全文を継承せず、TaskPacketを明示して開始する。
7. 手法別の共通fixture・境界試験を再利用する。実装をそのまま写すテストや、表示名だけの大量テストを作らず、値・依存・故障回復・利用者操作を確認する。
8. 節約するのは重複した文脈・出力・作業であり、必須テストや失敗情報ではない。合格証跡を省略して次へ進まない。

この指示は設計図と構造JSONにも同じ工程IDで反映する。初回導入範囲のD0〜D7はaccepted、JEVの妥当性を扱うEVALは未実施である。設計Schema検証だけを開発ゲートの合格とはみなしていない。

### 19.6 今回確認した実装成果物

初回導入範囲では、純粋な制御契約、M0の不変計画、M4の実行binding、固定snapshot、attempt台帳、段階ゲート、同段階並列、取消・再試行・起動回復、手動定義の少数試行、固定結果、JSON/CSV/ZIP、公開先別Outcomeを実装した。結果保存とVault公開は分離し、公開失敗時も計算済みrunを保持して公開だけを再試行する。

D0〜D7の対象試験、手入力からM0〜M7完了までの実ブラウザ操作、既存画面のブラウザ回帰を一時DB・一時Vaultとモック外部通信で確認した。正確な件数・対象は `implementation-gates.json` に記録する。JEV評価、LLM役割、推測統計、画像、SAV/jamovi/XLSX、47成果物の全展開は今回の合格範囲に含めない。
