"""Create one deadline-bound Colab job per reviewed source/expert pair."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PILOT = ROOT / "output/knowledge-colab-instruction-pilot"
BATCH_ID = "b" + datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")

PAIRS = [
    ("LIT-byrne-2022-reflexive-ta", "exp-thematic-analysis"),
    ("LIT-gilardi-2023-llm-annotation", "exp-qualitative-content-analysis"),
    ("LIT-gilardi-2023-llm-annotation", "exp-thematic-analysis"),
    ("LIT-gilardi-2023-llm-annotation", "exp-framework-method"),
    ("LIT-gilardi-2023-llm-annotation", "exp-scat"),
    ("LIT-gilardi-2023-llm-annotation", "exp-m-gta"),
    ("LIT-gilardi-2023-llm-annotation", "exp-focus-group-interaction"),
    ("LIT-hermann-2024-fg-interaction-coding", "exp-thematic-analysis"),
]


def main() -> None:
    pairs = [(source_id, expert_id, None) for source_id, expert_id in PAIRS]
    if len(sys.argv) == 2 and sys.argv[1] == "--retry-rejected":
        pairs = [(PAIRS[index][0], PAIRS[index][1], None) for index in (0, 2, 4)]
    elif len(sys.argv) == 2 and sys.argv[1] == "--gale":
        pairs = [("LIT-gale-2013-framework", "exp-framework-method", f"stage-{number}")
                 for number in range(1, 8)] + [
                     ("LIT-gale-2013-framework", "exp-framework-method", "summary"),
                     ("LIT-gale-2013-framework", "exp-cross-session-comparison", "stage-6"),
                     ("LIT-gale-2013-framework", "exp-cross-session-comparison", "summary"),
                 ]
    elif len(sys.argv) == 2 and sys.argv[1] == "--mayring":
        pairs = [("LIT-mayring-2000-qca", "exp-qualitative-content-analysis", anchor)
                 for anchor in ("principles", "inductive", "deductive", "integration", "limits")]
        pairs.append(("LIT-mayring-2000-qca", "exp-thematic-analysis", "limits"))
    jobs = []
    for index, (source_id, expert_id, anchor_id) in enumerate(pairs, 1):
        inputs = PILOT if source_id.startswith("LIT-hermann-") else HERE / "inputs" / source_id
        job_id = f"{BATCH_ID}-{index:02d}"
        target = HERE / "jobs" / job_id
        target.mkdir(parents=True, exist_ok=False)
        bundle = target / f"Gurumoji_Job_{job_id}_g1.zip"
        command = [
            sys.executable, str(ROOT / "scripts/prepare_colab_claim_job.py"),
            "--data-dir", str(HERE / "state"),
            "--expert-id", expert_id,
            "--source-json", str(inputs / "source.json"),
            "--excerpt-json", str(inputs / (f"excerpt-{anchor_id}.json" if anchor_id else "excerpt.json")),
            "--approved-sources-json", str(inputs / "approved_sources.json"),
            "--output", str(bundle), "--job-id", job_id, "--ttl-minutes", "55",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"{job_id}: {completed.stdout} {completed.stderr}")
        record = json.loads(completed.stdout)
        record.update({"bundle_path": str(bundle.relative_to(ROOT)).replace("\\", "/"),
                       "source_id": source_id, "expert_id": expert_id, "anchor_id": anchor_id})
        jobs.append(record)
    manifest = {"batch_id": BATCH_ID, "created_at": datetime.now(timezone.utc).isoformat(),
                "jobs": jobs}
    path = HERE / f"{BATCH_ID}.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({"batch_id": BATCH_ID, "jobs": len(jobs), "manifest": str(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
