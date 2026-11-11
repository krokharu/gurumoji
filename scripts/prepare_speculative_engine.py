"""公式llama.cppの固定リリースを検証領域へ取得し、配布hashを照合する。"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parents[4]
out = root / 'output/validation/obussql-speculative-20261110'
tag = 'b9553'
release = json.load(urllib.request.urlopen('https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/' + tag))
names = ['llama-b9553-bin-win-cuda-13.3-x64.zip', 'cudart-llama-bin-win-cuda-13.3-x64.zip']
assets = [a for a in release['assets'] if a['name'] in names]
assert len(assets) == 2
def get(asset):
    path = out / asset['name']
    if not path.exists():
        urllib.request.urlretrieve(asset['browser_download_url'], path)
    with path.open('rb') as handle:
        sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    assert asset['size'] == path.stat().st_size
    if asset.get('digest'):
        assert asset['digest'] == 'sha256:' + sha
    target = (out / 'engine' / tag).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            assert (target / name).resolve().is_relative_to(target)
        archive.extractall(target)
    return {'name': asset['name'], 'url': asset['browser_download_url'], 'sha256': sha, 'expected_digest': asset.get('digest')}
with ThreadPoolExecutor(max_workers=2) as pool:
    manifest = {'tag': tag, 'target_commitish': release['target_commitish'], 'assets': list(pool.map(get, assets))}
manifest['draft'] = {'repo': 'ensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant', 'revision': 'e9aaf2d12229b0b11d7e8b2c8821c5648c48334e',
    'sha256': '25f143b4c15b20cd04216e35e99bd7a56afc6f65e7a4e090a3e20091bb590cbb', 'license': 'Apache-2.0'}
(out / 'engine-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2), flush=True)
