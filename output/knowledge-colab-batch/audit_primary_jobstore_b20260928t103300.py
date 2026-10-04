"""Read-only integrity audit for the configured primary Knowledge JobStore."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "output" / "knowledge-colab-batch" / "state"
STORE_ROOT = DATA_DIR / "knowledge_builder"
DB_PATH = STORE_ROOT / "state.sqlite3"
EXPECTED_JOB = "b20260928t103300-01"
EXPECTED_COMMIT = "3a477e60dc7e63a9d420e2f99bef1f342da777cb3a9c15fc5fa562e80cb6bdee"


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from gurumoji.knowledge_builder import contracts

    connection = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    job_counts = Counter(row[0] for row in connection.execute("SELECT status FROM knowledge_jobs"))
    commit_rows = connection.execute(
        "SELECT job_id,generation,manifest_sha256,manifest_json,staging_relative FROM knowledge_commits ORDER BY job_id,generation"
    ).fetchall()
    pack_count = connection.execute("SELECT COUNT(*) FROM knowledge_packs").fetchone()[0]
    new_row = connection.execute(
        "SELECT manifest_sha256 FROM knowledge_commits WHERE job_id=? AND generation=1", (EXPECTED_JOB,)
    ).fetchone()
    errors: list[str] = []
    totals = Counter()
    claims_by_expert = Counter()
    for row in commit_rows:
        job_id = row["job_id"]
        generation = row["generation"]
        raw_manifest = row["manifest_json"].encode("utf-8")
        manifest = json.loads(raw_manifest.decode("utf-8"))
        unsigned_manifest = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        if hashlib.sha256(contracts.canonical_json(unsigned_manifest)).hexdigest() != row["manifest_sha256"]:
            errors.append(f"{job_id}/{generation}: commit manifest hash")
        if contracts.canonical_json(manifest) != raw_manifest:
            errors.append(f"{job_id}/{generation}: non-canonical commit manifest")
        contracts.validate_commit(manifest)
        stage = STORE_ROOT / row["staging_relative"]
        records: list[tuple[str, dict]] = []
        for artifact in manifest["artifacts"]:
            relative = artifact["path"]
            if "\\" in relative or ":" in relative or relative.startswith("/") or ".." in relative.split("/"):
                errors.append(f"{job_id}/{generation}: unsafe artifact path")
                continue
            path = stage.joinpath(*relative.split("/"))
            if not path.is_file():
                errors.append(f"{job_id}/{generation}: missing artifact {relative}")
                continue
            data = path.read_bytes()
            if len(data) != artifact["size_bytes"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                errors.append(f"{job_id}/{generation}: artifact bytes {relative}")
                continue
            try:
                record = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                errors.append(f"{job_id}/{generation}: invalid JSON {relative}")
                continue
            if contracts.canonical_json(record) != data or record.get("schema_version") != artifact["schema_version"]:
                errors.append(f"{job_id}/{generation}: canonical/schema mismatch {relative}")
                continue
            records.append((artifact["record_type"], record))
        sources = {}
        for kind, record in records:
            if kind == "Source":
                try:
                    source = contracts.validate_source(record)
                    if source["source_id"] in sources:
                        errors.append(f"{job_id}/{generation}: duplicate source ID")
                    sources[source["source_id"]] = source
                    totals["sources"] += 1
                except Exception as exc:
                    errors.append(f"{job_id}/{generation}: invalid Source {type(exc).__name__}")
        for kind, record in records:
            if kind == "Claim":
                try:
                    contracts.validate_claim(record, sources=sources)
                    totals["claims"] += 1
                    claims_by_expert[record["expert_id"]] += 1
                except Exception as exc:
                    errors.append(f"{job_id}/{generation}: invalid Claim {type(exc).__name__}")
            elif kind != "Source":
                errors.append(f"{job_id}/{generation}: unsupported artifact type {kind}")
    connection.close()
    current_commit = new_row[0] if new_row else None
    result = {
        "database_integrity": integrity,
        "accepted_commits": len(commit_rows),
        "artifact_counts": dict(sorted(totals.items())),
        "claim_expert_coverage": dict(sorted(claims_by_expert.items())),
        "covered_expert_domains": len(claims_by_expert),
        "job_status_counts": dict(sorted(job_counts.items())),
        "knowledge_packs": pack_count,
        "new_job_commit_sha256": current_commit,
        "new_job_commit_matches_manifest": current_commit == EXPECTED_COMMIT,
        "integrity_errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if integrity != "ok" or errors or current_commit != EXPECTED_COMMIT else 0


if __name__ == "__main__":
    raise SystemExit(main())
