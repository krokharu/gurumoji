"""Colabの取得処理と同じUI配信を、一時環境で確認する。"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from test_analysis_removal import ROOT, configure

validation=Path(__file__).resolve().parent
notebook=json.loads((ROOT/'notebooks/Gurumoji_Colab.ipynb').read_text(encoding='utf-8'))
codes=[''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code']
for code in codes:
    ast.parse(code)
tree=ast.parse(codes[0])
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prepare_colab_repository')
namespace={'subprocess':subprocess}
exec(compile(ast.Module(body=[function],type_ignores=[]),'<colab取得関数>','exec'),namespace)
expected=subprocess.check_output(['git','ls-remote','--heads','https://github.com/krokharu/Gurumoji-public.git','public/release'],text=True).split()[0]
with tempfile.TemporaryDirectory(prefix='colab-ui-check-',dir=validation) as temporary:
    temporary=Path(temporary).resolve()
    assert temporary.is_relative_to(validation)
    clone=temporary/'repo'
    prepare=namespace['prepare_colab_repository']
    assert prepare(clone,'https://github.com/krokharu/Gurumoji-public.git')==expected
    assert prepare(clone,'https://github.com/krokharu/Gurumoji-public.git')==expected
    try:
        prepare(clone,'https://github.com/krokharu/Gurumoji-public.git',[SimpleNamespace(poll=lambda:None)])
    except RuntimeError:
        pass
    else:
        raise AssertionError('実行中の更新が拒否されませんでした。')
    (clone/'README.md').write_text('local change\n',encoding='utf-8')
    try:
        prepare(clone,'https://github.com/krokharu/Gurumoji-public.git')
    except RuntimeError:
        pass
    else:
        raise AssertionError('編集済みの更新が拒否されませんでした。')
    os.environ['MOJIOKOSI_RUNTIME']='colab'
    (temporary/'app').mkdir()
    app=configure(temporary/'app')
    app.initialize_library()
    response=app.app.test_client().get('/')
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert 'vβ0.47.1' in html and '>Ollama</button>' in html
    assert 'id="show-analysis-button"' not in html
    assert 'https://colab.research.google.com' in response.headers['Content-Security-Policy']
    assets=set(re.findall(r'(?:src|href)="(/static/[^\"]+)"',html))
    checked=0
    for asset in assets:
        parts=urlsplit(asset)
        version=parse_qs(parts.query).get('v')
        if not version:
            continue
        filename=parts.path.removeprefix('/static/')
        target=clone/'src/gurumoji/static'/filename
        assert hashlib.sha256(target.read_bytes()).hexdigest()[:16]==version[0]
        assert app.app.test_client().get(asset).status_code==200
        checked+=1
    print(json.dumps({'public_head':expected,'version':'β0.47.1','code_cells':len(codes),'fresh_clone':True,'existing_checkout_update':True,'running_update_rejected':True,'local_edit_update_rejected':True,'colab_html':200,'same_release_assets':checked,'colab_iframe_policy':True},ensure_ascii=False))
