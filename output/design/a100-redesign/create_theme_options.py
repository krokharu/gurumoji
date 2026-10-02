from pathlib import Path
import re

out = Path(__file__).resolve().parent
source = (out / 'a100-workspace-target.svg').read_text(encoding='utf-8')
keys = ['#080F1B','#101C2C','#152337','#243348','#F1F5FA','#A0AEC1','#718399','#63DAEB','#63D7AC','#E8BB71','#0D1725','#143540','#173142','#254352','#111F30','#173443','#16352F','#352D23']
themes = [
    ('light', '01', '白・ライトグレー', 'すっきりとした、明るいワークスペース', ['#F6F7F9','#FFFFFF','#F0F2F5','#DFE3EA','#202630','#5D6878','#687586','#4564D7','#267556','#91641A','#FFFFFF','#E9EDFC','#EAF0FF','#DCE4FB','#F5F7FB','#EBEFFE','#E7F3EC','#FBF2E3']),
    ('warm', '02', 'アイボリー・セージ', '柔らかく、長時間でも落ち着く雰囲気', ['#F6F4EF','#FFFDF9','#F0EDE5','#E0DBD0','#333B33','#626D60','#74776C','#526E55','#427254','#96703E','#EEEEE5','#DFE6D9','#DFE6D9','#CFDCC8','#E8EADF','#E7EDE1','#E6EEE3','#F2EADB']),
    ('mono', '03', 'モノトーン', '色を抑えた、シャープで静かな画面', ['#FAFAFA','#FFFFFF','#F1F1F1','#DEDEDE','#222222','#666666','#737373','#303030','#4F6657','#7B6850','#F2F2F2','#E6E6E6','#E3E3E3','#D5D5D5','#E9E9E9','#E9E9E9','#EBEFEB','#F0EDE7']),
]
cards=[]
for name, number, title, subtitle, values in themes:
    colors=dict(zip(keys,values))
    svg=re.sub(r'#[0-9A-Fa-f]{6}', lambda m: colors.get(m.group().upper(),m.group()),source)
    svg=svg.replace('DESIGN CONCEPT  /  01', f'THEME STUDY  /  {number}')
    (out/f'a100-theme-{name}.svg').write_text(svg,encoding='utf-8')
    (out/f'a100-theme-{name}.html').write_text(f'<!doctype html><html lang="ja"><meta charset="utf-8"><style>html,body{{margin:0;width:1600px;height:1080px;overflow:hidden}}svg{{display:block}}</style>{svg}</html>',encoding='utf-8')
    cards.append(f'<section><div class="number">{number}</div><h2>{title}</h2><p>{subtitle}</p><div class="screen">{svg}</div></section>')
html='''<!doctype html><html lang="ja"><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{margin:0;width:1800px;height:680px;overflow:hidden;background:#ECEDEE;color:#25282D;font-family:"Yu Gothic UI",Meiryo,sans-serif}body{padding:42px}header{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:34px}h1{font-size:25px;margin:0;font-weight:650}header span{font-size:13px;color:#686D75}.options{display:flex;gap:24px}section{width:556px}.number{font-size:12px;color:#71777F;letter-spacing:2px}h2{font-size:22px;margin:8px 0}p{font-size:13px;color:#626970;margin:0 0 23px}.screen{border-radius:10px;overflow:hidden;border:1px solid #D4D7DC;box-shadow:0 12px 30px #19202C0C}.screen svg{display:block;width:554px;height:374px}footer{margin-top:25px;font-size:12px;color:#6D747C}
</style><header><h1>A100 ワークスペース — テーマ比較</h1><span>同じ画面構成で、配色と雰囲気を比較</span></header><main class="options">'''+''.join(cards)+'''</main><footer>表示値はサンプルです。各案の原寸画像・SVGも用意しています。</footer></html>'''
(out/'theme-comparison.html').write_text(html,encoding='utf-8')
print('Created three SVG theme options and comparison HTML')
