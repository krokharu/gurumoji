"""Shared fixtures that keep tests away from the real runtime directory."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import app
from runtime_isolation import application_paths


def use_temporary_library(
    testcase: unittest.TestCase,
    root: Path,
    *,
    output: Path | None = None,
    initialize: bool = True,
) -> Path:
    """Point the application database (and optionally output) at ``root``.

    The original settings are restored by ``addCleanup`` so a failing test
    cannot leak its temporary paths into later tests.
    """
    database = Path(root) / "library.sqlite3"
    for key, value in application_paths(Path(root) / "isolated").items():
        if key == "DATABASE_FILE" or not hasattr(app, key):
            continue
        local_patcher = patch.object(app, key, value)
        local_patcher.start()
        testcase.addCleanup(local_patcher.stop)
    patcher = patch.object(app, "DATABASE_FILE", database)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    if output is not None:
        output_patcher = patch.object(app, "DEFAULT_OUTPUT_DIRECTORY", Path(output))
        output_patcher.start()
        testcase.addCleanup(output_patcher.stop)
    if initialize:
        app.initialize_library()
    return database
