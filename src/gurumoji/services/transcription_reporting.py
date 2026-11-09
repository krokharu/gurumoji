"""Thread-safe reporting boundary for one transcription pipeline run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TranscriptionReporter:
    """Own mutable job status through the application-provided synchronization."""

    job: Any
    update_job: Callable[..., None]
    jobs_lock: Any
    normalize_usage: Callable[[Any], dict[str, Any]]
    merge_usage: Callable[[Any, Any], dict[str, Any]]

    def status(self, message: str) -> None:
        self.update_job(self.job, message=message)

    def progress(self, value: int) -> None:
        self.update_job(self.job, progress=value)

    def stage(self, key: str, label: str, value: int = 0) -> None:
        # 工程の完了は全体の割合から推測せず、工程自身の完了通知を記録する。
        with self.jobs_lock:
            history = [dict(item) for item in getattr(self.job, "stage_history", [])]
            current = next((item for item in history if item["key"] == self.job.stage), None)
            if key in {"failed", "cancelled"}:
                if current and current["status"] != "completed":
                    current["status"] = key
                else:
                    history.append({"key": key, "label": label, "progress": max(0, min(100, value)), "status": key})
            elif key == "completed":
                for item in history:
                    if item["status"] not in {"failed", "cancelled"}:
                        item["progress"] = 100
                        item["status"] = "completed"
            else:
                for item in history:
                    if item["status"] == "running" and item["key"] != key:
                        item["status"] = "pending"
                entry = next((item for item in history if item["key"] == key), None)
                if entry is None:
                    entry = {"key": key}
                    history.append(entry)
                entry.update(label=label, progress=max(0, min(100, value)), status="completed" if value >= 100 else "running")
            self.update_job(
                self.job, stage=key, stage_label=label, stage_progress=value,
            )
            self.job.stage_history = history

    def record_ai_usage(self, sample: dict[str, Any]) -> None:
        usage = self.normalize_usage(sample)
        if not usage:
            return
        with self.jobs_lock:
            current = self.normalize_usage(self.job.ai_usage)
            if current and current["provider"] != usage["provider"]:
                current = {}
            self.job.ai_usage = self.merge_usage(current, usage)

    def check_cancelled(self) -> None:
        if self.job.cancel_event.is_set():
            raise InterruptedError("処理を中止しました。")

    def warning(self, message: str) -> None:
        with self.jobs_lock:
            current = self.job.output_warning.strip()
            self.job.output_warning = f"{current}\n{message}".strip() if current else message
        self.status(message)
