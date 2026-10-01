"""Prepare one rights-approved, base-expert Claim-generation job for user-started Colab."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji.knowledge_builder.colab_job_builder import (  # noqa: E402
    build_colab_claim_job,
    write_bundle_files,
)
from gurumoji.knowledge_builder.colab_qwen3 import (  # noqa: E402
    MODEL_REFERENCE,
    load_base_expert_definition,
)
from gurumoji.knowledge_builder.job_store import KnowledgeJobStore  # noqa: E402


def _read_json(path: str, *, max_bytes: int) -> Any:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("input JSON must not be a symbolic link")
    target = requested.resolve(strict=True)
    if not target.is_file():
        raise ValueError("input JSON must be a regular local file")
    data = target.read_bytes()
    if len(data) > max_bytes:
        raise ValueError("input JSON exceeds the configured size limit")
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("input JSON is invalid") from exc


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source = _read_json(args.source_json, max_bytes=2 * 1024 * 1024)
    excerpt = _read_json(args.excerpt_json, max_bytes=128 * 1024)
    registry_value = _read_json(args.approved_sources_json, max_bytes=8 * 1024 * 1024)
    if (not isinstance(registry_value, dict) or set(registry_value) != {"schema_version", "sources"} or
            registry_value.get("schema_version") != 1 or not isinstance(registry_value.get("sources"), list)):
        raise ValueError("approved Source registry must contain schema_version=1 and a sources array")
    approved_sources = {item.get("source_id"): item for item in registry_value["sources"]
                        if isinstance(item, dict) and isinstance(item.get("source_id"), str)}
    if len(approved_sources) != len(registry_value["sources"]):
        raise ValueError("approved Source registry has invalid or duplicate Source IDs")

    output_path = Path(args.output).expanduser().absolute()
    registry_path = output_path.with_name(output_path.stem + ".local-approved-sources.json")
    expert_definition = load_base_expert_definition(args.expert_id)
    store = KnowledgeJobStore(args.data_dir)
    job, bundle_bytes, registry_bytes = build_colab_claim_job(
        store,
        expert_definition=expert_definition,
        source=source,
        excerpt=excerpt,
        approved_sources=approved_sources,
        ttl_seconds=args.ttl_minutes * 60,
        retry_limit=args.retry_limit,
        job_id=args.job_id,
    )
    write_bundle_files(output_path, registry_path, bundle_bytes=bundle_bytes, registry_bytes=registry_bytes)
    return {
        "status": "ready_for_user_started_colab",
        "job_id": job["job_id"],
        "generation": job["generation"],
        "expert_id": args.expert_id,
        "source_id": source.get("source_id"),
        "model_reference": MODEL_REFERENCE,
        "deadline": job["deadline"],
        "bundle_file_name": output_path.name,
        "bundle_size_bytes": len(bundle_bytes),
        "bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "local_registry_file_name": registry_path.name,
        "local_registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True,
                        help="Configured local application data directory (not an Obsidian Vault)")
    parser.add_argument("--expert-id", required=True,
                        help="Base Expert ID from the Software Vault")
    parser.add_argument("--source-json", required=True, help="Approved Source record JSON")
    parser.add_argument("--excerpt-json", required=True, help="One hash-bound SourceExcerpt JSON")
    parser.add_argument("--approved-sources-json", required=True,
                        help="Independent local approved registry: {schema_version: 1, sources: [...]}")
    parser.add_argument("--output", required=True, help="New local .zip path to upload manually to Drive")
    parser.add_argument("--ttl-minutes", type=int, default=55, choices=range(1, 56))
    parser.add_argument("--retry-limit", type=int, default=2, choices=range(0, 3))
    parser.add_argument("--job-id", help="Optional stable job ID; otherwise generated locally")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args), ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, LookupError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
