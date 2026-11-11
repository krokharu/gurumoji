"""Variable LM Studio placement: load the model with the smallest context a task
needs and the most GPU offload that fits the free video memory.

A larger context costs video memory (about 0.6 GiB per 4K tokens for a 12B
model), and layers left on the CPU make every token slow. Short tasks such as
outline windows therefore run fully on the GPU, and only a task that needs a
long context trades some offload for it. A reload takes about a minute, so the
model is reloaded only when the loaded context is too small or a smaller
context would move layers back to the GPU.

Opt-in: another program may be using the same LM Studio, and a reload drops
its loaded instance. Measurements come from ``lms --estimate-only`` and
``nvidia-smi``; without an NVIDIA GPU LM Studio picks the offload itself.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
import urllib.request

CONTEXT_STEPS = (8192, 12288, 16384, 20480, 24576, 32768)
OFFLOADS = ("max", "0.95", "0.9", "0.85", "0.8", "0.7", "0.6", "0.5")
HEADROOM_GIB = 0.8
MARGIN = 0.1


@dataclass(frozen=True)
class Placement:
    context: int
    gpu: str
    estimate_gib: float | None


def required_context(input_tokens: int, output_tokens: int) -> int:
    """The smallest context step holding the input, the output reserve and a margin."""
    needed = math.ceil((input_tokens + output_tokens) * (1 + MARGIN))
    for step in CONTEXT_STEPS:
        if step >= needed:
            return step
    raise ValueError(f"required context {needed} exceeds {CONTEXT_STEPS[-1]}")


def choose(context: int, budget_gib: float | None, estimate: Callable[[str, int], float]) -> Placement:
    """The most offload at this context that fits the budget; LM Studio's choice without a budget."""
    if budget_gib is None:
        return Placement(context, "auto", None)
    for gpu in OFFLOADS:
        gib = estimate(gpu, context)
        if gib <= budget_gib:
            return Placement(context, gpu, gib)
    raise RuntimeError(f"no GPU offload fits {budget_gib:.2f} GiB at context {context}")


def keep_current(loaded_context: int | None, recorded: dict | None, required: int, target: Placement) -> bool:
    """Keep a loaded instance that is large enough and already as fast as the target placement."""
    if loaded_context is None or loaded_context < required:
        return False
    if recorded is None or recorded.get("context") != loaded_context:
        return False  # placed by someone else: its offload is unknown
    return recorded.get("gpu") == "max" or (loaded_context == target.context and recorded.get("gpu") == target.gpu)


class LMStudioPlacement:
    def __init__(self, *, lms: str, endpoint: str, state_path: Path,
                 run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 fetch: Callable[[str], dict] | None = None):
        self.lms, self.endpoint, self.state_path = lms, endpoint.rstrip("/"), Path(state_path)
        self.run = run
        self.fetch = fetch or (lambda url: json.load(urllib.request.urlopen(url, timeout=10)))
        self._estimates: dict[tuple[str, str, int], float] = {}

    def _lms(self, *args: str, timeout: int = 300) -> str:
        done = self.run([self.lms, *args], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=timeout)
        if done.returncode != 0:
            raise RuntimeError(f"lms {args[0]} failed with exit code {done.returncode}")
        return (done.stdout or "") + (done.stderr or "")  # lms prints its reports on stderr

    def estimate(self, model: str, gpu: str, context: int) -> float:
        key = (model, gpu, context)
        if key not in self._estimates:
            out = self._lms("load", model, "--gpu", gpu, "-c", str(context), "--estimate-only", "-y")
            match = re.search(r"Estimated GPU Memory:\s*([0-9.]+)\s*GiB", out)
            if not match:
                raise RuntimeError("lms estimate did not report GPU memory")
            self._estimates[key] = float(match.group(1))
        return self._estimates[key]

    def loaded_context(self, model: str) -> int | None:
        for entry in self.fetch(self.endpoint + "/api/v1/models").get("models", []):
            if entry.get("key") == model and entry.get("loaded_instances"):
                return int(entry["loaded_instances"][0]["config"]["context_length"])
        return None

    def vram_budget(self) -> float | None:
        """Free video memory minus headroom, measured with the model unloaded; None without nvidia-smi."""
        try:
            done = self.run(["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if done.returncode != 0 or not done.stdout.strip():
            return None
        total, used = (float(value) for value in done.stdout.splitlines()[0].split(","))
        return (total - used) / 1024 - HEADROOM_GIB

    def _recorded(self, model: str) -> dict | None:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8")).get(model)
        except (OSError, ValueError):
            return None

    def _record(self, model: str, placement: Placement) -> None:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data[model] = asdict(placement)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def ensure(self, model: str, input_tokens: int, output_tokens: int) -> dict[str, Any]:
        """Make the loaded instance fit this task; returns what was kept or loaded."""
        required = required_context(input_tokens, output_tokens)
        loaded = self.loaded_context(model)
        recorded = self._recorded(model)
        # Keeping needs no measurement when the current instance is already ideal.
        if loaded is not None and recorded and keep_current(loaded, recorded, required,
                                                            Placement(required, recorded.get("gpu", ""), None)):
            return {"action": "kept", "required": required, **recorded}
        if loaded is not None:
            self._lms("unload", model)
        budget, failure = None, None
        try:
            budget = self.vram_budget()
            target = choose(required, budget, lambda gpu, context: self.estimate(model, gpu, context))
            self._load(model, target)
        except Exception as exc:
            # Never leave the model unloaded: fall back to LM Studio's own placement.
            failure, target = type(exc).__name__, Placement(required, "auto", None)
            self._load(model, target)
        if (self.loaded_context(model) or 0) < required:
            raise RuntimeError("LM Studio did not load the requested context")
        self._record(model, target)
        return {"action": "loaded" if failure is None else "loaded_with_lmstudio_placement",
                "required": required, "budget_gib": budget, **asdict(target),
                **({"placement_failure": failure} if failure else {})}

    def _load(self, model: str, target: Placement) -> None:
        args = ["load", model, "-c", str(target.context), "--identifier", model, "-y"]
        if target.gpu != "auto":
            args[2:2] = ["--gpu", target.gpu]
        self._lms(*args, timeout=600)
