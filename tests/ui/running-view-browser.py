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
                posts.append(path);state['job']=job();data=state['job']
            elif path=='/api/jobs/active':data={'job':state['job']}
            elif path.startswith('/api/jobs/'):
                data=state['job'] or {}; 
            elif path=='/api/speakers':data=dict(speakers=[],registry_revision=0)
            elif path=='/api/custom-vocabulary':data={'terms':[]}
            elif path=='/api/training':data=dict(event_count=0,ready_count=0)
            elif path=='/api/library':data=dict(items=[],pagination=dict(offset=0,limit=50,total=0,has_more=False))
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
    page.locator('#stitch-run-button').click()
    page.wait_for_function("document.body.dataset.view==='running' && activeJobId==='browser-job'")
    expect(page.locator('#create-view')).to_be_hidden();expect(page.locator('#running-view')).to_be_visible()
    page.locator('#running-view [data-job-home]').first.click()
    expect(page.locator('#job-form')).to_be_visible();expect(page.locator('#running-view')).to_be_hidden()
    expect(page.locator('#job-resume-notice')).to_be_visible();expect(page.locator('#start-button')).to_be_disabled()
    state['job']['progress']=56
    page.wait_for_function("document.querySelector('#progress-number').textContent==='56%'")
    assert page.evaluate('document.body.dataset.view')=='new'
    page.locator('[data-open-job]').click();expect(page.locator('#running-view')).to_be_visible()
    page.locator('.app-brand').click();expect(page.locator('#create-view')).to_be_visible()
    page.locator('#job-chip').click();expect(page.locator('#running-view')).to_be_visible()
    for width in [1360,390]:
        page.set_viewport_size(dict(width=width,height=1000))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(args.output/f'running-{width}.png'),full_page=True)
        page.locator('#running-view [data-job-home]').first.click()
        expect(page.locator('#job-resume-notice')).to_be_visible()
        page.screenshot(path=str(args.output/f'home-active-{width}.png'),full_page=True)
        page.locator('[data-open-job]').click()
    page.locator('#running-view [data-job-home]').first.click()
    state['job']=job(status='completed',progress=100)
    page.wait_for_function('!jobRunning && completedJob?.id==="browser-job"')
    assert page.evaluate('document.body.dataset.view')=='new'
    page.locator('#job-chip').click();expect(page.locator('#result-card')).to_be_visible()
    page.set_viewport_size(dict(width=1360,height=1000))
    state['job']=job('restored-job')
    page.evaluate("sessionStorage.setItem('gurumoji.activeJobId','restored-job');showView('new')")
    page.reload();page.wait_for_function("jobRunning && activeJobId==='restored-job'")
    assert page.evaluate('document.body.dataset.view')=='new'
    page.locator('#job-chip').click();expect(page.locator('#running-view')).to_be_visible()
    page.reload();page.wait_for_function("jobRunning && activeJobId==='restored-job'")
    assert page.evaluate('document.body.dataset.view')=='running'
    state['job']=job('restored-job','failed')
    page.wait_for_function('!jobRunning')
    expect(page.locator('#progress-dismiss')).to_be_visible()
    page.locator('#progress-dismiss').click();expect(page.locator('#create-view')).to_be_visible()
    expect(page.locator('#job-chip')).to_be_hidden()
    state['job']=None
    page.evaluate("sessionStorage.removeItem('gurumoji.activeJobId');showView('running')")
    page.reload();page.wait_for_function('!jobRunning')
    expect(page.locator('#job-empty-state')).to_be_visible()
    assert len(posts)==1,posts
    assert not errors,errors
    assert not external,external
    browser.close()
result=dict(result='passed',scope='開始・ホーム復帰・進捗更新・ロゴ/通知からの復帰・背景完了・再読込・失敗・空状態',viewports=[1360,390],post_count=len(posts),page_errors=errors,external_requests=external,backend='合成応答のみ')
(args.output/'browser-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
