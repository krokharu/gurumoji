"""Editable SVG design frames for import into Figma (no private data)."""
from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parents[1] / 'output/design/analysis'
OUT.mkdir(parents=True, exist_ok=True)

def build(mobile=False):
    width, height = (390, 1240) if mobile else (1440, 1120)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<title>Gurumoji 分析画面改善案・サンプルデータ</title>']
    def rect(x,y,w,h,fill='#fffef9',stroke='#d9ddd5',r=12):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')
    def text(x,y,value,size=14,color='#18211d',weight=400):
        parts.append(f'<text x="{x}" y="{y}" font-family="Yu Gothic UI, Noto Sans JP, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(value)}</text>')
    def button(x,y,w,label,active=False):
        rect(x,y,w,44,'#1c6b50' if active else '#fffef9')
        text(x+14,y+28,label,14,'#ffffff' if active else '#526159',700)
    rect(0,0,width,height,'#f4f5f0',r=0)
    rect(0,0,width,64,r=0)
    text(24 if mobile else 80,40,'GURUMOJI',18,weight=700)
    if not mobile:
        text(330,40,'文字起こし     データ一覧     分析・可視化     話者管理',14)
        text(1080,40,'画面改善案 / サンプルデータ',13,'#526159')
    x,w = (16,358) if mobile else (80,1280)
    rect(x,88,w,height-112)
    text(x+20,125,'分析・可視化',13,'#1c6b50',700)
    text(x+20,160,'会話データの分析結果',22 if mobile else 28,weight=700)
    text(x+20,189,'発話量・言葉・会話の流れを確認',14,'#526159')
    if mobile:
        button(36,210,142,'分析を実行',True)
        button(190,210,162,'文字起こしを開く')
        button(36,266,316,'出力・実行設定')
        top=330
    else:
        button(878,118,130,'分析を実行',True)
        button(1018,118,150,'文字起こしを開く')
        button(1178,118,158,'出力・実行設定')
        top=216
    rect(x+20,top,w-40,88,'#f2f5ef')
    text(x+34,top+26,'分析対象',13,'#526159',700)
    text(x+34,top+59,'架空の座談会.wav　（発話24件）',14)
    if not mobile:
        text(810,top+31,'現在の対象：架空の座談会.wav',14,'#1c6b50',700)
        text(810,top+59,'発話24件 / 02:23 / 保存済み',13,'#526159')
        rect(100,326,200,354,'#f2f5ef')
        text(116,356,'分析ワークスペース',15,weight=700)
        for i,label in enumerate(['自動分析','設定・手動分析','手法別']):
            button(116,380+i*54,168,label,i==0)
        text(116,576,'保存済みの結果を表示中',13,'#526159')
        text(116,636,'▸ 分析結果の読み方',14,'#1c6b50',700)
    cx,cw,cy = (36,316,442) if mobile else (324,1012,350)
    if mobile:
        for i,label in enumerate(['自動分析','設定・手動','手法別']):
            button(36+i*108,438,100,label,i==0)
        cy=518
    text(cx,cy,'会話全体の分析結果',20,weight=700)
    text(cx,cy+30,'概要から傾向をつかみ、根拠の発話を確認',13,'#526159')
    rect(cx,cy+50,cw,48,'#e9f2e6')
    text(cx+14,cy+80,'インタビュー全体',14,'#13513c',700)
    text(cx+cw*.6,cy+80,'話者ごと',14,'#526159')
    metrics=[('会話時間','02:23'),('対象発話','24件'),('話者','4人'),('参加者','3人'),('総発話時間','02:00')]
    for i,(label,value) in enumerate(metrics):
        mw=(cw-12)/2 if mobile else (cw-48)/5
        mx=cx+(i%2)*(mw+12) if mobile else cx+i*(mw+12)
        my=cy+114+(i//2)*90 if mobile else cy+114
        if mobile and i==4: mw=cw
        rect(mx,my,mw,78)
        text(mx+12,my+25,label,13,'#526159')
        text(mx+12,my+57,value,24,'#13513c',700)
    ny=cy+398 if mobile else cy+212
    labels=['概要','内容・文脈検索','会話推移','言語構造','統計','出力・検証']
    if mobile:
        nx=cx
        for i,(label,nw) in enumerate(zip(labels[:3],[60,140,104])):
            button(nx,ny,nw,label,i==0)
            nx+=nw+6
        text(cx,ny+66,'横にスクロールして他の項目を選択 →',12,'#526159')
    else:
        for i,label in enumerate(labels): button(cx+i*(cw/6),ny,cw/6-5,label,i==0)
    sy=ny+88 if mobile else ny+66
    rect(cx,sy,cw,174)
    text(cx+18,sy+30,'分析結果の見解',18,weight=700)
    text(cx+18,sy+65,'複数の話者が使っている言葉',15,'#13513c',700)
    text(cx+18,sy+93,'「改善」は3人・8発話に現れます。',14)
    text(cx+18,sy+118,'賛否や使われ方は文脈で確認します。',14,'#526159')
    text(cx+18,sy+151,'▸ 根拠の発話を確認（8件）',14,'#1c6b50',700)
    if not mobile:
        rect(cx,sy+192,cw,52)
        text(cx+18,sy+224,'▸ AIで内容・意見を整理',14,'#13513c',700)
        text(cx,sy+282,'改善点：概要を先頭に／目的別に切り替え／説明と追加操作を折りたたみ／本文14px以上',14,'#526159')
    parts.append('</svg>')
    name='mobile' if mobile else 'desktop'
    (OUT / f'figma-import-{name}.svg').write_text('\n'.join(parts),encoding='utf-8')

build()
build(True)
