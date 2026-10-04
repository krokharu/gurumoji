import importlib.metadata
import json
import torch
import tokenizers
import transformers

print(json.dumps({
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    "cuda_available": torch.cuda.is_available(),
    "transformers": transformers.__version__,
    "tokenizers": tokenizers.__version__,
    "huggingface_hub": importlib.metadata.version("huggingface-hub"),
}, sort_keys=True))
