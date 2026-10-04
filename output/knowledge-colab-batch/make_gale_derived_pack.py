"""Export candidate records without article-body excerpts or request payloads."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    batch_id = sys.argv[1] if len(sys.argv) > 1 else "b20260927t204359"
    source_id = sys.argv[2] if len(sys.argv) > 2 else "LIT-gale-2013-framework"
    label = "Mayring" if "mayring" in source_id else "Gale"
    output = HERE / f"Gurumoji_{label}_Derived_Candidates_{batch_id}.zip"
    progress = json.loads((HERE / f"{batch_id}-progress.json").read_text(encoding="utf-8"))
    files: dict[str, bytes] = {}
    claims = 0
    for job_id, job in sorted(progress["jobs"].items()):
        assert job["status"] == "accepted_unapproved_candidate_commit"
        result = HERE / "jobs" / job_id / f"Gurumoji_Result_{job_id}_g1.zip"
        assert sha(result.read_bytes()) == job["result_zip_sha256"]
        with zipfile.ZipFile(BytesIO(result.read_bytes())) as archive:
            for name in archive.namelist():
                if not name.startswith(("artifacts/claims/", "artifacts/sources/")):
                    continue
                value = json.loads(archive.read(name))
                if name.startswith("artifacts/claims/"):
                    assert value["status"] == "candidate"
                    assert value["evidence"][0]["source_id"] == source_id
                    claims += 1
                else:
                    assert value["source_id"] == source_id
                    assert "text" not in value and "excerpt" not in value
                files[f"jobs/{job_id}/{name}"] = archive.read(name)
    manifest = {"schema_version": 1, "kind": "derived_unreviewed_candidates",
                "status": "not_approved_for_release", "batch_id": batch_id,
                "source_id": source_id,
                "job_count": len(progress["jobs"]), "claim_count": claims,
                "article_body_included": False,
                "files_sha256": {name: sha(data) for name, data in sorted(files.items())}}
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            member = zipfile.ZipInfo(name, date_time=(2026, 9, 27, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data)
    print(json.dumps({"path": str(output), "claim_count": claims,
                      "size_bytes": output.stat().st_size,
                      "sha256": sha(output.read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
