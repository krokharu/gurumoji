"""Lifecycle-safe polling for the researcher-owned Obsidian workbench."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ObsidianWatcher:
    workbench: Callable[[], Any]
    engine: Callable[..., dict[str, Any]]
    migrate: Callable[[Any], None]
    log_exception: Callable[[str], None]

    def start(self) -> tuple[threading.Event, threading.Thread]:
        stop = threading.Event()

        def watch() -> None:
            try:
                current = self.workbench()
                current.recover()
                self.migrate(current.database_file)
            except Exception:
                self.log_exception("Obsidian workbench recovery failed")
                stop.set()
                return
            last_theme_sync = 0.0
            while not stop.is_set():
                try:
                    current = self.workbench()
                    current.poll_once(self.engine, stop.is_set)
                    if time.monotonic() - last_theme_sync > 10:
                        current.layout.sync_themes()
                        last_theme_sync = time.monotonic()
                except Exception:
                    self.log_exception("Obsidian workbench polling failed")
                stop.wait(2)

        worker = threading.Thread(target=watch, name="obsidian-finishing", daemon=True)
        worker.start()
        return stop, worker
