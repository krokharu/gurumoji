---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-02
title: Gurumoji 改善セッション：Backend区切り（9768b80）
summary: Backend区切り（9768b80）。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 66
- 92
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：Backend区切り（9768b80）

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

## Backend区切り（9768b80）

復旧後の新しい修正は2854ad6、8b8a5be、1ccd8b2、5cba079、b394553、19e886e、9768b80。旧の失われたcommitを復元したという意味ではない。

- `pytest tests -q -k 'not browser' --ignore=tests/test_qualitative_visualization.py`: 926成功、10skip、24deselect、467 subtests成功。実browserを合格扱いしない
- 独立48件成功。1120定義のmatrixは106受理/1014明示拒否、106実trial・44代表pipelineで不変条件違反0。非有限JSONを固定入力にできない条件は別計数
- 一時DB・合成fixtureのみ使用。外部AI、実モデル推論、実Vault移行、push/deployは未実施
- 依存・詳細ログ・再現probeは`../artifacts/eight-hour-20261003/`（appからの相対位置）。今後の差分をこの合格結果へ含めない
- 新binding/台帳を実runtimeで使う前には旧workerを停止またはdrainする。旧binaryを新runtimeへ戻す互換性は未検証。UIの撤回とbackend安全修正の撤回を分ける
- cloud browserの通常loopback経路は拒否、standalone Chromiumは起動制約あり。迂回せず、V3/V4/V5は未受入。静的・合成DOM確認と実画面を分ける

## 23:04 UTCの統合区切り

- 主branchは `5fa689f`。分析UIの14対象ファイルは受入元 `3443eae` のmanifest hashと一致して統合した
- 3種類の測定presetは元JavaScriptから実Flaskへ15要求の往復を検証。役割presetは登録来歴の不一致があり、独立受入を保留して修正中。合成DOMだけで実adapterの正しさを代用しない
- `869b843` の全体試験は976成功・32skip・1失敗。失敗は子processのimport経路で、`5fa689f` の対象3試験は成功。修正後の全体成功とはまだ扱わない
- 32skipの内訳は実browser opt-in未実施22、Windows依存10。GUI・支援技術・実音声の評価は別途未実施
- 保管source bundleは主branchに加えて本セッションの専用branchのcommitを含む。未統合branchを主branch受入済みとみなさない。最新の保管版とHEADはcheckpoint manifestに記録する

## 2026-10-04 00:05 UTCの統合区切り

- `c6e5094` のsourceを固定して `PYTHONPATH= .venv/bin/python -m pytest tests/ -q -rs`: 1012成功、32skip、953 subtests成功、失敗0。32skipはbrowser opt-in未実施22、Windows依存10。既存lokyのCPU数warning1
- 固定runは保存した要約・定義版・表を読取り、閲覧時に現入力から再計算しない。独立検証でDB・保存bytes不変、最新100件外のrun指定、破損/欠落停止、null/0/空欄と省略表示を確認
- 公開試行とpipeline台帳を同一DB snapshotから取得。最新の同package完了試行が4writer成功の根拠となり、古いpipeline台帳との不一致は別に表示。空scopeは不明なscopeや別packageと区別する
- source/synthetic受入と全体試験後も、追加監査で特殊keyを話者名やstatusにした不具合を再現したため修正する。既存テストの成功を、未試験条件の正しさへ拡張しない
- 次は実HTML・実handlerのDOM統合試験と、そこで再現した名前処理・control関連の局所改善。DOM libraryは外部resourceを読まず、実ブラウザーの描画・支援技術の評価には代用しない
