"""削除済みモジュールへの依存と公開版の実ワーカー・保存経路を検証する。"""
import ast
import copy
from dataclasses import replace
import importlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import uuid
import wave

import pytest
from test_analysis_removal import ROOT, core, create, save


MODULES=sorted('.'.join(p.relative_to(ROOT/'src').with_suffix('').parts)
               for p in (ROOT/'src/gurumoji').rglob('*.py') if p.name!='__init__.py')

@pytest.mark.parametrize('module',MODULES)
def test_import_remaining_module(module):
    importlib.import_module(module)


def test_no_imports_of_deleted_modules():
    paths=subprocess.check_output(['git','diff','--name-only','--diff-filter=D','8f0fc49', 'HEAD'],cwd=ROOT,text=True).splitlines()
    deleted={p[4:-3].replace('/','.') for p in paths if p.startswith('src/') and p.endswith('.py')}
    errors=[]
    for p in (ROOT/'src').rglob('*.py'):
        current=p.relative_to(ROOT/'src').with_suffix('').parts
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            if isinstance(n,ast.ImportFrom):
                base=list(current[:-n.level]) if n.level else []
                module='.'.join(base+((n.module or '').split('.') if n.module else []))
                if module in deleted or any(module+'.'+a.name in deleted for a in n.names):
                    errors.append((str(p.relative_to(ROOT)),n.lineno,module))
    assert not errors,errors


def install_model_doubles(core,monkeypatch,*,gpu=False,failure=None):
    """モデルと外部通信だけを置き換え、ワーカー・DB・ファイル保存は実装を使う。"""
    calls=[]
    source=[{'start':0.,'end':1.,'text':'確認用の発話です。','speaker':'SPEAKER_00'},
            {'start':1.,'end':2.,'text':'明日までに資料を作成します。','speaker':'SPEAKER_01'}]
    class Model:
        def transcribe(self,*args,**kwargs):
            if failure=='asr':raise RuntimeError('test-asr-failure')
            return {'language':'ja','segments':copy.deepcopy(source)}
    def load(name):
        def run(*args,**kwargs):calls.append(name);return Model()
        return run
    torch=ModuleType('torch')
    torch.cuda=SimpleNamespace(is_available=lambda:gpu,empty_cache=lambda:None,
        get_device_name=lambda _: 'test-gpu',get_device_capability=lambda _: (8,0),
        get_device_properties=lambda _:SimpleNamespace(total_memory=8*1024**3))
    whisper=ModuleType('whisper');whisper.load_model=load('whisper')
    whisperx=ModuleType('whisperx');whisperx.__path__=[]
    whisperx.load_model=load('whisperx')
    whisperx.load_audio=lambda *_:[0.]*32000
    whisperx.load_align_model=lambda **_:(object(),{})
    def align(segments,*args,**kwargs):
        if failure=='alignment':raise RuntimeError('test-alignment-failure')
        return {'language':'ja','segments':copy.deepcopy(segments)}
    whisperx.align=align
    whisperx.assign_word_speakers=lambda _diarization,result,**_:result
    class Diarization:
        def __call__(self,*args,**kwargs):
            if failure=='diarization':raise RuntimeError('test-diarization-failure')
            return []
    diarize=ModuleType('whisperx.diarize');diarize.DiarizationPipeline=Diarization
    for name,module in [('torch',torch),('whisper',whisper),('whisperx',whisperx),('whisperx.diarize',diarize)]:
        monkeypatch.setitem(sys.modules,name,module)
    monkeypatch.setattr(core,'configure_huggingface_hub_compatibility',lambda:None)
    monkeypatch.setattr(core,'configure_speechbrain_lazy_import_compatibility',lambda:None)
    monkeypatch.setattr(core,'create_diarization_pipeline',lambda cls,*_:cls())
    monkeypatch.setattr(core,'session_profile_from_media',lambda *_:{})
    runner=importlib.import_module('gurumoji.services.transcription.job_runner')
    original_which=runner.shutil.which
    monkeypatch.setattr(runner.shutil,'which',lambda name: 'test-ffmpeg' if name=='ffmpeg' else original_which(name))
    outline={'overall_summary':'確認用の概要','sections':[{'title':'確認事項','start':0.,'end':2.,'bullets':['資料を作成する。']}]}
    def make_outline(*args,**kwargs):
        if failure=='outline':raise RuntimeError('test-outline-failure')
        return copy.deepcopy(outline)
    monkeypatch.setattr(core,'create_outline_with_ai',make_outline)
    monkeypatch.setattr(core,'detect_speaker_names_with_ai',lambda *args,**kwargs:{'SPEAKER_00':'確認話者'})
    monkeypatch.setattr(core,'clean_segments_with_ai',lambda rows,*args,**kwargs:copy.deepcopy(rows))
    monkeypatch.setattr(core,'review_segments_with_jev',lambda *args,**kwargs:({},{}))
    monkeypatch.setattr(core,'clean_recommended_segments_with_ai',lambda rows,*args,**kwargs:copy.deepcopy(rows))
    monkeypatch.setattr(core,'unify_notation',lambda rows,*args,**kwargs:{'segments':copy.deepcopy(rows),'notation':{'groups':[]}})
    return calls


