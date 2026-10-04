from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "output" / "knowledge-colab-batch" / "state" / "knowledge_builder"
DB = STORE / "state.sqlite3"


def main() -> None:
    connection = sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    commits = connection.execute(
        "SELECT job_id,generation,manifest_json,staging_relative FROM knowledge_commits ORDER BY accepted_at"
    ).fetchall()
    records = []
    for row in commits:
        manifest = json.loads(row["manifest_json"])
        stage = STORE / row["staging_relative"]
        for artifact in manifest["artifacts"]:
            if artifact["record_type"] != "Claim":
                continue
            claim = json.loads((stage / artifact["path"]).read_text(encoding="utf-8"))
            records.append((claim["expert_id"], claim["claim"], row["job_id"]))
    connection.close()
    for expert, claim, job_id in sorted(records):
        print(json.dumps({"expert_id": expert, "job_id": job_id, "claim": claim}, ensure_ascii=False))


if __name__ == "__main__":
    main()
