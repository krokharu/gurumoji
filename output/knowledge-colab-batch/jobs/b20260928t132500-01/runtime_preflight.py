from importlib.metadata import version
import json
import torch
import transformers
import tokenizers

result = {
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    "cuda_available": torch.cuda.is_available(),
    "transformers": transformers.__version__,
    "tokenizers": tokenizers.__version__,
    "huggingface_hub": version("huggingface-hub"),
}
print(json.dumps(result, sort_keys=True))
assert result["cuda_available"] and "A100" in result["gpu"].upper()
assert result["transformers"] == "4.51.3"
assert result["tokenizers"] == "0.21.4"
assert result["huggingface_hub"] == "0.30.2"
