"""Environment-variable readers shared by the application and its services.

These live outside ``app`` so service modules can read tuning knobs without
importing the composition root, and so ``app`` can use them while building its
module-level constants.
"""

from __future__ import annotations

import os


def positive_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


DEFAULT_PORT = 7860


def app_port() -> int:
    """MOJIOKOSI_PORT when it is a valid port, else the default."""
    raw = os.environ.get("MOJIOKOSI_PORT", "").strip()
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= 65535 else DEFAULT_PORT


def local_app_url() -> str:
    """The one address written into notes and saved runs (ARCH-03)."""
    return f"http://127.0.0.1:{app_port()}"


def env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}
