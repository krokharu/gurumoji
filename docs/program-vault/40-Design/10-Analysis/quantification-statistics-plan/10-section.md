---
note_type: reference-section
status: proposed
updated: 2026-09-20
tags:
- gurumoji/analysis
- gurumoji/statistics
- gurumoji/design
note_id: design-quantification-statistics-plan-section-10
title: 発話の数値化とjamovi型統計の自動実行計画：12. 配布条件（ライセンス）
summary: 12. 配布条件（ライセンス）。出典ノート「発話の数値化とjamovi型統計の自動実行計画」の分割本文。
parent_note_id: design-quantification-statistics-plan
source_path: 40-Design/quantification-statistics-plan.md
source_sha256: 72fc8e49117b2416635ff3d9d9b2a07ed9a4e1287e75c4b43f96d73411bf9b04
source_body_lines:
- 309
- 333
split_on: '2026-10-11'
---

# 発話の数値化とjamovi型統計の自動実行計画：12. 配布条件（ライセンス）

親索引・状態・確認版：[[40-Design/10-Analysis/quantification-statistics-plan/00-Index]]。必要な本文だけを取得する。

## 12. 配布条件（ライセンス）

2026-09-15に、`.venv`のパッケージのメタデータとライセンスファイル、PyPIの情報、FFmpegのビルド構成（`-version`）で確認した。

| 区分 | 対象 | ライセンス | 義務・扱い |
| --- | --- | --- | --- |
| 本体 | このリポジトリのコード | MIT（Phase 0で`LICENSE`を追加） | 著作権表示とライセンス文 |
| 直接の依存 | Flask、psutil、NumPy、SciPy、scikit-learn、pandas、torch、torchaudio | BSD系 | 表示の保持 |
| 直接の依存 | openai-whisper、faster-whisper、CTranslate2、PyYAML、openpyxl、GiNZA、ja-ginza、spaCy | MIT | 表示の保持 |
| 直接の依存 | WhisperX、imageio-ffmpeg（ラッパー部分） | BSD-2-Clause | 表示の保持 |
| 直接の依存 | transformers、SudachiPy、SudachiDict-core | Apache-2.0 | 表示とNOTICEの保持 |
| 追加する依存 | statsmodels（BSD-3-Clause）、patsy（BSD-2-Clause）、formulaic（MIT）、interface-meta（MIT） | 許容型 | 表示の保持 |
| 間接の依存 | pyannote.audio（MIT）、torchcodec（BSD-3-Clause）、certifi（MPL-2.0）、tqdm（MPL-2.0とMIT） | 許容型、ファイル単位のコピーレフト | MPL-2.0の部分は改変しなければ表示だけ |
| 同梱バイナリ | imageio-ffmpegのWindows wheelに入るFFmpeg 7.1（gyan.dev essentialsビルド、`--enable-gpl --enable-version3`） | GPLv3 | 別プロセスとして実行する。`.venv`やインストーラーを配布する場合は、GPLv3の文と対応するソースの入手方法を付ける。ソース（Git）の配布には含まれない |
| 環境にあるが依存ではない | PySide6、shiboken6 | LGPL-3.0／GPL | どのパッケージにも必要とされず、コードでも使っていない。配布物に含めない |
| モデルの重み | Whisper、pyannote、E5、AISTの感情モデルなど | 各配布元の規約（Hugging Faceで同意が必要なものを含む） | リポジトリに含めない。利用者が各規約に同意して取得する |
| 利用者が別に導入するソフト | jamovi、R、jmv | 各ソフトの規約 | 同梱もimportもしない。アプリが出力するのはデータとR構文だけ |

依存の方針：

- プロセス内でimportする依存は、MIT・BSD・Apache-2.0などの許容型、改変しないMPL-2.0、動的リンクのLGPLに限る。
- GPL・AGPLのライブラリ（pingouin、Parselmouth、jmvReadWriteなど）はimportしない。必要なら、利用者が別に導入する外部プログラムとして呼ぶ。
- 参加者データとモデルの重みは、どの配布物にも含めない。
- 依存を追加・更新するときは、この表と`THIRD_PARTY_NOTICES.md`を同じ変更で更新する。
