"""検証専用領域へ公開重みを取得する。アプリのモデル配置は変えない。"""
import json
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parents[4]
out = root / 'output/validation/obussql-alternatives-20261110'
models = {
    'reranker': ('hotchpotch/japanese-reranker-cross-encoder-xsmall-v1', '8547ac84ae5aee35387aad7000b379bd1b968dc6'),
    'compressor': ('microsoft/llmlingua-2-xlm-roberta-large-meetingbank', 'ebaba9b0e874dadd3003ffcff828e4397e568089'),
}
manifest = {}
for key, (repo, revision) in models.items():
    try:
        path = snapshot_download(repo, revision=revision, token=False,
            cache_dir=out / 'model-cache', allow_patterns=['*.json', '*.safetensors', '*.model', 'README.md', 'LICENSE*'], max_workers=2)
        manifest[key] = {'repo': repo, 'revision': revision, 'path': path}
    except Exception as exc:
        manifest[key] = {'repo': repo, 'revision': revision, 'error': str(exc)}
    (out / 'models.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(key, 'ready' if 'path' in manifest[key] else 'failed', flush=True)
