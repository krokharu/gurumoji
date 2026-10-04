import importlib.metadata as m, sys
import transformers, tokenizers, huggingface_hub
for n,v in [("python",sys.version),("transformers",transformers.__version__),("tokenizers-module",tokenizers.__version__),("tokenizers-dist",m.version("tokenizers")),("huggingface_hub-module",huggingface_hub.__version__),("huggingface-hub-dist",m.version("huggingface-hub"))]: print(n, v)
print("tokenizers-file",tokenizers.__file__)
print("transformers-file",transformers.__file__)
