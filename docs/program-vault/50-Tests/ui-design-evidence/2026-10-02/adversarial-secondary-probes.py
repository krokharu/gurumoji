"""Independent color math and source-extracted SQLite read probes; no application import."""
import ast
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]/'app'

def rgb(code):
    return tuple(int(code.lstrip('#')[i:i+2],16) for i in (0,2,4))
def luminance(color):
    s=[v/255 for v in color]
    lin=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in s]
    return sum(x*w for x,w in zip(lin,(.2126,.7152,.0722)))
def ratio(fg,bg):
    a,b=sorted((luminance(fg),luminance(bg)))
    return (b+.05)/(a+.05)
def blend(fg,bg,alpha):
    return tuple(alpha*a+(1-alpha)*b for a,b in zip(fg,bg))
entries=[]
def check(label,fg,bg):
    value=ratio(rgb(fg),rgb(bg))
    entries.append(dict(label=label,foreground=fg,background=bg,ratio=value,normal_text_aa=value>=4.5,large_text_aa=value>=3))
for bg in ['#f2f8ec','#fafcf7']: check('drop-zone OLD base-rule pair (overridden in create form)', '#8a948f', bg)
check('drop-zone actual default background after all-width create-form overrides', '#8a948f','#ffffff')
for bg in ['#fffef9','#f8faf5','#f1f5ed']: check('orange on nominal card / actual registry overview endpoints', '#e87941', bg)
check('analysis side status, actual override', '#97451d','#f2f5ef')
check('solid field focus border on white', '#1c6b50','#ffffff')
check('qualitative matrix focus override on white', '#2975be','#ffffff')
for bg in ['#fffef9','#f4f5f0','#ffffff']:
    value=ratio(blend(rgb('#1c6b50'),rgb(bg),.35),rgb(bg))
    entries.append(dict(label='35%-green focus ring only',background=bg,ratio=value,non_text_aa=value>=3))
for alpha in [.95,.96]:
    values=[ratio(rgb('#e87941'),blend(rgb('#fffef9'),rgb(bg),alpha)) for bg in ['#000000','#ffffff']]
    entries.append(dict(label='orange on semi-transparent save bar, black/white backdrop bounds',alpha=alpha,ratio_bounds=values,all_below_normal_text_aa=max(values)<4.5))

source=(ROOT/'src/gurumoji/analysis_store.py').read_text()
klass=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='AnalysisStore')
methods=[n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name in {'list','list_comparisons','get'}]
ns={}; exec(compile(ast.Module(body=methods,type_ignores=[]),str(ROOT/'src/gurumoji/analysis_store.py'),'exec'),ns)
c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
c.execute('CREATE TABLE analysis_runs(id TEXT PRIMARY KEY,item_id TEXT,kind TEXT,created_at TEXT,status TEXT)')
for i in range(105):
    c.execute('INSERT INTO analysis_runs VALUES(?,?,?,?,?)',(f'synthetic_{i:03}', 'synthetic-only','interview_comparison',f'2026-01-01T00:{i//60:02}:{i%60:02}Z','completed'))
c.commit()
fake=SimpleNamespace(connect=lambda:c)
listed=ns['list'](fake,'synthetic-only'); comparisons=ns['list_comparisons'](fake)
old=ns['get'](fake,'synthetic_000')
assert len(listed)==len(comparisons)==100
assert listed[0]['id']=='synthetic_104' and listed[-1]['id']=='synthetic_005'
assert old['id']=='synthetic_000'
count=c.execute('SELECT COUNT(*) FROM analysis_runs').fetchone()[0]
assert count==105
c.close()
print(json.dumps({'method':'independent WCAG luminance math and AST-extracted original read methods on synthetic in-memory SQLite; no browser',
 'color_results':entries,'history':{'synthetic_rows':count,'list_count':len(listed),'comparison_count':len(comparisons),'newest_id':listed[0]['id'],'oldest_listed_id':listed[-1]['id'],'oldest_still_gettable_by_id':old['id'],'rows_deleted':0}},ensure_ascii=False,indent=2))