def make_job(core,tmp_path,**changes):
    from gurumoji.services.transcription.options import JobOptions
    from gurumoji.services.transcription.job_record import JobRecord
    source=tmp_path/'generated.wav'
    with wave.open(str(source),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0'*64000)
    identity=uuid.uuid4().hex;work=core.UPLOAD_DIRECTORY/identity;work.mkdir(parents=True)
    output=core.DEFAULT_OUTPUT_DIRECTORY/identity
    job=JobRecord(id=identity,source_name='削除後の処理確認',output_dir=output,write_srt=True,write_json=True)
    options=JobOptions(input_path=source,work_dir=work,source_name=job.source_name,output_dir=output,
        model_name='tiny',language='ja',hf_token='',audio_preprocess='none',min_speakers=None,max_speakers=None,
        device='cpu',diarization_device='cpu',triple_pass=False,boost_quiet_speech=False,
        vad_onset=.5,vad_offset=.3,no_speech_threshold=.6,write_srt=True,write_json=True,burn_subtitled_video=False,
        ai_provider='none',clean_transcript=False,detect_speaker_names=False,create_outline=False,
        owns_output_dir=True,transcript_finishing_mode='off')
    options=replace(options,**changes);core.jobs[job.id]=job
    return job,options


@pytest.mark.parametrize('scenario', ['cpu','gpu','triple','outline_names','recommended','full_cleanup','notation','meeting'])
def test_actual_worker_to_persisted_outputs(core,monkeypatch,tmp_path,scenario):
    calls=install_model_doubles(core,monkeypatch,gpu=scenario=='gpu')
    changes={}
    if scenario=='gpu':changes.update(device='cuda',diarization_device='cuda')
    if scenario=='triple':changes['triple_pass']=True
    if scenario=='outline_names':changes.update(ai_provider='openai',create_outline=True,detect_speaker_names=True)
    if scenario=='recommended':changes.update(ai_provider='openai',recommended_cleanup=True)
    if scenario=='full_cleanup':changes.update(ai_provider='openai',clean_transcript=True)
    if scenario=='notation':changes.update(ai_provider='openai',ai_efforts={'cleanup':'off','notation':'medium'})
    if scenario=='meeting':changes.update(conversation_mode='meeting',generate_meeting_minutes=True)
    job,options=make_job(core,tmp_path,**changes)
    core.run_transcription_job(job,options)
    assert job.status=='completed',(job.error,job.logs[-4:])
    assert job.progress==100 and len(job.segments)==2
    assert calls[0]==('whisperx' if scenario=='gpu' else 'whisper')
    row=core.library_row(job.id);assert row is not None
    assert json.loads(row['segments_json'])[0]['text']=='確認用の発話です。'
    assert job.media_path.is_file() and options.input_path.is_file()
    assert {p.suffix for p in job.files}>={'.json','.txt','.srt'}
    assert all(p.is_file() for p in job.files)
    assert not options.work_dir.exists()
    assert not any(word in job.error for word in ('NameError','ModuleNotFoundError','AttributeError'))
    if scenario=='outline_names':assert job.outline and job.speaker_names
    if scenario=='meeting':assert job.meeting_minutes


@pytest.mark.parametrize('failure,expected',[('asr','failed'),('diarization','failed'),('alignment','completed'),('outline','completed'),('cancel','cancelled')])
def test_worker_failures_preserve_source(core,monkeypatch,tmp_path,failure,expected):
    install_model_doubles(core,monkeypatch,failure=failure)
    job,options=make_job(core,tmp_path,create_outline=failure=='outline')
    if failure=='cancel':job.cancel_event.set()
    core.run_transcription_job(job,options)
    assert job.status==expected,(job.error,job.logs[-4:])
    assert options.input_path.is_file()
    assert not options.work_dir.exists()
    assert ('test-'+failure+'-failure' in job.error) if expected=='failed' else not job.error or expected=='cancelled'
    if expected!='completed':assert core.library_row(job.id) is None


@pytest.mark.parametrize('kind',['tags','data-groups'])
def test_catalog_membership_without_analysis_tables(core,kind):
    c,row=create(core)
    r=c.post('/api/library/'+kind,json={'name':'検証用','kind':'manual'});assert r.status_code==201,r.get_json()
    identity=r.get_json()['tag_id' if kind=='tags' else 'group_id']
    for remove in (False,True):
        r=c.put(f'/api/library/{kind}/{identity}/members',json={'item_ids':[row['id']],'remove':remove})
        assert r.status_code==200,r.get_json()
    assert c.delete(f'/api/library/{kind}/{identity}').status_code==200


def test_outline_rerun_after_deletion(core,monkeypatch):
    c,row=create(core);r=save(c,row);assert r.status_code==200
    row=r.get_json()
    from gurumoji.services.ai.settings import TokenConfig
    monkeypatch.setattr(core,'load_token_config',lambda *args,**kwargs:TokenConfig(openai_api_key='test-placeholder'))
    monkeypatch.setattr(core,'create_outline_with_ai',lambda *args,**kwargs:{'sections':[{'title':'確認用','start':0,'end':1.5}]})
    r=c.post(f"/api/library/{row['id']}/outline",json={'provider':'openai','revision_count':row['revision_count']})
    assert r.status_code==200,r.get_json()
    assert r.get_json()['segments']==row['segments']


def test_notation_roundtrip_without_analysis_engine(core):
    c,row=create(core);r=save(c,row);assert r.status_code==200
    r=c.get(f"/api/library/{row['id']}/notation/preview?provider=none")
    assert r.status_code==200,r.get_json()
