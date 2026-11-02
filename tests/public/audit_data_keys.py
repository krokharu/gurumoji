"""配布物・秘密値の応答・起動時データ更新を一時データだけで監査する。"""
from pathlib import Path
import io
import json
import subprocess
import tempfile
import zipfile

import test_analysis_removal as harness

root=harness.ROOT
# tarが既定なので、配布ZIP形式を明示して検査する。
archive=subprocess.check_output(['git','archive','--format=zip','HEAD'],cwd=root)
with zipfile.ZipFile(io.BytesIO(archive)) as package:
    files=[n for n in package.namelist() if not n.endswith('/')]
    forbidden=[n for n in files if set(Path(n).parts)&{'runtime','.env','.codex','.obsidian','uploads','backups','models'}
               or Path(n).name=='tokens.json' or Path(n).suffix.lower() in {'.db','.sqlite','.sqlite3','.pem','.key','.pfx','.wav','.mp3','.mp4'}]
    examples=json.loads(package.read('config/tokens.example.json'))
    secrets={k:bool(v) for k,v in examples.items() if any(w in k.lower() for w in ('key','token','password','secret'))}
    outputs=sum(bool(c.get('outputs')) or c.get('execution_count') is not None
                for n in files if n.endswith('.ipynb')
                for c in json.loads(package.read(n)).get('cells',[]) if c.get('cell_type')=='code')
    print(json.dumps({'source_zip_files':len(files),'forbidden_files':forbidden,
                      'example_credential_fields_nonempty':secrets,'executed_notebook_cells':outputs},ensure_ascii=False))
    assert not forbidden and not any(secrets.values()) and outputs==0

with tempfile.TemporaryDirectory(prefix='gurumoji-key-audit-') as temporary:
    a=harness.configure(Path(temporary));a.initialize_library()
    from gurumoji.services.ai.settings import TokenConfig
    from gurumoji.services import data_backup
    markers={k:'audit-placeholder-'+str(i) for i,k in enumerate(('huggingface_token','openai_api_key','google_api_key','lmstudio_api_key','typesafe_api_key'))}
    config=TokenConfig(**markers)
    a.load_token_config=lambda *args,**kwargs:config
    a.lmstudio_connection_status=lambda *_:{'reachable':False,'message':'audit'}
    a.get_machine_profile=lambda:{'status':'audit'}
    c=a.app.test_client();response=c.get('/api/config');body=response.get_data(as_text=True)
    assert response.status_code==200
    assert all(value not in body for value in markers.values())
    private_urls=['/config/tokens.json','/.env','/static/../../config/tokens.json']
    denied={url:c.get(url).status_code for url in private_urls}
    assert all(code==404 for code in denied.values())
    print(json.dumps({'config_status':response.status_code,'credential_values_in_response':False,'private_file_routes':denied},ensure_ascii=False))

    c,row=harness.create(a)
    response=harness.save(c,row);assert response.status_code==200
    with a.database_connection() as db:
        profile={'session_type':'focus_group','field_notes':'audit-note','confidentiality_notes':'audit-legacy-value'}
        db.execute('UPDATE library_items SET session_profile_json=? WHERE id=?',(json.dumps(profile),row['id']))
        db.execute("INSERT INTO speaker_registry(id,display_name,pseudonym,tags_json,attributes_json,notes,created_at,updated_at) VALUES ('audit-speaker','audit-name','audit-alias','[\"audit-tag\"]','{\"audit\":\"value\"}','audit-note','2026-11-03','2026-11-03')")
        before=dict(db.execute('SELECT * FROM library_items WHERE id=?',(row['id'],)).fetchone())
        speaker_before=dict(db.execute("SELECT * FROM speaker_registry WHERE id='audit-speaker'").fetchone())
    a.initialize_application()
    try:
        with a.database_connection() as db:
            after=dict(db.execute('SELECT * FROM library_items WHERE id=?',(row['id'],)).fetchone())
            speaker_after=dict(db.execute("SELECT * FROM speaker_registry WHERE id='audit-speaker'").fetchone())
        changed=[k for k in before if before[k]!=after[k]]
        removed_profile_keys=sorted(set(json.loads(before['session_profile_json']))-set(json.loads(after['session_profile_json'])))
        print(json.dumps({'startup_changed_item_columns':changed,'startup_removed_profile_keys':removed_profile_keys,
                          'transcript_preserved':before['segments_json']==after['segments_json'],
                          'speaker_name_alias_tags_notes_preserved':speaker_before==speaker_after},ensure_ascii=False))
        assert changed==['session_profile_json'] and removed_profile_keys==['confidentiality_notes']
        assert speaker_before==speaker_after
        (a.DATA_DIRECTORY/'.env').write_text('AUDIT_ONLY=placeholder',encoding='utf-8')
        (a.DATA_DIRECTORY/'config').mkdir()
        (a.DATA_DIRECTORY/'config/tokens.json').write_text(json.dumps(markers),encoding='utf-8')
        result=a.create_data_backup()
        names=[f['path'] for f in result['files']]
        leaked=[n for n in names if n.endswith(('tokens.json','.env'))]
        assert not leaked
        print(json.dumps({'credential_files_in_backup':leaked,'backup_verification_errors':data_backup.verify_backup(result['path'])},ensure_ascii=False))
    finally:
        a.application_lifecycle().shutdown()
