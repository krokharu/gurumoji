import importlib.metadata as m, sys, torch, transformers, tokenizers, huggingface_hub
print("python",sys.version)
print("gpu",torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CUDA unavailable")
print("transformers",transformers.__version__)
print("tokenizers",tokenizers.__version__,"dist",m.version("tokenizers"))
print("hub",huggingface_hub.__version__,"dist",m.version("huggingface-hub"))
