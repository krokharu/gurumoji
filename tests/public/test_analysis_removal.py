"""公開版の解析削除を一時DBだけで検証する。公開リポジトリには含めない。"""
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(os.environ.get('GURUMOJI_APP_ROOT',Path(__file__).parent/'public-remove-analysis-20261103'))
sys.path.insert(0,str(ROOT/'src'))
import pytest
pytestmark=pytest.mark.skipif(not ROOT.is_dir(),reason='GURUMOJI_APP_ROOT に公開版の検証対象を指定する。')

def configure(root):
    a=importlib.import_module('gurumoji.app')
    a.DATA_DIRECTORY=root/'data';a.DATABASE_FILE=a.DATA_DIRECTORY/'library.sqlite3'
    a.MEDIA_DIRECTORY=a.DATA_DIRECTORY/'media';a.THUMBNAIL_DIRECTORY=a.DATA_DIRECTORY/'thumbnails'
    a.TRAINING_AUDIO_DIRECTORY=a.DATA_DIRECTORY/'kushinada_training/audio'
    a.TRAINING_DIRECTORY=a.DATA_DIRECTORY/'kushinada_training'
    a.TRAINING_JSONL_FILE=a.TRAINING_DIRECTORY/'corrections.jsonl';a.TRAINING_MANIFEST_FILE=a.TRAINING_DIRECTORY/'manifest.csv'
    a.CUSTOM_VOCABULARY_FILE=a.DATA_DIRECTORY/'custom_vocabulary.json'
    a.UPLOAD_DIRECTORY=root/'uploads';a.DEFAULT_OUTPUT_DIRECTORY=root/'output';a.BACKUP_DIRECTORY=root/'backups'
    a.TOKEN_FILE=root/'tokens-test.json'
    a.TOKEN_FILE.write_text('{}',encoding='utf-8')
    a.app.config['TESTING']=True
    return a

@pytest.fixture
def core(tmp_path):
    a=configure(tmp_path)
    a.initialize_library()
    a.jobs.clear()
    return a

def create(core):
    c=core.app.test_client();r=c.post('/api/library',json={'source_name':'保存確認'})
    assert r.status_code==201,r.get_json()
    return c,r.get_json()

def save(c,row,text='記録の保存を確認します。'):
    return c.put(f"/api/library/{row['id']}",json={
        'revision_count':row['revision_count'],
        'segments':[{'id':'segment-one','start':0.0,'end':1.5,'speaker':'SPEAKER_00','text':text}],
        'speaker_names':{'SPEAKER_00':'確認用話者'},
    })

def test_removed_api_and_assets(core):
    assert not [r.rule for r in core.app.url_map.iter_rules() if any(x in r.rule for x in ('/analysis','/orchestration','/interview-comparison','/obsidian','/research-'))]
    c=core.app.test_client()
    for url in ['/api/analysis/methods','/api/library/x/analysis','/static/ui/analysis.js','/static/analysis-orchestration.js']:
        assert c.get(url).status_code==404
    for url in ['/api/library/x/analysis/pipelines','/api/library/x/analysis/orchestration','/api/library/interview-comparison']:
        assert c.post(url,json={}).status_code in (404,405)
    response=c.get('/');assert response.status_code==200
    html=response.get_data(as_text=True)
    assert 'show-analysis-button' not in html
    assert 'panel-emotion' not in html
    assert 'speaker-survey-analysis' not in html
    for filename in core.app.jinja_env.globals['application_scripts']:
        assert c.get('/static/'+filename).status_code==200

def test_transcript_save_export_and_conflict(core):
    c,row=create(core);r=save(c,row)
    assert r.status_code==200,r.get_json()
    value=r.get_json();assert value['segments'][0]['text']=='記録の保存を確認します。'
    assert value['revision_count']==row['revision_count']+1
    assert save(c,row,'古い画面からの更新').status_code==409
    for url in [f"/api/library/{row['id']}",'/api/library',f"/api/library/{row['id']}/speakers.csv",f"/api/library/{row['id']}/preparation/export.json"]:
        assert c.get(url).status_code==200,url
    for f in value['files']:
        assert c.get(f['url']).status_code==200,f

def test_tag_group_and_speaker_save(core):
    c,row=create(core)
    r=c.post('/api/library/tags',json={'name':'確認タグ'})
    assert r.status_code==201,r.get_json()
    r=c.get('/api/speakers');assert r.status_code==200
    data=r.get_json()
    r=c.put('/api/speakers',json={'speakers':[], 'registry_revision':data['registry_revision']})
    assert r.status_code==200,r.get_json()
    assert c.get('/api/library/catalog').status_code==200

