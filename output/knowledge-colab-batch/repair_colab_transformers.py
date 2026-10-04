import importlib
import subprocess
import sys

subprocess.run([
    sys.executable, "-m", "pip", "install", "--no-cache-dir", "--no-deps",
    "--force-reinstall", "transformers==4.51.3", "tokenizers==0.21.4",
], check=True, timeout=300)
for module_name in tuple(sys.modules):
    if (module_name == "transformers" or module_name.startswith("transformers.") or
            module_name == "tokenizers" or module_name.startswith("tokenizers.") or
            module_name == "awq" or module_name.startswith("awq.")):
        del sys.modules[module_name]
transformers = importlib.import_module("transformers")
print("transformers", transformers.__version__, transformers.__file__)
tokenizers = importlib.import_module("tokenizers")
print("tokenizers", tokenizers.__version__)
from transformers.utils import is_flax_available
print("is_flax_available", callable(is_flax_available))
from awq import AutoAWQForCausalLM
print("autoawq_import", AutoAWQForCausalLM.__module__)
