---
note_id: design-decisions-legacy-path
note_type: path-redirect
title: 設計判断の記録（ADR）（移動先案内）
summary: 本文と同じnote_idは移動先に保持。通常検索は移動先を使用する。
status: deprecated
updated: '2026-10-11'
redirect_to: 40-Design/50-Governance/decisions/00-Index.md
tags:
- gurumoji/redirect
---

# 設計判断の記録（ADR）

本文：[[40-Design/50-Governance/decisions/00-Index|設計判断の記録（ADR）]]。旧パスの互換案内。

### ADR-129 Coreの発注内で専門家がデータ取得hookを使う（2026-10-07）

[[40-Design/50-Governance/decisions/01-topics/01-section#ADR-129 Coreの発注内で専門家がデータ取得hookを使う（2026-10-07）|移動した本文を読む]]

### ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）

[[40-Design/50-Governance/decisions/01-topics/02-section#ADR-128 統計分野の知識付き専門家と手法別コードツール（2026-10-06）|移動した本文を読む]]

### ADR-127 専門家ごとの固定知識と宣言的入出力契約（2026-10-06）

[[40-Design/50-Governance/decisions/01-topics/02-section#ADR-127 専門家ごとの固定知識と宣言的入出力契約（2026-10-06）|移動した本文を読む]]

### ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）

[[40-Design/50-Governance/decisions/01-topics/03-section#ADR-126 Core・Handlerから受け取るObsidian管理担当（2026-10-06）|移動した本文を読む]]

### ADR-125 自律分析は最低3回後にCoreが終了を判断（2026-10-05）

[[40-Design/50-Governance/decisions/01-topics/04-section#ADR-125 自律分析は最低3回後にCoreが終了を判断（2026-10-05）|移動した本文を読む]]

### ADR-124 分析表の型付きJSON保存とCSV共有出力（2026-10-05）

[[40-Design/50-Governance/decisions/01-topics/04-section#ADR-124 分析表の型付きJSON保存とCSV共有出力（2026-10-05）|移動した本文を読む]]

## 採用済み（コードから復元）

[[40-Design/50-Governance/decisions/01-topics/05-section#採用済み（コードから復元）|移動した本文を読む]]

### ADR-001 Obsidianとはプラグインではなく、ファイルの直接読み書きで連携する

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-001 Obsidianとはプラグインではなく、ファイルの直接読み書きで連携する|移動した本文を読む]]

### ADR-002 正本はSQLiteと固定成果物で、Vaultは閲覧・考察用とする

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-002 正本はSQLiteと固定成果物で、Vaultは閲覧・考察用とする|移動した本文を読む]]

### ADR-003 アプリ専用のVaultはデータフォルダー配下に作り、利用者のVaultを探したり推測したりしない

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-003 アプリ専用のVaultはデータフォルダー配下に作り、利用者のVaultを探したり推測したりしない|移動した本文を読む]]

### ADR-004 自動生成ノートはhashで所有を確認し、外部で編集されていたら上書きしない

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-004 自動生成ノートはhashで所有を確認し、外部で編集されていたら上書きしない|移動した本文を読む]]

### ADR-005 AIの生成物は常に新しいパスへ保存し、人が編集中のノートを置き換えない

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-005 AIの生成物は常に新しいパスへ保存し、人が編集中のノートを置き換えない|移動した本文を読む]]

### ADR-006 Obsidianの内容をアプリへ反映するのは「結果をアプリへ反映」の明示操作だけとする

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-006 Obsidianの内容をアプリへ反映するのは「結果をアプリへ反映」の明示操作だけとする|移動した本文を読む]]

### ADR-007 4つのVaultは相互にリンクせず、IDで対応付ける

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-007 4つのVaultは相互にリンクせず、IDで対応付ける|移動した本文を読む]]

### ADR-008 Software Vault（このVault）はGitで管理し、アプリからは書き込まない

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-008 Software Vault（このVault）はGitで管理し、アプリからは書き込まない|移動した本文を読む]]

### ADR-009 Vaultへの書き出しに失敗しても、文字起こしや編集の保存は失敗させない

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-009 Vaultへの書き出しに失敗しても、文字起こしや編集の保存は失敗させない|移動した本文を読む]]

