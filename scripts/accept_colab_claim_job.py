"""Accept a downloaded Colab Claim result against the local Job and Source registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji.knowledge_builder.job_store import KnowledgeJobStore  # noqa: E402
from gurumoji.knowledge_builder.transport import MAX_TOTAL_BYTES, import_colab_result  # noqa: E402


def _load_registry(path: str) -> dict[str, dict]:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("approved registry must not be a symbolic link")
    target = requested.resolve(strict=True)
    if not target.is_file():
        raise ValueError("approved registry is not a regular file")
    data = target.read_bytes()
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("approved registry exceeds the size limit")
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict) or set(value) != {"schema_version", "sources"}:
        raise ValueError("approved registry has an invalid envelope")
    if value["schema_version"] != 1 or not isinstance(value["sources"], list) or not value["sources"]:
        raise ValueError("approved registry has an invalid schema or is empty")
    sources = {}
    for source in value["sources"]:
        if not isinstance(source, dict) or not isinstance(source.get("source_id"), str):
            raise ValueError("approved registry contains an invalid Source")
        if source["source_id"] in sources:
            raise ValueError("approved registry contains duplicate Source IDs")
        sources[source["source_id"]] = source
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Configured local application data directory")
    parser.add_argument("--result-zip", required=True, help="Downloaded Colab result ZIP")
    parser.add_argument("--approved-sources-json", required=True,
                        help="Local registry emitted beside the uploaded Job bundle")
    args = parser.parse_args()
    try:
        result_path = Path(args.result_zip).expanduser()
        if result_path.is_symlink():
            raise ValueError("result ZIP must not be a symbolic link")
        result_path = result_path.resolve(strict=True)
        if not result_path.is_file() or result_path.stat().st_size > MAX_TOTAL_BYTES:
            raise ValueError("result ZIP is missing or exceeds the size limit")
        result_bytes = result_path.read_bytes()
        source_registry = _load_registry(args.approved_sources_json)
        accepted = import_colab_result(
            KnowledgeJobStore(args.data_dir), result_bytes, approved_sources=source_registry,
        )
        print(json.dumps({
            "status": "accepted_unapproved_candidate_commit",
            "job_id": accepted["job_id"],
            "generation": accepted["generation"],
            "commit_sha256": accepted["manifest_sha256"],
            "result_zip_sha256": hashlib.sha256(result_bytes).hexdigest(),
        }, sort_keys=True))
    except (OSError, ValueError, LookupError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
