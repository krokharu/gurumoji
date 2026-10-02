from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parent
W, H = 1600, 1080
BG='#080F1B'; PANEL='#101C2C'; RAISED='#152337'; BORDER='#243348'
TEXT='#F1F5FA'; MUTED='#A0AEC1'; DIM='#718399'; CYAN='#63DAEB'; GREEN='#63D7AC'; AMBER='#E8BB71'
parts=[]
def rect(x,y,w,h,fill,rx=0,stroke=None):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')
def text(x,y,s,size=14,color=TEXT,weight=400,anchor='start',spacing=0):
    parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{spacing}">{escape(str(s))}</text>')
def line(x1,y1,x2,y2,c=BORDER):
    parts.append(f'<path d="M{x1} {y1}H{x2}" stroke="{c}"/>' if y1==y2 else f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{c}"/>')
def dot(x,y,color=GREEN,r=4):
    parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')
def icon(x,y,name,c=MUTED,size=20):
    paths={
      'grid':'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
      'chip':'<rect x="5" y="5" width="14" height="14" rx="3"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/>',
      'flow':'<circle cx="5" cy="5" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="5" cy="19" r="2"/><path d="M7 5h3a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7m5-7h5"/>',
      'arrow':'<path d="M5 12h14m-5-5 5 5-5 5"/>',
      'external':'<path d="M14 3h7v7m0-7L10 14M9 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
      'plus':'<path d="M12 5v14M5 12h14"/>',
      'check':'<path d="m5 12 4 4L19 6"/>',
      'refresh':'<path d="M20 7a9 9 0 1 0 1 9M20 2v6h-6"/>',
      'clock':'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      'gear':'<path d="M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1Z"/><circle cx="12" cy="12" r="3"/>',
      'chevron':'<path d="m9 6 6 6-6 6"/>',
      'search':'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
      'file':'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Zm0 0v6h6M8 13h8m-8 4h5"/>',
    }
    parts.append(f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>')
def pill(x,y,w,label,c=CYAN,fill='#173443'):
    rect(x,y,w,26,fill,13);text(x+w/2,y+18,label,11,c,600,'middle')
def button(x,y,w,label,primary=False,ic=None):
    rect(x,y,w,42,CYAN if primary else RAISED,9,None if primary else BORDER)
    col=BG if primary else TEXT
    if ic: icon(x+14,y+11,ic,col,18)
    text(x+w/2+(8 if ic else 0),y+27,label,13,col,600,'middle')
def panel(x,y,w,h):rect(x,y,w,h,PANEL,14,BORDER)

rect(0,0,W,H,BG)
rect(0,0,220,H,'#0D1725');line(220,0,220,H)
rect(24,29,36,36,'#143540',10);icon(32,37,'chip',CYAN,20)
text(72,46,'GURUMOJI',16,TEXT,700,spacing=1.4);text(72,64,'Knowledge Console',10,MUTED)
text(26,122,'WORKSPACE',10,DIM,600,spacing=1.8)
icon(27,151,'grid');text(59,167,'ダッシュボード',13,MUTED)
rect(14,192,192,48,'#173142',9);rect(14,204,3,24,CYAN,1)
icon(27,206,'chip',CYAN);text(59,223,'A100 実行',14,TEXT,600);pill(168,203,26,'4',CYAN,'#254352')
icon(27,259,'flow');text(59,275,'知識トレース',13,MUTED)
line(24,316,196,316)
text(26,349,'このワークスペース',10,DIM,600)
text(26,385,'17',24,TEXT,600);text(61,384,'専門家',12,MUTED)
text(26,417,'知識生成から評価まで',12,MUTED)
rect(16,883,188,95,'#111F30',10,BORDER)
dot(34,907);text(47,912,'Drive Worker',12,TEXT,600)
text(32,939,'Colab A100 に接続済み',11,MUTED)
text(32,959,'最終確認  12秒前',10,DIM)
icon(27,1009,'gear');text(59,1025,'接続設定',13,MUTED)
text(25,1060,'LOCAL WORKSPACE',9,DIM,spacing=1.5)

text(252,40,'ワークスペース',12,MUTED);text(367,40,'/',12,DIM);text(387,40,'A100 実行',12,TEXT,500)
pill(1261,20,115,'デザインプレビュー',MUTED,RAISED)
text(1559,39,'表示値はサンプル',11,DIM,anchor='end')
line(252,65,1560,65)
text(252,116,'A100 実行ワークスペース',30,TEXT,700)
text(253,145,'接続を確かめ、タスクを実行。進行中の処理と結果をひとつの場所で。',13,MUTED)
button(1254,98,136,'接続を確認',False,'refresh');button(1402,98,158,'タスクを追加',True,'plus')

stats=[('実行中','4','/ 4 スロット',CYAN,'4件を並列で処理中'),('待機中','3','件',AMBER,'保存順に自動で投入'),('実モデルで完了','5','件',GREEN,'結果は保存済み'),('失敗','0','件',MUTED,'対応が必要なタスクなし')]
for i,(label,num,unit,col,desc) in enumerate(stats):
    x=252+i*332
    panel(x,178,312,118);text(x+20,205,label,12,MUTED);dot(x+287,201,col,3)
    text(x+20,250,num,34,col,600);text(x+53,248,unit,12,MUTED)
    text(x+20,277,desc,11,DIM)

text(252,338,'実行中のタスク',18,TEXT,600);pill(410,318,42,'4件')
text(1188,336,'最大4件を並列処理',11,MUTED,anchor='end')

jobs=[('01','知識関係を抽出','質的内容分析','02:34','推論中','反復 2 / 5',True),('02','適用条件を評価','Framework Method','01:48','推論中','反復 1 / 5',False),('03','分析ラベル候補を生成','KJ法','00:56','推論中','1回実行',False),('04','会話タイミングを再評価','会話タイミング','03:12','評価中','反復 2 / 3',False)]
for i,(slot,title,expert,elapsed,phase,iteration,selected) in enumerate(jobs):
    x=252+(i%2)*480;y=356+(i//2)*168
    rect(x,y,456,148,PANEL,12,CYAN if selected else BORDER)
    text(x+18,y+25,'SLOT '+slot,10,CYAN if selected else DIM,600,spacing=1.1)
    pill(x+365,y+12,72,phase,GREEN if phase=='評価中' else CYAN,'#16352F' if phase=='評価中' else '#173443')
    text(x+18,y+55,title,17,TEXT,600);text(x+18,y+78,expert+'  ·  Qwen3 80B',11,MUTED)
    for j,label in enumerate(['投入','推論','評価','保存']):
        xx=x+18+j*106;active=(j==2 if phase=='評価中' else j==1);done=(j<2 if phase=='評価中' else j<1)
        rect(xx,y+96,98,3,CYAN if active else GREEN if done else BORDER,1)
        text(xx,y+115,label,10,CYAN if active else MUTED if done else DIM)
    icon(x+18,y+125,'clock',DIM,13);text(x+36,y+136,elapsed,10,MUTED)
    text(x+435,y+136,iteration,10,MUTED,anchor='end')

panel(252,718,936,278)
text(272,751,'待機キュー',17,TEXT,600);pill(377,730,42,'3件',AMBER,'#352D23')
text(1166,750,'一括実行中  ·  空き枠へ順次投入',11,CYAN,anchor='end')
line(252,770,1188,770)
text(272,795,'順番',10,DIM);text(329,795,'タスク / 専門家',10,DIM);text(786,795,'実行条件',10,DIM);text(1024,795,'状態',10,DIM)
rows=[('01','参加バランス指標を更新','参加バランス','目標 80点 · 最大5回'),('02','KJ法の分類ルールを検証','KJ法','1回実行'),('03','SCAT分析ステップを確認','SCAT','目標 80点 · 最大3回')]
for i,(n,title,expert,condition) in enumerate(rows):
    y=814+i*59
    if i:line(272,y-4,1168,y-4)
    text(277,y+25,n,12,DIM);text(329,y+18,title,13,TEXT,500);text(329,y+37,expert,10,DIM)
    text(786,y+26,condition,11,MUTED);pill(1024,y+8,66,'待機中',AMBER,'#352D23');icon(1138,y+13,'chevron',DIM,17)

text(254,1027,'✓  完了済み 5件',12,GREEN,500);text(422,1027,'結果を確認する',12,MUTED);icon(528,1013,'arrow',MUTED,18)
text(1188,1027,'工程表示は処理段階を示します',10,DIM,anchor='end')

panel(1212,318,348,368)
text(1234,350,'ランタイム',16,TEXT,600);pill(1460,329,78,'接続済み',GREEN,'#16352F')
rect(1234,372,44,44,'#173443',11);icon(1244,382,'chip',CYAN,24)
text(1292,391,'NVIDIA A100',20,TEXT,600);text(1292,412,'Google Colab  /  40 GB',11,MUTED)
line(1234,437,1538,437)
text(1234,466,'GPUメモリ',11,MUTED);text(1538,466,'33.8 / 40.0 GB',12,TEXT,600,'end')
rect(1234,481,304,6,BORDER,3);rect(1234,481,257,6,CYAN,3)
text(1234,518,'モデル',11,DIM);text(1538,518,'Qwen3 80B',12,TEXT,500,'end')
text(1234,548,'実行スロット',11,DIM);text(1538,548,'4 / 4 稼働中',12,CYAN,500,'end')
text(1234,578,'Compute Units',11,DIM);text(1538,578,'未取得',12,MUTED,400,'end')
line(1234,598,1538,598)
dot(1240,622,GREEN,3);text(1253,626,'12秒前に状態を確認',11,MUTED)
text(1234,657,'Colabを開く',12,TEXT,500);icon(1518,642,'external',MUTED,17)

panel(1212,706,348,290)
text(1234,738,'最新のアクティビティ',15,TEXT,600)
events=[('14:32:18','知識関係を抽出','改善点を反映して2回目を実行',CYAN),('14:31:42','群間比較統計の前提を評価','実モデルで完了 · 結果を保存',GREEN),('14:31:08','会話タイミングを再評価','Local LLMで評価を開始',CYAN)]
for i,(time,title,desc,col) in enumerate(events):
    y=768+i*68
    if i<2:line(1240,y+8,1240,y+66,BORDER)
    dot(1240,y+6,col,3)
    text(1254,y+9,time,10,DIM);text(1254,y+30,title,12,TEXT,500);text(1254,y+49,desc,10,MUTED)
text(1214,1027,'実行中は30秒ごとに状態を確認',10,DIM)
line(252,1047,1560,1047)
text(252,1068,'DESIGN CONCEPT  /  01',9,DIM,spacing=1.4)
text(1560,1068,'GURUMOJI  ·  A100 WORKSPACE',9,DIM,anchor='end',spacing=1.4)

svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans JP, Yu Gothic UI, Meiryo, sans-serif">'+''.join(parts)+'</svg>'
(OUT/'a100-workspace-target.svg').write_text(svg,encoding='utf-8')
(OUT/'preview.html').write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><title>A100 実行ワークスペース — 目標デザイン</title><style>html,body{margin:0;width:1600px;height:1080px;overflow:hidden;background:#080F1B}svg{display:block}</style>'+svg+'</html>',encoding='utf-8')
print(OUT/'a100-workspace-target.svg')