### ADR-010 新規の文字起こしは「Obsidianで仕上げる」を既定とする

[[40-Design/50-Governance/decisions/01-topics/05-section#ADR-010 新規の文字起こしは「Obsidianで仕上げる」を既定とする|移動した本文を読む]]

## 提案（収束フェーズ）

[[40-Design/50-Governance/decisions/01-topics/06-section#提案（収束フェーズ）|移動した本文を読む]]

### ADR-101 Vaultへの書き込み判定を1つの関数に統合する

[[40-Design/50-Governance/decisions/01-topics/06-section#ADR-101 Vaultへの書き込み判定を1つの関数に統合する|移動した本文を読む]]

### ADR-102 人が所有するノートは、変更するキーと管理区間だけを更新し、書く直前に再確認する

[[40-Design/50-Governance/decisions/01-topics/06-section#ADR-102 人が所有するノートは、変更するキーと管理区間だけを更新し、書く直前に再確認する|移動した本文を読む]]

### ADR-103 既存のVaultの `.obsidian` は、初回作成時と明示操作のとき以外は書かない

[[40-Design/50-Governance/decisions/01-topics/06-section#ADR-103 既存のVaultの .obsidian は、初回作成時と明示操作のとき以外は書かない|移動した本文を読む]]

### ADR-104 ファイル名とパスの生成規則を1つにする

[[40-Design/50-Governance/decisions/01-topics/07-section#ADR-104 ファイル名とパスの生成規則を1つにする|移動した本文を読む]]

### ADR-105 Obsidianの操作を監査ログに残す（本文は残さない）

[[40-Design/50-Governance/decisions/01-topics/07-section#ADR-105 Obsidianの操作を監査ログに残す（本文は残さない）|移動した本文を読む]]

### ADR-106 新機能を凍結し、「追加より統合」を開発ルールにする

[[40-Design/50-Governance/decisions/01-topics/07-section#ADR-106 新機能を凍結し、「追加より統合」を開発ルールにする|移動した本文を読む]]

### ADR-107 フロントエンドのAPI呼び出しは `apiFetch` に限定する

[[40-Design/50-Governance/decisions/01-topics/07-section#ADR-107 フロントエンドのAPI呼び出しは apiFetch に限定する|移動した本文を読む]]

### ADR-109 人のノートを自動更新せず、生成情報の保存先を分ける

[[40-Design/50-Governance/decisions/01-topics/07-section#ADR-109 人のノートを自動更新せず、生成情報の保存先を分ける|移動した本文を読む]]

### ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない

[[40-Design/50-Governance/decisions/01-topics/08-section#ADR-108 問題点を影響と根拠で選別し、大規模統合を前提にしない|移動した本文を読む]]

### ADR-110 発話の数値化とjamovi型統計の自動実行を、既存の分析層の拡張として段階的に実装する

[[40-Design/50-Governance/decisions/01-topics/08-section#ADR-110 発話の数値化とjamovi型統計の自動実行を、既存の分析層の拡張として段階的に実装する|移動した本文を読む]]

### ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする

[[40-Design/50-Governance/decisions/02-topics/09-section#ADR-111 クラウドLLMへの送信を認め、文字起こし・AI数値化・統計の実行を別のボタンにする|移動した本文を読む]]

### ADR-112 統計の依存にstatsmodelsを追加する

[[40-Design/50-Governance/decisions/02-topics/09-section#ADR-112 統計の依存にstatsmodelsを追加する|移動した本文を読む]]

### ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る

[[40-Design/50-Governance/decisions/02-topics/10-section#ADR-113 本体の配布条件をMITライセンスにし、依存はライセンスの方針に合うものに限る|移動した本文を読む]]

### ADR-114 議論用の人格をPersonaVaultに置き、OrchestratorVaultと用途を分ける

[[40-Design/50-Governance/decisions/02-topics/10-section#ADR-114 議論用の人格をPersonaVaultに置き、OrchestratorVaultと用途を分ける|移動した本文を読む]]

### ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む

[[40-Design/50-Governance/decisions/02-topics/11-section#ADR-115 分析手法ごとの専門家定義をSoftware Vaultに置き、実行時に選んだ専門家だけを読み込む|移動した本文を読む]]

### ADR-116 分析手法ごとの画面（手法別タブ）と、手法別の状態API

[[40-Design/50-Governance/decisions/02-topics/12-section#ADR-116 分析手法ごとの画面（手法別タブ）と、手法別の状態API|移動した本文を読む]]

### ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する

[[40-Design/50-Governance/decisions/02-topics/13-section#ADR-116 Web UIを画面単位のURLと3ステップの新規作成に作り直し、既存APIと要素IDを維持する|移動した本文を読む]]

### ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る

[[40-Design/50-Governance/decisions/02-topics/14-section#ADR-117 LLM分析専用オーケストレーターが役割別に相談し、再利用できる手法別契約を作る|移動した本文を読む]]

### ADR-118 分析UIを、結果閲覧・比較・計画・データ出力の作業単位へ整理する

[[40-Design/50-Governance/decisions/02-topics/14-section#ADR-118 分析UIを、結果閲覧・比較・計画・データ出力の作業単位へ整理する|移動した本文を読む]]

### ADR-119 文字起こしの外部連携を `app.py` から分離する

[[40-Design/50-Governance/decisions/02-topics/15-section#ADR-119 文字起こしの外部連携を app.py から分離する|移動した本文を読む]]

### ADR-120 実行環境ごとのローカル知識を、Gitで共有するSoftware Vaultとは別の階層に置く

[[40-Design/50-Governance/decisions/02-topics/15-section#ADR-120 実行環境ごとのローカル知識を、Gitで共有するSoftware Vaultとは別の階層に置く|移動した本文を読む]]

### ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る

[[40-Design/50-Governance/decisions/02-topics/16-section#ADR-121 A100目標モードは必要な知識の整理・深さ・検索到達と成果物品質を分けて測る|移動した本文を読む]]

### ADR-122 分析要求を表示contextから分離し、固定試行の明示採用を全件実行の前提にする

[[40-Design/50-Governance/decisions/02-topics/16-section#ADR-122 分析要求を表示contextから分離し、固定試行の明示採用を全件実行の前提にする|移動した本文を読む]]

#### ADR-122 追記: 固定run閲覧と公開証拠の分離（2026-10-03）

[[40-Design/50-Governance/decisions/02-topics/16-section#ADR-122 追記: 固定run閲覧と公開証拠の分離（2026-10-03）|移動した本文を読む]]

### ADR-123 保存済み分析の読取専用投影と追記監査、設計記録後のスライド出力

[[40-Design/50-Governance/decisions/03-topics/17-section#ADR-123 保存済み分析の読取専用投影と追記監査、設計記録後のスライド出力|移動した本文を読む]]

## Downloads系列の再構成記録（2026-10-10）

[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads系列の再構成記録（2026-10-10）|移動した本文を読む]]

### Downloads再構成・参照文脈（元系列ADR-127／2026-10-06）

[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・参照文脈（元系列ADR-127／2026-10-06）|移動した本文を読む]]

### Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）

[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・専門側責務（元系列ADR-126／2026-10-06）|移動した本文を読む]]

### Downloads再構成・最低回数後の追記: 初回のラベル・尺度は専門エージェントが作成する（2026-10-05）

[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・最低回数後の追記: 初回のラベル・尺度は専門エージェントが作成する（2026-10-05）|移動した本文を読む]]

### Downloads再構成・最低回数後の追記: 初回に全担当へ依頼し、尺度要件を集約して担当指示する（2026-10-05）

[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・最低回数後の追記: 初回に全担当へ依頼し、尺度要件を集約して担当指示する（2026-10-05）|移動した本文を読む]]

### Downloads再構成・最低回数後の追記: 同じ回答を最低回数に加算しない（2026-10-05）

[[40-Design/50-Governance/decisions/03-topics/17-section#Downloads再構成・最低回数後の追記: 同じ回答を最低回数に加算しない（2026-10-05）|移動した本文を読む]]
