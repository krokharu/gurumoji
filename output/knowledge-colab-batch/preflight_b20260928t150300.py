import importlib.metadata
import json

import torch
import tokenizers
import transformers
import huggingface_hub

if not torch.cuda.is_available():
    raise RuntimeError("CUDA is unavailable")
gpu = torch.cuda.get_device_name(0)
if "A100" not in gpu.upper():
    raise RuntimeError(f"Expected A100, got {gpu}")
versions = {
    "transformers": transformers.__version__,
    "tokenizers": tokenizers.__version__,
    "huggingface_hub": huggingface_hub.__version__,
    "autoawq": importlib.metadata.version("autoawq"),
}
expected = {
    "transformers": "4.51.3",
    "tokenizers": "0.21.4",
    "huggingface_hub": "0.30.2",
    "autoawq": "0.2.9",
}
if versions != expected:
    raise RuntimeError(f"Unexpected model stack: {versions}")
print(json.dumps({
    "status": "preflight_ok",
    "gpu": gpu,
    "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
    "cuda_version": torch.version.cuda,
    "packages": versions,
}, sort_keys=True))
