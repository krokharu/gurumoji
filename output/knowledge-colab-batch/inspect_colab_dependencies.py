import importlib.metadata as metadata
import sys
import traceback

print("python", sys.version)
for package in ("torch", "transformers", "autoawq", "accelerate", "flax"):
    try:
        print(package, metadata.version(package))
    except metadata.PackageNotFoundError:
        print(package, "not-installed")
try:
    import transformers
    print("transformers_path", transformers.__file__)
    print("utils_has_is_flax_available", hasattr(transformers.utils, "is_flax_available"))
except Exception:
    traceback.print_exc(limit=4)
try:
    from awq import AutoAWQForCausalLM
    print("autoawq_import", "ok", AutoAWQForCausalLM.__module__)
except Exception:
    traceback.print_exc(limit=8)
