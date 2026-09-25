"""Lifecycle-safe polling for the researcher-owned Obsidian workbench."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


def describe_error(error: BaseException) -> str:
    """A short reason for the screen: the error kind and message, without file paths."""
    if isinstance(error, OSError):
        detail = error.strerror or ""
    else:
        detail = str(error).splitlines()[0] if str(error) else ""
    return f"{type(error).__name__}: {detail[:200]}".rstrip(": ")


class WatcherStatus:
    """Whether the Obsidian watcher runs and why it stopped (OBS-09); never note text."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value = {"state": "not_started", "reason": "", "since": "",
                       "last_error": "", "last_error_at": ""}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def set(self, state: str, reason: str = "") -> None:
        with self._lock:
            self._value.update(state=state, reason=reason, since=self._now())

    def poll_failed(self, error: BaseException) -> None:
        with self._lock:
            self._value.update(last_error=describe_error(error), last_error_at=self._now())

    def poll_succeeded(self) -> None:
        with self._lock:
            self._value.update(last_error="", last_error_at="")

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return dict(self._value)


@dataclass(frozen=True)
class ObsidianWatcher:
    workbench: Callable[[], Any]
    engine: Callable[..., dict[str, Any]]
    migrate: Callable[[Any], None]
    log_exception: Callable[[str], None]
    status: WatcherStatus = field(default_factory=WatcherStatus)

    def start(self) -> tuple[threading.Event, threading.Thread]:
        stop = threading.Event()

        def watch() -> None:
            self.status.set("starting")
            try:
                current = self.workbench()
                current.recover()
                self.migrate(current.database_file)
            except Exception as exc:
                self.log_exception("Obsidian workbench recovery failed")
                self.status.set("stopped", "起動時の復旧・移行に失敗したため、Obsidianの操作ノートを監視していません。"
                                           f"原因: {describe_error(exc)}。ログを確認し、アプリを再起動してください。")
                stop.set()
                return
            self.status.set("running")
            last_theme_sync = 0.0
            while not stop.is_set():
                try:
                    current = self.workbench()
                    current.poll_once(self.engine, stop.is_set)
                    if time.monotonic() - last_theme_sync > 10:
                        current.layout.sync_themes()
                        last_theme_sync = time.monotonic()
                    self.status.poll_succeeded()
                except Exception as exc:
                    self.log_exception("Obsidian workbench polling failed")
                    self.status.poll_failed(exc)
                stop.wait(2)
            self.status.set("stopped", "アプリの終了により停止しました。")

        worker = threading.Thread(target=watch, name="obsidian-finishing", daemon=True)
        worker.start()
        return stop, worker
