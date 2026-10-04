import importlib, importlib.metadata, subprocess, sys
for cmd in ([sys.executable, "-m", "pip", "uninstall", "-y", "tokenizers"],
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--no-deps", "tokenizers==0.21.4"]):
    run=subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    print(run.stdout[-4000:])
    if run.returncode: raise RuntimeError("Tokenizers repair command failed")
importlib.invalidate_caches()
for name in tuple(sys.modules):
    if name == "tokenizers" or name.startswith("tokenizers."):
        del sys.modules[name]
import tokenizers
print("module", tokenizers.__version__, tokenizers.__file__)
print("distribution", importlib.metadata.version("tokenizers"))
if tokenizers.__version__ != "0.21.4" or importlib.metadata.version("tokenizers") != "0.21.4":
    raise RuntimeError("Tokenizers pinned version still does not match")
