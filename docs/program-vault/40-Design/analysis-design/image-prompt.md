# UI画像生成プロンプト

生成方式：組み込み image_gen。新規画像、参照画像なし。画面内の数値・発話は架空。

初回生成後に同じ画像を参照して編集。M2実行中のアイコンを完了チェックから数字2へ修正し、TIFFの選択肢を追加した。最終採用画像はv2。

編集プロンプト：

```text
Edit this Japanese Gurumoji 2x2 UI design board with only two targeted corrections. Preserve all panel layouts, typography, colors, text, tables and other content. In bottom-left S03 milestone stepper, M2 is currently running, so replace the check mark inside the teal M2 circle with the numeral 2 or a clear progress ring; M0 and M1 keep completed check marks, M3-M7 keep locks. In bottom-right S04 image format options, add a TIFF radio option next to SVG and PDF, maintaining spacing and legibility. Everything else remains unchanged. This is a conceptual mockup with fictional data.
```

成果物：`ui-concept-v2.png`。構造化先：`design-spec.json` の S01〜S04。生成画像の文字・細部より、設計書・JSONの定義を優先する。

```text
Use case: ui-mockup. Create a high-fidelity product design presentation board for Gurumoji, a Japanese group interview research analysis desktop web app. This is a conceptual UI design, all data fictional. Landscape high resolution preferably 3072x2048. Four equally sized desktop screen mockups in a precise 2x2 grid, large crisp readable Japanese UI type, no perspective, no devices, no photographs, no decorative illustrations. White surfaces, very pale blue gray backgrounds, navy typography, teal primary buttons, restrained amber pending states. Each screen has consistent top navigation "新規作成 / 処理済みデータ / 話者管理" and secondary analysis workspace navigation "結果を見る / 比較する / 分析を組む / データ・出力". Clearly annotate panel names with large headings:
"S01 結果を見る": research dashboard with an outline sidebar "導入効果", "費用", "運用体制"; central speaker-by-topic colored stance matrix with textual labels "賛成", "反対", "中立", "第三案", "未判定"; below a conversation timeline; right small evidence drawer showing fictional speaker A and quote "費用の条件が合えば賛成です". Scope selection and "図を保存" button.
"S02 手動で分析を組む": MOST IMPORTANT shows actual editable text fields and not only checkboxes. Three labeled editable cards "ラベル" with "導入への賛否", "測定" with "話者×論点ごとに分類", "尺度" with "名義：賛成・反対・中立・第三案". Under these explicit column selectors "対象カラム：立場 / 所属", method selector "分析手法：クロス集計", plus "少数で試す" and "定義を確定". A small preview table. No automatic scale replacement.
"S03 実行状況": horizontal milestones M0 M1 M2 M3 M4 M5 M6 M7, M0 and M1 completed teal, M2 active, all later milestones gray locked. Large "M2 一次分析 2 / 4 完了". Four task rows: "言語解析 完了", "話者集計 完了", "立場判定 実行中", "意見集約 待機". Explain "この段階の全処理が完了すると次へ進みます". Buttons "完了済みの結果を見る" and "中止". No next button bypassing barrier.
"S04 データ・出力": left export choices "SPSS .sav", "jamovi .sav / .csv", "Excel .xlsx"; right chart preview and image options "PNG", "JPEG", "SVG", "PDF", "TIFF", size controls "幅 1800 px", "高さ 1200 px", "300 dpi", background "白 / 透過". Transparent disabled for JPEG. Primary "選択した成果物をZIPで保存". Clearly distinguish sample mockups from an implemented application with small "設計案・架空データ". All panels consistent clean spacing and research-oriented restrained design. Prioritize visible information hierarchy and exact short Japanese labels; no invented unreadable paragraphs.
```
