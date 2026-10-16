---
note_type: reference-section
status: current
updated: '2026-10-02'
source_head: ddc23abe0d747a1e6cfd6d3bc262ce226f4756b0
tags:
- gurumoji/design
- gurumoji/ui
note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique-section-05
title: Gurumoji 静止モックアップの独立批評：修正連携と再確認
summary: 修正連携と再確認。出典ノート「Gurumoji 静止モックアップの独立批評」の分割本文。
parent_note_id: ui-archive-50-tests-ui-design-evidence-2026-10-02-mockup-critique
source_path: 50-Tests/ui-design-evidence/2026-10-02/mockup-critique.md
source_sha256: a5930f15d27ba0bde495c47e25e7920c6463caf23571b284ea0a61df3c58cbb7
source_body_lines:
- 161
- 210
split_on: '2026-10-11'
---

# Gurumoji 静止モックアップの独立批評：修正連携と再確認

親索引・状態・確認版：[[50-Tests/ui-design-evidence/2026-10-02/mockup-critique]]。必要な本文だけを取得する。

## 修正連携と再確認

MC-01〜06に相当する具体的な修正候補は、生成担当へ直接連携した。返却された修正版10図を再度画素確認し、初回の指摘を消さずに以下へ結果を追記した。このレビューによるアプリ、runtime、Vault、外部サービスの変更はない。


## 修正版の再確認

2026-10-02 20:00〜20:02 UTC頃、修正版の比較8図と新規補助状態2図をすべて `view_image` で再確認した。新しい `v2/outside-legend.md` 全文と `v2/validation.json` も読んだ。生成担当の静止validationは `issues=[]` だが、以下の判定は独立した画素所見であり、その結果をGUI合格へ拡張しない。

| 指摘 | 修正後に画素で確認したこと | 判定と残る条件 |
|---|---|---|
| MC-01 | 全測定図に「定義1版・入力12版で試行」。変更後2図に「定義を変更・未保存」「再試行が必要」「前の試行結果（秒）」と無効な採用の表現 | **設計を補強**。現在の編集値と試行bindingの照合、check失効、遅延応答排除、採用server gateは未検証。表示だけで解消としない |
| MC-02 | B mobileに「AI下書き・未確認」、主張全文、重要性／全体合意を判断しない注意、根拠1発話・条件が復帰link下へ戻った | **可視情報不足を解消**。研究者メモは展開／復帰が必要。A/B同等の実負担は未測定 |
| MC-03 | 全測定図headerが「全5発話・除外1 → 試行4」、説明が「除外後の先頭4発話を試しました」 | **このfixtureでの集合表現を改善**。0件・N件以上・異なる除外数への一般化は未検証 |
| MC-04 | S004の操作が緑の下線付き「発話を確認」になった。欠測と時刻不明は残る | **可視affordanceを改善**。実link・accessible name・固定試行入力への遷移は未検証。行contextを読めないATでもS004と分かるnameが必要 |
| MC-05 | 両mobileの定義要約に「重要性や関与の強さは表しません」が採用より前に追加された | **可視の限界説明を回復**。追加で長くなったことを欠点だけで評価せず、理解を比較する |
| MC-06 | 全根拠図で「S002・話者B・01:00–01:02」を表示。凡例にはE-002/run/hash等の詳細内容を記載 | **通常表示のID不足を解消**。実際のID解決・前後文脈の版整合は未検証 |
| MC-07 | A mobileの段階2の背景／枠は読みやすくなった。補助失効図では再試行が強い主操作で、採用不可の理由も明示 | **低優先の残留項目**。通常画面の未チェック採用disabledとmobile最上部nav現在地は、実装時に役割／状態／focusと併せて検討 |

### 追加2図の具体所見

- `b-measurement-changed-desktop.png`: 文字数へ変わった定義は上、amberの失効説明と「変更した定義で再試行する」が先にあり、旧20.7秒は下の「前の試行結果（秒）」へ格下げされた。旧値を新しい文字数と取り違えにくい表示になった
- `b-measurement-changed-390.png`: 同じ順序が1列で保たれ、失効理由は折返されても欠けていない。旧4発話の個票はdetailsに保留、採用は無効という意図が文章でも示される
- これらは**失効時の補助storyboard**。B desktopの左編集field／右試行という構成から、編集した瞬間にどうこの状態へ遷移するかは描いていない。実装で編集面全体を突然置換してfocusや未保存入力を失わないこと、又は同じ編集面内へこの警告と状態を収めることを次に確認する。追加図をその遷移の実証とはしない

### 修正版で残る比較上の注意

- B mobile根拠は1205px、Aは1299pxになったが、Bは研究者メモを展開／復帰へ移している。94px短いことを効率・認知負担の優位に換算しない
- 測定mobileはA1446px、B1385px。どちらも必須情報を足した結果として長くなった。次の改善対象は長文・複数個票での探しやすさと操作保持であり、必須の版・限界・欠測説明を再び隠すことではない
- 全10図でこのfixtureの文字の欠け・重なり・frame外への明白なはみ出しは見えなかった。Noto静止PNGでの所見に限定する
- quiet green、紙色、主張／研究者／原資料の文字による区別、音声停止理由、採用と全件実行の分離は維持されている

### 再確認した画像

以下のSHA-256は修正版再確認直後に読み取った。今後再生成した場合はこの判定と版を区別する。

| ファイル | 寸法 | SHA-256 |
|---|---|---|
| a-evidence-390.png | 390×1299 | `2186f4758516a96292dbb50829a2029c68ed4eb43b4333eaac577af0a34e8702` |
| a-evidence-desktop.png | 1280×1268 | `b21eeb523ecc0c6f2311649ac7dd9c061db39960b1ef3b0fc200602def2dbb86` |
| a-measurement-390.png | 390×1446 | `44fd05d66c7e7fa9db16d7ee6655dd61fc7d0d87902bb1094814d55737ec4cf1` |
| a-measurement-desktop.png | 1280×1013 | `95c51955f6dafbe54319354d3500ee6a98bba456d71ab71718b3f955bacb300b` |
| b-evidence-390.png | 390×1205 | `5baa423aac7bda9c9b29fbfab115834956325a5c8643450064cd946eb2911566` |
| b-evidence-desktop.png | 1280×963 | `5833b732126fa1406ab6080acfa363162d7b084c5230dbc8e8527b1a606290e9` |
| b-measurement-390.png | 390×1385 | `5d665d9301a3152394e89ea6f63aa36e49f17deecfab0717c32071ecaee193f4` |
| b-measurement-changed-390.png | 390×929 | `c28cce7267bcd8712f440d6039df0319ff6e97bf974271e9918e5da4af6eabb1` |
| b-measurement-changed-desktop.png | 1280×856 | `f6c73fc6251772c68c9cba8dcd9ae2a31b1e4219e0f9f1881d71384db229de7f` |
| b-measurement-desktop.png | 1280×1005 | `8c1499688a52d71bab4ebeb645fc72a48dab5497715ce4b063a863769cb10a45` |

最終判断: この静止案の具体的な情報欠落は修正で改善した。Aを段階導入の初期候補にする提案は維持するが、Bを使いにくいと確定はしない。操作可能な試作へ進む場合は、上記のbinding・採用・復帰・AT・reflowの未検証条件をそのまま引き継ぐ。
