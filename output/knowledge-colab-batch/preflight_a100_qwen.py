import importlib.metadata as metadata
import json

import torch
import transformers
import tokenizers
import huggingface_hub

print(json.dumps({
    "gpu_available": torch.cuda.is_available(),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    "transformers_module": transformers.__version__,
    "transformers_distribution": metadata.version("transformers"),
    "tokenizers_module": tokenizers.__version__,
    "tokenizers_distribution": metadata.version("tokenizers"),
    "huggingface_hub_module": huggingface_hub.__version__,
    "huggingface_hub_distribution": metadata.version("huggingface-hub"),
}, sort_keys=True))
