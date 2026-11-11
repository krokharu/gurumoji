"""実APIや実データを使わず、出荷コード全体の実行状況画面をEdgeで操作する。"""
import argparse
import io
import json
import subprocess
import sys
import wave
from pathlib import Path
from urllib.parse import unquote, urlparse
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.source_root.resolve();args.output.mkdir(parents=True,exist_ok=True)
fixture=Path(__file__).resolve().parents[1]/'dom/render_fixture.py'
html=subprocess.check_output([sys.executable,str(fixture),str(root)],encoding='utf-8')
static=root/'src/gurumoji/static'
state={'job':None};errors=[];posts=[];external=[]
def job(job_id='browser-job',status='running',progress=37):
    return dict(id=job_id,status=status,progress=progress,source_name='合成音声.wav',revision_count=1,files=[],segments=[dict(id='s1',speaker='A',start=0,end=1,text='合成発話')],speaker_profiles={},speaker_names={},session_profile={})
models={name:dict(status='cached',message=name+' / CPU: 合成モデル準備済み') for name in ['tiny','base','small','medium','large-v1','large-v2','large-v3','turbo']}
config=dict(ok=True,huggingface=True,runtime=dict(browser_upload=True),transcription_readiness=dict(whisperx=dict(blockers=[],notes=[],models=dict(cpu=models,cuda=models))))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport=dict(width=1360,height=1000),reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1');")
    page.on('pageerror',lambda e:errors.append(str(e)))
    def route(req):
        parsed=urlparse(req.request.url);path=unquote(parsed.path)
        if parsed.hostname!='gurumoji.invalid':external.append(req.request.url);req.abort();return
        if path=='/':req.fulfill(body=html,content_type='text/html');return
        if path.startswith('/static/'):
            file=(static/path.removeprefix('/static/')).resolve()
            if static in file.parents and file.is_file():req.fulfill(path=str(file));return
            req.fulfill(status=404,body='');return
        if path.startswith('/api/'):
            data={}
            if path=='/api/config':data=config
            elif path=='/api/jobs' and req.request.method=='POST':
                posts.append(path)
                if state.pop('reject_next',False):req.fulfill(status=400,json={'error':'合成の受付拒否'});return
                state['job']=job('queue-'+str(len(posts)));data=state['job']
                if state.pop('hold_next',False):state['held_route']=req;return
            elif path=='/api/jobs/active':data={'job':state['job']}
            elif path.endswith('/cancel'):
                state['job']['status']='cancelled';data=state['job']
            elif path.startswith('/api/jobs/'):
                data=state['job'] or {}; 
            elif path=='/api/speakers':data=dict(speakers=[],registry_revision=0)
            elif path=='/api/custom-vocabulary':data={'terms':[]}
            elif path=='/api/training':data=dict(event_count=0,ready_count=0)
            elif path=='/api/library':data=dict(items=[],groups=[],pagination=dict(offset=0,limit=50,total=0,has_more=False))
            elif path=='/api/library/groups':data={'id':'synthetic-group'}
            elif path=='/api/obsidian/obussql':data=dict(available=False,status='disabled')
            req.fulfill(json=data);return
        req.abort()
    page.route('**/*',route)
    page.goto('https://gurumoji.invalid/#/new')
    page.wait_for_function("configLoadState==='loaded' && !jobRunning")
    wav=io.BytesIO()
    with wave.open(wav,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\x00\x00'*1600)
    page.locator('#input-file').set_input_files(dict(name='合成音声.wav',mimeType='audio/wav',buffer=wav.getvalue()))
    page.wait_for_function('createReadiness().ready')
    state['hold_next']=True
    page.locator('#stitch-run-button').click()
    page.wait_for_function("jobRunning && lastProgressJob?.status==='admitting'")
    original=page.locator('#input-file').evaluate('(el)=>el.files[0].name')
    fixtures=args.output/'fixtures';fixtures.mkdir(exist_ok=True)
    files={}
    for name in ['B','C','D','E','F']:
        file=fixtures/(name+'.wav');file.write_bytes(wav.getvalue());files[name]=str(file)
    def add(names):
        with page.expect_file_chooser() as chooser:
            page.locator('#running-queue-add').click()
        chooser.value.set_files([files[name] for name in names])
    def rows(status):return page.locator('#running-queue-list > li.is-'+status)
    def wait_jobs(count):page.wait_for_function('(n)=>jobRunning && activeJobId==="queue-"+n',arg=count)
    expect(rows('running')).to_have_count(1)
    expect(rows('running').locator('button')).to_be_disabled()
    add(['B','C']);expect(rows('ready')).to_have_count(2)
    page.locator('#running-queue-clear').click();expect(rows('ready')).to_have_count(0)
    expect(rows('running')).to_have_count(1)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')==original
    state.pop('held_route').fulfill(json=state['job'])
    wait_jobs(1)
    add(['B','C','D'])
    expect(rows('ready')).to_have_count(3);expect(rows('running')).to_have_count(1)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')==original
    assert len(posts)==1
    page.get_by_role('button',name='B.wavの登録を解除',exact=True).focus()
    state['job']['progress']=49
    page.wait_for_function("document.querySelector('#progress-number').textContent==='49%'")
    assert page.evaluate("document.activeElement.getAttribute('aria-label')")=='B.wavの登録を解除'
    page.get_by_role('button',name='C.wavの登録を解除',exact=True).click()
    expect(rows('ready')).to_have_count(2)
    page.locator('#running-queue-toggle').click()
    add(['E']);expect(rows('ready')).to_have_count(3)
    expect(page.locator('#running-queue-summary')).to_contain_text('停止中')
    for width in [1360,390]:
        page.set_viewport_size(dict(width=width,height=1000))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate('scrollTo(0,0)')
        page.wait_for_timeout(100)
        page.screenshot(path=str(args.output/f'queue-{width}.png'),full_page=True)
    state['job']=job('queue-1','completed',100)
    page.wait_for_function('!jobRunning')
    page.wait_for_timeout(700);assert len(posts)==1
    page.locator('#job-chip').click();expect(page.locator('#running-view')).to_be_visible()
    page.locator('#running-queue-toggle').click();wait_jobs(2)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')=='B.wav'
    page.locator('#running-queue-clear').click();expect(rows('ready')).to_have_count(0)
    add(['C','D']);expect(rows('ready')).to_have_count(2)
    state['job']=job('queue-2','completed',100)
    wait_jobs(3)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')=='C.wav'
    state['job']=job('queue-3','failed')
    page.wait_for_function('!jobRunning');page.wait_for_timeout(700)
    assert len(posts)==3
    expect(rows('ready')).to_have_count(1)
    expect(page.locator('#running-queue-summary')).to_contain_text('停止中')
    page.locator('#running-queue-toggle').click();wait_jobs(4)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')=='D.wav'
    add(['E']);expect(rows('ready')).to_have_count(1)
    page.on('dialog',lambda dialog:dialog.accept())
    page.locator('#cancel-button').click()
    page.wait_for_function('!jobRunning');page.wait_for_timeout(700)
    assert len(posts)==4
    expect(rows('ready')).to_have_count(1)
    page.locator('#running-queue-toggle').click();wait_jobs(5)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')=='E.wav'
    page.locator('#running-view [data-job-home]').first.click()
    state['job']=job('queue-5','completed',100)
    page.wait_for_function('!jobRunning')
    assert page.evaluate('document.body.dataset.view')=='new'
    page.locator('#job-chip').click();expect(page.locator('#result-card')).to_be_visible()
    page.evaluate("showView('running')")
    # 再読み込みで復元したジョブには元のFileがなくても待機を追加できる。
    state['job']=job('external-job')
    page.evaluate("sessionStorage.setItem('gurumoji.activeJobId','external-job')")
    page.reload();page.wait_for_function("jobRunning && activeJobId==='external-job'")
    assert page.locator('#input-file').evaluate('el=>el.files.length')==0
    add(['B','C']);expect(rows('ready')).to_have_count(2);expect(rows('running')).to_have_count(1)
    state['reject_next']=True
    state['job']=job('external-job','completed',100)
    page.wait_for_function('!jobRunning && queuedJobCount===2')
    page.wait_for_function("document.querySelector('#running-queue-message').textContent.includes('合成の受付拒否')")
    assert len(posts)==6
    expect(rows('ready')).to_have_count(2)
    page.locator('#job-chip').click();expect(page.locator('#running-view')).to_be_visible()
    page.locator('#running-queue-toggle').click();wait_jobs(7)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')=='B.wav'
    state['job']=job('queue-7','completed',100)
    wait_jobs(8)
    assert page.locator('#input-file').evaluate('(el)=>el.files[0].name')=='C.wav'
    page.locator('#running-view [data-job-home]').first.click()
    state['job']=job('queue-8','completed',100)
    page.wait_for_function('!jobRunning')
    assert page.evaluate('document.body.dataset.view')=='new'
    page.locator('#job-chip').click();expect(page.locator('#result-card')).to_be_visible()
    page.evaluate("showView('running')")
    many=[]
    for index in range(35):
        file=fixtures/f'limit-{index}.wav';file.write_bytes(wav.getvalue());many.append(str(file))
    invalid=fixtures/'invalid.txt';invalid.write_text('合成の非対応ファイル',encoding='utf-8')
    with page.expect_file_chooser() as chooser:page.locator('#running-queue-add').click()
    chooser.value.set_files(many+[str(invalid),many[0]])
    expect(page.locator('#running-queue-list > li')).to_have_count(30)
    expect(page.locator('#running-queue-message')).to_contain_text('最大30件')
    expect(page.locator('#running-queue-message')).to_contain_text('重複')
    expect(page.locator('#running-queue-message')).to_contain_text('対応していない1件')
    assert len(posts)==8
    page.locator('#running-queue-clear').click()
    expect(rows('ready')).to_have_count(0)
    assert page.locator('#input-file').evaluate('el=>el.files.length')==0
    assert not errors,errors
    assert not external,external
    browser.close()
result=dict(result='passed',scope='受付待ちの保護・復元ジョブへの追加・受付拒否からの再開・実行中の複数追加・実行ファイル保護・個別解除・一時停止・再開・順次実行・待機一括解除・失敗/中止停止・ホーム維持・上限/重複/拡張子',viewports=[1360,390],job_posts=len(posts),page_errors=errors,external_requests=external,backend='合成応答のみ')
(args.output/'queue-browser-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
