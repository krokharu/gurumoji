---
note_type: reference-section
status: in-progress
updated: 2026-09-30
schema_version: 1
tags:
- gurumoji/analysis
- gurumoji/knowledge-builder
- gurumoji/colab
- gurumoji/plan
note_id: design-a100-knowledge-control-plane-plan-section-07
title: A100知識推論コントロールプレーン計画：8. Colab接続・再接続・利用時間の方針
summary: 8. Colab接続・再接続・利用時間の方針。出典ノート「A100知識推論コントロールプレーン計画」の分割本文。
parent_note_id: design-a100-knowledge-control-plane-plan
source_path: 40-Design/a100-knowledge-control-plane-plan.md
source_sha256: ea63a64d75500f68ce3e184529136bf4a2b05b7a85c74eeac32cd7120c925f64
source_body_lines:
- 375
- 411
split_on: '2026-10-11'
---

# A100知識推論コントロールプレーン計画：8. Colab接続・再接続・利用時間の方針

親索引・状態・確認版：[[40-Design/20-Knowledge/a100-knowledge-control-plane-plan/00-Index]]。必要な本文だけを取得する。

## 8. Colab接続・再接続・利用時間の方針

通常版Colabには、外部アプリからmanaged runtimeを起動・A100指定・再接続するための公開された管理APIがない。したがって「自動接続」は次の範囲に限定する。

### 自動化する

- Drive APIによる要求ZIPのupload、結果ZIP・heartbeat・checkpointのpollとdownload
- job/generation/hash/deadlineの照合
- heartbeat遅延、runtime消失、期限切れの検出
- 再実行後のcheckpoint検出と安全な再開
- キューが空、予算到達、deadline到達時のworker loop終了

### 手動に残す

- Colab Notebookを開く
- Googleアカウントでの認証とDrive許可
- runtime種別とGPUの選択
- 初回Run all、停止後の再接続、runtimeの明示的な切断

ブラウザー自動操作、疑似クリック、無意味な計算による接続維持、複数アカウントによる制限回避は実装しない。将来、完全なAPI制御が必要になった場合は通常版Colabを自動操作せず、Colab Enterpriseまたは専用GCP VM用の別adapterを追加する。

## 9. Pro利用枠を守る予算制御

ColabのGPU availability、idle timeout、最大VM寿命、消費率は固定値として公開されず、変動する。アプリだけで「Pro料金以外の請求が絶対に発生しない」と保証はできない。保証に近づけるため、Google側で追加Compute Unit購入またはPay As You Goを無効にし、アプリ側で保守的に停止する二重管理にする。

予算制御は次の順で実装する。

1. 利用者が月初残高、今回使えるCU、最低残高reserveを入力する。
2. 実行前に、同じGPU/model/contextの過去実測からCU、時間、tokenを予測する。
3. 予測上限が残予算を超えるjobはqueuedへ入れない。
4. 1 jobごとに結果と観測残高差を記録し、予測係数を更新する。
5. soft limitで新規claimを止めて進行中jobだけ完了し、hard limitで次の推論を開始しない。
6. 利用量を取得できない場合は`unknown`とし、設定した安全枠を超える新規A100 jobを止める。
7. キューが空ならGPU sessionを維持しない。CPUでのローカル監視も必要最小限にする。

既存の「キューが空でも毎時GPU health probeを行う」運用は、今回の予算優先要件と両立しないため廃止対象とする。health probeはsession開始時、model load後、異常復旧後だけにする。
