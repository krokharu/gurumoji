---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns-section-02
title: Gurumoji の研究作業に使う公式 UI 参照パターン：2 作業を横断した比較
summary: 2 作業を横断した比較。出典ノート「Gurumoji の研究作業に使う公式 UI 参照パターン」の分割本文。
parent_note_id: ui-archive-40-design-ui-design-research-2026-10-02-reference-patterns
source_path: 40-Design/ui-design-research/2026-10-02/reference-patterns.md
source_sha256: f1334e394b188d0ff4c52216c8a7ff37e52789869513174579c3868d7764a702
source_body_lines:
- 48
- 71
split_on: '2026-10-11'
---

# Gurumoji の研究作業に使う公式 UI 参照パターン：2 作業を横断した比較

親索引・状態・確認版：[[40-Design/ui-design-research/2026-10-02/reference-patterns]]。必要な本文だけを取得する。

## 2 作業を横断した比較

表内は特記がなければ **M**。製品間の優劣や使いやすさの得点ではない。

| 観点 | MAXQDA | ATLAS.ti | Dovetail | Descript |
|---|---|---|---|---|
| 選択を作業対象として残す | coded segment を取得一覧で扱う [R03] | quotation に ID・位置・名称・comment [R08, R10] | 選択から highlight、後から tag を付与 [R11] | script の選択がメディア編集範囲にもなる [R20] |
| 原文・原音への移動 | 出典を選ぶと元文書と該当範囲、時刻から再生 [R01, R03] | quotation の文脈再生、timestamp による同期 [R08, R09] | sidebar の highlight から本文へ移動、回答内の出典 preview [R11, R14] | 語と波形の alignment を wordbar で調整 [R18] |
| confidence と来歴 | 生成設定 memo、既存／提案／一致を区別 [R04, R06] | 時刻精度と推定同期の制約を明記 [R09] | AI 提案の承認／却下、AI 編集者の版帰属 [R11, R12] | 灰点線は再alignment中、赤下線はalignment問題の例 [R16, R17] |
| 長時間処理 | ジョブ数の入口と完了通知。別作業を続けられる [R04] | AI Coding 中に別作業が可能 [R07] | 処理中に離脱可能。clip出力準備の進捗を別表示 [R12, R15] | upload／処理の後に文字起こし。別途sync表示 [R17, R19] |
| コードとレビュー | 原文＋既存＋提案、適用前の追加／削除件数 [R06] | 候補の分類と引用を確認して Apply [R07] | AI highlight の Suggest／On／Off と承認・却下 [R11] | この資料集合では研究コードブックの review は不明 |
| 空・失敗・復旧 | 失敗時に既成 transcript の backup を確認する案内 [R05] | 今回の資料で失敗画面・空状態は不明 | codec不適合／音声trackなし等を切り分け [R12] | 未開始／stuck／misalignment／部分欠落を分けて案内 [R17] |
| 初学者と反復操作 | 文字だけの編集／聞きながら編集、基本再生＋詳細設定 [R02] | ボタンとshortcutの範囲作成、一覧の列／表示切替 [R08, R10] | 文脈actionからhighlight、後から整理 [R11] | 単語修正と継続Correct modeを併用 [R16] |
| 証拠を外へ渡す | 出典付きcopy、出力する属性を選択 [R21] | quotation reportの内容を選べる [R10] | VTT／CSV／PDF／clipで保存情報が異なる [R15] | 本文注記の出力とalignment付き字幕を扱う [R18, R20] |

### 「選択が残る」の4段階を混同しない

1. **一時選択**: マウスやキーボードで今選んだ範囲
2. **保存された抜粋**: quotation／highlight／coded segment として後で開ける範囲
3. **閲覧位置の復帰**: 根拠を開いて戻ると、同じ filter・並び・scroll・focus が戻ること
4. **版を越えた整合性**: 本文修正や再生成後も、元の版の引用と現在版を正しく識別すること

今回、2の公式記述は複数製品で得たが、3の完全な復帰契約や4の全条件を実証してはいない。Gurumoji の監査 F2/F5 に必要なのは2だけでなく3と4であり、ここを競合画面の見た目から補完しない。
