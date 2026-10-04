import subprocess, sys
steps=[[sys.executable,"-m","pip","uninstall","-y","tokenizers"],
       [sys.executable,"-m","pip","install","--no-cache-dir","--no-deps","--force-reinstall","transformers==4.51.3","tokenizers==0.21.4","huggingface-hub==0.30.2"]]
for cmd in steps:
 r=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
 print(r.stdout[-6000:])
 if r.returncode: raise RuntimeError("Pinned runtime install failed")
