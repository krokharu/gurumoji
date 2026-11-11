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
sys.path.insert(0,str(root/'src'))
from functools import partial
from gurumoji.runtime_state import RuntimeState
from gurumoji.services.transcription.job_record import JobRecord
from gurumoji.services.transcription_reporting import TranscriptionReporter

def record(identity):
    live=JobRecord(identity,'合成音声.wav',Path('/synthetic/output'),False,True)
    live.status='running'
    runtime=RuntimeState()
    JobRecord.state_lock=runtime.jobs_lock
    return live,TranscriptionReporter(live,partial(runtime.update_job,max_log_lines=50),runtime.jobs_lock,lambda x:x,lambda x,y:y)
live,reporter=record('motion-job')
def stage(key,label,value,overall=25):
    reporter.stage(key,label,value);live.progress=overall;live.message=label+('が完了しました。' if value>=100 else 'を進めています…');state['job']=live.public()
stage('environment','処理環境の確認',5,2)

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport=dict(width=1360,height=1000),reduced_motion='no-preference')
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
    page.goto('https://gurumoji.invalid/#/running')
    page.wait_for_function("configLoadState==='loaded' && jobRunning")
    motion=page.locator('#progress-motion')
    def wait_scene(scene):
        page.wait_for_function('(scene)=>document.querySelector("#progress-motion").dataset.scene===scene',arg=scene)
        page.wait_for_function("['loop','settled','waiting'].includes(document.querySelector('#progress-motion').dataset.cycle)")
    def playing():return motion.evaluate("el=>el.getAnimations({subtree:true}).filter(a=>a.playState==='running').length")
    def screenshot(name):
        page.evaluate('scrollTo(0,0)');page.wait_for_timeout(100)
        page.screenshot(path=str(args.output/name),full_page=True)
    wait_scene('prepare');assert playing()>0
    stage('preprocess','音声の前処理',25,5);wait_scene('audio');assert playing()>0
    assert page.locator('.progress-journey-step.is-pending').count()==1
    stage('preprocess','音声の前処理',100,7);wait_scene('complete');assert playing()==0
    stage('environment','処理環境の確認',100,8)
    stage('transcription','文字起こし',25,24);wait_scene('transcribe');assert playing()>0
    expect(page.locator('.progress-journey-step.is-completed')).to_have_count(2)
    page.evaluate("window.motionBefore=document.querySelector('#progress-motion svg');window.motionTime=document.querySelector('#progress-motion').getAnimations({subtree:true})[0].currentTime")
    stage('transcription','文字起こし',55,38)
    page.wait_for_function("document.querySelector('#progress-stage-number').textContent==='55%'")
    assert page.evaluate("window.motionBefore===document.querySelector('#progress-motion svg')")
    assert motion.evaluate('el=>el.getAnimations({subtree:true})[0].currentTime')>page.evaluate('window.motionTime')
    stage('transcription','文字起こし',100,52)
    stage('alignment','発話時刻の補正',35,57);wait_scene('align');assert playing()>0
    stage('alignment','発話時刻の補正',100,64)
    stage('diarization','話者の分離',42,72);wait_scene('speakers');assert playing()>0
    for width in [1360,390]:
        page.set_viewport_size(dict(width=width,height=1000))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        screenshot(f'active-speakers-{width}.png')
    stage('diarization','話者の分離',100,80)
    stage('finishing','文字起こしの仕上げ',38,84);wait_scene('edit');assert playing()>0
    stage('finishing','文字起こしの仕上げ',100,88)
    stage('output','結果ファイルの保存',45,98);wait_scene('save');assert playing()>0
    stage('output','結果ファイルの保存',100,99);wait_scene('complete');assert playing()==0
    live.status='completed';stage('completed','処理完了',100,100)
    page.wait_for_function("document.querySelector('#progress-card').dataset.outcome==='completed' && !jobRunning")
    wait_scene('complete')
    expect(page.locator('#running-view')).to_be_visible()
    expect(page.locator('#progress-open-result')).to_be_visible()
    expect(page.locator('.progress-journey-step.is-completed')).to_have_count(7)
    expect(page.locator('.progress-journey-step.is-running')).to_have_count(0)
    expect(page.locator('.running-queue-state.is-done')).to_contain_text('✓ 完了')
    assert playing()==0
    for width in [1360,390]:
        page.set_viewport_size(dict(width=width,height=1000));screenshot(f'completed-{width}.png')
    page.locator('#progress-open-result').click();expect(page.locator('#result-card')).to_be_visible()
    live,reporter=record('failed-motion')
    stage('transcription','文字起こし',100,52);stage('diarization','話者の分離',20,68)
    live.status='failed';stage('failed','エラー',20,68)
    page.evaluate('(job)=>{resumeJob(job);showProgressCard({open:true})}',state['job'])
    expect(page.locator('.progress-journey-step.is-failed')).to_have_count(1)
    expect(page.locator('.progress-journey-step.is-completed')).to_have_count(1)
    assert motion.get_attribute('data-state')=='failed' and playing()==0
    live,reporter=record('cancelled-motion')
    stage('transcription','文字起こし',20,30);live.status='cancelled';stage('cancelled','処理を中止',20,30)
    page.evaluate('(job)=>{resumeJob(job);showProgressCard({open:true})}',state['job'])
    assert motion.get_attribute('data-state')=='cancelled' and playing()==0
    page.emulate_media(reduced_motion='reduce')
    live,reporter=record('reduced-motion');stage('transcription','文字起こし',20,30)
    page.evaluate('(job)=>{resumeJob(job);showProgressCard({open:true})}',state['job'])
    wait_scene('transcribe');assert playing()==0
    expect(page.locator('.progress-journey-step.is-running')).to_have_count(1)
    assert not errors,errors
    assert not external,external
    browser.close()
result=dict(result='passed',scope='工程別7種の動き・継続更新・サーバー履歴・完了チェック・完了画面と結果ボタン・失敗中止停止・動きを減らす設定',viewports=[1360,390],page_errors=errors,external_requests=external,backend='工程記録は実コード、推論/APIは合成応答')
(args.output/'animation-browser-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
