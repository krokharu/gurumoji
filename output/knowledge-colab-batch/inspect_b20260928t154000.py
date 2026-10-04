import importlib.metadata
import json
import torch
import tokenizers
import transformers
import huggingface_hub

print(json.dumps({
    "cuda_available": torch.cuda.is_available(),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else None,
    "cuda_version": torch.version.cuda,
    "packages": {
        "transformers": transformers.__version__,
        "tokenizers": tokenizers.__version__,
        "huggingface_hub": huggingface_hub.__version__,
        "autoawq": importlib.metadata.version("autoawq"),
    },
}, sort_keys=True))
