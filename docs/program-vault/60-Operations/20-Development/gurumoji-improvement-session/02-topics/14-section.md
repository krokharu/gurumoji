---
note_type: reference-section
status: current
updated: 2026-10-11
note_id: ops-gurumoji-improvement-session-20261003-section-14
title: Gurumoji 改善セッション：同日：プログラムとマーラータン分析データをDriveへ保存
summary: 同日：プログラムとマーラータン分析データをDriveへ保存。出典ノート「Gurumoji 改善セッション」の分割本文。
parent_note_id: ops-gurumoji-improvement-session-20261003
source_path: 60-Operations/gurumoji-improvement-session.md
source_sha256: e764a28d48eacc8891bde46b74f2b17cdf659083d8482f2e62493d45f9701abe
source_body_lines:
- 249
- 259
split_on: '2026-10-11'
tags:
- gurumoji/program
---

# Gurumoji 改善セッション：同日：プログラムとマーラータン分析データをDriveへ保存

親索引・状態・確認版：[[60-Operations/20-Development/gurumoji-improvement-session/00-Index]]。必要な本文だけを取得する。

### 同日：プログラムとマーラータン分析データをDriveへ保存

- 利用者指定の[Driveフォルダー](https://drive.google.com/drive/folders/1TeCym1pulQdMUIrg0HxlU0XCaMo0RTlq)へ、[プログラム＋分析データZIP](https://drive.google.com/file/d/1pwGblwEnTyfXPqUz6XSOxnq3miVJu6wg/view?usp=drivesdk)を新規アップロードした。プログラムは`75ebbb6d5ab2cda50e5b90712bc3298e8b8c714b`のGit追跡ファイル907件を`program/`へ、成功したrun `run_008cbf3502d7400e94876c47734b1325`の試験用DB、固定入力・結果・JSON表/CSV・検証記録を`analysis-data/`へまとめた。既存Driveファイルの上書き・共有設定変更なし。
- 元の試験DBは読取専用でSQLite backupし、1インタビュー・正常終了・Core判断3回を照合。DB quick_check、保存artifactのhash、ZIP全922ファイルのCRC/manifest hashを確認した。アップロード後のDriveメタデータで指定親フォルダー・ファイル名・26,716,952 bytesの一致を確認。Drive応答にはchecksumが返らず、遠隔bytesのhash比較は未実施。ローカルSHA-256は`ee9c3ee5d3e1d62f788317dce80dcb8536a8c2af7366d430132e8537afcaa903`。確認記録は`output/drive-export/bundle-verification.json`と`drive-upload-verification.json`。
- 設定の秘密値、モデル、仮想環境、媒体、個人Vault、Git履歴は含めない。323発話を保持するがAI各回の入力は48発話、成功試験には回答量の制限指示がある。元のcollector失敗報告と最終再検証を両方保持し、READMEで区別した。利用者の原本DB/Vaultへの書込み、別環境への展開・自動取込・再推論は未実行。DB内の試験当時の絶対パスは保持し、可搬なアプリ復元を検証済みとは扱わない。

### 同日：3回反復の保存内容を点検

- 利用者への内容説明のため、上記成功runの試験DBを読取専用で照合。Core3回の原応答hashは全て`sha256:1807e2c811a0ed49a671df26d18f4fac6336ce05d5efa7b361f997b7d276079a`で一致し、要約・主張3件・代替説明3件・未解決点3件・作業案・終了案が同じ。view_versionも全て1。独立verificationの24主張が後続Coreの見解へ反映されたという根拠はない。3回目でも情報不足を記載しつつquestion_satisfiedで停止している。
- 既存のpassedは通信・採用回数・正常終了・保存の動作判定で、回答の新規性や研究上の十分性を判定していない。最低回数の制御は確認できるが、分析内容が深化するループを確認済みとは扱わない。次の調査対象は同一応答の検知、独立検証の採否、情報不足と終了判断の整合性。今回コード変更・再推論・原本DB/Vault書込み・Drive成果物更新は行っていない。
