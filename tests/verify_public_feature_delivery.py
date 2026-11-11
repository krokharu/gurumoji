"""公開候補の除外設定・再生成API・要約を合成データだけで検証する。"""
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
import ast,hashlib,importlib.util,json,os,sqlite3,subprocess,sys,tempfile,threading
from html.parser import HTMLParser

pub=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
sys.path.insert(0,str(pub/'src'))
checks=[]
with tempfile.TemporaryDirectory(prefix='gurumoji-public-contract-') as temporary:
    work=Path(temporary)
    for key,part in [('MOJIOKOSI_DATA_DIR','data'),('MOJIOKOSI_OUTPUT_DIR','output'),('MOJIOKOSI_BACKUP_DIR','backup')]:
        os.environ[key]=str(work/part)
    from gurumoji import app, ai_finishing
    from gurumoji.handlers.outline_rerun import make_library_outline_rerun, OutlineRerunError
    assert Path(app.__file__).is_relative_to(pub)
    assert app.OBSIDIAN_ENABLED is False
    application=app.create_app()
    assert not [r for r in application.url_map.iter_rules() if any(n in str(r) for n in ('obsidian','obussql'))]
    client=application.test_client()
    response=client.get('/')
    assert response.status_code==200
    class Assets(HTMLParser):
        def __init__(self): super().__init__(); self.paths=[]
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ('src','href') and value and value.startswith('/static/'):
                    self.paths.append(value)
    parser=Assets(); parser.feed(response.get_data(as_text=True))
    for path in parser.paths:
        assert (pub/'src/gurumoji'/path.lstrip('/')).is_file(),path
    checks.append({'application':'公開候補からimport、ホーム200、全静的参照が存在、除外ルートなし','assets':len(parser.paths)})
    for payload in ({'provider':'none','revision_count':0},{'provider':'openai','revision_count':True},{'provider':'openai','revision_count':'0'}):
        reply=client.post('/api/library/synthetic/outline',json=payload,headers={'X-Requested-With':'XMLHttpRequest'})
        assert reply.status_code==400,(reply.status_code,reply.get_json())
    checks.append({'api_validation':'無効なAI選択・真偽値や文字列の編集版を拒否'})
    db=sqlite3.connect(work/'synthetic.sqlite3'); db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE library_items(id TEXT PRIMARY KEY,revision_count INTEGER,outline_json TEXT,ai_usage_json TEXT,updated_at TEXT,speaker_names_json TEXT)')
    db.execute("INSERT INTO library_items VALUES('synthetic',1,'{}','{}','','{}')"); db.commit()
    @contextmanager
    def connection():
        with db: yield db
    def row(_id): return db.execute('SELECT * FROM library_items WHERE id=?',(_id,)).fetchone()
    outline={'summary':'合成データの要約','sections':[{'title':'議題','bullets':['合成の要点']}]}
    calls=[]
    def generate(*args): calls.append(True); return outline
    def make(call):
        return make_library_outline_rerun(configured_ai_credentials=lambda *a:('synthetic','synthetic-model'),create_outline_with_ai=call,
            database_connection=connection,library_public=lambda r:dict(r),library_row=row,library_write_lock=threading.RLock(),
            load_token_config=lambda:SimpleNamespace(lmstudio_base_url='http://127.0.0.1:1234/v1'),merge_ai_usage=lambda a,b:{**a,**b},
            public_diagnostic_text=lambda text,**kwargs:text,row_segments=lambda r:[{'id':'s1','text':'合成の発話','speaker':'A','start':0,'end':1}])
    run=make(generate)
    result=run('synthetic',provider='openai',expected_revision=1)
    assert json.loads(row('synthetic')['outline_json'])==outline
    assert result['outline_run']['section_count']==1
    checks.append({'outline_save':'選択したAIで生成し、編集版を保持してアウトラインを保存'})
    try: run('synthetic',provider='openai',expected_revision=0)
    except OutlineRerunError as error: assert error.status==409
    else: raise AssertionError('旧版を受理')
    assert len(calls)==1
    def edit_during_ai(*args):
        db.execute("UPDATE library_items SET revision_count=2,outline_json='{}' WHERE id='synthetic'"); db.commit(); return outline
    try: make(edit_during_ai)('synthetic',provider='openai',expected_revision=1)
    except OutlineRerunError as error: assert error.status==409
    else: raise AssertionError('競合を受理')
    assert row('synthetic')['outline_json']=='{}'
    checks.append({'outline_conflict':'開始前・AI実行中の本文更新を検出し、古い生成結果を書き込まない'})
    segments=[{'id':'s1','speaker':'A','start':0,'end':1,'text':'合成の発話'}]
    def ai(system,prompt,name,schema):
        if name=='meeting_overall_summary': return {'summary':'合成の要点を確認した。'}
        return {'sections':[{'title':'合成議題','bullets':[{'text':'合成の要点','segment_ids':['s1']}]}]}
    summary=ai_finishing.create_outline(segments,{},ai,lambda *a:None,lambda:None)
    assert summary['summary']=='合成の要点を確認した。'
    assert summary['sections'][0]['segment_ids']==['s1']
    assert 's1' not in summary['summary']
    try: ai_finishing.summarize_outline(summary['sections'],lambda *a:{'summary':''},lambda *a:None,lambda:None)
    except RuntimeError: pass
    else: raise AssertionError('空要約を受理')
    checks.append({'overall_summary':'根拠付き議題と全体要約を生成し、空のAI応答を拒否'})
    db.close()

# 公開範囲検査の既存規則を候補ファイルにも適用する。秘密値は表示しない。
spec=importlib.util.spec_from_file_location('boundary',pub/'.github/scripts/check_public_boundary.py')
boundary=importlib.util.module_from_spec(spec); spec.loader.exec_module(boundary)
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=pub).decode().split('\0')
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=pub).decode().split('\0')
errors=[]
for name in sorted(set(tracked+new)-{''}):
    p=pub/name
    assert not set(Path(name).parts)&boundary.FORBIDDEN_PARTS,name
    data=p.read_bytes()
    if b'\0' in data: continue
    text=data.decode('utf-8',errors='replace')
    for number,line in enumerate(text.splitlines(),1):
        for label,pattern in boundary.SECRET_PATTERNS.items():
            if pattern.search(line): errors.append(f'{label}:{name}:{number}')
    if p.suffix=='.py': ast.parse(text,filename=name)
assert not errors,errors
# 実行用の専門家・文献・スライド定義は一切変更していない。
for name in subprocess.check_output(['git','ls-files','docs/program-vault','config/analysis_slide_templates.json'],cwd=pub,text=True).splitlines():
    old=subprocess.check_output(['git','show','HEAD:'+name],cwd=pub)
    assert old==(pub/name).read_bytes(),name
checks.append({'public_boundary':'候補全ファイルの秘密値・個人パスなし、Python構文正常、実行用定義不変'})
result={'checks':checks,'passed':True,'isolation':'一時SQLite・合成発話・代替AIのみ。アプリサーバーや実モデル・実Vaultを起動しない。'}
(out/'candidate-contract.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