def test_delete_restore_backup(core,tmp_path):
    c,row=create(core);r=save(c,row);assert r.status_code==200,r.get_json()
    legacy=core.DATA_DIRECTORY/'analysis_store/runs/legacy/result.json'
    legacy.parent.mkdir(parents=True);legacy.write_bytes(b'{"saved":true}')
    note=core.DATA_DIRECTORY/'obsidian/ResearchVault/user.md'
    note.parent.mkdir(parents=True);note.write_text('本文とタグを保持',encoding='utf-8')
    r=c.post('/api/system/backup',json={});assert r.status_code==200,r.get_json()
    from gurumoji.services import data_backup
    backup=next(core.BACKUP_DIRECTORY.glob('gurumoji-backup-*'))
    assert data_backup.verify_backup(backup)==[]
    assert (backup/'data'/legacy.relative_to(core.DATA_DIRECTORY)).read_bytes()==legacy.read_bytes()
    assert (backup/'data'/note.relative_to(core.DATA_DIRECTORY)).read_bytes()==note.read_bytes()
    r=c.delete(f"/api/library/{row['id']}");assert r.status_code==200,r.get_json()
    entry=r.get_json()['trash_entry']
    assert c.get(f"/api/library/{row['id']}").status_code==404
    r=c.post(f'/api/library/trash/{entry}/restore',json={});assert r.status_code==200,r.get_json()
    assert c.get(f"/api/library/{row['id']}").get_json()['segments'][0]['text']=='記録の保存を確認します。'

def test_existing_database_columns_and_saved_results(tmp_path):
    import subprocess
    baseline=Path(os.environ.get('GURUMOJI_BASELINE_ROOT',ROOT.parent/'public-analysis-baseline-20261103'))
    script='''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'src'))
import gurumoji.app as a
root=Path(sys.argv[2]);a.DATA_DIRECTORY=root/'data';a.DATABASE_FILE=a.DATA_DIRECTORY/'library.sqlite3'
a.MEDIA_DIRECTORY=a.DATA_DIRECTORY/'media';a.THUMBNAIL_DIRECTORY=a.DATA_DIRECTORY/'thumbnails';a.TRAINING_AUDIO_DIRECTORY=a.DATA_DIRECTORY/'kushinada_training/audio'
a.initialize_library()
with a.database_connection() as db:
    db.execute("INSERT INTO analysis_runs(id,request_id,item_id,kind,fingerprint,input_fingerprint,snapshot_id,source_revision,analysis_revision,created_at,status) VALUES ('saved-run','saved-request','saved-item','text_analysis','fp','input','snapshot',0,0,'2026-11-03','completed')")
'''
    subprocess.run([sys.executable,'-c',script,str(baseline),str(tmp_path)],check=True,cwd=baseline)
    database=tmp_path/'data/library.sqlite3'
    with sqlite3.connect(database) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before={t:list(db.execute(f'PRAGMA table_info("{t}")')) for t in tables}
        result_before=db.execute("SELECT * FROM analysis_runs WHERE id='saved-run'").fetchone()
    a=configure(tmp_path)
    a.initialize_library()
    with sqlite3.connect(database) as db:
        after={t:list(db.execute(f'PRAGMA table_info("{t}")')) for t in tables}
        assert after==before
        assert db.execute("SELECT * FROM analysis_runs WHERE id='saved-run'").fetchone()==result_before
    c,row=create(a);response=save(c,row)
    assert response.status_code==200,response.get_json()

def test_old_metadata_is_preserved_in_transcript_json(core,tmp_path):
    c,row=create(core)
    saved={'enabled':True,'status':'completed','label_counts':{'legacy':{'neutral':1}}}
    with core.database_connection() as db:
        db.execute('UPDATE library_items SET emotion_analysis_json=? WHERE id=?',(json.dumps(saved),row['id']))
    r=save(c,row);assert r.status_code==200,r.get_json()
    current=core.library_row(row['id'])
    files=json.loads(current['files_json'])
    transcript=next(Path(p) for p in files if p.endswith('_話者分離.json'))
    assert json.loads(transcript.read_text(encoding='utf-8'))['emotion_analysis']==saved

def test_transcription_request_has_no_removed_model_options(core,monkeypatch,tmp_path):
    import threading
    import wave
    source=tmp_path/'sample.wav'
    with wave.open(str(source),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0'*3200)
    core.TOKEN_FILE.write_text(json.dumps({'huggingface_token':'test-placeholder'}),encoding='utf-8')
    load=core.load_token_config
    monkeypatch.setattr(core,'load_token_config',lambda *args,**kwargs:load(core.TOKEN_FILE))
    done=threading.Event();received=[]
    def run(job,options):
        received.append(options)
        with core.jobs_lock:
            job.status='completed'
        done.set()
    monkeypatch.setattr(core,'run_transcription_job',run)
    c=core.app.test_client()
    response=c.post('/api/jobs',data={'source_path':str(source),'device':'cpu','diarization_device':'cpu','ai_provider':'none','transcript_finishing_mode':'off','emotion_analysis':'1','finish_in_obsidian':'1'})
    assert response.status_code==202,response.get_json()
    assert done.wait(2)
    assert not hasattr(received[0],'emotion_analysis')
    assert not hasattr(received[0],'finish_in_obsidian')

if __name__=='__main__':
    root=Path(tempfile.mkdtemp(prefix='gurumoji-public-browser-'))
    a=configure(root);a.initialize_library()
    a.app.run(host='127.0.0.1',port=17864,use_reloader=False)
