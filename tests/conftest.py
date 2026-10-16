"""Isolate before collection imports app; isolate constants again per test."""
import atexit
import os
import tempfile
import sys

import pytest
from runtime_isolation import configure_environment, application_paths, protect_runtime

_session = tempfile.TemporaryDirectory(prefix="gurumoji-pytest-")
atexit.register(_session.cleanup)
configure_environment(_session.name)
protect_runtime()


def pytest_configure(config):
    for marker in ("slow: takes over ten seconds", "browser: requires a real browser",
                   "real_model: invokes an actual model or external provider"):
        config.addinivalue_line("markers", marker)


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    configure_environment(tmp_path)
    for name in ("app", "gurumoji.app"):
        module = sys.modules.get(name)
        if module:
            for key, value in application_paths(tmp_path).items():
                # setUpClass may deliberately own a shared synthetic DB.
                if hasattr(module, key) and str(getattr(module,key)).startswith(_session.name):
                    monkeypatch.setattr(module, key, value)
    yield
