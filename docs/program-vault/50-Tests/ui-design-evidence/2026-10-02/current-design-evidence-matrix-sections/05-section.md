---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix-section-05
title: Gurumoji デザイン監査・証拠対応表：DG-09 補助文字・未保存色・共通focusのコントラストを用途別に補正する
summary: DG-09 補助文字・未保存色・共通focusのコントラストを用途別に補正する。出典ノート「Gurumoji デザイン監査・証拠対応表」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-current-design-evidence-matrix
source_path: 50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix.md
source_sha256: 802a60c49581ed2fa58b53e0f6cf7c89e53cf3b8245598118fa442eccfa049cc
source_body_lines:
- 118
- 139
split_on: '2026-10-11'
---

# Gurumoji デザイン監査・証拠対応表：DG-09 補助文字・未保存色・共通focusのコントラストを用途別に補正する

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/current-design-evidence-matrix]]。必要な本文だけを取得する。

### DG-09 補助文字・未保存色・共通focusのコントラストを用途別に補正する

- 優先度: P2
- 根拠: `src/gurumoji/static/style.css:14-32,41,535,941-945,1052-1055,1580-1582,1635,2274,2313`、`artifacts/design-sprint-20261003/specified-color-contrast.json`
- 影響: cascade確認後の通常drop-zoneは背景white（1635/2274）で、#8a948fとの比率3.128:1。登録話者概要の未保存orangeはgradient上2.627〜2.759:1。保存バーは半透明のため実背景計算が必要。35%緑focus outlineは明背景との合成例で約1.7:1。一方、analysis sidebarの未保存#97451dは#f2f5ef上5.992:1であり同列に問題扱いしない。
- 最小案: 既存green/ink/paperを保ち、warning-text、muted-text、focus-ringを用途別にする。装飾のorangeを重要な文字へそのまま流用しない。focusは不透明で十分識別できる色を使う。
- 受入:
  - 通常の必要な小文字は実背景上4.5:1、必要な非テキスト状態表示は3:1を基準に測定する。disabledなど例外を通常文字と混同しない
  - hover/selected/stale/unsaved/error/high-contrast等を個別に確認。色だけで状態を区別しない
  - focusの境界と隣接背景、stickyで隠れないことをキーボード実操作で確認し、outlineの存在だけで合格にしない

### DG-10 相互作用リンクの対象・関係selectに名称がない

- 優先度: P2
- 根拠: `src/gurumoji/static/app.js:7317-7347`
- 影響: 2つのselectがlabel/aria-labelなしでdivへ追加される。対象発話と関係のどちらを選んでいるか、支援技術で区別しにくい。根拠メモinputはplaceholderの名前fallbackがあり得るため無名と断定せず、見えるlabelの改善対象とする。
- 最小案: 対象発話・関係・根拠メモを見えるlabelで結び、同じ発話のfield groupとして伝える。追加後はリンク一覧の新規行へ適切に通知し、入力を勝手に失わない。
- 受入:
  - Accessibility treeで各select/inputに一意で内容の分かるnameがあり、現在の発話文脈を確認できる
  - Tab/矢印/Enterのみで対象と関係を選び、追加・取消・削除できる
  - NVDA/Edge等の実読み上げを記録し、DOM属性だけを音声受入の代わりにしない
