path = "docs/program-vault/40-Design/ui-ux-issues.md"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("| UX-35 |"):
        new_lines.append("| UX-35 | 高 | 動画プレビュー領域が横幅300〜380pxに固定され、映像やスライドの文字が小さすぎて読めない | `static/style.css:363`: `.transcript-layout` | 会議スライドの文字、話者の表情・口元の動きが潰れ、動画を見ながらの文字起こし確認・修正が極めて困難 | 動画領域の横幅をminmax(380px, 480px)に拡大し動画の視認性を確保 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P0：最優先 |\n")
    elif line.startswith("| UX-36 |"):
        new_lines.append("| UX-36 | 中高 | ライトテーマの中に動画領域だけ真っ黒な枠（#17201c）があり、視線移動時のコントラスト差で目が疲れる | `static/style.css:679`: `.media-review` | 左の暗色ボックスと右の白背景エディタを交互に見るため、明暗差が激しく長時間の確認作業で疲労が大きい | 動画プレイヤーのコンテナ配色を全体のライトカードスタイルに統合 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P1：優先 |\n")
    elif line.startswith("| UX-37 |"):
        new_lines.append("| UX-37 | 高 | 発話（セグメント）1件ごとの縦幅が約250pxと巨大で、1画面に2〜3件しか入らず会話全体の文脈が見通せない | `static/style.css:803`: `.segment` | チャットや字幕のように文脈を一望できず、頻繁なスクロールを強いられ、全体の会話の流れの把握や校正が困難 | 通常時はタイムライン形式でコンパクト表示、選択・フォーカス時に詳細編集フォームを展開 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P0：最優先 |\n")
    elif line.startswith("| UX-38 |"):
        new_lines.append("| UX-38 | 中 | 上部のアウトライン・リザルト情報が巨大で、ファーストビューで動画プレイヤーとテキストが画面外に見切れる | `src/gurumoji/templates/index.html:701`: `<details id=\"session-outline\">` | 画面を開いた直後に作業対象の動画と発話リストが見えず、毎回下へスクロールする手間が生じる | アウトラインを既定で折りたたみ、ファーストビューに動画と発話冒頭が収まる配置に改善 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P1：優先 |\n")
    elif line.startswith("| UX-39 |"):
        new_lines.append("| UX-39 | 中 | 動画の再生位置と発話リストの連動・追従（オートスクロール）が弱く、現在位置を見失いやすい | `static/app.js:renderMedia`: 再生連動 | 「今、動画のどの発話を喋っているか」が視覚的に追えず、長時間の動画で迷子になりやすい | `timeupdate` に連動して再生中の発話をハイライト、スムーズ追従する自動追従トグルを導入 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P1：優先 |\n")
    elif line.startswith("| UX-40 |"):
        new_lines.append("| UX-40 | 中 | 処理中画面（Progress Card）のアニメーション・システム計器・点滅ランプが過剰で視覚的ノイズが大きい | `index.html:85-162`: 過密計器 | 視覚的疲労・圧迫感を軽減 | 主要進捗に絞り、システムモニタやトークン詳細・ログを「詳細システム情報とログ」アコーディオンに格納、波形アニメをマイルド化 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P1：優先 |\n")
    elif line.startswith("| UX-41 |"):
        new_lines.append("| UX-41 | 中 | 設定項目が5つのアコーディオンに埋もれ、フォントサイズが極小（約11px）で漢字が潰れて可読性が低い | `static/style.css`: フォントサイズと行間 | 日本語の可読性低下 | フォントサイズ・余白・行間を調整し、漢字潰れを解消し可読性を向上 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P2：後続 |\n")
    elif line.startswith("| UX-42 |"):
        new_lines.append("| UX-42 | 低中 | カードと背景の境界線・明度差が小さく、視覚的な階層（ビジュアルヒエラルキー）が曖昧で画面が散漫に見える | `static/style.css`: カード境界 | 画面が散漫に見える | カードのシャドウ・コントラスト・ボーダー色を調整しメリハリを向上 | 対応済み（[[40-Design/video-ui-redesign-plan]]） | P2：後続 |\n")
    else:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Updated ui-ux-issues.md successfully")
