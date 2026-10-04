import importlib.metadata
import json
import tokenizers
import transformers

packages = ("autoawq", "transformers", "tokenizers", "huggingface-hub", "torch")
versions = {}
for package in packages:
    try:
        versions[package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        versions[package] = None
print(json.dumps(versions, sort_keys=True))
print(json.dumps({"tokenizers_imported": tokenizers.__version__, "tokenizers_file": tokenizers.__file__,
                  "transformers_imported": transformers.__version__}, sort_keys=True))
