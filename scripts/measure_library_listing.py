"""Measure GET /api/library on a synthetic library (PERF-01).

Builds a throwaway library in a temporary folder (never the runtime data
directory), fills it with conversations of generated utterances, and reports
time, peak Python memory and response size for the list and a keyword search.

    python scripts/measure_library_listing.py --conversations 100 --utterances 10000
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import time
import tracemalloc
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def build(database: Path, conversations: int, utterances: int) -> None:
    import app

    app.initialize_library()
    speakers = [f"SPEAKER_{index:02d}" for index in range(6)]
    now = "2026-09-25T00:00:00+00:00"
    with closing(sqlite3.connect(database)) as connection, connection:
        for number in range(conversations):
            segments = [
                {"id": f"c{number}-s{index}", "start": index * 3.0, "end": index * 3.0 + 2.5,
                 "speaker": speakers[index % len(speakers)],
                 "text": f"会話{number}の発話{index}です。議題について意見を述べます。",
                 "emotions": {"kushinada": {"label_ja": ("中立", "喜び", "怒り")[index % 3]}}}
                for index in range(utterances)
            ]
            connection.execute(
                "INSERT INTO library_items (id, source_name, output_dir, segments_json, speaker_names_json, "
                "files_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"item-{number:04d}", f"会議{number:04d}.wav", str(database.parent / "output"),
                 json.dumps(segments, ensure_ascii=False), json.dumps({"SPEAKER_00": "司会"}, ensure_ascii=False),
                 "[]", now, now),
            )


def measure(client, url: str, repeat: int) -> dict:
    timings, size = [], 0
    for _ in range(repeat):
        started = time.perf_counter()
        response = client.get(url)
        timings.append(time.perf_counter() - started)
        if response.status_code != 200:
            raise RuntimeError(f"{url}: HTTP {response.status_code}")
        size = len(response.data)
    # Memory is traced in a separate run: tracing slows the request many times over.
    tracemalloc.start()
    client.get(url)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return {"url": url, "median_seconds": round(statistics.median(timings), 3),
            "peak_mib": round(peak / 1024 / 1024, 1), "response_kib": round(size / 1024, 1)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--conversations", type=int, default=100)
    parser.add_argument("--utterances", type=int, default=10000)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args(argv)
    import app

    with tempfile.TemporaryDirectory(prefix="gurumoji-perf-") as temporary:
        database = Path(temporary) / "library.sqlite3"
        with patch.object(app, "DATABASE_FILE", database):
            build(database, args.conversations, args.utterances)
            client = app.app.test_client()
            results = [measure(client, url, args.repeat)
                       for url in ("/api/library", "/api/library?keyword=%E8%AD%B0%E9%A1%8C")]
    print(json.dumps({"conversations": args.conversations, "utterances": args.utterances,
                      "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
